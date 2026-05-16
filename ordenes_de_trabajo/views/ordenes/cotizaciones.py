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

@login_required
def crear_cotizacion(request):
    """
    Crea una proforma desde el menú principal (Mostrador).
    """
    sucursal_activa = obtener_sucursal_activa(request)
    if not sucursal_activa: 
        messages.error(request, "Debe tener una sucursal activa.")
        return redirect("dashboard")

    if request.method == "POST":
        placa = request.POST.get("placa", "").strip().upper()
        vehiculo = request.POST.get("vehiculo", "").strip().upper()
        anio = request.POST.get("anio_vehiculo")
        identificacion = request.POST.get("identificacion", "").strip()
        nombre_cliente = request.POST.get("nombre_cliente", "").strip().upper()
        observaciones = request.POST.get("observaciones", "").strip()

        cliente_obj = None
        if identificacion:
            cliente_obj = Cliente.objects.filter(identificacion=identificacion).first()
            if not cliente_obj:
                cliente_obj = Cliente.objects.create(
                    identificacion=identificacion,
                    nombre_completo=nombre_cliente or "CONSUMIDOR FINAL"
                )

        with transaction.atomic():
            # Formato: COT-AñoMes-UUID
            num_cotizacion = f"COT-{timezone.now().strftime('%y%m')}-{uuid.uuid4().hex[:4].upper()}"
            nueva_cotizacion = Cotizacion.objects.create(
                numero_cotizacion=num_cotizacion,
                sucursal=sucursal_activa,
                cliente=cliente_obj,
                cliente_respaldo=nombre_cliente or None,
                placa=placa,
                vehiculo=vehiculo,
                anio_vehiculo=int(anio) if anio and anio.isdigit() else None,
                observaciones=observaciones,
                estado="PENDIENTE"
            )

        messages.success(request, f"Cotización {num_cotizacion} creada.")
        return redirect("detalle_cotizacion", pk=nueva_cotizacion.pk)

    return render(request, "crear_cotizacion.html", {"sucursal_activa": sucursal_activa})


@login_required
def nueva_cotizacion_desde_ot(request, pk_orden):
    """
    Lógica blindada: Busca la proforma de esta OT o crea una nueva si no existe.
    EVITA LAS 30 PROFORMAS REPETIDAS.
    """
    orden = get_object_or_404(OrdenTrabajo, pk=pk_orden)
    
    # 🔥 USAMOS GET_OR_CREATE PARA EVITAR DUPLICADOS 🔥
    cotizacion, created = Cotizacion.objects.get_or_create(
        orden=orden,
        defaults={
            'numero_cotizacion': f"PRO-{orden.numero_orden}",
            'sucursal': orden.sucursal,
            'cliente': orden.cliente,
            'placa': orden.placa,
            'vehiculo': orden.vehiculo,
            'anio_vehiculo': orden.anio_vehiculo,
            'estado': "PENDIENTE"
        }
    )
    
    if created:
        messages.success(request, f"Proforma de ampliación generada para {orden.numero_orden}.")
    
    return redirect('detalle_cotizacion', pk=cotizacion.pk)


@login_required
def detalle_cotizacion(request, pk):
    cotizacion = get_object_or_404(Cotizacion, pk=pk)
    sucursal_activa = obtener_sucursal_activa(request)
    categorias = Categoria.objects.all().order_by("nombre")

    if request.method == "POST":
        try:
            with transaction.atomic():
                # Limpieza de ítems actuales para reemplazo total
                cotizacion.insumos_cotizados.all().delete()
                cotizacion.servicios_cotizados.all().delete()

                # --- PROCESAMIENTO DE REPUESTOS ---
                rep_ids = request.POST.getlist("rep_producto_id[]")
                rep_desc = request.POST.getlist("rep_descripcion[]")
                rep_pu = request.POST.getlist("rep_pu[]")
                rep_cant = request.POST.getlist("rep_cantidad[]")
                rep_cat = request.POST.getlist("rep_categoria_id[]")
                rep_barras = request.POST.getlist("rep_codigo_barras[]")
                rep_empaque = request.POST.getlist("rep_codigo_empaque[]")

                total_filas_rep = max(len(rep_ids), len(rep_desc), len(rep_pu), len(rep_cant))
                repuestos_guardados = 0

                for i in range(total_filas_rep):
                    p_id = rep_ids[i].strip() if i < len(rep_ids) else ""
                    desc = rep_desc[i].strip() if i < len(rep_desc) else ""
                    pu_str = rep_pu[i].strip() if i < len(rep_pu) else ""
                    cant_str = rep_cant[i].strip() if i < len(rep_cant) else ""
                    cat_id = rep_cat[i].strip() if i < len(rep_cat) else ""
                    barras = rep_barras[i].strip() if i < len(rep_barras) else ""
                    empaque = rep_empaque[i].strip() if i < len(rep_empaque) else ""

                    if not p_id and not desc: continue

                    cantidad = parse_cantidad(cant_str, Decimal("1.00"))
                    precio = parse_decimal(pu_str, Decimal("0.00"))
                    if cantidad <= 0: continue

                    producto_id_final = int(p_id) if p_id and p_id.isdigit() else None
                    categoria_id_final = int(cat_id) if cat_id and cat_id.isdigit() else None

                    CotizacionInsumoDetalle.objects.create(
                        cotizacion=cotizacion,
                        producto_id=producto_id_final,
                        descripcion_factura=desc.upper(),
                        cantidad=cantidad,
                        precio_unitario=precio,
                        categoria_referencia_id=categoria_id_final if not producto_id_final else None,
                        codigo_barras_referencia=barras if not producto_id_final else None,
                        codigo_empaque_referencia=empaque if not producto_id_final else None,
                        orden_item=i + 1
                    )
                    repuestos_guardados += 1

                # --- PROCESAMIENTO DE MANO DE OBRA ---
                servicios_guardados = 0
                for prefix, tipo_bd in [("moi", "MEC"), ("moe", "EXT")]:
                    uid_list = request.POST.getlist(f"{prefix}_uid[]")
                    desc_list = request.POST.getlist(f"{prefix}_descripcion[]")
                    pu_list = request.POST.getlist(f"{prefix}_pu[]")
                    cant_list = request.POST.getlist(f"{prefix}_cantidad[]")
                    serv_ids = request.POST.getlist(f"{prefix}_servicio_id[]")

                    total_filas_mo = max(len(uid_list), len(desc_list), len(pu_list), len(cant_list), len(serv_ids))

                    for i in range(total_filas_mo):
                        uid = (uid_list[i].strip() if i < len(uid_list) and uid_list[i].strip() else str(i))
                        descripcion = desc_list[i].strip() if i < len(desc_list) else ""
                        s_id = serv_ids[i].strip() if i < len(serv_ids) else ""

                        if not descripcion and not s_id: continue

                        precio = parse_decimal(pu_list[i] if i < len(pu_list) else "0.00", Decimal("0.00"))
                        cantidad = parse_cantidad(cant_list[i] if i < len(cant_list) else "1.00", Decimal("1.00"))
                        if cantidad <= 0: continue

                        servicio_id_final = int(s_id) if s_id and s_id.isdigit() else None

                        detalle_servicio = CotizacionServicioDetalle.objects.create(
                            cotizacion=cotizacion,
                            servicio_id=servicio_id_final,
                            descripcion_servicio=descripcion.upper(),
                            cantidad=cantidad,
                            precio_unitario=precio,
                            orden_item=i + 1,
                            tipo_servicio=tipo_bd
                        )
                        servicios_guardados += 1

                        procedimientos = request.POST.getlist(f"{prefix}_procedimientos_{uid}[]")
                        for j, procedimiento in enumerate(procedimientos, start=1):
                            procedimiento = procedimiento.strip()
                            if not procedimiento: continue
                            CotizacionProcedimientoDetalle.objects.create(
                                servicio_cotizado=detalle_servicio,
                                descripcion=procedimiento.upper(),
                                orden_item=j
                            )

                cotizacion.calcular_total()
                messages.success(request, f"✅ Proforma guardada. ({repuestos_guardados} repuestos, {servicios_guardados} servicios).")
                return redirect('detalle_cotizacion', pk=cotizacion.pk)

        except Exception as e:
            error_msg = f"🚨 ERROR DEL SISTEMA: {str(e)}"
            print(traceback.format_exc())
            messages.error(request, error_msg)
            return redirect('detalle_cotizacion', pk=cotizacion.pk)

    return render(request, "detalle_cotizacion.html", {
        "cotizacion": cotizacion,
        "categorias_inventario": categorias,
        "sucursal_activa": sucursal_activa,
    })


@login_required
def aprobar_cotizacion(request, pk):
    """
    Pasa TODOS los datos a la OT y marca como aprobada.
    """
    cotizacion = get_object_or_404(Cotizacion, pk=pk)
    
    if not cotizacion.orden:
        messages.error(request, "Esta proforma no está vinculada a ninguna OT.")
        return redirect('detalle_cotizacion', pk=pk)

    if request.method == "POST":
        try:
            with transaction.atomic():
                orden_destino = cotizacion.orden
                
                # 1. Copiar Repuestos a la OT
                for item in cotizacion.insumos_cotizados.all():
                    OrdenInsumoDetalle.objects.create(
                        orden=orden_destino,
                        producto=item.producto,
                        descripcion_factura=item.descripcion_factura,
                        cantidad=item.cantidad,
                        precio_unitario=item.precio_unitario
                    )

                # 2. Copiar Servicios
                for serv in cotizacion.servicios_cotizados.all():
                    nuevo_servicio_ot = OrdenServicioDetalle.objects.create(
                        orden=orden_destino,
                        servicio=serv.servicio,
                        tipo_servicio=serv.tipo_servicio,
                        descripcion_servicio=serv.descripcion_servicio,
                        cantidad=serv.cantidad,
                        precio_unitario=serv.precio_unitario
                    )
                    
                    for proc in serv.procedimientos_detalle.all():
                        OrdenServicioProcedimientoDetalle.objects.create(
                            servicio_detalle=nuevo_servicio_ot,
                            descripcion=proc.descripcion
                        )

                # 3. Finalizar Proforma
                cotizacion.estado = 'APROBADA'
                cotizacion.save()
                
                orden_destino.calcular_total()

            messages.success(request, "Items cargados a la Orden de Trabajo con éxito.")
            return redirect('detalle_orden', pk=orden_destino.pk)
        except Exception as e:
            messages.error(request, f"Error al aprobar: {str(e)}")
            return redirect('detalle_cotizacion', pk=pk)

    return redirect('dashboard')