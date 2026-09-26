from collections import OrderedDict

from django.apps import apps
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.sessions.models import Session
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import RolForm
from .models import Rol
from .modulos import (
    ACCIONES_MODULO,
    MODULOS_MAO,
    buscar_modulo_configurado,
)
from .permissions import permiso_requerido


# =========================================================
# CONFIGURACIÓN
# =========================================================

ACCIONES_PERMISO = ACCIONES_MODULO


# =========================================================
# UTILIDADES DE NOMBRES
# =========================================================

def _nombre_aplicacion(app_label):
    try:
        config = apps.get_app_config(
            app_label
        )
        return str(config.verbose_name)

    except LookupError:
        return (
            app_label
            .replace("_", " ")
            .strip()
            .title()
        )


def _nombre_modelo(permission):
    model_class = (
        permission.content_type.model_class()
    )

    if model_class is not None:
        nombre = str(
            model_class._meta.verbose_name
        )
        return nombre[:1].upper() + nombre[1:]

    nombre = (
        permission.content_type.model
        .replace("_", " ")
        .strip()
    )

    return nombre[:1].upper() + nombre[1:]


def _detectar_accion(permission):
    codename = permission.codename

    for accion in ACCIONES_PERMISO.keys():

        if codename.startswith(
            f"{accion}_"
        ):
            return accion

    return "custom"


def _ids_permisos_seleccionados(form):
    valores = (
        form["permissions"].value()
        or []
    )

    return {
        str(valor)
        for valor in valores
    }


# =========================================================
# ESTRUCTURAS DE MÓDULO
# =========================================================

def _crear_modulo(
    clave,
    nombre,
    descripcion="",
    icono="bi-grid",
    automatico=False,
    app_label=None,
):
    return {
        "clave": clave,
        "nombre": nombre,
        "descripcion": descripcion,
        "icono": icono,
        "automatico": automatico,
        "app_label": app_label,

        "modelos": OrderedDict(),

        "total": 0,
        "seleccionados": 0,

        "acciones": OrderedDict(
            (
                accion,
                {
                    "clave": accion,
                    "nombre": nombre_accion,
                    "ids": [],
                    "ids_csv": "",
                    "total": 0,
                    "seleccionados": 0,
                    "todos_seleccionados": False,
                    "alguno_seleccionado": False,
                },
            )
            for accion, nombre_accion
            in ACCIONES_PERMISO.items()
        ),

        "otros": [],
    }


def _crear_modelo(
    model_name,
    nombre,
):
    return {
        "model": model_name,
        "nombre": nombre,

        "view": None,
        "add": None,
        "change": None,
        "delete": None,

        "otros": [],

        "total": 0,
        "seleccionados": 0,
    }


# =========================================================
# MATRIZ DE PERMISOS POR MÓDULOS
# =========================================================

def construir_matriz_permisos(form):
    """
    Construye una matriz orientada a módulos MAO.

    Las apps conocidas se agrupan mediante modulos.py.

    Una app nueva que no esté registrada en modulos.py
    aparece automáticamente como un nuevo módulo.
    """

    seleccionados = (
        _ids_permisos_seleccionados(
            form
        )
    )

    permisos = (
        form.fields["permissions"]
        .queryset
        .select_related("content_type")
        .order_by(
            "content_type__app_label",
            "content_type__model",
            "codename",
        )
    )

    modulos = OrderedDict()

    # -----------------------------------------------------
    # MÓDULOS CONFIGURADOS
    # -----------------------------------------------------

    for clave, configuracion in (
        MODULOS_MAO.items()
    ):

        modulos[clave] = _crear_modulo(
            clave=clave,
            nombre=configuracion.get(
                "nombre",
                clave.replace(
                    "_",
                    " ",
                ).title(),
            ),
            descripcion=configuracion.get(
                "descripcion",
                "",
            ),
            icono=configuracion.get(
                "icono",
                "bi-grid",
            ),
            automatico=False,
        )

    # -----------------------------------------------------
    # RECORRER PERMISOS
    # -----------------------------------------------------

    for permiso in permisos:

        app_label = (
            permiso.content_type.app_label
        )

        model_name = (
            permiso.content_type.model
        )

        seleccionado = (
            str(permiso.pk)
            in seleccionados
        )

        clave_modulo, _ = (
            buscar_modulo_configurado(
                permiso
            )
        )

        # ---------------------------------------------
        # APP NUEVA / MÓDULO AUTOMÁTICO
        # ---------------------------------------------

        if not clave_modulo:

            clave_modulo = (
                f"auto__{app_label}"
            )

            if clave_modulo not in modulos:

                modulos[clave_modulo] = (
                    _crear_modulo(
                        clave=clave_modulo,
                        nombre=_nombre_aplicacion(
                            app_label
                        ),
                        descripcion=(
                            "Módulo detectado "
                            "automáticamente desde Django."
                        ),
                        icono="bi-grid",
                        automatico=True,
                        app_label=app_label,
                    )
                )

        modulo = modulos[
            clave_modulo
        ]

        modulo["total"] += 1

        if seleccionado:
            modulo["seleccionados"] += 1

        # ---------------------------------------------
        # MODELO
        # ---------------------------------------------

        if model_name not in modulo["modelos"]:

            modulo["modelos"][model_name] = (
                _crear_modelo(
                    model_name=model_name,
                    nombre=_nombre_modelo(
                        permiso
                    ),
                )
            )

        modelo = modulo["modelos"][
            model_name
        ]

        modelo["total"] += 1

        if seleccionado:
            modelo["seleccionados"] += 1

        # ---------------------------------------------
        # PERMISO
        # ---------------------------------------------

        info = {
            "id": permiso.pk,
            "codename": permiso.codename,
            "nombre": permiso.name,
            "app_label": app_label,
            "model": model_name,
            "permiso_completo": (
                f"{app_label}."
                f"{permiso.codename}"
            ),
            "seleccionado": seleccionado,
        }

        accion = _detectar_accion(
            permiso
        )

        if accion in ACCIONES_PERMISO:

            modelo[accion] = info

            resumen = (
                modulo["acciones"][
                    accion
                ]
            )

            resumen["ids"].append(
                permiso.pk
            )

            resumen["total"] += 1

            if seleccionado:
                resumen[
                    "seleccionados"
                ] += 1

        else:

            modelo["otros"].append(
                info
            )

            modulo["otros"].append(
                info
            )

    # -----------------------------------------------------
    # ELIMINAR MÓDULOS VACÍOS Y FINALIZAR
    # -----------------------------------------------------

    resultado = []

    for modulo in modulos.values():

        if modulo["total"] <= 0:
            continue

        for accion in (
            modulo["acciones"].values()
        ):

            accion[
                "alguno_seleccionado"
            ] = (
                accion["seleccionados"] > 0
            )

            accion[
                "todos_seleccionados"
            ] = (
                accion["total"] > 0
                and
                accion["seleccionados"]
                == accion["total"]
            )

            accion["ids_csv"] = ",".join(
                str(pk)
                for pk in accion["ids"]
            )

        accion_view = (
            modulo["acciones"]["view"]
        )

        modulo["acceso"] = {
            "ids": accion_view["ids"],
            "ids_csv":
                accion_view["ids_csv"],
            "total":
                accion_view["total"],
            "seleccionados":
                accion_view[
                    "seleccionados"
                ],
            "activo":
                accion_view[
                    "alguno_seleccionado"
                ],
            "completo":
                accion_view[
                    "todos_seleccionados"
                ],
        }

        modulo[
            "todos_seleccionados"
        ] = (
            modulo["total"] > 0
            and
            modulo["seleccionados"]
            == modulo["total"]
        )

        modulo[
            "alguno_seleccionado"
        ] = (
            modulo["seleccionados"] > 0
        )

        modulo["modelos"] = list(
            modulo["modelos"].values()
        )

        resultado.append(
            modulo
        )

    return resultado


# =========================================================
# NORMALIZAR PERMISOS
# =========================================================

def _agregar_view_a_acciones(
    permisos_seleccionados,
):
    """
    Evita roles inconsistentes.

    Si se concede:
        add_modelo
        change_modelo
        delete_modelo

    se concede automáticamente:
        view_modelo

    Así nadie puede crear/editar/eliminar un recurso sin
    tener al menos permiso de lectura sobre ese recurso.
    """

    seleccionados = list(
        permisos_seleccionados
    )

    ids = {
        permiso.pk
        for permiso in seleccionados
    }

    extras = []

    for permiso in seleccionados:

        accion = _detectar_accion(
            permiso
        )

        if accion not in {
            "add",
            "change",
            "delete",
        }:
            continue

        modelo = (
            permiso.content_type.model
        )

        view_permiso = (
            Permission.objects
            .filter(
                content_type=
                    permiso.content_type,
                codename=f"view_{modelo}",
            )
            .first()
        )

        if (
            view_permiso
            and view_permiso.pk not in ids
        ):
            extras.append(
                view_permiso
            )
            ids.add(
                view_permiso.pk
            )

    return seleccionados + extras


# =========================================================
# GUARDAR ROL
# =========================================================

def _guardar_rol(form):
    """
    Guarda el rol y conserva permisos internos que no forman
    parte del queryset editable del formulario.
    """

    permisos_editables = (
        form.fields["permissions"]
        .queryset
    )

    ids_editables = set(
        permisos_editables
        .values_list(
            "pk",
            flat=True,
        )
    )

    permisos_protegidos_ids = []

    if (
        form.instance
        and form.instance.pk
    ):

        permisos_protegidos_ids = list(
            form.instance.permissions
            .exclude(
                pk__in=ids_editables
            )
            .values_list(
                "pk",
                flat=True,
            )
        )

    rol = form.save()

    seleccionados = (
        form.cleaned_data.get(
            "permissions"
        )
        or Permission.objects.none()
    )

    normalizados = (
        _agregar_view_a_acciones(
            seleccionados
        )
    )

    ids_finales = {
        permiso.pk
        for permiso in normalizados
        if permiso.pk in ids_editables
    }

    ids_finales.update(
        permisos_protegidos_ids
    )

    rol.permissions.set(
        ids_finales
    )

    return rol


# =========================================================
# CONTEXTO DEL FORMULARIO
# =========================================================

def _contexto_formulario(
    form,
    rol,
    titulo,
):
    matriz = construir_matriz_permisos(
        form
    )

    total_permisos = sum(
        modulo["total"]
        for modulo in matriz
    )

    total_seleccionados = sum(
        modulo["seleccionados"]
        for modulo in matriz
    )

    modulos_con_acceso = sum(
        1
        for modulo in matriz
        if modulo["acceso"]["activo"]
    )

    return {
        "form": form,
        "rol": rol,
        "titulo": titulo,

        "modulos_permisos":
            matriz,

        # Compatibilidad temporal
        "permisos_agrupados":
            matriz,

        "total_permisos":
            total_permisos,

        "total_seleccionados":
            total_seleccionados,

        "total_modulos":
            len(matriz),

        "modulos_con_acceso":
            modulos_con_acceso,

        "acciones_permiso":
            ACCIONES_PERMISO,
    }


# =========================================================
# LISTA DE ROLES
# =========================================================

@permiso_requerido(
    "accesos.view_rol"
)
def roles_lista(request):

    Usuario = get_user_model()

    roles = list(
        Rol.objects
        .prefetch_related(
            "permissions"
        )
        .order_by(
            "name"
        )
    )

    usuarios_por_rol = {
        fila["groups"]: fila["total"]
        for fila in (
            Usuario.objects
            .filter(
                groups__isnull=False
            )
            .values(
                "groups"
            )
            .annotate(
                total=Count(
                    "pk",
                    distinct=True,
                )
            )
        )
    }

    for rol in roles:

        rol.usuarios_count = (
            usuarios_por_rol.get(
                rol.pk,
                0,
            )
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

@permiso_requerido(
    "accesos.add_rol"
)
def rol_crear(request):

    if request.method == "POST":

        form = RolForm(
            request.POST
        )

        if form.is_valid():

            with transaction.atomic():

                rol = _guardar_rol(
                    form
                )

            messages.success(
                request,
                (
                    f'El rol "{rol.name}" '
                    "fue creado correctamente."
                ),
            )

            return redirect(
                "accesos:roles_lista"
            )

    else:

        form = RolForm()

    contexto = _contexto_formulario(
        form=form,
        rol=None,
        titulo="Nuevo rol",
    )

    return render(
        request,
        "accesos/rol_form.html",
        contexto,
    )


# =========================================================
# EDITAR ROL
# =========================================================

@permiso_requerido(
    "accesos.change_rol"
)
def rol_editar(request, pk):

    rol = get_object_or_404(
        Rol.objects.prefetch_related(
            "permissions"
        ),
        pk=pk,
    )

    if request.method == "POST":

        form = RolForm(
            request.POST,
            instance=rol,
        )

        if form.is_valid():

            with transaction.atomic():

                rol = _guardar_rol(
                    form
                )

            messages.success(
                request,
                (
                    f'El rol "{rol.name}" '
                    "fue actualizado correctamente."
                ),
            )

            return redirect(
                "accesos:roles_lista"
            )

    else:

        form = RolForm(
            instance=rol
        )

    contexto = _contexto_formulario(
        form=form,
        rol=rol,
        titulo=f"Editar rol: {rol.name}",
    )

    return render(
        request,
        "accesos/rol_form.html",
        contexto,
    )


# =========================================================
# ELIMINAR ROL
# =========================================================

@permiso_requerido(
    "accesos.delete_rol"
)
def rol_eliminar(request, pk):

    rol = get_object_or_404(
        Rol,
        pk=pk,
    )

    Usuario = get_user_model()

    usuarios_asignados = (
        Usuario.objects
        .filter(
            groups=rol
        )
        .order_by(
            "username"
        )
    )

    if request.method == "POST":

        if usuarios_asignados.exists():

            messages.error(
                request,
                (
                    "No se puede eliminar el rol "
                    f'"{rol.name}" porque todavía '
                    "tiene usuarios asignados."
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
            (
                f'El rol "{nombre}" '
                "fue eliminado correctamente."
            ),
        )

        return redirect(
            "accesos:roles_lista"
        )

    return render(
        request,
        "accesos/rol_confirmar_eliminar.html",
        {
            "rol": rol,
            "usuarios_asignados":
                usuarios_asignados,
        },
    )


# =========================================================
# SEGURIDAD
# =========================================================

@permiso_requerido(
    "accesos.cerrar_todas_sesiones"
)
@require_POST
def seguridad(request):

    confirmacion = (
        request.POST
        .get(
            "confirmacion",
            "",
        )
        .strip()
        .upper()
    )

    if (
        confirmacion
        != "CERRAR SESIONES"
    ):

        messages.error(
            request,
            (
                "La confirmación no es correcta. "
                'Debes escribir "CERRAR SESIONES".'
            ),
        )

        return redirect(
            "lista_usuarios"
        )

    Session.objects.all().delete()

    return redirect(
        "login"
    )
