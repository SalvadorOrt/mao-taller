"""
Excepciones propias del módulo de facturación electrónica SRI.

Archivo:
    facturacion/sri/excepciones.py

La idea es que xml_factura.py, firma_xades.py, cliente_sri.py
y validaciones.py utilicen estas excepciones en lugar de
Exception genérico.
"""


# =========================================================
# ERROR BASE
# =========================================================

class SRIError(Exception):
    """
    Excepción base de todo el módulo SRI.

    Todas las demás excepciones de esta carpeta heredan de
    esta clase para poder capturarlas de forma general:

        try:
            ...
        except SRIError as exc:
            ...
    """
    pass


# =========================================================
# CONFIGURACIÓN / VALIDACIONES
# =========================================================

class ConfiguracionSRIError(SRIError):
    """
    Error de configuración necesaria para facturación
    electrónica.

    Ejemplos:
    - empresa sin RUC
    - establecimiento no configurado
    - punto de emisión no configurado
    - ambiente inválido
    - falta una configuración requerida
    """
    pass


class ValidacionSRIError(SRIError):
    """
    Error encontrado antes de generar, firmar o enviar
    un comprobante.

    Ejemplos:
    - comprador inválido
    - factura sin detalles
    - totales inconsistentes
    - clave de acceso inválida
    - forma de pago incompleta
    """
    pass


# =========================================================
# XML
# =========================================================

class XMLFacturaError(SRIError):
    """
    Error al construir, validar, serializar o guardar
    el XML de una factura electrónica.
    """
    pass


# Alias corto por compatibilidad si se desea usar
# un nombre más genérico en otros archivos.
class ErrorXML(XMLFacturaError):
    pass


# =========================================================
# FIRMA ELECTRÓNICA XAdES
# =========================================================

class FirmaXADESError(SRIError):
    """
    Error durante el proceso de firma electrónica XAdES.

    Ejemplos:
    - archivo .p12/.pfx no disponible
    - contraseña incorrecta
    - certificado vencido
    - XML inválido
    - fallo al generar la firma
    """
    pass


class CertificadoFirmaError(FirmaXADESError):
    """
    Error específico relacionado con el certificado
    electrónico o su clave privada.
    """
    pass


# Alias corto por compatibilidad.
class ErrorFirma(FirmaXADESError):
    pass


# =========================================================
# CLIENTE / COMUNICACIÓN CON EL SRI
# =========================================================

class ClienteSRIError(SRIError):
    """
    Error base de la comunicación con los Web Services
    del SRI.
    """
    pass


class ConexionSRIError(ClienteSRIError):
    """
    No fue posible establecer o completar correctamente
    la comunicación HTTP/SOAP con el SRI.

    Ejemplos:
    - timeout
    - DNS
    - conexión rechazada
    - error SSL/TLS
    - HTTP inesperado
    """
    pass


class RespuestaSRIError(ClienteSRIError):
    """
    El SRI respondió, pero la respuesta recibida no pudo
    interpretarse correctamente.

    Ejemplos:
    - XML SOAP inválido
    - respuesta vacía
    - estructura inesperada
    - SOAP Fault
    """
    pass


class RecepcionSRIError(ClienteSRIError):
    """
    Error asociado específicamente con la recepción
    del comprobante firmado por parte del SRI.
    """
    pass


class AutorizacionSRIError(ClienteSRIError):
    """
    Error asociado específicamente con la consulta
    o procesamiento de la autorización del comprobante.
    """
    pass


# =========================================================
# ESTADOS / FLUJO
# =========================================================

class EstadoFacturaSRIError(SRIError):
    """
    La factura está en un estado que no permite ejecutar
    la operación solicitada.

    Ejemplos:
    - intentar enviar una factura BORRADOR
    - intentar firmar sin XML generado
    - intentar reenviar una factura AUTORIZADA
    """
    pass


# =========================================================
# EXPORTACIONES
# =========================================================

__all__ = [
    "SRIError",
    "ConfiguracionSRIError",
    "ValidacionSRIError",
    "XMLFacturaError",
    "ErrorXML",
    "FirmaXADESError",
    "CertificadoFirmaError",
    "ErrorFirma",
    "ClienteSRIError",
    "ConexionSRIError",
    "RespuestaSRIError",
    "RecepcionSRIError",
    "AutorizacionSRIError",
    "EstadoFacturaSRIError",
]