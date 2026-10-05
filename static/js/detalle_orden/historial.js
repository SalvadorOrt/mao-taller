/* ============================================================
   HISTORIAL DEL VEHÍCULO DENTRO DE DETALLE DE ORDEN
   ============================================================

   Responsabilidades:

   - Abrir el modal.
   - Consultar el historial por fetch.
   - Mostrar estado de carga.
   - Mostrar errores.
   - Insertar el HTML recibido desde Django.
   - Seleccionar una visita.
   - Navegar Anterior / Siguiente.
   - Mantener sincronizada la línea de tiempo.
   - Cerrar con botón, ESC o clic fuera.
   - Evitar solicitudes duplicadas.

   ============================================================ */


/* ============================================================
   ESTADO GENERAL
============================================================ */

let historialOrdenAbortController = null;

let historialOrdenCargado = false;

let historialOrdenCargando = false;

let historialOrdenIdActivo = null;

let historialOrdenUltimoFoco = null;


/* ============================================================
   OBTENER ELEMENTOS PRINCIPALES
============================================================ */

function obtenerModalHistorialOrden() {
    return document.getElementById(
        "modalHistorialOrden"
    );
}


function obtenerContenidoHistorialOrden() {
    return document.getElementById(
        "historialOrdenContenido"
    );
}


function obtenerCargandoHistorialOrden() {
    return document.getElementById(
        "historialOrdenCargando"
    );
}


function obtenerErrorHistorialOrden() {
    return document.getElementById(
        "historialOrdenError"
    );
}


function obtenerErrorTextoHistorialOrden() {
    return document.getElementById(
        "historialOrdenErrorTexto"
    );
}


/* ============================================================
   MOSTRAR / OCULTAR ESTADOS
============================================================ */

function mostrarCargaHistorialOrden() {

    const cargando =
        obtenerCargandoHistorialOrden();

    const contenido =
        obtenerContenidoHistorialOrden();

    const error =
        obtenerErrorHistorialOrden();


    if (cargando) {
        cargando.style.display = "block";
    }

    if (contenido) {
        contenido.style.display = "none";
    }

    if (error) {
        error.style.display = "none";
    }

}


function ocultarCargaHistorialOrden() {

    const cargando =
        obtenerCargandoHistorialOrden();

    if (cargando) {
        cargando.style.display = "none";
    }

}


function mostrarContenidoHistorialOrden() {

    const contenido =
        obtenerContenidoHistorialOrden();

    const error =
        obtenerErrorHistorialOrden();

    if (contenido) {
        contenido.style.display = "block";
    }

    if (error) {
        error.style.display = "none";
    }

}


function mostrarErrorHistorialOrden(
    mensaje = "No fue posible cargar el historial."
) {

    const cargando =
        obtenerCargandoHistorialOrden();

    const contenido =
        obtenerContenidoHistorialOrden();

    const error =
        obtenerErrorHistorialOrden();

    const errorTexto =
        obtenerErrorTextoHistorialOrden();


    if (cargando) {
        cargando.style.display = "none";
    }


    if (contenido) {
        contenido.style.display = "none";
    }


    if (errorTexto) {
        errorTexto.textContent = mensaje;
    }


    if (error) {
        error.style.display = "block";
    }

}


/* ============================================================
   ABRIR MODAL
============================================================ */

async function abrirModalHistorialOrden() {

    const modal =
        obtenerModalHistorialOrden();

    if (!modal) {

        console.error(
            "No se encontró #modalHistorialOrden."
        );

        return;
    }


    /* --------------------------------------------------------
       Recordar elemento que tenía foco
    -------------------------------------------------------- */

    historialOrdenUltimoFoco =
        document.activeElement;


    /* --------------------------------------------------------
       Abrir modal
    -------------------------------------------------------- */

    modal.style.display = "flex";

    modal.setAttribute(
        "aria-hidden",
        "false"
    );


    document.body.classList.add(
        "historial-orden-abierto"
    );


    /* --------------------------------------------------------
       Si ya está cargado no consultamos nuevamente
    -------------------------------------------------------- */

    if (historialOrdenCargado) {

        mostrarContenidoHistorialOrden();

        inicializarHistorialOrden();

        enfocarCerrarHistorialOrden();

        return;
    }


    /* --------------------------------------------------------
       Evitar doble llamada
    -------------------------------------------------------- */

    if (historialOrdenCargando) {
        return;
    }


    /* --------------------------------------------------------
       URL configurada en modal_historial.html
    -------------------------------------------------------- */

    const url = (
        modal.dataset.historialUrl || ""
    ).trim();


    if (!url) {

        mostrarErrorHistorialOrden(
            "No se configuró la URL del historial."
        );

        return;
    }


    await cargarHistorialOrden(
        url
    );

}


/* ============================================================
   CARGAR HISTORIAL POR FETCH
============================================================ */

async function cargarHistorialOrden(url) {

    historialOrdenCargando = true;

    mostrarCargaHistorialOrden();


    /* --------------------------------------------------------
       Cancelar llamada anterior si existe
    -------------------------------------------------------- */

    if (historialOrdenAbortController) {

        historialOrdenAbortController.abort();

    }


    historialOrdenAbortController =
        new AbortController();


    try {

        const respuesta = await fetch(
            url,
            {
                method: "GET",

                headers: {
                    "X-Requested-With":
                        "XMLHttpRequest"
                },

                credentials:
                    "same-origin",

                signal:
                    historialOrdenAbortController.signal
            }
        );


        if (!respuesta.ok) {

            throw new Error(
                `Error HTTP ${respuesta.status}`
            );

        }


        const html =
            await respuesta.text();


        const contenido =
            obtenerContenidoHistorialOrden();


        if (!contenido) {

            throw new Error(
                "No se encontró el contenedor del historial."
            );

        }


        contenido.innerHTML = html;


        historialOrdenCargado = true;

        historialOrdenCargando = false;


        ocultarCargaHistorialOrden();

        mostrarContenidoHistorialOrden();


        /* ----------------------------------------------------
           Inicializar carrusel recién insertado
        ---------------------------------------------------- */

        inicializarHistorialOrden();


        enfocarCerrarHistorialOrden();


    } catch (error) {

        historialOrdenCargando = false;


        if (
            error &&
            error.name === "AbortError"
        ) {

            return;

        }


        console.error(
            "Error cargando historial:",
            error
        );


        mostrarErrorHistorialOrden(
            "No fue posible cargar el historial del vehículo."
        );

    }

}


/* ============================================================
   INICIALIZAR HISTORIAL
============================================================ */

function inicializarHistorialOrden() {

    const contenido =
        obtenerContenidoHistorialOrden();

    if (!contenido) {
        return;
    }


    /* --------------------------------------------------------
       Buscar visita marcada como predeterminada.

       En nuestro template:
       la última visita anterior es la predeterminada.
    -------------------------------------------------------- */

    const botonPredeterminado =
        contenido.querySelector(
            "[data-historial-default='true']"
        );


    if (botonPredeterminado) {

        const ordenId =
            botonPredeterminado.dataset.ordenId;

        if (ordenId) {

            seleccionarOrdenHistorialModal(
                ordenId,
                false
            );

            return;

        }

    }


    /* --------------------------------------------------------
       Fallback:
       seleccionar último elemento de timeline.
    -------------------------------------------------------- */

    const botones =
        contenido.querySelectorAll(
            ".hm-timeline-button"
        );


    if (botones.length > 0) {

        const ultimo =
            botones[
                botones.length - 1
            ];

        const ordenId =
            ultimo.dataset.ordenId;


        if (ordenId) {

            seleccionarOrdenHistorialModal(
                ordenId,
                false
            );

        }

    }

}


/* ============================================================
   SELECCIONAR UNA OT DEL HISTORIAL
============================================================ */

function seleccionarOrdenHistorialModal(
    ordenId,
    animarScroll = true
) {

    if (!ordenId) {
        return;
    }


    const contenido =
        obtenerContenidoHistorialOrden();

    if (!contenido) {
        return;
    }


    ordenId =
        String(ordenId);


    /* --------------------------------------------------------
       Timeline
    -------------------------------------------------------- */

    const timelineItems =
        contenido.querySelectorAll(
            ".hm-timeline-item"
        );


    timelineItems.forEach(
        (item) => {

            item.classList.remove(
                "active"
            );

        }
    );


    /* --------------------------------------------------------
       Paneles
    -------------------------------------------------------- */

    const paneles =
        contenido.querySelectorAll(
            ".hm-panel"
        );


    paneles.forEach(
        (panel) => {

            panel.classList.remove(
                "active"
            );

        }
    );


    /* --------------------------------------------------------
       Elementos seleccionados
    -------------------------------------------------------- */

    const timelineItem =
        document.getElementById(
            `hm-timeline-item-${ordenId}`
        );


    const panel =
        document.getElementById(
            `hm-panel-${ordenId}`
        );


    if (!timelineItem || !panel) {

        console.warn(
            "No se encontró la visita del historial:",
            ordenId
        );

        return;

    }


    timelineItem.classList.add(
        "active"
    );


    panel.classList.add(
        "active"
    );


    historialOrdenIdActivo =
        ordenId;


    /* --------------------------------------------------------
       Centrar visita seleccionada en timeline
    -------------------------------------------------------- */

    if (animarScroll) {

        timelineItem.scrollIntoView({
            behavior: "smooth",
            inline: "center",
            block: "nearest"
        });

    } else {

        timelineItem.scrollIntoView({
            behavior: "auto",
            inline: "center",
            block: "nearest"
        });

    }


    /* --------------------------------------------------------
       Al cambiar de visita regresar al inicio del contenido.

       Solo desplazamos el BODY del modal.
       No movemos la página de detalle_orden.
    -------------------------------------------------------- */

    const bodyModal =
        document.querySelector(
            "#modalHistorialOrden .historial-orden-body"
        );


    if (bodyModal) {

        bodyModal.scrollTo({
            top: 0,
            behavior:
                animarScroll
                    ? "smooth"
                    : "auto"
        });

    }


    actualizarNavegacionHistorialOrden();

}


/* ============================================================
   OBTENER IDS DEL CARRUSEL
============================================================ */

function obtenerIdsHistorialOrden() {

    const contenido =
        obtenerContenidoHistorialOrden();

    if (!contenido) {
        return [];
    }


    return Array.from(
        contenido.querySelectorAll(
            ".hm-timeline-button[data-orden-id]"
        )
    )
        .map(
            (boton) =>
                String(
                    boton.dataset.ordenId || ""
                )
        )
        .filter(
            (ordenId) =>
                ordenId !== ""
        );

}


/* ============================================================
   MOVER ANTERIOR / SIGUIENTE
============================================================ */

function moverHistorialModal(
    direccion
) {

    const ids =
        obtenerIdsHistorialOrden();


    if (ids.length === 0) {
        return;
    }


    /* --------------------------------------------------------
       Si por alguna razón no existe activo,
       seleccionar la última visita.
    -------------------------------------------------------- */

    if (!historialOrdenIdActivo) {

        seleccionarOrdenHistorialModal(
            ids[ids.length - 1]
        );

        return;
    }


    const indiceActual =
        ids.indexOf(
            String(
                historialOrdenIdActivo
            )
        );


    if (indiceActual === -1) {

        seleccionarOrdenHistorialModal(
            ids[ids.length - 1]
        );

        return;
    }


    const paso =
        Number(direccion);


    if (
        paso !== -1 &&
        paso !== 1
    ) {

        return;

    }


    const nuevoIndice =
        indiceActual + paso;


    /* --------------------------------------------------------
       No hacemos loop.

       Ejemplo:
       visita más antigua:
       no puede ir más atrás.

       visita más reciente:
       no puede avanzar.
    -------------------------------------------------------- */

    if (
        nuevoIndice < 0 ||
        nuevoIndice >= ids.length
    ) {

        return;

    }


    seleccionarOrdenHistorialModal(
        ids[nuevoIndice]
    );

}


/* ============================================================
   ACTUALIZAR ESTADO DE BOTONES ANTERIOR / SIGUIENTE
============================================================ */

function actualizarNavegacionHistorialOrden() {

    const contenido =
        obtenerContenidoHistorialOrden();

    if (!contenido) {
        return;
    }


    const ids =
        obtenerIdsHistorialOrden();


    const indiceActual =
        ids.indexOf(
            String(
                historialOrdenIdActivo || ""
            )
        );


    const panelActivo =
        contenido.querySelector(
            ".hm-panel.active"
        );


    if (!panelActivo) {
        return;
    }


    const botones =
        panelActivo.querySelectorAll(
            ".hm-carousel-button"
        );


    if (botones.length < 2) {
        return;
    }


    const botonAnterior =
        botones[0];

    const botonSiguiente =
        botones[1];


    const esPrimera =
        indiceActual <= 0;


    const esUltima =
        indiceActual >=
        ids.length - 1;


    botonAnterior.disabled =
        esPrimera;


    botonSiguiente.disabled =
        esUltima;


    /* --------------------------------------------------------
       Estilo visual del estado disabled
    -------------------------------------------------------- */

    [
        botonAnterior,
        botonSiguiente
    ].forEach(
        (boton) => {

            if (boton.disabled) {

                boton.style.opacity =
                    "0.42";

                boton.style.cursor =
                    "default";

            } else {

                boton.style.opacity =
                    "";

                boton.style.cursor =
                    "";

            }

        }
    );

}


/* ============================================================
   CERRAR MODAL
============================================================ */

function cerrarModalHistorialOrden() {

    const modal =
        obtenerModalHistorialOrden();

    if (!modal) {
        return;
    }


    modal.style.display = "none";


    modal.setAttribute(
        "aria-hidden",
        "true"
    );


    document.body.classList.remove(
        "historial-orden-abierto"
    );


    /* --------------------------------------------------------
       Cancelar carga pendiente
    -------------------------------------------------------- */

    if (
        historialOrdenAbortController &&
        historialOrdenCargando
    ) {

        historialOrdenAbortController.abort();

        historialOrdenCargando = false;

    }


    /* --------------------------------------------------------
       Regresar foco al botón que abrió el modal
    -------------------------------------------------------- */

    if (
        historialOrdenUltimoFoco &&
        typeof historialOrdenUltimoFoco.focus
            === "function"
    ) {

        historialOrdenUltimoFoco.focus();

    }

}


/* ============================================================
   RECARGAR HISTORIAL
   Útil si posteriormente quieres refrescar sin recargar OT.
============================================================ */

async function recargarHistorialOrden() {

    const modal =
        obtenerModalHistorialOrden();

    if (!modal) {
        return;
    }


    const url = (
        modal.dataset.historialUrl || ""
    ).trim();


    if (!url) {
        return;
    }


    historialOrdenCargado = false;

    historialOrdenIdActivo = null;


    const contenido =
        obtenerContenidoHistorialOrden();


    if (contenido) {

        contenido.innerHTML = "";

    }


    await cargarHistorialOrden(
        url
    );

}


/* ============================================================
   ENFOCAR BOTÓN CERRAR
============================================================ */

function enfocarCerrarHistorialOrden() {

    const modal =
        obtenerModalHistorialOrden();

    if (!modal) {
        return;
    }


    const botonCerrar =
        modal.querySelector(
            ".historial-orden-cerrar"
        );


    if (botonCerrar) {

        setTimeout(
            () => {
                botonCerrar.focus();
            },
            20
        );

    }

}


/* ============================================================
   TECLADO
============================================================ */

document.addEventListener(
    "keydown",
    function (
        event
    ) {

        const modal =
            obtenerModalHistorialOrden();


        if (
            !modal ||
            modal.style.display !== "flex"
        ) {

            return;

        }


        /* ----------------------------------------------------
           ESC
        ---------------------------------------------------- */

        if (
            event.key === "Escape"
        ) {

            event.preventDefault();

            cerrarModalHistorialOrden();

            return;

        }


        /* ----------------------------------------------------
           FLECHA IZQUIERDA
        ---------------------------------------------------- */

        if (
            event.key === "ArrowLeft"
        ) {

            /* No interferir si usuario está sobre input */
            const tag =
                document.activeElement
                    ?.tagName
                    ?.toLowerCase();


            if (
                tag !== "input" &&
                tag !== "textarea" &&
                tag !== "select"
            ) {

                event.preventDefault();

                moverHistorialModal(
                    -1
                );

            }

            return;

        }


        /* ----------------------------------------------------
           FLECHA DERECHA
        ---------------------------------------------------- */

        if (
            event.key === "ArrowRight"
        ) {

            const tag =
                document.activeElement
                    ?.tagName
                    ?.toLowerCase();


            if (
                tag !== "input" &&
                tag !== "textarea" &&
                tag !== "select"
            ) {

                event.preventDefault();

                moverHistorialModal(
                    1
                );

            }

        }

    }
);


/* ============================================================
   CLIC EN EL FONDO DEL MODAL
============================================================ */

document.addEventListener(
    "click",
    function (
        event
    ) {

        const modal =
            obtenerModalHistorialOrden();


        if (!modal) {
            return;
        }


        if (
            event.target === modal
        ) {

            cerrarModalHistorialOrden();

        }

    }
);


/* ============================================================
   PREVENIR QUE CLIC DENTRO DEL DIALOG CIERRE MODAL
============================================================ */

document.addEventListener(
    "click",
    function (
        event
    ) {

        const dialog =
            event.target.closest(
                ".historial-orden-dialog"
            );


        if (!dialog) {
            return;
        }


        event.stopPropagation();

    }
);


/* ============================================================
   INICIALIZACIÓN
============================================================ */

document.addEventListener(
    "DOMContentLoaded",
    function () {

        const modal =
            obtenerModalHistorialOrden();


        if (!modal) {
            return;
        }


        /* El modal inicia cerrado */

        modal.style.display =
            "none";


        modal.setAttribute(
            "aria-hidden",
            "true"
        );

    }
);