// =========================================================
// precios.js
//
// Consulta histórica de precios para:
//
// - REP  -> Repuestos
// - MOI  -> Mano de obra interna
// - MOE  -> Mano de obra externa
//
// Funciones principales:
//
// 1. Agrega automáticamente una lupa junto al P.U.
// 2. Detecta filas nuevas creadas dinámicamente.
// 3. Obtiene los datos de la fila.
// 4. Para MOI recoge también sus procedimientos.
// 5. Consulta el backend.
// 6. Llena el modal consulta_precios.html.
// 7. Permite aplicar el precio sugerido o un antecedente.
// =========================================================


// =========================================================
// ESTADO GLOBAL
// =========================================================

let filaConsultaPrecioActiva = null;

let tipoConsultaPrecioActivo = null;

let precioSugeridoActual = null;

let overflowBodyAntesModalPrecio = '';


// =========================================================
// UTILIDADES
// =========================================================

function escaparHTMLPrecio(valor) {

    return String(
        valor ?? ''
    )
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}


function textoSeguroPrecio(valor) {

    return String(
        valor ?? ''
    ).trim();
}


function numeroPrecio(valor) {

    if (
        valor === null ||
        valor === undefined ||
        valor === ''
    ) {
        return null;
    }

    const texto = String(valor)
        .trim()
        .replace(',', '.');

    const numero = Number(texto);

    return Number.isFinite(numero)
        ? numero
        : null;
}


function enteroOpcionalPrecio(valor) {

    const texto = String(
        valor ?? ''
    ).trim();

    if (!texto) {
        return null;
    }

    const numero = Number.parseInt(
        texto,
        10
    );

    return Number.isFinite(numero)
        ? numero
        : null;
}


function dineroPrecio(valor) {

    const numero = numeroPrecio(
        valor
    );

    if (numero === null) {
        return '-';
    }

    return (
        '$' +
        numero.toLocaleString(
            'es-EC',
            {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            }
        )
    );
}


function kilometrajePrecio(valor) {

    const numero = numeroPrecio(
        valor
    );

    if (numero === null) {
        return '-';
    }

    return Math.round(
        numero
    ).toLocaleString(
        'es-EC'
    ) + ' km';
}


function fechaPrecio(valor) {

    if (!valor) {
        return '-';
    }

    const texto = String(
        valor
    ).trim();

    /*
     * Si Django envía YYYY-MM-DD evitamos
     * problemas de zona horaria.
     */
    const coincidencia = texto.match(
        /^(\d{4})-(\d{2})-(\d{2})/
    );

    if (coincidencia) {

        return [
            coincidencia[3],
            coincidencia[2],
            coincidencia[1]
        ].join('/');
    }

    const fecha = new Date(
        texto
    );

    if (
        Number.isNaN(
            fecha.getTime()
        )
    ) {
        return texto;
    }

    return fecha.toLocaleDateString(
        'es-EC'
    );
}


// =========================================================
// CSRF
// =========================================================

function obtenerCsrfTokenPrecio() {

    const input = document.querySelector(
        'input[name="csrfmiddlewaretoken"]'
    );

    if (
        input &&
        input.value
    ) {
        return input.value;
    }

    const nombre = 'csrftoken=';

    const cookies = document.cookie
        .split(';');

    for (
        const cookieOriginal
        of cookies
    ) {

        const cookie =
            cookieOriginal.trim();

        if (
            cookie.startsWith(
                nombre
            )
        ) {
            return decodeURIComponent(
                cookie.substring(
                    nombre.length
                )
            );
        }
    }

    return '';
}


// =========================================================
// MODAL
// =========================================================

function obtenerModalConsultaPrecios() {

    return document.getElementById(
        'modalConsultaPrecios'
    );
}


function abrirModalConsultaPrecios() {

    const modal =
        obtenerModalConsultaPrecios();

    if (!modal) {
        console.error(
            'No existe #modalConsultaPrecios.'
        );

        return;
    }

    overflowBodyAntesModalPrecio =
        document.body.style.overflow;

    document.body.style.overflow =
        'hidden';

    modal.style.display =
        'flex';
}


function cerrarModalConsultaPrecios() {

    const modal =
        obtenerModalConsultaPrecios();

    if (modal) {
        modal.style.display =
            'none';
    }

    document.body.style.overflow =
        overflowBodyAntesModalPrecio;

    /*
     * Conservamos la fila activa solo durante
     * el uso del modal.
     */
    filaConsultaPrecioActiva = null;

    tipoConsultaPrecioActivo = null;

    precioSugeridoActual = null;
}


window.cerrarModalConsultaPrecios =
    cerrarModalConsultaPrecios;


// =========================================================
// ESTADOS DEL MODAL
// =========================================================
function ponerModalPrecioCargando() {

    // Quitar cualquier precio de la consulta anterior
    precioSugeridoActual = null;

    const cargando =
        document.getElementById(
            'consultaPreciosCargando'
        );

    const contenido =
        document.getElementById(
            'consultaPreciosContenido'
        );

    const error =
        document.getElementById(
            'consultaPreciosError'
        );

    const boton =
        document.getElementById(
            'btnAplicarPrecioSugerido'
        );

    // Mostrar "Buscando..."
    if (cargando) {
        cargando.style.display = 'block';
    }

    // Ocultar todo el resultado de la búsqueda anterior
    if (contenido) {
        contenido.style.display = 'none';
    }

    // Borrar errores anteriores
    if (error) {
        error.style.display = 'none';
        error.textContent = '';
    }

    // IMPORTANTE:
    // desactivar y limpiar el botón del precio anterior
    if (boton) {
        boton.disabled = true;

        boton.innerHTML = `
            <i
                class="bi bi-check2"
                style="margin-right:5px;"
            ></i>
            Aplicar sugerencia
        `;
    }

    // Limpiar métricas anteriores
    ponerTextoPrecio(
        'consultaPrecioSugerido',
        '-'
    );

    ponerTextoPrecio(
        'consultaUltimoPrecio',
        '-'
    );

    ponerTextoPrecio(
        'consultaMedianaPrecio',
        '-'
    );

    ponerTextoPrecio(
        'consultaRangoPrecio',
        '-'
    );

    ponerTextoPrecio(
        'consultaCantidadComparables',
        '0'
    );

    // Limpiar historial anterior
    const lista =
        document.getElementById(
            'consultaCoincidenciasLista'
        );

    if (lista) {
        lista.innerHTML = '';
    }

    const vacio =
        document.getElementById(
            'consultaCoincidenciasVacio'
        );

    if (vacio) {
        vacio.style.display = 'none';
    }

    // Ocultar inventario anterior
    const inventario =
        document.getElementById(
            'consultaInventarioBox'
        );

    if (inventario) {
        inventario.style.display = 'none';
    }

    // Ocultar catálogo anterior
    const catalogo =
        document.getElementById(
            'consultaServicioCatalogoBox'
        );

    if (catalogo) {
        catalogo.style.display = 'none';
    }
}

function ponerModalPrecioContenido() {

    const cargando =
        document.getElementById(
            'consultaPreciosCargando'
        );

    const contenido =
        document.getElementById(
            'consultaPreciosContenido'
        );

    if (cargando) {
        cargando.style.display =
            'none';
    }

    if (contenido) {
        contenido.style.display =
            'block';
    }
}


function mostrarErrorConsultaPrecio(
    mensaje
) {

    const cargando =
        document.getElementById(
            'consultaPreciosCargando'
        );

    const contenido =
        document.getElementById(
            'consultaPreciosContenido'
        );

    const error =
        document.getElementById(
            'consultaPreciosError'
        );

    if (cargando) {
        cargando.style.display =
            'none';
    }

    if (contenido) {
        contenido.style.display =
            'none';
    }

    if (error) {

        error.textContent =
            mensaje ||
            'No fue posible consultar el precio.';

        error.style.display =
            'block';
    }
}


// =========================================================
// MODIFICAR TEXTO DE FORMA SEGURA
// =========================================================

function ponerTextoPrecio(
    id,
    valor,
    valorVacio = '-'
) {

    const elemento =
        document.getElementById(
            id
        );

    if (!elemento) {
        return;
    }

    const texto =
        valor === null ||
        valor === undefined ||
        String(valor).trim() === ''
            ? valorVacio
            : String(valor);

    elemento.textContent =
        texto;
}


// =========================================================
// ESTILOS DE LA LUPA
// =========================================================

function insertarEstilosConsultaPrecio() {

    if (
        document.getElementById(
            'estilosConsultaPrecioFila'
        )
    ) {
        return;
    }

    const style =
        document.createElement(
            'style'
        );

    style.id =
        'estilosConsultaPrecioFila';

    style.textContent = `
        .precio-consulta-wrap {
            width: 100%;
            display: grid;
            grid-template-columns: minmax(0, 1fr) 34px;
            gap: 5px;
            align-items: center;
        }

        .precio-consulta-wrap > .pu {
            min-width: 0;
            width: 100%;
        }

        .btn-consultar-precio {
            width: 34px;
            height: 34px;

            display: inline-flex;
            align-items: center;
            justify-content: center;

            padding: 0;

            border: 1px solid #d2d2d7;
            border-radius: 8px;

            background: #ffffff;
            color: #0071e3;

            cursor: pointer;

            font-size: 13px;

            transition:
                background-color 0.15s ease,
                border-color 0.15s ease,
                transform 0.15s ease;
        }

        .btn-consultar-precio:hover {
            background:
                rgba(0, 113, 227, 0.08);

            border-color:
                rgba(0, 113, 227, 0.45);
        }

        .btn-consultar-precio:active {
            transform: scale(0.95);
        }

        .btn-consultar-precio:focus-visible {
            outline: 2px solid #0071e3;
            outline-offset: 2px;
        }

        .btn-consultar-precio:disabled {
            opacity: 0.45;
            cursor: default;
        }

        .fila-precio-aplicado > td {
            animation:
                filaPrecioAplicado
                0.8s ease;
        }

        @keyframes filaPrecioAplicado {
            0% {
                background:
                    rgba(52, 199, 89, 0.18);
            }

            100% {
                background: inherit;
            }
        }

        @media print {
            .btn-consultar-precio {
                display: none !important;
            }
        }

        @media (max-width: 700px) {
            .precio-consulta-wrap {
                grid-template-columns:
                    minmax(64px, 1fr)
                    32px;

                gap: 4px;
            }

            .btn-consultar-precio {
                width: 32px;
                height: 32px;
            }
        }
    `;

    document.head.appendChild(
        style
    );
}


// =========================================================
// DETERMINAR TIPO DE FILA
// =========================================================

function obtenerTipoConsultaFila(
    fila
) {

    if (!fila) {
        return null;
    }

    if (
        fila.closest(
            '#tablaRepuestos'
        )
    ) {
        return 'REP';
    }

    if (
        fila.classList.contains(
            'fila-padre-moi'
        )
    ) {
        return 'MOI';
    }

    if (
        fila.classList.contains(
            'fila-padre-moe'
        )
    ) {
        return 'MOE';
    }

    return null;
}


// =========================================================
// DECORAR UNA FILA CON LUPA
// =========================================================

function decorarFilaConsultaPrecio(
    fila
) {

    if (!fila) {
        return;
    }

    /*
     * Nunca ponemos lupa en procedimientos.
     */
    if (
        fila.classList.contains(
            'fila-hijas-moi'
        )
    ) {
        return;
    }

    /*
     * No decoramos filas históricas de la OT actual
     * porque son de solo lectura.
     */
    if (
        fila.classList.contains(
            'form-readonly'
        )
    ) {
        return;
    }

    const tipo =
        obtenerTipoConsultaFila(
            fila
        );

    if (!tipo) {
        return;
    }

    const nombrePrecio = (
        tipo === 'REP'
            ? 'rep_pu[]'
            : tipo === 'MOI'
                ? 'moi_pu[]'
                : 'moe_pu[]'
    );

    const inputPrecio =
        fila.querySelector(
            `input[name="${nombrePrecio}"]`
        );

    if (!inputPrecio) {
        return;
    }

    /*
     * Ya fue procesada.
     */
    if (
        inputPrecio.closest(
            '.precio-consulta-wrap'
        )
    ) {
        return;
    }

    const padre =
        inputPrecio.parentElement;

    if (!padre) {
        return;
    }

    const wrapper =
        document.createElement(
            'div'
        );

    wrapper.className =
        'precio-consulta-wrap';

    padre.insertBefore(
        wrapper,
        inputPrecio
    );

    wrapper.appendChild(
        inputPrecio
    );

    const boton =
        document.createElement(
            'button'
        );

    boton.type =
        'button';

    boton.className =
        'btn-consultar-precio';

    boton.dataset.tipo =
        tipo;

    boton.title =
        'Consultar precio';

    boton.setAttribute(
        'aria-label',
        'Consultar precio'
    );

    boton.innerHTML = `
        <i class="bi bi-search"></i>
    `;

    wrapper.appendChild(
        boton
    );
}


// =========================================================
// DECORAR TODAS LAS FILAS
// =========================================================

function decorarFilasConsultaPrecio() {

    /*
     * La función de consulta está destinada a una OT
     * editable, porque su fin es aplicar un P.U.
     */
    const modal =
        obtenerModalConsultaPrecios();

    if (!modal) {
        return;
    }

    const puedeEditar =
        String(
            modal.dataset.puedeEditar ||
            ''
        ).toLowerCase() === 'true';

    if (!puedeEditar) {
        return;
    }

    document.querySelectorAll(
        [
            '#cuerpoTablaRepuestos tr.fila-repuesto',
            '#cuerpoTablaMOI tr.fila-padre-moi',
            '#cuerpoTablaMOE tr.fila-padre-moe'
        ].join(',')
    ).forEach(
        decorarFilaConsultaPrecio
    );
}


// =========================================================
// OBSERVAR NUEVAS FILAS
// =========================================================

function iniciarObservadorConsultaPrecio() {

    const formulario =
        document.getElementById(
            'formDetalleOT'
        );

    if (!formulario) {
        return;
    }

    const observer =
        new MutationObserver(
            function (
                mutaciones
            ) {

                const cambioEstructural =
                    mutaciones.some(
                        function (
                            mutacion
                        ) {
                            return (
                                mutacion.type ===
                                'childList'
                            );
                        }
                    );

                if (
                    cambioEstructural
                ) {
                    decorarFilasConsultaPrecio();
                }
            }
        );

    observer.observe(
        formulario,
        {
            childList: true,
            subtree: true
        }
    );
}


// =========================================================
// OBTENER CÓDIGO DEL REPUESTO
// =========================================================

function obtenerCodigoRepuesto(
    fila
) {

    const codigoBarras =
        textoSeguroPrecio(
            fila.querySelector(
                'input[name="rep_codigo_barras[]"]'
            )?.value
        );

    const codigoEmpaque =
        textoSeguroPrecio(
            fila.querySelector(
                'input[name="rep_codigo_empaque[]"]'
            )?.value
        );

    if (codigoEmpaque) {
        return codigoEmpaque;
    }

    if (codigoBarras) {
        return codigoBarras;
    }

    /*
     * Repuesto seleccionado desde inventario.
     * Actualmente el buscador muestra normalmente:
     *
     * CODIGO - DESCRIPCION
     */
    const buscador =
        textoSeguroPrecio(
            fila.querySelector(
                '.producto-busqueda-input'
            )?.value
        );

    if (buscador) {

        const partes =
            buscador.split(' - ');

        return textoSeguroPrecio(
            partes[0]
        );
    }

    /*
     * Ingreso rápido manual que tenga código.
     */
    const manual =
        textoSeguroPrecio(
            fila.querySelector(
                '.producto-manual'
            )?.textContent
        );

    if (
        manual &&
        !manual.includes(
            'TEXTO LIBRE'
        ) &&
        !manual.includes(
            'MANUAL'
        )
    ) {
        return manual;
    }

    return '';
}


// =========================================================
// PROCEDIMIENTOS MOI
// =========================================================

function obtenerProcedimientosMOI(
    filaPadre
) {

    const uid =
        textoSeguroPrecio(
            filaPadre.dataset.uidMoi
        ) ||
        textoSeguroPrecio(
            filaPadre.querySelector(
                'input[name="moi_uid[]"]'
            )?.value
        );

    if (!uid) {
        return [];
    }

    const filaHijas =
        document.querySelector(
            'tr.fila-hijas-moi' +
            `[data-parent-uid-moi="${CSS.escape(uid)}"]`
        );

    if (!filaHijas) {
        return [];
    }

    const procedimientos = [];

    filaHijas.querySelectorAll(
        '.procedimiento-item-moi'
    ).forEach(
        function (
            item
        ) {

            if (
                item.classList.contains(
                    'procedimiento-eliminado-moi'
                ) ||
                item.dataset.eliminada ===
                    '1' ||
                item.hidden ||
                item.style.display ===
                    'none'
            ) {
                return;
            }

            const deleteInput =
                item.querySelector(
                    'input[name^="moi_procedimiento_delete_"]'
                );

            if (
                deleteInput &&
                String(
                    deleteInput.value ||
                    ''
                ) === '1'
            ) {
                return;
            }

            const inputTexto =
                item.querySelector(
                    'input[name^="moi_procedimientos_"]'
                ) ||
                item.querySelector(
                    'input[type="text"]'
                );

            const texto =
                textoSeguroPrecio(
                    inputTexto?.value
                );

            if (texto) {
                procedimientos.push(
                    texto
                );
            }
        }
    );

    return procedimientos;
}


// =========================================================
// OBTENER VARIANTE, SI EXISTE
// =========================================================

function obtenerVarianteServicio(
    fila,
    tipo
) {

    const prefijo =
        tipo === 'MOI'
            ? 'moi'
            : 'moe';

    const selectores = [
        `[name="${prefijo}_variante[]"]`,
        `[name="${prefijo}_variante_precio[]"]`,
        '.variante-precio',
        '[data-variante-precio]'
    ];

    for (
        const selector
        of selectores
    ) {

        const elemento =
            fila.querySelector(
                selector
            );

        if (!elemento) {
            continue;
        }

        const valor =
            textoSeguroPrecio(
                elemento.value ||
                elemento.dataset
                    ?.variantePrecio
            );

        if (valor) {
            return valor;
        }
    }

    return 'NORMAL';
}


// =========================================================
// CONSTRUIR PAYLOAD
// =========================================================

function construirPayloadConsultaPrecio(
    fila,
    tipo
) {

    const modal =
        obtenerModalConsultaPrecios();

    if (!modal) {
        throw new Error(
            'No se encontró el modal de consulta.'
        );
    }

    const ordenId =
        enteroOpcionalPrecio(
            modal.dataset.ordenId
        );

    if (!ordenId) {
        throw new Error(
            'No se pudo identificar la orden.'
        );
    }

    let descripcion = '';

    let codigo = '';

    let codigoProductoId = null;

    let servicioId = null;

    let variante = 'NORMAL';

    let procedimientos = [];


    // =====================================================
    // REPUESTO
    // =====================================================

    if (tipo === 'REP') {

        descripcion =
            textoSeguroPrecio(
                fila.querySelector(
                    'input[name="rep_descripcion[]"]'
                )?.value
            );

        codigo =
            obtenerCodigoRepuesto(
                fila
            );

        codigoProductoId =
            enteroOpcionalPrecio(
                fila.querySelector(
                    'input[name="rep_producto_id[]"]'
                )?.value
            );
    }


    // =====================================================
    // MOI
    // =====================================================

    else if (tipo === 'MOI') {

        descripcion =
            textoSeguroPrecio(
                fila.querySelector(
                    'input[name="moi_descripcion[]"]'
                )?.value
            );

        servicioId =
            enteroOpcionalPrecio(
                fila.querySelector(
                    'input[name="moi_servicio_id[]"]'
                )?.value
            );

        codigo =
            textoSeguroPrecio(
                fila.querySelector(
                    '.servicio-busqueda-input'
                )?.value
            );

        if (
            codigo.includes(
                'MANUAL'
            )
        ) {
            codigo = '';
        }

        variante =
            obtenerVarianteServicio(
                fila,
                tipo
            );

        procedimientos =
            obtenerProcedimientosMOI(
                fila
            );
    }


    // =====================================================
    // MOE
    // =====================================================

    else if (tipo === 'MOE') {

        descripcion =
            textoSeguroPrecio(
                fila.querySelector(
                    'input[name="moe_descripcion[]"]'
                )?.value
            );

        servicioId =
            enteroOpcionalPrecio(
                fila.querySelector(
                    'input[name="moe_servicio_id[]"]'
                )?.value
            );

        codigo =
            textoSeguroPrecio(
                fila.querySelector(
                    '.servicio-busqueda-input'
                )?.value
            );

        if (
            codigo.includes(
                'MANUAL'
            )
        ) {
            codigo = '';
        }

        variante =
            obtenerVarianteServicio(
                fila,
                tipo
            );
    }


    if (!descripcion) {

        throw new Error(
            tipo === 'REP'
                ? 'Escriba primero la descripción del repuesto.'
                : 'Escriba primero la descripción del servicio.'
        );
    }


    return {
        orden_id: ordenId,

        tipo: tipo,

        descripcion: descripcion,

        codigo: codigo,

        codigo_producto_id:
            codigoProductoId,

        servicio_id:
            servicioId,

        variante: variante,

        procedimientos:
            procedimientos
    };
}


// =========================================================
// CONTEXTO ACTUAL DE LA OT
// =========================================================

function obtenerContextoOrdenActual() {

    const modal =
        obtenerModalConsultaPrecios();

    const vehiculo =
        textoSeguroPrecio(
            modal?.dataset.vehiculo
        ) ||
        textoSeguroPrecio(
            document.querySelector(
                '#id_vehiculo'
            )?.value
        ) ||
        textoSeguroPrecio(
            document.querySelector(
                '[name="vehiculo"]'
            )?.value
        );

    const anio =
        textoSeguroPrecio(
            modal?.dataset.anio
        ) ||
        textoSeguroPrecio(
            document.querySelector(
                '#id_anio_vehiculo'
            )?.value
        ) ||
        textoSeguroPrecio(
            document.querySelector(
                '[name="anio_vehiculo"]'
            )?.value
        );

    const kilometraje =
        textoSeguroPrecio(
            modal?.dataset.kilometraje
        ) ||
        textoSeguroPrecio(
            document.querySelector(
                '#id_kilometraje'
            )?.value
        ) ||
        textoSeguroPrecio(
            document.querySelector(
                '[name="kilometraje"]'
            )?.value
        );

    const sucursal =
        textoSeguroPrecio(
            modal?.dataset.sucursal
        );

    return {
        vehiculo,
        anio,
        kilometraje,
        sucursal
    };
}


// =========================================================
// MOSTRAR DATOS INICIALES DE LA CONSULTA
// =========================================================

function mostrarCabeceraConsultaPrecio(
    payload
) {

    ponerTextoPrecio(
        'consultaPrecioDescripcion',
        payload.descripcion
    );

    ponerTextoPrecio(
        'consultaPrecioCodigo',
        payload.codigo
            ? `Código / referencia: ${payload.codigo}`
            : 'Sin código asociado',
        ''
    );


    // =====================================================
    // TIPO
    // =====================================================

    const tipoElemento =
        document.getElementById(
            'consultaPrecioTipo'
        );

    if (tipoElemento) {

        const nombre = (
            payload.tipo === 'REP'
                ? 'REPUESTO'
                : payload.tipo === 'MOI'
                    ? 'M.O. INTERNA'
                    : 'M.O. EXTERNA'
        );

        tipoElemento.innerHTML = `
            <i class="bi bi-search"></i>
            <span>
                ${escaparHTMLPrecio(nombre)}
            </span>
        `;
    }


    // =====================================================
    // CONTEXTO
    // =====================================================

    const contexto =
        obtenerContextoOrdenActual();

    ponerTextoPrecio(
        'consultaPrecioVehiculo',
        contexto.vehiculo
    );

    ponerTextoPrecio(
        'consultaPrecioAnio',
        contexto.anio
    );

    ponerTextoPrecio(
        'consultaPrecioKilometraje',
        contexto.kilometraje
            ? kilometrajePrecio(
                contexto.kilometraje
            )
            : '-'
    );

    ponerTextoPrecio(
        'consultaPrecioSucursal',
        contexto.sucursal
    );


    // =====================================================
    // PROCEDIMIENTOS
    // =====================================================

    renderProcedimientosActuales(
        payload.procedimientos
    );
}


// =========================================================
// PROCEDIMIENTOS ACTUALES DEL MODAL
// =========================================================

function renderProcedimientosActuales(
    procedimientos
) {

    const box =
        document.getElementById(
            'consultaProcedimientosBox'
        );

    const lista =
        document.getElementById(
            'consultaProcedimientosLista'
        );

    if (
        !box ||
        !lista
    ) {
        return;
    }

    const items =
        Array.isArray(
            procedimientos
        )
            ? procedimientos.filter(
                function (
                    item
                ) {
                    return Boolean(
                        textoSeguroPrecio(
                            item
                        )
                    );
                }
            )
            : [];

    if (
        items.length === 0
    ) {

        box.style.display =
            'none';

        lista.innerHTML =
            '';

        return;
    }

    lista.innerHTML =
        items.map(
            function (
                procedimiento
            ) {

                return `
                    <div
                        class="consulta-procedimiento-item"
                    >
                        <span
                            class="consulta-procedimiento-check"
                        >
                            <i
                                class="bi bi-check2"
                            ></i>
                        </span>

                        <span>
                            ${escaparHTMLPrecio(
                                procedimiento
                            )}
                        </span>
                    </div>
                `;
            }
        ).join('');

    box.style.display =
        'block';
}


// =========================================================
// CONSULTAR
// =========================================================

async function consultarPrecioFila(
    fila,
    tipo
) {

    filaConsultaPrecioActiva =
        fila;

    tipoConsultaPrecioActivo =
        tipo;

    precioSugeridoActual =
        null;

    let payload;

    try {

        payload =
            construirPayloadConsultaPrecio(
                fila,
                tipo
            );

    } catch (error) {

        if (
            typeof Swal !==
            'undefined'
        ) {

            Swal.fire({
                title:
                    'No se puede consultar',

                text:
                    error.message,

                icon:
                    'warning',

                confirmButtonColor:
                    '#0071e3'
            });

        } else {

            alert(
                error.message
            );
        }

        filaConsultaPrecioActiva =
            null;

        tipoConsultaPrecioActivo =
            null;

        return;
    }


    mostrarCabeceraConsultaPrecio(
        payload
    );

    abrirModalConsultaPrecios();

    ponerModalPrecioCargando();


    const modal =
        obtenerModalConsultaPrecios();

    const url =
        modal?.dataset
            ?.consultaUrl;

    if (!url) {

        mostrarErrorConsultaPrecio(
            'No se encontró la URL de consulta de precios.'
        );

        return;
    }


    try {

        const respuesta =
            await fetch(
                url,
                {
                    method: 'POST',

                    headers: {
                        'Content-Type':
                            'application/json',

                        'X-CSRFToken':
                            obtenerCsrfTokenPrecio(),

                        'X-Requested-With':
                            'XMLHttpRequest'
                    },

                    body:
                        JSON.stringify(
                            payload
                        )
                }
            );


        const respuestaTexto =
        await respuesta.text();

        let respuestaJson = null;

        try {

            respuestaJson =
                respuestaTexto
                    ? JSON.parse(respuestaTexto)
                    : {};

        } catch (error) {

            console.error(
                'Respuesta no JSON del servidor:',
                {
                    status: respuesta.status,
                    statusText: respuesta.statusText,
                    url: respuesta.url,
                    contenido: respuestaTexto
                }
            );

            throw new Error(
                `El servidor respondió HTTP ${respuesta.status}. ` +
                `Revise la consola o el log de Django.`
            );
        }


        if (!respuesta.ok) {

            throw new Error(
                respuestaJson.error ||
                respuestaJson.message ||
                respuestaJson.mensaje ||
                `Error HTTP ${respuesta.status}`
            );
        }


        /*
         * Nuestra vista devuelve:
         *
         * {
         *     success: true,
         *     data: {...}
         * }
         *
         * También dejamos compatibilidad con una respuesta
         * directa para no acoplar el JS demasiado.
         */
        if (
            respuestaJson.success ===
            false
        ) {

            throw new Error(
                respuestaJson.error ||
                'No fue posible consultar el precio.'
            );
        }


        const resultado =
            respuestaJson.data ||
            respuestaJson.resultado ||
            respuestaJson;


        renderResultadoConsultaPrecio(
            resultado,
            payload
        );


    } catch (error) {

        console.error(
            'Error consultando precio:',
            error
        );

        mostrarErrorConsultaPrecio(
            error.message ||
            'No fue posible consultar el precio.'
        );
    }
}


window.consultarPrecioFila =
    consultarPrecioFila;


// =========================================================
// RENDER GENERAL
// =========================================================

function renderResultadoConsultaPrecio(
    resultado,
    payload
) {

    resultado =
        resultado || {};

    const sugerencia =
        resultado.sugerencia ||
        resultado.resumen ||
        {};

    const precioSugerido =
        numeroPrecio(
            sugerencia.precio_sugerido ??
            resultado.precio_sugerido
        );

    precioSugeridoActual =
        precioSugerido;


    // =====================================================
    // SUGERENCIA
    // =====================================================

    ponerTextoPrecio(
        'consultaPrecioSugerido',

        precioSugerido !== null
            ? dineroPrecio(
                precioSugerido
            )
            : 'Sin sugerencia'
    );


    const ayuda =
        document.getElementById(
            'consultaPrecioSugeridoAyuda'
        );

    if (ayuda) {

        ayuda.textContent =
            precioSugerido !== null
                ? (
                    'Basado en antecedentes comparables ' +
                    'encontrados en MAO.'
                )
                : (
                    'No existen suficientes antecedentes ' +
                    'comparables para recomendar un precio.'
                );
    }


    renderConfianzaPrecio(
        sugerencia.confianza ||
        resultado.confianza ||
        'BAJA'
    );


    // =====================================================
    // MÉTRICAS
    // =====================================================

    ponerTextoPrecio(
        'consultaUltimoPrecio',

        dineroPrecio(
            sugerencia.ultimo_precio
        )
    );

    ponerTextoPrecio(
        'consultaMedianaPrecio',

        dineroPrecio(
            sugerencia.mediana
        )
    );


    const minimo =
        numeroPrecio(
            sugerencia.minimo
        );

    const maximo =
        numeroPrecio(
            sugerencia.maximo
        );

    let rango = '-';

    if (
        minimo !== null &&
        maximo !== null
    ) {

        rango =
            `${dineroPrecio(minimo)} – ` +
            `${dineroPrecio(maximo)}`;
    }

    ponerTextoPrecio(
        'consultaRangoPrecio',
        rango
    );


    ponerTextoPrecio(
        'consultaCantidadComparables',

        sugerencia
            .cantidad_comparables ??
        resultado
            .cantidad_comparables ??
        0
    );


    // =====================================================
    // INVENTARIO OPCIONAL
    // =====================================================

    renderInventarioConsultaPrecio(
        resultado.inventario ||
        resultado.producto_actual ||
        resultado.repuesto_actual ||
        null
    );


    // =====================================================
    // CATÁLOGO OPCIONAL
    // =====================================================

    renderCatalogoConsultaPrecio(
        resultado.catalogo ||
        resultado.servicio_catalogo ||
        resultado.servicio_actual ||
        null
    );


    // =====================================================
    // EXPLICACIÓN
    // =====================================================

    const explicacion =
        resultado.explicacion ||
        sugerencia.explicacion ||
        '';

    const explicacionElemento =
        document.getElementById(
            'consultaExplicacionSugerencia'
        );

    if (explicacionElemento) {

        if (explicacion) {

            explicacionElemento.innerHTML = `
                <strong>
                    Cómo se obtuvo:
                </strong>
                ${escaparHTMLPrecio(
                    explicacion
                )}
            `;

        } else {

            explicacionElemento.innerHTML = `
                <strong>
                    Cómo se obtuvo:
                </strong>

                El sistema compara antecedentes históricos
                de todas las sucursales y prioriza los casos
                más parecidos al ítem actual.
            `;
        }
    }


    // =====================================================
    // COINCIDENCIAS
    // =====================================================

    const coincidencias =
        Array.isArray(
            resultado.coincidencias
        )
            ? resultado.coincidencias
            : Array.isArray(
                resultado.antecedentes
            )
                ? resultado.antecedentes
                : [];

    renderCoincidenciasPrecio(
    coincidencias,
            resultado.total_coincidencias
        );


        // =====================================================
        // ÚLTIMO ANTECEDENTE DEL MISMO VEHÍCULO
        // =====================================================

        renderAntecedenteMismoVehiculo(
            resultado.antecedente_mismo_vehiculo ||
            null
        );


        // =====================================================
        // BOTÓN PRINCIPAL
        // =====================================================

    const boton =
        document.getElementById(
            'btnAplicarPrecioSugerido'
        );

    if (boton) {

        boton.disabled =
            precioSugerido === null ||
            precioSugerido <= 0;

        if (
            precioSugerido !== null &&
            precioSugerido > 0
        ) {

            boton.innerHTML = `
                <i
                    class="bi bi-check2"
                    style="margin-right:5px;"
                ></i>

                Aplicar
                ${escaparHTMLPrecio(
                    dineroPrecio(
                        precioSugerido
                    )
                )}
            `;

        } else {

            boton.innerHTML = `
                <i
                    class="bi bi-check2"
                    style="margin-right:5px;"
                ></i>

                Aplicar sugerencia
            `;
        }
    }


    ponerModalPrecioContenido();
}


// =========================================================
// CONFIANZA
// =========================================================

function renderConfianzaPrecio(
    confianza
) {

    const elemento =
        document.getElementById(
            'consultaPrecioConfianza'
        );

    if (!elemento) {
        return;
    }

    const valor =
        textoSeguroPrecio(
            confianza
        ).toUpperCase() ||
        'BAJA';

    elemento.classList.remove(
        'alta',
        'media',
        'baja'
    );

    if (valor === 'ALTA') {
        elemento.classList.add(
            'alta'
        );

    } else if (
        valor === 'MEDIA'
    ) {
        elemento.classList.add(
            'media'
        );

    } else {
        elemento.classList.add(
            'baja'
        );
    }

    elemento.innerHTML = `
        Confianza:
        <strong>
            ${escaparHTMLPrecio(
                valor
            )}
        </strong>
    `;
}


// =========================================================
// INVENTARIO OPCIONAL
// =========================================================

function renderInventarioConsultaPrecio(
    inventario
) {

    const box =
        document.getElementById(
            'consultaInventarioBox'
        );

    if (!box) {
        return;
    }

    if (
        !inventario ||
        typeof inventario !==
            'object'
    ) {

        box.style.display =
            'none';

        return;
    }


    const codigo =
        inventario.codigo ??
        inventario.codigo_producto ??
        inventario.referencia ??
        '';

    const precioVenta =
        inventario.precio_venta ??
        inventario.precio ??
        null;

    const stockSucursal =
        inventario.stock_sucursal ??
        inventario.stock_actual ??
        null;

    const stockTotal =
        inventario.stock_total ??
        inventario.stock_mao ??
        null;

    const marca =
        inventario.marca ??
        '';

    const producto =
        inventario.producto ??
        inventario.nombre ??
        inventario.descripcion ??
        '';


    ponerTextoPrecio(
        'consultaInventarioCodigo',
        codigo
    );

    ponerTextoPrecio(
        'consultaInventarioPrecio',
        dineroPrecio(
            precioVenta
        )
    );

    ponerTextoPrecio(
        'consultaInventarioStockSucursal',
        stockSucursal
    );

    ponerTextoPrecio(
        'consultaInventarioStockTotal',
        stockTotal
    );

    ponerTextoPrecio(
        'consultaInventarioMarca',
        marca
    );

    ponerTextoPrecio(
        'consultaInventarioProducto',
        producto
    );


    box.style.display =
        'block';
}


// =========================================================
// CATÁLOGO OPCIONAL
// =========================================================

function renderCatalogoConsultaPrecio(
    catalogo
) {

    const box =
        document.getElementById(
            'consultaServicioCatalogoBox'
        );

    if (!box) {
        return;
    }

    if (
        !catalogo ||
        typeof catalogo !==
            'object'
    ) {

        box.style.display =
            'none';

        return;
    }


    ponerTextoPrecio(
        'consultaServicioCodigo',

        catalogo.codigo ??
        ''
    );

    ponerTextoPrecio(
        'consultaServicioPrecioCatalogo',

        dineroPrecio(
            catalogo.precio_catalogo ??
            catalogo.precio_sugerido ??
            catalogo.precio_base
        )
    );

    ponerTextoPrecio(
        'consultaServicioPrecioSucursal',

        dineroPrecio(
            catalogo.precio_sucursal ??
            catalogo.precio_referencial
        )
    );


    box.style.display =
        'block';
}
// =========================================================
// ÚLTIMO ANTECEDENTE DEL MISMO VEHÍCULO
// =========================================================

function renderAntecedenteMismoVehiculo(
    antecedente
) {

    // Eliminar el aviso de la consulta anterior
    const anterior =
        document.getElementById(
            'consultaAntecedenteMismoVehiculo'
        );

    if (anterior) {
        anterior.remove();
    }


    // Si este vehículo nunca tuvo este mismo
    // repuesto/servicio, no mostramos nada.
    if (
        !antecedente ||
        typeof antecedente !== 'object'
    ) {
        return;
    }


    const lista =
        document.getElementById(
            'consultaCoincidenciasLista'
        );

    if (!lista) {
        return;
    }


    const precio =
        numeroPrecio(
            antecedente.precio_unitario ??
            antecedente.precio
        );


    if (
        precio === null ||
        precio <= 0
    ) {
        return;
    }


    const numeroOrden =
        antecedente.numero_orden ||
        antecedente.orden ||
        'OT sin número';


    const fecha =
        fechaPrecio(
            antecedente.fecha
        );


    const kilometraje = (
        antecedente.kilometraje !== null &&
        antecedente.kilometraje !== undefined &&
        antecedente.kilometraje !== ''
    )
        ? kilometrajePrecio(
            antecedente.kilometraje
        )
        : '';


    const sucursal =
        textoSeguroPrecio(
            antecedente.sucursal ||
            antecedente.sucursal_codigo ||
            ''
        );


    const placa =
        textoSeguroPrecio(
            antecedente.placa ||
            ''
        );


    const descripcion =
        textoSeguroPrecio(
            antecedente.descripcion ||
            ''
        );


    const referencia =
        textoSeguroPrecio(
            antecedente.referencia ||
            antecedente.codigo ||
            ''
        );


    const metadatos = [
        numeroOrden,
        fecha !== '-' ? fecha : '',
        kilometraje,
        sucursal
    ]
        .filter(Boolean)
        .join(' · ');


    const puedeEditar =
        String(
            obtenerModalConsultaPrecios()
                ?.dataset
                ?.puedeEditar ||
            ''
        ).toLowerCase() === 'true';


    const botonAplicar =
        puedeEditar
            ? `
                <button
                    type="button"
                    class="
                        consulta-btn-aplicar-item
                        btn-aplicar-precio-historico
                    "
                    data-precio="${precio}"
                >
                    Aplicar
                    ${escaparHTMLPrecio(
                        dineroPrecio(precio)
                    )}
                </button>
            `
            : '';


    const box =
        document.createElement(
            'div'
        );


    box.id =
        'consultaAntecedenteMismoVehiculo';


    /*
     * Reutilizamos el diseño existente
     * del modal, sin crear un CSS nuevo.
     */
    box.className =
        'consulta-explicacion';


    box.style.cssText = `
        margin: 10px;
        border: 1px solid rgba(0, 113, 227, 0.20);
        border-radius: 10px;
        background: rgba(0, 113, 227, 0.05);
    `;


    box.innerHTML = `

        <div
            style="
                display:flex;
                align-items:center;
                justify-content:space-between;
                gap:12px;
            "
        >

            <div style="min-width:0;">

                <div
                    style="
                        color:#0071e3;
                        font-size:0.70rem;
                        font-weight:800;
                        text-transform:uppercase;
                        margin-bottom:4px;
                    "
                >
                    <i
                        class="bi bi-car-front"
                        style="margin-right:4px;"
                    ></i>

                    Último en este vehículo
                </div>


                <div
                    style="
                        color:#111111;
                        font-size:0.78rem;
                        font-weight:700;
                    "
                >
                    ${escaparHTMLPrecio(
                        metadatos
                    )}
                </div>


                ${
                    placa
                        ? `
                            <div
                                style="
                                    margin-top:3px;
                                    color:#6e6e73;
                                    font-size:0.68rem;
                                "
                            >
                                Placa:
                                ${escaparHTMLPrecio(
                                    placa
                                )}
                            </div>
                        `
                        : ''
                }


                ${
                    descripcion
                        ? `
                            <div
                                style="
                                    margin-top:4px;
                                    color:#4a4a4a;
                                    font-size:0.70rem;
                                "
                            >
                                ${escaparHTMLPrecio(
                                    descripcion
                                )}
                            </div>
                        `
                        : ''
                }


                ${
                    referencia
                        ? `
                            <div
                                style="
                                    margin-top:2px;
                                    color:#86868b;
                                    font-size:0.66rem;
                                "
                            >
                                Ref.:
                                ${escaparHTMLPrecio(
                                    referencia
                                )}
                            </div>
                        `
                        : ''
                }

            </div>


            <div
                style="
                    flex:0 0 auto;
                    text-align:right;
                "
            >

                <div
                    style="
                        color:#6e6e73;
                        font-size:0.60rem;
                        font-weight:800;
                        text-transform:uppercase;
                    "
                >
                    Último P.U.
                </div>


                <div
                    style="
                        color:#111111;
                        font-size:1.05rem;
                        font-weight:800;
                        margin:2px 0 6px;
                    "
                >
                    ${escaparHTMLPrecio(
                        dineroPrecio(precio)
                    )}
                </div>


                ${botonAplicar}

            </div>

        </div>
    `;


    /*
     * Lo colocamos antes del listado normal
     * de antecedentes.
     */
    lista.parentNode.insertBefore(
        box,
        lista
    );
}

// =========================================================
// COINCIDENCIAS
// =========================================================

function renderCoincidenciasPrecio(
    coincidencias,
    totalCoincidencias = null
) {

    const lista =
        document.getElementById(
            'consultaCoincidenciasLista'
        );

    const vacio =
        document.getElementById(
            'consultaCoincidenciasVacio'
        );

    const subtitulo =
        document.getElementById(
            'consultaCoincidenciasSubtitulo'
        );

    if (!lista) {
        return;
    }


    if (subtitulo) {

        const total =
            totalCoincidencias ??
            coincidencias.length;

        subtitulo.textContent =
            `${total} coincidencia(s) encontrada(s)`;
    }


    if (
        coincidencias.length === 0
    ) {

        lista.innerHTML =
            '';

        if (vacio) {
            vacio.style.display =
                'block';
        }

        return;
    }


    if (vacio) {
        vacio.style.display =
            'none';
    }


    lista.innerHTML =
        coincidencias.map(
            function (
                item,
                indice
            ) {

                return crearHTMLCoincidenciaPrecio(
                    item,
                    indice
                );
            }
        ).join('');
}


// =========================================================
// HTML DE UNA COINCIDENCIA
// =========================================================

function crearHTMLCoincidenciaPrecio(
    item,
    indice
) {

    item =
        item || {};

    const precio =
        numeroPrecio(
            item.precio_unitario ??
            item.precio
        );

    const numeroOrden =
        item.numero_orden ||
        item.orden ||
        'OT sin número';

    const fecha =
        fechaPrecio(
            item.fecha
        );

    const sucursal =
        item.sucursal ||
        item.sucursal_codigo ||
        item.sucursal_nombre ||
        '';

    const vehiculo =
        item.vehiculo ||
        '';

    const anio =
        item.anio ??
        item.anio_vehiculo ??
        '';

    const kilometraje =
        item.kilometraje;

    const descripcion =
        item.descripcion ||
        '';

    const referencia =
        item.referencia ||
        item.codigo ||
        '';

    const similitud =
        numeroPrecio(
            item.similitud
        );

    const origen =
        textoSeguroPrecio(
            item.origen
        );

    const procedimientos =
        Array.isArray(
            item.procedimientos
        )
            ? item.procedimientos
            : [];


    const metadatos = [];

    if (fecha !== '-') {
        metadatos.push(
            fecha
        );
    }

    if (sucursal) {
        metadatos.push(
            sucursal
        );
    }

    if (vehiculo) {

        metadatos.push(
            [
                vehiculo,
                anio
            ]
                .filter(Boolean)
                .join(' ')
        );
    }

    if (
        kilometraje !== null &&
        kilometraje !== undefined &&
        kilometraje !== ''
    ) {

        metadatos.push(
            kilometrajePrecio(
                kilometraje
            )
        );
    }


    let detalleExtra = '';

    if (referencia) {

        detalleExtra += `
            <div
                style="
                    margin-top:4px;
                    font-size:0.69rem;
                    color:#86868b;
                "
            >
                Ref.:
                ${escaparHTMLPrecio(
                    referencia
                )}
            </div>
        `;
    }


    if (
        procedimientos.length >
        0
    ) {

        detalleExtra += `
            <div
                style="
                    margin-top:7px;
                    font-size:0.70rem;
                    color:#6e6e73;
                    line-height:1.45;
                "
            >
                <strong>
                    Procedimientos:
                </strong>

                ${procedimientos
                    .map(
                        function (
                            procedimiento
                        ) {

                            const texto =
                                typeof procedimiento ===
                                'object'
                                    ? (
                                        procedimiento.descripcion ||
                                        procedimiento.texto ||
                                        procedimiento.nombre ||
                                        ''
                                    )
                                    : procedimiento;

                            return escaparHTMLPrecio(
                                texto
                            );
                        }
                    )
                    .filter(Boolean)
                    .join(' · ')
                }
            </div>
        `;
    }


    const puedeEditar =
        String(
            obtenerModalConsultaPrecios()
                ?.dataset
                ?.puedeEditar ||
            ''
        ).toLowerCase() ===
        'true';


    const botonAplicar =
        puedeEditar &&
        precio !== null &&
        precio > 0
            ? `
                <button
                    type="button"

                    class="
                        consulta-btn-aplicar-item
                        btn-aplicar-precio-historico
                    "

                    data-precio="${
                        precio
                    }"

                    data-indice="${
                        indice
                    }"
                >
                    Aplicar
                    ${escaparHTMLPrecio(
                        dineroPrecio(
                            precio
                        )
                    )}
                </button>
            `
            : '';


    const textoOrigen =
        origen === 'MIGRADA'
            ? 'Migrada / histórica'
            : origen === 'ACTUAL'
                ? 'MAO'
                : origen;


    return `
        <div
            class="consulta-coincidencia"
        >

            <div
                class="consulta-coincidencia-top"
            >

                <div
                    class="consulta-coincidencia-info"
                >

                    <div
                        class="consulta-coincidencia-orden"
                    >
                        ${escaparHTMLPrecio(
                            numeroOrden
                        )}
                    </div>

                    <div
                        class="consulta-coincidencia-meta"
                    >
                        ${metadatos
                            .map(
                                escaparHTMLPrecio
                            )
                            .join(' · ')
                        }

                        ${
                            textoOrigen
                                ? (
                                    metadatos.length
                                        ? ' · '
                                        : ''
                                ) +
                                escaparHTMLPrecio(
                                    textoOrigen
                                )
                                : ''
                        }
                    </div>

                </div>


                <div
                    class="consulta-coincidencia-precio"
                >

                    <div
                        class="
                            consulta-coincidencia-precio-label
                        "
                    >
                        P.U.
                    </div>

                    <div
                        class="
                            consulta-coincidencia-precio-valor
                        "
                    >
                        ${escaparHTMLPrecio(
                            dineroPrecio(
                                precio
                            )
                        )}
                    </div>

                </div>

            </div>


            <div
                class="consulta-coincidencia-detalle"
            >

                <div
                    class="
                        consulta-coincidencia-descripcion
                    "
                >

                    <strong>
                        ${escaparHTMLPrecio(
                            descripcion ||
                            'Sin descripción'
                        )}
                    </strong>

                    ${detalleExtra}

                    ${
                        similitud !== null
                            ? `
                                <div
                                    class="consulta-similitud"
                                >
                                    Similitud
                                    ${escaparHTMLPrecio(
                                        similitud.toFixed(
                                            1
                                        )
                                    )}%
                                </div>
                            `
                            : ''
                    }

                </div>


                <div>
                    ${botonAplicar}
                </div>

            </div>

        </div>
    `;
}


// =========================================================
// APLICAR SUGERENCIA
// =========================================================

function aplicarPrecioSugerido() {

    if (
        precioSugeridoActual ===
        null ||
        precioSugeridoActual <= 0
    ) {
        return;
    }

    aplicarPrecioAFilaActiva(
        precioSugeridoActual
    );
}


window.aplicarPrecioSugerido =
    aplicarPrecioSugerido;


// =========================================================
// APLICAR PRECIO
// =========================================================

function aplicarPrecioAFilaActiva(
    precio
) {

    const valor =
        numeroPrecio(
            precio
        );

    if (
        valor === null ||
        valor <= 0
    ) {
        return;
    }

    const fila =
        filaConsultaPrecioActiva;

    const tipo =
        tipoConsultaPrecioActivo;

    if (
        !fila ||
        !tipo
    ) {
        return;
    }


    const nombreInput = (
        tipo === 'REP'
            ? 'rep_pu[]'
            : tipo === 'MOI'
                ? 'moi_pu[]'
                : 'moe_pu[]'
    );


    const input =
        fila.querySelector(
            `input[name="${nombreInput}"]`
        );


    if (!input) {

        console.error(
            'No se encontró el P.U. de la fila.'
        );

        return;
    }


    input.value =
        valor.toFixed(2);


    /*
     * Usamos el sistema de cálculo que ya existe
     * en detalle_orden/base.js.
     */
    if (
        typeof calcularFila ===
        'function'
    ) {

        calcularFila(
            input
        );

    } else {

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


    if (
        typeof actualizarErroresNumericos ===
        'function'
    ) {

        actualizarErroresNumericos();
    }


    /*
     * Permite que otros listeners sepan que
     * el valor cambió.
     */
    input.dispatchEvent(
        new Event(
            'change',
            {
                bubbles: true
            }
        )
    );


    fila.classList.remove(
        'fila-precio-aplicado'
    );

    void fila.offsetWidth;

    fila.classList.add(
        'fila-precio-aplicado'
    );


    setTimeout(
        function () {

            fila.classList.remove(
                'fila-precio-aplicado'
            );

        },
        900
    );


    /*
     * Cerramos después de aplicar.
     */
    cerrarModalConsultaPrecios();


    /*
     * Volvemos el foco al P.U.
     */
    setTimeout(
        function () {

            input.focus();

            if (
                typeof input.select ===
                'function'
            ) {
                input.select();
            }

        },
        50
    );
}


// =========================================================
// EVENTOS
// =========================================================

function iniciarEventosConsultaPrecio() {

    /*
     * Lupa de cualquier fila.
     *
     * Delegado: funciona también para botones
     * creados después de cargar la página.
     */
    document.addEventListener(
        'click',
        function (
            event
        ) {

            const boton =
                event.target.closest(
                    '.btn-consultar-precio'
                );

            if (!boton) {
                return;
            }

            event.preventDefault();

            event.stopPropagation();

            const fila =
                boton.closest(
                    'tr'
                );

            const tipo =
                textoSeguroPrecio(
                    boton.dataset.tipo
                ).toUpperCase();


            if (
                !fila ||
                ![
                    'REP',
                    'MOI',
                    'MOE'
                ].includes(
                    tipo
                )
            ) {
                return;
            }


            consultarPrecioFila(
                fila,
                tipo
            );
        }
    );


    /*
     * Aplicar precio de un antecedente.
     */
    document.addEventListener(
        'click',
        function (
            event
        ) {

            const boton =
                event.target.closest(
                    '.btn-aplicar-precio-historico'
                );

            if (!boton) {
                return;
            }

            event.preventDefault();

            const precio =
                numeroPrecio(
                    boton.dataset.precio
                );

            if (
                precio === null ||
                precio <= 0
            ) {
                return;
            }

            aplicarPrecioAFilaActiva(
                precio
            );
        }
    );


    /*
     * Cerrar al hacer clic directamente
     * sobre el fondo oscuro.
     */
    document.addEventListener(
        'click',
        function (
            event
        ) {

            const modal =
                obtenerModalConsultaPrecios();

            if (
                modal &&
                event.target === modal
            ) {
                cerrarModalConsultaPrecios();
            }
        }
    );


    /*
     * ESC.
     */
    document.addEventListener(
        'keydown',
        function (
            event
        ) {

            if (
                event.key !==
                'Escape'
            ) {
                return;
            }

            const modal =
                obtenerModalConsultaPrecios();

            if (
                modal &&
                modal.style.display ===
                    'flex'
            ) {
                cerrarModalConsultaPrecios();
            }
        }
    );
}


// =========================================================
// INICIALIZAR
// =========================================================

function inicializarConsultaPrecios() {

    const modal =
        obtenerModalConsultaPrecios();

    if (!modal) {

        console.warn(
            'consulta_precios.html no está incluido.'
        );

        return;
    }

    insertarEstilosConsultaPrecio();

    decorarFilasConsultaPrecio();

    iniciarObservadorConsultaPrecio();

    iniciarEventosConsultaPrecio();
}


// =========================================================
// ARRANQUE
// =========================================================

if (
    document.readyState ===
    'loading'
) {

    document.addEventListener(
        'DOMContentLoaded',
        inicializarConsultaPrecios
    );

} else {

    inicializarConsultaPrecios();
}