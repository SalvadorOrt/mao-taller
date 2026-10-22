(() => {
    const form = document.querySelector("[data-editor-repuestos]");
    if (!form) return;

    const cuerpo = form.querySelector("[data-filas-repuestos]");
    const plantilla = form.querySelector("[data-plantilla-fila]");
    const total = form.querySelector('[name="repuestos-TOTAL_FORMS"]');
    const aviso = form.querySelector("[data-aviso-filas]");
    const deshacer = form.querySelector("[data-deshacer-fila]");

    const eliminadas = [];
    let siguienteOrden = Number(form.dataset.siguienteOrden);
    let modificado = false;

    function cambio() {
        modificado = true;
        aviso.textContent = "Tienes cambios sin guardar.";
    }

    function ocultarFila(fila) {
        fila.querySelector('[name$="-DELETE"]').checked = true;

        fila.querySelectorAll(
            'input:not([type="hidden"]), select, textarea'
        ).forEach(campo => {
            if (campo.name.endsWith("-DELETE")) return;

            campo.dataset.yaDeshabilitado = campo.disabled ? "1" : "0";
            campo.disabled = true;
        });

        fila.hidden = true;
        eliminadas.push(fila);
        deshacer.hidden = false;
    }

    cuerpo.querySelectorAll(".tc-fila").forEach(fila => {
        if (fila.querySelector('[name$="-DELETE"]').checked) {
            ocultarFila(fila);
        }
    });

    form.addEventListener("input", cambio);
    form.addEventListener("change", cambio);

    form.querySelector("[data-agregar-fila]")?.addEventListener("click", () => {
        const indice = Number(total.value);

        if (indice >= 30) {
            aviso.textContent = "Guarda estas filas antes de añadir más.";
            return;
        }

        const html = plantilla.innerHTML.replaceAll(
            "__prefix__",
            String(indice)
        );

        cuerpo.insertAdjacentHTML("beforeend", html);
        total.value = indice + 1;

        const fila = cuerpo.lastElementChild;
        fila.querySelector('[name$="-orden_item"]').value = siguienteOrden++;
        fila.querySelector('[name$="-descripcion_solicitada"]').focus();

        cambio();
    });

    cuerpo.addEventListener("click", event => {
        const boton = event.target.closest("[data-quitar-fila]");
        if (!boton) return;

        ocultarFila(boton.closest(".tc-fila"));
        cambio();
    });

    deshacer.addEventListener("click", () => {
        const fila = eliminadas.pop();
        if (!fila) return;

        fila.querySelector('[name$="-DELETE"]').checked = false;

        fila.querySelectorAll("[data-ya-deshabilitado]").forEach(campo => {
            campo.disabled = campo.dataset.yaDeshabilitado === "1";
            delete campo.dataset.yaDeshabilitado;
        });

        fila.hidden = false;
        deshacer.hidden = eliminadas.length === 0;
        cambio();
    });

    form.addEventListener("submit", () => {
        modificado = false;
    });

    window.addEventListener("beforeunload", event => {
        if (!modificado) return;

        event.preventDefault();
        event.returnValue = "";
    });
})();