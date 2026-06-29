// =====================================================
// CONFIG GENERAL
// =====================================================
document.addEventListener("DOMContentLoaded", function () {
    inicializarSelect2(document);
    inicializarPreviewsImagenes(document);
    inicializarPrecioSecreto(document);
});


// =====================================================
// SELECT2
// =====================================================
function inicializarSelect2(contexto) {
    if (typeof $ === "undefined") return;

    $(contexto).find(".select2").each(function () {
        if ($(this).hasClass("select2-hidden-accessible")) {
            $(this).select2("destroy");
        }

        $(this).select2({
            width: "100%",
            placeholder: "Buscar...",
            allowClear: true
        });
    });
}


// =====================================================
// FORMSET: CÓDIGOS COMERCIALES
// =====================================================
function agregarCodigo() {
    const totalFormsInput = document.getElementById("id_codigos-TOTAL_FORMS");
    const container = document.getElementById("codigosContainer");
    const template = document.getElementById("codigoEmptyFormTemplate");

    if (!totalFormsInput || !container || !template) {
        console.error("No se encontró el formset de códigos.");
        return;
    }

    const index = parseInt(totalFormsInput.value);
    let html = template.innerHTML.replaceAll("__prefix__", index);

    container.insertAdjacentHTML("beforeend", html);
    totalFormsInput.value = index + 1;

    const nuevaFila = container.lastElementChild;

    inicializarSelect2(nuevaFila);
    inicializarPreviewsImagenes(nuevaFila);
    inicializarPrecioSecreto(nuevaFila);
    actualizarNamesImagenes();
}


function eliminarCodigo(boton) {
    const filasVisibles = Array.from(
        document.querySelectorAll("#codigosContainer .codigo-form")
    ).filter(fila => fila.style.display !== "none");

    if (filasVisibles.length <= 1) {
        alert("Debe existir al menos un código comercial.");
        return;
    }

    const fila = boton.closest(".codigo-form");
    const deleteInput = fila.querySelector('input[type="checkbox"][name$="-DELETE"]');

    if (deleteInput) {
        deleteInput.checked = true;
        fila.style.display = "none";
    } else {
        fila.remove();
    }

    actualizarNamesImagenes();
}


// =====================================================
// FORMSET: ATRIBUTOS TÉCNICOS
// =====================================================
function agregarAtributo() {
    const totalFormsInput = document.getElementById("id_atributos-TOTAL_FORMS");
    const container = document.getElementById("atributosContainer");
    const template = document.getElementById("atributoEmptyFormTemplate");

    if (!totalFormsInput || !container || !template) {
        console.error("No se encontró el formset de atributos.");
        return;
    }

    const index = parseInt(totalFormsInput.value);
    let html = template.innerHTML.replaceAll("__prefix__", index);

    container.insertAdjacentHTML("beforeend", html);
    totalFormsInput.value = index + 1;

    const nuevaFila = container.lastElementChild;
    inicializarSelect2(nuevaFila);
}


function eliminarAtributo(boton) {
    const fila = boton.closest(".atributo-form");
    const deleteInput = fila.querySelector('input[type="checkbox"][name$="-DELETE"]');

    if (deleteInput) {
        deleteInput.checked = true;
        fila.style.display = "none";
    } else {
        fila.remove();
    }
}


// =====================================================
// IMÁGENES POR CÓDIGO
// =====================================================
function inicializarPreviewsImagenes(contexto) {
    contexto.querySelectorAll(".imagen-input").forEach(input => {
        input.addEventListener("change", function () {
            previewImagenes(this);
        });
    });

    actualizarNamesImagenes();
}


function actualizarNamesImagenes() {
    const filas = document.querySelectorAll("#codigosContainer .codigo-form");

    filas.forEach((fila, index) => {
        const inputImagen = fila.querySelector(".imagen-input");

        if (inputImagen) {
            inputImagen.name = `imagenes_codigo_${index}`;
        }
    });
}


function previewImagenes(input) {
    const fila = input.closest(".codigo-form");
    const preview = fila.querySelector(".preview-imagenes");

    if (!preview) return;

    preview.innerHTML = "";

    const archivos = Array.from(input.files || []);

    archivos.forEach(file => {
        if (!file.type.startsWith("image/")) return;

        const item = document.createElement("div");
        item.className = "preview-item";

        const img = document.createElement("img");
        img.src = URL.createObjectURL(file);

        item.appendChild(img);
        preview.appendChild(item);
    });
}


// =====================================================
// PRECIO SECRETO
// =====================================================
function inicializarPrecioSecreto(contexto) {
    contexto.querySelectorAll(".codigo-form").forEach(fila => {
        const precioVentaInput = fila.querySelector(".precio-venta-input");
        const precioSecretoInput = fila.querySelector(".precio-secreto-input");

        if (!precioVentaInput || !precioSecretoInput) return;

        actualizarPrecioSecretoFila(fila);

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
// AJAX HELPERS
// =====================================================
function getCSRFToken() {
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : "";
}


async function postForm(url, data) {
    const response = await fetch(url, {
        method: "POST",
        headers: {
            "X-CSRFToken": getCSRFToken(),
            "X-Requested-With": "XMLHttpRequest"
        },
        body: data
    });

    return await response.json();
}


// =====================================================
// CREACIÓN RÁPIDA: CATEGORÍA
// =====================================================
async function guardarCategoria() {
    const form = document.getElementById("catalogoForm");

    const url = form.dataset.urlCategoriaRapida;

    if (!url) {
        alert("Falta configurar la URL de categoría rápida.");
        return;
    }

    const nombre = document.getElementById("categoriaNombre").value.trim();
    const prefijo = document.getElementById("categoriaPrefijo").value.trim();

    const data = new FormData();
    data.append("nombre", nombre);
    data.append("prefijo_sku", prefijo);

    const resp = await postForm(url, data);

    if (!resp.ok) {
        alert(resp.error || "No se pudo crear la categoría.");
        return;
    }

    agregarOpcionSelect(
        document.querySelector('select[name="categoria"]'),
        resp.id,
        resp.nombre,
        true
    );

    cerrarModal("modalCategoria");

    document.getElementById("categoriaNombre").value = "";
    document.getElementById("categoriaPrefijo").value = "";
}


// =====================================================
// CREACIÓN RÁPIDA: MARCA
// =====================================================
async function guardarMarca() {
    const form = document.getElementById("catalogoForm");

    const url = form.dataset.urlMarcaRapida;

    if (!url) {
        alert("Falta configurar la URL de marca rápida.");
        return;
    }

    const nombre = document.getElementById("marcaNombre").value.trim();

    const data = new FormData();
    data.append("nombre", nombre);

    const resp = await postForm(url, data);

    if (!resp.ok) {
        alert(resp.error || "No se pudo crear la marca.");
        return;
    }

    document.querySelectorAll("select.codigo-marca").forEach(select => {
        agregarOpcionSelect(select, resp.id, resp.nombre, false);
    });

    const ultimaMarca = document.querySelector("#codigosContainer .codigo-form:last-child select.codigo-marca");

    if (ultimaMarca) {
        agregarOpcionSelect(ultimaMarca, resp.id, resp.nombre, true);
    }

    cerrarModal("modalMarca");

    document.getElementById("marcaNombre").value = "";
}


// =====================================================
// CREACIÓN RÁPIDA: ATRIBUTO
// =====================================================
async function guardarAtributo() {
    const form = document.getElementById("catalogoForm");

    const url = form.dataset.urlAtributoRapido;

    if (!url) {
        alert("Falta configurar la URL de atributo rápido.");
        return;
    }

    const nombre = document.getElementById("atributoNombre").value.trim();
    const unidad = document.getElementById("atributoUnidad").value.trim();

    const data = new FormData();
    data.append("nombre", nombre);
    data.append("unidad", unidad);

    const resp = await postForm(url, data);

    if (!resp.ok) {
        alert(resp.error || "No se pudo crear el atributo.");
        return;
    }

    document.querySelectorAll("select.atributo-select").forEach(select => {
        agregarOpcionSelect(select, resp.id, resp.nombre, false);
    });

    const ultimoAtributo = document.querySelector("#atributosContainer .atributo-form:last-child select.atributo-select");

    if (ultimoAtributo) {
        agregarOpcionSelect(ultimoAtributo, resp.id, resp.nombre, true);
    }

    cerrarModal("modalAtributo");

    document.getElementById("atributoNombre").value = "";
    document.getElementById("atributoUnidad").value = "";
}


// =====================================================
// UTILIDADES SELECT2 / MODAL
// =====================================================
function agregarOpcionSelect(select, id, texto, seleccionar) {
    if (!select) return;

    const existe = Array.from(select.options).some(option => option.value == id);

    if (!existe) {
        const option = new Option(texto, id, seleccionar, seleccionar);
        select.add(option);
    }

    if (seleccionar) {
        select.value = id;
    }

    if (typeof $ !== "undefined" && $(select).hasClass("select2-hidden-accessible")) {
        $(select).trigger("change");
    }
}


function cerrarModal(idModal) {
    const modalElement = document.getElementById(idModal);

    if (!modalElement) return;

    if (typeof bootstrap !== "undefined") {
        const modal = bootstrap.Modal.getInstance(modalElement);

        if (modal) {
            modal.hide();
        }
    } else {
        modalElement.style.display = "none";
    }
}