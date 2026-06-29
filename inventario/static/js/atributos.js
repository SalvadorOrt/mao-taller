// =========================================================
// ATRIBUTOS TÉCNICOS
// =========================================================

function inicializarAtributos() {
    const tabla = document.getElementById("tablaAtributos");

    if (!tabla) {
        return;
    }

    inicializarDropdownsApple();
}


// =========================================================
// AGREGAR ATRIBUTO
// =========================================================

function agregarAtributo() {
    const totalForms = document.getElementById(
        "id_atributos-TOTAL_FORMS"
    );

    const container = document.getElementById(
        "atributosContainer"
    );

    const template = document.getElementById(
        "atributoEmptyFormTemplate"
    );

    if (!totalForms || !container || !template) {
        console.error("No se encontró el formset de atributos.");
        return;
    }

    const indice = parseInt(totalForms.value);

    let html = template.innerHTML;

    html = html.replace(/__prefix__/g, indice);

    container.insertAdjacentHTML(
        "beforeend",
        html
    );

    totalForms.value = indice + 1;

    inicializarDropdownsApple();
}


// =========================================================
// ELIMINAR ATRIBUTO
// =========================================================

function eliminarAtributo(boton) {
    const fila = boton.closest(".atributo-form");

    if (!fila) {
        return;
    }

    const filasVisibles = Array.from(
        document.querySelectorAll(
            "#atributosContainer .atributo-form"
        )
    ).filter(
        fila => fila.style.display !== "none"
    );

    if (filasVisibles.length <= 1) {
        alert(
            "Debe existir al menos un atributo."
        );

        return;
    }

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
    });
}


// =========================================================
// VALIDAR ATRIBUTOS
// =========================================================

function validarAtributos() {
    let valido = true;

    const filas = document.querySelectorAll(
        "#atributosContainer .atributo-form"
    );

    filas.forEach(function (fila) {
        if (fila.style.display === "none") {
            return;
        }

        const atributo = fila.querySelector(
            'input[type="hidden"][name$="-atributo"]'
        );

        const valor = fila.querySelector(
            'input[name$="-valor"]'
        );

        if (!atributo || !atributo.value) {
            const visible = fila.querySelector(".apple-dropdown-input");

            if (visible) visible.focus();

            valido = false;
            return;
        }

        if (!valor.value.trim()) {
            valor.focus();
            valido = false;
            return;
        }
    });

    return valido;
}


// =========================================================
// OBTENER ATRIBUTOS
// =========================================================

function obtenerAtributos() {
    const atributos = [];

    document.querySelectorAll(
        "#atributosContainer .atributo-form"
    ).forEach(function (fila) {
        if (fila.style.display === "none") {
            return;
        }

        atributos.push({
            atributo: fila.querySelector(
                'input[type="hidden"][name$="-atributo"]'
            ).value,

            valor: fila.querySelector(
                'input[name$="-valor"]'
            ).value,
        });
    });

    return atributos;
}