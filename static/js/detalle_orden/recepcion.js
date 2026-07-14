console.log("RECEPCION JS CARGADO");
function abrirModalRecepcion() {
    renderModalListas();

    const modal = document.getElementById('modalEditarRecepcion');

    if (modal) {
        modal.style.display = 'flex';
    }
}

function cerrarModalRecepcion() {
    const modal = document.getElementById('modalEditarRecepcion');

    if (modal) {
        modal.style.display = 'none';
    }
}

function renderModalListas() {
    const listS = document.getElementById('modal_lista_sintomas');
    const listT = document.getElementById('modal_lista_trabajos');

    if (!listS || !listT) return;

    if (modalSintomas.length === 0) {
        listS.innerHTML = `
            <div style="color: var(--muted); font-size: 0.8rem; font-style: italic;">
                No hay síntomas registrados.
            </div>
        `;
    } else {
        listS.innerHTML = modalSintomas.map((s, i) => `
            <div class="modal-item-row">
                <span style="font-weight: 500; color: var(--text);">
                    • ${s}
                </span>

                <span onclick="modalEliminarSintoma(${i})"
                      style="color:var(--danger); cursor:pointer; font-weight:bold; font-size:1.1rem; padding:0 5px;"
                      title="Eliminar">
                    &times;
                </span>
            </div>
        `).join('');
    }

    if (modalTrabajos.length === 0) {
        listT.innerHTML = `
            <div style="color: var(--muted); font-size: 0.8rem; font-style: italic;">
                No hay trabajos registrados.
            </div>
        `;
    } else {
        listT.innerHTML = modalTrabajos.map((t, i) => `
            <div class="modal-item-row">
                <span style="font-weight: 500; color: var(--text);">
                    • ${t}
                </span>

                <span onclick="modalEliminarTrabajo(${i})"
                      style="color:var(--danger); cursor:pointer; font-weight:bold; font-size:1.1rem; padding:0 5px;"
                      title="Eliminar">
                    &times;
                </span>
            </div>
        `).join('');
    }
}

function modalAgregarSintoma() {
    const txt = document.getElementById('add_sintoma_txt');

    if (!txt) return;

    if (txt.value.trim()) {
        modalSintomas.push(txt.value.trim());
        txt.value = '';
        renderModalListas();
    }
}

function modalAgregarTrabajo() {
    const txt = document.getElementById('add_trabajo_txt');

    if (!txt) return;

    if (txt.value.trim()) {
        modalTrabajos.push(txt.value.trim());
        txt.value = '';
        renderModalListas();
    }
}

function modalEliminarSintoma(i) {
    modalSintomas.splice(i, 1);
    renderModalListas();
}

function modalEliminarTrabajo(i) {
    modalTrabajos.splice(i, 1);
    renderModalListas();
}

function guardarEdicionRapida() {
    const btn = document.getElementById('btnGuardarEdicionRapida');

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `
            <i class="spinner-border spinner-border-sm" style="margin-right: 5px;"></i>
            Actualizando...
        `;
    }

    const sintomasInput = document.getElementById('modal_sintomas_json');
    const trabajosInput = document.getElementById('modal_trabajos_json');
    const form = document.getElementById('formEdicionRapida');

    if (sintomasInput) {
        sintomasInput.value = JSON.stringify(
            modalSintomas.map(s => ({
                descripcion: s
            }))
        );
    }

    if (trabajosInput) {
        trabajosInput.value = JSON.stringify(
            modalTrabajos.map(t => ({
                descripcion: t
            }))
        );
    }

    if (form) {
        form.submit();
    }
}
function agregarTrabajoManualComoCheckbox() {
    const input = document.getElementById("nuevo_trabajo_manual");
    const grid = document.getElementById("grid_trabajos_realizar");

    if (!input || !grid) return;

    const descripcion = input.value.trim();

    if (descripcion === "") return;

    const existe = Array.from(
        grid.querySelectorAll(".trabajo-checkbox")
    ).some(c => c.value.toLowerCase() === descripcion.toLowerCase());

    if (existe) {
        alert("Ese trabajo ya existe.");
        return;
    }

    const label = document.createElement("label");
    label.className = "badge-trabajo";

    label.innerHTML = `
        <input
            type="checkbox"
            class="trabajo-checkbox"
            value="${descripcion}"
            checked>
        ${descripcion}
    `;

    grid.appendChild(label);

    input.value = "";
    input.focus();
}