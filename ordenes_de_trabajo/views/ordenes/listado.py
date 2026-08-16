from django.shortcuts import render
from django.db.models import Q, Count
from django.core.paginator import Paginator

from accesos.permissions import permiso_requerido

from ...models import OrdenTrabajo, Sucursal, Tecnico
from ..utils import (
    obtener_sucursal_activa,
    usuario_puede_cambiar_sucursal,
)


# =========================================================
# UTILIDADES INTERNAS
# =========================================================

def resolver_sucursal_filtro(
    request,
    sucursal_activa,
    parametro="sucursal_filtro",
    permitir_todas=True,
):
    """
    Resuelve qué sucursal se debe consultar.

    Usuarios con permiso:
        - pueden seleccionar una sucursal
        - pueden seleccionar 'todas'

    Usuarios sin permiso:
        - siempre quedan limitados
          a su sucursal activa

    IMPORTANTE:
    Esto NO cambia la sucursal activa del usuario.
    Solo cambia qué información se consulta.
    """

    puede_cambiar = usuario_puede_cambiar_sucursal(
        request
    )

    # -----------------------------------------------------
    # USUARIO SIN PERMISO
    # -----------------------------------------------------
    if not puede_cambiar:
        if sucursal_activa:
            return str(sucursal_activa.id)

        return ""

    # -----------------------------------------------------
    # USUARIO CON PERMISO
    # -----------------------------------------------------
    sucursal_id_req = request.GET.get(parametro)

    # Entró por primera vez:
    # usamos su sucursal activa.
    if sucursal_id_req is None:
        if sucursal_activa:
            return str(sucursal_activa.id)

        return "todas" if permitir_todas else ""

    sucursal_id_req = sucursal_id_req.strip()

    # -----------------------------------------------------
    # TODAS LAS SUCURSALES
    # -----------------------------------------------------
    if (
        permitir_todas
        and sucursal_id_req == "todas"
    ):
        return "todas"

    # -----------------------------------------------------
    # SIN VALOR
    # -----------------------------------------------------
    if not sucursal_id_req:
        if sucursal_activa:
            return str(sucursal_activa.id)

        return "todas" if permitir_todas else ""

    # -----------------------------------------------------
    # VALIDAR QUE LA SUCURSAL EXISTA Y ESTÉ ACTIVA
    # -----------------------------------------------------
    existe = (
        Sucursal.objects
        .filter(
            id=sucursal_id_req,
            activa=True,
        )
        .exists()
    )

    if existe:
        return sucursal_id_req

    # Si mandaron algo inválido por URL,
    # regresamos a la sucursal activa.
    if sucursal_activa:
        return str(sucursal_activa.id)

    return "todas" if permitir_todas else ""


# =========================================================
# DASHBOARD DEL TALLER
# =========================================================

@permiso_requerido(
    "ordenes_de_trabajo.view_ordentrabajo"
)
def dashboard_taller(request):
    sucursal_activa = obtener_sucursal_activa(
        request
    )

    puede_cambiar_sucursal = (
        usuario_puede_cambiar_sucursal(request)
    )

    sucursales = (
        Sucursal.objects
        .filter(activa=True)
        .order_by("nombre")
    )

    # -----------------------------------------------------
    # SUCURSAL QUE SE ESTÁ CONSULTANDO
    # -----------------------------------------------------
    sucursal_filtro = resolver_sucursal_filtro(
        request=request,
        sucursal_activa=sucursal_activa,
        parametro="sucursal_filtro",
        permitir_todas=True,
    )

    # -----------------------------------------------------
    # ÓRDENES ABIERTAS
    # -----------------------------------------------------
    ordenes_activas = (
        OrdenTrabajo.objects
        .filter(
            estado="ABIERTA",
        )
        .select_related(
            "cliente",
            "expediente",
            "sucursal",
        )
        .annotate(
            items_count=(
                Count(
                    "insumos_detalles",
                    distinct=True,
                )
                +
                Count(
                    "servicios_detalles",
                    distinct=True,
                )
            )
        )
        .order_by(
            "-fecha_ingreso"
        )
    )

    # -----------------------------------------------------
    # FILTRAR SUCURSAL
    # -----------------------------------------------------
    if (
        not puede_cambiar_sucursal
        and not sucursal_activa
    ):
        ordenes_activas = ordenes_activas.none()

    elif (
        sucursal_filtro
        and sucursal_filtro != "todas"
    ):
        ordenes_activas = (
            ordenes_activas.filter(
                sucursal_id=sucursal_filtro,
            )
        )

    return render(
        request,
        "dashboard.html",
        {
            "ordenes_activas": ordenes_activas,

            # Sucursal real con la que trabaja el usuario
            "sucursal_activa": sucursal_activa,

            # Sucursal que está consultando
            "sucursal_filtro": sucursal_filtro,

            "sucursales": sucursales,

            "puede_cambiar_sucursal": (
                puede_cambiar_sucursal
            ),
        },
    )


# =========================================================
# LISTADO GLOBAL DE ÓRDENES
# =========================================================

@permiso_requerido(
    "ordenes_de_trabajo.view_ordentrabajo"
)
def lista_ordenes(request):
    sucursal_activa = obtener_sucursal_activa(
        request
    )

    puede_cambiar_sucursal = (
        usuario_puede_cambiar_sucursal(request)
    )

    # =====================================================
    # MAESTROS
    # =====================================================

    sucursales = (
        Sucursal.objects
        .filter(activa=True)
        .order_by("nombre")
    )

    tecnicos = (
        Tecnico.objects
        .filter(activo=True)
        .order_by("nombre")
    )

    # =====================================================
    # SUCURSAL
    # =====================================================

    sucursal_filtro = resolver_sucursal_filtro(
        request=request,
        sucursal_activa=sucursal_activa,
        parametro="sucursal_filtro",
        permitir_todas=True,
    )

    # =====================================================
    # QUERY BASE
    # =====================================================

    ordenes = (
        OrdenTrabajo.objects
        .select_related(
            "cliente",
            "sucursal",
            "usuario_receptor",
            "expediente",
        )
        .prefetch_related(
            "tecnicos",
        )
        .order_by(
            "-fecha_ingreso",
        )
    )

    # =====================================================
    # APLICAR SEGURIDAD / SUCURSAL
    # =====================================================

    if (
        not puede_cambiar_sucursal
        and not sucursal_activa
    ):
        ordenes = ordenes.none()

    elif (
        sucursal_filtro
        and sucursal_filtro != "todas"
    ):
        ordenes = ordenes.filter(
            sucursal_id=sucursal_filtro
        )

    # Este total ya respeta la sucursal
    # que el usuario puede consultar.
    total_general = ordenes.count()

    # =====================================================
    # BÚSQUEDA
    # =====================================================

    q = request.GET.get(
        "q",
        "",
    ).strip()

    if q:
        ordenes = ordenes.filter(
            Q(
                numero_orden__icontains=q
            )
            |
            Q(
                numero_orden_origen__icontains=q
            )
            |
            Q(
                placa__icontains=q
            )
            |
            Q(
                vehiculo__icontains=q
            )
            |
            Q(
                cliente__nombre_completo__icontains=q
            )
            |
            Q(
                cliente_respaldo__icontains=q
            )
        )

    # =====================================================
    # ESTADO
    # =====================================================

    estado = request.GET.get(
        "estado",
        "",
    ).strip()

    if estado:
        ordenes = ordenes.filter(
            estado=estado
        )

    # =====================================================
    # TÉCNICO
    # =====================================================

    tecnico_id = request.GET.get(
        "tecnico",
        "",
    ).strip()

    if tecnico_id:
        ordenes = ordenes.filter(
            tecnicos__id=tecnico_id
        )

    # =====================================================
    # FECHA INICIO
    # =====================================================

    fecha_inicio = request.GET.get(
        "fecha_inicio",
        "",
    ).strip()

    if fecha_inicio:
        ordenes = ordenes.filter(
            fecha_ingreso__date__gte=fecha_inicio
        )

    # =====================================================
    # FECHA FIN
    # =====================================================

    fecha_fin = request.GET.get(
        "fecha_fin",
        "",
    ).strip()

    if fecha_fin:
        ordenes = ordenes.filter(
            fecha_ingreso__date__lte=fecha_fin
        )

    # =====================================================
    # TIPO DE ORDEN
    # =====================================================

    tipo_orden = request.GET.get(
        "tipo_orden",
        "",
    ).strip()

    if tipo_orden == "normal":
        ordenes = ordenes.filter(
            es_migrada=False
        )

    elif tipo_orden == "migrada":
        ordenes = ordenes.filter(
            es_migrada=True
        )

    # =====================================================
    # EVITAR DUPLICADOS
    # =====================================================

    ordenes = ordenes.distinct()

    # =====================================================
    # TOTALES
    # =====================================================

    total_filtrado = ordenes.count()

    # =====================================================
    # FILTROS ACTIVOS
    # =====================================================

    sucursal_activa_id = (
        str(sucursal_activa.id)
        if sucursal_activa
        else ""
    )

    filtro_sucursal_activo = (
        sucursal_filtro
        and sucursal_filtro
        != sucursal_activa_id
    )

    filtros_activos = any([
        q,
        estado,
        tecnico_id,
        fecha_inicio,
        fecha_fin,
        tipo_orden,
        filtro_sucursal_activo,
    ])

    # =====================================================
    # PAGINACIÓN
    # =====================================================

    LIMITE_RESULTADOS = 40

    paginator = Paginator(
        ordenes,
        LIMITE_RESULTADOS,
    )

    page_number = request.GET.get(
        "page"
    )

    page_obj = paginator.get_page(
        page_number
    )

    # =====================================================
    # RANGO MOSTRADO
    # =====================================================

    desde = (
        page_obj.start_index()
        if total_filtrado > 0
        else 0
    )

    hasta = (
        page_obj.end_index()
        if total_filtrado > 0
        else 0
    )

    # =====================================================
    # TEMPLATE
    # =====================================================

    return render(
        request,
        "lista_ordenes.html",
        {
            # ---------------------------------------------
            # ÓRDENES
            # ---------------------------------------------
            "ordenes": page_obj,
            "page_obj": page_obj,

            # ---------------------------------------------
            # SUCURSALES
            # ---------------------------------------------
            "sucursal_activa": sucursal_activa,
            "sucursales": sucursales,
            "sucursal_filtro": sucursal_filtro,
            "puede_cambiar_sucursal": (
                puede_cambiar_sucursal
            ),

            # ---------------------------------------------
            # MAESTROS
            # ---------------------------------------------
            "tecnicos": tecnicos,

            # ---------------------------------------------
            # FILTROS
            # ---------------------------------------------
            "q": q,
            "estado": estado,
            "tecnico_id": tecnico_id,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "tipo_orden": tipo_orden,

            # ---------------------------------------------
            # TOTALES
            # ---------------------------------------------
            "total_general": total_general,
            "total_filtrado": total_filtrado,

            # ---------------------------------------------
            # ESTADO FILTROS
            # ---------------------------------------------
            "filtros_activos": filtros_activos,

            # ---------------------------------------------
            # PAGINACIÓN
            # ---------------------------------------------
            "desde": desde,
            "hasta": hasta,
            "limite_resultados": (
                LIMITE_RESULTADOS
            ),
        },
    )