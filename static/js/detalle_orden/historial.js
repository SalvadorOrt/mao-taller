/* ============================================================
   HISTORIAL DEL VEHÍCULO - MODAL COMPACTO HORIZONTAL
============================================================ */

let historialOrdenAbortController = null;
let historialOrdenCargado = false;
let historialOrdenCargando = false;
let historialOrdenIdActivo = null;
let historialOrdenUltimoFoco = null;


/* ============================================================
   ELEMENTOS
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
   ESTADOS VISUALES
============================================================ */

function mostrarCargaHistorialOrden() {

    const cargando =
        obtenerCargandoHistorialOrden();

    const contenido =
        obtenerContenidoHistorialOrden();

    const error =
        obtenerErrorHistorialOrden();


    if (cargando) {
        cargando.style.display = "flex";
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
   ABRIR
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


    historialOrdenUltimoFoco =
        document.activeElement;


    modal.style.display = "flex";

    modal.setAttribute(
        "aria-hidden",
        "false"
    );


    document.body.classList.add(
        "historial-orden-abierto"
    );


    if (historialOrdenCargado) {

        mostrarContenidoHistorialOrden();

        inicializarHistorialOrden();

        enfocarCerrarHistorialOrden();

        return;
    }


    if (historialOrdenCargando) {
        return;
    }


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
   FETCH
============================================================ */

async function cargarHistorialOrden(url) {

    historialOrdenCargando = true;

    mostrarCargaHistorialOrden();


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
   INICIALIZAR
============================================================ */

function inicializarHistorialOrden() {

    const contenido =
        obtenerContenidoHistorialOrden();

    if (!contenido) {
        return;
    }


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


    const botones =
        contenido.querySelectorAll(
            ".hm-timeline-button[data-orden-id]"
        );


    if (botones.length > 0) {

        const ultimo =
            botones[
                botones.length - 1
            ];

        seleccionarOrdenHistorialModal(
            ultimo.dataset.ordenId,
            false
        );

    }

}


/* ============================================================
   SELECCIONAR VISITA
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


    contenido
        .querySelectorAll(
            ".hm-timeline-item"
        )
        .forEach(
            (item) => {
                item.classList.remove(
                    "active"
                );
            }
        );


    contenido
        .querySelectorAll(
            ".hm-panel"
        )
        .forEach(
            (panel) => {
                panel.classList.remove(
                    "active"
                );
            }
        );


    const timelineItem =
        document.getElementById(
            `hm-timeline-item-${ordenId}`
        );


    const panel =
        document.getElementById(
            `hm-panel-${ordenId}`
        );


    if (!timelineItem || !panel) {
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


    seleccionarTabHistorialModal(
        ordenId,
        "repuestos"
    );


    timelineItem.scrollIntoView({
        behavior:
            animarScroll
                ? "smooth"
                : "auto",
        inline: "center",
        block: "nearest"
    });


    actualizarNavegacionHistorialOrden();

}


/* ============================================================
   PESTAÑAS REP / MOI / MOE / NOTAS / ABONOS
============================================================ */

function seleccionarTabHistorialModal(
    ordenId,
    tabNombre
) {

    const panelOrden =
        document.getElementById(
            `hm-panel-${ordenId}`
        );


    if (!panelOrden) {
        return;
    }


    panelOrden
        .querySelectorAll(
            ".hm-tab-btn"
        )
        .forEach(
            (boton) => {

                boton.classList.toggle(
                    "active",
                    boton.dataset.hmTabBtn ===
                        tabNombre
                );

            }
        );


    panelOrden
        .querySelectorAll(
            ".hm-tab-panel"
        )
        .forEach(
            (panel) => {

                panel.classList.toggle(
                    "active",
                    panel.dataset.hmTabPanel ===
                        tabNombre
                );


                if (
                    panel.dataset.hmTabPanel ===
                    tabNombre
                ) {

                    panel.scrollTop = 0;
                    panel.scrollLeft = 0;

                }

            }
        );

}


/* ============================================================
   IDS DEL CARRUSEL
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
   ANTERIOR / SIGUIENTE
============================================================ */

function moverHistorialModal(
    direccion
) {

    const ids =
        obtenerIdsHistorialOrden();


    if (ids.length === 0) {
        return;
    }


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
   HABILITAR / DESHABILITAR FLECHAS
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


    const botonAnterior =
        panelActivo.querySelector(
            ".hm-btn-anterior"
        );


    const botonSiguiente =
        panelActivo.querySelector(
            ".hm-btn-siguiente"
        );


    if (botonAnterior) {
        botonAnterior.disabled =
            indiceActual <= 0;
    }


    if (botonSiguiente) {
        botonSiguiente.disabled =
            indiceActual >=
            ids.length - 1;
    }

}


/* ============================================================
   CERRAR
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


    if (
        historialOrdenAbortController &&
        historialOrdenCargando
    ) {

        historialOrdenAbortController.abort();

        historialOrdenCargando = false;

    }


    if (
        historialOrdenUltimoFoco &&
        typeof historialOrdenUltimoFoco.focus ===
            "function"
    ) {

        historialOrdenUltimoFoco.focus();

    }

}


/* ============================================================
   RECARGAR
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
   FOCO
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

        window.setTimeout(
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
    function (event) {

        const modal =
            obtenerModalHistorialOrden();


        if (
            !modal ||
            modal.style.display !== "flex"
        ) {
            return;
        }


        if (event.key === "Escape") {

            event.preventDefault();

            cerrarModalHistorialOrden();

            return;
        }


        const tag =
            document.activeElement
                ?.tagName
                ?.toLowerCase();


        if (
            tag === "input" ||
            tag === "textarea" ||
            tag === "select"
        ) {
            return;
        }


        if (event.key === "ArrowLeft") {

            event.preventDefault();

            moverHistorialModal(-1);

            return;
        }


        if (event.key === "ArrowRight") {

            event.preventDefault();

            moverHistorialModal(1);

        }

    }
);


/* ============================================================
   CLIC FUERA
============================================================ */

document.addEventListener(
    "click",
    function (event) {

        const modal =
            obtenerModalHistorialOrden();


        if (
            modal &&
            event.target === modal
        ) {

            cerrarModalHistorialOrden();

        }

    }
);


/* ============================================================
   ARRANQUE
============================================================ */

document.addEventListener(
    "DOMContentLoaded",
    function () {

        const modal =
            obtenerModalHistorialOrden();


        if (!modal) {
            return;
        }


        modal.style.display =
            "none";


        modal.setAttribute(
            "aria-hidden",
            "true"
        );

    }
);


/* ============================================================
   EXPONER FUNCIONES
============================================================ */

window.abrirModalHistorialOrden =
    abrirModalHistorialOrden;

window.cerrarModalHistorialOrden =
    cerrarModalHistorialOrden;

window.seleccionarOrdenHistorialModal =
    seleccionarOrdenHistorialModal;

window.seleccionarTabHistorialModal =
    seleccionarTabHistorialModal;

window.moverHistorialModal =
    moverHistorialModal;

window.recargarHistorialOrden =
    recargarHistorialOrden;