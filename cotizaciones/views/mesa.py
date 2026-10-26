"""Captura de repuestos y costos en una sola tabla."""

import json

from django.contrib.auth.decorators import (
    login_required,
    permission_required,
)
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Prefetch
from django.forms.models import model_to_dict
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.crypto import constant_time_compare, salted_hmac
from django.views.decorators.http import require_http_methods

from ..forms import CotizacionProveedorForm
from ..forms_filas import FilaRepuestoForm
from ..models import (
    CotizacionProveedor,
    ItemSolicitudCotizacion,
)
from .torre import (
    LECTURA,
    _argumentos_formulario,
    _contexto,
    _exigir_abierta,
    _solicitudes,
)


# =========================================================
# CAMPOS EDITABLES
# =========================================================

CAMPOS_ITEM = (
    "descripcion_solicitada",
    "cantidad",
    "resaltado",
)

CAMPOS_OFERTA = tuple(
    CotizacionProveedorForm._meta.fields
)


# =========================================================
# DATOS Y CONTROL DE VERSIONES
# =========================================================

def _datos(objeto, campos):
    return model_to_dict(
        objeto,
        fields=campos,
    )


def _revision(item, cotizaciones=None):
    def valores(objeto):
        return {
            campo.attname: getattr(objeto, campo.attname)
            for campo in objeto._meta.concrete_fields
        }

    if cotizaciones is None:
        cotizaciones = (
            item.cotizaciones_proveedor
            .order_by("pk")
        )

    datos = [
        valores(item),
        [
            valores(oferta)
            for oferta in cotizaciones
        ],
    ]

    return salted_hmac(
        "torre.mesa",
        json.dumps(
            datos,
            sort_keys=True,
            default=str,
        ),
    ).hexdigest()


# =========================================================
# PERMISOS Y VALIDACIONES
# =========================================================

def _permiso(request, accion, modelo):
    permiso = f"cotizaciones.{accion}_{modelo}"

    if not request.user.has_perm(permiso):
        raise PermissionDenied(
            "No tienes permiso para realizar este cambio."
        )


def _exigir_sin_cambios(originales, recibidos, campos):
    """
    Permite reenviar datos sin modificar cuando el usuario
    no tiene permiso para editar ese modelo.
    """

    def texto(valor):
        return "" if valor is None else str(valor)

    for campo in campos:
        if (
            campo in recibidos
            and texto(recibidos[campo])
            != texto(originales.get(campo))
        ):
            raise PermissionDenied(
                "No tienes permiso para modificar estos datos."
            )


def _validar(formulario, referencia):
    if formulario.is_valid():
        return

    errores = []

    for campo, mensajes in formulario.errors.items():
        etiqueta = (
            formulario.fields[campo].label
            if campo in formulario.fields
            else "Datos"
        )

        errores.append(
            f"{etiqueta or campo}: {' '.join(mensajes)}"
        )

    raise ValidationError(
        f"{referencia}: {'; '.join(errores)}"
    )


def _identificador(valor):
    if valor is None:
        return None

    if (
        isinstance(valor, bool)
        or not isinstance(valor, int)
        or valor < 1
    ):
        raise ValidationError(
            "Identificador de fila no válido. "
            "Recarga la pantalla."
        )

    return valor


# =========================================================
# GUARDADO DE TODA LA TABLA
# =========================================================

def _guardar(request, solicitud, filas):
    if not isinstance(filas, list) or len(filas) > 200:
        raise ValidationError(
            "Envía como máximo 200 repuestos por guardado."
        )

    items = {
        item.pk: item
        for item in (
            solicitud.items
            .select_for_update()
            .order_by("pk")
        )
    }

    ofertas = {}
    ofertas_por_item = {}

    cotizaciones = (
        CotizacionProveedor.objects
        .select_for_update()
        .filter(item__solicitud=solicitud)
        .order_by("pk")
    )

    for oferta in cotizaciones:
        ofertas[oferta.pk] = oferta

        ofertas_por_item.setdefault(
            oferta.item_id,
            [],
        ).append(oferta)

    siguiente_orden = (
        solicitud.items.aggregate(
            n=Max("orden_item")
        )["n"]
        or 0
    ) + 1

    vistos = set()
    ofertas_vistas = set()

    # Valida referencias y revisiones antes de guardar.
    for fila in filas:
        if (
            not isinstance(fila, dict)
            or not isinstance(fila.get("ofertas"), list)
        ):
            raise ValidationError(
                "Formato de fila no válido."
            )

        pk = _identificador(
            fila.get("id")
        )

        if pk is not None:
            if pk in vistos or pk not in items:
                raise PermissionDenied(
                    "El repuesto no pertenece a esta tabla."
                )

            vistos.add(pk)

            revision_actual = _revision(
                items[pk],
                ofertas_por_item.get(pk, []),
            )

            if not constant_time_compare(
                str(fila.get("revision", "")),
                revision_actual,
            ):
                raise ValidationError(
                    "Otra persona modificó la tabla. "
                    "Recarga antes de guardar."
                )

        if len(fila["ofertas"]) > 20:
            raise ValidationError(
                "Máximo 20 alternativas por repuesto."
            )

        existentes = set()

        for dato in fila["ofertas"]:
            if not isinstance(dato, dict):
                raise ValidationError(
                    "Formato de oferta no válido."
                )

            oferta_id = _identificador(
                dato.get("id")
            )

            if oferta_id is not None:
                if (
                    oferta_id in ofertas_vistas
                    or oferta_id not in ofertas
                    or ofertas[oferta_id].item_id != pk
                ):
                    raise PermissionDenied(
                        "La oferta no pertenece a este repuesto."
                    )

                ofertas_vistas.add(oferta_id)
                existentes.add(oferta_id)

        guardadas = {
            oferta.pk
            for oferta in ofertas_por_item.get(pk, [])
        }

        if existentes != guardadas:
            raise ValidationError(
                "Faltan ofertas guardadas. "
                "Recarga la tabla."
            )

    # El llamador mantiene una transacción para toda la tabla.
    for numero, fila in enumerate(filas, 1):
        referencia = f"Repuesto {numero}"

        item = items.get(
            fila.get("id")
        )

        nuevo = item is None

        if nuevo:
            _permiso(
                request,
                "add",
                "itemsolicitudcotizacion",
            )

            item = ItemSolicitudCotizacion(
                solicitud=solicitud,
                orden_item=siguiente_orden,
            )

            siguiente_orden += 1

        puede_editar_item = request.user.has_perm(
            "cotizaciones.change_itemsolicitudcotizacion"
        )

        if not nuevo and not puede_editar_item:
            _exigir_sin_cambios(
                _datos(item, CAMPOS_ITEM),
                fila,
                CAMPOS_ITEM,
            )

        else:
            datos_item = _datos(
                item,
                FilaRepuestoForm._meta.fields,
            )

            datos_item.update({
                campo: fila[campo]
                for campo in CAMPOS_ITEM
                if campo in fila
            })

            # La revisión completa se comprobó arriba.
            datos_item["revision"] = ""

            formulario = FilaRepuestoForm(
                datos_item,
                instance=item,
                solicitud=solicitud,
                **_argumentos_formulario(request),
            )

            formulario.initial["revision"] = ""

            if nuevo or formulario.has_changed():
                _permiso(
                    request,
                    "add" if nuevo else "change",
                    "itemsolicitudcotizacion",
                )

                _validar(
                    formulario,
                    referencia,
                )

                item = formulario.save()

        for posicion, dato in enumerate(
            fila["ofertas"],
            1,
        ):
            oferta = ofertas.get(
                dato.get("id")
            )

            es_nueva = oferta is None

            if es_nueva:
                _permiso(
                    request,
                    "add",
                    "cotizacionproveedor",
                )

                oferta = CotizacionProveedor(
                    item=item,
                )

            puede_editar_oferta = request.user.has_perm(
                "cotizaciones.change_cotizacionproveedor"
            )

            if not es_nueva and not puede_editar_oferta:
                _exigir_sin_cambios(
                    _datos(oferta, CAMPOS_OFERTA),
                    dato,
                    CAMPOS_OFERTA,
                )

                continue

            datos_oferta = _datos(
                oferta,
                CAMPOS_OFERTA,
            )

            datos_oferta.update({
                campo: dato[campo]
                for campo in CAMPOS_OFERTA
                if campo in dato
            })

            formulario_oferta = CotizacionProveedorForm(
                datos_oferta,
                instance=oferta,
                item=item,
                **_argumentos_formulario(request),
            )

            if (
                es_nueva
                or formulario_oferta.has_changed()
            ):
                _permiso(
                    request,
                    "add" if es_nueva else "change",
                    "cotizacionproveedor",
                )

                _validar(
                    formulario_oferta,
                    f"{referencia}, oferta {posicion}",
                )

                formulario_oferta.save()

    solicitud.actualizar_estado()


# =========================================================
# PANTALLA DE LA TORRE
# =========================================================

@login_required
@permission_required(
    LECTURA,
    raise_exception=True,
)
@require_http_methods(["GET", "POST"])
def detalle(request, pk):
    if request.method == "POST":
        try:
            carga = json.loads(request.body)

            if not isinstance(carga, dict):
                raise ValidationError(
                    "Formato de tabla no válido."
                )

            with transaction.atomic():
                solicitud = get_object_or_404(
                    _solicitudes(request).select_for_update(),
                    pk=pk,
                )

                _exigir_abierta(solicitud)

                _guardar(
                    request,
                    solicitud,
                    carga.get("filas"),
                )

        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
        ):
            return JsonResponse(
                {
                    "error": "Los datos enviados no son válidos.",
                },
                status=400,
            )

        except PermissionDenied as error:
            return JsonResponse(
                {
                    "error": str(error),
                },
                status=403,
            )

        except ValidationError as error:
            return JsonResponse(
                {
                    "error": " ".join(error.messages),
                },
                status=400,
            )

        return JsonResponse({
            "ok": True,
        })

    solicitud = get_object_or_404(
        _solicitudes(request),
        pk=pk,
    )

    items = (
        solicitud.items
        .order_by("orden_item", "pk")
        .prefetch_related(
            Prefetch(
                "cotizaciones_proveedor",
                queryset=(
                    CotizacionProveedor.objects
                    .order_by("pk")
                ),
            )
        )
    )

    filas = []

    for item in items:
        ofertas_item = list(
            item.cotizaciones_proveedor.all()
        )

        cotizaciones = []

        for oferta in ofertas_item:
            oferta.item = item

            cotizaciones.append({
                **_datos(oferta, CAMPOS_OFERTA),
                "id": oferta.pk,
                "total": oferta.costo_requerimiento,
            })

        filas.append({
            **_datos(item, CAMPOS_ITEM),
            "id": item.pk,
            "revision": _revision(
                item,
                ofertas_item,
            ),
            "ofertas": cotizaciones,
        })

    abierta = (
        solicitud.estado != "CANCELADA"
        and solicitud.orden.estado != "ANULADA"
    )

    permisos_modelo = {
        "agregar_item": "add_itemsolicitudcotizacion",
        "editar_item": "change_itemsolicitudcotizacion",
        "agregar_oferta": "add_cotizacionproveedor",
        "editar_oferta": "change_cotizacionproveedor",
    }

    permisos = {
        clave: (
            abierta
            and request.user.has_perm(
                f"cotizaciones.{permiso}"
            )
        )
        for clave, permiso in permisos_modelo.items()
    }

    return render(
        request,
        "cotizaciones/torre/mesa.html",
        _contexto(
            request,
            solicitud=solicitud,
            mesa={
                "filas": filas,
                "permisos": permisos,
                "resaltados": (
                    ItemSolicitudCotizacion.RESALTADOS
                ),
            },
        ),
    )