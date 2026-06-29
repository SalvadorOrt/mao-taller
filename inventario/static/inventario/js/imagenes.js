// =========================================================
// IMÁGENES DEL PRODUCTO
// =========================================================

function inicializarImagenes(contexto = document) {
    contexto.querySelectorAll(".imagen-input").forEach(input => {
        if (input.dataset.inicializado === "1") {
            return;
        }

        input.dataset.inicializado = "1";

        input.addEventListener("change", function () {
            mostrarPreviewImagenesProducto(this);
        });
    });
}


// =========================================================
// PREVIEW
// =========================================================

function mostrarPreviewImagenesProducto(input) {
    const contenedor = document.getElementById("previewImagenesProducto");

    if (!contenedor) {
        return;
    }

    contenedor.innerHTML = "";

    const archivos = Array.from(input.files);

    if (archivos.length === 0) {
        contenedor.innerHTML = `
            <div class="preview-vacio">
                Sin imágenes seleccionadas
            </div>
        `;

        return;
    }

    archivos.forEach((archivo) => {
        if (!archivo.type.startsWith("image/")) {
            return;
        }

        const lector = new FileReader();

        lector.onload = function (e) {
            const tarjeta = document.createElement("div");
            tarjeta.className = "preview-item";

            tarjeta.innerHTML = `
                <img
                    src="${e.target.result}"
                    alt="${archivo.name}"
                    class="preview-img">

                <div class="preview-nombre">
                    ${archivo.name}
                </div>

                <div class="preview-peso">
                    ${formatearTamanoArchivo(archivo.size)}
                </div>
            `;

            contenedor.appendChild(tarjeta);
        };

        lector.readAsDataURL(archivo);
    });
}


// =========================================================
// LIMPIAR
// =========================================================

function limpiarImagenesProducto() {
    const input = document.getElementById("imagenesProducto");
    const preview = document.getElementById("previewImagenesProducto");

    if (input) {
        input.value = "";
    }

    if (preview) {
        preview.innerHTML = "";
    }
}


// =========================================================
// CONTADOR
// =========================================================

function cantidadImagenesProducto() {
    const input = document.getElementById("imagenesProducto");

    if (!input) {
        return 0;
    }

    return input.files.length;
}


// =========================================================
// TAMAÑO
// =========================================================

function formatearTamanoArchivo(bytes) {
    if (bytes < 1024) {
        return bytes + " B";
    }

    if (bytes < 1024 * 1024) {
        return (bytes / 1024).toFixed(1) + " KB";
    }

    return (bytes / 1024 / 1024).toFixed(2) + " MB";
}


// =========================================================
// OBTENER IMÁGENES
// =========================================================

function obtenerImagenesProducto() {
    const input = document.getElementById("imagenesProducto");

    if (!input) {
        return [];
    }

    return Array.from(input.files);
}


// =========================================================
// VALIDAR
// =========================================================

function validarImagenesProducto() {
    const archivos = obtenerImagenesProducto();

    for (const archivo of archivos) {
        if (!archivo.type.startsWith("image/")) {
            alert(`"${archivo.name}" no es una imagen válida.`);
            return false;
        }

        if (archivo.size > (10 * 1024 * 1024)) {
            alert(`"${archivo.name}" supera los 10 MB.`);
            return false;
        }
    }

    return true;
}


// =========================================================
// INICIALIZACIÓN
// =========================================================

document.addEventListener("DOMContentLoaded", function () {
    inicializarImagenes();
});