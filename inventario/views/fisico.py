'''
fisico.py

Conteo físico de bodega.

Debe permitir:

crear inventario físico
listar inventarios físicos
abrir conteo
registrar cantidades contadas
ver diferencias
cerrar inventario
aplicar ajustes al stock

Modelos:

InventarioFisico
DetalleInventarioFisico
MovimientoStock

En resumen:

Catálogo = qué producto existe
Stock = cuánto hay
Movimientos = por qué cambió el stock
Dashboard = resumen
Físico = conteo real vs sistema
'''

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from ordenes_de_trabajo.models import Sucursal
from ordenes_de_trabajo.views.utils import (
    obtener_sucursal_activa,
    usuario_puede_cambiar_sucursal,
)

from ..models import (
    InventarioFisico,
    DetalleInventarioFisico,
    StockSucursal,
    CodigoProducto,
    MovimientoStock,
    Categoria,
    MarcaRepuesto,
)


@login_required
def inventario_fisico_lista(request):
    sucursal_activa = obtener_sucursal_activa(request)

    sucursales = (
        Sucursal.objects.filter(activa=True).order_by("nombre")
        if usuario_puede_cambiar_sucursal(request)
        else []
    )

    inventarios = (
        InventarioFisico.objects
        .select_related("sucursal")
        .annotate(total_detalles=Count("detalles"))
        .order_by("-fecha_inicio")
    )

    sucursal_id = request.GET.get("sucursal", "").strip()
    estado = request.GET.get("estado", "").strip()
    q = request.GET.get("q", "").strip()

    if sucursal_id:
        inventarios = inventarios.filter(sucursal_id=sucursal_id)
    elif sucursal_activa:
        inventarios = inventarios.filter(sucursal=sucursal_activa)

    if estado:
        inventarios = inventarios.filter(estado=estado)

    if q:
        inventarios = inventarios.filter(
            Q(nombre__icontains=q) |
            Q(observacion__icontains=q) |
            Q(sucursal__nombre__icontains=q) |
            Q(sucursal__codigo__icontains=q)
        )

    return render(request, "inventario/fisico/lista.html", {
        "inventarios": inventarios[:80],
        "sucursales": sucursales,
        "sucursal_activa": sucursal_activa,
        "puede_cambiar_sucursal": usuario_puede_cambiar_sucursal(request),
        "estado": estado,
        "q": q,
        "sucursal_id": sucursal_id,
        "estados": InventarioFisico.ESTADO_CHOICES,
    })


@login_required
def inventario_fisico_crear(request):
    sucursal_activa = obtener_sucursal_activa(request)

    sucursales = (
        Sucursal.objects.filter(activa=True).order_by("nombre")
        if usuario_puede_cambiar_sucursal(request)
        else []
    )

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        observacion = request.POST.get("observacion", "").strip()

        if usuario_puede_cambiar_sucursal(request):
            sucursal_id = request.POST.get("sucursal")
            sucursal = get_object_or_404(Sucursal, id=sucursal_id, activa=True)
        else:
            sucursal = sucursal_activa

        try:
            inventario = InventarioFisico.objects.create(
                nombre=nombre,
                sucursal=sucursal,
                estado="borrador",
                observacion=observacion or None,
            )

            messages.success(request, "Inventario físico creado correctamente.")
            return redirect("inventario_fisico_detalle", inventario_id=inventario.id)

        except ValidationError as e:
            messages.error(request, e)

        except Exception as e:
            messages.error(request, f"No se pudo crear el inventario físico: {e}")

    return render(request, "inventario/fisico/form_crear.html", {
        "sucursales": sucursales,
        "sucursal_activa": sucursal_activa,
        "puede_cambiar_sucursal": usuario_puede_cambiar_sucursal(request),
    })


@login_required
def inventario_fisico_detalle(request, inventario_id):
    inventario = get_object_or_404(
        InventarioFisico.objects.select_related("sucursal"),
        id=inventario_id,
    )

    q = request.GET.get("q", "").strip()
    diferencia = request.GET.get("diferencia", "").strip()
    categoria_id = request.GET.get("categoria", "").strip()
    marca_id = request.GET.get("marca", "").strip()

    detalles = (
        inventario.detalles
        .select_related(
            "codigo_producto",
            "codigo_producto__producto",
            "codigo_producto__producto__categoria",
            "codigo_producto__marca",
        )
        .order_by("codigo_producto__producto__nombre_base", "codigo_producto__codigo")
    )

    if q:
        detalles = detalles.filter(
            Q(codigo_producto__codigo__icontains=q) |
            Q(codigo_producto__codigo_normalizado__icontains=q) |
            Q(codigo_producto__codigo_barras__icontains=q) |
            Q(codigo_producto__nombre_comercial__icontains=q) |
            Q(codigo_producto__producto__sku_interno__icontains=q) |
            Q(codigo_producto__producto__nombre_base__icontains=q) |
            Q(codigo_producto__marca__nombre__icontains=q)
        )

    if categoria_id:
        detalles = detalles.filter(codigo_producto__producto__categoria_id=categoria_id)

    if marca_id:
        detalles = detalles.filter(codigo_producto__marca_id=marca_id)

    if diferencia == "sobrante":
        detalles = detalles.filter(diferencia__gt=0)
    elif diferencia == "faltante":
        detalles = detalles.filter(diferencia__lt=0)
    elif diferencia == "sin_diferencia":
        detalles = detalles.filter(diferencia=0)

    resumen = inventario.detalles.aggregate(
        total_sistema=Sum("stock_sistema"),
        total_contado=Sum("cantidad_contada"),
        total_diferencia=Sum("diferencia"),
    )

    categorias = Categoria.objects.all().order_by("nombre")
    marcas = MarcaRepuesto.objects.all().order_by("nombre")

    return render(request, "inventario/fisico/detalle.html", {
        "inventario": inventario,
        "detalles": detalles[:150],
        "q": q,
        "diferencia": diferencia,
        "categoria_id": categoria_id,
        "marca_id": marca_id,
        "categorias": categorias,
        "marcas": marcas,
        "total_sistema": resumen["total_sistema"] or Decimal("0.00"),
        "total_contado": resumen["total_contado"] or Decimal("0.00"),
        "total_diferencia": resumen["total_diferencia"] or Decimal("0.00"),
    })


@login_required
def inventario_fisico_generar_detalles(request, inventario_id):
    inventario = get_object_or_404(
        InventarioFisico.objects.select_related("sucursal"),
        id=inventario_id,
    )

    if request.method != "POST":
        return redirect("inventario_fisico_detalle", inventario_id=inventario.id)

    if inventario.estado not in ["borrador", "en_proceso"]:
        messages.error(request, "Solo se pueden generar detalles en inventarios abiertos.")
        return redirect("inventario_fisico_detalle", inventario_id=inventario.id)

    if not inventario.sucursal_id:
        messages.error(request, "El inventario físico debe tener una sucursal.")
        return redirect("inventario_fisico_detalle", inventario_id=inventario.id)

    stocks = (
        StockSucursal.objects
        .filter(sucursal=inventario.sucursal)
        .select_related("codigo_producto")
    )

    creados = 0

    with transaction.atomic():
        for stock in stocks:
            _, creado = DetalleInventarioFisico.objects.get_or_create(
                inventario=inventario,
                codigo_producto=stock.codigo_producto,
                defaults={
                    "stock_sistema": stock.cantidad,
                    "cantidad_contada": Decimal("0.00"),
                    "diferencia": Decimal("0.00") - stock.cantidad,
                },
            )

            if creado:
                creados += 1

        if inventario.estado == "borrador":
            inventario.estado = "en_proceso"
            inventario.save(update_fields=["estado"])

    messages.success(request, f"Se generaron {creados} líneas para conteo.")
    return redirect("inventario_fisico_detalle", inventario_id=inventario.id)


@login_required
def inventario_fisico_agregar_linea(request, inventario_id):
    inventario = get_object_or_404(
        InventarioFisico.objects.select_related("sucursal"),
        id=inventario_id,
    )

    if request.method == "POST":
        codigo_txt = request.POST.get("codigo", "").strip()
        cantidad_contada = request.POST.get("cantidad_contada", "0").strip()
        observacion = request.POST.get("observacion", "").strip()

        if inventario.estado not in ["borrador", "en_proceso"]:
            messages.error(request, "No se pueden agregar líneas a un inventario cerrado.")
            return redirect("inventario_fisico_detalle", inventario_id=inventario.id)

        codigo = (
            CodigoProducto.objects
            .select_related("producto", "marca")
            .filter(
                Q(codigo__iexact=codigo_txt) |
                Q(codigo_normalizado__iexact=CodigoProducto.normalizar_codigo(codigo_txt)) |
                Q(codigo_barras__iexact=codigo_txt)
            )
            .first()
        )

        if not codigo:
            messages.error(request, "No se encontró un producto con ese código o código de barras.")
            return redirect("inventario_fisico_detalle", inventario_id=inventario.id)

        stock = StockSucursal.objects.filter(
            codigo_producto=codigo,
            sucursal=inventario.sucursal,
        ).first()

        stock_sistema = stock.cantidad if stock else Decimal("0.00")

        try:
            detalle, _ = DetalleInventarioFisico.objects.get_or_create(
                inventario=inventario,
                codigo_producto=codigo,
                defaults={
                    "stock_sistema": stock_sistema,
                    "cantidad_contada": Decimal("0.00"),
                },
            )

            detalle.cantidad_contada = Decimal(cantidad_contada)
            detalle.escaneado_por_barcode = codigo.codigo_barras == codigo_txt
            detalle.observacion = observacion or None
            detalle.save()

            if inventario.estado == "borrador":
                inventario.estado = "en_proceso"
                inventario.save(update_fields=["estado"])

            messages.success(request, "Línea de inventario actualizada.")

        except Exception as e:
            messages.error(request, f"No se pudo agregar la línea: {e}")

    return redirect("inventario_fisico_detalle", inventario_id=inventario.id)


@login_required
def inventario_fisico_actualizar_conteo(request, detalle_id):
    detalle = get_object_or_404(
        DetalleInventarioFisico.objects.select_related(
            "inventario",
            "codigo_producto",
        ),
        id=detalle_id,
    )

    inventario = detalle.inventario

    if request.method == "POST":
        if inventario.estado not in ["borrador", "en_proceso"]:
            messages.error(request, "No se puede modificar un inventario cerrado.")
            return redirect("inventario_fisico_detalle", inventario_id=inventario.id)

        cantidad_contada = request.POST.get("cantidad_contada", "").strip()
        observacion = request.POST.get("observacion", "").strip()

        try:
            detalle.cantidad_contada = Decimal(cantidad_contada or "0")
            detalle.observacion = observacion or None
            detalle.save()

            if inventario.estado == "borrador":
                inventario.estado = "en_proceso"
                inventario.save(update_fields=["estado"])

            messages.success(request, "Conteo actualizado.")

        except Exception as e:
            messages.error(request, f"No se pudo actualizar el conteo: {e}")

    return redirect("inventario_fisico_detalle", inventario_id=inventario.id)


@login_required
def inventario_fisico_cerrar(request, inventario_id):
    inventario = get_object_or_404(InventarioFisico, id=inventario_id)

    if request.method == "POST":
        if inventario.estado not in ["borrador", "en_proceso"]:
            messages.error(request, "Este inventario ya está cerrado o aplicado.")
            return redirect("inventario_fisico_detalle", inventario_id=inventario.id)

        inventario.estado = "cerrado"
        inventario.fecha_cierre = timezone.now()
        inventario.save(update_fields=["estado", "fecha_cierre"])

        messages.success(request, "Inventario físico cerrado. Revise diferencias antes de aplicar ajustes.")

    return redirect("inventario_fisico_detalle", inventario_id=inventario.id)


@login_required
def inventario_fisico_aplicar_ajustes(request, inventario_id):
    inventario = get_object_or_404(
        InventarioFisico.objects.select_related("sucursal"),
        id=inventario_id,
    )

    if request.method != "POST":
        return redirect("inventario_fisico_detalle", inventario_id=inventario.id)

    if inventario.estado != "cerrado":
        messages.error(request, "Solo se pueden aplicar ajustes desde un inventario cerrado.")
        return redirect("inventario_fisico_detalle", inventario_id=inventario.id)

    detalles_con_diferencia = inventario.detalles.exclude(diferencia=0)

    aplicados = 0

    with transaction.atomic():
        for detalle in detalles_con_diferencia.select_related("codigo_producto"):
            MovimientoStock.objects.create(
                codigo_producto=detalle.codigo_producto,
                sucursal=inventario.sucursal,
                tipo_movimiento="ajuste",
                cantidad=detalle.cantidad_contada,
                referencia=f"Inventario físico: {inventario.nombre}",
                observacion=detalle.observacion or "Ajuste por conteo físico.",
            )
            aplicados += 1

        inventario.estado = "aplicado"
        inventario.save(update_fields=["estado"])

    messages.success(request, f"Inventario aplicado. Ajustes generados: {aplicados}.")
    return redirect("inventario_fisico_detalle", inventario_id=inventario.id)