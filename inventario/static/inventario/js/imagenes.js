(function () {
    "use strict";

    // =========================================================
    // CONFIGURACIÓN
    // =========================================================

    const MAX_MB = 10;
    const MAX_BYTES = MAX_MB * 1024 * 1024;

    const estado = {
        archivos: [],
        urls: [],
        indice: 0,
        zoom: 1,
        zoomMin: 0.5,
        zoomMax: 4,
        zoomPaso: 0.25,
        inicializado: false
    };


    // =========================================================
    // ELEMENTOS
    // =========================================================

    function obtenerElementos() {
        return {
            input:
                document.getElementById(
                    "imagenesProducto"
                ),

            vacio:
                document.getElementById(
                    "imagenesEmptyState"
                ),

            visor:
                document.getElementById(
                    "imagenesCarouselViewer"
                ),

            imagen:
                document.getElementById(
                    "imagenCarouselActual"
                ),

            anterior:
                document.getElementById(
                    "imagenAnterior"
                ),

            siguiente:
                document.getElementById(
                    "imagenSiguiente"
                ),

            eliminar:
                document.getElementById(
                    "eliminarImagenActual"
                ),

            ampliar:
                document.getElementById(
                    "ampliarImagenActual"
                ),

            numero:
                document.getElementById(
                    "imagenActualNumero"
                ),

            total:
                document.getElementById(
                    "imagenesTotal"
                ),

            puntos:
                document.getElementById(
                    "imagenesCarouselDots"
                ),

            miniaturas:
                document.getElementById(
                    "imagenesMiniaturas"
                ),

            fullscreen:
                document.getElementById(
                    "imagenFullscreen"
                ),

            fullscreenImg:
                document.getElementById(
                    "imagenFullscreenImg"
                ),

            fullscreenNombre:
                document.getElementById(
                    "imagenFullscreenNombre"
                ),

            fullscreenContador:
                document.getElementById(
                    "imagenFullscreenContador"
                ),

            fullscreenAnterior:
                document.getElementById(
                    "imagenFullscreenAnterior"
                ),

            fullscreenSiguiente:
                document.getElementById(
                    "imagenFullscreenSiguiente"
                ),

            fullscreenCerrar:
                document.getElementById(
                    "cerrarImagenFullscreen"
                ),

            zoomMas:
                document.getElementById(
                    "imagenZoomMas"
                ),

            zoomMenos:
                document.getElementById(
                    "imagenZoomMenos"
                ),

            zoomReset:
                document.getElementById(
                    "imagenZoomReset"
                ),

            zoomNivel:
                document.getElementById(
                    "imagenZoomNivel"
                )
        };
    }


    // =========================================================
    // VALIDAR ARCHIVO
    // =========================================================

    function archivoValido(archivo) {
        if (!archivo) {
            return false;
        }

        if (
            !archivo.type ||
            !archivo.type.startsWith("image/")
        ) {
            alert(
                `"${archivo.name}" no es una imagen válida.`
            );

            return false;
        }

        if (archivo.size > MAX_BYTES) {
            alert(
                `"${archivo.name}" supera los ${MAX_MB} MB.`
            );

            return false;
        }

        return true;
    }


    // =========================================================
    // DUPLICADOS
    // =========================================================

    function archivoDuplicado(archivo) {
        return estado.archivos.some(
            function (existente) {
                return (
                    existente.name === archivo.name &&
                    existente.size === archivo.size &&
                    existente.lastModified ===
                        archivo.lastModified
                );
            }
        );
    }


    // =========================================================
    // URLS
    // =========================================================

    function liberarUrls() {
        estado.urls.forEach(
            function (url) {
                try {
                    URL.revokeObjectURL(url);
                } catch (error) {
                    // Ignorar
                }
            }
        );

        estado.urls = [];
    }


    function generarUrls() {
        liberarUrls();

        estado.urls = estado.archivos.map(
            function (archivo) {
                return URL.createObjectURL(
                    archivo
                );
            }
        );
    }


    // =========================================================
    // SINCRONIZAR INPUT
    // =========================================================

    function sincronizarInput() {
        const input =
            document.getElementById(
                "imagenesProducto"
            );

        if (!input) {
            return;
        }

        /*
         * DataTransfer permite reconstruir input.files
         * después de eliminar/agregar fotografías.
         */
        try {
            const transferencia =
                new DataTransfer();

            estado.archivos.forEach(
                function (archivo) {
                    transferencia.items.add(
                        archivo
                    );
                }
            );

            input.files =
                transferencia.files;

        } catch (error) {
            console.error(
                "Error sincronizando imágenes:",
                error
            );
        }
    }


    // =========================================================
    // AGREGAR
    // =========================================================

    function agregarArchivos(fileList) {
        const nuevos =
            Array.from(
                fileList || []
            );

        if (nuevos.length === 0) {
            return;
        }

        let cantidadAgregada = 0;

        nuevos.forEach(
            function (archivo) {

                if (!archivoValido(archivo)) {
                    return;
                }

                if (archivoDuplicado(archivo)) {
                    return;
                }

                estado.archivos.push(
                    archivo
                );

                cantidadAgregada += 1;
            }
        );


        if (cantidadAgregada === 0) {
            sincronizarInput();
            return;
        }


        estado.indice =
            estado.archivos.length - 1;


        generarUrls();

        sincronizarInput();

        renderizar();
    }


    // =========================================================
    // RENDER PRINCIPAL
    // =========================================================

    function renderizar() {
        const e =
            obtenerElementos();

        const total =
            estado.archivos.length;


        // -----------------------------------------------------
        // VACÍO
        // -----------------------------------------------------

        if (total === 0) {

            estado.indice = 0;

            if (e.vacio) {
                e.vacio.style.display =
                    "flex";
            }

            if (e.visor) {
                e.visor.style.display =
                    "none";
            }

            if (e.imagen) {
                e.imagen.removeAttribute(
                    "src"
                );
            }

            if (e.puntos) {
                e.puntos.innerHTML =
                    "";
            }

            if (e.miniaturas) {
                e.miniaturas.innerHTML =
                    "";
            }

            cerrarFullscreen();

            return;
        }


        // -----------------------------------------------------
        // ÍNDICE
        // -----------------------------------------------------

        if (estado.indice < 0) {
            estado.indice =
                total - 1;
        }

        if (estado.indice >= total) {
            estado.indice = 0;
        }


        const archivo =
            estado.archivos[
                estado.indice
            ];

        const url =
            estado.urls[
                estado.indice
            ];


        // -----------------------------------------------------
        // MOSTRAR VISOR
        // -----------------------------------------------------

        if (e.vacio) {
            e.vacio.style.display =
                "none";
        }

        if (e.visor) {
            e.visor.style.display =
                "flex";
        }


        // -----------------------------------------------------
        // IMAGEN
        // -----------------------------------------------------

        if (e.imagen) {
            e.imagen.src =
                url;

            e.imagen.alt =
                archivo.name;
        }


        // -----------------------------------------------------
        // CONTADOR
        // -----------------------------------------------------

        if (e.numero) {
            e.numero.textContent =
                String(
                    estado.indice + 1
                );
        }

        if (e.total) {
            e.total.textContent =
                String(total);
        }


        actualizarFlechas();

        renderizarPuntos();

        renderizarMiniaturas();


        if (fullscreenAbierto()) {
            actualizarFullscreen();
        }
    }


    // =========================================================
    // MOSTRAR IMAGEN
    // =========================================================

    function mostrarImagen(indice) {
        const total =
            estado.archivos.length;

        if (total === 0) {
            return;
        }

        if (indice < 0) {
            indice =
                total - 1;
        }

        if (indice >= total) {
            indice = 0;
        }

        estado.indice =
            indice;

        renderizar();
    }


    function anterior() {
        mostrarImagen(
            estado.indice - 1
        );
    }


    function siguiente() {
        mostrarImagen(
            estado.indice + 1
        );
    }


    // =========================================================
    // FLECHAS
    // =========================================================

    function actualizarFlechas() {
        const e =
            obtenerElementos();

        const deshabilitar =
            estado.archivos.length <= 1;

        if (e.anterior) {
            e.anterior.disabled =
                deshabilitar;
        }

        if (e.siguiente) {
            e.siguiente.disabled =
                deshabilitar;
        }

        if (e.fullscreenAnterior) {
            e.fullscreenAnterior.disabled =
                deshabilitar;
        }

        if (e.fullscreenSiguiente) {
            e.fullscreenSiguiente.disabled =
                deshabilitar;
        }
    }


    // =========================================================
    // PUNTOS
    // =========================================================

    function renderizarPuntos() {
        const contenedor =
            document.getElementById(
                "imagenesCarouselDots"
            );

        if (!contenedor) {
            return;
        }

        contenedor.innerHTML = "";

        if (
            estado.archivos.length <= 1
        ) {
            return;
        }


        estado.archivos.forEach(
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

                punto.title =
                    archivo.name;

                punto.setAttribute(
                    "aria-label",
                    `Ver imagen ${indice + 1}`
                );


                if (
                    indice ===
                    estado.indice
                ) {
                    punto.classList.add(
                        "active"
                    );
                }


                punto.addEventListener(
                    "click",
                    function () {
                        mostrarImagen(
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

    function renderizarMiniaturas() {
        const contenedor =
            document.getElementById(
                "imagenesMiniaturas"
            );

        if (!contenedor) {
            return;
        }

        contenedor.innerHTML = "";


        estado.archivos.forEach(
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
                    estado.indice
                ) {
                    boton.classList.add(
                        "active"
                    );
                }


                const imagen =
                    document.createElement(
                        "img"
                    );

                imagen.src =
                    estado.urls[
                        indice
                    ];

                imagen.alt =
                    archivo.name;


                boton.appendChild(
                    imagen
                );


                boton.addEventListener(
                    "click",
                    function () {
                        mostrarImagen(
                            indice
                        );
                    }
                );


                contenedor.appendChild(
                    boton
                );
            }
        );
    }


    // =========================================================
    // ELIMINAR
    // =========================================================

    function eliminarActual() {
        if (
            estado.archivos.length === 0
        ) {
            return;
        }


        estado.archivos.splice(
            estado.indice,
            1
        );


        if (
            estado.indice >=
            estado.archivos.length
        ) {
            estado.indice =
                Math.max(
                    estado.archivos.length - 1,
                    0
                );
        }


        generarUrls();

        sincronizarInput();

        renderizar();
    }


    // =========================================================
    // FULLSCREEN
    // =========================================================

    function fullscreenAbierto() {
        const fullscreen =
            document.getElementById(
                "imagenFullscreen"
            );

        return Boolean(
            fullscreen &&
            fullscreen.classList.contains(
                "activo"
            )
        );
    }


    function abrirFullscreen() {
        if (
            estado.archivos.length === 0
        ) {
            return;
        }

        const e =
            obtenerElementos();

        if (!e.fullscreen) {
            return;
        }


        e.fullscreen.classList.add(
            "activo"
        );

        e.fullscreen.setAttribute(
            "aria-hidden",
            "false"
        );

        document.body.classList.add(
            "imagen-fullscreen-abierto"
        );


        estado.zoom = 1;

        actualizarFullscreen();
    }


    function cerrarFullscreen() {
        const fullscreen =
            document.getElementById(
                "imagenFullscreen"
            );

        if (!fullscreen) {
            return;
        }

        fullscreen.classList.remove(
            "activo"
        );

        fullscreen.setAttribute(
            "aria-hidden",
            "true"
        );

        document.body.classList.remove(
            "imagen-fullscreen-abierto"
        );

        estado.zoom = 1;

        aplicarZoom();
    }


    function actualizarFullscreen() {
        if (
            estado.archivos.length === 0
        ) {
            return;
        }

        const e =
            obtenerElementos();

        const archivo =
            estado.archivos[
                estado.indice
            ];

        const url =
            estado.urls[
                estado.indice
            ];


        if (e.fullscreenImg) {
            e.fullscreenImg.src =
                url;

            e.fullscreenImg.alt =
                archivo.name;
        }

        if (e.fullscreenNombre) {
            e.fullscreenNombre.textContent =
                archivo.name;
        }

        if (e.fullscreenContador) {
            e.fullscreenContador.textContent =
                `${estado.indice + 1} de ${estado.archivos.length}`;
        }


        estado.zoom = 1;

        aplicarZoom();

        actualizarFlechas();
    }


    // =========================================================
    // ZOOM
    // =========================================================

    function aplicarZoom() {
        const e =
            obtenerElementos();

        if (e.fullscreenImg) {
            e.fullscreenImg.style.transform =
                `scale(${estado.zoom})`;
        }

        if (e.zoomNivel) {
            e.zoomNivel.textContent =
                `${Math.round(
                    estado.zoom * 100
                )}%`;
        }
    }


    function cambiarZoom(cambio) {
        let nuevo =
            estado.zoom + cambio;

        nuevo =
            Math.max(
                estado.zoomMin,
                nuevo
            );

        nuevo =
            Math.min(
                estado.zoomMax,
                nuevo
            );

        estado.zoom =
            nuevo;

        aplicarZoom();
    }


    function resetZoom() {
        estado.zoom = 1;

        aplicarZoom();
    }


    // =========================================================
    // VALIDACIÓN
    // =========================================================

    function validarImagenesProducto() {
        for (
            const archivo
            of estado.archivos
        ) {

            if (
                !archivo.type ||
                !archivo.type.startsWith(
                    "image/"
                )
            ) {
                alert(
                    `"${archivo.name}" no es una imagen válida.`
                );

                return false;
            }

            if (
                archivo.size >
                MAX_BYTES
            ) {
                alert(
                    `"${archivo.name}" supera los ${MAX_MB} MB.`
                );

                return false;
            }
        }

        return true;
    }


    // =========================================================
    // API COMPATIBLE
    // =========================================================

    function limpiarImagenesProducto() {
        estado.archivos = [];
        estado.indice = 0;

        liberarUrls();

        sincronizarInput();

        renderizar();
    }


    function cantidadImagenesProducto() {
        return estado.archivos.length;
    }


    function obtenerImagenesProducto() {
        return Array.from(
            estado.archivos
        );
    }


    function mostrarPreviewImagenesProducto(
        input
    ) {
        if (!input) {
            return;
        }

        agregarArchivos(
            input.files
        );
    }


    function formatearTamanoArchivo(
        bytes
    ) {
        if (bytes < 1024) {
            return `${bytes} B`;
        }

        if (
            bytes <
            1024 * 1024
        ) {
            return (
                (bytes / 1024)
                    .toFixed(1) +
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


    // Exponer funciones por compatibilidad
    window.validarImagenesProducto =
        validarImagenesProducto;

    window.limpiarImagenesProducto =
        limpiarImagenesProducto;

    window.cantidadImagenesProducto =
        cantidadImagenesProducto;

    window.obtenerImagenesProducto =
        obtenerImagenesProducto;

    window.mostrarPreviewImagenesProducto =
        mostrarPreviewImagenesProducto;

    window.formatearTamanoArchivo =
        formatearTamanoArchivo;


    // =========================================================
    // INICIALIZAR
    // =========================================================

    function inicializar() {
        if (estado.inicializado) {
            return;
        }

        const e =
            obtenerElementos();


        if (!e.input) {
            console.error(
                "[IMÁGENES] No se encontró #imagenesProducto"
            );

            return;
        }


        if (!e.visor) {
            console.error(
                "[IMÁGENES] No se encontró #imagenesCarouselViewer"
            );
        }


        if (!e.imagen) {
            console.error(
                "[IMÁGENES] No se encontró #imagenCarouselActual"
            );
        }


        estado.inicializado = true;


        // -----------------------------------------------------
        // INPUT
        // -----------------------------------------------------

        e.input.addEventListener(
            "change",
            function (event) {

                /*
                 * Copiamos los archivos ANTES de modificar
                 * input.files.
                 */
                const seleccion =
                    Array.from(
                        event.target.files ||
                        []
                    );

                agregarArchivos(
                    seleccion
                );
            }
        );


        // -----------------------------------------------------
        // CARRUSEL
        // -----------------------------------------------------

        if (e.anterior) {
            e.anterior.addEventListener(
                "click",
                anterior
            );
        }


        if (e.siguiente) {
            e.siguiente.addEventListener(
                "click",
                siguiente
            );
        }


        if (e.eliminar) {
            e.eliminar.addEventListener(
                "click",
                eliminarActual
            );
        }


        if (e.ampliar) {
            e.ampliar.addEventListener(
                "click",
                abrirFullscreen
            );
        }


        if (e.imagen) {
            e.imagen.addEventListener(
                "click",
                abrirFullscreen
            );
        }


        // -----------------------------------------------------
        // FULLSCREEN
        // -----------------------------------------------------

        if (e.fullscreenCerrar) {
            e.fullscreenCerrar.addEventListener(
                "click",
                cerrarFullscreen
            );
        }


        if (e.fullscreenAnterior) {
            e.fullscreenAnterior.addEventListener(
                "click",
                anterior
            );
        }


        if (e.fullscreenSiguiente) {
            e.fullscreenSiguiente.addEventListener(
                "click",
                siguiente
            );
        }


        if (e.zoomMas) {
            e.zoomMas.addEventListener(
                "click",
                function () {
                    cambiarZoom(
                        estado.zoomPaso
                    );
                }
            );
        }


        if (e.zoomMenos) {
            e.zoomMenos.addEventListener(
                "click",
                function () {
                    cambiarZoom(
                        -estado.zoomPaso
                    );
                }
            );
        }


        if (e.zoomReset) {
            e.zoomReset.addEventListener(
                "click",
                resetZoom
            );
        }


        // -----------------------------------------------------
        // RUEDA DEL MOUSE
        // -----------------------------------------------------

        if (e.fullscreenImg) {

            e.fullscreenImg.addEventListener(
                "wheel",
                function (event) {

                    event.preventDefault();

                    if (event.deltaY < 0) {
                        cambiarZoom(
                            estado.zoomPaso
                        );
                    } else {
                        cambiarZoom(
                            -estado.zoomPaso
                        );
                    }

                },
                {
                    passive: false
                }
            );
        }


        // -----------------------------------------------------
        // FORMULARIO
        // -----------------------------------------------------

        const formulario =
            document.getElementById(
                "catalogoForm"
            );

        if (formulario) {

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


        renderizar();
    }


    // =========================================================
    // TECLADO
    // =========================================================

    document.addEventListener(
        "keydown",
        function (event) {

            if (!fullscreenAbierto()) {
                return;
            }


            if (event.key === "Escape") {
                cerrarFullscreen();

                return;
            }


            if (event.key === "ArrowLeft") {
                anterior();

                return;
            }


            if (event.key === "ArrowRight") {
                siguiente();

                return;
            }


            if (
                event.key === "+" ||
                event.key === "="
            ) {
                cambiarZoom(
                    estado.zoomPaso
                );

                return;
            }


            if (event.key === "-") {
                cambiarZoom(
                    -estado.zoomPaso
                );

                return;
            }


            if (event.key === "0") {
                resetZoom();
            }
        }
    );


    // =========================================================
    // LIMPIEZA
    // =========================================================

    window.addEventListener(
        "beforeunload",
        liberarUrls
    );


    // =========================================================
    // ARRANQUE
    // =========================================================

    if (
        document.readyState ===
        "loading"
    ) {

        document.addEventListener(
            "DOMContentLoaded",
            inicializar
        );

    } else {

        inicializar();

    }

})();