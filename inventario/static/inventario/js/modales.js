// =========================================================
// MODALES RÁPIDOS - CATÁLOGO MAO
// =========================================================
//
// En "Nuevo repuesto" únicamente permitimos
// creación rápida de MARCAS.
//
// NO se permite crear desde esta pantalla:
//
// - Familias
// - Categorías
// - Atributos
// - Opciones
// - Configuraciones Categoría ↔ Atributo
//
// Todo eso pertenece a Maestros.
//
// =========================================================

(function () {
    "use strict";


    // =====================================================
    // CSRF
    // =====================================================

    function obtenerCSRFToken() {

        const input = (
            document.querySelector(
                "input[name='csrfmiddlewaretoken']"
            )
        );

        return (
            input
                ? input.value
                : ""
        );
    }


    // =====================================================
    // FORMULARIO PRINCIPAL
    // =====================================================

    function obtenerFormularioCatalogo() {

        return document.getElementById(
            "catalogoForm"
        );
    }


    // =====================================================
    // NORMALIZAR TEXTO
    // =====================================================

    function normalizarTexto(
        valor
    ) {

        return String(
            valor
            || ""
        ).trim();
    }


    // =====================================================
    // ABRIR MODAL BOOTSTRAP
    // =====================================================

    function abrirModalBootstrap(
        idModal
    ) {

        const modalElement = (
            document.getElementById(
                idModal
            )
        );


        if (!modalElement) {

            console.error(
                `MAO: no existe el modal ${idModal}.`
            );

            return;
        }


        if (
            typeof bootstrap
            === "undefined"
        ) {

            console.error(
                "MAO: Bootstrap no está disponible."
            );

            return;
        }


        const modal = (
            bootstrap.Modal.getInstance(
                modalElement
            )
            || new bootstrap.Modal(
                modalElement
            )
        );


        modal.show();
    }


    // =====================================================
    // CERRAR MODAL
    // =====================================================

    function cerrarModalPorId(
        idModal
    ) {

        const modalElement = (
            document.getElementById(
                idModal
            )
        );


        if (
            !modalElement
            || typeof bootstrap
                === "undefined"
        ) {

            return;
        }


        const modal = (
            bootstrap.Modal.getInstance(
                modalElement
            )
        );


        if (modal) {

            modal.hide();
        }
    }


    // =====================================================
    // ERROR DEL MODAL MARCA
    // =====================================================

    function mostrarErrorMarca(
        mensaje
    ) {

        const error = (
            document.getElementById(
                "marcaModalError"
            )
        );


        if (!error) {

            if (mensaje) {
                alert(mensaje);
            }

            return;
        }


        if (!mensaje) {

            error.textContent = "";

            error.style.display = (
                "none"
            );

            return;
        }


        error.textContent = (
            mensaje
        );

        error.style.display = (
            "block"
        );
    }


    // =====================================================
    // ESTADO BOTÓN GUARDAR
    // =====================================================

    function establecerGuardandoMarca(
        guardando
    ) {

        const boton = (
            document.getElementById(
                "btnGuardarMarca"
            )
        );


        if (!boton) {
            return;
        }


        boton.disabled = (
            Boolean(
                guardando
            )
        );


        if (guardando) {

            boton.dataset.textoOriginal = (
                boton.innerHTML
            );


            boton.innerHTML = `
                <span
                    class="spinner-border spinner-border-sm"
                    aria-hidden="true"
                    style="
                        width:10px;
                        height:10px;
                        margin-right:5px;
                    "
                ></span>

                Guardando...
            `;

        } else {

            if (
                boton.dataset.textoOriginal
            ) {

                boton.innerHTML = (
                    boton.dataset
                    .textoOriginal
                );
            }
        }
    }


    // =====================================================
    // CREACIÓN RÁPIDA
    // =====================================================
    //
    // IMPORTANTE:
    //
    // Django está leyendo request.POST.
    //
    // Por eso enviamos:
    //
    // application/x-www-form-urlencoded
    //
    // y NO application/json.
    //
    // =====================================================

    async function enviarCreacionRapida(
        url,
        payload
    ) {

        if (!url) {

            throw new Error(
                "No está configurada la URL "
                + "de creación rápida."
            );
        }


        const parametros = (
            new URLSearchParams()
        );


        Object.entries(
            payload || {}
        ).forEach(
            function (
                [clave, valor]
            ) {

                parametros.append(
                    clave,
                    valor ?? ""
                );
            }
        );


        const response = await fetch(
            url,
            {
                method: "POST",

                headers: {

                    "X-CSRFToken":
                        obtenerCSRFToken(),

                    "X-Requested-With":
                        "XMLHttpRequest",

                    "Content-Type":
                        "application/x-www-form-urlencoded; charset=UTF-8",

                    "Accept":
                        "application/json",
                },

                body:
                    parametros.toString(),
            }
        );


        let data;


        try {

            data = await response.json();

        } catch (error) {

            throw new Error(
                "El servidor devolvió una "
                + "respuesta no válida."
            );
        }


        if (
            !response.ok
            || data.ok === false
        ) {

            throw new Error(
                data.error
                || "No se pudo guardar."
            );
        }


        return data;
    }


    // =====================================================
    // AGREGAR MARCA A LOS DROPDOWNS
    // =====================================================

    function agregarMarcaADropdowns(
        id,
        nombre,
        seleccionar = true
    ) {

        // =================================================
        // API DEL APPLE DROPDOWN
        // =================================================

        if (
            window.AppleDropdown
            && typeof (
                window.AppleDropdown
                .agregarOpcion
            ) === "function"
        ) {

            window.AppleDropdown
                .agregarOpcion(
                    "marca",
                    id,
                    nombre,
                    seleccionar
                );


            // Respaldo:
            // aseguramos change para que otros módulos,
            // por ejemplo sugerencias.js, detecten
            // la selección.
            if (seleccionar) {

                setTimeout(
                    function () {

                        document
                            .querySelectorAll(
                                '.apple-dropdown'
                                + '[data-dropdown-tipo="marca"]'
                                + ' .apple-dropdown-hidden'
                            )
                            .forEach(
                                function (hidden) {

                                    if (
                                        String(
                                            hidden.value
                                        )
                                        === String(
                                            id
                                        )
                                    ) {

                                        hidden.dispatchEvent(
                                            new Event(
                                                "change",
                                                {
                                                    bubbles:
                                                        true,
                                                }
                                            )
                                        );
                                    }
                                }
                            );

                    },
                    0
                );
            }


            return;
        }


        // =================================================
        // FALLBACK
        // =================================================

        const dropdowns = (
            document.querySelectorAll(
                '.apple-dropdown'
                + '[data-dropdown-tipo="marca"]'
            )
        );


        dropdowns.forEach(
            function (wrap) {

                const input = (
                    wrap.querySelector(
                        ".apple-dropdown-input"
                    )
                );


                const hidden = (
                    wrap.querySelector(
                        ".apple-dropdown-hidden"
                    )
                );


                const menu = (
                    wrap.querySelector(
                        ".apple-dropdown-menu"
                    )
                );


                if (
                    !input
                    || !hidden
                    || !menu
                ) {

                    return;
                }


                let item = Array.from(
                    menu.querySelectorAll(
                        ".apple-dropdown-item"
                    )
                ).find(
                    function (elemento) {

                        return (
                            String(
                                elemento.dataset.id
                                || ""
                            )
                            === String(
                                id
                            )
                        );
                    }
                );


                // =========================================
                // CREAR OPCIÓN
                // =========================================

                if (!item) {

                    item = (
                        document.createElement(
                            "div"
                        )
                    );


                    item.className = (
                        "apple-dropdown-item"
                    );


                    item.dataset.id = (
                        String(id)
                    );


                    item.dataset.nombre = (
                        nombre
                    );


                    item.textContent = (
                        nombre
                    );


                    const noResult = (
                        menu.querySelector(
                            ".apple-dropdown-no-result"
                        )
                    );


                    if (noResult) {

                        menu.insertBefore(
                            item,
                            noResult
                        );

                    } else {

                        menu.appendChild(
                            item
                        );
                    }
                }


                // =========================================
                // SELECCIONAR
                // =========================================

                if (seleccionar) {

                    input.value = (
                        nombre
                    );


                    hidden.value = (
                        String(id)
                    );


                    menu.style.display = (
                        "none"
                    );


                    hidden.dispatchEvent(
                        new Event(
                            "change",
                            {
                                bubbles: true,
                            }
                        )
                    );
                }
            }
        );
    }


    // =====================================================
    // GUARDAR MARCA
    // =====================================================

    async function guardarMarca() {

        const form = (
            obtenerFormularioCatalogo()
        );


        if (!form) {

            console.error(
                "MAO: no se encontró catalogoForm."
            );

            return;
        }


        const nombreInput = (
            document.getElementById(
                "marcaNombre"
            )
        );


        if (!nombreInput) {

            console.error(
                "MAO: no se encontró marcaNombre."
            );

            return;
        }


        mostrarErrorMarca(
            ""
        );


        const nombre = (
            normalizarTexto(
                nombreInput.value
            )
            .toUpperCase()
        );


        // =================================================
        // VALIDACIÓN
        // =================================================

        if (!nombre) {

            mostrarErrorMarca(
                "Ingrese el nombre de la marca."
            );


            nombreInput.focus();

            return;
        }


        const url = (
            form.dataset.urlMarcaRapida
            || ""
        );


        if (!url) {

            mostrarErrorMarca(
                "No está configurada la creación "
                + "rápida de marcas."
            );

            return;
        }


        establecerGuardandoMarca(
            true
        );


        try {

            const data = (
                await enviarCreacionRapida(
                    url,
                    {
                        nombre:
                            nombre,
                    }
                )
            );


            // =============================================
            // AGREGAR Y SELECCIONAR
            // =============================================

            agregarMarcaADropdowns(
                data.id,
                data.nombre,
                true
            );


            // =============================================
            // LIMPIAR MODAL
            // =============================================

            nombreInput.value = "";


            mostrarErrorMarca(
                ""
            );


            cerrarModalPorId(
                "modalMarca"
            );


        } catch (error) {

            console.error(
                "MAO: error creando marca:",
                error
            );


            mostrarErrorMarca(
                error.message
                || (
                    "No se pudo crear "
                    + "la marca."
                )
            );


        } finally {

            establecerGuardandoMarca(
                false
            );
        }
    }


    // =====================================================
    // ENTER EN MODAL
    // =====================================================

    function prepararEnterModal(
        inputId,
        callback
    ) {

        const input = (
            document.getElementById(
                inputId
            )
        );


        if (!input) {
            return;
        }


        if (
            input.dataset.enterInicializado
            === "1"
        ) {

            return;
        }


        input.dataset.enterInicializado = (
            "1"
        );


        input.addEventListener(
            "keydown",
            function (event) {

                if (
                    event.key
                    !== "Enter"
                ) {

                    return;
                }


                event.preventDefault();


                callback();
            }
        );
    }


    // =====================================================
    // EVENTOS DEL MODAL
    // =====================================================

    function prepararModalMarca() {

        const modal = (
            document.getElementById(
                "modalMarca"
            )
        );


        if (!modal) {
            return;
        }


        // =================================================
        // AL ABRIR
        // =================================================

        modal.addEventListener(
            "shown.bs.modal",
            function () {

                mostrarErrorMarca(
                    ""
                );


                const input = (
                    document.getElementById(
                        "marcaNombre"
                    )
                );


                if (input) {

                    setTimeout(
                        function () {

                            input.focus();

                        },
                        50
                    );
                }
            }
        );


        // =================================================
        // AL CERRAR
        // =================================================

        modal.addEventListener(
            "hidden.bs.modal",
            function () {

                mostrarErrorMarca(
                    ""
                );


                establecerGuardandoMarca(
                    false
                );
            }
        );
    }


    // =====================================================
    // INICIALIZACIÓN
    // =====================================================

    function inicializarModales() {

        prepararEnterModal(
            "marcaNombre",
            guardarMarca
        );


        prepararModalMarca();
    }


    // =====================================================
    // EXPORTACIÓN GLOBAL
    // =====================================================
    //
    // Necesario porque el HTML utiliza:
    //
    // onclick="abrirModalBootstrap(...)"
    // onclick="guardarMarca()"
    //
    // =====================================================

    window.abrirModalBootstrap = (
        abrirModalBootstrap
    );


    window.cerrarModalPorId = (
        cerrarModalPorId
    );


    window.guardarMarca = (
        guardarMarca
    );


    // =====================================================
    // ARRANQUE
    // =====================================================

    if (
        document.readyState
        === "loading"
    ) {

        document.addEventListener(
            "DOMContentLoaded",
            inicializarModales
        );

    } else {

        inicializarModales();
    }

})();