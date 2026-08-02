from collections import OrderedDict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.clickjacking import (
    xframe_options_sameorigin,
)

from avaluos.models import (
    AvaluoMecanico,
    CompresionCilindro,
    FotoAvaluo,
    ResultadoEquipamientoAvaluo,
    ResultadoInspeccionAvaluo,
    ResultadoPruebaRuta,
    ResultadoRevisionSiNo,
)
from empresa.models import EmpresaEmisora


# =========================================================
# VALIDAR ACCESO AL AVALÚO
# =========================================================

def usuario_puede_ver_avaluo(
    request,
    avaluo,
):
    """
    Determina si el usuario puede consultar e imprimir el avalúo.

    Puede acceder cuando:

    - Es administrador.
    - Tiene permiso para cambiar de sucursal.
    - El avalúo pertenece a su sucursal asignada.
    """

    if (
        request.user.rol == "ADMIN"
        or request.user.puede_cambiar_sucursal
    ):
        return True

    if not request.user.sucursal_id:
        return False

    return (
        avaluo.orden.sucursal_id
        == request.user.sucursal_id
    )


# =========================================================
# OBTENER EMPRESA DEL AVALÚO
# =========================================================

def obtener_empresa_avaluo(avaluo):
    """
    Obtiene primero la empresa asociada a la sucursal de la OT.

    Si la sucursal no tiene empresa, utiliza la primera empresa
    emisora activa configurada en el sistema.
    """

    orden = avaluo.orden

    if (
        orden.sucursal
        and orden.sucursal.empresa
    ):
        return orden.sucursal.empresa

    return (
        EmpresaEmisora.objects
        .filter(
            activo=True,
        )
        .order_by(
            "id",
        )
        .first()
    )


# =========================================================
# AGRUPAR RESULTADOS DE INSPECCIÓN
# =========================================================

def agrupar_resultados_inspeccion(resultados):
    """
    Agrupa los resultados NRR/RRM/RRT según la sección
    configurada en cada ítem.
    """

    grupos = OrderedDict()

    for resultado in resultados:
        codigo_seccion = resultado.item.seccion

        if codigo_seccion not in grupos:
            grupos[codigo_seccion] = {
                "codigo": codigo_seccion,
                "nombre": resultado.item.get_seccion_display(),
                "resultados": [],
            }

        grupos[codigo_seccion]["resultados"].append(
            resultado
        )

    return list(
        grupos.values()
    )


# =========================================================
# AGRUPAR REVISIONES SÍ / NO
# =========================================================

def agrupar_resultados_revision(resultados):
    """
    Agrupa las revisiones Sí/No según la sección definida
    en el catálogo.
    """

    grupos = OrderedDict()

    for resultado in resultados:
        codigo_seccion = resultado.item.seccion

        if codigo_seccion not in grupos:
            grupos[codigo_seccion] = {
                "codigo": codigo_seccion,
                "nombre": resultado.item.get_seccion_display(),
                "resultados": [],
            }

        grupos[codigo_seccion]["resultados"].append(
            resultado
        )

    return list(
        grupos.values()
    )


# =========================================================
# AGRUPAR EQUIPAMIENTO
# =========================================================

def agrupar_resultados_equipamiento(resultados):
    """
    Agrupa el equipamiento del vehículo por categoría.
    """

    grupos = OrderedDict()

    for resultado in resultados:
        categoria = resultado.equipamiento.categoria
        categoria_id = categoria.pk

        if categoria_id not in grupos:
            grupos[categoria_id] = {
                "categoria": categoria,
                "resultados": [],
            }

        grupos[categoria_id]["resultados"].append(
            resultado
        )

    return list(
        grupos.values()
    )


# =========================================================
# RESUMEN NUMÉRICO PARA IMPRESIÓN
# =========================================================

def obtener_totales_impresion(
    resultados_inspeccion,
    resultados_revision,
    resultados_ruta,
    resultados_equipamiento,
):
    """
    Genera contadores generales que pueden mostrarse
    en el resumen final del documento.
    """

    return {
        "total_nrr": sum(
            1
            for resultado in resultados_inspeccion
            if resultado.estado == "NRR"
        ),

        "total_rrm": sum(
            1
            for resultado in resultados_inspeccion
            if resultado.estado == "RRM"
        ),

        "total_rrt": sum(
            1
            for resultado in resultados_inspeccion
            if resultado.estado == "RRT"
        ),

        "total_inspecciones_pendientes": sum(
            1
            for resultado in resultados_inspeccion
            if resultado.estado == "NO_REVISADO"
        ),

        "total_revisiones_si": sum(
            1
            for resultado in resultados_revision
            if resultado.respuesta == "SI"
        ),

        "total_revisiones_no": sum(
            1
            for resultado in resultados_revision
            if resultado.respuesta == "NO"
        ),

        "total_ruta_si": sum(
            1
            for resultado in resultados_ruta
            if resultado.respuesta == "SI"
        ),

        "total_ruta_no": sum(
            1
            for resultado in resultados_ruta
            if resultado.respuesta == "NO"
        ),

        "equipamientos_presentes": sum(
            1
            for resultado in resultados_equipamiento
            if resultado.presencia == "SI"
        ),

        "equipamientos_ausentes": sum(
            1
            for resultado in resultados_equipamiento
            if resultado.presencia == "NO"
        ),

        "equipamientos_funcionan": sum(
            1
            for resultado in resultados_equipamiento
            if (
                resultado.presencia == "SI"
                and resultado.funcionamiento == "FUNCIONA"
            )
        ),

        "equipamientos_no_funcionan": sum(
            1
            for resultado in resultados_equipamiento
            if (
                resultado.presencia == "SI"
                and resultado.funcionamiento == "NO_FUNCIONA"
            )
        ),
    }


# =========================================================
# IMPRESIÓN PRINCIPAL DEL AVALÚO
# =========================================================

@login_required
@xframe_options_sameorigin
def imprimir_avaluo(request, pk):
    """
    Muestra la versión imprimible completa del avalúo mecánico.

    El navegador puede imprimirla directamente o guardarla como PDF.
    """

    avaluo = get_object_or_404(
        AvaluoMecanico.objects
        .select_related(
            "orden",
            "orden__sucursal",
            "orden__sucursal__empresa",
            "orden__cliente",
            "orden__expediente",
            "creado_por",
            "actualizado_por",
            "evaluador",
            "responsable_taller",
        ),
        pk=pk,
    )

    # =====================================================
    # VALIDAR PERMISO
    # =====================================================

    if not usuario_puede_ver_avaluo(
        request=request,
        avaluo=avaluo,
    ):
        messages.error(
            request,
            "No tienes permiso para imprimir este avalúo.",
        )

        return redirect(
            "avaluos:ordenes_pendientes",
        )

    # =====================================================
    # EMPRESA
    # =====================================================

    empresa = obtener_empresa_avaluo(
        avaluo
    )

    # =====================================================
    # INSPECCIÓN NRR / RRM / RRT
    # =====================================================

    resultados_inspeccion = list(
        ResultadoInspeccionAvaluo.objects
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

    grupos_inspeccion = (
        agrupar_resultados_inspeccion(
            resultados_inspeccion
        )
    )

    resultados_apariencia = [
        resultado
        for resultado in resultados_inspeccion
        if resultado.item.seccion in {
            "EXTERIOR",
            "INTERIOR",
        }
    ]

    resultados_mecanica = [
        resultado
        for resultado in resultados_inspeccion
        if resultado.item.seccion in {
            "MECANICA",
            "ELECTRICO",
            "FRENOS",
            "OTROS",
        }
    ]

    # =====================================================
    # REVISIONES SÍ / NO
    # =====================================================

    resultados_revision = list(
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

    grupos_revision = (
        agrupar_resultados_revision(
            resultados_revision
        )
    )

    # =====================================================
    # PRUEBA DE RUTA
    # =====================================================

    resultados_ruta = list(
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

    # =====================================================
    # EQUIPAMIENTO
    # =====================================================

    resultados_equipamiento = list(
        ResultadoEquipamientoAvaluo.objects
        .filter(
            avaluo=avaluo,
            equipamiento__activo=True,
            equipamiento__categoria__activo=True,
        )
        .select_related(
            "equipamiento",
            "equipamiento__categoria",
        )
        .order_by(
            "equipamiento__categoria__orden_visual",
            "equipamiento__categoria__nombre",
            "equipamiento__orden_visual",
            "equipamiento__nombre",
        )
    )

    grupos_equipamiento = (
        agrupar_resultados_equipamiento(
            resultados_equipamiento
        )
    )

    # =====================================================
    # COMPRESIÓN DEL MOTOR
    # =====================================================

    compresiones = list(
        CompresionCilindro.objects
        .filter(
            avaluo=avaluo,
        )
        .order_by(
            "numero_cilindro",
        )
    )

    # =====================================================
    # FOTOGRAFÍAS
    # =====================================================

    fotografias = list(
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
    # TOTALES
    # =====================================================

    resumen = obtener_totales_impresion(
        resultados_inspeccion=(
            resultados_inspeccion
        ),
        resultados_revision=(
            resultados_revision
        ),
        resultados_ruta=(
            resultados_ruta
        ),
        resultados_equipamiento=(
            resultados_equipamiento
        ),
    )

    # =====================================================
    # RENDER
    # =====================================================

    return render(
        request,
        "avaluos/impresion/imprimir_avaluo.html",
        {
            "avaluo": avaluo,
            "orden": avaluo.orden,
            "empresa": empresa,

            "resultados_inspeccion": (
                resultados_inspeccion
            ),
            "resultados_apariencia": (
                resultados_apariencia
            ),
            "resultados_mecanica": (
                resultados_mecanica
            ),
            "grupos_inspeccion": (
                grupos_inspeccion
            ),

            "resultados_revision": (
                resultados_revision
            ),
            "grupos_revision": (
                grupos_revision
            ),

            "resultados_ruta": (
                resultados_ruta
            ),

            "resultados_equipamiento": (
                resultados_equipamiento
            ),
            "grupos_equipamiento": (
                grupos_equipamiento
            ),

            "compresiones": compresiones,
            "fotografias": fotografias,
            "resumen": resumen,

            # Sirve para mostrar una marca de borrador.
            "es_borrador": (
                avaluo.estado == "BORRADOR"
            ),
        },
    )