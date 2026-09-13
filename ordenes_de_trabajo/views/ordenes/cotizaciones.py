import uuid
import traceback

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
    obtener_sucursal_activa,
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
            (
                "Debe tener una "
                "sucursal activa."
            ),
        )

        return redirect(
            "dashboard"
        )

    if request.method == "POST":

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

        anio = (
            request.POST.get(
                "anio_vehiculo",
                "",
            )
            .strip()
        )

        identificacion = (
            request.POST.get(
                "identificacion",
                "",
            )
            .strip()
        )

        nombre_cliente = (
            request.POST.get(
                "nombre_cliente",
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
                "crear_cotizacion"
            )

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

            if not cliente_obj:

                cliente_obj = (
                    Cliente.objects
                    .create(
                        identificacion=
                            identificacion,

                        nombre_completo=(
                            nombre_cliente
                            or
                            "CONSUMIDOR FINAL"
                        ),
                    )
                )

        with transaction.atomic():

            numero = (
                "COT-"
                f"{timezone.now().strftime('%y%m')}-"
                f"{uuid.uuid4().hex[:4].upper()}"
            )

            cotizacion = (
                Cotizacion.objects
                .create(
                    numero_cotizacion=
                        numero,

                    sucursal=
                        sucursal_activa,

                    cliente=
                        cliente_obj,

                    cliente_respaldo=(
                        nombre_cliente
                        or None
                    ),

                    placa=
                        placa,

                    vehiculo=
                        vehiculo,

                    anio_vehiculo=(
                        int(anio)
                        if anio.isdigit()
                        else None
                    ),

                    observaciones=
                        observaciones,

                    estado=
                        "PENDIENTE",
                )
            )

            # Obtiene el IVA vigente desde
            # el comienzo de la cotización.
            cotizacion.calcular_total()

        messages.success(
            request,
            (
                f"Cotización {numero} "
                "creada."
            ),
        )

        return redirect(
            "detalle_cotizacion",
            pk=cotizacion.pk,
        )

    return render(
        request,
        "crear_cotizacion.html",
        {
            "sucursal_activa":
                sucursal_activa,
        },
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

    cotizacion, created = (
        Cotizacion.objects
        .get_or_create(
            orden=orden,
            defaults={
                "numero_cotizacion":
                    f"PRO-{orden.numero_orden}",

                "sucursal":
                    orden.sucursal,

                "cliente":
                    orden.cliente,

                "cliente_respaldo":
                    orden.cliente_respaldo,

                "placa":
                    orden.placa,

                "vehiculo":
                    orden.vehiculo,

                "anio_vehiculo":
                    orden.anio_vehiculo,

                "estado":
                    "PENDIENTE",

                "configuracion_iva":
                    orden.configuracion_iva,

                "porcentaje_iva":
                    orden.porcentaje_iva,

                "sumar_iva_al_total":
                    orden.sumar_iva_al_total,
            },
        )
    )

    if created:

        cotizacion.calcular_total()

        messages.success(
            request,
            (
                "Proforma generada para "
                f"{orden.numero_orden}."
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
# APROBAR COTIZACIÓN
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
                .select_for_update()
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

            # Hay que comprobar el estado
            # DESPUÉS de adquirir el bloqueo.
            if (
                cotizacion.estado
                != "PENDIENTE"
            ):

                messages.error(
                    request,
                    (
                        "Esta cotización ya "
                        "no está pendiente."
                    ),
                )

                return redirect(
                    "detalle_cotizacion",
                    pk=pk,
                )

            # Fuerza validación económica final
            # antes de trasladar información.
            cotizacion.calcular_total()

            # =================================================
            # DESTINO: OT YA VINCULADA
            # =================================================

            es_ot_nueva = False

            if cotizacion.orden_id:

                orden_destino = (
                    OrdenTrabajo.objects
                    .select_for_update()
                    .get(
                        pk=
                            cotizacion.orden_id
                    )
                )

                if (
                    not orden_destino
                    .puede_editarse()
                ):
                    raise ValidationError(
                        (
                            "La Orden de Trabajo "
                            "vinculada está cerrada "
                            "o anulada y no puede "
                            "recibir la cotización."
                        )
                    )

            # =================================================
            # DESTINO: CREAR OT
            # =================================================

            else:

                if (
                    cotizacion
                    .orden_generada_id
                ):
                    raise ValidationError(
                        (
                            "Esta cotización ya tiene "
                            "una Orden de Trabajo "
                            "generada. Revise su estado "
                            "antes de volver a aprobarla."
                        )
                    )

                numero_ot = (
                    "OT-"
                    f"{timezone.now().strftime('%y%m')}-"
                    f"{uuid.uuid4().hex[:4].upper()}"
                )

                # IMPORTANTE:
                #
                # La OT se crea inicialmente SIN descuento.
                #
                # Si copiáramos un descuento fijo antes
                # de insertar todos los REP/MOI/MOE,
                # el primer detalle podría tener subtotal
                # menor al descuento y calcular_total()
                # rechazaría la operación.
                orden_destino = (
                    OrdenTrabajo.objects
                    .create(
                        numero_orden=
                            numero_ot,

                        sucursal=
                            cotizacion.sucursal,

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

                        tipo_descuento=
                            "PORCENTAJE",

                        descuento_ingresado=
                            Decimal("0.00"),
                    )
                )

                cotizacion.orden_generada = (
                    orden_destino
                )

                es_ot_nueva = True

            # =================================================
            # REPUESTOS
            # =================================================

            insumos = list(
                CotizacionInsumoDetalle
                .objects
                .select_for_update()
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

            for item_cotizado in insumos:

                OrdenInsumoDetalle.objects.create(
                    orden=
                        orden_destino,

                    producto=
                        item_cotizado
                        .producto,

                    descripcion_factura=
                        item_cotizado
                        .descripcion_factura,

                    cantidad=
                        item_cotizado
                        .cantidad,

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
                        item_cotizado
                        .orden_item,

                    marcado=
                        item_cotizado
                        .marcado,
                )

            # =================================================
            # SERVICIOS
            # =================================================

            servicios = list(
                CotizacionServicioDetalle
                .objects
                .select_for_update()
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

            for serv in servicios:

                nuevo_servicio_ot = (
                    OrdenServicioDetalle
                    .objects
                    .create(
                        orden=
                            orden_destino,

                        servicio=
                            serv.servicio,

                        tipo_servicio=
                            serv.tipo_servicio,

                        descripcion_servicio=
                            serv
                            .descripcion_servicio,

                        cantidad=
                            serv.cantidad,

                        precio_unitario=
                            serv.precio_unitario,

                        orden_item=
                            serv.orden_item,

                        variante_precio_aplicada=
                            serv
                            .variante_precio_aplicada,
                    )
                )

                for proc in (
                    serv
                    .procedimientos_detalle
                    .all()
                ):

                    (
                        OrdenServicioProcedimientoDetalle
                        .objects
                        .create(
                            detalle_servicio=
                                nuevo_servicio_ot,

                            descripcion=
                                proc.descripcion,

                            orden_item=
                                proc.orden_item,
                        )
                    )

            # =================================================
            # ECONOMÍA DE LA NUEVA OT
            # =================================================

            if es_ot_nueva:

                orden_destino.configuracion_iva = (
                    cotizacion
                    .configuracion_iva
                )

                orden_destino.porcentaje_iva = (
                    cotizacion
                    .porcentaje_iva
                )

                orden_destino.sumar_iva_al_total = (
                    cotizacion
                    .sumar_iva_al_total
                )

                orden_destino.tipo_descuento = (
                    cotizacion
                    .tipo_descuento
                )

                orden_destino.descuento_ingresado = (
                    cotizacion
                    .descuento_ingresado
                )

                orden_destino.save(
                    update_fields=[
                        "configuracion_iva",
                        "porcentaje_iva",
                        "sumar_iva_al_total",
                        "tipo_descuento",
                        "descuento_ingresado",
                    ]
                )

            # =================================================
            # TOTAL FINAL OT
            # =================================================

            orden_destino.calcular_total()

            # =================================================
            # CERRAR COTIZACIÓN
            # =================================================

            cotizacion.estado = (
                "APROBADA"
            )

            cotizacion.version += 1

            campos_update = [
                "estado",
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
        # FUERA DE LA TRANSACCIÓN
        # =====================================================

        if es_ot_nueva:

            mensaje = (
                "Cotización aprobada. "
                "Se creó la Orden de Trabajo "
                f"{orden_destino.numero_orden}."
            )

        else:

            mensaje = (
                "Cotización aprobada y "
                "trasladada a la Orden de "
                "Trabajo vinculada."
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