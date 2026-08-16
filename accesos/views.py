from collections import OrderedDict

from django.apps import apps
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from .forms import RolForm
from .models import Rol
from .permissions import permiso_requerido


# =========================================================
# CONFIGURACIÓN DE ACCIONES
# =========================================================

ACCIONES_PERMISO = OrderedDict([
    ("view", "Ver"),
    ("add", "Crear"),
    ("change", "Editar"),
    ("delete", "Eliminar"),
])


# =========================================================
# UTILIDADES
# =========================================================

def _nombre_aplicacion(app_label):
    """
    Devuelve el verbose_name de la aplicación.

    Ejemplo:
        ordenes_de_trabajo -> Ordenes De Trabajo
        inventario         -> Inventario
    """

    try:
        config = apps.get_app_config(app_label)
        return str(config.verbose_name)

    except LookupError:
        return (
            app_label
            .replace("_", " ")
            .strip()
            .title()
        )


def _nombre_modelo(permission):
    """
    Obtiene un nombre amigable para el modelo asociado
    al permiso.
    """

    model_class = permission.content_type.model_class()

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
    """
    Determina si un permiso es:
        view
        add
        change
        delete

    Si es un permiso personalizado devuelve "custom".
    """

    codename = permission.codename

    for accion in ACCIONES_PERMISO.keys():

        prefijo = f"{accion}_"

        if codename.startswith(prefijo):
            return accion

    return "custom"


def _ids_permisos_seleccionados(form):
    """
    Obtiene los IDs actualmente seleccionados.

    Funciona tanto:
        - al crear
        - al editar
        - después de un POST inválido
    """

    valores = form["permissions"].value() or []

    return {
        str(valor)
        for valor in valores
    }


# =========================================================
# MATRIZ DE PERMISOS
# =========================================================

def construir_matriz_permisos(form):
    """
    Convierte la lista plana de Permission de Django en:

        Aplicación
            └── Modelo
                    ├── Ver
                    ├── Crear
                    ├── Editar
                    └── Eliminar

    Esto permite mostrar los permisos en una tabla compacta
    en lugar de cientos de checkboxes individuales.
    """

    seleccionados = _ids_permisos_seleccionados(form)

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

    aplicaciones = OrderedDict()

    # =====================================================
    # RECORRER PERMISOS
    # =====================================================

    for permiso in permisos:

        app_label = permiso.content_type.app_label
        model_name = permiso.content_type.model

        permiso_seleccionado = (
            str(permiso.pk) in seleccionados
        )

        # -------------------------------------------------
        # APLICACIÓN
        # -------------------------------------------------

        if app_label not in aplicaciones:

            aplicaciones[app_label] = {
                "app_label": app_label,
                "nombre": _nombre_aplicacion(app_label),

                "modelos": OrderedDict(),

                "total": 0,
                "seleccionados": 0,
            }

        aplicacion = aplicaciones[app_label]

        aplicacion["total"] += 1

        if permiso_seleccionado:
            aplicacion["seleccionados"] += 1

        # -------------------------------------------------
        # MODELO
        # -------------------------------------------------

        if model_name not in aplicacion["modelos"]:

            aplicacion["modelos"][model_name] = {
                "model": model_name,
                "nombre": _nombre_modelo(permiso),

                "view": None,
                "add": None,
                "change": None,
                "delete": None,

                "otros": [],

                "total": 0,
                "seleccionados": 0,
            }

        modelo = aplicacion["modelos"][model_name]

        modelo["total"] += 1

        if permiso_seleccionado:
            modelo["seleccionados"] += 1

        # -------------------------------------------------
        # INFORMACIÓN DEL PERMISO
        # -------------------------------------------------

        info_permiso = {
            "id": permiso.pk,
            "codename": permiso.codename,
            "nombre": permiso.name,
            "seleccionado": permiso_seleccionado,
        }

        accion = _detectar_accion(permiso)

        # -------------------------------------------------
        # PERMISOS ESTÁNDAR
        # -------------------------------------------------

        if accion in ACCIONES_PERMISO:

            modelo[accion] = info_permiso

        # -------------------------------------------------
        # PERMISOS PERSONALIZADOS
        # -------------------------------------------------

        else:

            modelo["otros"].append(
                info_permiso
            )

    # =====================================================
    # CONVERTIR DICTS INTERNOS EN LISTAS
    # =====================================================

    resultado = []

    for aplicacion in aplicaciones.values():

        aplicacion["modelos"] = list(
            aplicacion["modelos"].values()
        )

        resultado.append(
            aplicacion
        )

    return resultado


# =========================================================
# GUARDAR ROL
# =========================================================

def _guardar_rol(form):
    """
    Guarda el RolForm sin perder permisos que no están
    incluidos dentro del queryset editable del formulario.

    Esto es especialmente importante para permisos internos
    o administrativos que hayamos decidido ocultar del editor.
    """

    permisos_protegidos_ids = []

    # =====================================================
    # SI ESTAMOS EDITANDO
    # =====================================================

    if form.instance and form.instance.pk:

        permisos_editables = (
            form.fields["permissions"]
            .queryset
        )

        permisos_protegidos_ids = list(
            form.instance.permissions
            .exclude(
                pk__in=permisos_editables.values("pk")
            )
            .values_list(
                "pk",
                flat=True,
            )
        )

    # =====================================================
    # GUARDAR FORMULARIO
    # =====================================================

    rol = form.save()

    # =====================================================
    # RESTAURAR PERMISOS PROTEGIDOS
    # =====================================================

    if permisos_protegidos_ids:

        rol.permissions.add(
            *permisos_protegidos_ids
        )

    return rol


# =========================================================
# CONTEXTO DEL FORMULARIO
# =========================================================

def _contexto_formulario(form, rol, titulo):
    """
    Contexto común para crear y editar un rol.
    """

    matriz = construir_matriz_permisos(
        form
    )

    total_permisos = sum(
        aplicacion["total"]
        for aplicacion in matriz
    )

    total_seleccionados = sum(
        aplicacion["seleccionados"]
        for aplicacion in matriz
    )

    return {
        "form": form,
        "rol": rol,
        "titulo": titulo,

        "permisos_agrupados": matriz,

        "total_permisos": total_permisos,
        "total_seleccionados": total_seleccionados,

        "acciones_permiso": ACCIONES_PERMISO,
    }


# =========================================================
# LISTA DE ROLES
# =========================================================

@permiso_requerido("accesos.view_rol")
def roles_lista(request):

    Usuario = get_user_model()

    # -----------------------------------------------------
    # ROLES
    # -----------------------------------------------------

    roles = list(
        Rol.objects
        .prefetch_related("permissions")
        .order_by("name")
    )

    # -----------------------------------------------------
    # CANTIDAD DE USUARIOS POR ROL
    #
    # Se consulta desde Usuario.groups para no depender
    # del related_name inverso configurado en Usuario.
    # -----------------------------------------------------

    usuarios_por_rol = {
        fila["groups"]: fila["total"]
        for fila in (
            Usuario.objects
            .filter(groups__isnull=False)
            .values("groups")
            .annotate(
                total=Count(
                    "pk",
                    distinct=True,
                )
            )
        )
    }

    # -----------------------------------------------------
    # AGREGAR CONTEO A CADA ROL
    # -----------------------------------------------------

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

@permiso_requerido("accesos.add_rol")
def rol_crear(request):

    # =====================================================
    # POST
    # =====================================================

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

    # =====================================================
    # GET
    # =====================================================

    else:

        form = RolForm()

    # =====================================================
    # RENDER
    # =====================================================

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

@permiso_requerido("accesos.change_rol")
def rol_editar(request, pk):

    rol = get_object_or_404(
        Rol.objects.prefetch_related(
            "permissions"
        ),
        pk=pk,
    )

    # =====================================================
    # POST
    # =====================================================

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

    # =====================================================
    # GET
    # =====================================================

    else:

        form = RolForm(
            instance=rol
        )

    # =====================================================
    # RENDER
    # =====================================================

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

@permiso_requerido("accesos.delete_rol")
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

    # =====================================================
    # CONFIRMAR ELIMINACIÓN
    # =====================================================

    if request.method == "POST":

        # -------------------------------------------------
        # NO ELIMINAR SI TIENE USUARIOS
        # -------------------------------------------------

        if usuarios_asignados.exists():

            messages.error(
                request,
                (
                    f'No se puede eliminar el rol '
                    f'"{rol.name}" porque todavía '
                    "tiene usuarios asignados."
                ),
            )

            return redirect(
                "accesos:roles_lista"
            )

        # -------------------------------------------------
        # ELIMINAR
        # -------------------------------------------------

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

    # =====================================================
    # MOSTRAR CONFIRMACIÓN
    # =====================================================

    return render(
        request,
        "accesos/rol_confirmar_eliminar.html",
        {
            "rol": rol,
            "usuarios_asignados": usuarios_asignados,
        },
    )