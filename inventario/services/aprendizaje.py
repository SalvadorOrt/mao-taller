# inventario/services/aprendizaje.py

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from inventario.models import (
    AliasProducto,
    AprendizajeProducto,
    SugerenciaProducto,
)

from .normalizacion import (
    normalizar_codigo,
    normalizar_texto,
)


CERO = Decimal("0.00")
CIEN = Decimal("100.00")
DOS_DECIMALES = Decimal("0.01")


class AprendizajeProductoService:
    """
    Registra decisiones confirmadas por el usuario.

    Este servicio no genera sugerencias.

    Su responsabilidad es convertir una confirmación humana
    en memoria reutilizable para el sistema mediante:

    - AprendizajeProducto
    - AliasProducto

    Puede aprender desde:

    - creación individual;
    - código confirmado;
    - mostrador;
    - factura XML;
    - factura manual;
    - importación;
    - corrección de sugerencias.
    """

    ORIGENES_VALIDOS = {
        "FACTURA",
        "INDIVIDUAL",
        "CODIGO",
        "MOSTRADOR",
        "CORRECCION",
        "IMPORTACION",
    }

    # =====================================================
    # VALIDACIONES BÁSICAS
    # =====================================================

    @staticmethod
    def _decimal_confianza(valor):
        """
        Convierte y valida el porcentaje de confianza.
        """

        if valor is None:
            return CIEN

        try:
            confianza = Decimal(str(valor))

        except (
            InvalidOperation,
            ValueError,
            TypeError,
        ) as error:
            raise ValidationError(
                "La confianza debe ser un número válido."
            ) from error

        if confianza < CERO or confianza > CIEN:
            raise ValidationError(
                "La confianza debe estar entre 0 y 100."
            )

        return confianza.quantize(
            DOS_DECIMALES
        )

    @classmethod
    def _validar_origen(cls, origen):
        """
        Normaliza y valida el origen del aprendizaje.
        """

        origen = str(
            origen or "INDIVIDUAL"
        ).strip().upper()

        if origen not in cls.ORIGENES_VALIDOS:
            raise ValidationError(
                f"Origen de aprendizaje inválido: {origen}."
            )

        return origen

    # =====================================================
    # RESOLUCIÓN DE RELACIONES
    # =====================================================

    @staticmethod
    def _resolver_relaciones(
        producto,
        categoria=None,
        codigo_producto=None,
        marca=None,
    ):
        """
        Resuelve producto, categoría, código y marca.

        También evita almacenar relaciones inconsistentes.
        """

        if producto is None and codigo_producto is None:
            raise ValidationError(
                "Debe indicar un producto o un código "
                "de producto."
            )

        if codigo_producto is not None:
            if producto is None:
                producto = codigo_producto.producto

            elif (
                codigo_producto.producto_id
                != producto.pk
            ):
                raise ValidationError(
                    "El código seleccionado no pertenece "
                    "al producto indicado."
                )

            if marca is None:
                marca = codigo_producto.marca

            elif (
                codigo_producto.marca_id
                != marca.pk
            ):
                raise ValidationError(
                    "La marca indicada no coincide con "
                    "la marca del código seleccionado."
                )

        if producto is None:
            raise ValidationError(
                "No fue posible determinar el producto."
            )

        if categoria is None:
            categoria = producto.categoria

        elif (
            producto.categoria_id
            != categoria.pk
        ):
            raise ValidationError(
                "La categoría indicada no coincide con "
                "la categoría actual del producto."
            )

        if categoria is None:
            raise ValidationError(
                "El producto debe tener una categoría."
            )

        return {
            "producto": producto,
            "categoria": categoria,
            "codigo_producto": codigo_producto,
            "marca": marca,
        }

    # =====================================================
    # DATOS DESDE DETALLE XML
    # =====================================================

    @staticmethod
    def _datos_desde_detalle_original(
        detalle_original,
    ):
        """
        Obtiene los datos originales de un detalle proveniente
        de una factura XML.
        """

        if detalle_original is None:
            return {}

        factura = getattr(
            detalle_original,
            "factura",
            None,
        )

        proveedor = (
            getattr(
                factura,
                "proveedor_rel",
                None,
            )
            if factura
            else None
        )

        return {
            "texto_original": (
                getattr(
                    detalle_original,
                    "descripcion_proveedor",
                    "",
                )
                or ""
            ),
            "codigo_original": (
                getattr(
                    detalle_original,
                    "codigo_proveedor",
                    "",
                )
                or ""
            ),
            "proveedor": proveedor,
            "origen": "FACTURA",
            "detalle_original": detalle_original,
        }

    # =====================================================
    # DATOS DESDE DETALLE NORMALIZADO
    # =====================================================

    @staticmethod
    def _datos_desde_detalle_normalizado(
        detalle_normalizado,
    ):
        """
        Obtiene los datos desde DetalleFacturaNormalizado.

        Funciona para:

        - facturas XML;
        - facturas manuales.

        Se utilizan las propiedades:

        - descripcion_original
        - codigo_original
        - factura
        """

        if detalle_normalizado is None:
            return {}

        factura = getattr(
            detalle_normalizado,
            "factura",
            None,
        )

        proveedor = (
            getattr(
                factura,
                "proveedor_rel",
                None,
            )
            if factura
            else None
        )

        detalle_original = getattr(
            detalle_normalizado,
            "detalle_original",
            None,
        )

        return {
            "texto_original": (
                getattr(
                    detalle_normalizado,
                    "descripcion_original",
                    "",
                )
                or ""
            ),
            "codigo_original": (
                getattr(
                    detalle_normalizado,
                    "codigo_original",
                    "",
                )
                or ""
            ),
            "proveedor": proveedor,
            "origen": "FACTURA",
            "detalle_original": detalle_original,
        }

    # =====================================================
    # BÚSQUEDA DE APRENDIZAJE EXISTENTE
    # =====================================================

    @staticmethod
    def _buscar_aprendizaje_existente(
        *,
        texto_normalizado,
        codigo_normalizado,
        proveedor,
        producto,
        codigo_producto,
    ):
        """
        Busca un aprendizaje existente para reforzarlo.

        Prioridad:

        1. Código normalizado exacto.
        2. Texto normalizado exacto.

        También separa los aprendizajes por:

        - proveedor;
        - producto;
        - código de producto confirmado.
        """

        queryset = (
            AprendizajeProducto.objects
            .select_for_update()
            .filter(
                activo=True,
                producto_confirmado=producto,
            )
        )

        if proveedor is None:
            queryset = queryset.filter(
                proveedor__isnull=True
            )
        else:
            queryset = queryset.filter(
                proveedor=proveedor
            )

        if codigo_producto is None:
            queryset = queryset.filter(
                codigo_producto_confirmado__isnull=True
            )
        else:
            queryset = queryset.filter(
                codigo_producto_confirmado=(
                    codigo_producto
                )
            )

        # El código exacto es la evidencia más fuerte.
        if codigo_normalizado:
            encontrado = (
                queryset
                .filter(
                    codigo_normalizado=(
                        codigo_normalizado
                    )
                )
                .order_by(
                    "-veces_confirmado",
                    "-ultima_confirmacion_en",
                )
                .first()
            )

            if encontrado:
                return encontrado

        # Si no existe coincidencia exacta por código,
        # se busca por texto normalizado.
        if texto_normalizado:
            return (
                queryset
                .filter(
                    texto_normalizado=(
                        texto_normalizado
                    )
                )
                .order_by(
                    "-veces_confirmado",
                    "-ultima_confirmacion_en",
                )
                .first()
            )

        return None

    # =====================================================
    # PROMEDIO DE CONFIANZA
    # =====================================================

    @staticmethod
    def _actualizar_promedio(
        *,
        promedio_actual,
        cantidad_actual,
        nueva_confianza,
    ):
        """
        Calcula el promedio acumulado de confianza.

        Respeta correctamente el valor 0.00 y no lo reemplaza
        accidentalmente por 100.
        """

        promedio_actual = Decimal(
            str(
                CIEN
                if promedio_actual is None
                else promedio_actual
            )
        )

        cantidad_actual = int(
            1
            if cantidad_actual is None
            else cantidad_actual
        )

        if cantidad_actual < 1:
            cantidad_actual = 1

        total_anterior = (
            promedio_actual
            * Decimal(cantidad_actual)
        )

        nueva_cantidad = cantidad_actual + 1

        promedio = (
            (
                total_anterior
                + nueva_confianza
            )
            / Decimal(nueva_cantidad)
        )

        return promedio.quantize(
            DOS_DECIMALES
        )

    # =====================================================
    # REGISTRO DE ALIAS
    # =====================================================

    @classmethod
    def _registrar_alias(
        cls,
        *,
        texto_original,
        producto,
        categoria,
        codigo_producto,
        marca,
        origen,
    ):
        """
        Crea o refuerza un alias confirmado.

        La búsqueda se realiza primero por la versión normalizada
        y luego por los alias existentes del producto para evitar
        duplicados cuando existen normalizadores históricos distintos.
        """

        texto_original = str(
            texto_original or ""
        ).strip()

        if not texto_original:
            return None

        alias_normalizado = normalizar_texto(
            texto_original
        )

        if not alias_normalizado:
            return None

        alias = (
            AliasProducto.objects
            .select_for_update()
            .filter(
                producto=producto,
                alias_normalizado=alias_normalizado,
            )
            .first()
        )

        # Compatibilidad con alias históricos creados con otra
        # versión de la función de normalización.
        if alias is None:
            alias_candidatos = (
                AliasProducto.objects
                .select_for_update()
                .filter(
                    producto=producto,
                )
            )

            for candidato in alias_candidatos:
                candidato_normalizado = normalizar_texto(
                    candidato.alias_original
                )

                if candidato_normalizado == alias_normalizado:
                    alias = candidato
                    break

        if alias:
            alias.veces_confirmado = (
                int(alias.veces_confirmado or 0)
                + 1
            )

            alias.activo = True

            if not alias.categoria_id:
                alias.categoria = categoria

            if (
                codigo_producto is not None
                and not alias.codigo_producto_id
            ):
                alias.codigo_producto = codigo_producto

            if (
                marca is not None
                and not alias.marca_id
            ):
                alias.marca = marca

            alias.save()

            return alias

        origen_alias = (
            "FACTURA"
            if origen == "FACTURA"
            else "APRENDIZAJE"
        )

        alias = AliasProducto(
            producto=producto,
            categoria=categoria,
            alias_original=texto_original,
            codigo_producto=codigo_producto,
            marca=marca,
            origen=origen_alias,
            veces_confirmado=1,
            activo=True,
        )

        # Se asigna explícitamente para que la consulta y el modelo
        # utilicen exactamente el mismo valor.
        alias.alias_normalizado = alias_normalizado
        alias.save()

        return alias

    # =====================================================
    # REGISTRO PRINCIPAL
    # =====================================================

    @classmethod
    @transaction.atomic
    def registrar(
        cls,
        *,
        texto_original=None,
        producto=None,
        categoria=None,
        codigo_original=None,
        codigo_producto=None,
        marca=None,
        proveedor=None,
        detalle_original=None,
        detalle_normalizado=None,
        origen="INDIVIDUAL",
        usuario=None,
        confianza=100,
        observacion=None,
        crear_alias=True,
    ):
        """
        Registra o refuerza un aprendizaje confirmado.

        Puede utilizarse desde:

        - creación individual;
        - factura XML;
        - factura manual;
        - código;
        - mostrador;
        - importación;
        - corrección.

        Importante:
        Este método debe llamarse únicamente después de una
        confirmación humana.
        """

        if (
            detalle_original is not None
            and detalle_normalizado is not None
        ):
            detalle_normalizado_original = getattr(
                detalle_normalizado,
                "detalle_original",
                None,
            )

            if (
                detalle_normalizado_original is not None
                and detalle_normalizado_original.pk
                != detalle_original.pk
            ):
                raise ValidationError(
                    "El detalle original no coincide con "
                    "el detalle normalizado indicado."
                )

        datos_detalle = {}

        if detalle_normalizado is not None:
            datos_detalle = (
                cls._datos_desde_detalle_normalizado(
                    detalle_normalizado
                )
            )

        elif detalle_original is not None:
            datos_detalle = (
                cls._datos_desde_detalle_original(
                    detalle_original
                )
            )

        if datos_detalle:
            texto_original = (
                texto_original
                or datos_detalle.get(
                    "texto_original",
                    "",
                )
            )

            codigo_original = (
                codigo_original
                or datos_detalle.get(
                    "codigo_original",
                    "",
                )
            )

            proveedor = (
                proveedor
                or datos_detalle.get(
                    "proveedor"
                )
            )

            # Si el detalle normalizado proviene de XML,
            # conservar el FK al detalle original.
            if detalle_original is None:
                detalle_original = (
                    datos_detalle.get(
                        "detalle_original"
                    )
                )

            # No sobrescribir CORRECCION, IMPORTACION,
            # CODIGO u otro origen indicado explícitamente.
            if (
                str(origen or "")
                .strip()
                .upper()
                == "INDIVIDUAL"
            ):
                origen = "FACTURA"

        origen = cls._validar_origen(
            origen
        )

        texto_original = str(
            texto_original or ""
        ).strip()

        codigo_original = str(
            codigo_original or ""
        ).strip().upper()

        if (
            not texto_original
            and not codigo_original
        ):
            raise ValidationError(
                "Debe indicar una descripción o un código "
                "para registrar el aprendizaje."
            )

        relaciones = cls._resolver_relaciones(
            producto=producto,
            categoria=categoria,
            codigo_producto=codigo_producto,
            marca=marca,
        )

        producto = relaciones["producto"]
        categoria = relaciones["categoria"]
        codigo_producto = relaciones[
            "codigo_producto"
        ]
        marca = relaciones["marca"]

        confianza = cls._decimal_confianza(
            confianza
        )

        texto_normalizado = normalizar_texto(
            texto_original
        )

        codigo_normalizado = normalizar_codigo(
            codigo_original
        )

        aprendizaje = (
            cls._buscar_aprendizaje_existente(
                texto_normalizado=(
                    texto_normalizado
                ),
                codigo_normalizado=(
                    codigo_normalizado
                ),
                proveedor=proveedor,
                producto=producto,
                codigo_producto=codigo_producto,
            )
        )

        fue_creado = False

        if aprendizaje:
            promedio = cls._actualizar_promedio(
                promedio_actual=(
                    aprendizaje.confianza_promedio
                ),
                cantidad_actual=(
                    aprendizaje.veces_confirmado
                ),
                nueva_confianza=confianza,
            )

            aprendizaje.veces_confirmado = (
                int(
                    aprendizaje.veces_confirmado
                    or 0
                )
                + 1
            )

            aprendizaje.confianza_promedio = (
                promedio
            )

            aprendizaje.ultima_confirmacion_en = (
                timezone.now()
            )

            aprendizaje.confirmado_por = (
                usuario
                or aprendizaje.confirmado_por
            )

            aprendizaje.activo = True

            # Si ahora existe un detalle XML, se conserva.
            if detalle_original is not None:
                aprendizaje.detalle_original = (
                    detalle_original
                )

            # Completar relaciones que antes podían
            # estar vacías.
            if (
                not aprendizaje.categoria_confirmada_id
            ):
                aprendizaje.categoria_confirmada = (
                    categoria
                )

            if (
                codigo_producto is not None
                and not (
                    aprendizaje
                    .codigo_producto_confirmado_id
                )
            ):
                aprendizaje.codigo_producto_confirmado = (
                    codigo_producto
                )

            if (
                marca is not None
                and not aprendizaje.marca_confirmada_id
            ):
                aprendizaje.marca_confirmada = marca

            if observacion:
                aprendizaje.observacion = (
                    str(observacion).strip()
                )

            aprendizaje.save()

        else:
            fue_creado = True

            aprendizaje = (
                AprendizajeProducto.objects.create(
                    detalle_original=detalle_original,
                    proveedor=proveedor,
                    origen=origen,
                    texto_original=texto_original,
                    texto_normalizado=(
                        texto_normalizado
                    ),
                    codigo_original=(
                        codigo_original
                        or None
                    ),
                    codigo_normalizado=(
                        codigo_normalizado
                        or ""
                    ),
                    producto_confirmado=producto,
                    categoria_confirmada=categoria,
                    codigo_producto_confirmado=(
                        codigo_producto
                    ),
                    marca_confirmada=marca,
                    veces_confirmado=1,
                    confianza_promedio=confianza,
                    activo=True,
                    confirmado_por=usuario,
                    ultima_confirmacion_en=(
                        timezone.now()
                    ),
                    observacion=(
                        str(observacion).strip()
                        if observacion
                        else None
                    ),
                )
            )

        alias = None

        if crear_alias:
            alias = cls._registrar_alias(
                texto_original=texto_original,
                producto=producto,
                categoria=categoria,
                codigo_producto=codigo_producto,
                marca=marca,
                origen=origen,
            )

        return {
            "aprendizaje": aprendizaje,
            "alias": alias,
            "creado": fue_creado,
        }

    # =====================================================
    # CONFIRMACIÓN O CORRECCIÓN DE SUGERENCIA
    # =====================================================

    @classmethod
    @transaction.atomic
    def confirmar_sugerencia(
        cls,
        *,
        sugerencia,
        producto=None,
        categoria=None,
        codigo_producto=None,
        marca=None,
        usuario=None,
        corregida=False,
        motivo=None,
        detalle_normalizado=None,
    ):
        """
        Confirma o corrige una SugerenciaProducto y registra
        el aprendizaje resultante.

        detalle_normalizado puede enviarse cuando la sugerencia
        corresponde a un detalle manual o normalizado de compras.
        """

        if not isinstance(
            sugerencia,
            SugerenciaProducto,
        ):
            raise ValidationError(
                "Debe proporcionar una "
                "SugerenciaProducto válida."
            )

        sugerencia = (
            SugerenciaProducto.objects
            .select_for_update()
            .get(
                pk=sugerencia.pk
            )
        )

        if sugerencia.estado in {
            "CONFIRMADA",
            "CORREGIDA",
            "RECHAZADA",
        }:
            raise ValidationError(
                "Esta sugerencia ya fue revisada."
            )

        producto = (
            producto
            or sugerencia.producto_sugerido
        )

        categoria = (
            categoria
            or (
                producto.categoria
                if producto
                else (
                    sugerencia
                    .categoria_sugerida
                )
            )
        )

        codigo_producto = (
            codigo_producto
            or (
                sugerencia
                .codigo_producto_sugerido
            )
        )

        marca = (
            marca
            or sugerencia.marca_sugerida
        )

        relaciones = cls._resolver_relaciones(
            producto=producto,
            categoria=categoria,
            codigo_producto=codigo_producto,
            marca=marca,
        )

        producto = relaciones["producto"]
        categoria = relaciones["categoria"]
        codigo_producto = relaciones[
            "codigo_producto"
        ]
        marca = relaciones["marca"]

        realmente_corregida = (
            corregida
            or any([
                (
                    sugerencia.producto_sugerido_id
                    != producto.pk
                ),
                (
                    sugerencia.categoria_sugerida_id
                    != categoria.pk
                ),
                (
                    sugerencia
                    .codigo_producto_sugerido_id
                    != (
                        codigo_producto.pk
                        if codigo_producto
                        else None
                    )
                ),
                (
                    sugerencia.marca_sugerida_id
                    != (
                        marca.pk
                        if marca
                        else None
                    )
                ),
            ])
        )

        sugerencia.producto_confirmado = producto
        sugerencia.categoria_confirmada = categoria

        sugerencia.codigo_producto_confirmado = (
            codigo_producto
        )

        sugerencia.marca_confirmada = marca

        sugerencia.estado = (
            "CORREGIDA"
            if realmente_corregida
            else "CONFIRMADA"
        )

        sugerencia.revisado_por = usuario
        sugerencia.revisado_en = timezone.now()

        sugerencia.motivo_revision = (
            str(motivo).strip()
            if motivo
            else None
        )

        sugerencia.save()

        origen_aprendizaje = (
            "CORRECCION"
            if realmente_corregida
            else sugerencia.origen
        )

        resultado = cls.registrar(
            texto_original=(
                sugerencia.texto_entrada
            ),
            codigo_original=(
                sugerencia.codigo_entrada
            ),
            producto=producto,
            categoria=categoria,
            codigo_producto=codigo_producto,
            marca=marca,
            proveedor=sugerencia.proveedor,
            detalle_original=(
                sugerencia.detalle_original
            ),
            detalle_normalizado=(
                detalle_normalizado
            ),
            origen=origen_aprendizaje,
            usuario=usuario,
            confianza=sugerencia.confianza,
            observacion=(
                motivo
                or (
                    "Aprendizaje generado al "
                    "confirmar una sugerencia."
                )
            ),
            crear_alias=True,
        )

        resultado["sugerencia"] = sugerencia

        return resultado

    # =====================================================
    # RECHAZO DE SUGERENCIA
    # =====================================================

    @staticmethod
    @transaction.atomic
    def rechazar_sugerencia(
        *,
        sugerencia,
        usuario=None,
        motivo=None,
    ):
        """
        Rechaza una sugerencia pendiente.

        Una sugerencia rechazada no genera aprendizaje positivo.
        """

        if not isinstance(
            sugerencia,
            SugerenciaProducto,
        ):
            raise ValidationError(
                "Debe proporcionar una "
                "SugerenciaProducto válida."
            )

        sugerencia = (
            SugerenciaProducto.objects
            .select_for_update()
            .get(
                pk=sugerencia.pk
            )
        )

        if sugerencia.estado != "PENDIENTE":
            raise ValidationError(
                "Solo se pueden rechazar "
                "sugerencias pendientes."
            )

        sugerencia.estado = "RECHAZADA"
        sugerencia.revisado_por = usuario
        sugerencia.revisado_en = timezone.now()

        sugerencia.motivo_revision = (
            str(motivo).strip()
            if motivo
            else (
                "Sugerencia rechazada "
                "por el usuario."
            )
        )

        sugerencia.save()

        return sugerencia