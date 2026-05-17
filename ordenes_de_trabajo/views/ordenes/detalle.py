from decimal import Decimal
import requests

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse

from inventario.models import CodigoProducto, Categoria
from servicios.models import ServicioCatalogo

from ...models import (
    OrdenTrabajo,
    OrdenCroquisDanio,
    OrdenInsumoDetalle,
    OrdenServicioDetalle,
    OrdenServicioProcedimientoDetalle,
    Cliente,
    ExpedienteVehiculo
)

from ..utils import (
    parse_decimal,
    parse_cantidad,
    obtener_sucursal_activa,
    puede_operar_orden_desde_sucursal_activa
)
# =========================================================
# DETALLE / EDICIÓN DE ORDEN
# =========================================================
@login_required
def detalle_orden(request, pk):
    sucursal_activa = obtener_sucursal_activa(request)

    orden = get_object_or_404(
        OrdenTrabajo.objects
        .select_related("sucursal", "cliente", "expediente")
        .prefetch_related(
            "insumos_historicos",
            "servicios_historicos",
            "insumos_detalles",
            "servicios_detalles",
        ),
        pk=pk
    )

    url_anterior = request.META.get("HTTP_REFERER")
    if not url_anterior or f"ordenes/{pk}" in url_anterior:
        url_anterior = reverse("lista_ordenes")

    es_su_sucursal = puede_operar_orden_desde_sucursal_activa(request, orden)
    puede_reabrir = request.user.has_perm("ordenes_de_trabajo.can_reopen_orden")
    puede_editar = (es_su_sucursal and orden.estado == "ABIERTA") or puede_reabrir

    categorias = Categoria.objects.all().order_by("nombre") if puede_editar else []

    # =====================================================
    # POST
    # =====================================================
    if request.method == "POST":
        if not puede_editar:
            messages.error(
                request,
                "Operación denegada: No tiene permisos para modificar esta orden."
            )
            return redirect("detalle_orden", pk=orden.pk)

        with transaction.atomic():
            orden.insumos_detalles.all().delete()
            orden.servicios_detalles.all().delete()

            # =================================================
            # REPUESTOS
            # =================================================
            rep_ids = request.POST.getlist("rep_producto_id[]")
            rep_desc = request.POST.getlist("rep_descripcion[]")
            rep_pu = request.POST.getlist("rep_pu[]")
            rep_cant = request.POST.getlist("rep_cantidad[]")
            rep_categorias = request.POST.getlist("rep_categoria_id[]")
            rep_barras = request.POST.getlist("rep_codigo_barras[]")
            rep_empaques = request.POST.getlist("rep_codigo_empaque[]")

            total_filas = max(
                len(rep_ids),
                len(rep_desc),
                len(rep_pu),
                len(rep_cant),
                len(rep_categorias),
                len(rep_barras),
                len(rep_empaques),
            )

            for i in range(total_filas):
                p_id = rep_ids[i].strip() if i < len(rep_ids) else ""
                desc = rep_desc[i].strip() if i < len(rep_desc) else ""
                pu_str = rep_pu[i].strip() if i < len(rep_pu) else ""
                cant_str = rep_cant[i].strip() if i < len(rep_cant) else ""
                cat_id = rep_categorias[i].strip() if i < len(rep_categorias) else ""
                barras = rep_barras[i].strip() if i < len(rep_barras) else ""
                empaque = rep_empaques[i].strip() if i < len(rep_empaques) else ""

                if not p_id and not desc:
                    continue

                cantidad = parse_cantidad(cant_str, Decimal("1.00"))
                if cantidad <= 0:
                    continue

                producto_obj = None
                precio = Decimal("0.00")

                if p_id:
                    producto_obj = CodigoProducto.objects.filter(
                        id=p_id,
                        activo=True
                    ).first()

                    if producto_obj:
                        precio = parse_decimal(
                            pu_str,
                            Decimal(producto_obj.precio_venta or 0)
                        )
                    else:
                        precio = parse_decimal(pu_str, Decimal("0.00"))

                else:
                    precio = parse_decimal(pu_str, Decimal("0.00"))
                    codigo_busqueda = barras.strip() or empaque.strip()

                    if codigo_busqueda:
                        producto_obj = CodigoProducto.objects.filter(
                            Q(codigo=codigo_busqueda) |
                            Q(codigo_barras=codigo_busqueda) |
                            Q(nombre_comercial__icontains=codigo_busqueda)
                        ).first()

                    if not (producto_obj and producto_obj.activo):
                        producto_obj = None

                OrdenInsumoDetalle.objects.create(
                    orden=orden,
                    producto=producto_obj,
                    descripcion_factura=desc,
                    cantidad=cantidad,
                    precio_unitario=precio,
                    categoria_referencia_id=None if producto_obj else (cat_id or None),
                    codigo_barras_referencia=None if producto_obj else (barras or None),
                    codigo_empaque_referencia=None if producto_obj else (empaque or None),
                    orden_item=i + 1,
                )

            # =================================================
            # MANO DE OBRA INTERNA / EXTERNA
            # =================================================
            for prefix, tipo_bd in [("moi", "MEC"), ("moe", "EXT")]:
                uid_list = request.POST.getlist(f"{prefix}_uid[]")
                desc_list = request.POST.getlist(f"{prefix}_descripcion[]")
                pu_list = request.POST.getlist(f"{prefix}_pu[]")
                cant_list = request.POST.getlist(f"{prefix}_cantidad[]")
                serv_ids = request.POST.getlist(f"{prefix}_servicio_id[]")
                variante_list = request.POST.getlist(f"{prefix}_variante_precio[]")

                total_filas_mo = max(
                    len(uid_list),
                    len(desc_list),
                    len(pu_list),
                    len(cant_list),
                    len(serv_ids),
                    len(variante_list),
                )

                for i in range(total_filas_mo):
                    uid = (
                        uid_list[i].strip()
                        if i < len(uid_list) and uid_list[i].strip()
                        else str(i)
                    )

                    descripcion = desc_list[i].strip() if i < len(desc_list) else ""
                    s_id = serv_ids[i].strip() if i < len(serv_ids) else ""

                    servicio_obj = None

                    if s_id:
                        servicio_obj = ServicioCatalogo.objects.filter(
                            id=s_id,
                            activo=True
                        ).first()

                    if servicio_obj and not descripcion:
                        descripcion = servicio_obj.descripcion

                    if not descripcion and not servicio_obj:
                        continue

                    precio = parse_decimal(
                        pu_list[i] if i < len(pu_list) else "0.00",
                        Decimal("0.00")
                    )

                    cantidad = parse_decimal(
                        cant_list[i] if i < len(cant_list) else "1.00",
                        Decimal("1.00")
                    )

                    if cantidad <= 0:
                        continue

                    variante_aplicada = (
                        variante_list[i].strip().upper()
                        if i < len(variante_list) and variante_list[i].strip()
                        else "NORMAL"
                    )

                    detalle_servicio = OrdenServicioDetalle.objects.create(
                        orden=orden,
                        servicio=servicio_obj,
                        descripcion_servicio=descripcion,
                        cantidad=cantidad,
                        precio_unitario=precio,
                        orden_item=i + 1,
                        tipo_servicio=tipo_bd,
                        tipo_tarifa_aplicada=orden.tipo_tarifa_vehiculo or "NO_APLICA",
                        variante_precio_aplicada=variante_aplicada,
                    )

                    procedimientos = request.POST.getlist(
                        f"{prefix}_procedimientos_{uid}[]"
                    )

                    for j, procedimiento in enumerate(procedimientos, start=1):
                        procedimiento = procedimiento.strip()

                        if not procedimiento:
                            continue

                        OrdenServicioProcedimientoDetalle.objects.create(
                            detalle_servicio=detalle_servicio,
                            descripcion=procedimiento,
                            orden_item=j,
                        )

            # =================================================
            # OBSERVACIONES
            # =================================================
            orden.observaciones_tecnicas = request.POST.get(
                "observaciones_tecnicas",
                ""
            ).strip()
            orden.save()

        messages.success(request, "Orden actualizada correctamente.")
        return redirect("detalle_orden", pk=orden.pk)

    # =====================================================
    # GET
    # =====================================================
    croquis = OrdenCroquisDanio.objects.filter(orden=orden).first()
    croquis_url = (
        croquis.imagen_generada.url
        if croquis and croquis.imagen_generada
        else ""
    )

    # =====================================================
    # TOTALES ECONÓMICOS
    # =====================================================

    subtotal = Decimal(orden.total_general or 0) / Decimal("1.15")
    iva = Decimal(orden.total_general or 0) - subtotal
    total_final = Decimal(orden.total_general or 0)

    # =====================================================
    # RENDER
    # =====================================================

    return render(
        request,
        "detalle_orden.html",
        {
            "orden": orden,
            "croquis": croquis,
            "croquis_url": croquis_url,
            "categorias_inventario": categorias,
            "sucursal_activa": sucursal_activa,
            "puede_editar": puede_editar,
            "puede_reabrir": puede_reabrir,
            "url_anterior": url_anterior,
            "subtotal": subtotal,
            "iva": iva,
            "total_final": total_final,
        }
    )




# =========================================================
# EDICIÓN EXCLUSIVA DE VEHÍCULO (ESTRATEGIA CASCADA)
# =========================================================
@login_required
def editar_vehiculo_ot(request, pk):
    orden = get_object_or_404(OrdenTrabajo, pk=pk)

    # Validaciones de seguridad (Las mismas que usas en detalle_orden)
    es_su_sucursal = puede_operar_orden_desde_sucursal_activa(request, orden)
    puede_reabrir = request.user.has_perm("ordenes_de_trabajo.can_reopen_orden")
    puede_editar = (es_su_sucursal and orden.estado == "ABIERTA") or puede_reabrir

    if not puede_editar:
        messages.error(request, "Operación denegada: No tiene permisos o la orden ya está cerrada.")
        return redirect('detalle_orden', pk=orden.pk)

    if request.method == "POST":
        nueva_placa = request.POST.get("placa", "").strip().upper()
        nuevo_vehiculo = request.POST.get("vehiculo", "").strip().upper()
        nuevo_anio = request.POST.get("anio_vehiculo", "").strip()
        nuevo_color = request.POST.get("color", "").strip().upper()
        nuevo_km = request.POST.get("kilometraje", "").strip()

        if not nueva_placa:
            messages.error(request, "La placa es obligatoria para realizar la corrección.")
            return redirect('detalle_orden', pk=orden.pk)

        try:
            with transaction.atomic():
                # 🚀 LÓGICA SOLO SI LA PLACA CAMBIÓ (El asesor se equivocó de auto)
                if nueva_placa != orden.placa:
                    
                    # --- FASE 1: CACHÉ LOCAL (Base de Datos) ---
                    expediente_existente = ExpedienteVehiculo.objects.filter(placa=nueva_placa).first()

                    if expediente_existente:
                        # ¡El auto ya era cliente! Lo reasignamos al instante.
                        orden.expediente = expediente_existente
                        orden.placa = nueva_placa
                        orden.vehiculo = expediente_existente.vehiculo
                        orden.anio_vehiculo = expediente_existente.anio_vehiculo
                        orden.cliente = expediente_existente.cliente
                        messages.success(request, f"¡Vehículo corregido! Datos cargados al instante desde el historial del taller.")

                    else:
                        # --- FASE 2: API EXTERNA (SRI/ANT) ---
                        token_api = getattr(settings, "CEDULA_API_TOKEN", "")
                        url_api = f"https://apiconsult.zampisoft.com/api/consultar?identificacion={nueva_placa}&token={token_api}"

                        try:
                            respuesta = requests.get(url_api, timeout=10)
                            data = respuesta.json()

                            if respuesta.status_code == 200 and not data.get("error"):
                                # Éxito en la API
                                marca_modelo = data.get("vehiculo") or data.get("modelo") or nuevo_vehiculo
                                anio_auto = data.get("anio") or data.get("anioVehiculo") or nuevo_anio
                                cedula_prop = data.get("cedulaPropietario") or data.get("identificacion")
                                nombre_prop = data.get("nombrePropietario") or data.get("propietario")

                                # Procesar Dueño
                                cliente_real = orden.cliente
                                if cedula_prop and nombre_prop:
                                    tipo_doc = "R" if len(cedula_prop) == 13 else "C"
                                    cliente_real, _ = Cliente.objects.get_or_create(
                                        identificacion=cedula_prop,
                                        defaults={"nombre_completo": str(nombre_prop).upper(), "tipo_documento": tipo_doc}
                                    )

                                # Crear nuevo Expediente
                                expediente, _ = ExpedienteVehiculo.objects.get_or_create(
                                    placa=nueva_placa,
                                    defaults={
                                        "vehiculo": marca_modelo.upper(),
                                        "anio_vehiculo": int(anio_auto) if anio_auto and str(anio_auto).isdigit() else None,
                                        "cliente": cliente_real
                                    }
                                )
                                
                                orden.expediente = expediente
                                orden.placa = nueva_placa
                                orden.vehiculo = marca_modelo.upper()
                                orden.cliente = cliente_real
                                if anio_auto and str(anio_auto).isdigit():
                                    orden.anio_vehiculo = int(anio_auto)

                                messages.success(request, "¡Placa corregida! Los datos fueron validados automáticamente con la ANT/SRI.")

                            else:
                                raise ValueError("La API no trajo datos válidos")

                        except Exception as e:
                            # --- FASE 3: PLAN DE EMERGENCIA (Manual Fallback) ---
                            # Si no hay internet o la API falla, usamos lo que el asesor escribió en el modal
                            expediente, _ = ExpedienteVehiculo.objects.get_or_create(
                                placa=nueva_placa,
                                defaults={
                                    "vehiculo": nuevo_vehiculo or "VEHÍCULO DESCONOCIDO",
                                    "anio_vehiculo": int(nuevo_anio) if nuevo_anio.isdigit() else None,
                                    "cliente": orden.cliente
                                }
                            )
                            orden.expediente = expediente
                            orden.placa = nueva_placa
                            orden.vehiculo = nuevo_vehiculo or "VEHÍCULO DESCONOCIDO"
                            if nuevo_anio.isdigit():
                                orden.anio_vehiculo = int(nuevo_anio)

                            messages.warning(request, "Placa corregida en Modo Manual (Sin conexión a la ANT).")
                if nuevo_km.isdigit():
                    orden.kilometraje = int(nuevo_km)
                if nuevo_color:
                    orden.color = nuevo_color

                orden.save()
                if nueva_placa == orden.placa:
                    messages.success(request, "Los datos del vehículo han sido actualizados exitosamente.")

        except Exception as e:
            messages.error(request, f"Error crítico al intentar corregir los datos: {str(e)}")

    return redirect('detalle_orden', pk=orden.pk)