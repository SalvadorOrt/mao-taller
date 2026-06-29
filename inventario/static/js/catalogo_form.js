// =====================================================
// CONFIG GENERAL - CATÁLOGO INVENTARIO
// =====================================================

document.addEventListener("DOMContentLoaded", function () {
    inicializarCatalogoForm();
});

function inicializarCatalogoForm() {
    if (typeof inicializarDropdownsApple === "function") {
        inicializarDropdownsApple();
    }

    if (typeof inicializarImagenes === "function") {
        inicializarImagenes(document);
    }

    inicializarPrecioSecreto(document);
}


// =====================================================
// PRECIO SECRETO
// =====================================================

function inicializarPrecioSecreto(contexto = document) {
    contexto.querySelectorAll(".codigo-form").forEach(fila => {
        const precioVentaInput = fila.querySelector(".precio-venta-input");
        const precioSecretoInput = fila.querySelector(".precio-secreto-input");

        if (!precioVentaInput || !precioSecretoInput) return;

        actualizarPrecioSecretoFila(fila);

        if (precioVentaInput.dataset.precioSecretoInicializado === "1") {
            return;
        }

        precioVentaInput.dataset.precioSecretoInicializado = "1";

        precioVentaInput.addEventListener("input", function () {
            actualizarPrecioSecretoFila(fila);
        });
    });
}

function actualizarPrecioSecretoFila(fila) {
    const precioVentaInput = fila.querySelector(".precio-venta-input");
    const precioSecretoInput = fila.querySelector(".precio-secreto-input");

    if (!precioVentaInput || !precioSecretoInput) return;

    precioSecretoInput.value = convertirPrecioSecreto(precioVentaInput.value);
}

function convertirPrecioSecreto(valor) {
    if (!valor) return "---";

    let numero = parseFloat(valor.toString().replace(",", "."));

    if (isNaN(numero)) return "---";

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
        ".": "."
    };

    const texto = numero.toFixed(2);

    return texto
        .split("")
        .map(caracter => clave[caracter] || caracter)
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

    if (typeof validarImagenesProducto === "function") {
        if (!validarImagenesProducto()) {
            event.preventDefault();
            return;
        }
    }

    if (typeof validarCodigos === "function") {
        if (!validarCodigos()) {
            event.preventDefault();
            alert("Revise los códigos comerciales.");
            return;
        }
    }

    if (typeof validarAtributos === "function") {
        if (!validarAtributos()) {
            event.preventDefault();
            alert("Revise los atributos técnicos.");
            return;
        }
    }
});