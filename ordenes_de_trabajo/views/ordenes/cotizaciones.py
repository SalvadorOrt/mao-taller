import uuid
import traceback
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from inventario.models import CodigoProducto, Categoria
from servicios.models import ServicioCatalogo

from ...models import (
    Cliente,
    OrdenTrabajo,
    OrdenInsumoDetalle,
    OrdenServicioDetalle,
    OrdenServicioProcedimientoDetalle,
    Cotizacion,
    CotizacionInsumoDetalle,
    CotizacionServicioDetalle,
    CotizacionProcedimientoDetalle,
)

from ..utils import (
    parse_decimal,
    parse_cantidad,
    obtener_sucursal_activa,
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


def merge_repuestos_cotizacion(request, cotizacion):
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
        for obj in CotizacionInsumoDetalle.objects.select_for_update().filter(
            cotizacion=cotizacion
        )
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

            CotizacionInsumoDetalle.objects.create(
                cotizacion=cotizacion,
                producto=producto,
                descripcion_factura=descripcion,
                cantidad=cantidad,
                precio_unitario=precio,
                categoria_referencia_id=None if producto else (categoria_id or None),
                codigo_barras_referencia=None if producto else (barras or None),
                codigo_empaque_referencia=None if producto else (empaque or None),
                orden_item=i + 1,
            )


def merge_procedimientos_cotizacion(request, detalle_servicio, prefix, uid):
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
        for obj in CotizacionProcedimientoDetalle.objects.select_for_update().filter(
            servicio_cotizado=detalle_servicio
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

            CotizacionProcedimientoDetalle.objects.create(
                servicio_cotizado=detalle_servicio,
                descripcion=descripcion,
                orden_item=i + 1,
            )


def merge_servicios_cotizacion(request, cotizacion):
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
            for obj in CotizacionServicioDetalle.objects.select_for_update().filter(
                cotizacion=cotizacion,
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
                detalle.tipo_tarifa_aplicada = cotizacion.tipo_tarifa_vehiculo or "NO_APLICA"
                detalle.variante_precio_aplicada = variante
                detalle.save()

            else:
                if eliminar:
                    continue

                cantidad = parse_decimal(cantidad_str, Decimal("1.00"))
                if cantidad <= 0:
                    continue

                precio = parse_decimal(precio_str, Decimal("0.00"))

                detalle = CotizacionServicioDetalle.objects.create(
                    cotizacion=cotizacion,
                    servicio=servicio,
                    descripcion_servicio=descripcion,
                    cantidad=cantidad,
                    precio_unitario=precio,
                    orden_item=i + 1,
                    tipo_servicio=tipo_bd,
                    tipo_tarifa_aplicada=cotizacion.tipo_tarifa_vehiculo or "NO_APLICA",
                    variante_precio_aplicada=variante,
                )

            merge_procedimientos_cotizacion(
                request=request,
                detalle_servicio=detalle,
                prefix=prefix,
                uid=uid,
            )


def guardar_detalle_cotizacion(request, pk):
    with transaction.atomic():
        cotizacion = (
            Cotizacion.objects
            .select_for_update(of=("self",))
            .get(pk=pk)
        )

        if cotizacion.estado != "PENDIENTE":
            messages.error(
                request,
                "No se puede modificar una cotización aprobada o rechazada.",
            )
            return redirect("detalle_cotizacion", pk=cotizacion.pk)

        merge_repuestos_cotizacion(request, cotizacion)
        merge_servicios_cotizacion(request, cotizacion)

        cotizacion.descuento_porcentaje = parse_decimal(
            request.POST.get("descuento_porcentaje", "0"),
            Decimal("0.00"),
        )

        cotizacion.observaciones = request.POST.get(
            "observaciones",
            "",
        ).strip()

        cotizacion.save(update_fields=[
            "descuento_porcentaje",
            "observaciones",
        ])

        cotizacion.calcular_total()

    messages.success(request, "Cotización actualizada correctamente.")
    return redirect("detalle_cotizacion", pk=pk)


@login_required
def crear_cotizacion(request):
    sucursal_activa = obtener_sucursal_activa(request)

    if not sucursal_activa:
        messages.error(request, "Debe tener una sucursal activa.")
        return redirect("dashboard")

    if request.method == "POST":
        placa = request.POST.get("placa", "").strip().upper().replace("-", "").replace(" ", "")
        vehiculo = request.POST.get("vehiculo", "").strip().upper()
        anio = request.POST.get("anio_vehiculo", "").strip()
        identificacion = request.POST.get("identificacion", "").strip()
        nombre_cliente = request.POST.get("nombre_cliente", "").strip().upper()
        observaciones = request.POST.get("observaciones", "").strip()

        if not placa:
            messages.error(request, "La placa es obligatoria.")
            return redirect("crear_cotizacion")

        cliente_obj = None

        if identificacion:
            cliente_obj = Cliente.objects.filter(
                identificacion=identificacion
            ).first()

            if not cliente_obj:
                cliente_obj = Cliente.objects.create(
                    identificacion=identificacion,
                    nombre_completo=nombre_cliente or "CONSUMIDOR FINAL",
                )

        with transaction.atomic():
            numero = f"COT-{timezone.now().strftime('%y%m')}-{uuid.uuid4().hex[:4].upper()}"

            cotizacion = Cotizacion.objects.create(
                numero_cotizacion=numero,
                sucursal=sucursal_activa,
                cliente=cliente_obj,
                cliente_respaldo=nombre_cliente or None,
                placa=placa,
                vehiculo=vehiculo,
                anio_vehiculo=int(anio) if anio.isdigit() else None,
                observaciones=observaciones,
                estado="PENDIENTE",
            )

        messages.success(request, f"Cotización {numero} creada.")
        return redirect("detalle_cotizacion", pk=cotizacion.pk)

    return render(
        request,
        "crear_cotizacion.html",
        {
            "sucursal_activa": sucursal_activa,
        },
    )


@login_required
def nueva_cotizacion_desde_ot(request, pk_orden):
    orden = get_object_or_404(OrdenTrabajo, pk=pk_orden)

    cotizacion, created = Cotizacion.objects.get_or_create(
        orden=orden,
        defaults={
            "numero_cotizacion": f"PRO-{orden.numero_orden}",
            "sucursal": orden.sucursal,
            "cliente": orden.cliente,
            "cliente_respaldo": orden.cliente_respaldo,
            "placa": orden.placa,
            "vehiculo": orden.vehiculo,
            "anio_vehiculo": orden.anio_vehiculo,
            "tipo_tarifa_vehiculo": orden.tipo_tarifa_vehiculo,
            "gama_vehiculo": orden.gama_vehiculo,
            "estado": "PENDIENTE",
        },
    )

    if created:
        messages.success(
            request,
            f"Proforma generada para {orden.numero_orden}.",
        )

    return redirect("detalle_cotizacion", pk=cotizacion.pk)


@login_required
def detalle_cotizacion(request, pk):
    cotizacion = get_object_or_404(
        Cotizacion.objects
        .select_related(
            "sucursal",
            "cliente",
            "orden",
            "orden_generada",
            "configuracion_iva",
        )
        .prefetch_related(
            "insumos_cotizados",
            "servicios_cotizados",
            "servicios_cotizados__procedimientos_detalle",
        ),
        pk=pk,
    )

    sucursal_activa = obtener_sucursal_activa(request)
    categorias = Categoria.objects.all().order_by("nombre")

    puede_editar = cotizacion.estado == "PENDIENTE"

    if request.method == "POST":
        if not puede_editar:
            messages.error(
                request,
                "No se puede modificar una cotización aprobada o rechazada.",
            )
            return redirect("detalle_cotizacion", pk=cotizacion.pk)

        try:
            return guardar_detalle_cotizacion(request, pk)

        except Exception as e:
            print(traceback.format_exc())
            messages.error(
                request,
                f"Ocurrió un error al guardar la cotización: {str(e)}",
            )
            return redirect("detalle_cotizacion", pk=cotizacion.pk)

    cotizacion.calcular_total()

    subtotal = Decimal(cotizacion.subtotal_sin_iva or 0)
    descuento = Decimal(cotizacion.valor_descuento or 0)
    porcentaje_descuento = Decimal(cotizacion.descuento_porcentaje or 0)
    porcentaje_iva = Decimal(cotizacion.porcentaje_iva or 0)
    iva = Decimal(cotizacion.valor_iva or 0)
    total_final = Decimal(cotizacion.total_final or 0)

    return render(
        request,
        "detalle_cotizacion.html",
        {
            "cotizacion": cotizacion,
            "categorias_inventario": categorias,
            "sucursal_activa": sucursal_activa,
            "puede_editar": puede_editar,
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


@login_required
def aprobar_cotizacion(request, pk):
    cotizacion = get_object_or_404(
        Cotizacion.objects.prefetch_related(
            "insumos_cotizados",
            "servicios_cotizados",
            "servicios_cotizados__procedimientos_detalle",
        ),
        pk=pk,
    )

    if cotizacion.estado != "PENDIENTE":
        messages.error(request, "Esta cotización ya no está pendiente.")
        return redirect("detalle_cotizacion", pk=pk)

    if request.method != "POST":
        return redirect("detalle_cotizacion", pk=pk)

    try:
        with transaction.atomic():
            if cotizacion.orden:
                orden_destino = cotizacion.orden
            else:
                numero_ot = f"OT-{timezone.now().strftime('%y%m')}-{uuid.uuid4().hex[:4].upper()}"

                orden_destino = OrdenTrabajo.objects.create(
                    numero_orden=numero_ot,
                    sucursal=cotizacion.sucursal,
                    cliente=cotizacion.cliente,
                    cliente_respaldo=cotizacion.cliente_respaldo,
                    placa=cotizacion.placa,
                    vehiculo=cotizacion.vehiculo,
                    anio_vehiculo=cotizacion.anio_vehiculo,
                    tipo_tarifa_vehiculo=cotizacion.tipo_tarifa_vehiculo,
                    gama_vehiculo=cotizacion.gama_vehiculo,
                    observaciones_tecnicas=cotizacion.observaciones,
                    estado="ABIERTA",
                )

                cotizacion.orden_generada = orden_destino

            for item in cotizacion.insumos_cotizados.all():
                OrdenInsumoDetalle.objects.create(
                    orden=orden_destino,
                    producto=item.producto,
                    descripcion_factura=item.descripcion_factura,
                    cantidad=item.cantidad,
                    precio_unitario=item.precio_unitario,
                    categoria_referencia=item.categoria_referencia,
                    codigo_empaque_referencia=item.codigo_empaque_referencia,
                    codigo_barras_referencia=item.codigo_barras_referencia,
                    orden_item=item.orden_item,
                )

            for serv in cotizacion.servicios_cotizados.all():
                nuevo_servicio_ot = OrdenServicioDetalle.objects.create(
                    orden=orden_destino,
                    servicio=serv.servicio,
                    tipo_servicio=serv.tipo_servicio,
                    descripcion_servicio=serv.descripcion_servicio,
                    cantidad=serv.cantidad,
                    precio_unitario=serv.precio_unitario,
                    orden_item=serv.orden_item,
                    tipo_tarifa_aplicada=serv.tipo_tarifa_aplicada,
                    variante_precio_aplicada=serv.variante_precio_aplicada,
                )

                for proc in serv.procedimientos_detalle.all():
                    OrdenServicioProcedimientoDetalle.objects.create(
                        detalle_servicio=nuevo_servicio_ot,
                        descripcion=proc.descripcion,
                        orden_item=proc.orden_item,
                    )

            cotizacion.estado = "APROBADA"
            cotizacion.save(update_fields=[
                "estado",
                "orden_generada",
            ])

            orden_destino.calcular_total()

        messages.success(
            request,
            "Cotización aprobada y cargada a la Orden de Trabajo.",
        )
        return redirect("detalle_orden", pk=orden_destino.pk)

    except Exception as e:
        print(traceback.format_exc())
        messages.error(request, f"Error al aprobar la cotización: {str(e)}")
        return redirect("detalle_cotizacion", pk=pk)