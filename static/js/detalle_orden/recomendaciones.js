document.addEventListener("DOMContentLoaded", function () {

    const btn = document.getElementById(
        "btnAgregarRecomendacion"
    );

    if (btn) {

        btn.addEventListener(
            "click",
            agregarFilaRecomendacionOT
        );

    }

    document.addEventListener("click", function (e) {

        const btnEliminar = e.target.closest(
            ".btn-eliminar-recomendacion"
        );

        if (btnEliminar) {

            const fila = btnEliminar.closest("tr");

            if (fila) fila.remove();

        }

    });

});


function agregarFilaRecomendacionOT() {

    const tbody = document.getElementById(
        "contenedorRecomendaciones"
    );

    if (!tbody) return;

    const filaVacia = tbody.querySelector(
        ".texto-sin-recomendaciones"
    );

    if (filaVacia) {
        filaVacia.remove();
    }

    const tr = document.createElement("tr");

    tr.classList.add("recomendacion-item");

    tr.innerHTML = `
        <td style="width:24%;">
            <input type="hidden"
                   name="recomendacion_id[]"
                   value="">

            <input type="text"
                   name="recomendacion_titulo[]"
                   class="form-control-apple recomendacion-busqueda"
                   placeholder="Buscar recomendación">
        </td>

        <td style="width:64%;">
            <textarea
                name="recomendacion_texto[]"
                class="form-control-apple recomendacion-textarea"
                rows="3"
                placeholder="Texto de recomendación"></textarea>
        </td>

        <td style="width:12%; text-align:center;">
            <button type="button"
                    class="btn-login danger small btn-eliminar-recomendacion">
                ✕
            </button>
        </td>
    `;

    tbody.appendChild(tr);

}