"""Captura libre de repuestos y costos con guardado automático."""

import json

from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Prefetch
from django.db.models.deletion import ProtectedError
from django.forms.models import model_to_dict
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.crypto import constant_time_compare, salted_hmac
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from ..forms import CotizacionProveedorForm
from ..forms_filas import FilaRepuestoForm
from ..models import CotizacionProveedor, ItemSolicitudCotizacion

from .torre import (
    LECTURA,
    _argumentos_formulario,
    _contexto,
    _exigir_abierta,
    _solicitudes,
)


CAMPOS_ITEM = (
    "descripcion_solicitada",
    "cantidad",
    "resaltado",
)

CAMPOS_OFERTA = tuple(
    CotizacionProveedorForm._meta.fields
)


class ConflictoGuardado(ValidationError):
    pass


def _datos(objeto, campos):
    return model_to_dict(objeto, fields=campos)


def _revision(item, cotizaciones=None):
    def valores(objeto):
        return {
            campo.attname: getattr(objeto, campo.attname)
            for campo in objeto._meta.concrete_fields
        }

    if cotizaciones is None:
        cotizaciones = item.cotizaciones_proveedor.order_by("pk")

    return salted_hmac(
        "torre.mesa",
        json.dumps(
            [
                valores(item),
                [valores(oferta) for oferta in cotizaciones],
            ],
            sort_keys=True,
            default=str,
        ),
    ).hexdigest()


def _permiso(request, accion, modelo):
    permiso = f"cotizaciones.{accion}_{modelo}"

    if not request.user.has_perm(permiso):
        raise PermissionDenied(
            "No tienes permiso para realizar este cambio."
        )


def _exigir_sin_cambios(originales, recibidos, campos):
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
            "Identificador no válido. Recarga la pantalla."
        )

    return valor


def _eliminar_ofertas(request, solicitud, filas):
    """Borra ofertas explícitas, con permiso y revisión vigentes."""
    for fila in filas:
        if not isinstance(fila, dict):
            raise ValidationError("Formato de fila no válido.")

        eliminadas = fila.get("ofertas_eliminadas", [])

        if not isinstance(eliminadas, list) or len(eliminadas) > 20:
            raise ValidationError("Formato de ofertas eliminadas no válido.")

        if not eliminadas:
            continue

        ids = [_identificador(valor) for valor in eliminadas]

        if None in ids or len(ids) != len(set(ids)):
            raise ValidationError("Hay ofertas eliminadas no válidas o repetidas.")

        _permiso(request, "delete", "cotizacionproveedor")

        item = (
            solicitud.items.select_for_update()
            .filter(pk=_identificador(fila.get("id")))
            .first()
        )

        if item is None:
            raise PermissionDenied("El repuesto no pertenece a esta tabla.")

        ofertas = list(
            item.cotizaciones_proveedor.select_for_update().order_by("pk")
        )

        if not set(ids).issubset({oferta.pk for oferta in ofertas}):
            raise PermissionDenied("La oferta no pertenece a este repuesto.")

        conservadas = fila.get("ofertas")

        if not isinstance(conservadas, list) or any(
            not isinstance(oferta, dict) for oferta in conservadas
        ):
            raise ValidationError("Formato de oferta no válido.")

        if set(ids).intersection(
            _identificador(oferta.get("id")) for oferta in conservadas
        ):
            raise ValidationError("No puedes guardar y eliminar la misma oferta.")

        if not constant_time_compare(
            str(fila.get("revision", "")), _revision(item, ofertas)
        ):
            raise ConflictoGuardado(
                "El repuesto cambió en otra sesión. Recarga para revisarlo."
            )

        item.cotizaciones_proveedor.filter(pk__in=ids).delete()
        item.refresh_from_db()
        fila["revision"] = _revision(item)


def _guardar(request, solicitud, filas, eliminadas=None):
    if not isinstance(filas, list) or len(filas) > 200:
        raise ValidationError(
            "Envía como máximo 200 repuestos por guardado."
        )

    if eliminadas is None:
        eliminadas = []

    if not isinstance(eliminadas, list) or len(eliminadas) > 200:
        raise ValidationError(
            "Formato de eliminación no válido."
        )

    _eliminar_ofertas(request, solicitud, filas)

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
    clientes = set()
    clientes_oferta = set()
    ids_eliminar = set()

    # Validar eliminaciones.
    for dato in eliminadas:
        if not isinstance(dato, dict):
            raise ValidationError(
                "Formato de eliminación no válido."
            )

        identificador = _identificador(
            dato.get("id")
        )

        _identificador(
            dato.get("cliente")
        )

        if (
            identificador in ids_eliminar
            or identificador not in items
        ):
            raise PermissionDenied(
                "El repuesto no pertenece a esta tabla."
            )

        ids_eliminar.add(identificador)

        item = items[identificador]

        _permiso(
            request,
            "delete",
            "itemsolicitudcotizacion",
        )

        if ofertas_por_item.get(identificador):
            _permiso(
                request,
                "delete",
                "cotizacionproveedor",
            )

        if item.fotos.exists():
            _permiso(
                request,
                "delete",
                "fotoitemcotizacion",
            )

        if not constant_time_compare(
            str(dato.get("revision", "")),
            _revision(
                item,
                ofertas_por_item.get(identificador, []),
            ),
        ):
            raise ConflictoGuardado(
                "El repuesto cambió en otra sesión. "
                "Recarga para revisarlo."
            )

    # Validar referencias antes de escribir.
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

        if pk in ids_eliminar:
            raise ValidationError(
                "No puedes guardar y eliminar "
                "el mismo repuesto a la vez."
            )

        cliente = _identificador(
            fila.get("cliente")
        )

        if cliente is not None:
            if cliente in clientes:
                raise ValidationError(
                    "Hay una referencia de fila repetida."
                )

            clientes.add(cliente)

        if pk is not None:
            if pk in vistos or pk not in items:
                raise PermissionDenied(
                    "El repuesto no pertenece a esta tabla."
                )

            vistos.add(pk)

            if not constant_time_compare(
                str(fila.get("revision", "")),
                _revision(
                    items[pk],
                    ofertas_por_item.get(pk, []),
                ),
            ):
                raise ConflictoGuardado(
                    "Hay cambios de otra sesión. "
                    "Recarga para revisarlos; "
                    "tu edición sigue en esta pantalla."
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

            cliente_oferta = _identificador(
                dato.get("cliente")
            )

            if cliente_oferta is not None:
                if cliente_oferta in clientes_oferta:
                    raise ValidationError(
                        "Hay una referencia de oferta repetida."
                    )

                clientes_oferta.add(cliente_oferta)

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
            raise ConflictoGuardado(
                "Hay nuevas ofertas en otra sesión. "
                "Recarga para revisarlas."
            )

    confirmacion_eliminadas = []

    for dato in eliminadas:
        identificador = dato["id"]

        items[identificador].delete()

        confirmacion_eliminadas.append({
            "id": identificador,
            "cliente": dato.get("cliente"),
        })

    confirmaciones = []

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

        confirmacion_ofertas = []

        for posicion, dato in enumerate(fila["ofertas"], 1):
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

            else:
                datos_oferta = _datos(
                    oferta,
                    CAMPOS_OFERTA,
                )

                datos_oferta.update({
                    campo: dato[campo]
                    for campo in CAMPOS_OFERTA
                    if campo in dato
                })

                formulario = CotizacionProveedorForm(
                    datos_oferta,
                    instance=oferta,
                    item=item,
                    **_argumentos_formulario(request),
                )

                if es_nueva or formulario.has_changed():
                    _permiso(
                        request,
                        "add" if es_nueva else "change",
                        "cotizacionproveedor",
                    )

                    _validar(
                        formulario,
                        f"{referencia}, oferta {posicion}",
                    )

                    oferta = formulario.save()

            if es_nueva:
                ofertas_por_item.setdefault(
                    item.pk,
                    [],
                ).append(oferta)

            ofertas[oferta.pk] = oferta

            confirmacion_ofertas.append({
                **_datos(oferta, CAMPOS_OFERTA),
                "id": oferta.pk,
                "cliente": dato.get("cliente"),
            })

        confirmaciones.append({
            **_datos(item, CAMPOS_ITEM),
            "id": item.pk,
            "cliente": fila.get("cliente"),
            "revision": _revision(
                item,
                sorted(
                    ofertas_por_item.get(item.pk, []),
                    key=lambda oferta: oferta.pk,
                ),
            ),
            "ofertas": confirmacion_ofertas,
        })

    solicitud.actualizar_estado()

    return (
        confirmaciones,
        confirmacion_eliminadas,
    )


@login_required
@permission_required(
    LECTURA,
    raise_exception=True,
)
@require_http_methods(["GET", "POST"])
@never_cache
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

                confirmaciones, eliminadas = _guardar(
                    request,
                    solicitud,
                    carga.get("filas", []),
                    carga.get("eliminadas"),
                )

        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
        ):
            return JsonResponse(
                {"error": "Los datos enviados no son válidos."},
                status=400,
            )

        except PermissionDenied as error:
            return JsonResponse(
                {"error": str(error)},
                status=403,
            )

        except ConflictoGuardado as error:
            return JsonResponse(
                {"error": " ".join(error.messages)},
                status=409,
            )

        except ProtectedError:
            return JsonResponse(
                {
                    "error": (
                        "La oferta o el repuesto tiene registros vinculados "
                        "que impiden eliminarlo."
                    ),
                },
                status=400,
            )

        except ValidationError as error:
            return JsonResponse(
                {"error": " ".join(error.messages)},
                status=400,
            )

        return JsonResponse({
            "ok": True,
            "filas": confirmaciones,
            "eliminadas": eliminadas,
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
        "eliminar_item": "delete_itemsolicitudcotizacion",
        "eliminar_oferta": "delete_cotizacionproveedor",
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