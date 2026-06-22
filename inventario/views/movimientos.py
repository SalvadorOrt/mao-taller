'''
movimientos.py

Aquí se manejan entradas, salidas y ajustes manuales.

Debe permitir:

listar movimientos
crear entrada manual
crear salida manual
crear ajuste
ver historial por producto
ver historial por sucursal

Modelo principal:

MovimientoStock

Ojo: no debería permitir editar ni borrar movimientos.
'''

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import render, redirect, get_object_or_404

from ordenes_de_trabajo.models import Sucursal
from ordenes_de_trabajo.views.utils import (
    obtener_sucursal_activa,
    usuario_puede_cambiar_sucursal,
)

from ..models import (
    MovimientoStock,
    CodigoProducto,
    Categoria,
    MarcaRepuesto,
)

@login_required
def movimiento_lista(request):
    LIMITE_RESULTADOS = 100

    movimientos = (
        MovimientoStock.objects
        .select_related(
            "sucursal",
            "codigo_producto",
            "codigo_producto__producto",
            "codigo_producto__producto__categoria",
            "codigo_producto__marca",
        )
        .order_by("-fecha")
    )

    q = request.GET.get("q", "").strip()
    tipo = request.GET.get("tipo", "").strip()
    sucursal_id = request.GET.get("sucursal", "").strip()

    if q:
        movimientos = movimientos.filter(
            Q(codigo_producto__codigo__icontains=q) |
            Q(codigo_producto__codigo_barras__icontains=q) |
            Q(codigo_producto__producto__nombre_base__icontains=q) |
            Q(codigo_producto__marca__nombre__icontains=q) |
            Q(referencia__icontains=q)
        )

    if tipo:
        movimientos = movimientos.filter(tipo_movimiento=tipo)

    if sucursal_id:
        movimientos = movimientos.filter(sucursal_id=sucursal_id)

    sucursales = Sucursal.objects.filter(activa=True).order_by("nombre")

    return render(request, "inventario/movimientos/lista.html", {
        "movimientos": movimientos[:LIMITE_RESULTADOS],
        "sucursales": sucursales,
        "tipo": tipo,
        "q": q,
        "sucursal_id": sucursal_id,
        "tipos": MovimientoStock.TIPO_MOVIMIENTO_CHOICES,
    })

@login_required
def movimiento_crear(request):
    sucursal_activa = obtener_sucursal_activa(request)

    if request.method == "POST":
        try:
            codigo_id = request.POST.get("codigo_producto")
            sucursal_id = request.POST.get("sucursal")

            movimiento = MovimientoStock.objects.create(
                codigo_producto_id=codigo_id,
                sucursal_id=sucursal_id,
                tipo_movimiento=request.POST.get("tipo_movimiento"),
                cantidad=Decimal(request.POST.get("cantidad")),
                precio_unitario=(
                    Decimal(request.POST.get("precio_unitario"))
                    if request.POST.get("precio_unitario")
                    else None
                ),
                referencia=request.POST.get("referencia") or None,
                observacion=request.POST.get("observacion") or None,
            )

            messages.success(request, "Movimiento registrado correctamente.")
            return redirect("inventario_movimiento_detalle", movimiento.id)

        except Exception as e:
            messages.error(request, str(e))

    sucursales = Sucursal.objects.filter(activa=True).order_by("nombre")

    return render(request, "inventario/movimientos/form.html", {
        "sucursales": sucursales,
        "sucursal_activa": sucursal_activa,
        "tipos": MovimientoStock.TIPO_MOVIMIENTO_CHOICES,
    })


@login_required
def movimiento_detalle(request, movimiento_id):
    movimiento = get_object_or_404(
        MovimientoStock.objects.select_related(
            "sucursal",
            "codigo_producto",
            "codigo_producto__producto",
            "codigo_producto__marca",
        ),
        id=movimiento_id,
    )

    return render(request, "inventario/movimientos/detalle.html", {
        "movimiento": movimiento,
    })


@login_required
def movimiento_historial_producto(request, codigo_id):
    codigo = get_object_or_404(
        CodigoProducto.objects.select_related(
            "producto",
            "marca",
        ),
        id=codigo_id,
    )

    movimientos = (
        codigo.movimientos
        .select_related("sucursal")
        .order_by("-fecha")
    )

    entradas = movimientos.filter(
        tipo_movimiento="entrada"
    ).aggregate(
        total=Sum("cantidad")
    )["total"] or Decimal("0")

    salidas = movimientos.filter(
        tipo_movimiento="salida"
    ).aggregate(
        total=Sum("cantidad")
    )["total"] or Decimal("0")

    return render(request, "inventario/movimientos/historial_producto.html", {
        "codigo": codigo,
        "movimientos": movimientos,
        "total_entradas": entradas,
        "total_salidas": salidas,
    })


@login_required
def movimiento_entrada_rapida(request, codigo_id):
    codigo = get_object_or_404(CodigoProducto, id=codigo_id)

    if request.method == "POST":
        try:
            MovimientoStock.objects.create(
                codigo_producto=codigo,
                sucursal_id=request.POST.get("sucursal"),
                tipo_movimiento="entrada",
                cantidad=Decimal(request.POST.get("cantidad")),
                referencia=request.POST.get("referencia") or "Entrada manual",
            )

            messages.success(request, "Entrada registrada.")
            return redirect(
                "inventario_historial_producto",
                codigo_id=codigo.id
            )

        except Exception as e:
            messages.error(request, str(e))

    sucursales = Sucursal.objects.filter(activa=True)

    return render(request, "inventario/movimientos/entrada.html", {
        "codigo": codigo,
        "sucursales": sucursales,
    })

@login_required
def movimiento_salida_rapida(request, codigo_id):
    codigo = get_object_or_404(CodigoProducto, id=codigo_id)

    if request.method == "POST":
        try:
            MovimientoStock.objects.create(
                codigo_producto=codigo,
                sucursal_id=request.POST.get("sucursal"),
                tipo_movimiento="salida",
                cantidad=Decimal(request.POST.get("cantidad")),
                referencia=request.POST.get("referencia") or "Salida manual",
            )

            messages.success(request, "Salida registrada.")
            return redirect(
                "inventario_historial_producto",
                codigo_id=codigo.id
            )

        except Exception as e:
            messages.error(request, str(e))

    sucursales = Sucursal.objects.filter(activa=True)

    return render(request, "inventario/movimientos/salida.html", {
        "codigo": codigo,
        "sucursales": sucursales,
    })