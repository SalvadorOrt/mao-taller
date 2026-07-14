console.log("RECEPCION JS CARGADO");


// ======================================================
// UTILIDADES
// ======================================================

function escaparTextoRecepcion(texto) {
    const elemento = document.createElement("div");
    elemento.textContent = texto;
    return elemento.innerHTML;
}


// ======================================================
// MODAL DE EDICIÓN RÁPIDA
// ======================================================

window.abrirModalRecepcion = function () {
    renderModalListas();

    const modal = document.getElementById("modalEditarRecepcion");

    if (modal) {
        modal.style.display = "flex";
    }
};


window.cerrarModalRecepcion = function () {
    const modal = document.getElementById("modalEditarRecepcion");

    if (modal) {
        modal.style.display = "none";
    }
};


window.renderModalListas = function () {
    const listS = document.getElementById("modal_lista_sintomas");
    const listT = document.getElementById("modal_lista_trabajos");

    if (!listS || !listT) {
        return;
    }

    /*
     * modalSintomas y modalTrabajos deben existir en el HTML
     * o en otro archivo JS que se cargue antes de recepcion.js.
     */
    if (
        typeof modalSintomas === "undefined" ||
        typeof modalTrabajos === "undefined"
    ) {
        console.error(
            "No se encontraron las variables modalSintomas o modalTrabajos."
        );
        return;
    }

    if (modalSintomas.length === 0) {
        listS.innerHTML = `
            <div
                style="
                    color: var(--muted);
                    font-size: 0.8rem;
                    font-style: italic;
                "
            >
                No hay síntomas registrados.
            </div>
        `;
    } else {
        listS.innerHTML = modalSintomas.map(function (sintoma, indice) {
            return `
                <div class="modal-item-row">
                    <span
                        style="
                            font-weight: 500;
                            color: var(--text);
                        "
                    >
                        • ${escaparTextoRecepcion(sintoma)}
                    </span>

                    <span
                        onclick="modalEliminarSintoma(${indice})"
                        style="
                            color: var(--danger);
                            cursor: pointer;
                            font-weight: bold;
                            font-size: 1.1rem;
                            padding: 0 5px;
                        "
                        title="Eliminar"
                    >
                        &times;
                    </span>
                </div>
            `;
        }).join("");
    }

    if (modalTrabajos.length === 0) {
        listT.innerHTML = `
            <div
                style="
                    color: var(--muted);
                    font-size: 0.8rem;
                    font-style: italic;
                "
            >
                No hay trabajos registrados.
            </div>
        `;
    } else {
        listT.innerHTML = modalTrabajos.map(function (trabajo, indice) {
            return `
                <div class="modal-item-row">
                    <span
                        style="
                            font-weight: 500;
                            color: var(--text);
                        "
                    >
                        • ${escaparTextoRecepcion(trabajo)}
                    </span>

                    <span
                        onclick="modalEliminarTrabajo(${indice})"
                        style="
                            color: var(--danger);
                            cursor: pointer;
                            font-weight: bold;
                            font-size: 1.1rem;
                            padding: 0 5px;
                        "
                        title="Eliminar"
                    >
                        &times;
                    </span>
                </div>
            `;
        }).join("");
    }
};


window.modalAgregarSintoma = function () {
    const input = document.getElementById("add_sintoma_txt");

    if (!input) {
        return;
    }

    if (typeof modalSintomas === "undefined") {
        console.error("No se encontró la variable modalSintomas.");
        return;
    }

    const descripcion = input.value.trim();

    if (!descripcion) {
        input.focus();
        return;
    }

    modalSintomas.push(descripcion);

    input.value = "";
    input.focus();

    renderModalListas();
};


window.modalAgregarTrabajo = function () {
    const input = document.getElementById("add_trabajo_txt");

    if (!input) {
        return;
    }

    if (typeof modalTrabajos === "undefined") {
        console.error("No se encontró la variable modalTrabajos.");
        return;
    }

    const descripcion = input.value.trim();

    if (!descripcion) {
        input.focus();
        return;
    }

    modalTrabajos.push(descripcion);

    input.value = "";
    input.focus();

    renderModalListas();
};


window.modalEliminarSintoma = function (indice) {
    if (typeof modalSintomas === "undefined") {
        return;
    }

    if (indice < 0 || indice >= modalSintomas.length) {
        return;
    }

    modalSintomas.splice(indice, 1);

    renderModalListas();
};


window.modalEliminarTrabajo = function (indice) {
    if (typeof modalTrabajos === "undefined") {
        return;
    }

    if (indice < 0 || indice >= modalTrabajos.length) {
        return;
    }

    modalTrabajos.splice(indice, 1);

    renderModalListas();
};


window.guardarEdicionRapida = function () {
    const btn = document.getElementById("btnGuardarEdicionRapida");

    if (btn) {
        btn.disabled = true;

        btn.innerHTML = `
            <i
                class="spinner-border spinner-border-sm"
                style="margin-right: 5px;"
            ></i>
            Actualizando...
        `;
    }

    const sintomasInput = document.getElementById(
        "modal_sintomas_json"
    );

    const trabajosInput = document.getElementById(
        "modal_trabajos_json"
    );

    const form = document.getElementById(
        "formEdicionRapida"
    );

    if (
        sintomasInput &&
        typeof modalSintomas !== "undefined"
    ) {
        sintomasInput.value = JSON.stringify(
            modalSintomas.map(function (sintoma) {
                return {
                    descripcion: sintoma
                };
            })
        );
    }

    if (
        trabajosInput &&
        typeof modalTrabajos !== "undefined"
    ) {
        trabajosInput.value = JSON.stringify(
            modalTrabajos.map(function (trabajo) {
                return {
                    descripcion: trabajo
                };
            })
        );
    }

    if (form) {
        form.submit();
    } else {
        console.error(
            "No se encontró el formulario #formEdicionRapida."
        );

        if (btn) {
            btn.disabled = false;
            btn.innerHTML = "Guardar cambios";
        }
    }
};


// ======================================================
// TRABAJOS ESPECIALES DE LA CREACIÓN DE LA ORDEN
// ======================================================

const trabajosManualesRecepcion = [];


/*
 * Agrega una oración a la lista de trabajos especiales.
 * No crea un checkbox.
 */
window.agregarTrabajoManual = function () {
    const input = document.getElementById(
        "nuevo_trabajo_manual"
    );

    if (!input) {
        console.error(
            "No se encontró #nuevo_trabajo_manual."
        );
        return;
    }

    const descripcion = input.value.trim();

    if (!descripcion) {
        input.focus();
        return;
    }

    const yaExiste = trabajosManualesRecepcion.some(
        function (trabajo) {
            return (
                trabajo.toLowerCase() ===
                descripcion.toLowerCase()
            );
        }
    );

    if (yaExiste) {
        alert("Ese trabajo ya fue agregado.");
        input.select();
        return;
    }

    trabajosManualesRecepcion.push(descripcion);

    input.value = "";
    input.focus();

    renderTrabajosManualesRecepcion();
    actualizarTrabajosRecepcionJson();
};


/*
 * Muestra los trabajos especiales dentro de:
 *
 * <div id="tabla_trabajos_body"></div>
 */
window.renderTrabajosManualesRecepcion = function () {
    const contenedor = document.getElementById(
        "tabla_trabajos_body"
    );

    /*
     * No se lanza error si esta página no contiene la tabla.
     * Esto permite reutilizar recepcion.js en otras vistas.
     */
    if (!contenedor) {
        return;
    }

    if (trabajosManualesRecepcion.length === 0) {
        contenedor.innerHTML = `
            <div class="tabla-mini-row tabla-2">
                <div>-</div>

                <div
                    style="
                        color: #86868b;
                        font-style: italic;
                    "
                >
                    No hay trabajos especiales agregados.
                </div>

                <div>-</div>
            </div>
        `;

        return;
    }

    contenedor.innerHTML = trabajosManualesRecepcion.map(
        function (descripcion, indice) {
            return `
                <div class="tabla-mini-row tabla-2">
                    <div>
                        ${indice + 1}
                    </div>

                    <div>
                        ${escaparTextoRecepcion(descripcion)}
                    </div>

                    <div>
                        <button
                            type="button"
                            class="btn-mao btn-mao-danger"
                            onclick="eliminarTrabajoManualRecepcion(${indice})"
                            title="Eliminar trabajo"
                        >
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </div>
            `;
        }
    ).join("");
};


window.eliminarTrabajoManualRecepcion = function (indice) {
    if (
        indice < 0 ||
        indice >= trabajosManualesRecepcion.length
    ) {
        return;
    }

    trabajosManualesRecepcion.splice(indice, 1);

    renderTrabajosManualesRecepcion();
    actualizarTrabajosRecepcionJson();
};


// ======================================================
// PREPARAR LOS TRABAJOS PARA ENVIARLOS A DJANGO
// ======================================================

window.obtenerTrabajosRecepcion = function () {
    const trabajosComunes = Array.from(
        document.querySelectorAll(
            "#grid_trabajos_realizar .trabajo-checkbox:checked"
        )
    ).map(function (checkbox) {
        return {
            descripcion: checkbox.value.trim(),
            tipo: "comun"
        };
    });

    const trabajosEspeciales = trabajosManualesRecepcion.map(
        function (descripcion) {
            return {
                descripcion: descripcion,
                tipo: "manual"
            };
        }
    );

    return trabajosComunes.concat(
        trabajosEspeciales
    );
};


/*
 * Este método busca un input hidden para guardar el JSON.
 *
 * Puedes usar cualquiera de estos IDs:
 * - trabajos_json
 * - id_trabajos_json
 * - trabajos_solicitados_json
 */
window.actualizarTrabajosRecepcionJson = function () {
    const inputJson =
        document.getElementById("trabajos_json") ||
        document.getElementById("id_trabajos_json") ||
        document.getElementById(
            "trabajos_solicitados_json"
        );

    if (!inputJson) {
        return;
    }

    inputJson.value = JSON.stringify(
        obtenerTrabajosRecepcion()
    );
};


// ======================================================
// EVENTOS
// ======================================================

document.addEventListener(
    "DOMContentLoaded",
    function () {
        const inputTrabajo = document.getElementById(
            "nuevo_trabajo_manual"
        );

        if (inputTrabajo) {
            inputTrabajo.addEventListener(
                "keydown",
                function (event) {
                    if (event.key === "Enter") {
                        event.preventDefault();
                        agregarTrabajoManual();
                    }
                }
            );
        }

        const inputSintoma = document.getElementById(
            "nuevo_sintoma"
        );

        if (inputSintoma) {
            inputSintoma.addEventListener(
                "keydown",
                function (event) {
                    if (
                        event.key === "Enter" &&
                        typeof window.agregarSintoma ===
                            "function"
                    ) {
                        event.preventDefault();
                        window.agregarSintoma();
                    }
                }
            );
        }

        const checkboxes = document.querySelectorAll(
            "#grid_trabajos_realizar .trabajo-checkbox"
        );

        checkboxes.forEach(function (checkbox) {
            checkbox.addEventListener(
                "change",
                actualizarTrabajosRecepcionJson
            );
        });

        renderTrabajosManualesRecepcion();
        actualizarTrabajosRecepcionJson();

        /*
         * Antes de enviar el formulario principal,
         * actualiza el JSON con checkboxes y trabajos manuales.
         *
         * Cambia #formCrearOrden si tu formulario tiene otro ID.
         */
        const formularioCrearOrden =
            document.getElementById("formCrearOrden") ||
            document.querySelector(
                'form[data-formulario-orden="true"]'
            );

        if (formularioCrearOrden) {
            formularioCrearOrden.addEventListener(
                "submit",
                function () {
                    actualizarTrabajosRecepcionJson();
                }
            );
        }
    }
);