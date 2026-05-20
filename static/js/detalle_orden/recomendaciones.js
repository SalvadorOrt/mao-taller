document.addEventListener("DOMContentLoaded", function () {
    const btnAgregar = document.getElementById("btnAgregarRecomendacion");

    if (btnAgregar) {
        btnAgregar.addEventListener("click", function () {
            agregarRecomendacionManual();
        });
    }

    document.addEventListener("click", function (e) {
        const botonEliminar = e.target.closest(".btn-eliminar-recomendacion");

        if (botonEliminar) {
            eliminarRecomendacion(botonEliminar);
        }
    });
});

function agregarRecomendacionManual() {
    const tbody = document.getElementById("contenedorRecomendaciones");
    if (!tbody) return;

    const filaVacia = tbody.querySelector(".texto-sin-recomendaciones");
    if (filaVacia) filaVacia.remove();

    const fila = document.createElement("tr");
    fila.className = "recomendacion-item";

    fila.innerHTML = `
        <td>
            <input type="hidden" name="recomendacion_id[]" value="">
            <input type="text"
                   name="recomendacion_titulo[]"
                   class="form-control-apple"
                   placeholder="Título">
        </td>

        <td>
            <textarea name="recomendacion_texto[]"
                      class="form-control-apple recomendacion-textarea"
                      rows="3"
                      placeholder="Texto de recomendación"></textarea>
        </td>

        <td style="text-align:center;">
            <button type="button"
                    class="btn-login danger small btn-eliminar-recomendacion"
                    title="Quitar">✕</button>
        </td>
    `;

    tbody.appendChild(fila);
}

function eliminarRecomendacion(boton) {
    const fila = boton.closest("tr");
    if (fila) fila.remove();
}