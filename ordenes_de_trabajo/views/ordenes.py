import uuid
import requests
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import JsonResponse
from .api import clasificar_vehiculo_con_ia
# 🚀 IMPORTAMOS LOS MODELOS DE INVENTARIO NECESARIOS PARA LA "CUARENTENA"
from inventario.models import CodigoProducto, StockSucursal, Categoria, Producto, MarcaRepuesto
from servicios.models import ServicioCatalogo
from ..models import (
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
    CotizacionServicioDetalle
)
from .utils import (
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
# =========================================================
# CREAR ORDEN
# =========================================================
@login_required
def crear_orden(request):
    sucursal_activa = obtener_sucursal_activa(request)
    if not sucursal_activa: return redirect("dashboard")

    if request.method == "POST":
        placa = request.POST.get("placa", "").strip().upper()
        vehiculo = request.POST.get("vehiculo", "").strip().upper()
        color = request.POST.get("color", "").strip().upper()
        anio = parse_int(request.POST.get("anio_vehiculo"), None)
        kilometraje = parse_int(request.POST.get("kilometraje"), None)
        nivel_combustible = request.POST.get("nivel_combustible", "1/2").strip()
        tipo_tarifa_vehiculo = request.POST.get(
            "tipo_tarifa_vehiculo",
            "NO_APLICA"
        ).strip().upper() or "NO_APLICA"
        gama_vehiculo = request.POST.get(
                "gama_vehiculo",
                "NO_APLICA"
            ).strip().upper() or "NO_APLICA"
        # Seguridad extra: si viene vacío, inválido o raro, no rompe la OT
        tipos_validos = {
            "NO_APLICA",
            "AUTO",
            "AUTO_3P",
            "AUTO_5P",
            "SUV_3P",
            "SUV_5P",
            "CAMIONETA_CS",
            "CAMIONETA_DC",
            "CAMIONETA_GRANDE",
        }

        gamas_validas = {
            "NO_APLICA",
            "ECONOMICA",
            "MEDIA",
            "MEDIA_ALTA",
            "ALTA",
            "PREMIUM",
            "LUJO",
            "COMERCIAL",
            "DEPORTIVA",
        }

        if tipo_tarifa_vehiculo not in tipos_validos:
            tipo_tarifa_vehiculo = "NO_APLICA"

        if gama_vehiculo not in gamas_validas:
            gama_vehiculo = "NO_APLICA"


        identificacion = request.POST.get("identificacion", "").strip()
        if identificacion.isdigit() and len(identificacion) == 13:
            tipo_documento = "R"

        elif identificacion.isdigit() and len(identificacion) == 10:
            tipo_documento = "C"

        else:
            tipo_documento = "P"
        nombre_cliente = request.POST.get("nombre_cliente", "").strip().upper()
        telefono = request.POST.get("telefono", "").strip()
        telefono_secundario = request.POST.get("telefono_secundario", "").strip()
        telefono_trabajo = request.POST.get("telefono_trabajo", "").strip()
        email = request.POST.get("email", "").strip()
        direccion = request.POST.get("direccion", "").strip()
        observaciones_recepcion = request.POST.get("observaciones_recepcion", "").strip()
                # =====================================================
        # IA: CLASIFICAR VEHÍCULO
        # =====================================================
        try:
            clasificacion_ia = clasificar_vehiculo_con_ia(
                marca=vehiculo.split(" ")[0] if vehiculo else "",
                modelo=vehiculo,
                anio=anio,
                descripcion=vehiculo,
            )

            print("CLASIFICACIÓN IA:", clasificacion_ia)

            tipo_tarifa_vehiculo = (
                clasificacion_ia.get("tipo_tarifa_vehiculo")
                or tipo_tarifa_vehiculo
                or "NO_APLICA"
            )

            gama_vehiculo = (
                clasificacion_ia.get("gama_vehiculo")
                or gama_vehiculo
                or "NO_APLICA"
            )

        except Exception as e:
            print("ERROR GENERAL IA:", str(e))
        sintomas_json = cargar_json_lista(request.POST.get("sintomas_json", ""))
        trabajos_json = cargar_json_lista(request.POST.get("trabajos_json", ""))
        objetos_json = cargar_json_lista(request.POST.get("objetos_json", ""))

        def es_marcado(campo):
            return request.POST.get(campo, "").strip().lower() in ["on", "true", "1", "yes"]

        checks = {
            "matricula": es_marcado("matricula"), "plumas": es_marcado("plumas"),
            "radio": es_marcado("radio"), "pantalla": es_marcado("pantalla"),
            "tuerca_seguridad": es_marcado("tuerca_seguridad"), "encendedor_cig": es_marcado("encendedor_cig"),
            "triangulos": es_marcado("triangulos"), "gata": es_marcado("gata"),
            "herramientas": es_marcado("herramientas"), "llanta_emergencia": es_marcado("llanta_emergencia"),
            "faros_lunas": es_marcado("faros_lunas"), "tapacubos": es_marcado("tapacubos"), "antena": es_marcado("antena"),
        }

        croquis_base64 = request.POST.get("imagen_croquis_base64", "").strip()
        firma_base64 = request.POST.get("firma_base64", "").strip()
        fotos = request.FILES.getlist("fotos_recepcion")
        descripcion_fotos = request.POST.get("descripcion_fotos", "").strip()

        cliente_obj = None
        if identificacion:
            cliente_obj = Cliente.objects.filter(identificacion=identificacion).first()
            if cliente_obj:
                cliente_obj.tipo_documento = tipo_documento
                cliente_obj.nombre_completo = nombre_cliente or cliente_obj.nombre_completo
                cliente_obj.telefono = telefono or cliente_obj.telefono
                cliente_obj.telefono_secundario = telefono_secundario or cliente_obj.telefono_secundario
                cliente_obj.telefono_trabajo = telefono_trabajo or cliente_obj.telefono_trabajo
                cliente_obj.email = email or cliente_obj.email
                cliente_obj.direccion = direccion or cliente_obj.direccion
                cliente_obj.save()
            else:
                cliente_obj = Cliente.objects.create(
                    tipo_documento=tipo_documento,
                    identificacion=identificacion, 
                    nombre_completo=nombre_cliente or "CONSUMIDOR FINAL", 
                    telefono=telefono, 
                    telefono_secundario=telefono_secundario,
                    telefono_trabajo=telefono_trabajo,
                    email=email, 
                    direccion=direccion
                )

        with transaction.atomic():
            expediente = obtener_o_crear_expediente(cliente_obj, nombre_cliente, placa, vehiculo, anio)
            
            nueva_orden = OrdenTrabajo.objects.create(
            numero_orden=generar_numero_orden(),
            sucursal=sucursal_activa,
            expediente=expediente,
            usuario_receptor=request.user,
            cliente=cliente_obj,
            cliente_respaldo=nombre_cliente or None,
            placa=placa,
            vehiculo=vehiculo,
            color=color,
            anio_vehiculo=anio,
            kilometraje=kilometraje,
            nivel_combustible=nivel_combustible,
            observaciones_recepcion=observaciones_recepcion,
            fecha_ingreso=timezone.now(),
            estado="ABIERTA",
            tipo_tarifa_vehiculo=tipo_tarifa_vehiculo,
            gama_vehiculo=gama_vehiculo,
        )

            archivo_firma = procesar_imagen_base64(firma_base64)
            if archivo_firma:
                nueva_orden.firma_cliente.save(f"firma_ot_{nueva_orden.numero_orden}_{uuid.uuid4().hex[:8]}.png", archivo_firma, save=False)
                nueva_orden.fecha_firma = timezone.now()
                nueva_orden.save()

            OrdenChecklistRecepcion.objects.create(orden=nueva_orden, **checks)

            for idx, item in enumerate(sintomas_json, start=1):
                if desc := str(item.get("descripcion", "")).strip(): OrdenSintoma.objects.create(orden=nueva_orden, descripcion=desc, orden_item=idx)

            for idx, item in enumerate(trabajos_json, start=1):
                if desc := str(item.get("descripcion", "")).strip(): OrdenTrabajoSolicitado.objects.create(orden=nueva_orden, descripcion_manual=desc, orden_item=idx)

            for item in objetos_json:
                if desc := str(item.get("descripcion", "")).strip():
                    OrdenObjetoAdicional.objects.create(orden=nueva_orden, descripcion=desc, cantidad=max(parse_int(item.get("cantidad"), 1), 1), observacion=str(item.get("observacion", "")).strip() or None)

            archivo_croquis = procesar_imagen_base64(croquis_base64)
            if archivo_croquis:
                croquis_obj = OrdenCroquisDanio.objects.create(orden=nueva_orden, trazos=[], observacion="Croquis generado")
                croquis_obj.imagen_generada.save(f"croquis_ot_{nueva_orden.numero_orden}_{uuid.uuid4().hex[:8]}.png", archivo_croquis)

            for foto in fotos: FotoRecepcionVehiculo.objects.create(orden=nueva_orden, imagen=foto, descripcion=descripcion_fotos)

        return redirect("dashboard")
    return render(request, "crear_orden.html", {"sucursal_activa": sucursal_activa})
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
# EDITAR RECEPCIÓN DE ORDEN (MODAL RÁPIDO COMPLETO)
# =========================================================
@login_required
def editar_recepcion_orden(request, pk):
    import uuid
    from django.db import transaction

    orden = get_object_or_404(OrdenTrabajo, pk=pk)

    if not puede_operar_orden_desde_sucursal_activa(request, orden):
        messages.error(request, "No tienes permiso para editar órdenes de otra sucursal.")
        return redirect("lista_ordenes")

    if orden.estado != "ABIERTA":
        messages.error(request, "No se puede editar la recepción de una orden cerrada o anulada.")
        return redirect("detalle_orden", pk=pk)

    if request.method == "POST":
        orden.observaciones_recepcion = request.POST.get(
            "observaciones_recepcion",
            orden.observaciones_recepcion or ""
        ).strip()

        sintomas_json = cargar_json_lista(request.POST.get("sintomas_json", ""))
        trabajos_json = cargar_json_lista(request.POST.get("trabajos_json", ""))
        croquis_base64 = request.POST.get("imagen_croquis_base64", "").strip()

        # Nuevas fotos desde el modal
        fotos_nuevas = request.FILES.getlist("fotos_recepcion")
        descripcion_fotos = request.POST.get("descripcion_fotos", "").strip()

        # Fotos a eliminar desde el modal
        fotos_eliminar = request.POST.getlist("fotos_eliminar")

        with transaction.atomic():
            orden.save()

            # Síntomas
            orden.sintomas_items.all().delete()
            for idx, item in enumerate(sintomas_json, start=1):
                desc = str(item.get("descripcion", "")).strip()
                if desc:
                    OrdenSintoma.objects.create(
                        orden=orden,
                        descripcion=desc,
                        orden_item=idx
                    )

            # Trabajos solicitados
            orden.trabajos_solicitados_items.all().delete()
            for idx, item in enumerate(trabajos_json, start=1):
                desc = str(item.get("descripcion", "")).strip()
                if desc:
                    OrdenTrabajoSolicitado.objects.create(
                        orden=orden,
                        descripcion_manual=desc,
                        orden_item=idx
                    )

            # Croquis
            if croquis_base64:
                archivo_croquis = procesar_imagen_base64(croquis_base64)
                if archivo_croquis:
                    croquis_obj, _ = OrdenCroquisDanio.objects.get_or_create(orden=orden)

                    if croquis_obj.imagen_generada:
                        croquis_obj.imagen_generada.delete(save=False)

                    nombre_archivo = f"croquis_upd_{orden.numero_orden}_{uuid.uuid4().hex[:8]}.png"
                    croquis_obj.imagen_generada.save(
                        nombre_archivo,
                        archivo_croquis,
                        save=True
                    )

            # Eliminar fotos marcadas
            if fotos_eliminar:
                fotos_queryset = FotoRecepcionVehiculo.objects.filter(
                    orden=orden,
                    id__in=fotos_eliminar
                )

                for foto in fotos_queryset:
                    if foto.imagen:
                        foto.imagen.delete(save=False)
                    foto.delete()

            # Agregar nuevas fotos
            for foto in fotos_nuevas:
                FotoRecepcionVehiculo.objects.create(
                    orden=orden,
                    imagen=foto,
                    descripcion=descripcion_fotos
                )

        messages.success(request, "Recepción, croquis y fotos actualizados con éxito.")

    return redirect("detalle_orden", pk=orden.pk)

# =========================================================
# ACCIONES DE ESTADO (Cerrar / Anular / Reabrir)
# =========================================================
@login_required
def cerrar_orden(request, pk):
    if request.method == "POST":
        orden = get_object_or_404(OrdenTrabajo, pk=pk)
        
        if not puede_operar_orden_desde_sucursal_activa(request, orden):
            messages.error(request, "No tienes permiso para operar esta orden desde tu sucursal activa.")
            return redirect("detalle_orden", pk=pk)
            
        if orden.estado == 'ABIERTA':
            orden.estado = 'CERRADA'
            orden.save()
            messages.success(request, f"La orden {orden.numero_orden} ha sido cerrada.")
        else:
            messages.error(request, f"No se puede cerrar la orden porque actualmente está {orden.estado}.")
    else:
        messages.error(request, "Método no permitido. Debe usar el botón oficial del sistema.")
        
    return redirect("detalle_orden", pk=pk)

@login_required
def anular_orden(request, pk):
    if request.method == "POST":
        orden = get_object_or_404(OrdenTrabajo, pk=pk)
        
        if not puede_operar_orden_desde_sucursal_activa(request, orden):
            messages.error(request, "No tienes permiso para operar esta orden desde tu sucursal activa.")
            return redirect("detalle_orden", pk=pk)
            
        if orden.estado == 'ABIERTA':
            orden.estado = 'ANULADA'
            orden.save()
            messages.success(request, f"La orden {orden.numero_orden} ha sido anulada.")
        else:
            messages.error(request, f"No se puede anular la orden porque actualmente está {orden.estado}.")
    else:
        messages.error(request, "Método no permitido. Debe usar el botón oficial del sistema.")
        
    return redirect("detalle_orden", pk=pk)

@login_required
@permission_required('ordenes_de_trabajo.can_reopen_orden', raise_exception=True)
def reabrir_orden(request, pk):
    if request.method == "POST":
        orden = get_object_or_404(OrdenTrabajo, pk=pk)
        
        if not puede_operar_orden_desde_sucursal_activa(request, orden):
            messages.error(request, "No tienes permiso para operar esta orden desde tu sucursal activa.")
            return redirect("detalle_orden", pk=pk)
            
        if orden.estado != 'ABIERTA':
            orden.estado = 'ABIERTA'
            orden.save()
            messages.success(request, f"Privilegio concedido: La orden {orden.numero_orden} ha sido reabierta.")
        else:
            messages.error(request, "La orden ya se encuentra ABIERTA.")
    else:
        messages.error(request, "Método no permitido. Debe usar el botón oficial del sistema.")
        
    return redirect("detalle_orden", pk=pk)

# =========================================================
# 🔥 APIS DE CONSULTA (CACHE-ASIDE PATTERN) 🔥
# =========================================================
@login_required
def consultar_cedula_api(request):
    cedula = request.GET.get("cedula", "").strip()

    if not cedula:
        return JsonResponse({"success": False, "error": "Cédula no proporcionada"})

    cliente_local = Cliente.objects.filter(identificacion=cedula).first()

    if cliente_local:
        return JsonResponse({
            "success": True,
            "fuente": "local",
            "data": {
                "nombre": cliente_local.nombre_completo,
                "telefono": cliente_local.telefono or "",
                "telefono_secundario": cliente_local.telefono_secundario or "",
                "telefono_trabajo": cliente_local.telefono_trabajo or "",
                "email": cliente_local.email or "",
                "direccion": cliente_local.direccion or "",
            }
        })

    token = "yKGE-7wqa-kwNp-3AvU"
    url_api = f"https://apiconsult.zampisoft.com/api/consultar?identificacion={cedula}&token={token}"

    try:
        response = requests.get(url_api, timeout=5)

        if response.status_code != 200:
            return JsonResponse({
                "success": False,
                "error": "Cédula no encontrada en el proveedor."
            })

        datos_api = response.json()

        return JsonResponse({
            "success": True,
            "fuente": "api",
            "data": {
                "nombre": datos_api.get("nombre", ""),
                "telefono": "",
                "telefono_secundario": "",
                "telefono_trabajo": "",
                "email": "",
                "direccion": datos_api.get("direccion", ""),
            }
        })

    except requests.exceptions.RequestException:
        return JsonResponse({
            "success": False,
            "error": "Error de conexión con el proveedor."
        })

    except ValueError:
        return JsonResponse({
            "success": False,
            "error": "Respuesta inválida del proveedor."
        })
@login_required
def consultar_regcheck(request):
    placa = request.GET.get('placa', '').strip().upper()
    if not placa:
        return JsonResponse({"success": False, "error": "Placa no proporcionada"})

    # 1. BÚSQUEDA LOCAL
    vehiculo_local = ExpedienteVehiculo.objects.filter(placa=placa).first()
    
    if vehiculo_local:
        cliente = vehiculo_local.cliente_actual
        
        return JsonResponse({
            "success": True,
            "fuente": "local",
            "data": {
                "vehiculo": vehiculo_local.vehiculo,
                "anio_vehiculo": vehiculo_local.anio,
                "color": vehiculo_local.color,
                "kilometraje": vehiculo_local.kilometraje_actual,
                "identificacion": cliente.identificacion if cliente else "",
                "nombre_cliente": cliente.nombre_completo if cliente else "",
                "telefono": cliente.telefono if cliente else "",
                "email": cliente.email if cliente else "",
                "direccion": cliente.direccion if cliente else ""
            }
        })

    # 2. CONSUMO DE API EXTERNA (Regcheck)
    url_regcheck = f"https://api.regcheck.org.uk/api/json.aspx/CheckEcuador/{placa}"
    
    try:
        response = requests.get(url_regcheck, timeout=8)
        
        if response.status_code == 200:
            datos_api = response.json()
            return JsonResponse({
                "success": True,
                "fuente": "api",
                "data": {
                    "vehiculo": datos_api.get("vehiculo", ""), 
                    "anio_vehiculo": datos_api.get("anio", ""),
                    "color": datos_api.get("color", ""),
                    "kilometraje": "",
                    "identificacion": "",
                    "nombre_cliente": "",
                }
            })
        else:
            return JsonResponse({"success": False, "error": "Placa no encontrada en ANT/SRI."})

    except requests.exceptions.RequestException as e:
        print(f"Error consultando API de Regcheck: {e}")
        return JsonResponse({"success": False, "error": "Servicio temporalmente no disponible."})
    

# =========================================================
# 💡 MÓDULO DE COTIZACIONES / PROFORMAS (COMPLETO)
# =========================================================

@login_required
def crear_cotizacion(request):
    """
    Crea una cotización rápida desde el menú principal (Mostrador).
    Ideal para clientes que solo consultan precios sin dejar el auto.
    """
    sucursal_activa = obtener_sucursal_activa(request)
    if not sucursal_activa: 
        return redirect("dashboard")

    if request.method == "POST":
        placa = request.POST.get("placa", "").strip().upper()
        vehiculo = request.POST.get("vehiculo", "").strip().upper()
        anio = parse_int(request.POST.get("anio_vehiculo"), None)
        identificacion = request.POST.get("identificacion", "").strip()
        nombre_cliente = request.POST.get("nombre_cliente", "").strip().upper()
        observaciones = request.POST.get("observaciones", "").strip()

        # Determinar tipo de documento para el cliente
        tipo_documento = "P"
        if identificacion.isdigit():
            if len(identificacion) == 10: tipo_documento = "C"
            elif len(identificacion) == 13: tipo_documento = "R"

        cliente_obj = None
        if identificacion:
            cliente_obj = Cliente.objects.filter(identificacion=identificacion).first()
            if not cliente_obj:
                cliente_obj = Cliente.objects.create(
                    tipo_documento=tipo_documento,
                    identificacion=identificacion,
                    nombre_completo=nombre_cliente or "CONSUMIDOR FINAL"
                )

        with transaction.atomic():
            # Generar número único (COT + AñoMes + UUID corto)
            num_cotizacion = f"COT-{timezone.now().strftime('%y%m')}-{uuid.uuid4().hex[:4].upper()}"

            nueva_cotizacion = Cotizacion.objects.create(
                numero_cotizacion=num_cotizacion,
                sucursal=sucursal_activa,
                cliente=cliente_obj,
                cliente_respaldo=nombre_cliente or None,
                placa=placa,
                vehiculo=vehiculo,
                anio_vehiculo=anio,
                observaciones=observaciones,
                estado="PENDIENTE"
            )

        messages.success(request, f"Cotización {num_cotizacion} creada.")
        return redirect("detalle_cotizacion", pk=nueva_cotizacion.pk)

    return render(request, "cotizaciones/crear_cotizacion.html", {"sucursal_activa": sucursal_activa})


@login_required
def nueva_cotizacion_desde_ot(request, pk_orden):
    """
    Crea una proforma vinculada a una OT existente (Ampliación de presupuesto).
    Hereda automáticamente placa, cliente y vehículo.
    """
    orden = get_object_or_404(OrdenTrabajo, pk=pk_orden)
    num_cotizacion = f"COT-{orden.numero_orden}-{uuid.uuid4().hex[:4].upper()}"
    
    nueva_cotizacion = Cotizacion.objects.create(
        numero_cotizacion=num_cotizacion,
        sucursal=orden.sucursal,
        orden=orden, # Aquí se vincula a la OT padre
        estado="PENDIENTE"
    )
    
    messages.success(request, f"Proforma de ampliación {num_cotizacion} generada para la OT {orden.numero_orden}.")
    return redirect('detalle_cotizacion', pk=nueva_cotizacion.pk)


@login_required
def detalle_cotizacion(request, pk):
    """
    Lienzo para agregar repuestos y servicios tentativos.
    No afecta stock ni contabilidad real.
    """
    cotizacion = get_object_or_404(Cotizacion, pk=pk)
    sucursal_activa = obtener_sucursal_activa(request)
    categorias = Categoria.objects.all().order_by("nombre")

    if request.method == "POST":
        with transaction.atomic():
            # Limpieza de items previos
            cotizacion.insumos_cotizados.all().delete()
            cotizacion.servicios_cotizados.all().delete()

            # --- PROCESAR REPUESTOS TENTATIVOS ---
            rep_ids = request.POST.getlist("rep_producto_id[]")
            rep_desc = request.POST.getlist("rep_descripcion[]")
            rep_pu = request.POST.getlist("rep_pu[]")
            rep_cant = request.POST.getlist("rep_cantidad[]")

            for i in range(len(rep_desc)):
                desc = rep_desc[i].strip()
                if not desc: continue
                
                CotizacionInsumoDetalle.objects.create(
                    cotizacion=cotizacion,
                    producto_id=rep_ids[i] if i < len(rep_ids) and rep_ids[i] else None,
                    descripcion_factura=desc.upper(),
                    cantidad=parse_decimal(rep_cant[i] if i < len(rep_cant) else "1", Decimal("1")),
                    precio_unitario=parse_decimal(rep_pu[i] if i < len(rep_pu) else "0", Decimal("0")),
                    orden_item=i + 1
                )

            # --- PROCESAR SERVICIOS TENTATIVOS ---
            serv_desc = request.POST.getlist("moi_descripcion[]")
            serv_pu = request.POST.getlist("moi_pu[]")
            serv_cant = request.POST.getlist("moi_cantidad[]")

            for i in range(len(serv_desc)):
                desc = serv_desc[i].strip()
                if not desc: continue

                CotizacionServicioDetalle.objects.create(
                    cotizacion=cotizacion,
                    descripcion_servicio=desc.upper(),
                    cantidad=parse_decimal(serv_cant[i] if i < len(serv_cant) else "1", Decimal("1")),
                    precio_unitario=parse_decimal(serv_pu[i] if i < len(serv_pu) else "0", Decimal("0")),
                    orden_item=i + 1
                )

            cotizacion.calcular_total()
            messages.success(request, "Cambios guardados en la proforma.")
            return redirect('detalle_cotizacion', pk=cotizacion.pk)

    return render(request, "cotizaciones/detalle_cotizacion.html", {
        "cotizacion": cotizacion,
        "categorias_inventario": categorias,
        "sucursal_activa": sucursal_activa
    })


@login_required
def aprobar_cotizacion(request, pk):
    """
    Inyecta los datos de la proforma en la Orden de Trabajo oficial.
    Solo aquí se dispara el descuento de stock real.
    """
    cotizacion = get_object_or_404(Cotizacion, pk=pk)
    
    if request.method == "POST":
        if cotizacion.estado != 'PENDIENTE':
            messages.error(request, "Esta cotización ya fue procesada.")
            return redirect('dashboard')

        with transaction.atomic():
            # Si es de mostrador y no tiene OT, crear la OT primero
            if not cotizacion.orden:
                expediente = obtener_o_crear_expediente(
                    cotizacion.cliente, cotizacion.nombre_cliente_final, 
                    cotizacion.placa, cotizacion.vehiculo, cotizacion.anio_vehiculo
                )
                nueva_ot = OrdenTrabajo.objects.create(
                    numero_orden=generar_numero_orden(),
                    sucursal=cotizacion.sucursal,
                    expediente=expediente,
                    usuario_receptor=request.user,
                    cliente=cotizacion.cliente,
                    cliente_respaldo=cotizacion.cliente_respaldo,
                    placa=cotizacion.placa,
                    vehiculo=cotizacion.vehiculo,
                    anio_vehiculo=cotizacion.anio_vehiculo,
                    estado="ABIERTA"
                )
                cotizacion.orden = nueva_ot

            orden_destino = cotizacion.orden

            # 1. Mover Insumos (Aquí se activa MovimientoStock en el save del detalle)
            for item in cotizacion.insumos_cotizados.all():
                OrdenInsumoDetalle.objects.create(
                    orden=orden_destino,
                    producto=item.producto,
                    descripcion_factura=item.descripcion_factura,
                    cantidad=item.cantidad,
                    precio_unitario=item.precio_unitario
                )

            # 2. Mover Servicios
            for serv in cotizacion.servicios_cotizados.all():
                OrdenServicioDetalle.objects.create(
                    orden=orden_destino,
                    descripcion_servicio=serv.descripcion_servicio,
                    cantidad=serv.cantidad,
                    precio_unitario=serv.precio_unitario
                )

            cotizacion.estado = 'APROBADA'
            cotizacion.save()
            orden_destino.calcular_total()

        messages.success(request, f"Proforma aprobada. Items cargados a la OT {orden_destino.numero_orden}.")
        return redirect('detalle_orden', pk=orden_destino.pk)

    return redirect('dashboard')