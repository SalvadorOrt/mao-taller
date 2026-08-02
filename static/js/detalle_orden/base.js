function numeroSeguro(valor) {
    if (
        valor === null ||
        valor === undefined ||
        valor === ''
    ) {
        return 0;
    }

    const valorNormalizado = String(valor)
        .trim()
        .replace(',', '.');

    const numero = parseFloat(
        valorNormalizado
    );

    return Number.isFinite(numero)
        ? numero
        : 0;
}


// =====================================================
// CÁLCULO POR FILA
// =====================================================
function recalcularFilaDesdeTr(fila) {
    if (!fila) {
        return;
    }

    if (filaEstaEliminada(fila)) {
        return;
    }

    const precioUnitario = numeroSeguro(
        fila.querySelector('.pu')?.value
    );

    const cantidad = numeroSeguro(
        fila.querySelector('.cantidad')?.value
    );

    const campoValor =
        fila.querySelector('.valor');

    if (!campoValor) {
        return;
    }

    campoValor.value = (
        precioUnitario *
        cantidad
    ).toFixed(2);
}


function calcularFila(elemento) {
    if (!elemento) {
        return;
    }

    const fila = elemento.closest('tr');

    recalcularFilaDesdeTr(
        fila
    );

    recalcularTotales();
}


// =====================================================
// FILAS ELIMINADAS
// =====================================================
function filaEstaEliminada(fila) {
    if (!fila) {
        return true;
    }

    if (
        fila.classList.contains(
            'fila-eliminada'
        ) ||
        fila.classList.contains(
            'eliminado'
        ) ||
        fila.dataset.eliminada === '1'
    ) {
        return true;
    }

    if (
        fila.hidden ||
        fila.style.display === 'none'
    ) {
        return true;
    }

    /*
     * Formsets tradicionales de Django:
     * ejemplo: repuestos-0-DELETE
     */
    const campoDeleteFormset =
        fila.querySelector(
            'input[name$="-DELETE"]'
        );

    if (
        campoDeleteFormset &&
        campoDeleteFormset.checked
    ) {
        return true;
    }

    /*
     * Estructura personalizada actual:
     * rep_delete[]
     * moi_delete[]
     * moe_delete[]
     */
    const campoDeletePersonalizado =
        fila.querySelector(
            [
                'input[name="rep_delete[]"]',
                'input[name="moi_delete[]"]',
                'input[name="moe_delete[]"]',
                'input[name*="eliminar"]',
                'input[name*="eliminado"]',
                'input[data-delete-field]'
            ].join(',')
        );

    if (campoDeletePersonalizado) {
        const valor = String(
            campoDeletePersonalizado.value ?? ''
        )
            .trim()
            .toLowerCase();

        if (
            campoDeletePersonalizado.checked ||
            valor === '1' ||
            valor === 'true'
        ) {
            return true;
        }
    }

    return false;
}


// =====================================================
// SUMA DE TABLAS
// =====================================================
function sumarTabla(idTabla) {
    const tabla = document.getElementById(
        idTabla
    );

    if (!tabla) {
        return 0;
    }

    let total = 0;

    tabla.querySelectorAll(
        'tbody tr'
    ).forEach(function (fila) {
        if (filaEstaEliminada(fila)) {
            return;
        }

        /*
         * Las filas hijas de procedimientos
         * no tienen valor económico propio.
         */
        if (
            fila.classList.contains(
                'fila-hijas-moi'
            )
        ) {
            return;
        }

        const campoValor =
            fila.querySelector('.valor');

        if (!campoValor) {
            return;
        }

        total += numeroSeguro(
            campoValor.value
        );
    });

    return total;
}


// =====================================================
// CONTEO DE PRODUCTOS Y SERVICIOS
// =====================================================
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
        if (filaEstaEliminada(fila)) {
            return;
        }

        if (
            fila.classList.contains(
                'fila-hijas-moi'
            )
        ) {
            return;
        }

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

        cantidad += 1;
    });

    return cantidad;
}


// =====================================================
// COMPOSICIÓN ECONÓMICA
// =====================================================
function calcularPorcentajeComposicion(
    valor,
    subtotal
) {
    const valorSeguro =
        numeroSeguro(valor);

    const subtotalSeguro =
        numeroSeguro(subtotal);

    if (
        subtotalSeguro <= 0 ||
        valorSeguro <= 0
    ) {
        return 0;
    }

    return (
        valorSeguro /
        subtotalSeguro
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
            Math.max(
                porcentaje,
                0
            ),
            100
        );

        barraElemento.style.width =
            `${ancho.toFixed(2)}%`;
    }
}


function actualizarComposicionOrden(
    repuestos,
    manoObraInterna,
    manoObraExterna,
    subtotalSinIva
) {
    const porcentajeRepuestos =
        calcularPorcentajeComposicion(
            repuestos,
            subtotalSinIva
        );

    const porcentajeMOI =
        calcularPorcentajeComposicion(
            manoObraInterna,
            subtotalSinIva
        );

    const porcentajeMOE =
        calcularPorcentajeComposicion(
            manoObraExterna,
            subtotalSinIva
        );

    const cantidadRepuestos =
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
        porcentaje:
            porcentajeRepuestos,
        cantidad:
            cantidadRepuestos,
        singular: 'producto',
        plural: 'productos'
    });

    actualizarDatoComposicion({
        porcentajeId: 'porcentajeMOI',
        cantidadId: 'cantidadMOI',
        barraId: 'barraMOI',
        porcentaje:
            porcentajeMOI,
        cantidad:
            cantidadMOI,
        singular: 'servicio',
        plural: 'servicios'
    });

    actualizarDatoComposicion({
        porcentajeId: 'porcentajeMOE',
        cantidadId: 'cantidadMOE',
        barraId: 'barraMOE',
        porcentaje:
            porcentajeMOE,
        cantidad:
            cantidadMOE,
        singular: 'servicio',
        plural: 'servicios'
    });
}


// =====================================================
// DESCUENTO
// =====================================================
function validarDescuento() {
    const tipoCampo =
        document.getElementById(
            'tipo_descuento'
        );

    const descuentoCampo =
        document.getElementById(
            'descuento_ingresado'
        );

    const subtotalElemento =
        document.getElementById(
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

    const tipo =
        tipoCampo.value;

    const descuento = Number(
        String(
            descuentoCampo.value
        )
            .trim()
            .replace(',', '.')
    );

    const subtotal = Number(
        String(
            subtotalElemento.textContent
        )
            .trim()
            .replace(',', '.')
    );

    if (
        !Number.isFinite(
            descuento
        )
    ) {
        return {
            valido: false,
            mensaje:
                'Ingrese un descuento válido.'
        };
    }

    if (descuento < 0) {
        return {
            valido: false,
            mensaje:
                'El descuento no puede ser negativo.'
        };
    }

    if (
        subtotal <= 0 &&
        descuento > 0
    ) {
        return {
            valido: false,
            mensaje:
                'No se puede aplicar un descuento cuando el subtotal es cero.'
        };
    }

    if (
        tipo === 'PORCENTAJE' &&
        descuento > 100
    ) {
        return {
            valido: false,
            mensaje:
                'El descuento porcentual no puede superar el 100%.'
        };
    }

    if (
        tipo === 'VALOR_FIJO' &&
        descuento > subtotal
    ) {
        return {
            valido: false,
            mensaje:
                'El descuento fijo no puede superar el subtotal de la orden.'
        };
    }

    return {
        valido: true,
        mensaje: ''
    };
}


function mostrarEstadoDescuento() {
    const campo =
        document.getElementById(
            'descuento_ingresado'
        );

    const mensaje =
        document.getElementById(
            'descuentoError'
        );

    if (!campo) {
        return true;
    }

    const validacion =
        validarDescuento();

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


// =====================================================
// ACTUALIZACIÓN DE ELEMENTOS
// =====================================================
function actualizarTextoNumerico(
    idElemento,
    valor
) {
    const elemento =
        document.getElementById(
            idElemento
        );

    if (!elemento) {
        return;
    }

    elemento.textContent =
        numeroSeguro(valor).toFixed(2);
}


// =====================================================
// RECÁLCULO GENERAL
// =====================================================
function recalcularTotales() {
    const repuestos =
        sumarTabla(
            'tablaRepuestos'
        );

    const manoObraInterna =
        sumarTabla(
            'tablaMOI'
        );

    const manoObraExterna =
        sumarTabla(
            'tablaMOE'
        );

    const subtotalSinIva =
        repuestos +
        manoObraInterna +
        manoObraExterna;

    actualizarComposicionOrden(
        repuestos,
        manoObraInterna,
        manoObraExterna,
        subtotalSinIva
    );

    const porcentajeIva =
        numeroSeguro(
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

    if (
        descuentoIngresado < 0
    ) {
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

    const iva = (
        baseImponible *
        porcentajeIva
    ) / 100;

    const checkboxIva =
        document.getElementById(
            'sumar_iva_al_total'
        );

    const sumarIvaAlTotal =
        checkboxIva
            ? checkboxIva.checked
            : true;

    const totalFinal =
        sumarIvaAlTotal
            ? baseImponible + iva
            : baseImponible;

    /*
     * Tarjetas principales.
     */
    actualizarTextoNumerico(
        'subtotalRepuestos',
        repuestos
    );

    actualizarTextoNumerico(
        'subtotalMOI',
        manoObraInterna
    );

    actualizarTextoNumerico(
        'subtotalMOE',
        manoObraExterna
    );

    /*
     * Resumen adicional.
     */
    actualizarTextoNumerico(
        'resumenRep',
        repuestos
    );

    actualizarTextoNumerico(
        'resumenMOI',
        manoObraInterna
    );

    actualizarTextoNumerico(
        'resumenMOE',
        manoObraExterna
    );

    actualizarTextoNumerico(
        'subtotalGeneral',
        subtotalSinIva
    );

    actualizarTextoNumerico(
        'descuentoTotal',
        valorDescuento
    );

    actualizarTextoNumerico(
        'ivaTotal',
        iva
    );

    actualizarTextoNumerico(
        'granTotal',
        totalFinal
    );

    /*
     * Texto del descuento.
     */
    const descuentoPorcentajeTexto =
        document.getElementById(
            'descuentoPorcentajeTexto'
        );

    if (
        descuentoPorcentajeTexto
    ) {
        descuentoPorcentajeTexto.textContent =
            `${porcentajeDescuento.toFixed(2)}%`;
    }

    const descuentoValorTexto =
        document.getElementById(
            'descuentoValorTexto'
        );

    if (
        descuentoValorTexto
    ) {
        descuentoValorTexto.textContent =
            `$${valorDescuento.toFixed(2)}`;
    }

    /*
     * Etiqueta IVA.
     */
    const ivaLabel =
        document.getElementById(
            'ivaLabel'
        );

    if (ivaLabel) {
        ivaLabel.textContent =
            `IVA ${porcentajeIva.toFixed(2)}%`;
    }

    mostrarEstadoDescuento();
}


// =====================================================
// ESCAPAR HTML
// =====================================================
function escaparHTML(valor) {
    return String(
        valor ?? ''
    )
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}


// =====================================================
// INICIALIZACIÓN
// =====================================================
document.addEventListener(
    'DOMContentLoaded',
    function () {
        recalcularTotales();
    }
);