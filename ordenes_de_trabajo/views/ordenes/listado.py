
import uuid
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Count
from ..api import clasificar_vehiculo_con_ia
# 🚀 IMPORTAMOS LOS MODELOS DE INVENTARIO NECESARIOS PARA LA "CUARENTENA"
from inventario.models import CodigoProducto, Categoria
from servicios.models import ServicioCatalogo
from ...models import (
    Sucursal,
    Cliente,
    OrdenTrabajo,
    FotoRecepcionVehiculo,
    OrdenChecklistRecepcion,
    OrdenCroquisDanio,
    OrdenInsumoDetalle,
    OrdenObjetoAdicional,
    OrdenServicioDetalle,
    OrdenServicioProcedimientoDetalle, 
    OrdenSintoma,
    OrdenTrabajoSolicitado,
    ExpedienteVehiculo,
    Cotizacion,                   
    CotizacionInsumoDetalle,      
    CotizacionServicioDetalle,
    CotizacionProcedimientoDetalle
)
from ..utils import (
    parse_int, parse_decimal, cargar_json_lista, procesar_imagen_base64,
    obtener_sucursal_activa, obtener_o_crear_expediente, generar_numero_orden,
    puede_operar_orden_desde_sucursal_activa,parse_cantidad
)
from django.urls import reverse

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
    LIMITE_RESULTADOS = 40

    sucursal_activa = obtener_sucursal_activa(request)
    sucursales = Sucursal.objects.filter(activa=True).order_by("nombre")

    sucursal_id_req = request.GET.get("sucursal_filtro")

    if sucursal_id_req is None:
        sucursal_filtro = str(sucursal_activa.id) if sucursal_activa else "todas"
    else:
        sucursal_filtro = sucursal_id_req

    ordenes_base = (
        OrdenTrabajo.objects
        .select_related("cliente", "sucursal")
        .order_by("-fecha_ingreso")
    )

    total_general = ordenes_base.count()
    ordenes = ordenes_base

    if sucursal_filtro and sucursal_filtro != "todas":
        ordenes = ordenes.filter(sucursal_id=sucursal_filtro)

    q = request.GET.get("q", "").strip()
    if q:
        ordenes = ordenes.filter(
            Q(numero_orden__icontains=q) |
            Q(numero_orden_origen__icontains=q) |
            Q(placa__icontains=q) |
            Q(cliente__nombre_completo__icontains=q) |
            Q(cliente_respaldo__icontains=q)
        )

    estado = request.GET.get("estado", "")
    if estado:
        ordenes = ordenes.filter(estado=estado)

    fecha_inicio = request.GET.get("fecha_inicio", "")
    if fecha_inicio:
        ordenes = ordenes.filter(fecha_ingreso__date__gte=fecha_inicio)

    fecha_fin = request.GET.get("fecha_fin", "")
    if fecha_fin:
        ordenes = ordenes.filter(fecha_ingreso__date__lte=fecha_fin)

    total_filtrado = ordenes.count()

    filtros_activos = any([
        q,
        estado,
        fecha_inicio,
        fecha_fin,
        sucursal_id_req not in [None, "", "todas"],
    ])

    ordenes = ordenes[:LIMITE_RESULTADOS]

    desde = 1 if total_filtrado > 0 else 0
    hasta = min(LIMITE_RESULTADOS, total_filtrado)

    return render(request, "lista_ordenes.html", {
        "ordenes": ordenes,
        "sucursales": sucursales,
        "sucursal_filtro": sucursal_filtro,
        "q": q,
        "estado": estado,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "total_general": total_general,
        "total_filtrado": total_filtrado,
        "filtros_activos": filtros_activos,
        "desde": desde,
        "hasta": hasta,
        "limite_resultados": LIMITE_RESULTADOS,
    })