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


async function postForm(url, data) {
    const response = await fetch(url, {
        method: "POST",
        headers: {
            "X-CSRFToken": getCSRFToken(),
            "X-Requested-With": "XMLHttpRequest"
        },
        body: data
    });

    let json = {};

    try {
        json = await response.json();
    } catch (error) {
        json = {
            ok: false,
            error: "Respuesta inválida del servidor."
        };
    }

    if (!response.ok && !json.error) {
        json.error = "No se pudo completar la operación.";
    }

    return json;
}


function agregarOpcionSelect(select, id, texto, seleccionar = false) {
    if (!select || !id || !texto) return;

    const existe = Array.from(select.options).some(
        option => String(option.value) === String(id)
    );

    if (!existe) {
        const option = new Option(texto, id, seleccionar, seleccionar);
        select.add(option);
    }

    if (seleccionar) {
        select.value = id;
    }

    if (typeof $ !== "undefined" && $(select).hasClass("select2-hidden-accessible")) {
        $(select).trigger("change");
    }
}


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


function limpiarInputs(selectorContenedor) {
    const contenedor = document.querySelector(selectorContenedor);

    if (!contenedor) return;

    contenedor.querySelectorAll("input, textarea, select").forEach(campo => {
        if (campo.type === "checkbox" || campo.type === "radio") {
            campo.checked = false;
        } else {
            campo.value = "";
        }

        if (typeof $ !== "undefined" && $(campo).hasClass("select2-hidden-accessible")) {
            $(campo).trigger("change");
        }
    });
}


function mostrarError(mensaje) {
    alert(mensaje || "Ocurrió un error.");
}


function mostrarExito(mensaje) {
    alert(mensaje || "Operación realizada correctamente.");
}


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