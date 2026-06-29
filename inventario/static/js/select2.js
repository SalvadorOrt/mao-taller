// ======================================================
// SELECT2
// ======================================================

"use strict";

/*
    Inicializa todos los Select2 dentro de un contenedor.

    Ejemplo:

    inicializarSelect2(document);

    inicializarSelect2(nuevaFila);
*/

function inicializarSelect2(contenedor = document) {

    if (typeof $ === "undefined") {
        console.warn("jQuery no está cargado.");
        return;
    }

    if (typeof $.fn.select2 === "undefined") {
        console.warn("Select2 no está cargado.");
        return;
    }

    $(contenedor)
        .find("select.select2")
        .each(function () {

            // Evitar inicializar dos veces
            if ($(this).hasClass("select2-hidden-accessible")) {
                return;
            }

            $(this).select2({

                width: "100%",

                language: {

                    noResults: function () {
                        return "Sin resultados";
                    },

                    searching: function () {
                        return "Buscando...";
                    }

                }

            });

        });

}


/*
    Destruye todos los select2 de un contenedor.

    Útil antes de eliminar filas dinámicas.
*/

function destruirSelect2(contenedor = document) {

    if (typeof $ === "undefined") {
        return;
    }

    if (typeof $.fn.select2 === "undefined") {
        return;
    }

    $(contenedor)
        .find("select.select2")
        .each(function () {

            if ($(this).hasClass("select2-hidden-accessible")) {

                $(this).select2("destroy");

            }

        });

}


/*
    Reinicializa Select2.

    Muy útil cuando agregas un nuevo código
    o un nuevo atributo.
*/

function reinicializarSelect2(contenedor = document) {

    destruirSelect2(contenedor);

    inicializarSelect2(contenedor);

}


/*
    Agrega una opción a un select y opcionalmente
    la deja seleccionada.
*/

function agregarOpcionSelect(
    select,
    value,
    texto,
    seleccionar = false
) {

    if (!select) {
        return;
    }

    let existe = false;

    Array.from(select.options).forEach(function (opcion) {

        if (String(opcion.value) === String(value)) {

            existe = true;

        }

    });

    if (!existe) {

        const opcion = new Option(
            texto,
            value,
            seleccionar,
            seleccionar
        );

        select.add(opcion);

    }

    if (seleccionar) {

        select.value = value;

    }

    if (typeof $ !== "undefined") {

        $(select).trigger("change");

    }

}


/*
    Abre automáticamente el buscador
    cuando el usuario recibe foco.

    Hace que el combobox se comporte
    como el del sistema de órdenes.
*/

$(document).on(
    "focus",
    ".select2-selection",
    function () {

        $(this)
            .closest(".select2-container")
            .siblings("select.select2")
            .select2("open");

    }
);


/*
    Si agregamos filas dinámicamente,
    volveremos a llamar a:

        inicializarSelect2(nuevaFila);

    No es necesario volver a inicializar
    todo el documento.
*/