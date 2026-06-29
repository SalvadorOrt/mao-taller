function agregarFilaRecomendacionOT(enfocar = false) {
    const tbody = document.querySelector('#tablaRecomendaciones tbody');
    if (!tbody) return;

    const filaVacia = tbody.querySelector('.texto-sin-recomendaciones');
    if (filaVacia) filaVacia.remove();

    const filaHtml = `
        <tr class="recomendacion-item">
            <td>
                <input type="hidden" name="recomendacion_id[]" value="">
                <input type="text"
                       name="recomendacion_titulo[]"
                       class="form-control-apple recomendacion-busqueda"
                       placeholder="Buscar recomendación">
            </td>
            <td>
                <textarea name="recomendacion_texto[]"
                          class="form-control-apple recomendacion-textarea"
                          rows="3"
                          placeholder="Texto de recomendación"></textarea>
            </td>
            <td style="text-align:center;">
                <button type="button"
                        class="btn-login danger small"
                        onclick="eliminarFilaRecomendacion(this)"
                        title="Quitar">✕</button>
            </td>
        </tr>
    `;

    tbody.insertAdjacentHTML('beforeend', filaHtml);

    if (enfocar) {
        setTimeout(() => {
            const filas = tbody.querySelectorAll('tr.recomendacion-item');
            const ultimaFila = filas[filas.length - 1];
            const input = ultimaFila?.querySelector('.recomendacion-busqueda');
            if (input) input.focus();
        }, 50);
    }
}

function eliminarFilaRecomendacion(boton) {
    const fila = boton.closest('tr');
    if (fila) fila.remove();
}