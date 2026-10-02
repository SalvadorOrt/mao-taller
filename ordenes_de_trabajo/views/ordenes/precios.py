# ordenes_de_trabajo/views/ordenes/precios.py

import json
import logging

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from accesos.permissions import permiso_requerido

from ...models import OrdenTrabajo
from ...services.precios import (
    consultar_precio as ejecutar_consulta_precio,
)


logger = logging.getLogger(__name__)


# ==========================================================
# RESPUESTAS JSON
# ==========================================================

def _respuesta_error(
    mensaje,
    *,
    status=400,
    campo=None,
):
    respuesta = {
        "success": False,
        "error": mensaje,
    }

    if campo:
        respuesta["campo"] = campo

    return JsonResponse(
        respuesta,
        status=status,
    )


def _respuesta_ok(data):
    return JsonResponse(
        {
            "success": True,
            "data": data,
        },
        status=200,
    )


# ==========================================================
# LEER JSON
# ==========================================================

def _leer_json(request):
    """
    Lee el cuerpo JSON enviado desde precios.js.

    Ejemplo:

    {
        "orden_id": 123,
        "tipo": "MOI",
        "descripcion": "TRABAJOS DE REFRIGERACION",
        "servicio_id": 8,
        "variante": "NORMAL",
        "procedimientos": [
            "CAMBIO DE REFRIGERANTE",
            "CAMBIO JUNTA TERMOSTATICA"
        ]
    }
    """

    if not request.body:
        return {}

    try:
        contenido = request.body.decode(
            "utf-8"
        )

        data = json.loads(
            contenido
        )

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise ValueError(
            "La solicitud contiene un JSON inválido."
        ) from exc

    if not isinstance(
        data,
        dict,
    ):
        raise ValueError(
            "El cuerpo de la solicitud debe ser un objeto JSON."
        )

    return data


# ==========================================================
# LIMPIAR TEXTO
# ==========================================================

def _texto(
    valor,
    default="",
):
    if valor is None:
        return default

    return str(
        valor
    ).strip()


# ==========================================================
# ID ENTERO O NULL
# ==========================================================

def _id_opcional(
    valor,
    nombre_campo,
):
    """
    Convierte IDs opcionales enviados desde JavaScript.

    Acepta:
        None
        ""
        "123"
        123

    Devuelve:
        None
        123
    """

    if valor in {
        None,
        "",
    }:
        return None

    try:
        valor = int(
            valor
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            f"{nombre_campo} no es válido."
        ) from exc

    if valor <= 0:
        raise ValueError(
            f"{nombre_campo} no es válido."
        )

    return valor


# ==========================================================
# PROCEDIMIENTOS
# ==========================================================

def _procesar_procedimientos(
    valor,
):
    """
    Las hijas de MOI/MOE deben llegar como lista.

    También elimina:
    - valores vacíos
    - espacios sobrantes
    - duplicados exactos

    Conserva el orden de pantalla.
    """

    if valor in {
        None,
        "",
    }:
        return []

    if not isinstance(
        valor,
        list,
    ):
        raise ValueError(
            "Los procedimientos deben enviarse como una lista."
        )

    resultado = []
    vistos = set()

    for procedimiento in valor:

        # ----------------------------------------------
        # FUTURO:
        # también soportamos objetos por si después
        # el JS manda más datos de la hija.
        # ----------------------------------------------

        if isinstance(
            procedimiento,
            dict,
        ):
            descripcion = (
                procedimiento.get(
                    "descripcion"
                )
                or procedimiento.get(
                    "texto"
                )
                or procedimiento.get(
                    "nombre"
                )
                or ""
            )

        else:
            descripcion = (
                procedimiento
            )

        descripcion = _texto(
            descripcion
        )

        if not descripcion:
            continue

        clave = (
            descripcion.upper()
        )

        if clave in vistos:
            continue

        vistos.add(
            clave
        )

        resultado.append(
            descripcion
        )

    return resultado


# ==========================================================
# VALIDAR TIPO
# ==========================================================

def _validar_tipo(
    valor,
):
    tipo = _texto(
        valor
    ).upper()

    tipos_validos = {
        "REP",
        "MOI",
        "MOE",
    }

    if tipo not in tipos_validos:
        raise ValueError(
            "El tipo debe ser REP, MOI o MOE."
        )

    return tipo


# ==========================================================
# CONSULTAR PRECIO
# ==========================================================

@permiso_requerido(
    "ordenes_de_trabajo.view_ordentrabajo"
)
@require_POST
def consultar_precio(request):
    """
    Endpoint de consulta histórica de precios.

    NO modifica:
        - la OT
        - el inventario
        - servicios
        - precios
        - stock

    Únicamente analiza y devuelve información.

    El botón "Aplicar" del modal modificará el P.U.
    únicamente en el navegador.

    La OT seguirá guardándose mediante su flujo normal.
    """

    # ======================================================
    # LEER SOLICITUD
    # ======================================================

    try:
        data = _leer_json(
            request
        )

    except ValueError as exc:
        return _respuesta_error(
            str(exc),
            status=400,
        )

    # ======================================================
    # ORDEN
    # ======================================================

    try:
        orden_id = _id_opcional(
            data.get(
                "orden_id"
            ),
            "orden_id",
        )

    except ValueError as exc:
        return _respuesta_error(
            str(exc),
            status=400,
            campo="orden_id",
        )

    if not orden_id:
        return _respuesta_error(
            "Debe indicar la orden de trabajo.",
            status=400,
            campo="orden_id",
        )

    orden = (
        OrdenTrabajo.objects
        .select_related(
            "sucursal",
            "expediente",
        )
        .filter(
            pk=orden_id
        )
        .first()
    )

    if not orden:
        return _respuesta_error(
            "La orden de trabajo no existe.",
            status=404,
            campo="orden_id",
        )

    # ======================================================
    # TIPO
    # ======================================================

    try:
        tipo = _validar_tipo(
            data.get(
                "tipo"
            )
        )

    except ValueError as exc:
        return _respuesta_error(
            str(exc),
            status=400,
            campo="tipo",
        )

    # ======================================================
    # DESCRIPCIÓN
    # ======================================================

    descripcion = _texto(
        data.get(
            "descripcion"
        )
    )

    if not descripcion:
        return _respuesta_error(
            (
                "Debe ingresar una descripción "
                "antes de consultar el precio."
            ),
            status=400,
            campo="descripcion",
        )

    # ======================================================
    # CAMPOS COMUNES / OPCIONALES
    # ======================================================

    codigo = _texto(
        data.get(
            "codigo"
        )
    )

    variante = (
        _texto(
            data.get(
                "variante"
            ),
            default="NORMAL",
        )
        or "NORMAL"
    ).upper()

    # ======================================================
    # IDS OPCIONALES
    # ======================================================

    try:
        codigo_producto_id = (
            _id_opcional(
                data.get(
                    "codigo_producto_id"
                ),
                "codigo_producto_id",
            )
        )

        servicio_id = (
            _id_opcional(
                data.get(
                    "servicio_id"
                ),
                "servicio_id",
            )
        )

    except ValueError as exc:
        return _respuesta_error(
            str(exc),
            status=400,
        )

    # ======================================================
    # PROCEDIMIENTOS / HIJAS
    # ======================================================

    try:
        procedimientos = (
            _procesar_procedimientos(
                data.get(
                    "procedimientos",
                    [],
                )
            )
        )

    except ValueError as exc:
        return _respuesta_error(
            str(exc),
            status=400,
            campo="procedimientos",
        )

    # ======================================================
    # LIMPIAR CAMPOS SEGÚN TIPO
    # ======================================================

    if tipo == "REP":

        # Un repuesto no utiliza estos campos.
        servicio_id = None
        variante = "NORMAL"
        procedimientos = []

    else:

        # MOI / MOE no utilizan CodigoProducto.
        codigo_producto_id = None

    # ======================================================
    # EJECUTAR MOTOR
    # ======================================================

    try:
        resultado = (
            ejecutar_consulta_precio(
                orden_actual=orden,
                tipo=tipo,
                descripcion=descripcion,
                codigo=codigo,
                codigo_producto_id=(
                    codigo_producto_id
                ),
                servicio_id=(
                    servicio_id
                ),
                variante=variante,
                procedimientos=(
                    procedimientos
                ),
            )
        )

    # ------------------------------------------------------
    # ERROR DE VALIDACIÓN DEL MOTOR
    # ------------------------------------------------------

    except ValueError as exc:

        return _respuesta_error(
            str(exc),
            status=400,
        )

    # ------------------------------------------------------
    # ERROR NO ESPERADO
    # ------------------------------------------------------

    except Exception:

        logger.exception(
            (
                "Error consultando precio. "
                "orden_id=%s tipo=%s"
            ),
            orden_id,
            tipo,
        )

        return _respuesta_error(
            (
                "Ocurrió un error interno "
                "al consultar el historial de precios."
            ),
            status=500,
        )

    # ======================================================
    # RESPUESTA
    # ======================================================

    return _respuesta_ok(
        resultado
    )