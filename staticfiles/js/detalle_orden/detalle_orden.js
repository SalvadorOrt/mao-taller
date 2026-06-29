document.addEventListener('DOMContentLoaded', function () {

    const formDetalle = document.getElementById('formDetalleOT');

    if (formDetalle) {
        formDetalle.addEventListener('keydown', function (event) {
            if (
                event.key === 'Enter' &&
                event.target.tagName !== 'TEXTAREA'
            ) {
                event.preventDefault();
            }
        });
    }

    const wrapper = document.querySelector('.ot-wrapper');

    const puedeEditar = wrapper
        ? wrapper.getAttribute('data-puede-editar') === 'true'
        : false;

    if (puedeEditar) {
        asegurarFilaVaciaSiTablaEstaVacia(
            'tablaRepuestos',
            'repuestos'
        );
    }

    recalcularTotales();
});

function asegurarFilaVaciaSiTablaEstaVacia(idTabla, tipo) {
    const tbody = document.querySelector(`#${idTabla} tbody`);

    if (!tbody) return;

    if (tbody.querySelectorAll('tr').length === 0) {
        if (tipo === 'repuestos') {
            agregarFilaRepuesto();
        } else {
            agregarFilaSimple(idTabla);
        }
    }
}