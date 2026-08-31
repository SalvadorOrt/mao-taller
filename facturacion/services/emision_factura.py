from __future__ import annotations

"""
Orquestador del flujo de emisión de facturas electrónicas.

Archivo:
    facturacion/services/emision_factura.py

Responsabilidad:
    Conectar las piezas que ya existen:

        FacturaVenta
            ↓
        validaciones.py
            ↓
        xml_factura.py
            ↓
        firma_xades.py
            ↓
        cliente_sri.py

Este archivo NO:
    - crea una FacturaVenta desde una OrdenTrabajo;
    - construye manualmente XML;
    - implementa criptografía;
    - implementa SOAP del SRI.

La creación OT -> Factura permanece separada en:
    facturacion/services/factura_desde_orden.py
"""

from dataclasses import dataclass
import time
from typing import Any

from django.core.exceptions import ValidationError

from facturacion.models import FacturaVenta

from facturacion.sri.cliente_sri import (
    ResultadoAutorizacion,
    ResultadoRecepcion,
    consultar_factura_en_sri,
    enviar_factura_al_sri,
)

from facturacion.sri.excepciones import (
    EstadoFacturaSRIError,
    SRIError,
    ValidacionSRIError,
)

from facturacion.sri.firma_xades import (
    firmar_factura,
)

from facturacion.sri.validaciones import (
    validar_factura_para_consulta,
    validar_factura_para_envio,
    validar_factura_para_firma,
    validar_factura_para_xml,
)

from facturacion.sri.xml_factura import (
    generar_xml_factura,
)


# =========================================================
# ESTADOS
# =========================================================

ESTADO_BORRADOR = "BORRADOR"
ESTADO_GENERADO = "GENERADO"
ESTADO_FIRMADO = "FIRMADO"
ESTADO_RECIBIDO = "RECIBIDO"
ESTADO_AUTORIZADO = "AUTORIZADO"
ESTADO_RECHAZADO = "RECHAZADO"

ESTADOS_VALIDOS = {
    ESTADO_BORRADOR,
    ESTADO_GENERADO,
    ESTADO_FIRMADO,
    ESTADO_RECIBIDO,
    ESTADO_AUTORIZADO,
    ESTADO_RECHAZADO,
}


# =========================================================
# RESULTADO DEL ORQUESTADOR
# =========================================================

@dataclass
class ResultadoEmisionFactura:
    """
    Resultado resumido del flujo.

    La factura siempre se vuelve a consultar desde la BD
    antes de devolver el resultado final.
    """

    factura: FacturaVenta
    estado_inicial: str
    estado_final: str

    xml_generado: bool = False
    xml_firmado: bool = False
    enviada_sri: bool = False
    consulta_realizada: bool = False

    recepcion: ResultadoRecepcion | None = None
    autorizacion: ResultadoAutorizacion | None = None

    mensaje: str = ""

    @property
    def autorizada(self) -> bool:
        return (
            self.estado_final
            == ESTADO_AUTORIZADO
        )

    @property
    def rechazada(self) -> bool:
        return (
            self.estado_final
            == ESTADO_RECHAZADO
        )

    @property
    def pendiente(self) -> bool:
        return self.estado_final in {
            ESTADO_BORRADOR,
            ESTADO_GENERADO,
            ESTADO_FIRMADO,
            ESTADO_RECIBIDO,
        }


# =========================================================
# HELPERS
# =========================================================

def _validar_instancia_factura(
    factura: FacturaVenta,
) -> None:
    if factura is None:
        raise ValidacionSRIError(
            "No se recibió una factura."
        )

    if not isinstance(
        factura,
        FacturaVenta,
    ):
        raise ValidacionSRIError(
            "El objeto recibido no es una "
            "FacturaVenta."
        )

    if not factura.pk:
        raise ValidacionSRIError(
            "La factura debe estar guardada "
            "antes de iniciar la emisión."
        )

    if factura.estado not in ESTADOS_VALIDOS:
        raise EstadoFacturaSRIError(
            "La factura tiene un estado "
            f"no reconocido: {factura.estado}."
        )


def _recargar_factura(
    factura: FacturaVenta,
) -> FacturaVenta:
    """
    Recarga la factura con las relaciones principales.

    No usamos select_for_update durante llamadas de red:
    nunca conviene mantener una transacción/lock abierto
    mientras se espera una respuesta del SRI.
    """

    _validar_instancia_factura(
        factura
    )

    return (
        FacturaVenta.objects
        .select_related(
            "empresa",
            "sucursal",
            "firma_electronica",
            "orden",
        )
        .prefetch_related(
            "detalles",
            "pagos",
        )
        .get(
            pk=factura.pk
        )
    )


def _mensaje_estado(
    factura: FacturaVenta,
) -> str:
    estado = factura.estado

    if estado == ESTADO_BORRADOR:
        return (
            "Factura en borrador. "
            "Todavía no se ha emitido ni generado el XML."
        )

    if estado == ESTADO_GENERADO:
        return (
            "XML generado. "
            "Falta firmar electrónicamente."
        )

    if estado == ESTADO_FIRMADO:
        return (
            "XML firmado. "
            "Falta enviarlo al SRI."
        )

    if estado == ESTADO_RECIBIDO:
        return (
            "El SRI recibió el comprobante. "
            "Falta obtener la autorización."
        )

    if estado == ESTADO_AUTORIZADO:
        return (
            "Factura autorizada por el SRI."
        )

    if estado == ESTADO_RECHAZADO:
        return (
            factura.mensaje_sri
            or factura.mensaje_firma
            or (
                "La factura está rechazada. "
                "Debe revisarse antes de reintentar."
            )
        )

    return (
        f"Estado actual: {estado}."
    )


# =========================================================
# PASO 1: GENERAR XML
# =========================================================

def generar_comprobante(
    factura: FacturaVenta,
    *,
    ruc_proveedor: str | None = None,
) -> FacturaVenta:
    """
    BORRADOR/GENERADO/RECHAZADO -> GENERADO

    Genera y guarda factura.xml_generado.

    RECHAZADO solo debe usarse para regenerar cuando el
    problema ya fue corregido y el comprobante todavía
    puede ser reutilizado conforme a la lógica del negocio.
    """

    factura = _recargar_factura(
        factura
    )

    # Una factura BORRADOR no consume secuencial ni genera clave.
    # Justo antes de construir el XML reservamos ambos datos fiscales.
    # Si ya fueron preparados previamente (por ejemplo desde views.py),
    # este bloque no hace nada.
    if (
        factura.estado == ESTADO_BORRADOR
        and not factura.tiene_datos_emision
    ):
        factura.preparar_emision()
        factura = _recargar_factura(
            factura
        )

    if not factura.tiene_datos_emision:
        raise ValidacionSRIError(
            "La factura no tiene secuencial y clave de acceso "
            "preparados para la emisión."
        )

    validar_factura_para_xml(
        factura
    )

    generar_xml_factura(
        factura,
        guardar=True,
        ruc_proveedor=ruc_proveedor,
    )

    return _recargar_factura(
        factura
    )


# =========================================================
# PASO 2: FIRMAR
# =========================================================

def firmar_comprobante(
    factura: FacturaVenta,
) -> FacturaVenta:
    """
    GENERADO -> FIRMADO

    Usa factura.xml_generado y la FirmaElectronica
    asociada a la factura.
    """

    factura = _recargar_factura(
        factura
    )

    validar_factura_para_firma(
        factura
    )

    firmar_factura(
        factura
    )

    return _recargar_factura(
        factura
    )


# =========================================================
# PASO 3: ENVIAR A RECEPCIÓN SRI
# =========================================================

def enviar_comprobante_sri(
    factura: FacturaVenta,
) -> tuple[
    FacturaVenta,
    ResultadoRecepcion,
]:
    """
    FIRMADO -> RECIBIDO o RECHAZADO.

    La comunicación real la realiza cliente_sri.py.
    """

    factura = _recargar_factura(
        factura
    )

    validar_factura_para_envio(
        factura
    )

    resultado = enviar_factura_al_sri(
        factura
    )

    factura = _recargar_factura(
        factura
    )

    return (
        factura,
        resultado,
    )


# =========================================================
# PASO 4: CONSULTAR AUTORIZACIÓN
# =========================================================

def consultar_comprobante_sri(
    factura: FacturaVenta,
) -> tuple[
    FacturaVenta,
    ResultadoAutorizacion,
]:
    """
    Consulta la autorización usando la clave de acceso.

    RECIBIDO normalmente terminará en:
        AUTORIZADO
        RECHAZADO
        RECIBIDO (si el SRI aún está procesando)
    """

    factura = _recargar_factura(
        factura
    )

    validar_factura_para_consulta(
        factura
    )

    resultado = consultar_factura_en_sri(
        factura
    )

    factura = _recargar_factura(
        factura
    )

    return (
        factura,
        resultado,
    )


# =========================================================
# REINTENTO EXPLÍCITO DE ENVÍO
# =========================================================

def reenviar_comprobante_rechazado(
    factura: FacturaVenta,
) -> tuple[
    FacturaVenta,
    ResultadoRecepcion,
]:
    """
    Reenvía explícitamente un XML ya firmado.

    IMPORTANTE:
    Esta función NO corrige ni regenera la factura.

    Úsala únicamente cuando:
        - factura.estado == RECHAZADO;
        - xml_firmado todavía es el comprobante que se
          desea reenviar;
        - el motivo permite un nuevo intento.

    Para corregir datos tributarios, lo normal es volver
    al flujo de edición/regeneración definido por la
    aplicación, no reenviar ciegamente el mismo XML.
    """

    factura = _recargar_factura(
        factura
    )

    if (
        factura.estado
        != ESTADO_RECHAZADO
    ):
        raise EstadoFacturaSRIError(
            "Esta operación solo corresponde "
            "a una factura RECHAZADA."
        )

    if not factura.xml_firmado:
        raise ValidacionSRIError(
            "La factura rechazada no tiene "
            "un XML firmado para reenviar."
        )

    validar_factura_para_envio(
        factura
    )

    resultado = enviar_factura_al_sri(
        factura
    )

    factura = _recargar_factura(
        factura
    )

    return (
        factura,
        resultado,
    )


# =========================================================
# PROCESO COMPLETO
# =========================================================

def procesar_factura_completa(
    factura: FacturaVenta,
    *,
    ruc_proveedor: str | None = None,
    consultar_autorizacion: bool = True,
    espera_segundos: int | float = 2,
) -> ResultadoEmisionFactura:
    """
    Ejecuta el flujo que corresponda según el estado actual.

    Estados:

        BORRADOR
            ↓
        preparar_emision()
        (reserva secuencial + genera clave)
            ↓
        GENERADO
            ↓
        FIRMADO
            ↓
        RECIBIDO
            ↓
        AUTORIZADO

    Si una factura ya está en un estado intermedio,
    continúa desde ese punto.

    NO reintenta automáticamente una factura RECHAZADA.

    Tampoco mantiene una transacción abierta durante todo
    el flujo, porque las llamadas al SRI pueden tardar y
    no deben mantener locks de base de datos.
    """

    factura = _recargar_factura(
        factura
    )

    estado_inicial = (
        factura.estado
    )

    resultado = ResultadoEmisionFactura(
        factura=factura,
        estado_inicial=estado_inicial,
        estado_final=factura.estado,
        mensaje=_mensaje_estado(
            factura
        ),
    )

    # -----------------------------------------------------
    # YA AUTORIZADA
    # -----------------------------------------------------

    if (
        factura.estado
        == ESTADO_AUTORIZADO
    ):
        resultado.estado_final = (
            factura.estado
        )
        resultado.mensaje = (
            "La factura ya está AUTORIZADA."
        )
        return resultado

    # -----------------------------------------------------
    # RECHAZADA
    # -----------------------------------------------------

    if (
        factura.estado
        == ESTADO_RECHAZADO
    ):
        resultado.estado_final = (
            factura.estado
        )
        resultado.mensaje = (
            _mensaje_estado(
                factura
            )
        )
        return resultado

    # -----------------------------------------------------
    # BORRADOR -> GENERADO
    # -----------------------------------------------------

    if (
        factura.estado
        == ESTADO_BORRADOR
    ):
        factura = generar_comprobante(
            factura,
            ruc_proveedor=ruc_proveedor,
        )

        resultado.xml_generado = True
        resultado.factura = factura
        resultado.estado_final = (
            factura.estado
        )

    # -----------------------------------------------------
    # GENERADO -> FIRMADO
    # -----------------------------------------------------

    if (
        factura.estado
        == ESTADO_GENERADO
    ):
        factura = firmar_comprobante(
            factura
        )

        resultado.xml_firmado = True
        resultado.factura = factura
        resultado.estado_final = (
            factura.estado
        )

    # -----------------------------------------------------
    # FIRMADO -> RECEPCIÓN SRI
    # -----------------------------------------------------

    if (
        factura.estado
        == ESTADO_FIRMADO
    ):
        (
            factura,
            recepcion,
        ) = enviar_comprobante_sri(
            factura
        )

        resultado.enviada_sri = True
        resultado.recepcion = (
            recepcion
        )
        resultado.factura = factura
        resultado.estado_final = (
            factura.estado
        )

        # El SRI devolvió el comprobante.
        if (
            factura.estado
            == ESTADO_RECHAZADO
        ):
            resultado.mensaje = (
                _mensaje_estado(
                    factura
                )
            )
            return resultado

    # -----------------------------------------------------
    # RECIBIDO -> AUTORIZACIÓN
    # -----------------------------------------------------

    if (
        factura.estado
        == ESTADO_RECIBIDO
    ):
        if not consultar_autorizacion:
            resultado.factura = factura
            resultado.estado_final = (
                factura.estado
            )
            resultado.mensaje = (
                _mensaje_estado(
                    factura
                )
            )
            return resultado

        if espera_segundos < 0:
            raise ValidacionSRIError(
                "espera_segundos no puede "
                "ser negativo."
            )

        if espera_segundos:
            time.sleep(
                espera_segundos
            )

        (
            factura,
            autorizacion,
        ) = consultar_comprobante_sri(
            factura
        )

        resultado.consulta_realizada = True
        resultado.autorizacion = (
            autorizacion
        )
        resultado.factura = factura
        resultado.estado_final = (
            factura.estado
        )

    # -----------------------------------------------------
    # RESULTADO FINAL
    # -----------------------------------------------------

    resultado.factura = (
        _recargar_factura(
            factura
        )
    )

    resultado.estado_final = (
        resultado.factura.estado
    )

    resultado.mensaje = (
        _mensaje_estado(
            resultado.factura
        )
    )

    return resultado


# =========================================================
# REANUDAR
# =========================================================

def reanudar_emision(
    factura: FacturaVenta,
    *,
    ruc_proveedor: str | None = None,
    consultar_autorizacion: bool = True,
    espera_segundos: int | float = 0,
) -> ResultadoEmisionFactura:
    """
    Alias semántico de procesar_factura_completa().

    Sirve cuando una factura quedó, por ejemplo, en:
        GENERADO
        FIRMADO
        RECIBIDO

    y quieres continuar desde ahí.
    """

    return procesar_factura_completa(
        factura,
        ruc_proveedor=ruc_proveedor,
        consultar_autorizacion=(
            consultar_autorizacion
        ),
        espera_segundos=(
            espera_segundos
        ),
    )


# =========================================================
# ESTADO / DIAGNÓSTICO SIMPLE
# =========================================================

def obtener_estado_emision(
    factura: FacturaVenta,
) -> dict[str, Any]:
    """
    Devuelve información simple para una vista/template,
    API interna o diagnóstico.

    No hace llamadas al SRI.
    """

    factura = _recargar_factura(
        factura
    )

    return {
        "factura_id":
            factura.pk,

        "numero_factura":
            factura.numero_factura,

        "clave_acceso":
            factura.clave_acceso or "",

        "tiene_datos_emision":
            factura.tiene_datos_emision,

        "ambiente":
            factura.ambiente,

        "estado":
            factura.estado,

        "mensaje":
            _mensaje_estado(
                factura
            ),

        "tiene_xml_generado":
            bool(
                factura.xml_generado
            ),

        "tiene_xml_firmado":
            bool(
                factura.xml_firmado
            ),

        "tiene_xml_autorizado":
            bool(
                factura.xml_autorizado
            ),

        "numero_autorizacion":
            factura.numero_autorizacion
            or "",

        "fecha_autorizacion":
            factura.fecha_autorizacion,

        "mensaje_sri":
            factura.mensaje_sri
            or "",

        "mensaje_firma":
            factura.mensaje_firma
            or "",
    }


# =========================================================
# API PÚBLICA
# =========================================================

__all__ = [
    "ResultadoEmisionFactura",
    "generar_comprobante",
    "firmar_comprobante",
    "enviar_comprobante_sri",
    "consultar_comprobante_sri",
    "reenviar_comprobante_rechazado",
    "procesar_factura_completa",
    "reanudar_emision",
    "obtener_estado_emision",
]