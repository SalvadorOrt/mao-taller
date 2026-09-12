import uuid

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect
from django.utils import timezone

from ...models import (
    Cliente,
    ConfiguracionTributaria,
    FotoRecepcionVehiculo,
    OrdenChecklistRecepcion,
    OrdenCroquisDanio,
    OrdenObjetoAdicional,
    OrdenSintoma,
    OrdenTrabajo,
    OrdenTrabajoSolicitado,
)

from ..utils import (
    cargar_json_lista,
    generar_numero_orden,
    obtener_o_crear_expediente,
    obtener_sucursal_activa,
    parse_int,
    procesar_imagen_base64,
)


# =========================================================
# CREAR ORDEN
# =========================================================
@login_required
def crear_orden(request):

    sucursal_activa = obtener_sucursal_activa(request)

    if not sucursal_activa:
        return redirect("dashboard")

    # =====================================================
    # POST
    # =====================================================
    if request.method == "POST":

        # =================================================
        # VEHÍCULO
        # =================================================
        placa = (
            request.POST
            .get("placa", "")
            .strip()
            .upper()
        )

        vehiculo = (
            request.POST
            .get("vehiculo", "")
            .strip()
            .upper()
        )

        color = (
            request.POST
            .get("color", "")
            .strip()
            .upper()
        )

        color_hex = (
            request.POST
            .get(
                "color_hex",
                "#1d1d1f",
            )
            .strip()
        )

        anio = parse_int(
            request.POST.get(
                "anio_vehiculo"
            ),
            None,
        )

        kilometraje = parse_int(
            request.POST.get(
                "kilometraje"
            ),
            None,
        )

        nivel_combustible = (
            request.POST
            .get(
                "nivel_combustible",
                "1/2",
            )
            .strip()
        )

        clave_encendido = (
            request.POST
            .get(
                "clave_encendido",
                "",
            )
            .strip()
        )

        # =================================================
        # CLIENTE
        # =================================================
        identificacion = (
            request.POST
            .get(
                "identificacion",
                "",
            )
            .strip()
            .upper()
        )

        if (
            identificacion.isdigit()
            and len(identificacion) == 13
        ):
            tipo_documento = "R"

        elif (
            identificacion.isdigit()
            and len(identificacion) == 10
        ):
            tipo_documento = "C"

        elif identificacion:
            tipo_documento = "P"

        else:
            tipo_documento = "S"

        nombre_cliente = (
            request.POST
            .get(
                "nombre_cliente",
                "",
            )
            .strip()
            .upper()
        )

        telefono = (
            request.POST
            .get(
                "telefono",
                "",
            )
            .strip()
        )

        telefono_secundario = (
            request.POST
            .get(
                "telefono_secundario",
                "",
            )
            .strip()
        )

        telefono_trabajo = (
            request.POST
            .get(
                "telefono_trabajo",
                "",
            )
            .strip()
        )

        email = (
            request.POST
            .get(
                "email",
                "",
            )
            .strip()
            .lower()
        )

        direccion = (
            request.POST
            .get(
                "direccion",
                "",
            )
            .strip()
            .upper()
        )

        observaciones_recepcion = (
            request.POST
            .get(
                "observaciones_recepcion",
                "",
            )
            .strip()
        )

        # =================================================
        # JSON RECEPCIÓN
        # =================================================
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

        objetos_json = cargar_json_lista(
            request.POST.get(
                "objetos_json",
                "",
            )
        )

        # =================================================
        # CHECKLIST
        # =================================================
        def es_marcado(campo):

            return (
                request.POST
                .get(
                    campo,
                    "",
                )
                .strip()
                .lower()
                in [
                    "on",
                    "true",
                    "1",
                    "yes",
                ]
            )

        checks = {
            "matricula":
                es_marcado(
                    "matricula"
                ),

            "plumas":
                es_marcado(
                    "plumas"
                ),

            "radio":
                es_marcado(
                    "radio"
                ),

            "pantalla":
                es_marcado(
                    "pantalla"
                ),

            "tuerca_seguridad":
                es_marcado(
                    "tuerca_seguridad"
                ),

            "encendedor_cig":
                es_marcado(
                    "encendedor_cig"
                ),

            "triangulos":
                es_marcado(
                    "triangulos"
                ),

            "gata":
                es_marcado(
                    "gata"
                ),

            "herramientas":
                es_marcado(
                    "herramientas"
                ),

            "llanta_emergencia":
                es_marcado(
                    "llanta_emergencia"
                ),

            "faros_lunas":
                es_marcado(
                    "faros_lunas"
                ),

            "tapacubos":
                es_marcado(
                    "tapacubos"
                ),

            "antena":
                es_marcado(
                    "antena"
                ),
        }

        # =================================================
        # CROQUIS / FIRMA / FOTOS
        # =================================================
        croquis_base64 = (
            request.POST
            .get(
                "imagen_croquis_base64",
                "",
            )
            .strip()
        )

        firma_base64 = (
            request.POST
            .get(
                "firma_base64",
                "",
            )
            .strip()
        )

        fotos = request.FILES.getlist(
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

        # =================================================
        # CLIENTE
        # =================================================
        cliente_obj = None

        if identificacion:

            cliente_obj = (
                Cliente.objects
                .filter(
                    identificacion=
                        identificacion
                )
                .first()
            )

            # =============================================
            # CLIENTE EXISTENTE
            # =============================================
            if cliente_obj:

                cliente_obj.tipo_documento = (
                    tipo_documento
                )

                if nombre_cliente:
                    cliente_obj.nombre_completo = (
                        nombre_cliente
                    )

                if telefono:
                    cliente_obj.telefono = (
                        telefono
                    )

                if telefono_secundario:
                    cliente_obj.telefono_secundario = (
                        telefono_secundario
                    )

                if telefono_trabajo:
                    cliente_obj.telefono_trabajo = (
                        telefono_trabajo
                    )

                if email:
                    cliente_obj.email = (
                        email
                    )

                if direccion:
                    cliente_obj.direccion = (
                        direccion
                    )

                cliente_obj.save()

            # =============================================
            # CLIENTE NUEVO
            # =============================================
            else:

                cliente_obj = (
                    Cliente.objects.create(
                        tipo_documento=
                            tipo_documento,

                        identificacion=
                            identificacion,

                        nombre_completo=
                            nombre_cliente
                            or
                            "CONSUMIDOR FINAL",

                        telefono=
                            telefono,

                        telefono_secundario=
                            telefono_secundario,

                        telefono_trabajo=
                            telefono_trabajo,

                        email=
                            email,

                        direccion=
                            direccion,
                    )
                )

        # =================================================
        # CLIENTE SIN DOCUMENTO
        # =================================================
        elif nombre_cliente:

            cliente_obj = (
                Cliente.objects.create(
                    tipo_documento="S",
                    identificacion=None,
                    nombre_completo=
                        nombre_cliente,
                    telefono=
                        telefono,
                    telefono_secundario=
                        telefono_secundario,
                    telefono_trabajo=
                        telefono_trabajo,
                    email=
                        email,
                    direccion=
                        direccion,
                )
            )

        # =================================================
        # TRANSACCIÓN
        # =================================================
        with transaction.atomic():

            # =============================================
            # EXPEDIENTE
            # =============================================
            expediente = (
                obtener_o_crear_expediente(
                    cliente_obj,
                    nombre_cliente,
                    placa,
                    vehiculo,
                    anio,
                )
            )

            # =============================================
            # ACTUALIZAR EXPEDIENTE
            # =============================================
            expediente_modificado = False

            # Cambio de dueño
            if (
                expediente.cliente
                != cliente_obj
            ):

                expediente.cliente = (
                    cliente_obj
                )

                expediente_modificado = True

            # =============================================
            # CLAVE / PIN
            # =============================================
            if clave_encendido:

                expediente.clave_encendido = (
                    clave_encendido
                )

                expediente_modificado = True

            else:

                clave_encendido = (
                    expediente.clave_encendido
                )

            if expediente_modificado:
                expediente.save()

            # =============================================
            # CONFIGURACIÓN TRIBUTARIA
            # =============================================
            configuracion_iva = (
                ConfiguracionTributaria.objects
                .filter(
                    activa=True
                )
                .order_by(
                    "-fecha_inicio",
                    "-id",
                )
                .first()
            )

            porcentaje_iva = (
                configuracion_iva.porcentaje_iva
                if configuracion_iva
                else Decimal("0.00")
            )

            # =============================================
            # CREAR ORDEN
            # =============================================
            nueva_orden = (
                OrdenTrabajo.objects.create(
                    numero_orden=
                        generar_numero_orden(),

                    sucursal=
                        sucursal_activa,

                    expediente=
                        expediente,

                    usuario_receptor=
                        request.user,

                    cliente=
                        cliente_obj,

                    cliente_respaldo=
                        nombre_cliente
                        or None,

                    placa=
                        placa,

                    vehiculo=
                        vehiculo,

                    color=
                        color,

                    color_hex=
                        color_hex,

                    anio_vehiculo=
                        anio,

                    kilometraje=
                        kilometraje,

                    nivel_combustible=
                        nivel_combustible,

                    observaciones_recepcion=
                        observaciones_recepcion,

                    fecha_ingreso=
                        timezone.now(),

                    estado=
                        "ABIERTA",

                    clave_encendido=
                        clave_encendido,

                    configuracion_iva=
                        configuracion_iva,

                    porcentaje_iva=
                        porcentaje_iva,
                )
            )

            # =============================================
            # FIRMA
            # =============================================
            archivo_firma = (
                procesar_imagen_base64(
                    firma_base64
                )
            )

            if archivo_firma:

                nueva_orden.firma_cliente.save(
                    (
                        f"firma_ot_"
                        f"{nueva_orden.numero_orden}_"
                        f"{uuid.uuid4().hex[:8]}.png"
                    ),
                    archivo_firma,
                    save=False,
                )

                nueva_orden.fecha_firma = (
                    timezone.now()
                )

                nueva_orden.save()

            # =============================================
            # CHECKLIST
            # =============================================
            OrdenChecklistRecepcion.objects.create(
                orden=nueva_orden,
                **checks,
            )

            # =============================================
            # SÍNTOMAS
            # =============================================
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
                        orden=
                            nueva_orden,

                        descripcion=
                            desc,

                        orden_item=
                            idx,
                    )

            # =============================================
            # TRABAJOS SOLICITADOS
            # =============================================
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
                        orden=
                            nueva_orden,

                        descripcion_manual=
                            desc,

                        orden_item=
                            idx,
                    )

            # =============================================
            # OBJETOS ADICIONALES
            # =============================================
            for item in objetos_json:

                desc = str(
                    item.get(
                        "descripcion",
                        "",
                    )
                ).strip()

                if desc:

                    OrdenObjetoAdicional.objects.create(
                        orden=
                            nueva_orden,

                        descripcion=
                            desc,

                        cantidad=max(
                            parse_int(
                                item.get(
                                    "cantidad"
                                ),
                                1,
                            ),
                            1,
                        ),

                        observacion=(
                            str(
                                item.get(
                                    "observacion",
                                    "",
                                )
                            ).strip()
                            or None
                        ),
                    )

            # =================================================
            # CROQUIS
            # =================================================
            #
            # VERSIONES:
            #
            # 1 = croquis antiguo
            #     base_autos.svg + imagen de trazos
            #
            # 2 = croquis nuevo
            #     PNG completo con:
            #     - izquierda
            #     - frente
            #     - derecha
            #     - trasera
            #     - superior
            #     - trazos realizados
            #
            # Toda OT creada desde este formulario utiliza
            # automáticamente la versión 2.
            # =================================================
            archivo_croquis = (
                procesar_imagen_base64(
                    croquis_base64
                )
            )

            if archivo_croquis:

                croquis_obj = (
                    OrdenCroquisDanio.objects.create(
                        orden=
                            nueva_orden,

                        trazos=[],

                        version_croquis=2,

                        observacion=
                            "Croquis generado",
                    )
                )

                croquis_obj.imagen_generada.save(
                    (
                        f"croquis_ot_"
                        f"{nueva_orden.numero_orden}_"
                        f"{uuid.uuid4().hex[:8]}.png"
                    ),
                    archivo_croquis,
                )

            # =============================================
            # FOTOS
            # =============================================
            for foto in fotos:

                FotoRecepcionVehiculo.objects.create(
                    orden=
                        nueva_orden,

                    imagen=
                        foto,

                    descripcion=
                        descripcion_fotos,
                )

        # =================================================
        # TERMINADO
        # =================================================
        return redirect(
            "dashboard"
        )

    # =====================================================
    # GET
    # =====================================================
    return render(
        request,
        "crear_orden.html",
        {
            "sucursal_activa":
                sucursal_activa,
        },
    )