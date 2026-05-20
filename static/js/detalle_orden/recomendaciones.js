document.addEventListener("DOMContentLoaded", () => {

    const btnAgregar = document.getElementById("btnAgregarRecomendacion");

    if (btnAgregar) {
        btnAgregar.addEventListener(
            "click",
            agregarRecomendacionManual
        );
    }

    document.addEventListener("click", (e) => {

        if (
            e.target.classList.contains(
                "btn-eliminar-recomendacion"
            )
        ) {
            eliminarRecomendacion(e.target);
        }

    });

});


function agregarRecomendacionManual() {

    const contenedor = document.getElementById(
        "contenedorRecomendaciones"
    );

    if (!contenedor) return;

    const textoVacio = contenedor.querySelector(
        ".texto-sin-recomendaciones"
    );

    if (textoVacio) {
        textoVacio.remove();
    }

    const html = `
        <div class="recomendacion-item"
             style="border:1px solid #e5e5ea;
                    border-radius:10px;
                    padding:12px;
                    margin-bottom:10px;">

            <input type="hidden"
                   name="recomendacion_id[]"
                   value="">

            <input type="text"
                   name="recomendacion_titulo[]"
                   class="form-control"
                   placeholder="Título de la recomendación">

            <textarea name="recomendacion_texto[]"
                      class="form-control"
                      rows="5"
                      style="margin-top:8px;"
                      placeholder="Texto de la recomendación"></textarea>

            <button type="button"
                    class="btn-login btn-eliminar-recomendacion"
                    style="margin-top:10px;
                           background:#ff3b30;
                           border-color:#ff3b30;">

                Eliminar

            </button>

        </div>
    `;

    contenedor.insertAdjacentHTML(
        "beforeend",
        html
    );
}


function eliminarRecomendacion(boton) {

    const item = boton.closest(
        ".recomendacion-item"
    );

    if (item) {
        item.remove();
    }

}