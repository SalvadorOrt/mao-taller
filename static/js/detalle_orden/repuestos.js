let inputActivoBusqueda = null;
let timeoutBusquedaProducto = null;

const PUEDE_EDITAR_OT =
    document.querySelector(".ot-wrapper")?.dataset.puedeEditar === "true";

const floatingDropdown = document.getElementById("productoFloatingDropdown");

// =====================================================
// AGREGAR FILA REPUESTO
// =====================================================
function agregarFilaRepuesto(enfocar = false) {
    if (!PUEDE_EDITAR_OT) return;

    const tbody = document.querySelector("#tablaRepuestos tbody");
    if (!tbody) return;

    const filaHtml = `
        <tr>
            <td class="producto-cell">
                <input type="hidden" name="rep_producto_id[]" class="producto-id-hidden" value="">
                <input type="hidden" name="rep_categoria_id[]" value="">
                <input type="hidden" name="rep_codigo_barras[]" value="">
                <input type="hidden" name="rep_codigo_empaque[]" value="">

                <div class="producto-busqueda-wrap">
                    <input type="text"
                           class="form-control-apple producto-busqueda-input"
                           placeholder="Código / barras / nombre"
                           autocomplete="off"
                           oninput="buscarProductoEnFila(this)"
                           onkeydown="manejarTeclaBusquedaProducto(event, this)"
                           onfocus="buscarProductoEnFila(this)">
                </div>
            </td>

            <td>
                <input type="text"
                       name="rep_descripcion[]"
                       class="form-control-apple descripcion-manual"
                       placeholder="Descripción del repuesto">
            </td>

            <td>
                <div class="stock-chip stock-view">0</div>
            </td>

            <td>
                <input type="text"
                       inputmode="decimal"
                       name="rep_pu[]"
                       class="form-control-apple pu"
                       value="0.00"
                       oninput="calcularFila(this)">
            </td>

            <td>
                <input type="text"
                       inputmode="decimal"
                       name="rep_cantidad[]"
                       class="form-control-apple cantidad"
                       value="1.00"
                       oninput="calcularFila(this)">
            </td>

            <td>
                <input type="text"
                       inputmode="decimal"
                       name="rep_valor[]"
                       class="form-control-apple valor"
                       value="0.00"
                       readonly>
            </td>

            <td>
                <div class="row-controls">
                    ${PUEDE_EDITAR_OT ? `
                        <button type="button"
                                class="btn-login danger small"
                                onclick="eliminarFila(this)"
                                title="Quitar">
                            ✕
                        </button>
                    ` : ""}
                </div>
            </td>
        </tr>
    `;

    tbody.insertAdjacentHTML("beforeend", filaHtml);

    if (enfocar) {
        setTimeout(() => {
            const filas = tbody.querySelectorAll("tr");
            const ultimaFila = filas[filas.length - 1];
            const input = ultimaFila?.querySelector(".producto-busqueda-input");

            if (input) input.focus();
        }, 50);
    }
}

// =====================================================
// BUSCAR PRODUCTO
// =====================================================
async function buscarProductoEnFila(input) {
    if (!PUEDE_EDITAR_OT) return;

    const texto = (input.value || "").trim();

    if (texto.length < 2) {
        ocultarDropdownFlotante();
        return;
    }

    inputActivoBusqueda = input;
    posicionarDropdownFlotante(input);

    clearTimeout(timeoutBusquedaProducto);

    timeoutBusquedaProducto = setTimeout(async () => {
        try {
            const response = await fetch(
                `/api/buscar-repuestos?q=${encodeURIComponent(texto)}`
            );

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            const resultados = data.resultados || [];

            if (resultados.length > 0) {
                if (resultados[0].match_exacto === true) {
                    seleccionarProductoEnFilaDesdeObjeto(resultados[0]);
                    agregarFilaRepuesto(true);
                    return;
                }

                renderDropdownFlotante(input, resultados);
            } else if (floatingDropdown) {
                floatingDropdown.innerHTML = `
                    <div class="sin-resultados">
                        Sin coincidencias en inventario
                    </div>
                `;

                floatingDropdown.style.display = "block";
            }

        } catch (error) {
            console.error("Error buscando productos:", error);
            ocultarDropdownFlotante();
        }
    }, 250);
}

// =====================================================
// RENDER DROPDOWN
// =====================================================
function renderDropdownFlotante(input, resultados) {
    if (!PUEDE_EDITAR_OT) return;
    if (!floatingDropdown) return;

    floatingDropdown.innerHTML = resultados.map((item, index) => {
        const precio = item.precio_venta || item.p_u || "0.00";

        return `
            <div class="producto-sugerencia-item ${index === 0 ? "active" : ""}"
                 data-item='${JSON.stringify(item).replace(/'/g, "&apos;")}'
                 onclick="seleccionarProductoEnFilaDesdeObjeto(JSON.parse(this.dataset.item))">

                <div class="producto-sugerencia-codigo">
                    ${item.codigo || ""}
                </div>

                <div class="producto-sugerencia-extra">
                    ${item.descripcion || ""}
                    ·
                    <strong>Stock: ${item.stock || 0}</strong>
                    ·
                    $${precio}
                </div>
            </div>
        `;
    }).join("");

    floatingDropdown.style.display = "block";
}

// =====================================================
// SELECCIONAR PRODUCTO
// =====================================================
function seleccionarProductoEnFilaDesdeObjeto(item) {
    if (!PUEDE_EDITAR_OT) return;
    if (!inputActivoBusqueda || !item) return;

    const fila = inputActivoBusqueda.closest("tr");
    if (!fila) return;

    const precio = item.precio_venta || item.p_u || 0;
    const descripcion = item.descripcion || "";
    const codigo = item.codigo || "";

    const hidden = fila.querySelector(".producto-id-hidden");
    const inputBusqueda = fila.querySelector(".producto-busqueda-input");
    const descripcionInput = fila.querySelector(".descripcion-manual");
    const puInput = fila.querySelector(".pu");
    const stockView = fila.querySelector(".stock-view");

    if (hidden) hidden.value = item.id || "";

    if (inputBusqueda) {
        const descripcionCorta = descripcion.includes("-")
            ? descripcion.split("-")[0].trim()
            : descripcion;

        inputBusqueda.value = `${codigo} - ${descripcionCorta}`.trim();
    }

    if (descripcionInput) {
        descripcionInput.value = descripcion;
    }

    if (puInput) {
        puInput.value = Number(precio || 0).toFixed(2);
    }

    if (stockView) {
        stockView.textContent = item.stock || 0;
    }

    ocultarDropdownFlotante();

    if (typeof recalcularFilaDesdeTr === "function") {
        recalcularFilaDesdeTr(fila);
    }

    if (typeof recalcularTotales === "function") {
        recalcularTotales();
    }
}

// =====================================================
// TECLAS
// =====================================================
function manejarTeclaBusquedaProducto(event, input) {
    if (!PUEDE_EDITAR_OT) return;
    if (!floatingDropdown) return;

    const items = Array.from(
        floatingDropdown.querySelectorAll(".producto-sugerencia-item")
    );

    if (event.key === "Enter") {
        event.preventDefault();

        if (items.length > 0 && floatingDropdown.style.display === "block") {
            const activeItem =
                items.find(item => item.classList.contains("active")) || items[0];

            if (activeItem) {
                seleccionarProductoEnFilaDesdeObjeto(
                    JSON.parse(activeItem.dataset.item)
                );

                agregarFilaRepuesto(true);
            }
        }

        return;
    }

    if (!items.length || floatingDropdown.style.display !== "block") return;

    let activeIndex = items.findIndex(
        item => item.classList.contains("active")
    );

    if (activeIndex < 0) activeIndex = 0;

    if (event.key === "ArrowDown") {
        event.preventDefault();
        items[activeIndex]?.classList.remove("active");
        activeIndex = (activeIndex + 1) % items.length;
        items[activeIndex].classList.add("active");
        items[activeIndex].scrollIntoView({ block: "nearest" });
    }

    if (event.key === "ArrowUp") {
        event.preventDefault();
        items[activeIndex]?.classList.remove("active");
        activeIndex = (activeIndex - 1 + items.length) % items.length;
        items[activeIndex].classList.add("active");
        items[activeIndex].scrollIntoView({ block: "nearest" });
    }

    if (event.key === "Escape") {
        ocultarDropdownFlotante();
    }
}

// =====================================================
// DROPDOWN HELPERS
// =====================================================
function ocultarDropdownFlotante() {
    if (!floatingDropdown) return;

    floatingDropdown.style.display = "none";
    floatingDropdown.innerHTML = "";
}

function posicionarDropdownFlotante(input) {
    if (!PUEDE_EDITAR_OT) return;
    if (!floatingDropdown || !input) return;

    const rect = input.getBoundingClientRect();

    floatingDropdown.style.top = `${rect.bottom + 4}px`;
    floatingDropdown.style.left = `${rect.left}px`;
    floatingDropdown.style.width = `${rect.width}px`;
}

// =====================================================
// EVENTOS GLOBALES
// =====================================================
document.addEventListener("click", function (e) {
    if (
        floatingDropdown &&
        !floatingDropdown.contains(e.target) &&
        !e.target.classList.contains("producto-busqueda-input")
    ) {
        ocultarDropdownFlotante();
    }
});

window.addEventListener("resize", function () {
    if (
        inputActivoBusqueda &&
        floatingDropdown &&
        floatingDropdown.style.display === "block"
    ) {
        posicionarDropdownFlotante(inputActivoBusqueda);
    }
});

window.addEventListener("scroll", function () {
    if (
        inputActivoBusqueda &&
        floatingDropdown &&
        floatingDropdown.style.display === "block"
    ) {
        posicionarDropdownFlotante(inputActivoBusqueda);

        const rect = inputActivoBusqueda.getBoundingClientRect();

        if (rect.bottom < 0 || rect.top > window.innerHeight) {
            ocultarDropdownFlotante();
        }
    }
}, true);