function numeroSeguro(valor) {

    if (!valor) return 0;

    valor = valor.toString().replace(',', '.');

    const n = parseFloat(valor);

    return isNaN(n) ? 0 : n;
}

function recalcularFilaDesdeTr(fila) {

    if (!fila) return;

    const pu = numeroSeguro(
        fila.querySelector('.pu')?.value
    );

    const cantidad = numeroSeguro(
        fila.querySelector('.cantidad')?.value
    );

    const campoValor = fila.querySelector('.valor');

    if (campoValor) {
        campoValor.value = (
            pu * cantidad
        ).toFixed(2);
    }
}

function calcularFila(elemento) {

    recalcularFilaDesdeTr(
        elemento.closest('tr')
    );

    recalcularTotales();
}

function sumarTabla(idTabla) {

    let total = 0;

    document.querySelectorAll(
        `#${idTabla} tbody tr`
    ).forEach(fila => {

        const valInput = fila.querySelector('.valor');

        if (valInput) {

            total += numeroSeguro(
                valInput.value
            );
        }

    });

    return total;
}
function validarDescuento() {
    const tipoCampo = document.getElementById(
        'tipo_descuento'
    );

    const descuentoCampo = document.getElementById(
        'descuento_ingresado'
    );

    const subtotalElemento = document.getElementById(
        'subtotalGeneral'
    );

    if (
        !tipoCampo ||
        !descuentoCampo ||
        !subtotalElemento
    ) {
        return {
            valido: true,
            mensaje: ''
        };
    }

    const tipo = tipoCampo.value;
    const descuento = Number(
        String(descuentoCampo.value)
            .replace(',', '.')
    );

    const subtotal = Number(
        String(subtotalElemento.textContent)
            .replace(',', '.')
            .trim()
    );

    if (!Number.isFinite(descuento)) {
        return {
            valido: false,
            mensaje: 'Ingrese un descuento válido.'
        };
    }

    if (descuento < 0) {
        return {
            valido: false,
            mensaje: 'El descuento no puede ser negativo.'
        };
    }

    if (subtotal <= 0 && descuento > 0) {
        return {
            valido: false,
            mensaje: (
                'No se puede aplicar un descuento ' +
                'cuando el subtotal es cero.'
            )
        };
    }

    if (
        tipo === 'PORCENTAJE' &&
        descuento > 100
    ) {
        return {
            valido: false,
            mensaje: (
                'El descuento porcentual no puede ' +
                'superar el 100%.'
            )
        };
    }

    if (
        tipo === 'VALOR_FIJO' &&
        descuento > subtotal
    ) {
        return {
            valido: false,
            mensaje: (
                'El descuento fijo no puede superar ' +
                'el subtotal de la orden.'
            )
        };
    }

    return {
        valido: true,
        mensaje: ''
    };
}
function recalcularTotales() {
    const rep = sumarTabla('tablaRepuestos');
    const moi = sumarTabla('tablaMOI');
    const moe = sumarTabla('tablaMOE');

    const subtotalSinIva = rep + moi + moe;

    const porcentajeIva = numeroSeguro(
        document.getElementById('porcentajeIva')?.value
    );

    const tipoDescuento = (
        document.getElementById('tipo_descuento')?.value
        || 'PORCENTAJE'
    );

    let descuentoIngresado = numeroSeguro(
        document.getElementById('descuento_ingresado')?.value
    );

    if (descuentoIngresado < 0) {
        descuentoIngresado = 0;
    }

    let valorDescuento = 0;
    let porcentajeDescuento = 0;

    if (tipoDescuento === 'VALOR_FIJO') {
        valorDescuento = descuentoIngresado;

        if (valorDescuento > subtotalSinIva) {
            valorDescuento = subtotalSinIva;
        }

        porcentajeDescuento = subtotalSinIva > 0
            ? (valorDescuento / subtotalSinIva) * 100
            : 0;
    } else {
        porcentajeDescuento = descuentoIngresado;

        if (porcentajeDescuento > 100) {
            porcentajeDescuento = 100;
        }

        valorDescuento = (
            subtotalSinIva
            * porcentajeDescuento
            / 100
        );
    }

    let baseImponible = subtotalSinIva - valorDescuento;

    if (baseImponible < 0) {
        baseImponible = 0;
    }

    const iva = baseImponible * (porcentajeIva / 100);

    const sumarIvaAlTotal = (
        document.getElementById(
            'sumar_iva_al_total'
        )?.checked ?? true
    );

    const totalFinal = sumarIvaAlTotal
        ? baseImponible + iva
        : baseImponible;

    const subtotalRep = document.getElementById(
        'subtotalRepuestos'
    );

    if (subtotalRep) {
        subtotalRep.textContent = rep.toFixed(2);
    }

    const subtotalMOI = document.getElementById(
        'subtotalMOI'
    );

    if (subtotalMOI) {
        subtotalMOI.textContent = moi.toFixed(2);
    }

    const subtotalMOE = document.getElementById(
        'subtotalMOE'
    );

    if (subtotalMOE) {
        subtotalMOE.textContent = moe.toFixed(2);
    }

    const resumenRep = document.getElementById(
        'resumenRep'
    );

    if (resumenRep) {
        resumenRep.textContent = rep.toFixed(2);
    }

    const resumenMOI = document.getElementById(
        'resumenMOI'
    );

    if (resumenMOI) {
        resumenMOI.textContent = moi.toFixed(2);
    }

    const resumenMOE = document.getElementById(
        'resumenMOE'
    );

    if (resumenMOE) {
        resumenMOE.textContent = moe.toFixed(2);
    }

    const subtotalGeneral = document.getElementById(
        'subtotalGeneral'
    );

    if (subtotalGeneral) {
        subtotalGeneral.textContent = (
            subtotalSinIva.toFixed(2)
        );
    }

    const descuentoTotal = document.getElementById(
        'descuentoTotal'
    );

    if (descuentoTotal) {
        descuentoTotal.textContent = (
            valorDescuento.toFixed(2)
        );
    }

    const descuentoPorcentajeTexto = document.getElementById(
        'descuentoPorcentajeTexto'
    );

    if (descuentoPorcentajeTexto) {
        descuentoPorcentajeTexto.textContent = (
            `${porcentajeDescuento.toFixed(2)}%`
        );
    }

    const descuentoValorTexto = document.getElementById(
        'descuentoValorTexto'
    );

    if (descuentoValorTexto) {
        descuentoValorTexto.textContent = (
            `$${valorDescuento.toFixed(2)}`
        );
    }

    const ivaLabel = document.getElementById(
        'ivaLabel'
    );

    if (ivaLabel) {
        ivaLabel.textContent = (
            `IVA ${porcentajeIva.toFixed(2)}%`
        );
    }

    const ivaTotal = document.getElementById(
        'ivaTotal'
    );

    if (ivaTotal) {
        ivaTotal.textContent = iva.toFixed(2);
    }

    const granTotal = document.getElementById(
        'granTotal'
    );

    if (granTotal) {
        granTotal.textContent = totalFinal.toFixed(2);
    }
}
function eliminarFila(boton) {

    const fila = boton.closest('tr');

    if (!fila) return;

    // =========================================
    // MANO DE OBRA INTERNA
    // =========================================
    if (
        fila.classList.contains('fila-padre-moi')
    ) {

        const filaHijas = fila.nextElementSibling;

        if (
            filaHijas &&
            filaHijas.classList.contains('fila-hijas-moi')
        ) {

            filaHijas.remove();
        }
    }

    fila.remove();

    recalcularTotales();
}

function escaparHTML(valor) {

    return String(valor ?? '')
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}