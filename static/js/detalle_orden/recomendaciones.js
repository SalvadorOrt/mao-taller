document.addEventListener("DOMContentLoaded", () => {
    const btnAgregar = document.getElementById("btnAgregarRecomendacion");

    if (btnAgregar) {
        btnAgregar.addEventListener("click", agregarRecomendacionManual);
    }

    document.addEventListener("click", (e) => {
        if (e.target.classList.contains("btn-eliminar-recomendacion")) {
            eliminarRecomendacion(e.target);
        }
    });
});

function agregarRecomendacionManual() {
    const contenedor = document.getElementById("contenedorRecomendaciones");
    if (!contenedor) return;

    const textoVacio = contenedor.querySelector(".texto-sin-recomendaciones");
    if (textoVacio) textoVacio.remove();

    const html = `
        <tr class="recomendacion-item">
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
        </tr>
    `.replace(/>\s+</g, '><');

    contenedor.insertAdjacentHTML("beforeend", html);
}

function eliminarRecomendacion(boton) {
    const item = boton.closest(".recomendacion-item");
    if (item) item.remove();
}