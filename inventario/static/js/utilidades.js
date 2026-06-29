// =====================================================
// UTILIDADES GENERALES - CATÁLOGO INVENTARIO
// =====================================================

function getCSRFToken() {
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');

    if (!input) {
        console.error("No se encontró el token CSRF.");
        return "";
    }

    return input.value;
}


// =====================================================
// FETCH / AJAX
// =====================================================

async function postForm(url, data) {
    const response = await fetch(url, {
        method: "POST",
        headers: {
            "X-CSRFToken": getCSRFToken(),
            "X-Requested-With": "XMLHttpRequest",
        },
        body: data,
    });

    return await procesarRespuestaJSON(response);
}


async function postJSON(url, payload) {
    const response = await fetch(url, {
        method: "POST",
        headers: {
            "X-CSRFToken": getCSRFToken(),
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json",
        },
        body: JSON.stringify(payload || {}),
    });

    return await procesarRespuestaJSON(response);
}


async function procesarRespuestaJSON(response) {
    let json = {};

    try {
        json = await response.json();
    } catch (error) {
        json = {
            ok: false,
            error: "Respuesta inválida del servidor.",
        };
    }

    if (!response.ok && !json.error) {
        json.error = "No se pudo completar la operación.";
    }

    return json;
}


// =====================================================
// APPLE DROPDOWNS
// =====================================================

function agregarOpcionDropdown(tipo, id, texto, seleccionar = false) {
    if (!tipo || !id || !texto) return;

    if (
        window.AppleDropdown &&
        typeof window.AppleDropdown.agregarOpcion === "function"
    ) {
        window.AppleDropdown.agregarOpcion(
            tipo,
            id,
            texto,
            seleccionar
        );

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

        let item = menu.querySelector(
            `.apple-dropdown-item[data-id="${id}"]`
        );

        if (!item) {
            item = document.createElement("div");
            item.className = "apple-dropdown-item";
            item.dataset.id = id;
            item.dataset.nombre = texto;
            item.textContent = texto;

            item.addEventListener("click", function () {
                input.value = texto;
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
            input.value = texto;
            hidden.value = id;
            menu.style.display = "none";
        }
    });
}


function refrescarDropdowns() {
    if (
        window.AppleDropdown &&
        typeof window.AppleDropdown.refrescar === "function"
    ) {
        window.AppleDropdown.refrescar();
    } else if (typeof inicializarDropdownsApple === "function") {
        inicializarDropdownsApple();
    }
}


// =====================================================
// MODALES
// =====================================================

function cerrarModal(idModal) {
    const modalElement = document.getElementById(idModal);

    if (!modalElement) return;

    if (typeof bootstrap !== "undefined") {
        const modal = bootstrap.Modal.getInstance(modalElement)
            || new bootstrap.Modal(modalElement);

        modal.hide();
    } else {
        modalElement.style.display = "none";
    }
}


function abrirModal(idModal) {
    const modalElement = document.getElementById(idModal);

    if (!modalElement) return;

    if (typeof bootstrap !== "undefined") {
        const modal = bootstrap.Modal.getInstance(modalElement)
            || new bootstrap.Modal(modalElement);

        modal.show();
    } else {
        modalElement.style.display = "block";
    }
}


function abrirModalBootstrap(idModal) {
    abrirModal(idModal);
}


function cerrarModalBootstrap(idModal) {
    cerrarModal(idModal);
}


// =====================================================
// LIMPIEZA DE CAMPOS
// =====================================================

function limpiarInputs(selectorContenedor) {
    const contenedor = document.querySelector(selectorContenedor);

    if (!contenedor) return;

    contenedor.querySelectorAll("input, textarea").forEach(campo => {
        if (campo.type === "checkbox" || campo.type === "radio") {
            campo.checked = false;
        } else if (campo.type !== "hidden") {
            campo.value = "";
        }
    });

    contenedor.querySelectorAll(".apple-dropdown").forEach(dropdown => {
        const visible = dropdown.querySelector(".apple-dropdown-input");
        const hidden = dropdown.querySelector(".apple-dropdown-hidden");

        if (visible) visible.value = "";
        if (hidden) hidden.value = "";
    });
}


function limpiarCampo(id) {
    const campo = document.getElementById(id);

    if (!campo) return;

    if (campo.type === "checkbox" || campo.type === "radio") {
        campo.checked = false;
    } else {
        campo.value = "";
    }
}


// =====================================================
// MENSAJES
// =====================================================

function mostrarError(mensaje) {
    alert(mensaje || "Ocurrió un error.");
}


function mostrarExito(mensaje) {
    alert(mensaje || "Operación realizada correctamente.");
}


// =====================================================
// NÚMEROS
// =====================================================

function numeroSeguro(valor, defecto = 0) {
    if (valor === null || valor === undefined || valor === "") {
        return defecto;
    }

    const numero = parseFloat(
        String(valor).replace(",", ".")
    );

    return Number.isNaN(numero) ? defecto : numero;
}


function formatoDecimal(valor, decimales = 2) {
    const numero = numeroSeguro(valor, 0);
    return numero.toFixed(decimales);
}


// =====================================================
// STRINGS
// =====================================================

function textoSeguro(valor) {
    return (valor || "").toString().trim();
}


function textoMayuscula(valor) {
    return textoSeguro(valor).toUpperCase();
}