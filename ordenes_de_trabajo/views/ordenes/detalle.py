from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse

from inventario.models import CodigoProducto, Categoria
from servicios.models import ServicioCatalogo

from ...models import (
    OrdenTrabajo,
    OrdenCroquisDanio,
    OrdenInsumoDetalle,
    OrdenServicioDetalle,
    OrdenServicioProcedimientoDetalle,
    PlantillaRecomendacion,
    OrdenRecomendacion,
    Tecnico,
)

from ..utils import (
    parse_decimal,
    parse_cantidad,
    obtener_sucursal_activa,
    puede_operar_orden_desde_sucursal_activa,
)


def item(lista, i, default=""):
    if i < len(lista):
        return str(lista[i]).strip()
    return default


def buscar_producto(p_id, barras, empaque):
    if p_id:
        producto = CodigoProducto.objects.filter(id=p_id, activo=True).first()
        if producto:
            return producto

    codigo_busqueda = barras or empaque

    if codigo_busqueda:
        producto = CodigoProducto.objects.filter(
            Q(codigo=codigo_busqueda)
            | Q(codigo_barras=codigo_busqueda)
            | Q(nombre_comercial__icontains=codigo_busqueda)
        ).first()

        if producto and producto.activo:
            return producto

    return None


def merge_repuestos(request, orden):
    detalle_ids = request.POST.getlist("rep_detalle_id[]")
    producto_ids = request.POST.getlist("rep_producto_id[]")
    descripciones = request.POST.getlist("rep_descripcion[]")
    precios = request.POST.getlist("rep_pu[]")
    cantidades = request.POST.getlist("rep_cantidad[]")
    categorias = request.POST.getlist("rep_categoria_id[]")
    barras_list = request.POST.getlist("rep_codigo_barras[]")
    empaques = request.POST.getlist("rep_codigo_empaque[]")
    deletes = request.POST.getlist("rep_delete[]")

    total = max(
        len(detalle_ids),
        len(producto_ids),
        len(descripciones),
        len(precios),
        len(cantidades),
        len(categorias),
        len(barras_list),
        len(empaques),
        len(deletes),
        0,
    )

    existentes = {
        str(obj.id): obj
        for obj in OrdenInsumoDetalle.objects.select_for_update().filter(orden=orden)
    }

    for i in range(total):
        detalle_id = item(detalle_ids, i)
        producto_id = item(producto_ids, i)
        descripcion = item(descripciones, i)
        pu_str = item(precios, i)
        cantidad_str = item(cantidades, i)
        categoria_id = item(categorias, i)
        barras = item(barras_list, i)
        empaque = item(empaques, i)
        eliminar = item(deletes, i) == "1"

        if not detalle_id and not producto_id and not descripcion:
            continue

        if detalle_id:
            detalle = existentes.get(detalle_id)

            if not detalle:
                continue

            if eliminar:
                detalle.delete()
                continue

            cantidad = parse_cantidad(cantidad_str, Decimal("1.00"))
            if cantidad <= 0:
                continue

            producto = buscar_producto(producto_id, barras, empaque)

            precio_default = (
                Decimal(producto.precio_venta or 0)
                if producto
                else Decimal("0.00")
            )

            precio = parse_decimal(pu_str, precio_default)

            detalle.producto = producto
            detalle.descripcion_factura = descripcion
            detalle.cantidad = cantidad
            detalle.precio_unitario = precio
            detalle.categoria_referencia_id = None if producto else (categoria_id or None)
            detalle.codigo_barras_referencia = None if producto else (barras or None)
            detalle.codigo_empaque_referencia = None if producto else (empaque or None)
            detalle.orden_item = i + 1
            detalle.save()

        else:
            if eliminar:
                continue

            cantidad = parse_cantidad(cantidad_str, Decimal("1.00"))
            if cantidad <= 0:
                continue

            producto = buscar_producto(producto_id, barras, empaque)

            precio_default = (
                Decimal(producto.precio_venta or 0)
                if producto
                else Decimal("0.00")
            )

            precio = parse_decimal(pu_str, precio_default)

            OrdenInsumoDetalle.objects.create(
                orden=orden,
                producto=producto,
                descripcion_factura=descripcion,
                cantidad=cantidad,
                precio_unitario=precio,
                categoria_referencia_id=None if producto else (categoria_id or None),
                codigo_barras_referencia=None if producto else (barras or None),
                codigo_empaque_referencia=None if producto else (empaque or None),
                orden_item=i + 1,
            )


def merge_procedimientos(request, detalle_servicio, prefix, uid):
    proc_ids = request.POST.getlist(f"{prefix}_procedimiento_id_{uid}[]")
    proc_descs = request.POST.getlist(f"{prefix}_procedimientos_{uid}[]")
    proc_deletes = request.POST.getlist(f"{prefix}_procedimiento_delete_{uid}[]")

    total = max(
        len(proc_ids),
        len(proc_descs),
        len(proc_deletes),
        0,
    )

    existentes = {
        str(obj.id): obj
        for obj in OrdenServicioProcedimientoDetalle.objects.select_for_update().filter(
            detalle_servicio=detalle_servicio
        )
    }

    vistos = set()

    for i in range(total):
        proc_id = item(proc_ids, i)
        descripcion = item(proc_descs, i)
        eliminar = item(proc_deletes, i) == "1"

        if not proc_id and not descripcion:
            continue

        clave = descripcion.upper()

        if clave and clave in vistos:
            continue

        if clave:
            vistos.add(clave)

        if proc_id:
            proc = existentes.get(proc_id)

            if not proc:
                continue

            if eliminar:
                proc.delete()
                continue

            proc.descripcion = descripcion
            proc.orden_item = i + 1
            proc.save()

        else:
            if eliminar:
                continue

            if not descripcion:
                continue

            OrdenServicioProcedimientoDetalle.objects.create(
                detalle_servicio=detalle_servicio,
                descripcion=descripcion,
                orden_item=i + 1,
            )


def merge_servicios(request, orden):
    recomendaciones_auto_ids = set()

    for prefix, tipo_bd in [("moi", "MEC"), ("moe", "EXT")]:
        detalle_ids = request.POST.getlist(f"{prefix}_detalle_id[]")
        uid_list = request.POST.getlist(f"{prefix}_uid[]")
        desc_list = request.POST.getlist(f"{prefix}_descripcion[]")
        pu_list = request.POST.getlist(f"{prefix}_pu[]")
        cant_list = request.POST.getlist(f"{prefix}_cantidad[]")
        serv_ids = request.POST.getlist(f"{prefix}_servicio_id[]")
        variante_list = request.POST.getlist(f"{prefix}_variante_precio[]")
        deletes = request.POST.getlist(f"{prefix}_delete[]")

        total = max(
            len(detalle_ids),
            len(uid_list),
            len(desc_list),
            len(pu_list),
            len(cant_list),
            len(serv_ids),
            len(variante_list),
            len(deletes),
            0,
        )

        existentes = {
            str(obj.id): obj
            for obj in OrdenServicioDetalle.objects.select_for_update().filter(
                orden=orden,
                tipo_servicio=tipo_bd,
            )
        }

        for i in range(total):
            detalle_id = item(detalle_ids, i)
            uid = item(uid_list, i) or detalle_id or str(i)
            descripcion = item(desc_list, i)
            precio_str = item(pu_list, i, "0.00")
            cantidad_str = item(cant_list, i, "1.00")
            servicio_id = item(serv_ids, i)
            variante = item(variante_list, i).upper() or "NORMAL"
            eliminar = item(deletes, i) == "1"

            servicio = None

            if servicio_id:
                servicio = ServicioCatalogo.objects.filter(
                    id=servicio_id,
                    activo=True,
                ).first()

            if servicio and not descripcion:
                descripcion = servicio.descripcion

            if not detalle_id and not descripcion and not servicio:
                continue

            if detalle_id:
                detalle = existentes.get(detalle_id)

                if not detalle:
                    continue

                if eliminar:
                    detalle.delete()
                    continue

                cantidad = parse_decimal(cantidad_str, Decimal("1.00"))
                if cantidad <= 0:
                    continue

                precio = parse_decimal(precio_str, Decimal("0.00"))

                detalle.servicio = servicio
                detalle.descripcion_servicio = descripcion
                detalle.cantidad = cantidad
                detalle.precio_unitario = precio
                detalle.orden_item = i + 1
                detalle.tipo_servicio = tipo_bd
                detalle.tipo_tarifa_aplicada = orden.tipo_tarifa_vehiculo or "NO_APLICA"
                detalle.variante_precio_aplicada = variante
                detalle.save()

            else:
                if eliminar:
                    continue

                cantidad = parse_decimal(cantidad_str, Decimal("1.00"))
                if cantidad <= 0:
                    continue

                precio = parse_decimal(precio_str, Decimal("0.00"))

                detalle = OrdenServicioDetalle.objects.create(
                    orden=orden,
                    servicio=servicio,
                    descripcion_servicio=descripcion,
                    cantidad=cantidad,
                    precio_unitario=precio,
                    orden_item=i + 1,
                    tipo_servicio=tipo_bd,
                    tipo_tarifa_aplicada=orden.tipo_tarifa_vehiculo or "NO_APLICA",
                    variante_precio_aplicada=variante,
                )

            if servicio:
                recs = PlantillaRecomendacion.objects.filter(
                    activo=True,
                    servicios=servicio,
                ).values_list("id", flat=True)

                recomendaciones_auto_ids.update(recs)

            merge_procedimientos(
                request=request,
                detalle_servicio=detalle,
                prefix=prefix,
                uid=uid,
            )

    return recomendaciones_auto_ids


def merge_recomendaciones_automaticas(orden, recomendaciones_auto_ids):
    claves_existentes = {
        (
            (obj.titulo or "").strip().upper(),
            (obj.texto or "").strip().upper(),
        )
        for obj in OrdenRecomendacion.objects.filter(orden=orden)
    }

    orden_item = OrdenRecomendacion.objects.filter(orden=orden).count() + 1

    for rec in PlantillaRecomendacion.objects.filter(
        id__in=recomendaciones_auto_ids,
        activo=True,
    ).order_by("orden_visual", "titulo"):

        clave = (
            rec.titulo.strip().upper(),
            rec.texto.strip().upper(),
        )

        if clave in claves_existentes:
            continue

        OrdenRecomendacion.objects.create(
            orden=orden,
            plantilla=rec,
            titulo=rec.titulo,
            texto=rec.texto,
            orden_item=orden_item,
        )

        claves_existentes.add(clave)
        orden_item += 1


def merge_recomendaciones_manuales(request, orden):
    detalle_ids = request.POST.getlist("recomendacion_detalle_id[]")
    plantilla_ids = request.POST.getlist("recomendacion_id[]")
    titulos = request.POST.getlist("recomendacion_titulo[]")
    textos = request.POST.getlist("recomendacion_texto[]")
    deletes = request.POST.getlist("recomendacion_delete[]")

    total = max(
        len(detalle_ids),
        len(plantilla_ids),
        len(titulos),
        len(textos),
        len(deletes),
        0,
    )

    existentes = {
        str(obj.id): obj
        for obj in OrdenRecomendacion.objects.select_for_update().filter(
            orden=orden
        )
    }

    claves = {
        (
            (obj.titulo or "").strip().upper(),
            (obj.texto or "").strip().upper(),
        )
        for obj in existentes.values()
    }

    orden_item = len(existentes) + 1

    for i in range(total):
        detalle_id = item(detalle_ids, i)
        plantilla_id = item(plantilla_ids, i)
        titulo = item(titulos, i)
        texto = item(textos, i)
        eliminar = item(deletes, i) == "1"

        if not detalle_id and not titulo and not texto:
            continue

        if not titulo:
            titulo = "RECOMENDACIÓN"

        if detalle_id:
            recomendacion = existentes.get(detalle_id)

            if not recomendacion:
                continue

            if eliminar:
                recomendacion.delete()
                continue

            recomendacion.titulo = titulo
            recomendacion.texto = texto
            recomendacion.orden_item = i + 1
            recomendacion.save()

        else:
            if eliminar:
                continue

            clave = (titulo.upper(), texto.upper())

            if clave in claves:
                continue

            plantilla = None

            if plantilla_id and plantilla_id.isdigit():
                plantilla = PlantillaRecomendacion.objects.filter(
                    id=plantilla_id
                ).first()

            OrdenRecomendacion.objects.create(
                orden=orden,
                plantilla=plantilla,
                titulo=titulo,
                texto=texto,
                orden_item=orden_item,
            )

            claves.add(clave)
            orden_item += 1


def guardar_detalle_ot(request, pk):
    with transaction.atomic():
        orden = (
            OrdenTrabajo.objects
            .select_for_update(of=("self",))
            .get(pk=pk)
        )
        messages.error(
            request,
            f"DEBUG POST: rep={len(request.POST.getlist('rep_descripcion[]'))}, "
            f"moi={len(request.POST.getlist('moi_descripcion[]'))}, "
            f"moe={len(request.POST.getlist('moe_descripcion[]'))}, "
            f"rec={len(request.POST.getlist('recomendacion_titulo[]'))}"
        )
        if orden.estado != "ABIERTA":
            messages.error(
                request,
                "No se puede modificar una orden cerrada o anulada.",
            )
            return redirect("detalle_orden", pk=orden.pk)

        version_form = request.POST.get("orden_version")
        version_coincide = True

        if version_form and version_form.isdigit():
            version_coincide = int(version_form) == orden.version

        merge_repuestos(request, orden)

        recomendaciones_auto_ids = merge_servicios(request, orden)

        merge_recomendaciones_automaticas(
            orden=orden,
            recomendaciones_auto_ids=recomendaciones_auto_ids,
        )

        merge_recomendaciones_manuales(request, orden)

        if version_coincide:
            orden.descuento_porcentaje = parse_decimal(
                request.POST.get("descuento_porcentaje", "0"),
                Decimal("0.00"),
            )

            orden.observaciones_tecnicas = request.POST.get(
                "observaciones_tecnicas",
                "",
            ).strip()
        else:
            messages.warning(
                request,
                "La orden fue modificada por otro usuario mientras estaba abierta. "
                "Se guardaron los detalles enviados, pero no se sobrescribió la cabecera.",
            )

        orden.version += 1

        if version_coincide:
            orden.save(update_fields=[
                "descuento_porcentaje",
                "observaciones_tecnicas",
                "version",
                "actualizado_en",
            ])
        else:
            orden.save(update_fields=[
                "version",
                "actualizado_en",
            ])

        orden.calcular_total()

    messages.success(request, "Orden actualizada correctamente.")
    return redirect("detalle_orden", pk=pk)

@login_required
def detalle_orden(request, pk):
    sucursal_activa = obtener_sucursal_activa(request)

    orden = get_object_or_404(
        OrdenTrabajo.objects
        .select_related(
            "sucursal",
            "cliente",
            "expediente",
            "configuracion_iva",
        )
        .prefetch_related(
            "insumos_historicos",
            "servicios_historicos",
            "insumos_detalles",
            "servicios_detalles",
            "recomendaciones_items",
            "tecnicos",
        ),
        pk=pk,
    )

    url_anterior = request.META.get("HTTP_REFERER")

    if not url_anterior or f"ordenes/{pk}" in url_anterior:
        url_anterior = reverse("lista_ordenes")

    es_su_sucursal = puede_operar_orden_desde_sucursal_activa(
        request,
        orden,
    )

    puede_reabrir = (
        request.user.has_perm("ordenes_de_trabajo.can_reopen_orden")
        and orden.estado in ["CERRADA", "ANULADA"]
    )

    puede_editar = (
        es_su_sucursal
        and orden.estado == "ABIERTA"
    )

    if request.method == "POST":
        if not puede_editar:
            messages.error(
                request,
                "Operación denegada: No tiene permisos para modificar esta orden.",
            )
            return redirect("detalle_orden", pk=orden.pk)

        return guardar_detalle_ot(request, pk)

    categorias = (
        Categoria.objects.all().order_by("nombre")
        if puede_editar
        else []
    )

    tecnicos_disponibles = Tecnico.objects.filter(activo=True)

    croquis = OrdenCroquisDanio.objects.filter(orden=orden).first()

    croquis_url = (
        croquis.imagen_generada.url
        if croquis and croquis.imagen_generada
        else ""
    )

    orden.calcular_total()

    subtotal = Decimal(orden.subtotal_sin_iva or 0)
    descuento = Decimal(orden.valor_descuento or 0)
    porcentaje_descuento = Decimal(orden.descuento_porcentaje or 0)
    porcentaje_iva = Decimal(orden.porcentaje_iva or 0)
    iva = Decimal(orden.valor_iva or 0)
    total_final = Decimal(orden.total_final or 0)

    return render(
        request,
        "detalle_orden.html",
        {
            "orden": orden,
            "croquis": croquis,
            "croquis_url": croquis_url,
            "categorias_inventario": categorias,
            "tecnicos_disponibles": tecnicos_disponibles,
            "sucursal_activa": sucursal_activa,
            "puede_editar": puede_editar,
            "puede_reabrir": puede_reabrir,
            "url_anterior": url_anterior,
            "subtotal": subtotal,
            "descuento": descuento,
            "porcentaje_descuento": porcentaje_descuento,
            "porcentaje_iva": porcentaje_iva,
            "iva": iva,
            "total_final": total_final,
            "porcentaje_iva_html": str(porcentaje_iva).replace(",", "."),
            "descuento_porcentaje_html": str(porcentaje_descuento).replace(",", "."),
        },
    )