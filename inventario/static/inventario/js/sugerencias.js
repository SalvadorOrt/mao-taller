// =========================================================
// MOTOR INTELIGENTE DE SUGERENCIAS - CATÁLOGO
// =========================================================
//
// RESPONSABILIDADES:
//
// - Analizar nombre / descripción / código / barcode.
// - Sugerir categoría.
// - Sugerir productos existentes.
// - Sugerir marca.
// - Aplicar categoría sugerida.
// - Aplicar marca sugerida.
//
// IMPORTANTE:
//
// Este archivo NO administra atributos técnicos.
//
// La lógica:
//
// Categoría
//     ↓
// atributos.js
//     ↓
// Familia automática
//     ↓
// Características técnicas
//
// =========================================================

(function () {
    "use strict";


    // =====================================================
    // CONFIGURACIÓN
    // =====================================================

    const DEBOUNCE_MS = 550;

    const MIN_TEXTO = 3;
    const MIN_CODIGO = 2;

    const CONFIANZA_AUTO_CATEGORIA = 75;
    const CONFIANZA_AUTO_MARCA = 80;


    // =====================================================
    // ESTADO
    // =====================================================

    let form = null;

    let urlSugerencias = "";

    let temporizador = null;

    let controladorPeticion = null;

    let filaCodigoActiva = null;

    let categoriaTocadaManual = false;

    let aplicandoAutomaticamente = false;

    const marcasTocadasManual = new WeakSet();


    // =====================================================
    // INICIALIZACIÓN
    // =====================================================

    function inicializarSugerencias() {

        form = document.getElementById(
            "catalogoForm"
        );

        if (!form) {
            return;
        }


        // Evitar inicialización doble.
        if (
            form.dataset.sugerenciasInicializadas
            === "1"
        ) {
            return;
        }

        form.dataset.sugerenciasInicializadas = "1";


        urlSugerencias = (
            form.dataset.urlSugerencias
            || ""
        );


        if (!urlSugerencias) {
            console.warn(
                "MAO: falta data-url-sugerencias "
                + "en catalogoForm."
            );
        }


        conectarEventos();

        conectarCerrarPanel();
    }


    // =====================================================
    // EVENTOS
    // =====================================================

    function conectarEventos() {


        // =================================================
        // INPUT
        // =================================================

        form.addEventListener(
            "input",
            function (event) {

                const target = (
                    event.target
                );


                // =========================================
                // CATEGORÍA ESCRITA MANUALMENTE
                // =========================================

                if (
                    target.classList.contains(
                        "apple-dropdown-input"
                    )
                    && target.closest(
                        '.apple-dropdown[data-dropdown-tipo="categoria"]'
                    )
                ) {

                    if (
                        !aplicandoAutomaticamente
                    ) {
                        categoriaTocadaManual = true;
                    }

                    return;
                }


                // =========================================
                // MARCA ESCRITA MANUALMENTE
                // =========================================

                if (
                    target.classList.contains(
                        "apple-dropdown-input"
                    )
                    && target.closest(
                        '.apple-dropdown[data-dropdown-tipo="marca"]'
                    )
                ) {

                    const fila = (
                        target.closest(
                            ".codigo-form"
                        )
                    );

                    if (
                        fila
                        && !aplicandoAutomaticamente
                    ) {
                        marcasTocadasManual.add(
                            fila
                        );
                    }

                    return;
                }


                // =========================================
                // CAMPOS DEL PRODUCTO
                // =========================================

                if (
                    esCampoProducto(
                        target
                    )
                ) {

                    programarAnalisis(
                        obtenerPrimeraFilaCodigoVisible()
                    );

                    return;
                }


                // =========================================
                // CAMPOS DE CÓDIGO
                // =========================================

                if (
                    esCampoCodigo(
                        target
                    )
                ) {

                    filaCodigoActiva = (
                        target.closest(
                            ".codigo-form"
                        )
                    );

                    programarAnalisis(
                        filaCodigoActiva
                    );
                }
            }
        );


        // =================================================
        // CHANGE
        // =================================================

        form.addEventListener(
            "change",
            function (event) {

                const target = (
                    event.target
                );


                // =========================================
                // CATEGORÍA SELECCIONADA
                // =========================================
                //
                // NO cargamos atributos aquí.
                //
                // atributos.js escucha este mismo evento
                // y se encarga de:
                //
                // categoría -> familia
                // categoría -> atributos técnicos
                //
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
                        !aplicandoAutomaticamente
                    ) {
                        categoriaTocadaManual = true;
                    }

                    return;
                }


                // =========================================
                // MARCA SELECCIONADA
                // =========================================

                if (
                    target.classList.contains(
                        "apple-dropdown-hidden"
                    )
                    && target.closest(
                        '.apple-dropdown[data-dropdown-tipo="marca"]'
                    )
                ) {

                    const fila = (
                        target.closest(
                            ".codigo-form"
                        )
                    );

                    if (
                        fila
                        && !aplicandoAutomaticamente
                    ) {

                        marcasTocadasManual.add(
                            fila
                        );
                    }

                    return;
                }


                // =========================================
                // MOTOR - PRODUCTO
                // =========================================

                if (
                    esCampoProducto(
                        target
                    )
                ) {

                    programarAnalisis(
                        obtenerPrimeraFilaCodigoVisible()
                    );

                    return;
                }


                // =========================================
                // MOTOR - CÓDIGO
                // =========================================

                if (
                    esCampoCodigo(
                        target
                    )
                ) {

                    filaCodigoActiva = (
                        target.closest(
                            ".codigo-form"
                        )
                    );

                    programarAnalisis(
                        filaCodigoActiva
                    );
                }
            }
        );


        // =================================================
        // CLICK EN CATEGORÍA
        // =================================================
        //
        // Respaldo para detectar intención humana incluso
        // antes de que dropdowns.js emita el change.
        //
        // =================================================

        form.addEventListener(
            "click",
            function (event) {

                const itemCategoria = (
                    event.target.closest(
                        '.apple-dropdown'
                        + '[data-dropdown-tipo="categoria"] '
                        + '.apple-dropdown-item'
                    )
                );


                if (
                    itemCategoria
                    && !aplicandoAutomaticamente
                ) {

                    categoriaTocadaManual = true;
                }
            }
        );


        // =================================================
        // BOTONES DEL PANEL DE SUGERENCIAS
        // =================================================

        const contenido = (
            document.getElementById(
                "motorSugerenciasContenido"
            )
        );


        if (contenido) {

            contenido.addEventListener(
                "click",
                manejarAccionSugerencia
            );
        }
    }


    // =====================================================
    // CAMPOS QUE ACTIVAN EL MOTOR
    // =====================================================

    function esCampoProducto(
        elemento
    ) {

        if (!elemento?.name) {
            return false;
        }


        return [
            "nombre_base",
            "descripcion",
        ].includes(
            elemento.name
        );
    }


    function esCampoCodigo(
        elemento
    ) {

        if (!elemento?.name) {
            return false;
        }


        return (
            elemento.name.endsWith(
                "-codigo"
            )

            || elemento.name.endsWith(
                "-codigo_barras"
            )

            || elemento.name.endsWith(
                "-nombre_comercial"
            )
        );
    }


    // =====================================================
    // DEBOUNCE
    // =====================================================

    function programarAnalisis(
        filaCodigo = null
    ) {

        clearTimeout(
            temporizador
        );


        filaCodigoActiva = (
            filaCodigo
            || filaCodigoActiva
            || obtenerPrimeraFilaCodigoVisible()
        );


        temporizador = setTimeout(
            analizarFormulario,
            DEBOUNCE_MS
        );
    }


    // =====================================================
    // DATOS PARA EL MOTOR
    // =====================================================

    function obtenerDatosMotor() {

        const nombre = (
            form.querySelector(
                '[name="nombre_base"]'
            )?.value
            || ""
        ).trim();


        const descripcion = (
            form.querySelector(
                '[name="descripcion"]'
            )?.value
            || ""
        ).trim();


        const fila = (
            filaCodigoActiva
            || obtenerPrimeraFilaCodigoVisible()
        );


        const nombreComercial = (
            fila?.querySelector(
                'input[name$="-nombre_comercial"]'
            )?.value
            || ""
        ).trim();


        const codigo = (
            obtenerCodigoFila(
                fila
            )
        );


        const partes = [];


        [
            nombre,
            descripcion,
            nombreComercial,
        ].forEach(
            function (valor) {

                if (
                    valor
                    && !partes.some(
                        function (existente) {

                            return (
                                existente
                                .toLowerCase()
                                ===
                                valor
                                .toLowerCase()
                            );
                        }
                    )
                ) {

                    partes.push(
                        valor
                    );
                }
            }
        );


        const texto = (
            partes
            .join(" | ")
            .trim()
        );


        return {
            texto,
            codigo,
            nombre,
            descripcion,
            nombreComercial,
            fila,
        };
    }


    // =====================================================
    // CÓDIGO DE LA FILA
    // =====================================================

    function obtenerCodigoFila(
        fila
    ) {

        if (!fila) {
            return "";
        }


        const codigo = (
            fila.querySelector(
                'input[name$="-codigo"]'
            )?.value
            || ""
        ).trim();


        // Preferimos referencia comercial.
        if (codigo) {
            return codigo;
        }


        // Si no existe, usamos barcode.
        return (
            fila.querySelector(
                'input[name$="-codigo_barras"]'
            )?.value
            || ""
        ).trim();
    }


    // =====================================================
    // CONSULTA AL MOTOR
    // =====================================================

    async function analizarFormulario() {

        if (!urlSugerencias) {
            return;
        }


        const datos = (
            obtenerDatosMotor()
        );


        guardarTextoAprendizaje(
            datos.texto
        );


        const textoValido = (
            datos.texto.length
            >= MIN_TEXTO
        );


        const codigoValido = (
            datos.codigo.length
            >= MIN_CODIGO
        );


        if (
            !textoValido
            && !codigoValido
        ) {

            ocultarPanel();

            return;
        }


        // =================================================
        // CANCELAR CONSULTA ANTERIOR
        // =================================================

        if (
            controladorPeticion
        ) {

            controladorPeticion.abort();
        }


        controladorPeticion = (
            new AbortController()
        );


        mostrarPanelAnalizando();


        try {

            const parametros = (
                new URLSearchParams()
            );


            if (datos.texto) {

                parametros.set(
                    "texto",
                    datos.texto
                );
            }


            if (datos.codigo) {

                parametros.set(
                    "codigo",
                    datos.codigo
                );
            }


            const respuesta = await fetch(
                (
                    `${urlSugerencias}`
                    + `?${parametros.toString()}`
                ),
                {
                    method: "GET",

                    headers: {

                        "X-Requested-With":
                            "XMLHttpRequest",

                        "Accept":
                            "application/json",
                    },

                    signal:
                        controladorPeticion.signal,
                }
            );


            const resultado = (
                await respuesta.json()
            );


            if (!respuesta.ok) {

                throw new Error(
                    resultado.error
                    || (
                        "No se pudo analizar "
                        + "el producto."
                    )
                );
            }


            if (
                resultado.ok
                === false
            ) {

                throw new Error(
                    resultado.error
                    || (
                        "No se pudo analizar "
                        + "el producto."
                    )
                );
            }


            procesarResultado(
                resultado,
                datos
            );


        } catch (error) {

            if (
                error.name
                === "AbortError"
            ) {

                return;
            }


            console.error(
                "MAO - MotorSugerenciasProducto:",
                error
            );


            mostrarErrorMotor(
                error.message
            );


        } finally {

            controladorPeticion = null;
        }
    }


    // =====================================================
    // PROCESAR RESULTADO
    // =====================================================

    function procesarResultado(
        resultado,
        datosEntrada
    ) {

        const categorias = (
            Array.isArray(
                resultado.categorias
            )
                ? resultado.categorias
                : []
        );


        const productos = (
            Array.isArray(
                resultado.productos
            )
                ? resultado.productos
                : []
        );


        const mejorCategoria = (
            categorias[0]
            || null
        );


        const mejorProducto = (
            productos[0]
            || null
        );


        // =================================================
        // CATEGORÍA AUTOMÁTICA
        // =================================================

        if (
            mejorCategoria
            && Number(
                mejorCategoria.confianza
                || 0
            )
            >= CONFIANZA_AUTO_CATEGORIA
        ) {

            autoAplicarCategoria(
                mejorCategoria
            );
        }


        else if (
            !mejorCategoria
            && mejorProducto?.categoria_id
            && Number(
                mejorProducto.confianza
                || 0
            )
            >= CONFIANZA_AUTO_CATEGORIA
        ) {

            autoAplicarCategoria({
                id:
                    mejorProducto.categoria_id,

                nombre:
                    mejorProducto.categoria,

                confianza:
                    mejorProducto.confianza,
            });
        }


        // =================================================
        // MARCA AUTOMÁTICA
        // =================================================

        if (
            mejorProducto?.marca_id
            && Number(
                mejorProducto.confianza
                || 0
            )
            >= CONFIANZA_AUTO_MARCA
        ) {

            autoAplicarMarca(
                datosEntrada.fila,
                mejorProducto
            );
        }


        // =================================================
        // MOSTRAR RESULTADOS
        // =================================================

        renderizarResultado(
            resultado
        );
    }


    // =====================================================
    // AUTO APLICAR CATEGORÍA
    // =====================================================

    function autoAplicarCategoria(
        categoria
    ) {

        const dropdown = (
            obtenerDropdownCategoria()
        );


        if (
            !dropdown
            || !categoria?.id
        ) {

            return;
        }


        // =================================================
        // NO PISAR DECISIÓN HUMANA
        // =================================================

        if (
            categoriaTocadaManual
        ) {

            return;
        }


        // =================================================
        // NO CAMBIAR UNA CATEGORÍA YA SELECCIONADA
        // =================================================

        if (
            dropdown.hidden.value
            && String(
                dropdown.hidden.value
            )
            !== String(
                categoria.id
            )
        ) {

            return;
        }


        // =================================================
        // RESPETAR FAMILIA SELECCIONADA
        // =================================================
        //
        // Si el usuario eligió:
        //
        // Familia = Frenos
        //
        // el motor no debe autoasignar:
        //
        // Categoría = Filtro de aire
        //
        // =================================================

        if (
            !categoriaPerteneceFamiliaActual(
                categoria.id
            )
        ) {

            return;
        }


        seleccionarDropdownLocal(
            dropdown.wrap,
            categoria.id,
            categoria.nombre,
            true
        );
    }


    // =====================================================
    // APLICAR CATEGORÍA DESDE BOTÓN "APLICAR"
    // =====================================================

    function aplicarCategoriaForzada(
        categoriaId,
        categoriaNombre
    ) {

        const dropdown = (
            obtenerDropdownCategoria()
        );


        if (!dropdown) {
            return;
        }


        seleccionarDropdownLocal(
            dropdown.wrap,
            categoriaId,
            categoriaNombre,
            true
        );


        // A partir de aquí se considera
        // una decisión explícita del usuario.
        categoriaTocadaManual = true;


        // NO cargamos atributos aquí.
        //
        // seleccionarDropdownLocal() dispara "change".
        //
        // atributos.js escucha ese evento y realiza:
        //
        // categoría -> familia
        // categoría -> características
    }


    // =====================================================
    // VALIDAR FAMILIA ACTUAL
    // =====================================================

    function categoriaPerteneceFamiliaActual(
        categoriaId
    ) {

        const familia = (
            obtenerDropdownFamilia()
        );


        if (
            !familia
            || !familia.hidden?.value
        ) {

            return true;
        }


        const dropdownCategoria = (
            obtenerDropdownCategoria()
        );


        if (!dropdownCategoria) {
            return true;
        }


        const item = (
            buscarItemDropdown(
                dropdownCategoria.wrap,
                categoriaId
            )
        );


        // Si por alguna razón no encontramos el item,
        // no bloqueamos la sugerencia.
        if (!item) {
            return true;
        }


        const familiaCategoria = String(
            item.dataset.familiaId
            || ""
        );


        if (!familiaCategoria) {
            return true;
        }


        return (
            familiaCategoria
            === String(
                familia.hidden.value
            )
        );
    }


    // =====================================================
    // AUTO APLICAR MARCA
    // =====================================================

    function autoAplicarMarca(
        fila,
        producto
    ) {

        if (
            !fila
            || !producto?.marca_id
        ) {

            return;
        }


        // No pisar selección manual.
        if (
            marcasTocadasManual.has(
                fila
            )
        ) {

            return;
        }


        const wrap = (
            fila.querySelector(
                '.apple-dropdown'
                + '[data-dropdown-tipo="marca"]'
            )
        );


        if (!wrap) {
            return;
        }


        const hidden = (
            wrap.querySelector(
                ".apple-dropdown-hidden"
            )
        );


        if (
            hidden?.value
            && String(
                hidden.value
            )
            !== String(
                producto.marca_id
            )
        ) {

            return;
        }


        seleccionarDropdownLocal(
            wrap,
            producto.marca_id,
            producto.marca,
            true
        );
    }


    // =====================================================
    // APLICAR MARCA MANUAL DESDE MOTOR
    // =====================================================

    function aplicarMarcaForzada(
        marcaId,
        marcaNombre
    ) {

        const fila = (
            filaCodigoActiva
            || obtenerPrimeraFilaCodigoVisible()
        );


        if (!fila) {
            return;
        }


        const wrap = (
            fila.querySelector(
                '.apple-dropdown'
                + '[data-dropdown-tipo="marca"]'
            )
        );


        if (!wrap) {
            return;
        }


        seleccionarDropdownLocal(
            wrap,
            marcaId,
            marcaNombre,
            true
        );


        marcasTocadasManual.add(
            fila
        );
    }


    // =====================================================
    // SELECCIONAR APPLE DROPDOWN
    // =====================================================

    function seleccionarDropdownLocal(
        wrap,
        id,
        nombre = "",
        automatico = false
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


        const idTexto = (
            String(id)
        );


        const item = (
            buscarItemDropdown(
                wrap,
                idTexto
            )
        );


        const nombreFinal = (
            item?.dataset.nombre
            || item?.textContent?.trim()
            || nombre
            || ""
        );


        aplicandoAutomaticamente = (
            automatico
        );


        try {

            // =================================================
            // APPLE DROPDOWN
            // =================================================

            if (
                item
                && window.AppleDropdown
                && typeof (
                    window.AppleDropdown
                    .seleccionarItem
                ) === "function"
            ) {

                window.AppleDropdown
                    .seleccionarItem(
                        wrap,
                        item
                    );


                hidden.value = (
                    idTexto
                );


                input.value = (
                    nombreFinal
                );


                // =============================================
                // EVENTO FUNDAMENTAL
                // =============================================
                //
                // Este evento lo recibe atributos.js.
                //
                // Categoría seleccionada
                //        ↓
                // familia automática
                //        ↓
                // atributos automáticos
                //
                // =============================================

                hidden.dispatchEvent(
                    new Event(
                        "change",
                        {
                            bubbles: true,
                        }
                    )
                );
            }


            // =================================================
            // FALLBACK
            // =================================================

            else {

                input.value = (
                    nombreFinal
                );


                hidden.value = (
                    idTexto
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


        } finally {

            aplicandoAutomaticamente = false;
        }


        return true;
    }


    // =====================================================
    // BUSCAR ITEM DROPDOWN
    // =====================================================

    function buscarItemDropdown(
        wrap,
        id
    ) {

        if (!wrap) {
            return null;
        }


        const idTexto = (
            String(id)
        );


        return Array.from(
            wrap.querySelectorAll(
                ".apple-dropdown-item"
            )
        ).find(
            function (elemento) {

                return (
                    String(
                        elemento.dataset.id
                        || ""
                    )
                    === idTexto
                );
            }
        ) || null;
    }


    // =====================================================
    // DROPDOWN CATEGORÍA
    // =====================================================

    function obtenerDropdownCategoria() {

        const wrap = (
            form.querySelector(
                '.apple-dropdown'
                + '[data-dropdown-tipo="categoria"]'
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
        };
    }


    // =====================================================
    // DROPDOWN FAMILIA
    // =====================================================

    function obtenerDropdownFamilia() {

        const wrap = (
            form.querySelector(
                '.apple-dropdown'
                + '[data-dropdown-tipo="familia"]'
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
        };
    }


    // =====================================================
    // PANEL - ANALIZANDO
    // =====================================================

    function mostrarPanelAnalizando() {

        const panel = (
            document.getElementById(
                "motorSugerencias"
            )
        );


        const estado = (
            document.getElementById(
                "motorSugerenciasEstado"
            )
        );


        const contenido = (
            document.getElementById(
                "motorSugerenciasContenido"
            )
        );


        if (!panel) {
            return;
        }


        panel.hidden = false;


        if (estado) {

            estado.textContent = (
                "Analizando producto..."
            );
        }


        if (contenido) {

            contenido.innerHTML = `
                <div class="motor-sugerencia-bloque">

                    <div class="motor-sugerencia-valor">

                        Buscando coincidencias en catálogo,
                        compras y aprendizaje...

                    </div>

                </div>
            `;
        }
    }


    // =====================================================
    // RENDER RESULTADO
    // =====================================================

    function renderizarResultado(
        resultado
    ) {

        const panel = (
            document.getElementById(
                "motorSugerencias"
            )
        );


        const estado = (
            document.getElementById(
                "motorSugerenciasEstado"
            )
        );


        const contenido = (
            document.getElementById(
                "motorSugerenciasContenido"
            )
        );


        if (
            !panel
            || !contenido
        ) {

            return;
        }


        const categorias = (
            Array.isArray(
                resultado.categorias
            )
                ? resultado.categorias
                : []
        );


        const productos = (
            Array.isArray(
                resultado.productos
            )
                ? resultado.productos
                : []
        );


        // =================================================
        // SIN RESULTADOS
        // =================================================

        if (
            !categorias.length
            && !productos.length
        ) {

            panel.hidden = false;


            if (estado) {

                estado.textContent = (
                    "Sin coincidencias suficientes"
                );
            }


            contenido.innerHTML = `
                <div class="motor-sugerencia-bloque">

                    <div class="motor-sugerencia-valor">

                        No encontré un producto existente
                        con suficiente confianza.

                        Puede continuar creando una
                        referencia nueva.

                    </div>

                </div>
            `;


            return;
        }


        panel.hidden = false;


        if (estado) {

            estado.textContent = (
                resultado.hay_codigo_exacto
                    ? "Código encontrado en el catálogo"
                    : "Resultados encontrados"
            );
        }


        let html = "";


        // =================================================
        // CATEGORÍA SUGERIDA
        // =================================================

        if (
            categorias.length
        ) {

            const categoria = (
                categorias[0]
            );


            html += `
                <div class="motor-sugerencia-bloque">

                    <div class="motor-sugerencia-label">
                        Categoría sugerida
                    </div>

                    <div class="motor-sugerencia-valor">

                        ${escaparHTML(
                            categoria.nombre
                            || ""
                        )}

                        <span class="motor-confianza">

                            ${formatearConfianza(
                                categoria.confianza
                            )}

                        </span>

                        <button
                            type="button"
                            class="btn-login"

                            data-motor-accion="categoria"

                            data-categoria-id="${escaparAtributo(
                                categoria.id
                            )}"

                            data-categoria-nombre="${escaparAtributo(
                                categoria.nombre
                                || ""
                            )}"

                            style="
                                margin-left:8px;
                                height:25px;
                                padding:0 8px;
                                font-size:8px;
                            "
                        >
                            Aplicar
                        </button>

                    </div>

                </div>
            `;
        }


        // =================================================
        // PRODUCTOS EXISTENTES
        // =================================================

        if (
            productos.length
        ) {

            html += `
                <div class="motor-sugerencia-bloque">

                    <div class="motor-sugerencia-label">
                        Posibles productos existentes
                    </div>
            `;


            productos
                .slice(
                    0,
                    3
                )
                .forEach(
                    function (producto) {

                        html += `
                            <div class="motor-producto-item">

                                <div>

                                    <div class="motor-producto-nombre">

                                        ${escaparHTML(
                                            producto.producto
                                            || "Producto"
                                        )}

                                    </div>

                                    <div class="motor-producto-meta">

                                        ${escaparHTML(
                                            producto.sku
                                            || ""
                                        )}

                                        ${
                                            producto.marca
                                                ? (
                                                    " · "
                                                    + escaparHTML(
                                                        producto.marca
                                                    )
                                                )
                                                : ""
                                        }

                                        ${
                                            producto.codigo
                                                ? (
                                                    " · "
                                                    + escaparHTML(
                                                        producto.codigo
                                                    )
                                                )
                                                : ""
                                        }

                                    </div>

                                </div>


                                <div
                                    style="
                                        display:flex;
                                        align-items:center;
                                        gap:6px;
                                        flex-shrink:0;
                                    "
                                >

                                    <span class="motor-confianza">

                                        ${formatearConfianza(
                                            producto.confianza
                                        )}

                                    </span>


                                    ${
                                        producto.marca_id

                                            ? `
                                                <button
                                                    type="button"

                                                    class="btn-login"

                                                    data-motor-accion="marca"

                                                    data-marca-id="${escaparAtributo(
                                                        producto.marca_id
                                                    )}"

                                                    data-marca-nombre="${escaparAtributo(
                                                        producto.marca
                                                        || ""
                                                    )}"

                                                    style="
                                                        height:25px;
                                                        padding:0 7px;
                                                        font-size:8px;
                                                    "
                                                >
                                                    Usar marca
                                                </button>
                                            `

                                            : ""
                                    }

                                </div>

                            </div>
                        `;
                    }
                );


            html += `
                </div>
            `;
        }


        contenido.innerHTML = (
            html
        );
    }


    // =====================================================
    // ERROR MOTOR
    // =====================================================

    function mostrarErrorMotor(
        mensaje
    ) {

        const panel = (
            document.getElementById(
                "motorSugerencias"
            )
        );


        const estado = (
            document.getElementById(
                "motorSugerenciasEstado"
            )
        );


        const contenido = (
            document.getElementById(
                "motorSugerenciasContenido"
            )
        );


        if (!panel) {
            return;
        }


        panel.hidden = false;


        if (estado) {

            estado.textContent = (
                "No se pudo completar el análisis"
            );
        }


        if (contenido) {

            contenido.innerHTML = `
                <div class="motor-sugerencia-bloque">

                    <div class="motor-sugerencia-valor">

                        ${escaparHTML(
                            mensaje
                            || "Error consultando el motor."
                        )}

                    </div>

                </div>
            `;
        }
    }


    // =====================================================
    // OCULTAR PANEL
    // =====================================================

    function ocultarPanel() {

        const panel = (
            document.getElementById(
                "motorSugerencias"
            )
        );


        if (panel) {

            panel.hidden = true;
        }
    }


    // =====================================================
    // CERRAR PANEL
    // =====================================================

    function conectarCerrarPanel() {

        const boton = (
            document.getElementById(
                "cerrarMotorSugerencias"
            )
        );


        if (!boton) {
            return;
        }


        boton.addEventListener(
            "click",
            ocultarPanel
        );
    }


    // =====================================================
    // ACCIONES DEL PANEL
    // =====================================================

    function manejarAccionSugerencia(
        event
    ) {

        const boton = (
            event.target.closest(
                "[data-motor-accion]"
            )
        );


        if (!boton) {
            return;
        }


        const accion = (
            boton.dataset.motorAccion
        );


        // =================================================
        // CATEGORÍA
        // =================================================

        if (
            accion === "categoria"
        ) {

            aplicarCategoriaForzada(
                boton.dataset.categoriaId,
                boton.dataset.categoriaNombre
            );

            return;
        }


        // =================================================
        // MARCA
        // =================================================

        if (
            accion === "marca"
        ) {

            aplicarMarcaForzada(
                boton.dataset.marcaId,
                boton.dataset.marcaNombre
            );
        }
    }


    // =====================================================
    // TEXTO DE APRENDIZAJE
    // =====================================================

    function guardarTextoAprendizaje(
        texto
    ) {

        const input = (
            document.getElementById(
                "textoAprendizaje"
            )
        );


        if (!input) {
            return;
        }


        input.value = (
            String(
                texto
                || ""
            ).trim()
        );
    }


    // =====================================================
    // PRIMERA FILA DE CÓDIGO
    // =====================================================

    function obtenerPrimeraFilaCodigoVisible() {

        return Array.from(
            document.querySelectorAll(
                "#codigosContainer .codigo-form"
            )
        ).find(
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


                return (
                    !deleteInput?.checked
                );
            }
        ) || null;
    }


    // =====================================================
    // ESCAPAR HTML
    // =====================================================

    function escaparHTML(
        valor
    ) {

        return String(
            valor
            ?? ""
        )
            .replaceAll(
                "&",
                "&amp;"
            )
            .replaceAll(
                "<",
                "&lt;"
            )
            .replaceAll(
                ">",
                "&gt;"
            )
            .replaceAll(
                '"',
                "&quot;"
            )
            .replaceAll(
                "'",
                "&#039;"
            );
    }


    // =====================================================
    // ESCAPAR ATRIBUTO HTML
    // =====================================================

    function escaparAtributo(
        valor
    ) {

        return escaparHTML(
            valor
        );
    }


    // =====================================================
    // CONFIANZA
    // =====================================================

    function formatearConfianza(
        valor
    ) {

        const numero = Number(
            valor
            || 0
        );


        if (
            !Number.isFinite(
                numero
            )
        ) {

            return "0%";
        }


        return (
            `${Math.round(numero)}%`
        );
    }


    // =====================================================
    // API PÚBLICA
    // =====================================================

    window.MAOSugerencias = {

        analizar:
            analizarFormulario,

        aplicarCategoria:
            aplicarCategoriaForzada,

        aplicarMarca:
            aplicarMarcaForzada,
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
            inicializarSugerencias
        );

    } else {

        inicializarSugerencias();
    }

})();