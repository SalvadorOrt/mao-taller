// =========================================================
// MOTOR INTELIGENTE DE SUGERENCIAS - CATÁLOGO
// =========================================================

(function () {
    "use strict";

    const DEBOUNCE_MS = 550;
    const MIN_TEXTO = 3;
    const MIN_CODIGO = 2;

    // Solo se autoselecciona cuando la confianza es razonable.
    // El usuario siempre puede cambiar la decisión.
    const CONFIANZA_AUTO_CATEGORIA = 75;
    const CONFIANZA_AUTO_MARCA = 80;

    let form = null;
    let urlSugerencias = "";
    let urlAtributosCategoria = "";

    let temporizador = null;
    let controladorPeticion = null;
    let controladorAtributos = null;

    let filaCodigoActiva = null;
    let categoriaTocadaManual = false;
    let aplicandoAutomaticamente = false;
    let ultimaCategoriaAtributos = null;

    const marcasTocadasManual = new WeakSet();


    // =====================================================
    // INICIALIZACIÓN
    // =====================================================

    function inicializarSugerencias() {
        form = document.getElementById("catalogoForm");

        if (!form) return;

        urlSugerencias = form.dataset.urlSugerencias || "";
        urlAtributosCategoria = (
            form.dataset.urlAtributosCategoria || ""
        );

        if (!urlSugerencias) {
            console.warn(
                "MAO: falta data-url-sugerencias en catalogoForm."
            );
        }

        conectarEventos();
        conectarCerrarPanel();

        const categoriaInicial = obtenerDropdownCategoria();

        if (
            categoriaInicial?.hidden?.value
            && urlAtributosCategoria
        ) {
            cargarAtributosCategoria(
                categoriaInicial.hidden.value
            );
        }
    }


    // =====================================================
    // EVENTOS GENERALES
    // =====================================================

    function conectarEventos() {
        form.addEventListener("input", function (event) {
            const target = event.target;

            // ---------------------------------------------
            // CATEGORÍA ESCRITA MANUALMENTE
            // ---------------------------------------------

            if (
                target.classList.contains("apple-dropdown-input")
                && target.closest(
                    '.apple-dropdown[data-dropdown-tipo="categoria"]'
                )
            ) {
                if (!aplicandoAutomaticamente) {
                    categoriaTocadaManual = true;
                }
            }

            // ---------------------------------------------
            // MARCA ESCRITA MANUALMENTE
            // ---------------------------------------------

            if (
                target.classList.contains("apple-dropdown-input")
                && target.closest(
                    '.apple-dropdown[data-dropdown-tipo="marca"]'
                )
            ) {
                const fila = target.closest(".codigo-form");

                if (
                    fila
                    && !aplicandoAutomaticamente
                ) {
                    marcasTocadasManual.add(fila);
                }
            }

            // ---------------------------------------------
            // CAMPOS QUE DISPARAN EL MOTOR
            // ---------------------------------------------

            if (esCampoProducto(target)) {
                programarAnalisis(
                    obtenerPrimeraFilaCodigoVisible()
                );
                return;
            }

            if (esCampoCodigo(target)) {
                filaCodigoActiva = target.closest(".codigo-form");

                programarAnalisis(
                    filaCodigoActiva
                );
            }
        });


        form.addEventListener("change", function (event) {
            const target = event.target;

            // ---------------------------------------------
            // CATEGORÍA SELECCIONADA
            // ---------------------------------------------

            if (
                target.classList.contains("apple-dropdown-hidden")
                && target.closest(
                    '.apple-dropdown[data-dropdown-tipo="categoria"]'
                )
            ) {
                if (!aplicandoAutomaticamente) {
                    categoriaTocadaManual = true;
                }

                const categoriaId = target.value;

                if (categoriaId) {
                    cargarAtributosCategoria(categoriaId);
                }

                return;
            }

            // ---------------------------------------------
            // MARCA SELECCIONADA
            // ---------------------------------------------

            if (
                target.classList.contains("apple-dropdown-hidden")
                && target.closest(
                    '.apple-dropdown[data-dropdown-tipo="marca"]'
                )
            ) {
                const fila = target.closest(".codigo-form");

                if (
                    fila
                    && !aplicandoAutomaticamente
                ) {
                    marcasTocadasManual.add(fila);
                }
            }

            if (esCampoProducto(target)) {
                programarAnalisis(
                    obtenerPrimeraFilaCodigoVisible()
                );
                return;
            }

            if (esCampoCodigo(target)) {
                filaCodigoActiva = target.closest(".codigo-form");

                programarAnalisis(
                    filaCodigoActiva
                );
            }
        });


        // ---------------------------------------------
        // BOTONES DEL PANEL DE SUGERENCIAS
        // ---------------------------------------------

        const contenido = document.getElementById(
            "motorSugerenciasContenido"
        );

        if (contenido) {
            contenido.addEventListener(
                "click",
                manejarAccionSugerencia
            );
        }
    }


    // =====================================================
    // CAMPOS QUE DISPARAN ANÁLISIS
    // =====================================================

    function esCampoProducto(elemento) {
        if (!elemento?.name) return false;

        return [
            "nombre_base",
            "descripcion",
        ].includes(elemento.name);
    }


    function esCampoCodigo(elemento) {
        if (!elemento?.name) return false;

        return (
            elemento.name.endsWith("-codigo")
            || elemento.name.endsWith("-codigo_barras")
            || elemento.name.endsWith("-nombre_comercial")
        );
    }


    // =====================================================
    // DEBOUNCE
    // =====================================================

    function programarAnalisis(filaCodigo = null) {
        clearTimeout(temporizador);

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
    // CONSTRUIR ENTRADA DEL MOTOR
    // =====================================================

    function obtenerDatosMotor() {
        const nombre = (
            form.querySelector('[name="nombre_base"]')?.value
            || ""
        ).trim();

        const descripcion = (
            form.querySelector('[name="descripcion"]')?.value
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

        const codigo = obtenerCodigoFila(fila);

        // El nombre forma parte explícitamente de la entrada.
        // Evitamos repetir exactamente el mismo texto.
        const partes = [];

        [nombre, descripcion, nombreComercial].forEach(
            function (valor) {
                if (
                    valor
                    && !partes.some(
                        existente =>
                            existente.toLowerCase()
                            === valor.toLowerCase()
                    )
                ) {
                    partes.push(valor);
                }
            }
        );

        const texto = partes.join(" | ").trim();

        return {
            texto,
            codigo,
            nombre,
            descripcion,
            nombreComercial,
            fila,
        };
    }


    function obtenerCodigoFila(fila) {
        if (!fila) return "";

        const codigo = (
            fila.querySelector(
                'input[name$="-codigo"]'
            )?.value
            || ""
        ).trim();

        if (codigo) return codigo;

        // Si todavía no existe código comercial pero se escaneó
        // un código de barras, también puede consultarse al motor.
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
        if (!urlSugerencias) return;

        const datos = obtenerDatosMotor();

        guardarTextoAprendizaje(datos.texto);

        const textoValido = (
            datos.texto.length >= MIN_TEXTO
        );

        const codigoValido = (
            datos.codigo.length >= MIN_CODIGO
        );

        if (!textoValido && !codigoValido) {
            ocultarPanel();
            return;
        }

        if (controladorPeticion) {
            controladorPeticion.abort();
        }

        controladorPeticion = new AbortController();

        mostrarPanelAnalizando();

        try {
            const parametros = new URLSearchParams();

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
                `${urlSugerencias}?${parametros.toString()}`,
                {
                    method: "GET",
                    headers: {
                        "X-Requested-With": "XMLHttpRequest",
                        "Accept": "application/json",
                    },
                    signal: controladorPeticion.signal,
                }
            );

            const resultado = await respuesta.json();

            if (!respuesta.ok) {
                throw new Error(
                    resultado.error
                    || "No se pudo analizar el producto."
                );
            }

            if (resultado.ok === false) {
                throw new Error(
                    resultado.error
                    || "No se pudo analizar el producto."
                );
            }

            procesarResultado(
                resultado,
                datos
            );

        } catch (error) {
            if (error.name === "AbortError") {
                return;
            }

            console.error(
                "Error en MotorSugerenciasProducto:",
                error
            );

            mostrarErrorMotor(error.message);

        } finally {
            controladorPeticion = null;
        }
    }


    // =====================================================
    // PROCESAR RESULTADO
    // =====================================================

    function procesarResultado(resultado, datosEntrada) {
        const categorias = Array.isArray(
            resultado.categorias
        )
            ? resultado.categorias
            : [];

        const productos = Array.isArray(
            resultado.productos
        )
            ? resultado.productos
            : [];

        const mejorCategoria = categorias[0] || null;
        const mejorProducto = productos[0] || null;

        // ---------------------------------------------
        // AUTO CATEGORÍA
        // ---------------------------------------------

        if (
            mejorCategoria
            && Number(mejorCategoria.confianza || 0)
                >= CONFIANZA_AUTO_CATEGORIA
        ) {
            autoAplicarCategoria(mejorCategoria);
        }

        // Si el motor no trajo la categoría agregada, pero
        // el mejor producto sí tiene categoría, la usamos.
        else if (
            !mejorCategoria
            && mejorProducto?.categoria_id
            && Number(mejorProducto.confianza || 0)
                >= CONFIANZA_AUTO_CATEGORIA
        ) {
            autoAplicarCategoria({
                id: mejorProducto.categoria_id,
                nombre: mejorProducto.categoria,
                confianza: mejorProducto.confianza,
            });
        }

        // ---------------------------------------------
        // AUTO MARCA
        // ---------------------------------------------

        if (
            mejorProducto?.marca_id
            && Number(mejorProducto.confianza || 0)
                >= CONFIANZA_AUTO_MARCA
        ) {
            autoAplicarMarca(
                datosEntrada.fila,
                mejorProducto
            );
        }

        renderizarResultado(resultado);
    }


    // =====================================================
    // APLICAR CATEGORÍA
    // =====================================================

    function autoAplicarCategoria(categoria) {
        const dropdown = obtenerDropdownCategoria();

        if (!dropdown) return;

        // Nunca sobreescribir una decisión humana.
        if (categoriaTocadaManual) return;

        // Si ya existe una categoría seleccionada tampoco
        // la reemplazamos automáticamente.
        if (
            dropdown.hidden.value
            && String(dropdown.hidden.value)
                !== String(categoria.id)
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


    function aplicarCategoriaForzada(
        categoriaId,
        categoriaNombre
    ) {
        const dropdown = obtenerDropdownCategoria();

        if (!dropdown) return;

        seleccionarDropdownLocal(
            dropdown.wrap,
            categoriaId,
            categoriaNombre,
            true
        );

        categoriaTocadaManual = true;
    }


    // =====================================================
    // APLICAR MARCA
    // =====================================================

    function autoAplicarMarca(fila, producto) {
        if (!fila || !producto?.marca_id) return;

        if (marcasTocadasManual.has(fila)) {
            return;
        }

        const wrap = fila.querySelector(
            '.apple-dropdown[data-dropdown-tipo="marca"]'
        );

        if (!wrap) return;

        const hidden = wrap.querySelector(
            ".apple-dropdown-hidden"
        );

        if (
            hidden?.value
            && String(hidden.value)
                !== String(producto.marca_id)
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


    function aplicarMarcaForzada(
        marcaId,
        marcaNombre
    ) {
        const fila = (
            filaCodigoActiva
            || obtenerPrimeraFilaCodigoVisible()
        );

        if (!fila) return;

        const wrap = fila.querySelector(
            '.apple-dropdown[data-dropdown-tipo="marca"]'
        );

        if (!wrap) return;

        seleccionarDropdownLocal(
            wrap,
            marcaId,
            marcaNombre,
            true
        );

        marcasTocadasManual.add(fila);
    }


    // =====================================================
    // SELECCIÓN DE APPLE DROPDOWN LOCAL
    // =====================================================

    function seleccionarDropdownLocal(
        wrap,
        id,
        nombre = "",
        automatico = false
    ) {
        if (!wrap || id === null || id === undefined) {
            return false;
        }

        const input = wrap.querySelector(
            ".apple-dropdown-input"
        );

        const hidden = wrap.querySelector(
            ".apple-dropdown-hidden"
        );

        if (!input || !hidden) return false;

        const idTexto = String(id);

        const item = Array.from(
            wrap.querySelectorAll(".apple-dropdown-item")
        ).find(
            elemento =>
                String(elemento.dataset.id || "")
                === idTexto
        );

        const nombreFinal = (
            item?.dataset.nombre
            || item?.textContent?.trim()
            || nombre
            || ""
        );

        aplicandoAutomaticamente = automatico;

        try {
            if (
                item
                && window.AppleDropdown
                && typeof window.AppleDropdown.seleccionarItem
                    === "function"
            ) {
                window.AppleDropdown.seleccionarItem(
                    wrap,
                    item
                );
            } else {
                input.value = nombreFinal;
                hidden.value = idTexto;

                input.dispatchEvent(
                    new Event(
                        "change",
                        { bubbles: true }
                    )
                );

                hidden.dispatchEvent(
                    new Event(
                        "change",
                        { bubbles: true }
                    )
                );
            }

        } finally {
            aplicandoAutomaticamente = false;
        }

        return true;
    }


    // =====================================================
    // DROPDOWN CATEGORÍA
    // =====================================================

    function obtenerDropdownCategoria() {
        const wrap = form.querySelector(
            '.apple-dropdown[data-dropdown-tipo="categoria"]'
        );

        if (!wrap) return null;

        return {
            wrap,
            input: wrap.querySelector(
                ".apple-dropdown-input"
            ),
            hidden: wrap.querySelector(
                ".apple-dropdown-hidden"
            ),
        };
    }


    // =====================================================
    // ATRIBUTOS POR CATEGORÍA
    // =====================================================

    async function cargarAtributosCategoria(
        categoriaId
    ) {
        if (
            !categoriaId
            || !urlAtributosCategoria
        ) {
            return;
        }

        const categoriaTexto = String(categoriaId);

        if (
            ultimaCategoriaAtributos
            === categoriaTexto
        ) {
            return;
        }

        if (controladorAtributos) {
            controladorAtributos.abort();
        }

        controladorAtributos = new AbortController();

        try {
            const url = construirUrlAtributos(
                categoriaId
            );

            const respuesta = await fetch(
                url,
                {
                    method: "GET",
                    headers: {
                        "X-Requested-With": "XMLHttpRequest",
                        "Accept": "application/json",
                    },
                    signal: controladorAtributos.signal,
                }
            );

            const resultado = await respuesta.json();

            if (!respuesta.ok) {
                throw new Error(
                    resultado.error
                    || "No se pudieron obtener los atributos."
                );
            }

            ultimaCategoriaAtributos = categoriaTexto;

            const atributos = Array.isArray(
                resultado.atributos
            )
                ? resultado.atributos
                : [];

            aplicarAtributosRecomendados(
                categoriaId,
                atributos
            );

        } catch (error) {
            if (error.name === "AbortError") {
                return;
            }

            console.error(
                "Error cargando atributos de categoría:",
                error
            );

        } finally {
            controladorAtributos = null;
        }
    }


    function construirUrlAtributos(categoriaId) {
        // crear.html entrega una URL usando categoria_id = 0.
        // Aquí sustituimos únicamente ese segmento.
        return urlAtributosCategoria.replace(
            /\/0\/(?=atributos\/?)/,
            `/${categoriaId}/`
        );
    }


    // =====================================================
    // CARGAR ATRIBUTOS RECOMENDADOS EN EL FORMSET
    // =====================================================

    function aplicarAtributosRecomendados(
        categoriaId,
        atributos
    ) {
        if (!Array.isArray(atributos)) return;

        limpiarAtributosAutomaticosAnteriores(
            categoriaId
        );

        for (const atributo of atributos) {
            if (!atributo?.id) continue;

            let fila = buscarFilaAtributo(
                atributo.id
            );

            if (!fila) {
                fila = obtenerFilaAtributoVacia();

                if (!fila) {
                    if (
                        typeof window.agregarAtributo
                        === "function"
                    ) {
                        window.agregarAtributo();
                    } else if (
                        typeof agregarAtributo
                        === "function"
                    ) {
                        agregarAtributo();
                    }

                    fila = obtenerUltimaFilaAtributoVisible();
                }
            }

            if (!fila) continue;

            colocarAtributoEnFila(
                fila,
                atributo,
                categoriaId
            );
        }
    }


    function buscarFilaAtributo(atributoId) {
        return Array.from(
            document.querySelectorAll(
                "#atributosContainer .atributo-form"
            )
        ).find(function (fila) {
            if (fila.style.display === "none") {
                return false;
            }

            const hidden = fila.querySelector(
                'input[type="hidden"][name$="-atributo"]'
            );

            return (
                hidden
                && String(hidden.value)
                    === String(atributoId)
            );
        }) || null;
    }


    function obtenerFilaAtributoVacia() {
        return Array.from(
            document.querySelectorAll(
                "#atributosContainer .atributo-form"
            )
        ).find(function (fila) {
            if (fila.style.display === "none") {
                return false;
            }

            const deleteInput = fila.querySelector(
                'input[type="checkbox"][name$="-DELETE"]'
            );

            if (deleteInput?.checked) {
                return false;
            }

            const atributo = fila.querySelector(
                'input[type="hidden"][name$="-atributo"]'
            );

            const valor = fila.querySelector(
                'input[name$="-valor"]'
            );

            return (
                !atributo?.value
                && !valor?.value?.trim()
            );
        }) || null;
    }


    function obtenerUltimaFilaAtributoVisible() {
        const filas = Array.from(
            document.querySelectorAll(
                "#atributosContainer .atributo-form"
            )
        ).filter(
            fila => fila.style.display !== "none"
        );

        return filas.at(-1) || null;
    }


    function colocarAtributoEnFila(
        fila,
        atributo,
        categoriaId
    ) {
        const wrap = fila.querySelector(
            ".apple-dropdown"
        );

        const hidden = fila.querySelector(
            'input[type="hidden"][name$="-atributo"]'
        );

        if (!wrap || !hidden) return;

        // Si la fila ya contiene un atributo manual diferente,
        // nunca lo reemplazamos.
        if (
            hidden.value
            && String(hidden.value)
                !== String(atributo.id)
        ) {
            return;
        }

        seleccionarDropdownLocal(
            wrap,
            atributo.id,
            construirNombreAtributo(atributo),
            true
        );

        fila.dataset.sugerido = "1";
        fila.dataset.categoriaSugerida = String(
            categoriaId
        );

        fila.dataset.requerido = (
            atributo.requerido
            ? "1"
            : "0"
        );

        // Metadata útil para atributos.js.
        const valor = fila.querySelector(
            'input[name$="-valor"]'
        );

        if (valor) {
            valor.dataset.atributoRequerido = (
                atributo.requerido
                ? "1"
                : "0"
            );

            valor.dataset.atributoSugerido = "1";
        }
    }


    function construirNombreAtributo(atributo) {
        if (!atributo) return "";

        if (atributo.unidad) {
            return `${atributo.nombre} (${atributo.unidad})`;
        }

        return atributo.nombre || "";
    }


    // =====================================================
    // CAMBIO DE CATEGORÍA
    // =====================================================

    function limpiarAtributosAutomaticosAnteriores(
        nuevaCategoriaId
    ) {
        document.querySelectorAll(
            "#atributosContainer .atributo-form"
        ).forEach(function (fila) {
            if (
                fila.dataset.sugerido !== "1"
                || !fila.dataset.categoriaSugerida
                || String(fila.dataset.categoriaSugerida)
                    === String(nuevaCategoriaId)
            ) {
                return;
            }

            const valor = fila.querySelector(
                'input[name$="-valor"]'
            );

            // Si el usuario ya escribió un valor,
            // conservamos la fila.
            if (valor?.value?.trim()) {
                delete fila.dataset.sugerido;
                delete fila.dataset.categoriaSugerida;
                return;
            }

            const deleteInput = fila.querySelector(
                'input[type="checkbox"][name$="-DELETE"]'
            );

            // No eliminamos físicamente la fila porque pertenece
            // a un formset de Django. La marcamos DELETE.
            if (deleteInput) {
                deleteInput.checked = true;
                fila.style.display = "none";
            }
        });
    }


    // =====================================================
    // PANEL
    // =====================================================

    function mostrarPanelAnalizando() {
        const panel = document.getElementById(
            "motorSugerencias"
        );

        const estado = document.getElementById(
            "motorSugerenciasEstado"
        );

        const contenido = document.getElementById(
            "motorSugerenciasContenido"
        );

        if (!panel) return;

        panel.hidden = false;

        if (estado) {
            estado.textContent = "Analizando producto...";
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


    function renderizarResultado(resultado) {
        const panel = document.getElementById(
            "motorSugerencias"
        );

        const estado = document.getElementById(
            "motorSugerenciasEstado"
        );

        const contenido = document.getElementById(
            "motorSugerenciasContenido"
        );

        if (!panel || !contenido) return;

        const categorias = Array.isArray(
            resultado.categorias
        )
            ? resultado.categorias
            : [];

        const productos = Array.isArray(
            resultado.productos
        )
            ? resultado.productos
            : [];

        if (!categorias.length && !productos.length) {
            panel.hidden = false;

            if (estado) {
                estado.textContent = (
                    "Sin coincidencias suficientes"
                );
            }

            contenido.innerHTML = `
                <div class="motor-sugerencia-bloque">
                    <div class="motor-sugerencia-valor">
                        No encontré un producto existente con
                        suficiente confianza. Puede continuar
                        creando una referencia nueva.
                    </div>
                </div>
            `;

            return;
        }

        panel.hidden = false;

        if (estado) {
            estado.textContent = resultado.hay_codigo_exacto
                ? "Código encontrado en el catálogo"
                : "Resultados encontrados";
        }

        let html = "";

        if (categorias.length) {
            const categoria = categorias[0];

            html += `
                <div class="motor-sugerencia-bloque">
                    <div class="motor-sugerencia-label">
                        Categoría sugerida
                    </div>

                    <div class="motor-sugerencia-valor">
                        ${escaparHTML(categoria.nombre || "")}

                        <span class="motor-confianza">
                            ${formatearConfianza(categoria.confianza)}
                        </span>

                        <button
                            type="button"
                            class="btn-login"
                            data-motor-accion="categoria"
                            data-categoria-id="${escaparAtributo(categoria.id)}"
                            data-categoria-nombre="${escaparAtributo(categoria.nombre || "")}"
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

        if (productos.length) {
            html += `
                <div class="motor-sugerencia-bloque">

                    <div class="motor-sugerencia-label">
                        Posibles productos existentes
                    </div>
            `;

            productos.slice(0, 3).forEach(function (producto) {
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
                                    producto.sku || ""
                                )}

                                ${producto.marca
                                    ? ` · ${escaparHTML(producto.marca)}`
                                    : ""
                                }

                                ${producto.codigo
                                    ? ` · ${escaparHTML(producto.codigo)}`
                                    : ""
                                }
                            </div>
                        </div>

                        <div style="
                            display:flex;
                            align-items:center;
                            gap:6px;
                            flex-shrink:0;
                        ">

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
                                        data-marca-id="${escaparAtributo(producto.marca_id)}"
                                        data-marca-nombre="${escaparAtributo(producto.marca || "")}"
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
            });

            html += `</div>`;
        }

        contenido.innerHTML = html;
    }


    function mostrarErrorMotor(mensaje) {
        const panel = document.getElementById(
            "motorSugerencias"
        );

        const estado = document.getElementById(
            "motorSugerenciasEstado"
        );

        const contenido = document.getElementById(
            "motorSugerenciasContenido"
        );

        if (!panel) return;

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


    function ocultarPanel() {
        const panel = document.getElementById(
            "motorSugerencias"
        );

        if (panel) {
            panel.hidden = true;
        }
    }


    function conectarCerrarPanel() {
        const boton = document.getElementById(
            "cerrarMotorSugerencias"
        );

        if (!boton) return;

        boton.addEventListener(
            "click",
            ocultarPanel
        );
    }


    // =====================================================
    // ACCIONES DEL PANEL
    // =====================================================

    function manejarAccionSugerencia(event) {
        const boton = event.target.closest(
            "[data-motor-accion]"
        );

        if (!boton) return;

        const accion = boton.dataset.motorAccion;

        if (accion === "categoria") {
            aplicarCategoriaForzada(
                boton.dataset.categoriaId,
                boton.dataset.categoriaNombre
            );

            return;
        }

        if (accion === "marca") {
            aplicarMarcaForzada(
                boton.dataset.marcaId,
                boton.dataset.marcaNombre
            );
        }
    }


    // =====================================================
    // TEXTO QUE SE GUARDARÁ PARA APRENDIZAJE
    // =====================================================

    function guardarTextoAprendizaje(texto) {
        const input = document.getElementById(
            "textoAprendizaje"
        );

        if (!input) return;

        input.value = String(texto || "").trim();
    }


    // =====================================================
    // FILAS DE CÓDIGOS
    // =====================================================

    function obtenerPrimeraFilaCodigoVisible() {
        return Array.from(
            document.querySelectorAll(
                "#codigosContainer .codigo-form, .codigo-form"
            )
        ).find(function (fila) {
            if (fila.style.display === "none") {
                return false;
            }

            const deleteInput = fila.querySelector(
                'input[type="checkbox"][name$="-DELETE"]'
            );

            return !deleteInput?.checked;
        }) || null;
    }


    // =====================================================
    // SEGURIDAD HTML
    // =====================================================

    function escaparHTML(valor) {
        return String(valor ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }


    function escaparAtributo(valor) {
        return escaparHTML(valor);
    }


    function formatearConfianza(valor) {
        const numero = Number(valor || 0);

        if (!Number.isFinite(numero)) {
            return "0%";
        }

        return `${Math.round(numero)}%`;
    }


    // =====================================================
    // EXPORTAR ALGUNAS FUNCIONES
    // =====================================================

    window.MAOSugerencias = {
        analizar: analizarFormulario,
        cargarAtributosCategoria,
        aplicarCategoria: aplicarCategoriaForzada,
        aplicarMarca: aplicarMarcaForzada,
    };


    // =====================================================
    // ARRANQUE
    // =====================================================

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            inicializarSugerencias
        );
    } else {
        inicializarSugerencias();
    }

})();