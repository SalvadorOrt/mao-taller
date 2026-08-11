// =========================================================
// IMÁGENES DEL PRODUCTO
// =========================================================
//
// Funciones:
// - Seleccionar varias imágenes.
// - Agregar imágenes en varias selecciones sin perder anteriores.
// - Evitar duplicados.
// - Carrusel anterior / siguiente.
// - Contador.
// - Indicadores.
// - Miniaturas.
// - Eliminar una imagen antes de guardar.
// - Sincronizar los archivos reales con <input type="file">.
// - Validar tipo y tamaño.
// =========================================================


// =========================================================
// CONFIGURACIÓN
// =========================================================

const IMAGEN_PRODUCTO_MAX_MB = 10;

const IMAGEN_PRODUCTO_MAX_BYTES =
    IMAGEN_PRODUCTO_MAX_MB * 1024 * 1024;


// =========================================================
// ESTADO
// =========================================================

const imagenesProductoEstado = {
    archivos: [],
    indiceActual: 0,
    urlsTemporales: [],
    inicializado: false,
};


// =========================================================
// ELEMENTOS
// =========================================================

function obtenerElementosImagenesProducto() {
    return {
        input: document.getElementById(
            "imagenesProducto"
        ),

        contenedor: document.getElementById(
            "previewImagenesProducto"
        ),

        vacio: document.getElementById(
            "imagenesEmptyState"
        ),

        visor: document.getElementById(
            "imagenesCarouselViewer"
        ),

        imagen: document.getElementById(
            "imagenCarouselActual"
        ),

        botonAnterior: document.getElementById(
            "imagenAnterior"
        ),

        botonSiguiente: document.getElementById(
            "imagenSiguiente"
        ),

        botonEliminar: document.getElementById(
            "eliminarImagenActual"
        ),

        numeroActual: document.getElementById(
            "imagenActualNumero"
        ),

        total: document.getElementById(
            "imagenesTotal"
        ),

        puntos: document.getElementById(
            "imagenesCarouselDots"
        ),

        miniaturas: document.getElementById(
            "imagenesMiniaturas"
        ),
    };
}


// =========================================================
// INICIALIZACIÓN
// =========================================================

function inicializarImagenes(contexto = document) {
    const input = contexto.querySelector(
        "#imagenesProducto"
    );

    if (!input) {
        return;
    }

    if (input.dataset.inicializado === "1") {
        return;
    }

    input.dataset.inicializado = "1";

    imagenesProductoEstado.inicializado = true;

    // -----------------------------------------------------
    // CAMBIO DE ARCHIVOS
    // -----------------------------------------------------

    input.addEventListener(
        "change",
        function () {
            agregarImagenesSeleccionadas(
                this.files
            );
        }
    );


    // -----------------------------------------------------
    // BOTONES DEL CARRUSEL
    // -----------------------------------------------------

    const elementos =
        obtenerElementosImagenesProducto();


    if (elementos.botonAnterior) {
        elementos.botonAnterior.addEventListener(
            "click",
            function () {
                imagenAnteriorProducto();
            }
        );
    }


    if (elementos.botonSiguiente) {
        elementos.botonSiguiente.addEventListener(
            "click",
            function () {
                imagenSiguienteProducto();
            }
        );
    }


    if (elementos.botonEliminar) {
        elementos.botonEliminar.addEventListener(
            "click",
            function () {
                eliminarImagenProductoActual();
            }
        );
    }


    // -----------------------------------------------------
    // ESTADO INICIAL
    // -----------------------------------------------------

    renderizarCarruselImagenes();
}


// =========================================================
// AGREGAR IMÁGENES
// =========================================================

function agregarImagenesSeleccionadas(fileList) {
    const nuevosArchivos = Array.from(
        fileList || []
    );

    if (nuevosArchivos.length === 0) {
        sincronizarInputImagenes();
        return;
    }

    let imagenesAgregadas = 0;

    for (const archivo of nuevosArchivos) {

        // -------------------------------------------------
        // VALIDAR TIPO
        // -------------------------------------------------

        if (
            !archivo.type ||
            !archivo.type.startsWith("image/")
        ) {
            alert(
                `"${archivo.name}" no es una imagen válida.`
            );

            continue;
        }


        // -------------------------------------------------
        // VALIDAR PESO
        // -------------------------------------------------

        if (
            archivo.size >
            IMAGEN_PRODUCTO_MAX_BYTES
        ) {
            alert(
                `"${archivo.name}" supera los ` +
                `${IMAGEN_PRODUCTO_MAX_MB} MB.`
            );

            continue;
        }


        // -------------------------------------------------
        // EVITAR DUPLICADOS
        // -------------------------------------------------

        const yaExiste =
            imagenesProductoEstado.archivos.some(
                function (existente) {
                    return archivosSonIguales(
                        existente,
                        archivo
                    );
                }
            );

        if (yaExiste) {
            continue;
        }


        imagenesProductoEstado.archivos.push(
            archivo
        );

        imagenesAgregadas += 1;
    }


    // =====================================================
    // MOSTRAR LA ÚLTIMA IMAGEN NUEVA
    // =====================================================

    if (imagenesAgregadas > 0) {
        imagenesProductoEstado.indiceActual =
            imagenesProductoEstado.archivos.length - 1;
    }


    sincronizarInputImagenes();

    regenerarUrlsImagenes();

    renderizarCarruselImagenes();
}


// =========================================================
// COMPARAR ARCHIVOS
// =========================================================

function archivosSonIguales(
    archivoA,
    archivoB
) {
    if (!archivoA || !archivoB) {
        return false;
    }

    return (
        archivoA.name === archivoB.name &&
        archivoA.size === archivoB.size &&
        archivoA.lastModified ===
            archivoB.lastModified
    );
}


// =========================================================
// SINCRONIZAR INPUT REAL
// =========================================================
//
// Muy importante:
//
// Django recibe:
// request.FILES.getlist("imagenes_producto")
//
// Por eso, si eliminamos una imagen visualmente,
// también debemos quitarla de input.files.
// =========================================================

function sincronizarInputImagenes() {
    const input =
        document.getElementById(
            "imagenesProducto"
        );

    if (!input) {
        return;
    }

    try {
        const dataTransfer =
            new DataTransfer();

        imagenesProductoEstado.archivos.forEach(
            function (archivo) {
                dataTransfer.items.add(
                    archivo
                );
            }
        );

        input.files =
            dataTransfer.files;

    } catch (error) {
        console.error(
            "No se pudo sincronizar el input de imágenes:",
            error
        );
    }
}


// =========================================================
// URLS TEMPORALES
// =========================================================

function liberarUrlsImagenes() {
    imagenesProductoEstado.urlsTemporales.forEach(
        function (url) {
            try {
                URL.revokeObjectURL(
                    url
                );
            } catch (error) {
                // No hacemos nada.
            }
        }
    );

    imagenesProductoEstado.urlsTemporales = [];
}


function regenerarUrlsImagenes() {
    liberarUrlsImagenes();

    imagenesProductoEstado.urlsTemporales =
        imagenesProductoEstado.archivos.map(
            function (archivo) {
                return URL.createObjectURL(
                    archivo
                );
            }
        );
}


// =========================================================
// RENDER PRINCIPAL
// =========================================================

function renderizarCarruselImagenes() {
    const elementos =
        obtenerElementosImagenesProducto();

    const total =
        imagenesProductoEstado.archivos.length;


    // =====================================================
    // SIN IMÁGENES
    // =====================================================

    if (total === 0) {
        imagenesProductoEstado.indiceActual = 0;

        if (elementos.vacio) {
            elementos.vacio.style.display =
                "flex";
        }

        if (elementos.visor) {
            elementos.visor.style.display =
                "none";
        }

        if (elementos.imagen) {
            elementos.imagen.removeAttribute(
                "src"
            );
        }

        if (elementos.puntos) {
            elementos.puntos.innerHTML =
                "";
        }

        if (elementos.miniaturas) {
            elementos.miniaturas.innerHTML =
                "";
        }

        return;
    }


    // =====================================================
    // CORREGIR ÍNDICE
    // =====================================================

    if (
        imagenesProductoEstado.indiceActual <
        0
    ) {
        imagenesProductoEstado.indiceActual =
            total - 1;
    }

    if (
        imagenesProductoEstado.indiceActual >=
        total
    ) {
        imagenesProductoEstado.indiceActual =
            0;
    }


    const indice =
        imagenesProductoEstado.indiceActual;

    const archivo =
        imagenesProductoEstado.archivos[
            indice
        ];

    const url =
        imagenesProductoEstado.urlsTemporales[
            indice
        ];


    // =====================================================
    // MOSTRAR VISOR
    // =====================================================

    if (elementos.vacio) {
        elementos.vacio.style.display =
            "none";
    }

    if (elementos.visor) {
        elementos.visor.style.display =
            "flex";
    }


    // =====================================================
    // IMAGEN
    // =====================================================

    if (
        elementos.imagen &&
        url
    ) {
        elementos.imagen.src =
            url;

        elementos.imagen.alt =
            archivo?.name ||
            "Imagen del producto";
    }


    // =====================================================
    // CONTADOR
    // =====================================================

    if (elementos.numeroActual) {
        elementos.numeroActual.textContent =
            String(
                indice + 1
            );
    }

    if (elementos.total) {
        elementos.total.textContent =
            String(
                total
            );
    }


    // =====================================================
    // FLECHAS
    // =====================================================

    actualizarFlechasImagenes();


    // =====================================================
    // INDICADORES
    // =====================================================

    renderizarPuntosImagenes();


    // =====================================================
    // MINIATURAS
    // =====================================================

    renderizarMiniaturasImagenes();
}


// =========================================================
// MOSTRAR UNA IMAGEN ESPECÍFICA
// =========================================================

function mostrarImagenProducto(indice) {
    const total =
        imagenesProductoEstado.archivos.length;

    if (total === 0) {
        return;
    }

    if (indice < 0) {
        indice = total - 1;
    }

    if (indice >= total) {
        indice = 0;
    }

    imagenesProductoEstado.indiceActual =
        indice;

    renderizarCarruselImagenes();
}


// =========================================================
// ANTERIOR
// =========================================================

function imagenAnteriorProducto() {
    mostrarImagenProducto(
        imagenesProductoEstado.indiceActual - 1
    );
}


// =========================================================
// SIGUIENTE
// =========================================================

function imagenSiguienteProducto() {
    mostrarImagenProducto(
        imagenesProductoEstado.indiceActual + 1
    );
}


// =========================================================
// ACTUALIZAR FLECHAS
// =========================================================

function actualizarFlechasImagenes() {
    const elementos =
        obtenerElementosImagenesProducto();

    const deshabilitar =
        imagenesProductoEstado.archivos.length <= 1;

    if (elementos.botonAnterior) {
        elementos.botonAnterior.disabled =
            deshabilitar;
    }

    if (elementos.botonSiguiente) {
        elementos.botonSiguiente.disabled =
            deshabilitar;
    }
}


// =========================================================
// PUNTOS DEL CARRUSEL
// =========================================================

function renderizarPuntosImagenes() {
    const contenedor =
        document.getElementById(
            "imagenesCarouselDots"
        );

    if (!contenedor) {
        return;
    }

    contenedor.innerHTML = "";

    const total =
        imagenesProductoEstado.archivos.length;

    if (total <= 1) {
        return;
    }


    imagenesProductoEstado.archivos.forEach(
        function (
            archivo,
            indice
        ) {
            const punto =
                document.createElement(
                    "button"
                );

            punto.type =
                "button";

            punto.className =
                "producto-carousel-dot";

            punto.setAttribute(
                "aria-label",
                `Ver imagen ${indice + 1}`
            );

            punto.title =
                archivo.name;


            if (
                indice ===
                imagenesProductoEstado.indiceActual
            ) {
                punto.classList.add(
                    "active"
                );
            }


            punto.addEventListener(
                "click",
                function () {
                    mostrarImagenProducto(
                        indice
                    );
                }
            );


            contenedor.appendChild(
                punto
            );
        }
    );
}


// =========================================================
// MINIATURAS
// =========================================================

function renderizarMiniaturasImagenes() {
    const contenedor =
        document.getElementById(
            "imagenesMiniaturas"
        );

    if (!contenedor) {
        return;
    }

    contenedor.innerHTML = "";


    imagenesProductoEstado.archivos.forEach(
        function (
            archivo,
            indice
        ) {

            const boton =
                document.createElement(
                    "button"
                );

            boton.type =
                "button";

            boton.className =
                "producto-carousel-thumbnail";

            boton.title =
                archivo.name;


            if (
                indice ===
                imagenesProductoEstado.indiceActual
            ) {
                boton.classList.add(
                    "active"
                );
            }


            // =============================================
            // IMAGEN
            // =============================================

            const imagen =
                document.createElement(
                    "img"
                );

            imagen.src =
                imagenesProductoEstado.urlsTemporales[
                    indice
                ];

            imagen.alt =
                archivo.name;


            // =============================================
            // BOTÓN
            // =============================================

            boton.appendChild(
                imagen
            );

            boton.addEventListener(
                "click",
                function () {
                    mostrarImagenProducto(
                        indice
                    );
                }
            );


            contenedor.appendChild(
                boton
            );
        }
    );


    // =====================================================
    // ASEGURAR QUE LA ACTIVA SEA VISIBLE
    // =====================================================

    const activa =
        contenedor.querySelector(
            ".producto-carousel-thumbnail.active"
        );

    if (activa) {
        activa.scrollIntoView({
            behavior: "smooth",
            block: "nearest",
            inline: "nearest",
        });
    }
}


// =========================================================
// ELIMINAR IMAGEN ACTUAL
// =========================================================

function eliminarImagenProductoActual() {
    const total =
        imagenesProductoEstado.archivos.length;

    if (total === 0) {
        return;
    }


    imagenesProductoEstado.archivos.splice(
        imagenesProductoEstado.indiceActual,
        1
    );


    // =====================================================
    // CORREGIR ÍNDICE
    // =====================================================

    if (
        imagenesProductoEstado.indiceActual >=
        imagenesProductoEstado.archivos.length
    ) {
        imagenesProductoEstado.indiceActual =
            Math.max(
                imagenesProductoEstado.archivos.length - 1,
                0
            );
    }


    sincronizarInputImagenes();

    regenerarUrlsImagenes();

    renderizarCarruselImagenes();
}


// =========================================================
// COMPATIBILIDAD CON FUNCIÓN ANTERIOR
// =========================================================
//
// Si otro archivo llama:
// mostrarPreviewImagenesProducto(input)
//
// seguirá funcionando.
// =========================================================

function mostrarPreviewImagenesProducto(input) {
    if (!input) {
        return;
    }

    /*
     * Si el input ya es el oficial, usamos la misma
     * lógica de acumulación.
     */
    agregarImagenesSeleccionadas(
        input.files
    );
}


// =========================================================
// LIMPIAR TODAS LAS IMÁGENES
// =========================================================

function limpiarImagenesProducto() {
    imagenesProductoEstado.archivos = [];
    imagenesProductoEstado.indiceActual = 0;

    liberarUrlsImagenes();

    sincronizarInputImagenes();

    renderizarCarruselImagenes();
}


// =========================================================
// CONTADOR
// =========================================================

function cantidadImagenesProducto() {
    return (
        imagenesProductoEstado.archivos.length
    );
}


// =========================================================
// OBTENER IMÁGENES
// =========================================================

function obtenerImagenesProducto() {
    return Array.from(
        imagenesProductoEstado.archivos
    );
}


// =========================================================
// TAMAÑO DE ARCHIVO
// =========================================================

function formatearTamanoArchivo(bytes) {
    if (
        bytes === null ||
        bytes === undefined
    ) {
        return "0 B";
    }

    if (bytes < 1024) {
        return `${bytes} B`;
    }

    if (
        bytes <
        1024 * 1024
    ) {
        return (
            (bytes / 1024).toFixed(1) +
            " KB"
        );
    }

    return (
        (
            bytes /
            1024 /
            1024
        ).toFixed(2) +
        " MB"
    );
}


// =========================================================
// VALIDAR
// =========================================================

function validarImagenesProducto() {
    const archivos =
        obtenerImagenesProducto();

    for (
        const archivo
        of archivos
    ) {

        if (
            !archivo.type ||
            !archivo.type.startsWith("image/")
        ) {
            alert(
                `"${archivo.name}" no es una imagen válida.`
            );

            return false;
        }


        if (
            archivo.size >
            IMAGEN_PRODUCTO_MAX_BYTES
        ) {
            alert(
                `"${archivo.name}" supera los ` +
                `${IMAGEN_PRODUCTO_MAX_MB} MB.`
            );

            return false;
        }
    }

    return true;
}


// =========================================================
// VALIDACIÓN ANTES DE ENVIAR EL FORMULARIO
// =========================================================

function inicializarValidacionFormularioImagenes() {
    const formulario =
        document.getElementById(
            "catalogoForm"
        );

    if (!formulario) {
        return;
    }


    if (
        formulario.dataset.imagenesValidacion ===
        "1"
    ) {
        return;
    }


    formulario.dataset.imagenesValidacion =
        "1";


    formulario.addEventListener(
        "submit",
        function (event) {

            if (
                !validarImagenesProducto()
            ) {
                event.preventDefault();
                event.stopPropagation();
            }

        }
    );
}


// =========================================================
// LIMPIEZA AL SALIR
// =========================================================

window.addEventListener(
    "beforeunload",
    function () {
        liberarUrlsImagenes();
    }
);


// =========================================================
// INICIALIZACIÓN GENERAL
// =========================================================

document.addEventListener(
    "DOMContentLoaded",
    function () {

        inicializarImagenes();

        inicializarValidacionFormularioImagenes();

    }
);