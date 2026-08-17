from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
import re
import xml.etree.ElementTree as ET

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile


VERSION_XML_FACTURA = "2.1.0"
CENTAVO = Decimal("0.01")
CERO = Decimal("0.00")
LIMITE_CONSUMIDOR_FINAL = Decimal("50.00")


# =========================================================
# HELPERS
# =========================================================

def _d(valor, default="0.00"):
    return Decimal(default) if valor is None else Decimal(str(valor))


def _q2(valor):
    return _d(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _fmt2(valor):
    return format(_q2(valor), ".2f")


def _fmt6(valor):
    return format(
        _d(valor).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
        ".6f",
    )


def _texto(valor):
    return "" if valor is None else str(valor).strip()


def _digitos(valor):
    return bool(re.fullmatch(r"\d+", _texto(valor)))


def _primero(objeto, *nombres, default=""):
    if objeto is None:
        return default
    for nombre in nombres:
        if not hasattr(objeto, nombre):
            continue
        valor = getattr(objeto, nombre)
        if valor is None:
            continue
        if isinstance(valor, str):
            valor = valor.strip()
            if not valor:
                continue
        return valor
    return default


def _si_no(valor):
    if valor is None or valor == "":
        return ""
    if isinstance(valor, bool):
        return "SI" if valor else "NO"
    texto = _texto(valor).upper()
    if texto in {"SI", "SÍ", "S", "1", "TRUE", "VERDADERO"}:
        return "SI"
    if texto in {"NO", "N", "0", "FALSE", "FALSO"}:
        return "NO"
    return texto


def _maximo(valor, longitud, campo):
    texto = _texto(valor)
    if len(texto) > longitud:
        raise ValidationError(
            f"{campo} supera el máximo permitido por SRI ({longitud} caracteres)."
        )
    return texto


def _sub(padre, nombre, valor, obligatorio=True):
    texto = _texto(valor)
    if not texto:
        if obligatorio:
            raise ValidationError(f"El campo XML <{nombre}> es obligatorio.")
        return None
    nodo = ET.SubElement(padre, nombre)
    nodo.text = texto
    return nodo


def _campo_adicional(padre, nombre, valor):
    valor = _maximo(valor, 300, f"Campo adicional {nombre}")
    if not valor:
        return None
    nodo = ET.SubElement(padre, "campoAdicional", {"nombre": _maximo(nombre, 300, "nombre")})
    nodo.text = valor
    return nodo


# =========================================================
# EMISOR
# =========================================================

def _datos_emisor(factura):
    empresa = factura.empresa
    if empresa is None:
        raise ValidationError("La factura no tiene EmpresaEmisora.")

    ruc = _texto(_primero(empresa, "ruc"))
    if not _digitos(ruc) or len(ruc) != 13:
        raise ValidationError("El RUC del emisor debe tener exactamente 13 dígitos.")

    razon_social = _texto(
        _primero(empresa, "razon_social", "razonSocial", "nombre_legal", "nombre")
    )
    if not razon_social:
        raise ValidationError("La EmpresaEmisora no tiene razón social configurada.")

    direccion_matriz = _texto(
        _primero(
            empresa,
            "direccion_matriz",
            "dir_matriz",
            "direccion",
            "direccion_principal",
        )
    )
    if not direccion_matriz:
        raise ValidationError("La EmpresaEmisora no tiene dirección matriz configurada.")

    agente_retencion = _primero(
        empresa,
        "agente_retencion",
        "numero_agente_retencion",
        "resolucion_agente_retencion",
        default="",
    )
    # Si el modelo tuviera un booleano, no podemos inventar el número de resolución.
    if isinstance(agente_retencion, bool):
        agente_retencion = ""
    agente_retencion = _texto(agente_retencion)
    if agente_retencion and (not _digitos(agente_retencion) or len(agente_retencion) > 8):
        raise ValidationError("El número de Agente de Retención debe ser numérico y máximo 8 dígitos.")

    contribuyente_especial = _primero(
        empresa,
        "contribuyente_especial",
        "numero_contribuyente_especial",
        "resolucion_contribuyente_especial",
        default="",
    )
    if isinstance(contribuyente_especial, bool):
        contribuyente_especial = ""

    direccion_establecimiento = _texto(
        _primero(factura.sucursal, "direccion", "direccion_establecimiento", default="")
    ) or direccion_matriz

    return {
        "ruc": ruc,
        "razon_social": razon_social,
        "nombre_comercial": _texto(_primero(empresa, "nombre_comercial", "nombreComercial")),
        "direccion_matriz": direccion_matriz,
        "direccion_establecimiento": direccion_establecimiento,
        "contribuyente_especial": _texto(contribuyente_especial),
        "obligado_contabilidad": _si_no(
            _primero(
                empresa,
                "obligado_llevar_contabilidad",
                "obligado_contabilidad",
                default="",
            )
        ),
        "agente_retencion": agente_retencion,
        "contribuyente_rimpe": _texto(
            _primero(empresa, "contribuyente_rimpe", "leyenda_rimpe", default="")
        ),
    }


# =========================================================
# VALIDACIÓN PREVIA
# =========================================================

def _validar_factura(factura):
    if factura is None or not factura.pk:
        raise ValidationError("La factura debe existir y estar guardada antes de generar el XML.")

    if factura.estado in {"FIRMADO", "RECIBIDO", "AUTORIZADO"}:
        raise ValidationError(
            "No se puede regenerar el XML de una factura firmada, recibida o autorizada."
        )

    if not factura.sucursal_id or not factura.empresa_id:
        raise ValidationError("La factura debe tener sucursal y empresa emisora.")

    if not _digitos(factura.establecimiento) or len(factura.establecimiento) != 3:
        raise ValidationError("El establecimiento debe tener exactamente 3 dígitos.")
    if not _digitos(factura.punto_emision) or len(factura.punto_emision) != 3:
        raise ValidationError("El punto de emisión debe tener exactamente 3 dígitos.")
    if not _digitos(factura.secuencial) or len(factura.secuencial) != 9:
        raise ValidationError("El secuencial debe tener exactamente 9 dígitos.")
    if not _digitos(factura.clave_acceso) or len(factura.clave_acceso) != 49:
        raise ValidationError("La clave de acceso debe tener exactamente 49 dígitos.")
    if not factura.fecha_emision:
        raise ValidationError("La factura no tiene fecha de emisión.")

    tipo = factura.tipo_identificacion_comprador
    identificacion = _texto(factura.identificacion_comprador)
    if tipo not in {"04", "05", "06", "07"}:
        raise ValidationError("Tipo de identificación del comprador no válido para SRI.")
    if not _texto(factura.razon_social_comprador):
        raise ValidationError("La factura no tiene razón social del comprador.")

    if tipo == "04" and (not _digitos(identificacion) or len(identificacion) != 13):
        raise ValidationError("Para RUC, la identificación debe tener 13 dígitos.")
    if tipo == "05" and (not _digitos(identificacion) or len(identificacion) != 10):
        raise ValidationError("Para cédula, la identificación debe tener 10 dígitos.")
    if tipo == "06" and len(identificacion) < 3:
        raise ValidationError("El pasaporte del comprador no es válido.")
    if tipo == "07":
        if identificacion != "9999999999999":
            raise ValidationError("Consumidor Final debe usar 9999999999999.")
        if _q2(factura.importe_total) > LIMITE_CONSUMIDOR_FINAL:
            raise ValidationError(
                "El SRI exige identificar al adquirente cuando la factura supera USD 50.00; "
                "no puede emitirse como Consumidor Final."
            )

    detalles = list(factura.detalles.all().order_by("id"))
    if not detalles:
        raise ValidationError("La factura no tiene detalles.")

    total_base = CERO
    total_descuento = CERO
    total_iva = CERO

    for detalle in detalles:
        if _d(detalle.cantidad) <= CERO:
            raise ValidationError(f"El detalle {detalle.pk} tiene cantidad inválida.")
        if _d(detalle.precio_unitario) < CERO:
            raise ValidationError(f"El detalle {detalle.pk} tiene precio unitario inválido.")
        if _q2(detalle.descuento) < CERO:
            raise ValidationError(f"El detalle {detalle.pk} tiene descuento inválido.")
        if detalle.codigo_impuesto != "2":
            raise ValidationError(f"El detalle {detalle.pk} usa un impuesto no soportado.")
        if detalle.codigo_porcentaje_iva not in {"0", "4"}:
            raise ValidationError(f"El detalle {detalle.pk} usa una tarifa IVA no soportada.")
        if detalle.codigo_porcentaje_iva == "4" and _q2(detalle.tarifa_iva) != Decimal("15.00"):
            raise ValidationError(f"El detalle {detalle.pk} usa código IVA 4 pero tarifa distinta de 15%.")
        if detalle.codigo_porcentaje_iva == "0" and _q2(detalle.tarifa_iva) != CERO:
            raise ValidationError(f"El detalle {detalle.pk} usa código IVA 0 pero tarifa distinta de 0%.")

        _maximo(detalle.codigo_principal, 25, "codigoPrincipal")
        if detalle.codigo_auxiliar:
            _maximo(detalle.codigo_auxiliar, 25, "codigoAuxiliar")
        _maximo(detalle.descripcion, 300, "descripcion")

        total_base += _q2(detalle.precio_total_sin_impuesto)
        total_descuento += _q2(detalle.descuento)
        total_iva += _q2(detalle.valor_iva)

    total_base = _q2(total_base)
    total_descuento = _q2(total_descuento)
    total_iva = _q2(total_iva)

    if total_base != _q2(factura.total_sin_impuestos):
        raise ValidationError("La suma de detalles no coincide con total_sin_impuestos.")
    if total_descuento != _q2(factura.total_descuento):
        raise ValidationError("La suma de descuentos no coincide con total_descuento.")
    if total_iva != _q2(factura.valor_iva):
        raise ValidationError("La suma del IVA de detalles no coincide con valor_iva.")

    total_esperado = _q2(total_base + total_iva + _q2(factura.propina))
    if total_esperado != _q2(factura.importe_total):
        raise ValidationError("El importe total no coincide con base + impuestos + propina.")

    pagos = list(factura.pagos.all().order_by("id"))
    if not pagos:
        raise ValidationError("Debes declarar al menos una forma de pago antes de generar el XML.")

    total_pagos = _q2(sum((_q2(p.total) for p in pagos), CERO))
    if total_pagos != _q2(factura.importe_total):
        raise ValidationError("La suma de las formas de pago debe ser igual al importe total.")

    _datos_emisor(factura)
    return detalles, pagos


# =========================================================
# IMPUESTOS CABECERA
# =========================================================

def _agrupar_impuestos(detalles):
    grupos = defaultdict(lambda: {"base": CERO, "valor": CERO})
    for d in detalles:
        clave = (_texto(d.codigo_impuesto), _texto(d.codigo_porcentaje_iva))
        grupos[clave]["base"] += _q2(d.base_imponible)
        grupos[clave]["valor"] += _q2(d.valor_iva)

    resultado = []
    for (codigo, porcentaje), valores in grupos.items():
        resultado.append(
            {
                "codigo": codigo,
                "codigo_porcentaje": porcentaje,
                "base": _q2(valores["base"]),
                "valor": _q2(valores["valor"]),
            }
        )
    return sorted(resultado, key=lambda x: (x["codigo"], x["codigo_porcentaje"]))


# =========================================================
# CONSTRUCCIÓN XML
# =========================================================

def _info_tributaria(raiz, factura, emisor):
    info = ET.SubElement(raiz, "infoTributaria")
    _sub(info, "ambiente", factura.ambiente)
    _sub(info, "tipoEmision", factura.tipo_emision)
    _sub(info, "razonSocial", _maximo(emisor["razon_social"], 300, "razonSocial"))
    if emisor["nombre_comercial"]:
        _sub(
            info,
            "nombreComercial",
            _maximo(emisor["nombre_comercial"], 300, "nombreComercial"),
            obligatorio=False,
        )
    _sub(info, "ruc", emisor["ruc"])
    _sub(info, "claveAcceso", factura.clave_acceso)
    _sub(info, "codDoc", factura.tipo_comprobante)
    _sub(info, "estab", factura.establecimiento)
    _sub(info, "ptoEmi", factura.punto_emision)
    _sub(info, "secuencial", factura.secuencial)
    _sub(info, "dirMatriz", _maximo(emisor["direccion_matriz"], 300, "dirMatriz"))
    if emisor["agente_retencion"]:
        _sub(info, "agenteRetencion", emisor["agente_retencion"], obligatorio=False)
    if emisor["contribuyente_rimpe"]:
        _sub(
            info,
            "contribuyenteRimpe",
            _maximo(emisor["contribuyente_rimpe"], 50, "contribuyenteRimpe"),
            obligatorio=False,
        )


def _info_factura(raiz, factura, emisor, detalles, pagos):
    info = ET.SubElement(raiz, "infoFactura")
    _sub(info, "fechaEmision", factura.fecha_emision.strftime("%d/%m/%Y"))
    if emisor["direccion_establecimiento"]:
        _sub(
            info,
            "dirEstablecimiento",
            _maximo(emisor["direccion_establecimiento"], 300, "dirEstablecimiento"),
            obligatorio=False,
        )
    if emisor["contribuyente_especial"]:
        _sub(
            info,
            "contribuyenteEspecial",
            _maximo(emisor["contribuyente_especial"], 13, "contribuyenteEspecial"),
            obligatorio=False,
        )
    if emisor["obligado_contabilidad"]:
        _sub(info, "obligadoContabilidad", emisor["obligado_contabilidad"], obligatorio=False)

    _sub(info, "tipoIdentificacionComprador", factura.tipo_identificacion_comprador)
    if factura.guia_remision:
        _sub(info, "guiaRemision", _maximo(factura.guia_remision, 20, "guiaRemision"), obligatorio=False)
    _sub(
        info,
        "razonSocialComprador",
        _maximo(factura.razon_social_comprador, 300, "razonSocialComprador"),
    )
    _sub(
        info,
        "identificacionComprador",
        _maximo(factura.identificacion_comprador, 20, "identificacionComprador"),
    )
    if factura.direccion_comprador:
        _sub(
            info,
            "direccionComprador",
            _maximo(factura.direccion_comprador, 300, "direccionComprador"),
            obligatorio=False,
        )

    _sub(info, "totalSinImpuestos", _fmt2(factura.total_sin_impuestos))
    _sub(info, "totalDescuento", _fmt2(factura.total_descuento))

    total_con_impuestos = ET.SubElement(info, "totalConImpuestos")
    for grupo in _agrupar_impuestos(detalles):
        total = ET.SubElement(total_con_impuestos, "totalImpuesto")
        _sub(total, "codigo", grupo["codigo"])
        _sub(total, "codigoPorcentaje", grupo["codigo_porcentaje"])
        _sub(total, "baseImponible", _fmt2(grupo["base"]))
        _sub(total, "valor", _fmt2(grupo["valor"]))

    _sub(info, "propina", _fmt2(factura.propina))
    _sub(info, "importeTotal", _fmt2(factura.importe_total))
    _sub(info, "moneda", factura.moneda or "DOLAR")

    pagos_xml = ET.SubElement(info, "pagos")
    for pago in pagos:
        nodo = ET.SubElement(pagos_xml, "pago")
        _sub(nodo, "formaPago", pago.forma_pago)
        _sub(nodo, "total", _fmt2(pago.total))
        if pago.plazo and pago.plazo > 0:
            _sub(nodo, "plazo", str(pago.plazo), obligatorio=False)
            _sub(
                nodo,
                "unidadTiempo",
                _maximo(pago.unidad_tiempo or "dias", 10, "unidadTiempo"),
                obligatorio=False,
            )


def _detalles(raiz, detalles):
    contenedor = ET.SubElement(raiz, "detalles")
    for d in detalles:
        detalle = ET.SubElement(contenedor, "detalle")
        _sub(detalle, "codigoPrincipal", _maximo(d.codigo_principal, 25, "codigoPrincipal"))
        if d.codigo_auxiliar:
            _sub(
                detalle,
                "codigoAuxiliar",
                _maximo(d.codigo_auxiliar, 25, "codigoAuxiliar"),
                obligatorio=False,
            )
        _sub(detalle, "descripcion", _maximo(d.descripcion, 300, "descripcion"))
        _sub(detalle, "cantidad", _fmt6(d.cantidad))
        _sub(detalle, "precioUnitario", _fmt6(d.precio_unitario))
        _sub(detalle, "descuento", _fmt2(d.descuento))
        _sub(detalle, "precioTotalSinImpuesto", _fmt2(d.precio_total_sin_impuesto))

        adicionales = []
        if d.unidad_medida:
            adicionales.append(("Unidad", d.unidad_medida))
        if d.observaciones:
            adicionales.append(("Observación", d.observaciones))
        if adicionales:
            extras = ET.SubElement(detalle, "detallesAdicionales")
            for nombre, valor in adicionales[:3]:
                ET.SubElement(
                    extras,
                    "detAdicional",
                    {
                        "nombre": _maximo(nombre, 300, "nombre detAdicional"),
                        "valor": _maximo(valor, 300, "valor detAdicional"),
                    },
                )

        impuestos = ET.SubElement(detalle, "impuestos")
        impuesto = ET.SubElement(impuestos, "impuesto")
        _sub(impuesto, "codigo", d.codigo_impuesto)
        _sub(impuesto, "codigoPorcentaje", d.codigo_porcentaje_iva)
        _sub(impuesto, "tarifa", _fmt2(d.tarifa_iva))
        _sub(impuesto, "baseImponible", _fmt2(d.base_imponible))
        _sub(impuesto, "valor", _fmt2(d.valor_iva))


def _ruc_proveedor(ruc_proveedor=None):
    if ruc_proveedor is None:
        ruc_proveedor = getattr(settings, "SRI_RUC_PROVEEDOR", "")
    ruc_proveedor = _texto(ruc_proveedor)
    if not ruc_proveedor:
        return ""
    if not _digitos(ruc_proveedor) or len(ruc_proveedor) != 13:
        raise ValidationError("SRI_RUC_PROVEEDOR debe tener exactamente 13 dígitos.")
    return ruc_proveedor


def _info_adicional(raiz, factura, ruc_proveedor=None):
    campos = []
    if factura.telefono_comprador:
        campos.append(("Teléfono", factura.telefono_comprador))
    if factura.correo_comprador:
        campos.append(("Email", factura.correo_comprador))

    if factura.orden_id:
        orden = factura.orden
        if orden.numero_orden:
            campos.append(("OT", orden.numero_orden))
        if orden.placa:
            campos.append(("Placa", orden.placa))
        if orden.vehiculo:
            campos.append(("Vehículo", orden.vehiculo))
        if orden.kilometraje is not None:
            campos.append(("Kilometraje", orden.kilometraje))

    if factura.comentario:
        campos.append(("Comentario", factura.comentario))

    proveedor = _ruc_proveedor(ruc_proveedor)
    if proveedor:
        campos.append(("RUC Proveedor", proveedor))

    campos = [(n, v) for n, v in campos if _texto(v)][:15]
    if not campos:
        return

    info = ET.SubElement(raiz, "infoAdicional")
    for nombre, valor in campos:
        _campo_adicional(info, nombre, valor)


# =========================================================
# API PÚBLICA
# =========================================================

def construir_xml_factura(factura, ruc_proveedor=None):
    """
    Construye XML de Factura SRI 2.1.0.
    No firma, no envía al SRI y no cambia el estado.
    Retorna bytes UTF-8.
    """
    detalles, pagos = _validar_factura(factura)
    emisor = _datos_emisor(factura)

    raiz = ET.Element(
        "factura",
        {"id": "comprobante", "version": VERSION_XML_FACTURA},
    )
    _info_tributaria(raiz, factura, emisor)
    _info_factura(raiz, factura, emisor, detalles, pagos)
    _detalles(raiz, detalles)
    _info_adicional(raiz, factura, ruc_proveedor=ruc_proveedor)

    ET.indent(raiz, space="  ")
    return ET.tostring(
        raiz,
        encoding="utf-8",
        xml_declaration=True,
        short_empty_elements=True,
    )


def generar_xml_factura(factura, guardar=True, ruc_proveedor=None):
    """
    Genera el XML.

    Si guardar=True:
      - lo guarda en factura.xml_generado
      - cambia factura.estado a GENERADO

    Retorna los bytes XML.
    """
    xml_bytes = construir_xml_factura(factura, ruc_proveedor=ruc_proveedor)

    if not guardar:
        return xml_bytes

    nombre = (
        f"factura_{factura.establecimiento}-"
        f"{factura.punto_emision}-{factura.secuencial}.xml"
    )
    factura.xml_generado.save(nombre, ContentFile(xml_bytes), save=False)
    factura.estado = "GENERADO"
    factura.save(update_fields=["xml_generado", "estado", "updated_at"])
    return xml_bytes