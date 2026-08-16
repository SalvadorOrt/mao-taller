// =========================================================
// ATRIBUTOS TÉCNICOS
// =========================================================

function inicializarAtributos() {
    const tabla = document.getElementById("tablaAtributos");
    if (!tabla) return;

    inicializarDropdownsApple();
    conectarEventosAtributos();
}


// =========================================================
// EVENTOS
// =========================================================

function conectarEventosAtributos() {
    const container = document.getElementById("atributosContainer");
    if (!container || container.dataset.eventosAtributos === "1") return;

    container.dataset.eventosAtributos = "1";

    // Si el usuario cambia manualmente un atributo que había sido
    // sugerido, deja de considerarse automático.
    container.addEventListener("change", function (event) {
        const target = event.target;

        if (
            !target.matches('input[type="hidden"][name$="-atributo"]') &&
            !target.classList.contains("apple-dropdown-input")
        ) return;

        const fila = target.closest(".atributo-form");
        if (!fila || fila.dataset.sugerido !== "1") return;

        quitarMarcaSugerencia(fila);
    });

    // Si comienza a escribir un valor, conservamos la fila aunque
    // posteriormente cambie la categoría.
    container.addEventListener("input", function (event) {
        if (!event.target.matches('input[name$="-valor"]')) return;

        const fila = event.target.closest(".atributo-form");
        if (!fila) return;

        if (event.target.value.trim()) {
            fila.dataset.valorIngresado = "1";
        } else {
            delete fila.dataset.valorIngresado;
        }
    });
}


// =========================================================
// AGREGAR ATRIBUTO
// =========================================================

function agregarAtributo() {
    const totalForms = document.getElementById("id_atributos-TOTAL_FORMS");
    const container = document.getElementById("atributosContainer");
    const template = document.getElementById("atributoEmptyFormTemplate");

    if (!totalForms || !container || !template) {
        console.error("No se encontró el formset de atributos.");
        return null;
    }

    const indice = parseInt(totalForms.value || "0", 10);
    const html = template.innerHTML.replace(/__prefix__/g, indice);

    container.insertAdjacentHTML("beforeend", html);
    totalForms.value = indice + 1;

    inicializarDropdownsApple();

    return obtenerUltimaFilaAtributo();
}


// =========================================================
// ELIMINAR ATRIBUTO
// =========================================================

function eliminarAtributo(boton) {
    const fila = boton.closest(".atributo-form");
    if (!fila) return;

    const deleteInput = fila.querySelector(
        'input[type="checkbox"][name$="-DELETE"]'
    );

    if (deleteInput) {
        deleteInput.checked = true;
        fila.style.display = "none";
    } else {
        fila.remove();
    }
}


// =========================================================
// LIMPIAR ATRIBUTOS
// =========================================================

function limpiarAtributos() {
    document.querySelectorAll(
        "#atributosContainer .atributo-form"
    ).forEach(function (fila) {

        fila.style.display = "";

        const deleteInput = fila.querySelector(
            'input[type="checkbox"][name$="-DELETE"]'
        );

        if (deleteInput) deleteInput.checked = false;

        fila.querySelectorAll("input").forEach(function (input) {
            if (
                input.type !== "hidden" &&
                input.type !== "checkbox"
            ) {
                input.value = "";
            }
        });

        fila.querySelectorAll(".apple-dropdown").forEach(function (dropdown) {
            const visible = dropdown.querySelector(".apple-dropdown-input");
            const hidden = dropdown.querySelector(".apple-dropdown-hidden");

            if (visible) visible.value = "";
            if (hidden) hidden.value = "";
        });

        quitarMarcaSugerencia(fila);
    });
}


// =========================================================
// VALIDAR ATRIBUTOS
// =========================================================

function validarAtributos() {
    let valido = true;
    let primerCampoError = null;

    document.querySelectorAll(
        "#atributosContainer .atributo-form"
    ).forEach(function (fila) {

        if (fila.style.display === "none") return;

        const deleteInput = fila.querySelector(
            'input[type="checkbox"][name$="-DELETE"]'
        );

        if (deleteInput?.checked) return;

        const atributo = fila.querySelector(
            'input[type="hidden"][name$="-atributo"]'
        );

        const valor = fila.querySelector(
            'input[name$="-valor"]'
        );

        const visible = fila.querySelector(
            ".apple-dropdown-input"
        );

        const atributoId = (atributo?.value || "").trim();
        const valorTexto = (valor?.value || "").trim();


        // =================================================
        // 1. FILA TOTALMENTE VACÍA
        // =================================================

        if (!atributoId && !valorTexto) {
            marcarErrorAtributo(fila, false);
            return;
        }


        // =================================================
        // 2. ESCRIBIÓ VALOR PERO NO ELIGIÓ ATRIBUTO
        // =================================================

        if (!atributoId && valorTexto) {
            valido = false;
            primerCampoError ||= visible;

            marcarErrorAtributo(fila, true);
            return;
        }


        // =================================================
        // 3. ATRIBUTO + VALOR
        // =================================================

        if (atributoId && valorTexto) {
            marcarErrorAtributo(fila, false);
            return;
        }


        // =================================================
        // 4. ATRIBUTO SIN VALOR
        //
        // Todos los atributos son opcionales.
        // No se guarda esta fila.
        // =================================================

        if (atributoId && !valorTexto) {

            if (deleteInput) {
                deleteInput.checked = true;
            } else {
                if (atributo) atributo.value = "";
                if (visible) visible.value = "";
            }

            marcarErrorAtributo(fila, false);
        }
    });


    if (!valido && primerCampoError) {
        primerCampoError.focus();
    }

    return valido;
}

// =========================================================
// ERROR VISUAL
// =========================================================

function marcarErrorAtributo(fila, error) {
    if (!fila) return;

    const visible = fila.querySelector(".apple-dropdown-input");
    const valor = fila.querySelector('input[name$="-valor"]');

    [visible, valor].forEach(function (input) {
        if (!input) return;

        if (error) {
            input.style.borderColor = "var(--danger)";
        } else {
            input.style.borderColor = "";
        }
    });
}


// =========================================================
// QUITAR ESTADO DE SUGERENCIA
// =========================================================

function quitarMarcaSugerencia(fila) {
    if (!fila) return;

    delete fila.dataset.sugerido;
    delete fila.dataset.categoriaSugerida;
    delete fila.dataset.requerido;

    const valor = fila.querySelector(
        'input[name$="-valor"]'
    );

    if (valor) {
        delete valor.dataset.atributoRequerido;
        delete valor.dataset.atributoSugerido;
    }
}


// =========================================================
// OBTENER ÚLTIMA FILA
// =========================================================

function obtenerUltimaFilaAtributo() {
    const filas = Array.from(
        document.querySelectorAll(
            "#atributosContainer .atributo-form"
        )
    );

    return filas.length
        ? filas[filas.length - 1]
        : null;
}


// =========================================================
// OBTENER ATRIBUTOS
// =========================================================

function obtenerAtributos() {
    const atributos = [];

    document.querySelectorAll(
        "#atributosContainer .atributo-form"
    ).forEach(function (fila) {
        if (fila.style.display === "none") return;

        const deleteInput = fila.querySelector(
            'input[type="checkbox"][name$="-DELETE"]'
        );

        if (deleteInput?.checked) return;

        const atributo = fila.querySelector(
            'input[type="hidden"][name$="-atributo"]'
        );

        const valor = fila.querySelector(
            'input[name$="-valor"]'
        );

        const atributoId = (atributo?.value || "").trim();
        const valorTexto = (valor?.value || "").trim();

        if (!atributoId || !valorTexto) return;

        atributos.push({
            atributo: atributoId,
            valor: valorTexto,
            sugerido: fila.dataset.sugerido === "1",
            requerido: fila.dataset.requerido === "1",
        });
    });

    return atributos;
}


// =========================================================
// CONSULTAS ÚTILES
// =========================================================

function atributoEstaEnFormulario(atributoId) {
    return Array.from(
        document.querySelectorAll(
            "#atributosContainer .atributo-form"
        )
    ).some(function (fila) {
        if (fila.style.display === "none") return false;

        const deleteInput = fila.querySelector(
            'input[type="checkbox"][name$="-DELETE"]'
        );

        if (deleteInput?.checked) return false;

        const atributo = fila.querySelector(
            'input[type="hidden"][name$="-atributo"]'
        );

        return (
            atributo &&
            String(atributo.value) === String(atributoId)
        );
    });
}


// =========================================================
// EXPORTAR
// =========================================================

window.inicializarAtributos = inicializarAtributos;
window.agregarAtributo = agregarAtributo;
window.eliminarAtributo = eliminarAtributo;
window.limpiarAtributos = limpiarAtributos;
window.validarAtributos = validarAtributos;
window.obtenerAtributos = obtenerAtributos;
window.atributoEstaEnFormulario = atributoEstaEnFormulario;