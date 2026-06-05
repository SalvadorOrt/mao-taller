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
function recalcularTotales() {

    const rep = sumarTabla('tablaRepuestos');
    const moi = sumarTabla('tablaMOI');
    const moe = sumarTabla('tablaMOE');

    const subtotalSinIva = rep + moi + moe;

    const porcentajeIva = numeroSeguro(
        document.getElementById('porcentajeIva')?.value
    );

    const porcentajeDescuento = numeroSeguro(
        document.getElementById('descuento_porcentaje')?.value
    );

    const valorDescuento = subtotalSinIva * (porcentajeDescuento / 100);

    let baseImponible = subtotalSinIva - valorDescuento;

    if (baseImponible < 0) {
        baseImponible = 0;
    }

    const iva = baseImponible * (porcentajeIva / 100);

    const totalFinal = baseImponible + iva;

    const subtotalRep = document.getElementById('subtotalRepuestos');
    if (subtotalRep) subtotalRep.textContent = rep.toFixed(2);

    const subtotalMOI = document.getElementById('subtotalMOI');
    if (subtotalMOI) subtotalMOI.textContent = moi.toFixed(2);

    const subtotalMOE = document.getElementById('subtotalMOE');
    if (subtotalMOE) subtotalMOE.textContent = moe.toFixed(2);

    const resumenRep = document.getElementById('resumenRep');
    if (resumenRep) resumenRep.textContent = rep.toFixed(2);

    const resumenMOI = document.getElementById('resumenMOI');
    if (resumenMOI) resumenMOI.textContent = moi.toFixed(2);

    const resumenMOE = document.getElementById('resumenMOE');
    if (resumenMOE) resumenMOE.textContent = moe.toFixed(2);

    const subtotalGeneral = document.getElementById('subtotalGeneral');
    if (subtotalGeneral) subtotalGeneral.textContent = subtotalSinIva.toFixed(2);

    const descuentoTotal = document.getElementById('descuentoTotal');
    if (descuentoTotal) descuentoTotal.textContent = valorDescuento.toFixed(2);

    const ivaLabel = document.getElementById('ivaLabel');
    if (ivaLabel) ivaLabel.textContent = `IVA ${porcentajeIva.toFixed(2)}%`;

    const ivaTotal = document.getElementById('ivaTotal');
    if (ivaTotal) ivaTotal.textContent = iva.toFixed(2);

    const granTotal = document.getElementById('granTotal');
    if (granTotal) granTotal.textContent = totalFinal.toFixed(2);
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