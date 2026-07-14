# compras/services/importador.py

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction

from compras.models import (
    DetalleFacturaOriginal,
    FacturaCompra,
    Proveedor,
)


class ImportadorFacturaCompra:
    ORIGENES_VALIDOS = {
        "CLAVE",
        "XML",
    }

    def __init__(self, sucursal_destino):
        if sucursal_destino is None:
            raise ValidationError(
                "Debe indicar la sucursal destino."
            )

        self.sucursal_destino = sucursal_destino

    def _buscar_proveedor(self, datos):
        ruc = str(
            datos.get("ruc") or ""
        ).strip()

        if not ruc:
            return None

        return (
            Proveedor.objects
            .filter(ruc=ruc)
            .order_by("id")
            .first()
        )

    def _buscar_configuracion_iva(self, porcentaje):
        from ordenes_de_trabajo.models import (
            ConfiguracionTributaria,
        )

        porcentaje = (
            porcentaje
            if porcentaje is not None
            else Decimal("0.00")
        )

        configuracion = (
            ConfiguracionTributaria.objects
            .filter(
                activa=True,
                porcentaje_iva=porcentaje,
            )
            .order_by("-fecha_inicio", "-id")
            .first()
        )

        if configuracion:
            return configuracion

        return (
            ConfiguracionTributaria.objects
            .filter(activa=True)
            .order_by("-fecha_inicio", "-id")
            .first()
        )

    def _validar_origen(self, origen):
        origen = str(origen or "").strip().upper()

        if origen not in self.ORIGENES_VALIDOS:
            raise ValidationError(
                "El origen debe ser 'CLAVE' o 'XML'."
            )

        return origen

    def _validar_clave(self, clave_acceso):
        clave = str(
            clave_acceso or ""
        ).strip()

        if not clave:
            raise ValidationError(
                "No existe clave de acceso para importar."
            )

        if len(clave) != 49 or not clave.isdigit():
            raise ValidationError(
                "La clave de acceso debe contener "
                "exactamente 49 dígitos."
            )

        return clave

    def _validar_duplicado(self, clave_acceso):
        existente = (
            FacturaCompra.objects
            .filter(clave_acceso_sri=clave_acceso)
            .first()
        )

        if existente:
            raise ValidationError(
                "Esta factura ya fue importada. "
                f"Registro existente: {existente}"
            )

    def _preparar_xml(self, xml_original):
        if xml_original is None:
            return None

        if isinstance(xml_original, bytes):
            return xml_original

        if isinstance(xml_original, str):
            return xml_original.encode("utf-8")

        if hasattr(xml_original, "read"):
            contenido = xml_original.read()

            if isinstance(contenido, str):
                contenido = contenido.encode("utf-8")

            return contenido

        raise ValidationError(
            "El XML recibido no tiene un formato válido."
        )

    def _crear_factura(
        self,
        datos,
        origen,
        clave,
        contenido_xml,
    ):
        porcentaje_iva = (
            datos.get("porcentaje_iva")
            if datos.get("porcentaje_iva") is not None
            else Decimal("0.00")
        )

        configuracion_iva = (
            self._buscar_configuracion_iva(
                porcentaje_iva
            )
        )

        proveedor_rel = self._buscar_proveedor(
            datos
        )

        total = (
            datos.get("total")
            if datos.get("total") is not None
            else Decimal("0.00")
        )

        factura = FacturaCompra(
            origen_ingreso=origen,

            proveedor_rel=proveedor_rel,
            sucursal_destino=self.sucursal_destino,

            configuracion_iva=configuracion_iva,
            porcentaje_iva=porcentaje_iva,

            clave_acceso_sri=clave,
            clave_acceso=clave,

            proveedor=datos.get("proveedor"),
            ruc=datos.get("ruc"),
            numero_factura=datos.get(
                "numero_factura"
            ),
            fecha_emision=datos.get(
                "fecha_emision"
            ),

            subtotal=datos.get(
                "subtotal",
                Decimal("0.00"),
            ),
            iva=datos.get(
                "iva",
                Decimal("0.00"),
            ),
            total=total,

            forma_pago="CONTADO",
            dias_plazo=0,

            saldo_pendiente=total,
            esta_pagada=False,

            estado="BORRADOR",
            procesado=False,

            observaciones=(
                "Factura importada automáticamente "
                f"mediante {origen}."
            ),
        )

        if contenido_xml:
            factura.archivo_xml.save(
                f"factura_{clave}.xml",
                ContentFile(contenido_xml),
                save=False,
            )

        factura.save()

        return factura

    def _crear_detalles(
        self,
        factura,
        datos,
    ):
        detalles = []

        for item in datos.get("detalles", []):
            codigo = (
                item.get("codigo_principal")
                or item.get("codigo_auxiliar")
                or ""
            )

            descripcion = (
                item.get("descripcion")
                or "SIN DESCRIPCIÓN"
            )

            cantidad = (
                item.get("cantidad")
                if item.get("cantidad") is not None
                else Decimal("0.00")
            )

            precio_unitario = (
                item.get("precio_unitario")
                if item.get("precio_unitario") is not None
                else Decimal("0.00")
            )

            descuento = (
                item.get("descuento")
                if item.get("descuento") is not None
                else Decimal("0.00")
            )

            aplica_iva = item.get(
                "aplica_iva",
                True,
            )

            if cantidad <= Decimal("0.00"):
                raise ValidationError(
                    f"La cantidad del producto "
                    f"'{descripcion}' debe ser mayor que 0."
                )

            if precio_unitario < Decimal("0.00"):
                raise ValidationError(
                    f"El precio unitario del producto "
                    f"'{descripcion}' no puede ser negativo."
                )

            if descuento < Decimal("0.00"):
                raise ValidationError(
                    f"El descuento del producto "
                    f"'{descripcion}' no puede ser negativo."
                )

            importe_bruto = (
                cantidad * precio_unitario
            )

            if descuento > importe_bruto:
                raise ValidationError(
                    f"El descuento del producto "
                    f"'{descripcion}' supera el importe bruto."
                )

            detalles.append(
                DetalleFacturaOriginal(
                    factura=factura,
                    codigo_proveedor=codigo,
                    descripcion_proveedor=descripcion,
                    cantidad=cantidad,
                    precio_unitario=precio_unitario,
                    descuento=descuento,
                    aplica_iva=aplica_iva,
                )
            )

        if not detalles:
            raise ValidationError(
                "No existen detalles para guardar."
            )

        DetalleFacturaOriginal.objects.bulk_create(
            detalles
        )

        return detalles

    @transaction.atomic
    def importar(
        self,
        datos,
        origen,
        xml_original=None,
    ):
        origen = self._validar_origen(
            origen
        )

        clave = self._validar_clave(
            datos.get("clave_acceso")
        )

        self._validar_duplicado(
            clave
        )

        contenido_xml = self._preparar_xml(
            xml_original
        )

        if origen == "XML" and not contenido_xml:
            raise ValidationError(
                "Para importar por XML debe proporcionar "
                "el archivo XML."
            )

        factura = self._crear_factura(
            datos=datos,
            origen=origen,
            clave=clave,
            contenido_xml=contenido_xml,
        )

        self._crear_detalles(
            factura=factura,
            datos=datos,
        )

        factura.calcular_totales()
        factura.recalcular_estado_pago(
            guardar=True
        )

        return factura