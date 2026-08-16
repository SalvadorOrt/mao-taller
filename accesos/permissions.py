from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def permiso_requerido(permiso, redirect_url="dashboard"):
    def decorador(view_func):

        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):

            # Superusuario: acceso total
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            # Usuario normal: validar permiso
            if not request.user.has_perm(permiso):
                messages.error(
                    request,
                    "No tienes permisos para realizar esta acción.",
                )
                return redirect(redirect_url)

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorador