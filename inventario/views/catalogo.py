from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from inventario.forms import (
    CodigoProductoFormSet,
    ProductoForm,
    ValorAtributoProductoFormSet,
)
from inventario.models import (
    Atributo,
    Categoria,
    CategoriaAtributo,
    CodigoProducto,
    ImagenProducto,
    MarcaRepuesto,
    Producto,
    StockSucursal,
    ValorAtributoProducto,
)
from inventario.services.creacion_producto import CreacionProductoService
from inventario.services.sugerencias import MotorSugerenciasProducto


# =========================================================
# LISTADO
# =========================================================

@login_required
def catalogo_lista(request):
    LIMITE_RESULTADOS = 80

    q = request.GET.get("q", "").strip()
    categoria_id = request.GET.get("categoria", "").strip()
    marca_id = request.GET.get("marca", "").strip()
    estado = request.GET.get("estado", "").strip()

    codigos = (
        CodigoProducto.objects
        .select_related("producto", "producto__categoria", "marca")
        .prefetch_related(
            "stocks_por_sucursal",
            "stocks_por_sucursal__sucursal",
            "producto__imagenes",
        )
        .order_by("producto__nombre_base", "marca__nombre", "codigo")
    )

    if q:
        codigos = codigos.filter(
            Q(codigo__icontains=q)
            | Q(codigo_normalizado__icontains=q)
            | Q(codigo_barras__icontains=q)
            | Q(nombre_comercial__icontains=q)
            | Q(producto__sku_interno__icontains=q)
            | Q(producto__nombre_base__icontains=q)
            | Q(producto__descripcion__icontains=q)
            | Q(marca__nombre__icontains=q)
            | Q(producto__categoria__nombre__icontains=q)
            | Q(producto__valores_atributos__valor__icontains=q)
            | Q(producto__valores_atributos__atributo__nombre__icontains=q)
        ).distinct()

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
    filas = []

    for codigo in codigos[:LIMITE_RESULTADOS]:
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
            "total_imagenes": codigo.producto.imagenes.count(),
        })

    return render(request, "inventario/catalogo/lista.html", {
        "filas": filas,
        "categorias": Categoria.objects.all().order_by("nombre"),
        "marcas": MarcaRepuesto.objects.all().order_by("nombre"),
        "q": q,
        "categoria_id": categoria_id,
        "marca_id": marca_id,
        "estado": estado,
        "total_filtrado": total_filtrado,
        "limite_resultados": LIMITE_RESULTADOS,
    })


# =========================================================
# DETALLE
# =========================================================

@login_required
def catalogo_detalle(request, codigo_id):
    codigo = get_object_or_404(
        CodigoProducto.objects
        .select_related("producto", "producto__categoria", "marca")
        .prefetch_related(
            "producto__imagenes",
            "producto__codigos",
            "producto__codigos__marca",
            "producto__valores_atributos",
            "producto__valores_atributos__atributo",
        ),
        id=codigo_id,
    )

    producto = codigo.producto

    return render(request, "inventario/catalogo/detalle.html", {
        "codigo": codigo,
        "producto": producto,
        "codigos_equivalentes": (
            producto.codigos
            .select_related("marca")
            .order_by("marca__nombre", "codigo")
        ),
        "atributos": (
            producto.valores_atributos
            .select_related("atributo")
            .order_by("atributo__nombre")
        ),
        "imagenes": producto.imagenes.all().order_by("id"),
        "stocks": (
            StockSucursal.objects
            .filter(codigo_producto=codigo)
            .select_related("sucursal")
            .order_by("sucursal__nombre")
        ),
        "movimientos": (
            codigo.movimientos
            .select_related("sucursal")
            .order_by("-fecha")[:20]
        ),
        "precio_secreto": codigo.precio_secreto,
    })


# =========================================================
# API - MOTOR DE SUGERENCIAS
# =========================================================

@login_required
def catalogo_sugerir_producto(request):
    texto = request.GET.get("texto", "").strip()
    codigo = request.GET.get("codigo", "").strip()

    if not texto and not codigo:
        return JsonResponse({
            "texto": "",
            "codigo": "",
            "hay_codigo_exacto": False,
            "confianza": 0,
            "confianza_categoria": 0,
            "categorias": [],
            "productos": [],
        })

    try:
        motor = MotorSugerenciasProducto(
            limite_resultados=5,
            limite_candidatos=300,
            umbral_minimo=20,
        )

        resultado = motor.sugerir(
            texto=texto,
            codigo=codigo,
            origen="INDIVIDUAL",
        )

        return JsonResponse(
            motor.convertir_a_dict(resultado)
        )

    except ValidationError as error:
        return JsonResponse({
            "ok": False,
            "error": " ".join(error.messages),
        }, status=400)

    except Exception as error:
        return JsonResponse({
            "ok": False,
            "error": str(error),
        }, status=500)


# =========================================================
# API - ATRIBUTOS DE UNA CATEGORÍA
# =========================================================

@login_required
def catalogo_atributos_categoria(request, categoria_id):
    categoria = get_object_or_404(Categoria, pk=categoria_id)

    configuraciones = (
        CategoriaAtributo.objects
        .filter(categoria=categoria, activo=True)
        .select_related("atributo")
        .order_by("orden", "atributo__nombre")
    )

    return JsonResponse({
        "categoria": {
            "id": categoria.pk,
            "nombre": categoria.nombre,
        },
        "atributos": [
            {
                "id": item.atributo_id,
                "nombre": item.atributo.nombre,
                "unidad": item.atributo.unidad,
                "requerido": item.requerido,
                "orden": item.orden,
            }
            for item in configuraciones
        ],
    })


# =========================================================
# CREAR PRODUCTO
# =========================================================

@login_required
def catalogo_crear(request):
    atributos_catalogo = Atributo.objects.all().order_by("nombre", "unidad")

    if request.method == "POST":
        producto_form = ProductoForm(request.POST)

        codigo_formset = CodigoProductoFormSet(
            request.POST,
            queryset=CodigoProducto.objects.none(),
            prefix="codigos",
        )

        atributo_formset = ValorAtributoProductoFormSet(
            request.POST,
            queryset=ValorAtributoProducto.objects.none(),
            prefix="atributos",
        )

        formularios_validos = (
            producto_form.is_valid()
            and codigo_formset.is_valid()
            and atributo_formset.is_valid()
        )

        if formularios_validos:
            codigos_validos = []

            for form in codigo_formset:
                if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                    continue

                datos = form.cleaned_data

                if (
                    datos.get("codigo")
                    or datos.get("marca")
                    or datos.get("nombre_comercial")
                ):
                    codigos_validos.append(form)

            if not codigos_validos:
                messages.error(
                    request,
                    "Debe agregar al menos un código comercial.",
                )

            else:
                try:
                    with transaction.atomic():
                        datos_producto = producto_form.cleaned_data
                        primera_forma_codigo = codigos_validos[0]
                        datos_codigo = primera_forma_codigo.cleaned_data

                        # Texto que utilizará el aprendizaje.
                        # Se conserva lo escrito por el usuario.
                        texto_aprendizaje = (
                            request.POST.get("texto_aprendizaje", "").strip()
                            or datos_producto.get("descripcion")
                            or datos_codigo.get("nombre_comercial")
                            or datos_producto.get("nombre_base")
                        )

                        # =========================================
                        # PRODUCTO + PRIMER CÓDIGO + APRENDIZAJE
                        # =========================================

                        resultado = CreacionProductoService.crear_individual(
                            categoria=datos_producto["categoria"],
                            nombre_base=datos_producto["nombre_base"],
                            descripcion=datos_producto.get("descripcion"),
                            marca=datos_codigo["marca"],
                            codigo=datos_codigo["codigo"],
                            texto_original=texto_aprendizaje,
                            nombre_comercial=datos_codigo.get("nombre_comercial"),
                            tipo_codigo=datos_codigo.get("tipo_codigo") or "aftermarket",
                            codigo_barras=datos_codigo.get("codigo_barras"),
                            presentacion_cantidad=datos_codigo.get("presentacion_cantidad"),
                            presentacion_unidad=datos_codigo.get("presentacion_unidad"),
                            precio_compra=datos_codigo.get("precio_compra"),
                            precio_venta=datos_codigo.get("precio_venta"),
                            margen_ganancia_porcentaje=(
                                datos_codigo.get("margen_ganancia_porcentaje")
                                or 100
                            ),
                            porcentaje_iva_costo=(
                                datos_codigo.get("porcentaje_iva_costo")
                                or 0
                            ),
                            usuario=request.user,
                            registrar_aprendizaje=True,
                            permitir_producto_existente=False,
                            permitir_codigo_existente=False,
                        )

                        producto = resultado["producto"]
                        codigo_principal = resultado["codigo_producto"]

                        # Mantener los estados escogidos en el formulario.
                        producto.datos_incompletos = bool(
                            datos_producto.get("datos_incompletos")
                        )
                        producto.descontinuado = bool(
                            datos_producto.get("descontinuado")
                        )
                        producto.activo = bool(
                            datos_producto.get("activo")
                        )

                        if producto.descontinuado:
                            producto.activo = False

                        producto.save()

                        # Mantener estado del primer código.
                        codigo_principal.activo = bool(
                            datos_codigo.get("activo")
                        )
                        codigo_principal.save()

                        codigos_creados = [codigo_principal]

                        # =========================================
                        # CÓDIGOS ADICIONALES
                        # =========================================

                        for codigo_form in codigos_validos[1:]:
                            codigo_obj = codigo_form.save(commit=False)
                            codigo_obj.producto = producto
                            codigo_obj.save()
                            codigos_creados.append(codigo_obj)

                        # =========================================
                        # ATRIBUTOS
                        # =========================================

                        for atributo_form in atributo_formset:
                            if (
                                not atributo_form.cleaned_data
                                or atributo_form.cleaned_data.get("DELETE")
                            ):
                                continue

                            atributo = atributo_form.cleaned_data.get("atributo")
                            valor = atributo_form.cleaned_data.get("valor")

                            if not atributo and not valor:
                                continue

                            atributo_valor = atributo_form.save(commit=False)
                            atributo_valor.producto = producto
                            atributo_valor.save()

                        # =========================================
                        # IMÁGENES
                        # =========================================

                        for imagen in request.FILES.getlist("imagenes_producto"):
                            ImagenProducto.objects.create(
                                producto=producto,
                                imagen=imagen,
                                descripcion=f"Imagen de {producto.nombre_base}",
                            )

                        messages.success(
                            request,
                            "Producto creado correctamente.",
                        )

                        return redirect(
                            "inventario_catalogo_detalle",
                            codigo_id=codigos_creados[0].pk,
                        )

                except ValidationError as error:
                    messages.error(
                        request,
                        " ".join(error.messages),
                    )

                except Exception as error:
                    messages.error(
                        request,
                        f"No se pudo crear el producto: {error}",
                    )

        else:
            messages.error(
                request,
                "Revise los datos ingresados.",
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

    return render(request, "catalogo/crear.html", {
        "producto_form": producto_form,
        "codigo_formset": codigo_formset,
        "atributo_formset": atributo_formset,
        "atributos_catalogo": atributos_catalogo,
    })


# =========================================================
# EDITAR PRODUCTO / CÓDIGOS
# =========================================================

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

    producto = codigo.producto
    atributos_catalogo = Atributo.objects.all().order_by("nombre", "unidad")

    if request.method == "POST":
        producto_form = ProductoForm(request.POST, instance=producto)

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
            try:
                with transaction.atomic():
                    # IMPORTANTE:
                    # No modificar el origen del producto.
                    producto = producto_form.save(commit=False)
                    producto.save()

                    codigos_guardados = []

                    for codigo_form in codigo_formset:
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

                    if not producto.codigos.exists():
                        raise ValidationError(
                            "El producto debe tener al menos un código comercial."
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

                    # Las imágenes pertenecen al PRODUCTO.
                    for imagen in request.FILES.getlist("imagenes_producto"):
                        ImagenProducto.objects.create(
                            producto=producto,
                            imagen=imagen,
                            descripcion=f"Imagen de {producto.nombre_base}",
                        )

                    codigo_destino = (
                        codigos_guardados[0]
                        if codigos_guardados
                        else producto.codigo_principal()
                    )

                    messages.success(
                        request,
                        "Producto actualizado correctamente.",
                    )

                    return redirect(
                        "inventario_catalogo_detalle",
                        codigo_id=codigo_destino.pk,
                    )

            except ValidationError as error:
                messages.error(request, " ".join(error.messages))

            except Exception as error:
                messages.error(
                    request,
                    f"No se pudo actualizar el producto: {error}",
                )

        else:
            messages.error(request, "Revise los datos ingresados.")

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
        "atributos_catalogo": atributos_catalogo,
        "imagenes": producto.imagenes.all().order_by("id"),
    })


# =========================================================
# NUEVO CÓDIGO EQUIVALENTE
# =========================================================

@login_required
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
            try:
                with transaction.atomic():
                    codigos_creados = []

                    for codigo_form in codigo_formset:
                        if (
                            not codigo_form.cleaned_data
                            or codigo_form.cleaned_data.get("DELETE")
                        ):
                            continue

                        codigo = codigo_form.save(commit=False)
                        codigo.producto = producto
                        codigo.save()
                        codigos_creados.append(codigo)

                    if not codigos_creados:
                        raise ValidationError(
                            "Debe agregar al menos un código comercial."
                        )

                    for imagen in request.FILES.getlist("imagenes_producto"):
                        ImagenProducto.objects.create(
                            producto=producto,
                            imagen=imagen,
                            descripcion=f"Imagen de {producto.nombre_base}",
                        )

                    messages.success(
                        request,
                        "Código equivalente agregado correctamente.",
                    )

                    return redirect(
                        "inventario_catalogo_detalle",
                        codigo_id=codigos_creados[0].pk,
                    )

            except ValidationError as error:
                messages.error(request, " ".join(error.messages))

            except Exception as error:
                messages.error(
                    request,
                    f"No se pudo agregar el código: {error}",
                )

        else:
            messages.error(request, "Revise los datos ingresados.")

    else:
        codigo_formset = CodigoProductoFormSet(
            queryset=CodigoProducto.objects.none(),
            prefix="codigos",
        )

    return render(
        request,
        "inventario/catalogo/form_codigo_equivalente.html",
        {
            "producto": producto,
            "codigo_formset": codigo_formset,
        },
    )


# =========================================================
# ACTIVAR / DESACTIVAR
# =========================================================

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
        codigo_id=codigo.pk,
    )