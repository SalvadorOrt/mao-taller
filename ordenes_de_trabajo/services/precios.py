# ordenes_de_trabajo/services/precios.py



from datetime import date

from decimal import Decimal, ROUND_HALF_UP

from difflib import SequenceMatcher

import re

import unicodedata



from django.db.models import Q, Sum

from django.utils import timezone



from inventario.models import (

    AliasProducto,

    CodigoProducto,

    StockSucursal,

)



from servicios.models import ServicioCatalogo



from ordenes_de_trabajo.models import (

    OrdenInsumoDetalle,

    OrdenInsumoHistorico,

    OrdenServicioDetalle,

    OrdenServicioHistorico,

)





# ==========================================================

# CONSTANTES

# ==========================================================



CERO = Decimal("0.00")



UMBRAL_COINCIDENCIA = 35.0

UMBRAL_COMPARABLE = 60.0



MAXIMO_COINCIDENCIAS_RESPUESTA = 30

MAXIMO_COMPARABLES_SUGERENCIA = 15
# La búsqueda histórica sigue siendo GLOBAL:
# no se filtra por sucursal.
#
# Estos límites únicamente reducen el conjunto preliminar
# que PostgreSQL entrega al cálculo de similitud en Python.
MAXIMO_CANDIDATOS_MO_ACTUALES = 500
MAXIMO_CANDIDATOS_MO_HISTORICOS = 500
MAXIMO_CANDIDATOS_MO_FALLBACK = 250
MAXIMO_TERMINOS_BUSQUEDA_MO = 8


PALABRAS_IGNORADAS_BUSQUEDA_MO = {
    "A",
    "AL",
    "CON",
    "DE",
    "DEL",
    "E",
    "EL",
    "EN",
    "LA",
    "LAS",
    "LOS",
    "MANO",
    "OBRA",
    "PARA",
    "POR",
    "SIN",
    "SERVICIO",
    "SERVICIOS",
    "TRABAJO",
    "TRABAJOS",
    "UN",
    "UNA",
    "UNO",
    "Y",
    "CAMBIO",
    "CAMBIAR",
    "REALIZAR",
    "REVISION",
    "REVISAR",
}





# ==========================================================

# NORMALIZACIÓN

# ==========================================================



def normalizar_texto(valor):

    """

    Convierte textos a una forma comparable.



    Ejemplo:

        "Cambio de Refrigeración"

        -> "CAMBIO DE REFRIGERACION"

    """



    texto = str(

        valor or ""

    ).strip().upper()



    if not texto:

        return ""



    texto = unicodedata.normalize(

        "NFD",

        texto,

    )



    texto = "".join(

        caracter

        for caracter in texto

        if unicodedata.category(

            caracter

        ) != "Mn"

    )



    texto = re.sub(

        r"[^A-Z0-9\s]",

        " ",

        texto,

    )



    texto = re.sub(

        r"\s+",

        " ",

        texto,

    )



    return texto.strip()





def normalizar_codigo(valor):

    """

    Normaliza códigos de repuesto.



    Ejemplos:

        FC-8625

        FC 8625

        fc8625



    Resultado:

        FC8625

    """



    return re.sub(

        r"[^A-Z0-9]",

        "",

        str(

            valor or ""

        ).strip().upper(),

    )





# ==========================================================

# CONVERSIÓN SEGURA A DECIMAL

# ==========================================================



def decimal_seguro(
    valor,
    default=CERO,
):
    """
    Convierte valores numéricos a Decimal de forma segura.

    Si llega None, cadena vacía o un tipo no convertible,
    devuelve el valor por defecto.
    """
    if valor is None or valor == "":
        return default

    try:
        return Decimal(
            str(valor)
        )
    except (
        TypeError,
        ValueError,
        ArithmeticError,
    ):
        return default





def decimal_dos(valor):

    if valor is None:

        return None



    return decimal_seguro(

        valor

    ).quantize(

        Decimal("0.01"),

        rounding=ROUND_HALF_UP,

    )





# ==========================================================
# HISTORIAL DEL MISMO VEHÍCULO
# ==========================================================


def normalizar_placa(valor):
    """
    Normaliza una placa para comparar formatos como:

        PBA-1234
        PBA 1234
        pba1234

    como la misma placa.
    """

    return re.sub(
        r"[^A-Z0-9]",
        "",
        str(
            valor or ""
        ).strip().upper(),
    )


def prioridad_mismo_vehiculo(
    fila,
    orden_actual,
):
    """
    Devuelve una prioridad adicional SOLO cuando:

    - la placa es exactamente la misma, y
    - el repuesto/servicio también es suficientemente parecido.

    Prioridad:
        4 = producto/código/servicio exacto
        3 = descripción prácticamente idéntica
        2 = descripción muy parecida
        1 = similitud global excepcional
        0 = no dar prioridad especial
    """

    # ======================================================
    # IDENTIDAD DEL VEHÍCULO
    #
    # 1. Primero usamos expediente_id, porque el historial
    #    de visitas ya agrupa el mismo vehículo por expediente.
    #
    # 2. Si no existe expediente en alguno de los registros,
    #    usamos la placa como respaldo.
    # ======================================================

    expediente_actual = getattr(
        orden_actual,
        "expediente_id",
        None,
    )

    expediente_historico = fila.get(
        "expediente_id"
    )

    mismo_expediente = bool(
        expediente_actual
        and expediente_historico
        and expediente_actual
        == expediente_historico
    )

    placa_actual = normalizar_placa(
        getattr(
            orden_actual,
            "placa",
            "",
        )
    )

    placa_historica = normalizar_placa(
        fila.get(
            "placa"
        )
    )

    misma_placa = bool(
        placa_actual
        and placa_historica
        and placa_actual
        == placa_historica
    )

    if not (
        mismo_expediente
        or misma_placa
    ):
        return 0

    detalle = (
        fila.get(
            "detalle_similitud"
        )
        or {}
    )

    # Identidad estructurada exacta.
    if (
        detalle.get(
            "producto_exacto"
        )
        or detalle.get(
            "codigo_exacto"
        )
        or detalle.get(
            "servicio_exacto"
        )
    ):
        return 4

    # REP usa "descripcion".
    # MOI / MOE usan "descripcion_padre".
    descripcion = detalle.get(
        "descripcion"
    )

    if descripcion is None:
        descripcion = detalle.get(
            "descripcion_padre"
        )

    try:
        descripcion = float(
            descripcion or 0
        )
    except (
        TypeError,
        ValueError,
    ):
        descripcion = 0.0

    procedimientos = detalle.get(
        "procedimientos"
    )

    try:
        procedimientos = (
            float(
                procedimientos
            )
            if procedimientos is not None
            else None
        )
    except (
        TypeError,
        ValueError,
    ):
        procedimientos = None

    # Descripción prácticamente exacta.
    if (
        descripcion >= 95
        and (
            procedimientos is None
            or procedimientos >= 75
        )
    ):
        return 3

    # Descripción suficientemente fuerte para considerarla
    # antecedente del mismo trabajo/repuesto.
    if (
        descripcion >= 88
        and (
            procedimientos is None
            or procedimientos >= 65
        )
    ):
        return 2

    try:
        similitud = float(
            fila.get(
                "similitud",
                0,
            )
            or 0
        )
    except (
        TypeError,
        ValueError,
    ):
        similitud = 0.0

    if similitud >= 95:
        return 1

    return 0


def ordenar_resultados(
    resultados,
    orden_actual,
):
    """
    Prioriza:

    1. mismo vehículo + mismo ítem
    2. similitud
    3. fecha

    Así, si este mismo auto ya tuvo el mismo filtro,
    repuesto o servicio, ese antecedente aparece primero.
    """

    resultados.sort(
        key=lambda fila: (
            prioridad_mismo_vehiculo(
                fila,
                orden_actual,
            ),
            fila.get(
                "similitud",
                0,
            ),
            fila.get(
                "fecha"
            )
            or date.min,
        ),
        reverse=True,
    )


def obtener_antecedente_mismo_vehiculo(
    resultados,
    orden_actual,
):
    """
    Devuelve el antecedente MÁS RECIENTE del mismo vehículo
    cuando el ítem es suficientemente equivalente.

    Se entrega aparte para que el frontend pueda mostrar:

        "Anterior en este vehículo: $XX.XX · OT-XXXXX"
    """

    candidatos = [
        fila
        for fila in resultados
        if (
            prioridad_mismo_vehiculo(
                fila,
                orden_actual,
            )
            >= 2
            and decimal_seguro(
                fila.get(
                    "precio_unitario"
                )
            )
            > CERO
        )
    ]

    if not candidatos:
        return None

    candidatos.sort(
        key=lambda fila: (
            fila.get(
                "fecha"
            )
            or date.min,
            prioridad_mismo_vehiculo(
                fila,
                orden_actual,
            ),
            fila.get(
                "similitud",
                0,
            ),
        ),
        reverse=True,
    )

    fila = candidatos[0]

    return {
        "orden_id": fila.get(
            "orden_id"
        ),
        "expediente_id": fila.get(
            "expediente_id"
        ),
        "numero_orden": fila.get(
            "numero_orden"
        ),
        "fecha": fila.get(
            "fecha"
        ),
        "sucursal": fila.get(
            "sucursal"
        ),
        "placa": fila.get(
            "placa"
        ),
        "vehiculo": fila.get(
            "vehiculo"
        ),
        "anio": fila.get(
            "anio"
        ),
        "kilometraje": fila.get(
            "kilometraje"
        ),
        "descripcion": fila.get(
            "descripcion"
        ),
        "referencia": fila.get(
            "referencia"
        ),
        "precio_unitario": fila.get(
            "precio_unitario"
        ),
        "similitud": fila.get(
            "similitud"
        ),
        "origen": fila.get(
            "origen"
        ),
        "prioridad": (
            prioridad_mismo_vehiculo(
                fila,
                orden_actual,
            )
        ),
    }


# ==========================================================

# SIMILITUD DE TEXTO

# ==========================================================



def similitud_texto(

    texto_a,

    texto_b,

):

    a = normalizar_texto(

        texto_a

    )



    b = normalizar_texto(

        texto_b

    )



    if not a or not b:

        return 0.0



    if a == b:

        return 1.0



    return SequenceMatcher(

        None,

        a,

        b,

    ).ratio()





# ==========================================================

# NORMALIZAR PROCEDIMIENTOS

# ==========================================================



def normalizar_lista_procedimientos(

    procedimientos,

):

    """

    Acepta procedimientos provenientes de:



    - frontend

    - OrdenServicioProcedimientoDetalle

    - JSON histórico migrado



    Devuelve:

        [

            "CAMBIO ...",

            "REPARACION ..."

        ]

    """



    if not procedimientos:

        return []



    if isinstance(

        procedimientos,

        str,

    ):

        procedimientos = [

            procedimientos

        ]



    if isinstance(

        procedimientos,

        dict,

    ):

        procedimientos = [

            procedimientos

        ]



    resultado = []



    for procedimiento in procedimientos:



        if procedimiento is None:

            continue



        if isinstance(

            procedimiento,

            dict,

        ):

            texto = (

                procedimiento.get(

                    "descripcion"

                )

                or procedimiento.get(

                    "texto"

                )

                or procedimiento.get(

                    "nombre"

                )

                or procedimiento.get(

                    "detalle"

                )

                or ""

            )



        else:

            texto = str(

                procedimiento

            )



        texto = texto.strip()



        if texto:

            resultado.append(

                texto

            )



    return resultado





# ==========================================================

# SIMILITUD DE PROCEDIMIENTOS

# ==========================================================



def _cobertura_procedimientos(

    origen,

    destino,

):

    """

    Calcula cuánto de ORIGEN puede encontrarse

    dentro de DESTINO.



    Para cada procedimiento de origen se busca

    su mejor coincidencia en destino.

    """



    if not origen:

        return 0.0



    if not destino:

        return 0.0



    puntuaciones = []



    for actual in origen:



        mejor = max(

            (

                similitud_texto(

                    actual,

                    candidato,

                )

                for candidato

                in destino

            ),

            default=0.0,

        )



        puntuaciones.append(

            mejor

        )



    if not puntuaciones:

        return 0.0



    return (

        sum(puntuaciones)

        / len(puntuaciones)

    )





def similitud_procedimientos(

    procedimientos_actuales,

    procedimientos_historicos,

):

    """

    Comparación bidireccional.



    Esto es importante porque:



        ACTUAL:

        A + B + C



    no debe considerarse igual a:



        HISTÓRICO:

        A



    aunque A coincida perfectamente.



    También penaliza el caso contrario:



        ACTUAL:

        A



        HISTÓRICO:

        A + B + C + D

    """



    actuales = [

        normalizar_texto(x)

        for x in

        normalizar_lista_procedimientos(

            procedimientos_actuales

        )

        if normalizar_texto(x)

    ]



    historicos = [

        normalizar_texto(x)

        for x in

        normalizar_lista_procedimientos(

            procedimientos_historicos

        )

        if normalizar_texto(x)

    ]



    if (

        not actuales

        and not historicos

    ):

        return 1.0



    if (

        not actuales

        or not historicos

    ):

        return 0.0



    cobertura_actual = (

        _cobertura_procedimientos(

            actuales,

            historicos,

        )

    )



    cobertura_historico = (

        _cobertura_procedimientos(

            historicos,

            actuales,

        )

    )



    return (

        cobertura_actual

        + cobertura_historico

    ) / 2





# ==========================================================

# FECHA REAL DE LA ORDEN

# ==========================================================



def obtener_fecha_orden(

    orden,

):

    """

    Para migradas se utiliza fecha_origen.



    Para las demás, fecha_ingreso.

    """



    if (

        getattr(

            orden,

            "es_migrada",

            False,

        )

        and getattr(

            orden,

            "fecha_origen",

            None,

        )

    ):

        fecha = (

            orden.fecha_origen

        )



        if hasattr(

            fecha,

            "date",

        ):

            return fecha.date()



        return fecha



    fecha_ingreso = getattr(

        orden,

        "fecha_ingreso",

        None,

    )



    if fecha_ingreso:

        if hasattr(

            fecha_ingreso,

            "date",

        ):

            return (

                fecha_ingreso.date()

            )



        return fecha_ingreso



    return None





# ==========================================================

# RECENCIA

# ==========================================================



def puntuar_recencia(

    orden,

):

    """

    1.00 = antecedente muy reciente.



    Los precios viejos siguen apareciendo,

    pero pesan menos.

    """



    fecha = obtener_fecha_orden(

        orden

    )



    if not fecha:

        return 0.30



    hoy = timezone.localdate()



    diferencia = (

        hoy - fecha

    ).days



    if diferencia < 0:

        diferencia = 0



    if diferencia <= 90:

        return 1.00



    if diferencia <= 180:

        return 0.90



    if diferencia <= 365:

        return 0.75



    if diferencia <= 730:

        return 0.50



    if diferencia <= 1095:

        return 0.30



    return 0.15





# ==========================================================

# VEHÍCULO / AÑO / KILOMETRAJE

# ==========================================================



def puntuar_vehiculo(

    orden_actual,

    orden_historica,

):

    """

    Devuelve valor entre 0 y 1.



    Internamente:



        vehículo       65%

        año            20%

        kilometraje    15%

    """



    puntuacion = 0.0



    # ------------------------------------------------------

    # VEHÍCULO

    # ------------------------------------------------------



    vehiculo_actual = normalizar_texto(

        getattr(

            orden_actual,

            "vehiculo",

            "",

        )

    )



    vehiculo_historico = normalizar_texto(

        getattr(

            orden_historica,

            "vehiculo",

            "",

        )

    )



    if (

        vehiculo_actual

        and vehiculo_historico

    ):

        puntuacion += (

            similitud_texto(

                vehiculo_actual,

                vehiculo_historico,

            )

            * 0.65

        )



    # ------------------------------------------------------

    # AÑO

    # ------------------------------------------------------



    anio_actual = getattr(

        orden_actual,

        "anio_vehiculo",

        None,

    )



    anio_historico = getattr(

        orden_historica,

        "anio_vehiculo",

        None,

    )



    if (

        anio_actual

        and anio_historico

    ):

        try:

            diferencia_anio = abs(

                int(anio_actual)

                - int(anio_historico)

            )



            if diferencia_anio == 0:

                puntuacion += 0.20



            elif diferencia_anio <= 2:

                puntuacion += 0.16



            elif diferencia_anio <= 5:

                puntuacion += 0.10



            elif diferencia_anio <= 10:

                puntuacion += 0.04



        except (

            TypeError,

            ValueError,

        ):

            pass



    # ------------------------------------------------------

    # KILOMETRAJE

    # ------------------------------------------------------



    km_actual = getattr(

        orden_actual,

        "kilometraje",

        None,

    )



    km_historico = getattr(

        orden_historica,

        "kilometraje",

        None,

    )



    if (

        km_actual is not None

        and km_historico is not None

    ):

        try:

            diferencia_km = abs(

                int(km_actual)

                - int(km_historico)

            )



            if diferencia_km <= 10000:

                puntuacion += 0.15



            elif diferencia_km <= 30000:

                puntuacion += 0.11



            elif diferencia_km <= 60000:

                puntuacion += 0.07



            elif diferencia_km <= 100000:

                puntuacion += 0.03



        except (

            TypeError,

            ValueError,

        ):

            pass



    return min(

        puntuacion,

        1.0,

    )





# ==========================================================

# DATOS BASE DE COINCIDENCIA

# ==========================================================



def construir_resultado(

    *,

    orden,

    descripcion,

    precio_unitario,

    cantidad,

    origen,

    similitud,

    referencia=None,

    procedimientos=None,

    detalle_similitud=None,

    item_id=None,

    producto_id=None,

    servicio_id=None,

    variante=None,

):

    return {

        "item_id": item_id,

        "orden_id": orden.pk,

        "expediente_id": getattr(
            orden,
            "expediente_id",
            None,
        ),

        "numero_orden": (

            orden.numero_orden

        ),

        "fecha": obtener_fecha_orden(

            orden

        ),

        "sucursal": (

            orden.sucursal.codigo

            if getattr(

                orden,

                "sucursal",

                None,

            )

            else ""

        ),

        "placa": (

            orden.placa

            or ""

        ),

        "vehiculo": (

            orden.vehiculo

            or ""

        ),

        "anio": (

            orden.anio_vehiculo

        ),

        "kilometraje": (

            orden.kilometraje

        ),

        "descripcion": (

            descripcion

            or ""

        ),

        "referencia": (

            referencia

            or ""

        ),

        "cantidad": cantidad,

        "precio_unitario": (

            precio_unitario

        ),

        "procedimientos": (

            procedimientos

            or []

        ),

        "origen": origen,

        "producto_id": producto_id,

        "servicio_id": servicio_id,

        "variante": variante,

        "similitud": round(

            float(similitud) * 100,

            1,

        ),

        "detalle_similitud": (

            detalle_similitud

            or {}

        ),

    }





# ==========================================================

# INVENTARIO

# ==========================================================



def resolver_codigo_producto(

    *,

    codigo_producto_id=None,

    codigo=None,

    descripcion=None,

):

    """

    Orden de resolución:



    1. ID exacto recibido desde la fila OT.

    2. Código comercial normalizado.

    3. Código de barras.

    4. SKU interno.

    5. Alias exacto confirmado.



    Si un código es ambiguo y corresponde a

    más de un CodigoProducto, no elegimos uno

    automáticamente.

    """



    # ------------------------------------------------------

    # ID EXACTO

    # ------------------------------------------------------



    if codigo_producto_id:

        try:

            return (

                CodigoProducto.objects

                .select_related(

                    "producto",

                    "producto__categoria",

                    "marca",

                )

                .filter(

                    pk=codigo_producto_id,

                    activo=True,

                )

                .first()

            )



        except (

            TypeError,

            ValueError,

        ):

            pass



    # ------------------------------------------------------

    # CÓDIGO

    # ------------------------------------------------------



    codigo_original = str(

        codigo or ""

    ).strip()



    codigo_norm = normalizar_codigo(

        codigo_original

    )



    if codigo_norm:



        candidatos = (

            CodigoProducto.objects

            .select_related(

                "producto",

                "producto__categoria",

                "marca",

            )

            .filter(

                activo=True

            )

            .filter(

                Q(

                    codigo_normalizado=

                    codigo_norm

                )

                |

                Q(

                    codigo_barras=

                    codigo_original

                )

                |

                Q(

                    producto__sku_interno__iexact=

                    codigo_original

                )

            )

            .distinct()

        )



        ids = list(

            candidatos.values_list(

                "id",

                flat=True,

            )[:2]

        )



        if len(ids) == 1:

            return candidatos.get(

                pk=ids[0]

            )



    # ------------------------------------------------------

    # ALIAS EXACTO

    # ------------------------------------------------------



    descripcion_norm = (

        normalizar_texto(

            descripcion

        )

    )



    if descripcion_norm:



        alias_qs = (

            AliasProducto.objects

            .select_related(

                "codigo_producto",

                "codigo_producto__producto",

                "codigo_producto__producto__categoria",

                "codigo_producto__marca",

            )

            .filter(

                activo=True,

                alias_normalizado=

                    descripcion_norm,

                codigo_producto__isnull=False,

                codigo_producto__activo=True,

            )

            .order_by(

                "-veces_confirmado"

            )

        )



        codigo_ids = list(

            alias_qs

            .values_list(

                "codigo_producto_id",

                flat=True,

            )

            .distinct()[:2]

        )



        if len(codigo_ids) == 1:



            return (

                CodigoProducto.objects

                .select_related(

                    "producto",

                    "producto__categoria",

                    "marca",

                )

                .filter(

                    pk=codigo_ids[0],

                    activo=True,

                )

                .first()

            )



    return None





# ==========================================================

# RESUMEN ACTUAL DEL INVENTARIO

# ==========================================================



def obtener_resumen_inventario(

    *,

    orden_actual,

    codigo_producto,

):

    if not codigo_producto:

        return None



    sucursal = getattr(

        orden_actual,

        "sucursal",

        None,

    )



    stock_sucursal = None



    if sucursal:



        stock_obj = (

            StockSucursal.objects

            .filter(

                codigo_producto=

                    codigo_producto,

                sucursal=sucursal,

            )

            .first()

        )



        if stock_obj:

            stock_sucursal = (

                stock_obj.cantidad

            )



    stock_total = (

        StockSucursal.objects

        .filter(

            codigo_producto=

                codigo_producto

        )

        .aggregate(

            total=Sum(

                "cantidad"

            )

        )

        .get(

            "total"

        )

    )



    producto = (

        codigo_producto.producto

    )



    marca = (

        codigo_producto.marca

    )



    categoria = (

        producto.categoria

        if producto

        else None

    )



    return {

        "codigo_producto_id": (

            codigo_producto.id

        ),

        "producto_id": (

            producto.id

            if producto

            else None

        ),

        "sku_interno": (

            producto.sku_interno

            if producto

            else ""

        ),

        "codigo": (

            codigo_producto.codigo

        ),

        "codigo_normalizado": (

            codigo_producto

            .codigo_normalizado

        ),

        "codigo_barras": (

            codigo_producto.codigo_barras

        ),

        "nombre_producto": (

            producto.nombre_base

            if producto

            else ""

        ),

        "nombre_comercial": (

            codigo_producto

            .nombre_comercial

            or ""

        ),

        "marca": (

            marca.nombre

            if marca

            else ""

        ),

        "categoria": (

            categoria.nombre

            if categoria

            else ""

        ),

        "precio_compra": (

            codigo_producto

            .precio_compra

        ),

        "precio_venta": (

            codigo_producto

            .precio_venta

        ),

        "precio_secreto": (

            codigo_producto

            .precio_secreto

        ),

        "margen_ganancia_porcentaje": (

            codigo_producto

            .margen_ganancia_porcentaje

        ),

        "porcentaje_iva_costo": (

            codigo_producto

            .porcentaje_iva_costo

        ),

        "presentacion_cantidad": (

            codigo_producto

            .presentacion_cantidad

        ),

        "presentacion_unidad": (

            codigo_producto

            .presentacion_unidad

        ),

        "sucursal_id": (

            sucursal.id

            if sucursal

            else None

        ),

        "sucursal_codigo": (

            sucursal.codigo

            if sucursal

            else None

        ),

        "stock_sucursal": (

            stock_sucursal

        ),

        "stock_total": (

            stock_total

            if stock_total is not None

            else CERO

        ),

    }





# ==========================================================

# PUNTUACIÓN REPUESTO ACTUAL

# ==========================================================



def calcular_similitud_repuesto_actual(

    *,

    orden_actual,

    item,

    descripcion,

    codigo,

    codigo_producto,

):

    similitud_descripcion = (

        similitud_texto(

            descripcion,

            item.descripcion_factura,

        )

    )



    similitud_vehiculo = (

        puntuar_vehiculo(

            orden_actual,

            item.orden,

        )

    )



    recencia = puntuar_recencia(

        item.orden

    )



    # ------------------------------------------------------

    # MISMO CodigoProducto

    # ------------------------------------------------------



    mismo_producto = bool(

        codigo_producto

        and item.producto_id

        == codigo_producto.id

    )



    if mismo_producto:



        total = (

            0.55

            + similitud_descripcion

            * 0.20

            + similitud_vehiculo

            * 0.15

            + recencia

            * 0.10

        )



        return min(

            total,

            1.0,

        ), {

            "producto_exacto": True,

            "codigo_exacto": True,

            "descripcion": round(

                similitud_descripcion

                * 100,

                1,

            ),

            "vehiculo": round(

                similitud_vehiculo

                * 100,

                1,

            ),

            "recencia": round(

                recencia

                * 100,

                1,

            ),

        }



    # ------------------------------------------------------

    # CÓDIGO

    # ------------------------------------------------------



    codigo_norm = normalizar_codigo(

        codigo

    )



    referencias = [

        item.codigo_empaque_referencia,

        item.codigo_barras_referencia,

    ]



    if item.producto:

        referencias.extend([

            item.producto.codigo,

            item.producto.codigo_barras,

            (

                item.producto.producto

                .sku_interno

                if item.producto.producto

                else None

            ),

        ])



    codigo_exacto = False



    if codigo_norm:



        for referencia in referencias:



            if (

                referencia

                and normalizar_codigo(

                    referencia

                )

                == codigo_norm

            ):

                codigo_exacto = True

                break



    if codigo_exacto:



        total = (

            0.50

            + similitud_descripcion

            * 0.25

            + similitud_vehiculo

            * 0.15

            + recencia

            * 0.10

        )



    else:



        total = (

            similitud_descripcion

            * 0.70

            + similitud_vehiculo

            * 0.18

            + recencia

            * 0.12

        )



    return min(

        total,

        1.0,

    ), {

        "producto_exacto": False,

        "codigo_exacto": (

            codigo_exacto

        ),

        "descripcion": round(

            similitud_descripcion

            * 100,

            1,

        ),

        "vehiculo": round(

            similitud_vehiculo

            * 100,

            1,

        ),

        "recencia": round(

            recencia

            * 100,

            1,

        ),

    }





# ==========================================================
# PRECIO UNITARIO HISTÓRICO DE REPUESTO
# ==========================================================


def obtener_precio_unitario_historico_repuesto(
    item,
):
    """
    Obtiene el P.U. utilizable de un repuesto histórico.

    Regla:
    1. Si precio_unitario existe y es > 0, usarlo.
    2. Si no existe, pero subtotal > 0 y cantidad > 0:
           P.U. = subtotal / cantidad
    3. En cualquier otro caso, no existe un precio válido.

    Esto permite recuperar correctamente históricos migrados
    donde Getsoft guardó cantidad y subtotal, pero dejó
    precio_unitario en NULL.
    """

    precio = decimal_seguro(
        getattr(
            item,
            "precio_unitario",
            None,
        )
    )

    if precio > CERO:
        return decimal_dos(
            precio
        )

    cantidad = decimal_seguro(
        getattr(
            item,
            "cantidad",
            None,
        )
    )

    subtotal = decimal_seguro(
        getattr(
            item,
            "subtotal",
            None,
        )
    )

    if (
        cantidad > CERO
        and subtotal > CERO
    ):
        return decimal_dos(
            subtotal / cantidad
        )

    return None


# ==========================================================

# PUNTUACIÓN REPUESTO HISTÓRICO

# ==========================================================



def calcular_similitud_repuesto_historico(

    *,

    orden_actual,

    item,

    descripcion,

    codigo,

    codigo_producto,

):

    similitud_descripcion = (

        similitud_texto(

            descripcion,

            item.descripcion_original,

        )

    )



    similitud_vehiculo = (

        puntuar_vehiculo(

            orden_actual,

            item.orden,

        )

    )



    recencia = puntuar_recencia(

        item.orden

    )



    codigos_consulta = set()



    if codigo:

        codigo_norm = (

            normalizar_codigo(

                codigo

            )

        )



        if codigo_norm:

            codigos_consulta.add(

                codigo_norm

            )



    if codigo_producto:



        for valor in [

            codigo_producto.codigo,

            codigo_producto.codigo_barras,

            (

                codigo_producto.producto

                .sku_interno

                if codigo_producto.producto

                else None

            ),

        ]:

            valor_norm = (

                normalizar_codigo(

                    valor

                )

            )



            if valor_norm:

                codigos_consulta.add(

                    valor_norm

                )



    codigo_historico = (

        normalizar_codigo(

            item.codigo_original

        )

    )



    codigo_exacto = bool(

        codigo_historico

        and codigo_historico

        in codigos_consulta

    )



    if codigo_exacto:



        total = (

            0.50

            + similitud_descripcion

            * 0.25

            + similitud_vehiculo

            * 0.15

            + recencia

            * 0.10

        )



    else:



        total = (

            similitud_descripcion

            * 0.70

            + similitud_vehiculo

            * 0.18

            + recencia

            * 0.12

        )



    return min(

        total,

        1.0,

    ), {

        "producto_exacto": False,

        "codigo_exacto": (

            codigo_exacto

        ),

        "descripcion": round(

            similitud_descripcion

            * 100,

            1,

        ),

        "vehiculo": round(

            similitud_vehiculo

            * 100,

            1,

        ),

        "recencia": round(

            recencia

            * 100,

            1,

        ),

    }





# ==========================================================

# BUSCAR REPUESTOS

# ==========================================================



def buscar_repuestos(

    *,

    orden_actual,

    descripcion,

    codigo=None,

    codigo_producto_id=None,

):

    resultados = []



    codigo_producto = (

        resolver_codigo_producto(

            codigo_producto_id=

                codigo_producto_id,

            codigo=codigo,

            descripcion=descripcion,

        )

    )



    # ------------------------------------------------------

    # DETALLES ACTUALES

    # ------------------------------------------------------



    actuales = (

        OrdenInsumoDetalle.objects

        .select_related(

            "orden",

            "orden__sucursal",

            "producto",

            "producto__producto",

            "producto__producto__categoria",

            "producto__marca",

        )

        .exclude(

            precio_unitario__lte=CERO

        )

    )



    for item in actuales.iterator(

        chunk_size=1000

    ):



        if (

            item.orden_id

            == orden_actual.pk

        ):

            continue



        (

            similitud,

            detalle,

        ) = (

            calcular_similitud_repuesto_actual(

                orden_actual=

                    orden_actual,

                item=item,

                descripcion=

                    descripcion,

                codigo=codigo,

                codigo_producto=

                    codigo_producto,

            )

        )



        if (

            similitud

            * 100

            < UMBRAL_COINCIDENCIA

        ):

            continue



        referencia = (

            item.codigo_empaque_referencia

            or item.codigo_barras_referencia

            or (

                item.producto.codigo

                if item.producto

                else ""

            )

        )



        resultados.append(

            construir_resultado(

                item_id=item.id,

                orden=item.orden,

                descripcion=(

                    item.descripcion_factura

                ),

                precio_unitario=(

                    item.precio_unitario

                ),

                cantidad=item.cantidad,

                origen="ACTUAL",

                similitud=similitud,

                referencia=referencia,

                producto_id=(

                    item.producto_id

                ),

                detalle_similitud=

                    detalle,

            )

        )



    # ------------------------------------------------------

    # MIGRADOS

    # ------------------------------------------------------



    historicos = (

        OrdenInsumoHistorico.objects

        .select_related(

            "orden",

            "orden__sucursal",

        )

        .exclude(

            precio_unitario__isnull=True

        )

        .exclude(

            precio_unitario__lte=CERO

        )

    )



    for item in historicos.iterator(

        chunk_size=1000

    ):



        if (

            item.orden_id

            == orden_actual.pk

        ):

            continue



        (

            similitud,

            detalle,

        ) = (

            calcular_similitud_repuesto_historico(

                orden_actual=

                    orden_actual,

                item=item,

                descripcion=

                    descripcion,

                codigo=codigo,

                codigo_producto=

                    codigo_producto,

            )

        )



        if (

            similitud

            * 100

            < UMBRAL_COINCIDENCIA

        ):

            continue



        resultados.append(

            construir_resultado(

                item_id=item.id,

                orden=item.orden,

                descripcion=(

                    item.descripcion_original

                ),

                precio_unitario=(

                    item.precio_unitario

                ),

                cantidad=item.cantidad,

                origen="MIGRADA",

                similitud=similitud,

                referencia=(

                    item.codigo_original

                ),

                detalle_similitud=

                    detalle,

            )

        )




    # ------------------------------------------------------
    # HISTÓRICOS DEL MISMO VEHÍCULO SIN P.U.
    #
    # Algunos datos migrados de Getsoft tienen:
    #
    #     precio_unitario = NULL
    #     cantidad > 0
    #     subtotal > 0
    #
    # No abrimos esta regla a toda la base porque eso vuelve
    # muy costosa la consulta. Se recupera SOLO para el mismo
    # vehículo actual (expediente o placa).
    # ------------------------------------------------------

    expediente_actual_id = getattr(
        orden_actual,
        "expediente_id",
        None,
    )

    placa_actual = str(
        getattr(
            orden_actual,
            "placa",
            "",
        )
        or ""
    ).strip()

    identidad_mismo_vehiculo = Q()

    if expediente_actual_id:
        identidad_mismo_vehiculo |= Q(
            orden__expediente_id=
                expediente_actual_id
        )

    if placa_actual:
        identidad_mismo_vehiculo |= Q(
            orden__placa__iexact=
                placa_actual
        )

    if identidad_mismo_vehiculo:

        historicos_mismo_vehiculo = (

            OrdenInsumoHistorico.objects

            .select_related(
                "orden",
                "orden__sucursal",
            )

            .filter(
                identidad_mismo_vehiculo,
                cantidad__gt=CERO,
                subtotal__gt=CERO,
            )

            .filter(
                Q(
                    precio_unitario__isnull=True
                )
                |
                Q(
                    precio_unitario__lte=CERO
                )
            )
        )

        for item in historicos_mismo_vehiculo.iterator(
            chunk_size=200
        ):

            if (
                item.orden_id
                == orden_actual.pk
            ):
                continue

            precio_unitario_historico = (
                obtener_precio_unitario_historico_repuesto(
                    item
                )
            )

            if (
                precio_unitario_historico
                is None
                or precio_unitario_historico
                <= CERO
            ):
                continue

            (
                similitud,
                detalle,
            ) = (
                calcular_similitud_repuesto_historico(
                    orden_actual=
                        orden_actual,
                    item=item,
                    descripcion=
                        descripcion,
                    codigo=codigo,
                    codigo_producto=
                        codigo_producto,
                )
            )

            if (
                similitud
                * 100
                < UMBRAL_COINCIDENCIA
            ):
                continue

            resultados.append(
                construir_resultado(
                    item_id=item.id,
                    orden=item.orden,
                    descripcion=(
                        item.descripcion_original
                    ),
                    precio_unitario=(
                        precio_unitario_historico
                    ),
                    cantidad=item.cantidad,
                    origen="MIGRADA",
                    similitud=similitud,
                    referencia=(
                        item.codigo_original
                    ),
                    detalle_similitud=
                        detalle,
                )
            )


    ordenar_resultados(
        resultados,
        orden_actual,
    )



    inventario = (

        obtener_resumen_inventario(

            orden_actual=

                orden_actual,

            codigo_producto=

                codigo_producto,

        )

    )



    return (

        resultados,

        inventario,

        codigo_producto,

    )





# ==========================================================

# CATÁLOGO DE SERVICIOS

# ==========================================================



def obtener_servicio_catalogo(

    servicio_id,

):

    if not servicio_id:

        return None



    try:

        return (

            ServicioCatalogo.objects

            .prefetch_related(

                "procedimientos",

                "precios_configurados",

            )

            .filter(

                pk=servicio_id,

                activo=True,

            )

            .first()

        )



    except (

        TypeError,

        ValueError,

    ):

        return None





# ==========================================================

# RESUMEN CATÁLOGO SERVICIO

# ==========================================================



def obtener_resumen_servicio(

    *,

    orden_actual,

    servicio,

    variante,

):

    if not servicio:

        return None



    variante = (

        variante

        or "NORMAL"

    ).strip().upper()



    resumen = (

        servicio

        .obtener_resumen_precio(

            sucursal=(

                orden_actual.sucursal

                if getattr(

                    orden_actual,

                    "sucursal",

                    None,

                )

                else None

            ),

            variante=variante,

        )

    )



    procedimientos_catalogo = [

        {

            "id": procedimiento.id,

            "descripcion": (

                procedimiento.descripcion

            ),

            "obligatorio": (

                procedimiento.obligatorio

            ),

        }

        for procedimiento

        in servicio.procedimientos.all()

        if procedimiento.visible_en_ot

    ]



    resumen[

        "procedimientos"

    ] = procedimientos_catalogo



    resumen[

        "requiere_variante"

    ] = (

        servicio.requiere_variante

    )



    resumen[

        "tipo_servicio_catalogo"

    ] = (

        servicio.tipo_servicio

    )



    return resumen





# ==========================================================

# PUNTUAR SERVICIO ACTUAL

# ==========================================================



def calcular_similitud_servicio_actual(

    *,

    orden_actual,

    item,

    descripcion,

    procedimientos,

    servicio,

    variante,

):

    hijos = [

        procedimiento.descripcion

        for procedimiento

        in item.procedimientos_detalle.all()

        if procedimiento.descripcion

    ]



    padre = similitud_texto(

        descripcion,

        item.descripcion_servicio,

    )



    hijos_score = (

        similitud_procedimientos(

            procedimientos,

            hijos,

        )

    )



    vehiculo = puntuar_vehiculo(

        orden_actual,

        item.orden,

    )



    recencia = puntuar_recencia(

        item.orden

    )



    servicio_exacto = bool(

        servicio

        and item.servicio_id

        == servicio.id

    )



    variante_actual = (

        variante

        or "NORMAL"

    ).strip().upper()



    variante_item = (

        item.variante_precio_aplicada

        or "NORMAL"

    ).strip().upper()



    variante_exacta = (

        variante_actual

        == variante_item

    )



    tiene_hijos = bool(

        procedimientos

    )



    # ------------------------------------------------------

    # SERVICIO ESTRUCTURADO EXACTO

    # ------------------------------------------------------



    if servicio_exacto:



        if tiene_hijos:



            total = (

                0.20

                + padre

                * 0.25

                + hijos_score

                * 0.30

                + (

                    0.05

                    if variante_exacta

                    else 0.00

                )

                + vehiculo

                * 0.10

                + recencia

                * 0.10

            )



        else:



            total = (

                0.30

                + padre

                * 0.35

                + (

                    0.05

                    if variante_exacta

                    else 0.00

                )

                + vehiculo

                * 0.15

                + recencia

                * 0.15

            )



    # ------------------------------------------------------

    # MANUAL / SERVICIO DIFERENTE

    # ------------------------------------------------------



    else:



        if tiene_hijos:



            total = (

                padre

                * 0.40

                + hijos_score

                * 0.35

                + vehiculo

                * 0.15

                + recencia

                * 0.10

            )



        else:



            total = (

                padre

                * 0.70

                + vehiculo

                * 0.15

                + recencia

                * 0.15

            )



    return min(

        total,

        1.0,

    ), hijos, {

        "servicio_exacto": (

            servicio_exacto

        ),

        "variante_exacta": (

            variante_exacta

        ),

        "descripcion_padre": round(

            padre * 100,

            1,

        ),

        "procedimientos": round(

            hijos_score * 100,

            1,

        ),

        "vehiculo": round(

            vehiculo * 100,

            1,

        ),

        "recencia": round(

            recencia * 100,

            1,

        ),

    }





# ==========================================================

# PUNTUAR SERVICIO HISTÓRICO

# ==========================================================



def calcular_similitud_servicio_historico(

    *,

    orden_actual,

    item,

    descripcion,

    procedimientos,

):

    hijos = (

        normalizar_lista_procedimientos(

            item.procedimientos

        )

    )



    padre = similitud_texto(

        descripcion,

        item.descripcion_original,

    )



    hijos_score = (

        similitud_procedimientos(

            procedimientos,

            hijos,

        )

    )



    vehiculo = puntuar_vehiculo(

        orden_actual,

        item.orden,

    )



    recencia = puntuar_recencia(

        item.orden

    )



    if procedimientos:



        total = (

            padre

            * 0.40

            + hijos_score

            * 0.35

            + vehiculo

            * 0.15

            + recencia

            * 0.10

        )



    else:



        total = (

            padre

            * 0.70

            + vehiculo

            * 0.15

            + recencia

            * 0.15

        )



    return min(

        total,

        1.0,

    ), hijos, {

        "servicio_exacto": False,

        "variante_exacta": None,

        "descripcion_padre": round(

            padre * 100,

            1,

        ),

        "procedimientos": round(

            hijos_score * 100,

            1,

        ),

        "vehiculo": round(

            vehiculo * 100,

            1,

        ),

        "recencia": round(

            recencia * 100,

            1,

        ),

    }





# ==========================================================

# BUSCAR MANO DE OBRA

# ==========================================================



# ==========================================================
# PRESELECCIÓN DE CANDIDATOS DE MANO DE OBRA
# ==========================================================

def _terminos_busqueda_mano_obra(
    descripcion,
    procedimientos=None,
):
    """
    Extrae términos útiles para reducir candidatos en PostgreSQL.

    La comparación final NO se hace aquí. Después se sigue usando
    calcular_similitud_servicio_actual / historico.

    La búsqueda continúa abarcando todas las sucursales.
    """

    valores = [
        descripcion,
        *normalizar_lista_procedimientos(
            procedimientos
        ),
    ]

    terminos = []
    vistos = set()

    for valor in valores:

        texto_original = str(
            valor or ""
        ).strip().upper()

        if not texto_original:
            continue

        palabras_originales = re.findall(
            r"[A-ZÁÉÍÓÚÜÑ0-9]+",
            texto_original,
        )

        for palabra_original in palabras_originales:

            normalizada = normalizar_texto(
                palabra_original
            )

            if (
                not normalizada
                or len(normalizada) < 4
                or normalizada
                in PALABRAS_IGNORADAS_BUSQUEDA_MO
            ):
                continue

            # Se conserva primero la forma escrita por el usuario.
            # Esto ayuda cuando la BD contiene tildes.
            for termino in (
                palabra_original,
                normalizada,
            ):

                termino = str(
                    termino or ""
                ).strip()

                if not termino:
                    continue

                clave = termino.upper()

                if clave in vistos:
                    continue

                vistos.add(
                    clave
                )

                terminos.append(
                    termino
                )

                if (
                    len(terminos)
                    >= MAXIMO_TERMINOS_BUSQUEDA_MO
                ):
                    return terminos

    return terminos


def _agregar_ids_unicos(
    destino,
    vistos,
    nuevos_ids,
    limite,
):
    """
    Agrega IDs manteniendo prioridad y evitando duplicados.
    """

    for item_id in nuevos_ids:

        if item_id in vistos:
            continue

        vistos.add(
            item_id
        )

        destino.append(
            item_id
        )

        if len(destino) >= limite:
            break


def _ids_candidatos_mano_obra_actual(
    *,
    queryset_base,
    descripcion,
    procedimientos,
    servicio,
    variante,
):
    """
    Reduce el universo de OrdenServicioDetalle antes de ejecutar
    SequenceMatcher y comparación de procedimientos.

    Prioridad:
    1. mismo servicio + misma variante
    2. mismo servicio
    3. descripción completa
    4. palabras relevantes de descripción/procedimientos
    5. fallback reciente

    No existe filtro por sucursal.
    """

    ids = []
    vistos = set()

    limite = MAXIMO_CANDIDATOS_MO_ACTUALES

    variante_normalizada = str(
        variante or "NORMAL"
    ).strip().upper()

    # ------------------------------------------------------
    # MISMO SERVICIO + MISMA VARIANTE
    # ------------------------------------------------------

    if servicio:

        exactos_variante = (
            queryset_base
            .filter(
                servicio_id=servicio.id,
                variante_precio_aplicada=
                    variante_normalizada,
            )
            .order_by(
                "-id"
            )
            .values_list(
                "id",
                flat=True,
            )[:250]
        )

        _agregar_ids_unicos(
            ids,
            vistos,
            exactos_variante,
            limite,
        )

        if len(ids) < limite:

            mismo_servicio = (
                queryset_base
                .filter(
                    servicio_id=servicio.id,
                )
                .order_by(
                    "-id"
                )
                .values_list(
                    "id",
                    flat=True,
                )[:250]
            )

            _agregar_ids_unicos(
                ids,
                vistos,
                mismo_servicio,
                limite,
            )

    # ------------------------------------------------------
    # DESCRIPCIÓN COMPLETA
    # ------------------------------------------------------

    descripcion_limpia = str(
        descripcion or ""
    ).strip()

    if (
        descripcion_limpia
        and len(ids) < limite
    ):

        por_descripcion = (
            queryset_base
            .filter(
                descripcion_servicio__icontains=
                    descripcion_limpia,
            )
            .order_by(
                "-id"
            )
            .values_list(
                "id",
                flat=True,
            )[:200]
        )

        _agregar_ids_unicos(
            ids,
            vistos,
            por_descripcion,
            limite,
        )

    # ------------------------------------------------------
    # TÉRMINOS DEL PADRE Y DE LAS HIJAS
    # ------------------------------------------------------

    terminos = (
        _terminos_busqueda_mano_obra(
            descripcion,
            procedimientos,
        )
    )

    if (
        terminos
        and len(ids) < limite
    ):

        condicion = Q()

        for termino in terminos:

            condicion |= Q(
                descripcion_servicio__icontains=
                    termino
            )

            condicion |= Q(
                procedimientos_detalle__descripcion__icontains=
                    termino
            )

        por_terminos = (
            queryset_base
            .filter(
                condicion
            )
            .distinct()
            .order_by(
                "-id"
            )
            .values_list(
                "id",
                flat=True,
            )[:350]
        )

        _agregar_ids_unicos(
            ids,
            vistos,
            por_terminos,
            limite,
        )

    # ------------------------------------------------------
    # FALLBACK
    # ------------------------------------------------------

    if not ids:

        recientes = (
            queryset_base
            .order_by(
                "-id"
            )
            .values_list(
                "id",
                flat=True,
            )[
                :MAXIMO_CANDIDATOS_MO_FALLBACK
            ]
        )

        _agregar_ids_unicos(
            ids,
            vistos,
            recientes,
            limite,
        )

    return ids


def _ids_candidatos_mano_obra_historico(
    *,
    queryset_base,
    descripcion,
    procedimientos,
):
    """
    Preselección para OrdenServicioHistorico.

    El histórico migrado no tiene FK a ServicioCatalogo, por eso
    se usa descripción y luego el algoritmo completo en Python.

    No existe filtro por sucursal.
    """

    ids = []
    vistos = set()

    limite = MAXIMO_CANDIDATOS_MO_HISTORICOS

    descripcion_limpia = str(
        descripcion or ""
    ).strip()

    # ------------------------------------------------------
    # DESCRIPCIÓN EXACTA
    # ------------------------------------------------------

    if descripcion_limpia:

        exactos = (
            queryset_base
            .filter(
                descripcion_original__iexact=
                    descripcion_limpia,
            )
            .order_by(
                "-id"
            )
            .values_list(
                "id",
                flat=True,
            )[:200]
        )

        _agregar_ids_unicos(
            ids,
            vistos,
            exactos,
            limite,
        )

    # ------------------------------------------------------
    # DESCRIPCIÓN CONTENIDA
    # ------------------------------------------------------

    if (
        descripcion_limpia
        and len(ids) < limite
    ):

        contenidos = (
            queryset_base
            .filter(
                descripcion_original__icontains=
                    descripcion_limpia,
            )
            .order_by(
                "-id"
            )
            .values_list(
                "id",
                flat=True,
            )[:250]
        )

        _agregar_ids_unicos(
            ids,
            vistos,
            contenidos,
            limite,
        )

    # ------------------------------------------------------
    # TÉRMINOS RELEVANTES
    # ------------------------------------------------------

    terminos = (
        _terminos_busqueda_mano_obra(
            descripcion,
            procedimientos,
        )
    )

    if (
        terminos
        and len(ids) < limite
    ):

        condicion = Q()

        for termino in terminos:

            condicion |= Q(
                descripcion_original__icontains=
                    termino
            )

        por_terminos = (
            queryset_base
            .filter(
                condicion
            )
            .order_by(
                "-id"
            )
            .values_list(
                "id",
                flat=True,
            )[:350]
        )

        _agregar_ids_unicos(
            ids,
            vistos,
            por_terminos,
            limite,
        )

    # ------------------------------------------------------
    # FALLBACK
    # ------------------------------------------------------

    if not ids:

        recientes = (
            queryset_base
            .order_by(
                "-id"
            )
            .values_list(
                "id",
                flat=True,
            )[
                :MAXIMO_CANDIDATOS_MO_FALLBACK
            ]
        )

        _agregar_ids_unicos(
            ids,
            vistos,
            recientes,
            limite,
        )

    return ids


def buscar_mano_obra(
    *,
    orden_actual,
    tipo,
    descripcion,
    procedimientos=None,
    servicio_id=None,
    variante="NORMAL",
):
    """
    Busca antecedentes de MOI / MOE en todas las sucursales.

    Optimización:
    - PostgreSQL reduce primero el universo de candidatos.
    - Python conserva la comparación avanzada de texto,
      procedimientos, vehículo y recencia.
    - Se mantienen órdenes actuales y migradas.
    """

    resultados = []

    procedimientos = (
        normalizar_lista_procedimientos(
            procedimientos
        )
    )

    servicio = (
        obtener_servicio_catalogo(
            servicio_id
        )
    )

    tipo_actual = (
        "MEC"
        if tipo == "MOI"
        else "EXT"
    )

    tipo_historico = (
        "MO"
        if tipo == "MOI"
        else "MOE"
    )

    # ======================================================
    # SERVICIOS ACTUALES
    # ======================================================

    actuales_base = (
        OrdenServicioDetalle.objects
        .filter(
            tipo_servicio=tipo_actual
        )
        .exclude(
            orden_id=orden_actual.pk
        )
        .exclude(
            precio_unitario__lte=CERO
        )
    )

    ids_actuales = (
        _ids_candidatos_mano_obra_actual(
            queryset_base=
                actuales_base,
            descripcion=
                descripcion,
            procedimientos=
                procedimientos,
            servicio=
                servicio,
            variante=
                variante,
        )
    )

    actuales = (
        actuales_base
        .filter(
            id__in=ids_actuales
        )
        .select_related(
            "orden",
            "orden__sucursal",
            "servicio",
        )
        .prefetch_related(
            "procedimientos_detalle"
        )
    )

    for item in actuales:

        (
            similitud,
            hijos,
            detalle,
        ) = (
            calcular_similitud_servicio_actual(
                orden_actual=
                    orden_actual,
                item=item,
                descripcion=
                    descripcion,
                procedimientos=
                    procedimientos,
                servicio=
                    servicio,
                variante=
                    variante,
            )
        )

        if (
            similitud
            * 100
            < UMBRAL_COINCIDENCIA
        ):
            continue

        resultados.append(
            construir_resultado(
                item_id=item.id,
                orden=item.orden,
                descripcion=(
                    item.descripcion_servicio
                ),
                precio_unitario=(
                    item.precio_unitario
                ),
                cantidad=item.cantidad,
                origen="ACTUAL",
                similitud=similitud,
                referencia=(
                    item.servicio.codigo
                    if item.servicio
                    else ""
                ),
                procedimientos=hijos,
                servicio_id=(
                    item.servicio_id
                ),
                variante=(
                    item
                    .variante_precio_aplicada
                ),
                detalle_similitud=
                    detalle,
            )
        )

    # ======================================================
    # SERVICIOS MIGRADOS / HISTÓRICOS
    # ======================================================

    historicos_base = (
        OrdenServicioHistorico.objects
        .filter(
            tipo=tipo_historico,
            es_cortesia=False,
        )
        .exclude(
            orden_id=orden_actual.pk
        )
        .exclude(
            precio_unitario__isnull=True
        )
        .exclude(
            precio_unitario__lte=CERO
        )
    )

    ids_historicos = (
        _ids_candidatos_mano_obra_historico(
            queryset_base=
                historicos_base,
            descripcion=
                descripcion,
            procedimientos=
                procedimientos,
        )
    )

    historicos = (
        historicos_base
        .filter(
            id__in=ids_historicos
        )
        .select_related(
            "orden",
            "orden__sucursal",
        )
    )

    for item in historicos:

        (
            similitud,
            hijos,
            detalle,
        ) = (
            calcular_similitud_servicio_historico(
                orden_actual=
                    orden_actual,
                item=item,
                descripcion=
                    descripcion,
                procedimientos=
                    procedimientos,
            )
        )

        if (
            similitud
            * 100
            < UMBRAL_COINCIDENCIA
        ):
            continue

        resultados.append(
            construir_resultado(
                item_id=item.id,
                orden=item.orden,
                descripcion=(
                    item.descripcion_original
                ),
                precio_unitario=(
                    item.precio_unitario
                ),
                cantidad=item.cantidad,
                origen="MIGRADA",
                similitud=similitud,
                procedimientos=hijos,
                detalle_similitud=
                    detalle,
            )
        )

    # ======================================================
    # ORDENAR RESULTADOS
    # ======================================================

    ordenar_resultados(
        resultados,
        orden_actual,
    )

    # ======================================================
    # REFERENCIA DE CATÁLOGO
    # ======================================================

    resumen_catalogo = (
        obtener_resumen_servicio(
            orden_actual=
                orden_actual,
            servicio=
                servicio,
            variante=
                variante,
        )
    )

    return (
        resultados,
        resumen_catalogo,
        servicio,
    )





# ==========================================================

# MEDIANA PONDERADA

# ==========================================================



def mediana_ponderada(

    filas,

):

    """

    Utiliza la similitud como peso.



    A mayor similitud con el caso actual,

    mayor influencia tiene el antecedente.



    La mediana ponderada resiste mejor

    precios atípicos que un promedio simple.

    """



    datos = []



    for fila in filas:



        precio = decimal_seguro(

            fila.get(

                "precio_unitario"

            )

        )



        similitud = decimal_seguro(

            fila.get(

                "similitud"

            )

        )



        if (

            precio <= CERO

            or similitud <= CERO

        ):

            continue



        datos.append(

            (

                precio,

                similitud,

            )

        )



    if not datos:

        return None



    datos.sort(

        key=lambda dato: dato[0]

    )



    peso_total = sum(

        (

            peso

            for _, peso in datos

        ),

        CERO,

    )



    if peso_total <= CERO:

        return None



    objetivo = (

        peso_total

        / Decimal("2")

    )



    acumulado = CERO



    for precio, peso in datos:



        acumulado += peso



        if acumulado >= objetivo:

            return decimal_dos(

                precio

            )



    return decimal_dos(

        datos[-1][0]

    )





# ==========================================================

# PROMEDIO PONDERADO

# ==========================================================



def promedio_ponderado(

    filas,

):

    numerador = CERO

    denominador = CERO



    for fila in filas:



        precio = decimal_seguro(

            fila.get(

                "precio_unitario"

            )

        )



        peso = decimal_seguro(

            fila.get(

                "similitud"

            )

        )



        if (

            precio <= CERO

            or peso <= CERO

        ):

            continue



        numerador += (

            precio * peso

        )



        denominador += peso



    if denominador <= CERO:

        return None



    return decimal_dos(

        numerador

        / denominador

    )





# ==========================================================

# PRECIO SUGERIDO HISTÓRICO

# ==========================================================


def calcular_sugerencia(
    resultados,
):
    """
    Calcula una sugerencia histórica robusta.

    REGLA MAO:

    1. Solo usa antecedentes con similitud suficiente.
    2. Toma como máximo los antecedentes más comparables.
    3. Detecta valores atípicos mediante IQR.
    4. Los atípicos NO participan en la sugerencia.
    5. Cada antecedente recibe un peso según:
       - similitud;
       - antigüedad.
    6. El precio sugerido corresponde al percentil 65
       ponderado.

    Esto busca un precio ligeramente superior al centro
    del mercado histórico de MAO, sin caer automáticamente
    en el valor máximo.

    El rango mínimo/máximo se conserva sobre los antecedentes
    originales para que el usuario pueda ver el rango real.
    """

    # =====================================================
    # FILTRAR COMPARABLES
    # =====================================================

    comparables = [
        fila
        for fila in resultados
        if (
            fila.get(
                "similitud",
                0,
            )
            >= UMBRAL_COMPARABLE

            and fila.get(
                "precio_unitario"
            )
            is not None

            and decimal_seguro(
                fila.get(
                    "precio_unitario"
                )
            )
            > CERO
        )
    ]


    # =====================================================
    # SIN DATOS
    # =====================================================

    if not comparables:

        return {
            "precio_sugerido": None,
            "confianza": "BAJA",
            "cantidad_comparables": 0,
            "cantidad_utilizados": 0,
            "atipicos_excluidos": 0,
            "mediana": None,
            "promedio_ponderado": None,
            "minimo": None,
            "maximo": None,
            "ultimo_precio": None,
            "mejor_similitud": None,
        }


    # =====================================================
    # TOMAR LOS MÁS COMPARABLES
    # =====================================================

    principales = comparables[
        :MAXIMO_COMPARABLES_SUGERENCIA
    ]


    precios_originales = [
        decimal_seguro(
            fila[
                "precio_unitario"
            ]
        )
        for fila in principales
    ]


    # =====================================================
    # PERCENTIL SIMPLE
    # Se usa para obtener Q1 y Q3.
    # =====================================================

    def percentil_simple(
        valores,
        proporcion,
    ):

        valores = sorted(
            valores
        )

        cantidad = len(
            valores
        )

        if cantidad == 1:
            return valores[0]

        posicion = (
            (cantidad - 1)
            * proporcion
        )

        inferior = int(
            posicion
        )

        superior = min(
            inferior + 1,
            cantidad - 1,
        )

        fraccion = (
            posicion
            - inferior
        )

        fraccion_decimal = (
            decimal_seguro(
                str(
                    fraccion
                )
            )
        )

        return (
            valores[inferior]
            +
            (
                valores[superior]
                - valores[inferior]
            )
            * fraccion_decimal
        )


    # =====================================================
    # ELIMINAR PRECIOS ATÍPICOS
    # Método IQR:
    #
    # Q1 - 1.5 * IQR
    # Q3 + 1.5 * IQR
    # =====================================================

    principales_limpios = list(
        principales
    )

    if len(
        precios_originales
    ) >= 7:

        q1 = percentil_simple(
            precios_originales,
            0.25,
        )

        q3 = percentil_simple(
            precios_originales,
            0.75,
        )

        iqr = (
            q3
            - q1
        )

        # Si todos los precios son prácticamente iguales,
        # no tiene sentido aplicar filtro IQR.
        if iqr > CERO:

            factor_iqr = (
                decimal_seguro(
                    "1.5"
                )
            )

            limite_inferior = (
                q1
                -
                (
                    factor_iqr
                    * iqr
                )
            )

            limite_superior = (
                q3
                +
                (
                    factor_iqr
                    * iqr
                )
            )


            filtrados = [
                fila
                for fila in principales
                if (
                    decimal_seguro(
                        fila[
                            "precio_unitario"
                        ]
                    )
                    >= limite_inferior

                    and decimal_seguro(
                        fila[
                            "precio_unitario"
                        ]
                    )
                    <= limite_superior
                )
            ]


            # Seguridad:
            # nunca nos quedamos sin antecedentes.
            if filtrados:
                principales_limpios = (
                    filtrados
                )


    # =====================================================
    # PESO POR ANTIGÜEDAD
    # =====================================================

    def peso_recencia(
        fecha_fila,
    ):

        if not fecha_fila:
            return 0.35


        # Por si alguna fecha llega como datetime.
        if (
            hasattr(
                fecha_fila,
                "date",
            )
            and callable(
                fecha_fila.date
            )
        ):
            try:
                fecha_fila = (
                    fecha_fila.date()
                )
            except Exception:
                pass


        try:

            dias = (
                date.today()
                - fecha_fila
            ).days

        except (
            TypeError,
            ValueError,
        ):

            return 0.35


        dias = max(
            dias,
            0,
        )


        # 0 - 3 meses
        if dias <= 90:
            return 1.00

        # 4 - 6 meses
        if dias <= 180:
            return 0.90

        # 7 - 12 meses
        if dias <= 365:
            return 0.75

        # 13 - 24 meses
        if dias <= 730:
            return 0.55

        # Más de 2 años
        return 0.35


    # =====================================================
    # PERCENTIL PONDERADO
    # =====================================================

    def percentil_ponderado(
        filas,
        proporcion=0.65,
    ):

        datos = []


        for fila in filas:

            precio = decimal_seguro(
                fila[
                    "precio_unitario"
                ]
            )


            similitud = float(
                fila.get(
                    "similitud",
                    0,
                )
                or 0
            )


            # La similitud pesa de forma no lineal.
            #
            # 95% pesa mucho más que 65%.
            peso_similitud = (
                similitud
                / 100.0
            ) ** 2


            recencia = peso_recencia(
                fila.get(
                    "fecha"
                )
            )


            peso = (
                peso_similitud
                * recencia
            )


            if peso <= 0:
                continue


            datos.append(
                (
                    precio,
                    decimal_seguro(
                        str(
                            peso
                        )
                    ),
                )
            )


        if not datos:
            return None


        # Percentil requiere precios ordenados
        # de menor a mayor.
        datos.sort(
            key=lambda item: (
                item[0]
            )
        )


        peso_total = sum(
            (
                item[1]
                for item in datos
            ),
            CERO,
        )


        if peso_total <= CERO:
            return None


        objetivo = (
            peso_total
            * decimal_seguro(
                str(
                    proporcion
                )
            )
        )


        acumulado = CERO


        for (
            precio,
            peso,
        ) in datos:

            acumulado += peso

            if acumulado >= objetivo:
                return precio


        return datos[-1][0]


    # =====================================================
    # PRECIO SUGERIDO
    # =====================================================

    sugerido = percentil_ponderado(
        principales_limpios,
        proporcion=0.65,
    )


    if sugerido is not None:

        sugerido = decimal_dos(
            sugerido
        )


    # =====================================================
    # ESTADÍSTICAS
    # =====================================================

    mediana = mediana_ponderada(
        principales_limpios
    )


    promedio = promedio_ponderado(
        principales_limpios
    )


    mejor_similitud = (
        principales[0][
            "similitud"
        ]
    )


    # =====================================================
    # CONFIANZA
    # =====================================================

    cantidad_utilizados = len(
        principales_limpios
    )


    if (
        cantidad_utilizados >= 5
        and mejor_similitud >= 80
    ):

        confianza = "ALTA"


    elif (
        cantidad_utilizados >= 2
        and mejor_similitud >= 70
    ):

        confianza = "MEDIA"


    else:

        confianza = "BAJA"


    # =====================================================
    # ÚLTIMO PRECIO
    #
    # Aquí NO eliminamos atípicos porque queremos mostrar
    # cuál fue realmente el último precio registrado.
    # =====================================================

    por_fecha = sorted(
        principales,
        key=lambda fila: (
            fila.get(
                "fecha"
            )
            or date.min
        ),
        reverse=True,
    )


    ultimo_precio = (
        por_fecha[0][
            "precio_unitario"
        ]
        if por_fecha
        else None
    )


    # =====================================================
    # RESPUESTA
    # =====================================================

    return {

        "precio_sugerido": (
            sugerido
        ),

        "confianza": (
            confianza
        ),

        # Seguimos mostrando cuántos antecedentes
        # principales fueron encontrados.
        "cantidad_comparables": (
            len(
                principales
            )
        ),

        # Cuántos participaron realmente en el cálculo.
        "cantidad_utilizados": (
            cantidad_utilizados
        ),

        "atipicos_excluidos": (
            len(
                principales
            )
            - cantidad_utilizados
        ),

        "mediana": (
            mediana
        ),

        "promedio_ponderado": (
            promedio
        ),

        # El rango sigue mostrando TODO el rango observado
        # entre los 15 principales.
        "minimo": decimal_dos(
            min(
                precios_originales
            )
        ),

        "maximo": decimal_dos(
            max(
                precios_originales
            )
        ),

        "ultimo_precio": (
            ultimo_precio
        ),

        "mejor_similitud": (
            mejor_similitud
        ),
    }

# ==========================================================
# DATOS DE CONTEXTO DE LA OT
# ==========================================================


def obtener_contexto_orden(

    orden_actual,

):

    return {

        "orden_id": (

            orden_actual.id

        ),

        "numero_orden": (

            orden_actual.numero_orden

        ),

        "sucursal_id": (

            orden_actual.sucursal_id

        ),

        "sucursal": (

            orden_actual.sucursal.codigo

            if orden_actual.sucursal

            else ""

        ),

        "placa": (

            orden_actual.placa

            or ""

        ),

        "vehiculo": (

            orden_actual.vehiculo

            or ""

        ),

        "anio": (

            orden_actual.anio_vehiculo

        ),

        "kilometraje": (

            orden_actual.kilometraje

        ),

    }





# ==========================================================

# FUNCIÓN PRINCIPAL

# ==========================================================



def consultar_precio(

    *,

    orden_actual,

    tipo,

    descripcion,

    codigo=None,

    codigo_producto_id=None,

    servicio_id=None,

    variante="NORMAL",

    procedimientos=None,

):

    """

    Punto de entrada único del motor.



    TIPOS:



        REP

        MOI

        MOE



    ----------------------------------------------------------



    REP:



        Puede trabajar con:

        - texto libre

        - código escrito

        - CodigoProducto seleccionado



    ----------------------------------------------------------



    MOI / MOE:



        Puede trabajar con:

        - texto libre

        - ServicioCatalogo seleccionado

        - procedimientos/hijas actuales

        - variante actual



    ----------------------------------------------------------



    IMPORTANTE:



    procedimientos debe contener LO QUE EXISTE

    ACTUALMENTE EN LA PANTALLA.



    No depende de que las hijas ya estén guardadas.

    """



    tipo = (

        str(

            tipo or ""

        )

        .strip()

        .upper()

    )



    descripcion = str(

        descripcion or ""

    ).strip()



    codigo = str(

        codigo or ""

    ).strip()



    variante = (

        str(

            variante or "NORMAL"

        )

        .strip()

        .upper()

    )



    procedimientos = (

        normalizar_lista_procedimientos(

            procedimientos

        )

    )



    if not descripcion:



        raise ValueError(

            "La descripción del ítem es obligatoria."

        )



    # ======================================================

    # REPUESTOS

    # ======================================================



    if tipo == "REP":



        (

            resultados,

            inventario,

            codigo_producto,

        ) = buscar_repuestos(

            orden_actual=

                orden_actual,

            descripcion=

                descripcion,

            codigo=

                codigo,

            codigo_producto_id=

                codigo_producto_id,

        )



        sugerencia = (

            calcular_sugerencia(

                resultados

            )

        )


        antecedente_mismo_vehiculo = (

            obtener_antecedente_mismo_vehiculo(

                resultados,

                orden_actual,

            )

        )



        return {

            "tipo": "REP",

            "descripcion": (

                descripcion

            ),

            "codigo": (

                codigo

            ),

            "codigo_producto_id": (

                codigo_producto.id

                if codigo_producto

                else None

            ),

            "orden_actual": (

                obtener_contexto_orden(

                    orden_actual

                )

            ),

            "inventario": (

                inventario

            ),

            "catalogo_servicio": None,

            "procedimientos": [],

            "sugerencia": (

                sugerencia

            ),

            "antecedente_mismo_vehiculo": (

                antecedente_mismo_vehiculo

            ),

            "total_coincidencias": (

                len(resultados)

            ),

            "coincidencias": (

                resultados[

                    :MAXIMO_COINCIDENCIAS_RESPUESTA

                ]

            ),

        }



    # ======================================================

    # MANO DE OBRA

    # ======================================================



    if tipo in {

        "MOI",

        "MOE",

    }:



        (

            resultados,

            resumen_catalogo,

            servicio,

        ) = buscar_mano_obra(

            orden_actual=

                orden_actual,

            tipo=tipo,

            descripcion=

                descripcion,

            procedimientos=

                procedimientos,

            servicio_id=

                servicio_id,

            variante=

                variante,

        )



        sugerencia = (

            calcular_sugerencia(

                resultados

            )

        )


        antecedente_mismo_vehiculo = (

            obtener_antecedente_mismo_vehiculo(

                resultados,

                orden_actual,

            )

        )



        return {

            "tipo": tipo,

            "descripcion": (

                descripcion

            ),

            "codigo": (

                servicio.codigo

                if servicio

                else ""

            ),

            "servicio_id": (

                servicio.id

                if servicio

                else None

            ),

            "variante": (

                variante

            ),

            "orden_actual": (

                obtener_contexto_orden(

                    orden_actual

                )

            ),

            "inventario": None,

            "catalogo_servicio": (

                resumen_catalogo

            ),

            "procedimientos": (

                procedimientos

            ),

            "sugerencia": (

                sugerencia

            ),

            "antecedente_mismo_vehiculo": (

                antecedente_mismo_vehiculo

            ),

            "total_coincidencias": (

                len(resultados)

            ),

            "coincidencias": (

                resultados[

                    :MAXIMO_COINCIDENCIAS_RESPUESTA

                ]

            ),

        }



    raise ValueError(

        "Tipo de consulta no válido. "

        "Debe ser REP, MOI o MOE."

    )