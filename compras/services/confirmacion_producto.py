# compras/services/confirmacion_producto.py

from django.core.exceptions import ValidationError
from django.db import transaction

from compras.models import DetalleFacturaNormalizado
from inventario.models import (
    CodigoProducto,
    Producto,
)
from inventario.services.aprendizaje import (
    AprendizajeProductoService,
)


class ConfirmacionProductoCompraService:
    """
    Confirma la relación entre un detalle de compra y un producto
    del inventario.

    Después de la confirmación humana registra el aprendizaje.
    """

    @classmethod
    @transaction.atomic
    def confirmar(
        cls,
        *,
        detalle,
        producto,
        usuario,
        codigo_producto=None,
        marca=None,
        confianza=100,
        observacion=None,
    ):
        if detalle is None or not detalle.pk:
            raise ValidationError(
                "Debe indicar un detalle de factura válido."
            )

        if producto is None or not producto.pk:
            raise ValidationError(
                "Debe seleccionar un producto válido."
            )

        if not isinstance(
            producto,
            Producto,
        ):
            raise ValidationError(
                "El producto seleccionado no es válido."
            )

        if (
            codigo_producto is not None
            and not isinstance(
                codigo_producto,
                CodigoProducto,
            )
        ):
            raise ValidationError(
                "El código seleccionado no es válido."
            )

        # Bloqueamos el detalle para evitar que dos usuarios
        # lo confirmen simultáneamente.
        detalle = (
            DetalleFacturaNormalizado.objects
            .select_for_update()
            .select_related(
                "detalle_original",
                "producto_rel",
                "factura",
                "factura__proveedor_rel",
            )
            .get(
                pk=detalle.pk
            )
        )

        if not producto.activo:
            raise ValidationError(
                "No puede confirmar un producto inactivo."
            )

        if getattr(
            producto,
            "descontinuado",
            False,
        ):
            raise ValidationError(
                "No puede confirmar un producto descontinuado."
            )

        if (
            codigo_producto is not None
            and codigo_producto.producto_id
            != producto.pk
        ):
            raise ValidationError(
                "El código seleccionado no pertenece "
                "al producto indicado."
            )

        if (
            marca is not None
            and codigo_producto is not None
            and codigo_producto.marca_id
            != marca.pk
        ):
            raise ValidationError(
                "La marca no coincide con la marca "
                "del código seleccionado."
            )

        # Comprobar la relación anterior.
        producto_anterior_id = (
            detalle.producto_rel_id
        )

        # Guardar la confirmación en compras.
        detalle.producto_rel = producto

        # Ajusta estos campos si tu modelo tiene nombres distintos.
        if hasattr(
            detalle,
            "codigo_sistema",
        ):
            detalle.codigo_sistema = (
                codigo_producto.codigo
                if codigo_producto
                else producto.sku_interno
            )

        if hasattr(
            detalle,
            "nombre_limpio",
        ):
            detalle.nombre_limpio = (
                producto.nombre
            )

        if hasattr(
            detalle,
            "tipo_destino",
        ):
            detalle.tipo_destino = "INVENTARIO"

        # Si tu modelo tiene alguno de estos campos,
        # se actualizan sin obligarte a tenerlos.
        if hasattr(
            detalle,
            "confirmado_por",
        ):
            detalle.confirmado_por = usuario

        if hasattr(
            detalle,
            "confirmado",
        ):
            detalle.confirmado = True

        if hasattr(
            detalle,
            "procesado",
        ):
            detalle.procesado = True

        detalle.full_clean()
        detalle.save()

        # Solo ahora, después de la confirmación humana,
        # se registra el aprendizaje.
        resultado_aprendizaje = (
            AprendizajeProductoService.registrar(
                detalle_normalizado=detalle,
                producto=producto,
                categoria=producto.categoria,
                codigo_producto=codigo_producto,
                marca=marca,
                proveedor=getattr(
                    detalle.factura,
                    "proveedor_rel",
                    None,
                ),
                origen="FACTURA",
                usuario=usuario,
                confianza=confianza,
                observacion=(
                    observacion
                    or (
                        "Producto confirmado manualmente "
                        "desde un detalle de compra."
                    )
                ),
                crear_alias=True,
            )
        )

        return {
            "detalle": detalle,
            "producto": producto,
            "producto_anterior_id": (
                producto_anterior_id
            ),
            "producto_cambiado": (
                producto_anterior_id
                != producto.pk
            ),
            "aprendizaje": (
                resultado_aprendizaje[
                    "aprendizaje"
                ]
            ),
            "alias": (
                resultado_aprendizaje[
                    "alias"
                ]
            ),
            "aprendizaje_creado": (
                resultado_aprendizaje[
                    "creado"
                ]
            ),
        }