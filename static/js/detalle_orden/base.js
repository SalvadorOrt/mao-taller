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
function contarFilasTabla(idTabla) {
    let cantidad = 0;

    document.querySelectorAll(
        `#${idTabla} tbody tr`
    ).forEach(function (fila) {
        /*
         * Solo contamos filas económicas reales.
         *
         * Las filas auxiliares, procedimientos,
         * mensajes vacíos o filas hijas normalmente
         * no contienen un campo con clase .valor.
         */
        const campoValor = fila.querySelector(
            '.valor'
        );

        if (!campoValor) {
            return;
        }

        /*
         * No contar filas eliminadas u ocultas.
         */
        if (
            fila.hidden ||
            fila.style.display === 'none'
        ) {
            return;
        }

        cantidad += 1;
    });

    return cantidad;
}

function calcularPorcentajeParte(
    valorParte,
    subtotalGeneral
) {
    if (
        subtotalGeneral <= 0 ||
        valorParte <= 0
    ) {
        return 0;
    }

    return (
        valorParte /
        subtotalGeneral
    ) * 100;
}

function textoCantidad(
    cantidad,
    singular,
    plural
) {
    return cantidad === 1
        ? `1 ${singular}`
        : `${cantidad} ${plural}`;
}

function actualizarComposicionOrden({
    rep,
    moi,
    moe,
    subtotalSinIva
}) {
    const porcentajeRep =
        calcularPorcentajeParte(
            rep,
            subtotalSinIva
        );

    const porcentajeMOI =
        calcularPorcentajeParte(
            moi,
            subtotalSinIva
        );

    const porcentajeMOE =
        calcularPorcentajeParte(
            moe,
            subtotalSinIva
        );

    const cantidadRep =
        contarFilasTabla(
            'tablaRepuestos'
        );

    const cantidadMOI =
        contarFilasTabla(
            'tablaMOI'
        );

    const cantidadMOE =
        contarFilasTabla(
            'tablaMOE'
        );

    const elementoPorcentajeRep =
        document.getElementById(
            'porcentajeRep'
        );

    if (elementoPorcentajeRep) {
        elementoPorcentajeRep.textContent =
            `${porcentajeRep.toFixed(2)}%`;
    }

    const elementoPorcentajeMOI =
        document.getElementById(
            'porcentajeMOI'
        );

    if (elementoPorcentajeMOI) {
        elementoPorcentajeMOI.textContent =
            `${porcentajeMOI.toFixed(2)}%`;
    }

    const elementoPorcentajeMOE =
        document.getElementById(
            'porcentajeMOE'
        );

    if (elementoPorcentajeMOE) {
        elementoPorcentajeMOE.textContent =
            `${porcentajeMOE.toFixed(2)}%`;
    }

    const elementoCantidadRep =
        document.getElementById(
            'cantidadRep'
        );

    if (elementoCantidadRep) {
        elementoCantidadRep.textContent =
            textoCantidad(
                cantidadRep,
                'producto',
                'productos'
            );
    }

    const elementoCantidadMOI =
        document.getElementById(
            'cantidadMOI'
        );

    if (elementoCantidadMOI) {
        elementoCantidadMOI.textContent =
            textoCantidad(
                cantidadMOI,
                'servicio',
                'servicios'
            );
    }

    const elementoCantidadMOE =
        document.getElementById(
            'cantidadMOE'
        );

    if (elementoCantidadMOE) {
        elementoCantidadMOE.textContent =
            textoCantidad(
                cantidadMOE,
                'servicio',
                'servicios'
            );
    }

    const barraRep =
        document.getElementById(
            'barraRep'
        );

    if (barraRep) {
        barraRep.style.width =
            `${Math.min(
                porcentajeRep,
                100
            ).toFixed(2)}%`;
    }

    const barraMOI =
        document.getElementById(
            'barraMOI'
        );

    if (barraMOI) {
        barraMOI.style.width =
            `${Math.min(
                porcentajeMOI,
                100
            ).toFixed(2)}%`;
    }

    const barraMOE =
        document.getElementById(
            'barraMOE'
        );

    if (barraMOE) {
        barraMOE.style.width =
            `${Math.min(
                porcentajeMOE,
                100
            ).toFixed(2)}%`;
    }
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

function mostrarEstadoDescuento() {
    const campo = document.getElementById(
        'descuento_ingresado'
    );

    const mensaje = document.getElementById(
        'descuentoError'
    );

    if (!campo) {
        return true;
    }

    const validacion = validarDescuento();

    campo.setCustomValidity(
        validacion.valido
            ? ''
            : validacion.mensaje
    );

    campo.classList.toggle(
        'is-invalid',
        !validacion.valido
    );

    campo.setAttribute(
        'aria-invalid',
        validacion.valido
            ? 'false'
            : 'true'
    );

    if (mensaje) {
        mensaje.textContent =
            validacion.mensaje;

        mensaje.classList.toggle(
            'visible',
            !validacion.valido
        );
    }

    return validacion.valido;
}
function contarItemsTabla(idTabla) {
    const tabla = document.getElementById(
        idTabla
    );

    if (!tabla) {
        return 0;
    }

    let cantidad = 0;

    tabla.querySelectorAll(
        'tbody tr'
    ).forEach(function (fila) {
        /*
         * Una fila económica real debe contener
         * cantidad, precio unitario o valor.
         *
         * Esto evita contar filas auxiliares,
         * procedimientos y mensajes vacíos.
         */
        const campoCantidad =
            fila.querySelector('.cantidad');

        const campoPrecio =
            fila.querySelector('.pu');

        const campoValor =
            fila.querySelector('.valor');

        const esFilaEconomica = Boolean(
            campoCantidad ||
            campoPrecio ||
            campoValor
        );

        if (!esFilaEconomica) {
            return;
        }

        /*
         * No contar filas hijas de procedimientos
         * de mano de obra interna.
         */
        if (
            fila.classList.contains(
                'fila-hijas-moi'
            )
        ) {
            return;
        }

        /*
         * No contar filas eliminadas u ocultas.
         */
        if (
            fila.hidden ||
            fila.style.display === 'none'
        ) {
            return;
        }

        cantidad += 1;
    });

    return cantidad;
}

function calcularPorcentajeComposicion(
    valor,
    subtotal
) {
    valor = numeroSeguro(valor);
    subtotal = numeroSeguro(subtotal);

    if (subtotal <= 0) {
        return 0;
    }

    return (
        valor /
        subtotal
    ) * 100;
}

function formarTextoCantidad(
    cantidad,
    singular,
    plural
) {
    return cantidad === 1
        ? `1 ${singular}`
        : `${cantidad} ${plural}`;
}

function actualizarDatoComposicion({
    porcentajeId,
    cantidadId,
    barraId,
    porcentaje,
    cantidad,
    singular,
    plural
}) {
    const porcentajeElemento =
        document.getElementById(
            porcentajeId
        );

    const cantidadElemento =
        document.getElementById(
            cantidadId
        );

    const barraElemento =
        document.getElementById(
            barraId
        );

    if (porcentajeElemento) {
        porcentajeElemento.textContent =
            `${porcentaje.toFixed(2)}%`;
    }

    if (cantidadElemento) {
        cantidadElemento.textContent =
            formarTextoCantidad(
                cantidad,
                singular,
                plural
            );
    }

    if (barraElemento) {
        const ancho = Math.min(
            Math.max(porcentaje, 0),
            100
        );

        barraElemento.style.width =
            `${ancho.toFixed(2)}%`;
    }
}

function actualizarComposicionOrden(
    rep,
    moi,
    moe,
    subtotalSinIva
) {
    const porcentajeRep =
        calcularPorcentajeComposicion(
            rep,
            subtotalSinIva
        );

    const porcentajeMOI =
        calcularPorcentajeComposicion(
            moi,
            subtotalSinIva
        );

    const porcentajeMOE =
        calcularPorcentajeComposicion(
            moe,
            subtotalSinIva
        );

    const cantidadRep =
        contarItemsTabla(
            'tablaRepuestos'
        );

    const cantidadMOI =
        contarItemsTabla(
            'tablaMOI'
        );

    const cantidadMOE =
        contarItemsTabla(
            'tablaMOE'
        );

    actualizarDatoComposicion({
        porcentajeId: 'porcentajeRep',
        cantidadId: 'cantidadRep',
        barraId: 'barraRep',
        porcentaje: porcentajeRep,
        cantidad: cantidadRep,
        singular: 'producto',
        plural: 'productos'
    });

    actualizarDatoComposicion({
        porcentajeId: 'porcentajeMOI',
        cantidadId: 'cantidadMOI',
        barraId: 'barraMOI',
        porcentaje: porcentajeMOI,
        cantidad: cantidadMOI,
        singular: 'servicio',
        plural: 'servicios'
    });

    actualizarDatoComposicion({
        porcentajeId: 'porcentajeMOE',
        cantidadId: 'cantidadMOE',
        barraId: 'barraMOE',
        porcentaje: porcentajeMOE,
        cantidad: cantidadMOE,
        singular: 'servicio',
        plural: 'servicios'
    });
}
function recalcularTotales() {
    const rep = sumarTabla(
        'tablaRepuestos'
    );

    const moi = sumarTabla(
        'tablaMOI'
    );

    const moe = sumarTabla(
        'tablaMOE'
    );

    const subtotalSinIva =
        rep + moi + moe;

    actualizarComposicionOrden(
        rep,
        moi,
        moe,
        subtotalSinIva
    );

    const porcentajeIva = numeroSeguro(
        document.getElementById(
            'porcentajeIva'
        )?.value
    );

    const tipoDescuento = (
        document.getElementById(
            'tipo_descuento'
        )?.value ||
        'PORCENTAJE'
    );

    let descuentoIngresado =
        numeroSeguro(
            document.getElementById(
                'descuento_ingresado'
            )?.value
        );

    if (descuentoIngresado < 0) {
        descuentoIngresado = 0;
    }

    let valorDescuento = 0;
    let porcentajeDescuento = 0;

    if (
        tipoDescuento ===
        'VALOR_FIJO'
    ) {
        valorDescuento =
            descuentoIngresado;

        if (
            valorDescuento >
            subtotalSinIva
        ) {
            valorDescuento =
                subtotalSinIva;
        }

        porcentajeDescuento =
            subtotalSinIva > 0
                ? (
                    valorDescuento /
                    subtotalSinIva
                ) * 100
                : 0;
    } else {
        porcentajeDescuento =
            descuentoIngresado;

        if (
            porcentajeDescuento >
            100
        ) {
            porcentajeDescuento = 100;
        }

        valorDescuento = (
            subtotalSinIva *
            porcentajeDescuento /
            100
        );
    }

    let baseImponible =
        subtotalSinIva -
        valorDescuento;

    if (baseImponible < 0) {
        baseImponible = 0;
    }

    const iva =
        baseImponible *
        (
            porcentajeIva /
            100
        );

    const sumarIvaAlTotal = (
        document.getElementById(
            'sumar_iva_al_total'
        )?.checked ?? true
    );

    const totalFinal =
        sumarIvaAlTotal
            ? baseImponible + iva
            : baseImponible;

    const subtotalRep =
        document.getElementById(
            'subtotalRepuestos'
        );

    if (subtotalRep) {
        subtotalRep.textContent =
            rep.toFixed(2);
    }

    const subtotalMOI =
        document.getElementById(
            'subtotalMOI'
        );

    if (subtotalMOI) {
        subtotalMOI.textContent =
            moi.toFixed(2);
    }

    const subtotalMOE =
        document.getElementById(
            'subtotalMOE'
        );

    if (subtotalMOE) {
        subtotalMOE.textContent =
            moe.toFixed(2);
    }

    const resumenRep =
        document.getElementById(
            'resumenRep'
        );

    if (resumenRep) {
        resumenRep.textContent =
            rep.toFixed(2);
    }

    const resumenMOI =
        document.getElementById(
            'resumenMOI'
        );

    if (resumenMOI) {
        resumenMOI.textContent =
            moi.toFixed(2);
    }

    const resumenMOE =
        document.getElementById(
            'resumenMOE'
        );

    if (resumenMOE) {
        resumenMOE.textContent =
            moe.toFixed(2);
    }

    const subtotalGeneral =
        document.getElementById(
            'subtotalGeneral'
        );

    if (subtotalGeneral) {
        subtotalGeneral.textContent =
            subtotalSinIva.toFixed(2);
    }

    const descuentoTotal =
        document.getElementById(
            'descuentoTotal'
        );

    if (descuentoTotal) {
        descuentoTotal.textContent =
            valorDescuento.toFixed(2);
    }

    const descuentoPorcentajeTexto =
        document.getElementById(
            'descuentoPorcentajeTexto'
        );

    if (
        descuentoPorcentajeTexto
    ) {
        descuentoPorcentajeTexto
            .textContent =
            `${porcentajeDescuento
                .toFixed(2)}%`;
    }

    const descuentoValorTexto =
        document.getElementById(
            'descuentoValorTexto'
        );

    if (descuentoValorTexto) {
        descuentoValorTexto.textContent =
            `$${valorDescuento
                .toFixed(2)}`;
    }

    const ivaLabel =
        document.getElementById(
            'ivaLabel'
        );

    if (ivaLabel) {
        ivaLabel.textContent =
            `IVA ${porcentajeIva
                .toFixed(2)}%`;
    }

    const ivaTotal =
        document.getElementById(
            'ivaTotal'
        );

    if (ivaTotal) {
        ivaTotal.textContent =
            iva.toFixed(2);
    }

    const granTotal =
        document.getElementById(
            'granTotal'
        );

    if (granTotal) {
        granTotal.textContent =
            totalFinal.toFixed(2);
    }

    mostrarEstadoDescuento();
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