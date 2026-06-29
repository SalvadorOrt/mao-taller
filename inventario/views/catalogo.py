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
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404

from inventario.forms import (
    ProductoForm,
    CodigoProductoFormSet,
    ValorAtributoProductoFormSet,
)

from inventario.models import (
    Categoria,
    MarcaRepuesto,
    Producto,
    CodigoProducto,
    StockSucursal,
    ImagenProducto,
    ValorAtributoProducto,
)
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404

from inventario.forms import (
    ProductoForm,
    CodigoProductoFormSet,
    ValorAtributoProductoFormSet,
)

from inventario.models import (
    Categoria,
    MarcaRepuesto,
    Producto,
    CodigoProducto,
    StockSucursal,
    ImagenProducto,
    ValorAtributoProducto,
)


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
            "imagenes",
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
            Q(producto__categoria__nombre__icontains=q) |
            Q(producto__valores_atributos__valor__icontains=q) |
            Q(producto__valores_atributos__atributo__nombre__icontains=q)
        ).distinct()

    if categoria_id:
        codigos = codigos.filter(producto__categoria_id=categoria_id)

    if marca_id:
        codigos = codigos.filter(marca_id=marca_id)

    if estado == "activos":
        codigos = codigos.filter(activo=True, producto__activo=True)

    elif estado == "inactivos":
        codigos = codigos.filter(
            Q(activo=False) |
            Q(producto__activo=False)
        )

    elif estado == "sin_precio":
        codigos = codigos.filter(
            Q(precio_venta__isnull=True) |
            Q(precio_venta=0)
        )

    total_filtrado = codigos.count()
    codigos = codigos[:LIMITE_RESULTADOS]

    filas = []

    for codigo in codigos:
        stock_total = sum(
            stock.cantidad
            for stock in codigo.stocks_por_sucursal.all()
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
            "precio_secreto": codigo.precio_secreto,
            "equivalencias": equivalencias,
            "total_imagenes": codigo.imagenes.count(),
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
        CodigoProducto.objects
        .select_related(
            "producto",
            "producto__categoria",
            "marca",
        )
        .prefetch_related(
            "imagenes",
            "producto__codigos",
            "producto__codigos__marca",
            "producto__valores_atributos",
            "producto__valores_atributos__atributo",
        ),
        id=codigo_id,
    )

    producto = codigo.producto

    codigos_equivalentes = (
        producto.codigos
        .select_related("marca")
        .prefetch_related("imagenes")
        .order_by("marca__nombre", "codigo")
    )

    atributos = (
        producto.valores_atributos
        .select_related("atributo")
        .order_by("atributo__nombre")
    )

    imagenes = codigo.imagenes.all().order_by("id")

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
        "atributos": atributos,
        "imagenes": imagenes,
        "stocks": stocks,
        "movimientos": movimientos,
        "precio_secreto": codigo.precio_secreto,
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
            prefix="codigos",
        )

        atributo_formset = ValorAtributoProductoFormSet(
            request.POST,
            queryset=ValorAtributoProducto.objects.none(),
            prefix="atributos",
        )

        if (
            producto_form.is_valid()
            and codigo_formset.is_valid()
            and atributo_formset.is_valid()
        ):
            producto = producto_form.save(commit=False)
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

            for atributo_form in atributo_formset:
                if not atributo_form.cleaned_data:
                    continue

                if atributo_form.cleaned_data.get("DELETE"):
                    continue

                atributo_valor = atributo_form.save(commit=False)
                atributo_valor.producto = producto
                atributo_valor.save()

            if not codigos_creados:
                messages.error(
                    request,
                    "Debe agregar al menos un código comercial."
                )
                raise ValidationError(
                    "Debe agregar al menos un código comercial."
                )

            messages.success(
                request,
                "Producto creado correctamente."
            )

            return redirect(
                "inventario_catalogo_detalle",
                codigo_id=codigos_creados[0].id,
            )

        messages.error(
            request,
            "Revise los datos ingresados."
        )

    else:
        producto_form = ProductoForm()

        codigo_formset = CodigoProductoFormSet(
            queryset=CodigoProducto.objects.none(),
            prefix="codigos",
        )

        atributo_formset = ValorAtributoProductoFormSet(
            queryset=ValorAtributoProducto.objects.none(),
            prefix="atributos",
        )

    return render(request,"catalogo/crear.html", {
        "producto_form": producto_form,
        "codigo_formset": codigo_formset,
        "atributo_formset": atributo_formset,
    })


@login_required
@transaction.atomic
def catalogo_editar_codigo(request, codigo_id):
    codigo = get_object_or_404(
        CodigoProducto.objects.select_related(
            "producto",
            "producto__categoria",
            "marca",
        ),
        id=codigo_id,
    )

    producto = codigo.producto

    if request.method == "POST":
        try:
            producto_form = ProductoForm(
                request.POST,
                instance=producto,
            )

            codigo_formset = CodigoProductoFormSet(
                request.POST,
                request.FILES,
                queryset=producto.codigos.all().order_by("id"),
                prefix="codigos",
            )

            atributo_formset = ValorAtributoProductoFormSet(
                request.POST,
                queryset=producto.valores_atributos.all().order_by("id"),
                prefix="atributos",
            )

            if (
                producto_form.is_valid()
                and codigo_formset.is_valid()
                and atributo_formset.is_valid()
            ):
                producto = producto_form.save(commit=False)
                producto.origen = producto.origen or "BODEGA"
                producto.save()

                codigos_guardados = []

                for index, codigo_form in enumerate(codigo_formset):
                    if not codigo_form.cleaned_data:
                        continue

                    if codigo_form.cleaned_data.get("DELETE"):
                        if codigo_form.instance.pk:
                            codigo_form.instance.delete()
                        continue

                    codigo_obj = codigo_form.save(commit=False)
                    codigo_obj.producto = producto
                    codigo_obj.save()

                    codigos_guardados.append(codigo_obj)

                    imagenes = request.FILES.getlist(
                        f"imagenes_codigo_{index}"
                    )

                    for imagen in imagenes:
                        ImagenProducto.objects.create(
                            codigo_producto=codigo_obj,
                            imagen=imagen,
                            descripcion=f"Imagen de {codigo_obj.codigo}",
                        )

                for atributo_form in atributo_formset:
                    if not atributo_form.cleaned_data:
                        continue

                    if atributo_form.cleaned_data.get("DELETE"):
                        if atributo_form.instance.pk:
                            atributo_form.instance.delete()
                        continue

                    atributo_valor = atributo_form.save(commit=False)
                    atributo_valor.producto = producto
                    atributo_valor.save()

                codigo_destino = (
                    codigos_guardados[0]
                    if codigos_guardados
                    else producto.codigo_principal()
                )

                if not codigo_destino:
                    messages.error(
                        request,
                        "El producto debe tener al menos un código comercial."
                    )
                    raise ValidationError(
                        "El producto debe tener al menos un código comercial."
                    )

                messages.success(
                    request,
                    "Producto actualizado correctamente."
                )

                return redirect(
                    "inventario_catalogo_detalle",
                    codigo_id=codigo_destino.id,
                )

            messages.error(
                request,
                "Revise los datos ingresados."
            )

        except ValidationError as e:
            messages.error(request, e)

        except Exception as e:
            messages.error(
                request,
                f"No se pudo actualizar el producto: {e}"
            )

    else:
        producto_form = ProductoForm(instance=producto)

        codigo_formset = CodigoProductoFormSet(
            queryset=producto.codigos.all().order_by("id"),
            prefix="codigos",
        )

        atributo_formset = ValorAtributoProductoFormSet(
            queryset=producto.valores_atributos.all().order_by("id"),
            prefix="atributos",
        )

    return render(request, "inventario/catalogo/form_editar.html", {
        "codigo": codigo,
        "producto": producto,
        "producto_form": producto_form,
        "codigo_formset": codigo_formset,
        "atributo_formset": atributo_formset,
    })


@login_required
@transaction.atomic
def catalogo_crear_codigo_equivalente(request, producto_id):
    producto = get_object_or_404(
        Producto.objects.select_related("categoria"),
        id=producto_id,
    )

    if request.method == "POST":
        codigo_formset = CodigoProductoFormSet(
            request.POST,
            request.FILES,
            queryset=CodigoProducto.objects.none(),
            prefix="codigos",
        )

        if codigo_formset.is_valid():
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
                raise ValidationError(
                    "Debe agregar al menos un código comercial."
                )

            messages.success(
                request,
                "Código equivalente agregado correctamente."
            )

            return redirect(
                "inventario_catalogo_detalle",
                codigo_id=codigos_creados[0].id,
            )

        messages.error(
            request,
            "Revise los datos ingresados."
        )

    else:
        codigo_formset = CodigoProductoFormSet(
            queryset=CodigoProducto.objects.none(),
            prefix="codigos",
        )

    return render(request, "inventario/catalogo/form_codigo_equivalente.html", {
        "producto": producto,
        "codigo_formset": codigo_formset,
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

    return redirect(
        "inventario_catalogo_detalle",
        codigo_id=codigo.id,
    )