let inputActivoBusqueda = null;
let timeoutBusquedaProducto = null;

let PUEDE_EDITAR_OT = false;


function actualizarPermisoEdicionOT() {
    const wrapper =
        document.querySelector(
            '.ot-wrapper'
        );

    const valor =
        String(
            wrapper?.dataset
                ?.puedeEditar || ''
        )
            .trim()
            .toLowerCase();

    PUEDE_EDITAR_OT =
        valor === 'true' ||
        valor === '1';
}


actualizarPermisoEdicionOT();

if (
    document.readyState ===
    'loading'
) {
    document.addEventListener(
        'DOMContentLoaded',
        actualizarPermisoEdicionOT
    );
}

const floatingDropdown =
    document.getElementById(
        'productoFloatingDropdown'
    );


// =====================================================
// ESCAPAR HTML
// =====================================================
function escaparHtml(valor) {
    return String(
        valor ?? ''
    )
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}


// =====================================================
// AGREGAR FILA REPUESTO
// =====================================================
function agregarFilaRepuesto(
    enfocar = false
) {
    if (!PUEDE_EDITAR_OT) {
        return;
    }

    const tbody =
        document.querySelector(
            '#tablaRepuestos tbody'
        );

    if (!tbody) {
        return;
    }

    const filaHtml = `
        <tr class="fila-repuesto">
            <td class="producto-cell">
                <input
                    type="hidden"
                    name="rep_detalle_id[]"
                    value=""
                >

                <input
                    type="hidden"
                    name="rep_delete[]"
                    value="0"
                >
                <input
                    type="hidden"
                    name="rep_marcado[]"
                    class="rep-marcado-input"
                    value="0"
                >
                <input
                    type="hidden"
                    name="rep_actualizado_en[]"
                    value=""
                >

                <input
                    type="hidden"
                    name="rep_producto_id[]"
                    class="producto-id-hidden"
                    value=""
                >

                <input
                    type="hidden"
                    name="rep_categoria_id[]"
                    value=""
                >

                <input
                    type="hidden"
                    name="rep_codigo_barras[]"
                    value=""
                >

                <input
                    type="hidden"
                    name="rep_codigo_empaque[]"
                    value=""
                >

                <div class="producto-busqueda-wrap">
                    <input
                        type="text"
                        class="
                            form-control-apple
                            producto-busqueda-input
                        "
                        placeholder="
                            Código / barras / nombre
                        "
                        autocomplete="off"
                        oninput="
                            buscarProductoEnFila(this)
                        "
                        onkeydown="
                            manejarTeclaBusquedaProducto(
                                event,
                                this
                            )
                        "
                        onfocus="
                            buscarProductoEnFila(this)
                        "
                    >
                </div>
            </td>

            <td>
                <input
                    type="text"
                    name="rep_descripcion[]"
                    class="
                        form-control-apple
                        descripcion-manual
                    "
                    placeholder="
                        Descripción del repuesto
                    "
                >
            </td>

            <td>
                <div class="stock-chip stock-view">
                    0
                </div>
            </td>

            <td>
                <input
                    type="text"
                    inputmode="decimal"
                    name="rep_pu[]"
                    class="form-control-apple pu"
                    value="0.00"
                    oninput="
                        calcularFila(this)
                    "
                >
            </td>

            <td>
                <input
                    type="text"
                    inputmode="decimal"
                    name="rep_cantidad[]"
                    class="
                        form-control-apple
                        cantidad
                    "
                    value="1.00"
                    oninput="
                        calcularFila(this)
                    "
                >
            </td>

            <td>
                <input
                    type="text"
                    inputmode="decimal"
                    name="rep_valor[]"
                    class="
                        form-control-apple
                        valor
                    "
                    value="0.00"
                    readonly
                >
            </td>

            <td>
                <div class="row-controls">
                    <div class="row-controls">

                        <button
                            type="button"
                            class="repuesto-marcar-btn"
                            onclick="marcarRepuesto(this)"
                            title="Marcar repuesto"
                            aria-label="Marcar repuesto"
                        >
                            ✓
                        </button>

                        <button
                            type="button"
                            class="repuesto-drag-handle"
                            draggable="true"
                            title="Mantén presionado y arrastra"
                            aria-label="Mover repuesto"
                        >
                            ⠿
                        </button>

                        <button
                            type="button"
                            class="
                                btn-login
                                danger
                                small
                            "
                            onclick="
                                eliminarFilaRepuesto(this)
                            "
                            title="Quitar"
                        >
                            ✕
                        </button>

                    </div>
                </div>
            </td>
        </tr>
    `;

    tbody.insertAdjacentHTML(
        'beforeend',
        filaHtml
    );

    if (
        typeof recalcularTotales ===
        'function'
    ) {
        recalcularTotales();
    }

    if (!enfocar) {
        return;
    }

    setTimeout(function () {
        const filas =
            tbody.querySelectorAll(
                'tr:not(.fila-eliminada)'
            );

        const ultimaFila =
            filas[
                filas.length - 1
            ];

        const input =
            ultimaFila?.querySelector(
                '.producto-busqueda-input'
            );

        if (input) {
            input.focus();
        }
    }, 50);
}


// =====================================================
// ELIMINAR FILA REPUESTO
// =====================================================
function eliminarFilaRepuesto(
    boton
) {
    if (!PUEDE_EDITAR_OT) {
        return;
    }

    const fila =
        boton?.closest('tr');

    if (!fila) {
        return;
    }

    const detalleId =
        fila.querySelector(
            'input[name="rep_detalle_id[]"]'
        );

    const deleteInput =
        fila.querySelector(
            'input[name="rep_delete[]"]'
        );

    const registroGuardado =
        Boolean(
            detalleId &&
            String(
                detalleId.value || ''
            ).trim()
        );

    if (registroGuardado) {
        /*
         * La fila ya existe en la base de datos.
         * Se mantiene en el formulario para que
         * el backend reciba rep_delete[]=1.
         */
        if (deleteInput) {
            deleteInput.value = '1';
        }

        fila.classList.add(
            'fila-eliminada'
        );

        fila.dataset.eliminada = '1';
        fila.hidden = true;
        fila.style.display = 'none';
    } else {
        /*
         * La fila todavía no existe en la base
         * de datos y puede retirarse del DOM.
         */
        fila.remove();
    }

    ocultarDropdownFlotante();

    if (
        typeof recalcularTotales ===
        'function'
    ) {
        recalcularTotales();
    }

    if (
        typeof mostrarEstadoDescuento ===
        'function'
    ) {
        mostrarEstadoDescuento();
    }
}


// =====================================================
// BUSCAR PRODUCTO
// =====================================================
async function buscarProductoEnFila(
    input
) {
    if (!PUEDE_EDITAR_OT) {
        return;
    }

    const texto = String(
        input?.value || ''
    ).trim();

    if (texto.length < 2) {
        ocultarDropdownFlotante();
        return;
    }

    inputActivoBusqueda = input;

    posicionarDropdownFlotante(
        input
    );

    clearTimeout(
        timeoutBusquedaProducto
    );

    timeoutBusquedaProducto =
        setTimeout(
            async function () {
                await ejecutarBusquedaProducto(
                    texto
                );
            },
            250
        );
}


// =====================================================
// EJECUTAR BÚSQUEDA
// =====================================================
async function ejecutarBusquedaProducto(
    texto
) {
    try {
        const response = await fetch(
            `/api/buscar-repuestos?q=${
                encodeURIComponent(texto)
            }`
        );

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        const data =
            await response.json();

        const resultados =
            Array.isArray(
                data.resultados
            )
                ? data.resultados
                : [];

        if (
            resultados.length === 0
        ) {
            mostrarSinResultados();
            return;
        }

        const primerResultado =
            resultados[0];

        if (
            primerResultado
                ?.match_exacto === true
        ) {
            seleccionarProductoEnFilaDesdeObjeto(
                primerResultado
            );

            agregarFilaRepuesto(
                true
            );

            return;
        }

        renderDropdownFlotante(
            inputActivoBusqueda,
            resultados
        );
    } catch (error) {
        console.error(
            'Error buscando productos:',
            error
        );

        ocultarDropdownFlotante();
    }
}


// =====================================================
// MOSTRAR SIN RESULTADOS
// =====================================================
function mostrarSinResultados() {
    if (!floatingDropdown) {
        return;
    }

    floatingDropdown.innerHTML = `
        <div class="sin-resultados">
            Sin coincidencias en inventario
        </div>
    `;

    floatingDropdown.style.display =
        'block';
}


// =====================================================
// RENDER DROPDOWN
// =====================================================
function renderDropdownFlotante(
    input,
    resultados
) {
    if (!PUEDE_EDITAR_OT) {
        return;
    }

    if (
        !floatingDropdown ||
        !input ||
        !Array.isArray(resultados)
    ) {
        return;
    }

    inputActivoBusqueda = input;

    floatingDropdown.innerHTML =
        resultados
            .map(function (
                item,
                index
            ) {
                const precio =
                    item.precio_venta ||
                    item.p_u ||
                    '0.00';

                const itemSeguro =
                    escaparHtml(
                        JSON.stringify(
                            item
                        )
                    );

                const claseActiva =
                    index === 0
                        ? 'active'
                        : '';

                return `
                    <div
                        class="
                            producto-sugerencia-item
                            ${claseActiva}
                        "
                        data-item="${itemSeguro}"
                        onclick="
                            seleccionarProductoEnFilaDesdeObjeto(
                                JSON.parse(
                                    this.dataset.item
                                )
                            )
                        "
                    >
                        <div
                            class="
                                producto-sugerencia-codigo
                            "
                        >
                            ${escaparHtml(
                                item.codigo || ''
                            )}
                        </div>

                        <div
                            class="
                                producto-sugerencia-extra
                            "
                        >
                            ${escaparHtml(
                                item.descripcion || ''
                            )}
                            ·
                            <strong>
                                Stock:
                                ${escaparHtml(
                                    item.stock || 0
                                )}
                            </strong>
                            ·
                            $${escaparHtml(
                                precio
                            )}
                        </div>
                    </div>
                `;
            })
            .join('');

    floatingDropdown.style.display =
        'block';
}


// =====================================================
// SELECCIONAR PRODUCTO
// =====================================================
function seleccionarProductoEnFilaDesdeObjeto(
    item
) {
    if (!PUEDE_EDITAR_OT) {
        return;
    }

    if (
        !inputActivoBusqueda ||
        !item
    ) {
        return;
    }

    const fila =
        inputActivoBusqueda.closest(
            'tr'
        );

    if (!fila) {
        return;
    }

    const precio =
        item.precio_venta ||
        item.p_u ||
        0;

    const descripcion =
        item.descripcion || '';

    const codigo =
        item.codigo || '';

    const productoId =
        fila.querySelector(
            '.producto-id-hidden'
        );

    const inputBusqueda =
        fila.querySelector(
            '.producto-busqueda-input'
        );

    const descripcionInput =
        fila.querySelector(
            '.descripcion-manual'
        );

    const precioInput =
        fila.querySelector(
            '.pu'
        );

    const stockView =
        fila.querySelector(
            '.stock-view'
        );

    const categoriaInput =
        fila.querySelector(
            'input[name="rep_categoria_id[]"]'
        );

    const codigoBarrasInput =
        fila.querySelector(
            'input[name="rep_codigo_barras[]"]'
        );

    const codigoEmpaqueInput =
        fila.querySelector(
            'input[name="rep_codigo_empaque[]"]'
        );

    if (productoId) {
        productoId.value =
            item.id || '';
    }

    if (categoriaInput) {
        categoriaInput.value =
            item.categoria_id || '';
    }

    if (codigoBarrasInput) {
        codigoBarrasInput.value =
            item.codigo_barras || '';
    }

    if (codigoEmpaqueInput) {
        codigoEmpaqueInput.value =
            item.codigo_empaque || '';
    }

    if (inputBusqueda) {
        const descripcionCorta =
            descripcion.includes('-')
                ? descripcion
                    .split('-')[0]
                    .trim()
                : descripcion;

        inputBusqueda.value =
            `${codigo} - ${descripcionCorta}`
                .trim();
    }

    if (descripcionInput) {
        descripcionInput.value =
            descripcion;
    }

    if (precioInput) {
        precioInput.value =
            Number(
                precio || 0
            ).toFixed(2);
    }

    if (stockView) {
        stockView.textContent =
            item.stock ?? 0;
    }

    ocultarDropdownFlotante();

    if (
        typeof recalcularFilaDesdeTr ===
        'function'
    ) {
        recalcularFilaDesdeTr(
            fila
        );
    }

    if (
        typeof recalcularTotales ===
        'function'
    ) {
        recalcularTotales();
    }
}


// =====================================================
// MANEJO DE TECLADO
// =====================================================
function manejarTeclaBusquedaProducto(
    event,
    input
) {
    if (!PUEDE_EDITAR_OT) {
        return;
    }

    if (!floatingDropdown) {
        return;
    }

    const items = Array.from(
        floatingDropdown.querySelectorAll(
            '.producto-sugerencia-item'
        )
    );

    if (event.key === 'Enter') {
        event.preventDefault();

        const dropdownVisible =
            floatingDropdown
                .style
                .display === 'block';

        if (
            items.length > 0 &&
            dropdownVisible
        ) {
            const itemActivo =
                items.find(function (
                    item
                ) {
                    return item.classList
                        .contains(
                            'active'
                        );
                }) ||
                items[0];

            if (itemActivo) {
                seleccionarProductoEnFilaDesdeObjeto(
                    JSON.parse(
                        itemActivo
                            .dataset
                            .item
                    )
                );

                agregarFilaRepuesto(
                    true
                );
            }
        }

        return;
    }

    const dropdownVisible =
        floatingDropdown
            .style
            .display === 'block';

    if (
        items.length === 0 ||
        !dropdownVisible
    ) {
        return;
    }

    let indiceActivo =
        items.findIndex(
            function (item) {
                return item.classList
                    .contains(
                        'active'
                    );
            }
        );

    if (indiceActivo < 0) {
        indiceActivo = 0;
    }

    if (
        event.key ===
        'ArrowDown'
    ) {
        event.preventDefault();

        items[
            indiceActivo
        ]?.classList.remove(
            'active'
        );

        indiceActivo = (
            indiceActivo + 1
        ) % items.length;

        items[
            indiceActivo
        ].classList.add(
            'active'
        );

        items[
            indiceActivo
        ].scrollIntoView({
            block: 'nearest'
        });

        return;
    }

    if (
        event.key ===
        'ArrowUp'
    ) {
        event.preventDefault();

        items[
            indiceActivo
        ]?.classList.remove(
            'active'
        );

        indiceActivo = (
            indiceActivo -
            1 +
            items.length
        ) % items.length;

        items[
            indiceActivo
        ].classList.add(
            'active'
        );

        items[
            indiceActivo
        ].scrollIntoView({
            block: 'nearest'
        });

        return;
    }

    if (
        event.key ===
        'Escape'
    ) {
        ocultarDropdownFlotante();
    }
}


// =====================================================
// OCULTAR DROPDOWN
// =====================================================
function ocultarDropdownFlotante() {
    if (!floatingDropdown) {
        return;
    }

    floatingDropdown.style.display =
        'none';

    floatingDropdown.innerHTML =
        '';
}


// =====================================================
// POSICIONAR DROPDOWN
// =====================================================
function posicionarDropdownFlotante(
    input
) {
    if (!PUEDE_EDITAR_OT) {
        return;
    }

    if (
        !floatingDropdown ||
        !input
    ) {
        return;
    }

    const rect =
        input.getBoundingClientRect();

    floatingDropdown.style.top =
        `${rect.bottom + 4}px`;

    floatingDropdown.style.left =
        `${rect.left}px`;

    floatingDropdown.style.width =
        `${rect.width}px`;
}


// =====================================================
// CLICK GLOBAL
// =====================================================
document.addEventListener(
    'click',
    function (event) {
        if (
            !floatingDropdown
        ) {
            return;
        }

        const clicEnDropdown =
            floatingDropdown.contains(
                event.target
            );

        const clicEnInput =
            event.target
                .classList
                ?.contains(
                    'producto-busqueda-input'
                );

        if (
            !clicEnDropdown &&
            !clicEnInput
        ) {
            ocultarDropdownFlotante();
        }
    }
);


// =====================================================
// REDIMENSIONAMIENTO
// =====================================================
window.addEventListener(
    'resize',
    function () {
        if (
            inputActivoBusqueda &&
            floatingDropdown &&
            floatingDropdown
                .style
                .display === 'block'
        ) {
            posicionarDropdownFlotante(
                inputActivoBusqueda
            );
        }
    }
);


// =====================================================
// SCROLL
// =====================================================
window.addEventListener(
    'scroll',
    function () {
        if (
            !inputActivoBusqueda ||
            !floatingDropdown ||
            floatingDropdown
                .style
                .display !== 'block'
        ) {
            return;
        }

        posicionarDropdownFlotante(
            inputActivoBusqueda
        );

        const rect =
            inputActivoBusqueda
                .getBoundingClientRect();

        if (
            rect.bottom < 0 ||
            rect.top >
                window.innerHeight
        ) {
            ocultarDropdownFlotante();
        }
    },
    true
);