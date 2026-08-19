# inventario/services/sugerencias.py

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from difflib import SequenceMatcher

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from compras.models import (
    DetalleFacturaNormalizado,
    DetalleFacturaOriginal,
)

from inventario.models import (
    AliasProducto,
    AprendizajeProducto,
    CodigoProducto,
    Producto,
    SugerenciaProducto,
    ValorAtributoProducto,
)

from .evidencia import (
    MotorEvidenciaCategoria,
)

from .normalizacion import (
    construir_huella_atributo,
    normalizar_codigo,
    normalizar_texto,
    normalizar_valor_tecnico,
    tokenizar_texto,
    tokenizar_valor_tecnico,
)


# =========================================================
# CONSTANTES
# =========================================================

CERO = Decimal("0.00")
CIEN = Decimal("100.00")
DOS_DECIMALES = Decimal("0.01")


class MotorSugerenciasProducto:
    """
    Motor central de sugerencias de productos MAO.

    Utiliza exclusivamente información existente o confirmada
    dentro del sistema.

    Fuentes:

    1. Código exacto.
    2. Aprendizajes confirmados.
    3. Alias confirmados.
    4. Compras históricas.
    5. Catálogo existente.
    6. Familia.
    7. Categoría.
    8. Atributos técnicos reales.
    9. Motor de evidencia de categoría.

    La clasificación ahora es jerárquica:

        Familia
            ↓
        Categoría
            ↓
        Producto
            ↓
        Código / Marca / Atributos

    Ejemplo:

        FOCO PHILIPS H4 LED 12V 60W

    puede encontrar evidencia mediante:

        Familia:
            Encendido y eléctrico

        Categoría:
            Foco

        Marca:
            PHILIPS

        Atributos:
            Tecnología = LED
            Tipo foco = H4
            Voltaje = 12V
            Potencia = 60W

    No existen reglas automotrices quemadas en este servicio.
    """

    ORIGENES_VALIDOS = {
        "FACTURA",
        "INDIVIDUAL",
        "CODIGO",
        "MOSTRADOR",
        "IMPORTACION",
    }

    # =====================================================
    # CONSTRUCTOR
    # =====================================================

    def __init__(
        self,
        *,
        limite_resultados=5,
        limite_candidatos=300,
        umbral_minimo=25,
    ):
        self.limite_resultados = max(
            int(limite_resultados),
            1,
        )

        self.limite_candidatos = max(
            int(limite_candidatos),
            20,
        )

        self.umbral_minimo = (
            self._decimal(
                umbral_minimo,
                default=Decimal("25.00"),
            )
        )

        self.motor_evidencia = (
            MotorEvidenciaCategoria(
                limite_resultados=max(
                    self.limite_resultados * 4,
                    20,
                )
            )
        )

    # =====================================================
    # UTILIDADES
    # =====================================================

    @staticmethod
    def _decimal(
        valor,
        *,
        default=CERO,
    ):
        try:
            resultado = Decimal(
                str(
                    default
                    if valor is None
                    else valor
                )
            )

        except Exception:
            return Decimal(
                default
            )

        return resultado.quantize(
            DOS_DECIMALES,
            rounding=ROUND_HALF_UP,
        )

    # =====================================================

    @staticmethod
    def _limitar_porcentaje(
        valor,
    ):
        valor = Decimal(
            str(
                valor
                or 0
            )
        )

        return min(
            max(
                valor,
                CERO,
            ),
            CIEN,
        ).quantize(
            DOS_DECIMALES,
            rounding=ROUND_HALF_UP,
        )

    # =====================================================

    @staticmethod
    def _validar_origen(
        origen,
    ):
        origen = str(
            origen
            or "INDIVIDUAL"
        ).strip().upper()

        if (
            origen
            not in MotorSugerenciasProducto.ORIGENES_VALIDOS
        ):
            raise ValidationError(
                f"Origen de sugerencia inválido: "
                f"{origen}."
            )

        return origen

    # =====================================================
    # SIMILITUD GENERAL
    # =====================================================

    @staticmethod
    def _similitud_texto(
        texto_a,
        texto_b,
    ):
        """
        Calcula similitud textual utilizando:

        - SequenceMatcher;
        - Jaccard;
        - cobertura;
        - tokens con números.

        Los tokens con números tienen importancia adicional
        porque suelen contener referencias técnicas.
        """

        texto_a = normalizar_texto(
            texto_a
        )

        texto_b = normalizar_texto(
            texto_b
        )

        if (
            not texto_a
            or not texto_b
        ):
            return CERO

        secuencia = Decimal(
            str(
                SequenceMatcher(
                    None,
                    texto_a,
                    texto_b,
                ).ratio()
            )
        )

        tokens_a = set(
            tokenizar_texto(
                texto_a
            )
        )

        tokens_b = set(
            tokenizar_texto(
                texto_b
            )
        )

        interseccion = (
            tokens_a
            & tokens_b
        )

        union = (
            tokens_a
            | tokens_b
        )

        jaccard = (
            Decimal(
                len(interseccion)
            )
            / Decimal(
                len(union)
            )
            if union
            else CERO
        )

        cobertura = (
            Decimal(
                len(interseccion)
            )
            / Decimal(
                len(tokens_a)
            )
            if tokens_a
            else CERO
        )

        # =================================================
        # TOKENS ESPECÍFICOS
        # =================================================

        tokens_especificos = {
            token
            for token in tokens_a
            if any(
                caracter.isdigit()
                for caracter in token
            )
        }

        especificos_coincidentes = (
            tokens_especificos
            & tokens_b
        )

        coincidencia_especifica = (
            Decimal(
                len(
                    especificos_coincidentes
                )
            )
            / Decimal(
                len(
                    tokens_especificos
                )
            )
            if tokens_especificos
            else CERO
        )

        puntaje = (
            (
                secuencia
                * Decimal("0.20")
            )
            +
            (
                jaccard
                * Decimal("0.20")
            )
            +
            (
                cobertura
                * Decimal("0.25")
            )
            +
            (
                coincidencia_especifica
                * Decimal("0.35")
            )
        ) * CIEN

        # Si el usuario escribió códigos/números
        # específicos y ninguno coincide, penalizamos.
        if (
            tokens_especificos
            and not especificos_coincidentes
        ):
            puntaje *= (
                Decimal("0.65")
            )

        return (
            MotorSugerenciasProducto
            ._limitar_porcentaje(
                puntaje
            )
        )

    # =====================================================
    # MARCA EN TEXTO
    # =====================================================

    @classmethod
    def _puntaje_marca_texto(
        cls,
        texto,
        marca,
    ):
        """
        Detecta una marca escrita explícitamente.

        Ejemplo:

            MANN W712/93 FILTRO ACEITE
        """

        texto_normalizado = (
            normalizar_texto(
                texto
            )
        )

        marca_normalizada = (
            normalizar_texto(
                marca
            )
        )

        if (
            not texto_normalizado
            or not marca_normalizada
        ):
            return CERO

        tokens_texto = set(
            tokenizar_texto(
                texto_normalizado
            )
        )

        tokens_marca = set(
            tokenizar_texto(
                marca_normalizada
            )
        )

        if (
            tokens_marca
            and tokens_marca.issubset(
                tokens_texto
            )
        ):
            return CIEN

        if (
            marca_normalizada
            in texto_normalizado
        ):
            return CIEN

        return cls._similitud_texto(
            texto_normalizado,
            marca_normalizada,
        )

    # =====================================================
    # FAMILIA / CATEGORÍA EN TEXTO
    # =====================================================

    @classmethod
    def _puntaje_clasificacion_texto(
        cls,
        texto,
        objeto,
    ):
        """
        Calcula evidencia directa para una FamiliaProducto
        o Categoria a partir de su nombre.
        """

        if objeto is None:
            return CERO

        nombre = str(
            getattr(
                objeto,
                "nombre",
                "",
            )
            or ""
        ).strip()

        if not nombre:
            return CERO

        texto_normalizado = (
            normalizar_texto(
                texto
            )
        )

        nombre_normalizado = (
            normalizar_texto(
                nombre
            )
        )

        if (
            not texto_normalizado
            or not nombre_normalizado
        ):
            return CERO

        tokens_texto = set(
            tokenizar_texto(
                texto_normalizado
            )
        )

        tokens_nombre = set(
            tokenizar_texto(
                nombre_normalizado
            )
        )

        # Nombre completo contenido.
        if (
            nombre_normalizado
            in texto_normalizado
        ):
            return CIEN

        # Todos los tokens del nombre están presentes.
        if (
            tokens_nombre
            and tokens_nombre.issubset(
                tokens_texto
            )
        ):
            return Decimal("95.00")

        return cls._similitud_texto(
            texto_normalizado,
            nombre_normalizado,
        )

    # =====================================================
    # PONDERACIÓN DINÁMICA
    # =====================================================

    @staticmethod
    def _ponderar(
        *valores,
    ):
        """
        Calcula promedio únicamente utilizando fuentes
        que realmente encontraron evidencia.

        Si una fuente tiene puntaje 0, no reduce artificialmente
        las demás.
        """

        total = CERO
        pesos_activos = CERO

        for (
            puntaje,
            peso,
        ) in valores:

            puntaje = Decimal(
                str(
                    puntaje
                    or 0
                )
            )

            peso = Decimal(
                str(
                    peso
                    or 0
                )
            )

            if (
                puntaje <= CERO
                or peso <= CERO
            ):
                continue

            total += (
                puntaje
                * peso
            )

            pesos_activos += (
                peso
            )

        if pesos_activos <= CERO:
            return CERO

        return (
            total
            / pesos_activos
        ).quantize(
            DOS_DECIMALES,
            rounding=ROUND_HALF_UP,
        )

    # =====================================================
    # RESULTADO BASE
    # =====================================================

    @staticmethod
    def _clave_resultado(
        producto,
        codigo_producto=None,
    ):
        """
        Un producto puede tener varios códigos comerciales.

        La sugerencia se agrupa por Producto.
        """

        return producto.pk

    # =====================================================

    @staticmethod
    def _estructura_resultado(
        *,
        producto,
        codigo_producto=None,
    ):
        categoria = (
            producto.categoria
            if producto
            else None
        )

        familia = (
            getattr(
                categoria,
                "familia",
                None,
            )
            if categoria
            else None
        )

        marca = (
            codigo_producto.marca
            if codigo_producto
            else None
        )

        return {
            "producto":
                producto,

            "familia":
                familia,

            "categoria":
                categoria,

            "codigo_producto":
                codigo_producto,

            "marca":
                marca,

            # ---------------------------------------------
            # Señales existentes
            # ---------------------------------------------

            "puntaje_codigo":
                CERO,

            "puntaje_texto":
                CERO,

            "puntaje_categoria":
                CERO,

            "puntaje_compras":
                CERO,

            "puntaje_aprendizaje":
                CERO,

            "puntaje_alias":
                CERO,

            "puntaje_proveedor":
                CERO,

            # ---------------------------------------------
            # Nuevas señales
            # ---------------------------------------------

            "puntaje_familia":
                CERO,

            "puntaje_tecnico":
                CERO,

            "atributos_coincidentes":
                [],

            # ---------------------------------------------

            "confianza":
                CERO,

            "fuentes":
                set(),
        }

    # =====================================================
    # REDUCCIÓN DE CANDIDATOS
    # =====================================================

    def _filtro_por_tokens(
        self,
        texto,
        *,
        campos,
    ):
        """
        Construye un Q dinámico.

        No contiene vocabulario automotriz.
        """

        tokens = tokenizar_texto(
            texto
        )

        consulta = Q()

        for token in tokens[:8]:

            if len(token) < 2:
                continue

            for campo in campos:

                consulta |= Q(
                    **{
                        f"{campo}__icontains":
                            token
                    }
                )

        return consulta

    # =====================================================
    # PUNTAJE TÉCNICO DE PRODUCTO
    # =====================================================

    def _puntaje_tecnico_producto(
        self,
        *,
        texto,
        producto,
    ):
        """
        Compara la entrada contra TODOS los valores técnicos
        almacenados para el producto.

        No presupone qué atributos existen.

        Ejemplos que puede aprovechar:

            LED
            H4
            12V
            60W
            5W30
            M20X1.5
            DELANTERA
            145MM

        Devuelve:

        {
            "puntaje": Decimal,
            "atributos": [...]
        }
        """

        if (
            producto is None
            or not texto
        ):
            return {
                "puntaje": CERO,
                "atributos": [],
            }

        # =================================================
        # TOKENS DE LA CONSULTA
        # =================================================

        tokens_consulta = set(
            tokenizar_texto(
                texto
            )
        )

        tokens_consulta_tecnicos = set(
            tokenizar_valor_tecnico(
                texto
            )
        )

        tokens_consulta_total = (
            tokens_consulta
            | tokens_consulta_tecnicos
        )

        if not tokens_consulta_total:
            return {
                "puntaje": CERO,
                "atributos": [],
            }

        # =================================================
        # VALORES DEL PRODUCTO
        # =================================================

        try:
            valores = list(
                producto
                .valores_atributos
                .all()
            )

        except Exception:
            return {
                "puntaje": CERO,
                "atributos": [],
            }

        puntajes = []

        atributos_coincidentes = []

        for valor_producto in valores:

            atributo = getattr(
                valor_producto,
                "atributo",
                None,
            )

            if atributo is None:
                continue

            valor = str(
                getattr(
                    valor_producto,
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

            unidad = str(
                getattr(
                    atributo,
                    "unidad",
                    "",
                )
                or ""
            ).strip()

            # =============================================
            # NORMALIZACIÓN TÉCNICA
            # =============================================

            valor_tecnico = (
                normalizar_valor_tecnico(
                    valor,
                    unidad=unidad,
                )
            )

            huella = (
                construir_huella_atributo(
                    nombre,
                    valor,
                    unidad=unidad,
                )
            )

            tokens_valor = set(
                tokenizar_valor_tecnico(
                    valor,
                    unidad=unidad,
                )
            )

            tokens_nombre = set(
                tokenizar_texto(
                    nombre
                )
            )

            tokens_huella = (
                tokens_valor
                | tokens_nombre
            )

            if not tokens_huella:
                continue

            coincidencia_valor = (
                tokens_consulta_total
                & tokens_valor
            )

            coincidencia_nombre = (
                tokens_consulta_total
                & tokens_nombre
            )

            puntaje_atributo = CERO

            # =============================================
            # VALOR TÉCNICO EXACTO
            # =============================================

            if (
                valor_tecnico
                and valor_tecnico
                in normalizar_valor_tecnico(
                    texto
                )
            ):
                puntaje_atributo = (
                    Decimal("85.00")
                )

            # =============================================
            # TOKENS DEL VALOR
            # =============================================

            elif coincidencia_valor:

                cobertura = (
                    Decimal(
                        len(
                            coincidencia_valor
                        )
                    )
                    / Decimal(
                        len(
                            tokens_valor
                        )
                    )
                    if tokens_valor
                    else CERO
                )

                puntaje_atributo = (
                    Decimal("55.00")
                    +
                    (
                        cobertura
                        * Decimal("25.00")
                    )
                )

            # =============================================
            # NOMBRE DEL ATRIBUTO
            # =============================================

            if coincidencia_nombre:

                puntaje_atributo += (
                    Decimal("12.00")
                )

            # =============================================
            # HUELLA COMPLETA
            # =============================================

            if huella:

                similitud_huella = (
                    self._similitud_texto(
                        texto,
                        huella,
                    )
                )

                # La similitud textual completa es
                # evidencia secundaria.
                puntaje_atributo = max(
                    puntaje_atributo,
                    similitud_huella
                    * Decimal("0.80"),
                )

            puntaje_atributo = (
                self._limitar_porcentaje(
                    puntaje_atributo
                )
            )

            if (
                puntaje_atributo
                <= CERO
            ):
                continue

            puntajes.append(
                puntaje_atributo
            )

            atributos_coincidentes.append({
                "atributo_id":
                    getattr(
                        atributo,
                        "pk",
                        None,
                    ),

                "atributo":
                    nombre,

                "valor":
                    valor,

                "unidad":
                    unidad,

                "valor_normalizado":
                    valor_tecnico,

                "puntaje":
                    puntaje_atributo,
            })

        if not puntajes:
            return {
                "puntaje": CERO,
                "atributos": [],
            }

        # =================================================
        # COMBINAR MÚLTIPLES ATRIBUTOS
        # =================================================
        #
        # Un producto coincidiendo con:
        #
        #   LED
        #   H4
        #   12V
        #   60W
        #
        # debe tener más fuerza que uno que solamente
        # coincida con LED.
        # =================================================

        puntajes.sort(
            reverse=True
        )

        pesos = [
            Decimal("1.00"),
            Decimal("0.85"),
            Decimal("0.70"),
            Decimal("0.55"),
            Decimal("0.45"),
            Decimal("0.35"),
        ]

        total = CERO
        total_pesos = CERO

        for indice, puntaje in enumerate(
            puntajes[
                :len(pesos)
            ]
        ):
            peso = pesos[
                indice
            ]

            total += (
                puntaje
                * peso
            )

            total_pesos += (
                peso
            )

        promedio = (
            total
            / total_pesos
            if total_pesos > CERO
            else CERO
        )

        bonificacion = min(
            Decimal(
                max(
                    len(puntajes) - 1,
                    0,
                )
            )
            * Decimal("4.00"),
            Decimal("16.00"),
        )

        puntaje_final = (
            promedio
            + bonificacion
        )

        puntaje_final = (
            self._limitar_porcentaje(
                puntaje_final
            )
        )

        atributos_coincidentes.sort(
            key=lambda item: (
                item["puntaje"]
            ),
            reverse=True,
        )

        return {
            "puntaje":
                puntaje_final,

            "atributos":
                atributos_coincidentes,
        }

    # =====================================================
    # RESULTADOS POR ATRIBUTOS TÉCNICOS
    # =====================================================

    def _buscar_en_atributos(
        self,
        *,
        texto,
        resultados,
    ):
        """
        Permite encontrar productos incluso cuando el nombre
        comercial no coincide, pero sí sus datos técnicos.

        Ejemplo:

            entrada:
                H4 LED 12V

            puede localizar productos cuyos atributos contienen
            esos valores aunque el nombre del producto sea distinto.
        """

        if not texto:
            return

        tokens = tokenizar_texto(
            texto
        )

        consulta = Q()

        for token in tokens[:10]:

            if len(token) < 2:
                continue

            consulta |= (
                Q(
                    valor__icontains=token
                )
                |
                Q(
                    atributo__nombre__icontains=token
                )
                |
                Q(
                    atributo__unidad__icontains=token
                )
                |
                Q(
                    producto__categoria__nombre__icontains=token
                )
                |
                Q(
                    producto__categoria__familia__nombre__icontains=token
                )
            )

        if not consulta:
            return

        valores = (
            ValorAtributoProducto.objects
            .filter(
                producto__activo=True,
                producto__descontinuado=False,
            )
            .filter(
                consulta
            )
            .select_related(
                "producto",
                "producto__categoria",
                "producto__categoria__familia",
                "atributo",
            )
            [:self.limite_candidatos * 3]
        )

        ids_productos = []

        vistos = set()

        for item in valores:

            producto_id = (
                item.producto_id
            )

            if producto_id in vistos:
                continue

            vistos.add(
                producto_id
            )

            ids_productos.append(
                producto_id
            )

            if (
                len(ids_productos)
                >= self.limite_candidatos
            ):
                break

        if not ids_productos:
            return

        productos = (
            Producto.objects
            .filter(
                pk__in=ids_productos,
                activo=True,
                descontinuado=False,
            )
            .select_related(
                "categoria",
                "categoria__familia",
            )
            .prefetch_related(
                "valores_atributos",
                "valores_atributos__atributo",
            )
        )

        for producto in productos:

            analisis = (
                self._puntaje_tecnico_producto(
                    texto=texto,
                    producto=producto,
                )
            )

            puntaje = (
                analisis["puntaje"]
            )

            if puntaje <= CERO:
                continue

            clave = (
                self._clave_resultado(
                    producto
                )
            )

            resultado = (
                resultados.setdefault(
                    clave,
                    self._estructura_resultado(
                        producto=producto,
                    ),
                )
            )

            if (
                puntaje
                > resultado[
                    "puntaje_tecnico"
                ]
            ):
                resultado[
                    "puntaje_tecnico"
                ] = puntaje

                resultado[
                    "atributos_coincidentes"
                ] = analisis[
                    "atributos"
                ]

            resultado[
                "fuentes"
            ].add(
                "ATRIBUTOS_TECNICOS"
            )

    # =====================================================
    # RESULTADOS POR CÓDIGO
    # =====================================================

    def _buscar_por_codigo(
        self,
        *,
        codigo_normalizado,
        resultados,
    ):
        if not codigo_normalizado:
            return

        codigos = (
            CodigoProducto.objects
            .filter(
                activo=True,
                producto__activo=True,
                producto__descontinuado=False,
            )
            .filter(
                Q(
                    codigo_normalizado=(
                        codigo_normalizado
                    )
                )
                |
                Q(
                    codigo_barras=(
                        codigo_normalizado
                    )
                )
            )
            .select_related(
                "producto",
                "producto__categoria",
                "producto__categoria__familia",
                "marca",
            )
            [:self.limite_candidatos]
        )

        for codigo_producto in codigos:

            producto = (
                codigo_producto.producto
            )

            clave = (
                self._clave_resultado(
                    producto,
                    codigo_producto,
                )
            )

            resultado = (
                resultados.setdefault(
                    clave,
                    self._estructura_resultado(
                        producto=producto,
                        codigo_producto=(
                            codigo_producto
                        ),
                    ),
                )
            )

            resultado[
                "codigo_producto"
            ] = codigo_producto

            resultado[
                "marca"
            ] = codigo_producto.marca

            resultado[
                "puntaje_codigo"
            ] = CIEN

            resultado[
                "fuentes"
            ].add(
                "CODIGO_EXACTO"
            )

    # =====================================================
    # APRENDIZAJES CONFIRMADOS
    # =====================================================

    def _buscar_en_aprendizajes(
        self,
        *,
        texto,
        codigo_normalizado,
        proveedor,
        resultados,
    ):
        queryset = (
            AprendizajeProducto.objects
            .filter(
                activo=True
            )
            .select_related(
                "producto_confirmado",
                "producto_confirmado__categoria",
                "producto_confirmado__categoria__familia",
                "codigo_producto_confirmado",
                "codigo_producto_confirmado__marca",
                "proveedor",
            )
        )

        filtro = (
            self._filtro_por_tokens(
                texto,
                campos=[
                    "texto_normalizado",
                ],
            )
        )

        if codigo_normalizado:

            filtro |= Q(
                codigo_normalizado=(
                    codigo_normalizado
                )
            )

        if filtro:
            queryset = (
                queryset.filter(
                    filtro
                )
            )

        queryset = (
            queryset
            .order_by(
                "-veces_confirmado",
                "-ultima_confirmacion_en",
            )
            [:self.limite_candidatos]
        )

        for aprendizaje in queryset:

            producto = (
                aprendizaje
                .producto_confirmado
            )

            if producto is None:
                continue

            codigo_producto = (
                aprendizaje
                .codigo_producto_confirmado
            )

            clave = (
                self._clave_resultado(
                    producto,
                    codigo_producto,
                )
            )

            resultado = (
                resultados.setdefault(
                    clave,
                    self._estructura_resultado(
                        producto=producto,
                        codigo_producto=(
                            codigo_producto
                        ),
                    ),
                )
            )

            puntaje_texto = (
                self._similitud_texto(
                    texto,
                    aprendizaje.texto_original,
                )
            )

            puntaje_codigo = CERO

            if codigo_normalizado:

                if (
                    aprendizaje.codigo_normalizado
                    == codigo_normalizado
                ):
                    puntaje_codigo = (
                        CIEN
                    )

                elif (
                    aprendizaje
                    .codigo_normalizado
                ):
                    puntaje_codigo = (
                        self._similitud_texto(
                            codigo_normalizado,
                            aprendizaje
                            .codigo_normalizado,
                        )
                    )

            fuerza_confirmacion = min(
                Decimal(
                    aprendizaje
                    .veces_confirmado
                    or 1
                )
                * Decimal("4.00"),
                Decimal("20.00"),
            )

            puntaje_aprendizaje = min(
                max(
                    puntaje_texto,
                    puntaje_codigo,
                )
                + fuerza_confirmacion,
                CIEN,
            )

            resultado[
                "puntaje_aprendizaje"
            ] = max(
                resultado[
                    "puntaje_aprendizaje"
                ],
                puntaje_aprendizaje,
            )

            resultado[
                "puntaje_texto"
            ] = max(
                resultado[
                    "puntaje_texto"
                ],
                puntaje_texto,
            )

            resultado[
                "puntaje_codigo"
            ] = max(
                resultado[
                    "puntaje_codigo"
                ],
                puntaje_codigo,
            )

            if (
                codigo_producto
                and (
                    resultado[
                        "codigo_producto"
                    ]
                    is None
                    or puntaje_codigo
                    > resultado[
                        "puntaje_codigo"
                    ]
                )
            ):
                resultado[
                    "codigo_producto"
                ] = codigo_producto

                resultado[
                    "marca"
                ] = (
                    codigo_producto.marca
                )

            if (
                proveedor
                and aprendizaje.proveedor_id
                == proveedor.pk
            ):
                resultado[
                    "puntaje_proveedor"
                ] = max(
                    resultado[
                        "puntaje_proveedor"
                    ],
                    CIEN,
                )

                resultado[
                    "fuentes"
                ].add(
                    "MISMO_PROVEEDOR"
                )

            resultado[
                "fuentes"
            ].add(
                "APRENDIZAJE"
            )

    # =====================================================
    # ALIAS
    # =====================================================

    def _buscar_en_alias(
        self,
        *,
        texto,
        resultados,
    ):
        if not texto:
            return

        filtro = (
            self._filtro_por_tokens(
                texto,
                campos=[
                    "alias_normalizado",
                ],
            )
        )

        queryset = (
            AliasProducto.objects
            .filter(
                activo=True
            )
        )

        if filtro:
            queryset = queryset.filter(
                filtro
            )

        queryset = (
            queryset
            .select_related(
                "producto",
                "producto__categoria",
                "producto__categoria__familia",
                "codigo_producto",
                "codigo_producto__marca",
            )
            .order_by(
                "-veces_confirmado",
                "-actualizado_en",
            )
            [:self.limite_candidatos]
        )

        for alias in queryset:

            producto = (
                alias.producto
            )

            if producto is None:
                continue

            codigo_producto = (
                alias.codigo_producto
            )

            clave = (
                self._clave_resultado(
                    producto,
                    codigo_producto,
                )
            )

            resultado = (
                resultados.setdefault(
                    clave,
                    self._estructura_resultado(
                        producto=producto,
                        codigo_producto=(
                            codigo_producto
                        ),
                    ),
                )
            )

            similitud = (
                self._similitud_texto(
                    texto,
                    alias.alias_original,
                )
            )

            fuerza = min(
                Decimal(
                    alias.veces_confirmado
                    or 1
                )
                * Decimal("3.00"),
                Decimal("15.00"),
            )

            puntaje = min(
                similitud
                + fuerza,
                CIEN,
            )

            es_alias_tecnico = (
                str(
                    alias.alias_original
                    or ""
                )
                .strip()
                .upper()
                .startswith(
                    "TEC "
                )
            )

            # La huella técnica ya está confirmada y puede
            # tener una pequeña bonificación.
            if es_alias_tecnico:

                puntaje = min(
                    puntaje
                    + Decimal("5.00"),
                    CIEN,
                )

                resultado[
                    "fuentes"
                ].add(
                    "ALIAS_TECNICO"
                )

            resultado[
                "puntaje_alias"
            ] = max(
                resultado[
                    "puntaje_alias"
                ],
                puntaje,
            )

            resultado[
                "puntaje_texto"
            ] = max(
                resultado[
                    "puntaje_texto"
                ],
                similitud,
            )

            if (
                codigo_producto
                and resultado[
                    "codigo_producto"
                ] is None
            ):
                resultado[
                    "codigo_producto"
                ] = codigo_producto

                resultado[
                    "marca"
                ] = (
                    codigo_producto.marca
                )

            resultado[
                "fuentes"
            ].add(
                "ALIAS"
            )

    # =====================================================
    # COMPRAS HISTÓRICAS
    # =====================================================

    def _buscar_en_compras(
        self,
        *,
        texto,
        codigo_original,
        codigo_normalizado,
        proveedor,
        excluir_detalle=None,
        resultados,
    ):
        queryset = (
            DetalleFacturaNormalizado.objects
            .filter(
                producto_rel__isnull=False,
                ingresado_al_inventario=True,
            )
            .select_related(
                "detalle_original",
                "detalle_original__factura",
                "detalle_original__factura__proveedor_rel",
                "producto_rel",
                "producto_rel__categoria",
                "producto_rel__categoria__familia",
                "codigo_producto_rel",
                "codigo_producto_rel__marca",
            )
        )

        if excluir_detalle is not None:

            queryset = (
                queryset.exclude(
                    detalle_original=(
                        excluir_detalle
                    )
                )
            )

        filtro = (
            self._filtro_por_tokens(
                texto,
                campos=[
                    "detalle_original__descripcion_proveedor",
                    "nombre_limpio",
                ],
            )
        )

        if codigo_original:

            filtro |= Q(
                detalle_original__codigo_proveedor__icontains=(
                    codigo_original
                )
            )

        if filtro:
            queryset = queryset.filter(
                filtro
            )

        queryset = (
            queryset
            .order_by(
                "-actualizado_en",
            )
            [:self.limite_candidatos]
        )

        for normalizado in queryset:

            detalle = (
                normalizado
                .detalle_original
            )

            if detalle is None:
                continue

            producto = (
                normalizado.producto_rel
            )

            if producto is None:
                continue

            codigo_producto = (
                normalizado
                .codigo_producto_rel
            )

            clave = (
                self._clave_resultado(
                    producto,
                    codigo_producto,
                )
            )

            resultado = (
                resultados.setdefault(
                    clave,
                    self._estructura_resultado(
                        producto=producto,
                        codigo_producto=(
                            codigo_producto
                        ),
                    ),
                )
            )

            puntaje_texto = (
                self._similitud_texto(
                    texto,
                    detalle.descripcion_proveedor,
                )
            )

            puntaje_codigo = CERO

            codigo_historico = (
                normalizar_codigo(
                    detalle.codigo_proveedor
                )
            )

            if (
                codigo_normalizado
                and codigo_historico
            ):

                if (
                    codigo_normalizado
                    == codigo_historico
                ):
                    puntaje_codigo = CIEN

                else:
                    puntaje_codigo = (
                        self._similitud_texto(
                            codigo_normalizado,
                            codigo_historico,
                        )
                    )

            puntaje_compra = max(
                puntaje_texto,
                puntaje_codigo,
            )

            resultado[
                "puntaje_compras"
            ] = max(
                resultado[
                    "puntaje_compras"
                ],
                puntaje_compra,
            )

            resultado[
                "puntaje_texto"
            ] = max(
                resultado[
                    "puntaje_texto"
                ],
                puntaje_texto,
            )

            resultado[
                "puntaje_codigo"
            ] = max(
                resultado[
                    "puntaje_codigo"
                ],
                puntaje_codigo,
            )

            if (
                codigo_producto
                and resultado[
                    "codigo_producto"
                ] is None
            ):
                resultado[
                    "codigo_producto"
                ] = codigo_producto

                resultado[
                    "marca"
                ] = (
                    codigo_producto.marca
                )

            proveedor_historico = getattr(
                detalle.factura,
                "proveedor_rel",
                None,
            )

            if (
                proveedor
                and proveedor_historico
                and proveedor_historico.pk
                == proveedor.pk
            ):
                resultado[
                    "puntaje_proveedor"
                ] = max(
                    resultado[
                        "puntaje_proveedor"
                    ],
                    CIEN,
                )

                resultado[
                    "fuentes"
                ].add(
                    "MISMO_PROVEEDOR"
                )

            resultado[
                "fuentes"
            ].add(
                "COMPRA_CONFIRMADA"
            )

    # =====================================================
    # CATÁLOGO
    # =====================================================

    def _buscar_en_catalogo(
        self,
        *,
        texto,
        codigo_normalizado,
        resultados,
    ):
        """
        Busca productos utilizando:

        - nombre;
        - descripción;
        - nombre comercial;
        - código;
        - barcode;
        - marca;
        - categoría;
        - familia;
        - atributos técnicos.
        """

        filtro_productos = (
            self._filtro_por_tokens(
                texto,
                campos=[
                    "nombre_base",
                    "descripcion",
                    "codigos__nombre_comercial",
                    "codigos__codigo",
                    "codigos__codigo_barras",
                    "codigos__marca__nombre",
                    "categoria__nombre",
                    "categoria__familia__nombre",
                    "valores_atributos__valor",
                    "valores_atributos__atributo__nombre",
                    "valores_atributos__atributo__unidad",
                ],
            )
        )

        productos = (
            Producto.objects
            .filter(
                activo=True,
                descontinuado=False,
            )
            .select_related(
                "categoria",
                "categoria__familia",
            )
            .prefetch_related(
                "codigos",
                "codigos__marca",
                "valores_atributos",
                "valores_atributos__atributo",
            )
            .distinct()
        )

        if filtro_productos:

            productos = (
                productos.filter(
                    filtro_productos
                )
            )

        productos = (
            productos[
                :self.limite_candidatos
            ]
        )

        for producto in productos:

            puntaje_producto = max(
                self._similitud_texto(
                    texto,
                    producto.nombre_base,
                ),
                self._similitud_texto(
                    texto,
                    producto.descripcion,
                ),
            )

            analisis_tecnico = (
                self._puntaje_tecnico_producto(
                    texto=texto,
                    producto=producto,
                )
            )

            puntaje_tecnico = (
                analisis_tecnico[
                    "puntaje"
                ]
            )

            codigos = list(
                producto.codigos.all()
            )

            # =============================================
            # PRODUCTO SIN CÓDIGOS
            # =============================================

            if not codigos:

                clave = (
                    self._clave_resultado(
                        producto
                    )
                )

                resultado = (
                    resultados.setdefault(
                        clave,
                        self._estructura_resultado(
                            producto=producto,
                        ),
                    )
                )

                resultado[
                    "puntaje_texto"
                ] = max(
                    resultado[
                        "puntaje_texto"
                    ],
                    puntaje_producto,
                )

                resultado[
                    "puntaje_tecnico"
                ] = max(
                    resultado[
                        "puntaje_tecnico"
                    ],
                    puntaje_tecnico,
                )

                if puntaje_tecnico > CERO:

                    resultado[
                        "atributos_coincidentes"
                    ] = (
                        analisis_tecnico[
                            "atributos"
                        ]
                    )

                    resultado[
                        "fuentes"
                    ].add(
                        "ATRIBUTOS_TECNICOS"
                    )

                resultado[
                    "fuentes"
                ].add(
                    "CATALOGO"
                )

                continue

            # =============================================
            # PRODUCTO CON CÓDIGOS
            # =============================================

            for codigo_producto in codigos:

                puntaje_comercial = (
                    self._similitud_texto(
                        texto,
                        codigo_producto
                        .nombre_comercial,
                    )
                )

                puntaje_marca = CERO

                if (
                    codigo_producto.marca
                    and codigo_producto
                    .marca.nombre
                ):
                    puntaje_marca = (
                        self._puntaje_marca_texto(
                            texto,
                            codigo_producto
                            .marca.nombre,
                        )
                    )

                puntaje_codigo = CERO

                if codigo_normalizado:

                    codigo_catalogo = (
                        codigo_producto
                        .codigo_normalizado
                    )

                    if (
                        codigo_catalogo
                        == codigo_normalizado
                    ):
                        puntaje_codigo = CIEN

                    elif codigo_catalogo:

                        puntaje_codigo = (
                            self._similitud_texto(
                                codigo_normalizado,
                                codigo_catalogo,
                            )
                        )

                clave = (
                    self._clave_resultado(
                        producto,
                        codigo_producto,
                    )
                )

                resultado = (
                    resultados.setdefault(
                        clave,
                        self._estructura_resultado(
                            producto=producto,
                            codigo_producto=(
                                codigo_producto
                            ),
                        ),
                    )
                )

                puntaje_codigo_anterior = (
                    resultado[
                        "puntaje_codigo"
                    ]
                )

                if (
                    resultado[
                        "codigo_producto"
                    ] is None
                    or puntaje_codigo
                    > puntaje_codigo_anterior
                ):
                    resultado[
                        "codigo_producto"
                    ] = codigo_producto

                    resultado[
                        "marca"
                    ] = (
                        codigo_producto.marca
                    )

                resultado[
                    "puntaje_texto"
                ] = max(
                    resultado[
                        "puntaje_texto"
                    ],
                    puntaje_producto,
                    puntaje_comercial,
                    puntaje_marca,
                )

                resultado[
                    "puntaje_codigo"
                ] = max(
                    resultado[
                        "puntaje_codigo"
                    ],
                    puntaje_codigo,
                )

                resultado[
                    "puntaje_tecnico"
                ] = max(
                    resultado[
                        "puntaje_tecnico"
                    ],
                    puntaje_tecnico,
                )

                if (
                    puntaje_tecnico
                    > CERO
                ):
                    resultado[
                        "atributos_coincidentes"
                    ] = (
                        analisis_tecnico[
                            "atributos"
                        ]
                    )

                    resultado[
                        "fuentes"
                    ].add(
                        "ATRIBUTOS_TECNICOS"
                    )

                resultado[
                    "fuentes"
                ].add(
                    "CATALOGO"
                )

                if (
                    puntaje_marca
                    >= Decimal("80.00")
                ):
                    resultado[
                        "fuentes"
                    ].add(
                        "MARCA_CATALOGO"
                    )

    # =====================================================
    # EVIDENCIA DE CATEGORÍA EN PRODUCTOS
    # =====================================================

    @staticmethod
    def _aplicar_evidencia_categorias(
        resultados,
        categorias_evidencia,
    ):
        """
        Una categoría respaldada por MotorEvidenciaCategoria
        refuerza los productos de esa misma categoría.
        """

        mapa = {
            item["categoria"].pk:
                item
            for item in categorias_evidencia
            if item.get(
                "categoria"
            )
        }

        for resultado in (
            resultados.values()
        ):

            categoria = (
                resultado[
                    "categoria"
                ]
            )

            if categoria is None:
                continue

            evidencia = (
                mapa.get(
                    categoria.pk
                )
            )

            if not evidencia:
                continue

            puntaje = Decimal(
                str(
                    evidencia.get(
                        "puntaje",
                        0,
                    )
                )
            )

            resultado[
                "puntaje_categoria"
            ] = max(
                resultado[
                    "puntaje_categoria"
                ],
                puntaje,
            )

            resultado[
                "fuentes"
            ].add(
                "EVIDENCIA_CATEGORIA"
            )

    # =====================================================
    # CONTEXTO FAMILIA / CATEGORÍA
    # =====================================================

    def _actualizar_contexto_clasificacion(
        self,
        *,
        resultado,
        texto,
    ):
        """
        Completa puntajes directos de:

        - familia;
        - categoría.
        """

        categoria = (
            resultado[
                "categoria"
            ]
        )

        familia = (
            getattr(
                categoria,
                "familia",
                None,
            )
            if categoria
            else None
        )

        resultado[
            "familia"
        ] = familia

        puntaje_categoria_directo = (
            self._puntaje_clasificacion_texto(
                texto,
                categoria,
            )
        )

        puntaje_familia = (
            self._puntaje_clasificacion_texto(
                texto,
                familia,
            )
        )

        resultado[
            "puntaje_categoria"
        ] = max(
            resultado[
                "puntaje_categoria"
            ],
            puntaje_categoria_directo,
        )

        resultado[
            "puntaje_familia"
        ] = max(
            resultado[
                "puntaje_familia"
            ],
            puntaje_familia,
        )

        if (
            puntaje_categoria_directo
            > CERO
        ):
            resultado[
                "fuentes"
            ].add(
                "CATEGORIA"
            )

        if (
            puntaje_familia
            > CERO
        ):
            resultado[
                "fuentes"
            ].add(
                "FAMILIA"
            )

    # =====================================================
    # CONFIANZA FINAL
    # =====================================================

    def _calcular_confianza(
        self,
        resultado,
    ):
        """
        Combina todas las señales.

        Las ponderaciones son relativas porque _ponderar()
        utiliza únicamente las fuentes activas.

        Una fuente ausente NO resta confianza.
        """

        codigo = (
            resultado[
                "puntaje_codigo"
            ]
        )

        aprendizaje = (
            resultado[
                "puntaje_aprendizaje"
            ]
        )

        compras = (
            resultado[
                "puntaje_compras"
            ]
        )

        alias = (
            resultado[
                "puntaje_alias"
            ]
        )

        texto = (
            resultado[
                "puntaje_texto"
            ]
        )

        proveedor = (
            resultado[
                "puntaje_proveedor"
            ]
        )

        tecnico = (
            resultado[
                "puntaje_tecnico"
            ]
        )

        categoria = (
            resultado[
                "puntaje_categoria"
            ]
        )

        familia = (
            resultado[
                "puntaje_familia"
            ]
        )

        # =================================================
        # CÓDIGO EXACTO
        # =================================================

        if (
            codigo
            >= Decimal("99.00")
        ):
            if (
                proveedor
                >= Decimal("90.00")
                or aprendizaje
                >= Decimal("80.00")
                or compras
                >= Decimal("80.00")
                or tecnico
                >= Decimal("80.00")
            ):
                return CIEN

            return Decimal(
                "98.00"
            )

        # =================================================
        # PONDERACIÓN
        # =================================================

        confianza = (
            self._ponderar(
                (
                    codigo,
                    Decimal("0.30"),
                ),
                (
                    aprendizaje,
                    Decimal("0.25"),
                ),
                (
                    tecnico,
                    Decimal("0.20"),
                ),
                (
                    compras,
                    Decimal("0.20"),
                ),
                (
                    alias,
                    Decimal("0.15"),
                ),
                (
                    categoria,
                    Decimal("0.12"),
                ),
                (
                    texto,
                    Decimal("0.10"),
                ),
                (
                    familia,
                    Decimal("0.06"),
                ),
                (
                    proveedor,
                    Decimal("0.05"),
                ),
            )
        )

        # =================================================
        # VARIAS FUENTES FUERTES
        # =================================================

        fuentes_fuertes = sum([
            codigo
            >= Decimal("70.00"),

            aprendizaje
            >= Decimal("70.00"),

            tecnico
            >= Decimal("70.00"),

            compras
            >= Decimal("70.00"),

            alias
            >= Decimal("70.00"),

            categoria
            >= Decimal("70.00"),

            texto
            >= Decimal("70.00"),
        ])

        if (
            fuentes_fuertes
            >= 3
        ):
            confianza += (
                Decimal("10.00")
            )

        elif (
            fuentes_fuertes
            == 2
        ):
            confianza += (
                Decimal("7.00")
            )

        elif (
            fuentes_fuertes
            == 1
        ):
            confianza += (
                Decimal("3.00")
            )

        # Coincidencia técnica múltiple.
        atributos = (
            resultado.get(
                "atributos_coincidentes",
                [],
            )
            or []
        )

        if (
            len(atributos)
            >= 3
        ):
            confianza += (
                Decimal("5.00")
            )

        elif (
            len(atributos)
            == 2
        ):
            confianza += (
                Decimal("3.00")
            )

        return (
            self._limitar_porcentaje(
                confianza
            )
        )

    # =====================================================
    # ORDENAR RESULTADOS
    # =====================================================

    def _ordenar_resultados(
        self,
        resultados,
        *,
        texto,
    ):
        lista = []

        for resultado in (
            resultados.values()
        ):

            self._actualizar_contexto_clasificacion(
                resultado=resultado,
                texto=texto,
            )

            resultado[
                "confianza"
            ] = (
                self._calcular_confianza(
                    resultado
                )
            )

            if (
                resultado[
                    "confianza"
                ]
                < self.umbral_minimo
            ):
                continue

            resultado[
                "fuentes"
            ] = sorted(
                resultado[
                    "fuentes"
                ]
            )

            lista.append(
                resultado
            )

        lista.sort(
            key=lambda item: (
                item[
                    "confianza"
                ],
                item[
                    "puntaje_codigo"
                ],
                item[
                    "puntaje_tecnico"
                ],
                item[
                    "puntaje_aprendizaje"
                ],
                item[
                    "puntaje_compras"
                ],
                item[
                    "puntaje_alias"
                ],
                item[
                    "puntaje_categoria"
                ],
                item[
                    "puntaje_texto"
                ],
            ),
            reverse=True,
        )

        return lista

    # =====================================================
    # AGRUPACIÓN DE CATEGORÍAS
    # =====================================================

    @staticmethod
    def _agrupar_categorias(
        resultados,
    ):
        acumulado = defaultdict(
            lambda: {
                "categoria": None,
                "productos": {},
            }
        )

        for resultado in resultados:

            categoria = (
                resultado[
                    "categoria"
                ]
            )

            producto = (
                resultado[
                    "producto"
                ]
            )

            if (
                categoria is None
                or producto is None
            ):
                continue

            grupo = acumulado[
                categoria.pk
            ]

            grupo[
                "categoria"
            ] = categoria

            confianza = (
                resultado[
                    "confianza"
                ]
            )

            confianza_anterior = (
                grupo[
                    "productos"
                ]
                .get(
                    producto.pk
                )
            )

            if (
                confianza_anterior
                is None
                or confianza
                > confianza_anterior
            ):
                grupo[
                    "productos"
                ][
                    producto.pk
                ] = confianza

        categorias = []

        pesos = [
            Decimal("1.00"),
            Decimal("0.85"),
            Decimal("0.70"),
            Decimal("0.55"),
            Decimal("0.45"),
            Decimal("0.35"),
            Decimal("0.30"),
            Decimal("0.25"),
            Decimal("0.20"),
            Decimal("0.15"),
        ]

        for grupo in (
            acumulado.values()
        ):

            puntajes = sorted(
                grupo[
                    "productos"
                ].values(),
                reverse=True,
            )

            if not puntajes:
                continue

            total = CERO
            total_pesos = CERO

            for indice, puntaje in enumerate(
                puntajes[
                    :len(pesos)
                ]
            ):
                peso = pesos[
                    indice
                ]

                total += (
                    puntaje
                    * peso
                )

                total_pesos += (
                    peso
                )

            promedio = (
                total
                / total_pesos
            ).quantize(
                DOS_DECIMALES,
                rounding=ROUND_HALF_UP,
            )

            cantidad = len(
                puntajes
            )

            bonificacion = min(
                Decimal(
                    max(
                        cantidad - 1,
                        0,
                    )
                )
                * Decimal("3.00"),
                Decimal("18.00"),
            )

            puntaje_categoria = (
                min(
                    promedio
                    + bonificacion,
                    CIEN,
                )
                .quantize(
                    DOS_DECIMALES,
                    rounding=ROUND_HALF_UP,
                )
            )

            categorias.append({
                "categoria":
                    grupo[
                        "categoria"
                    ],

                "puntaje":
                    puntaje_categoria,

                "coincidencias":
                    cantidad,
            })

        categorias.sort(
            key=lambda item: (
                item[
                    "puntaje"
                ],
                item[
                    "coincidencias"
                ],
            ),
            reverse=True,
        )

        return categorias

    # =====================================================
    # COMBINAR CATEGORÍAS
    # =====================================================

    @staticmethod
    def _combinar_categorias(
        categorias_similitud,
        categorias_evidencia,
    ):
        acumulado = {}

        for item in (
            categorias_similitud
        ):

            categoria = (
                item[
                    "categoria"
                ]
            )

            acumulado[
                categoria.pk
            ] = {
                "categoria":
                    categoria,

                "puntaje_similitud":
                    item[
                        "puntaje"
                    ],

                "puntaje_evidencia":
                    CERO,

                "coincidencias":
                    item[
                        "coincidencias"
                    ],
            }

        for item in (
            categorias_evidencia
        ):

            categoria = (
                item[
                    "categoria"
                ]
            )

            grupo = (
                acumulado.setdefault(
                    categoria.pk,
                    {
                        "categoria":
                            categoria,

                        "puntaje_similitud":
                            CERO,

                        "puntaje_evidencia":
                            CERO,

                        "coincidencias":
                            0,
                    },
                )
            )

            grupo[
                "puntaje_evidencia"
            ] = (
                item[
                    "puntaje"
                ]
            )

            grupo[
                "coincidencias"
            ] += (
                item[
                    "coincidencias"
                ]
            )

        resultado = []

        for grupo in (
            acumulado.values()
        ):

            similitud = (
                grupo[
                    "puntaje_similitud"
                ]
            )

            evidencia = (
                grupo[
                    "puntaje_evidencia"
                ]
            )

            fuentes_activas = []

            if similitud > CERO:

                fuentes_activas.append(
                    (
                        similitud,
                        Decimal("0.45"),
                    )
                )

            if evidencia > CERO:

                fuentes_activas.append(
                    (
                        evidencia,
                        Decimal("0.55"),
                    )
                )

            total = sum(
                puntaje
                * peso
                for (
                    puntaje,
                    peso,
                ) in fuentes_activas
            )

            pesos = sum(
                peso
                for (
                    _,
                    peso,
                ) in fuentes_activas
            )

            puntaje_final = (
                total
                / pesos
                if pesos
                else CERO
            )

            resultado.append({
                "categoria":
                    grupo[
                        "categoria"
                    ],

                "puntaje":
                    min(
                        puntaje_final,
                        CIEN,
                    ).quantize(
                        DOS_DECIMALES,
                        rounding=ROUND_HALF_UP,
                    ),

                "puntaje_similitud":
                    similitud,

                "puntaje_evidencia":
                    evidencia,

                "coincidencias":
                    grupo[
                        "coincidencias"
                    ],
            })

        resultado.sort(
            key=lambda item: (
                item[
                    "puntaje"
                ],
                item[
                    "puntaje_evidencia"
                ],
                item[
                    "coincidencias"
                ],
            ),
            reverse=True,
        )

        return resultado

    # =====================================================
    # API PRINCIPAL
    # =====================================================

    def sugerir(
        self,
        *,
        texto,
        codigo=None,
        proveedor=None,
        detalle_original=None,
        origen="INDIVIDUAL",
    ):
        origen = (
            self._validar_origen(
                origen
            )
        )

        # =================================================
        # FACTURA
        # =================================================

        if (
            detalle_original
            is not None
        ):

            if not isinstance(
                detalle_original,
                DetalleFacturaOriginal,
            ):
                raise ValidationError(
                    "El detalle original "
                    "no es válido."
                )

            texto = (
                texto
                or detalle_original
                .descripcion_proveedor
            )

            codigo = (
                codigo
                or detalle_original
                .codigo_proveedor
            )

            proveedor = (
                proveedor
                or detalle_original
                .factura
                .proveedor_rel
            )

            origen = (
                "FACTURA"
            )

        # =================================================
        # NORMALIZACIÓN
        # =================================================

        texto_original = str(
            texto
            or ""
        ).strip()

        codigo_original = str(
            codigo
            or ""
        ).strip().upper()

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

        if (
            not texto_normalizado
            and not codigo_normalizado
        ):
            raise ValidationError(
                "Debe escribir una descripción "
                "o un código."
            )

        resultados = {}

        # =================================================
        # 1. CÓDIGO EXACTO
        # =================================================

        self._buscar_por_codigo(
            codigo_normalizado=(
                codigo_normalizado
            ),
            resultados=resultados,
        )

        hay_codigo_exacto_inicial = any(
            (
                resultado[
                    "puntaje_codigo"
                ]
                >= Decimal("99.00")
                and "CODIGO_EXACTO"
                in resultado[
                    "fuentes"
                ]
            )
            for resultado
            in resultados.values()
        )

        # =================================================
        # 2. APRENDIZAJE
        # =================================================

        self._buscar_en_aprendizajes(
            texto=(
                texto_normalizado
            ),
            codigo_normalizado=(
                codigo_normalizado
            ),
            proveedor=proveedor,
            resultados=resultados,
        )

        # =================================================
        # 3. ALIAS
        # =================================================

        if texto_normalizado:

            self._buscar_en_alias(
                texto=(
                    texto_normalizado
                ),
                resultados=(
                    resultados
                ),
            )

        # =================================================
        # 4. ATRIBUTOS TÉCNICOS
        # =================================================

        if texto_normalizado:

            self._buscar_en_atributos(
                texto=(
                    texto_original
                ),
                resultados=(
                    resultados
                ),
            )

        # =================================================
        # 5. COMPRAS
        # =================================================

        self._buscar_en_compras(
            texto=(
                texto_normalizado
            ),
            codigo_original=(
                codigo_original
            ),
            codigo_normalizado=(
                codigo_normalizado
            ),
            proveedor=proveedor,
            excluir_detalle=(
                detalle_original
            ),
            resultados=resultados,
        )

        # =================================================
        # 6. CATÁLOGO
        # =================================================

        if (
            texto_normalizado
            or not hay_codigo_exacto_inicial
        ):
            self._buscar_en_catalogo(
                texto=(
                    texto_original
                ),
                codigo_normalizado=(
                    codigo_normalizado
                ),
                resultados=(
                    resultados
                ),
            )

        # =================================================
        # 7. MOTOR DE EVIDENCIA
        # =================================================

        categorias_evidencia = []

        if (
            texto_normalizado
            and not hay_codigo_exacto_inicial
        ):
            categorias_evidencia = (
                self.motor_evidencia
                .analizar(
                    texto_original
                )
            )

            self._aplicar_evidencia_categorias(
                resultados,
                categorias_evidencia,
            )

        # =================================================
        # ORDENAR PRODUCTOS
        # =================================================

        todos_los_resultados = (
            self._ordenar_resultados(
                resultados,
                texto=(
                    texto_original
                ),
            )
        )

        # =================================================
        # CÓDIGOS EXACTOS
        # =================================================

        resultados_codigo_exacto = [
            item
            for item
            in todos_los_resultados
            if (
                item[
                    "puntaje_codigo"
                ]
                >= Decimal("99.00")
                and "CODIGO_EXACTO"
                in item[
                    "fuentes"
                ]
            )
        ]

        hay_codigo_exacto = bool(
            resultados_codigo_exacto
        )

        # =================================================
        # CÓDIGO EXACTO
        # =================================================

        if hay_codigo_exacto:

            alternativas_confiables = [
                item
                for item
                in todos_los_resultados
                if (
                    item[
                        "puntaje_codigo"
                    ]
                    < Decimal("99.00")
                    and item[
                        "confianza"
                    ]
                    >= Decimal("60.00")
                )
            ]

            coincidencias = (
                resultados_codigo_exacto
                + alternativas_confiables
            )[
                :self.limite_resultados
            ]

            categorias_similitud = (
                self._agrupar_categorias(
                    resultados_codigo_exacto
                )
            )

            categorias_evidencia = []

            categorias = (
                categorias_similitud
            )

        # =================================================
        # SIN CÓDIGO EXACTO
        # =================================================

        else:

            categorias_similitud = (
                self._agrupar_categorias(
                    todos_los_resultados
                )
            )

            categorias = (
                self._combinar_categorias(
                    categorias_similitud,
                    categorias_evidencia,
                )
            )

            coincidencias = (
                todos_los_resultados[
                    :self.limite_resultados
                ]
            )

        # =================================================
        # MEJOR PRODUCTO
        # =================================================

        mejor_producto_resultado = (
            coincidencias[0]
            if coincidencias
            else None
        )

        # =================================================
        # MEJOR CATEGORÍA
        # =================================================

        mejor_categoria_resultado = (
            categorias[0]
            if categorias
            else None
        )

        # =================================================
        # DECIDIR CATEGORÍA FINAL
        # =================================================
        #
        # Código exacto:
        #     categoría del producto identificado.
        #
        # Sin código exacto:
        #     prioridad al motor colectivo de categorías.
        #
        # Esto evita que un producto débilmente parecido
        # imponga una categoría incorrecta.
        # =================================================

        if (
            hay_codigo_exacto
            and mejor_producto_resultado
        ):
            mejor_categoria = (
                mejor_producto_resultado[
                    "categoria"
                ]
            )

            confianza_categoria = (
                mejor_producto_resultado[
                    "confianza"
                ]
            )

        elif mejor_categoria_resultado:

            mejor_categoria = (
                mejor_categoria_resultado[
                    "categoria"
                ]
            )

            confianza_categoria = (
                mejor_categoria_resultado[
                    "puntaje"
                ]
            )

        elif mejor_producto_resultado:

            mejor_categoria = (
                mejor_producto_resultado[
                    "categoria"
                ]
            )

            confianza_categoria = (
                mejor_producto_resultado[
                    "confianza"
                ]
            )

        else:
            mejor_categoria = None
            confianza_categoria = CERO

        # =================================================
        # FAMILIA FINAL
        # =================================================

        mejor_familia = (
            getattr(
                mejor_categoria,
                "familia",
                None,
            )
            if mejor_categoria
            else None
        )

        # =================================================
        # RESPUESTA
        # =================================================

        return {
            "origen":
                origen,

            "texto_original":
                texto_original,

            "texto_normalizado":
                texto_normalizado,

            "codigo_original":
                codigo_original,

            "codigo_normalizado":
                codigo_normalizado,

            "proveedor":
                proveedor,

            "detalle_original":
                detalle_original,

            "mejor_producto": (
                mejor_producto_resultado[
                    "producto"
                ]
                if mejor_producto_resultado
                else None
            ),

            "mejor_familia":
                mejor_familia,

            "mejor_categoria":
                mejor_categoria,

            "mejor_codigo_producto": (
                mejor_producto_resultado[
                    "codigo_producto"
                ]
                if mejor_producto_resultado
                else None
            ),

            "mejor_marca": (
                mejor_producto_resultado[
                    "marca"
                ]
                if mejor_producto_resultado
                else None
            ),

            "confianza": (
                mejor_producto_resultado[
                    "confianza"
                ]
                if mejor_producto_resultado
                else CERO
            ),

            "confianza_categoria":
                confianza_categoria,

            "coincidencias":
                coincidencias,

            "categorias":
                categorias,

            "categorias_similitud":
                categorias_similitud,

            "categorias_evidencia":
                categorias_evidencia,

            "hay_codigo_exacto":
                hay_codigo_exacto,
        }

    # =====================================================
    # GUARDAR SUGERENCIA
    # =====================================================

    @transaction.atomic
    def generar_y_guardar(
        self,
        *,
        texto=None,
        codigo=None,
        proveedor=None,
        detalle_original=None,
        origen="INDIVIDUAL",
    ):
        resultado = (
            self.sugerir(
                texto=texto,
                codigo=codigo,
                proveedor=proveedor,
                detalle_original=(
                    detalle_original
                ),
                origen=origen,
            )
        )

        mejor_producto = (
            resultado[
                "mejor_producto"
            ]
        )

        mejor_categoria = (
            resultado[
                "mejor_categoria"
            ]
        )

        mejor_codigo = (
            resultado[
                "mejor_codigo_producto"
            ]
        )

        mejor_marca = (
            resultado[
                "mejor_marca"
            ]
        )

        mejor_resultado = (
            resultado[
                "coincidencias"
            ][0]
            if resultado[
                "coincidencias"
            ]
            else {}
        )

        # =================================================
        # NO AGREGAMOS CAMPOS NUEVOS A SugerenciaProducto
        # =================================================
        #
        # Familia y atributos se derivan de los modelos
        # actuales. Por eso NO necesitamos migración.
        # =================================================

        sugerencia = (
            SugerenciaProducto.objects
            .create(
                detalle_original=(
                    detalle_original
                ),

                proveedor=(
                    resultado[
                        "proveedor"
                    ]
                ),

                origen=(
                    resultado[
                        "origen"
                    ]
                ),

                texto_entrada=(
                    resultado[
                        "texto_original"
                    ]
                ),

                codigo_entrada=(
                    resultado[
                        "codigo_original"
                    ]
                    or None
                ),

                producto_sugerido=(
                    mejor_producto
                ),

                categoria_sugerida=(
                    mejor_categoria
                ),

                codigo_producto_sugerido=(
                    mejor_codigo
                ),

                marca_sugerida=(
                    mejor_marca
                ),

                confianza=(
                    resultado[
                        "confianza"
                    ]
                ),

                puntaje_codigo=(
                    mejor_resultado.get(
                        "puntaje_codigo",
                        CERO,
                    )
                ),

                puntaje_texto=(
                    mejor_resultado.get(
                        "puntaje_texto",
                        CERO,
                    )
                ),

                puntaje_categoria=(
                    resultado.get(
                        "confianza_categoria",
                        CERO,
                    )
                ),

                puntaje_compras=(
                    mejor_resultado.get(
                        "puntaje_compras",
                        CERO,
                    )
                ),

                puntaje_aprendizaje=(
                    mejor_resultado.get(
                        "puntaje_aprendizaje",
                        CERO,
                    )
                ),

                puntaje_alias=(
                    mejor_resultado.get(
                        "puntaje_alias",
                        CERO,
                    )
                ),

                puntaje_proveedor=(
                    mejor_resultado.get(
                        "puntaje_proveedor",
                        CERO,
                    )
                ),

                estado=(
                    "PENDIENTE"
                ),
            )
        )

        resultado[
            "sugerencia"
        ] = sugerencia

        return resultado

    # =====================================================
    # JSON
    # =====================================================

    @staticmethod
    def convertir_a_dict(
        resultado,
    ):
        """
        Convierte el resultado a información apta
        para JsonResponse.

        Incluye ahora:

        - familia;
        - categoría;
        - puntaje técnico;
        - atributos coincidentes.
        """

        def producto_dict(
            item,
        ):
            producto = (
                item[
                    "producto"
                ]
            )

            categoria = (
                item[
                    "categoria"
                ]
            )

            familia = (
                item.get(
                    "familia"
                )
            )

            if (
                familia is None
                and categoria
            ):
                familia = getattr(
                    categoria,
                    "familia",
                    None,
                )

            codigo = (
                item[
                    "codigo_producto"
                ]
            )

            marca = (
                item[
                    "marca"
                ]
            )

            atributos = []

            for atributo in (
                item.get(
                    "atributos_coincidentes",
                    []
                )
                or []
            ):
                atributos.append({
                    "atributo_id":
                        atributo.get(
                            "atributo_id"
                        ),

                    "atributo":
                        atributo.get(
                            "atributo"
                        ),

                    "valor":
                        atributo.get(
                            "valor"
                        ),

                    "unidad":
                        atributo.get(
                            "unidad"
                        ),

                    "valor_normalizado":
                        atributo.get(
                            "valor_normalizado"
                        ),

                    "puntaje":
                        float(
                            atributo.get(
                                "puntaje",
                                CERO,
                            )
                        ),
                })

            return {
                "producto_id":
                    producto.pk,

                "producto":
                    producto.nombre_base,

                "sku":
                    producto.sku_interno,

                # =========================================
                # FAMILIA
                # =========================================

                "familia_id": (
                    familia.pk
                    if familia
                    else None
                ),

                "familia": (
                    familia.nombre
                    if familia
                    else None
                ),

                # =========================================
                # CATEGORÍA
                # =========================================

                "categoria_id": (
                    categoria.pk
                    if categoria
                    else None
                ),

                "categoria": (
                    categoria.nombre
                    if categoria
                    else None
                ),

                # =========================================
                # CÓDIGO
                # =========================================

                "codigo_producto_id": (
                    codigo.pk
                    if codigo
                    else None
                ),

                "codigo": (
                    codigo.codigo
                    if codigo
                    else None
                ),

                # =========================================
                # MARCA
                # =========================================

                "marca_id": (
                    marca.pk
                    if marca
                    else None
                ),

                "marca": (
                    marca.nombre
                    if marca
                    else None
                ),

                # =========================================
                # CONFIANZA
                # =========================================

                "confianza": float(
                    item[
                        "confianza"
                    ]
                ),

                # =========================================
                # PUNTAJES
                # =========================================

                "puntajes": {
                    "codigo": float(
                        item[
                            "puntaje_codigo"
                        ]
                    ),

                    "texto": float(
                        item[
                            "puntaje_texto"
                        ]
                    ),

                    "familia": float(
                        item.get(
                            "puntaje_familia",
                            CERO,
                        )
                    ),

                    "categoria": float(
                        item.get(
                            "puntaje_categoria",
                            CERO,
                        )
                    ),

                    "tecnico": float(
                        item.get(
                            "puntaje_tecnico",
                            CERO,
                        )
                    ),

                    "compras": float(
                        item[
                            "puntaje_compras"
                        ]
                    ),

                    "aprendizaje": float(
                        item[
                            "puntaje_aprendizaje"
                        ]
                    ),

                    "alias": float(
                        item[
                            "puntaje_alias"
                        ]
                    ),

                    "proveedor": float(
                        item[
                            "puntaje_proveedor"
                        ]
                    ),
                },

                # =========================================
                # ATRIBUTOS QUE COINCIDIERON
                # =========================================

                "atributos_coincidentes":
                    atributos,

                "fuentes":
                    item[
                        "fuentes"
                    ],
            }

        # =================================================
        # CATEGORÍAS
        # =================================================

        categorias = []

        for item in (
            resultado[
                "categorias"
            ]
        ):

            categoria = (
                item[
                    "categoria"
                ]
            )

            familia = getattr(
                categoria,
                "familia",
                None,
            )

            categorias.append({
                "id":
                    categoria.pk,

                "nombre":
                    categoria.nombre,

                "familia_id": (
                    familia.pk
                    if familia
                    else None
                ),

                "familia": (
                    familia.nombre
                    if familia
                    else None
                ),

                "confianza":
                    float(
                        item[
                            "puntaje"
                        ]
                    ),

                "coincidencias":
                    item[
                        "coincidencias"
                    ],
            })

        # =================================================
        # MEJOR FAMILIA
        # =================================================

        mejor_familia = (
            resultado.get(
                "mejor_familia"
            )
        )

        # =================================================
        # SALIDA
        # =================================================

        datos = {
            "texto":
                resultado[
                    "texto_original"
                ],

            "codigo":
                resultado[
                    "codigo_original"
                ],

            "hay_codigo_exacto":
                bool(
                    resultado.get(
                        "hay_codigo_exacto",
                        False,
                    )
                ),

            "confianza":
                float(
                    resultado[
                        "confianza"
                    ]
                ),

            "confianza_categoria":
                float(
                    resultado.get(
                        "confianza_categoria",
                        CERO,
                    )
                ),

            # =============================================
            # FAMILIA SUGERIDA
            # =============================================

            "familia_id": (
                mejor_familia.pk
                if mejor_familia
                else None
            ),

            "familia": (
                mejor_familia.nombre
                if mejor_familia
                else None
            ),

            # =============================================
            # CATEGORÍAS
            # =============================================

            "categorias":
                categorias,

            # =============================================
            # PRODUCTOS
            # =============================================

            "productos": [
                producto_dict(
                    item
                )
                for item in resultado[
                    "coincidencias"
                ]
            ],
        }

        if (
            resultado.get(
                "sugerencia"
            )
        ):
            datos[
                "sugerencia_id"
            ] = (
                resultado[
                    "sugerencia"
                ].pk
            )

        return datos