# inventario/services/aprendizaje.py

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from inventario.models import (
    AliasProducto,
    AprendizajeProducto,
    Categoria,
    CodigoProducto,
    MarcaRepuesto,
    Producto,
    SugerenciaProducto,
)

from .normalizacion import (
    normalizar_codigo,
    normalizar_texto,
)


CERO = Decimal("0.00")
CIEN = Decimal("100.00")


class AprendizajeProductoService:
    """
    Registra decisiones confirmadas por el usuario.

    No genera sugerencias. Su responsabilidad es convertir una
    confirmación humana en memoria reutilizable para el sistema.
    """

    ORIGENES_VALIDOS = {
        "FACTURA",
        "INDIVIDUAL",
        "MOSTRADOR",
        "CORRECCION",
        "IMPORTACION",
    }

    @staticmethod
    def _decimal_confianza(valor):
        if valor is None:
            return CIEN

        try:
            confianza = Decimal(str(valor))
        except (InvalidOperation, ValueError, TypeError) as error:
            raise ValidationError(
                "La confianza debe ser un número válido."
            ) from error

        if confianza < CERO or confianza > CIEN:
            raise ValidationError(
                "La confianza debe estar entre 0 y 100."
            )

        return confianza.quantize(
            Decimal("0.01")
        )

    @classmethod
    def _validar_origen(cls, origen):
        origen = str(
            origen or "INDIVIDUAL"
        ).strip().upper()

        if origen not in cls.ORIGENES_VALIDOS:
            raise ValidationError(
                f"Origen de aprendizaje inválido: {origen}."
            )

        return origen

    @staticmethod
    def _resolver_relaciones(
        producto,
        categoria=None,
        codigo_producto=None,
        marca=None,
    ):
        if producto is None and codigo_producto is None:
            raise ValidationError(
                "Debe indicar un producto o un código de producto."
            )

        if codigo_producto is not None:
            if producto is None:
                producto = codigo_producto.producto

            elif codigo_producto.producto_id != producto.pk:
                raise ValidationError(
                    "El código seleccionado no pertenece "
                    "al producto indicado."
                )

            if marca is None:
                marca = codigo_producto.marca

            elif codigo_producto.marca_id != marca.pk:
                raise ValidationError(
                    "La marca indicada no coincide con "
                    "la marca del código seleccionado."
                )

        if categoria is None:
            categoria = producto.categoria

        elif producto.categoria_id != categoria.pk:
            raise ValidationError(
                "La categoría indicada no coincide con "
                "la categoría actual del producto."
            )

        return {
            "producto": producto,
            "categoria": categoria,
            "codigo_producto": codigo_producto,
            "marca": marca,
        }

    @staticmethod
    def _datos_desde_detalle(detalle_original):
        if detalle_original is None:
            return {}

        factura = detalle_original.factura

        return {
            "texto_original": (
                detalle_original.descripcion_proveedor
                or ""
            ),
            "codigo_original": (
                detalle_original.codigo_proveedor
                or ""
            ),
            "proveedor": factura.proveedor_rel,
            "origen": "FACTURA",
        }

    @staticmethod
    def _buscar_aprendizaje_existente(
        texto_normalizado,
        codigo_normalizado,
        proveedor,
        producto,
        codigo_producto,
    ):
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
                codigo_producto_confirmado=codigo_producto
            )

        # El código exacto es la evidencia más fuerte.
        if codigo_normalizado:
            encontrado = (
                queryset
                .filter(
                    codigo_normalizado=codigo_normalizado
                )
                .order_by("-veces_confirmado")
                .first()
            )

            if encontrado:
                return encontrado

        # Si no existe código, o no hubo coincidencia,
        # se busca por texto normalizado.
        if texto_normalizado:
            return (
                queryset
                .filter(
                    texto_normalizado=texto_normalizado
                )
                .order_by("-veces_confirmado")
                .first()
            )

        return None

    @staticmethod
    def _actualizar_promedio(
        promedio_actual,
        cantidad_actual,
        nueva_confianza,
    ):
        promedio_actual = Decimal(
            str(promedio_actual or CIEN)
        )

        cantidad_actual = int(
            cantidad_actual or 1
        )

        total_anterior = (
            promedio_actual
            * Decimal(cantidad_actual)
        )

        nueva_cantidad = cantidad_actual + 1

        return (
            (
                total_anterior
                + nueva_confianza
            )
            / Decimal(nueva_cantidad)
        ).quantize(
            Decimal("0.01")
        )

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

        if alias:
            alias.veces_confirmado += 1
            alias.activo = True

            # Completa relaciones que antes podían estar vacías.
            if not alias.categoria_id:
                alias.categoria = categoria

            if (
                codigo_producto is not None
                and not alias.codigo_producto_id
            ):
                alias.codigo_producto = codigo_producto

            if marca is not None and not alias.marca_id:
                alias.marca = marca

            alias.save()

            return alias

        return AliasProducto.objects.create(
            producto=producto,
            categoria=categoria,
            alias_original=str(
                texto_original
            ).strip(),
            codigo_producto=codigo_producto,
            marca=marca,
            origen=(
                "FACTURA"
                if origen == "FACTURA"
                else "APRENDIZAJE"
            ),
            veces_confirmado=1,
            activo=True,
        )

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
        origen="INDIVIDUAL",
        usuario=None,
        confianza=100,
        observacion=None,
        crear_alias=True,
    ):
        """
        Registra o refuerza un aprendizaje confirmado.

        Puede usarse tanto en creación individual como desde factura.
        """

        datos_detalle = cls._datos_desde_detalle(
            detalle_original
        )

        if detalle_original is not None:
            texto_original = (
                texto_original
                or datos_detalle["texto_original"]
            )

            codigo_original = (
                codigo_original
                or datos_detalle["codigo_original"]
            )

            proveedor = (
                proveedor
                or datos_detalle["proveedor"]
            )

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

        if not texto_original:
            raise ValidationError(
                "El texto original es obligatorio "
                "para registrar aprendizaje."
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
                texto_normalizado=texto_normalizado,
                codigo_normalizado=codigo_normalizado,
                proveedor=proveedor,
                producto=producto,
                codigo_producto=codigo_producto,
            )
        )

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

            aprendizaje.veces_confirmado += 1
            aprendizaje.confianza_promedio = promedio
            aprendizaje.ultima_confirmacion_en = (
                timezone.now()
            )
            aprendizaje.confirmado_por = (
                usuario
                or aprendizaje.confirmado_por
            )
            aprendizaje.activo = True

            if detalle_original is not None:
                aprendizaje.detalle_original = (
                    detalle_original
                )

            if observacion:
                aprendizaje.observacion = (
                    str(observacion).strip()
                )

            aprendizaje.save()

        else:
            aprendizaje = (
                AprendizajeProducto.objects.create(
                    detalle_original=detalle_original,
                    proveedor=proveedor,
                    origen=origen,
                    texto_original=texto_original,
                    texto_normalizado=texto_normalizado,
                    codigo_original=(
                        codigo_original or None
                    ),
                    codigo_normalizado=(
                        codigo_normalizado or ""
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
            "creado": aprendizaje.veces_confirmado == 1,
        }

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
    ):
        """
        Confirma o corrige una SugerenciaProducto y registra
        el aprendizaje resultante.
        """

        if not isinstance(
            sugerencia,
            SugerenciaProducto,
        ):
            raise ValidationError(
                "Debe proporcionar una SugerenciaProducto válida."
            )

        sugerencia = (
            SugerenciaProducto.objects
            .select_for_update()
            .get(pk=sugerencia.pk)
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
                else sugerencia.categoria_sugerida
            )
        )

        codigo_producto = (
            codigo_producto
            or sugerencia.codigo_producto_sugerido
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

        realmente_corregida = corregida or any([
            sugerencia.producto_sugerido_id
            != producto.pk,

            sugerencia.categoria_sugerida_id
            != categoria.pk,

            sugerencia.codigo_producto_sugerido_id
            != (
                codigo_producto.pk
                if codigo_producto
                else None
            ),

            sugerencia.marca_sugerida_id
            != (
                marca.pk
                if marca
                else None
            ),
        ])

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
            texto_original=sugerencia.texto_entrada,
            codigo_original=sugerencia.codigo_entrada,
            producto=producto,
            categoria=categoria,
            codigo_producto=codigo_producto,
            marca=marca,
            proveedor=sugerencia.proveedor,
            detalle_original=sugerencia.detalle_original,
            origen=origen_aprendizaje,
            usuario=usuario,
            confianza=sugerencia.confianza,
            observacion=(
                motivo
                or (
                    "Aprendizaje generado al confirmar "
                    "una sugerencia."
                )
            ),
            crear_alias=True,
        )

        resultado["sugerencia"] = sugerencia

        return resultado

    @staticmethod
    @transaction.atomic
    def rechazar_sugerencia(
        *,
        sugerencia,
        usuario=None,
        motivo=None,
    ):
        if not isinstance(
            sugerencia,
            SugerenciaProducto,
        ):
            raise ValidationError(
                "Debe proporcionar una SugerenciaProducto válida."
            )

        sugerencia = (
            SugerenciaProducto.objects
            .select_for_update()
            .get(pk=sugerencia.pk)
        )

        if sugerencia.estado != "PENDIENTE":
            raise ValidationError(
                "Solo se pueden rechazar sugerencias pendientes."
            )

        sugerencia.estado = "RECHAZADA"
        sugerencia.revisado_por = usuario
        sugerencia.revisado_en = timezone.now()
        sugerencia.motivo_revision = (
            str(motivo).strip()
            if motivo
            else "Sugerencia rechazada por el usuario."
        )

        sugerencia.save()

        return sugerencia