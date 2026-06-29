from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from inventario.models import Categoria, MarcaRepuesto, Atributo
from inventario.forms import CategoriaForm, MarcaRepuestoForm, AtributoForm


def es_admin_o_bodega(user):
    return user.is_authenticated and user.rol in ["ADMIN", "BODEGA"]


# =========================================================
# CATEGORÍAS
# =========================================================
@login_required
def categoria_lista(request):
    if not es_admin_o_bodega(request.user):
        messages.error(request, "No tienes permisos para gestionar categorías.")
        return redirect("dashboard")

    q = request.GET.get("q", "").strip()

    categorias = Categoria.objects.all().order_by("nombre")

    if q:
        categorias = categorias.filter(
            Q(nombre__icontains=q) |
            Q(prefijo_sku__icontains=q)
        )

    return render(request, "inventario/maestros/categoria_lista.html", {
        "categorias": categorias,
        "q": q,
    })


@login_required
def categoria_gestionar(request, pk=None):
    if not es_admin_o_bodega(request.user):
        messages.error(request, "No tienes permisos para gestionar categorías.")
        return redirect("dashboard")

    categoria = get_object_or_404(Categoria, pk=pk) if pk else None

    if request.method == "POST":
        form = CategoriaForm(request.POST, instance=categoria)

        if form.is_valid():
            form.save()

            if categoria:
                messages.success(request, "Categoría actualizada correctamente.")
            else:
                messages.success(request, "Categoría creada correctamente.")

            return redirect("categoria_lista")
    else:
        form = CategoriaForm(instance=categoria)

    return render(request, "inventario/maestros/categoria_form.html", {
        "form": form,
        "categoria": categoria,
    })


# =========================================================
# MARCAS
# =========================================================
@login_required
def marca_lista(request):
    if not es_admin_o_bodega(request.user):
        messages.error(request, "No tienes permisos para gestionar marcas.")
        return redirect("dashboard")

    q = request.GET.get("q", "").strip()

    marcas = MarcaRepuesto.objects.all().order_by("nombre")

    if q:
        marcas = marcas.filter(nombre__icontains=q)

    return render(request, "inventario/maestros/marca_lista.html", {
        "marcas": marcas,
        "q": q,
    })


@login_required
def marca_gestionar(request, pk=None):
    if not es_admin_o_bodega(request.user):
        messages.error(request, "No tienes permisos para gestionar marcas.")
        return redirect("dashboard")

    marca = get_object_or_404(MarcaRepuesto, pk=pk) if pk else None

    if request.method == "POST":
        form = MarcaRepuestoForm(request.POST, instance=marca)

        if form.is_valid():
            form.save()

            if marca:
                messages.success(request, "Marca actualizada correctamente.")
            else:
                messages.success(request, "Marca creada correctamente.")

            return redirect("marca_lista")
    else:
        form = MarcaRepuestoForm(instance=marca)

    return render(request, "inventario/maestros/marca_form.html", {
        "form": form,
        "marca": marca,
    })


# =========================================================
# ATRIBUTOS TÉCNICOS
# =========================================================
@login_required
def atributo_lista(request):
    if not es_admin_o_bodega(request.user):
        messages.error(request, "No tienes permisos para gestionar atributos.")
        return redirect("dashboard")

    q = request.GET.get("q", "").strip()

    atributos = Atributo.objects.all().order_by("nombre", "unidad")

    if q:
        atributos = atributos.filter(
            Q(nombre__icontains=q) |
            Q(unidad__icontains=q)
        )

    return render(request, "inventario/maestros/atributo_lista.html", {
        "atributos": atributos,
        "q": q,
    })


@login_required
def atributo_gestionar(request, pk=None):
    if not es_admin_o_bodega(request.user):
        messages.error(request, "No tienes permisos para gestionar atributos.")
        return redirect("dashboard")

    atributo = get_object_or_404(Atributo, pk=pk) if pk else None

    if request.method == "POST":
        form = AtributoForm(request.POST, instance=atributo)

        if form.is_valid():
            form.save()

            if atributo:
                messages.success(request, "Atributo actualizado correctamente.")
            else:
                messages.success(request, "Atributo creado correctamente.")

            return redirect("atributo_lista")
    else:
        form = AtributoForm(instance=atributo)

    return render(request, "inventario/maestros/atributo_form.html", {
        "form": form,
        "atributo": atributo,
    })


# =========================================================
# CREACIÓN RÁPIDA AJAX
# =========================================================
@login_required
def categoria_crear_rapida(request):
    if not es_admin_o_bodega(request.user):
        return JsonResponse({
            "ok": False,
            "error": "No tienes permisos."
        }, status=403)

    if request.method != "POST":
        return JsonResponse({
            "ok": False,
            "error": "Método no permitido."
        }, status=405)

    nombre = request.POST.get("nombre", "").strip().upper()
    prefijo_sku = request.POST.get("prefijo_sku", "").strip().upper()

    if not nombre:
        return JsonResponse({
            "ok": False,
            "error": "El nombre es obligatorio."
        }, status=400)

    if not prefijo_sku:
        return JsonResponse({
            "ok": False,
            "error": "El prefijo SKU es obligatorio."
        }, status=400)

    categoria, creada = Categoria.objects.get_or_create(
        nombre=nombre,
        defaults={
            "prefijo_sku": prefijo_sku,
        }
    )

    if not creada:
        return JsonResponse({
            "ok": False,
            "error": "Ya existe una categoría con ese nombre.",
            "id": categoria.id,
            "nombre": categoria.nombre,
        }, status=400)

    return JsonResponse({
        "ok": True,
        "id": categoria.id,
        "nombre": categoria.nombre,
        "prefijo_sku": categoria.prefijo_sku,
    })


@login_required
def marca_crear_rapida(request):
    if not es_admin_o_bodega(request.user):
        return JsonResponse({
            "ok": False,
            "error": "No tienes permisos."
        }, status=403)

    if request.method != "POST":
        return JsonResponse({
            "ok": False,
            "error": "Método no permitido."
        }, status=405)

    nombre = request.POST.get("nombre", "").strip().upper()

    if not nombre:
        return JsonResponse({
            "ok": False,
            "error": "El nombre es obligatorio."
        }, status=400)

    marca, creada = MarcaRepuesto.objects.get_or_create(
        nombre=nombre,
    )

    if not creada:
        return JsonResponse({
            "ok": False,
            "error": "Ya existe una marca con ese nombre.",
            "id": marca.id,
            "nombre": marca.nombre,
        }, status=400)

    return JsonResponse({
        "ok": True,
        "id": marca.id,
        "nombre": marca.nombre,
    })


@login_required
def atributo_crear_rapido(request):
    if not es_admin_o_bodega(request.user):
        return JsonResponse({
            "ok": False,
            "error": "No tienes permisos."
        }, status=403)

    if request.method != "POST":
        return JsonResponse({
            "ok": False,
            "error": "Método no permitido."
        }, status=405)

    nombre = request.POST.get("nombre", "").strip().upper()
    unidad = request.POST.get("unidad", "").strip().upper()

    if not nombre:
        return JsonResponse({
            "ok": False,
            "error": "El nombre es obligatorio."
        }, status=400)

    atributo, creada = Atributo.objects.get_or_create(
        nombre=nombre,
        unidad=unidad or None,
    )

    if not creada:
        return JsonResponse({
            "ok": False,
            "error": "Ya existe un atributo igual.",
            "id": atributo.id,
            "nombre": str(atributo),
        }, status=400)

    return JsonResponse({
        "ok": True,
        "id": atributo.id,
        "nombre": str(atributo),
    })