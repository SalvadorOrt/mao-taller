# inventario/services/evidencia.py

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from math import log

from django.db.models import Q

from inventario.models import (
    AliasProducto,
    AprendizajeProducto,
    Categoria,
    CategoriaAtributo,
    Producto,
    TerminoCategoria,
    ValorAtributoProducto,
)

from .normalizacion import (
    normalizar_texto,
    tokenizar_texto,
)


# =========================================================
# CONSTANTES
# =========================================================

CERO = Decimal("0.00")
CIEN = Decimal("100.00")
DOS_DECIMALES = Decimal("0.01")


class MotorEvidenciaCategoria:
    """
    Calcula evidencia para determinar la categoría más probable.

    No contiene vocabulario automotriz quemado.

    Toda la inteligencia se construye utilizando datos reales
    almacenados por MAO.

    Fuentes utilizadas:

    1. Nombre real de la categoría.
    2. Familia de la categoría.
    3. Términos configurados.
    4. Estructura de atributos configurados por categoría.
    5. Valores técnicos reales aprendidos de productos.
    6. Alias confirmados.
    7. Aprendizajes confirmados.
    8. Catálogo existente.
    9. Compras históricas confirmadas.

    Ejemplo:

        Entrada:
            FOCO H4 LED 12V

        Base de datos:
            Familia:
                Encendido y eléctrico

            Categoría:
                Foco

            Productos confirmados:
                Tecnología = LED
                Tipo de foco = H4
                Voltaje = 12

        Resultado:
            la evidencia técnica refuerza Foco sin necesidad
            de escribir reglas específicas para "H4" o "LED".
    """

    def __init__(
        self,
        *,
        limite_tokens=10,
        minimo_coincidencias=1,
        limite_resultados=20,
    ):
        self.limite_tokens = max(
            int(limite_tokens),
            1,
        )

        self.minimo_coincidencias = max(
            int(minimo_coincidencias),
            1,
        )

        self.limite_resultados = max(
            int(limite_resultados),
            1,
        )

        # Cache por instancia.
        self._cache_pesos = {}

        self._total_documentos_cache = None

    # =====================================================
    # API PRINCIPAL
    # =====================================================

    def analizar(
        self,
        texto,
    ):
        """
        Analiza una descripción y devuelve las categorías
        ordenadas por evidencia.
        """

        texto_normalizado = (
            normalizar_texto(
                texto
            )
        )

        tokens = (
            self._tokens_unicos(
                texto_normalizado
            )
            [:self.limite_tokens]
        )

        if not tokens:
            return []

        # =================================================
        # PESO ESTADÍSTICO DE CADA TOKEN
        # =================================================

        pesos_tokens = {
            token: self._peso_token(token)
            for token in tokens
        }

        # =================================================
        # ACUMULADOR DE EVIDENCIA
        # =================================================

        evidencia = defaultdict(
            lambda: {
                "categoria": None,
                "puntaje_directo": CERO,
                "coincidencias": 0,
                "tokens": {},
                "fuentes": set(),
            }
        )

        # =================================================
        # 1. NOMBRE REAL DE CATEGORÍA
        # =================================================

        self._evidencia_nombre_categoria(
            texto_normalizado=(
                texto_normalizado
            ),
            tokens=tokens,
            pesos_tokens=pesos_tokens,
            evidencia=evidencia,
        )

        # =================================================
        # 2. FAMILIA
        # =================================================

        self._evidencia_familia(
            texto_normalizado=(
                texto_normalizado
            ),
            tokens=tokens,
            pesos_tokens=pesos_tokens,
            evidencia=evidencia,
        )

        # =================================================
        # 3 - 9. EVIDENCIA POR TOKEN
        # =================================================

        for token in tokens:

            # ---------------------------------------------
            # Términos configurados
            # ---------------------------------------------

            self._evidencia_terminos(
                token=token,
                evidencia=evidencia,
            )

            # ---------------------------------------------
            # Molde técnico de la categoría
            # ---------------------------------------------

            self._evidencia_atributos_configurados(
                token=token,
                evidencia=evidencia,
            )

            # ---------------------------------------------
            # Atributos reales ya aprendidos
            # ---------------------------------------------

            self._evidencia_atributos_productos(
                token=token,
                evidencia=evidencia,
            )

            # ---------------------------------------------
            # Alias
            # ---------------------------------------------

            self._evidencia_alias(
                token=token,
                evidencia=evidencia,
            )

            # ---------------------------------------------
            # Aprendizajes
            # ---------------------------------------------

            self._evidencia_aprendizajes(
                token=token,
                evidencia=evidencia,
            )

            # ---------------------------------------------
            # Catálogo
            # ---------------------------------------------

            self._evidencia_catalogo(
                token=token,
                evidencia=evidencia,
            )

            # ---------------------------------------------
            # Compras
            # ---------------------------------------------

            self._evidencia_compras(
                token=token,
                evidencia=evidencia,
            )

        # =================================================
        # RESULTADO FINAL
        # =================================================

        resultados = []

        peso_total_consulta = sum(
            pesos_tokens.values(),
            CERO,
        )

        # Si todavía no hay suficiente información
        # estadística, cada token pesa igual.
        if (
            peso_total_consulta
            <= CERO
        ):
            pesos_tokens = {
                token: Decimal("1.00")
                for token in tokens
            }

            peso_total_consulta = (
                Decimal(
                    len(tokens)
                )
            )

        # =================================================
        # CALCULAR CATEGORÍAS
        # =================================================

        for grupo in (
            evidencia.values()
        ):

            categoria = (
                grupo["categoria"]
            )

            if categoria is None:
                continue

            if (
                grupo["coincidencias"]
                < self.minimo_coincidencias
                and grupo["puntaje_directo"]
                <= CERO
            ):
                continue

            suma_ponderada = CERO
            peso_coincidente = CERO

            for token in tokens:

                peso_token = (
                    pesos_tokens[token]
                )

                info = (
                    grupo["tokens"]
                    .get(token)
                )

                if not info:
                    continue

                puntaje_token = Decimal(
                    str(
                        info["puntaje"]
                        or 0
                    )
                )

                # Una gran cantidad de evidencia histórica
                # no debe permitir que un token individual
                # exceda 100.
                puntaje_token = min(
                    max(
                        puntaje_token,
                        Decimal("-100.00"),
                    ),
                    CIEN,
                )

                suma_ponderada += (
                    puntaje_token
                    * peso_token
                )

                if (
                    puntaje_token
                    > CERO
                ):
                    peso_coincidente += (
                        peso_token
                    )

            # =============================================
            # EVIDENCIA PONDERADA
            # =============================================

            puntaje_evidencia = (
                (
                    suma_ponderada
                    / peso_total_consulta
                )
                if peso_total_consulta > CERO
                else CERO
            )

            puntaje_evidencia = (
                self._limitar_porcentaje(
                    puntaje_evidencia
                )
            )

            # =============================================
            # COBERTURA DE LA CONSULTA
            # =============================================

            cobertura = (
                (
                    peso_coincidente
                    / peso_total_consulta
                )
                if peso_total_consulta > CERO
                else CERO
            )

            puntaje_evidencia *= (
                cobertura
            )

            puntaje_evidencia = (
                self._limitar_porcentaje(
                    puntaje_evidencia
                )
            )

            # =============================================
            # COINCIDENCIA DIRECTA DE CATEGORÍA
            # =============================================

            puntaje_final = max(
                puntaje_evidencia,
                grupo["puntaje_directo"],
            )

            resultados.append({
                "categoria":
                    categoria,

                "puntaje":
                    self._limitar_porcentaje(
                        puntaje_final
                    ),

                "coincidencias":
                    grupo["coincidencias"],

                "tokens":
                    grupo["tokens"],

                "fuentes":
                    sorted(
                        grupo["fuentes"]
                    ),
            })

        # =================================================
        # ORDEN
        # =================================================

        resultados.sort(
            key=lambda item: (
                item["puntaje"],
                item["coincidencias"],
            ),
            reverse=True,
        )

        return resultados[
            :self.limite_resultados
        ]

    # =====================================================
    # NOMBRE DE CATEGORÍA
    # =====================================================

    def _evidencia_nombre_categoria(
        self,
        *,
        texto_normalizado,
        tokens,
        pesos_tokens,
        evidencia,
    ):
        """
        Compara la consulta con el nombre real
        de cada categoría.
        """

        tokens_consulta = set(
            tokens
        )

        categorias = (
            Categoria.objects
            .select_related(
                "familia"
            )
            .all()
        )

        for categoria in categorias:

            nombre_normalizado = (
                normalizar_texto(
                    categoria.nombre
                )
            )

            if not nombre_normalizado:
                continue

            tokens_categoria = (
                self._tokens_unicos(
                    nombre_normalizado
                )
            )

            if not tokens_categoria:
                continue

            tokens_categoria_set = set(
                tokens_categoria
            )

            interseccion = (
                tokens_categoria_set
                & tokens_consulta
            )

            if not interseccion:
                continue

            # =============================================
            # COINCIDENCIA EXACTA
            # =============================================

            if (
                texto_normalizado
                == nombre_normalizado
            ):
                puntaje = CIEN

            else:
                # =========================================
                # COBERTURA PONDERADA
                # =========================================

                peso_categoria = CERO

                peso_categoria_coincidente = (
                    CERO
                )

                for token in (
                    tokens_categoria
                ):

                    peso = (
                        self._peso_token(
                            token
                        )
                    )

                    peso_categoria += peso

                    if (
                        token
                        in tokens_consulta
                    ):
                        peso_categoria_coincidente += (
                            peso
                        )

                peso_consulta = sum(
                    pesos_tokens.values(),
                    CERO,
                )

                peso_consulta_coincidente = sum(
                    (
                        pesos_tokens[token]
                        for token
                        in interseccion
                        if token
                        in pesos_tokens
                    ),
                    CERO,
                )

                cobertura_categoria = (
                    (
                        peso_categoria_coincidente
                        / peso_categoria
                    )
                    if peso_categoria > CERO
                    else CERO
                )

                cobertura_consulta = (
                    (
                        peso_consulta_coincidente
                        / peso_consulta
                    )
                    if peso_consulta > CERO
                    else CERO
                )

                puntaje = (
                    (
                        cobertura_categoria
                        * Decimal("0.90")
                    )
                    +
                    (
                        cobertura_consulta
                        * Decimal("0.10")
                    )
                ) * CIEN

                puntaje = (
                    self._limitar_porcentaje(
                        puntaje
                    )
                )

            grupo = evidencia[
                categoria.pk
            ]

            grupo["categoria"] = (
                categoria
            )

            grupo["puntaje_directo"] = (
                max(
                    grupo[
                        "puntaje_directo"
                    ],
                    puntaje,
                )
            )

            grupo["fuentes"].add(
                "NOMBRE_CATEGORIA"
            )

            grupo[
                "coincidencias"
            ] += 1

            for token in interseccion:

                self._registrar(
                    evidencia=evidencia,
                    categoria=categoria,
                    token=token,
                    puntaje=puntaje,
                    cantidad=0,
                    fuente=(
                        "NOMBRE_CATEGORIA"
                    ),
                )

    # =====================================================
    # FAMILIA
    # =====================================================

    def _evidencia_familia(
        self,
        *,
        texto_normalizado,
        tokens,
        pesos_tokens,
        evidencia,
    ):
        """
        Usa FamiliaProducto como primera capa jerárquica.

        IMPORTANTE:

        Una familia NO determina por sí sola la categoría.

        Por ejemplo:

            Frenos

        puede contener varias categorías.

        Por eso la evidencia de familia sirve para restringir
        y reforzar, pero tiene menos fuerza que una coincidencia
        directa contra el nombre de categoría.
        """

        tokens_consulta = set(
            tokens
        )

        categorias = (
            Categoria.objects
            .filter(
                familia__isnull=False
            )
            .select_related(
                "familia"
            )
        )

        for categoria in categorias:

            familia = getattr(
                categoria,
                "familia",
                None,
            )

            if familia is None:
                continue

            nombre_familia = (
                normalizar_texto(
                    familia.nombre
                )
            )

            if not nombre_familia:
                continue

            tokens_familia = (
                self._tokens_unicos(
                    nombre_familia
                )
            )

            if not tokens_familia:
                continue

            interseccion = (
                set(tokens_familia)
                & tokens_consulta
            )

            if not interseccion:
                continue

            # =============================================
            # COBERTURA DE LA FAMILIA
            # =============================================

            peso_familia = CERO

            peso_coincidente = CERO

            for token in (
                tokens_familia
            ):

                peso = (
                    self._peso_token(
                        token
                    )
                )

                peso_familia += peso

                if (
                    token
                    in interseccion
                ):
                    peso_coincidente += (
                        peso
                    )

            cobertura = (
                (
                    peso_coincidente
                    / peso_familia
                )
                if peso_familia > CERO
                else CERO
            )

            # Familia tiene una importancia deliberadamente
            # menor que el nombre exacto de categoría.
            puntaje = (
                cobertura
                * Decimal("25.00")
            )

            if (
                texto_normalizado
                == nombre_familia
            ):
                puntaje = (
                    Decimal("30.00")
                )

            puntaje = (
                self._limitar_porcentaje(
                    puntaje
                )
            )

            for token in interseccion:

                self._registrar(
                    evidencia=evidencia,
                    categoria=categoria,
                    token=token,
                    puntaje=puntaje,
                    cantidad=1,
                    fuente="FAMILIA",
                )

    # =====================================================
    # TÉRMINOS CONFIGURADOS
    # =====================================================

    def _evidencia_terminos(
        self,
        *,
        token,
        evidencia,
    ):
        """
        Evidencia configurada manualmente mediante
        TerminoCategoria.
        """

        terminos = (
            TerminoCategoria.objects
            .filter(
                activo=True,
                termino__icontains=token,
            )
            .select_related(
                "categoria"
            )
        )

        for termino in terminos:

            peso = Decimal(
                str(
                    termino.peso
                    or 0
                )
            )

            if (
                termino.tipo
                == "NEGATIVO"
            ):
                puntaje = (
                    -abs(peso)
                )

            elif (
                termino.tipo
                == "SINONIMO"
            ):
                puntaje = (
                    abs(peso)
                    * Decimal("0.90")
                )

            else:
                puntaje = abs(
                    peso
                )

            self._registrar(
                evidencia=evidencia,
                categoria=(
                    termino.categoria
                ),
                token=token,
                puntaje=puntaje,
                cantidad=1,
                fuente=(
                    "TERMINO_CATEGORIA"
                ),
            )

    # =====================================================
    # ATRIBUTOS CONFIGURADOS DE LA CATEGORÍA
    # =====================================================

    def _evidencia_atributos_configurados(
        self,
        *,
        token,
        evidencia,
    ):
        """
        Usa el molde técnico CategoriaAtributo.

        Esto permite aprovechar el diseño del catálogo incluso
        antes de existir muchos productos aprendidos.

        Ejemplo:

            Categoría Foco tiene:
                Voltaje
                Potencia
                Tecnología
                Tipo de foco

        Si una consulta menciona uno de esos conceptos,
        existe evidencia débil a favor de esa categoría.

        Es deliberadamente una evidencia débil porque muchos
        atributos pueden existir en varias categorías.
        """

        configuraciones = (
            CategoriaAtributo.objects
            .filter(
                activo=True,
            )
            .filter(
                Q(
                    atributo__nombre__icontains=(
                        token
                    )
                )
                |
                Q(
                    atributo__unidad__icontains=(
                        token
                    )
                )
            )
            .select_related(
                "categoria",
                "atributo",
            )
            [:500]
        )

        grupos = defaultdict(
            lambda: {
                "categoria": None,
                "puntaje": CERO,
                "coincidencias": 0,
                "fuentes": set(),
            }
        )

        for configuracion in (
            configuraciones
        ):

            categoria = (
                configuracion.categoria
            )

            atributo = (
                configuracion.atributo
            )

            if (
                categoria is None
                or atributo is None
            ):
                continue

            puntaje = CERO

            # =============================================
            # NOMBRE DEL ATRIBUTO
            # =============================================

            if self._texto_contiene_token(
                atributo.nombre,
                token,
            ):
                puntaje += (
                    Decimal("8.00")
                )

                fuente = (
                    "ATRIBUTO_CONFIGURADO"
                )

            else:
                fuente = None

            # =============================================
            # UNIDAD
            # =============================================

            if (
                atributo.unidad
                and self._texto_contiene_token(
                    atributo.unidad,
                    token,
                )
            ):
                puntaje += (
                    Decimal("4.00")
                )

                fuente = (
                    "UNIDAD_CONFIGURADA"
                    if fuente is None
                    else fuente
                )

            if puntaje <= CERO:
                continue

            grupo = grupos[
                categoria.pk
            ]

            grupo["categoria"] = (
                categoria
            )

            grupo["puntaje"] = max(
                grupo["puntaje"],
                puntaje,
            )

            grupo[
                "coincidencias"
            ] += 1

            if fuente:
                grupo["fuentes"].add(
                    fuente
                )

        for grupo in grupos.values():

            bonificacion = min(
                Decimal(
                    grupo["coincidencias"]
                )
                * Decimal("1.00"),
                Decimal("5.00"),
            )

            puntaje = (
                grupo["puntaje"]
                + bonificacion
            )

            self._registrar(
                evidencia=evidencia,
                categoria=(
                    grupo["categoria"]
                ),
                token=token,
                puntaje=puntaje,
                cantidad=(
                    grupo[
                        "coincidencias"
                    ]
                ),
                fuente=(
                    "ATRIBUTO_CONFIGURADO"
                ),
            )

    # =====================================================
    # ATRIBUTOS REALES DE PRODUCTOS
    # =====================================================

    def _evidencia_atributos_productos(
        self,
        *,
        token,
        evidencia,
    ):
        """
        Esta es una de las piezas nuevas más importantes.

        Aprende directamente de:

            ValorAtributoProducto

        es decir, de valores técnicos que usuarios ya
        confirmaron al guardar productos.

        Ejemplos:

            Tecnología = LED
            Tipo de foco = H4
            Voltaje = 12
            Rosca = M20X1.5
            Viscosidad = 5W30
            Posición = Delantera

        No existe vocabulario automotriz quemado:
        todo proviene de la base de datos.
        """

        valores = (
            ValorAtributoProducto.objects
            .filter(
                producto__activo=True,
                producto__descontinuado=False,
                producto__categoria__isnull=False,
            )
            .filter(
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
            )
            .select_related(
                "producto",
                "producto__categoria",
                "producto__categoria__familia",
                "atributo",
            )
            [:600]
        )

        grupos = defaultdict(
            lambda: {
                "categoria": None,
                "mejor_puntaje": CERO,
                "coincidencias": 0,
                "valor": 0,
                "nombre": 0,
                "unidad": 0,
            }
        )

        for item in valores:

            producto = (
                item.producto
            )

            if (
                not producto
                or not producto.categoria_id
            ):
                continue

            categoria = (
                producto.categoria
            )

            atributo = (
                item.atributo
            )

            if atributo is None:
                continue

            puntaje = CERO

            coincidencia_valor = (
                self._texto_contiene_token(
                    item.valor,
                    token,
                )
            )

            coincidencia_nombre = (
                self._texto_contiene_token(
                    atributo.nombre,
                    token,
                )
            )

            coincidencia_unidad = (
                bool(
                    atributo.unidad
                )
                and self._texto_contiene_token(
                    atributo.unidad,
                    token,
                )
            )

            # =============================================
            # VALOR TÉCNICO
            # =============================================
            #
            # Es la señal más fuerte.
            #
            # H4
            # LED
            # M20X1.5
            # 5W30
            # DELANTERA
            # etc.
            # =============================================

            if coincidencia_valor:

                puntaje += (
                    Decimal("34.00")
                )

            # =============================================
            # NOMBRE DEL ATRIBUTO
            # =============================================

            if coincidencia_nombre:

                puntaje += (
                    Decimal("10.00")
                )

            # =============================================
            # UNIDAD
            # =============================================

            if coincidencia_unidad:

                puntaje += (
                    Decimal("5.00")
                )

            if puntaje <= CERO:
                continue

            grupo = grupos[
                categoria.pk
            ]

            grupo["categoria"] = (
                categoria
            )

            grupo[
                "mejor_puntaje"
            ] = max(
                grupo[
                    "mejor_puntaje"
                ],
                puntaje,
            )

            grupo[
                "coincidencias"
            ] += 1

            if coincidencia_valor:
                grupo["valor"] += 1

            if coincidencia_nombre:
                grupo["nombre"] += 1

            if coincidencia_unidad:
                grupo["unidad"] += 1

        # =================================================
        # AGREGAR POR CATEGORÍA
        # =================================================

        for grupo in grupos.values():

            # Más productos confirmando la misma evidencia
            # refuerzan el resultado, pero con límite.
            bonificacion = min(
                Decimal(
                    grupo[
                        "coincidencias"
                    ]
                )
                * Decimal("1.50"),
                Decimal("12.00"),
            )

            puntaje = (
                grupo[
                    "mejor_puntaje"
                ]
                + bonificacion
            )

            puntaje = min(
                puntaje,
                Decimal("55.00"),
            )

            fuentes = []

            if grupo["valor"]:
                fuentes.append(
                    "ATRIBUTO_VALOR"
                )

            if grupo["nombre"]:
                fuentes.append(
                    "ATRIBUTO_NOMBRE"
                )

            if grupo["unidad"]:
                fuentes.append(
                    "ATRIBUTO_UNIDAD"
                )

            fuente = (
                "+".join(fuentes)
                if fuentes
                else "ATRIBUTO_PRODUCTO"
            )

            self._registrar(
                evidencia=evidencia,
                categoria=(
                    grupo["categoria"]
                ),
                token=token,
                puntaje=puntaje,
                cantidad=(
                    grupo[
                        "coincidencias"
                    ]
                ),
                fuente=fuente,
            )

    # =====================================================
    # ALIAS CONFIRMADOS
    # =====================================================

    def _evidencia_alias(
        self,
        *,
        token,
        evidencia,
    ):
        """
        AliasProducto incluye tanto nombres históricos como
        las huellas técnicas generadas por aprendizaje.py.
        """

        aliases = (
            AliasProducto.objects
            .filter(
                activo=True,
                alias_normalizado__icontains=token,
            )
            .select_related(
                "categoria",
                "producto",
            )
            .order_by(
                "-veces_confirmado"
            )
            [:300]
        )

        for alias in aliases:

            if (
                alias.categoria
                is None
            ):
                continue

            confirmaciones = Decimal(
                alias.veces_confirmado
                or 1
            )

            bonificacion = min(
                confirmaciones
                * Decimal("1.50"),
                Decimal("15.00"),
            )

            puntaje = (
                Decimal("15.00")
                + bonificacion
            )

            # Las huellas creadas por aprendizaje.py
            # comienzan con TEC.
            es_tecnico = (
                str(
                    alias.alias_original
                    or ""
                )
                .strip()
                .upper()
                .startswith("TEC ")
            )

            if es_tecnico:
                fuente = (
                    "ALIAS_TECNICO"
                )

                puntaje += (
                    Decimal("5.00")
                )

            else:
                fuente = "ALIAS"

            self._registrar(
                evidencia=evidencia,
                categoria=(
                    alias.categoria
                ),
                token=token,
                puntaje=puntaje,
                cantidad=1,
                fuente=fuente,
            )

    # =====================================================
    # APRENDIZAJES CONFIRMADOS
    # =====================================================

    def _evidencia_aprendizajes(
        self,
        *,
        token,
        evidencia,
    ):
        """
        Utiliza memoria explícitamente confirmada por
        los usuarios.
        """

        aprendizajes = (
            AprendizajeProducto.objects
            .filter(
                activo=True,
            )
            .filter(
                Q(
                    texto_normalizado__icontains=token
                )
                |
                Q(
                    codigo_normalizado__icontains=token
                )
            )
            .select_related(
                "categoria_confirmada",
                "categoria_confirmada__familia",
                "producto_confirmado",
            )
            .order_by(
                "-veces_confirmado",
                "-ultima_confirmacion_en",
            )
            [:300]
        )

        for aprendizaje in (
            aprendizajes
        ):

            categoria = (
                aprendizaje
                .categoria_confirmada
            )

            if categoria is None:
                continue

            confirmaciones = Decimal(
                aprendizaje.veces_confirmado
                or 1
            )

            confianza = Decimal(
                str(
                    aprendizaje.confianza_promedio
                    or 0
                )
            )

            bonificacion_confirmaciones = min(
                confirmaciones
                * Decimal("2.00"),
                Decimal("20.00"),
            )

            bonificacion_confianza = (
                confianza
                * Decimal("0.20")
            )

            puntaje = (
                Decimal("20.00")
                + bonificacion_confirmaciones
                + bonificacion_confianza
            )

            self._registrar(
                evidencia=evidencia,
                categoria=categoria,
                token=token,
                puntaje=puntaje,
                cantidad=1,
                fuente="APRENDIZAJE",
            )

    # =====================================================
    # CATÁLOGO EXISTENTE
    # =====================================================

    def _evidencia_catalogo(
        self,
        *,
        token,
        evidencia,
    ):
        """
        Busca evidencia textual en el catálogo.

        Los atributos técnicos se procesan aparte para no
        mezclarlos con nombre/código/marca.
        """

        productos = list(
            Producto.objects
            .filter(
                activo=True,
                descontinuado=False,
            )
            .filter(
                Q(
                    nombre_base__icontains=token
                )
                |
                Q(
                    descripcion__icontains=token
                )
                |
                Q(
                    codigos__nombre_comercial__icontains=token
                )
                |
                Q(
                    codigos__codigo__icontains=token
                )
                |
                Q(
                    codigos__codigo_barras__icontains=token
                )
                |
                Q(
                    codigos__marca__nombre__icontains=token
                )
            )
            .select_related(
                "categoria",
                "categoria__familia",
            )
            .distinct()
            [:300]
        )

        total_productos = len(
            productos
        )

        if (
            total_productos
            == 0
        ):
            return

        conteo = defaultdict(
            lambda: {
                "categoria": None,
                "cantidad": 0,
            }
        )

        for producto in productos:

            categoria = (
                producto.categoria
            )

            if categoria is None:
                continue

            grupo = conteo[
                categoria.pk
            ]

            grupo["categoria"] = (
                categoria
            )

            grupo["cantidad"] += 1

        for grupo in (
            conteo.values()
        ):

            categoria = (
                grupo["categoria"]
            )

            cantidad = (
                grupo["cantidad"]
            )

            concentracion = (
                Decimal(
                    cantidad
                )
                /
                Decimal(
                    total_productos
                )
            )

            puntaje = (
                concentracion
                * Decimal("35.00")
            )

            self._registrar(
                evidencia=evidencia,
                categoria=categoria,
                token=token,
                puntaje=puntaje,
                cantidad=cantidad,
                fuente="CATALOGO",
            )

    # =====================================================
    # COMPRAS HISTÓRICAS
    # =====================================================

    def _evidencia_compras(
        self,
        *,
        token,
        evidencia,
    ):
        """
        Usa compras realmente interpretadas y confirmadas.

        No aprende de documentos anulados ni de líneas que
        todavía no hayan sido confirmadas.
        """

        from compras.models import (
            DetalleFacturaNormalizado,
        )

        detalles = (
            DetalleFacturaNormalizado.objects
            .filter(
                tipo_destino="INVENTARIO",
                producto_rel__isnull=False,
                producto_rel__activo=True,
                producto_rel__descontinuado=False,
            )
            .filter(
                Q(
                    nombre_limpio__icontains=token
                )
                |
                Q(
                    descripcion_origen__icontains=token
                )
                |
                Q(
                    codigo_origen__icontains=token
                )
                |
                Q(
                    codigo_sistema__icontains=token
                )
                |
                Q(
                    detalle_original__descripcion_proveedor__icontains=token
                )
                |
                Q(
                    detalle_original__codigo_proveedor__icontains=token
                )
            )
            .select_related(
                "producto_rel",
                "producto_rel__categoria",
                "producto_rel__categoria__familia",
                "detalle_original",
                "detalle_original__factura",
                "factura_manual",
            )
            .order_by(
                "-actualizado_en"
            )
            [:300]
        )

        for detalle in detalles:

            producto = (
                detalle.producto_rel
            )

            if (
                not producto
                or not producto.categoria_id
            ):
                continue

            factura = None

            if (
                detalle.detalle_original_id
                and detalle.detalle_original
            ):
                factura = (
                    detalle
                    .detalle_original
                    .factura
                )

            elif (
                detalle.factura_manual_id
            ):
                factura = (
                    detalle.factura_manual
                )

            if not factura:
                continue

            if (
                factura.estado
                == "ANULADA"
            ):
                continue

            if (
                factura.estado
                == "PROCESADA"
                and detalle.ingresado_al_inventario
            ):
                puntaje = (
                    Decimal("35.00")
                )

                fuente = (
                    "COMPRA_PROCESADA"
                )

            elif (
                factura.estado
                == "PROCESADA"
            ):
                puntaje = (
                    Decimal("25.00")
                )

                fuente = (
                    "COMPRA_CONFIRMADA"
                )

            else:
                continue

            self._registrar(
                evidencia=evidencia,
                categoria=(
                    producto.categoria
                ),
                token=token,
                puntaje=puntaje,
                cantidad=1,
                fuente=fuente,
            )

    # =====================================================
    # REGISTRAR EVIDENCIA
    # =====================================================

    @staticmethod
    def _registrar(
        *,
        evidencia,
        categoria,
        token,
        puntaje,
        cantidad,
        fuente,
    ):
        """
        Centraliza acumulación de evidencia.
        """

        if categoria is None:
            return

        grupo = evidencia[
            categoria.pk
        ]

        grupo["categoria"] = (
            categoria
        )

        grupo[
            "coincidencias"
        ] += int(
            cantidad
            or 0
        )

        grupo["fuentes"].add(
            fuente
        )

        token_info = (
            grupo["tokens"]
            .setdefault(
                token,
                {
                    "puntaje": CERO,
                    "coincidencias": 0,
                    "fuentes": set(),
                },
            )
        )

        token_info["puntaje"] += (
            Decimal(
                str(
                    puntaje
                    or 0
                )
            )
        )

        token_info[
            "coincidencias"
        ] += int(
            cantidad
            or 0
        )

        token_info["fuentes"].add(
            fuente
        )

    # =====================================================
    # DETECCIÓN DE TOKEN EN TEXTO
    # =====================================================

    def _texto_contiene_token(
        self,
        texto,
        token,
    ):
        """
        Comprueba coincidencia evitando, cuando sea posible,
        falsos positivos por substring.

        Ejemplo:

            token = 12

        no debería coincidir automáticamente con:

            3120

        pero códigos técnicos como:

            H4
            M20X1.5
            5W30

        siguen siendo utilizables.
        """

        normalizado = (
            normalizar_texto(
                texto
            )
        )

        if not normalizado:
            return False

        token = str(
            token
            or ""
        ).strip().upper()

        if not token:
            return False

        tokens_texto = (
            self._tokens_unicos(
                normalizado
            )
        )

        if token in tokens_texto:
            return True

        # Para referencias técnicas algo más largas,
        # permitimos coincidencia dentro del valor.
        if (
            len(token) >= 3
            and token in normalizado
        ):
            return True

        return False

    # =====================================================
    # TOKENS
    # =====================================================

    @staticmethod
    def _tokens_unicos(
        texto,
    ):
        """
        Tokeniza manteniendo orden y eliminando duplicados.
        """

        resultado = []

        for token in (
            tokenizar_texto(
                texto
            )
        ):

            token = str(
                token
                or ""
            ).strip().upper()

            if not token:
                continue

            if (
                token
                not in resultado
            ):
                resultado.append(
                    token
                )

        return resultado

    # =====================================================
    # TOTAL DE DOCUMENTOS DEL CORPUS
    # =====================================================

    def _total_documentos(
        self,
    ):
        """
        Tamaño aproximado del corpus utilizado para IDF.

        Ahora incluye también:

        - configuraciones técnicas;
        - valores técnicos confirmados.
        """

        if (
            self._total_documentos_cache
            is not None
        ):
            return (
                self._total_documentos_cache
            )

        from compras.models import (
            DetalleFacturaNormalizado,
        )

        total = (
            # Categorías/familias
            Categoria.objects.count()

            # Catálogo
            + Producto.objects
            .filter(
                activo=True,
                descontinuado=False,
            )
            .count()

            # Alias
            + AliasProducto.objects
            .filter(
                activo=True
            )
            .count()

            # Aprendizaje
            + AprendizajeProducto.objects
            .filter(
                activo=True
            )
            .count()

            # Configuración técnica
            + CategoriaAtributo.objects
            .filter(
                activo=True
            )
            .count()

            # Valores técnicos reales
            + ValorAtributoProducto.objects
            .filter(
                producto__activo=True,
                producto__descontinuado=False,
            )
            .count()

            # Compras
            + DetalleFacturaNormalizado.objects
            .filter(
                tipo_destino="INVENTARIO",
            )
            .count()
        )

        self._total_documentos_cache = max(
            int(total),
            1,
        )

        return (
            self._total_documentos_cache
        )

    # =====================================================
    # FRECUENCIA DOCUMENTAL DE UN TOKEN
    # =====================================================

    def _frecuencia_token(
        self,
        token,
    ):
        """
        Calcula cuántos documentos contienen el token.

        Cuanto más común sea un token, menos peso tendrá.

        Ahora considera además:

        - familia;
        - atributos configurados;
        - valores técnicos confirmados.
        """

        from compras.models import (
            DetalleFacturaNormalizado,
        )

        # =================================================
        # CATEGORÍA + FAMILIA
        # =================================================

        categorias = (
            Categoria.objects
            .filter(
                Q(
                    nombre__icontains=token
                )
                |
                Q(
                    familia__nombre__icontains=token
                )
            )
            .distinct()
            .count()
        )

        # =================================================
        # PRODUCTOS
        # =================================================

        productos = (
            Producto.objects
            .filter(
                activo=True,
                descontinuado=False,
            )
            .filter(
                Q(
                    nombre_base__icontains=token
                )
                |
                Q(
                    descripcion__icontains=token
                )
                |
                Q(
                    codigos__nombre_comercial__icontains=token
                )
                |
                Q(
                    codigos__codigo__icontains=token
                )
                |
                Q(
                    codigos__codigo_barras__icontains=token
                )
                |
                Q(
                    codigos__marca__nombre__icontains=token
                )
            )
            .distinct()
            .count()
        )

        # =================================================
        # ATRIBUTOS CONFIGURADOS
        # =================================================

        atributos_configurados = (
            CategoriaAtributo.objects
            .filter(
                activo=True
            )
            .filter(
                Q(
                    atributo__nombre__icontains=token
                )
                |
                Q(
                    atributo__unidad__icontains=token
                )
            )
            .count()
        )

        # =================================================
        # VALORES TÉCNICOS REALES
        # =================================================

        atributos_productos = (
            ValorAtributoProducto.objects
            .filter(
                producto__activo=True,
                producto__descontinuado=False,
            )
            .filter(
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
            )
            .count()
        )

        # =================================================
        # ALIAS
        # =================================================

        aliases = (
            AliasProducto.objects
            .filter(
                activo=True,
                alias_normalizado__icontains=token,
            )
            .count()
        )

        # =================================================
        # APRENDIZAJES
        # =================================================

        aprendizajes = (
            AprendizajeProducto.objects
            .filter(
                activo=True,
            )
            .filter(
                Q(
                    texto_normalizado__icontains=token
                )
                |
                Q(
                    codigo_normalizado__icontains=token
                )
            )
            .count()
        )

        # =================================================
        # COMPRAS
        # =================================================

        compras = (
            DetalleFacturaNormalizado.objects
            .filter(
                tipo_destino="INVENTARIO",
            )
            .filter(
                Q(
                    nombre_limpio__icontains=token
                )
                |
                Q(
                    descripcion_origen__icontains=token
                )
                |
                Q(
                    codigo_origen__icontains=token
                )
                |
                Q(
                    codigo_sistema__icontains=token
                )
                |
                Q(
                    detalle_original__descripcion_proveedor__icontains=token
                )
                |
                Q(
                    detalle_original__codigo_proveedor__icontains=token
                )
            )
            .count()
        )

        frecuencia = (
            categorias
            + productos
            + atributos_configurados
            + atributos_productos
            + aliases
            + aprendizajes
            + compras
        )

        return max(
            int(frecuencia),
            0,
        )

    # =====================================================
    # PESO ESTADÍSTICO DEL TOKEN
    # =====================================================

    def _peso_token(
        self,
        token,
    ):
        """
        Peso tipo IDF generado exclusivamente con los
        datos almacenados.

        Token muy frecuente:
            peso bajo.

        Token raro/específico:
            peso alto.

        Esto es particularmente útil para atributos.

        Ejemplo:

            "12"
                puede existir en muchos productos
                → menor importancia.

            "M20X1.5"
                puede aparecer en pocos
                → mayor importancia.
        """

        if (
            token
            in self._cache_pesos
        ):
            return (
                self._cache_pesos[
                    token
                ]
            )

        total = (
            self._total_documentos()
        )

        frecuencia = (
            self._frecuencia_token(
                token
            )
        )

        # Evitar que el conteo aproximado de las distintas
        # fuentes supere conceptualmente el corpus.
        frecuencia = min(
            frecuencia,
            total,
        )

        if total <= 1:

            peso = Decimal(
                "1.00"
            )

        else:

            numerador = log(
                (
                    total + 1
                )
                /
                (
                    frecuencia + 1
                )
            )

            denominador = log(
                total + 1
            )

            valor = (
                numerador
                / denominador
                if denominador > 0
                else 1
            )

            peso = Decimal(
                str(
                    valor
                )
            )

        peso = (
            min(
                max(
                    peso,
                    CERO,
                ),
                Decimal("1.00"),
            )
            .quantize(
                Decimal("0.0001"),
                rounding=ROUND_HALF_UP,
            )
        )

        self._cache_pesos[
            token
        ] = peso

        return peso

    # =====================================================
    # LIMITAR PORCENTAJE
    # =====================================================

    @staticmethod
    def _limitar_porcentaje(
        valor,
    ):
        """
        Mantiene un porcentaje entre 0 y 100.
        """

        valor = Decimal(
            str(
                valor
                or 0
            )
        )

        return (
            min(
                max(
                    valor,
                    CERO,
                ),
                CIEN,
            )
            .quantize(
                DOS_DECIMALES,
                rounding=ROUND_HALF_UP,
            )
        )