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


# =========================================================
# CONSTANTES
# =========================================================

CERO = Decimal("0.00")
CIEN = Decimal("100.00")
DOS_DECIMALES = Decimal("0.01")


class AprendizajeProductoService:
    """
    Registra decisiones confirmadas por el usuario.

    Este servicio NO genera sugerencias.

    Su responsabilidad es convertir una confirmación humana
    en memoria reutilizable para el sistema mediante:

    - AprendizajeProducto
    - AliasProducto
    - Huella técnica del producto

    La huella técnica utiliza:

    - familia;
    - categoría;
    - marca;
    - todos los atributos técnicos confirmados;
    - valores;
    - unidades;
    - tipo de dato.

    Ejemplo:

        Producto:
            FOCO H4 LED

        Familia:
            Encendido y eléctrico

        Categoría:
            Foco

        Atributos:
            Tecnología = LED
            Tipo de foco = H4
            Voltaje = 12 V
            Potencia = 60 W

    El servicio crea evidencia reutilizable para que
    MotorSugerenciasProducto pueda encontrar posteriormente
    el producto mediante AliasProducto.

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

    # Los alias técnicos usan este prefijo para poder
    # identificarlos y regenerarlos si cambian los atributos.
    PREFIJO_ALIAS_TECNICO = "TEC "

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
            confianza = Decimal(
                str(valor)
            )

        except (
            InvalidOperation,
            ValueError,
            TypeError,
        ) as error:
            raise ValidationError(
                "La confianza debe ser un número válido."
            ) from error

        if (
            confianza < CERO
            or confianza > CIEN
        ):
            raise ValidationError(
                "La confianza debe estar entre 0 y 100."
            )

        return confianza.quantize(
            DOS_DECIMALES
        )

    @classmethod
    def _validar_origen(
        cls,
        origen,
    ):
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
        Resuelve:

        - producto;
        - categoría;
        - código comercial;
        - marca.

        Evita guardar relaciones inconsistentes.
        """

        if (
            producto is None
            and codigo_producto is None
        ):
            raise ValidationError(
                "Debe indicar un producto o un código "
                "de producto."
            )

        # =================================================
        # CÓDIGO
        # =================================================

        if codigo_producto is not None:

            if producto is None:
                producto = (
                    codigo_producto.producto
                )

            elif (
                codigo_producto.producto_id
                != producto.pk
            ):
                raise ValidationError(
                    "El código seleccionado no pertenece "
                    "al producto indicado."
                )

            # ---------------------------------------------
            # MARCA DEL CÓDIGO
            # ---------------------------------------------

            if marca is None:
                marca = (
                    codigo_producto.marca
                )

            elif (
                codigo_producto.marca_id
                != marca.pk
            ):
                raise ValidationError(
                    "La marca indicada no coincide con "
                    "la marca del código seleccionado."
                )

        # =================================================
        # PRODUCTO
        # =================================================

        if producto is None:
            raise ValidationError(
                "No fue posible determinar el producto."
            )

        # =================================================
        # CATEGORÍA
        # =================================================

        if categoria is None:
            categoria = (
                producto.categoria
            )

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
    # FAMILIA
    # =====================================================

    @staticmethod
    def _resolver_familia(
        categoria,
    ):
        """
        Obtiene la familia desde la categoría.

        NO se almacena familia nuevamente en Producto ni
        AprendizajeProducto porque la fuente de verdad es:

            Producto
                ↓
            Categoria
                ↓
            FamiliaProducto
        """

        if categoria is None:
            return None

        return getattr(
            categoria,
            "familia",
            None,
        )

    # =====================================================
    # DATOS DESDE DETALLE XML
    # =====================================================

    @staticmethod
    def _datos_desde_detalle_original(
        detalle_original,
    ):
        """
        Obtiene datos originales de una factura XML.
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

            "proveedor":
                proveedor,

            "origen":
                "FACTURA",

            "detalle_original":
                detalle_original,
        }

    # =====================================================
    # DATOS DESDE DETALLE NORMALIZADO
    # =====================================================

    @staticmethod
    def _datos_desde_detalle_normalizado(
        detalle_normalizado,
    ):
        """
        Obtiene datos desde DetalleFacturaNormalizado.

        Compatible con:

        - factura XML;
        - factura manual.
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

            "proveedor":
                proveedor,

            "origen":
                "FACTURA",

            "detalle_original":
                detalle_original,
        }

    # =====================================================
    # ATRIBUTOS TÉCNICOS
    # =====================================================

    @classmethod
    def _obtener_atributos_producto(
        cls,
        producto,
    ):
        """
        Obtiene TODOS los atributos técnicos actualmente
        guardados en el producto.

        Devuelve una estructura independiente de los modelos:

        [
            {
                "atributo_id": 1,
                "nombre": "Voltaje",
                "unidad": "V",
                "tipo_dato": "DECIMAL",
                "valor": "12",
            },
            ...
        ]
        """

        if producto is None:
            return []

        manager = getattr(
            producto,
            "valores_atributos",
            None,
        )

        if manager is None:
            return []

        try:
            valores = (
                manager
                .select_related(
                    "atributo"
                )
                .all()
                .order_by(
                    "atributo__nombre"
                )
            )

        except Exception:
            return []

        resultado = []

        for item in valores:

            atributo = getattr(
                item,
                "atributo",
                None,
            )

            if atributo is None:
                continue

            valor = str(
                getattr(
                    item,
                    "valor",
                    "",
                )
                or ""
            ).strip()

            if not valor:
                continue

            nombre = str(
                getattr(
                    atributo,
                    "nombre",
                    "",
                )
                or ""
            ).strip()

            if not nombre:
                continue

            unidad = str(
                getattr(
                    atributo,
                    "unidad",
                    "",
                )
                or ""
            ).strip()

            tipo_dato = str(
                getattr(
                    atributo,
                    "tipo_dato",
                    "TEXTO",
                )
                or "TEXTO"
            ).strip().upper()

            resultado.append({
                "atributo_id": (
                    getattr(
                        atributo,
                        "pk",
                        None,
                    )
                ),

                "nombre":
                    nombre,

                "unidad":
                    unidad,

                "tipo_dato":
                    tipo_dato,

                "valor":
                    valor,
            })

        return resultado

    # =====================================================
    # ATRIBUTOS RECIBIDOS EXTERNAMENTE
    # =====================================================

    @classmethod
    def _normalizar_atributos_confirmados(
        cls,
        *,
        producto,
        atributos_confirmados=None,
    ):
        """
        Normaliza atributos provenientes de distintas fuentes.

        Si atributos_confirmados es None:
            lee producto.valores_atributos.

        También admite objetos ValorAtributoProducto o diccionarios.

        Esto permitirá reutilizar el servicio desde:

        - inventario;
        - compras;
        - importaciones;
        - facturas;
        - correcciones.
        """

        if atributos_confirmados is None:
            return cls._obtener_atributos_producto(
                producto
            )

        # =================================================
        # DICCIONARIO
        # =================================================

        if isinstance(
            atributos_confirmados,
            dict,
        ):
            iterable = []

            for clave, valor in (
                atributos_confirmados.items()
            ):

                if isinstance(
                    valor,
                    dict,
                ):
                    item = dict(valor)

                    if (
                        "atributo" not in item
                        and hasattr(
                            clave,
                            "nombre",
                        )
                    ):
                        item[
                            "atributo"
                        ] = clave

                    iterable.append(
                        item
                    )

                else:
                    iterable.append({
                        "atributo":
                            (
                                clave
                                if hasattr(
                                    clave,
                                    "nombre",
                                )
                                else None
                            ),

                        "nombre":
                            (
                                ""
                                if hasattr(
                                    clave,
                                    "nombre",
                                )
                                else str(
                                    clave
                                    or ""
                                )
                            ),

                        "valor":
                            valor,
                    })

        else:
            iterable = list(
                atributos_confirmados
            )

        resultado = []

        claves_usadas = set()

        for item in iterable:

            # =============================================
            # DICCIONARIO
            # =============================================

            if isinstance(
                item,
                dict,
            ):

                atributo = (
                    item.get(
                        "atributo"
                    )
                )

                valor = str(
                    item.get(
                        "valor",
                        "",
                    )
                    or ""
                ).strip()

                if atributo is not None:

                    atributo_id = getattr(
                        atributo,
                        "pk",
                        None,
                    )

                    nombre = str(
                        getattr(
                            atributo,
                            "nombre",
                            "",
                        )
                        or ""
                    ).strip()

                    unidad = str(
                        getattr(
                            atributo,
                            "unidad",
                            "",
                        )
                        or ""
                    ).strip()

                    tipo_dato = str(
                        getattr(
                            atributo,
                            "tipo_dato",
                            "TEXTO",
                        )
                        or "TEXTO"
                    ).strip().upper()

                else:

                    atributo_id = (
                        item.get(
                            "atributo_id"
                        )
                    )

                    nombre = str(
                        item.get(
                            "nombre",
                            "",
                        )
                        or ""
                    ).strip()

                    unidad = str(
                        item.get(
                            "unidad",
                            "",
                        )
                        or ""
                    ).strip()

                    tipo_dato = str(
                        item.get(
                            "tipo_dato",
                            "TEXTO",
                        )
                        or "TEXTO"
                    ).strip().upper()

            # =============================================
            # OBJETO ValorAtributoProducto
            # =============================================

            else:

                atributo = getattr(
                    item,
                    "atributo",
                    None,
                )

                if atributo is None:
                    continue

                valor = str(
                    getattr(
                        item,
                        "valor",
                        "",
                    )
                    or ""
                ).strip()

                atributo_id = getattr(
                    atributo,
                    "pk",
                    None,
                )

                nombre = str(
                    getattr(
                        atributo,
                        "nombre",
                        "",
                    )
                    or ""
                ).strip()

                unidad = str(
                    getattr(
                        atributo,
                        "unidad",
                        "",
                    )
                    or ""
                ).strip()

                tipo_dato = str(
                    getattr(
                        atributo,
                        "tipo_dato",
                        "TEXTO",
                    )
                    or "TEXTO"
                ).strip().upper()

            # =============================================
            # VALIDACIONES
            # =============================================

            if (
                not nombre
                or not valor
            ):
                continue

            clave = (
                str(
                    atributo_id
                )
                if atributo_id is not None
                else normalizar_texto(
                    nombre
                )
            )

            if clave in claves_usadas:
                continue

            claves_usadas.add(
                clave
            )

            resultado.append({
                "atributo_id":
                    atributo_id,

                "nombre":
                    nombre,

                "unidad":
                    unidad,

                "tipo_dato":
                    tipo_dato,

                "valor":
                    valor,
            })

        resultado.sort(
            key=lambda item: (
                normalizar_texto(
                    item["nombre"]
                ),
                str(
                    item.get(
                        "atributo_id"
                    )
                    or ""
                ),
            )
        )

        return resultado

    # =====================================================
    # HUELLA TÉCNICA
    # =====================================================

    @classmethod
    def _construir_huella_tecnica(
        cls,
        *,
        producto,
        categoria,
        marca=None,
        atributos_confirmados=None,
    ):
        """
        Construye una representación técnica del producto.

        NO crea nuevas tablas.

        Ejemplo:

        {
            "familia": "Encendido y eléctrico",
            "categoria": "Foco",
            "marca": "PHILIPS",
            "atributos": [
                {"nombre": "Tecnología", "valor": "LED"},
                {"nombre": "Voltaje", "valor": "12"},
            ],
        }
        """

        familia = cls._resolver_familia(
            categoria
        )

        atributos = (
            cls._normalizar_atributos_confirmados(
                producto=producto,
                atributos_confirmados=(
                    atributos_confirmados
                ),
            )
        )

        return {
            "producto_id": (
                producto.pk
                if producto
                else None
            ),

            "producto": (
                producto.nombre_base
                if producto
                else ""
            ),

            "familia_id": (
                familia.pk
                if familia
                else None
            ),

            "familia": (
                familia.nombre
                if familia
                else ""
            ),

            "categoria_id": (
                categoria.pk
                if categoria
                else None
            ),

            "categoria": (
                categoria.nombre
                if categoria
                else ""
            ),

            "marca_id": (
                marca.pk
                if marca
                else None
            ),

            "marca": (
                marca.nombre
                if marca
                else ""
            ),

            "atributos":
                atributos,
        }

    # =====================================================
    # TEXTO SEGURO PARA ALIAS
    # =====================================================

    @staticmethod
    def _limitar_texto_alias(
        texto,
    ):
        """
        Respeta max_length de AliasProducto.alias_original.
        """

        texto = str(
            texto or ""
        ).strip()

        if not texto:
            return ""

        try:
            max_length = (
                AliasProducto
                ._meta
                .get_field(
                    "alias_original"
                )
                .max_length
            )

        except Exception:
            max_length = 255

        max_length = (
            max_length
            or 255
        )

        if len(texto) <= max_length:
            return texto

        return (
            texto[:max_length]
            .rstrip()
        )

    # =====================================================
    # CONSTRUIR ALIAS TÉCNICOS
    # =====================================================

    @classmethod
    def _construir_aliases_tecnicos(
        cls,
        huella,
    ):
        """
        Crea evidencia textual a partir de la huella técnica.

        Se genera:

        1. Contexto familia + categoría + marca.
        2. Un alias por CADA atributo.
        3. Alias compuestos que combinan varios atributos.

        De esta manera ningún atributo se pierde aunque el
        perfil completo supere los 255 caracteres.
        """

        atributos = (
            huella.get(
                "atributos",
                []
            )
            or []
        )

        # Si no existen atributos todavía, no creamos
        # huella técnica. Esto evita registrar una huella
        # incompleta antes de que el formulario termine
        # de guardar los atributos.
        if not atributos:
            return []

        familia = str(
            huella.get(
                "familia",
                "",
            )
            or ""
        ).strip()

        categoria = str(
            huella.get(
                "categoria",
                "",
            )
            or ""
        ).strip()

        marca = str(
            huella.get(
                "marca",
                "",
            )
            or ""
        ).strip()

        base = [
            cls.PREFIJO_ALIAS_TECNICO.strip()
        ]

        if familia:
            base.append(
                familia
            )

        if categoria:
            base.append(
                categoria
            )

        if marca:
            base.append(
                marca
            )

        aliases = []

        # =================================================
        # CONTEXTO GENERAL
        # =================================================

        contexto = " ".join(
            base
        ).strip()

        if contexto:
            aliases.append(
                contexto
            )

        # =================================================
        # CADA ATRIBUTO INDIVIDUAL
        # =================================================

        for atributo in atributos:

            partes = list(
                base
            )

            nombre = str(
                atributo.get(
                    "nombre",
                    "",
                )
                or ""
            ).strip()

            valor = str(
                atributo.get(
                    "valor",
                    "",
                )
                or ""
            ).strip()

            unidad = str(
                atributo.get(
                    "unidad",
                    "",
                )
                or ""
            ).strip()

            if nombre:
                partes.append(
                    nombre
                )

            if valor:
                partes.append(
                    valor
                )

            # Evitar:
            #
            # "12 V V"
            #
            # si la unidad ya viene escrita dentro del valor.
            if (
                unidad
                and normalizar_texto(
                    unidad
                )
                not in normalizar_texto(
                    valor
                ).split()
            ):
                partes.append(
                    unidad
                )

            texto = " ".join(
                partes
            ).strip()

            if texto:
                aliases.append(
                    texto
                )

        # =================================================
        # PERFIL COMPUESTO
        # =================================================
        #
        # Intentamos colocar varios atributos juntos.
        #
        # Si supera max_length, se parte en varios alias.
        # =================================================

        try:
            max_length = (
                AliasProducto
                ._meta
                .get_field(
                    "alias_original"
                )
                .max_length
                or 255
            )
        except Exception:
            max_length = 255

        actual = list(
            base
        )

        for atributo in atributos:

            segmento = []

            nombre = str(
                atributo.get(
                    "nombre",
                    "",
                )
                or ""
            ).strip()

            valor = str(
                atributo.get(
                    "valor",
                    "",
                )
                or ""
            ).strip()

            unidad = str(
                atributo.get(
                    "unidad",
                    "",
                )
                or ""
            ).strip()

            if nombre:
                segmento.append(
                    nombre
                )

            if valor:
                segmento.append(
                    valor
                )

            if (
                unidad
                and normalizar_texto(
                    unidad
                )
                not in normalizar_texto(
                    valor
                ).split()
            ):
                segmento.append(
                    unidad
                )

            if not segmento:
                continue

            candidato = " ".join(
                actual + segmento
            ).strip()

            if (
                len(candidato)
                <= max_length
            ):
                actual.extend(
                    segmento
                )

            else:
                texto_actual = " ".join(
                    actual
                ).strip()

                if (
                    texto_actual
                    and len(actual)
                    > len(base)
                ):
                    aliases.append(
                        texto_actual
                    )

                actual = (
                    list(base)
                    + segmento
                )

        texto_final = " ".join(
            actual
        ).strip()

        if (
            texto_final
            and len(actual) > len(base)
        ):
            aliases.append(
                texto_final
            )

        # =================================================
        # DEDUPLICAR
        # =================================================

        resultado = []

        normalizados = set()

        for texto in aliases:

            texto = (
                cls._limitar_texto_alias(
                    texto
                )
            )

            normalizado = (
                normalizar_texto(
                    texto
                )
            )

            if (
                not texto
                or not normalizado
                or normalizado
                in normalizados
            ):
                continue

            normalizados.add(
                normalizado
            )

            resultado.append(
                texto
            )

        return resultado

    # =====================================================
    # DESACTIVAR HUELLA ANTERIOR
    # =====================================================

    @classmethod
    def _desactivar_aliases_tecnicos_anteriores(
        cls,
        *,
        producto,
    ):
        """
        Cuando cambian los atributos técnicos, las huellas
        anteriores no deben seguir participando en sugerencias.

        Solo toca alias generados por este servicio.
        Los alias humanos/facturas NO se alteran.
        """

        if producto is None:
            return 0

        return (
            AliasProducto.objects
            .filter(
                producto=producto,
                alias_original__startswith=(
                    cls.PREFIJO_ALIAS_TECNICO
                ),
                activo=True,
            )
            .update(
                activo=False
            )
        )

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

        Se separa además por:

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

        # =================================================
        # PROVEEDOR
        # =================================================

        if proveedor is None:
            queryset = queryset.filter(
                proveedor__isnull=True
            )

        else:
            queryset = queryset.filter(
                proveedor=proveedor
            )

        # =================================================
        # CÓDIGO CONFIRMADO
        # =================================================

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

        # =================================================
        # CÓDIGO EXACTO
        # =================================================

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

        # =================================================
        # TEXTO EXACTO
        # =================================================

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
        Calcula promedio acumulado de confianza.

        Respeta correctamente 0.00.
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
            * Decimal(
                cantidad_actual
            )
        )

        nueva_cantidad = (
            cantidad_actual + 1
        )

        promedio = (
            (
                total_anterior
                + nueva_confianza
            )
            / Decimal(
                nueva_cantidad
            )
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

        Se utiliza tanto para:

        - alias humano;
        - alias de factura;
        - huellas técnicas.
        """

        texto_original = str(
            texto_original or ""
        ).strip()

        if not texto_original:
            return None

        texto_original = (
            cls._limitar_texto_alias(
                texto_original
            )
        )

        alias_normalizado = (
            normalizar_texto(
                texto_original
            )
        )

        if not alias_normalizado:
            return None

        alias = (
            AliasProducto.objects
            .select_for_update()
            .filter(
                producto=producto,
                alias_normalizado=(
                    alias_normalizado
                ),
            )
            .first()
        )

        # =================================================
        # COMPATIBILIDAD CON ALIAS HISTÓRICOS
        # =================================================

        if alias is None:

            alias_candidatos = (
                AliasProducto.objects
                .select_for_update()
                .filter(
                    producto=producto,
                )
            )

            for candidato in (
                alias_candidatos
            ):

                candidato_normalizado = (
                    normalizar_texto(
                        candidato.alias_original
                    )
                )

                if (
                    candidato_normalizado
                    == alias_normalizado
                ):
                    alias = candidato
                    break

        # =================================================
        # REFORZAR ALIAS EXISTENTE
        # =================================================

        if alias:

            alias.veces_confirmado = (
                int(
                    alias.veces_confirmado
                    or 0
                )
                + 1
            )

            alias.activo = True

            if not alias.categoria_id:
                alias.categoria = (
                    categoria
                )

            if (
                codigo_producto is not None
                and not alias.codigo_producto_id
            ):
                alias.codigo_producto = (
                    codigo_producto
                )

            if (
                marca is not None
                and not alias.marca_id
            ):
                alias.marca = (
                    marca
                )

            alias.save()

            return alias

        # =================================================
        # CREAR NUEVO ALIAS
        # =================================================

        origen_alias = (
            "FACTURA"
            if origen == "FACTURA"
            else "APRENDIZAJE"
        )

        alias = AliasProducto(
            producto=producto,
            categoria=categoria,
            alias_original=(
                texto_original
            ),
            codigo_producto=(
                codigo_producto
            ),
            marca=marca,
            origen=origen_alias,
            veces_confirmado=1,
            activo=True,
        )

        alias.alias_normalizado = (
            alias_normalizado
        )

        alias.save()

        return alias

    # =====================================================
    # REGISTRAR HUELLA TÉCNICA
    # =====================================================

    @classmethod
    @transaction.atomic
    def registrar_huella_tecnica(
        cls,
        *,
        producto,
        categoria=None,
        codigo_producto=None,
        marca=None,
        atributos_confirmados=None,
        origen="INDIVIDUAL",
    ):
        """
        Registra o regenera la huella técnica de un producto.

        Este método debe ejecutarse DESPUÉS de guardar
        ValorAtributoProducto.

        Aprende:

        Familia
            ↓
        Categoría
            ↓
        Marca
            ↓
        TODOS los atributos técnicos
            ↓
        valores + unidades

        No crea AprendizajeProducto adicional.
        Solo actualiza la evidencia técnica reutilizable
        mediante AliasProducto.
        """

        origen = cls._validar_origen(
            origen
        )

        relaciones = (
            cls._resolver_relaciones(
                producto=producto,
                categoria=categoria,
                codigo_producto=(
                    codigo_producto
                ),
                marca=marca,
            )
        )

        producto = relaciones[
            "producto"
        ]

        categoria = relaciones[
            "categoria"
        ]

        codigo_producto = relaciones[
            "codigo_producto"
        ]

        marca = relaciones[
            "marca"
        ]

        huella = (
            cls._construir_huella_tecnica(
                producto=producto,
                categoria=categoria,
                marca=marca,
                atributos_confirmados=(
                    atributos_confirmados
                ),
            )
        )

        # =================================================
        # RETIRAR HUELLA VIEJA
        # =================================================

        cls._desactivar_aliases_tecnicos_anteriores(
            producto=producto
        )

        textos = (
            cls._construir_aliases_tecnicos(
                huella
            )
        )

        alias_creados = []

        # =================================================
        # NUEVA HUELLA
        # =================================================

        for texto in textos:

            alias = cls._registrar_alias(
                texto_original=texto,
                producto=producto,
                categoria=categoria,
                codigo_producto=(
                    codigo_producto
                ),
                marca=marca,
                origen=origen,
            )

            if alias:
                alias_creados.append(
                    alias
                )

        return {
            "producto":
                producto,

            "categoria":
                categoria,

            "familia":
                cls._resolver_familia(
                    categoria
                ),

            "huella_tecnica":
                huella,

            "alias_tecnicos":
                alias_creados,

            "total_atributos": len(
                huella.get(
                    "atributos",
                    []
                )
            ),

            "total_alias_tecnicos": len(
                alias_creados
            ),
        }

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
        registrar_huella=True,
        atributos_confirmados=None,
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

        Además, si el producto ya tiene atributos técnicos
        guardados, registra automáticamente su huella técnica.

        IMPORTANTE:

        Este método debe llamarse únicamente después de una
        confirmación humana.
        """

        # =================================================
        # COHERENCIA DETALLES
        # =================================================

        if (
            detalle_original is not None
            and detalle_normalizado is not None
        ):

            detalle_normalizado_original = (
                getattr(
                    detalle_normalizado,
                    "detalle_original",
                    None,
                )
            )

            if (
                detalle_normalizado_original
                is not None
                and detalle_normalizado_original.pk
                != detalle_original.pk
            ):
                raise ValidationError(
                    "El detalle original no coincide con "
                    "el detalle normalizado indicado."
                )

        # =================================================
        # EXTRAER DATOS DE FACTURA
        # =================================================

        datos_detalle = {}

        if detalle_normalizado is not None:

            datos_detalle = (
                cls
                ._datos_desde_detalle_normalizado(
                    detalle_normalizado
                )
            )

        elif detalle_original is not None:

            datos_detalle = (
                cls
                ._datos_desde_detalle_original(
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

            if detalle_original is None:

                detalle_original = (
                    datos_detalle.get(
                        "detalle_original"
                    )
                )

            if (
                str(
                    origen or ""
                )
                .strip()
                .upper()
                == "INDIVIDUAL"
            ):
                origen = (
                    "FACTURA"
                )

        # =================================================
        # NORMALIZAR ORIGEN
        # =================================================

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

        # =================================================
        # RELACIONES
        # =================================================

        relaciones = (
            cls._resolver_relaciones(
                producto=producto,
                categoria=categoria,
                codigo_producto=(
                    codigo_producto
                ),
                marca=marca,
            )
        )

        producto = relaciones[
            "producto"
        ]

        categoria = relaciones[
            "categoria"
        ]

        codigo_producto = relaciones[
            "codigo_producto"
        ]

        marca = relaciones[
            "marca"
        ]

        # =================================================
        # CONFIANZA
        # =================================================

        confianza = (
            cls._decimal_confianza(
                confianza
            )
        )

        # =================================================
        # NORMALIZACIÓN
        # =================================================

        texto_normalizado = (
            normalizar_texto(
                texto_original
            )
        )

        codigo_normalizado = (
            normalizar_codigo(
                codigo_original
            )
        )

        # =================================================
        # BUSCAR MEMORIA EXISTENTE
        # =================================================

        aprendizaje = (
            cls
            ._buscar_aprendizaje_existente(
                texto_normalizado=(
                    texto_normalizado
                ),
                codigo_normalizado=(
                    codigo_normalizado
                ),
                proveedor=proveedor,
                producto=producto,
                codigo_producto=(
                    codigo_producto
                ),
            )
        )

        fue_creado = False

        # =================================================
        # REFORZAR EXISTENTE
        # =================================================

        if aprendizaje:

            promedio = (
                cls._actualizar_promedio(
                    promedio_actual=(
                        aprendizaje
                        .confianza_promedio
                    ),
                    cantidad_actual=(
                        aprendizaje
                        .veces_confirmado
                    ),
                    nueva_confianza=(
                        confianza
                    ),
                )
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

            # ---------------------------------------------
            # DETALLE ORIGINAL
            # ---------------------------------------------

            if detalle_original is not None:

                aprendizaje.detalle_original = (
                    detalle_original
                )

            # ---------------------------------------------
            # CATEGORÍA
            # ---------------------------------------------

            if (
                not aprendizaje
                .categoria_confirmada_id
            ):
                aprendizaje.categoria_confirmada = (
                    categoria
                )

            # ---------------------------------------------
            # CÓDIGO
            # ---------------------------------------------

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

            # ---------------------------------------------
            # MARCA
            # ---------------------------------------------

            if (
                marca is not None
                and not aprendizaje
                .marca_confirmada_id
            ):
                aprendizaje.marca_confirmada = (
                    marca
                )

            # ---------------------------------------------
            # OBSERVACIÓN
            # ---------------------------------------------

            if observacion:

                aprendizaje.observacion = (
                    str(
                        observacion
                    ).strip()
                )

            aprendizaje.save()

        # =================================================
        # NUEVO APRENDIZAJE
        # =================================================

        else:

            fue_creado = True

            aprendizaje = (
                AprendizajeProducto
                .objects
                .create(
                    detalle_original=(
                        detalle_original
                    ),

                    proveedor=(
                        proveedor
                    ),

                    origen=(
                        origen
                    ),

                    texto_original=(
                        texto_original
                    ),

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

                    producto_confirmado=(
                        producto
                    ),

                    categoria_confirmada=(
                        categoria
                    ),

                    codigo_producto_confirmado=(
                        codigo_producto
                    ),

                    marca_confirmada=(
                        marca
                    ),

                    veces_confirmado=1,

                    confianza_promedio=(
                        confianza
                    ),

                    activo=True,

                    confirmado_por=(
                        usuario
                    ),

                    ultima_confirmacion_en=(
                        timezone.now()
                    ),

                    observacion=(
                        str(
                            observacion
                        ).strip()
                        if observacion
                        else None
                    ),
                )
            )

        # =================================================
        # ALIAS DE TEXTO HUMANO
        # =================================================

        alias = None

        if crear_alias:

            alias = (
                cls._registrar_alias(
                    texto_original=(
                        texto_original
                    ),
                    producto=producto,
                    categoria=categoria,
                    codigo_producto=(
                        codigo_producto
                    ),
                    marca=marca,
                    origen=origen,
                )
            )

        # =================================================
        # HUELLA TÉCNICA
        # =================================================

        resultado_huella = None

        if registrar_huella:

            atributos = (
                cls
                ._normalizar_atributos_confirmados(
                    producto=producto,
                    atributos_confirmados=(
                        atributos_confirmados
                    ),
                )
            )

            # Solo generamos huella cuando ya existen
            # atributos confirmados.
            if atributos:

                resultado_huella = (
                    cls.registrar_huella_tecnica(
                        producto=producto,
                        categoria=categoria,
                        codigo_producto=(
                            codigo_producto
                        ),
                        marca=marca,
                        atributos_confirmados=(
                            atributos
                        ),
                        origen=origen,
                    )
                )

        # =================================================
        # RESPUESTA
        # =================================================

        return {
            "aprendizaje":
                aprendizaje,

            "alias":
                alias,

            "creado":
                fue_creado,

            "familia": (
                cls._resolver_familia(
                    categoria
                )
            ),

            "huella_tecnica": (
                resultado_huella[
                    "huella_tecnica"
                ]
                if resultado_huella
                else None
            ),

            "alias_tecnicos": (
                resultado_huella[
                    "alias_tecnicos"
                ]
                if resultado_huella
                else []
            ),
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
        atributos_confirmados=None,
    ):
        """
        Confirma o corrige una SugerenciaProducto.

        También registra:

        - texto confirmado;
        - código;
        - producto;
        - categoría;
        - familia derivada;
        - marca;
        - atributos técnicos disponibles.
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

        # =================================================
        # PRODUCTO
        # =================================================

        producto = (
            producto
            or sugerencia.producto_sugerido
        )

        # =================================================
        # CATEGORÍA
        # =================================================

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

        # =================================================
        # CÓDIGO
        # =================================================

        codigo_producto = (
            codigo_producto
            or (
                sugerencia
                .codigo_producto_sugerido
            )
        )

        # =================================================
        # MARCA
        # =================================================

        marca = (
            marca
            or sugerencia.marca_sugerida
        )

        relaciones = (
            cls._resolver_relaciones(
                producto=producto,
                categoria=categoria,
                codigo_producto=(
                    codigo_producto
                ),
                marca=marca,
            )
        )

        producto = relaciones[
            "producto"
        ]

        categoria = relaciones[
            "categoria"
        ]

        codigo_producto = relaciones[
            "codigo_producto"
        ]

        marca = relaciones[
            "marca"
        ]

        # =================================================
        # DETECTAR CORRECCIÓN
        # =================================================

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

        # =================================================
        # GUARDAR CONFIRMACIÓN
        # =================================================

        sugerencia.producto_confirmado = (
            producto
        )

        sugerencia.categoria_confirmada = (
            categoria
        )

        sugerencia.codigo_producto_confirmado = (
            codigo_producto
        )

        sugerencia.marca_confirmada = (
            marca
        )

        sugerencia.estado = (
            "CORREGIDA"
            if realmente_corregida
            else "CONFIRMADA"
        )

        sugerencia.revisado_por = (
            usuario
        )

        sugerencia.revisado_en = (
            timezone.now()
        )

        sugerencia.motivo_revision = (
            str(
                motivo
            ).strip()
            if motivo
            else None
        )

        sugerencia.save()

        origen_aprendizaje = (
            "CORRECCION"
            if realmente_corregida
            else sugerencia.origen
        )

        # =================================================
        # APRENDER
        # =================================================

        resultado = cls.registrar(
            texto_original=(
                sugerencia.texto_entrada
            ),

            codigo_original=(
                sugerencia.codigo_entrada
            ),

            producto=producto,

            categoria=categoria,

            codigo_producto=(
                codigo_producto
            ),

            marca=marca,

            proveedor=(
                sugerencia.proveedor
            ),

            detalle_original=(
                sugerencia.detalle_original
            ),

            detalle_normalizado=(
                detalle_normalizado
            ),

            origen=(
                origen_aprendizaje
            ),

            usuario=usuario,

            confianza=(
                sugerencia.confianza
            ),

            observacion=(
                motivo
                or (
                    "Aprendizaje generado al "
                    "confirmar una sugerencia."
                )
            ),

            crear_alias=True,

            registrar_huella=True,

            atributos_confirmados=(
                atributos_confirmados
            ),
        )

        resultado[
            "sugerencia"
        ] = sugerencia

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

        Una sugerencia rechazada NO genera aprendizaje
        positivo ni huella técnica.
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

        if (
            sugerencia.estado
            != "PENDIENTE"
        ):
            raise ValidationError(
                "Solo se pueden rechazar "
                "sugerencias pendientes."
            )

        sugerencia.estado = (
            "RECHAZADA"
        )

        sugerencia.revisado_por = (
            usuario
        )

        sugerencia.revisado_en = (
            timezone.now()
        )

        sugerencia.motivo_revision = (
            str(
                motivo
            ).strip()
            if motivo
            else (
                "Sugerencia rechazada "
                "por el usuario."
            )
        )

        sugerencia.save()

        return sugerencia