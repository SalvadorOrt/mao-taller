// =========================================================
// CÓDIGOS COMERCIALES
// =========================================================

function inicializarCodigos() {
    const tabla = document.getElementById("tablaCodigos");

    if (!tabla) {
        return;
    }

    inicializarDropdownsApple();
}


// =========================================================
// AGREGAR CÓDIGO
// =========================================================

function agregarCodigo() {
    const totalForms = document.getElementById("id_codigos-TOTAL_FORMS");
    const container = document.getElementById("codigosContainer");
    const template = document.getElementById("codigoEmptyFormTemplate");

    if (!totalForms || !container || !template) {
        console.error("No se encontró el formset de códigos.");
        return;
    }

    const indice = parseInt(totalForms.value);

    let html = template.innerHTML;
    html = html.replace(/__prefix__/g, indice);

    container.insertAdjacentHTML("beforeend", html);
    totalForms.value = indice + 1;

    inicializarDropdownsApple();
}


// =========================================================
// ELIMINAR CÓDIGO
// =========================================================

function eliminarCodigo(boton) {
    const fila = boton.closest(".codigo-form");

    if (!fila) {
        return;
    }

    const filasVisibles = Array.from(
        document.querySelectorAll("#codigosContainer .codigo-form")
    ).filter(fila => fila.style.display !== "none");

    if (filasVisibles.length <= 1) {
        alert("Debe existir al menos un código comercial.");
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
// LIMPIAR CÓDIGOS
// =========================================================

function limpiarCodigos() {
    document.querySelectorAll("#codigosContainer .codigo-form").forEach(function (fila) {
        fila.querySelectorAll("input").forEach(function (input) {
            if (
                input.type !== "hidden" &&
                input.type !== "checkbox"
            ) {
                input.value = "";
            }

            if (input.type === "checkbox" && !input.name.endsWith("-DELETE")) {
                input.checked = false;
            }
        });

        fila.querySelectorAll("select").forEach(function (select) {
            select.selectedIndex = 0;
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
// VALIDAR CÓDIGOS
// =========================================================

function validarCodigos() {
    let valido = true;

    const filas = document.querySelectorAll("#codigosContainer .codigo-form");

    filas.forEach(function (fila) {
        if (fila.style.display === "none") {
            return;
        }

        const marca = fila.querySelector(
            'input[type="hidden"][name$="-marca"]'
        );

        const codigo = fila.querySelector(
            'input[name$="-codigo"]'
        );

        if (!marca || !marca.value) {
            const visible = fila.querySelector(".apple-dropdown-input");

            if (visible) visible.focus();

            valido = false;
            return;
        }

        if (!codigo || !codigo.value.trim()) {
            codigo.focus();
            valido = false;
            return;
        }
    });

    return valido;
}


// =========================================================
// OBTENER CÓDIGOS
// =========================================================

function obtenerCodigos() {
    const codigos = [];

    document.querySelectorAll("#codigosContainer .codigo-form").forEach(function (fila) {
        if (fila.style.display === "none") {
            return;
        }

        codigos.push({
            marca: obtenerValorFila(fila, 'input[type="hidden"][name$="-marca"]'),
            tipo_codigo: obtenerValorFila(fila, 'select[name$="-tipo_codigo"]'),
            codigo: obtenerValorFila(fila, 'input[name$="-codigo"]'),
            codigo_barras: obtenerValorFila(fila, 'input[name$="-codigo_barras"]'),
            nombre_comercial: obtenerValorFila(fila, 'input[name$="-nombre_comercial"]'),
            presentacion_cantidad: obtenerValorFila(fila, 'input[name$="-presentacion_cantidad"]'),
            presentacion_unidad: obtenerValorFila(fila, 'input[name$="-presentacion_unidad"]'),
            precio_compra: obtenerValorFila(fila, 'input[name$="-precio_compra"]'),
            precio_venta: obtenerValorFila(fila, 'input[name$="-precio_venta"]'),
            margen_ganancia_porcentaje: obtenerValorFila(fila, 'input[name$="-margen_ganancia_porcentaje"]'),
            porcentaje_iva_costo: obtenerValorFila(fila, 'input[name$="-porcentaje_iva_costo"]'),
            activo: obtenerCheckboxFila(fila, 'input[name$="-activo"]'),
        });
    });

    return codigos;
}


// =========================================================
// UTILIDADES DE FILA
// =========================================================

function obtenerValorFila(fila, selector) {
    const campo = fila.querySelector(selector);
    return campo ? campo.value : "";
}

function obtenerCheckboxFila(fila, selector) {
    const campo = fila.querySelector(selector);
    return campo ? campo.checked : false;
}


// =========================================================
// INICIALIZACIÓN
// =========================================================

document.addEventListener("DOMContentLoaded", function () {
    inicializarCodigos();
});