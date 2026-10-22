import json

from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.forms.models import model_to_dict
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.crypto import constant_time_compare, salted_hmac
from django.views.decorators.http import require_http_methods

from compras.models import Proveedor

from ..forms import CotizacionProveedorForm
from ..forms_filas import FilaRepuestoForm
from ..models import CotizacionProveedor, ItemSolicitudCotizacion, SolicitudCotizacion
from .torre import LECTURA, _argumentos_formulario, _contexto, _exigir_abierta, _solicitudes


CAMPOS_ITEM = (
    "descripcion_solicitada", "cantidad", "unidad", "codigo_referencia",
    "marca_referencia", "medida_solicitada", "lado", "posicion", "observacion",
)
CAMPOS_OFERTA = tuple(CotizacionProveedorForm._meta.fields)


def _datos(objeto, campos):
    datos = model_to_dict(objeto, fields=campos)
    if isinstance(objeto, CotizacionProveedor):
        datos["disponible"] = {True: "SI", False: "NO", None: ""}[objeto.disponible]
    return datos


def _revision(item):
    def valores(objeto):
        return {f.attname: getattr(objeto, f.attname) for f in objeto._meta.concrete_fields}
    datos = [valores(item), [valores(o) for o in item.cotizaciones_proveedor.order_by("pk")]]
    return salted_hmac("torre.mesa", json.dumps(datos, sort_keys=True, default=str)).hexdigest()


def _permiso(request, accion, modelo):
    if not request.user.has_perm(f"cotizaciones.{accion}_{modelo}"):
        raise PermissionDenied("No tienes permiso para realizar este cambio.")


def _validar(formulario, referencia):
    if not formulario.is_valid():
        errores = []
        for campo, mensajes in formulario.errors.items():
            etiqueta = formulario.fields[campo].label if campo in formulario.fields else "Datos"
            errores.append(f"{etiqueta or campo}: {' '.join(mensajes)}")
        raise ValidationError(f"{referencia}: {'; '.join(errores)}")


def _identificador(valor):
    if valor is None:
        return None
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
        raise ValidationError("Identificador de fila no vÃ¡lido. Recarga la pantalla.")
    return valor


def _guardar(request, solicitud, filas):
    if not isinstance(filas, list) or len(filas) > 200:
        raise ValidationError("EnvÃ­a como mÃ¡ximo 200 repuestos por guardado.")
    items = {i.pk: i for i in solicitud.items.select_for_update().order_by("pk")}
    ofertas = {
        o.pk: o for o in CotizacionProveedor.objects.select_for_update().filter(
            item__solicitud=solicitud
        ).order_by("pk")
    }
    siguientes = (solicitud.items.aggregate(n=Max("orden_item"))["n"] or 0) + 1
    vistos, ofertas_vistas = set(), set()

    # Comprueba pertenencia y versiones antes de modificar cualquier fila.
    for fila in filas:
        if not isinstance(fila, dict) or not isinstance(fila.get("ofertas"), list):
            raise ValidationError("Formato de fila no vÃ¡lido.")
        pk = _identificador(fila.get("id"))
        if pk is not None:
            if pk in vistos or pk not in items:
                raise PermissionDenied("El repuesto no pertenece a esta tabla.")
            vistos.add(pk)
            if not constant_time_compare(str(fila.get("revision", "")), _revision(items[pk])):
                raise ValidationError("Otra persona modificÃ³ la tabla. Recarga antes de guardar.")
        if len(fila["ofertas"]) > 20:
            raise ValidationError("MÃ¡ximo 20 alternativas por repuesto.")
        existentes = set()
        for dato in fila["ofertas"]:
            if not isinstance(dato, dict):
                raise ValidationError("Formato de oferta no vÃ¡lido.")
            oid = _identificador(dato.get("id"))
            if oid is not None:
                if oid in ofertas_vistas or oid not in ofertas or ofertas[oid].item_id != pk:
                    raise PermissionDenied("La oferta no pertenece a este repuesto.")
                ofertas_vistas.add(oid)
                existentes.add(oid)
        if existentes != {o.pk for o in ofertas.values() if o.item_id == pk}:
            raise ValidationError("Faltan ofertas guardadas. Recarga la tabla.")

    for numero, fila in enumerate(filas, 1):
        referencia = f"Repuesto {numero}"
        item = items.get(fila.get("id"))
        nuevo = item is None
        if nuevo:
            item = ItemSolicitudCotizacion(
                solicitud=solicitud, orden_item=siguientes,
                unidad="UNIDAD", lado="NO_APLICA", posicion="NO_APLICA",
            )
            siguientes += 1
        comprado = item.estado_abastecimiento == "COMPRADO"
        unidad_anterior = item.unidad
        anteriores = [o for o in ofertas.values() if o.item_id == item.pk] if not nuevo else []
        ganadora_anterior = next((o.pk for o in anteriores if o.estado == "GANADORA"), None)
        datos = _datos(item, FilaRepuestoForm._meta.fields)
        datos.update({c: fila[c] for c in CAMPOS_ITEM if c in fila})
        datos["revision"] = ""  # La versiÃ³n completa se valida arriba.
        formulario = FilaRepuestoForm(
            datos, instance=item, solicitud=solicitud, **_argumentos_formulario(request)
        )
        formulario.initial["revision"] = ""
        cambios = formulario.has_changed()
        if nuevo or cambios:
            _permiso(request, "add" if nuevo else "change", "itemsolicitudcotizacion")
            _validar(formulario, referencia)
            if anteriores and formulario.cleaned_data["unidad"] != unidad_anterior:
                raise ValidationError(f"{referencia}: conserva la unidad ya cotizada; cambia la presentaciÃ³n dentro de la oferta.")
            item = formulario.save()

        elegidas = [d for d in fila["ofertas"] if d.get("elegida") is True]
        if len(elegidas) > 1:
            raise ValidationError(f"{referencia}: elige solamente una oferta.")
        ganadora_pedida = elegidas[0].get("id") if elegidas else None
        cambia_eleccion = bool(elegidas and ganadora_pedida is None) or ganadora_pedida != ganadora_anterior
        if cambia_eleccion:
            _permiso(request, "change", "cotizacionproveedor")
        elegida = None
        for posicion, dato in enumerate(fila["ofertas"], 1):
            oferta = ofertas.get(dato.get("id"))
            es_nueva = oferta is None
            if es_nueva:
                oferta = CotizacionProveedor(item=item)
            datos_oferta = _datos(oferta, CAMPOS_OFERTA)
            datos_oferta.update({c: dato[c] for c in CAMPOS_OFERTA if c in dato})
            form = CotizacionProveedorForm(
                datos_oferta, instance=oferta, item=item, **_argumentos_formulario(request)
            )
            if es_nueva or form.has_changed():
                if comprado:
                    raise ValidationError(f"{referencia}: las ofertas del repuesto comprado estÃ¡n bloqueadas.")
                _permiso(request, "add" if es_nueva else "change", "cotizacionproveedor")
                if oferta.estado == "GANADORA":
                    oferta.estado = "RESPONDIO"
                _validar(form, f"{referencia}, oferta {posicion}")
                oferta = form.save()
            if dato.get("elegida") is True:
                elegida = oferta

        if not comprado and request.user.has_perm("cotizaciones.change_cotizacionproveedor"):
            if elegida is not None:
                elegida.seleccionar()
            elif ganadora_anterior is not None:
                item.cotizaciones_proveedor.filter(estado="GANADORA").update(estado="RESPONDIO")
                item.actualizar_estado_abastecimiento()
        if fila.get("comprado") is True and not comprado:
            _permiso(request, "change", "itemsolicitudcotizacion")
            item.refresh_from_db()
            item.marcar_comprado()
    solicitud.actualizar_estado()


@login_required
@permission_required(LECTURA, raise_exception=True)
@require_http_methods(["GET", "POST"])
def detalle(request, pk):
    if request.method == "POST":
        try:
            carga = json.loads(request.body)
            if not isinstance(carga, dict):
                raise ValidationError("Formato de tabla no vÃ¡lido.")
            with transaction.atomic():
                solicitud = get_object_or_404(_solicitudes(request).select_for_update(), pk=pk)
                _exigir_abierta(solicitud)
                _guardar(request, solicitud, carga.get("filas"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"error": "Los datos enviados no son vÃ¡lidos."}, status=400)
        except ValidationError as error:
            return JsonResponse({"error": " ".join(error.messages)}, status=400)
        return JsonResponse({"ok": True})

    solicitud = get_object_or_404(_solicitudes(request), pk=pk)
    filas = []
    for item in solicitud.items.order_by("orden_item", "pk"):
        cotizaciones = []
        for oferta in item.cotizaciones_proveedor.order_by("pk"):
            cotizaciones.append({
                **_datos(oferta, CAMPOS_OFERTA), "id": oferta.pk,
                "elegida": oferta.estado == "GANADORA",
                "total": oferta.costo_requerimiento,
            })
        filas.append({
            **_datos(item, CAMPOS_ITEM), "id": item.pk, "revision": _revision(item),
            "estado": item.get_estado_abastecimiento_display(),
            "clase_estado": item.clase_estado,
            "comprado": item.estado_abastecimiento == "COMPRADO",
            "ofertas": cotizaciones,
        })
    abierta = solicitud.estado != "CANCELADA" and solicitud.orden.estado != "ANULADA"
    permisos = {
        clave: abierta and request.user.has_perm(f"cotizaciones.{permiso}")
        for clave, permiso in {
            "agregar_item": "add_itemsolicitudcotizacion",
            "editar_item": "change_itemsolicitudcotizacion",
            "agregar_oferta": "add_cotizacionproveedor",
            "editar_oferta": "change_cotizacionproveedor",
        }.items()
    }
    proveedores = Proveedor.objects.filter(activo=True)
    usados = {o["proveedor"] for f in filas for o in f["ofertas"]}
    proveedores = (proveedores | Proveedor.objects.filter(pk__in=usados)).order_by("empresa", "nombre_contacto")
    return render(request, "cotizaciones/torre/mesa.html", _contexto(
        request, solicitud=solicitud,
        mesa={
            "filas": filas, "permisos": permisos,
            "proveedores": [[p.pk, p.empresa or p.nombre_contacto or str(p.pk)] for p in proveedores],
            "unidades": ItemSolicitudCotizacion.UNIDADES,
            "lados": ItemSolicitudCotizacion.LADOS,
            "posiciones": ItemSolicitudCotizacion.POSICIONES,
        },
    ))