from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)

from accesos.permissions import permiso_requerido

from inventario.forms import UsuarioForm
from inventario.models import Usuario


@login_required
def dashboard(request):
    return render(
        request,
        "dashboard.html",
    )


@permiso_requerido(
    "inventario.view_usuario"
)
def lista_usuarios(request):
    usuarios = (
        Usuario.objects
        .all()
        .prefetch_related(
            "groups",
        )
        .order_by(
            "-is_active",
            "first_name",
            "last_name",
            "username",
        )
    )

    return render(
        request,
        "usuarios/lista_usuarios.html",
        {
            "usuarios": usuarios,
        },
    )


@login_required
def gestionar_usuario(
    request,
    pk=None,
):
    # =====================================================
    # PERMISO NECESARIO
    # =====================================================

    permiso_necesario = (
        "inventario.change_usuario"
        if pk
        else "inventario.add_usuario"
    )

    if not request.user.has_perm(
        permiso_necesario
    ):
        messages.error(
            request,
            (
                "No tienes permisos para "
                "gestionar usuarios."
            ),
        )

        return redirect(
            "dashboard"
        )

    # =====================================================
    # EDITAR
    # =====================================================

    if pk:
        usuario = get_object_or_404(
            Usuario,
            pk=pk,
        )

        mensaje_exito = (
            f"El usuario {usuario.username} "
            "fue actualizado."
        )

    # =====================================================
    # CREAR
    # =====================================================

    else:
        usuario = None

        mensaje_exito = (
            "Usuario creado y asignado "
            "correctamente."
        )

    # =====================================================
    # POST
    # =====================================================

    if request.method == "POST":
        form = UsuarioForm(
            request.POST,
            instance=usuario,
        )

        if form.is_valid():

            # Un usuario nuevo debe tener contraseña.
            if (
                not pk
                and not form.cleaned_data.get(
                    "password"
                )
            ):
                form.add_error(
                    "password",
                    (
                        "Debe asignar una contraseña "
                        "al nuevo usuario."
                    ),
                )

            else:
                form.save()

                messages.success(
                    request,
                    mensaje_exito,
                )

                return redirect(
                    "lista_usuarios"
                )

    # =====================================================
    # GET
    # =====================================================

    else:
        form = UsuarioForm(
            instance=usuario,
        )

    # =====================================================
    # RENDER
    # =====================================================

    return render(
        request,
        "usuarios/gestionar_usuario.html",
        {
            "form": form,
            "usuario": usuario,
        },
    )