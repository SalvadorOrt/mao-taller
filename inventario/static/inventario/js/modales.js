// =====================================================
// MODALES RÁPIDOS: CATEGORÍA, MARCA, ATRIBUTO
// Compatible con AppleDropdown
// =====================================================

function obtenerCSRFToken() {
    const input = document.querySelector("input[name='csrfmiddlewaretoken']");
    return input ? input.value : "";
}

function obtenerFormularioCatalogo() {
    return document.getElementById("catalogoForm");
}

function abrirModalBootstrap(idModal) {
    const modalElement = document.getElementById(idModal);

    if (!modalElement || typeof bootstrap === "undefined") {
        alert("No se pudo abrir el modal.");
        return;
    }

    const modal = bootstrap.Modal.getInstance(modalElement)
        || new bootstrap.Modal(modalElement);

    modal.show();
}

function cerrarModalPorId(idModal) {
    const modalElement = document.getElementById(idModal);

    if (!modalElement || typeof bootstrap === "undefined") return;

    const modal = bootstrap.Modal.getInstance(modalElement)
        || new bootstrap.Modal(modalElement);

    modal.hide();
}

function limpiarInput(id) {
    const input = document.getElementById(id);

    if (input) {
        input.value = "";
    }
}

function normalizarTexto(valor) {
    return (valor || "").toString().trim();
}

async function enviarCreacionRapida(url, payload) {
    if (!url) {
        throw new Error("Falta configurar la URL de creación rápida.");
    }

    const response = await fetch(url, {
        method: "POST",
        headers: {
            "X-CSRFToken": obtenerCSRFToken(),
            "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
    });

    let data = {};

    try {
        data = await response.json();
    } catch (error) {
        throw new Error("La respuesta del servidor no es JSON válido.");
    }

    if (!response.ok || !data.ok) {
        throw new Error(data.error || "No se pudo guardar.");
    }

    return data;
}

function agregarOpcionADropdowns(tipo, id, nombre, seleccionar = true) {
    if (window.AppleDropdown && typeof window.AppleDropdown.agregarOpcion === "function") {
        window.AppleDropdown.agregarOpcion(tipo, id, nombre, seleccionar);
        return;
    }

    const dropdowns = document.querySelectorAll(
        `.apple-dropdown[data-dropdown-tipo="${tipo}"]`
    );

    dropdowns.forEach((wrap) => {
        const input = wrap.querySelector(".apple-dropdown-input");
        const hidden = wrap.querySelector(".apple-dropdown-hidden");
        const menu = wrap.querySelector(".apple-dropdown-menu");

        if (!input || !hidden || !menu) return;

        let item = menu.querySelector(`.apple-dropdown-item[data-id="${id}"]`);

        if (!item) {
            item = document.createElement("div");
            item.className = "apple-dropdown-item";
            item.dataset.id = id;
            item.dataset.nombre = nombre;
            item.textContent = nombre;

            item.addEventListener("click", () => {
                input.value = nombre;
                hidden.value = id;
                menu.style.display = "none";
            });

            const noResult = menu.querySelector(".apple-dropdown-no-result");

            if (noResult) {
                menu.insertBefore(item, noResult);
            } else {
                menu.appendChild(item);
            }
        }

        if (seleccionar) {
            input.value = nombre;
            hidden.value = id;
            menu.style.display = "none";
        }
    });
}


// =====================================================
// INICIALIZACIÓN
// =====================================================

function inicializarModales() {
    prepararEnterModal("categoriaNombre", guardarCategoria);
    prepararEnterModal("categoriaPrefijo", guardarCategoria);

    prepararEnterModal("marcaNombre", guardarMarca);

    prepararEnterModal("atributoNombre", guardarAtributo);
    prepararEnterModal("atributoUnidad", guardarAtributo);
}

function prepararEnterModal(inputId, callback) {
    const input = document.getElementById(inputId);

    if (!input) return;

    if (input.dataset.enterInicializado === "1") return;

    input.dataset.enterInicializado = "1";

    input.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
            event.preventDefault();
            callback();
        }
    });
}


// =====================================================
// CATEGORÍA RÁPIDA
// =====================================================

async function guardarCategoria() {
    const form = obtenerFormularioCatalogo();

    if (!form) {
        alert("No se encontró el formulario del catálogo.");
        return;
    }

    const nombreInput = document.getElementById("categoriaNombre");
    const prefijoInput = document.getElementById("categoriaPrefijo");

    const nombre = normalizarTexto(nombreInput?.value).toUpperCase();
    const prefijo = normalizarTexto(prefijoInput?.value).toUpperCase();

    if (!nombre) {
        alert("Ingrese el nombre de la categoría.");
        if (nombreInput) nombreInput.focus();
        return;
    }

    if (!prefijo) {
        alert("Ingrese el prefijo SKU.");
        if (prefijoInput) prefijoInput.focus();
        return;
    }

    try {
        const data = await enviarCreacionRapida(
            form.dataset.urlCategoriaRapida,
            {
                nombre: nombre,
                prefijo_sku: prefijo,
            }
        );

        agregarOpcionADropdowns("categoria", data.id, data.nombre, true);

        limpiarInput("categoriaNombre");
        limpiarInput("categoriaPrefijo");

        cerrarModalPorId("modalCategoria");

    } catch (error) {
        alert(error.message || "No se pudo crear la categoría.");
    }
}


// =====================================================
// MARCA RÁPIDA
// =====================================================

async function guardarMarca() {
    const form = obtenerFormularioCatalogo();

    if (!form) {
        alert("No se encontró el formulario del catálogo.");
        return;
    }

    const nombreInput = document.getElementById("marcaNombre");
    const nombre = normalizarTexto(nombreInput?.value).toUpperCase();

    if (!nombre) {
        alert("Ingrese el nombre de la marca.");
        if (nombreInput) nombreInput.focus();
        return;
    }

    try {
        const data = await enviarCreacionRapida(
            form.dataset.urlMarcaRapida,
            {
                nombre: nombre,
            }
        );

        agregarOpcionADropdowns("marca", data.id, data.nombre, true);

        limpiarInput("marcaNombre");

        cerrarModalPorId("modalMarca");

    } catch (error) {
        alert(error.message || "No se pudo crear la marca.");
    }
}


// =====================================================
// ATRIBUTO RÁPIDO
// =====================================================

async function guardarAtributo() {
    const form = obtenerFormularioCatalogo();

    if (!form) {
        alert("No se encontró el formulario del catálogo.");
        return;
    }

    const nombreInput = document.getElementById("atributoNombre");
    const unidadInput = document.getElementById("atributoUnidad");

    const nombre = normalizarTexto(nombreInput?.value).toUpperCase();
    const unidad = normalizarTexto(unidadInput?.value).toUpperCase();

    if (!nombre) {
        alert("Ingrese el nombre del atributo.");
        if (nombreInput) nombreInput.focus();
        return;
    }

    try {
        const data = await enviarCreacionRapida(
            form.dataset.urlAtributoRapido,
            {
                nombre: nombre,
                unidad: unidad,
            }
        );

        agregarOpcionADropdowns("atributo", data.id, data.nombre, true);

        limpiarInput("atributoNombre");
        limpiarInput("atributoUnidad");

        cerrarModalPorId("modalAtributo");

    } catch (error) {
        alert(error.message || "No se pudo crear el atributo.");
    }
}

document.addEventListener("DOMContentLoaded", function () {
    inicializarModales();
});