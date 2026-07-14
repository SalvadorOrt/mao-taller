# inventario/services/normalizacion.py

import re
import unicodedata
from typing import Iterable


def convertir_a_texto(valor) -> str:
    """
    Convierte cualquier valor a texto de forma segura.

    None → ""
    """
    if valor is None:
        return ""

    return str(valor).strip()


def quitar_acentos(texto: str) -> str:
    """
    Elimina tildes y signos diacríticos.

    Ejemplo:
        "FILTRO HABITÁCULO"
        → "FILTRO HABITACULO"
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
    Sustituye múltiples espacios, saltos de línea y tabulaciones
    por un solo espacio.
    """
    texto = convertir_a_texto(texto)

    return re.sub(
        r"\s+",
        " ",
        texto,
    ).strip()


def normalizar_texto(valor) -> str:
    """
    Genera una versión normalizada para búsquedas y similitud.

    No modifica el texto original guardado en la factura.

    Ejemplos:
        "Aceite 10W-30 API SP"
        → "ACEITE 10W 30 API SP"

        "Filtro de cabina / habitáculo"
        → "FILTRO DE CABINA HABITACULO"
    """
    texto = convertir_a_texto(valor)

    if not texto:
        return ""

    texto = quitar_acentos(texto)
    texto = texto.upper()

    # Todo separador se convierte en espacio.
    texto = re.sub(
        r"[^A-Z0-9]+",
        " ",
        texto,
    )

    return normalizar_espacios(texto)


def normalizar_codigo(valor) -> str:
    """
    Genera una versión normalizada para comparar códigos.

    Elimina espacios, guiones, puntos y otros separadores.

    Ejemplos:
        "FC-8625" → "FC8625"
        "FC 8625" → "FC8625"
        "fc/8625" → "FC8625"
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


def tokenizar_texto(valor) -> list[str]:
    """
    Divide el texto normalizado en palabras o tokens.

    Mantiene el orden y elimina tokens repetidos.

    Ejemplo:
        "ACEITE MOTOR 10W30 ACEITE"
        → ["ACEITE", "MOTOR", "10W30"]
    """
    texto = normalizar_texto(valor)

    if not texto:
        return []

    resultado = []
    vistos = set()

    for token in texto.split():
        if token not in vistos:
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
    tokens_a = set(tokenizar_texto(texto_a))
    tokens_b = set(tokenizar_texto(texto_b))

    return tokens_a & tokens_b


def unir_textos(*valores) -> str:
    """
    Une varios campos y devuelve un único texto normalizado.

    Útil para combinar:
        nombre_base + descripción + nombre_comercial.
    """
    textos = [
        convertir_a_texto(valor)
        for valor in valores
        if convertir_a_texto(valor)
    ]

    return normalizar_texto(
        " ".join(textos)
    )


def generar_ngramas(
    valor,
    longitud: int = 2,
) -> list[str]:
    """
    Genera grupos consecutivos de palabras.

    Ejemplo:
        "ACEITE MOTOR 10W30", longitud=2

        [
            "ACEITE MOTOR",
            "MOTOR 10W30",
        ]

    Ayuda a comparar frases y no únicamente palabras individuales.
    """
    if longitud <= 0:
        raise ValueError(
            "La longitud del n-grama debe ser mayor que cero."
        )

    tokens = tokenizar_texto(valor)

    if len(tokens) < longitud:
        return []

    return [
        " ".join(tokens[indice:indice + longitud])
        for indice in range(
            len(tokens) - longitud + 1
        )
    ]


def contiene_token(
    texto,
    token,
) -> bool:
    """
    Comprueba si un token completo existe dentro de un texto.

    Evita coincidencias parciales incorrectas.
    """
    token_normalizado = normalizar_texto(token)

    if not token_normalizado:
        return False

    return token_normalizado in set(
        tokenizar_texto(texto)
    )


def normalizar_lista_textos(
    valores: Iterable,
) -> list[str]:
    """
    Normaliza una colección de textos y elimina resultados vacíos
    y duplicados.
    """
    resultado = []
    vistos = set()

    for valor in valores:
        texto = normalizar_texto(valor)

        if texto and texto not in vistos:
            resultado.append(texto)
            vistos.add(texto)

    return resultado