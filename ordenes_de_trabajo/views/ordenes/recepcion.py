from django.shortcuts import  redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from ...models import (
    OrdenTrabajo,
    FotoRecepcionVehiculo,
    OrdenCroquisDanio,
    OrdenSintoma,
    OrdenTrabajoSolicitado,
)
from ..utils import (
     cargar_json_lista, procesar_imagen_base64,
    
    puede_operar_orden_desde_sucursal_activa
)# =========================================================
# EDITAR RECEPCIÓN DE ORDEN (MODAL RÁPIDO COMPLETO)
# =========================================================
@login_required
def editar_recepcion_orden(request, pk):
    import uuid
    import requests
    import xml.etree.ElementTree as ET
    from django.db import transaction
    from django.conf import settings
    from ...models import ExpedienteVehiculo 

    orden = get_object_or_404(OrdenTrabajo, pk=pk)

    if not puede_operar_orden_desde_sucursal_activa(request, orden):
        messages.error(request, "No tienes permiso para editar órdenes de otra sucursal.")
        return redirect("lista_ordenes")

    if orden.estado != "ABIERTA":
        messages.error(request, "No se puede editar la recepción de una orden cerrada o anulada.")
        return redirect("detalle_orden", pk=pk)

    if request.method == "POST":
        # 1. CAPTURAR TEXTOS DEL MODAL
        nueva_placa = request.POST.get("placa", "").strip().upper()
        nuevo_vehiculo = request.POST.get("vehiculo", "").strip().upper()
        nuevo_anio = request.POST.get("anio_vehiculo", "").strip()
        nuevo_color = request.POST.get("color", "").strip().upper()
        nuevo_km = request.POST.get("kilometraje", "").strip()
        nueva_clave = request.POST.get("clave_encendido", "").strip()

        orden.observaciones_recepcion = request.POST.get("observaciones_recepcion", orden.observaciones_recepcion or "").strip()
        sintomas_json = cargar_json_lista(request.POST.get("sintomas_json", ""))
        trabajos_json = cargar_json_lista(request.POST.get("trabajos_json", ""))
        croquis_base64 = request.POST.get("imagen_croquis_base64", "").strip()

        fotos_nuevas = request.FILES.getlist("fotos_recepcion")
        descripcion_fotos = request.POST.get("descripcion_fotos", "").strip()
        fotos_eliminar = request.POST.getlist("fotos_eliminar")

        try:
            with transaction.atomic():
                
                # ====================================================
                # MAGIA DEL VEHÍCULO: REGLA -> "EL ASESOR MANDA"
                # ====================================================
                
                # CASO A: EL ASESOR CAMBIÓ LA PLACA
                if nueva_placa and nueva_placa != orden.placa:
                    expediente_existente = ExpedienteVehiculo.objects.filter(placa=nueva_placa).first()

                    if expediente_existente:
                        orden.expediente = expediente_existente
                        orden.placa = nueva_placa
                        orden.vehiculo = expediente_existente.vehiculo
                        orden.anio_vehiculo = expediente_existente.anio_vehiculo
                    else:
                        user_placa = getattr(settings, "PLACA_API_USERNAME", "SalvadorOrtega")
                        url_placa = f"https://www.placaapi.ec/API/reg.asmx/CheckEcuador?RegistrationNumber={nueva_placa}&username={user_placa}"
                        
                        try:
                            resp_placa = requests.get(url_placa, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                            if resp_placa.status_code == 200:
                                root = ET.fromstring(resp_placa.content)
                                json_text = None
                                for elem in root.iter():
                                    if elem.tag.endswith("vehicleJson"):
                                        json_text = elem.text
                                        break
                                
                                if json_text:
                                    import json
                                    datos_auto = json.loads(json_text)
                                    marca = datos_auto.get("MakeDescription", {}).get("CurrentTextValue", "") if isinstance(datos_auto.get("MakeDescription"), dict) else str(datos_auto.get("MakeDescription", ""))
                                    modelo = datos_auto.get("ModelDescription", {}).get("CurrentTextValue", "") if isinstance(datos_auto.get("ModelDescription"), dict) else str(datos_auto.get("ModelDescription", ""))
                                    anio_real = datos_auto.get("Year")
                                    
                                    desc_real = f"{marca} {modelo}".strip().upper()
                                    
                                    # ¡BLINDAJE 1! Si la API trajo basura, pero el asesor escribió un nombre a mano, ignoramos a la API.
                                    if nuevo_vehiculo and nuevo_vehiculo != orden.vehiculo:
                                        desc_real = nuevo_vehiculo
                                    elif not desc_real:
                                        desc_real = nuevo_vehiculo
                                    
                                    expediente = ExpedienteVehiculo.objects.create(
                                        placa=nueva_placa,
                                        vehiculo=desc_real,
                                        anio_vehiculo=int(anio_real) if anio_real and str(anio_real).isdigit() else None,
                                        cliente=orden.cliente
                                    )
                                    orden.expediente = expediente
                                    orden.placa = nueva_placa
                                    orden.vehiculo = desc_real
                                    if anio_real and str(anio_real).isdigit():
                                        orden.anio_vehiculo = int(anio_real)
                                else:
                                    raise ValueError("XML sin JSON")
                            else:
                                raise ValueError("Falla API Placas")
                                
                        except Exception:
                            expediente = ExpedienteVehiculo.objects.create(
                                placa=nueva_placa,
                                vehiculo=nuevo_vehiculo or "VEHÍCULO DESCONOCIDO",
                                anio_vehiculo=int(nuevo_anio) if nuevo_anio.isdigit() else None,
                                cliente=orden.cliente
                            )
                            orden.expediente = expediente
                            orden.placa = nueva_placa
                            orden.vehiculo = nuevo_vehiculo
                            if nuevo_anio.isdigit(): orden.anio_vehiculo = int(nuevo_anio)

                # CASO B: LA PLACA NO CAMBIÓ (Solo quiere arreglar el nombre "BMW" -> "HYUNDAI")
                else:
                    # ¡BLINDAJE 2! Verificamos si el asesor borró el nombre viejo y puso uno nuevo
                    if nuevo_vehiculo and nuevo_vehiculo != orden.vehiculo:
                        orden.vehiculo = nuevo_vehiculo
                        if orden.expediente:
                            orden.expediente.vehiculo = nuevo_vehiculo
                            
                            # ESTA ES LA CLAVE: Borramos la "basura" de la API para que no lo reescriba en el frontend
                            orden.expediente.descripcion_api = ""
                            orden.expediente.marca_api = ""
                            orden.expediente.modelo_api = ""
                            
                    if nuevo_anio and str(nuevo_anio).isdigit():
                        orden.anio_vehiculo = int(nuevo_anio)
                        if orden.expediente:
                            orden.expediente.anio_vehiculo = int(nuevo_anio)

                # ====================================================
                # ACTUALIZACIONES COMUNES (KM, COLOR, CLAVE)
                # ====================================================
                if nuevo_km.isdigit():
                    orden.kilometraje = int(nuevo_km)
                if nuevo_color:
                    orden.color = nuevo_color

                orden.clave_encendido = nueva_clave
                
                # Guardamos todas las correcciones al expediente de un solo golpe
                if orden.expediente:
                    orden.expediente.clave_encendido = nueva_clave
                    orden.expediente.save() 

                orden.save()

                # ====================================================
                # GUARDAR SÍNTOMAS, CROQUIS Y FOTOS
                # ====================================================
                orden.sintomas_items.all().delete()
                for idx, item in enumerate(sintomas_json, start=1):
                    desc = str(item.get("descripcion", "")).strip()
                    if desc: OrdenSintoma.objects.create(orden=orden, descripcion=desc, orden_item=idx)

                orden.trabajos_solicitados_items.all().delete()
                for idx, item in enumerate(trabajos_json, start=1):
                    desc = str(item.get("descripcion", "")).strip()
                    if desc: OrdenTrabajoSolicitado.objects.create(orden=orden, descripcion_manual=desc, orden_item=idx)

                if croquis_base64:
                    archivo_croquis = procesar_imagen_base64(croquis_base64)
                    if archivo_croquis:
                        croquis_obj, _ = OrdenCroquisDanio.objects.get_or_create(orden=orden)
                        if croquis_obj.imagen_generada: croquis_obj.imagen_generada.delete(save=False)
                        croquis_obj.imagen_generada.save(f"croquis_upd_{orden.numero_orden}_{uuid.uuid4().hex[:8]}.png", archivo_croquis, save=True)

                if fotos_eliminar:
                    for foto in FotoRecepcionVehiculo.objects.filter(orden=orden, id__in=fotos_eliminar):
                        if foto.imagen: foto.imagen.delete(save=False)
                        foto.delete()

                for foto in fotos_nuevas:
                    FotoRecepcionVehiculo.objects.create(orden=orden, imagen=foto, descripcion=descripcion_fotos)

            messages.success(request, "¡Recepción y datos del vehículo actualizados con éxito!")
            
        except Exception as e:
            messages.error(request, f"Ocurrió un error al guardar: {str(e)}")

    return redirect("detalle_orden", pk=orden.pk)