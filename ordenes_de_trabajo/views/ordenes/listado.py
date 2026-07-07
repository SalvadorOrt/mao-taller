from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.core.paginator import Paginator

from ...models import OrdenTrabajo, Sucursal, Tecnico
from ..utils import obtener_sucursal_activa


# =========================================================
# DASHBOARD DEL TALLER (TARJETAS DE VEHÍCULOS)
# =========================================================
@login_required
def dashboard_taller(request):
    sucursal_activa = obtener_sucursal_activa(request)
    ordenes_activas = []
    if sucursal_activa:
        ordenes_activas = (
            OrdenTrabajo.objects.filter(
                sucursal=sucursal_activa,
                estado='ABIERTA' 
            )
            .select_related('cliente')
            .annotate(
                items_count=Count('insumos_detalles', distinct=True) + 
                            Count('servicios_detalles', distinct=True)
            )
            .order_by('-fecha_ingreso')
        )
        
    sucursales = Sucursal.objects.filter(activa=True).order_by("nombre")
    puede_cambiar_sucursal = request.user.has_perm('empresa.can_change_active_branch') or request.user.is_superuser

    return render(request, "dashboard.html", {
        "ordenes_activas": ordenes_activas,
        "sucursal_activa": sucursal_activa,
        "sucursales": sucursales,
        "puede_cambiar_sucursal": puede_cambiar_sucursal
    })


# =========================================================
# LISTADO GLOBAL DE ÓRDENES (Buscador y Filtros de Precisión)
# =========================================================
@login_required
def lista_ordenes(request):
    sucursal_activa = obtener_sucursal_activa(request)

    sucursales = Sucursal.objects.filter(activa=True).order_by("nombre")
    tecnicos = Tecnico.objects.filter(activo=True).order_by("nombre")

    sucursal_id_req = request.GET.get("sucursal_filtro")

    if sucursal_id_req is None:
        sucursal_filtro = str(sucursal_activa.id) if sucursal_activa else "todas"
    else:
        sucursal_filtro = sucursal_id_req

    ordenes = (
        OrdenTrabajo.objects
        .select_related("cliente", "sucursal", "usuario_receptor")
        .prefetch_related("tecnicos")
        .order_by("-fecha_ingreso")
    )

    total_general = ordenes.count()

    if sucursal_filtro and sucursal_filtro != "todas":
        ordenes = ordenes.filter(sucursal_id=sucursal_filtro)

    q = request.GET.get("q", "").strip()

    if q:
        ordenes = ordenes.filter(
            Q(numero_orden__icontains=q) |
            Q(numero_orden_origen__icontains=q) |
            Q(placa__icontains=q) |
            Q(vehiculo__icontains=q) |
            Q(cliente__nombre_completo__icontains=q) |
            Q(cliente_respaldo__icontains=q)
        )

    estado = request.GET.get("estado", "")
    if estado:
        ordenes = ordenes.filter(estado=estado)

    tecnico_id = request.GET.get("tecnico", "")
    if tecnico_id:
        ordenes = ordenes.filter(tecnicos__id=tecnico_id)

    fecha_inicio = request.GET.get("fecha_inicio", "")
    if fecha_inicio:
        ordenes = ordenes.filter(fecha_ingreso__date__gte=fecha_inicio)

    fecha_fin = request.GET.get("fecha_fin", "")
    if fecha_fin:
        ordenes = ordenes.filter(fecha_ingreso__date__lte=fecha_fin)

    tipo_orden = request.GET.get("tipo_orden", "")
    if tipo_orden == "normal":
        ordenes = ordenes.filter(es_migrada=False)
    elif tipo_orden == "migrada":
        ordenes = ordenes.filter(es_migrada=True)

    total_filtrado = ordenes.distinct().count()

    filtros_activos = any([
        q,
        estado,
        tecnico_id,
        fecha_inicio,
        fecha_fin,
        tipo_orden,
        sucursal_id_req not in [None, "", "todas"],
    ])

    paginator = Paginator(ordenes.distinct(), 40)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    desde = page_obj.start_index() if total_filtrado > 0 else 0
    hasta = page_obj.end_index() if total_filtrado > 0 else 0

    return render(request, "lista_ordenes.html", {
        "ordenes": page_obj,
        "page_obj": page_obj,

        "sucursales": sucursales,
        "tecnicos": tecnicos,

        "sucursal_filtro": sucursal_filtro,
        "q": q,
        "estado": estado,
        "tecnico_id": tecnico_id,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "tipo_orden": tipo_orden,

        "total_general": total_general,
        "total_filtrado": total_filtrado,
        "filtros_activos": filtros_activos,
        "desde": desde,
        "hasta": hasta,
        "limite_resultados": 40,
    })