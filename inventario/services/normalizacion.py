# inventario/services/normalizacion.py

import re
import unicodedata

from typing import Iterable


# =========================================================
# CONVERSIÓN BÁSICA
# =========================================================

def convertir_a_texto(valor) -> str:
    """
    Convierte cualquier valor a texto de forma segura.

    Ejemplos:

        None
        -> ""

        123
        -> "123"

        " texto "
        -> "texto"
    """

    if valor is None:
        return ""

    return str(valor).strip()


# =========================================================
# ACENTOS
# =========================================================

def quitar_acentos(texto: str) -> str:
    """
    Elimina tildes y signos diacríticos.

    Ejemplo:

        FILTRO HABITÁCULO
        -> FILTRO HABITACULO
    """

    texto = convertir_a_texto(
        texto
    )

    if not texto:
        return ""

    descompuesto = (
        unicodedata.normalize(
            "NFD",
            texto,
        )
    )

    return "".join(
        caracter
        for caracter in descompuesto
        if unicodedata.category(
            caracter
        ) != "Mn"
    )


# =========================================================
# ESPACIOS
# =========================================================

def normalizar_espacios(
    texto: str,
) -> str:
    """
    Sustituye espacios repetidos, tabs y saltos
    de línea por un solo espacio.
    """

    texto = convertir_a_texto(
        texto
    )

    if not texto:
        return ""

    return re.sub(
        r"\s+",
        " ",
        texto,
    ).strip()


# =========================================================
# DECIMALES TÉCNICOS
# =========================================================

def normalizar_decimales_tecnicos(
    texto: str,
) -> str:
    """
    Convierte coma decimal a punto cuando realmente
    está entre números.

    Ejemplos:

        1,5
        -> 1.5

        M20X1,5
        -> M20X1.5

        12,50 MM
        -> 12.50 MM

    No modifica comas que no sean decimales.
    """

    texto = convertir_a_texto(
        texto
    )

    if not texto:
        return ""

    return re.sub(
        r"(?<=\d),(?=\d)",
        ".",
        texto,
    )


# =========================================================
# VISCOSIDADES
# =========================================================

def normalizar_viscosidades(
    texto: str,
) -> str:
    """
    Unifica diferentes formas de escribir viscosidades SAE.

    Ejemplos:

        5W30
        -> 5W30

        5W-30
        -> 5W30

        5 W 30
        -> 5W30

        5/W/30
        -> 5W30

        SAE 20W-50
        -> SAE 20W50
    """

    texto = convertir_a_texto(
        texto
    )

    if not texto:
        return ""

    patron = re.compile(
        r"""
        (?<![A-Z0-9])
        (\d{1,2})
        \s*
        [-./]?
        \s*
        W
        \s*
        [-./]?
        \s*
        (\d{1,2})
        (?![A-Z0-9])
        """,
        flags=(
            re.IGNORECASE
            | re.VERBOSE
        ),
    )

    return patron.sub(
        lambda coincidencia: (
            f"{coincidencia.group(1)}"
            f"W"
            f"{coincidencia.group(2)}"
        ),
        texto,
    )


# =========================================================
# ROSCAS
# =========================================================

def normalizar_roscas(
    texto: str,
) -> str:
    """
    Normaliza medidas de rosca métricas.

    Ejemplos:

        M 20 x 1.5
        -> M20X1.5

        M20 X 1,5
        -> M20X1.5

        M 14 x 1.25
        -> M14X1.25

    No intenta determinar qué producto utiliza la rosca.
    Solo normaliza su representación.
    """

    texto = convertir_a_texto(
        texto
    )

    if not texto:
        return ""

    texto = normalizar_decimales_tecnicos(
        texto
    )

    patron = re.compile(
        r"""
        (?<![A-Z0-9])
        M
        \s*
        (\d{1,3}(?:\.\d+)?)
        \s*
        [Xx]
        \s*
        (\d+(?:\.\d+)?)
        (?![A-Z0-9])
        """,
        flags=(
            re.IGNORECASE
            | re.VERBOSE
        ),
    )

    return patron.sub(
        lambda coincidencia: (
            f"M{coincidencia.group(1)}"
            f"X{coincidencia.group(2)}"
        ),
        texto,
    )


# =========================================================
# MEDIDAS COMUNES
# =========================================================

def normalizar_medidas_comunes(
    texto: str,
) -> str:
    """
    Normaliza representaciones comunes de medidas.

    Ejemplos:

        12 X 1.5
        -> 12X1.5

        205 / 55 R16
        -> 205/55R16

        205/55 R 16
        -> 205/55R16

    Esta función no interpreta el significado del producto.
    """

    texto = convertir_a_texto(
        texto
    )

    if not texto:
        return ""

    texto = normalizar_decimales_tecnicos(
        texto
    )

    # =====================================================
    # MEDIDAS NUMÉRICAS TIPO 12 X 1.5
    # =====================================================

    texto = re.sub(
        r"(?<=\d)\s*[Xx]\s*(?=\d)",
        "X",
        texto,
    )

    # =====================================================
    # MEDIDAS DE NEUMÁTICOS
    # =====================================================

    texto = re.sub(
        r"""
        (?<!\d)
        (\d{3})
        \s*/\s*
        (\d{2})
        \s*R\s*
        (\d{2})
        (?!\d)
        """,
        lambda coincidencia: (
            f"{coincidencia.group(1)}/"
            f"{coincidencia.group(2)}"
            f"R{coincidencia.group(3)}"
        ),
        texto,
        flags=(
            re.IGNORECASE
            | re.VERBOSE
        ),
    )

    return texto


# =========================================================
# UNIDADES TÉCNICAS
# =========================================================

def normalizar_unidades_tecnicas(
    texto: str,
) -> str:
    """
    Normaliza unidades técnicas comunes únicamente cuando
    aparecen asociadas a un número.

    Esto permite que distintas escrituras representen
    la misma evidencia técnica.

    Ejemplos:

        12 voltios
        -> 12V

        12 V
        -> 12V

        60 watts
        -> 60W

        70 amperios hora
        -> 70AH

        145 milímetros
        -> 145MM

        1,5 litros
        -> 1.5L

        4 bar
        -> 4BAR

    No contiene vocabulario de productos.
    Solo normaliza unidades físicas.
    """

    texto = convertir_a_texto(
        texto
    )

    if not texto:
        return ""

    texto = quitar_acentos(
        texto
    ).upper()

    texto = (
        normalizar_decimales_tecnicos(
            texto
        )
    )

    # =====================================================
    # AMPERIOS HORA
    # =====================================================

    texto = re.sub(
        r"""
        (?<![A-Z0-9])
        (\d+(?:\.\d+)?)
        \s*
        (?:
            AMP(?:ERIO)?S?
            \s*
            HORA(?:S)?
            |
            A\s*H
            |
            AH
        )
        (?![A-Z])
        """,
        r"\1AH",
        texto,
        flags=re.VERBOSE,
    )

    # =====================================================
    # VOLTAJE
    # =====================================================

    texto = re.sub(
        r"""
        (?<![A-Z0-9])
        (\d+(?:\.\d+)?)
        \s*
        (?:V|VOLTIO(?:S)?|VOLT(?:S)?)
        (?![A-Z])
        """,
        r"\1V",
        texto,
        flags=re.VERBOSE,
    )

    # =====================================================
    # POTENCIA
    # =====================================================

    texto = re.sub(
        r"""
        (?<![A-Z0-9])
        (\d+(?:\.\d+)?)
        \s*
        (?:W|WATT(?:S)?|VATIO(?:S)?)
        (?![A-Z])
        """,
        r"\1W",
        texto,
        flags=re.VERBOSE,
    )

    texto = re.sub(
        r"""
        (?<![A-Z0-9])
        (\d+(?:\.\d+)?)
        \s*
        (?:KW|KILOWATT(?:S)?)
        (?![A-Z])
        """,
        r"\1KW",
        texto,
        flags=re.VERBOSE,
    )

    # =====================================================
    # LONGITUD
    # =====================================================

    texto = re.sub(
        r"""
        (?<![A-Z0-9])
        (\d+(?:\.\d+)?)
        \s*
        (?:MM|MILIMETRO(?:S)?)
        (?![A-Z])
        """,
        r"\1MM",
        texto,
        flags=re.VERBOSE,
    )

    texto = re.sub(
        r"""
        (?<![A-Z0-9])
        (\d+(?:\.\d+)?)
        \s*
        (?:CM|CENTIMETRO(?:S)?)
        (?![A-Z])
        """,
        r"\1CM",
        texto,
        flags=re.VERBOSE,
    )

    # =====================================================
    # VOLUMEN
    # =====================================================

    texto = re.sub(
        r"""
        (?<![A-Z0-9])
        (\d+(?:\.\d+)?)
        \s*
        (?:ML|MILILITRO(?:S)?)
        (?![A-Z])
        """,
        r"\1ML",
        texto,
        flags=re.VERBOSE,
    )

    texto = re.sub(
        r"""
        (?<![A-Z0-9])
        (\d+(?:\.\d+)?)
        \s*
        (?:L|LT|LTS|LITRO(?:S)?)
        (?![A-Z])
        """,
        r"\1L",
        texto,
        flags=re.VERBOSE,
    )

    # =====================================================
    # PRESIÓN
    # =====================================================

    texto = re.sub(
        r"""
        (?<![A-Z0-9])
        (\d+(?:\.\d+)?)
        \s*
        BAR
        (?![A-Z])
        """,
        r"\1BAR",
        texto,
        flags=re.VERBOSE,
    )

    texto = re.sub(
        r"""
        (?<![A-Z0-9])
        (\d+(?:\.\d+)?)
        \s*
        PSI
        (?![A-Z])
        """,
        r"\1PSI",
        texto,
        flags=re.VERBOSE,
    )

    # =====================================================
    # PORCENTAJE
    # =====================================================

    texto = re.sub(
        r"""
        (?<![A-Z0-9])
        (\d+(?:\.\d+)?)
        \s*
        %
        """,
        r"\1%",
        texto,
        flags=re.VERBOSE,
    )

    return normalizar_espacios(
        texto
    )


# =========================================================
# NORMALIZACIÓN GENERAL DE DESCRIPCIONES
# =========================================================

def normalizar_texto(
    valor,
) -> str:
    """
    Genera una versión estable y general para:

    - búsquedas;
    - aprendizaje histórico;
    - comparación;
    - similitud textual.

    IMPORTANTE:

    Esta función conserva la lógica histórica del sistema.

    Para valores técnicos utilizar adicionalmente:

        normalizar_valor_tecnico()

    Ejemplos:

        Aceite 5W-30 API SP
        -> ACEITE 5W30 API SP

        ACEITE 5 W 30
        -> ACEITE 5W30

        Filtro de cabina / habitáculo
        -> FILTRO DE CABINA HABITACULO
    """

    texto = convertir_a_texto(
        valor
    )

    if not texto:
        return ""

    texto = quitar_acentos(
        texto
    )

    texto = texto.upper()

    # Estas transformaciones deben ejecutarse antes
    # de eliminar separadores.
    texto = normalizar_viscosidades(
        texto
    )

    texto = normalizar_medidas_comunes(
        texto
    )

    # =====================================================
    # COMPATIBILIDAD HISTÓRICA
    # =====================================================
    #
    # Conservamos solamente letras y números.
    #
    # Esto evita cambiar de forma brusca los valores
    # almacenados previamente en:
    #
    # - AprendizajeProducto.texto_normalizado
    # - AliasProducto.alias_normalizado
    #
    # =====================================================

    texto = re.sub(
        r"[^A-Z0-9]+",
        " ",
        texto,
    )

    return normalizar_espacios(
        texto
    )


# =========================================================
# NORMALIZACIÓN TÉCNICA
# =========================================================

def normalizar_valor_tecnico(
    valor,
    unidad=None,
) -> str:
    """
    Normaliza específicamente valores de atributos técnicos.

    A diferencia de normalizar_texto(), aquí conservamos
    determinados símbolos importantes:

        .
        /
        %
        +
        -

    porque pueden formar parte de una especificación.

    Ejemplos:

        M 20 x 1,5
        -> M20X1.5

        12 voltios
        -> 12V

        60 W
        -> 60W

        5 W 30
        -> 5W30

        205 / 55 R 16
        -> 205/55R16

    Si recibe unidad:

        valor = 12
        unidad = V

        -> 12V
    """

    texto = convertir_a_texto(
        valor
    )

    unidad = convertir_a_texto(
        unidad
    )

    if (
        not texto
        and not unidad
    ):
        return ""

    if (
        texto
        and unidad
    ):
        texto = (
            f"{texto} {unidad}"
        )

    elif unidad:
        texto = unidad

    texto = quitar_acentos(
        texto
    ).upper()

    texto = normalizar_decimales_tecnicos(
        texto
    )

    texto = normalizar_viscosidades(
        texto
    )

    texto = normalizar_roscas(
        texto
    )

    texto = normalizar_medidas_comunes(
        texto
    )

    texto = normalizar_unidades_tecnicas(
        texto
    )

    # =====================================================
    # CONSERVAR SÍMBOLOS TÉCNICOS
    # =====================================================

    texto = re.sub(
        r"[^A-Z0-9./%+\-]+",
        " ",
        texto,
    )

    return normalizar_espacios(
        texto
    )


# =========================================================
# NORMALIZACIÓN DE CÓDIGOS
# =========================================================

def normalizar_codigo(
    valor,
) -> str:
    """
    Genera una versión normalizada para comparar códigos.

    Elimina espacios, guiones, puntos, barras y separadores.

    Ejemplos:

        FC-8625
        -> FC8625

        FC 8625
        -> FC8625

        fc/8625
        -> FC8625

        AFI.22005
        -> AFI22005
    """

    texto = convertir_a_texto(
        valor
    )

    if not texto:
        return ""

    texto = quitar_acentos(
        texto
    )

    texto = texto.upper()

    return re.sub(
        r"[^A-Z0-9]",
        "",
        texto,
    )


# =========================================================
# CÓDIGOS EQUIVALENTES
# =========================================================

def codigos_equivalentes(
    codigo_a,
    codigo_b,
) -> bool:
    """
    Indica si dos códigos representan el mismo
    valor normalizado.

    Ejemplo:

        AFI-22005
        AFI 22005

        -> True
    """

    normalizado_a = (
        normalizar_codigo(
            codigo_a
        )
    )

    normalizado_b = (
        normalizar_codigo(
            codigo_b
        )
    )

    if (
        not normalizado_a
        or not normalizado_b
    ):
        return False

    return (
        normalizado_a
        == normalizado_b
    )


# =========================================================
# TOKENIZACIÓN GENERAL
# =========================================================

def tokenizar_texto(
    valor,
) -> list[str]:
    """
    Divide texto normalizado en tokens únicos.

    Mantiene el orden.

    Ejemplo:

        ACEITE MOTOR 5W-30 ACEITE

        -> [
            "ACEITE",
            "MOTOR",
            "5W30",
        ]
    """

    texto = normalizar_texto(
        valor
    )

    if not texto:
        return []

    resultado = []

    vistos = set()

    for token in (
        texto.split()
    ):

        if token in vistos:
            continue

        resultado.append(
            token
        )

        vistos.add(
            token
        )

    return resultado


# =========================================================
# TOKENIZACIÓN TÉCNICA
# =========================================================

def tokenizar_valor_tecnico(
    valor,
    unidad=None,
) -> list[str]:
    """
    Tokeniza un valor técnico sin destruir su estructura.

    Ejemplo:

        M 20 X 1.5
        -> ["M20X1.5"]

        12 VOLTIOS
        -> ["12V"]

        5W-30
        -> ["5W30"]

    Además agrega tokens genéricos compatibles con el
    motor histórico cuando aportan información distinta.
    """

    tecnico = (
        normalizar_valor_tecnico(
            valor,
            unidad=unidad,
        )
    )

    resultado = []

    vistos = set()

    # =====================================================
    # TOKENS TÉCNICOS
    # =====================================================

    for token in tecnico.split():

        if (
            token
            and token not in vistos
        ):
            resultado.append(
                token
            )

            vistos.add(
                token
            )

    # =====================================================
    # TOKENS GENERALES
    # =====================================================

    general = normalizar_texto(
        f"{convertir_a_texto(valor)} "
        f"{convertir_a_texto(unidad)}"
    )

    for token in general.split():

        if (
            token
            and token not in vistos
        ):
            resultado.append(
                token
            )

            vistos.add(
                token
            )

    return resultado


# =========================================================
# TOKENS COMUNES
# =========================================================

def obtener_tokens_comunes(
    texto_a,
    texto_b,
) -> set[str]:
    """
    Devuelve tokens generales compartidos.
    """

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

    return (
        tokens_a
        & tokens_b
    )


# =========================================================
# TOKENS TÉCNICOS COMUNES
# =========================================================

def obtener_tokens_tecnicos_comunes(
    valor_a,
    valor_b,
    *,
    unidad_a=None,
    unidad_b=None,
) -> set[str]:
    """
    Compara valores técnicos.

    Ejemplo:

        "M 20 X 1,5"
        "M20X1.5"

        -> {"M20X1.5"}
    """

    tokens_a = set(
        tokenizar_valor_tecnico(
            valor_a,
            unidad=unidad_a,
        )
    )

    tokens_b = set(
        tokenizar_valor_tecnico(
            valor_b,
            unidad=unidad_b,
        )
    )

    return (
        tokens_a
        & tokens_b
    )


# =========================================================
# CONTIENE TOKEN
# =========================================================

def contiene_token(
    texto,
    token,
) -> bool:
    """
    Comprueba tokens completos.

    Evita coincidencias parciales incorrectas.

    Ejemplo:

        contiene_token(
            "FILTRO ACEITE",
            "ACEITE"
        )
        -> True

        contiene_token(
            "ACEITERA",
            "ACEITE"
        )
        -> False
    """

    tokens_texto = (
        tokenizar_texto(
            texto
        )
    )

    tokens_buscados = (
        tokenizar_texto(
            token
        )
    )

    if (
        not tokens_texto
        or not tokens_buscados
    ):
        return False

    cantidad_buscados = len(
        tokens_buscados
    )

    if cantidad_buscados == 1:

        return (
            tokens_buscados[0]
            in set(tokens_texto)
        )

    limite = (
        len(tokens_texto)
        - cantidad_buscados
        + 1
    )

    for indice in range(
        max(
            limite,
            0,
        )
    ):

        fragmento = (
            tokens_texto[
                indice:
                indice + cantidad_buscados
            ]
        )

        if (
            fragmento
            == tokens_buscados
        ):
            return True

    return False


# =========================================================
# CONTIENE TOKEN TÉCNICO
# =========================================================

def contiene_token_tecnico(
    texto,
    token,
    *,
    unidad=None,
) -> bool:
    """
    Comprueba tokens técnicos normalizados.

    Especialmente útil para:

        H4
        H7
        LED
        12V
        60W
        70AH
        M20X1.5
        5W30
        205/55R16
    """

    tokens_texto = set(
        tokenizar_valor_tecnico(
            texto,
            unidad=unidad,
        )
    )

    tokens_buscados = (
        tokenizar_valor_tecnico(
            token
        )
    )

    if (
        not tokens_texto
        or not tokens_buscados
    ):
        return False

    return all(
        token_buscado
        in tokens_texto
        for token_buscado
        in tokens_buscados
    )


# =========================================================
# COMBINACIÓN DE CAMPOS
# =========================================================

def unir_textos(
    *valores,
) -> str:
    """
    Une varios campos y devuelve un único texto normalizado.

    Útil para combinar:

        nombre_base
        descripción
        nombre_comercial
        marca
        código
    """

    textos = []

    for valor in valores:

        texto = (
            convertir_a_texto(
                valor
            )
        )

        if texto:
            textos.append(
                texto
            )

    return normalizar_texto(
        " ".join(
            textos
        )
    )


# =========================================================
# COMBINACIÓN TÉCNICA
# =========================================================

def unir_textos_tecnicos(
    *valores,
) -> str:
    """
    Une varias evidencias técnicas preservando su estructura.

    Ejemplo:

        unir_textos_tecnicos(
            "H4",
            "LED",
            "12 voltios",
            "60 W"
        )

        -> "H4 LED 12V 60W"
    """

    resultado = []

    vistos = set()

    for valor in valores:

        normalizado = (
            normalizar_valor_tecnico(
                valor
            )
        )

        if (
            not normalizado
            or normalizado in vistos
        ):
            continue

        resultado.append(
            normalizado
        )

        vistos.add(
            normalizado
        )

    return normalizar_espacios(
        " ".join(
            resultado
        )
    )


# =========================================================
# CONSTRUIR HUELLA DE ATRIBUTO
# =========================================================

def construir_huella_atributo(
    nombre,
    valor,
    unidad=None,
) -> str:
    """
    Construye una representación normalizada de un
    atributo técnico.

    Ejemplo:

        nombre = "Voltaje"
        valor = "12"
        unidad = "V"

        -> "VOLTAJE 12V"

    Otro:

        nombre = "Rosca"
        valor = "M 20 X 1,5"

        -> "ROSCA M20X1.5"
    """

    nombre_normalizado = (
        normalizar_texto(
            nombre
        )
    )

    valor_normalizado = (
        normalizar_valor_tecnico(
            valor,
            unidad=unidad,
        )
    )

    partes = []

    if nombre_normalizado:
        partes.append(
            nombre_normalizado
        )

    if valor_normalizado:
        partes.append(
            valor_normalizado
        )

    return normalizar_espacios(
        " ".join(
            partes
        )
    )


# =========================================================
# N-GRAMAS
# =========================================================

def generar_ngramas(
    valor,
    longitud: int = 2,
) -> list[str]:
    """
    Genera grupos consecutivos de palabras.

    Ejemplo:

        FILTRO COMBUSTIBLE NISSAN VERSA

        longitud=2:

        [
            "FILTRO COMBUSTIBLE",
            "COMBUSTIBLE NISSAN",
            "NISSAN VERSA",
        ]
    """

    if longitud <= 0:
        raise ValueError(
            "La longitud del n-grama debe "
            "ser mayor que cero."
        )

    tokens = tokenizar_texto(
        valor
    )

    if (
        len(tokens)
        < longitud
    ):
        return []

    return [
        " ".join(
            tokens[
                indice:
                indice + longitud
            ]
        )
        for indice in range(
            len(tokens)
            - longitud
            + 1
        )
    ]


# =========================================================
# N-GRAMAS MÚLTIPLES
# =========================================================

def generar_ngramas_multiples(
    valor,
    longitudes=(2, 3),
) -> list[str]:
    """
    Genera n-gramas de varias longitudes
    sin duplicados.
    """

    resultado = []

    vistos = set()

    for longitud in longitudes:

        for ngrama in generar_ngramas(
            valor,
            longitud=longitud,
        ):

            if (
                ngrama
                in vistos
            ):
                continue

            resultado.append(
                ngrama
            )

            vistos.add(
                ngrama
            )

    return resultado


# =========================================================
# COLECCIONES GENERALES
# =========================================================

def normalizar_lista_textos(
    valores: Iterable,
) -> list[str]:
    """
    Normaliza una colección de textos.

    Elimina:

    - vacíos;
    - duplicados.
    """

    resultado = []

    vistos = set()

    for valor in valores:

        texto = (
            normalizar_texto(
                valor
            )
        )

        if (
            not texto
            or texto in vistos
        ):
            continue

        resultado.append(
            texto
        )

        vistos.add(
            texto
        )

    return resultado


# =========================================================
# COLECCIONES TÉCNICAS
# =========================================================

def normalizar_lista_valores_tecnicos(
    valores: Iterable,
) -> list[str]:
    """
    Normaliza una colección de valores técnicos.

    Ejemplo:

        [
            "12 voltios",
            "12 V",
            "60 W",
            "M 20 X 1,5",
        ]

        -> [
            "12V",
            "60W",
            "M20X1.5",
        ]

    También elimina duplicados.
    """

    resultado = []

    vistos = set()

    for valor in valores:

        texto = (
            normalizar_valor_tecnico(
                valor
            )
        )

        if (
            not texto
            or texto in vistos
        ):
            continue

        resultado.append(
            texto
        )

        vistos.add(
            texto
        )

    return resultado