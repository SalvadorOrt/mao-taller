function agregarFilaRecomendacionOT(enfocar = false) {
    const tbody = document.querySelector('#tablaRecomendaciones tbody');
    if (!tbody) return;

    const filaVacia = tbody.querySelector('.texto-sin-recomendaciones');
    if (filaVacia) filaVacia.remove();

    const filaHtml = `
        <tr class="recomendacion-item">
            <td>
                <input type="hidden" name="recomendacion_detalle_id[]" value="">
                <input type="hidden" name="recomendacion_delete[]" value="0">
                <input type="hidden" name="recomendacion_actualizado_en[]" value="">
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
            const filas = tbody.querySelectorAll('tr.recomendacion-item:not(.recomendacion-eliminada)');
            const ultimaFila = filas[filas.length - 1];
            const input = ultimaFila?.querySelector('.recomendacion-busqueda');
            if (input) input.focus();
        }, 50);
    }
}

function eliminarFilaRecomendacion(boton) {
    const fila = boton.closest('tr');
    if (!fila) return;

    const detalleId = fila.querySelector('input[name="recomendacion_detalle_id[]"]');
    const deleteInput = fila.querySelector('input[name="recomendacion_delete[]"]');

    if (detalleId && detalleId.value) {
        if (deleteInput) {
            deleteInput.value = "1";
        }

        fila.classList.add("recomendacion-eliminada");
        fila.style.display = "none";
    } else {
        fila.remove();
    }

    const tbody = document.querySelector('#tablaRecomendaciones tbody');
    if (!tbody) return;

    const visibles = Array.from(tbody.querySelectorAll('.recomendacion-item'))
        .filter(item => !item.classList.contains('recomendacion-eliminada'));

    if (visibles.length === 0 && !tbody.querySelector('.texto-sin-recomendaciones')) {
        tbody.insertAdjacentHTML('beforeend', `
            <tr class="texto-sin-recomendaciones">
                <td colspan="3" style="text-align:center; color:#86868b; padding:14px;">
                    No hay recomendaciones técnicas registradas.
                </td>
            </tr>
        `);
    }
}