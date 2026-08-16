"""
movimientos.py

Aquí se manejan entradas, salidas y ajustes manuales.

Debe permitir:

- listar movimientos
- crear entrada manual
- crear salida manual
- crear ajuste
- ver historial por producto
- ver historial por sucursal

Modelo principal:

MovimientoStock

Importante:
Los movimientos no se editan ni se eliminan.
"""

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db.models import Q, Sum
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)

from accesos.permissions import permiso_requerido

from ordenes_de_trabajo.models import Sucursal
from ordenes_de_trabajo.views.utils import (
    obtener_sucursal_activa,
    usuario_puede_cambiar_sucursal,
)

from ..models import (
    CodigoProducto,
    MovimientoStock,
)


# =========================================================
# UTILIDADES
# =========================================================

def _decimal_positivo(valor):
    """
    Convierte un valor a Decimal y exige que sea mayor que 0.
    """

    texto = str(valor or "").strip().replace(",", ".")

    if not texto:
        raise ValueError("La cantidad es obligatoria.")

    try:
        numero = Decimal(texto)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("La cantidad ingresada no es válida.")

    if numero <= 0:
        raise ValueError("La cantidad debe ser mayor que 0.")

    return numero


def _decimal_opcional_no_negativo(valor):
    """
    Convierte un valor opcional a Decimal.
    Si viene vacío devuelve None.
    """

    texto = str(valor or "").strip().replace(",", ".")

    if not texto:
        return None

    try:
        numero = Decimal(texto)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("El precio unitario no es válido.")

    if numero < 0:
        raise ValueError(
            "El precio unitario no puede ser negativo."
        )

    return numero


def _sucursales_disponibles(request):
    """
    Devuelve las sucursales que pueden mostrarse al usuario.

    - Con permiso global: todas las sucursales activas.
    - Sin permiso global: únicamente su sucursal activa.
    """

    if usuario_puede_cambiar_sucursal(request):
        return (
            Sucursal.objects
            .filter(activa=True)
            .order_by("nombre")
        )

    sucursal_activa = obtener_sucursal_activa(request)

    if not sucursal_activa:
        return Sucursal.objects.none()

    return Sucursal.objects.filter(
        pk=sucursal_activa.pk,
        activa=True,
    )


def _resolver_sucursal_escritura(
    request,
    sucursal_id=None,
):
    """
    Resuelve en qué sucursal se registrará el movimiento.

    - Usuario con permiso global:
      puede elegir cualquier sucursal activa.
    - Usuario sin permiso global:
      queda forzado a su sucursal activa.
    """

    if usuario_puede_cambiar_sucursal(request):
        sucursal_id = str(
            sucursal_id or ""
        ).strip()

        if not sucursal_id.isdigit():
            return None

        return (
            Sucursal.objects
            .filter(
                pk=int(sucursal_id),
                activa=True,
            )
            .first()
        )

    return obtener_sucursal_activa(request)


def _limitar_movimientos_por_sucursal(
    request,
    queryset,
):
    """
    Aplica el alcance de sucursal al queryset de movimientos.

    Un usuario sin permiso global nunca puede consultar
    movimientos de otra sucursal.
    """

    if usuario_puede_cambiar_sucursal(request):
        return queryset

    sucursal_activa = obtener_sucursal_activa(request)

    if not sucursal_activa:
        return queryset.none()

    return queryset.filter(
        sucursal=sucursal_activa
    )


# =========================================================
# LISTADO
# =========================================================

@permiso_requerido(
    "inventario.view_movimientostock"
)
def movimiento_lista(request):
    LIMITE_RESULTADOS = 100

    sucursal_activa = obtener_sucursal_activa(
        request
    )

    puede_cambiar_sucursal = (
        usuario_puede_cambiar_sucursal(
            request
        )
    )

    movimientos = (
        MovimientoStock.objects
        .select_related(
            "sucursal",
            "codigo_producto",
            "codigo_producto__producto",
            "codigo_producto__producto__categoria",
            "codigo_producto__marca",
        )
        .order_by("-fecha")
    )

    # Seguridad base por sucursal.
    movimientos = _limitar_movimientos_por_sucursal(
        request,
        movimientos,
    )

    q = (
        request.GET
        .get("q", "")
        .strip()
    )

    tipo = (
        request.GET
        .get("tipo", "")
        .strip()
    )

    sucursal_id = (
        request.GET
        .get("sucursal", "")
        .strip()
    )

    # =====================================================
    # FILTRO DE SUCURSAL
    # =====================================================

    if puede_cambiar_sucursal:
        if sucursal_id.isdigit():
            sucursal_valida = (
                Sucursal.objects
                .filter(
                    pk=int(sucursal_id),
                    activa=True,
                )
                .exists()
            )

            if sucursal_valida:
                movimientos = movimientos.filter(
                    sucursal_id=int(sucursal_id)
                )
            else:
                sucursal_id = ""

        elif sucursal_id:
            # Ignorar parámetros manipulados o inválidos.
            sucursal_id = ""

    else:
        # El usuario sin permiso no puede elegir sucursal
        # mediante parámetros GET.
        sucursal_id = (
            str(sucursal_activa.id)
            if sucursal_activa
            else ""
        )

    # =====================================================
    # BÚSQUEDA
    # =====================================================

    if q:
        movimientos = movimientos.filter(
            Q(
                codigo_producto__codigo__icontains=q
            )
            |
            Q(
                codigo_producto__codigo_barras__icontains=q
            )
            |
            Q(
                codigo_producto__producto__nombre_base__icontains=q
            )
            |
            Q(
                codigo_producto__marca__nombre__icontains=q
            )
            |
            Q(
                referencia__icontains=q
            )
        )

    # =====================================================
    # TIPO
    # =====================================================

    tipos_validos = {
        valor
        for valor, _label
        in MovimientoStock.TIPO_MOVIMIENTO_CHOICES
    }

    if tipo in tipos_validos:
        movimientos = movimientos.filter(
            tipo_movimiento=tipo
        )
    elif tipo:
        tipo = ""

    sucursales = _sucursales_disponibles(
        request
    )

    return render(
        request,
        "inventario/movimientos/lista.html",
        {
            "movimientos": (
                movimientos[:LIMITE_RESULTADOS]
            ),
            "sucursales": sucursales,
            "sucursal_activa": sucursal_activa,
            "puede_cambiar_sucursal": (
                puede_cambiar_sucursal
            ),
            "tipo": tipo,
            "q": q,
            "sucursal_id": sucursal_id,
            "tipos": (
                MovimientoStock.TIPO_MOVIMIENTO_CHOICES
            ),
            "limite_resultados": (
                LIMITE_RESULTADOS
            ),
        },
    )


# =========================================================
# CREAR MOVIMIENTO
# =========================================================

@permiso_requerido(
    "inventario.add_movimientostock"
)
def movimiento_crear(request):
    sucursal_activa = obtener_sucursal_activa(
        request
    )

    puede_cambiar_sucursal = (
        usuario_puede_cambiar_sucursal(
            request
        )
    )

    sucursales = _sucursales_disponibles(
        request
    )

    if request.method == "POST":
        try:
            codigo_id = (
                request.POST
                .get("codigo_producto", "")
                .strip()
            )

            if not codigo_id.isdigit():
                raise ValueError(
                    "Debes seleccionar un producto válido."
                )

            codigo = get_object_or_404(
                CodigoProducto,
                pk=int(codigo_id),
            )

            sucursal = _resolver_sucursal_escritura(
                request,
                request.POST.get("sucursal"),
            )

            if not sucursal:
                raise ValueError(
                    "Debes seleccionar una sucursal válida."
                )

            tipo_movimiento = (
                request.POST
                .get("tipo_movimiento", "")
                .strip()
            )

            tipos_validos = {
                valor
                for valor, _label
                in MovimientoStock.TIPO_MOVIMIENTO_CHOICES
            }

            if tipo_movimiento not in tipos_validos:
                raise ValueError(
                    "El tipo de movimiento no es válido."
                )

            cantidad = _decimal_positivo(
                request.POST.get("cantidad")
            )

            precio_unitario = (
                _decimal_opcional_no_negativo(
                    request.POST.get(
                        "precio_unitario"
                    )
                )
            )

            referencia = (
                request.POST
                .get("referencia", "")
                .strip()
                or None
            )

            observacion = (
                request.POST
                .get("observacion", "")
                .strip()
                or None
            )

            movimiento = (
                MovimientoStock.objects
                .create(
                    codigo_producto=codigo,
                    sucursal=sucursal,
                    tipo_movimiento=(
                        tipo_movimiento
                    ),
                    cantidad=cantidad,
                    precio_unitario=(
                        precio_unitario
                    ),
                    referencia=referencia,
                    observacion=observacion,
                )
            )

            messages.success(
                request,
                "Movimiento registrado correctamente.",
            )

            return redirect(
                "inventario_movimiento_detalle",
                movimiento.id,
            )

        except Exception as e:
            messages.error(
                request,
                str(e),
            )

    return render(
        request,
        "inventario/movimientos/form.html",
        {
            "sucursales": sucursales,
            "sucursal_activa": sucursal_activa,
            "puede_cambiar_sucursal": (
                puede_cambiar_sucursal
            ),
            "tipos": (
                MovimientoStock.TIPO_MOVIMIENTO_CHOICES
            ),
        },
    )


# =========================================================
# DETALLE
# =========================================================

@permiso_requerido(
    "inventario.view_movimientostock"
)
def movimiento_detalle(
    request,
    movimiento_id,
):
    movimientos = (
        MovimientoStock.objects
        .select_related(
            "sucursal",
            "codigo_producto",
            "codigo_producto__producto",
            "codigo_producto__marca",
        )
    )

    movimientos = _limitar_movimientos_por_sucursal(
        request,
        movimientos,
    )

    movimiento = get_object_or_404(
        movimientos,
        id=movimiento_id,
    )

    return render(
        request,
        "inventario/movimientos/detalle.html",
        {
            "movimiento": movimiento,
        },
    )


# =========================================================
# HISTORIAL POR PRODUCTO
# =========================================================

@permiso_requerido(
    "inventario.view_movimientostock"
)
def movimiento_historial_producto(
    request,
    codigo_id,
):
    codigo = get_object_or_404(
        CodigoProducto.objects
        .select_related(
            "producto",
            "marca",
        ),
        id=codigo_id,
    )

    movimientos = (
        codigo.movimientos
        .select_related(
            "sucursal"
        )
        .order_by(
            "-fecha"
        )
    )

    movimientos = _limitar_movimientos_por_sucursal(
        request,
        movimientos,
    )

    entradas = (
        movimientos
        .filter(
            tipo_movimiento="entrada"
        )
        .aggregate(
            total=Sum("cantidad")
        )["total"]
        or Decimal("0")
    )

    salidas = (
        movimientos
        .filter(
            tipo_movimiento="salida"
        )
        .aggregate(
            total=Sum("cantidad")
        )["total"]
        or Decimal("0")
    )

    return render(
        request,
        "inventario/movimientos/historial_producto.html",
        {
            "codigo": codigo,
            "movimientos": movimientos,
            "total_entradas": entradas,
            "total_salidas": salidas,
            "sucursal_activa": (
                obtener_sucursal_activa(
                    request
                )
            ),
            "puede_cambiar_sucursal": (
                usuario_puede_cambiar_sucursal(
                    request
                )
            ),
        },
    )


# =========================================================
# ENTRADA RÁPIDA
# =========================================================

@permiso_requerido(
    "inventario.add_movimientostock"
)
def movimiento_entrada_rapida(
    request,
    codigo_id,
):
    codigo = get_object_or_404(
        CodigoProducto,
        id=codigo_id,
    )

    sucursal_activa = obtener_sucursal_activa(
        request
    )

    puede_cambiar_sucursal = (
        usuario_puede_cambiar_sucursal(
            request
        )
    )

    sucursales = _sucursales_disponibles(
        request
    )

    if request.method == "POST":
        try:
            sucursal = _resolver_sucursal_escritura(
                request,
                request.POST.get("sucursal"),
            )

            if not sucursal:
                raise ValueError(
                    "Debes seleccionar una sucursal válida."
                )

            cantidad = _decimal_positivo(
                request.POST.get("cantidad")
            )

            referencia = (
                request.POST
                .get("referencia", "")
                .strip()
                or "Entrada manual"
            )

            MovimientoStock.objects.create(
                codigo_producto=codigo,
                sucursal=sucursal,
                tipo_movimiento="entrada",
                cantidad=cantidad,
                referencia=referencia,
            )

            messages.success(
                request,
                "Entrada registrada.",
            )

            return redirect(
                "inventario_historial_producto",
                codigo_id=codigo.id,
            )

        except Exception as e:
            messages.error(
                request,
                str(e),
            )

    return render(
        request,
        "inventario/movimientos/entrada.html",
        {
            "codigo": codigo,
            "sucursales": sucursales,
            "sucursal_activa": sucursal_activa,
            "puede_cambiar_sucursal": (
                puede_cambiar_sucursal
            ),
        },
    )


# =========================================================
# SALIDA RÁPIDA
# =========================================================

@permiso_requerido(
    "inventario.add_movimientostock"
)
def movimiento_salida_rapida(
    request,
    codigo_id,
):
    codigo = get_object_or_404(
        CodigoProducto,
        id=codigo_id,
    )

    sucursal_activa = obtener_sucursal_activa(
        request
    )

    puede_cambiar_sucursal = (
        usuario_puede_cambiar_sucursal(
            request
        )
    )

    sucursales = _sucursales_disponibles(
        request
    )

    if request.method == "POST":
        try:
            sucursal = _resolver_sucursal_escritura(
                request,
                request.POST.get("sucursal"),
            )

            if not sucursal:
                raise ValueError(
                    "Debes seleccionar una sucursal válida."
                )

            cantidad = _decimal_positivo(
                request.POST.get("cantidad")
            )

            referencia = (
                request.POST
                .get("referencia", "")
                .strip()
                or "Salida manual"
            )

            MovimientoStock.objects.create(
                codigo_producto=codigo,
                sucursal=sucursal,
                tipo_movimiento="salida",
                cantidad=cantidad,
                referencia=referencia,
            )

            messages.success(
                request,
                "Salida registrada.",
            )

            return redirect(
                "inventario_historial_producto",
                codigo_id=codigo.id,
            )

        except Exception as e:
            messages.error(
                request,
                str(e),
            )

    return render(
        request,
        "inventario/movimientos/salida.html",
        {
            "codigo": codigo,
            "sucursales": sucursales,
            "sucursal_activa": sucursal_activa,
            "puede_cambiar_sucursal": (
                puede_cambiar_sucursal
            ),
        },
    )