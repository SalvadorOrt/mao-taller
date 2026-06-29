document.addEventListener("DOMContentLoaded", () => {

    if (typeof inicializarDropdownsApple === "function") {
        inicializarDropdownsApple();
    }

    if (typeof inicializarCodigos === "function") {
        inicializarCodigos();
    }

    if (typeof inicializarAtributos === "function") {
        inicializarAtributos();
    }

    if (typeof inicializarImagenes === "function") {
        inicializarImagenes();
    }

    if (typeof inicializarModales === "function") {
        inicializarModales();
    }

    if (typeof inicializarPrecioSecreto === "function") {
        inicializarPrecioSecreto(document);
    }

});