# compras/services/importador.py

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction

from compras.models import (
    DetalleFacturaNormalizado,
    DetalleFacturaOriginal,
    FacturaCompra,
    Proveedor,
)


CERO = Decimal("0.00")


class ImportadorFacturaCompra:
    """
    Importa una factura obtenida mediante:

    - consulta por clave de acceso al SRI;
    - carga directa de un archivo XML.

    El servicio crea:

    1. FacturaCompra.
    2. DetalleFacturaOriginal por cada línea recibida.
    3. DetalleFacturaNormalizado por cada detalle original.

    Los detalles normalizados quedan pendientes de confirmación
    humana porque todavía no tienen producto ni código del
    inventario relacionados.

    Este servicio NO aumenta el stock y NO registra aprendizaje.
    """

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

    # =====================================================
    # CONVERSIÓN DE DATOS
    # =====================================================

    @staticmethod
    def _decimal(
        valor,
        *,
        default=CERO,
        nombre="valor",
    ):
        """
        Convierte un valor a Decimal.

        Evita almacenar flotantes en cantidades, precios,
        descuentos e impuestos.
        """

        if valor in {
            None,
            "",
        }:
            return Decimal(str(default))

        try:
            return Decimal(str(valor))
        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ) as error:
            raise ValidationError(
                f"{nombre} debe ser un número válido."
            ) from error

    @staticmethod
    def _texto(
        valor,
        *,
        default="",
    ):
        return str(
            valor
            if valor is not None
            else default
        ).strip()

    # =====================================================
    # PROVEEDOR
    # =====================================================

    def _buscar_proveedor(self, datos):
        """
        Busca un proveedor ya registrado por RUC.

        No crea automáticamente el proveedor porque puede ser
        necesario que una persona revise sus datos antes de
        registrarlo en el catálogo definitivo.
        """

        ruc = self._texto(
            datos.get("ruc")
        )

        if not ruc:
            return None

        return (
            Proveedor.objects
            .filter(ruc=ruc)
            .order_by("id")
            .first()
        )

    # =====================================================
    # CONFIGURACIÓN TRIBUTARIA
    # =====================================================

    def _buscar_configuracion_iva(
        self,
        porcentaje,
    ):
        from ordenes_de_trabajo.models import (
            ConfiguracionTributaria,
        )

        porcentaje = self._decimal(
            porcentaje,
            default=CERO,
            nombre="porcentaje de IVA",
        )

        configuracion = (
            ConfiguracionTributaria.objects
            .filter(
                activa=True,
                porcentaje_iva=porcentaje,
            )
            .order_by(
                "-fecha_inicio",
                "-id",
            )
            .first()
        )

        if configuracion:
            return configuracion

        return (
            ConfiguracionTributaria.objects
            .filter(activa=True)
            .order_by(
                "-fecha_inicio",
                "-id",
            )
            .first()
        )

    # =====================================================
    # VALIDACIÓN DEL ORIGEN
    # =====================================================

    def _validar_origen(self, origen):
        origen = self._texto(
            origen
        ).upper()

        if origen not in self.ORIGENES_VALIDOS:
            raise ValidationError(
                "El origen debe ser 'CLAVE' o 'XML'."
            )

        return origen

    # =====================================================
    # VALIDACIÓN DE LA CLAVE
    # =====================================================

    def _validar_clave(self, clave_acceso):
        clave = self._texto(
            clave_acceso
        )

        if not clave:
            raise ValidationError(
                "No existe clave de acceso para importar."
            )

        if len(clave) != 49:
            raise ValidationError(
                "La clave de acceso debe contener "
                "exactamente 49 dígitos."
            )

        if not clave.isdigit():
            raise ValidationError(
                "La clave de acceso solo puede contener números."
            )

        return clave

    # =====================================================
    # CONTROL DE DUPLICADOS
    # =====================================================

    def _validar_duplicado(
        self,
        clave_acceso,
    ):
        existente = (
            FacturaCompra.objects
            .filter(
                clave_acceso_sri=clave_acceso
            )
            .order_by("id")
            .first()
        )

        if existente:
            raise ValidationError(
                "Esta factura ya fue importada. "
                f"Registro existente: {existente}"
            )

    # =====================================================
    # XML ORIGINAL
    # =====================================================

    def _preparar_xml(
        self,
        xml_original,
    ):
        if xml_original is None:
            return None

        if isinstance(
            xml_original,
            bytes,
        ):
            return xml_original

        if isinstance(
            xml_original,
            str,
        ):
            return xml_original.encode(
                "utf-8"
            )

        if hasattr(
            xml_original,
            "read",
        ):
            contenido = xml_original.read()

            if isinstance(
                contenido,
                str,
            ):
                contenido = contenido.encode(
                    "utf-8"
                )

            if not isinstance(
                contenido,
                bytes,
            ):
                raise ValidationError(
                    "No se pudo obtener el contenido "
                    "binario del archivo XML."
                )

            return contenido

        raise ValidationError(
            "El XML recibido no tiene un formato válido."
        )

    # =====================================================
    # CREACIÓN DE FACTURA
    # =====================================================

    def _crear_factura(
        self,
        *,
        datos,
        origen,
        clave,
        contenido_xml,
    ):
        porcentaje_iva = self._decimal(
            datos.get("porcentaje_iva"),
            default=CERO,
            nombre="porcentaje de IVA",
        )

        subtotal = self._decimal(
            datos.get("subtotal"),
            default=CERO,
            nombre="subtotal",
        )

        iva = self._decimal(
            datos.get("iva"),
            default=CERO,
            nombre="IVA",
        )

        total = self._decimal(
            datos.get("total"),
            default=CERO,
            nombre="total",
        )

        if subtotal < CERO:
            raise ValidationError(
                "El subtotal de la factura "
                "no puede ser negativo."
            )

        if iva < CERO:
            raise ValidationError(
                "El IVA de la factura "
                "no puede ser negativo."
            )

        if total < CERO:
            raise ValidationError(
                "El total de la factura "
                "no puede ser negativo."
            )

        configuracion_iva = (
            self._buscar_configuracion_iva(
                porcentaje_iva
            )
        )

        proveedor_rel = self._buscar_proveedor(
            datos
        )

        factura = FacturaCompra(
            origen_ingreso=origen,

            proveedor_rel=proveedor_rel,
            sucursal_destino=(
                self.sucursal_destino
            ),

            configuracion_iva=(
                configuracion_iva
            ),
            porcentaje_iva=porcentaje_iva,

            clave_acceso_sri=clave,
            clave_acceso=clave,

            proveedor=self._texto(
                datos.get("proveedor")
            )
            or None,

            ruc=self._texto(
                datos.get("ruc")
            )
            or None,

            numero_factura=self._texto(
                datos.get("numero_factura")
            )
            or None,

            fecha_emision=datos.get(
                "fecha_emision"
            ),

            subtotal=subtotal,
            iva=iva,
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
                ContentFile(
                    contenido_xml
                ),
                save=False,
            )

        factura.save()

        return factura

    # =====================================================
    # PREPARACIÓN DE DETALLES
    # =====================================================

    def _preparar_detalle(
        self,
        *,
        item,
        indice,
    ):
        codigo_principal = self._texto(
            item.get("codigo_principal")
        )

        codigo_auxiliar = self._texto(
            item.get("codigo_auxiliar")
        )

        codigo = (
            codigo_principal
            or codigo_auxiliar
        )

        descripcion = self._texto(
            item.get("descripcion"),
            default="SIN DESCRIPCIÓN",
        )

        if not descripcion:
            descripcion = "SIN DESCRIPCIÓN"

        cantidad = self._decimal(
            item.get("cantidad"),
            default=CERO,
            nombre=(
                f"cantidad del detalle {indice}"
            ),
        )

        precio_unitario = self._decimal(
            item.get("precio_unitario"),
            default=CERO,
            nombre=(
                f"precio unitario del detalle {indice}"
            ),
        )

        descuento = self._decimal(
            item.get("descuento"),
            default=CERO,
            nombre=(
                f"descuento del detalle {indice}"
            ),
        )

        porcentaje_iva = self._decimal(
            item.get("porcentaje_iva"),
            default=CERO,
            nombre=(
                f"porcentaje de IVA del detalle {indice}"
            ),
        )

        valor_iva = self._decimal(
            item.get("valor_iva"),
            default=CERO,
            nombre=(
                f"valor de IVA del detalle {indice}"
            ),
        )

        aplica_iva = bool(
            item.get(
                "aplica_iva",
                porcentaje_iva > CERO,
            )
        )

        if cantidad <= CERO:
            raise ValidationError(
                f"La cantidad del producto "
                f"'{descripcion}' debe ser mayor que 0."
            )

        if precio_unitario < CERO:
            raise ValidationError(
                f"El precio unitario del producto "
                f"'{descripcion}' no puede ser negativo."
            )

        if descuento < CERO:
            raise ValidationError(
                f"El descuento del producto "
                f"'{descripcion}' no puede ser negativo."
            )

        if porcentaje_iva < CERO:
            raise ValidationError(
                f"El porcentaje de IVA del producto "
                f"'{descripcion}' no puede ser negativo."
            )

        if valor_iva < CERO:
            raise ValidationError(
                f"El valor del IVA del producto "
                f"'{descripcion}' no puede ser negativo."
            )

        importe_bruto = (
            cantidad
            * precio_unitario
        )

        if descuento > importe_bruto:
            raise ValidationError(
                f"El descuento del producto "
                f"'{descripcion}' supera el importe bruto."
            )

        return {
            "indice": indice,
            "codigo": codigo,
            "descripcion": descripcion,
            "cantidad": cantidad,
            "precio_unitario": precio_unitario,
            "descuento": descuento,
            "aplica_iva": aplica_iva,
            "porcentaje_iva": porcentaje_iva,
            "valor_iva": valor_iva,
        }

    # =====================================================
    # CREACIÓN DE DETALLE ORIGINAL
    # =====================================================

    def _crear_detalle_original(
        self,
        *,
        factura,
        detalle_preparado,
    ):
        """
        Conserva exactamente la información de origen.

        Este registro no debe modificarse para adaptar el nombre
        o código al catálogo interno.
        """

        detalle_original = (
            DetalleFacturaOriginal(
                factura=factura,

                codigo_proveedor=(
                    detalle_preparado["codigo"]
                    or None
                ),

                descripcion_proveedor=(
                    detalle_preparado[
                        "descripcion"
                    ]
                ),

                cantidad=(
                    detalle_preparado[
                        "cantidad"
                    ]
                ),

                precio_unitario=(
                    detalle_preparado[
                        "precio_unitario"
                    ]
                ),

                descuento=(
                    detalle_preparado[
                        "descuento"
                    ]
                ),

                aplica_iva=(
                    detalle_preparado[
                        "aplica_iva"
                    ]
                ),

                porcentaje_iva=(
                    detalle_preparado[
                        "porcentaje_iva"
                    ]
                ),

                valor_iva=(
                    detalle_preparado[
                        "valor_iva"
                    ]
                ),
            )
        )

        detalle_original.save()

        return detalle_original

    # =====================================================
    # CREACIÓN DE DETALLE NORMALIZADO
    # =====================================================

    def _crear_detalle_normalizado(
        self,
        *,
        detalle_original,
        detalle_preparado,
    ):
        """
        Crea el registro operativo que posteriormente será
        clasificado y vinculado con inventario.

        Se utiliza tipo_destino='INVENTARIO' como clasificación
        inicial porque el modelo no posee una opción PENDIENTE.

        El registro continúa pendiente de confirmación porque:

        - producto_rel es None;
        - codigo_producto_rel es None;
        - ingresado_al_inventario es False.
        """

        detalle_normalizado = (
            DetalleFacturaNormalizado(
                detalle_original=(
                    detalle_original
                ),

                factura_manual=None,

                codigo_origen=(
                    detalle_preparado["codigo"]
                    or None
                ),

                descripcion_origen=(
                    detalle_preparado[
                        "descripcion"
                    ]
                ),

                tipo_destino="INVENTARIO",

                aplica_iva=(
                    detalle_preparado[
                        "aplica_iva"
                    ]
                ),

                porcentaje_iva=(
                    detalle_preparado[
                        "porcentaje_iva"
                    ]
                ),

                producto_rel=None,
                codigo_producto_rel=None,

                cantidad=(
                    detalle_preparado[
                        "cantidad"
                    ]
                ),

                costo_unitario=(
                    detalle_preparado[
                        "precio_unitario"
                    ]
                ),

                descuento=(
                    detalle_preparado[
                        "descuento"
                    ]
                ),

                actualizar_pvp_inventario=False,
                ingresado_al_inventario=False,

                observaciones=(
                    "Detalle importado desde el SRI. "
                    "Pendiente de revisión y vinculación "
                    "con el inventario."
                ),
            )
        )

        detalle_normalizado.save()

        return detalle_normalizado

    # =====================================================
    # CREACIÓN DE TODOS LOS DETALLES
    # =====================================================

    def _crear_detalles(
        self,
        *,
        factura,
        datos,
    ):
        """
        Por cada renglón del XML crea:

        - un DetalleFacturaOriginal;
        - un DetalleFacturaNormalizado.

        Se utiliza save() en lugar de bulk_create() para respetar
        las validaciones y lógica definida en los modelos.
        """

        items = datos.get(
            "detalles",
            []
        )

        if not isinstance(
            items,
            (
                list,
                tuple,
            ),
        ):
            raise ValidationError(
                "Los detalles de la factura "
                "deben enviarse como una lista."
            )

        if not items:
            raise ValidationError(
                "No existen detalles para guardar."
            )

        detalles_originales = []
        detalles_normalizados = []

        for indice, item in enumerate(
            items,
            start=1,
        ):
            if not isinstance(
                item,
                dict,
            ):
                raise ValidationError(
                    f"El detalle número {indice} "
                    "no tiene un formato válido."
                )

            detalle_preparado = (
                self._preparar_detalle(
                    item=item,
                    indice=indice,
                )
            )

            detalle_original = (
                self._crear_detalle_original(
                    factura=factura,
                    detalle_preparado=(
                        detalle_preparado
                    ),
                )
            )

            detalle_normalizado = (
                self._crear_detalle_normalizado(
                    detalle_original=(
                        detalle_original
                    ),
                    detalle_preparado=(
                        detalle_preparado
                    ),
                )
            )

            detalles_originales.append(
                detalle_original
            )

            detalles_normalizados.append(
                detalle_normalizado
            )

        return {
            "originales": detalles_originales,
            "normalizados": detalles_normalizados,
        }

    # =====================================================
    # IMPORTACIÓN PRINCIPAL
    # =====================================================

    @transaction.atomic
    def importar(
        self,
        datos,
        origen,
        xml_original=None,
    ):
        """
        Ejecuta la importación completa en una sola transacción.

        Si cualquier factura o detalle falla, Django revierte
        toda la operación.
        """

        if not isinstance(
            datos,
            dict,
        ):
            raise ValidationError(
                "Los datos de la factura "
                "no tienen un formato válido."
            )

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

        if (
            origen == "XML"
            and not contenido_xml
        ):
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

        resultado_detalles = (
            self._crear_detalles(
                factura=factura,
                datos=datos,
            )
        )

        factura.calcular_totales()

        factura.refresh_from_db(
            fields=[
                "subtotal",
                "iva",
                "total",
                "porcentaje_iva",
                "saldo_pendiente",
                "esta_pagada",
            ]
        )

        factura.recalcular_estado_pago(
            guardar=True
        )

        return {
            "factura": factura,
            "detalles_originales": (
                resultado_detalles[
                    "originales"
                ]
            ),
            "detalles_normalizados": (
                resultado_detalles[
                    "normalizados"
                ]
            ),
        }