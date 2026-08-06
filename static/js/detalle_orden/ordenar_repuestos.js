
// =====================================================
// ORDENAR REPUESTOS ARRASTRANDO FILAS
// =====================================================
let filaRepuestoArrastrada = null;
let filaRepuestoPreparada = null;


// =====================================================
// VALIDAR FILA ORDENABLE
// =====================================================
function esFilaRepuestoOrdenable(
    fila
) {
    if (!fila) {
        return false;
    }

    if (
        fila.classList.contains(
            'form-readonly'
        )
    ) {
        return false;
    }

    if (
        fila.classList.contains(
            'fila-eliminada'
        )
    ) {
        return false;
    }

    if (
        fila.dataset.eliminada === '1'
    ) {
        return false;
    }

    return Boolean(
        fila.querySelector(
            '.repuesto-drag-handle'
        )
    );
}


// =====================================================
// LIMPIAR ARRASTRE
// =====================================================
function finalizarArrastreRepuesto() {
    if (filaRepuestoArrastrada) {
        filaRepuestoArrastrada
            .classList
            .remove(
                'repuesto-arrastrando'
            );

        filaRepuestoArrastrada
            .removeAttribute(
                'draggable'
            );
    }

    if (
        filaRepuestoPreparada &&
        filaRepuestoPreparada !==
            filaRepuestoArrastrada
    ) {
        filaRepuestoPreparada
            .removeAttribute(
                'draggable'
            );
    }

    filaRepuestoArrastrada = null;
    filaRepuestoPreparada = null;

    document.body.classList.remove(
        'ordenando-repuestos'
    );
}


// =====================================================
// INICIALIZAR ORDENAMIENTO
// =====================================================
function inicializarOrdenamientoRepuestos() {
    actualizarPermisoEdicionOT();

    if (!PUEDE_EDITAR_OT) {
        return;
    }

    const tbody =
        document.getElementById(
            'cuerpoTablaRepuestos'
        );

    if (!tbody) {
        return;
    }

    if (
        tbody.dataset
            .ordenamientoInicializado ===
        '1'
    ) {
        return;
    }

    tbody.dataset
        .ordenamientoInicializado = '1';


    // =============================================
    // PREPARAR FILA AL PRESIONAR EL ASA
    // =============================================
    tbody.addEventListener(
        'pointerdown',
        function (event) {
            const asa =
                event.target.closest(
                    '.repuesto-drag-handle'
                );

            if (!asa) {
                return;
            }

            const fila =
                asa.closest('tr');

            if (
                !esFilaRepuestoOrdenable(
                    fila
                )
            ) {
                return;
            }

            /*
             * El botón no se arrastra.
             * Se arrastra la fila completa.
             */
            asa.draggable = false;

            filaRepuestoPreparada =
                fila;

            fila.setAttribute(
                'draggable',
                'true'
            );

            ocultarDropdownFlotante();
        }
    );


    // =============================================
    // INICIAR ARRASTRE
    // =============================================
    tbody.addEventListener(
        'dragstart',
        function (event) {
            const fila =
                event.target.closest(
                    'tr'
                );

            if (
                !fila ||
                fila !==
                    filaRepuestoPreparada ||
                !esFilaRepuestoOrdenable(
                    fila
                )
            ) {
                event.preventDefault();
                return;
            }

            filaRepuestoArrastrada =
                fila;

            fila.classList.add(
                'repuesto-arrastrando'
            );

            document.body.classList.add(
                'ordenando-repuestos'
            );

            ocultarDropdownFlotante();

            if (event.dataTransfer) {
                event.dataTransfer
                    .effectAllowed =
                    'move';

                event.dataTransfer.setData(
                    'text/plain',
                    'reordenar-repuesto'
                );
            }
        }
    );


    // =============================================
    // MOVER FILA
    // =============================================
    tbody.addEventListener(
        'dragover',
        function (event) {
            if (
                !filaRepuestoArrastrada
            ) {
                return;
            }

            event.preventDefault();

            if (event.dataTransfer) {
                event.dataTransfer
                    .dropEffect =
                    'move';
            }

            const filaObjetivo =
                event.target.closest(
                    'tr'
                );

            if (
                !esFilaRepuestoOrdenable(
                    filaObjetivo
                )
            ) {
                return;
            }

            if (
                filaObjetivo ===
                filaRepuestoArrastrada
            ) {
                return;
            }

            const rect =
                filaObjetivo
                    .getBoundingClientRect();

            const mitad =
                rect.top +
                rect.height / 2;

            const colocarDespues =
                event.clientY > mitad;

            if (colocarDespues) {
                const siguiente =
                    filaObjetivo
                        .nextElementSibling;

                if (
                    siguiente ===
                    filaRepuestoArrastrada
                ) {
                    return;
                }

                tbody.insertBefore(
                    filaRepuestoArrastrada,
                    siguiente
                );
            } else {
                const anterior =
                    filaObjetivo
                        .previousElementSibling;

                if (
                    anterior ===
                    filaRepuestoArrastrada
                ) {
                    return;
                }

                tbody.insertBefore(
                    filaRepuestoArrastrada,
                    filaObjetivo
                );
            }
        }
    );


    // =============================================
    // SOLTAR FILA
    // =============================================
    tbody.addEventListener(
        'drop',
        function (event) {
            if (
                !filaRepuestoArrastrada
            ) {
                return;
            }

            event.preventDefault();

            finalizarArrastreRepuesto();
        }
    );


    // =============================================
    // TERMINAR ARRASTRE
    // =============================================
    tbody.addEventListener(
        'dragend',
        function () {
            finalizarArrastreRepuesto();
        }
    );


    // =============================================
    // CANCELAR SI SOLO SE HIZO CLIC
    // =============================================
    document.addEventListener(
        'pointerup',
        function () {
            if (
                filaRepuestoPreparada &&
                !filaRepuestoArrastrada
            ) {
                filaRepuestoPreparada
                    .removeAttribute(
                        'draggable'
                    );

                filaRepuestoPreparada =
                    null;
            }
        }
    );


    
}


// =====================================================
// EJECUTAR INICIALIZACIÓN
// =====================================================
if (
    document.readyState ===
    'loading'
) {
    document.addEventListener(
        'DOMContentLoaded',
        inicializarOrdenamientoRepuestos
    );
} else {
    inicializarOrdenamientoRepuestos();
}