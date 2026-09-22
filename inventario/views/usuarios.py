from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import require_POST

from accesos.permissions import permiso_requerido
from accesos.session_utils import (
    cerrar_sesiones_de_usuario,
)
from django.db import transaction

from asistencia.models import (
    ConfiguracionAsistenciaUsuario,
)
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
    # USUARIO
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

    else:

        usuario = None

        mensaje_exito = (
            "Usuario creado y asignado "
            "correctamente."
        )

    # =====================================================
    # CONFIGURACIÓN ACTUAL DE ASISTENCIA
    # =====================================================

    configuracion_asistencia = None

    if usuario is not None:

        configuracion_asistencia = (
            ConfiguracionAsistenciaUsuario.objects
            .filter(
                usuario=usuario
            )
            .first()
        )

    asistencia_tiene_pin = bool(
        configuracion_asistencia
        and configuracion_asistencia.tiene_pin
    )

    asistencia_error = None

    # =====================================================
    # POST
    # =====================================================

    if request.method == "POST":

        form = UsuarioForm(
            request.POST,
            instance=usuario,
        )

        # =================================================
        # ASISTENCIA
        # =================================================

        asistencia_habilitada = (
            request.POST.get(
                "asistencia_habilitada"
            )
            == "on"
        )

        pin_asistencia = (
            request.POST.get(
                "pin_asistencia",
                "",
            )
            .strip()
        )

        # =================================================
        # VALIDAR FORMULARIO
        # =================================================

        if form.is_valid():

            # ---------------------------------------------
            # USUARIO NUEVO DEBE TENER CONTRASEÑA ERP
            # ---------------------------------------------

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

                # =========================================
                # VALIDAR ASISTENCIA
                # =========================================

                if asistencia_habilitada:

                    # -------------------------------------
                    # SE INGRESÓ UN PIN
                    # -------------------------------------

                    if pin_asistencia:

                        if (
                            not pin_asistencia.isdigit()
                            or len(
                                pin_asistencia
                            ) != 4
                        ):

                            asistencia_error = (
                                "El PIN de asistencia debe "
                                "tener exactamente 4 dígitos."
                            )

                    # -------------------------------------
                    # NO SE INGRESÓ PIN
                    # -------------------------------------
                    #
                    # Si ya tenía uno, puede dejarlo vacío.
                    #
                    # Si todavía no tiene PIN, es obligatorio.
                    # -------------------------------------

                    elif not asistencia_tiene_pin:

                        asistencia_error = (
                            "Debes configurar un PIN "
                            "de asistencia de 4 dígitos."
                        )

                # =========================================
                # GUARDAR
                # =========================================

                if asistencia_error is None:

                    with transaction.atomic():

                        # ---------------------------------
                        # GUARDAR USUARIO
                        # ---------------------------------

                        usuario_guardado = (
                            form.save()
                        )

                        # ---------------------------------
                        # ASISTENCIA HABILITADA
                        # ---------------------------------

                        if asistencia_habilitada:

                            (
                                config_asistencia,
                                _
                            ) = (
                                ConfiguracionAsistenciaUsuario
                                .objects
                                .get_or_create(
                                    usuario=usuario_guardado,
                                    defaults={
                                        "habilitado": True,
                                    },
                                )
                            )

                            config_asistencia.habilitado = (
                                True
                            )

                            # ---------------------------------
                            # NUEVO PIN
                            # ---------------------------------
                            #
                            # Solo se modifica si el campo
                            # contiene un nuevo PIN.
                            # ---------------------------------

                            if pin_asistencia:

                                config_asistencia.set_pin(
                                    pin_asistencia
                                )

                            config_asistencia.save()

                        # ---------------------------------
                        # ASISTENCIA DESHABILITADA
                        # ---------------------------------

                        else:

                            config_asistencia = (
                                ConfiguracionAsistenciaUsuario
                                .objects
                                .filter(
                                    usuario=usuario_guardado
                                )
                                .first()
                            )

                            if (
                                config_asistencia
                                is not None
                            ):

                                config_asistencia.habilitado = (
                                    False
                                )

                                config_asistencia.save(
                                    update_fields=[
                                        "habilitado",
                                    ]
                                )

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

        asistencia_habilitada = bool(
            configuracion_asistencia
            and configuracion_asistencia.habilitado
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

            "asistencia_habilitada": (
                asistencia_habilitada
            ),

            "asistencia_tiene_pin": (
                asistencia_tiene_pin
            ),

            "asistencia_error": (
                asistencia_error
            ),
        },
    )
# =========================================================
# HABILITAR / DESHABILITAR USUARIO
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
    # NO DESHABILITAR LA PROPIA CUENTA
    # =====================================================

    if usuario.pk == request.user.pk:
        messages.error(
            request,
            (
                "No puedes cambiar el estado "
                "de tu propia cuenta."
            ),
        )

        return redirect(
            "editar_usuario",
            pk=usuario.pk,
        )

    # =====================================================
    # PROTEGER SUPERUSUARIOS
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
            "editar_usuario",
            pk=usuario.pk,
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
                    "No puedes deshabilitar "
                    "el último superusuario activo."
                ),
            )

            return redirect(
                "editar_usuario",
                pk=usuario.pk,
            )

    # =====================================================
    # HABILITAR
    # =====================================================

    if not usuario.is_active:
        usuario.is_active = True

        usuario.save(
            update_fields=[
                "is_active",
            ]
        )

        messages.success(
            request,
            (
                f'El usuario "{usuario.username}" '
                "fue habilitado correctamente."
            ),
        )

        return redirect(
            "editar_usuario",
            pk=usuario.pk,
        )

    # =====================================================
    # DESHABILITAR
    # =====================================================

    usuario.is_active = False

    usuario.save(
        update_fields=[
            "is_active",
        ]
    )

    # Al deshabilitarlo también se cierran
    # inmediatamente todas sus sesiones.
    sesiones_cerradas = (
        cerrar_sesiones_de_usuario(
            usuario
        )
    )

    messages.success(
        request,
        (
            f'El usuario "{usuario.username}" '
            "fue deshabilitado correctamente. "
            f"Se cerraron {sesiones_cerradas} "
            "sesiones activas."
        ),
    )

    return redirect(
        "editar_usuario",
        pk=usuario.pk,
    )


# =========================================================
# CERRAR SESIONES DE UN USUARIO
# =========================================================

@permiso_requerido(
    "inventario.change_usuario"
)
@require_POST
def cerrar_sesiones_usuario(
    request,
    pk,
):
    usuario = get_object_or_404(
        Usuario,
        pk=pk,
    )

    # =====================================================
    # PROTEGER SUPERUSUARIOS
    # =====================================================

    if (
        usuario.is_superuser
        and not request.user.is_superuser
    ):
        messages.error(
            request,
            (
                "Solo un superusuario puede "
                "cerrar las sesiones de otro "
                "superusuario."
            ),
        )

        return redirect(
            "editar_usuario",
            pk=usuario.pk,
        )

    # =====================================================
    # CERRAR SESIONES
    # =====================================================

    sesiones_cerradas = (
        cerrar_sesiones_de_usuario(
            usuario
        )
    )

    # =====================================================
    # SI CERRÓ SUS PROPIAS SESIONES
    # =====================================================

    if usuario.pk == request.user.pk:
        return redirect(
            "login"
        )

    # =====================================================
    # MENSAJE
    # =====================================================

    if sesiones_cerradas:
        messages.success(
            request,
            (
                f"Se cerraron "
                f"{sesiones_cerradas} "
                f"sesiones del usuario "
                f'"{usuario.username}".'
            ),
        )

    else:
        messages.info(
            request,
            (
                f'El usuario "{usuario.username}" '
                "no tenía sesiones activas."
            ),
        )

    return redirect(
        "editar_usuario",
        pk=usuario.pk,
    )