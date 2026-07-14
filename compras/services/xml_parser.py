# compras/services/xml_parser.py

import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError


class XMLFacturaParser:
    TIPOS_FACTURA = {
        "factura",
        "liquidacionCompra",
    }

    @staticmethod
    def _nombre_etiqueta(elemento):
        return elemento.tag.split("}")[-1]

    @staticmethod
    def _decimal(valor, default="0.00"):
        try:
            return Decimal(str(valor or default).strip())
        except (InvalidOperation, ValueError, TypeError):
            return Decimal(default)

    @staticmethod
    def _fecha(valor):
        valor = str(valor or "").strip()

        if not valor:
            return None

        formatos = [
            "%d/%m/%Y",
            "%Y-%m-%d",
            "%d-%m-%Y",
        ]

        for formato in formatos:
            try:
                return datetime.strptime(
                    valor,
                    formato,
                ).date()
            except ValueError:
                continue

        raise ValidationError(
            f"La fecha '{valor}' no tiene un formato reconocido."
        )

    def _buscar_texto(
        self,
        elemento,
        etiqueta_buscada,
        default="",
    ):
        if elemento is None:
            return default

        for hijo in elemento.iter():
            if (
                self._nombre_etiqueta(hijo)
                == etiqueta_buscada
            ):
                return (hijo.text or default).strip()

        return default

    def _buscar_hijo_directo(
        self,
        elemento,
        etiqueta_buscada,
    ):
        if elemento is None:
            return None

        for hijo in list(elemento):
            if (
                self._nombre_etiqueta(hijo)
                == etiqueta_buscada
            ):
                return hijo

        return None

    def _buscar_hijos(
        self,
        elemento,
        etiqueta_buscada,
    ):
        if elemento is None:
            return []

        return [
            hijo
            for hijo in elemento.iter()
            if self._nombre_etiqueta(hijo)
            == etiqueta_buscada
        ]

    def leer(self, xml):
        if isinstance(xml, bytes):
            contenido = xml
        else:
            contenido = str(xml or "").encode("utf-8")

        try:
            raiz = ET.fromstring(contenido)
        except ET.ParseError as error:
            raise ValidationError(
                f"No se pudo interpretar el XML: {error}"
            ) from error

        tipo_documento = self._nombre_etiqueta(raiz)

        if tipo_documento not in self.TIPOS_FACTURA:
            raise ValidationError(
                f"El XML corresponde a '{tipo_documento}', "
                "no a una factura de compra."
            )

        info_tributaria = self._buscar_hijo_directo(
            raiz,
            "infoTributaria",
        )

        info_factura = self._buscar_hijo_directo(
            raiz,
            "infoFactura",
        )

        if info_tributaria is None:
            raise ValidationError(
                "El XML no contiene infoTributaria."
            )

        if info_factura is None:
            raise ValidationError(
                "El XML no contiene infoFactura."
            )

        establecimiento = self._buscar_texto(
            info_tributaria,
            "estab",
        )

        punto_emision = self._buscar_texto(
            info_tributaria,
            "ptoEmi",
        )

        secuencial = self._buscar_texto(
            info_tributaria,
            "secuencial",
        )

        numero_factura = "-".join(
            parte
            for parte in [
                establecimiento,
                punto_emision,
                secuencial,
            ]
            if parte
        )

        impuestos = self._leer_impuestos_factura(
            info_factura
        )

        datos = {
            "tipo_documento": tipo_documento,

            "clave_acceso": self._buscar_texto(
                info_tributaria,
                "claveAcceso",
            ),

            "ruc": self._buscar_texto(
                info_tributaria,
                "ruc",
            ),

            "proveedor": self._buscar_texto(
                info_tributaria,
                "razonSocial",
            ),

            "nombre_comercial": self._buscar_texto(
                info_tributaria,
                "nombreComercial",
            ),

            "numero_factura": numero_factura,

            "fecha_emision": self._fecha(
                self._buscar_texto(
                    info_factura,
                    "fechaEmision",
                )
            ),

            "subtotal": self._decimal(
                self._buscar_texto(
                    info_factura,
                    "totalSinImpuestos",
                )
            ),

            "iva": impuestos["iva"],

            "porcentaje_iva": impuestos[
                "porcentaje_iva"
            ],

            "total": self._decimal(
                self._buscar_texto(
                    info_factura,
                    "importeTotal",
                )
            ),

            "moneda": self._buscar_texto(
                info_factura,
                "moneda",
                "DOLAR",
            ),

            "forma_pago_sri": self._leer_forma_pago(
                info_factura
            ),

            "detalles": self._leer_detalles(raiz),
        }

        if not datos["clave_acceso"]:
            raise ValidationError(
                "El XML no contiene la clave de acceso."
            )

        if not datos["ruc"]:
            raise ValidationError(
                "El XML no contiene el RUC del proveedor."
            )

        if not datos["proveedor"]:
            raise ValidationError(
                "El XML no contiene la razón social."
            )

        if not datos["detalles"]:
            raise ValidationError(
                "La factura no contiene detalles de compra."
            )

        return datos

    def _leer_impuestos_factura(self, info_factura):
        total_iva = Decimal("0.00")
        porcentaje_principal = Decimal("0.00")

        total_con_impuestos = self._buscar_hijo_directo(
            info_factura,
            "totalConImpuestos",
        )

        if total_con_impuestos is None:
            return {
                "iva": total_iva,
                "porcentaje_iva": porcentaje_principal,
            }

        for impuesto in self._buscar_hijos(
            total_con_impuestos,
            "totalImpuesto",
        ):
            codigo = self._buscar_texto(
                impuesto,
                "codigo",
            )

            tarifa = self._decimal(
                self._buscar_texto(
                    impuesto,
                    "tarifa",
                )
            )

            valor = self._decimal(
                self._buscar_texto(
                    impuesto,
                    "valor",
                )
            )

            # En el SRI, código 2 corresponde al IVA.
            if codigo == "2":
                total_iva += valor

                if tarifa > porcentaje_principal:
                    porcentaje_principal = tarifa

        return {
            "iva": total_iva,
            "porcentaje_iva": porcentaje_principal,
        }

    def _leer_forma_pago(self, info_factura):
        pagos = self._buscar_hijo_directo(
            info_factura,
            "pagos",
        )

        if pagos is None:
            return None

        pago = self._buscar_hijo_directo(
            pagos,
            "pago",
        )

        if pago is None:
            return None

        return self._buscar_texto(
            pago,
            "formaPago",
        )

    def _leer_detalles(self, raiz):
        detalles_resultado = []

        contenedor_detalles = self._buscar_hijo_directo(
            raiz,
            "detalles",
        )

        if contenedor_detalles is None:
            return detalles_resultado

        for detalle in list(contenedor_detalles):
            if self._nombre_etiqueta(detalle) != "detalle":
                continue

            impuesto = self._leer_impuesto_detalle(
                detalle
            )

            detalles_resultado.append({
                "codigo_principal": self._buscar_texto(
                    detalle,
                    "codigoPrincipal",
                ),

                "codigo_auxiliar": self._buscar_texto(
                    detalle,
                    "codigoAuxiliar",
                ),

                "descripcion": self._buscar_texto(
                    detalle,
                    "descripcion",
                ),

                "cantidad": self._decimal(
                    self._buscar_texto(
                        detalle,
                        "cantidad",
                    )
                ),

                "precio_unitario": self._decimal(
                    self._buscar_texto(
                        detalle,
                        "precioUnitario",
                    )
                ),

                "descuento": self._decimal(
                    self._buscar_texto(
                        detalle,
                        "descuento",
                    )
                ),

                "subtotal": self._decimal(
                    self._buscar_texto(
                        detalle,
                        "precioTotalSinImpuesto",
                    )
                ),

                "aplica_iva": impuesto["tarifa"]
                > Decimal("0.00"),

                "porcentaje_iva": impuesto["tarifa"],

                "valor_iva": impuesto["valor"],
            })

        return detalles_resultado

    def _leer_impuesto_detalle(self, detalle):
        total_valor = Decimal("0.00")
        tarifa_principal = Decimal("0.00")

        impuestos = self._buscar_hijo_directo(
            detalle,
            "impuestos",
        )

        if impuestos is None:
            return {
                "tarifa": tarifa_principal,
                "valor": total_valor,
            }

        for impuesto in self._buscar_hijos(
            impuestos,
            "impuesto",
        ):
            codigo = self._buscar_texto(
                impuesto,
                "codigo",
            )

            if codigo != "2":
                continue

            tarifa = self._decimal(
                self._buscar_texto(
                    impuesto,
                    "tarifa",
                )
            )

            valor = self._decimal(
                self._buscar_texto(
                    impuesto,
                    "valor",
                )
            )

            total_valor += valor

            if tarifa > tarifa_principal:
                tarifa_principal = tarifa

        return {
            "tarifa": tarifa_principal,
            "valor": total_valor,
        }