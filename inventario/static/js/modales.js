function obtenerCSRFToken() {
    const input = document.querySelector("input[name='csrfmiddlewaretoken']");
    return input ? input.value : "";
}

function cerrarModalPorId(idModal) {
    const modalElement = document.getElementById(idModal);

    if (!modalElement) return;

    const modal = bootstrap.Modal.getInstance(modalElement);

    if (modal) {
        modal.hide();
    }
}

function limpiarInput(id) {
    const input = document.getElementById(id);

    if (input) {
        input.value = "";
    }
}

function agregarOpcionADropdowns(tipo, id, nombre, seleccionar = true) {
    const dropdowns = document.querySelectorAll(
        `.apple-dropdown[data-dropdown-tipo="${tipo}"]`
    );

    dropdowns.forEach((wrap) => {
        const input = wrap.querySelector(".apple-dropdown-input");
        const hidden = wrap.querySelector(".apple-dropdown-hidden");
        const menu = wrap.querySelector(".apple-dropdown-menu");

        if (!input || !hidden || !menu) return;

        const existe = menu.querySelector(
            `.apple-dropdown-item[data-id="${id}"]`
        );

        if (!existe) {
            const item = document.createElement("div");

            item.className = "apple-dropdown-item";
            item.dataset.id = id;
            item.dataset.nombre = nombre;
            item.textContent = nombre;

            item.addEventListener("click", () => {
                input.value = nombre;
                hidden.value = id;
                menu.style.display = "none";
            });

            const noResult = menu.querySelector(".apple-dropdown-no-result");

            if (noResult) {
                menu.insertBefore(item, noResult);
            } else {
                menu.appendChild(item);
            }
        }

        if (seleccionar) {
            input.value = nombre;
            hidden.value = id;
            menu.style.display = "none";
        }
    });
}

async function guardarCategoria() {
    const form = document.getElementById("catalogoForm");

    const nombre = document.getElementById("categoriaNombre").value.trim();
    const prefijo = document.getElementById("categoriaPrefijo").value.trim();

    if (!nombre) {
        alert("Ingrese el nombre de la categoría.");
        return;
    }

    if (!prefijo) {
        alert("Ingrese el prefijo SKU.");
        return;
    }

    const response = await fetch(form.dataset.urlCategoriaRapida, {
        method: "POST",
        headers: {
            "X-CSRFToken": obtenerCSRFToken(),
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            nombre: nombre,
            prefijo_sku: prefijo,
        }),
    });

    const data = await response.json();

    if (!response.ok || !data.ok) {
        alert(data.error || "No se pudo crear la categoría.");
        return;
    }

    agregarOpcionADropdowns("categoria", data.id, data.nombre, true);

    limpiarInput("categoriaNombre");
    limpiarInput("categoriaPrefijo");

    cerrarModalPorId("modalCategoria");
}

async function guardarMarca() {
    const form = document.getElementById("catalogoForm");

    const nombre = document.getElementById("marcaNombre").value.trim();

    if (!nombre) {
        alert("Ingrese el nombre de la marca.");
        return;
    }

    const response = await fetch(form.dataset.urlMarcaRapida, {
        method: "POST",
        headers: {
            "X-CSRFToken": obtenerCSRFToken(),
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            nombre: nombre,
        }),
    });

    const data = await response.json();

    if (!response.ok || !data.ok) {
        alert(data.error || "No se pudo crear la marca.");
        return;
    }

    agregarOpcionADropdowns("marca", data.id, data.nombre, true);

    limpiarInput("marcaNombre");

    cerrarModalPorId("modalMarca");
}

async function guardarAtributo() {
    const form = document.getElementById("catalogoForm");

    const nombre = document.getElementById("atributoNombre").value.trim();
    const unidad = document.getElementById("atributoUnidad").value.trim();

    if (!nombre) {
        alert("Ingrese el nombre del atributo.");
        return;
    }

    const response = await fetch(form.dataset.urlAtributoRapido, {
        method: "POST",
        headers: {
            "X-CSRFToken": obtenerCSRFToken(),
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            nombre: nombre,
            unidad: unidad,
        }),
    });

    const data = await response.json();

    if (!response.ok || !data.ok) {
        alert(data.error || "No se pudo crear el atributo.");
        return;
    }

    agregarOpcionADropdowns("atributo", data.id, data.nombre, true);

    limpiarInput("atributoNombre");
    limpiarInput("atributoUnidad");

    cerrarModalPorId("modalAtributo");
}