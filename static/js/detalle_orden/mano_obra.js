const PUEDE_EDITAR_MANO_OBRA =
    document.querySelector(".ot-wrapper")?.dataset.puedeEditar === "true";

let timeoutBusquedaServicio = null;

function escaparHTML(valor) {
    return String(valor ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

// =====================================================
// AGREGAR FILAS
// =====================================================
function agregarFilaMOI(enfocar = false) {
    if (!PUEDE_EDITAR_MANO_OBRA) return;

    agregarFilaSimple("tablaMOI");

    if (enfocar) {
        const filasPadre = document.querySelectorAll("#cuerpoTablaMOI .fila-padre-moi:not(.fila-eliminada-moi)");
        const ultimaFila = filasPadre[filasPadre.length - 1];
        const input = ultimaFila?.querySelector(".servicio-busqueda-input");

        if (input) input.focus();
    }
}

function agregarFilaMOE(enfocar = false) {
    if (!PUEDE_EDITAR_MANO_OBRA) return;

    agregarFilaSimple("tablaMOE");

    if (enfocar) {
        const filas = document.querySelectorAll("#cuerpoTablaMOE tr:not(.fila-eliminada-moe)");
        const ultimaFila = filas[filas.length - 1];
        const input = ultimaFila?.querySelector(".servicio-busqueda-input");

        if (input) input.focus();
    }
}

function agregarFilaSimple(idTabla) {
    if (!PUEDE_EDITAR_MANO_OBRA) return;

    const tbody = document.querySelector(`#${idTabla} tbody`);
    if (!tbody) return;

    const isMoi = idTabla === "tablaMOI";
    const prefix = isMoi ? "moi" : "moe";
    const parentIndex = Date.now();
    const placeholder = isMoi ? "Buscar servicio interno..." : "Buscar servicio externo...";
    const clasePadre = isMoi ? "fila-padre-moi" : "fila-padre-moe";
    const dataUid = isMoi ? `data-uid-moi="${parentIndex}"` : `data-uid-moe="${parentIndex}"`;
    const eliminarFn = isMoi ? "eliminarFilaMOI(this)" : "eliminarFilaMOE(this)";

    const filaPadre = `
        <tr class="${clasePadre}" ${dataUid}>
            <td class="servicio-cell">
                <input type="hidden" name="${prefix}_detalle_id[]" value="">
                <input type="hidden" name="${prefix}_delete[]" value="0">
                <input type="hidden" name="${prefix}_actualizado_en[]" value="">

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
                            onclick="${eliminarFn}">
                        ✕
                    </button>
                </div>
            </td>
        </tr>
    `;

    tbody.insertAdjacentHTML("beforeend", filaPadre);

    if (isMoi) {
        const filaHijas = `
            <tr class="fila-hijas-moi" data-parent-uid-moi="${parentIndex}">
                <td></td>
                <td>
                    <div class="procedimientos-moi" data-parent-index="${parentIndex}"></div>

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

        tbody.insertAdjacentHTML("beforeend", filaHijas);
    }
}

// =====================================================
// ELIMINAR FILAS
// =====================================================
function eliminarFilaMOI(boton) {
    if (!PUEDE_EDITAR_MANO_OBRA) return;

    const filaPadre = boton.closest("tr");
    if (!filaPadre) return;

    const uid = filaPadre.dataset.uidMoi;
    const detalleId = filaPadre.querySelector('input[name="moi_detalle_id[]"]');
    const deleteInput = filaPadre.querySelector('input[name="moi_delete[]"]');

    const filaHijas = uid
        ? document.querySelector(`tr.fila-hijas-moi[data-parent-uid-moi="${uid}"]`)
        : filaPadre.nextElementSibling;

    if (detalleId && detalleId.value) {
        if (deleteInput) deleteInput.value = "1";

        filaPadre.classList.add("fila-eliminada-moi");
        filaPadre.style.display = "none";

        if (filaHijas) {
            filaHijas.classList.add("fila-eliminada-moi");
            filaHijas.style.display = "none";
        }
    } else {
        if (filaHijas) filaHijas.remove();
        filaPadre.remove();
    }

    if (typeof recalcularTotales === "function") {
        recalcularTotales();
    }
}

function eliminarFilaMOE(boton) {
    if (!PUEDE_EDITAR_MANO_OBRA) return;

    const fila = boton.closest("tr");
    if (!fila) return;

    const detalleId = fila.querySelector('input[name="moe_detalle_id[]"]');
    const deleteInput = fila.querySelector('input[name="moe_delete[]"]');

    if (detalleId && detalleId.value) {
        if (deleteInput) deleteInput.value = "1";

        fila.classList.add("fila-eliminada-moe");
        fila.style.display = "none";
    } else {
        fila.remove();
    }

    if (typeof recalcularTotales === "function") {
        recalcularTotales();
    }
}

// =====================================================
// BUSCAR SERVICIO
// =====================================================
function buscarServicioEnFila(inputElement, prefix = "moi") {
    if (!PUEDE_EDITAR_MANO_OBRA) return;

    const query = inputElement.value.trim();
    const fila = inputElement.closest("tr");
    const dropdown = fila.querySelector(".dropdown-resultados-servicios");

    if (!dropdown) return;

    if (query.length < 2) {
        dropdown.style.display = "none";
        dropdown.innerHTML = "";
        return;
    }

    clearTimeout(timeoutBusquedaServicio);

    timeoutBusquedaServicio = setTimeout(() => {
        fetch(`/api/buscar-servicios-ot/?q=${encodeURIComponent(query)}&categoria=${prefix}`)
            .then(response => response.json())
            .then(data => {
                dropdown.innerHTML = "";

                if (data.resultados && data.resultados.length > 0) {
                    data.resultados.forEach(item => {
                        const opcion = document.createElement("div");

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
                                ${escaparHTML(item.codigo || "")}
                            </div>
                            <div style="color:#4a4a4a;">
                                ${escaparHTML(item.descripcion || "")}
                            </div>
                            <div style="font-size:10px; color:#34c759; font-weight:600; margin-top:2px;">
                                P.U. $${escaparHTML(item.precio_recomendado || item.p_u || "0.00")}
                            </div>
                        `;

                        opcion.addEventListener("click", () => {
                            seleccionarServicioEnFila(item, inputElement, prefix);
                            dropdown.style.display = "none";
                        });

                        dropdown.appendChild(opcion);
                    });

                    dropdown.style.display = "block";
                } else {
                    dropdown.innerHTML = `
                        <div style="padding:10px; color:#86868b; font-size:12px; text-align:center;">
                            No se encontraron servicios
                        </div>
                    `;
                    dropdown.style.display = "block";
                }
            })
            .catch(error => {
                console.error("Error buscando servicios:", error);
                dropdown.style.display = "none";
            });
    }, 300);
}

function seleccionarServicioEnFila(item, inputElement, prefix = "moi") {
    if (!PUEDE_EDITAR_MANO_OBRA) return;
    if (!item || !inputElement) return;

    const filaPadre = inputElement.closest("tr");
    if (!filaPadre) return;

    const servicioHidden = filaPadre.querySelector(".servicio-id-hidden");
    if (servicioHidden) servicioHidden.value = item.id || "";

    inputElement.value = item.codigo || "";

    const descripcionInput = filaPadre.querySelector(".descripcion-manual");
    if (descripcionInput) descripcionInput.value = item.descripcion || "";

    const puInput = filaPadre.querySelector(".pu");
    if (puInput) {
        puInput.value = numeroSeguro(item.precio_recomendado || item.p_u || 0).toFixed(2);
        calcularFila(puInput);
    }

    const cantidadInput = filaPadre.querySelector(".cantidad");
    if (cantidadInput && (!cantidadInput.value || cantidadInput.value === "0.00")) {
        cantidadInput.value = "1.00";
    }

    if (prefix === "moi") {
        const uid = filaPadre.dataset.uidMoi || filaPadre.querySelector('input[name="moi_uid[]"]')?.value;
        const filaHijas = uid
            ? document.querySelector(`tr.fila-hijas-moi[data-parent-uid-moi="${uid}"]`)
            : filaPadre.nextElementSibling;

        if (filaHijas && filaHijas.classList.contains("fila-hijas-moi")) {
            const contenedor = filaHijas.querySelector(".procedimientos-moi");
            const botonAgregar = filaHijas.querySelector('button[onclick*="agregarProcedimientoMOI"]');

            if (contenedor) {
                contenedor.innerHTML = "";

                if (Array.isArray(item.procedimientos) && botonAgregar) {
                    item.procedimientos.forEach(proc => {
                        agregarProcedimientoMOI(
                            botonAgregar,
                            proc.descripcion || ""
                        );
                    });
                }
            }
        }
    }

    if (typeof recalcularTotales === "function") {
        recalcularTotales();
    }
}

// =====================================================
// PROCEDIMIENTOS MOI
// =====================================================
function agregarProcedimientoMOI(boton, texto = "") {
    if (!PUEDE_EDITAR_MANO_OBRA) return;

    const filaHijas = boton?.closest(".fila-hijas-moi");
    if (!filaHijas) return;

    const contenedor = filaHijas.querySelector(".procedimientos-moi");
    if (!contenedor) return;

    const uid = contenedor.dataset.parentIndex;

    if (!uid && uid !== "0") {
        console.error("No existe data-parent-index en procedimientos-moi");
        return;
    }

    const html = `
        <div class="procedimiento-item-moi">
            <input type="hidden" name="moi_procedimiento_id_${uid}[]" value="">
            <input type="hidden" name="moi_procedimiento_delete_${uid}[]" value="0">
            <input type="hidden" name="moi_procedimiento_actualizado_en_${uid}[]" value="">

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

    contenedor.insertAdjacentHTML("beforeend", html);
}

function eliminarProcedimientoMOI(boton) {
    if (!PUEDE_EDITAR_MANO_OBRA) return;

    const item = boton.closest(".procedimiento-item-moi");
    if (!item) return;

    const procId = item.querySelector('input[name^="moi_procedimiento_id_"]');
    const deleteInput = item.querySelector('input[name^="moi_procedimiento_delete_"]');

    if (procId && procId.value) {
        if (deleteInput) deleteInput.value = "1";

        item.classList.add("procedimiento-eliminado-moi");
        item.style.display = "none";
    } else {
        item.remove();
    }
}

// =====================================================
// MODAL MOI
// =====================================================
function abrirModalIngresoRapidoMOI() {
    if (!PUEDE_EDITAR_MANO_OBRA) return;

    const modal = document.getElementById("modalIngresoRapidoMOI");
    if (modal) modal.style.display = "flex";

    const input = document.getElementById("irmoi_descripcion");
    if (input) setTimeout(() => input.focus(), 100);
}

function cerrarModalIngresoRapidoMOI() {
    const modal = document.getElementById("modalIngresoRapidoMOI");
    if (modal) modal.style.display = "none";

    const descripcion = document.getElementById("irmoi_descripcion");
    const precio = document.getElementById("irmoi_precio");
    const cantidad = document.getElementById("irmoi_cantidad");

    if (descripcion) descripcion.value = "";
    if (precio) precio.value = "0.00";
    if (cantidad) cantidad.value = "1";
}

function confirmarIngresoRapidoMOI() {
    if (!PUEDE_EDITAR_MANO_OBRA) return;

    const descripcion = document.getElementById("irmoi_descripcion").value.trim();
    const precio = numeroSeguro(document.getElementById("irmoi_precio").value);
    const cantidad = numeroSeguro(document.getElementById("irmoi_cantidad").value);

    if (!descripcion) {
        alert("La descripción es obligatoria.");
        return;
    }

    const tbody = document.getElementById("cuerpoTablaMOI");
    if (!tbody) return;

    const parentIndex = Date.now();
    const subtotal = (precio * cantidad).toFixed(2);

    const html = `
        <tr class="fila-padre-moi" data-uid-moi="${parentIndex}">
            <td class="servicio-cell">
                <input type="hidden" name="moi_detalle_id[]" value="">
                <input type="hidden" name="moi_delete[]" value="0">
                <input type="hidden" name="moi_actualizado_en[]" value="">

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
                            onclick="eliminarFilaMOI(this)">
                        ✕
                    </button>
                </div>
            </td>
        </tr>

        <tr class="fila-hijas-moi" data-parent-uid-moi="${parentIndex}">
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

    tbody.insertAdjacentHTML("beforeend", html);

    if (typeof recalcularTotales === "function") {
        recalcularTotales();
    }

    cerrarModalIngresoRapidoMOI();
}

// =====================================================
// MODAL MOE
// =====================================================
function abrirModalIngresoRapidoMOE() {
    if (!PUEDE_EDITAR_MANO_OBRA) return;

    const modal = document.getElementById("modalIngresoRapidoMOE");
    if (modal) modal.style.display = "flex";

    const input = document.getElementById("irmoe_descripcion");
    if (input) setTimeout(() => input.focus(), 100);
}

function cerrarModalIngresoRapidoMOE() {
    const modal = document.getElementById("modalIngresoRapidoMOE");
    if (modal) modal.style.display = "none";

    const descripcion = document.getElementById("irmoe_descripcion");
    const precio = document.getElementById("irmoe_precio");
    const cantidad = document.getElementById("irmoe_cantidad");

    if (descripcion) descripcion.value = "";
    if (precio) precio.value = "0.00";
    if (cantidad) cantidad.value = "1";
}

function confirmarIngresoRapidoMOE() {
    if (!PUEDE_EDITAR_MANO_OBRA) return;

    const descripcion = document.getElementById("irmoe_descripcion").value.trim();
    const precio = numeroSeguro(document.getElementById("irmoe_precio").value);
    const cantidad = numeroSeguro(document.getElementById("irmoe_cantidad").value);

    if (!descripcion) {
        alert("La descripción es obligatoria.");
        return;
    }

    const tbody = document.getElementById("cuerpoTablaMOE");
    if (!tbody) return;

    const uid = Date.now();
    const subtotal = (precio * cantidad).toFixed(2);

    const html = `
        <tr class="fila-padre-moe" data-uid-moe="${uid}">
            <td class="servicio-cell">
                <input type="hidden" name="moe_detalle_id[]" value="">
                <input type="hidden" name="moe_delete[]" value="0">
                <input type="hidden" name="moe_actualizado_en[]" value="">

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
                            onclick="eliminarFilaMOE(this)">
                        ✕
                    </button>
                </div>
            </td>
        </tr>
    `;

    tbody.insertAdjacentHTML("beforeend", html);

    if (typeof recalcularTotales === "function") {
        recalcularTotales();
    }

    cerrarModalIngresoRapidoMOE();
}