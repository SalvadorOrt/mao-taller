'''
listar productos
buscar por código, marca, nombre, SKU, código de barras
crear producto
editar producto
ver detalle del producto
crear códigos/equivalencias
editar precios
activar/desactivar producto
'''

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum, Prefetch
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation
from django.db import transaction
from ..models import (
    Categoria,
    MarcaRepuesto,
    Producto,
    CodigoProducto,
    StockSucursal,
    ImagenProducto,
)
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction

from inventario.forms import ProductoForm, CodigoProductoFormSet
from inventario.models import CodigoProducto, ImagenProducto

def precio_secreto(precio):
    if precio is None:
        return "---"

    clave = {
        "1": "M",
        "2": "E",
        "3": "C",
        "4": "A",
        "5": "N",
        "6": "I",
        "7": "O",
        "8": "R",
        "9": "T",
        "0": "S",
        ".": ".",
    }

    texto = f"{precio:.2f}"
    return "".join(clave.get(c, c) for c in texto)


@login_required
def catalogo_lista(request):
    LIMITE_RESULTADOS = 80

    q = request.GET.get("q", "").strip()
    categoria_id = request.GET.get("categoria", "").strip()
    marca_id = request.GET.get("marca", "").strip()
    estado = request.GET.get("estado", "").strip()

    codigos = (
        CodigoProducto.objects
        .select_related(
            "producto",
            "producto__categoria",
            "marca",
        )
        .prefetch_related(
            "stocks_por_sucursal",
            "stocks_por_sucursal__sucursal",
        )
        .order_by("producto__nombre_base", "marca__nombre", "codigo")
    )

    if q:
        codigos = codigos.filter(
            Q(codigo__icontains=q) |
            Q(codigo_normalizado__icontains=q) |
            Q(codigo_barras__icontains=q) |
            Q(nombre_comercial__icontains=q) |
            Q(producto__sku_interno__icontains=q) |
            Q(producto__nombre_base__icontains=q) |
            Q(producto__descripcion__icontains=q) |
            Q(marca__nombre__icontains=q) |
            Q(producto__categoria__nombre__icontains=q)
        )

    if categoria_id:
        codigos = codigos.filter(producto__categoria_id=categoria_id)

    if marca_id:
        codigos = codigos.filter(marca_id=marca_id)

    if estado == "activos":
        codigos = codigos.filter(activo=True, producto__activo=True)

    elif estado == "inactivos":
        codigos = codigos.filter(Q(activo=False) | Q(producto__activo=False))

    elif estado == "sin_precio":
        codigos = codigos.filter(Q(precio_venta__isnull=True) | Q(precio_venta=0))

    total_filtrado = codigos.count()
    codigos = codigos[:LIMITE_RESULTADOS]

    filas = []

    for codigo in codigos:
        stock_total = sum(
            stock.cantidad for stock in codigo.stocks_por_sucursal.all()
        )

        equivalencias = (
            codigo.producto.codigos
            .exclude(id=codigo.id)
            .select_related("marca")
            .order_by("marca__nombre", "codigo")[:5]
        )

        filas.append({
            "codigo": codigo,
            "producto": codigo.producto,
            "categoria": codigo.producto.categoria,
            "marca": codigo.marca,
            "stock_total": stock_total,
            "precio_secreto": precio_secreto(codigo.precio_venta),
            "equivalencias": equivalencias,
        })

    categorias = Categoria.objects.all().order_by("nombre")
    marcas = MarcaRepuesto.objects.all().order_by("nombre")

    return render(request, "inventario/catalogo/lista.html", {
        "filas": filas,
        "categorias": categorias,
        "marcas": marcas,
        "q": q,
        "categoria_id": categoria_id,
        "marca_id": marca_id,
        "estado": estado,
        "total_filtrado": total_filtrado,
        "limite_resultados": LIMITE_RESULTADOS,
    })


@login_required
def catalogo_detalle(request, codigo_id):
    codigo = get_object_or_404(
        CodigoProducto.objects.select_related(
            "producto",
            "producto__categoria",
            "marca",
        ),
        id=codigo_id,
    )

    producto = codigo.producto

    codigos_equivalentes = (
        producto.codigos
        .select_related("marca")
        .order_by("marca__nombre", "codigo")
    )

    stocks = (
        StockSucursal.objects
        .filter(codigo_producto=codigo)
        .select_related("sucursal")
        .order_by("sucursal__nombre")
    )

    movimientos = (
        codigo.movimientos
        .select_related("sucursal")
        .order_by("-fecha")[:20]
    )

    return render(request, "inventario/catalogo/detalle.html", {
        "codigo": codigo,
        "producto": producto,
        "codigos_equivalentes": codigos_equivalentes,
        "stocks": stocks,
        "movimientos": movimientos,
        "precio_secreto": precio_secreto(codigo.precio_venta),
    })




@login_required
@transaction.atomic
def catalogo_crear(request):

    if request.method == "POST":

        producto_form = ProductoForm(request.POST)

        codigo_formset = CodigoProductoFormSet(
            request.POST,
            request.FILES,
            queryset=CodigoProducto.objects.none(),
            prefix="codigos"
        )

        if producto_form.is_valid() and codigo_formset.is_valid():

            producto = producto_form.save(commit=False)

            # SKU automático: NO se asigna aquí.
            # Origen formal de bodega.
            producto.origen = "BODEGA"

            producto.save()

            codigos_creados = []

            for index, codigo_form in enumerate(codigo_formset):

                if not codigo_form.cleaned_data:
                    continue

                if codigo_form.cleaned_data.get("DELETE"):
                    continue

                codigo = codigo_form.save(commit=False)
                codigo.producto = producto
                codigo.save()

                codigos_creados.append(codigo)

                imagenes = request.FILES.getlist(
                    f"imagenes_codigo_{index}"
                )

                for imagen in imagenes:
                    ImagenProducto.objects.create(
                        codigo_producto=codigo,
                        imagen=imagen,
                        descripcion=f"Imagen de {codigo.codigo}",
                    )

            if not codigos_creados:
                messages.error(
                    request,
                    "Debe agregar al menos un código comercial."
                )
                raise ValueError("Debe agregar al menos un código comercial.")

            messages.success(
                request,
                "Producto creado correctamente."
            )

            return redirect(
                "inventario_catalogo_detalle",
                codigo_id=codigos_creados[0].id
            )

        messages.error(
            request,
            "Revise los datos ingresados."
        )

    else:
        producto_form = ProductoForm()

        codigo_formset = CodigoProductoFormSet(
            queryset=CodigoProducto.objects.none(),
            prefix="codigos"
        )

    return render(
        request,
        "inventario/catalogo_crear.html",
        {
            "producto_form": producto_form,
            "codigo_formset": codigo_formset,
        }
    )
@login_required
def catalogo_editar_codigo(request, codigo_id):
    codigo = get_object_or_404(
        CodigoProducto.objects.select_related(
            "producto",
            "producto__categoria",
            "marca",
        ),
        id=codigo_id,
    )

    categorias = Categoria.objects.all().order_by("nombre")
    marcas = MarcaRepuesto.objects.all().order_by("nombre")

    if request.method == "POST":
        try:
            producto = codigo.producto

            producto.categoria_id = request.POST.get("categoria")
            producto.nombre_base = request.POST.get("nombre_base", "").strip()
            producto.descripcion = request.POST.get("descripcion", "").strip()
            producto.activo = request.POST.get("producto_activo") == "on"
            producto.descontinuado = request.POST.get("descontinuado") == "on"
            producto.save()

            codigo.marca_id = request.POST.get("marca")
            codigo.codigo = request.POST.get("codigo", "").strip()
            codigo.codigo_barras = request.POST.get("codigo_barras", "").strip() or None
            codigo.nombre_comercial = request.POST.get("nombre_comercial", "").strip() or None
            codigo.tipo_codigo = request.POST.get("tipo_codigo", "aftermarket")
            codigo.activo = request.POST.get("codigo_activo") == "on"

            precio_compra = request.POST.get("precio_compra", "").strip()
            precio_venta = request.POST.get("precio_venta", "").strip()
            margen = request.POST.get("margen_ganancia_porcentaje", "").strip()

            codigo.precio_compra = Decimal(precio_compra) if precio_compra else None
            codigo.precio_venta = Decimal(precio_venta) if precio_venta else None
            codigo.margen_ganancia_porcentaje = Decimal(margen) if margen else Decimal("100.00")

            codigo.save()

            messages.success(request, "Producto actualizado correctamente.")
            return redirect("inventario_catalogo_detalle", codigo_id=codigo.id)

        except ValidationError as e:
            messages.error(request, e)

        except Exception as e:
            messages.error(request, f"No se pudo actualizar el producto: {e}")

    return render(request, "inventario/catalogo/form_editar.html", {
        "codigo": codigo,
        "producto": codigo.producto,
        "categorias": categorias,
        "marcas": marcas,
        "tipos_codigo": CodigoProducto.TIPO_CODIGO_CHOICES,
    })


@login_required
def catalogo_crear_codigo_equivalente(request, producto_id):
    producto = get_object_or_404(
        Producto.objects.select_related("categoria"),
        id=producto_id,
    )

    marcas = MarcaRepuesto.objects.all().order_by("nombre")

    if request.method == "POST":
        try:
            marca = get_object_or_404(MarcaRepuesto, id=request.POST.get("marca"))

            codigo = CodigoProducto.objects.create(
                producto=producto,
                marca=marca,
                codigo=request.POST.get("codigo", "").strip(),
                codigo_barras=request.POST.get("codigo_barras", "").strip() or None,
                nombre_comercial=request.POST.get("nombre_comercial", "").strip() or None,
                tipo_codigo=request.POST.get("tipo_codigo", "aftermarket"),
                precio_compra=Decimal(request.POST.get("precio_compra")) if request.POST.get("precio_compra") else None,
                precio_venta=Decimal(request.POST.get("precio_venta")) if request.POST.get("precio_venta") else None,
                activo=True,
            )

            messages.success(request, "Código equivalente agregado correctamente.")
            return redirect("inventario_catalogo_detalle", codigo_id=codigo.id)

        except ValidationError as e:
            messages.error(request, e)

        except Exception as e:
            messages.error(request, f"No se pudo crear el código equivalente: {e}")

    return render(request, "inventario/catalogo/form_codigo_equivalente.html", {
        "producto": producto,
        "marcas": marcas,
        "tipos_codigo": CodigoProducto.TIPO_CODIGO_CHOICES,
    })


@login_required
def catalogo_toggle_codigo(request, codigo_id):
    codigo = get_object_or_404(CodigoProducto, id=codigo_id)

    if request.method == "POST":
        codigo.activo = not codigo.activo
        codigo.save(update_fields=["activo", "actualizado_en"])

        if codigo.activo:
            messages.success(request, "Código activado.")
        else:
            messages.warning(request, "Código desactivado.")

    return redirect("inventario_catalogo_detalle", codigo_id=codigo.id)