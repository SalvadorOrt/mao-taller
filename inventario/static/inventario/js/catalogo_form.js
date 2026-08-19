// =========================================================
// CONFIG GENERAL - CATÁLOGO INVENTARIO
// =========================================================

document.addEventListener(
    "DOMContentLoaded",
    function () {
        inicializarCatalogoForm();
    }
);


// =========================================================
// INICIALIZACIÓN
// =========================================================

function inicializarCatalogoForm() {

    const form = (
        document.getElementById(
            "catalogoForm"
        )
    );

    if (!form) {
        return;
    }


    // =====================================================
    // DROPDOWNS
    // =====================================================

    if (
        typeof inicializarDropdownsApple
        === "function"
    ) {

        inicializarDropdownsApple();
    }


    // =====================================================
    // IMÁGENES
    // =====================================================

    if (
        typeof inicializarImagenes
        === "function"
    ) {

        inicializarImagenes(
            document
        );
    }


    // =====================================================
    // PRECIO SECRETO
    // =====================================================

    inicializarPrecioSecreto(
        form
    );
}


// =========================================================
// PRECIO SECRETO
// =========================================================

function inicializarPrecioSecreto(
    contexto = document
) {

    // =====================================================
    // CALCULAR VALORES INICIALES
    // =====================================================

    contexto
        .querySelectorAll(
            ".codigo-form"
        )
        .forEach(
            function (fila) {

                actualizarPrecioSecretoFila(
                    fila
                );
            }
        );


    // =====================================================
    // EVITAR LISTENER DUPLICADO
    // =====================================================

    if (
        contexto.dataset
        ?.precioSecretoInicializado
        === "1"
    ) {

        return;
    }


    if (
        contexto.dataset
    ) {

        contexto.dataset
            .precioSecretoInicializado = (
                "1"
            );
    }


    // =====================================================
    // DELEGACIÓN DE EVENTOS
    // =====================================================
    //
    // También funciona con códigos agregados
    // dinámicamente después.
    //
    // =====================================================

    contexto.addEventListener(
        "input",
        function (event) {

            const input = (
                event.target
            );


            if (
                !input.classList.contains(
                    "precio-venta-input"
                )
            ) {

                return;
            }


            const fila = (
                input.closest(
                    ".codigo-form"
                )
            );


            if (!fila) {
                return;
            }


            actualizarPrecioSecretoFila(
                fila
            );
        }
    );
}


// =========================================================
// ACTUALIZAR PRECIO SECRETO DE UNA FILA
// =========================================================

function actualizarPrecioSecretoFila(
    fila
) {

    if (!fila) {
        return;
    }


    const precioVentaInput = (
        fila.querySelector(
            ".precio-venta-input"
        )
    );


    const precioSecretoInput = (
        fila.querySelector(
            ".precio-secreto-input"
        )
    );


    if (
        !precioVentaInput
        || !precioSecretoInput
    ) {

        return;
    }


    precioSecretoInput.value = (
        convertirPrecioSecreto(
            precioVentaInput.value
        )
    );
}


// =========================================================
// CONVERTIR PRECIO A CÓDIGO SECRETO
// =========================================================

function convertirPrecioSecreto(
    valor
) {

    if (
        valor === null
        || valor === undefined
        || String(
            valor
        ).trim() === ""
    ) {

        return "---";
    }


    const numero = (
        parseFloat(
            String(
                valor
            )
                .trim()
                .replace(
                    ",",
                    "."
                )
        )
    );


    if (
        !Number.isFinite(
            numero
        )
    ) {

        return "---";
    }


    const clave = {

        "1": "M",
        "2": "E",
        "3": "C",
        "4": "A",
        "5": "N",
        "6": "I",
        "7": "O",
        "8": "R",
        "9": "T",
        "0": "S",

        ".": ".",
    };


    return (
        numero
            .toFixed(2)
            .split("")
            .map(
                function (
                    caracter
                ) {

                    return (
                        clave[
                            caracter
                        ]
                        || caracter
                    );
                }
            )
            .join("")
    );
}


// =========================================================
// VALIDAR CLASIFICACIÓN
// =========================================================

function validarClasificacionProducto(
    form
) {

    if (!form) {
        return false;
    }


    const categoriaHidden = (
        form.querySelector(
            '.apple-dropdown'
            + '[data-dropdown-tipo="categoria"] '
            + '.apple-dropdown-hidden'
        )
    );


    const categoriaVisible = (
        form.querySelector(
            '.apple-dropdown'
            + '[data-dropdown-tipo="categoria"] '
            + '.apple-dropdown-input'
        )
    );


    const categoriaId = (
        String(
            categoriaHidden
                ?.value
            || ""
        ).trim()
    );


    // =====================================================
    // CATEGORÍA OBLIGATORIA
    // =====================================================

    if (!categoriaId) {

        if (
            categoriaVisible
        ) {

            categoriaVisible.style.borderColor = (
                "var(--danger)"
            );


            categoriaVisible.focus();
        }


        alert(
            "Seleccione una categoría válida para el repuesto."
        );


        return false;
    }


    if (
        categoriaVisible
    ) {

        categoriaVisible.style.borderColor = "";
    }


    return true;
}


// =========================================================
// VALIDACIÓN GENERAL ANTES DE ENVIAR
// =========================================================

document.addEventListener(
    "submit",
    function (event) {

        const form = (
            event.target
        );


        if (
            !form
            || form.id
                !== "catalogoForm"
        ) {

            return;
        }


        // =================================================
        // CLASIFICACIÓN
        // =================================================

        if (
            !validarClasificacionProducto(
                form
            )
        ) {

            event.preventDefault();

            return;
        }


        // =================================================
        // IMÁGENES
        // =================================================

        if (
            typeof validarImagenesProducto
                === "function"
            && !validarImagenesProducto()
        ) {

            event.preventDefault();

            return;
        }


        // =================================================
        // CÓDIGOS COMERCIALES
        // =================================================

        if (
            typeof validarCodigos
                === "function"
            && !validarCodigos()
        ) {

            event.preventDefault();


            alert(
                "Revise los códigos comerciales."
            );


            return;
        }


        // =================================================
        // CARACTERÍSTICAS TÉCNICAS
        // =================================================

        if (
            typeof validarAtributos
                === "function"
            && !validarAtributos()
        ) {

            event.preventDefault();


            alert(
                "Revise las características técnicas "
                + "obligatorias del repuesto."
            );


            return;
        }
    }
);


// =========================================================
// EXPORTAR
// =========================================================

window.inicializarCatalogoForm = (
    inicializarCatalogoForm
);

window.inicializarPrecioSecreto = (
    inicializarPrecioSecreto
);

window.actualizarPrecioSecretoFila = (
    actualizarPrecioSecretoFila
);

window.convertirPrecioSecreto = (
    convertirPrecioSecreto
);

window.validarClasificacionProducto = (
    validarClasificacionProducto
);