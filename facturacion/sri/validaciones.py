from __future__ import annotations

"""
Validaciones centralizadas para facturación electrónica SRI.

Archivo:
    facturacion/sri/validaciones.py

Este módulo NO:
    - genera XML;
    - firma XML;
    - envía al SRI.

Solo valida que FacturaVenta y sus relaciones estén
consistentes antes de cada etapa.

Pensado para trabajar con:
    facturacion.models.FacturaVenta
    facturacion.models.DetalleFacturaVenta
    facturacion.models.PagoFacturaVenta
    empresa.models.EmpresaEmisora
    empresa.models.FirmaElectronica
"""

from decimal import Decimal, ROUND_HALF_UP

from .excepciones import (
    CertificadoFirmaError,
    ConfiguracionSRIError,
    EstadoFacturaSRIError,
    ValidacionSRIError,
)


# =========================================================
# CONSTANTES
# =========================================================

CENTAVO = Decimal("0.01")
CERO = Decimal("0.00")

AMBIENTE_PRUEBAS = "1"
AMBIENTE_PRODUCCION = "2"

TIPO_COMPROBANTE_FACTURA = "01"
TIPO_EMISION_NORMAL = "1"

TIPOS_IDENTIFICACION_SRI = {
    "04",  # RUC
    "05",  # Cédula
    "06",  # Pasaporte
    "07",  # Consumidor Final
}

IDENTIFICACION_CONSUMIDOR_FINAL = "9999999999999"
LIMITE_CONSUMIDOR_FINAL = Decimal("50.00")

FORMAS_PAGO_SRI = {
    "01",
    "15",
    "16",
    "17",
    "18",
    "19",
    "20",
    "21",
}

# Este proyecto actualmente soporta:
#   código 0 -> IVA 0%
#   código 4 -> IVA 15%
#
# Si después agregas otra tarifa SRI, se debe actualizar
# el modelo y esta tabla conjuntamente.
TARIFAS_IVA_SOPORTADAS = {
    "0": Decimal("0.00"),
    "4": Decimal("15.00"),
}

CODIGO_IMPUESTO_IVA = "2"

ESTADOS_FACTURA = {
    "BORRADOR",
    "GENERADO",
    "FIRMADO",
    "RECIBIDO",
    "AUTORIZADO",
    "RECHAZADO",
}


# =========================================================
# DECIMALES / TEXTO
# =========================================================

def _d(valor, default="0.00") -> Decimal:
    if valor is None:
        return Decimal(default)

    return Decimal(str(valor))


def _q2(valor) -> Decimal:
    return _d(valor).quantize(
        CENTAVO,
        rounding=ROUND_HALF_UP,
    )


def _texto(valor) -> str:
    if valor is None:
        return ""

    return str(valor).strip()


def _solo_digitos(valor) -> bool:
    texto = _texto(valor)
    return bool(texto) and texto.isdigit()


def _validar_longitud_maxima(
    valor,
    longitud: int,
    nombre: str,
) -> None:
    texto = _texto(valor)

    if len(texto) > longitud:
        raise ValidacionSRIError(
            f"{nombre} supera el máximo permitido "
            f"de {longitud} caracteres."
        )


# =========================================================
# CLAVE DE ACCESO
# =========================================================

def calcular_digito_verificador(
    clave_parcial: str,
) -> str:
    """
    Calcula módulo 11 para los primeros 48 dígitos
    de la clave de acceso.
    """

    clave_parcial = _texto(
        clave_parcial
    )

    if (
        len(clave_parcial) != 48
        or not clave_parcial.isdigit()
    ):
        raise ValidacionSRIError(
            "La clave parcial debe contener "
            "exactamente 48 dígitos."
        )

    factores = [
        2,
        3,
        4,
        5,
        6,
        7,
    ]

    total = 0
    indice = 0

    for digito in reversed(
        clave_parcial
    ):
        total += (
            int(digito)
            * factores[indice]
        )

        indice = (
            indice + 1
        ) % len(factores)

    residuo = total % 11
    verificador = 11 - residuo

    if verificador == 11:
        verificador = 0

    elif verificador == 10:
        verificador = 1

    return str(
        verificador
    )


def validar_clave_acceso(
    clave_acceso,
) -> bool:
    clave = _texto(
        clave_acceso
    )

    if (
        len(clave) != 49
        or not clave.isdigit()
    ):
        raise ValidacionSRIError(
            "La clave de acceso debe contener "
            "exactamente 49 dígitos."
        )

    esperado = (
        calcular_digito_verificador(
            clave[:48]
        )
    )

    if clave[-1] != esperado:
        raise ValidacionSRIError(
            "El dígito verificador de la "
            "clave de acceso es incorrecto."
        )

    return True


def validar_datos_emision(
    factura,
) -> bool:
    """
    Valida los datos fiscales que solo deben existir cuando
    la factura va a entrar al flujo de emisión.

    Un BORRADOR guardado puede existir sin secuencial y sin
    clave de acceso. Esta validación se usa desde la generación
    del XML en adelante.
    """
    validar_factura_guardada(
        factura
    )

    establecimiento = _texto(
        getattr(
            factura,
            "establecimiento",
            "",
        )
    )

    punto_emision = _texto(
        getattr(
            factura,
            "punto_emision",
            "",
        )
    )

    secuencial = _texto(
        getattr(
            factura,
            "secuencial",
            "",
        )
    )

    if (
        not establecimiento.isdigit()
        or len(establecimiento) != 3
    ):
        raise ConfiguracionSRIError(
            "El establecimiento debe tener "
            "exactamente 3 dígitos para emitir."
        )

    if (
        not punto_emision.isdigit()
        or len(punto_emision) != 3
    ):
        raise ConfiguracionSRIError(
            "El punto de emisión debe tener "
            "exactamente 3 dígitos para emitir."
        )

    if (
        not secuencial.isdigit()
        or len(secuencial) != 9
    ):
        raise ConfiguracionSRIError(
            "La factura todavía no tiene un "
            "secuencial fiscal válido de 9 dígitos."
        )

    validar_clave_acceso(
        getattr(
            factura,
            "clave_acceso",
            "",
        )
    )

    return True


# =========================================================
# FACTURA BASE
# =========================================================

def validar_factura_guardada(
    factura,
) -> bool:
    if factura is None:
        raise ValidacionSRIError(
            "No se recibió una factura."
        )

    if not getattr(
        factura,
        "pk",
        None,
    ):
        raise ValidacionSRIError(
            "La factura debe estar guardada "
            "antes de procesarla."
        )

    estado = _texto(
        getattr(
            factura,
            "estado",
            "",
        )
    )

    if estado not in ESTADOS_FACTURA:
        raise EstadoFacturaSRIError(
            f"Estado de factura no válido: "
            f"{estado or 'VACÍO'}."
        )

    return True


# =========================================================
# EMPRESA / EMISOR
# =========================================================

def validar_emisor(
    factura,
) -> bool:
    validar_factura_guardada(
        factura
    )

    if not getattr(
        factura,
        "sucursal_id",
        None,
    ):
        raise ConfiguracionSRIError(
            "La factura no tiene sucursal."
        )

    if not getattr(
        factura,
        "empresa_id",
        None,
    ):
        raise ConfiguracionSRIError(
            "La factura no tiene empresa emisora."
        )

    empresa = factura.empresa
    sucursal = factura.sucursal

    empresa_sucursal = getattr(
        sucursal,
        "empresa",
        None,
    )

    if (
        empresa_sucursal is not None
        and empresa_sucursal.pk
        != empresa.pk
    ):
        raise ConfiguracionSRIError(
            "La sucursal no pertenece a la "
            "empresa emisora de la factura."
        )

    ruc = _texto(
        getattr(
            empresa,
            "ruc",
            "",
        )
    )

    if (
        not ruc.isdigit()
        or len(ruc) != 13
    ):
        raise ConfiguracionSRIError(
            "El RUC del emisor debe tener "
            "exactamente 13 dígitos."
        )

    razon_social = _texto(
        getattr(
            empresa,
            "razon_social",
            "",
        )
    )

    if not razon_social:
        raise ConfiguracionSRIError(
            "La empresa emisora no tiene "
            "razón social configurada."
        )

    _validar_longitud_maxima(
        razon_social,
        300,
        "Razón social del emisor",
    )

    direccion_matriz = _texto(
        getattr(
            empresa,
            "dir_matriz",
            "",
        )
    )

    if not direccion_matriz:
        direccion_matriz = _texto(
            getattr(
                empresa,
                "direccion_matriz",
                "",
            )
        )

    if not direccion_matriz:
        raise ConfiguracionSRIError(
            "La empresa emisora no tiene "
            "dirección matriz configurada."
        )

    establecimiento = _texto(
        factura.establecimiento
    )

    if (
        not establecimiento.isdigit()
        or len(establecimiento) != 3
    ):
        raise ConfiguracionSRIError(
            "El establecimiento debe tener "
            "exactamente 3 dígitos."
        )

    punto_emision = _texto(
        factura.punto_emision
    )

    if (
        not punto_emision.isdigit()
        or len(punto_emision) != 3
    ):
        raise ConfiguracionSRIError(
            "El punto de emisión debe tener "
            "exactamente 3 dígitos."
        )

    if factura.ambiente not in {
        AMBIENTE_PRUEBAS,
        AMBIENTE_PRODUCCION,
    }:
        raise ConfiguracionSRIError(
            "El ambiente debe ser '1' "
            "(Pruebas) o '2' (Producción)."
        )

    if (
        factura.tipo_comprobante
        != TIPO_COMPROBANTE_FACTURA
    ):
        raise ConfiguracionSRIError(
            "El tipo de comprobante debe ser "
            "'01' para Factura."
        )

    if (
        factura.tipo_emision
        != TIPO_EMISION_NORMAL
    ):
        raise ConfiguracionSRIError(
            "El tipo de emisión soportado "
            "actualmente es '1' (Normal)."
        )

    if not getattr(
        factura,
        "fecha_emision",
        None,
    ):
        raise ValidacionSRIError(
            "La factura no tiene fecha "
            "de emisión."
        )

    return True


# =========================================================
# COMPRADOR
# =========================================================

def validar_comprador(
    factura,
) -> bool:
    validar_factura_guardada(
        factura
    )

    tipo = _texto(
        factura.tipo_identificacion_comprador
    )

    identificacion = _texto(
        factura.identificacion_comprador
    )

    razon_social = _texto(
        factura.razon_social_comprador
    )

    if (
        tipo
        not in TIPOS_IDENTIFICACION_SRI
    ):
        raise ValidacionSRIError(
            "Tipo de identificación del "
            "comprador no soportado."
        )

    if not razon_social:
        raise ValidacionSRIError(
            "La razón social o nombre del "
            "comprador es obligatorio."
        )

    _validar_longitud_maxima(
        razon_social,
        300,
        "Razón social del comprador",
    )

    if tipo == "04":
        if (
            not identificacion.isdigit()
            or len(identificacion) != 13
        ):
            raise ValidacionSRIError(
                "Para RUC, la identificación "
                "debe tener 13 dígitos."
            )

    elif tipo == "05":
        if (
            not identificacion.isdigit()
            or len(identificacion) != 10
        ):
            raise ValidacionSRIError(
                "Para cédula, la identificación "
                "debe tener 10 dígitos."
            )

    elif tipo == "06":
        if len(identificacion) < 3:
            raise ValidacionSRIError(
                "El pasaporte del comprador "
                "no es válido."
            )

    elif tipo == "07":
        if (
            identificacion
            != IDENTIFICACION_CONSUMIDOR_FINAL
        ):
            raise ValidacionSRIError(
                "Consumidor Final debe usar "
                "9999999999999."
            )

        if (
            _q2(factura.importe_total)
            > LIMITE_CONSUMIDOR_FINAL
        ):
            raise ValidacionSRIError(
                "Una factura superior a USD 50.00 "
                "no puede emitirse como "
                "Consumidor Final."
            )

    direccion = _texto(
        factura.direccion_comprador
    )

    telefono = _texto(
        factura.telefono_comprador
    )

    correo = _texto(
        factura.correo_comprador
    )

    _validar_longitud_maxima(
        direccion,
        500,
        "Dirección del comprador",
    )

    _validar_longitud_maxima(
        telefono,
        20,
        "Teléfono del comprador",
    )

    _validar_longitud_maxima(
        correo,
        254,
        "Correo del comprador",
    )

    return True


# =========================================================
# DETALLES
# =========================================================

def validar_detalles(
    factura,
) -> bool:
    validar_factura_guardada(
        factura
    )

    detalles = list(
        factura.detalles
        .all()
        .order_by("id")
    )

    if not detalles:
        raise ValidacionSRIError(
            "La factura no tiene detalles."
        )

    for detalle in detalles:
        identificador = (
            detalle.pk
            or "NUEVO"
        )

        codigo_principal = _texto(
            detalle.codigo_principal
        )

        if not codigo_principal:
            raise ValidacionSRIError(
                f"El detalle {identificador} "
                "no tiene código principal."
            )

        # XSD Factura 2.1.0
        _validar_longitud_maxima(
            codigo_principal,
            25,
            (
                f"Código principal del detalle "
                f"{identificador}"
            ),
        )

        codigo_auxiliar = _texto(
            detalle.codigo_auxiliar
        )

        if codigo_auxiliar:
            _validar_longitud_maxima(
                codigo_auxiliar,
                25,
                (
                    f"Código auxiliar del detalle "
                    f"{identificador}"
                ),
            )

        descripcion = _texto(
            detalle.descripcion
        )

        if not descripcion:
            raise ValidacionSRIError(
                f"El detalle {identificador} "
                "no tiene descripción."
            )

        _validar_longitud_maxima(
            descripcion,
            300,
            (
                f"Descripción del detalle "
                f"{identificador}"
            ),
        )

        cantidad = _d(
            detalle.cantidad
        )

        precio_unitario = _d(
            detalle.precio_unitario
        )

        descuento = _q2(
            detalle.descuento
        )

        if cantidad <= CERO:
            raise ValidacionSRIError(
                f"El detalle {identificador} "
                "debe tener cantidad mayor a cero."
            )

        if precio_unitario < CERO:
            raise ValidacionSRIError(
                f"El detalle {identificador} "
                "no puede tener precio unitario "
                "negativo."
            )

        subtotal_bruto = _q2(
            cantidad
            * precio_unitario
        )

        if descuento < CERO:
            raise ValidacionSRIError(
                f"El detalle {identificador} "
                "no puede tener descuento negativo."
            )

        if descuento > subtotal_bruto:
            raise ValidacionSRIError(
                f"El descuento del detalle "
                f"{identificador} supera su "
                "subtotal bruto."
            )

        base_calculada = _q2(
            subtotal_bruto
            - descuento
        )

        base_guardada = _q2(
            detalle.precio_total_sin_impuesto
        )

        if (
            base_calculada
            != base_guardada
        ):
            raise ValidacionSRIError(
                f"El detalle {identificador} "
                "tiene un precio total sin "
                "impuesto inconsistente. "
                f"Calculado: ${base_calculada} | "
                f"Guardado: ${base_guardada}."
            )

        base_imponible = _q2(
            detalle.base_imponible
        )

        if (
            base_imponible
            != base_guardada
        ):
            raise ValidacionSRIError(
                f"La base imponible del detalle "
                f"{identificador} no coincide "
                "con su precio total sin impuesto."
            )

        if (
            _texto(detalle.codigo_impuesto)
            != CODIGO_IMPUESTO_IVA
        ):
            raise ValidacionSRIError(
                f"El detalle {identificador} "
                "usa un código de impuesto "
                "no soportado."
            )

        codigo_porcentaje = _texto(
            detalle.codigo_porcentaje_iva
        )

        if (
            codigo_porcentaje
            not in TARIFAS_IVA_SOPORTADAS
        ):
            raise ValidacionSRIError(
                f"El detalle {identificador} "
                "usa una tarifa de IVA "
                "no soportada actualmente."
            )

        tarifa_esperada = (
            TARIFAS_IVA_SOPORTADAS[
                codigo_porcentaje
            ]
        )

        tarifa_guardada = _q2(
            detalle.tarifa_iva
        )

        if (
            tarifa_guardada
            != tarifa_esperada
        ):
            raise ValidacionSRIError(
                f"El detalle {identificador} "
                "tiene una tarifa de IVA "
                "inconsistente. "
                f"Código {codigo_porcentaje} "
                f"requiere {tarifa_esperada}%."
            )

        iva_esperado = CERO

        if tarifa_esperada > CERO:
            iva_esperado = _q2(
                base_guardada
                * tarifa_esperada
                / Decimal("100")
            )

        iva_guardado = _q2(
            detalle.valor_iva
        )

        if (
            iva_guardado
            != iva_esperado
        ):
            raise ValidacionSRIError(
                f"El IVA del detalle "
                f"{identificador} no coincide. "
                f"Calculado: ${iva_esperado} | "
                f"Guardado: ${iva_guardado}."
            )

    return True


# =========================================================
# TOTALES
# =========================================================

def validar_totales(
    factura,
) -> bool:
    validar_factura_guardada(
        factura
    )

    detalles = list(
        factura.detalles
        .all()
        .order_by("id")
    )

    if not detalles:
        raise ValidacionSRIError(
            "No se pueden validar los totales "
            "porque la factura no tiene detalles."
        )

    total_sin_impuestos = CERO
    total_descuento = CERO
    subtotal_gravado = CERO
    subtotal_iva_0 = CERO
    valor_iva = CERO

    for detalle in detalles:
        base = _q2(
            detalle.precio_total_sin_impuesto
        )

        descuento = _q2(
            detalle.descuento
        )

        iva = _q2(
            detalle.valor_iva
        )

        total_sin_impuestos += base
        total_descuento += descuento
        valor_iva += iva

        if (
            detalle.codigo_porcentaje_iva
            == "4"
        ):
            subtotal_gravado += base

        elif (
            detalle.codigo_porcentaje_iva
            == "0"
        ):
            subtotal_iva_0 += base

    total_sin_impuestos = _q2(
        total_sin_impuestos
    )

    total_descuento = _q2(
        total_descuento
    )

    subtotal_gravado = _q2(
        subtotal_gravado
    )

    subtotal_iva_0 = _q2(
        subtotal_iva_0
    )

    valor_iva = _q2(
        valor_iva
    )

    if (
        total_sin_impuestos
        != _q2(
            factura.total_sin_impuestos
        )
    ):
        raise ValidacionSRIError(
            "La suma de los detalles no coincide "
            "con total_sin_impuestos. "
            f"Detalles: ${total_sin_impuestos} | "
            f"Factura: "
            f"${_q2(factura.total_sin_impuestos)}."
        )

    if (
        total_descuento
        != _q2(
            factura.total_descuento
        )
    ):
        raise ValidacionSRIError(
            "La suma de descuentos de los "
            "detalles no coincide con "
            "total_descuento."
        )

    if (
        subtotal_gravado
        != _q2(
            factura.subtotal_gravado
        )
    ):
        raise ValidacionSRIError(
            "El subtotal gravado de los "
            "detalles no coincide con "
            "subtotal_gravado."
        )

    if (
        subtotal_iva_0
        != _q2(
            factura.subtotal_iva_0
        )
    ):
        raise ValidacionSRIError(
            "El subtotal IVA 0% de los "
            "detalles no coincide con "
            "subtotal_iva_0."
        )

    if (
        valor_iva
        != _q2(
            factura.valor_iva
        )
    ):
        raise ValidacionSRIError(
            "La suma del IVA de los detalles "
            "no coincide con valor_iva. "
            f"Detalles: ${valor_iva} | "
            f"Factura: ${_q2(factura.valor_iva)}."
        )

    propina = _q2(
        factura.propina
    )

    if propina < CERO:
        raise ValidacionSRIError(
            "La propina no puede ser negativa."
        )

    importe_esperado = _q2(
        total_sin_impuestos
        + valor_iva
        + propina
    )

    importe_guardado = _q2(
        factura.importe_total
    )

    if (
        importe_esperado
        != importe_guardado
    ):
        raise ValidacionSRIError(
            "El importe total no coincide con "
            "total sin impuestos + IVA + propina. "
            f"Calculado: ${importe_esperado} | "
            f"Guardado: ${importe_guardado}."
        )

    return True


# =========================================================
# PAGOS
# =========================================================

def validar_pagos(
    factura,
) -> bool:
    validar_factura_guardada(
        factura
    )

    pagos = list(
        factura.pagos
        .all()
        .order_by("id")
    )

    if not pagos:
        raise ValidacionSRIError(
            "La factura debe declarar al menos "
            "una forma de pago."
        )

    total_pagos = CERO

    for pago in pagos:
        identificador = (
            pago.pk
            or "NUEVO"
        )

        forma_pago = _texto(
            pago.forma_pago
        )

        if (
            forma_pago
            not in FORMAS_PAGO_SRI
        ):
            raise ValidacionSRIError(
                f"El pago {identificador} "
                "usa una forma de pago "
                "no soportada por el modelo."
            )

        total = _q2(
            pago.total
        )

        if total <= CERO:
            raise ValidacionSRIError(
                f"El pago {identificador} "
                "debe ser mayor a cero."
            )

        if (
            getattr(
                pago,
                "plazo",
                0,
            )
            is None
        ):
            raise ValidacionSRIError(
                f"El pago {identificador} "
                "no tiene plazo."
            )

        if pago.plazo < 0:
            raise ValidacionSRIError(
                f"El plazo del pago "
                f"{identificador} no puede "
                "ser negativo."
            )

        unidad = _texto(
            pago.unidad_tiempo
        )

        if not unidad:
            raise ValidacionSRIError(
                f"El pago {identificador} "
                "no tiene unidad de tiempo."
            )

        total_pagos += total

    total_pagos = _q2(
        total_pagos
    )

    importe_total = _q2(
        factura.importe_total
    )

    if (
        total_pagos
        != importe_total
    ):
        raise ValidacionSRIError(
            "La suma de las formas de pago "
            "debe ser igual al importe total. "
            f"Pagos: ${total_pagos} | "
            f"Factura: ${importe_total}."
        )

    return True


# =========================================================
# FIRMA ELECTRÓNICA
# =========================================================

def validar_firma_electronica(
    factura,
) -> bool:
    validar_factura_guardada(
        factura
    )

    firma = getattr(
        factura,
        "firma_electronica",
        None,
    )

    if firma is None:
        raise CertificadoFirmaError(
            "La factura no tiene firma "
            "electrónica asignada."
        )

    if (
        firma.empresa_id
        != factura.empresa_id
    ):
        raise CertificadoFirmaError(
            "La firma electrónica no pertenece "
            "a la empresa emisora."
        )

    ruc_firma = _texto(
        getattr(
            firma,
            "ruc",
            "",
        )
    )

    ruc_empresa = _texto(
        getattr(
            factura.empresa,
            "ruc",
            "",
        )
    )

    if (
        ruc_firma
        and ruc_empresa
        and ruc_firma != ruc_empresa
    ):
        raise CertificadoFirmaError(
            "El RUC de la firma electrónica "
            "no coincide con el RUC emisor."
        )

    if not getattr(
        firma,
        "archivo_firma",
        None,
    ):
        raise CertificadoFirmaError(
            "La firma electrónica no tiene "
            "archivo .p12/.pfx."
        )

    password = _texto(
        getattr(
            firma,
            "password_firma",
            "",
        )
    )

    if not password:
        raise CertificadoFirmaError(
            "La firma electrónica no tiene "
            "contraseña configurada."
        )

    if hasattr(
        firma,
        "esta_vigente",
    ):
        if not firma.esta_vigente():
            raise CertificadoFirmaError(
                "La firma electrónica no está "
                "activa o vigente."
            )

    return True


# =========================================================
# VALIDACIONES POR ETAPA
# =========================================================

def validar_factura_para_xml(
    factura,
) -> bool:
    """
    Requisitos para construir el XML tributario.

    Permite BORRADOR y GENERADO para facilitar
    regeneración antes de la firma.

    No permite modificar una factura que ya fue firmada
    o enviada.
    """

    validar_factura_guardada(
        factura
    )

    if factura.estado not in {
        "BORRADOR",
        "GENERADO",
        "RECHAZADO",
    }:
        raise EstadoFacturaSRIError(
            "Solo se puede generar o regenerar "
            "el XML de una factura BORRADOR, "
            "GENERADA o RECHAZADA."
        )

    validar_emisor(
        factura
    )

    validar_datos_emision(
        factura
    )

    validar_comprador(
        factura
    )

    validar_detalles(
        factura
    )

    validar_totales(
        factura
    )

    validar_pagos(
        factura
    )

    return True


def validar_factura_para_firma(
    factura,
) -> bool:
    """
    Requisitos para firmar factura.xml_generado.
    """

    validar_factura_guardada(
        factura
    )

    if factura.estado != "GENERADO":
        raise EstadoFacturaSRIError(
            "Solo se puede firmar una factura "
            "en estado GENERADO."
        )

    if not getattr(
        factura,
        "xml_generado",
        None,
    ):
        raise ValidacionSRIError(
            "La factura no tiene XML generado."
        )

    validar_emisor(
        factura
    )

    validar_datos_emision(
        factura
    )

    validar_comprador(
        factura
    )

    validar_detalles(
        factura
    )

    validar_totales(
        factura
    )

    validar_pagos(
        factura
    )

    validar_firma_electronica(
        factura
    )

    return True


def validar_factura_para_envio(
    factura,
) -> bool:
    """
    Requisitos para enviar al WS de recepción SRI.
    """

    validar_factura_guardada(
        factura
    )

    if factura.estado not in {
        "FIRMADO",
        "RECHAZADO",
    }:
        raise EstadoFacturaSRIError(
            "La factura debe estar FIRMADA "
            "antes de enviarla al SRI."
        )

    if not getattr(
        factura,
        "xml_firmado",
        None,
    ):
        raise ValidacionSRIError(
            "La factura no tiene XML firmado."
        )

    validar_emisor(
        factura
    )

    validar_datos_emision(
        factura
    )

    return True


def validar_factura_para_consulta(
    factura,
) -> bool:
    """
    Requisitos para consultar autorización por
    clave de acceso.
    """

    validar_factura_guardada(
        factura
    )

    if factura.estado == "AUTORIZADO":
        raise EstadoFacturaSRIError(
            "La factura ya está AUTORIZADA."
        )

    if factura.estado not in {
        "RECIBIDO",
        "RECHAZADO",
        "FIRMADO",
    }:
        raise EstadoFacturaSRIError(
            "La factura todavía no está en un "
            "estado válido para consultar "
            "autorización."
        )

    validar_datos_emision(
        factura
    )

    return True


# =========================================================
# VALIDACIÓN GENERAL
# =========================================================

def validar_factura_para_sri(
    factura,
) -> bool:
    """
    Alias general para validar todos los datos necesarios
    antes de generar el XML.
    """

    return validar_factura_para_xml(
        factura
    )


# =========================================================
# DIAGNÓSTICO
# =========================================================

def diagnosticar_factura(
    factura,
) -> dict:
    """
    Ejecuta grupos de validación y devuelve un diagnóstico
    sin detenerse en el primer grupo que falle.

    Ejemplo:
        {
            "valida": False,
            "emisor": {"ok": True, "error": ""},
            "comprador": {"ok": False, "error": "..."},
            ...
        }
    """

    grupos = [
        (
            "factura",
            validar_factura_guardada,
        ),
        (
            "emisor",
            validar_emisor,
        ),
        (
            "emision",
            validar_datos_emision,
        ),
        (
            "comprador",
            validar_comprador,
        ),
        (
            "detalles",
            validar_detalles,
        ),
        (
            "totales",
            validar_totales,
        ),
        (
            "pagos",
            validar_pagos,
        ),
        (
            "firma",
            validar_firma_electronica,
        ),
    ]

    resultado = {
        "valida": True,
    }

    for nombre, funcion in grupos:
        try:
            funcion(
                factura
            )

            resultado[nombre] = {
                "ok": True,
                "error": "",
            }

        except Exception as exc:
            resultado[nombre] = {
                "ok": False,
                "error": str(exc),
            }

            resultado["valida"] = False

    return resultado


__all__ = [
    "AMBIENTE_PRUEBAS",
    "AMBIENTE_PRODUCCION",
    "IDENTIFICACION_CONSUMIDOR_FINAL",
    "LIMITE_CONSUMIDOR_FINAL",
    "calcular_digito_verificador",
    "validar_clave_acceso",
    "validar_datos_emision",
    "validar_factura_guardada",
    "validar_emisor",
    "validar_comprador",
    "validar_detalles",
    "validar_totales",
    "validar_pagos",
    "validar_firma_electronica",
    "validar_factura_para_xml",
    "validar_factura_para_firma",
    "validar_factura_para_envio",
    "validar_factura_para_consulta",
    "validar_factura_para_sri",
    "diagnosticar_factura",
]