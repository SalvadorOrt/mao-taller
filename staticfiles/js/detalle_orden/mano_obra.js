let contadorPadresMOI = document.querySelectorAll('#cuerpoTablaMOI .fila-padre-moi').length;
let timeoutBusquedaServicio = null;

// =====================================================
// AGREGAR FILA MOI DESDE CATÁLOGO
// =====================================================
function agregarFilaMOI(enfocar = false) {
    agregarFilaSimple('tablaMOI');

    if (enfocar) {
        const filasPadre = document.querySelectorAll('#cuerpoTablaMOI .fila-padre-moi');
        const ultimaFila = filasPadre[filasPadre.length - 1];
        const input = ultimaFila?.querySelector('.servicio-busqueda-input');
        if (input) input.focus();
    }
}

// =====================================================
// AGREGAR FILA SIMPLE MOI / MOE (CORREGIDO PARA EDITAR)
// =====================================================
function agregarFilaSimple(idTabla) {
    const tbody = document.querySelector(`#${idTabla} tbody`);
    if (!tbody) return;

    const isMoi = idTabla === 'tablaMOI';
    const prefix = isMoi ? 'moi' : 'moe';
    const parentIndex = Date.now();

    const placeholder = isMoi
        ? 'Buscar servicio interno...'
        : 'Buscar servicio externo...';

    const filaPadre = `
        <tr class="${isMoi ? 'fila-padre-moi' : ''}">
            <td class="servicio-cell">
                <input type="hidden" name="${prefix}_uid[]" value="${parentIndex}">
                <input type="hidden" name="${prefix}_servicio_id[]" class="servicio-id-hidden" value="">

                <div class="servicio-busqueda-wrap" style="position:relative;">
                    <input type="text"
                           class="form-control-apple servicio-busqueda-input"
                           placeholder="${placeholder}"
                           autocomplete="off"
                           style="text-align:center; font-weight:600;"
                           oninput="buscarServicioEnFila(this, '${prefix}')"
                           onfocus="buscarServicioEnFila(this, '${prefix}')">

                    <div class="dropdown-resultados-servicios"
                         style="display:none; position:absolute; top:100%; left:0; right:0; background:white; border:1px solid #d2d2d7; border-radius:8px; box-shadow:0 4px 12px rgba(0,0,0,0.15); z-index:1000; margin-top:4px; text-align:left;">
                    </div>
                </div>
            </td>

            <td>
                <input type="text"
                       name="${prefix}_descripcion[]"
                       class="form-control-apple descripcion-manual descripcion-${prefix} w-100"
                       style="font-size:13px; font-weight:500; color:#1d1d1f; padding:8px;"
                       placeholder="Descripción del servicio"
                       value="">
            </td>

            <td>
                <input type="number"
                       step="0.01"
                       name="${prefix}_pu[]"
                       class="form-control-apple pu"
                       value="0.00"
                       oninput="calcularFila(this)">
            </td>

            <td>
                <input type="number"
                       step="0.01"
                       name="${prefix}_cantidad[]"
                       class="form-control-apple cantidad"
                       value="1.00"
                       oninput="calcularFila(this)">
            </td>

            <td>
                <input type="number"
                       step="0.01"
                       name="${prefix}_valor[]"
                       class="form-control-apple valor"
                       value="0.00"
                       readonly>
            </td>

            <td>
                <div class="row-controls">
                    <button type="button"
                            class="btn-login danger small"
                            onclick="eliminarFila(this)">
                        ✕
                    </button>
                </div>
            </td>
        </tr>
    `;

    tbody.insertAdjacentHTML('beforeend', filaPadre);

    if (isMoi) {
        const filaHijas = `
            <tr class="fila-hijas-moi">
                <td></td>

                <td>
                    <div class="procedimientos-moi"
                         data-parent-index="${parentIndex}">
                    </div>

                    <button type="button"
                            class="btn-login small"
                            onclick="agregarProcedimientoMOI(this)">
                        + Agregar procedimiento
                    </button>
                </td>

                <td></td>
                <td></td>
                <td></td>
                <td></td>
            </tr>
        `;

        tbody.insertAdjacentHTML('beforeend', filaHijas);
    }
}

// =====================================================
// BUSCAR SERVICIO EN API
// =====================================================
function buscarServicioEnFila(inputElement, prefix = 'moi') {
    const query = inputElement.value.trim();
    const fila = inputElement.closest('tr');
    const dropdown = fila.querySelector('.dropdown-resultados-servicios');

    if (!dropdown) return;

    if (query.length < 2) {
        dropdown.style.display = 'none';
        dropdown.innerHTML = '';
        return;
    }

    clearTimeout(timeoutBusquedaServicio);

    timeoutBusquedaServicio = setTimeout(() => {
        fetch(`/api/buscar-servicios-ot/?q=${encodeURIComponent(query)}&categoria=${prefix}`)
            .then(response => response.json())
            .then(data => {
                dropdown.innerHTML = '';

                if (data.resultados && data.resultados.length > 0) {
                    data.resultados.forEach(item => {
                        const opcion = document.createElement('div');

                        opcion.style.cssText = `
                            padding:10px 12px;
                            font-size:12px;
                            color:#1d1d1f;
                            cursor:pointer;
                            border-bottom:1px solid #f5f5f7;
                            line-height:1.3;
                        `;

                        opcion.innerHTML = `
                            <div style="font-weight:700; color:#0071e3; margin-bottom:2px;">
                                ${escaparHTML(item.codigo || '')}
                            </div>

                            <div style="color:#4a4a4a;">
                                ${escaparHTML(item.descripcion || '')}
                            </div>

                            <div style="font-size:10px; color:#34c759; font-weight:600; margin-top:2px;">
                                P.U. $${escaparHTML(item.precio_recomendado || item.p_u || '0.00')}
                            </div>
                        `;

                        opcion.addEventListener('click', () => {
                            seleccionarServicioEnFila(item, inputElement, prefix);
                            dropdown.style.display = 'none';
                        });

                        dropdown.appendChild(opcion);
                    });

                    dropdown.style.display = 'block';
                } else {
                    dropdown.innerHTML = `
                        <div style="padding:10px; color:#86868b; font-size:12px; text-align:center;">
                            No se encontraron servicios
                        </div>
                    `;
                    dropdown.style.display = 'block';
                }
            })
            .catch(error => {
                console.error('Error buscando servicios:', error);
                dropdown.style.display = 'none';
            });
    }, 300);
}
// =====================================================
// SELECCIONAR SERVICIO DE LA BDD (CORREGIDO)
// =====================================================
function seleccionarServicioEnFila(item, inputElement, prefix = 'moi') {
    if (!item || !inputElement) return;

    const filaPadre = inputElement.closest('tr');
    if (!filaPadre) return;

    const servicioHidden = filaPadre.querySelector('.servicio-id-hidden');
    if (servicioHidden) servicioHidden.value = item.id || '';

    // Escribe el código en la primera columna
    inputElement.value = item.codigo || '';

    // Escribe la descripción en nuestro nuevo input editable de la segunda columna
    const descripcionInput = filaPadre.querySelector('.descripcion-manual');
    if (descripcionInput) {
        descripcionInput.value = item.descripcion || '';
    }

    const puInput = filaPadre.querySelector('.pu');
    if (puInput) {
        puInput.value = numeroSeguro(item.precio_recomendado || item.p_u || 0).toFixed(2);
        calcularFila(puInput);
    }

    const cantidadInput = filaPadre.querySelector('.cantidad');
    if (cantidadInput && (!cantidadInput.value || cantidadInput.value == '0.00')) {
        cantidadInput.value = '1.00';
    }

    if (prefix === 'moi') {
        const filaHijas = filaPadre.nextElementSibling;

        if (filaHijas && filaHijas.classList.contains('fila-hijas-moi')) {
            const contenedor = filaHijas.querySelector('.procedimientos-moi');
            const botonAgregar = filaHijas.querySelector('button[onclick*="agregarProcedimientoMOI"]');

            if (contenedor) {
                contenedor.innerHTML = '';

                if (Array.isArray(item.procedimientos)) {
                    item.procedimientos.forEach(proc => {
                        agregarProcedimientoMOI(
                            botonAgregar,
                            proc.descripcion || ''
                        );
                    });
                }
            }
        }
    }

    recalcularTotales();
}

// =====================================================
// AGREGAR PROCEDIMIENTO
// =====================================================
function agregarProcedimientoMOI(boton, texto = '') {
    const filaHijas = boton.closest('.fila-hijas-moi');
    if (!filaHijas) return;

    const contenedor = filaHijas.querySelector('.procedimientos-moi');
    if (!contenedor) return;

    const uid = contenedor.dataset.parentIndex;

    if (!uid && uid !== '0') {
        console.error('No existe data-parent-index en procedimientos-moi');
        return;
    }

    const html = `
        <div class="procedimiento-item-moi">
            <input type="text"
                   name="moi_procedimientos_${uid}[]"
                   class="form-control-apple"
                   value="${escaparHTML(texto)}"
                   placeholder="Procedimiento incluido">

            <button type="button"
                    class="btn-login danger small"
                    onclick="eliminarProcedimientoMOI(this)">
                ✕
            </button>
        </div>
    `;

    contenedor.insertAdjacentHTML('beforeend', html);
}

// =====================================================
// ELIMINAR PROCEDIMIENTO
// =====================================================
function eliminarProcedimientoMOI(boton) {
    const item = boton.closest('.procedimiento-item-moi');
    if (item) item.remove();
}

// =====================================================
// MODAL INGRESO RÁPIDO MOI
// =====================================================
function abrirModalIngresoRapidoMOI() {
    const modal = document.getElementById('modalIngresoRapidoMOI');
    if (modal) modal.style.display = 'flex';

    const input = document.getElementById('irmoi_descripcion');
    if (input) setTimeout(() => input.focus(), 100);
}

function cerrarModalIngresoRapidoMOI() {
    const modal = document.getElementById('modalIngresoRapidoMOI');
    if (modal) modal.style.display = 'none';

    document.getElementById('irmoi_descripcion').value = '';
    document.getElementById('irmoi_precio').value = '0.00';
    document.getElementById('irmoi_cantidad').value = '1';
}
// =====================================================
// MODAL INGRESO RÁPIDO MOI (CORREGIDO)
// =====================================================
function confirmarIngresoRapidoMOI() {
    const descripcion = document.getElementById('irmoi_descripcion').value.trim();
    const precio = numeroSeguro(document.getElementById('irmoi_precio').value);
    const cantidad = numeroSeguro(document.getElementById('irmoi_cantidad').value);

    if (!descripcion) {
        alert('La descripción es obligatoria.');
        return;
    }

    const tbody = document.getElementById('cuerpoTablaMOI');
    const parentIndex = Date.now();
    const subtotal = (precio * cantidad).toFixed(2);

    const html = `
        <tr class="fila-padre-moi">
            <td class="servicio-cell">
                <input type="hidden" name="moi_uid[]" value="${parentIndex}">
                <input type="hidden" name="moi_servicio_id[]" class="servicio-id-hidden" value="">

                <div style="text-align:center; background-color:#f5f5f7; padding:8px; border-radius:6px; font-weight:bold; color:#86868b; font-size:11px;">
                    [ MANUAL ]
                </div>
            </td>

            <td>
                <input type="text"
                       name="moi_descripcion[]"
                       class="form-control-apple descripcion-manual descripcion-moi w-100"
                       style="font-size:13px; font-weight:500; color:#1d1d1f; padding:8px;"
                       value="${escaparHTML(descripcion)}">
            </td>

            <td>
                <input type="number"
                       step="0.01"
                       name="moi_pu[]"
                       class="form-control-apple pu"
                       value="${precio.toFixed(2)}"
                       oninput="calcularFila(this)">
            </td>

            <td>
                <input type="number"
                       step="1"
                       name="moi_cantidad[]"
                       class="form-control-apple cantidad"
                       value="${cantidad.toFixed(2)}"
                       oninput="calcularFila(this)">
            </td>

            <td>
                <input type="number"
                       step="0.01"
                       name="moi_valor[]"
                       class="form-control-apple valor"
                       value="${subtotal}"
                       readonly>
            </td>

            <td>
                <div class="row-controls">
                    <button type="button"
                            class="btn-login danger small"
                            onclick="eliminarFila(this)">
                        ✕
                    </button>
                </div>
            </td>
        </tr>

        <tr class="fila-hijas-moi">
            <td></td>

            <td>
                <div class="procedimientos-moi"
                     data-parent-index="${parentIndex}">
                </div>

                <button type="button"
                        class="btn-login small"
                        onclick="agregarProcedimientoMOI(this)">
                    + Agregar procedimiento
                </button>
            </td>

            <td></td>
            <td></td>
            <td></td>
            <td></td>
        </tr>
    `;

    tbody.insertAdjacentHTML('beforeend', html);

    recalcularTotales();
    cerrarModalIngresoRapidoMOI();
}
// =====================================================
// AGREGAR FILA MOE DESDE CATÁLOGO
// =====================================================
function agregarFilaMOE(enfocar = false) {
    agregarFilaSimple('tablaMOE');

    if (enfocar) {
        const filas = document.querySelectorAll('#cuerpoTablaMOE tr');
        const ultimaFila = filas[filas.length - 1];
        const input = ultimaFila?.querySelector('.servicio-busqueda-input');

        if (input) input.focus();
    }
}

// =====================================================
// MODAL INGRESO RÁPIDO MOE
// =====================================================
function abrirModalIngresoRapidoMOE() {
    const modal = document.getElementById('modalIngresoRapidoMOE');
    if (modal) modal.style.display = 'flex';

    const input = document.getElementById('irmoe_descripcion');
    if (input) setTimeout(() => input.focus(), 100);
}

function cerrarModalIngresoRapidoMOE() {
    const modal = document.getElementById('modalIngresoRapidoMOE');
    if (modal) modal.style.display = 'none';

    document.getElementById('irmoe_descripcion').value = '';
    document.getElementById('irmoe_precio').value = '0.00';
    document.getElementById('irmoe_cantidad').value = '1';
}
// =====================================================
// MODAL INGRESO RÁPIDO MOE (CORREGIDO)
// =====================================================
function confirmarIngresoRapidoMOE() {
    const descripcion = document.getElementById('irmoe_descripcion').value.trim();
    const precio = numeroSeguro(document.getElementById('irmoe_precio').value);
    const cantidad = numeroSeguro(document.getElementById('irmoe_cantidad').value);

    if (!descripcion) {
        alert('La descripción es obligatoria.');
        return;
    }

    const tbody = document.getElementById('cuerpoTablaMOE');
    const uid = Date.now();
    const subtotal = (precio * cantidad).toFixed(2);

    const html = `
        <tr>
            <td class="servicio-cell">
                <input type="hidden" name="moe_uid[]" value="${uid}">
                <input type="hidden" name="moe_servicio_id[]" class="servicio-id-hidden" value="">

                <div style="text-align:center; background-color:#f5f5f7; padding:8px; border-radius:6px; font-weight:bold; color:#86868b; font-size:11px;">
                    [ MANUAL ]
                </div>
            </td>

            <td>
                <input type="text"
                       name="moe_descripcion[]"
                       class="form-control-apple descripcion-manual descripcion-moe w-100"
                       style="font-size:13px; font-weight:500; color:#1d1d1f; padding:8px;"
                       value="${escaparHTML(descripcion)}">
            </td>

            <td>
                <input type="number"
                       step="0.01"
                       name="moe_pu[]"
                       class="form-control-apple pu"
                       value="${precio.toFixed(2)}"
                       oninput="calcularFila(this)">
            </td>

            <td>
                <input type="number"
                       step="1"
                       name="moe_cantidad[]"
                       class="form-control-apple cantidad"
                       value="${cantidad.toFixed(2)}"
                       oninput="calcularFila(this)">
            </td>

            <td>
                <input type="number"
                       step="0.01"
                       name="moe_valor[]"
                       class="form-control-apple valor"
                       value="${subtotal}"
                       readonly>
            </td>

            <td>
                <div class="row-controls">
                    <button type="button"
                            class="btn-login danger small"
                            onclick="eliminarFila(this)">
                        ✕
                    </button>
                </div>
            </td>
        </tr>
    `;

    tbody.insertAdjacentHTML('beforeend', html);

    recalcularTotales();
    cerrarModalIngresoRapidoMOE();
}