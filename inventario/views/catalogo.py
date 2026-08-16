from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from accesos.permissions import permiso_requerido

from ordenes_de_trabajo.views.utils import (
    obtener_sucursal_activa,
    usuario_puede_cambiar_sucursal,
)

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
# UTILIDADES
# =========================================================

def _mensajes_validacion(error):
    if hasattr(error, "message_dict"):
        mensajes = []

        for errores in error.message_dict.values():
            if isinstance(errores, (list, tuple)):
                mensajes.extend(str(item) for item in errores)
            else:
                mensajes.append(str(errores))

        return " ".join(mensajes)

    if hasattr(error, "messages"):
        return " ".join(str(item) for item in error.messages)

    return str(error)


def _preparar_post_atributos(post_data, prefix="atributos"):
    """
    Hace flexible el formset de atributos también en backend.

    Reglas:

    - sin atributo + sin valor -> ignorar;
    - atributo + valor -> guardar;
    - atributo + sin valor -> ignorar/eliminar;
    - sin atributo + valor -> dejar que el formulario reporte error.

    Esto evita depender exclusivamente de JavaScript.
    """

    datos = post_data.copy()

    try:
        total_forms = int(
            datos.get(
                f"{prefix}-TOTAL_FORMS",
                0,
            )
            or 0
        )
    except (TypeError, ValueError):
        total_forms = 0

    for indice in range(total_forms):
        atributo = str(
            datos.get(
                f"{prefix}-{indice}-atributo",
                "",
            )
            or ""
        ).strip()

        valor = str(
            datos.get(
                f"{prefix}-{indice}-valor",
                "",
            )
            or ""
        ).strip()

        # Atributo seleccionado pero sin valor:
        # la fila es opcional, por lo que se ignora.
        if atributo and not valor:
            datos[
                f"{prefix}-{indice}-DELETE"
            ] = "on"

    return datos


def _datos_codigo_form(datos):
    return {
        "marca": datos.get("marca"),
        "codigo": datos.get("codigo"),
        "tipo_codigo": (
            datos.get("tipo_codigo")
            or "aftermarket"
        ),
        "codigo_barras": datos.get("codigo_barras"),
        "nombre_comercial": datos.get(
            "nombre_comercial"
        ),
        "presentacion_cantidad": datos.get(
            "presentacion_cantidad"
        ),
        "presentacion_unidad": datos.get(
            "presentacion_unidad"
        ),
        "precio_compra": datos.get("precio_compra"),
        "precio_venta": datos.get("precio_venta"),
        "margen_ganancia_porcentaje": (
            datos.get("margen_ganancia_porcentaje")
            if datos.get("margen_ganancia_porcentaje")
            is not None
            else 100
        ),
        "porcentaje_iva_costo": (
            datos.get("porcentaje_iva_costo")
            if datos.get("porcentaje_iva_costo")
            is not None
            else 0
        ),
    }
def _crear_codigo_adicional(producto, datos):
    """
    Agrega una referencia comercial a un producto existente
    utilizando la API pública de CreacionProductoService.

    La vista no maneja directamente:
    - normalización;
    - duplicados;
    - precios;
    - validaciones;
    - creación del CodigoProducto.
    """

    resultado = CreacionProductoService.agregar_codigo_equivalente(
        producto=producto,
        marca=datos.get("marca"),
        codigo=datos.get("codigo"),
        tipo_codigo=(
            datos.get("tipo_codigo")
            or "aftermarket"
        ),
        codigo_barras=datos.get(
            "codigo_barras"
        ),
        nombre_comercial=datos.get(
            "nombre_comercial"
        ),
        presentacion_cantidad=datos.get(
            "presentacion_cantidad"
        ),
        presentacion_unidad=datos.get(
            "presentacion_unidad"
        ),
        precio_compra=datos.get(
            "precio_compra"
        ),
        precio_venta=datos.get(
            "precio_venta"
        ),
        margen_ganancia_porcentaje=(
            datos.get(
                "margen_ganancia_porcentaje"
            )
            if datos.get(
                "margen_ganancia_porcentaje"
            ) is not None
            else 100
        ),
        porcentaje_iva_costo=(
            datos.get(
                "porcentaje_iva_costo"
            )
            if datos.get(
                "porcentaje_iva_costo"
            ) is not None
            else 0
        ),
        activo=bool(
            datos.get("activo")
        ),
        registrar_aprendizaje=False,
        permitir_codigo_existente=False,
    )

    return (
        resultado["codigo_producto"],
        resultado["codigo_creado"],
    )


def _validar_codigo_editado(codigo_obj):
    """
    Evita referencias equivalentes duplicadas incluso si fueron
    escritas con guiones, espacios u otra puntuación.
    """

    codigo_normalizado = (
        CodigoProducto.normalizar_codigo(
            codigo_obj.codigo
        )
    )

    if not codigo_normalizado:
        raise ValidationError(
            "El código comercial no es válido."
        )

    duplicado = (
        CodigoProducto.objects
        .select_related(
            "producto",
            "marca",
        )
        .filter(
            marca=codigo_obj.marca,
            codigo_normalizado=codigo_normalizado,
        )
        .exclude(pk=codigo_obj.pk)
        .first()
    )

    if duplicado:
        raise ValidationError(
            "Ya existe la referencia "
            f"{duplicado.marca.nombre} "
            f"{duplicado.codigo} en "
            f"{duplicado.producto}."
        )


# =========================================================
# LISTADO
# =========================================================

@permiso_requerido(
    "inventario.view_producto"
)
def catalogo_lista(request):
    LIMITE_RESULTADOS = 80

    sucursal_activa = obtener_sucursal_activa(
        request
    )

    puede_cambiar_sucursal = (
        usuario_puede_cambiar_sucursal(
            request
        )
    )

    stocks_visibles = (
        StockSucursal.objects
        .select_related(
            "sucursal"
        )
    )

    if not puede_cambiar_sucursal:
        if sucursal_activa:
            stocks_visibles = stocks_visibles.filter(
                sucursal=sucursal_activa
            )
        else:
            stocks_visibles = stocks_visibles.none()

    q = request.GET.get("q", "").strip()
    categoria_id = request.GET.get(
        "categoria",
        "",
    ).strip()
    marca_id = request.GET.get(
        "marca",
        "",
    ).strip()
    estado = request.GET.get(
        "estado",
        "",
    ).strip()

    codigos = (
        CodigoProducto.objects
        .select_related(
            "producto",
            "producto__categoria",
            "marca",
        )
        .prefetch_related(
            Prefetch(
                "stocks_por_sucursal",
                queryset=stocks_visibles,
                to_attr="stocks_visibles",
            ),
            "producto__imagenes",
        )
        .order_by(
            "producto__nombre_base",
            "marca__nombre",
            "codigo",
        )
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
            | Q(
                producto__categoria__nombre__icontains=q
            )
            | Q(
                producto__valores_atributos__valor__icontains=q
            )
            | Q(
                producto__valores_atributos__atributo__nombre__icontains=q
            )
        ).distinct()

    if categoria_id:
        codigos = codigos.filter(
            producto__categoria_id=categoria_id
        )

    if marca_id:
        codigos = codigos.filter(
            marca_id=marca_id
        )

    if estado == "activos":
        codigos = codigos.filter(
            activo=True,
            producto__activo=True,
        )

    elif estado == "inactivos":
        codigos = codigos.filter(
            Q(activo=False)
            | Q(producto__activo=False)
        )

    elif estado == "sin_precio":
        codigos = codigos.filter(
            Q(precio_venta__isnull=True)
            | Q(precio_venta=0)
        )

    total_filtrado = codigos.count()
    filas = []

    for codigo in codigos[:LIMITE_RESULTADOS]:
        stock_total = sum(
            stock.cantidad
            for stock
            in codigo.stocks_visibles
        )

        equivalencias = (
            codigo.producto.codigos
            .exclude(id=codigo.id)
            .select_related("marca")
            .order_by(
                "marca__nombre",
                "codigo",
            )[:5]
        )

        filas.append({
            "codigo": codigo,
            "producto": codigo.producto,
            "categoria": codigo.producto.categoria,
            "marca": codigo.marca,
            "stock_total": stock_total,
            "precio_secreto": codigo.precio_secreto,
            "equivalencias": equivalencias,
            "total_imagenes": (
                codigo.producto.imagenes.count()
            ),
        })

    return render(
        request,
        "inventario/catalogo/lista.html",
        {
            "filas": filas,
            "categorias": (
                Categoria.objects
                .all()
                .order_by("nombre")
            ),
            "marcas": (
                MarcaRepuesto.objects
                .all()
                .order_by("nombre")
            ),
            "q": q,
            "categoria_id": categoria_id,
            "marca_id": marca_id,
            "estado": estado,
            "total_filtrado": total_filtrado,
            "limite_resultados": LIMITE_RESULTADOS,
            "sucursal_activa": sucursal_activa,
            "puede_cambiar_sucursal": (
                puede_cambiar_sucursal
            ),
        },
    )


# =========================================================
# DETALLE
# =========================================================

@permiso_requerido(
    "inventario.view_producto"
)
def catalogo_detalle(request, codigo_id):
    codigo = get_object_or_404(
        CodigoProducto.objects
        .select_related(
            "producto",
            "producto__categoria",
            "marca",
        )
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

    sucursal_activa = obtener_sucursal_activa(
        request
    )

    puede_cambiar_sucursal = (
        usuario_puede_cambiar_sucursal(
            request
        )
    )

    stocks = (
        StockSucursal.objects
        .filter(
            codigo_producto=codigo
        )
        .select_related(
            "sucursal"
        )
        .order_by(
            "sucursal__nombre"
        )
    )

    movimientos = (
        codigo.movimientos
        .select_related(
            "sucursal"
        )
        .order_by(
            "-fecha"
        )
    )

    if not puede_cambiar_sucursal:
        if sucursal_activa:
            stocks = stocks.filter(
                sucursal=sucursal_activa
            )

            movimientos = movimientos.filter(
                sucursal=sucursal_activa
            )
        else:
            stocks = stocks.none()
            movimientos = movimientos.none()

    return render(
        request,
        "inventario/catalogo/detalle.html",
        {
            "codigo": codigo,
            "producto": producto,
            "codigos_equivalentes": (
                producto.codigos
                .select_related("marca")
                .order_by(
                    "marca__nombre",
                    "codigo",
                )
            ),
            "atributos": (
                producto.valores_atributos
                .select_related("atributo")
                .order_by("atributo__nombre")
            ),
            "imagenes": (
                producto.imagenes
                .all()
                .order_by("id")
            ),
            "stocks": stocks,
            "movimientos": movimientos[:20],
            "precio_secreto": (
                codigo.precio_secreto
            ),
            "sucursal_activa": sucursal_activa,
            "puede_cambiar_sucursal": (
                puede_cambiar_sucursal
            ),
        },
    )


# =========================================================
# API - MOTOR DE SUGERENCIAS
# =========================================================

@permiso_requerido(
    "inventario.view_producto"
)
def catalogo_sugerir_producto(request):
    texto = request.GET.get(
        "texto",
        "",
    ).strip()

    codigo = request.GET.get(
        "codigo",
        "",
    ).strip()

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
            motor.convertir_a_dict(
                resultado
            )
        )

    except ValidationError as error:
        return JsonResponse(
            {
                "ok": False,
                "error": _mensajes_validacion(
                    error
                ),
            },
            status=400,
        )

    except Exception as error:
        return JsonResponse(
            {
                "ok": False,
                "error": str(error),
            },
            status=500,
        )


# =========================================================
# API - ATRIBUTOS POR CATEGORÍA
# =========================================================

@permiso_requerido(
    "inventario.view_atributo"
)
def catalogo_atributos_categoria(
    request,
    categoria_id,
):
    categoria = get_object_or_404(
        Categoria,
        pk=categoria_id,
    )

    configuraciones = (
        CategoriaAtributo.objects
        .filter(
            categoria=categoria,
            activo=True,
        )
        .select_related("atributo")
        .order_by(
            "orden",
            "atributo__nombre",
        )
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

                # Conservamos el dato en la API,
                # pero el formulario actual trabaja
                # de forma flexible.
                "requerido": item.requerido,

                "orden": item.orden,
            }
            for item in configuraciones
        ],
    })


# =========================================================
# CREAR PRODUCTO
# =========================================================

@permiso_requerido(
    "inventario.add_producto"
)
def catalogo_crear(request):
    atributos_catalogo = (
        Atributo.objects
        .all()
        .order_by(
            "nombre",
            "unidad",
        )
    )

    if request.method == "POST":

        # -------------------------------------------------
        # PREPARAR ATRIBUTOS OPCIONALES
        # -------------------------------------------------

        post_atributos = (
            _preparar_post_atributos(
                request.POST,
                prefix="atributos",
            )
        )

        producto_form = ProductoForm(
            request.POST
        )

        codigo_formset = CodigoProductoFormSet(
            request.POST,
            request.FILES,
            queryset=CodigoProducto.objects.none(),
            prefix="codigos",
        )

        atributo_formset = (
            ValorAtributoProductoFormSet(
                post_atributos,
                queryset=(
                    ValorAtributoProducto
                    .objects.none()
                ),
                prefix="atributos",
            )
        )

        producto_valido = (
            producto_form.is_valid()
        )

        codigos_validos_formset = (
            codigo_formset.is_valid()
        )

        atributos_validos_formset = (
            atributo_formset.is_valid()
        )

        formularios_validos = (
            producto_valido
            and codigos_validos_formset
            and atributos_validos_formset
        )

        if formularios_validos:
            codigos_validos = []

            for codigo_form in codigo_formset:
                if not codigo_form.cleaned_data:
                    continue

                if codigo_form.cleaned_data.get(
                    "DELETE"
                ):
                    continue

                datos = codigo_form.cleaned_data

                if (
                    datos.get("codigo")
                    or datos.get("marca")
                    or datos.get("nombre_comercial")
                ):
                    codigos_validos.append(
                        codigo_form
                    )

            if not codigos_validos:
                messages.error(
                    request,
                    "Debe agregar al menos "
                    "un código comercial.",
                )

            else:
                try:
                    with transaction.atomic():
                        datos_producto = (
                            producto_form.cleaned_data
                        )

                        primera_forma_codigo = (
                            codigos_validos[0]
                        )

                        datos_codigo = (
                            primera_forma_codigo
                            .cleaned_data
                        )

                        texto_aprendizaje = (
                            request.POST.get(
                                "texto_aprendizaje",
                                "",
                            ).strip()
                            or datos_producto.get(
                                "descripcion"
                            )
                            or datos_codigo.get(
                                "nombre_comercial"
                            )
                            or datos_producto.get(
                                "nombre_base"
                            )
                        )

                        # =================================
                        # PRODUCTO + PRIMER CÓDIGO
                        # =================================

                        resultado = (
                            CreacionProductoService
                            .crear_individual(
                                categoria=(
                                    datos_producto[
                                        "categoria"
                                    ]
                                ),
                                nombre_base=(
                                    datos_producto[
                                        "nombre_base"
                                    ]
                                ),
                                descripcion=(
                                    datos_producto.get(
                                        "descripcion"
                                    )
                                ),
                                marca=(
                                    datos_codigo[
                                        "marca"
                                    ]
                                ),
                                codigo=(
                                    datos_codigo[
                                        "codigo"
                                    ]
                                ),
                                texto_original=(
                                    texto_aprendizaje
                                ),
                                nombre_comercial=(
                                    datos_codigo.get(
                                        "nombre_comercial"
                                    )
                                ),
                                tipo_codigo=(
                                    datos_codigo.get(
                                        "tipo_codigo"
                                    )
                                    or "aftermarket"
                                ),
                                codigo_barras=(
                                    datos_codigo.get(
                                        "codigo_barras"
                                    )
                                ),
                                presentacion_cantidad=(
                                    datos_codigo.get(
                                        "presentacion_cantidad"
                                    )
                                ),
                                presentacion_unidad=(
                                    datos_codigo.get(
                                        "presentacion_unidad"
                                    )
                                ),
                                precio_compra=(
                                    datos_codigo.get(
                                        "precio_compra"
                                    )
                                ),
                                precio_venta=(
                                    datos_codigo.get(
                                        "precio_venta"
                                    )
                                ),
                                margen_ganancia_porcentaje=(
                                    datos_codigo.get(
                                        "margen_ganancia_porcentaje"
                                    )
                                    if datos_codigo.get(
                                        "margen_ganancia_porcentaje"
                                    )
                                    is not None
                                    else 100
                                ),
                                porcentaje_iva_costo=(
                                    datos_codigo.get(
                                        "porcentaje_iva_costo"
                                    )
                                    if datos_codigo.get(
                                        "porcentaje_iva_costo"
                                    )
                                    is not None
                                    else 0
                                ),
                                usuario=request.user,
                                registrar_aprendizaje=True,
                                permitir_producto_existente=False,
                                permitir_codigo_existente=False,
                            )
                        )

                        producto = resultado[
                            "producto"
                        ]

                        codigo_principal = resultado[
                            "codigo_producto"
                        ]

                        # =================================
                        # ESTADO DEL PRODUCTO
                        # =================================

                        producto.datos_incompletos = bool(
                            datos_producto.get(
                                "datos_incompletos"
                            )
                        )

                        producto.descontinuado = bool(
                            datos_producto.get(
                                "descontinuado"
                            )
                        )

                        producto.activo = bool(
                            datos_producto.get(
                                "activo"
                            )
                        )

                        if producto.descontinuado:
                            producto.activo = False

                        producto.save()

                        # =================================
                        # ESTADO DEL PRIMER CÓDIGO
                        # =================================

                        codigo_principal.activo = bool(
                            datos_codigo.get(
                                "activo"
                            )
                        )

                        codigo_principal.save(
                            update_fields=[
                                "activo",
                                "actualizado_en",
                            ]
                        )

                        codigos_creados = [
                            codigo_principal
                        ]

                        # =================================
                        # CÓDIGOS ADICIONALES
                        # =================================

                        for codigo_form in (
                            codigos_validos[1:]
                        ):
                            codigo_adicional, _ = (
                                _crear_codigo_adicional(
                                    producto,
                                    codigo_form.cleaned_data,
                                )
                            )

                            codigos_creados.append(
                                codigo_adicional
                            )

                        # =================================
                        # ATRIBUTOS TÉCNICOS
                        # =================================

                        for atributo_form in (
                            atributo_formset
                        ):
                            if (
                                not atributo_form.cleaned_data
                            ):
                                continue

                            if (
                                atributo_form
                                .cleaned_data
                                .get("DELETE")
                            ):
                                continue

                            atributo = (
                                atributo_form
                                .cleaned_data
                                .get("atributo")
                            )

                            valor = str(
                                atributo_form
                                .cleaned_data
                                .get("valor")
                                or ""
                            ).strip()

                            # Todos los atributos son
                            # opcionales.
                            if not atributo or not valor:
                                continue

                            atributo_valor = (
                                atributo_form
                                .save(commit=False)
                            )

                            atributo_valor.producto = (
                                producto
                            )

                            atributo_valor.valor = valor

                            atributo_valor.save()

                        # =================================
                        # IMÁGENES
                        # =================================

                        for imagen in (
                            request.FILES.getlist(
                                "imagenes_producto"
                            )
                        ):
                            ImagenProducto.objects.create(
                                producto=producto,
                                imagen=imagen,
                                descripcion=(
                                    f"Imagen de "
                                    f"{producto.nombre_base}"
                                ),
                            )

                        messages.success(
                            request,
                            "Producto creado correctamente.",
                        )

                        return redirect(
                            "inventario_catalogo_detalle",
                            codigo_id=(
                                codigos_creados[0].pk
                            ),
                        )

                except ValidationError as error:
                    messages.error(
                        request,
                        _mensajes_validacion(
                            error
                        ),
                    )

                except Exception as error:
                    messages.error(
                        request,
                        (
                            "No se pudo crear el "
                            f"producto: {error}"
                        ),
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

        atributo_formset = (
            ValorAtributoProductoFormSet(
                queryset=(
                    ValorAtributoProducto
                    .objects.none()
                ),
                prefix="atributos",
            )
        )

    return render(
        request,
        "catalogo/crear.html",
        {
            "producto_form": producto_form,
            "codigo_formset": codigo_formset,
            "atributo_formset": atributo_formset,
            "atributos_catalogo": (
                atributos_catalogo
            ),
        },
    )


# =========================================================
# EDITAR PRODUCTO / CÓDIGOS
# =========================================================

@permiso_requerido(
    "inventario.change_producto"
)
def catalogo_editar_codigo(
    request,
    codigo_id,
):
    codigo = get_object_or_404(
        CodigoProducto.objects
        .select_related(
            "producto",
            "producto__categoria",
            "marca",
        ),
        id=codigo_id,
    )

    producto = codigo.producto

    atributos_catalogo = (
        Atributo.objects
        .all()
        .order_by(
            "nombre",
            "unidad",
        )
    )

    if request.method == "POST":

        post_atributos = (
            _preparar_post_atributos(
                request.POST,
                prefix="atributos",
            )
        )

        producto_form = ProductoForm(
            request.POST,
            instance=producto,
        )

        codigo_formset = CodigoProductoFormSet(
            request.POST,
            request.FILES,
            queryset=(
                producto.codigos
                .all()
                .order_by("id")
            ),
            prefix="codigos",
        )

        atributo_formset = (
            ValorAtributoProductoFormSet(
                post_atributos,
                queryset=(
                    producto
                    .valores_atributos
                    .all()
                    .order_by("id")
                ),
                prefix="atributos",
            )
        )

        producto_valido = (
            producto_form.is_valid()
        )

        codigos_validos = (
            codigo_formset.is_valid()
        )

        atributos_validos = (
            atributo_formset.is_valid()
        )

        if (
            producto_valido
            and codigos_validos
            and atributos_validos
        ):
            try:
                with transaction.atomic():

                    # =====================================
                    # PRODUCTO
                    # =====================================

                    producto = (
                        producto_form.save(
                            commit=False
                        )
                    )

                    # Conservamos origen y trazabilidad.
                    producto.save()

                    # =====================================
                    # CÓDIGOS
                    # =====================================

                    codigos_guardados = []

                    for codigo_form in (
                        codigo_formset
                    ):
                        if (
                            not codigo_form.cleaned_data
                        ):
                            continue

                        if (
                            codigo_form
                            .cleaned_data
                            .get("DELETE")
                        ):
                            if codigo_form.instance.pk:
                                codigo_form.instance.delete()

                            continue

                        codigo_obj = (
                            codigo_form.save(
                                commit=False
                            )
                        )

                        codigo_obj.producto = (
                            producto
                        )

                        _validar_codigo_editado(
                            codigo_obj
                        )

                        codigo_obj.save()

                        codigos_guardados.append(
                            codigo_obj
                        )

                    if not producto.codigos.exists():
                        raise ValidationError(
                            "El producto debe tener al menos "
                            "un código comercial."
                        )

                    # =====================================
                    # ATRIBUTOS
                    # =====================================

                    for atributo_form in (
                        atributo_formset
                    ):
                        if (
                            not atributo_form.cleaned_data
                        ):
                            continue

                        if (
                            atributo_form
                            .cleaned_data
                            .get("DELETE")
                        ):
                            if atributo_form.instance.pk:
                                atributo_form.instance.delete()

                            continue

                        atributo = (
                            atributo_form
                            .cleaned_data
                            .get("atributo")
                        )

                        valor = str(
                            atributo_form
                            .cleaned_data
                            .get("valor")
                            or ""
                        ).strip()

                        # Si no se completó, simplemente
                        # no existe ValorAtributoProducto.
                        if not atributo or not valor:
                            if atributo_form.instance.pk:
                                atributo_form.instance.delete()

                            continue

                        atributo_valor = (
                            atributo_form
                            .save(commit=False)
                        )

                        atributo_valor.producto = (
                            producto
                        )

                        atributo_valor.valor = valor

                        atributo_valor.save()

                    # =====================================
                    # IMÁGENES
                    # =====================================

                    for imagen in (
                        request.FILES.getlist(
                            "imagenes_producto"
                        )
                    ):
                        ImagenProducto.objects.create(
                            producto=producto,
                            imagen=imagen,
                            descripcion=(
                                f"Imagen de "
                                f"{producto.nombre_base}"
                            ),
                        )

                    codigo_destino = (
                        codigos_guardados[0]
                        if codigos_guardados
                        else producto.codigo_principal()
                    )

                    if not codigo_destino:
                        raise ValidationError(
                            "El producto debe tener al menos "
                            "un código comercial."
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
                messages.error(
                    request,
                    _mensajes_validacion(
                        error
                    ),
                )

            except Exception as error:
                messages.error(
                    request,
                    (
                        "No se pudo actualizar "
                        f"el producto: {error}"
                    ),
                )

        else:
            messages.error(
                request,
                "Revise los datos ingresados.",
            )

    else:
        producto_form = ProductoForm(
            instance=producto
        )

        codigo_formset = CodigoProductoFormSet(
            queryset=(
                producto.codigos
                .all()
                .order_by("id")
            ),
            prefix="codigos",
        )

        atributo_formset = (
            ValorAtributoProductoFormSet(
                queryset=(
                    producto
                    .valores_atributos
                    .all()
                    .order_by("id")
                ),
                prefix="atributos",
            )
        )

    return render(
        request,
        "inventario/catalogo/form_editar.html",
        {
            "codigo": codigo,
            "producto": producto,
            "producto_form": producto_form,
            "codigo_formset": codigo_formset,
            "atributo_formset": atributo_formset,
            "atributos_catalogo": (
                atributos_catalogo
            ),
            "imagenes": (
                producto.imagenes
                .all()
                .order_by("id")
            ),
        },
    )


# =========================================================
# NUEVO CÓDIGO EQUIVALENTE
# =========================================================

@permiso_requerido(
    "inventario.add_codigoproducto"
)
def catalogo_crear_codigo_equivalente(
    request,
    producto_id,
):
    producto = get_object_or_404(
        Producto.objects.select_related(
            "categoria"
        ),
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

                    for codigo_form in (
                        codigo_formset
                    ):
                        if (
                            not codigo_form.cleaned_data
                        ):
                            continue

                        if (
                            codigo_form
                            .cleaned_data
                            .get("DELETE")
                        ):
                            continue

                        codigo_nuevo, _ = (
                            _crear_codigo_adicional(
                                producto,
                                codigo_form.cleaned_data,
                            )
                        )

                        codigos_creados.append(
                            codigo_nuevo
                        )

                    if not codigos_creados:
                        raise ValidationError(
                            "Debe agregar al menos "
                            "un código comercial."
                        )

                    for imagen in (
                        request.FILES.getlist(
                            "imagenes_producto"
                        )
                    ):
                        ImagenProducto.objects.create(
                            producto=producto,
                            imagen=imagen,
                            descripcion=(
                                f"Imagen de "
                                f"{producto.nombre_base}"
                            ),
                        )

                    messages.success(
                        request,
                        "Código equivalente agregado correctamente.",
                    )

                    return redirect(
                        "inventario_catalogo_detalle",
                        codigo_id=(
                            codigos_creados[0].pk
                        ),
                    )

            except ValidationError as error:
                messages.error(
                    request,
                    _mensajes_validacion(
                        error
                    ),
                )

            except Exception as error:
                messages.error(
                    request,
                    (
                        "No se pudo agregar "
                        f"el código: {error}"
                    ),
                )

        else:
            messages.error(
                request,
                "Revise los datos ingresados.",
            )

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
# ACTIVAR / DESACTIVAR CÓDIGO
# =========================================================

@permiso_requerido(
    "inventario.change_codigoproducto"
)
def catalogo_toggle_codigo(
    request,
    codigo_id,
):
    codigo = get_object_or_404(
        CodigoProducto,
        id=codigo_id,
    )

    if request.method == "POST":
        codigo.activo = not codigo.activo

        codigo.save(
            update_fields=[
                "activo",
                "actualizado_en",
            ]
        )

        if codigo.activo:
            messages.success(
                request,
                "Código activado.",
            )
        else:
            messages.warning(
                request,
                "Código desactivado.",
            )

    return redirect(
        "inventario_catalogo_detalle",
        codigo_id=codigo.pk,
    )