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
        None       -> ""
        123        -> "123"
        " texto "  -> "texto"
    """
    if valor is None:
        return ""

    return str(valor).strip()


def quitar_acentos(texto: str) -> str:
    """
    Elimina tildes y signos diacríticos.

    Ejemplo:
        "FILTRO HABITÁCULO"
        -> "FILTRO HABITACULO"
    """
    texto = convertir_a_texto(texto)

    if not texto:
        return ""

    descompuesto = unicodedata.normalize(
        "NFD",
        texto,
    )

    return "".join(
        caracter
        for caracter in descompuesto
        if unicodedata.category(caracter) != "Mn"
    )


def normalizar_espacios(texto: str) -> str:
    """
    Sustituye espacios repetidos, saltos de línea y tabulaciones
    por un único espacio.
    """
    texto = convertir_a_texto(texto)

    if not texto:
        return ""

    return re.sub(
        r"\s+",
        " ",
        texto,
    ).strip()


# =========================================================
# NORMALIZACIONES ESPECIALIZADAS
# =========================================================

def normalizar_viscosidades(texto: str) -> str:
    """
    Unifica diferentes formas de escribir viscosidades SAE.

    Ejemplos:
        5W30       -> 5W30
        5W-30      -> 5W30
        5 W 30     -> 5W30
        5/W/30     -> 5W30
        5-W-30     -> 5W30
        SAE 20W-50 -> SAE 20W50
    """
    texto = convertir_a_texto(texto)

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
        flags=re.IGNORECASE | re.VERBOSE,
    )

    return patron.sub(
        lambda coincidencia: (
            f"{coincidencia.group(1)}"
            f"W"
            f"{coincidencia.group(2)}"
        ),
        texto,
    )

def normalizar_medidas_comunes(texto: str) -> str:
    """
    Unifica algunas medidas escritas con espacios innecesarios.

    Ejemplos:
        12 X 1.5 -> 12X1.5
        205 / 55 R16 -> 205/55R16

    Esta función no elimina unidades ni interpreta el producto.
    """
    texto = convertir_a_texto(texto)

    if not texto:
        return ""

    # Medidas del tipo 12 X 1.5
    texto = re.sub(
        r"(?<=\d)\s*[Xx]\s*(?=\d)",
        "X",
        texto,
    )

    # Medidas de neumáticos: 205 / 55 R 16
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
        flags=re.IGNORECASE | re.VERBOSE,
    )

    return texto


# =========================================================
# NORMALIZACIÓN DE DESCRIPCIONES
# =========================================================

def normalizar_texto(valor) -> str:
    """
    Genera una versión normalizada para búsquedas, comparación
    y similitud.

    No modifica el texto original almacenado.

    Ejemplos:
        "Aceite 5W-30 API SP"
        -> "ACEITE 5W30 API SP"

        "ACEITE 5 W 30"
        -> "ACEITE 5W30"

        "Filtro de cabina / habitáculo"
        -> "FILTRO DE CABINA HABITACULO"
    """
    texto = convertir_a_texto(valor)

    if not texto:
        return ""

    texto = quitar_acentos(texto)
    texto = texto.upper()

    # Estas transformaciones deben ejecutarse antes de eliminar
    # separadores, para no perder la estructura de viscosidades
    # y medidas.
    texto = normalizar_viscosidades(texto)
    texto = normalizar_medidas_comunes(texto)

    # Conservamos únicamente letras y números como tokens.
    # Los separadores restantes se convierten en espacios.
    texto = re.sub(
        r"[^A-Z0-9]+",
        " ",
        texto,
    )

    return normalizar_espacios(texto)


# =========================================================
# NORMALIZACIÓN DE CÓDIGOS
# =========================================================

def normalizar_codigo(valor) -> str:
    """
    Genera una versión normalizada para comparar códigos.

    Elimina espacios, guiones, puntos, barras y separadores.

    Ejemplos:
        "FC-8625"   -> "FC8625"
        "FC 8625"   -> "FC8625"
        "fc/8625"   -> "FC8625"
        "AFI.22005" -> "AFI22005"
    """
    texto = convertir_a_texto(valor)

    if not texto:
        return ""

    texto = quitar_acentos(texto)
    texto = texto.upper()

    return re.sub(
        r"[^A-Z0-9]",
        "",
        texto,
    )


def codigos_equivalentes(
    codigo_a,
    codigo_b,
) -> bool:
    """
    Indica si dos códigos representan el mismo valor normalizado.

    Ejemplo:
        AFI-22005 y AFI 22005 -> True
    """
    normalizado_a = normalizar_codigo(
        codigo_a
    )
    normalizado_b = normalizar_codigo(
        codigo_b
    )

    if not normalizado_a or not normalizado_b:
        return False

    return normalizado_a == normalizado_b


# =========================================================
# TOKENIZACIÓN
# =========================================================

def tokenizar_texto(valor) -> list[str]:
    """
    Divide el texto normalizado en tokens.

    Mantiene el orden y elimina tokens repetidos.

    Ejemplos:
        "ACEITE MOTOR 5W-30 ACEITE"
        -> ["ACEITE", "MOTOR", "5W30"]

        "FILTRO COMBUSTIBLE NISSAN VERSA"
        -> ["FILTRO", "COMBUSTIBLE", "NISSAN", "VERSA"]
    """
    texto = normalizar_texto(valor)

    if not texto:
        return []

    resultado = []
    vistos = set()

    for token in texto.split():
        if token in vistos:
            continue

        resultado.append(token)
        vistos.add(token)

    return resultado


def obtener_tokens_comunes(
    texto_a,
    texto_b,
) -> set[str]:
    """
    Devuelve los tokens compartidos entre dos textos.
    """
    tokens_a = set(
        tokenizar_texto(texto_a)
    )
    tokens_b = set(
        tokenizar_texto(texto_b)
    )

    return tokens_a & tokens_b


def contiene_token(
    texto,
    token,
) -> bool:
    """
    Comprueba si uno o varios tokens completos existen dentro
    de un texto.

    Evita coincidencias parciales incorrectas.

    Ejemplos:
        contiene_token("FILTRO ACEITE", "ACEITE")
        -> True

        contiene_token("FILTRO COMBUSTIBLE", "FILTRO COMBUSTIBLE")
        -> True

        contiene_token("ACEITERA", "ACEITE")
        -> False
    """
    tokens_texto = tokenizar_texto(
        texto
    )
    tokens_buscados = tokenizar_texto(
        token
    )

    if not tokens_texto or not tokens_buscados:
        return False

    cantidad_buscados = len(
        tokens_buscados
    )

    if cantidad_buscados == 1:
        return tokens_buscados[0] in set(
            tokens_texto
        )

    limite = (
        len(tokens_texto)
        - cantidad_buscados
        + 1
    )

    for indice in range(max(limite, 0)):
        fragmento = tokens_texto[
            indice:indice + cantidad_buscados
        ]

        if fragmento == tokens_buscados:
            return True

    return False


# =========================================================
# COMBINACIÓN DE CAMPOS
# =========================================================

def unir_textos(*valores) -> str:
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
        texto = convertir_a_texto(
            valor
        )

        if texto:
            textos.append(texto)

    return normalizar_texto(
        " ".join(textos)
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
        "FILTRO COMBUSTIBLE NISSAN VERSA"

        Con longitud=2:

        [
            "FILTRO COMBUSTIBLE",
            "COMBUSTIBLE NISSAN",
            "NISSAN VERSA",
        ]

    Permite comparar frases y no solo palabras individuales.
    """
    if longitud <= 0:
        raise ValueError(
            "La longitud del n-grama debe ser mayor que cero."
        )

    tokens = tokenizar_texto(
        valor
    )

    if len(tokens) < longitud:
        return []

    return [
        " ".join(
            tokens[
                indice:indice + longitud
            ]
        )
        for indice in range(
            len(tokens) - longitud + 1
        )
    ]


def generar_ngramas_multiples(
    valor,
    longitudes=(2, 3),
) -> list[str]:
    """
    Genera n-gramas de varias longitudes sin duplicados.

    Ejemplo:
        longitudes=(2, 3)
    """
    resultado = []
    vistos = set()

    for longitud in longitudes:
        for ngrama in generar_ngramas(
            valor,
            longitud=longitud,
        ):
            if ngrama in vistos:
                continue

            resultado.append(ngrama)
            vistos.add(ngrama)

    return resultado


# =========================================================
# COLECCIONES
# =========================================================

def normalizar_lista_textos(
    valores: Iterable,
) -> list[str]:
    """
    Normaliza una colección y elimina valores vacíos
    y duplicados.
    """
    resultado = []
    vistos = set()

    for valor in valores:
        texto = normalizar_texto(
            valor
        )

        if not texto or texto in vistos:
            continue

        resultado.append(texto)
        vistos.add(texto)

    return resultado