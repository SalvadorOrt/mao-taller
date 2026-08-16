// =========================================================
// INICIALIZACIÓN GENERAL DEL CATÁLOGO
// =========================================================

document.addEventListener("DOMContentLoaded", function () {

    if (typeof inicializarCodigos === "function") {
        inicializarCodigos();
    }

    if (typeof inicializarAtributos === "function") {
        inicializarAtributos();
    }

    if (typeof inicializarModales === "function") {
        inicializarModales();
    }

});