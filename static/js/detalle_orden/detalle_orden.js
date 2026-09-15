function inicializarProximoMantenimiento() {
    const kilometrajeInput = document.getElementById(
        'id_kilometraje'
    );

    const intervaloInput = document.getElementById(
        'id_intervalo_mantenimiento_km'
    );

    const proximoElemento = document.getElementById(
        'id_proximo_mantenimiento_km'
    );

    if (
        !kilometrajeInput ||
        !intervaloInput ||
        !proximoElemento
    ) {
        return;
    }

    function calcularProximoMantenimiento() {
        const kilometraje = Number.parseInt(
            kilometrajeInput.value,
            10
        );

        const intervalo = Number.parseInt(
            intervaloInput.value,
            10
        );

        intervaloInput.setCustomValidity('');

        if (intervaloInput.value.trim() === '') {
            proximoElemento.textContent = '-';
            return;
        }

        if (
            Number.isNaN(intervalo) ||
            intervalo <= 0
        ) {
            intervaloInput.setCustomValidity(
                'El intervalo debe ser mayor que cero.'
            );

            proximoElemento.textContent = '-';
            return;
        }

        if (
            Number.isNaN(kilometraje) ||
            kilometraje < 0
        ) {
            intervaloInput.setCustomValidity(
                'La orden no tiene un kilometraje actual válido.'
            );

            proximoElemento.textContent = '-';
            return;
        }

        const proximoMantenimiento =
            kilometraje + intervalo;

        if (
            proximoMantenimiento <= kilometraje
        ) {
            intervaloInput.setCustomValidity(
                'El próximo mantenimiento debe ser mayor que el kilometraje actual.'
            );

            proximoElemento.textContent = '-';
            return;
        }

        proximoElemento.textContent =
            proximoMantenimiento.toLocaleString(
                'es-EC'
            );
    }

    intervaloInput.addEventListener(
        'input',
        calcularProximoMantenimiento
    );

    intervaloInput.addEventListener(
        'blur',
        function () {
            calcularProximoMantenimiento();

            if (!intervaloInput.checkValidity()) {
                intervaloInput.reportValidity();
            }
        }
    );

    calcularProximoMantenimiento();
}

document.addEventListener('DOMContentLoaded', function () {

    const formDetalle = document.getElementById(
        'formDetalleOT'
    );

    if (formDetalle) {
        formDetalle.addEventListener(
            'keydown',
            function (event) {
                if (
                    event.key === 'Enter' &&
                    event.target.tagName !== 'TEXTAREA'
                ) {
                    event.preventDefault();
                }
            }
        );
    }

    const wrapper = document.querySelector(
        '.ot-wrapper'
    );

    const puedeEditar = wrapper
        ? wrapper.getAttribute(
            'data-puede-editar'
        ) === 'true'
        : false;

    if (puedeEditar) {
        asegurarFilaVaciaSiTablaEstaVacia(
            'tablaRepuestos',
            'repuestos'
        );
    }

    inicializarProximoMantenimiento();

    recalcularTotales();
});


function asegurarFilaVaciaSiTablaEstaVacia(
    idTabla,
    tipo
) {
    const tbody = document.querySelector(
        `#${idTabla} tbody`
    );

    if (!tbody) {
        return;
    }

    if (
        tbody.querySelectorAll('tr').length === 0
    ) {
        if (tipo === 'repuestos') {
            agregarFilaRepuesto();
        } else {
            agregarFilaSimple(
                idTabla
            );
        }
    }
}

// =========================================================
// MARCAR EN ROJO VALORES EN CERO O NEGATIVOS
// REPUESTOS / MOI / MOE
// =========================================================

function actualizarErroresNumericos() {

    const selectores = [
        '[name="rep_pu[]"]',
        '[name="rep_cantidad[]"]',
        '[name="rep_valor[]"]',

        '[name="moi_pu[]"]',
        '[name="moi_cantidad[]"]',
        '[name="moi_valor[]"]',

        '[name="moe_pu[]"]',
        '[name="moe_cantidad[]"]',
        '[name="moe_valor[]"]'
    ];

    const campos = document.querySelectorAll(
        selectores.join(",")
    );

    campos.forEach(function (campo) {

        const celda = campo.closest("td");

        if (!celda) {
            return;
        }

        const valor = parseFloat(
            String(campo.value || "0")
                .replace(",", ".")
        );

        if (
            Number.isNaN(valor) ||
            valor <= 0
        ) {
            celda.classList.add(
                "celda-error-numero"
            );
        } else {
            celda.classList.remove(
                "celda-error-numero"
            );
        }
    });
}


// =========================================================
// VALIDAR AL ABRIR LA ORDEN
// =========================================================

document.addEventListener(
    "DOMContentLoaded",
    function () {
        actualizarErroresNumericos();
    }
);


// =========================================================
// VALIDAR MIENTRAS SE EDITA
// =========================================================

document.addEventListener(
    "input",
    function (event) {

        const campo = event.target;

        if (
            campo.matches(
                `
                [name="rep_pu[]"],
                [name="rep_cantidad[]"],
                [name="rep_valor[]"],
                [name="moi_pu[]"],
                [name="moi_cantidad[]"],
                [name="moi_valor[]"],
                [name="moe_pu[]"],
                [name="moe_cantidad[]"],
                [name="moe_valor[]"]
                `
            )
        ) {
            /*
             * Esperamos a que calcularFila()
             * actualice también el campo Valor.
             */
            setTimeout(
                actualizarErroresNumericos,
                0
            );
        }
    }
);


// =========================================================
// TAMBIÉN SIRVE PARA FILAS AGREGADAS DINÁMICAMENTE
// =========================================================

window.actualizarErroresNumericos =
    actualizarErroresNumericos;