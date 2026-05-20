// =====================================================
// INIT
// =====================================================

document.addEventListener("DOMContentLoaded", function () {

    const btnAgregar = document.getElementById(
        "btnAgregarRecomendacion"
    );

    if (btnAgregar) {
        btnAgregar.addEventListener(
            "click",
            agregarRecomendacionManual
        );
    }

    document.addEventListener("click", function (e) {

        const botonEliminar = e.target.closest(
            ".btn-eliminar-recomendacion"
        );

        if (botonEliminar) {
            eliminarRecomendacion(botonEliminar);
        }

    });

});


// =====================================================
// AGREGAR FILA
// =====================================================
function agregarRecomendacionManual() {
    const tbody = document.getElementById("contenedorRecomendaciones");
    if (!tbody) return;

    const filaVacia = tbody.querySelector(".texto-sin-recomendaciones");
    if (filaVacia) filaVacia.remove();

    const html = `
        <tr class="recomendacion-item">
            <td style="width:24%;">
                <input type="hidden" name="recomendacion_id[]" value="">
                <input type="text"
                       name="recomendacion_titulo[]"
                       class="form-control-apple recomendacion-busqueda"
                       placeholder="Buscar o escribir título">
            </td>

            <td style="width:64%;">
                <textarea name="recomendacion_texto[]"
                          class="form-control-apple recomendacion-textarea"
                          rows="3"
                          placeholder="Texto de recomendación"></textarea>
            </td>

            <td style="width:12%; text-align:center;">
                <button type="button"
                        class="btn-login danger small btn-eliminar-recomendacion"
                        title="Quitar">✕</button>
            </td>
        </tr>
    `;

    tbody.insertAdjacentHTML("beforeend", html);
}
// =====================================================
// ELIMINAR FILA
// =====================================================

function eliminarRecomendacion(boton) {

    const fila = boton.closest("tr");

    if (fila) {
        fila.remove();
    }

}


// =====================================================
// AUTOCOMPLETE
// =====================================================

document.addEventListener("input", async function (e) {

    if (
        !e.target.classList.contains(
            "recomendacion-busqueda"
        )
    ) {
        return;
    }

    const input = e.target;

    const texto = input.value.trim();

    cerrarDropdownRecomendaciones();

    if (texto.length < 2) return;

    try {

        const response = await fetch(
            `/api/buscar-recomendaciones/?q=${encodeURIComponent(texto)}`
        );

        const data = await response.json();

        if (
            !data.resultados ||
            !data.resultados.length
        ) {
            return;
        }

        mostrarDropdownRecomendaciones(
            input,
            data.resultados
        );

    } catch (err) {

        console.error(err);

    }

});


// =====================================================
// MOSTRAR DROPDOWN
// =====================================================

function mostrarDropdownRecomendaciones(
    input,
    resultados
) {

    cerrarDropdownRecomendaciones();

    const dropdown = document.createElement("div");

    dropdown.id = "dropdownRecomendaciones";

    dropdown.style.position = "fixed";
    dropdown.style.background = "#fff";
    dropdown.style.border = "1px solid #d2d2d7";
    dropdown.style.borderRadius = "10px";
    dropdown.style.boxShadow =
        "0 4px 12px rgba(0,0,0,0.15)";
    dropdown.style.zIndex = "999999";
    dropdown.style.maxHeight = "220px";
    dropdown.style.overflowY = "auto";

    const rect = input.getBoundingClientRect();

    dropdown.style.left = rect.left + "px";
    dropdown.style.top = (rect.bottom + 4) + "px";
    dropdown.style.width = rect.width + "px";

    resultados.forEach(item => {

        const opcion = document.createElement("div");

        opcion.style.padding = "10px";
        opcion.style.cursor = "pointer";
        opcion.style.borderBottom =
            "1px solid #f5f5f7";

        opcion.style.fontSize = "12px";

        opcion.innerHTML = `
            <strong>${item.titulo}</strong>
        `;

        opcion.addEventListener("click", () => {

            seleccionarRecomendacion(
                input,
                item
            );

        });

        dropdown.appendChild(opcion);

    });

    document.body.appendChild(dropdown);

}


// =====================================================
// SELECCIONAR RECOMENDACIÓN
// =====================================================

function seleccionarRecomendacion(
    input,
    item
) {

    const fila = input.closest("tr");

    if (!fila) return;

    const inputId = fila.querySelector(
        'input[name="recomendacion_id[]"]'
    );

    const inputTitulo = fila.querySelector(
        'input[name="recomendacion_titulo[]"]'
    );

    const textarea = fila.querySelector(
        'textarea[name="recomendacion_texto[]"]'
    );

    if (inputId) {
        inputId.value = item.id;
    }

    if (inputTitulo) {
        inputTitulo.value = item.titulo;
    }

    if (textarea) {
        textarea.value = item.texto;
    }

    cerrarDropdownRecomendaciones();

}


// =====================================================
// CERRAR DROPDOWN
// =====================================================

function cerrarDropdownRecomendaciones() {

    const existente = document.getElementById(
        "dropdownRecomendaciones"
    );

    if (existente) {
        existente.remove();
    }

}


document.addEventListener("click", function (e) {

    if (
        !e.target.classList.contains(
            "recomendacion-busqueda"
        )
    ) {

        cerrarDropdownRecomendaciones();

    }

});