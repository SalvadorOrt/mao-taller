// =========================================================
// CÓDIGOS COMERCIALES
// =========================================================

function inicializarCodigos() {
    const tabla = document.getElementById("tablaCodigos");
    if (!tabla) return;

    // No inicializamos aquí AppleDropdown otra vez.
    // catalogo_form.js ya lo hace al cargar la página.
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
        return null;
    }

    const indice = parseInt(totalForms.value || "0", 10);
    const html = template.innerHTML.replace(/__prefix__/g, indice);

    container.insertAdjacentHTML("beforeend", html);
    totalForms.value = indice + 1;

    // Aquí sí es necesario porque acabamos de crear
    // un nuevo AppleDropdown dinámicamente.
    if (typeof inicializarDropdownsApple === "function") {
        inicializarDropdownsApple();
    }

    const nuevaFila = obtenerUltimaFilaCodigo();

    // Dejamos disponible la nueva fila para otros módulos,
    // por ejemplo el motor de sugerencias.
    return nuevaFila;
}


// =========================================================
// ELIMINAR CÓDIGO
// =========================================================

function eliminarCodigo(boton) {
    const fila = boton.closest(".codigo-form");
    if (!fila) return;

    const filasVisibles = obtenerFilasCodigoActivas();

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
    document.querySelectorAll(
        "#codigosContainer .codigo-form"
    ).forEach(function (fila) {

        fila.style.display = "";

        const deleteInput = fila.querySelector(
            'input[type="checkbox"][name$="-DELETE"]'
        );

        if (deleteInput) {
            deleteInput.checked = false;
        }

        fila.querySelectorAll("input").forEach(function (input) {
            if (
                input.type !== "hidden" &&
                input.type !== "checkbox"
            ) {
                input.value = "";
            }

            if (
                input.type === "checkbox" &&
                !input.name.endsWith("-DELETE")
            ) {
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
    let primerCampoError = null;

    const filas = obtenerFilasCodigoActivas();

    if (!filas.length) {
        alert("Debe existir al menos un código comercial.");
        return false;
    }

    filas.forEach(function (fila) {
        const marca = fila.querySelector(
            'input[type="hidden"][name$="-marca"]'
        );

        const codigo = fila.querySelector(
            'input[name$="-codigo"]'
        );

        const marcaVisible = fila.querySelector(
            '.apple-dropdown[data-dropdown-tipo="marca"] .apple-dropdown-input'
        );

        // =================================================
        // MARCA
        // =================================================

        if (!marca || !marca.value) {
            valido = false;
            primerCampoError ||= marcaVisible;

            marcarErrorCodigo(marcaVisible, true);
        } else {
            marcarErrorCodigo(marcaVisible, false);
        }

        // =================================================
        // CÓDIGO
        // =================================================

        if (!codigo || !codigo.value.trim()) {
            valido = false;
            primerCampoError ||= codigo;

            marcarErrorCodigo(codigo, true);
        } else {
            marcarErrorCodigo(codigo, false);
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

function marcarErrorCodigo(campo, error) {
    if (!campo) return;

    campo.style.borderColor = error
        ? "var(--danger)"
        : "";
}


// =========================================================
// OBTENER CÓDIGOS
// =========================================================

function obtenerCodigos() {
    const codigos = [];

    obtenerFilasCodigoActivas().forEach(function (fila) {
        codigos.push({
            marca: obtenerValorFila(
                fila,
                'input[type="hidden"][name$="-marca"]'
            ),

            tipo_codigo: obtenerValorFila(
                fila,
                'select[name$="-tipo_codigo"]'
            ),

            codigo: obtenerValorFila(
                fila,
                'input[name$="-codigo"]'
            ),

            codigo_barras: obtenerValorFila(
                fila,
                'input[name$="-codigo_barras"]'
            ),

            nombre_comercial: obtenerValorFila(
                fila,
                'input[name$="-nombre_comercial"]'
            ),

            presentacion_cantidad: obtenerValorFila(
                fila,
                'input[name$="-presentacion_cantidad"]'
            ),

            presentacion_unidad: obtenerValorFila(
                fila,
                'input[name$="-presentacion_unidad"]'
            ),

            precio_compra: obtenerValorFila(
                fila,
                'input[name$="-precio_compra"]'
            ),

            precio_venta: obtenerValorFila(
                fila,
                'input[name$="-precio_venta"]'
            ),

            margen_ganancia_porcentaje: obtenerValorFila(
                fila,
                'input[name$="-margen_ganancia_porcentaje"]'
            ),

            porcentaje_iva_costo: obtenerValorFila(
                fila,
                'input[name$="-porcentaje_iva_costo"]'
            ),

            activo: obtenerCheckboxFila(
                fila,
                'input[name$="-activo"]'
            ),
        });
    });

    return codigos;
}


// =========================================================
// FILAS ACTIVAS
// =========================================================

function obtenerFilasCodigoActivas() {
    return Array.from(
        document.querySelectorAll(
            "#codigosContainer .codigo-form"
        )
    ).filter(function (fila) {

        if (fila.style.display === "none") {
            return false;
        }

        const deleteInput = fila.querySelector(
            'input[type="checkbox"][name$="-DELETE"]'
        );

        return !deleteInput?.checked;
    });
}


// =========================================================
// ÚLTIMA FILA
// =========================================================

function obtenerUltimaFilaCodigo() {
    const filas = Array.from(
        document.querySelectorAll(
            "#codigosContainer .codigo-form"
        )
    );

    return filas.length
        ? filas[filas.length - 1]
        : null;
}


// =========================================================
// UTILIDADES
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
// EXPORTAR
// =========================================================

window.inicializarCodigos = inicializarCodigos;
window.agregarCodigo = agregarCodigo;
window.eliminarCodigo = eliminarCodigo;
window.limpiarCodigos = limpiarCodigos;
window.validarCodigos = validarCodigos;
window.obtenerCodigos = obtenerCodigos;
window.obtenerFilasCodigoActivas = obtenerFilasCodigoActivas;
window.obtenerUltimaFilaCodigo = obtenerUltimaFilaCodigo;