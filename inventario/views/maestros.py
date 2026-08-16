from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from inventario.forms import (
    AtributoForm,
    CategoriaForm,
    MarcaRepuestoForm,
)
from inventario.models import (
    Atributo,
    Categoria,
    CategoriaAtributo,
    MarcaRepuesto,
)


# =========================================================
# PERMISOS
# =========================================================

def es_admin_o_bodega(user):
    return (
        user.is_authenticated
        and user.rol in ["ADMIN", "BODEGA"]
    )


# =========================================================
# CATEGORÍAS
# =========================================================

@login_required
def categoria_lista(request):
    if not es_admin_o_bodega(request.user):
        messages.error(
            request,
            "No tienes permisos para gestionar categorías.",
        )
        return redirect("dashboard")

    q = request.GET.get("q", "").strip()

    categorias = Categoria.objects.all().order_by("nombre")

    if q:
        categorias = categorias.filter(
            Q(nombre__icontains=q)
            | Q(prefijo_sku__icontains=q)
        )

    return render(
        request,
        "maestros/categoria_lista.html",
        {
            "categorias": categorias,
            "q": q,
        },
    )


@login_required
def categoria_gestionar(request, pk=None):
    if not es_admin_o_bodega(request.user):
        messages.error(
            request,
            "No tienes permisos para gestionar categorías.",
        )
        return redirect("dashboard")

    categoria = (
        get_object_or_404(Categoria, pk=pk)
        if pk
        else None
    )

    atributos_catalogo = (
        Atributo.objects
        .all()
        .order_by("nombre", "unidad")
    )

    # =====================================================
    # ATRIBUTOS SELECCIONADOS
    # =====================================================

    if request.method == "POST":
        atributos_configurados = set()

        for atributo_id in request.POST.getlist(
            "atributos_categoria"
        ):
            try:
                atributos_configurados.add(
                    int(atributo_id)
                )
            except (TypeError, ValueError):
                continue

    elif categoria:
        atributos_configurados = set(
            CategoriaAtributo.objects
            .filter(
                categoria=categoria,
                activo=True,
            )
            .values_list(
                "atributo_id",
                flat=True,
            )
        )

    else:
        atributos_configurados = set()

    # =====================================================
    # POST
    # =====================================================

    if request.method == "POST":
        form = CategoriaForm(
            request.POST,
            instance=categoria,
        )

        if form.is_valid():
            try:
                with transaction.atomic():
                    categoria_guardada = form.save()

                    # =====================================
                    # CATEGORÍA ↔ ATRIBUTOS
                    # =====================================

                    if (
                        request.POST.get(
                            "atributos_categoria_present"
                        ) == "1"
                    ):
                        atributos_ids_originales = (
                            request.POST.getlist(
                                "atributos_categoria"
                            )
                        )

                        atributos_ids = []

                        for atributo_id in atributos_ids_originales:
                            try:
                                atributo_id = int(
                                    atributo_id
                                )
                            except (
                                TypeError,
                                ValueError,
                            ):
                                continue

                            if atributo_id not in atributos_ids:
                                atributos_ids.append(
                                    atributo_id
                                )

                        # =================================
                        # VALIDAR QUE EXISTAN EN BD
                        # =================================

                        ids_validos = set(
                            Atributo.objects
                            .filter(
                                pk__in=atributos_ids
                            )
                            .values_list(
                                "pk",
                                flat=True,
                            )
                        )

                        # =================================
                        # DESACTIVAR LOS NO SELECCIONADOS
                        # =================================

                        (
                            CategoriaAtributo.objects
                            .filter(
                                categoria=categoria_guardada,
                                activo=True,
                            )
                            .exclude(
                                atributo_id__in=ids_validos
                            )
                            .update(
                                activo=False
                            )
                        )

                        # =================================
                        # CREAR / REACTIVAR / ORDENAR
                        # =================================

                        orden = 0

                        for atributo_id in atributos_ids:
                            if atributo_id not in ids_validos:
                                continue

                            CategoriaAtributo.objects.update_or_create(
                                categoria=categoria_guardada,
                                atributo_id=atributo_id,
                                defaults={
                                    "activo": True,
                                    "requerido": False,
                                    "orden": orden,
                                },
                            )

                            orden += 1

                    # =====================================
                    # MENSAJE
                    # =====================================

                    if categoria:
                        messages.success(
                            request,
                            "Categoría actualizada correctamente.",
                        )
                    else:
                        messages.success(
                            request,
                            "Categoría creada correctamente.",
                        )

                    return redirect(
                        "categoria_lista"
                    )

            except Exception as error:
                messages.error(
                    request,
                    f"No se pudo guardar la categoría: {error}",
                )

    # =====================================================
    # GET
    # =====================================================

    else:
        form = CategoriaForm(
            instance=categoria
        )

    return render(
        request,
        "maestros/categoria_form.html",
        {
            "form": form,
            "categoria": categoria,
            "atributos_catalogo": atributos_catalogo,
            "atributos_configurados": atributos_configurados,
        },
    )


# =========================================================
# MARCAS
# =========================================================

@login_required
def marca_lista(request):
    if not es_admin_o_bodega(request.user):
        messages.error(
            request,
            "No tienes permisos para gestionar marcas.",
        )
        return redirect("dashboard")

    q = request.GET.get("q", "").strip()

    marcas = MarcaRepuesto.objects.all().order_by("nombre")

    if q:
        marcas = marcas.filter(
            nombre__icontains=q
        )

    return render(
        request,
        "maestros/marca_lista.html",
        {
            "marcas": marcas,
            "q": q,
        },
    )


@login_required
def marca_gestionar(request, pk=None):
    if not es_admin_o_bodega(request.user):
        messages.error(
            request,
            "No tienes permisos para gestionar marcas.",
        )
        return redirect("dashboard")

    marca = (
        get_object_or_404(
            MarcaRepuesto,
            pk=pk,
        )
        if pk
        else None
    )

    if request.method == "POST":
        form = MarcaRepuestoForm(
            request.POST,
            instance=marca,
        )

        if form.is_valid():
            form.save()

            if marca:
                messages.success(
                    request,
                    "Marca actualizada correctamente.",
                )
            else:
                messages.success(
                    request,
                    "Marca creada correctamente.",
                )

            return redirect(
                "marca_lista"
            )

    else:
        form = MarcaRepuestoForm(
            instance=marca
        )

    return render(
        request,
        "maestros/marca_form.html",
        {
            "form": form,
            "marca": marca,
        },
    )


# =========================================================
# ATRIBUTOS TÉCNICOS
# =========================================================

@login_required
def atributo_lista(request):
    if not es_admin_o_bodega(request.user):
        messages.error(
            request,
            "No tienes permisos para gestionar atributos.",
        )
        return redirect("dashboard")

    q = request.GET.get("q", "").strip()

    atributos = (
        Atributo.objects
        .all()
        .order_by(
            "nombre",
            "unidad",
        )
    )

    if q:
        atributos = atributos.filter(
            Q(nombre__icontains=q)
            | Q(unidad__icontains=q)
        )

    return render(
        request,
        "maestros/atributo_lista.html",
        {
            "atributos": atributos,
            "q": q,
        },
    )


@login_required
def atributo_gestionar(request, pk=None):
    if not es_admin_o_bodega(request.user):
        messages.error(
            request,
            "No tienes permisos para gestionar atributos.",
        )
        return redirect("dashboard")

    atributo = (
        get_object_or_404(
            Atributo,
            pk=pk,
        )
        if pk
        else None
    )

    if request.method == "POST":
        form = AtributoForm(
            request.POST,
            instance=atributo,
        )

        if form.is_valid():
            form.save()

            if atributo:
                messages.success(
                    request,
                    "Atributo actualizado correctamente.",
                )
            else:
                messages.success(
                    request,
                    "Atributo creado correctamente.",
                )

            return redirect(
                "atributo_lista"
            )

    else:
        form = AtributoForm(
            instance=atributo
        )

    return render(
        request,
        "maestros/atributo_form.html",
        {
            "form": form,
            "atributo": atributo,
        },
    )


# =========================================================
# CREACIÓN RÁPIDA - CATEGORÍA
# =========================================================

@login_required
def categoria_crear_rapida(request):
    if not es_admin_o_bodega(request.user):
        return JsonResponse(
            {
                "ok": False,
                "error": "No tienes permisos.",
            },
            status=403,
        )

    if request.method != "POST":
        return JsonResponse(
            {
                "ok": False,
                "error": "Método no permitido.",
            },
            status=405,
        )

    nombre = (
        request.POST.get(
            "nombre",
            "",
        )
        .strip()
        .upper()
    )

    prefijo_sku = (
        request.POST.get(
            "prefijo_sku",
            "",
        )
        .strip()
        .upper()
    )

    if not nombre:
        return JsonResponse(
            {
                "ok": False,
                "error": "El nombre es obligatorio.",
            },
            status=400,
        )

    if not prefijo_sku:
        return JsonResponse(
            {
                "ok": False,
                "error": "El prefijo SKU es obligatorio.",
            },
            status=400,
        )

    categoria, creada = (
        Categoria.objects
        .get_or_create(
            nombre=nombre,
            defaults={
                "prefijo_sku": prefijo_sku,
            },
        )
    )

    if not creada:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Ya existe una categoría con ese nombre."
                ),
                "id": categoria.id,
                "nombre": categoria.nombre,
            },
            status=400,
        )

    return JsonResponse(
        {
            "ok": True,
            "id": categoria.id,
            "nombre": categoria.nombre,
            "prefijo_sku": categoria.prefijo_sku,
        }
    )


# =========================================================
# CREACIÓN RÁPIDA - MARCA
# =========================================================

@login_required
def marca_crear_rapida(request):
    if not es_admin_o_bodega(request.user):
        return JsonResponse(
            {
                "ok": False,
                "error": "No tienes permisos.",
            },
            status=403,
        )

    if request.method != "POST":
        return JsonResponse(
            {
                "ok": False,
                "error": "Método no permitido.",
            },
            status=405,
        )

    nombre = (
        request.POST.get(
            "nombre",
            "",
        )
        .strip()
        .upper()
    )

    if not nombre:
        return JsonResponse(
            {
                "ok": False,
                "error": "El nombre es obligatorio.",
            },
            status=400,
        )

    marca, creada = (
        MarcaRepuesto.objects
        .get_or_create(
            nombre=nombre
        )
    )

    if not creada:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Ya existe una marca con ese nombre."
                ),
                "id": marca.id,
                "nombre": marca.nombre,
            },
            status=400,
        )

    return JsonResponse(
        {
            "ok": True,
            "id": marca.id,
            "nombre": marca.nombre,
        }
    )


# =========================================================
# CREACIÓN RÁPIDA - ATRIBUTO
# =========================================================

@login_required
def atributo_crear_rapido(request):
    if not es_admin_o_bodega(request.user):
        return JsonResponse(
            {
                "ok": False,
                "error": "No tienes permisos.",
            },
            status=403,
        )

    if request.method != "POST":
        return JsonResponse(
            {
                "ok": False,
                "error": "Método no permitido.",
            },
            status=405,
        )

    nombre = (
        request.POST.get(
            "nombre",
            "",
        )
        .strip()
        .upper()
    )

    unidad = (
        request.POST.get(
            "unidad",
            "",
        )
        .strip()
        .upper()
    )

    if not nombre:
        return JsonResponse(
            {
                "ok": False,
                "error": "El nombre es obligatorio.",
            },
            status=400,
        )

    atributo, creada = (
        Atributo.objects
        .get_or_create(
            nombre=nombre,
            unidad=unidad or None,
        )
    )

    if not creada:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Ya existe un atributo igual."
                ),
                "id": atributo.id,
                "nombre": str(atributo),
            },
            status=400,
        )

    return JsonResponse(
        {
            "ok": True,
            "id": atributo.id,
            "nombre": str(atributo),
        }
    )