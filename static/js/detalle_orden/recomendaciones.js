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

            if (fila) {
                fila.remove();
            }

        }

    });

});


// =====================================================
// AGREGAR FILA
// =====================================================

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
        <td style="vertical-align:top; width:24%;">

            <input type="hidden"
                   name="recomendacion_id[]"
                   value="">

            <input type="text"
                   name="recomendacion_titulo[]"
                   class="form-control-apple recomendacion-busqueda"
                   placeholder="Buscar o escribir título"
                   style="width:100%;">

        </td>

        <td style="vertical-align:top; width:64%;">

            <textarea
                name="recomendacion_texto[]"
                class="form-control-apple recomendacion-textarea"
                rows="3"
                placeholder="Texto de recomendación"
                style="width:100%; min-height:72px;"></textarea>

        </td>

        <td style="vertical-align:top; width:12%; text-align:center;">

            <button type="button"
                    class="btn-login danger small btn-eliminar-recomendacion"
                    title="Quitar">

                ✕

            </button>

        </td>
    `;

    tbody.appendChild(tr);

}