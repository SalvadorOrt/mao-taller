import uuid
import traceback
from django.core.paginator import Paginator
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import (
    render,
    redirect,
    get_object_or_404,
)
from django.utils import timezone

from inventario.models import (
    CodigoProducto,
    Categoria,
)

from servicios.models import ServicioCatalogo

from ...models import (
    Sucursal,
    Cliente,
    OrdenTrabajo,
    OrdenInsumoDetalle,
    OrdenServicioDetalle,
    OrdenServicioProcedimientoDetalle,
    Cotizacion,
    CotizacionInsumoDetalle,
    CotizacionServicioDetalle,
    CotizacionProcedimientoDetalle,
)

from ..utils import (
    parse_decimal,
    parse_cantidad,
    parse_int,
    obtener_sucursal_activa,
    obtener_o_crear_expediente,
)


# =========================================================
# UTILIDADES
# =========================================================

def item(
    lista,
    i,
    default="",
):
    if i < len(lista):
        return str(
            lista[i]
        ).strip()

    return default


def post_booleano(
    request,
    nombre,
    default=False,
):
    """
    Lee correctamente campos tipo checkbox.

    Soporta el patrón:

        hidden = 0
        checkbox = 1

    por lo que QueryDict puede contener:
        ["0", "1"]
    """

    if nombre not in request.POST:
        return default

    valores = request.POST.getlist(
        nombre
    )

    valores_verdaderos = {
        "1",
        "true",
        "on",
        "yes",
        "si",
        "sí",
    }

    return any(
        str(valor)
        .strip()
        .lower()
        in valores_verdaderos
        for valor in valores
    )


def obtener_version_cotizacion_post(
    request,
    version_actual,
):
    """
    Compatibilidad temporal:

    Si el HTML antiguo todavía no envía
    cotizacion_version, utilizamos la versión
    actualmente bloqueada.

    Cuando actualicemos detalle_cotizacion.html
    sí enviaremos siempre este campo.
    """

    valor = request.POST.get(
        "cotizacion_version"
    )

    if valor in (
        None,
        "",
    ):
        return version_actual

    try:
        version = int(
            str(valor).strip()
        )

    except (
        TypeError,
        ValueError,
    ):
        raise ValidationError(
            "La versión recibida de la "
            "cotización no es válida."
        )

    if version <= 0:
        raise ValidationError(
            "La versión recibida de la "
            "cotización no es válida."
        )

    return version


# =========================================================
# DATOS HISTÓRICOS DEL CLIENTE EN COTIZACIÓN
# =========================================================

def snapshot_cliente_cotizacion(
    cliente,
    nombre_respaldo="",
):
    """
    Devuelve los datos de contacto que deben quedar congelados
    en la cotización/revisión.

    La FK cliente conserva la relación con la ficha maestra, pero
    estos campos impiden que una proforma histórica cambie si el
    cliente actualiza después su teléfono, correo o dirección.
    """

    if cliente:
        return {
            "cliente_respaldo": (
                cliente.nombre_completo
                or nombre_respaldo
                or None
            ),
            "identificacion_cliente_respaldo": (
                cliente.identificacion
                or None
            ),
            "telefono_respaldo": (
                cliente.telefono
                or None
            ),
            "telefono_secundario_respaldo": (
                cliente.telefono_secundario
                or None
            ),
            "telefono_trabajo_respaldo": (
                cliente.telefono_trabajo
                or None
            ),
            "email_respaldo": (
                cliente.email
                or None
            ),
            "direccion_respaldo": (
                cliente.direccion
                or None
            ),
        }

    return {
        "cliente_respaldo": (
            nombre_respaldo
            or None
        ),
        "identificacion_cliente_respaldo": None,
        "telefono_respaldo": None,
        "telefono_secundario_respaldo": None,
        "telefono_trabajo_respaldo": None,
        "email_respaldo": None,
        "direccion_respaldo": None,
    }


# =========================================================
# PRODUCTOS
# =========================================================

def buscar_producto(
    p_id,
    barras,
    empaque,
):
    if p_id:

        producto = (
            CodigoProducto.objects
            .filter(
                id=p_id,
                activo=True,
            )
            .first()
        )

        if producto:
            return producto

    codigo_busqueda = (
        barras
        or empaque
    )

    if codigo_busqueda:

        producto = (
            CodigoProducto.objects
            .filter(
                Q(
                    codigo=
                    codigo_busqueda
                )
                |
                Q(
                    codigo_barras=
                    codigo_busqueda
                )
                |
                Q(
                    nombre_comercial__icontains=
                    codigo_busqueda
                )
            )
            .first()
        )

        if (
            producto
            and producto.activo
        ):
            return producto

    return None


# =========================================================
# MERGE REPUESTOS
# =========================================================

def merge_repuestos_cotizacion(
    request,
    cotizacion,
):

    detalle_ids = (
        request.POST.getlist(
            "rep_detalle_id[]"
        )
    )

    producto_ids = (
        request.POST.getlist(
            "rep_producto_id[]"
        )
    )

    descripciones = (
        request.POST.getlist(
            "rep_descripcion[]"
        )
    )

    precios = (
        request.POST.getlist(
            "rep_pu[]"
        )
    )

    cantidades = (
        request.POST.getlist(
            "rep_cantidad[]"
        )
    )

    categorias = (
        request.POST.getlist(
            "rep_categoria_id[]"
        )
    )

    barras_list = (
        request.POST.getlist(
            "rep_codigo_barras[]"
        )
    )

    empaques = (
        request.POST.getlist(
            "rep_codigo_empaque[]"
        )
    )

    deletes = (
        request.POST.getlist(
            "rep_delete[]"
        )
    )

    marcados = (
        request.POST.getlist(
            "rep_marcado[]"
        )
    )

    total = max(
        len(detalle_ids),
        len(producto_ids),
        len(descripciones),
        len(precios),
        len(cantidades),
        len(categorias),
        len(barras_list),
        len(empaques),
        len(deletes),
        len(marcados),
        0,
    )

    existentes = {
        str(obj.id): obj
        for obj
        in (
            CotizacionInsumoDetalle
            .objects
            .select_for_update()
            .filter(
                cotizacion=cotizacion
            )
        )
    }

    for i in range(total):

        detalle_id = item(
            detalle_ids,
            i,
        )

        producto_id = item(
            producto_ids,
            i,
        )

        descripcion = item(
            descripciones,
            i,
        )

        pu_str = item(
            precios,
            i,
        )

        cantidad_str = item(
            cantidades,
            i,
        )

        categoria_id = item(
            categorias,
            i,
        )

        barras = item(
            barras_list,
            i,
        )

        empaque = item(
            empaques,
            i,
        )

        eliminar = (
            item(
                deletes,
                i,
            )
            == "1"
        )

        marcado_raw = item(
            marcados,
            i,
            None,
        )

        # -----------------------------------------------------
        # FILA VACÍA NUEVA
        # -----------------------------------------------------

        if (
            not detalle_id
            and not producto_id
            and not descripcion
        ):
            continue

        # -----------------------------------------------------
        # REGISTRO EXISTENTE
        # -----------------------------------------------------

        if detalle_id:

            detalle = (
                existentes.get(
                    detalle_id
                )
            )

            if not detalle:
                raise ValidationError(
                    "Uno de los repuestos que intenta "
                    "modificar ya no pertenece a esta "
                    "cotización."
                )

            if eliminar:
                detalle.delete()
                continue

            cantidad = parse_cantidad(
                cantidad_str,
                Decimal("1.00"),
            )

            if cantidad <= 0:
                continue

            producto = buscar_producto(
                producto_id,
                barras,
                empaque,
            )

            precio_default = (
                Decimal(
                    producto.precio_venta
                    or 0
                )
                if producto
                else Decimal("0.00")
            )

            precio = parse_decimal(
                pu_str,
                precio_default,
            )

            detalle.producto = (
                producto
            )

            detalle.descripcion_factura = (
                descripcion
            )

            detalle.cantidad = (
                cantidad
            )

            detalle.precio_unitario = (
                precio
            )

            detalle.categoria_referencia_id = (
                None
                if producto
                else (
                    categoria_id
                    or None
                )
            )

            detalle.codigo_barras_referencia = (
                None
                if producto
                else (
                    barras
                    or None
                )
            )

            detalle.codigo_empaque_referencia = (
                None
                if producto
                else (
                    empaque
                    or None
                )
            )

            detalle.orden_item = (
                i + 1
            )

            # Si el HTML nuevo envía el valor,
            # actualizamos el marcado.
            # Si todavía estamos usando el HTML viejo,
            # conservamos el valor actual.
            if marcado_raw is not None:

                detalle.marcado = (
                    str(marcado_raw)
                    .strip()
                    == "1"
                )

            detalle.save()

        # -----------------------------------------------------
        # REGISTRO NUEVO
        # -----------------------------------------------------

        else:

            if eliminar:
                continue

            cantidad = parse_cantidad(
                cantidad_str,
                Decimal("1.00"),
            )

            if cantidad <= 0:
                continue

            producto = buscar_producto(
                producto_id,
                barras,
                empaque,
            )

            precio_default = (
                Decimal(
                    producto.precio_venta
                    or 0
                )
                if producto
                else Decimal("0.00")
            )

            precio = parse_decimal(
                pu_str,
                precio_default,
            )

            marcado = (
                str(
                    marcado_raw
                    or ""
                ).strip()
                == "1"
            )

            CotizacionInsumoDetalle.objects.create(
                cotizacion=
                    cotizacion,

                producto=
                    producto,

                descripcion_factura=
                    descripcion,

                cantidad=
                    cantidad,

                precio_unitario=
                    precio,

                categoria_referencia_id=(
                    None
                    if producto
                    else (
                        categoria_id
                        or None
                    )
                ),

                codigo_barras_referencia=(
                    None
                    if producto
                    else (
                        barras
                        or None
                    )
                ),

                codigo_empaque_referencia=(
                    None
                    if producto
                    else (
                        empaque
                        or None
                    )
                ),

                orden_item=
                    i + 1,

                marcado=
                    marcado,
            )


# =========================================================
# MERGE PROCEDIMIENTOS
# =========================================================

def merge_procedimientos_cotizacion(
    request,
    detalle_servicio,
    prefix,
    uid,
):

    proc_ids = (
        request.POST.getlist(
            f"{prefix}_procedimiento_id_{uid}[]"
        )
    )

    proc_descs = (
        request.POST.getlist(
            f"{prefix}_procedimientos_{uid}[]"
        )
    )

    proc_deletes = (
        request.POST.getlist(
            f"{prefix}_procedimiento_delete_{uid}[]"
        )
    )

    total = max(
        len(proc_ids),
        len(proc_descs),
        len(proc_deletes),
        0,
    )

    existentes = {
        str(obj.id): obj
        for obj
        in (
            CotizacionProcedimientoDetalle
            .objects
            .select_for_update()
            .filter(
                servicio_cotizado=
                    detalle_servicio
            )
        )
    }

    vistos = set()

    for i in range(total):

        proc_id = item(
            proc_ids,
            i,
        )

        descripcion = item(
            proc_descs,
            i,
        )

        eliminar = (
            item(
                proc_deletes,
                i,
            )
            == "1"
        )

        if (
            not proc_id
            and not descripcion
        ):
            continue

        clave = (
            descripcion
            .strip()
            .upper()
        )

        # Evita que el mismo procedimiento
        # venga dos veces dentro del mismo POST.
        if (
            clave
            and clave in vistos
        ):
            continue

        if clave:
            vistos.add(
                clave
            )

        # -----------------------------------------------------
        # EXISTENTE
        # -----------------------------------------------------

        if proc_id:

            proc = (
                existentes.get(
                    proc_id
                )
            )

            if not proc:
                raise ValidationError(
                    "Uno de los procedimientos que "
                    "intenta modificar ya no pertenece "
                    "a este servicio cotizado."
                )

            if eliminar:
                proc.delete()
                continue

            if not descripcion:
                continue

            proc.descripcion = (
                descripcion
            )

            proc.orden_item = (
                i + 1
            )

            proc.save()

        # -----------------------------------------------------
        # NUEVO
        # -----------------------------------------------------

        else:

            if eliminar:
                continue

            if not descripcion:
                continue

            CotizacionProcedimientoDetalle.objects.create(
                servicio_cotizado=
                    detalle_servicio,

                descripcion=
                    descripcion,

                orden_item=
                    i + 1,
            )


# =========================================================
# MERGE SERVICIOS MOI / MOE
# =========================================================

def merge_servicios_cotizacion(
    request,
    cotizacion,
):

    for prefix, tipo_bd in [
        (
            "moi",
            "MEC",
        ),
        (
            "moe",
            "EXT",
        ),
    ]:

        detalle_ids = (
            request.POST.getlist(
                f"{prefix}_detalle_id[]"
            )
        )

        uid_list = (
            request.POST.getlist(
                f"{prefix}_uid[]"
            )
        )

        desc_list = (
            request.POST.getlist(
                f"{prefix}_descripcion[]"
            )
        )

        pu_list = (
            request.POST.getlist(
                f"{prefix}_pu[]"
            )
        )

        cant_list = (
            request.POST.getlist(
                f"{prefix}_cantidad[]"
            )
        )

        serv_ids = (
            request.POST.getlist(
                f"{prefix}_servicio_id[]"
            )
        )

        variante_list = (
            request.POST.getlist(
                f"{prefix}_variante_precio[]"
            )
        )

        deletes = (
            request.POST.getlist(
                f"{prefix}_delete[]"
            )
        )

        total = max(
            len(detalle_ids),
            len(uid_list),
            len(desc_list),
            len(pu_list),
            len(cant_list),
            len(serv_ids),
            len(variante_list),
            len(deletes),
            0,
        )

        existentes = {
            str(obj.id): obj
            for obj
            in (
                CotizacionServicioDetalle
                .objects
                .select_for_update()
                .filter(
                    cotizacion=
                        cotizacion,

                    tipo_servicio=
                        tipo_bd,
                )
            )
        }

        for i in range(total):

            detalle_id = item(
                detalle_ids,
                i,
            )

            uid = (
                item(
                    uid_list,
                    i,
                )
                or detalle_id
                or str(i)
            )

            descripcion = item(
                desc_list,
                i,
            )

            precio_str = item(
                pu_list,
                i,
                "0.00",
            )

            cantidad_str = item(
                cant_list,
                i,
                "1.00",
            )

            servicio_id = item(
                serv_ids,
                i,
            )

            variante = (
                item(
                    variante_list,
                    i,
                ).upper()
                or "NORMAL"
            )

            eliminar = (
                item(
                    deletes,
                    i,
                )
                == "1"
            )

            servicio = None

            if servicio_id:

                servicio = (
                    ServicioCatalogo.objects
                    .filter(
                        id=servicio_id,
                        activo=True,
                    )
                    .first()
                )

            if (
                servicio
                and not descripcion
            ):
                descripcion = (
                    servicio.descripcion
                )

            if (
                not detalle_id
                and not descripcion
                and not servicio
            ):
                continue

            # -------------------------------------------------
            # EXISTENTE
            # -------------------------------------------------

            if detalle_id:

                detalle = (
                    existentes.get(
                        detalle_id
                    )
                )

                if not detalle:
                    raise ValidationError(
                        "Uno de los servicios que intenta "
                        "modificar ya no pertenece a esta "
                        "cotización."
                    )

                if eliminar:
                    detalle.delete()
                    continue

                cantidad = parse_decimal(
                    cantidad_str,
                    Decimal("1.00"),
                )

                if cantidad <= 0:
                    continue

                precio = parse_decimal(
                    precio_str,
                    Decimal("0.00"),
                )

                detalle.servicio = (
                    servicio
                )

                detalle.descripcion_servicio = (
                    descripcion
                )

                detalle.cantidad = (
                    cantidad
                )

                detalle.precio_unitario = (
                    precio
                )

                detalle.orden_item = (
                    i + 1
                )

                detalle.tipo_servicio = (
                    tipo_bd
                )

                detalle.variante_precio_aplicada = (
                    variante
                )

                detalle.save()

            # -------------------------------------------------
            # NUEVO
            # -------------------------------------------------

            else:

                if eliminar:
                    continue

                cantidad = parse_decimal(
                    cantidad_str,
                    Decimal("1.00"),
                )

                if cantidad <= 0:
                    continue

                precio = parse_decimal(
                    precio_str,
                    Decimal("0.00"),
                )

                detalle = (
                    CotizacionServicioDetalle
                    .objects
                    .create(
                        cotizacion=
                            cotizacion,

                        servicio=
                            servicio,

                        descripcion_servicio=
                            descripcion,

                        cantidad=
                            cantidad,

                        precio_unitario=
                            precio,

                        orden_item=
                            i + 1,

                        tipo_servicio=
                            tipo_bd,

                        variante_precio_aplicada=
                            variante,
                    )
                )

            # -------------------------------------------------
            # PROCEDIMIENTOS
            # -------------------------------------------------

            merge_procedimientos_cotizacion(
                request=
                    request,

                detalle_servicio=
                    detalle,

                prefix=
                    prefix,

                uid=
                    uid,
            )


# =========================================================
# GUARDAR DETALLE COTIZACIÓN
# =========================================================

def guardar_detalle_cotizacion(
    request,
    pk,
):

    with transaction.atomic():

        cotizacion = (
            Cotizacion.objects
            .select_for_update(
                of=("self",)
            )
            .get(
                pk=pk
            )
        )

        # -----------------------------------------------------
        # BLOQUEO POR ESTADO
        # -----------------------------------------------------

        if not cotizacion.puede_editarse():

            messages.error(
                request,
                (
                    "No se puede modificar una "
                    "cotización aprobada o rechazada."
                ),
            )

            return redirect(
                "detalle_cotizacion",
                pk=cotizacion.pk,
            )

        # -----------------------------------------------------
        # CONTROL DE VERSIÓN
        # -----------------------------------------------------

        version_recibida = (
            obtener_version_cotizacion_post(
                request,
                cotizacion.version,
            )
        )

        if (
            version_recibida
            != cotizacion.version
        ):

            messages.warning(
                request,
                (
                    "Esta cotización cambió mientras "
                    "usted la estaba editando. "
                    "Se recargó la versión más reciente "
                    "para evitar duplicar información."
                ),
            )

            return redirect(
                "detalle_cotizacion",
                pk=cotizacion.pk,
            )

        # -----------------------------------------------------
        # DETALLES
        # -----------------------------------------------------

        merge_repuestos_cotizacion(
            request,
            cotizacion,
        )

        merge_servicios_cotizacion(
            request,
            cotizacion,
        )

        # -----------------------------------------------------
        # DESCUENTO
        # -----------------------------------------------------

        tipo_descuento_post = (
            request.POST.get(
                "tipo_descuento"
            )
        )

        if tipo_descuento_post:

            tipo_descuento = (
                tipo_descuento_post
                .strip()
                .upper()
            )

        else:
            tipo_descuento = (
                cotizacion.tipo_descuento
                or "PORCENTAJE"
            )

        if tipo_descuento not in {
            "PORCENTAJE",
            "VALOR_FIJO",
        }:
            raise ValidationError(
                "El tipo de descuento "
                "no es válido."
            )

        # Nuevo formulario
        descuento_raw = (
            request.POST.get(
                "descuento_ingresado"
            )
        )

        # Compatibilidad con formulario viejo
        if descuento_raw is None:

            descuento_antiguo = (
                request.POST.get(
                    "descuento_porcentaje"
                )
            )

            if descuento_antiguo is not None:

                tipo_descuento = (
                    "PORCENTAJE"
                )

                descuento_raw = (
                    descuento_antiguo
                )

            else:

                descuento_raw = (
                    cotizacion
                    .descuento_ingresado
                )

        descuento_ingresado = (
            parse_decimal(
                descuento_raw,
                cotizacion.descuento_ingresado
                or Decimal("0.00"),
            )
        )

        # -----------------------------------------------------
        # IVA
        # -----------------------------------------------------

        sumar_iva_al_total = (
            post_booleano(
                request,
                "sumar_iva_al_total",
                default=(
                    cotizacion
                    .sumar_iva_al_total
                ),
            )
        )

        # -----------------------------------------------------
        # OBSERVACIONES
        # -----------------------------------------------------

        observaciones = (
            request.POST.get(
                "observaciones",
                cotizacion.observaciones
                or "",
            )
            .strip()
        )

        # -----------------------------------------------------
        # ACTUALIZAR CABECERA
        # -----------------------------------------------------

        cotizacion.tipo_descuento = (
            tipo_descuento
        )

        cotizacion.descuento_ingresado = (
            descuento_ingresado
        )

        cotizacion.sumar_iva_al_total = (
            sumar_iva_al_total
        )

        cotizacion.observaciones = (
            observaciones
        )

        cotizacion.version += 1

        cotizacion.save(
            update_fields=[
                "tipo_descuento",
                "descuento_ingresado",
                "sumar_iva_al_total",
                "observaciones",
                "version",
            ]
        )

        # -----------------------------------------------------
        # RECÁLCULO FINAL
        # -----------------------------------------------------

        cotizacion.calcular_total()

    messages.success(
        request,
        (
            "Cotización actualizada "
            "correctamente."
        ),
    )

    return redirect(
        "detalle_cotizacion",
        pk=pk,
    )

# =========================================================
# LISTADO DE COTIZACIONES / PROFORMAS
# =========================================================

@login_required
def lista_cotizaciones(
    request,
):

    # =====================================================
    # SUCURSAL ACTIVA
    # =====================================================

    sucursal_activa = (
        obtener_sucursal_activa(
            request
        )
    )

    # =====================================================
    # SUCURSALES DISPONIBLES
    # =====================================================

    sucursales = (
        Sucursal.objects
        .filter(
            activa=True
        )
        .order_by(
            "nombre"
        )
    )

    # =====================================================
    # FILTRO SUCURSAL
    # =====================================================

    sucursal_filtro = (
        request.GET.get(
            "sucursal_filtro",
            "",
        )
        .strip()
    )

    # Primera entrada:
    # mostrar sucursal activa.
    if not sucursal_filtro:

        if sucursal_activa:

            sucursal_filtro = str(
                sucursal_activa.id
            )

        else:

            sucursal_filtro = "todas"

    # =====================================================
    # QUERY BASE
    # =====================================================

    cotizaciones = (
        Cotizacion.objects
        .select_related(
            "sucursal",
            "cliente",
            "orden",
            "orden_generada",
            "configuracion_iva",
            "cotizacion_anterior",
        )
        .order_by(
            "-fecha_creacion",
            "-revision",
            "-id",
        )
    )

    # =====================================================
    # SUCURSAL
    # =====================================================

    if (
        sucursal_filtro
        and sucursal_filtro
        != "todas"
    ):

        cotizaciones = (
            cotizaciones
            .filter(
                sucursal_id=
                    sucursal_filtro
            )
        )

    # =====================================================
    # TOTAL GENERAL
    # =====================================================

    total_general = (
        cotizaciones.count()
    )

    # =====================================================
    # BÚSQUEDA
    # =====================================================

    q = (
        request.GET.get(
            "q",
            "",
        )
        .strip()
    )

    if q:

        cotizaciones = (
            cotizaciones
            .filter(
                Q(
                    numero_cotizacion__icontains=
                        q
                )
                |
                Q(
                    placa__icontains=
                        q
                )
                |
                Q(
                    vehiculo__icontains=
                        q
                )
                |
                Q(
                    cliente__nombre_completo__icontains=
                        q
                )
                |
                Q(
                    cliente_respaldo__icontains=
                        q
                )
                |
                Q(
                    orden__numero_orden__icontains=
                        q
                )
                |
                Q(
                    orden_generada__numero_orden__icontains=
                        q
                )
            )
        )

    # =====================================================
    # ESTADO
    # =====================================================

    estado = (
        request.GET.get(
            "estado",
            "",
        )
        .strip()
        .upper()
    )

    if estado in {
        "PENDIENTE",
        "APROBADA",
        "RECHAZADA",
    }:

        cotizaciones = (
            cotizaciones
            .filter(
                estado=estado
            )
        )

    else:

        estado = ""

    # =====================================================
    # ORIGEN
    # =====================================================

    origen = (
        request.GET.get(
            "origen",
            "",
        )
        .strip()
        .upper()
    )

    if origen == "OT":

        # Cotización nacida desde una OT.
        cotizaciones = (
            cotizaciones
            .filter(
                orden__isnull=False
            )
        )

    elif origen == "INDEPENDIENTE":

        # Cotización creada directamente.
        # Aunque luego genere una OT,
        # su campo "orden" permanece NULL.
        cotizaciones = (
            cotizaciones
            .filter(
                orden__isnull=True
            )
        )

    else:

        origen = ""

    # =====================================================
    # REVISIONES
    # =====================================================

    vigencia = (
        request.GET.get(
            "vigencia",
            "vigentes",
        )
        .strip()
        .lower()
    )

    if vigencia == "todas":

        pass

    else:

        vigencia = "vigentes"

        cotizaciones = (
            cotizaciones
            .filter(
                es_vigente=True
            )
        )

    # =====================================================
    # FECHA INICIO
    # =====================================================

    fecha_inicio = (
        request.GET.get(
            "fecha_inicio",
            "",
        )
        .strip()
    )

    if fecha_inicio:

        cotizaciones = (
            cotizaciones
            .filter(
                fecha_creacion__date__gte=
                    fecha_inicio
            )
        )

    # =====================================================
    # FECHA FIN
    # =====================================================

    fecha_fin = (
        request.GET.get(
            "fecha_fin",
            "",
        )
        .strip()
    )

    if fecha_fin:

        cotizaciones = (
            cotizaciones
            .filter(
                fecha_creacion__date__lte=
                    fecha_fin
            )
        )

    # =====================================================
    # EVITAR DUPLICADOS
    # =====================================================

    cotizaciones = (
        cotizaciones.distinct()
    )

    # =====================================================
    # TOTAL FILTRADO
    # =====================================================

    total_filtrado = (
        cotizaciones.count()
    )

    # =====================================================
    # FILTROS ACTIVOS
    # =====================================================

    sucursal_activa_id = (
        str(
            sucursal_activa.id
        )
        if sucursal_activa
        else ""
    )

    filtro_sucursal_activo = (
        sucursal_filtro
        and sucursal_filtro
        != sucursal_activa_id
    )

    filtros_activos = any([
        q,
        estado,
        origen,
        fecha_inicio,
        fecha_fin,
        vigencia == "todas",
        filtro_sucursal_activo,
    ])

    # =====================================================
    # PAGINACIÓN
    # =====================================================

    LIMITE_RESULTADOS = 40

    paginator = Paginator(
        cotizaciones,
        LIMITE_RESULTADOS,
    )

    page_number = (
        request.GET.get(
            "page"
        )
    )

    page_obj = (
        paginator.get_page(
            page_number
        )
    )

    # =====================================================
    # RANGO MOSTRADO
    # =====================================================

    desde = (
        page_obj.start_index()
        if total_filtrado > 0
        else 0
    )

    hasta = (
        page_obj.end_index()
        if total_filtrado > 0
        else 0
    )

    # =====================================================
    # RENDER
    # =====================================================

    return render(
        request,
        "lista_cotizaciones.html",
        {
            # ---------------------------------------------
            # COTIZACIONES
            # ---------------------------------------------
            "cotizaciones":
                page_obj,

            "page_obj":
                page_obj,

            # ---------------------------------------------
            # SUCURSALES
            # ---------------------------------------------
            "sucursal_activa":
                sucursal_activa,

            "sucursales":
                sucursales,

            "sucursal_filtro":
                sucursal_filtro,

            # ---------------------------------------------
            # FILTROS
            # ---------------------------------------------
            "q":
                q,

            "estado":
                estado,

            "origen":
                origen,

            "vigencia":
                vigencia,

            "fecha_inicio":
                fecha_inicio,

            "fecha_fin":
                fecha_fin,

            # ---------------------------------------------
            # TOTALES
            # ---------------------------------------------
            "total_general":
                total_general,

            "total_filtrado":
                total_filtrado,

            # ---------------------------------------------
            # FILTROS ACTIVOS
            # ---------------------------------------------
            "filtros_activos":
                filtros_activos,

            # ---------------------------------------------
            # PAGINACIÓN
            # ---------------------------------------------
            "desde":
                desde,

            "hasta":
                hasta,

            "limite_resultados":
                LIMITE_RESULTADOS,
        },
    )
# =========================================================
# CREAR COTIZACIÓN INDEPENDIENTE
# =========================================================

@login_required
def crear_cotizacion(
    request,
):

    sucursal_activa = (
        obtener_sucursal_activa(
            request
        )
    )

    if not sucursal_activa:

        messages.error(
            request,
            "Debe tener una sucursal activa.",
        )

        return redirect(
            "dashboard"
        )

    # La creación independiente ahora se realiza desde el modal
    # del listado de proformas. Conservamos esta URL como endpoint
    # POST para no duplicar rutas ni lógica.
    if request.method != "POST":

        return redirect(
            "lista_cotizaciones"
        )

    placa = (
        request.POST.get(
            "placa",
            "",
        )
        .strip()
        .upper()
        .replace("-", "")
        .replace(" ", "")
    )

    vehiculo = (
        request.POST.get(
            "vehiculo",
            "",
        )
        .strip()
        .upper()
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

    identificacion = (
        request.POST.get(
            "identificacion",
            "",
        )
        .strip()
        .upper()
    )

    nombre_cliente = (
        request.POST.get(
            "nombre_cliente",
            "",
        )
        .strip()
        .upper()
    )

    telefono = (
        request.POST.get(
            "telefono",
            "",
        )
        .strip()
    )

    telefono_secundario = (
        request.POST.get(
            "telefono_secundario",
            "",
        )
        .strip()
    )

    telefono_trabajo = (
        request.POST.get(
            "telefono_trabajo",
            "",
        )
        .strip()
    )

    email = (
        request.POST.get(
            "email",
            "",
        )
        .strip()
        .lower()
    )

    direccion = (
        request.POST.get(
            "direccion",
            "",
        )
        .strip()
        .upper()
    )

    observaciones = (
        request.POST.get(
            "observaciones",
            "",
        )
        .strip()
    )

    if not placa:
        messages.error(
            request,
            "La placa es obligatoria.",
        )
        return redirect(
            "lista_cotizaciones"
        )

    if kilometraje is not None and kilometraje < 0:
        messages.error(
            request,
            "El kilometraje no puede ser negativo.",
        )
        return redirect(
            "lista_cotizaciones"
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

    try:
        with transaction.atomic():

            cliente_obj = None

            # =============================================
            # CLIENTE CON IDENTIFICACIÓN
            # =============================================
            if identificacion:

                cliente_obj = (
                    Cliente.objects
                    .select_for_update()
                    .filter(
                        identificacion=
                            identificacion
                    )
                    .first()
                )

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
                        cliente_obj.email = email

                    if direccion:
                        cliente_obj.direccion = (
                            direccion
                        )

                    cliente_obj.save()

                else:

                    cliente_obj = (
                        Cliente.objects
                        .create(
                            tipo_documento=
                                tipo_documento,
                            identificacion=
                                identificacion,
                            nombre_completo=(
                                nombre_cliente
                                or "CONSUMIDOR FINAL"
                            ),
                            telefono=
                                telefono or None,
                            telefono_secundario=
                                telefono_secundario or None,
                            telefono_trabajo=
                                telefono_trabajo or None,
                            email=
                                email or None,
                            direccion=
                                direccion or None,
                        )
                    )

            # =============================================
            # CLIENTE SIN DOCUMENTO
            # =============================================
            elif nombre_cliente:

                cliente_obj = (
                    Cliente.objects
                    .create(
                        tipo_documento="S",
                        identificacion=None,
                        nombre_completo=
                            nombre_cliente,
                        telefono=
                            telefono or None,
                        telefono_secundario=
                            telefono_secundario or None,
                        telefono_trabajo=
                            telefono_trabajo or None,
                        email=
                            email or None,
                        direccion=
                            direccion or None,
                    )
                )

            numero = (
                "COT-"
                f"{timezone.now().strftime('%y%m')}-"
                f"{uuid.uuid4().hex[:4].upper()}"
            )

            datos_cliente = (
                snapshot_cliente_cotizacion(
                    cliente_obj,
                    nombre_cliente,
                )
            )

            cotizacion = (
                Cotizacion.objects
                .create(
                    numero_cotizacion=
                        numero,
                    revision=1,
                    es_vigente=True,
                    sucursal=
                        sucursal_activa,
                    cliente=
                        cliente_obj,
                    placa=placa,
                    vehiculo=vehiculo or None,
                    anio_vehiculo=anio,
                    kilometraje=kilometraje,
                    observaciones=
                        observaciones or None,
                    estado="PENDIENTE",
                    **datos_cliente,
                )
            )

            cotizacion.calcular_total()

        messages.success(
            request,
            (
                f"Cotización {numero} "
                "creada correctamente."
            ),
        )

        return redirect(
            "detalle_cotizacion",
            pk=cotizacion.pk,
        )

    except ValidationError as e:

        messages.error(
            request,
            str(e),
        )

        return redirect(
            "lista_cotizaciones"
        )

    except Exception as e:

        print(
            traceback.format_exc()
        )

        messages.error(
            request,
            (
                "No se pudo crear la proforma: "
                f"{str(e)}"
            ),
        )

        return redirect(
            "lista_cotizaciones"
        )


# =========================================================
# NUEVA COTIZACIÓN DESDE OT
# =========================================================

@login_required
def nueva_cotizacion_desde_ot(
    request,
    pk_orden,
):

    orden = get_object_or_404(
        OrdenTrabajo.objects
        .select_related(
            "sucursal",
            "cliente",
            "configuracion_iva",
        ),
        pk=pk_orden,
    )

    # =====================================================
    # BUSCAR LA ÚLTIMA REVISIÓN DE ESTA OT
    # =====================================================

    cotizacion_existente = (
        Cotizacion.objects
        .filter(
            Q(orden=orden)
            |
            Q(orden_generada=orden)
        )
        .order_by(
            "-revision",
            "-id",
        )
        .first()
    )

    if cotizacion_existente:

        if (
            cotizacion_existente.estado
            == "PENDIENTE"
        ):
            messages.info(
                request,
                (
                    "Ya existe una proforma pendiente "
                    "para esta Orden de Trabajo."
                ),
            )

        elif (
            cotizacion_existente.estado
            == "APROBADA"
        ):
            messages.info(
                request,
                (
                    "La última proforma ya fue aprobada. "
                    "Si necesita cambiarla, cree una "
                    "nueva revisión desde la proforma."
                ),
            )

        return redirect(
            "detalle_cotizacion",
            pk=cotizacion_existente.pk,
        )

    # =====================================================
    # CREAR REV. 1
    # =====================================================

    with transaction.atomic():

        cotizacion = (
            Cotizacion.objects
            .create(
                numero_cotizacion=
                    f"PRO-{orden.numero_orden}",

                revision=1,

                es_vigente=True,

                sucursal=
                    orden.sucursal,

                orden=
                    orden,

                cliente=
                    orden.cliente,

                **snapshot_cliente_cotizacion(
                    orden.cliente,
                    orden.cliente_respaldo,
                ),

                placa=
                    orden.placa,

                vehiculo=
                    orden.vehiculo,

                anio_vehiculo=
                    orden.anio_vehiculo,

                kilometraje=
                    orden.kilometraje,

                estado=
                    "PENDIENTE",

                configuracion_iva=
                    orden.configuracion_iva,

                porcentaje_iva=
                    orden.porcentaje_iva,

                sumar_iva_al_total=
                    orden.sumar_iva_al_total,

                # Una proforma nueva empieza sin descuento.
                # Evita inconsistencias si todavía no tiene
                # REP/MOI/MOE y la OT usa descuento fijo.
                tipo_descuento=
                    "PORCENTAJE",

                descuento_ingresado=
                    Decimal("0.00"),
            )
        )

        cotizacion.calcular_total()

    messages.success(
        request,
        (
            "Proforma "
            f"{cotizacion.numero_cotizacion} "
            "Rev. 1 creada."
        ),
    )

    return redirect(
        "detalle_cotizacion",
        pk=cotizacion.pk,
    )


# =========================================================
# DETALLE COTIZACIÓN
# =========================================================

@login_required
def detalle_cotizacion(
    request,
    pk,
):

    cotizacion = get_object_or_404(
        (
            Cotizacion.objects
            .select_related(
                "sucursal",
                "cliente",
                "orden",
                "orden_generada",
                "configuracion_iva",
                "cotizacion_anterior",
            )
            .prefetch_related(
                "insumos_cotizados",
                "servicios_cotizados",
                (
                    "servicios_cotizados"
                    "__procedimientos_detalle"
                ),
            )
        ),
        pk=pk,
    )

    sucursal_activa = (
        obtener_sucursal_activa(
            request
        )
    )

    categorias = (
        Categoria.objects
        .all()
        .order_by(
            "nombre"
        )
    )

    puede_editar = (
        cotizacion.puede_editarse()
    )

    puede_crear_revision = (
        cotizacion.puede_crear_revision()
    )

    revision_anterior = (
        cotizacion.cotizacion_anterior
    )

    revision_siguiente = (
        Cotizacion.objects
        .filter(
            cotizacion_anterior=
                cotizacion
        )
        .order_by(
            "revision",
            "id",
        )
        .first()
    )

    # =====================================================
    # POST
    # =====================================================

    if request.method == "POST":

        if not puede_editar:

            messages.error(
                request,
                (
                    "No se puede modificar una "
                    "cotización aprobada o rechazada."
                ),
            )

            return redirect(
                "detalle_cotizacion",
                pk=cotizacion.pk,
            )

        try:

            return (
                guardar_detalle_cotizacion(
                    request,
                    pk,
                )
            )

        except ValidationError as e:

            print(
                traceback.format_exc()
            )

            messages.error(
                request,
                str(e),
            )

            return redirect(
                "detalle_cotizacion",
                pk=cotizacion.pk,
            )

        except Exception as e:

            print(
                traceback.format_exc()
            )

            messages.error(
                request,
                (
                    "Ocurrió un error al guardar "
                    f"la cotización: {str(e)}"
                ),
            )

            return redirect(
                "detalle_cotizacion",
                pk=cotizacion.pk,
            )

    # =====================================================
    # CÁLCULO ECONÓMICO
    # =====================================================

    cotizacion.calcular_total()

    subtotal = Decimal(
        cotizacion.subtotal_sin_iva
        or 0
    )

    descuento = Decimal(
        cotizacion.valor_descuento
        or 0
    )

    porcentaje_descuento = Decimal(
        cotizacion.descuento_porcentaje
        or 0
    )

    descuento_ingresado = Decimal(
        cotizacion.descuento_ingresado
        or 0
    )

    porcentaje_iva = Decimal(
        cotizacion.porcentaje_iva
        or 0
    )

    iva = Decimal(
        cotizacion.valor_iva
        or 0
    )

    total_final = Decimal(
        cotizacion.total_final
        or 0
    )

    return render(
        request,
        "detalle_cotizacion.html",
        {
            "cotizacion":
                cotizacion,

            "categorias_inventario":
                categorias,

            "sucursal_activa":
                sucursal_activa,

            "puede_editar":
                puede_editar,

            "puede_crear_revision":
                puede_crear_revision,

            "revision_anterior":
                revision_anterior,

            "revision_siguiente":
                revision_siguiente,

            "subtotal":
                subtotal,

            "descuento":
                descuento,

            "porcentaje_descuento":
                porcentaje_descuento,

            "descuento_ingresado":
                descuento_ingresado,

            "porcentaje_iva":
                porcentaje_iva,

            "iva":
                iva,

            "total_final":
                total_final,

            "tipo_descuento":
                cotizacion.tipo_descuento,

            "sumar_iva_al_total":
                cotizacion.sumar_iva_al_total,

            "porcentaje_iva_html":
                str(
                    porcentaje_iva
                ).replace(
                    ",",
                    ".",
                ),

            "descuento_porcentaje_html":
                str(
                    porcentaje_descuento
                ).replace(
                    ",",
                    ".",
                ),

            "descuento_ingresado_html":
                str(
                    descuento_ingresado
                ).replace(
                    ",",
                    ".",
                ),
        },
    )


# =========================================================
# UTILIDADES DE REVISIONES / SINCRONIZACIÓN
# =========================================================

def asegurar_linea_uuid(
    objeto,
):
    """
    Garantiza que una línea de cotización tenga UUID estable.

    Se usa update() deliberadamente para poder completar UUID
    de una revisión aprobada sin pasar por la validación que
    bloquea la edición de cotizaciones históricas.
    """

    if objeto.linea_uuid:
        return objeto.linea_uuid

    valor = uuid.uuid4()

    objeto.__class__.objects.filter(
        pk=objeto.pk
    ).update(
        linea_uuid=valor
    )

    objeto.linea_uuid = valor

    return valor


def obtener_ot_destino_cotizacion(
    cotizacion,
    crear_si_no_existe=False,
):
    """
    Devuelve (orden_destino, es_ot_nueva).

    Prioridad:
    1. OT original si la proforma nació desde una OT.
    2. OT generada si la proforma nació independiente.
    3. Crear una nueva OT únicamente cuando se solicita.
    """

    if cotizacion.orden_id:

        orden = (
            OrdenTrabajo.objects
            .select_for_update()
            .get(
                pk=cotizacion.orden_id
            )
        )

        return orden, False

    if cotizacion.orden_generada_id:

        orden = (
            OrdenTrabajo.objects
            .select_for_update()
            .get(
                pk=
                    cotizacion
                    .orden_generada_id
            )
        )

        return orden, False

    if not crear_si_no_existe:
        return None, False

    numero_ot = (
        "OT-"
        f"{timezone.now().strftime('%y%m')}-"
        f"{uuid.uuid4().hex[:4].upper()}"
    )

    expediente = (
        obtener_o_crear_expediente(
            cotizacion.cliente,
            cotizacion.cliente_respaldo,
            cotizacion.placa,
            cotizacion.vehiculo,
            cotizacion.anio_vehiculo,
        )
    )

    orden = (
        OrdenTrabajo.objects
        .create(
            numero_orden=
                numero_ot,

            sucursal=
                cotizacion.sucursal,

            expediente=
                expediente,

            cliente=
                cotizacion.cliente,

            cliente_respaldo=
                cotizacion
                .cliente_respaldo,

            placa=
                cotizacion.placa,

            vehiculo=
                cotizacion.vehiculo,

            anio_vehiculo=
                cotizacion
                .anio_vehiculo,

            kilometraje=
                cotizacion
                .kilometraje,

            observaciones_tecnicas=
                cotizacion
                .observaciones,

            estado=
                "ABIERTA",

            configuracion_iva=
                cotizacion
                .configuracion_iva,

            porcentaje_iva=
                cotizacion
                .porcentaje_iva,

            sumar_iva_al_total=
                cotizacion
                .sumar_iva_al_total,

            # Se crea temporalmente sin descuento.
            # El descuento real se aplica al final,
            # cuando todos los detalles ya existen.
            tipo_descuento=
                "PORCENTAJE",

            descuento_ingresado=
                Decimal("0.00"),
        )
    )

    cotizacion.orden_generada = orden

    return orden, True


def preparar_ot_para_sincronizacion(
    orden,
):
    """
    Desactiva temporalmente el descuento durante el merge.

    Esto evita que un descuento fijo válido para el total final
    falle durante estados intermedios de UPDATE/CREATE/DELETE.
    """

    orden.tipo_descuento = (
        "PORCENTAJE"
    )

    orden.descuento_ingresado = (
        Decimal("0.00")
    )

    OrdenTrabajo.objects.filter(
        pk=orden.pk
    ).update(
        tipo_descuento=
            "PORCENTAJE",
        descuento_ingresado=
            Decimal("0.00"),
    )


def aplicar_economia_cotizacion_a_ot(
    cotizacion,
    orden,
):

    orden.configuracion_iva = (
        cotizacion.configuracion_iva
    )

    orden.porcentaje_iva = (
        cotizacion.porcentaje_iva
    )

    orden.sumar_iva_al_total = (
        cotizacion.sumar_iva_al_total
    )

    orden.tipo_descuento = (
        cotizacion.tipo_descuento
    )

    orden.descuento_ingresado = (
        cotizacion.descuento_ingresado
    )

    orden.save(
        update_fields=[
            "configuracion_iva",
            "porcentaje_iva",
            "sumar_iva_al_total",
            "tipo_descuento",
            "descuento_ingresado",
        ]
    )

    orden.calcular_total()


def validar_trazabilidad_revision(
    cotizacion,
):
    """
    Impide crear una revisión si la revisión aprobada fue
    trasladada con el código antiguo y la OT no conserva UUID.

    Es preferible bloquear la revisión a duplicar información.
    """

    orden, _ = (
        obtener_ot_destino_cotizacion(
            cotizacion,
            crear_si_no_existe=False,
        )
    )

    if not orden:
        raise ValidationError(
            (
                "La cotización aprobada no tiene una "
                "Orden de Trabajo asociada. No se puede "
                "crear una revisión segura."
            )
        )

    # -----------------------------------------------------
    # REPUESTOS
    # -----------------------------------------------------

    insumos = list(
        CotizacionInsumoDetalle.objects
        .filter(
            cotizacion=cotizacion
        )
        .only(
            "id",
            "linea_uuid",
        )
    )

    uuids_insumos = {
        asegurar_linea_uuid(obj)
        for obj in insumos
    }

    if uuids_insumos:

        uuids_ot = set(
            OrdenInsumoDetalle.objects
            .filter(
                orden=orden,
                cotizacion_linea_uuid__in=
                    uuids_insumos,
            )
            .values_list(
                "cotizacion_linea_uuid",
                flat=True,
            )
        )

        if uuids_insumos - uuids_ot:
            raise ValidationError(
                (
                    "Esta cotización fue aprobada con una "
                    "versión anterior del módulo y los "
                    "repuestos de la OT no tienen la "
                    "trazabilidad necesaria. No se creó "
                    "la revisión para evitar duplicados."
                )
            )

    # -----------------------------------------------------
    # SERVICIOS
    # -----------------------------------------------------

    servicios = list(
        CotizacionServicioDetalle.objects
        .filter(
            cotizacion=cotizacion
        )
        .only(
            "id",
            "linea_uuid",
        )
    )

    uuids_servicios = {
        asegurar_linea_uuid(obj)
        for obj in servicios
    }

    if uuids_servicios:

        uuids_ot = set(
            OrdenServicioDetalle.objects
            .filter(
                orden=orden,
                cotizacion_linea_uuid__in=
                    uuids_servicios,
            )
            .values_list(
                "cotizacion_linea_uuid",
                flat=True,
            )
        )

        if uuids_servicios - uuids_ot:
            raise ValidationError(
                (
                    "Esta cotización fue aprobada con una "
                    "versión anterior del módulo y los "
                    "servicios de la OT no tienen la "
                    "trazabilidad necesaria. No se creó "
                    "la revisión para evitar duplicados."
                )
            )

    # -----------------------------------------------------
    # PROCEDIMIENTOS
    # -----------------------------------------------------

    procedimientos = list(
        CotizacionProcedimientoDetalle.objects
        .filter(
            servicio_cotizado__cotizacion=
                cotizacion
        )
        .only(
            "id",
            "linea_uuid",
        )
    )

    uuids_procedimientos = {
        asegurar_linea_uuid(obj)
        for obj in procedimientos
    }

    if uuids_procedimientos:

        uuids_ot = set(
            OrdenServicioProcedimientoDetalle
            .objects
            .filter(
                detalle_servicio__orden=orden,
                cotizacion_linea_uuid__in=
                    uuids_procedimientos,
            )
            .values_list(
                "cotizacion_linea_uuid",
                flat=True,
            )
        )

        if uuids_procedimientos - uuids_ot:
            raise ValidationError(
                (
                    "Esta cotización fue aprobada con una "
                    "versión anterior del módulo y los "
                    "procedimientos de la OT no tienen la "
                    "trazabilidad necesaria. No se creó "
                    "la revisión para evitar duplicados."
                )
            )


# =========================================================
# CREAR NUEVA REVISIÓN
# =========================================================

@login_required
def crear_revision_cotizacion(
    request,
    pk,
):

    if request.method != "POST":

        return redirect(
            "detalle_cotizacion",
            pk=pk,
        )

    try:

        with transaction.atomic():

            # =================================================
            # BLOQUEAR REVISIÓN ACTUAL
            # =================================================

            anterior = (
                Cotizacion.objects
                .select_for_update(
                    of=("self",)
                )
                .select_related(
                    "sucursal",
                    "cliente",
                    "orden",
                    "orden_generada",
                    "configuracion_iva",
                )
                .get(
                    pk=pk
                )
            )

            # =================================================
            # VALIDACIONES
            # =================================================

            if (
                anterior.estado
                != "APROBADA"
            ):
                raise ValidationError(
                    (
                        "Solo se puede crear una "
                        "nueva revisión desde una "
                        "cotización aprobada."
                    )
                )

            if not anterior.es_vigente:

                revision_vigente = (
                    Cotizacion.objects
                    .filter(
                        numero_cotizacion=
                            anterior
                            .numero_cotizacion,

                        es_vigente=True,
                    )
                    .order_by(
                        "-revision",
                        "-id",
                    )
                    .first()
                )

                if revision_vigente:

                    messages.warning(
                        request,
                        (
                            "Esta revisión ya no es "
                            "la vigente. Se abrió la "
                            "revisión actual."
                        ),
                    )

                    return redirect(
                        "detalle_cotizacion",
                        pk=
                            revision_vigente.pk,
                    )

                raise ValidationError(
                    (
                        "Esta revisión ya no es "
                        "la revisión vigente."
                    )
                )

            # Asegura que la OT tenga UUID de origen.
            # Evita que una Rev. 1 antigua produzca
            # duplicados al intentar crear Rev. 2.
            validar_trazabilidad_revision(
                anterior
            )

            nueva_revision_numero = (
                anterior.revision
                + 1
            )

            existente = (
                Cotizacion.objects
                .filter(
                    numero_cotizacion=
                        anterior
                        .numero_cotizacion,

                    revision=
                        nueva_revision_numero,
                )
                .first()
            )

            if existente:

                return redirect(
                    "detalle_cotizacion",
                    pk=existente.pk,
                )

            # =================================================
            # CABECERA NUEVA
            # =================================================

            nueva = (
                Cotizacion.objects
                .create(
                    numero_cotizacion=
                        anterior
                        .numero_cotizacion,

                    revision=
                        nueva_revision_numero,

                    cotizacion_anterior=
                        anterior,

                    es_vigente=
                        True,

                    sucursal=
                        anterior.sucursal,

                    orden=
                        anterior.orden,

                    orden_generada=
                        anterior
                        .orden_generada,

                    cliente=
                        anterior.cliente,

                    cliente_respaldo=
                        anterior
                        .cliente_respaldo,

                    identificacion_cliente_respaldo=
                        anterior
                        .identificacion_cliente_respaldo,

                    telefono_respaldo=
                        anterior
                        .telefono_respaldo,

                    telefono_secundario_respaldo=
                        anterior
                        .telefono_secundario_respaldo,

                    telefono_trabajo_respaldo=
                        anterior
                        .telefono_trabajo_respaldo,

                    email_respaldo=
                        anterior
                        .email_respaldo,

                    direccion_respaldo=
                        anterior
                        .direccion_respaldo,

                    placa=
                        anterior.placa,

                    vehiculo=
                        anterior.vehiculo,

                    anio_vehiculo=
                        anterior
                        .anio_vehiculo,

                    kilometraje=
                        anterior
                        .kilometraje,

                    estado=
                        "PENDIENTE",

                    validez_dias=
                        anterior
                        .validez_dias,

                    observaciones=
                        anterior
                        .observaciones,

                    configuracion_iva=
                        anterior
                        .configuracion_iva,

                    porcentaje_iva=
                        anterior
                        .porcentaje_iva,

                    sumar_iva_al_total=
                        anterior
                        .sumar_iva_al_total,

                    # Temporalmente sin descuento.
                    # Evita error durante la clonación
                    # cuando el descuento es VALOR_FIJO.
                    tipo_descuento=
                        "PORCENTAJE",

                    descuento_ingresado=
                        Decimal("0.00"),
                )
            )

            # =================================================
            # CLONAR REPUESTOS
            # =================================================

            insumos_anteriores = list(
                CotizacionInsumoDetalle
                .objects
                .select_for_update(
                    of=("self",)
                )
                .select_related(
                    "producto",
                    "categoria_referencia",
                )
                .filter(
                    cotizacion=
                        anterior
                )
                .order_by(
                    "orden_item",
                    "id",
                )
            )

            for item_anterior in (
                insumos_anteriores
            ):

                linea_uuid = (
                    asegurar_linea_uuid(
                        item_anterior
                    )
                )

                (
                    CotizacionInsumoDetalle
                    .objects
                    .create(
                        cotizacion=
                            nueva,

                        linea_uuid=
                            linea_uuid,

                        producto=
                            item_anterior
                            .producto,

                        descripcion_factura=
                            item_anterior
                            .descripcion_factura,

                        cantidad=
                            item_anterior
                            .cantidad,

                        precio_unitario=
                            item_anterior
                            .precio_unitario,

                        orden_item=
                            item_anterior
                            .orden_item,

                        marcado=
                            item_anterior
                            .marcado,

                        categoria_referencia=
                            item_anterior
                            .categoria_referencia,

                        codigo_empaque_referencia=
                            item_anterior
                            .codigo_empaque_referencia,

                        codigo_barras_referencia=
                            item_anterior
                            .codigo_barras_referencia,
                    )
                )

            # =================================================
            # CLONAR SERVICIOS + PROCEDIMIENTOS
            # =================================================

            servicios_anteriores = list(
                CotizacionServicioDetalle
                .objects
                .select_for_update(
                    of=("self",)
                )
                .select_related(
                    "servicio"
                )
                .prefetch_related(
                    "procedimientos_detalle"
                )
                .filter(
                    cotizacion=
                        anterior
                )
                .order_by(
                    "orden_item",
                    "id",
                )
            )

            for servicio_anterior in (
                servicios_anteriores
            ):

                linea_uuid = (
                    asegurar_linea_uuid(
                        servicio_anterior
                    )
                )

                servicio_nuevo = (
                    CotizacionServicioDetalle
                    .objects
                    .create(
                        cotizacion=
                            nueva,

                        linea_uuid=
                            linea_uuid,

                        servicio=
                            servicio_anterior
                            .servicio,

                        tipo_servicio=
                            servicio_anterior
                            .tipo_servicio,

                        descripcion_servicio=
                            servicio_anterior
                            .descripcion_servicio,

                        cantidad=
                            servicio_anterior
                            .cantidad,

                        precio_unitario=
                            servicio_anterior
                            .precio_unitario,

                        orden_item=
                            servicio_anterior
                            .orden_item,

                        variante_precio_aplicada=
                            servicio_anterior
                            .variante_precio_aplicada,
                    )
                )

                for procedimiento_anterior in (
                    servicio_anterior
                    .procedimientos_detalle
                    .all()
                ):

                    proc_uuid = (
                        asegurar_linea_uuid(
                            procedimiento_anterior
                        )
                    )

                    (
                        CotizacionProcedimientoDetalle
                        .objects
                        .create(
                            servicio_cotizado=
                                servicio_nuevo,

                            linea_uuid=
                                proc_uuid,

                            descripcion=
                                procedimiento_anterior
                                .descripcion,

                            orden_item=
                                procedimiento_anterior
                                .orden_item,
                        )
                    )

            # =================================================
            # RESTAURAR ECONOMÍA DE LA REVISIÓN
            # =================================================

            nueva.tipo_descuento = (
                anterior.tipo_descuento
            )

            nueva.descuento_ingresado = (
                anterior
                .descuento_ingresado
            )

            nueva.save(
                update_fields=[
                    "tipo_descuento",
                    "descuento_ingresado",
                ]
            )

            nueva.calcular_total()

            # =================================================
            # LA ANTERIOR PASA A HISTÓRICA
            # =================================================

            anterior.es_vigente = (
                False
            )

            anterior.save(
                update_fields=[
                    "es_vigente",
                ]
            )

        messages.success(
            request,
            (
                "Se creó "
                f"{nueva.numero_cotizacion} "
                f"Rev. {nueva.revision}. "
                "Ahora puede modificarla."
            ),
        )

        return redirect(
            "detalle_cotizacion",
            pk=nueva.pk,
        )

    except Cotizacion.DoesNotExist:

        messages.error(
            request,
            "La cotización no existe.",
        )

        return redirect(
            "dashboard"
        )

    except ValidationError as e:

        messages.error(
            request,
            str(e),
        )

        return redirect(
            "detalle_cotizacion",
            pk=pk,
        )

    except Exception as e:

        print(
            traceback.format_exc()
        )

        messages.error(
            request,
            (
                "No se pudo crear la "
                "nueva revisión: "
                f"{str(e)}"
            ),
        )

        return redirect(
            "detalle_cotizacion",
            pk=pk,
        )


# =========================================================
# SINCRONIZAR REPUESTOS CON OT
# =========================================================

def sincronizar_repuestos_cotizacion(
    cotizacion,
    orden_destino,
):

    insumos_actuales = list(
        CotizacionInsumoDetalle
        .objects
        .select_for_update(
            of=("self",)
        )
        .select_related(
            "producto",
            "categoria_referencia",
        )
        .filter(
            cotizacion=
                cotizacion
        )
        .order_by(
            "orden_item",
            "id",
        )
    )

    uuids_actuales = set()

    for item_cotizado in (
        insumos_actuales
    ):

        linea_uuid = (
            asegurar_linea_uuid(
                item_cotizado
            )
        )

        uuids_actuales.add(
            linea_uuid
        )

        coincidencias = list(
            OrdenInsumoDetalle.objects
            .select_for_update()
            .filter(
                orden=
                    orden_destino,

                cotizacion_linea_uuid=
                    linea_uuid,
            )
            .order_by(
                "id"
            )[:2]
        )

        if len(coincidencias) > 1:
            raise ValidationError(
                (
                    "Se encontraron repuestos duplicados "
                    "en la OT para una misma línea de "
                    "cotización. Revise la trazabilidad."
                )
            )

        detalle_ot = (
            coincidencias[0]
            if coincidencias
            else None
        )

        if detalle_ot:

            detalle_ot.producto = (
                item_cotizado.producto
            )

            detalle_ot.descripcion_factura = (
                item_cotizado
                .descripcion_factura
            )

            detalle_ot.cantidad = (
                item_cotizado.cantidad
            )

            detalle_ot.precio_unitario = (
                item_cotizado
                .precio_unitario
            )

            detalle_ot.categoria_referencia = (
                item_cotizado
                .categoria_referencia
            )

            detalle_ot.codigo_empaque_referencia = (
                item_cotizado
                .codigo_empaque_referencia
            )

            detalle_ot.codigo_barras_referencia = (
                item_cotizado
                .codigo_barras_referencia
            )

            detalle_ot.orden_item = (
                item_cotizado.orden_item
            )

            detalle_ot.marcado = (
                item_cotizado.marcado
            )

            detalle_ot.cotizacion_origen = (
                cotizacion
            )

            detalle_ot.cotizacion_linea_uuid = (
                linea_uuid
            )

            detalle_ot.save()

        else:

            (
                OrdenInsumoDetalle
                .objects
                .create(
                    orden=
                        orden_destino,

                    producto=
                        item_cotizado.producto,

                    descripcion_factura=
                        item_cotizado
                        .descripcion_factura,

                    cantidad=
                        item_cotizado.cantidad,

                    precio_unitario=
                        item_cotizado
                        .precio_unitario,

                    categoria_referencia=
                        item_cotizado
                        .categoria_referencia,

                    codigo_empaque_referencia=
                        item_cotizado
                        .codigo_empaque_referencia,

                    codigo_barras_referencia=
                        item_cotizado
                        .codigo_barras_referencia,

                    orden_item=
                        item_cotizado.orden_item,

                    marcado=
                        item_cotizado.marcado,

                    cotizacion_origen=
                        cotizacion,

                    cotizacion_linea_uuid=
                        linea_uuid,
                )
            )

    # =====================================================
    # ELIMINADOS RESPECTO A LA REVISIÓN ANTERIOR
    # =====================================================

    if cotizacion.cotizacion_anterior_id:

        uuids_anteriores = set(
            CotizacionInsumoDetalle
            .objects
            .filter(
                cotizacion=
                    cotizacion
                    .cotizacion_anterior,

                linea_uuid__isnull=False,
            )
            .values_list(
                "linea_uuid",
                flat=True,
            )
        )

        uuids_eliminados = (
            uuids_anteriores
            -
            uuids_actuales
        )

        if uuids_eliminados:

            para_eliminar = list(
                OrdenInsumoDetalle
                .objects
                .select_for_update()
                .filter(
                    orden=
                        orden_destino,

                    cotizacion_linea_uuid__in=
                        uuids_eliminados,
                )
            )

            for detalle_ot in (
                para_eliminar
            ):
                detalle_ot.delete()


# =========================================================
# SINCRONIZAR SERVICIOS / PROCEDIMIENTOS CON OT
# =========================================================

def sincronizar_servicios_cotizacion(
    cotizacion,
    orden_destino,
):

    servicios_actuales = list(
        CotizacionServicioDetalle
        .objects
        .select_for_update(
            of=("self",)
        )
        .select_related(
            "servicio"
        )
        .prefetch_related(
            "procedimientos_detalle"
        )
        .filter(
            cotizacion=
                cotizacion
        )
        .order_by(
            "orden_item",
            "id",
        )
    )

    uuids_servicios_actuales = set()

    for servicio_cotizado in (
        servicios_actuales
    ):

        servicio_uuid = (
            asegurar_linea_uuid(
                servicio_cotizado
            )
        )

        uuids_servicios_actuales.add(
            servicio_uuid
        )

        coincidencias = list(
            OrdenServicioDetalle.objects
            .select_for_update()
            .filter(
                orden=
                    orden_destino,

                cotizacion_linea_uuid=
                    servicio_uuid,
            )
            .order_by(
                "id"
            )[:2]
        )

        if len(coincidencias) > 1:
            raise ValidationError(
                (
                    "Se encontraron servicios duplicados "
                    "en la OT para una misma línea de "
                    "cotización. Revise la trazabilidad."
                )
            )

        servicio_ot = (
            coincidencias[0]
            if coincidencias
            else None
        )

        if servicio_ot:

            servicio_ot.servicio = (
                servicio_cotizado
                .servicio
            )

            servicio_ot.tipo_servicio = (
                servicio_cotizado
                .tipo_servicio
            )

            servicio_ot.descripcion_servicio = (
                servicio_cotizado
                .descripcion_servicio
            )

            servicio_ot.cantidad = (
                servicio_cotizado
                .cantidad
            )

            servicio_ot.precio_unitario = (
                servicio_cotizado
                .precio_unitario
            )

            servicio_ot.orden_item = (
                servicio_cotizado
                .orden_item
            )

            servicio_ot.variante_precio_aplicada = (
                servicio_cotizado
                .variante_precio_aplicada
            )

            servicio_ot.cotizacion_origen = (
                cotizacion
            )

            servicio_ot.cotizacion_linea_uuid = (
                servicio_uuid
            )

            servicio_ot.save()

        else:

            servicio_ot = (
                OrdenServicioDetalle
                .objects
                .create(
                    orden=
                        orden_destino,

                    servicio=
                        servicio_cotizado
                        .servicio,

                    tipo_servicio=
                        servicio_cotizado
                        .tipo_servicio,

                    descripcion_servicio=
                        servicio_cotizado
                        .descripcion_servicio,

                    cantidad=
                        servicio_cotizado
                        .cantidad,

                    precio_unitario=
                        servicio_cotizado
                        .precio_unitario,

                    orden_item=
                        servicio_cotizado
                        .orden_item,

                    variante_precio_aplicada=
                        servicio_cotizado
                        .variante_precio_aplicada,

                    cotizacion_origen=
                        cotizacion,

                    cotizacion_linea_uuid=
                        servicio_uuid,
                )
            )

        # =================================================
        # PROCEDIMIENTOS DEL SERVICIO
        # =================================================

        procedimientos_actuales = list(
            servicio_cotizado
            .procedimientos_detalle
            .all()
        )

        uuids_proc_actuales = set()

        for procedimiento in (
            procedimientos_actuales
        ):

            proc_uuid = (
                asegurar_linea_uuid(
                    procedimiento
                )
            )

            uuids_proc_actuales.add(
                proc_uuid
            )

            coincidencias_proc = list(
                OrdenServicioProcedimientoDetalle
                .objects
                .select_for_update()
                .filter(
                    detalle_servicio=
                        servicio_ot,

                    cotizacion_linea_uuid=
                        proc_uuid,
                )
                .order_by(
                    "id"
                )[:2]
            )

            if len(coincidencias_proc) > 1:
                raise ValidationError(
                    (
                        "Se encontraron procedimientos "
                        "duplicados en la OT para una misma "
                        "línea de cotización."
                    )
                )

            procedimiento_ot = (
                coincidencias_proc[0]
                if coincidencias_proc
                else None
            )

            if procedimiento_ot:

                procedimiento_ot.descripcion = (
                    procedimiento.descripcion
                )

                procedimiento_ot.orden_item = (
                    procedimiento.orden_item
                )

                procedimiento_ot.cotizacion_origen = (
                    cotizacion
                )

                procedimiento_ot.cotizacion_linea_uuid = (
                    proc_uuid
                )

                procedimiento_ot.save()

            else:

                (
                    OrdenServicioProcedimientoDetalle
                    .objects
                    .create(
                        detalle_servicio=
                            servicio_ot,

                        descripcion=
                            procedimiento
                            .descripcion,

                        orden_item=
                            procedimiento
                            .orden_item,

                        cotizacion_origen=
                            cotizacion,

                        cotizacion_linea_uuid=
                            proc_uuid,
                    )
                )

        # =================================================
        # PROCEDIMIENTOS ELIMINADOS EN ESTA REVISIÓN
        # =================================================

        if cotizacion.cotizacion_anterior_id:

            servicio_anterior = (
                CotizacionServicioDetalle
                .objects
                .filter(
                    cotizacion=
                        cotizacion
                        .cotizacion_anterior,

                    linea_uuid=
                        servicio_uuid,
                )
                .first()
            )

            if servicio_anterior:

                uuids_proc_anteriores = set(
                    CotizacionProcedimientoDetalle
                    .objects
                    .filter(
                        servicio_cotizado=
                            servicio_anterior,

                        linea_uuid__isnull=False,
                    )
                    .values_list(
                        "linea_uuid",
                        flat=True,
                    )
                )

                proc_eliminados = (
                    uuids_proc_anteriores
                    -
                    uuids_proc_actuales
                )

                if proc_eliminados:

                    proc_ot_eliminar = list(
                        OrdenServicioProcedimientoDetalle
                        .objects
                        .select_for_update()
                        .filter(
                            detalle_servicio=
                                servicio_ot,

                            cotizacion_linea_uuid__in=
                                proc_eliminados,
                        )
                    )

                    for proc_ot in (
                        proc_ot_eliminar
                    ):
                        proc_ot.delete()

    # =====================================================
    # SERVICIOS ELIMINADOS EN ESTA REVISIÓN
    # =====================================================

    if cotizacion.cotizacion_anterior_id:

        uuids_servicios_anteriores = set(
            CotizacionServicioDetalle
            .objects
            .filter(
                cotizacion=
                    cotizacion
                    .cotizacion_anterior,

                linea_uuid__isnull=False,
            )
            .values_list(
                "linea_uuid",
                flat=True,
            )
        )

        servicios_eliminados = (
            uuids_servicios_anteriores
            -
            uuids_servicios_actuales
        )

        if servicios_eliminados:

            servicios_ot_eliminar = list(
                OrdenServicioDetalle
                .objects
                .select_for_update()
                .filter(
                    orden=
                        orden_destino,

                    cotizacion_linea_uuid__in=
                        servicios_eliminados,
                )
            )

            for servicio_ot in (
                servicios_ot_eliminar
            ):
                servicio_ot.delete()


# =========================================================
# APROBAR / SINCRONIZAR COTIZACIÓN
# =========================================================

@login_required
def aprobar_cotizacion(
    request,
    pk,
):

    if request.method != "POST":

        return redirect(
            "detalle_cotizacion",
            pk=pk,
        )

    try:

        with transaction.atomic():

            # =================================================
            # BLOQUEAR COTIZACIÓN
            # =================================================

            cotizacion = (
                Cotizacion.objects
                .select_for_update(
                    of=("self",)
                )
                .select_related(
                    "sucursal",
                    "cliente",
                    "orden",
                    "orden_generada",
                    "configuracion_iva",
                    "cotizacion_anterior",
                )
                .get(
                    pk=pk
                )
            )

            if (
                cotizacion.estado
                != "PENDIENTE"
            ):
                raise ValidationError(
                    (
                        "Esta cotización ya "
                        "no está pendiente."
                    )
                )

            if not cotizacion.es_vigente:
                raise ValidationError(
                    (
                        "Esta revisión ya no "
                        "es la revisión vigente."
                    )
                )

            # =================================================
            # VALIDAR ECONOMÍA DE COTIZACIÓN
            # =================================================

            cotizacion.calcular_total()

            # =================================================
            # OBTENER / CREAR OT DESTINO
            # =================================================

            orden_destino, es_ot_nueva = (
                obtener_ot_destino_cotizacion(
                    cotizacion,
                    crear_si_no_existe=True,
                )
            )

            if (
                not orden_destino
                .puede_editarse()
            ):
                raise ValidationError(
                    (
                        "La Orden de Trabajo está "
                        "cerrada o anulada y no puede "
                        "recibir esta revisión."
                    )
                )

            # El merge puede pasar por subtotales
            # intermedios. Dejamos temporalmente
            # el descuento en cero para evitar que
            # un descuento fijo válido al final falle.
            preparar_ot_para_sincronizacion(
                orden_destino
            )

            # =================================================
            # SINCRONIZAR REP / MOI / MOE
            # =================================================

            sincronizar_repuestos_cotizacion(
                cotizacion,
                orden_destino,
            )

            sincronizar_servicios_cotizacion(
                cotizacion,
                orden_destino,
            )

            # =================================================
            # APLICAR ECONOMÍA FINAL
            # =================================================

            aplicar_economia_cotizacion_a_ot(
                cotizacion,
                orden_destino,
            )

            # =================================================
            # APROBAR REVISIÓN
            # =================================================

            cotizacion.estado = (
                "APROBADA"
            )

            cotizacion.fecha_aprobacion = (
                timezone.now()
            )

            cotizacion.version += 1

            campos_update = [
                "estado",
                "fecha_aprobacion",
                "version",
            ]

            if es_ot_nueva:
                campos_update.append(
                    "orden_generada"
                )

            cotizacion.save(
                update_fields=
                    campos_update
            )

        # =====================================================
        # MENSAJE FINAL
        # =====================================================

        if es_ot_nueva:

            mensaje = (
                "Cotización aprobada. "
                "Se creó la Orden de Trabajo "
                f"{orden_destino.numero_orden}."
            )

        elif cotizacion.revision > 1:

            mensaje = (
                f"Rev. {cotizacion.revision} "
                "aprobada y sincronizada "
                "con la Orden de Trabajo."
            )

        else:

            mensaje = (
                "Cotización aprobada y "
                "trasladada correctamente "
                "a la Orden de Trabajo."
            )

        messages.success(
            request,
            mensaje,
        )

        return redirect(
            "detalle_orden",
            pk=orden_destino.pk,
        )

    except Cotizacion.DoesNotExist:

        messages.error(
            request,
            (
                "La cotización solicitada "
                "no existe."
            ),
        )

        return redirect(
            "dashboard"
        )

    except ValidationError as e:

        print(
            traceback.format_exc()
        )

        messages.error(
            request,
            str(e),
        )

        return redirect(
            "detalle_cotizacion",
            pk=pk,
        )

    except Exception as e:

        print(
            traceback.format_exc()
        )

        messages.error(
            request,
            (
                "Error al aprobar la "
                f"cotización: {str(e)}"
            ),
        )

        return redirect(
            "detalle_cotizacion",
            pk=pk,
        )