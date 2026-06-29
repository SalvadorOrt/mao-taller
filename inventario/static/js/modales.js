// =====================================================
// MODALES RÁPIDOS: CATEGORÍA, MARCA, ATRIBUTO
// Requiere:
// - utilidades.js
// - select2.js
// =====================================================

function inicializarModales() {
    prepararEnterModal("categoriaNombre", guardarCategoria);
    prepararEnterModal("categoriaPrefijo", guardarCategoria);

    prepararEnterModal("marcaNombre", guardarMarca);

    prepararEnterModal("atributoNombre", guardarAtributo);
    prepararEnterModal("atributoUnidad", guardarAtributo);
}

function prepararEnterModal(inputId, callback) {
    const input = document.getElementById(inputId);

    if (!input) return;

    input.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
            event.preventDefault();
            callback();
        }
    });
}


// =====================================================
// CATEGORÍA RÁPIDA
// =====================================================
async function guardarCategoria() {
    const form = document.getElementById("catalogoForm");

    if (!form || !form.dataset.urlCategoriaRapida) {
        alert("Falta configurar la URL de categoría rápida.");
        return;
    }

    const nombreInput = document.getElementById("categoriaNombre");
    const prefijoInput = document.getElementById("categoriaPrefijo");

    const nombre = nombreInput.value.trim().toUpperCase();
    const prefijo = prefijoInput.value.trim().toUpperCase();

    if (!nombre) {
        alert("Ingrese el nombre de la categoría.");
        nombreInput.focus();
        return;
    }

    if (!prefijo) {
        alert("Ingrese el prefijo SKU.");
        prefijoInput.focus();
        return;
    }

    const data = new FormData();
    data.append("nombre", nombre);
    data.append("prefijo_sku", prefijo);

    const resp = await postForm(form.dataset.urlCategoriaRapida, data);

    if (!resp.ok) {
        alert(resp.error || "No se pudo crear la categoría.");
        return;
    }

    const selectCategoria = document.querySelector('select[name="categoria"]');

    agregarOpcionSelect(
        selectCategoria,
        resp.id,
        resp.nombre,
        true
    );

    limpiarModalCategoria();
    cerrarModal("modalCategoria");
}

function limpiarModalCategoria() {
    const nombreInput = document.getElementById("categoriaNombre");
    const prefijoInput = document.getElementById("categoriaPrefijo");

    if (nombreInput) nombreInput.value = "";
    if (prefijoInput) prefijoInput.value = "";
}


// =====================================================
// MARCA RÁPIDA
// =====================================================
async function guardarMarca() {
    const form = document.getElementById("catalogoForm");

    if (!form || !form.dataset.urlMarcaRapida) {
        alert("Falta configurar la URL de marca rápida.");
        return;
    }

    const nombreInput = document.getElementById("marcaNombre");
    const nombre = nombreInput.value.trim().toUpperCase();

    if (!nombre) {
        alert("Ingrese el nombre de la marca.");
        nombreInput.focus();
        return;
    }

    const data = new FormData();
    data.append("nombre", nombre);

    const resp = await postForm(form.dataset.urlMarcaRapida, data);

    if (!resp.ok) {
        alert(resp.error || "No se pudo crear la marca.");
        return;
    }

    const selectsMarca = document.querySelectorAll("select.codigo-marca");

    selectsMarca.forEach(select => {
        agregarOpcionSelect(
            select,
            resp.id,
            resp.nombre,
            false
        );
    });

    const ultimaFila = document.querySelector(
        "#codigosContainer .codigo-form:last-child"
    );

    const ultimoSelectMarca = ultimaFila
        ? ultimaFila.querySelector("select.codigo-marca")
        : null;

    if (ultimoSelectMarca) {
        agregarOpcionSelect(
            ultimoSelectMarca,
            resp.id,
            resp.nombre,
            true
        );
    }

    limpiarModalMarca();
    cerrarModal("modalMarca");
}

function limpiarModalMarca() {
    const nombreInput = document.getElementById("marcaNombre");

    if (nombreInput) nombreInput.value = "";
}


// =====================================================
// ATRIBUTO RÁPIDO
// =====================================================
async function guardarAtributo() {
    const form = document.getElementById("catalogoForm");

    if (!form || !form.dataset.urlAtributoRapido) {
        alert("Falta configurar la URL de atributo rápido.");
        return;
    }

    const nombreInput = document.getElementById("atributoNombre");
    const unidadInput = document.getElementById("atributoUnidad");

    const nombre = nombreInput.value.trim().toUpperCase();
    const unidad = unidadInput.value.trim().toUpperCase();

    if (!nombre) {
        alert("Ingrese el nombre del atributo.");
        nombreInput.focus();
        return;
    }

    const data = new FormData();
    data.append("nombre", nombre);
    data.append("unidad", unidad);

    const resp = await postForm(form.dataset.urlAtributoRapido, data);

    if (!resp.ok) {
        alert(resp.error || "No se pudo crear el atributo.");
        return;
    }

    const selectsAtributo = document.querySelectorAll("select.atributo-select");

    selectsAtributo.forEach(select => {
        agregarOpcionSelect(
            select,
            resp.id,
            resp.nombre,
            false
        );
    });

    const ultimaFila = document.querySelector(
        "#atributosContainer .atributo-form:last-child"
    );

    const ultimoSelectAtributo = ultimaFila
        ? ultimaFila.querySelector("select.atributo-select")
        : null;

    if (ultimoSelectAtributo) {
        agregarOpcionSelect(
            ultimoSelectAtributo,
            resp.id,
            resp.nombre,
            true
        );
    }

    limpiarModalAtributo();
    cerrarModal("modalAtributo");
}

function limpiarModalAtributo() {
    const nombreInput = document.getElementById("atributoNombre");
    const unidadInput = document.getElementById("atributoUnidad");

    if (nombreInput) nombreInput.value = "";
    if (unidadInput) unidadInput.value = "";
}