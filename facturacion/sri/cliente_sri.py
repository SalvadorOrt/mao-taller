from __future__ import annotations

import base64
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

import requests

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils.dateparse import parse_datetime


# =========================================================
# CONFIGURACIÓN
# =========================================================
#
# Los endpoints pueden sobrescribirse desde settings.py.
# Se dejan valores oficiales actuales como fallback.
#
# Ambiente:
#   "1" = PRUEBAS / CERTIFICACIÓN
#   "2" = PRODUCCIÓN
# =========================================================

AMBIENTE_PRUEBAS = "1"
AMBIENTE_PRODUCCION = "2"

DEFAULT_RECEPCION_PRUEBAS = (
    "https://celcer.sri.gob.ec/"
    "comprobantes-electronicos-ws/"
    "RecepcionComprobantesOffline"
)

DEFAULT_AUTORIZACION_PRUEBAS = (
    "https://celcer.sri.gob.ec/"
    "comprobantes-electronicos-ws/"
    "AutorizacionComprobantesOffline"
)

DEFAULT_RECEPCION_PRODUCCION = (
    "https://cel.sri.gob.ec/"
    "comprobantes-electronicos-ws/"
    "RecepcionComprobantesOffline"
)

DEFAULT_AUTORIZACION_PRODUCCION = (
    "https://cel.sri.gob.ec/"
    "comprobantes-electronicos-ws/"
    "AutorizacionComprobantesOffline"
)

SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
NS_RECEPCION = "http://ec.gob.sri.ws.recepcion"
NS_AUTORIZACION = "http://ec.gob.sri.ws.autorizacion"

MAX_XML_INDIVIDUAL_BYTES = 320 * 1024

DEFAULT_CONNECT_TIMEOUT = 10
DEFAULT_READ_TIMEOUT = 40


# =========================================================
# EXCEPCIONES
# =========================================================

class ClienteSRIError(Exception):
    """Error base de comunicación con los Web Services del SRI."""


class ConexionSRIError(ClienteSRIError):
    """No fue posible comunicarse correctamente con el SRI."""


class RespuestaSRIError(ClienteSRIError):
    """El SRI respondió con una estructura inesperada o inválida."""


# =========================================================
# RESULTADOS
# =========================================================

@dataclass
class ResultadoRecepcion:
    estado: str
    mensajes: list[dict[str, str]]
    clave_acceso: str = ""
    raw_xml: bytes = b""

    @property
    def recibida(self) -> bool:
        return self.estado == "RECIBIDA"


@dataclass
class ResultadoAutorizacion:
    estado: str
    numero_autorizacion: str = ""
    fecha_autorizacion: datetime | None = None
    ambiente: str = ""
    comprobante: str = ""
    mensajes: list[dict[str, str]] | None = None
    clave_acceso_consultada: str = ""
    numero_comprobantes: int = 0
    xml_autorizacion: bytes = b""
    raw_xml: bytes = b""

    @property
    def autorizado(self) -> bool:
        return self.estado == "AUTORIZADO"


# =========================================================
# HELPERS GENERALES
# =========================================================

def _texto(valor: Any) -> str:
    return "" if valor is None else str(valor).strip()


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    if ":" in tag:
        return tag.rsplit(":", 1)[-1]
    return tag


def _hijos_por_nombre(elemento: ET.Element, nombre: str) -> list[ET.Element]:
    return [
        hijo
        for hijo in list(elemento)
        if _local_name(hijo.tag) == nombre
    ]


def _primer_hijo(elemento: ET.Element, nombre: str) -> ET.Element | None:
    for hijo in list(elemento):
        if _local_name(hijo.tag) == nombre:
            return hijo
    return None


def _buscar_primero(
    elemento: ET.Element,
    nombre: str,
) -> ET.Element | None:
    for nodo in elemento.iter():
        if _local_name(nodo.tag) == nombre:
            return nodo
    return None


def _texto_hijo(elemento: ET.Element, nombre: str) -> str:
    nodo = _primer_hijo(elemento, nombre)
    if nodo is None:
        return ""
    return _texto(nodo.text)


def _texto_busqueda(elemento: ET.Element, nombre: str) -> str:
    nodo = _buscar_primero(elemento, nombre)
    if nodo is None:
        return ""
    return _texto(nodo.text)


def _parse_xml(contenido: bytes, contexto: str) -> ET.Element:
    try:
        return ET.fromstring(contenido)
    except ET.ParseError as exc:
        raise RespuestaSRIError(
            f"El SRI devolvió una respuesta XML inválida durante {contexto}: {exc}"
        ) from exc


def _parse_fecha(valor: str) -> datetime | None:
    valor = _texto(valor)

    if not valor:
        return None

    fecha = parse_datetime(valor)

    if fecha is not None:
        return fecha

    # Fallback para respuestas ISO válidas que Django no interpretase.
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return None


def _timeout() -> tuple[int | float, int | float]:
    valor = getattr(settings, "SRI_HTTP_TIMEOUT", None)

    if isinstance(valor, (list, tuple)) and len(valor) == 2:
        return valor[0], valor[1]

    return (
        getattr(
            settings,
            "SRI_CONNECT_TIMEOUT",
            DEFAULT_CONNECT_TIMEOUT,
        ),
        getattr(
            settings,
            "SRI_READ_TIMEOUT",
            DEFAULT_READ_TIMEOUT,
        ),
    )


def _validar_ambiente(ambiente: str) -> str:
    ambiente = _texto(ambiente)

    if ambiente not in {
        AMBIENTE_PRUEBAS,
        AMBIENTE_PRODUCCION,
    }:
        raise ValidationError(
            "Ambiente SRI inválido. "
            "Debe ser '1' para pruebas o '2' para producción."
        )

    return ambiente


def _endpoint_recepcion(ambiente: str) -> str:
    ambiente = _validar_ambiente(ambiente)

    if ambiente == AMBIENTE_PRUEBAS:
        return getattr(
            settings,
            "SRI_RECEPCION_PRUEBAS_URL",
            DEFAULT_RECEPCION_PRUEBAS,
        )

    return getattr(
        settings,
        "SRI_RECEPCION_PRODUCCION_URL",
        DEFAULT_RECEPCION_PRODUCCION,
    )


def _endpoint_autorizacion(ambiente: str) -> str:
    ambiente = _validar_ambiente(ambiente)

    if ambiente == AMBIENTE_PRUEBAS:
        return getattr(
            settings,
            "SRI_AUTORIZACION_PRUEBAS_URL",
            DEFAULT_AUTORIZACION_PRUEBAS,
        )

    return getattr(
        settings,
        "SRI_AUTORIZACION_PRODUCCION_URL",
        DEFAULT_AUTORIZACION_PRODUCCION,
    )


def _extraer_mensajes(
    elemento: ET.Element,
) -> list[dict[str, str]]:
    """
    Extrae mensajes tanto de recepción como de autorización.

    Devuelve:
    [
        {
            "identificador": "...",
            "mensaje": "...",
            "informacion_adicional": "...",
            "tipo": "...",
        }
    ]
    """

    mensajes: list[dict[str, str]] = []

    for nodo in elemento.iter():

        if _local_name(nodo.tag) != "mensaje":
            continue

        # El XML del SRI usa un nodo <mensaje> contenedor
        # y dentro de él otro <mensaje> con el texto.
        # Solo tomamos como registro los que tienen hijos
        # como identificador/tipo/informacionAdicional.
        nombres_hijos = {
            _local_name(hijo.tag)
            for hijo in list(nodo)
        }

        if not nombres_hijos.intersection(
            {
                "identificador",
                "mensaje",
                "informacionAdicional",
                "tipo",
            }
        ):
            continue

        registro = {
            "identificador":
                _texto_hijo(nodo, "identificador"),

            "mensaje":
                _texto_hijo(nodo, "mensaje"),

            "informacion_adicional":
                _texto_hijo(
                    nodo,
                    "informacionAdicional",
                ),

            "tipo":
                _texto_hijo(nodo, "tipo"),
        }

        if any(registro.values()):
            mensajes.append(registro)

    return mensajes


def _resumen_mensajes(
    mensajes: Iterable[dict[str, str]],
) -> str:
    partes: list[str] = []

    for item in mensajes:
        identificador = _texto(
            item.get("identificador")
        )
        tipo = _texto(
            item.get("tipo")
        )
        mensaje = _texto(
            item.get("mensaje")
        )
        adicional = _texto(
            item.get("informacion_adicional")
        )

        prefijo = " - ".join(
            dato
            for dato in [
                identificador,
                tipo,
            ]
            if dato
        )

        texto = mensaje

        if adicional:
            texto = (
                f"{texto} | {adicional}"
                if texto
                else adicional
            )

        if prefijo and texto:
            partes.append(
                f"{prefijo}: {texto}"
            )
        elif texto:
            partes.append(texto)
        elif prefijo:
            partes.append(prefijo)

    return " || ".join(partes)


def _leer_archivo_django(
    campo_archivo,
) -> bytes:
    if not campo_archivo:
        raise ValidationError(
            "No existe un archivo XML para procesar."
        )

    try:
        campo_archivo.open("rb")

        try:
            contenido = campo_archivo.read()
        finally:
            campo_archivo.close()

    except Exception as exc:
        raise ValidationError(
            "No se pudo leer el archivo XML."
        ) from exc

    if not contenido:
        raise ValidationError(
            "El archivo XML está vacío."
        )

    return contenido


# =========================================================
# SOAP
# =========================================================

def _post_soap(
    url: str,
    cuerpo: bytes,
    contexto: str,
) -> bytes:

    headers = {
        "Content-Type":
            "text/xml; charset=utf-8",

        "SOAPAction":
            "",
    }

    try:
        respuesta = requests.post(
            url,
            data=cuerpo,
            headers=headers,
            timeout=_timeout(),
            verify=True,
        )

    except requests.Timeout as exc:
        raise ConexionSRIError(
            f"Tiempo de espera agotado al comunicarse con el SRI durante {contexto}."
        ) from exc

    except requests.RequestException as exc:
        raise ConexionSRIError(
            f"No fue posible comunicarse con el SRI durante {contexto}: {exc}"
        ) from exc

    if respuesta.status_code < 200 or respuesta.status_code >= 300:
        raise ConexionSRIError(
            f"El SRI respondió HTTP {respuesta.status_code} durante {contexto}."
        )

    if not respuesta.content:
        raise RespuestaSRIError(
            f"El SRI devolvió una respuesta vacía durante {contexto}."
        )

    return respuesta.content


def _soap_fault(root: ET.Element) -> str:
    for nodo in root.iter():
        if _local_name(nodo.tag) != "Fault":
            continue

        faultstring = _texto_busqueda(
            nodo,
            "faultstring",
        )

        detail = _texto_busqueda(
            nodo,
            "detail",
        )

        return (
            faultstring
            or detail
            or "SOAP Fault sin descripción."
        )

    return ""


# =========================================================
# RECEPCIÓN
# =========================================================

def enviar_comprobante(
    xml_firmado: bytes,
    ambiente: str,
) -> ResultadoRecepcion:
    """
    Envía UN comprobante XML FIRMADO al WS de recepción del SRI.

    No consulta la autorización.
    """

    ambiente = _validar_ambiente(
        ambiente
    )

    if not isinstance(
        xml_firmado,
        (bytes, bytearray),
    ):
        raise ValidationError(
            "xml_firmado debe ser bytes."
        )

    xml_firmado = bytes(
        xml_firmado
    )

    if not xml_firmado:
        raise ValidationError(
            "El XML firmado está vacío."
        )

    if len(xml_firmado) > MAX_XML_INDIVIDUAL_BYTES:
        raise ValidationError(
            "El XML supera el tamaño máximo "
            "permitido para envío individual "
            "al SRI (320 KB)."
        )

    xml_base64 = base64.b64encode(
        xml_firmado
    ).decode("ascii")

    envelope = ET.Element(
        f"{{{SOAP_NS}}}Envelope"
    )

    ET.SubElement(
        envelope,
        f"{{{SOAP_NS}}}Header",
    )

    body = ET.SubElement(
        envelope,
        f"{{{SOAP_NS}}}Body",
    )

    validar = ET.SubElement(
        body,
        f"{{{NS_RECEPCION}}}validarComprobante",
    )

    nodo_xml = ET.SubElement(
        validar,
        "xml",
    )

    nodo_xml.text = xml_base64

    cuerpo = ET.tostring(
        envelope,
        encoding="utf-8",
        xml_declaration=True,
    )

    respuesta_xml = _post_soap(
        url=_endpoint_recepcion(
            ambiente
        ),
        cuerpo=cuerpo,
        contexto="la recepción del comprobante",
    )

    root = _parse_xml(
        respuesta_xml,
        "la recepción del comprobante",
    )

    fault = _soap_fault(root)

    if fault:
        raise RespuestaSRIError(
            f"SOAP Fault en recepción: {fault}"
        )

    respuesta = _buscar_primero(
        root,
        "RespuestaRecepcionComprobante",
    )

    if respuesta is None:
        raise RespuestaSRIError(
            "La respuesta del SRI no contiene "
            "RespuestaRecepcionComprobante."
        )

    estado = _texto_busqueda(
        respuesta,
        "estado",
    ).upper()

    if not estado:
        raise RespuestaSRIError(
            "La respuesta de recepción del SRI "
            "no contiene estado."
        )

    mensajes = _extraer_mensajes(
        respuesta
    )

    clave_acceso = _texto_busqueda(
        respuesta,
        "claveAcceso",
    )

    return ResultadoRecepcion(
        estado=estado,
        mensajes=mensajes,
        clave_acceso=clave_acceso,
        raw_xml=respuesta_xml,
    )


# =========================================================
# AUTORIZACIÓN
# =========================================================

def consultar_autorizacion(
    clave_acceso: str,
    ambiente: str,
) -> ResultadoAutorizacion:
    """
    Consulta la autorización de un comprobante usando
    su clave de acceso de 49 dígitos.
    """

    ambiente = _validar_ambiente(
        ambiente
    )

    clave_acceso = _texto(
        clave_acceso
    )

    if (
        len(clave_acceso) != 49
        or not clave_acceso.isdigit()
    ):
        raise ValidationError(
            "La clave de acceso debe tener "
            "exactamente 49 dígitos."
        )

    envelope = ET.Element(
        f"{{{SOAP_NS}}}Envelope"
    )

    ET.SubElement(
        envelope,
        f"{{{SOAP_NS}}}Header",
    )

    body = ET.SubElement(
        envelope,
        f"{{{SOAP_NS}}}Body",
    )

    consultar = ET.SubElement(
        body,
        (
            f"{{{NS_AUTORIZACION}}}"
            "autorizacionComprobante"
        ),
    )

    nodo_clave = ET.SubElement(
        consultar,
        "claveAccesoComprobante",
    )

    nodo_clave.text = clave_acceso

    cuerpo = ET.tostring(
        envelope,
        encoding="utf-8",
        xml_declaration=True,
    )

    respuesta_xml = _post_soap(
        url=_endpoint_autorizacion(
            ambiente
        ),
        cuerpo=cuerpo,
        contexto="la consulta de autorización",
    )

    root = _parse_xml(
        respuesta_xml,
        "la consulta de autorización",
    )

    fault = _soap_fault(root)

    if fault:
        raise RespuestaSRIError(
            f"SOAP Fault en autorización: {fault}"
        )

    respuesta = _buscar_primero(
        root,
        "RespuestaAutorizacionComprobante",
    )

    if respuesta is None:
        raise RespuestaSRIError(
            "La respuesta del SRI no contiene "
            "RespuestaAutorizacionComprobante."
        )

    clave_consultada = _texto_busqueda(
        respuesta,
        "claveAccesoConsultada",
    )

    numero_comprobantes_texto = (
        _texto_busqueda(
            respuesta,
            "numeroComprobantes",
        )
    )

    try:
        numero_comprobantes = int(
            numero_comprobantes_texto
            or "0"
        )
    except ValueError:
        numero_comprobantes = 0

    autorizaciones: list[
        ET.Element
    ] = [
        nodo
        for nodo in respuesta.iter()
        if _local_name(nodo.tag)
        == "autorizacion"
    ]

    # Si todavía no hay autorización disponible,
    # mantenemos la factura como RECIBIDA / EN PROCESO.
    if not autorizaciones:
        return ResultadoAutorizacion(
            estado="EN_PROCESO",
            mensajes=[],
            clave_acceso_consultada=(
                clave_consultada
                or clave_acceso
            ),
            numero_comprobantes=(
                numero_comprobantes
            ),
            raw_xml=respuesta_xml,
        )

    # Si existe una autorización AUTORIZADA,
    # la preferimos. Si no, usamos la primera.
    autorizacion = next(
        (
            item
            for item in autorizaciones
            if _texto_busqueda(
                item,
                "estado",
            ).upper()
            == "AUTORIZADO"
        ),
        autorizaciones[0],
    )

    estado = _texto_busqueda(
        autorizacion,
        "estado",
    ).upper()

    numero_autorizacion = (
        _texto_busqueda(
            autorizacion,
            "numeroAutorizacion",
        )
    )

    fecha_autorizacion = _parse_fecha(
        _texto_busqueda(
            autorizacion,
            "fechaAutorizacion",
        )
    )

    ambiente_respuesta = (
        _texto_busqueda(
            autorizacion,
            "ambiente",
        )
    )

    comprobante = _texto_busqueda(
        autorizacion,
        "comprobante",
    )

    mensajes = _extraer_mensajes(
        autorizacion
    )

    xml_autorizacion = ET.tostring(
        autorizacion,
        encoding="utf-8",
        xml_declaration=True,
    )

    return ResultadoAutorizacion(
        estado=estado or "EN_PROCESO",
        numero_autorizacion=(
            numero_autorizacion
        ),
        fecha_autorizacion=(
            fecha_autorizacion
        ),
        ambiente=ambiente_respuesta,
        comprobante=comprobante,
        mensajes=mensajes,
        clave_acceso_consultada=(
            clave_consultada
            or clave_acceso
        ),
        numero_comprobantes=(
            numero_comprobantes
        ),
        xml_autorizacion=(
            xml_autorizacion
        ),
        raw_xml=respuesta_xml,
    )


# =========================================================
# INTEGRACIÓN CON FacturaVenta
# =========================================================

def enviar_factura_al_sri(
    factura,
) -> ResultadoRecepcion:
    """
    Envía factura.xml_firmado al SRI.

    Si el SRI responde RECIBIDA:
        factura.estado -> RECIBIDO

    Si responde DEVUELTA:
        factura.estado -> RECHAZADO

    NO consulta autorización.
    """

    if factura is None or not factura.pk:
        raise ValidationError(
            "La factura debe existir "
            "y estar guardada."
        )

    if not factura.clave_acceso:
        raise ValidationError(
            "La factura no tiene clave de acceso."
        )

    if not factura.xml_firmado:
        raise ValidationError(
            "La factura no tiene XML firmado."
        )

    if factura.estado == "AUTORIZADO":
        raise ValidationError(
            "La factura ya está autorizada."
        )

    if factura.estado not in {
        "FIRMADO",
        "RECIBIDO",
        "RECHAZADO",
    }:
        raise ValidationError(
            "La factura debe estar FIRMADA "
            "antes de enviarla al SRI."
        )

    contenido = _leer_archivo_django(
        factura.xml_firmado
    )

    resultado = enviar_comprobante(
        xml_firmado=contenido,
        ambiente=factura.ambiente,
    )

    resumen = _resumen_mensajes(
        resultado.mensajes
    )

    if resultado.recibida:

        factura.marcar_como_recibido(
            mensaje=(
                resumen
                or "Comprobante RECIBIDO por el SRI."
            )
        )

    else:

        factura.marcar_como_rechazado(
            mensaje=(
                resumen
                or (
                    "El SRI devolvió el comprobante "
                    f"con estado {resultado.estado}."
                )
            )
        )

    return resultado


def consultar_factura_en_sri(
    factura,
) -> ResultadoAutorizacion:
    """
    Consulta por clave de acceso y actualiza FacturaVenta.

    AUTORIZADO:
        - guarda número de autorización
        - guarda fecha de autorización
        - guarda XML de autorización
        - estado -> AUTORIZADO

    RECHAZADO / NO AUTORIZADO:
        - estado -> RECHAZADO

    EN_PROCESO:
        - mantiene el estado actual
    """

    if factura is None or not factura.pk:
        raise ValidationError(
            "La factura debe existir "
            "y estar guardada."
        )

    if not factura.clave_acceso:
        raise ValidationError(
            "La factura no tiene clave de acceso."
        )

    if factura.estado == "AUTORIZADO":
        raise ValidationError(
            "La factura ya está autorizada."
        )

    resultado = consultar_autorizacion(
        clave_acceso=factura.clave_acceso,
        ambiente=factura.ambiente,
    )

    mensajes = (
        resultado.mensajes
        or []
    )

    resumen = _resumen_mensajes(
        mensajes
    )

    if resultado.autorizado:

        if not resultado.numero_autorizacion:
            raise RespuestaSRIError(
                "El SRI indicó AUTORIZADO "
                "pero no devolvió número "
                "de autorización."
            )

        factura.marcar_como_autorizado(
            numero_autorizacion=(
                resultado.numero_autorizacion
            ),
            fecha_autorizacion=(
                resultado.fecha_autorizacion
            ),
            mensaje=(
                resumen
                or "Comprobante AUTORIZADO por el SRI."
            ),
        )

        if resultado.xml_autorizacion:

            nombre = (
                f"{factura.clave_acceso}"
                "_autorizado.xml"
            )

            factura.xml_autorizado.save(
                nombre,
                ContentFile(
                    resultado.xml_autorizacion
                ),
                save=False,
            )

            factura.save(
                update_fields=[
                    "xml_autorizado",
                    "updated_at",
                ]
            )

    elif resultado.estado in {
        "RECHAZADO",
        "NO AUTORIZADO",
        "NO_AUTORIZADO",
    }:

        factura.marcar_como_rechazado(
            mensaje=(
                resumen
                or (
                    "El SRI no autorizó "
                    "el comprobante."
                )
            )
        )

    # EN_PROCESO u otro estado temporal:
    # no se fuerza RECHAZADO.

    return resultado


def enviar_y_consultar_factura(
    factura,
    espera_segundos: int | float = 2,
) -> tuple[
    ResultadoRecepcion,
    ResultadoAutorizacion | None,
]:
    """
    Helper conveniente para pruebas/manual.

    Para una vista web en producción es preferible:
        1. enviar_factura_al_sri()
        2. consultar_factura_en_sri()
       como pasos separados.

    El SRI trata recepción y autorización
    como pasos independientes.
    """

    recepcion = enviar_factura_al_sri(
        factura
    )

    if not recepcion.recibida:
        return recepcion, None

    if espera_segundos > 0:
        time.sleep(
            espera_segundos
        )

    factura.refresh_from_db()

    autorizacion = (
        consultar_factura_en_sri(
            factura
        )
    )

    return (
        recepcion,
        autorizacion,
    )