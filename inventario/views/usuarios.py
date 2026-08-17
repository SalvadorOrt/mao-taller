from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import require_POST

from accesos.permissions import permiso_requerido

from inventario.forms import UsuarioForm
from inventario.models import Usuario


# =========================================================
# DASHBOARD
# =========================================================

@login_required
def dashboard(request):
    return render(
        request,
        "dashboard.html",
    )


# =========================================================
# LISTADO DE USUARIOS
# =========================================================

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


# =========================================================
# CREAR / EDITAR USUARIO
# =========================================================

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


# =========================================================
# HABILITAR / INHABILITAR USUARIO
# =========================================================

@permiso_requerido(
    "inventario.change_usuario"
)
@require_POST
def cambiar_estado_usuario(
    request,
    pk,
):
    usuario = get_object_or_404(
        Usuario,
        pk=pk,
    )

    # =====================================================
    # NO PERMITIR INHABILITARSE A SÍ MISMO
    # =====================================================

    if usuario.pk == request.user.pk:
        messages.error(
            request,
            (
                "No puedes inhabilitar "
                "tu propio usuario."
            ),
        )

        return redirect(
            "lista_usuarios"
        )

    # =====================================================
    # PROTEGER SUPERUSUARIOS
    # =====================================================
    #
    # Un usuario normal con change_usuario no debería
    # poder desactivar una cuenta superusuario.
    # =====================================================

    if (
        usuario.is_superuser
        and not request.user.is_superuser
    ):
        messages.error(
            request,
            (
                "Solo un superusuario puede "
                "cambiar el estado de otro "
                "superusuario."
            ),
        )

        return redirect(
            "lista_usuarios"
        )

    # =====================================================
    # PROTEGER EL ÚLTIMO SUPERUSUARIO ACTIVO
    # =====================================================

    if (
        usuario.is_superuser
        and usuario.is_active
    ):
        superusuarios_activos = (
            Usuario.objects
            .filter(
                is_superuser=True,
                is_active=True,
            )
            .count()
        )

        if superusuarios_activos <= 1:
            messages.error(
                request,
                (
                    "No puedes inhabilitar el "
                    "último superusuario activo."
                ),
            )

            return redirect(
                "lista_usuarios"
            )

    # =====================================================
    # CAMBIAR ESTADO
    # =====================================================

    usuario.is_active = (
        not usuario.is_active
    )

    usuario.save(
        update_fields=[
            "is_active",
        ]
    )

    # =====================================================
    # MENSAJE
    # =====================================================

    if usuario.is_active:
        messages.success(
            request,
            (
                f"El usuario {usuario.username} "
                "fue habilitado correctamente."
            ),
        )

    else:
        messages.success(
            request,
            (
                f"El usuario {usuario.username} "
                "fue inhabilitado correctamente."
            ),
        )

    return redirect(
        "lista_usuarios"
    )