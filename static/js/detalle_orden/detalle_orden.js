function inicializarProximoMantenimiento() {
    const kilometrajeInput = document.getElementById(
        'id_kilometraje'
    );

    const intervaloSelect = document.getElementById(
        'id_intervalo_mantenimiento_km'
    );

    const proximoElemento = document.getElementById(
        'id_proximo_mantenimiento_km'
    );

    if (
        !kilometrajeInput ||
        !intervaloSelect ||
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
            intervaloSelect.value,
            10
        );

        if (
            Number.isNaN(kilometraje) ||
            Number.isNaN(intervalo)
        ) {
            proximoElemento.textContent = '-';
            return;
        }

        const proximoMantenimiento =
            kilometraje + intervalo;

        proximoElemento.textContent =
            proximoMantenimiento.toLocaleString(
                'es-EC'
            );
    }

    kilometrajeInput.addEventListener(
        'input',
        calcularProximoMantenimiento
    );

    intervaloSelect.addEventListener(
        'change',
        calcularProximoMantenimiento
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