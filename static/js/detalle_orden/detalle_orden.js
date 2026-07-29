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