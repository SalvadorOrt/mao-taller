// =========================================================
// INICIALIZACIÓN GENERAL DEL CATÁLOGO
// =========================================================
//
// Este archivo solamente inicia módulos que todavía
// necesitan un arranque centralizado.
//
// IMPORTANTE:
//
// atributos.js
// modales.js
// sugerencias.js
// catalogo_form.js
//
// ya tienen su propia inicialización mediante
// DOMContentLoaded.
//
// Por eso NO se vuelven a inicializar aquí.
// =========================================================


(function () {
    "use strict";


    // =====================================================
    // INICIALIZACIÓN
    // =====================================================

    function inicializarCatalogo() {

        // =================================================
        // CÓDIGOS COMERCIALES
        // =================================================

        if (
            typeof window.inicializarCodigos
            === "function"
        ) {

            window.inicializarCodigos();
        }
    }


    // =====================================================
    // ARRANQUE
    // =====================================================

    if (
        document.readyState
        === "loading"
    ) {

        document.addEventListener(
            "DOMContentLoaded",
            inicializarCatalogo
        );

    } else {

        inicializarCatalogo();
    }

})();