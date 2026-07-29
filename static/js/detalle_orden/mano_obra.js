const PUEDE_EDITAR_MANO_OBRA =
    document.querySelector(
        '.ot-wrapper'
    )?.dataset.puedeEditar === 'true';

let timeoutBusquedaServicio = null;


// =====================================================
// UTILIDADES
// =====================================================
function escaparHTMLManoObra(valor) {
    return String(
        valor ?? ''
    )
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}


function recalcularTotalesManoObra() {
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


function generarUidManoObra() {
    return (
        Date.now().toString() +
        Math.floor(
            Math.random() * 1000
        ).toString()
    );
}


// =====================================================
// AGREGAR FILAS
// =====================================================
function agregarFilaMOI(
    enfocar = false
) {
    if (!PUEDE_EDITAR_MANO_OBRA) {
        return;
    }

    agregarFilaSimple(
        'tablaMOI'
    );

    if (!enfocar) {
        return;
    }

    setTimeout(function () {
        const filasPadre =
            document.querySelectorAll(
                [
                    '#cuerpoTablaMOI',
                    '.fila-padre-moi',
                    ':not(.fila-eliminada)',
                    ':not(.fila-eliminada-moi)'
                ].join(' ')
            );

        const ultimaFila =
            filasPadre[
                filasPadre.length - 1
            ];

        const input =
            ultimaFila?.querySelector(
                '.servicio-busqueda-input'
            );

        if (input) {
            input.focus();
        }
    }, 50);
}


function agregarFilaMOE(
    enfocar = false
) {
    if (!PUEDE_EDITAR_MANO_OBRA) {
        return;
    }

    agregarFilaSimple(
        'tablaMOE'
    );

    if (!enfocar) {
        return;
    }

    setTimeout(function () {
        const filas =
            document.querySelectorAll(
                [
                    '#cuerpoTablaMOE',
                    'tr',
                    ':not(.fila-eliminada)',
                    ':not(.fila-eliminada-moe)'
                ].join(' ')
            );

        const ultimaFila =
            filas[
                filas.length - 1
            ];

        const input =
            ultimaFila?.querySelector(
                '.servicio-busqueda-input'
            );

        if (input) {
            input.focus();
        }
    }, 50);
}


function agregarFilaSimple(
    idTabla
) {
    if (!PUEDE_EDITAR_MANO_OBRA) {
        return;
    }

    const tbody =
        document.querySelector(
            `#${idTabla} tbody`
        );

    if (!tbody) {
        return;
    }

    const esMOI =
        idTabla === 'tablaMOI';

    const prefijo =
        esMOI
            ? 'moi'
            : 'moe';

    const uid =
        generarUidManoObra();

    const placeholder =
        esMOI
            ? 'Buscar servicio interno...'
            : 'Buscar servicio externo...';

    const clasePadre =
        esMOI
            ? 'fila-padre-moi'
            : 'fila-padre-moe';

    const atributoUid =
        esMOI
            ? `data-uid-moi="${uid}"`
            : `data-uid-moe="${uid}"`;

    const funcionEliminar =
        esMOI
            ? 'eliminarFilaMOI(this)'
            : 'eliminarFilaMOE(this)';

    const filaPadre = `
        <tr
            class="${clasePadre}"
            ${atributoUid}
        >
            <td class="servicio-cell">
                <input
                    type="hidden"
                    name="${prefijo}_detalle_id[]"
                    value=""
                >

                <input
                    type="hidden"
                    name="${prefijo}_delete[]"
                    value="0"
                >

                <input
                    type="hidden"
                    name="${prefijo}_actualizado_en[]"
                    value=""
                >

                <input
                    type="hidden"
                    name="${prefijo}_uid[]"
                    value="${uid}"
                >

                <input
                    type="hidden"
                    name="${prefijo}_servicio_id[]"
                    class="servicio-id-hidden"
                    value=""
                >

                <div
                    class="servicio-busqueda-wrap"
                    style="position: relative;"
                >
                    <input
                        type="text"
                        class="
                            form-control-apple
                            servicio-busqueda-input
                        "
                        placeholder="${placeholder}"
                        autocomplete="off"
                        style="
                            text-align: center;
                            font-weight: 600;
                        "
                        oninput="
                            buscarServicioEnFila(
                                this,
                                '${prefijo}'
                            )
                        "
                        onfocus="
                            buscarServicioEnFila(
                                this,
                                '${prefijo}'
                            )
                        "
                    >

                    <div
                        class="
                            dropdown-resultados-servicios
                        "
                        style="
                            display: none;
                            position: absolute;
                            top: 100%;
                            left: 0;
                            right: 0;
                            background: white;
                            border: 1px solid #d2d2d7;
                            border-radius: 8px;
                            box-shadow:
                                0 4px 12px
                                rgba(0, 0, 0, 0.15);
                            z-index: 1000;
                            margin-top: 4px;
                            text-align: left;
                        "
                    >
                    </div>
                </div>
            </td>

            <td>
                <input
                    type="text"
                    name="${prefijo}_descripcion[]"
                    class="
                        form-control-apple
                        descripcion-manual
                        descripcion-${prefijo}
                        w-100
                    "
                    style="
                        font-size: 13px;
                        font-weight: 500;
                        color: #1d1d1f;
                        padding: 8px;
                    "
                    placeholder="
                        Descripción del servicio
                    "
                    value=""
                >
            </td>

            <td>
                <input
                    type="number"
                    step="0.01"
                    min="0"
                    name="${prefijo}_pu[]"
                    class="form-control-apple pu"
                    value="0.00"
                    oninput="calcularFila(this)"
                >
            </td>

            <td>
                <input
                    type="number"
                    step="0.01"
                    min="0"
                    name="${prefijo}_cantidad[]"
                    class="
                        form-control-apple
                        cantidad
                    "
                    value="1.00"
                    oninput="calcularFila(this)"
                >
            </td>

            <td>
                <input
                    type="number"
                    step="0.01"
                    name="${prefijo}_valor[]"
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
                    <button
                        type="button"
                        class="
                            btn-login
                            danger
                            small
                        "
                        onclick="${funcionEliminar}"
                        title="Quitar"
                    >
                        ✕
                    </button>
                </div>
            </td>
        </tr>
    `;

    tbody.insertAdjacentHTML(
        'beforeend',
        filaPadre
    );

    if (esMOI) {
        const filaHijas = `
            <tr
                class="fila-hijas-moi"
                data-parent-uid-moi="${uid}"
            >
                <td></td>

                <td>
                    <div
                        class="procedimientos-moi"
                        data-parent-index="${uid}"
                    >
                    </div>

                    <button
                        type="button"
                        class="btn-login small"
                        onclick="
                            agregarProcedimientoMOI(
                                this
                            )
                        "
                    >
                        + Agregar procedimiento
                    </button>
                </td>

                <td></td>
                <td></td>
                <td></td>
                <td></td>
            </tr>
        `;

        tbody.insertAdjacentHTML(
            'beforeend',
            filaHijas
        );
    }

    recalcularTotalesManoObra();
}


// =====================================================
// ELIMINAR MOI
// =====================================================
function eliminarFilaMOI(
    boton
) {
    if (!PUEDE_EDITAR_MANO_OBRA) {
        return;
    }

    const filaPadre =
        boton?.closest('tr');

    if (!filaPadre) {
        return;
    }

    const uid =
        filaPadre.dataset.uidMoi ||
        filaPadre.querySelector(
            'input[name="moi_uid[]"]'
        )?.value;

    const detalleId =
        filaPadre.querySelector(
            'input[name="moi_detalle_id[]"]'
        );

    const deleteInput =
        filaPadre.querySelector(
            'input[name="moi_delete[]"]'
        );

    const registroGuardado =
        Boolean(
            detalleId &&
            String(
                detalleId.value || ''
            ).trim()
        );

    const filaHijas =
        uid
            ? document.querySelector(
                [
                    'tr.fila-hijas-moi',
                    `[data-parent-uid-moi="${uid}"]`
                ].join('')
            )
            : filaPadre.nextElementSibling;

    if (registroGuardado) {
        if (deleteInput) {
            deleteInput.value = '1';
        }

        filaPadre.classList.add(
            'fila-eliminada',
            'fila-eliminada-moi'
        );

        filaPadre.dataset.eliminada =
            '1';

        filaPadre.hidden = true;
        filaPadre.style.display = 'none';

        if (filaHijas) {
            filaHijas.classList.add(
                'fila-eliminada',
                'fila-eliminada-moi'
            );

            filaHijas.dataset.eliminada =
                '1';

            filaHijas.hidden = true;
            filaHijas.style.display =
                'none';
        }
    } else {
        if (filaHijas) {
            filaHijas.remove();
        }

        filaPadre.remove();
    }

    cerrarDropdownsServicios();

    recalcularTotalesManoObra();
}


// =====================================================
// ELIMINAR MOE
// =====================================================
function eliminarFilaMOE(
    boton
) {
    if (!PUEDE_EDITAR_MANO_OBRA) {
        return;
    }

    const fila =
        boton?.closest('tr');

    if (!fila) {
        return;
    }

    const detalleId =
        fila.querySelector(
            'input[name="moe_detalle_id[]"]'
        );

    const deleteInput =
        fila.querySelector(
            'input[name="moe_delete[]"]'
        );

    const registroGuardado =
        Boolean(
            detalleId &&
            String(
                detalleId.value || ''
            ).trim()
        );

    if (registroGuardado) {
        if (deleteInput) {
            deleteInput.value = '1';
        }

        fila.classList.add(
            'fila-eliminada',
            'fila-eliminada-moe'
        );

        fila.dataset.eliminada =
            '1';

        fila.hidden = true;
        fila.style.display = 'none';
    } else {
        fila.remove();
    }

    cerrarDropdownsServicios();

    recalcularTotalesManoObra();
}


// =====================================================
// BUSCAR SERVICIO
// =====================================================
function buscarServicioEnFila(
    inputElement,
    prefijo = 'moi'
) {
    if (!PUEDE_EDITAR_MANO_OBRA) {
        return;
    }

    if (!inputElement) {
        return;
    }

    const consulta =
        String(
            inputElement.value || ''
        ).trim();

    const fila =
        inputElement.closest('tr');

    const dropdown =
        fila?.querySelector(
            '.dropdown-resultados-servicios'
        );

    if (!dropdown) {
        return;
    }

    if (consulta.length < 2) {
        dropdown.style.display =
            'none';

        dropdown.innerHTML =
            '';

        return;
    }

    clearTimeout(
        timeoutBusquedaServicio
    );

    timeoutBusquedaServicio =
        setTimeout(
            async function () {
                await ejecutarBusquedaServicio(
                    consulta,
                    inputElement,
                    prefijo,
                    dropdown
                );
            },
            300
        );
}


async function ejecutarBusquedaServicio(
    consulta,
    inputElement,
    prefijo,
    dropdown
) {
    try {
        const url = (
            '/api/buscar-servicios-ot/' +
            `?q=${encodeURIComponent(
                consulta
            )}` +
            `&categoria=${encodeURIComponent(
                prefijo
            )}`
        );

        const response =
            await fetch(url);

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

        renderResultadosServicios(
            resultados,
            inputElement,
            prefijo,
            dropdown
        );
    } catch (error) {
        console.error(
            'Error buscando servicios:',
            error
        );

        dropdown.style.display =
            'none';

        dropdown.innerHTML =
            '';
    }
}


function renderResultadosServicios(
    resultados,
    inputElement,
    prefijo,
    dropdown
) {
    dropdown.innerHTML = '';

    if (resultados.length === 0) {
        dropdown.innerHTML = `
            <div
                style="
                    padding: 10px;
                    color: #86868b;
                    font-size: 12px;
                    text-align: center;
                "
            >
                No se encontraron servicios
            </div>
        `;

        dropdown.style.display =
            'block';

        return;
    }

    resultados.forEach(function (
        item
    ) {
        const opcion =
            document.createElement(
                'div'
            );

        opcion.className =
            'servicio-sugerencia-item';

        opcion.style.cssText = `
            padding: 10px 12px;
            font-size: 12px;
            color: #1d1d1f;
            cursor: pointer;
            border-bottom:
                1px solid #f5f5f7;
            line-height: 1.3;
        `;

        const precio =
            item.precio_recomendado ||
            item.p_u ||
            '0.00';

        opcion.innerHTML = `
            <div
                style="
                    font-weight: 700;
                    color: #0071e3;
                    margin-bottom: 2px;
                "
            >
                ${escaparHTMLManoObra(
                    item.codigo || ''
                )}
            </div>

            <div
                style="
                    color: #4a4a4a;
                "
            >
                ${escaparHTMLManoObra(
                    item.descripcion || ''
                )}
            </div>

            <div
                style="
                    font-size: 10px;
                    color: #34c759;
                    font-weight: 600;
                    margin-top: 2px;
                "
            >
                P.U. $
                ${escaparHTMLManoObra(
                    precio
                )}
            </div>
        `;

        opcion.addEventListener(
            'click',
            function () {
                seleccionarServicioEnFila(
                    item,
                    inputElement,
                    prefijo
                );

                dropdown.style.display =
                    'none';

                dropdown.innerHTML =
                    '';
            }
        );

        dropdown.appendChild(
            opcion
        );
    });

    dropdown.style.display =
        'block';
}


// =====================================================
// SELECCIONAR SERVICIO
// =====================================================
function seleccionarServicioEnFila(
    item,
    inputElement,
    prefijo = 'moi'
) {
    if (!PUEDE_EDITAR_MANO_OBRA) {
        return;
    }

    if (
        !item ||
        !inputElement
    ) {
        return;
    }

    const filaPadre =
        inputElement.closest('tr');

    if (!filaPadre) {
        return;
    }

    const servicioHidden =
        filaPadre.querySelector(
            '.servicio-id-hidden'
        );

    const descripcionInput =
        filaPadre.querySelector(
            '.descripcion-manual'
        );

    const precioInput =
        filaPadre.querySelector(
            '.pu'
        );

    const cantidadInput =
        filaPadre.querySelector(
            '.cantidad'
        );

    if (servicioHidden) {
        servicioHidden.value =
            item.id || '';
    }

    inputElement.value =
        item.codigo || '';

    if (descripcionInput) {
        descripcionInput.value =
            item.descripcion || '';
    }

    if (cantidadInput) {
        const cantidadActual =
            typeof numeroSeguro ===
            'function'
                ? numeroSeguro(
                    cantidadInput.value
                )
                : Number(
                    cantidadInput.value
                ) || 0;

        if (cantidadActual <= 0) {
            cantidadInput.value =
                '1.00';
        }
    }

    if (precioInput) {
        const precio =
            typeof numeroSeguro ===
            'function'
                ? numeroSeguro(
                    item.precio_recomendado ||
                    item.p_u ||
                    0
                )
                : Number(
                    item.precio_recomendado ||
                    item.p_u ||
                    0
                ) || 0;

        precioInput.value =
            precio.toFixed(2);
    }

    if (
        typeof recalcularFilaDesdeTr ===
        'function'
    ) {
        recalcularFilaDesdeTr(
            filaPadre
        );
    }

    if (prefijo === 'moi') {
        cargarProcedimientosServicioMOI(
            filaPadre,
            item
        );
    }

    recalcularTotalesManoObra();
}


function cargarProcedimientosServicioMOI(
    filaPadre,
    item
) {
    const uid =
        filaPadre.dataset.uidMoi ||
        filaPadre.querySelector(
            'input[name="moi_uid[]"]'
        )?.value;

    const filaHijas =
        uid
            ? document.querySelector(
                [
                    'tr.fila-hijas-moi',
                    `[data-parent-uid-moi="${uid}"]`
                ].join('')
            )
            : filaPadre.nextElementSibling;

    if (
        !filaHijas ||
        !filaHijas.classList.contains(
            'fila-hijas-moi'
        )
    ) {
        return;
    }

    const contenedor =
        filaHijas.querySelector(
            '.procedimientos-moi'
        );

    const botonAgregar =
        filaHijas.querySelector(
            'button[onclick*="agregarProcedimientoMOI"]'
        );

    if (!contenedor) {
        return;
    }

    contenedor.innerHTML = '';

    if (
        !Array.isArray(
            item.procedimientos
        ) ||
        !botonAgregar
    ) {
        return;
    }

    item.procedimientos.forEach(
        function (procedimiento) {
            agregarProcedimientoMOI(
                botonAgregar,
                procedimiento.descripcion ||
                ''
            );
        }
    );
}


// =====================================================
// PROCEDIMIENTOS MOI
// =====================================================
function agregarProcedimientoMOI(
    boton,
    texto = ''
) {
    if (!PUEDE_EDITAR_MANO_OBRA) {
        return;
    }

    const filaHijas =
        boton?.closest(
            '.fila-hijas-moi'
        );

    if (!filaHijas) {
        return;
    }

    const contenedor =
        filaHijas.querySelector(
            '.procedimientos-moi'
        );

    if (!contenedor) {
        return;
    }

    const uid =
        contenedor.dataset.parentIndex;

    if (
        uid === undefined ||
        uid === null ||
        uid === ''
    ) {
        console.error(
            'No existe data-parent-index en procedimientos-moi.'
        );

        return;
    }

    const textoSeguro =
        escaparHTMLManoObra(
            texto
        );

    const html = `
        <div
            class="procedimiento-item-moi"
        >
            <input
                type="hidden"
                name="moi_procedimiento_id_${uid}[]"
                value=""
            >

            <input
                type="hidden"
                name="moi_procedimiento_delete_${uid}[]"
                value="0"
            >

            <input
                type="hidden"
                name="moi_procedimiento_actualizado_en_${uid}[]"
                value=""
            >

            <input
                type="text"
                name="moi_procedimientos_${uid}[]"
                class="form-control-apple"
                value="${textoSeguro}"
                placeholder="
                    Procedimiento incluido
                "
            >

            <button
                type="button"
                class="
                    btn-login
                    danger
                    small
                "
                onclick="
                    eliminarProcedimientoMOI(
                        this
                    )
                "
                title="Quitar procedimiento"
            >
                ✕
            </button>
        </div>
    `;

    contenedor.insertAdjacentHTML(
        'beforeend',
        html
    );
}


function eliminarProcedimientoMOI(
    boton
) {
    if (!PUEDE_EDITAR_MANO_OBRA) {
        return;
    }

    const item =
        boton?.closest(
            '.procedimiento-item-moi'
        );

    if (!item) {
        return;
    }

    const procedimientoId =
        item.querySelector(
            'input[name^="moi_procedimiento_id_"]'
        );

    const deleteInput =
        item.querySelector(
            'input[name^="moi_procedimiento_delete_"]'
        );

    const registroGuardado =
        Boolean(
            procedimientoId &&
            String(
                procedimientoId.value ||
                ''
            ).trim()
        );

    if (registroGuardado) {
        if (deleteInput) {
            deleteInput.value = '1';
        }

        item.classList.add(
            'procedimiento-eliminado-moi'
        );

        item.dataset.eliminada =
            '1';

        item.hidden = true;
        item.style.display = 'none';
    } else {
        item.remove();
    }
}


// =====================================================
// MODAL INGRESO RÁPIDO MOI
// =====================================================
function abrirModalIngresoRapidoMOI() {
    if (!PUEDE_EDITAR_MANO_OBRA) {
        return;
    }

    const modal =
        document.getElementById(
            'modalIngresoRapidoMOI'
        );

    if (modal) {
        modal.style.display =
            'flex';
    }

    const input =
        document.getElementById(
            'irmoi_descripcion'
        );

    if (input) {
        setTimeout(
            function () {
                input.focus();
            },
            100
        );
    }
}


function cerrarModalIngresoRapidoMOI() {
    const modal =
        document.getElementById(
            'modalIngresoRapidoMOI'
        );

    if (modal) {
        modal.style.display =
            'none';
    }

    const descripcion =
        document.getElementById(
            'irmoi_descripcion'
        );

    const precio =
        document.getElementById(
            'irmoi_precio'
        );

    const cantidad =
        document.getElementById(
            'irmoi_cantidad'
        );

    if (descripcion) {
        descripcion.value = '';
    }

    if (precio) {
        precio.value = '0.00';
    }

    if (cantidad) {
        cantidad.value = '1';
    }
}


function confirmarIngresoRapidoMOI() {
    if (!PUEDE_EDITAR_MANO_OBRA) {
        return;
    }

    const descripcionInput =
        document.getElementById(
            'irmoi_descripcion'
        );

    const precioInput =
        document.getElementById(
            'irmoi_precio'
        );

    const cantidadInput =
        document.getElementById(
            'irmoi_cantidad'
        );

    if (
        !descripcionInput ||
        !precioInput ||
        !cantidadInput
    ) {
        return;
    }

    const descripcion =
        descripcionInput.value.trim();

    const precio =
        numeroSeguro(
            precioInput.value
        );

    const cantidad =
        numeroSeguro(
            cantidadInput.value
        );

    if (!descripcion) {
        alert(
            'La descripción es obligatoria.'
        );

        descripcionInput.focus();
        return;
    }

    if (precio < 0) {
        alert(
            'El precio no puede ser negativo.'
        );

        precioInput.focus();
        return;
    }

    if (cantidad <= 0) {
        alert(
            'La cantidad debe ser mayor que cero.'
        );

        cantidadInput.focus();
        return;
    }

    insertarIngresoManualMOI({
        descripcion,
        precio,
        cantidad
    });

    cerrarModalIngresoRapidoMOI();
}


// =====================================================
// INSERTAR MOI MANUAL
// =====================================================
function insertarIngresoManualMOI({
    descripcion,
    precio,
    cantidad
}) {
    const tbody =
        document.getElementById(
            'cuerpoTablaMOI'
        );

    if (!tbody) {
        return;
    }

    const uid =
        generarUidManoObra();

    const subtotal = (
        precio *
        cantidad
    ).toFixed(2);

    const html = `
        <tr
            class="fila-padre-moi"
            data-uid-moi="${uid}"
        >
            <td class="servicio-cell">
                <input
                    type="hidden"
                    name="moi_detalle_id[]"
                    value=""
                >

                <input
                    type="hidden"
                    name="moi_delete[]"
                    value="0"
                >

                <input
                    type="hidden"
                    name="moi_actualizado_en[]"
                    value=""
                >

                <input
                    type="hidden"
                    name="moi_uid[]"
                    value="${uid}"
                >

                <input
                    type="hidden"
                    name="moi_servicio_id[]"
                    class="servicio-id-hidden"
                    value=""
                >

                <div
                    style="
                        text-align: center;
                        background-color: #f5f5f7;
                        padding: 8px;
                        border-radius: 6px;
                        font-weight: bold;
                        color: #86868b;
                        font-size: 11px;
                    "
                >
                    [ MANUAL ]
                </div>
            </td>

            <td>
                <input
                    type="text"
                    name="moi_descripcion[]"
                    class="
                        form-control-apple
                        descripcion-manual
                        descripcion-moi
                        w-100
                    "
                    style="
                        font-size: 13px;
                        font-weight: 500;
                        color: #1d1d1f;
                        padding: 8px;
                    "
                    value="${escaparHTMLManoObra(
                        descripcion
                    )}"
                >
            </td>

            <td>
                <input
                    type="number"
                    step="0.01"
                    min="0"
                    name="moi_pu[]"
                    class="form-control-apple pu"
                    value="${precio.toFixed(2)}"
                    oninput="calcularFila(this)"
                >
            </td>

            <td>
                <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    name="moi_cantidad[]"
                    class="
                        form-control-apple
                        cantidad
                    "
                    value="${cantidad.toFixed(2)}"
                    oninput="calcularFila(this)"
                >
            </td>

            <td>
                <input
                    type="number"
                    step="0.01"
                    name="moi_valor[]"
                    class="
                        form-control-apple
                        valor
                    "
                    value="${subtotal}"
                    readonly
                >
            </td>

            <td>
                <div class="row-controls">
                    <button
                        type="button"
                        class="
                            btn-login
                            danger
                            small
                        "
                        onclick="
                            eliminarFilaMOI(this)
                        "
                        title="Quitar"
                    >
                        ✕
                    </button>
                </div>
            </td>
        </tr>

        <tr
            class="fila-hijas-moi"
            data-parent-uid-moi="${uid}"
        >
            <td></td>

            <td>
                <div
                    class="procedimientos-moi"
                    data-parent-index="${uid}"
                >
                </div>

                <button
                    type="button"
                    class="btn-login small"
                    onclick="
                        agregarProcedimientoMOI(
                            this
                        )
                    "
                >
                    + Agregar procedimiento
                </button>
            </td>

            <td></td>
            <td></td>
            <td></td>
            <td></td>
        </tr>
    `;

    tbody.insertAdjacentHTML(
        'beforeend',
        html
    );

    recalcularTotalesManoObra();
}


// =====================================================
// MODAL INGRESO RÁPIDO MOE
// =====================================================
function abrirModalIngresoRapidoMOE() {
    if (!PUEDE_EDITAR_MANO_OBRA) {
        return;
    }

    const modal =
        document.getElementById(
            'modalIngresoRapidoMOE'
        );

    if (modal) {
        modal.style.display =
            'flex';
    }

    const input =
        document.getElementById(
            'irmoe_descripcion'
        );

    if (input) {
        setTimeout(
            function () {
                input.focus();
            },
            100
        );
    }
}


function cerrarModalIngresoRapidoMOE() {
    const modal =
        document.getElementById(
            'modalIngresoRapidoMOE'
        );

    if (modal) {
        modal.style.display =
            'none';
    }

    const descripcion =
        document.getElementById(
            'irmoe_descripcion'
        );

    const precio =
        document.getElementById(
            'irmoe_precio'
        );

    const cantidad =
        document.getElementById(
            'irmoe_cantidad'
        );

    if (descripcion) {
        descripcion.value = '';
    }

    if (precio) {
        precio.value = '0.00';
    }

    if (cantidad) {
        cantidad.value = '1';
    }
}


function confirmarIngresoRapidoMOE() {
    if (!PUEDE_EDITAR_MANO_OBRA) {
        return;
    }

    const descripcionInput =
        document.getElementById(
            'irmoe_descripcion'
        );

    const precioInput =
        document.getElementById(
            'irmoe_precio'
        );

    const cantidadInput =
        document.getElementById(
            'irmoe_cantidad'
        );

    if (
        !descripcionInput ||
        !precioInput ||
        !cantidadInput
    ) {
        return;
    }

    const descripcion =
        descripcionInput.value.trim();

    const precio =
        numeroSeguro(
            precioInput.value
        );

    const cantidad =
        numeroSeguro(
            cantidadInput.value
        );

    if (!descripcion) {
        alert(
            'La descripción es obligatoria.'
        );

        descripcionInput.focus();
        return;
    }

    if (precio < 0) {
        alert(
            'El precio no puede ser negativo.'
        );

        precioInput.focus();
        return;
    }

    if (cantidad <= 0) {
        alert(
            'La cantidad debe ser mayor que cero.'
        );

        cantidadInput.focus();
        return;
    }

    insertarIngresoManualMOE({
        descripcion,
        precio,
        cantidad
    });

    cerrarModalIngresoRapidoMOE();
}


// =====================================================
// INSERTAR MOE MANUAL
// =====================================================
function insertarIngresoManualMOE({
    descripcion,
    precio,
    cantidad
}) {
    const tbody =
        document.getElementById(
            'cuerpoTablaMOE'
        );

    if (!tbody) {
        return;
    }

    const uid =
        generarUidManoObra();

    const subtotal = (
        precio *
        cantidad
    ).toFixed(2);

    const html = `
        <tr
            class="fila-padre-moe"
            data-uid-moe="${uid}"
        >
            <td class="servicio-cell">
                <input
                    type="hidden"
                    name="moe_detalle_id[]"
                    value=""
                >

                <input
                    type="hidden"
                    name="moe_delete[]"
                    value="0"
                >

                <input
                    type="hidden"
                    name="moe_actualizado_en[]"
                    value=""
                >

                <input
                    type="hidden"
                    name="moe_uid[]"
                    value="${uid}"
                >

                <input
                    type="hidden"
                    name="moe_servicio_id[]"
                    class="servicio-id-hidden"
                    value=""
                >

                <div
                    style="
                        text-align: center;
                        background-color: #f5f5f7;
                        padding: 8px;
                        border-radius: 6px;
                        font-weight: bold;
                        color: #86868b;
                        font-size: 11px;
                    "
                >
                    [ MANUAL ]
                </div>
            </td>

            <td>
                <input
                    type="text"
                    name="moe_descripcion[]"
                    class="
                        form-control-apple
                        descripcion-manual
                        descripcion-moe
                        w-100
                    "
                    style="
                        font-size: 13px;
                        font-weight: 500;
                        color: #1d1d1f;
                        padding: 8px;
                    "
                    value="${escaparHTMLManoObra(
                        descripcion
                    )}"
                >
            </td>

            <td>
                <input
                    type="number"
                    step="0.01"
                    min="0"
                    name="moe_pu[]"
                    class="form-control-apple pu"
                    value="${precio.toFixed(2)}"
                    oninput="calcularFila(this)"
                >
            </td>

            <td>
                <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    name="moe_cantidad[]"
                    class="
                        form-control-apple
                        cantidad
                    "
                    value="${cantidad.toFixed(2)}"
                    oninput="calcularFila(this)"
                >
            </td>

            <td>
                <input
                    type="number"
                    step="0.01"
                    name="moe_valor[]"
                    class="
                        form-control-apple
                        valor
                    "
                    value="${subtotal}"
                    readonly
                >
            </td>

            <td>
                <div class="row-controls">
                    <button
                        type="button"
                        class="
                            btn-login
                            danger
                            small
                        "
                        onclick="
                            eliminarFilaMOE(this)
                        "
                        title="Quitar"
                    >
                        ✕
                    </button>
                </div>
            </td>
        </tr>
    `;

    tbody.insertAdjacentHTML(
        'beforeend',
        html
    );

    recalcularTotalesManoObra();
}


// =====================================================
// CERRAR DROPDOWNS
// =====================================================
function cerrarDropdownsServicios(
    excepto = null
) {
    document.querySelectorAll(
        '.dropdown-resultados-servicios'
    ).forEach(function (
        dropdown
    ) {
        if (
            excepto &&
            dropdown === excepto
        ) {
            return;
        }

        dropdown.style.display =
            'none';
    });
}


// =====================================================
// EVENTOS GLOBALES
// =====================================================
document.addEventListener(
    'click',
    function (event) {
        const dentroBuscador =
            event.target.closest(
                '.servicio-busqueda-wrap'
            );

        if (!dentroBuscador) {
            cerrarDropdownsServicios();
        }
    }
);