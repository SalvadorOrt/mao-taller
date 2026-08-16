from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .forms import RolForm
from .models import Rol
from .permissions import permiso_requerido


# =========================================================
# LISTA DE ROLES
# =========================================================

@permiso_requerido("auth.view_group")
def roles_lista(request):
    roles = (
        Rol.objects
        .prefetch_related("permissions")
        .order_by("name")
    )

    return render(
        request,
        "accesos/roles_lista.html",
        {
            "roles": roles,
        },
    )


# =========================================================
# CREAR ROL
# =========================================================

@permiso_requerido("auth.add_group")
def rol_crear(request):
    if request.method == "POST":
        form = RolForm(request.POST)

        if form.is_valid():
            with transaction.atomic():
                rol = form.save()

            messages.success(
                request,
                f'El rol "{rol.name}" fue creado correctamente.',
            )

            return redirect(
                "accesos:roles_lista"
            )

    else:
        form = RolForm()

    return render(
        request,
        "accesos/rol_form.html",
        {
            "form": form,
            "rol": None,
            "titulo": "Nuevo rol",
        },
    )


# =========================================================
# EDITAR ROL
# =========================================================

@permiso_requerido("auth.change_group")
def rol_editar(request, pk):
    rol = get_object_or_404(
        Rol.objects.prefetch_related("permissions"),
        pk=pk,
    )

    if request.method == "POST":
        form = RolForm(
            request.POST,
            instance=rol,
        )

        if form.is_valid():
            with transaction.atomic():
                rol = form.save()

            messages.success(
                request,
                f'El rol "{rol.name}" fue actualizado correctamente.',
            )

            return redirect(
                "accesos:roles_lista"
            )

    else:
        form = RolForm(
            instance=rol
        )

    return render(
        request,
        "accesos/rol_form.html",
        {
            "form": form,
            "rol": rol,
            "titulo": f"Editar rol: {rol.name}",
        },
    )


# =========================================================
# ELIMINAR ROL
# =========================================================

@permiso_requerido("auth.delete_group")
def rol_eliminar(request, pk):
    rol = get_object_or_404(
        Rol,
        pk=pk,
    )

    Usuario = get_user_model()

    usuarios_asignados = (
        Usuario.objects
        .filter(groups=rol)
        .order_by("username")
    )

    if request.method == "POST":

        # -------------------------------------------------
        # No permitir eliminar un rol que todavía tenga
        # usuarios asociados.
        # -------------------------------------------------
        if usuarios_asignados.exists():
            messages.error(
                request,
                (
                    f'No se puede eliminar el rol "{rol.name}" '
                    "porque todavía tiene usuarios asignados."
                ),
            )

            return redirect(
                "accesos:roles_lista"
            )

        nombre = rol.name

        with transaction.atomic():
            rol.delete()

        messages.success(
            request,
            f'El rol "{nombre}" fue eliminado correctamente.',
        )

        return redirect(
            "accesos:roles_lista"
        )

    return render(
        request,
        "accesos/rol_confirmar_eliminar.html",
        {
            "rol": rol,
            "usuarios_asignados": usuarios_asignados,
        },
    )