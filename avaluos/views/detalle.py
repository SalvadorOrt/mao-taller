from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from avaluos.models import (
    AvaluoMecanico,
    CompresionCilindro,
    EstadoAvaluo,
    EstadoRevision,
    FotoAvaluo,
    RespuestaSiNo,
    ResultadoInspeccionAvaluo,
    ResultadoPruebaRuta,
    ResultadoRevisionSiNo,
)

from .crear import crear_resultados_iniciales


TOTAL_PASOS = 7


# =========================================================
# UTILIDADES GENERALES
# =========================================================

def limpiar_texto(valor):
    """
    Limpia un texto y devuelve None cuando queda vacío.
    """

    if valor is None:
        return None

    valor = str(valor).strip()

    return valor or None


def convertir_entero(valor):
    """
    Convierte un valor a entero.

    Devuelve None si está vacío o no es válido.
    """

    valor = limpiar_texto(valor)

    if valor is None:
        return None

    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def convertir_decimal(valor):
    """
    Convierte un valor a Decimal.

    Acepta tanto coma como punto decimal.
    Devuelve None cuando el campo está vacío.
    """

    valor = limpiar_texto(valor)

    if valor is None:
        return None

    valor = valor.replace(",", ".")

    try:
        return Decimal(valor)
    except (InvalidOperation, TypeError, ValueError):
        return None


def convertir_booleano_triestado(valor):
    """
    Convierte las respuestas del formulario:

    SI -> True
    NO -> False
    vacío -> None
    """

    valor = str(valor or "").strip().upper()

    if valor in {
        "SI",
        "TRUE",
        "1",
        "ON",
        "YES",
    }:
        return True

    if valor in {
        "NO",
        "FALSE",
        "0",
    }:
        return False

    return None


def validar_numero_no_negativo(
    valor,
    nombre_campo,
):
    """
    Verifica que un valor Decimal no sea negativo.
    """

    if (
        valor is not None
        and valor < Decimal("0.00")
    ):
        raise ValidationError({
            nombre_campo: (
                "El valor no puede ser negativo."
            ),
        })


def validar_acceso_avaluo(
    request,
    avaluo,
):
    """
    ADMIN puede acceder a cualquier sucursal.

    Los demás usuarios solamente pueden acceder a
    avalúos pertenecientes a su sucursal.
    """

    if request.user.rol == "ADMIN":
        return True

    if not request.user.sucursal_id:
        return False

    return (
        avaluo.orden.sucursal_id
        == request.user.sucursal_id
    )


def obtener_avaluo(pk):
    """
    Obtiene el avalúo con las relaciones principales.
    """

    return get_object_or_404(
        AvaluoMecanico.objects.select_related(
            "orden",
            "orden__sucursal",
            "orden__cliente",
            "orden__expediente",
            "creado_por",
            "actualizado_por",
            "evaluador",
            "responsable_taller",
        ),
        pk=pk,
    )


def obtener_paso_destino(
    paso_actual,
    accion,
):
    """
    Determina a qué paso debe ir el usuario
    después de guardar.
    """

    if accion == "anterior":
        return max(
            paso_actual - 1,
            1,
        )

    if accion == "siguiente":
        return min(
            paso_actual + 1,
            TOTAL_PASOS,
        )

    return paso_actual


def nombre_error_validacion(error):
    """
    Convierte ValidationError en un texto entendible.
    """

    if hasattr(error, "message_dict"):
        mensajes = []

        for campo, errores in error.message_dict.items():
            for mensaje in errores:
                mensajes.append(
                    f"{campo}: {mensaje}"
                )

        return " ".join(mensajes)

    if hasattr(error, "messages"):
        return " ".join(error.messages)

    return str(error)


# =========================================================
# PASO 1
# DATOS GENERALES Y EQUIPAMIENTO
# =========================================================

def guardar_paso_1_datos(
    request,
    avaluo,
):
    avaluo.solicitado_por = limpiar_texto(
        request.POST.get(
            "solicitado_por",
        )
    )

    fecha_avaluo = limpiar_texto(
        request.POST.get(
            "fecha_avaluo",
        )
    )

    if fecha_avaluo:
        fecha_convertida = parse_date(
            fecha_avaluo
        )

        if not fecha_convertida:
            raise ValidationError({
                "fecha_avaluo": (
                    "La fecha ingresada no es válida."
                ),
            })

        avaluo.fecha_avaluo = fecha_convertida

    avaluo.numero_motor = limpiar_texto(
        request.POST.get(
            "numero_motor",
        )
    )

    avaluo.motor = limpiar_texto(
        request.POST.get(
            "motor",
        )
    )

    avaluo.cilindraje = limpiar_texto(
        request.POST.get(
            "cilindraje",
        )
    )

    tipo_transmision = (
        request.POST.get(
            "tipo_transmision",
            "NO_DEFINIDA",
        )
        .strip()
        .upper()
    )

    transmisiones_validas = {
        codigo
        for codigo, _ in
        AvaluoMecanico.TIPOS_TRANSMISION
    }

    if (
        tipo_transmision
        not in transmisiones_validas
    ):
        tipo_transmision = "NO_DEFINIDA"

    avaluo.tipo_transmision = (
        tipo_transmision
    )

    avaluo.aire_acondicionado = (
        convertir_booleano_triestado(
            request.POST.get(
                "aire_acondicionado",
            )
        )
    )

    avaluo.vidrios_electricos = (
        convertir_booleano_triestado(
            request.POST.get(
                "vidrios_electricos",
            )
        )
    )

    avaluo.alarma = (
        convertir_booleano_triestado(
            request.POST.get(
                "alarma",
            )
        )
    )

    avaluo.aros = (
        convertir_booleano_triestado(
            request.POST.get(
                "aros",
            )
        )
    )

    avaluo.radio = (
        convertir_booleano_triestado(
            request.POST.get(
                "radio",
            )
        )
    )

    avaluo.cierre_centralizado = (
        convertir_booleano_triestado(
            request.POST.get(
                "cierre_centralizado",
            )
        )
    )


# =========================================================
# PASOS 2 Y 4
# INSPECCIÓN NRR / RRM / RRT
# =========================================================

def guardar_resultados_inspeccion(
    request,
    avaluo,
    secciones,
):
    resultados = (
        ResultadoInspeccionAvaluo.objects
        .select_for_update()
        .filter(
            avaluo=avaluo,
            item__activo=True,
            item__seccion__in=secciones,
        )
        .select_related(
            "item",
        )
    )

    estados_validos = {
        codigo
        for codigo, _ in
        EstadoRevision.choices
    }

    for resultado in resultados:
        prefijo = (
            f"inspeccion_{resultado.item_id}"
        )

        estado = (
            request.POST.get(
                f"{prefijo}_estado",
                EstadoRevision.NO_REVISADO,
            )
            .strip()
            .upper()
        )

        if estado not in estados_validos:
            estado = (
                EstadoRevision.NO_REVISADO
            )

        observacion = limpiar_texto(
            request.POST.get(
                f"{prefijo}_observacion",
            )
        )

        diagnostico = limpiar_texto(
            request.POST.get(
                f"{prefijo}_diagnostico",
            )
        )

        costo_estimado = convertir_decimal(
            request.POST.get(
                f"{prefijo}_costo",
            )
        )

        validar_numero_no_negativo(
            costo_estimado,
            f"{prefijo}_costo",
        )

        resultado.estado = estado

        # Si no requiere reparación, se conserva solamente
        # la observación y se limpian diagnóstico y costo.
        if estado in {
            EstadoRevision.NO_REVISADO,
            EstadoRevision.NRR,
        }:
            resultado.observacion = observacion
            resultado.diagnostico = None
            resultado.costo_estimado = None

        else:
            resultado.observacion = observacion
            resultado.diagnostico = diagnostico
            resultado.costo_estimado = (
                costo_estimado
            )

        resultado.save()


def guardar_paso_2_apariencia(
    request,
    avaluo,
):
    guardar_resultados_inspeccion(
        request=request,
        avaluo=avaluo,
        secciones=[
            "EXTERIOR",
            "INTERIOR",
        ],
    )


def guardar_paso_4_mecanica(
    request,
    avaluo,
):
    guardar_resultados_inspeccion(
        request=request,
        avaluo=avaluo,
        secciones=[
            "MECANICA",
            "ELECTRICO",
            "FRENOS",
            "OTROS",
        ],
    )


# =========================================================
# PASO 3
# MOTOR, COMPRESIÓN, PARTÍCULAS Y FUGAS
# =========================================================

def guardar_paso_3_motor(
    request,
    avaluo,
):
    avaluo.ruido_motor_otros = limpiar_texto(
        request.POST.get(
            "ruido_motor_otros",
        )
    )

    unidades_validas = {
        codigo
        for codigo, _ in
        CompresionCilindro.UNIDADES
    }

    compresiones = (
        CompresionCilindro.objects
        .select_for_update()
        .filter(
            avaluo=avaluo,
        )
        .order_by(
            "numero_cilindro",
        )
    )

    for compresion in compresiones:
        numero = (
            compresion.numero_cilindro
        )

        valor = convertir_decimal(
            request.POST.get(
                f"compresion_{numero}_valor",
            )
        )

        validar_numero_no_negativo(
            valor,
            f"compresion_{numero}_valor",
        )

        unidad = (
            request.POST.get(
                f"compresion_{numero}_unidad",
                "PSI",
            )
            .strip()
            .upper()
        )

        if unidad not in unidades_validas:
            unidad = "PSI"

        observacion = limpiar_texto(
            request.POST.get(
                f"compresion_{numero}_observacion",
            )
        )

        compresion.valor = valor
        compresion.unidad = unidad
        compresion.observacion = observacion

        compresion.save()

    respuestas_validas = {
        codigo
        for codigo, _ in
        RespuestaSiNo.choices
    }

    resultados_revision = (
        ResultadoRevisionSiNo.objects
        .select_for_update()
        .filter(
            avaluo=avaluo,
            item__activo=True,
        )
        .select_related(
            "item",
        )
    )

    for resultado in resultados_revision:
        prefijo = (
            f"revision_{resultado.item_id}"
        )

        respuesta = (
            request.POST.get(
                f"{prefijo}_respuesta",
                RespuestaSiNo.NO_REVISADO,
            )
            .strip()
            .upper()
        )

        if respuesta not in respuestas_validas:
            respuesta = (
                RespuestaSiNo.NO_REVISADO
            )

        resultado.respuesta = respuesta

        resultado.observacion = limpiar_texto(
            request.POST.get(
                f"{prefijo}_observacion",
            )
        )

        resultado.save()


# =========================================================
# PASO 5
# PRUEBA DE RUTA
# =========================================================

def guardar_paso_5_ruta(
    request,
    avaluo,
):
    respuestas_validas = {
        codigo
        for codigo, _ in
        RespuestaSiNo.choices
    }

    resultados = (
        ResultadoPruebaRuta.objects
        .select_for_update()
        .filter(
            avaluo=avaluo,
            item__activo=True,
        )
        .select_related(
            "item",
        )
    )

    for resultado in resultados:
        prefijo = (
            f"ruta_{resultado.item_id}"
        )

        respuesta = (
            request.POST.get(
                f"{prefijo}_respuesta",
                RespuestaSiNo.NO_REVISADO,
            )
            .strip()
            .upper()
        )

        if respuesta not in respuestas_validas:
            respuesta = (
                RespuestaSiNo.NO_REVISADO
            )

        resultado.respuesta = respuesta

        if resultado.item.permite_observacion:
            resultado.observacion = limpiar_texto(
                request.POST.get(
                    f"{prefijo}_observacion",
                )
            )
        else:
            resultado.observacion = None

        resultado.save()


# =========================================================
# PASO 6
# DIAGNÓSTICO, VEHÍCULO USADO Y FOTOGRAFÍAS
# =========================================================

def limpiar_datos_vehiculo_usado(
    avaluo,
):
    """
    Limpia los datos comerciales cuando se desactiva
    la opción de vehículo usado.
    """

    avaluo.recibido_como_parte_pago_de = None
    avaluo.vendedor_que_solicita = None
    avaluo.anio_matricula = None
    avaluo.anio_modelo_usado = None
    avaluo.cilindraje_usado = None
    avaluo.reserva_dominio = None
    avaluo.color_usado = None
    avaluo.propietario = None
    avaluo.telefono_propietario = None
    avaluo.direccion_propietario = None
    avaluo.identificacion_propietario = None
    avaluo.avaluo_comercial = None
    avaluo.precio_recepcion = None
    avaluo.costo_reparacion = None
    avaluo.costo_total = None


def guardar_paso_6_diagnostico_fotos(
    request,
    avaluo,
):
    avaluo.diagnostico_general = limpiar_texto(
        request.POST.get(
            "diagnostico_general",
        )
    )

    avaluo.reparaciones_recomendadas = (
        limpiar_texto(
            request.POST.get(
                "reparaciones_recomendadas",
            )
        )
    )

    avaluo.observaciones_generales = (
        limpiar_texto(
            request.POST.get(
                "observaciones_generales",
            )
        )
    )

    avaluo.aplica_vehiculo_usado = (
        request.POST.get(
            "aplica_vehiculo_usado",
        )
        in {
            "1",
            "on",
            "ON",
            "true",
            "TRUE",
            "SI",
        }
    )

    if avaluo.aplica_vehiculo_usado:
        avaluo.recibido_como_parte_pago_de = (
            limpiar_texto(
                request.POST.get(
                    "recibido_como_parte_pago_de",
                )
            )
        )

        avaluo.vendedor_que_solicita = (
            limpiar_texto(
                request.POST.get(
                    "vendedor_que_solicita",
                )
            )
        )

        avaluo.anio_matricula = convertir_entero(
            request.POST.get(
                "anio_matricula",
            )
        )

        avaluo.anio_modelo_usado = (
            convertir_entero(
                request.POST.get(
                    "anio_modelo_usado",
                )
            )
        )

        avaluo.cilindraje_usado = limpiar_texto(
            request.POST.get(
                "cilindraje_usado",
            )
        )

        avaluo.reserva_dominio = (
            convertir_booleano_triestado(
                request.POST.get(
                    "reserva_dominio",
                )
            )
        )

        avaluo.color_usado = limpiar_texto(
            request.POST.get(
                "color_usado",
            )
        )

        avaluo.propietario = limpiar_texto(
            request.POST.get(
                "propietario",
            )
        )

        avaluo.telefono_propietario = (
            limpiar_texto(
                request.POST.get(
                    "telefono_propietario",
                )
            )
        )

        avaluo.direccion_propietario = (
            limpiar_texto(
                request.POST.get(
                    "direccion_propietario",
                )
            )
        )

        avaluo.identificacion_propietario = (
            limpiar_texto(
                request.POST.get(
                    "identificacion_propietario",
                )
            )
        )

        avaluo.avaluo_comercial = (
            convertir_decimal(
                request.POST.get(
                    "avaluo_comercial",
                )
            )
        )

        avaluo.precio_recepcion = (
            convertir_decimal(
                request.POST.get(
                    "precio_recepcion",
                )
            )
        )

        avaluo.costo_reparacion = (
            convertir_decimal(
                request.POST.get(
                    "costo_reparacion",
                )
            )
        )

        avaluo.costo_total = convertir_decimal(
            request.POST.get(
                "costo_total",
            )
        )

        validar_numero_no_negativo(
            avaluo.avaluo_comercial,
            "avaluo_comercial",
        )

        validar_numero_no_negativo(
            avaluo.precio_recepcion,
            "precio_recepcion",
        )

        validar_numero_no_negativo(
            avaluo.costo_reparacion,
            "costo_reparacion",
        )

        validar_numero_no_negativo(
            avaluo.costo_total,
            "costo_total",
        )

    else:
        limpiar_datos_vehiculo_usado(
            avaluo,
        )

    # =====================================================
    # FOTOGRAFÍAS
    # =====================================================

    fotografias = request.FILES.getlist(
        "fotografias",
    )

    tipo_foto = (
        request.POST.get(
            "tipo_foto",
            "OTRA",
        )
        .strip()
        .upper()
    )

    tipos_foto_validos = {
        codigo
        for codigo, _ in
        FotoAvaluo.TIPOS_FOTO
    }

    if tipo_foto not in tipos_foto_validos:
        tipo_foto = "OTRA"

    descripcion_foto = limpiar_texto(
        request.POST.get(
            "descripcion_foto",
        )
    )

    ultimo_orden = (
        FotoAvaluo.objects
        .filter(
            avaluo=avaluo,
        )
        .order_by(
            "-orden_visual",
        )
        .values_list(
            "orden_visual",
            flat=True,
        )
        .first()
        or 0
    )

    for indice, fotografia in enumerate(
        fotografias,
        start=1,
    ):
        FotoAvaluo.objects.create(
            avaluo=avaluo,
            imagen=fotografia,
            tipo_foto=tipo_foto,
            descripcion=descripcion_foto,
            orden_visual=(
                ultimo_orden + indice
            ),
            subida_por=request.user,
        )


# =========================================================
# PASO 7
# RESULTADO GENERAL Y RESPONSABLE
# =========================================================

def guardar_paso_7_resumen(
    request,
    avaluo,
):
    resultado_general = (
        request.POST.get(
            "resultado_general",
            "SIN_DEFINIR",
        )
        .strip()
        .upper()
    )

    resultados_validos = {
        codigo
        for codigo, _ in
        AvaluoMecanico.RESULTADOS_GENERALES
    }

    if resultado_general not in resultados_validos:
        resultado_general = "SIN_DEFINIR"

    avaluo.resultado_general = (
        resultado_general
    )

    responsable_id = convertir_entero(
        request.POST.get(
            "responsable_taller",
        )
    )

    if responsable_id:
        Usuario = get_user_model()

        responsable = (
            Usuario.objects
            .filter(
                pk=responsable_id,
                is_active=True,
            )
            .first()
        )

        if responsable:
            avaluo.responsable_taller = (
                responsable
            )

    else:
        avaluo.responsable_taller = None

    # Cualquier rol autorizado puede realizar el avalúo.
    # Si todavía no existe evaluador, se asigna al usuario
    # que está guardando esta sección.
    if not avaluo.evaluador_id:
        avaluo.evaluador = request.user


# =========================================================
# GUARDAR EL PASO ACTUAL
# =========================================================

@transaction.atomic
def guardar_detalle_avaluo(
    request,
    avaluo,
    paso,
):
    """
    Guarda el contenido del paso y redirige según la
    acción seleccionada.
    """

    # Bloqueamos nuevamente el registro durante el guardado.
    avaluo = (
        AvaluoMecanico.objects
        .select_for_update()
        .select_related(
            "orden",
            "orden__sucursal",
        )
        .get(
            pk=avaluo.pk,
        )
    )

    if avaluo.estado != EstadoAvaluo.BORRADOR:
        messages.error(
            request,
            "El avalúo ya no se encuentra disponible para edición.",
        )

        return redirect(
            "avaluos:detalle_avaluo",
            pk=avaluo.pk,
        )

    accion = (
        request.POST.get(
            "accion",
            "guardar",
        )
        .strip()
        .lower()
    )

    acciones_validas = {
        "guardar",
        "anterior",
        "siguiente",
        "finalizar",
    }

    if accion not in acciones_validas:
        accion = "guardar"

    try:
        if paso == 1:
            guardar_paso_1_datos(
                request,
                avaluo,
            )

        elif paso == 2:
            guardar_paso_2_apariencia(
                request,
                avaluo,
            )

        elif paso == 3:
            guardar_paso_3_motor(
                request,
                avaluo,
            )

        elif paso == 4:
            guardar_paso_4_mecanica(
                request,
                avaluo,
            )

        elif paso == 5:
            guardar_paso_5_ruta(
                request,
                avaluo,
            )

        elif paso == 6:
            guardar_paso_6_diagnostico_fotos(
                request,
                avaluo,
            )

        elif paso == 7:
            guardar_paso_7_resumen(
                request,
                avaluo,
            )

        avaluo.actualizado_por = request.user

        # La finalización se realiza después de guardar
        # los datos del paso 7.
        if (
            paso == 7
            and accion == "finalizar"
        ):
            confirmar = (
                request.POST.get(
                    "confirmar_finalizacion",
                )
                in {
                    "1",
                    "on",
                    "ON",
                    "true",
                    "TRUE",
                }
            )

            if not confirmar:
                raise ValidationError(
                    "Debes confirmar que revisaste la información."
                )

            if (
                avaluo.resultado_general
                == "SIN_DEFINIR"
            ):
                raise ValidationError(
                    "Debes seleccionar un resultado general."
                )

            if not avaluo.evaluador_id:
                avaluo.evaluador = request.user

            avaluo.estado = (
                EstadoAvaluo.FINALIZADO
            )

            avaluo.finalizado_en = (
                timezone.now()
            )

            avaluo.save()

            messages.success(
                request,
                "El avalúo fue finalizado correctamente.",
            )

            return redirect(
                "avaluos:detalle_avaluo",
                pk=avaluo.pk,
            )

        avaluo.save()

    except ValidationError as error:
        transaction.set_rollback(True)

        messages.error(
            request,
            nombre_error_validacion(
                error
            ),
        )

        return redirect(
            "avaluos:detalle_avaluo_paso",
            pk=avaluo.pk,
            paso=paso,
        )

    messages.success(
        request,
        "Los datos fueron guardados correctamente.",
    )

    paso_destino = obtener_paso_destino(
        paso_actual=paso,
        accion=accion,
    )

    return redirect(
        "avaluos:detalle_avaluo_paso",
        pk=avaluo.pk,
        paso=paso_destino,
    )


# =========================================================
# RESUMEN DEL AVALÚO
# =========================================================

def obtener_resumen_avaluo(avaluo):
    resultados_inspeccion = (
        ResultadoInspeccionAvaluo.objects
        .filter(
            avaluo=avaluo,
            item__activo=True,
        )
    )

    resultados_revision = (
        ResultadoRevisionSiNo.objects
        .filter(
            avaluo=avaluo,
            item__activo=True,
        )
    )

    resultados_ruta = (
        ResultadoPruebaRuta.objects
        .filter(
            avaluo=avaluo,
            item__activo=True,
        )
    )

    return {
        "total_nrr": (
            resultados_inspeccion
            .filter(
                estado=EstadoRevision.NRR,
            )
            .count()
        ),

        "total_rrm": (
            resultados_inspeccion
            .filter(
                estado=EstadoRevision.RRM,
            )
            .count()
        ),

        "total_rrt": (
            resultados_inspeccion
            .filter(
                estado=EstadoRevision.RRT,
            )
            .count()
        ),

        "inspecciones_pendientes": (
            resultados_inspeccion
            .filter(
                estado=(
                    EstadoRevision.NO_REVISADO
                ),
            )
            .count()
        ),

        "revisiones_pendientes": (
            resultados_revision
            .filter(
                respuesta=(
                    RespuestaSiNo.NO_REVISADO
                ),
            )
            .count()
        ),

        "ruta_pendiente": (
            resultados_ruta
            .filter(
                respuesta=(
                    RespuestaSiNo.NO_REVISADO
                ),
            )
            .count()
        ),

        "total_fotos": (
            FotoAvaluo.objects
            .filter(
                avaluo=avaluo,
            )
            .count()
        ),
    }


# =========================================================
# VISTA PRINCIPAL
# =========================================================

@login_required
def detalle_avaluo(
    request,
    pk,
    paso=1,
):
    avaluo = obtener_avaluo(pk)

    if not validar_acceso_avaluo(
        request,
        avaluo,
    ):
        messages.error(
            request,
            "No tienes permiso para acceder a este avalúo.",
        )

        return redirect(
            "avaluos:ordenes_pendientes",
        )

    if paso < 1 or paso > TOTAL_PASOS:
        return redirect(
            "avaluos:detalle_avaluo_paso",
            pk=avaluo.pk,
            paso=1,
        )

    # Si se agregaron nuevos elementos al catálogo después
    # de crear el avalúo, se generan sus respuestas faltantes.
    crear_resultados_iniciales(
        avaluo,
    )

    puede_editar = (
        avaluo.estado
        == EstadoAvaluo.BORRADOR
    )

    if request.method == "POST":
        if not puede_editar:
            messages.error(
                request,
                "El avalúo está finalizado o anulado y no puede modificarse.",
            )

            return redirect(
                "avaluos:detalle_avaluo",
                pk=avaluo.pk,
            )

        return guardar_detalle_avaluo(
            request=request,
            avaluo=avaluo,
            paso=paso,
        )

    # =====================================================
    # CONSULTAS PARA LOS PASOS
    # =====================================================

    resultados_apariencia = (
        ResultadoInspeccionAvaluo.objects
        .filter(
            avaluo=avaluo,
            item__seccion__in=[
                "EXTERIOR",
                "INTERIOR",
            ],
            item__activo=True,
        )
        .select_related(
            "item",
        )
        .order_by(
            "item__seccion",
            "item__orden_visual",
            "item__nombre",
        )
    )

    resultados_mecanica = (
        ResultadoInspeccionAvaluo.objects
        .filter(
            avaluo=avaluo,
            item__seccion__in=[
                "MECANICA",
                "ELECTRICO",
                "FRENOS",
                "OTROS",
            ],
            item__activo=True,
        )
        .select_related(
            "item",
        )
        .order_by(
            "item__seccion",
            "item__orden_visual",
            "item__nombre",
        )
    )

    resultados_revision = (
        ResultadoRevisionSiNo.objects
        .filter(
            avaluo=avaluo,
            item__activo=True,
        )
        .select_related(
            "item",
        )
        .order_by(
            "item__seccion",
            "item__orden_visual",
            "item__nombre",
        )
    )

    resultados_ruta = (
        ResultadoPruebaRuta.objects
        .filter(
            avaluo=avaluo,
            item__activo=True,
        )
        .select_related(
            "item",
        )
        .order_by(
            "item__orden_visual",
            "item__pregunta",
        )
    )

    compresiones = (
        CompresionCilindro.objects
        .filter(
            avaluo=avaluo,
        )
        .order_by(
            "numero_cilindro",
        )
    )

    fotografias = (
        FotoAvaluo.objects
        .filter(
            avaluo=avaluo,
        )
        .select_related(
            "subida_por",
        )
        .order_by(
            "orden_visual",
            "fecha_subida",
            "id",
        )
    )

    # =====================================================
    # RESPONSABLES DISPONIBLES
    # =====================================================

    Usuario = get_user_model()

    responsables_disponibles = (
        Usuario.objects
        .filter(
            is_active=True,
        )
        .filter(
            Q(
                rol="ADMIN",
            )
            | Q(
                sucursal_id=(
                    avaluo.orden.sucursal_id
                ),
            )
        )
        .order_by(
            "first_name",
            "last_name",
            "username",
        )
    )

    contexto = {
        "avaluo": avaluo,
        "orden": avaluo.orden,
        "paso": paso,
        "total_pasos": TOTAL_PASOS,
        "puede_editar": puede_editar,

        "resultados_apariencia": (
            resultados_apariencia
        ),

        "resultados_mecanica": (
            resultados_mecanica
        ),

        "resultados_revision": (
            resultados_revision
        ),

        "resultados_ruta": (
            resultados_ruta
        ),

        "compresiones": compresiones,
        "fotografias": fotografias,

        "tipos_foto": (
            FotoAvaluo.TIPOS_FOTO
        ),

        "responsables_disponibles": (
            responsables_disponibles
        ),
    }

    contexto.update(
        obtener_resumen_avaluo(
            avaluo,
        )
    )

    return render(
        request,
        "avaluos/detalle_avaluo.html",
        contexto,
    )


# =========================================================
# ELIMINAR FOTOGRAFÍA
# =========================================================

@login_required
@require_POST
@transaction.atomic
def eliminar_foto_avaluo(
    request,
    foto_id,
):
    foto = get_object_or_404(
        FotoAvaluo.objects
        .select_for_update()
        .select_related(
            "avaluo",
            "avaluo__orden",
            "avaluo__orden__sucursal",
        ),
        pk=foto_id,
    )

    avaluo = foto.avaluo

    if not validar_acceso_avaluo(
        request,
        avaluo,
    ):
        messages.error(
            request,
            "No tienes permiso para eliminar esta fotografía.",
        )

        return redirect(
            "avaluos:ordenes_pendientes",
        )

    if (
        avaluo.estado
        != EstadoAvaluo.BORRADOR
    ):
        messages.error(
            request,
            "No se pueden eliminar fotografías de un avalúo finalizado o anulado.",
        )

        return redirect(
            "avaluos:detalle_avaluo",
            pk=avaluo.pk,
        )

    archivo = foto.imagen

    foto.delete()

    if archivo:
        archivo.delete(
            save=False,
        )

    messages.success(
        request,
        "La fotografía fue eliminada correctamente.",
    )

    return redirect(
        "avaluos:detalle_avaluo_paso",
        pk=avaluo.pk,
        paso=6,
    )