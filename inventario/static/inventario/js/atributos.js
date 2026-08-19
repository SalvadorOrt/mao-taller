// =========================================================
// MAO - CLASIFICACIÓN Y ATRIBUTOS TÉCNICOS
// =========================================================

(function () {
    "use strict";

    let form = null;

    let urlAtributosCategoria = "";

    let controladorAtributos = null;

    let ultimaCategoriaCargada = null;

    let sincronizandoClasificacion = false;


    // =====================================================
    // INICIALIZACIÓN
    // =====================================================

    function inicializarAtributos() {

        form = document.getElementById(
            "catalogoForm"
        );

        if (!form) {
            return;
        }

        if (
            form.dataset.atributosInicializados
            === "1"
        ) {
            return;
        }

        form.dataset.atributosInicializados = "1";


        urlAtributosCategoria = (
            form.dataset.urlAtributosCategoria
            || ""
        );


        if (
            typeof window.inicializarDropdownsApple
            === "function"
        ) {
            window.inicializarDropdownsApple();
        }


        conectarEventosClasificacion();

        sincronizarTextosIniciales();


        const categoria = (
            obtenerDropdown(
                "categoria"
            )
        );

        const familia = (
            obtenerDropdown(
                "familia"
            )
        );


        // =================================================
        // CATEGORÍA YA SELECCIONADA
        // =================================================

        if (
            categoria?.hidden?.value
        ) {
            sincronizarFamiliaDesdeCategoria(
                categoria.hidden.value
            );

            cargarAtributosCategoria(
                categoria.hidden.value
            );

            return;
        }


        // =================================================
        // FAMILIA YA SELECCIONADA
        // =================================================

        if (
            familia?.hidden?.value
        ) {
            filtrarCategoriasPorFamilia(
                familia.hidden.value
            );
        }


        limpiarAtributos();
    }


    // =====================================================
    // OBTENER DROPDOWN
    // =====================================================

    function obtenerDropdown(
        tipo
    ) {

        if (!form) {
            return null;
        }

        const wrap = (
            form.querySelector(
                `.apple-dropdown[data-dropdown-tipo="${tipo}"]`
            )
        );

        if (!wrap) {
            return null;
        }

        return {
            wrap,

            input: (
                wrap.querySelector(
                    ".apple-dropdown-input"
                )
            ),

            hidden: (
                wrap.querySelector(
                    ".apple-dropdown-hidden"
                )
            ),

            menu: (
                wrap.querySelector(
                    ".apple-dropdown-menu"
                )
            ),
        };
    }


    // =====================================================
    // EVENTOS
    // =====================================================

    function conectarEventosClasificacion() {

        form.addEventListener(
            "change",
            function (event) {

                const target = event.target;


                // =========================================
                // FAMILIA
                // =========================================

                if (
                    target.classList.contains(
                        "apple-dropdown-hidden"
                    )
                    && target.closest(
                        '.apple-dropdown[data-dropdown-tipo="familia"]'
                    )
                ) {

                    if (
                        sincronizandoClasificacion
                    ) {
                        return;
                    }

                    manejarCambioFamilia(
                        target.value
                    );

                    return;
                }


                // =========================================
                // CATEGORÍA
                // =========================================

                if (
                    target.classList.contains(
                        "apple-dropdown-hidden"
                    )
                    && target.closest(
                        '.apple-dropdown[data-dropdown-tipo="categoria"]'
                    )
                ) {

                    if (
                        sincronizandoClasificacion
                    ) {
                        return;
                    }

                    manejarCambioCategoria(
                        target.value
                    );
                }
            }
        );


        // =================================================
        // RESPALDO PARA APPLE DROPDOWN
        // =================================================

        form.addEventListener(
            "click",
            function (event) {

                const itemFamilia = (
                    event.target.closest(
                        '.apple-dropdown[data-dropdown-tipo="familia"] .apple-dropdown-item'
                    )
                );

                if (itemFamilia) {

                    setTimeout(
                        function () {

                            const dropdown = (
                                obtenerDropdown(
                                    "familia"
                                )
                            );

                            manejarCambioFamilia(
                                dropdown?.hidden?.value
                                || itemFamilia.dataset.id
                            );

                        },
                        0
                    );

                    return;
                }


                const itemCategoria = (
                    event.target.closest(
                        '.apple-dropdown[data-dropdown-tipo="categoria"] .apple-dropdown-item'
                    )
                );

                if (itemCategoria) {

                    setTimeout(
                        function () {

                            const dropdown = (
                                obtenerDropdown(
                                    "categoria"
                                )
                            );

                            manejarCambioCategoria(
                                dropdown?.hidden?.value
                                || itemCategoria.dataset.id
                            );

                        },
                        0
                    );
                }
            }
        );
    }


    // =====================================================
    // CAMBIO DE FAMILIA
    // =====================================================

    function manejarCambioFamilia(
        familiaId
    ) {

        familiaId = String(
            familiaId
            || ""
        );


        filtrarCategoriasPorFamilia(
            familiaId
        );


        const categoria = (
            obtenerDropdown(
                "categoria"
            )
        );

        if (!categoria) {
            return;
        }


        const categoriaId = String(
            categoria.hidden?.value
            || ""
        );


        if (!categoriaId) {

            limpiarAtributos();

            return;
        }


        const itemCategoria = (
            buscarItemPorId(
                categoria.wrap,
                categoriaId
            )
        );


        const familiaCategoria = String(
            itemCategoria?.dataset
                ?.familiaId
            || ""
        );


        // =================================================
        // LA CATEGORÍA YA NO PERTENECE A LA FAMILIA
        // =================================================

        if (
            familiaId
            && familiaCategoria
            !== familiaId
        ) {

            limpiarDropdown(
                categoria.wrap
            );

            limpiarAtributos();

            ultimaCategoriaCargada = null;

            return;
        }


        cargarAtributosCategoria(
            categoriaId
        );
    }


    // =====================================================
    // CAMBIO DE CATEGORÍA
    // =====================================================

    function manejarCambioCategoria(
        categoriaId
    ) {

        categoriaId = String(
            categoriaId
            || ""
        );


        if (!categoriaId) {

            ultimaCategoriaCargada = null;

            limpiarAtributos();

            return;
        }


        sincronizarFamiliaDesdeCategoria(
            categoriaId
        );


        cargarAtributosCategoria(
            categoriaId
        );
    }


    // =====================================================
    // CATEGORÍA -> FAMILIA
    // =====================================================

    function sincronizarFamiliaDesdeCategoria(
        categoriaId
    ) {

        const categoria = (
            obtenerDropdown(
                "categoria"
            )
        );

        const familia = (
            obtenerDropdown(
                "familia"
            )
        );


        if (
            !categoria
            || !familia
        ) {
            return;
        }


        const itemCategoria = (
            buscarItemPorId(
                categoria.wrap,
                categoriaId
            )
        );


        if (!itemCategoria) {
            return;
        }


        const familiaId = String(
            itemCategoria.dataset
                .familiaId
            || ""
        );


        const familiaNombre = (
            itemCategoria.dataset
                .familiaNombre
            || ""
        );


        if (!familiaId) {
            return;
        }


        sincronizandoClasificacion = true;

        try {

            seleccionarDropdown(
                familia.wrap,
                familiaId,
                familiaNombre,
                false
            );


            filtrarCategoriasPorFamilia(
                familiaId
            );

        } finally {

            sincronizandoClasificacion = false;
        }
    }


    // =====================================================
    // FILTRAR CATEGORÍAS
    // =====================================================

    function filtrarCategoriasPorFamilia(
        familiaId
    ) {

        const categoria = (
            obtenerDropdown(
                "categoria"
            )
        );

        if (!categoria) {
            return;
        }


        familiaId = String(
            familiaId
            || ""
        );


        const items = (
            categoria.wrap
            .querySelectorAll(
                ".apple-dropdown-item"
            )
        );


        items.forEach(
            function (item) {

                const familiaItem = String(
                    item.dataset
                        .familiaId
                    || ""
                );


                const mostrar = (
                    !familiaId
                    || familiaItem
                    === familiaId
                );


                item.hidden = !mostrar;

                item.dataset.filtroFamilia = (
                    mostrar
                    ? "1"
                    : "0"
                );
            }
        );


        // Limpiamos búsqueda visual para que el usuario
        // vea inmediatamente las categorías disponibles.

        if (categoria.input) {
            categoria.input.value = (
                categoria.hidden.value
                    ? categoria.input.value
                    : ""
            );
        }
    }


    // =====================================================
    // SINCRONIZAR TEXTOS INICIALES
    // =====================================================

    function sincronizarTextosIniciales() {

        [
            "familia",
            "categoria",
        ].forEach(
            function (tipo) {

                const dropdown = (
                    obtenerDropdown(
                        tipo
                    )
                );

                if (
                    !dropdown
                    || !dropdown.hidden?.value
                ) {
                    return;
                }


                const item = (
                    buscarItemPorId(
                        dropdown.wrap,
                        dropdown.hidden.value
                    )
                );


                if (
                    item
                    && dropdown.input
                ) {
                    dropdown.input.value = (
                        item.dataset.nombre
                        || item.textContent.trim()
                    );
                }
            }
        );
    }


    // =====================================================
    // SELECCIONAR DROPDOWN
    // =====================================================

    function seleccionarDropdown(
        wrap,
        id,
        nombre = "",
        dispararCambio = true
    ) {

        if (
            !wrap
            || id === null
            || id === undefined
        ) {
            return false;
        }


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


        if (
            !input
            || !hidden
        ) {
            return false;
        }


        const idTexto = String(
            id
        );


        const item = (
            buscarItemPorId(
                wrap,
                idTexto
            )
        );


        const nombreFinal = (
            item?.dataset?.nombre
            || item?.textContent?.trim()
            || nombre
            || ""
        );


        hidden.value = (
            idTexto
        );

        input.value = (
            nombreFinal
        );


        if (
            dispararCambio
        ) {
            hidden.dispatchEvent(
                new Event(
                    "change",
                    {
                        bubbles: true,
                    }
                )
            );
        }


        return true;
    }


    // =====================================================
    // LIMPIAR DROPDOWN
    // =====================================================

    function limpiarDropdown(
        wrap
    ) {

        if (!wrap) {
            return;
        }


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


        if (input) {
            input.value = "";
        }

        if (hidden) {
            hidden.value = "";
        }
    }


    // =====================================================
    // ITEM POR ID
    // =====================================================

    function buscarItemPorId(
        wrap,
        id
    ) {

        if (!wrap) {
            return null;
        }


        const idTexto = String(
            id
        );


        return Array.from(
            wrap.querySelectorAll(
                ".apple-dropdown-item"
            )
        ).find(
            function (item) {

                return (
                    String(
                        item.dataset.id
                        || ""
                    )
                    === idTexto
                );
            }
        ) || null;
    }


    // =====================================================
    // API ATRIBUTOS
    // =====================================================

    async function cargarAtributosCategoria(
        categoriaId
    ) {

        categoriaId = String(
            categoriaId
            || ""
        );


        if (
            !categoriaId
            || !urlAtributosCategoria
        ) {
            limpiarAtributos();

            return;
        }


        if (
            ultimaCategoriaCargada
            === categoriaId
        ) {
            return;
        }


        if (
            controladorAtributos
        ) {
            controladorAtributos.abort();
        }


        controladorAtributos = (
            new AbortController()
        );


        try {

            const url = (
                construirUrlAtributos(
                    categoriaId
                )
            );


            const respuesta = await fetch(
                url,
                {
                    method: "GET",

                    headers: {
                        "X-Requested-With":
                            "XMLHttpRequest",

                        "Accept":
                            "application/json",
                    },

                    signal:
                        controladorAtributos.signal,
                }
            );


            const resultado = (
                await respuesta.json()
            );


            if (!respuesta.ok) {

                throw new Error(
                    resultado.error
                    || (
                        "No se pudieron cargar "
                        + "las características."
                    )
                );
            }


            // =============================================
            // RESPALDO:
            // LA API TAMBIÉN NOS DICE LA FAMILIA
            // =============================================

            if (
                resultado.categoria
                ?.familia_id
            ) {

                sincronizarFamiliaDesdeAPI(
                    resultado.categoria
                );
            }


            const atributos = (
                Array.isArray(
                    resultado.atributos
                )
                    ? resultado.atributos
                    : []
            );


            renderizarAtributos(
                categoriaId,
                atributos
            );


            ultimaCategoriaCargada = (
                categoriaId
            );


        } catch (error) {

            if (
                error.name
                === "AbortError"
            ) {
                return;
            }


            console.error(
                "MAO: error cargando atributos:",
                error
            );


            mostrarEstadoVacio(
                "No se pudieron cargar "
                + "las características técnicas."
            );


        } finally {

            controladorAtributos = null;
        }
    }


    // =====================================================
    // FAMILIA DESDE API
    // =====================================================

    function sincronizarFamiliaDesdeAPI(
        categoria
    ) {

        const familia = (
            obtenerDropdown(
                "familia"
            )
        );


        if (
            !familia
            || !categoria?.familia_id
        ) {
            return;
        }


        sincronizandoClasificacion = true;

        try {

            seleccionarDropdown(
                familia.wrap,
                categoria.familia_id,
                categoria.familia || "",
                false
            );


            filtrarCategoriasPorFamilia(
                categoria.familia_id
            );

        } finally {

            sincronizandoClasificacion = false;
        }
    }


    // =====================================================
    // URL
    // =====================================================

    function construirUrlAtributos(
        categoriaId
    ) {

        const id = (
            encodeURIComponent(
                String(
                    categoriaId
                )
            )
        );


        if (
            urlAtributosCategoria
            .includes(
                "/0/"
            )
        ) {

            return (
                urlAtributosCategoria
                .replace(
                    "/0/",
                    `/${id}/`
                )
            );
        }


        return (
            urlAtributosCategoria
            .replace(
                /\/0$/,
                `/${id}`
            )
        );
    }


    // =====================================================
    // RENDER DE ATRIBUTOS
    // =====================================================

    function renderizarAtributos(
        categoriaId,
        atributos
    ) {

        const utilizadas = (
            new Set()
        );


        if (
            !Array.isArray(
                atributos
            )
            || atributos.length === 0
        ) {

            desactivarFilasNoUtilizadas(
                utilizadas
            );

            mostrarEstadoVacio(
                "Esta categoría no tiene "
                + "características técnicas configuradas."
            );

            return;
        }


        for (
            const atributo
            of atributos
        ) {

            if (
                !atributo
                || !atributo.id
            ) {
                continue;
            }


            let fila = (
                buscarFilaAtributo(
                    atributo.id,
                    utilizadas
                )
            );


            if (!fila) {

                fila = (
                    buscarFilaVacia(
                        utilizadas
                    )
                );
            }


            if (!fila) {

                fila = (
                    crearFilaAtributo()
                );
            }


            if (!fila) {
                continue;
            }


            utilizadas.add(
                fila
            );


            configurarFila(
                fila,
                atributo,
                categoriaId
            );
        }


        desactivarFilasNoUtilizadas(
            utilizadas
        );


        mostrarTabla();
    }


    // =====================================================
    // BUSCAR FILA POR ATRIBUTO
    // =====================================================

    function buscarFilaAtributo(
        atributoId,
        utilizadas
    ) {

        return Array.from(
            document.querySelectorAll(
                "#atributosContainer .atributo-form"
            )
        ).find(
            function (fila) {

                if (
                    utilizadas.has(
                        fila
                    )
                ) {
                    return false;
                }


                const hidden = (
                    fila.querySelector(
                        'input[type="hidden"][name$="-atributo"]'
                    )
                );


                return (
                    hidden
                    && String(
                        hidden.value
                    )
                    === String(
                        atributoId
                    )
                );
            }
        ) || null;
    }


    // =====================================================
    // BUSCAR FILA VACÍA
    // =====================================================

    function buscarFilaVacia(
        utilizadas
    ) {

        return Array.from(
            document.querySelectorAll(
                "#atributosContainer .atributo-form"
            )
        ).find(
            function (fila) {

                if (
                    utilizadas.has(
                        fila
                    )
                ) {
                    return false;
                }


                const atributo = (
                    fila.querySelector(
                        'input[type="hidden"][name$="-atributo"]'
                    )
                );


                return (
                    !String(
                        atributo?.value
                        || ""
                    ).trim()
                );
            }
        ) || null;
    }


    // =====================================================
    // CREAR FILA
    // =====================================================

    function crearFilaAtributo() {

        const totalForms = (
            document.getElementById(
                "id_atributos-TOTAL_FORMS"
            )
        );

        const container = (
            document.getElementById(
                "atributosContainer"
            )
        );

        const template = (
            document.getElementById(
                "atributoEmptyFormTemplate"
            )
        );


        if (
            !totalForms
            || !container
            || !template
        ) {

            console.error(
                "MAO: no se pudo crear "
                + "una fila de atributos."
            );

            return null;
        }


        const indice = (
            parseInt(
                totalForms.value
                || "0",
                10
            )
        );


        const html = (
            template.innerHTML
            .replace(
                /__prefix__/g,
                indice
            )
        );


        container.insertAdjacentHTML(
            "beforeend",
            html
        );


        totalForms.value = (
            indice + 1
        );


        const filas = (
            container.querySelectorAll(
                ".atributo-form"
            )
        );


        return (
            filas.length
                ? filas[
                    filas.length - 1
                ]
                : null
        );
    }


    // =====================================================
    // CONFIGURAR FILA
    // =====================================================

    function configurarFila(
        fila,
        atributo,
        categoriaId
    ) {

        const atributoHidden = (
            fila.querySelector(
                'input[type="hidden"][name$="-atributo"]'
            )
        );

        const nombre = (
            fila.querySelector(
                ".atributo-nombre"
            )
        );

        const meta = (
            fila.querySelector(
                ".atributo-meta"
            )
        );

        const deleteInput = (
            fila.querySelector(
                'input[type="checkbox"][name$="-DELETE"]'
            )
        );


        if (!atributoHidden) {
            return;
        }


        if (deleteInput) {
            deleteInput.checked = false;
        }


        atributoHidden.value = (
            String(
                atributo.id
            )
        );


        if (nombre) {

            nombre.textContent = (
                atributo.nombre
                || "Característica"
            );
        }


        if (meta) {

            const partes = [];


            if (
                atributo.tipo_dato
            ) {
                partes.push(
                    nombreTipoDato(
                        atributo.tipo_dato
                    )
                );
            }


            if (
                atributo.requerido
            ) {
                partes.push(
                    "Obligatorio"
                );
            }


            meta.textContent = (
                partes.join(
                    " · "
                )
            );
        }


        fila.dataset.atributoId = (
            String(
                atributo.id
            )
        );

        fila.dataset.categoriaId = (
            String(
                categoriaId
            )
        );

        fila.dataset.tipoDato = (
            atributo.tipo_dato
            || "TEXTO"
        );

        fila.dataset.requerido = (
            atributo.requerido
                ? "1"
                : "0"
        );


        configurarControlValor(
            fila,
            atributo
        );


        fila.style.display = "";
    }


    // =====================================================
    // CONTROL SEGÚN TIPO
    // =====================================================

    function configurarControlValor(
        fila,
        atributo
    ) {

        const controlActual = (
            fila.querySelector(
                '[name$="-valor"]'
            )
        );

        const unidad = (
            fila.querySelector(
                ".atributo-unidad"
            )
        );


        if (!controlActual) {
            return;
        }


        const nombreCampo = (
            controlActual.name
        );

        const idCampo = (
            controlActual.id
        );

        let valorActual = (
            controlActual.value
            || ""
        );


        const tipo = (
            atributo.tipo_dato
            || "TEXTO"
        );


        let nuevoControl;


        // =================================================
        // OPCIÓN
        // =================================================

        if (
            tipo === "OPCION"
        ) {

            nuevoControl = (
                document.createElement(
                    "select"
                )
            );


            agregarOpcionSelect(
                nuevoControl,
                "",
                "Seleccione..."
            );


            const opciones = (
                Array.isArray(
                    atributo.opciones
                )
                    ? atributo.opciones
                    : []
            );


            opciones.forEach(
                function (opcion) {

                    agregarOpcionSelect(
                        nuevoControl,
                        opcion,
                        opcion
                    );
                }
            );


            if (
                opciones.includes(
                    valorActual
                )
            ) {
                nuevoControl.value = (
                    valorActual
                );
            }
        }


        // =================================================
        // BOOLEANO
        // =================================================

        else if (
            tipo === "BOOLEANO"
        ) {

            nuevoControl = (
                document.createElement(
                    "select"
                )
            );


            agregarOpcionSelect(
                nuevoControl,
                "",
                "Seleccione..."
            );

            agregarOpcionSelect(
                nuevoControl,
                "Sí",
                "Sí"
            );

            agregarOpcionSelect(
                nuevoControl,
                "No",
                "No"
            );


            if (
                [
                    "Sí",
                    "No",
                ].includes(
                    valorActual
                )
            ) {
                nuevoControl.value = (
                    valorActual
                );
            }
        }


        // =================================================
        // ENTERO
        // =================================================

        else if (
            tipo === "ENTERO"
        ) {

            nuevoControl = (
                document.createElement(
                    "input"
                )
            );

            nuevoControl.type = (
                "number"
            );

            nuevoControl.step = (
                "1"
            );

            nuevoControl.value = (
                valorActual
            );
        }


        // =================================================
        // DECIMAL
        // =================================================

        else if (
            tipo === "DECIMAL"
        ) {

            nuevoControl = (
                document.createElement(
                    "input"
                )
            );

            nuevoControl.type = (
                "number"
            );

            nuevoControl.step = (
                "any"
            );

            nuevoControl.value = (
                String(
                    valorActual
                ).replace(
                    ",",
                    "."
                )
            );
        }


        // =================================================
        // TEXTO
        // =================================================

        else {

            nuevoControl = (
                document.createElement(
                    "input"
                )
            );

            nuevoControl.type = (
                "text"
            );

            nuevoControl.value = (
                valorActual
            );
        }


        nuevoControl.name = (
            nombreCampo
        );

        if (idCampo) {
            nuevoControl.id = (
                idCampo
            );
        }


        nuevoControl.className = (
            "form-control-apple "
            + "atributo-valor-input"
        );


        nuevoControl.dataset.tipoDato = (
            tipo
        );


        if (
            atributo.requerido
        ) {
            nuevoControl.required = true;
        }


        controlActual.replaceWith(
            nuevoControl
        );


        // =================================================
        // UNIDAD
        // =================================================

        if (unidad) {

            const textoUnidad = (
                atributo.unidad
                || ""
            );


            unidad.textContent = (
                textoUnidad
            );


            unidad.style.display = (
                textoUnidad
                    ? "inline"
                    : "none"
            );
        }
    }


    // =====================================================
    // OPTION
    // =====================================================

    function agregarOpcionSelect(
        select,
        valor,
        texto
    ) {

        const opcion = (
            document.createElement(
                "option"
            )
        );

        opcion.value = (
            valor
        );

        opcion.textContent = (
            texto
        );

        select.appendChild(
            opcion
        );
    }


    // =====================================================
    // TIPO LEGIBLE
    // =====================================================

    function nombreTipoDato(
        tipo
    ) {

        const nombres = {
            TEXTO: "Texto",
            ENTERO: "Número entero",
            DECIMAL: "Número decimal",
            BOOLEANO: "Sí / No",
            OPCION: "Lista",
        };


        return (
            nombres[
                tipo
            ]
            || "Texto"
        );
    }


    // =====================================================
    // DESACTIVAR FILAS NO UTILIZADAS
    // =====================================================

    function desactivarFilasNoUtilizadas(
        utilizadas
    ) {

        document.querySelectorAll(
            "#atributosContainer .atributo-form"
        ).forEach(
            function (fila) {

                if (
                    utilizadas.has(
                        fila
                    )
                ) {
                    return;
                }


                const deleteInput = (
                    fila.querySelector(
                        'input[type="checkbox"][name$="-DELETE"]'
                    )
                );


                if (deleteInput) {
                    deleteInput.checked = true;
                }


                fila.style.display = (
                    "none"
                );
            }
        );
    }


    // =====================================================
    // LIMPIAR ATRIBUTOS
    // =====================================================

    function limpiarAtributos() {

        document.querySelectorAll(
            "#atributosContainer .atributo-form"
        ).forEach(
            function (fila) {

                const deleteInput = (
                    fila.querySelector(
                        'input[type="checkbox"][name$="-DELETE"]'
                    )
                );


                if (deleteInput) {
                    deleteInput.checked = true;
                }


                fila.style.display = (
                    "none"
                );
            }
        );


        mostrarEstadoVacio(
            "Seleccione una categoría para cargar "
            + "sus características técnicas."
        );
    }


    // =====================================================
    // ESTADO VACÍO
    // =====================================================

    function mostrarEstadoVacio(
        mensaje
    ) {

        const estado = (
            document.getElementById(
                "atributosEstadoVacio"
            )
        );

        const tabla = (
            document.getElementById(
                "atributosTablaWrap"
            )
        );


        if (estado) {

            estado.textContent = (
                mensaje
            );

            estado.style.display = "";
        }


        if (tabla) {

            tabla.style.display = (
                "none"
            );
        }
    }


    // =====================================================
    // MOSTRAR TABLA
    // =====================================================

    function mostrarTabla() {

        const estado = (
            document.getElementById(
                "atributosEstadoVacio"
            )
        );

        const tabla = (
            document.getElementById(
                "atributosTablaWrap"
            )
        );


        if (estado) {

            estado.style.display = (
                "none"
            );
        }


        if (tabla) {

            tabla.style.display = "";
        }
    }


    // =====================================================
    // VALIDACIÓN
    // =====================================================

    function validarAtributos() {

        let valido = true;

        let primerError = null;


        document.querySelectorAll(
            "#atributosContainer .atributo-form"
        ).forEach(
            function (fila) {

                if (
                    fila.style.display
                    === "none"
                ) {
                    return;
                }


                const deleteInput = (
                    fila.querySelector(
                        'input[type="checkbox"][name$="-DELETE"]'
                    )
                );


                if (
                    deleteInput?.checked
                ) {
                    return;
                }


                const valor = (
                    fila.querySelector(
                        '[name$="-valor"]'
                    )
                );


                if (!valor) {
                    return;
                }


                valor.style.borderColor = (
                    ""
                );


                const requerido = (
                    fila.dataset.requerido
                    === "1"
                );


                const contenido = (
                    String(
                        valor.value
                        || ""
                    ).trim()
                );


                if (
                    requerido
                    && !contenido
                ) {

                    valido = false;

                    valor.style.borderColor = (
                        "var(--danger)"
                    );

                    primerError = (
                        primerError
                        || valor
                    );

                    return;
                }


                if (
                    contenido
                    && typeof valor.checkValidity
                    === "function"
                    && !valor.checkValidity()
                ) {

                    valido = false;

                    valor.style.borderColor = (
                        "var(--danger)"
                    );

                    primerError = (
                        primerError
                        || valor
                    );
                }
            }
        );


        if (
            !valido
            && primerError
        ) {

            primerError.focus();
        }


        return valido;
    }


    // =====================================================
    // OBTENER ATRIBUTOS
    // =====================================================

    function obtenerAtributos() {

        const resultado = [];


        document.querySelectorAll(
            "#atributosContainer .atributo-form"
        ).forEach(
            function (fila) {

                if (
                    fila.style.display
                    === "none"
                ) {
                    return;
                }


                const deleteInput = (
                    fila.querySelector(
                        'input[type="checkbox"][name$="-DELETE"]'
                    )
                );


                if (
                    deleteInput?.checked
                ) {
                    return;
                }


                const atributo = (
                    fila.querySelector(
                        'input[type="hidden"][name$="-atributo"]'
                    )
                );


                const valor = (
                    fila.querySelector(
                        '[name$="-valor"]'
                    )
                );


                const atributoId = String(
                    atributo?.value
                    || ""
                ).trim();


                const valorTexto = String(
                    valor?.value
                    || ""
                ).trim();


                if (
                    !atributoId
                    || !valorTexto
                ) {
                    return;
                }


                resultado.push({
                    atributo:
                        atributoId,

                    valor:
                        valorTexto,

                    requerido:
                        fila.dataset.requerido
                        === "1",

                    tipo_dato:
                        fila.dataset.tipoDato
                        || "TEXTO",
                });
            }
        );


        return resultado;
    }


    // =====================================================
    // CONSULTA
    // =====================================================

    function atributoEstaEnFormulario(
        atributoId
    ) {

        return Array.from(
            document.querySelectorAll(
                "#atributosContainer .atributo-form"
            )
        ).some(
            function (fila) {

                if (
                    fila.style.display
                    === "none"
                ) {
                    return false;
                }


                const deleteInput = (
                    fila.querySelector(
                        'input[type="checkbox"][name$="-DELETE"]'
                    )
                );


                if (
                    deleteInput?.checked
                ) {
                    return false;
                }


                const atributo = (
                    fila.querySelector(
                        'input[type="hidden"][name$="-atributo"]'
                    )
                );


                return (
                    String(
                        atributo?.value
                        || ""
                    )
                    === String(
                        atributoId
                    )
                );
            }
        );
    }


    // =====================================================
    // API PÚBLICA
    // =====================================================

    window.inicializarAtributos = (
        inicializarAtributos
    );

    window.limpiarAtributos = (
        limpiarAtributos
    );

    window.validarAtributos = (
        validarAtributos
    );

    window.obtenerAtributos = (
        obtenerAtributos
    );

    window.atributoEstaEnFormulario = (
        atributoEstaEnFormulario
    );


    window.MAOAtributos = {

        cargarCategoria:
            cargarAtributosCategoria,

        sincronizarFamilia:
            sincronizarFamiliaDesdeCategoria,

        filtrarCategorias:
            filtrarCategoriasPorFamilia,
    };


    // =====================================================
    // ARRANQUE
    // =====================================================

    if (
        document.readyState
        === "loading"
    ) {

        document.addEventListener(
            "DOMContentLoaded",
            inicializarAtributos
        );

    } else {

        inicializarAtributos();
    }

})();