# compras/services/sri.py

import html
import xml.etree.ElementTree as ET

import requests
from django.core.exceptions import ValidationError


class SRIService:
    URL_PRODUCCION = (
        "https://cel.sri.gob.ec/"
        "comprobantes-electronicos-ws/"
        "AutorizacionComprobantesOffline"
    )

    URL_PRUEBAS = (
        "https://celcer.sri.gob.ec/"
        "comprobantes-electronicos-ws/"
        "AutorizacionComprobantesOffline"
    )

    def __init__(self, ambiente="produccion"):
        if ambiente == "pruebas":
            self.url = self.URL_PRUEBAS
        else:
            self.url = self.URL_PRODUCCION

    @staticmethod
    def validar_clave(clave_acceso):
        clave = str(clave_acceso or "").strip()

        if not clave:
            raise ValidationError(
                "Debe ingresar una clave de acceso."
            )

        if len(clave) != 49:
            raise ValidationError(
                "La clave de acceso debe tener exactamente 49 dígitos."
            )

        if not clave.isdigit():
            raise ValidationError(
                "La clave de acceso solo puede contener números."
            )

        return clave

    @staticmethod
    def _nombre_etiqueta(elemento):
        return elemento.tag.split("}")[-1]

    def _crear_soap_body(self, clave_acceso):
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:ec="http://ec.gob.sri.ws.autorizacion">

    <soapenv:Header/>

    <soapenv:Body>
        <ec:autorizacionComprobante>
            <claveAccesoComprobante>{clave_acceso}</claveAccesoComprobante>
        </ec:autorizacionComprobante>
    </soapenv:Body>
</soapenv:Envelope>
"""

    def consultar(self, clave_acceso):
        clave = self.validar_clave(clave_acceso)
        soap_body = self._crear_soap_body(clave)

        try:
            respuesta = requests.post(
                self.url,
                data=soap_body.encode("utf-8"),
                headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "SOAPAction": "",
                },
                timeout=30,
            )

            respuesta.raise_for_status()

        except requests.Timeout as error:
            raise ValidationError(
                "El SRI tardó demasiado en responder."
            ) from error

        except requests.ConnectionError as error:
            raise ValidationError(
                "No se pudo establecer conexión con el SRI."
            ) from error

        except requests.RequestException as error:
            raise ValidationError(
                f"Error al consultar el SRI: {error}"
            ) from error

        if not respuesta.content:
            raise ValidationError(
                "El SRI devolvió una respuesta vacía."
            )

        return self._extraer_comprobante(
            respuesta.content,
            clave,
        )

    def _extraer_comprobante(self, respuesta_xml, clave_acceso):
        try:
            raiz = ET.fromstring(respuesta_xml)
        except ET.ParseError as error:
            raise ValidationError(
                "El SRI devolvió un XML inválido."
            ) from error

        nombre_raiz = self._nombre_etiqueta(raiz)

        # Algunas respuestas pueden traer directamente <factura>.
        if nombre_raiz in {
            "factura",
            "notaCredito",
            "notaDebito",
            "comprobanteRetencion",
            "liquidacionCompra",
            "guiaRemision",
        }:
            return respuesta_xml.decode(
                "utf-8",
                errors="replace",
            )

        estado = None
        comprobante = None
        mensajes = []

        for elemento in raiz.iter():
            etiqueta = self._nombre_etiqueta(elemento)
            texto = (elemento.text or "").strip()

            if etiqueta == "estado" and texto:
                estado = texto

            elif etiqueta == "comprobante" and texto:
                comprobante = html.unescape(texto)

            elif etiqueta == "mensaje" and texto:
                mensajes.append(texto)

            elif etiqueta == "informacionAdicional" and texto:
                mensajes.append(texto)

        if estado and estado.upper() != "AUTORIZADO":
            detalle = " | ".join(dict.fromkeys(mensajes))

            mensaje = (
                f"El comprobante no está autorizado. Estado: {estado}."
            )

            if detalle:
                mensaje += f" Detalle: {detalle}"

            raise ValidationError(mensaje)

        if not comprobante:
            raise ValidationError(
                "El SRI no devolvió una factura para la clave "
                f"{clave_acceso}."
            )

        return comprobante.strip()