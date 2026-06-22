from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from inventario.models import Usuario
from inventario.forms import UsuarioForm


@login_required
def dashboard(request):
    return render(request, "dashboard.html")


@login_required
def lista_usuarios(request):
    # Protección total: Solo dueños
    if request.user.rol != "ADMIN":
        messages.error(request, "No tienes permisos para ver el personal.")
        return redirect("dashboard")

    usuarios = Usuario.objects.all().order_by(
        "-is_active",
        "rol",
        "username"
    )

    return render(
        request,
        "usuarios/lista_usuarios.html",
        {"usuarios": usuarios}
    )


@login_required
def gestionar_usuario(request, pk=None):
    if request.user.rol != "ADMIN":
        messages.error(
            request,
            "Solo los administradores pueden gestionar usuarios."
        )
        return redirect("dashboard")

    # EDITAR
    if pk:
        usuario = get_object_or_404(
            Usuario,
            pk=pk
        )
        mensaje_exito = (
            f"El usuario {usuario.username} fue actualizado."
        )

    # CREAR
    else:
        usuario = None
        mensaje_exito = (
            "Usuario creado y asignado a sucursal correctamente."
        )

    if request.method == "POST":

        form = UsuarioForm(
            request.POST,
            instance=usuario
        )

        if form.is_valid():

            # Si es nuevo debe tener contraseña
            if not pk and not form.cleaned_data.get("password"):
                form.add_error(
                    "password",
                    "Debe asignar una contraseña al nuevo usuario."
                )

            else:
                form.save()

                messages.success(
                    request,
                    mensaje_exito
                )

                return redirect("lista_usuarios")

    else:
        form = UsuarioForm(
            instance=usuario
        )

    return render(
        request,
        "usuarios/gestionar_usuario.html",
        {
            "form": form,
            "usuario": usuario,
        }
    )