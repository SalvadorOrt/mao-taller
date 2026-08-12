import json
import uuid
import requests
import xml.etree.ElementTree as ET

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect

from ...models import (
    Cliente,
    ExpedienteVehiculo,
    Tecnico,
    OrdenTrabajo,
    FotoRecepcionVehiculo,
    OrdenCroquisDanio,
    OrdenSintoma,
    OrdenTrabajoSolicitado,
)

from ..utils import (
    cargar_json_lista,
    procesar_imagen_base64,
    puede_operar_orden_desde_sucursal_activa,
)


# =========================================================
# EDITAR RECEPCIÓN DE ORDEN
# MODAL RÁPIDO COMPLETO
# =========================================================
@login_required
def editar_recepcion_orden(request, pk):

    orden = get_object_or_404(
        OrdenTrabajo.objects.select_related(
            "cliente",
            "expediente",
        ),
        pk=pk,
    )

    # =====================================================
    # PERMISOS DE SUCURSAL
    # =====================================================
    if not puede_operar_orden_desde_sucursal_activa(
        request,
        orden,
    ):
        messages.error(
            request,
            "No tienes permiso para editar órdenes de otra sucursal."
        )

        return redirect(
            "lista_ordenes"
        )

    # =====================================================
    # SOLO ÓRDENES ABIERTAS
    # =====================================================
    if orden.estado != "ABIERTA":

        messages.error(
            request,
            "No se puede editar la recepción de una orden "
            "cerrada o anulada."
        )

        return redirect(
            "detalle_orden",
            pk=pk,
        )

    # =====================================================
    # SOLO PROCESAMOS POST
    # =====================================================
    if request.method != "POST":

        return redirect(
            "detalle_orden",
            pk=orden.pk,
        )

    # =====================================================
    # DATOS DEL VEHÍCULO
    # =====================================================
    nueva_placa = (
        request.POST
        .get("placa", "")
        .strip()
        .upper()
        .replace("-", "")
        .replace(" ", "")
    )

    nuevo_vehiculo = (
        request.POST
        .get("vehiculo", "")
        .strip()
        .upper()
    )

    nuevo_anio = (
        request.POST
        .get("anio_vehiculo", "")
        .strip()
    )

    nuevo_color = (
        request.POST
        .get("color", "")
        .strip()
        .upper()
    )

    nuevo_km = (
        request.POST
        .get("kilometraje", "")
        .strip()
    )

    nueva_clave = (
        request.POST
        .get("clave_encendido", "")
        .strip()
    )

    # =====================================================
    # CLIENTE CONSULTADO DESDE EL MODAL
    # =====================================================
    nuevo_cliente_id = (
        request.POST
        .get("cliente_id", "")
        .strip()
    )

    nueva_identificacion_cliente = (
        request.POST
        .get(
            "cliente_identificacion",
            ""
        )
        .strip()
    )

    # =====================================================
    # TÉCNICOS
    # =====================================================
    tecnicos_ids = request.POST.getlist(
        "tecnicos"
    )

    # =====================================================
    # OBSERVACIONES
    # =====================================================
    orden.observaciones_recepcion = (
        request.POST
        .get(
            "observaciones_recepcion",
            orden.observaciones_recepcion or "",
        )
        .strip()
    )

    # =====================================================
    # SÍNTOMAS / TRABAJOS
    # =====================================================
    sintomas_json = cargar_json_lista(
        request.POST.get(
            "sintomas_json",
            "",
        )
    )

    trabajos_json = cargar_json_lista(
        request.POST.get(
            "trabajos_json",
            "",
        )
    )

    # =====================================================
    # CROQUIS
    # =====================================================
    croquis_base64 = (
        request.POST
        .get(
            "imagen_croquis_base64",
            "",
        )
        .strip()
    )

    # =====================================================
    # FOTOS
    # =====================================================
    fotos_nuevas = request.FILES.getlist(
        "fotos_recepcion"
    )

    descripcion_fotos = (
        request.POST
        .get(
            "descripcion_fotos",
            "",
        )
        .strip()
    )

    fotos_eliminar = request.POST.getlist(
        "fotos_eliminar"
    )

    # =====================================================
    # GUARDADO
    # =====================================================
    try:

        with transaction.atomic():

            # =================================================
            # BLOQUEAMOS OT MIENTRAS SE EDITA
            # =================================================
            orden = (
                OrdenTrabajo.objects
                .select_for_update()
                .get(pk=orden.pk)
            )

            # =================================================
            # VALIDAR QUE SIGA ABIERTA
            # =================================================
            if orden.estado != "ABIERTA":

                raise ValueError(
                    "La orden fue cerrada o anulada mientras "
                    "se estaba editando."
                )

            # =================================================
            # 1. DETERMINAR CLIENTE CORRECTO
            # =================================================
            cliente_destino = orden.cliente

            identificacion_actual = ""

            if (
                orden.cliente
                and orden.cliente.identificacion
            ):
                identificacion_actual = str(
                    orden.cliente.identificacion
                ).strip()

            # -------------------------------------------------
            # SI EL MODAL ENVIÓ UN CLIENTE CONSULTADO
            # -------------------------------------------------
            if nuevo_cliente_id:

                if not nuevo_cliente_id.isdigit():

                    raise ValueError(
                        "El identificador del cliente no es válido."
                    )

                cliente_destino = (
                    Cliente.objects
                    .select_for_update()
                    .filter(
                        pk=int(nuevo_cliente_id)
                    )
                    .first()
                )

                if not cliente_destino:

                    raise ValueError(
                        "El cliente seleccionado ya no existe."
                    )

                # =============================================
                # SEGURIDAD:
                # ID Y CÉDULA DEBEN CORRESPONDER
                # =============================================
                identificacion_cliente_destino = str(
                    cliente_destino.identificacion or ""
                ).strip()

                if (
                    nueva_identificacion_cliente
                    and
                    identificacion_cliente_destino
                    != nueva_identificacion_cliente
                ):
                    raise ValueError(
                        "La identificación consultada no coincide "
                        "con el cliente seleccionado. "
                        "Vuelve a consultar la cédula o RUC."
                    )

            # -------------------------------------------------
            # CAMBIÓ LA CÉDULA PERO NO CONSULTÓ
            # -------------------------------------------------
            elif (
                nueva_identificacion_cliente
                and
                nueva_identificacion_cliente
                != identificacion_actual
            ):

                raise ValueError(
                    "Cambiaste la cédula o RUC del cliente. "
                    "Debes presionar Consultar antes de guardar."
                )

            # =================================================
            # 2. CORREGIR PLACA / EXPEDIENTE
            # =================================================
            placa_actual_normalizada = (
                (orden.placa or "")
                .strip()
                .upper()
                .replace("-", "")
                .replace(" ", "")
            )

            if (
                nueva_placa
                and
                nueva_placa != placa_actual_normalizada
            ):

                # =============================================
                # BUSCAR SI YA EXISTE ESA PLACA
                # =============================================
                expediente_existente = (
                    ExpedienteVehiculo.objects
                    .select_for_update()
                    .filter(
                        placa=nueva_placa
                    )
                    .order_by("-id")
                    .first()
                )

                # =============================================
                # LA PLACA YA EXISTE
                # =============================================
                if expediente_existente:

                    orden.expediente = (
                        expediente_existente
                    )

                    orden.placa = (
                        expediente_existente.placa
                        or nueva_placa
                    )

                    # Si el usuario escribió vehículo,
                    # respetamos la corrección manual.
                    if nuevo_vehiculo:

                        orden.vehiculo = (
                            nuevo_vehiculo
                        )

                        expediente_existente.vehiculo = (
                            nuevo_vehiculo
                        )

                    else:

                        orden.vehiculo = (
                            expediente_existente.vehiculo
                            or orden.vehiculo
                        )

                    # Año manual si fue enviado.
                    if (
                        nuevo_anio
                        and
                        nuevo_anio.isdigit()
                    ):

                        orden.anio_vehiculo = int(
                            nuevo_anio
                        )

                        expediente_existente.anio_vehiculo = int(
                            nuevo_anio
                        )

                    else:

                        orden.anio_vehiculo = (
                            expediente_existente.anio_vehiculo
                        )

                # =============================================
                # PLACA NO EXISTE:
                # CONSULTAMOS API
                # =============================================
                else:

                    expediente = None

                    try:

                        user_placa = (
                            settings.PLACA_API_USERNAME
                        )

                        url_placa = (
                            "https://www.placaapi.ec/"
                            "API/reg.asmx/CheckEcuador"
                            f"?RegistrationNumber={nueva_placa}"
                            f"&username={user_placa}"
                        )

                        resp_placa = requests.get(
                            url_placa,
                            headers={
                                "User-Agent": "Mozilla/5.0"
                            },
                            timeout=15,
                        )

                        if resp_placa.status_code != 200:

                            raise ValueError(
                                "Falla API Placas"
                            )

                        root = ET.fromstring(
                            resp_placa.content
                        )

                        json_text = None

                        for elem in root.iter():

                            if elem.tag.endswith(
                                "vehicleJson"
                            ):
                                json_text = elem.text
                                break

                        if not json_text:

                            raise ValueError(
                                "XML sin JSON del vehículo"
                            )

                        datos_auto = json.loads(
                            json_text
                        )

                        # =====================================
                        # CREAR EXPEDIENTE
                        # =====================================
                        expediente = ExpedienteVehiculo(
                            placa=nueva_placa,
                            cliente=cliente_destino,
                            cliente_respaldo=(
                                cliente_destino.nombre_completo
                                if cliente_destino
                                else orden.cliente_respaldo
                            ),
                        )

                        # Aprovechamos el método del modelo
                        expediente.cargar_desde_api_placa(
                            datos_auto
                        )

                        expediente.fecha_ultima_consulta_placa = (
                            timezone.now()
                        )

                        # =====================================
                        # CORRECCIONES MANUALES TIENEN
                        # PRIORIDAD SOBRE API
                        # =====================================
                        if nuevo_vehiculo:

                            expediente.vehiculo = (
                                nuevo_vehiculo
                            )

                        if (
                            nuevo_anio
                            and
                            nuevo_anio.isdigit()
                        ):

                            expediente.anio_vehiculo = int(
                                nuevo_anio
                            )

                        if not expediente.vehiculo:

                            expediente.vehiculo = (
                                "VEHÍCULO DESCONOCIDO"
                            )

                        expediente.save()

                    except Exception:

                        # =====================================
                        # FALLBACK SI FALLA API
                        # =====================================
                        expediente = (
                            ExpedienteVehiculo.objects
                            .create(
                                placa=nueva_placa,
                                vehiculo=(
                                    nuevo_vehiculo
                                    or "VEHÍCULO DESCONOCIDO"
                                ),
                                anio_vehiculo=(
                                    int(nuevo_anio)
                                    if nuevo_anio.isdigit()
                                    else None
                                ),
                                cliente=cliente_destino,
                                cliente_respaldo=(
                                    cliente_destino.nombre_completo
                                    if cliente_destino
                                    else orden.cliente_respaldo
                                ),
                            )
                        )

                    orden.expediente = expediente
                    orden.placa = nueva_placa
                    orden.vehiculo = (
                        expediente.vehiculo
                        or nuevo_vehiculo
                        or "VEHÍCULO DESCONOCIDO"
                    )

                    orden.anio_vehiculo = (
                        expediente.anio_vehiculo
                    )

            # =================================================
            # 3. MISMA PLACA:
            # ACTUALIZAR DATOS MANUALES
            # =================================================
            else:

                if (
                    nuevo_vehiculo
                    and
                    nuevo_vehiculo != (
                        orden.vehiculo or ""
                    ).strip().upper()
                ):

                    orden.vehiculo = (
                        nuevo_vehiculo
                    )

                    if orden.expediente:

                        orden.expediente.vehiculo = (
                            nuevo_vehiculo
                        )

                        # La descripción fue corregida
                        # manualmente, así que limpiamos
                        # datos descriptivos API anteriores.
                        orden.expediente.descripcion_api = ""
                        orden.expediente.marca_api = ""
                        orden.expediente.modelo_api = ""

                if (
                    nuevo_anio
                    and
                    nuevo_anio.isdigit()
                ):

                    orden.anio_vehiculo = int(
                        nuevo_anio
                    )

                    if orden.expediente:

                        orden.expediente.anio_vehiculo = int(
                            nuevo_anio
                        )

            # =================================================
            # 4. SINCRONIZAR CLIENTE
            #    OT + EXPEDIENTE
            # =================================================
            if cliente_destino:

                orden.cliente = (
                    cliente_destino
                )

                orden.cliente_respaldo = (
                    cliente_destino.nombre_completo
                )

                if orden.expediente:

                    orden.expediente.cliente = (
                        cliente_destino
                    )

                    orden.expediente.cliente_respaldo = (
                        cliente_destino.nombre_completo
                    )

            # =================================================
            # 5. KILOMETRAJE
            # =================================================
            if nuevo_km:

                if not nuevo_km.isdigit():

                    raise ValueError(
                        "El kilometraje debe contener "
                        "solo números."
                    )

                orden.kilometraje = int(
                    nuevo_km
                )

            # =================================================
            # 6. COLOR
            # =================================================
            if nuevo_color:

                orden.color = (
                    nuevo_color
                )

            # =================================================
            # 7. CLAVE / PIN
            # =================================================
            orden.clave_encendido = (
                nueva_clave
            )

            # =================================================
            # 8. GUARDAR EXPEDIENTE
            # =================================================
            if orden.expediente:

                orden.expediente.clave_encendido = (
                    nueva_clave
                )

                orden.expediente.save()

            # =================================================
            # 9. GUARDAR ORDEN
            # =================================================
            orden.save()

            # =================================================
            # 10. TÉCNICOS
            # =================================================
            tecnicos_validos = (
                Tecnico.objects
                .filter(
                    id__in=tecnicos_ids
                )
            )

            orden.tecnicos.set(
                tecnicos_validos
            )

            # =================================================
            # 11. SÍNTOMAS
            # =================================================
            orden.sintomas_items.all().delete()

            for idx, item in enumerate(
                sintomas_json,
                start=1,
            ):

                desc = str(
                    item.get(
                        "descripcion",
                        "",
                    )
                ).strip()

                if desc:

                    OrdenSintoma.objects.create(
                        orden=orden,
                        descripcion=desc,
                        orden_item=idx,
                    )

            # =================================================
            # 12. TRABAJOS SOLICITADOS
            # =================================================
            (
                orden
                .trabajos_solicitados_items
                .all()
                .delete()
            )

            for idx, item in enumerate(
                trabajos_json,
                start=1,
            ):

                desc = str(
                    item.get(
                        "descripcion",
                        "",
                    )
                ).strip()

                if desc:

                    OrdenTrabajoSolicitado.objects.create(
                        orden=orden,
                        descripcion_manual=desc,
                        orden_item=idx,
                    )

            # =================================================
            # 13. CROQUIS
            # =================================================
            if croquis_base64:

                archivo_croquis = (
                    procesar_imagen_base64(
                        croquis_base64
                    )
                )

                if archivo_croquis:

                    croquis_obj, _ = (
                        OrdenCroquisDanio.objects
                        .get_or_create(
                            orden=orden
                        )
                    )

                    if croquis_obj.imagen_generada:

                        croquis_obj.imagen_generada.delete(
                            save=False
                        )

                    croquis_obj.imagen_generada.save(
                        (
                            f"croquis_upd_"
                            f"{orden.numero_orden}_"
                            f"{uuid.uuid4().hex[:8]}.png"
                        ),
                        archivo_croquis,
                        save=True,
                    )

            # =================================================
            # 14. ELIMINAR FOTOS
            # =================================================
            if fotos_eliminar:

                fotos_a_eliminar = (
                    FotoRecepcionVehiculo.objects
                    .filter(
                        orden=orden,
                        id__in=fotos_eliminar,
                    )
                )

                for foto in fotos_a_eliminar:

                    if foto.imagen:

                        foto.imagen.delete(
                            save=False
                        )

                    foto.delete()

            # =================================================
            # 15. NUEVAS FOTOS
            # =================================================
            for foto in fotos_nuevas:

                FotoRecepcionVehiculo.objects.create(
                    orden=orden,
                    imagen=foto,
                    descripcion=descripcion_fotos,
                )

        # =====================================================
        # ÉXITO
        # =====================================================
        messages.success(
            request,
            (
                "¡Recepción, cliente, vehículo y técnicos "
                "actualizados con éxito!"
            )
        )

    except Exception as e:

        messages.error(
            request,
            f"Ocurrió un error al guardar: {str(e)}"
        )

    return redirect(
        "detalle_orden",
        pk=orden.pk,
    )