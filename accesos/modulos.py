from collections import OrderedDict

from django.contrib.auth.models import Permission
from django.db.models import Q


# =========================================================
# ACCIONES ESTÁNDAR
# =========================================================

ACCIONES_MODULO = OrderedDict([
    ("view", "Acceso / Ver"),
    ("add", "Crear"),
    ("change", "Editar"),
    ("delete", "Eliminar"),
])


# =========================================================
# MÓDULOS DE NEGOCIO MAO
# =========================================================
#
# IMPORTANTE:
#
# - No crea permisos nuevos.
# - Sigue usando los Permission nativos de Django.
# - Sirve para agrupar los permisos técnicos en módulos
#   comprensibles para la administración del ERP.
# - Las aplicaciones nuevas que no estén aquí se detectan
#   automáticamente desde accesos/views.py.
# =========================================================

MODULOS_MAO = OrderedDict([

    (
        "operacion_taller",
        {
            "nombre": "Operación Taller",
            "descripcion": (
                "Órdenes de trabajo, clientes, vehículos, "
                "servicios y operación diaria del taller."
            ),
            "icono": "bi-tools",
            "selectores": [
                {
                    "app_label": "ordenes_de_trabajo",
                    "excluir_modelos": {
                        "cotizacion",
                        "cotizacioninsumodetalle",
                        "cotizacionserviciodetalle",
                        "cotizacionprocedimientodetalle",
                    },
                },
                {
                    "app_label": "servicios",
                },
            ],
        },
    ),

    (
        "cotizaciones",
        {
            "nombre": "Cotizaciones / Proformas",
            "descripcion": (
                "Proformas para clientes, revisiones, "
                "aprobaciones y traslado a órdenes de trabajo."
            ),
            "icono": "bi-file-earmark-text",
            "selectores": [
                {
                    "app_label": "ordenes_de_trabajo",
                    "incluir_modelos": {
                        "cotizacion",
                        "cotizacioninsumodetalle",
                        "cotizacionserviciodetalle",
                        "cotizacionprocedimientodetalle",
                    },
                },
            ],
        },
    ),

    (
        "cotizaciones_proveedor",
        {
            "nombre": "Cotizaciones de Proveedores",
            "descripcion": (
                "Solicitudes y comparaciones de cotización "
                "para compras a proveedores."
            ),
            "icono": "bi-chat-square-text",
            "selectores": [
                {
                    "app_label": "cotizaciones",
                },
            ],
        },
    ),

    (
        "avaluos",
        {
            "nombre": "Avalúos",
            "descripcion": (
                "Inspecciones, avalúos mecánicos y "
                "documentación relacionada."
            ),
            "icono": "bi-clipboard2-pulse",
            "selectores": [
                {
                    "app_label": "avaluos",
                },
            ],
        },
    ),

    (
        "inventario",
        {
            "nombre": "Inventario",
            "descripcion": (
                "Productos, catálogo, stock, movimientos "
                "e inventario físico."
            ),
            "icono": "bi-box-seam",
            "selectores": [
                {
                    "app_label": "inventario",
                    "excluir_modelos": {
                        "usuario",
                    },
                },
            ],
        },
    ),

    (
        "compras",
        {
            "nombre": "Compras",
            "descripcion": (
                "Proveedores, documentos y procesos "
                "relacionados con compras."
            ),
            "icono": "bi-cart3",
            "selectores": [
                {
                    "app_label": "compras",
                },
            ],
        },
    ),

    (
        "facturacion",
        {
            "nombre": "Facturación",
            "descripcion": (
                "Facturas, borradores, emisión electrónica, "
                "SRI, pagos y documentos relacionados."
            ),
            "icono": "bi-receipt",
            "selectores": [
                {
                    "app_label": "facturacion",
                },
            ],
        },
    ),

    (
        "contabilidad",
        {
            "nombre": "Contabilidad",
            "descripcion": (
                "Registros, asientos y procesos del "
                "módulo contable."
            ),
            "icono": "bi-calculator",
            "selectores": [
                {
                    "app_label": "contabilidad",
                },
            ],
        },
    ),

    (
        "asistencia",
        {
            "nombre": "Asistencia",
            "descripcion": (
                "Administración de horarios, marcaciones, "
                "incidencias y terminales."
            ),
            "icono": "bi-clock-history",
            "selectores": [
                {
                    "app_label": "asistencia",
                },
            ],
        },
    ),

    (
        "administracion",
        {
            "nombre": "Administración",
            "descripcion": (
                "Usuarios, roles, permisos y configuración "
                "general del ERP."
            ),
            "icono": "bi-shield-lock",
            "selectores": [
                {
                    "app_label": "inventario",
                    "incluir_modelos": {
                        "usuario",
                    },
                },
                {
                    "app_label": "accesos",
                    "excluir_modelos": {
                        "permiso",
                    },
                },
                {
                    "app_label": "empresa",
                },
            ],
        },
    ),
])


# =========================================================
# SELECTORES
# =========================================================

def permiso_coincide_selector(permission, selector):
    app_label = selector.get("app_label")

    if (
        app_label
        and permission.content_type.app_label != app_label
    ):
        return False

    model_name = permission.content_type.model

    incluir_modelos = set(
        selector.get("incluir_modelos", set())
    )

    excluir_modelos = set(
        selector.get("excluir_modelos", set())
    )

    if (
        incluir_modelos
        and model_name not in incluir_modelos
    ):
        return False

    if (
        excluir_modelos
        and model_name in excluir_modelos
    ):
        return False

    return True


def buscar_modulo_configurado(permission):
    """
    Retorna:
        (clave, configuracion)

    Si el permiso no pertenece a un módulo configurado,
    retorna:
        (None, None)
    """

    for clave, configuracion in MODULOS_MAO.items():

        for selector in configuracion.get(
            "selectores",
            [],
        ):
            if permiso_coincide_selector(
                permission,
                selector,
            ):
                return clave, configuracion

    return None, None


# =========================================================
# QUERYS DE PERMISOS
# =========================================================

def _query_selector(selector):
    app_label = selector.get("app_label")

    query = Q(
        content_type__app_label=app_label
    )

    incluir_modelos = set(
        selector.get("incluir_modelos", set())
    )

    excluir_modelos = set(
        selector.get("excluir_modelos", set())
    )

    if incluir_modelos:
        query &= Q(
            content_type__model__in=incluir_modelos
        )

    if excluir_modelos:
        query &= ~Q(
            content_type__model__in=excluir_modelos
        )

    return query


def permisos_del_modulo(clave):
    modulo = MODULOS_MAO.get(clave)

    if not modulo:
        return Permission.objects.none()

    selectores = modulo.get(
        "selectores",
        [],
    )

    if not selectores:
        return Permission.objects.none()

    query_total = Q()

    for selector in selectores:
        query_total |= _query_selector(
            selector
        )

    return (
        Permission.objects
        .select_related("content_type")
        .filter(query_total)
        .exclude(
            content_type__app_label__in=[
                "admin",
                "auth",
                "contenttypes",
                "sessions",
            ]
        )
        .distinct()
    )


def permisos_accion_modulo(
    clave,
    accion,
):
    if accion not in ACCIONES_MODULO:
        return Permission.objects.none()

    return (
        permisos_del_modulo(clave)
        .filter(
            codename__startswith=f"{accion}_"
        )
    )


def nombres_permisos_accion(
    clave,
    accion,
):
    return {
        (
            f"{permiso.content_type.app_label}."
            f"{permiso.codename}"
        )
        for permiso
        in permisos_accion_modulo(
            clave,
            accion,
        )
    }


# =========================================================
# COMPROBACIÓN DE ACCESO
# =========================================================

def usuario_tiene_modulo(
    usuario,
    clave,
):
    """
    Un módulo se considera visible cuando el usuario tiene
    al menos un permiso view_* perteneciente al módulo.

    El superusuario siempre tiene acceso.
    """

    if not usuario:
        return False

    if not usuario.is_authenticated:
        return False

    if usuario.is_superuser:
        return True

    permisos_view = nombres_permisos_accion(
        clave,
        "view",
    )

    if not permisos_view:
        return False

    permisos_usuario = usuario.get_all_permissions()

    return bool(
        permisos_view.intersection(
            permisos_usuario
        )
    )


def usuario_tiene_accion(
    usuario,
    clave,
    accion,
):
    if not usuario:
        return False

    if not usuario.is_authenticated:
        return False

    if usuario.is_superuser:
        return True

    permisos_accion = nombres_permisos_accion(
        clave,
        accion,
    )

    if not permisos_accion:
        return False

    permisos_usuario = usuario.get_all_permissions()

    return bool(
        permisos_accion.intersection(
            permisos_usuario
        )
    )
