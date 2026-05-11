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

    const subtotal = rep + moi + moe;

    const iva = subtotal * 0.15;

    const total = subtotal + iva;

    // =========================================
    // TABLAS
    // =========================================
    const subtotalRep = document.getElementById('subtotalRepuestos');

    if (subtotalRep) {
        subtotalRep.textContent = rep.toFixed(2);
    }

    const subtotalMOI = document.getElementById('subtotalMOI');

    if (subtotalMOI) {
        subtotalMOI.textContent = moi.toFixed(2);
    }

    const subtotalMOE = document.getElementById('subtotalMOE');

    if (subtotalMOE) {
        subtotalMOE.textContent = moe.toFixed(2);
    }

    // =========================================
    // RESUMEN
    // =========================================
    const resumenRep = document.getElementById('resumenRep');

    if (resumenRep) {
        resumenRep.textContent = rep.toFixed(2);
    }

    const resumenMOI = document.getElementById('resumenMOI');

    if (resumenMOI) {
        resumenMOI.textContent = moi.toFixed(2);
    }

    const resumenMOE = document.getElementById('resumenMOE');

    if (resumenMOE) {
        resumenMOE.textContent = moe.toFixed(2);
    }

    const subtotalGeneral = document.getElementById('subtotalGeneral');

    if (subtotalGeneral) {
        subtotalGeneral.textContent = subtotal.toFixed(2);
    }

    const ivaTotal = document.getElementById('ivaTotal');

    if (ivaTotal) {
        ivaTotal.textContent = iva.toFixed(2);
    }

    const granTotal = document.getElementById('granTotal');

    if (granTotal) {
        granTotal.textContent = total.toFixed(2);
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