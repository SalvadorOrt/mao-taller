// =====================================================
// CONFIG GENERAL - CATÁLOGO INVENTARIO
// =====================================================

document.addEventListener("DOMContentLoaded", function () {
    inicializarCatalogoForm();
});


function inicializarCatalogoForm() {
    const form = document.getElementById("catalogoForm");
    if (!form) return;

    if (typeof inicializarDropdownsApple === "function") {
        inicializarDropdownsApple();
    }

    if (typeof inicializarImagenes === "function") {
        inicializarImagenes(document);
    }

    inicializarPrecioSecreto(form);
}


// =====================================================
// PRECIO SECRETO
// =====================================================

function inicializarPrecioSecreto(contexto = document) {

    // Calcular valores iniciales.
    contexto.querySelectorAll(".codigo-form").forEach(function (fila) {
        actualizarPrecioSecretoFila(fila);
    });

    // Evitar registrar el listener más de una vez.
    if (contexto.dataset?.precioSecretoInicializado === "1") {
        return;
    }

    if (contexto.dataset) {
        contexto.dataset.precioSecretoInicializado = "1";
    }

    // Delegación de eventos:
    // también funciona con códigos agregados después.
    contexto.addEventListener("input", function (event) {
        const input = event.target;

        if (!input.classList.contains("precio-venta-input")) {
            return;
        }

        const fila = input.closest(".codigo-form");
        if (!fila) return;

        actualizarPrecioSecretoFila(fila);
    });
}


// =====================================================
// ACTUALIZAR PRECIO SECRETO DE UNA FILA
// =====================================================

function actualizarPrecioSecretoFila(fila) {
    if (!fila) return;

    const precioVentaInput = fila.querySelector(
        ".precio-venta-input"
    );

    const precioSecretoInput = fila.querySelector(
        ".precio-secreto-input"
    );

    if (!precioVentaInput || !precioSecretoInput) {
        return;
    }

    precioSecretoInput.value = convertirPrecioSecreto(
        precioVentaInput.value
    );
}


// =====================================================
// CONVERTIR PRECIO A CÓDIGO SECRETO
// =====================================================

function convertirPrecioSecreto(valor) {
    if (
        valor === null ||
        valor === undefined ||
        String(valor).trim() === ""
    ) {
        return "---";
    }

    const numero = parseFloat(
        String(valor)
            .trim()
            .replace(",", ".")
    );

    if (!Number.isFinite(numero)) {
        return "---";
    }

    const clave = {
        "1": "M",
        "2": "E",
        "3": "C",
        "4": "A",
        "5": "N",
        "6": "I",
        "7": "O",
        "8": "R",
        "9": "T",
        "0": "S",
        ".": ".",
    };

    return numero
        .toFixed(2)
        .split("")
        .map(function (caracter) {
            return clave[caracter] || caracter;
        })
        .join("");
}


// =====================================================
// VALIDACIÓN GENERAL ANTES DE ENVIAR
// =====================================================

document.addEventListener("submit", function (event) {
    const form = event.target;

    if (!form || form.id !== "catalogoForm") {
        return;
    }


    // =================================================
    // IMÁGENES
    // =================================================

    if (
        typeof validarImagenesProducto === "function" &&
        !validarImagenesProducto()
    ) {
        event.preventDefault();
        return;
    }


    // =================================================
    // CÓDIGOS
    // =================================================

    if (
        typeof validarCodigos === "function" &&
        !validarCodigos()
    ) {
        event.preventDefault();

        alert(
            "Revise los códigos comerciales."
        );

        return;
    }


    // =================================================
    // ATRIBUTOS
    // =================================================

    if (
        typeof validarAtributos === "function" &&
        !validarAtributos()
    ) {
        event.preventDefault();

        alert(
            "Existe un valor técnico sin un atributo seleccionado."
        );

        return;
    }
});


// =====================================================
// EXPORTAR
// =====================================================

window.inicializarCatalogoForm = inicializarCatalogoForm;
window.inicializarPrecioSecreto = inicializarPrecioSecreto;
window.actualizarPrecioSecretoFila = actualizarPrecioSecretoFila;
window.convertirPrecioSecreto = convertirPrecioSecreto;