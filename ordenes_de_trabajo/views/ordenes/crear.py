import uuid
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from ..api import clasificar_vehiculo_con_ia
from ...models import (
    Cliente,
    OrdenTrabajo,
    FotoRecepcionVehiculo,
    OrdenChecklistRecepcion,
    OrdenCroquisDanio,
    OrdenObjetoAdicional,
    OrdenSintoma,
    OrdenTrabajoSolicitado
)
from ..utils import (
    parse_int, cargar_json_lista, procesar_imagen_base64,
    obtener_sucursal_activa, obtener_o_crear_expediente, generar_numero_orden,
   
)
# =========================================================
# CREAR ORDEN
# =========================================================
@login_required
def crear_orden(request):
    import uuid
    from django.db import transaction
    
    sucursal_activa = obtener_sucursal_activa(request)

    if not sucursal_activa:
        return redirect("dashboard")

    if request.method == "POST":
        placa = request.POST.get("placa", "").strip().upper()
        vehiculo = request.POST.get("vehiculo", "").strip().upper()
        color = request.POST.get("color", "").strip().upper()
        color_hex = request.POST.get("color_hex", "#1d1d1f").strip()
        anio = parse_int(request.POST.get("anio_vehiculo"), None)
        kilometraje = parse_int(request.POST.get("kilometraje"), None)
        nivel_combustible = request.POST.get("nivel_combustible", "1/2").strip()
        
        # ---> NUEVO: CAPTURAR LA CLAVE DE ENCENDIDO <---
        clave_encendido = request.POST.get("clave_encendido", "").strip()

        tipo_tarifa_vehiculo = request.POST.get(
            "tipo_tarifa_vehiculo",
            "NO_APLICA"
        ).strip().upper() or "NO_APLICA"

        gama_vehiculo = request.POST.get(
            "gama_vehiculo",
            "NO_APLICA"
        ).strip().upper() or "NO_APLICA"

        tipos_validos = {
            "NO_APLICA", "AUTO", "AUTO_3P", "AUTO_5P", "SUV_3P", "SUV_5P",
            "CAMIONETA_CS", "CAMIONETA_DC", "CAMIONETA_GRANDE",
        }

        gamas_validas = {
            "NO_APLICA", "ECONOMICA", "MEDIA", "MEDIA_ALTA", "ALTA",
            "PREMIUM", "LUJO", "COMERCIAL", "DEPORTIVA",
        }

        if tipo_tarifa_vehiculo not in tipos_validos:
            tipo_tarifa_vehiculo = "NO_APLICA"

        if gama_vehiculo not in gamas_validas:
            gama_vehiculo = "NO_APLICA"

        identificacion = request.POST.get("identificacion", "").strip().upper()

        if identificacion.isdigit() and len(identificacion) == 13:
            tipo_documento = "R"
        elif identificacion.isdigit() and len(identificacion) == 10:
            tipo_documento = "C"
        elif identificacion:
            tipo_documento = "P"
        else:
            tipo_documento = "S"

        nombre_cliente = request.POST.get("nombre_cliente", "").strip().upper()
        telefono = request.POST.get("telefono", "").strip()
        telefono_secundario = request.POST.get("telefono_secundario", "").strip()
        telefono_trabajo = request.POST.get("telefono_trabajo", "").strip()
        email = request.POST.get("email", "").strip().lower()
        direccion = request.POST.get("direccion", "").strip().upper()

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
            return request.POST.get(campo, "").strip().lower() in [
                "on", "true", "1", "yes",
            ]

        checks = {
            "matricula": es_marcado("matricula"),
            "plumas": es_marcado("plumas"),
            "radio": es_marcado("radio"),
            "pantalla": es_marcado("pantalla"),
            "tuerca_seguridad": es_marcado("tuerca_seguridad"),
            "encendedor_cig": es_marcado("encendedor_cig"),
            "triangulos": es_marcado("triangulos"),
            "gata": es_marcado("gata"),
            "herramientas": es_marcado("herramientas"),
            "llanta_emergencia": es_marcado("llanta_emergencia"),
            "faros_lunas": es_marcado("faros_lunas"),
            "tapacubos": es_marcado("tapacubos"),
            "antena": es_marcado("antena"),
        }

        croquis_base64 = request.POST.get("imagen_croquis_base64", "").strip()
        firma_base64 = request.POST.get("firma_base64", "").strip()
        fotos = request.FILES.getlist("fotos_recepcion")
        descripcion_fotos = request.POST.get("descripcion_fotos", "").strip()

        # =====================================================
        # CLIENTE ACTUALIZADO
        # =====================================================
        cliente_obj = None

        if identificacion:
            cliente_obj = Cliente.objects.filter(identificacion=identificacion).first()

            if cliente_obj:
                cliente_obj.tipo_documento = tipo_documento
                if nombre_cliente: cliente_obj.nombre_completo = nombre_cliente
                if telefono: cliente_obj.telefono = telefono
                if telefono_secundario: cliente_obj.telefono_secundario = telefono_secundario
                if telefono_trabajo: cliente_obj.telefono_trabajo = telefono_trabajo
                if email: cliente_obj.email = email
                if direccion: cliente_obj.direccion = direccion
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
                    direccion=direccion,
                )

        elif nombre_cliente:
            cliente_obj = Cliente.objects.create(
                tipo_documento="S",
                identificacion=None,
                nombre_completo=nombre_cliente,
                telefono=telefono,
                telefono_secundario=telefono_secundario,
                telefono_trabajo=telefono_trabajo,
                email=email,
                direccion=direccion,
            )

        with transaction.atomic():
            expediente = obtener_o_crear_expediente(
                cliente_obj,
                nombre_cliente,
                placa,
                vehiculo,
                anio
            )

            # =====================================================
            # ACTUALIZAR EXPEDIENTE (CAMBIO DE DUEÑO Y CLAVE)
            # =====================================================
            expediente_modificado = False

            # 1. Lógica de Cambio de Dueño
            if expediente.cliente != cliente_obj:
                expediente.cliente = cliente_obj
                expediente_modificado = True

            # 2. Lógica de la clave de encendido
            if clave_encendido:
                # Si el asesor escribió una clave hoy, actualizamos el maestro del auto
                expediente.clave_encendido = clave_encendido
                expediente_modificado = True
            else:
                # Si el asesor lo dejó en blanco, traemos la última clave guardada
                clave_encendido = expediente.clave_encendido

            # Guardamos el expediente una sola vez si hubo algún cambio
            if expediente_modificado:
                expediente.save()

            # Crear la orden
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
                color_hex=color_hex,
                anio_vehiculo=anio,
                kilometraje=kilometraje,
                nivel_combustible=nivel_combustible,
                observaciones_recepcion=observaciones_recepcion,
                fecha_ingreso=timezone.now(),
                estado="ABIERTA",
                tipo_tarifa_vehiculo=tipo_tarifa_vehiculo,
                gama_vehiculo=gama_vehiculo,
                clave_encendido=clave_encendido,  # <--- SE GUARDA EN LA ORDEN ACTUAL
            )

            archivo_firma = procesar_imagen_base64(firma_base64)

            if archivo_firma:
                nueva_orden.firma_cliente.save(
                    f"firma_ot_{nueva_orden.numero_orden}_{uuid.uuid4().hex[:8]}.png",
                    archivo_firma,
                    save=False
                )
                nueva_orden.fecha_firma = timezone.now()
                nueva_orden.save()

            OrdenChecklistRecepcion.objects.create(
                orden=nueva_orden,
                **checks
            )

            for idx, item in enumerate(sintomas_json, start=1):
                desc = str(item.get("descripcion", "")).strip()
                if desc:
                    OrdenSintoma.objects.create(
                        orden=nueva_orden,
                        descripcion=desc,
                        orden_item=idx
                    )

            for idx, item in enumerate(trabajos_json, start=1):
                desc = str(item.get("descripcion", "")).strip()
                if desc:
                    OrdenTrabajoSolicitado.objects.create(
                        orden=nueva_orden,
                        descripcion_manual=desc,
                        orden_item=idx
                    )

            for item in objetos_json:
                desc = str(item.get("descripcion", "")).strip()
                if desc:
                    OrdenObjetoAdicional.objects.create(
                        orden=nueva_orden,
                        descripcion=desc,
                        cantidad=max(parse_int(item.get("cantidad"), 1), 1),
                        observacion=str(item.get("observacion", "")).strip() or None
                    )

            archivo_croquis = procesar_imagen_base64(croquis_base64)

            if archivo_croquis:
                croquis_obj = OrdenCroquisDanio.objects.create(
                    orden=nueva_orden,
                    trazos=[],
                    observacion="Croquis generado"
                )
                croquis_obj.imagen_generada.save(
                    f"croquis_ot_{nueva_orden.numero_orden}_{uuid.uuid4().hex[:8]}.png",
                    archivo_croquis
                )

            for foto in fotos:
                FotoRecepcionVehiculo.objects.create(
                    orden=nueva_orden,
                    imagen=foto,
                    descripcion=descripcion_fotos
                )

        return redirect("dashboard")

    return render(
        request,
        "crear_orden.html",
        {
            "sucursal_activa": sucursal_activa
        }
    )