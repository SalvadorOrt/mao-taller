class AppleDropdownManager {
    constructor() {
        this.dropdownActivo = null;
        this.indiceActivo = -1;
    }

    inicializar() {
        document.querySelectorAll(".apple-dropdown").forEach((wrap) => {
            this.inicializarDropdown(wrap);
        });

        document.addEventListener("click", (event) => {
            if (!event.target.closest(".apple-dropdown")) {
                this.cerrarTodos();
            }
        });
    }

    inicializarDropdown(wrap) {
        if (wrap.dataset.inicializado === "1") return;

        const input = wrap.querySelector(".apple-dropdown-input");
        const hidden = wrap.querySelector(".apple-dropdown-hidden");
        const menu = wrap.querySelector(".apple-dropdown-menu");

        if (!input || !hidden || !menu) return;

        wrap.dataset.inicializado = "1";

        this.cargarValorInicial(wrap);

        input.addEventListener("focus", () => {
            this.abrir(wrap);
        });

        input.addEventListener("click", () => {
            this.abrir(wrap);
        });

        input.addEventListener("input", () => {
            hidden.value = "";
            this.filtrar(wrap);
            this.abrir(wrap);
        });

        input.addEventListener("keydown", (event) => {
            this.manejarTeclado(event, wrap);
        });

        this.conectarItems(wrap);
    }

    conectarItems(wrap) {
        const items = wrap.querySelectorAll(".apple-dropdown-item");

        items.forEach((item) => {
            if (item.dataset.eventoClick === "1") return;

            item.dataset.eventoClick = "1";

            item.addEventListener("click", () => {
                this.seleccionarItem(wrap, item);
            });
        });
    }

    abrir(wrap) {
        this.cerrarTodos();

        const menu = wrap.querySelector(".apple-dropdown-menu");

        if (!menu) return;

        this.dropdownActivo = wrap;
        this.indiceActivo = -1;

        menu.style.display = "block";

        this.filtrar(wrap);
    }

    cerrar(wrap) {
        const menu = wrap.querySelector(".apple-dropdown-menu");

        if (menu) {
            menu.style.display = "none";
        }

        this.limpiarActivo(wrap);
    }

    cerrarTodos() {
        document.querySelectorAll(".apple-dropdown-menu").forEach((menu) => {
            menu.style.display = "none";
        });

        document.querySelectorAll(".apple-dropdown-item.activo").forEach((item) => {
            item.classList.remove("activo");
        });

        this.dropdownActivo = null;
        this.indiceActivo = -1;
    }

    filtrar(wrap) {
        const input = wrap.querySelector(".apple-dropdown-input");
        const menu = wrap.querySelector(".apple-dropdown-menu");
        const noResult = wrap.querySelector(".apple-dropdown-no-result");

        if (!input || !menu) return;

        const filtro = input.value.toLowerCase().trim();

        let visibles = 0;

        this.obtenerItems(wrap).forEach((item) => {
            const texto = (item.dataset.nombre || item.textContent || "")
                .toLowerCase();

            if (texto.includes(filtro)) {
                item.style.display = "block";
                visibles++;
            } else {
                item.style.display = "none";
            }
        });

        if (noResult) {
            noResult.style.display = visibles === 0 ? "block" : "none";
        }

        this.indiceActivo = -1;
        this.limpiarActivo(wrap);
    }

    obtenerItems(wrap) {
        return Array.from(
            wrap.querySelectorAll(".apple-dropdown-item")
        );
    }

    obtenerItemsVisibles(wrap) {
        return this.obtenerItems(wrap).filter((item) => {
            return item.style.display !== "none";
        });
    }

    manejarTeclado(event, wrap) {
        const menu = wrap.querySelector(".apple-dropdown-menu");

        if (!menu) return;

        const abierto = menu.style.display === "block";

        if (!abierto && ["ArrowDown", "ArrowUp", "Enter"].includes(event.key)) {
            event.preventDefault();
            this.abrir(wrap);
            return;
        }

        if (event.key === "Escape") {
            this.cerrar(wrap);
            return;
        }

        const visibles = this.obtenerItemsVisibles(wrap);

        if (!visibles.length) return;

        if (event.key === "ArrowDown") {
            event.preventDefault();

            this.indiceActivo++;

            if (this.indiceActivo >= visibles.length) {
                this.indiceActivo = 0;
            }

            this.marcarActivo(wrap, visibles[this.indiceActivo]);
        }

        if (event.key === "ArrowUp") {
            event.preventDefault();

            this.indiceActivo--;

            if (this.indiceActivo < 0) {
                this.indiceActivo = visibles.length - 1;
            }

            this.marcarActivo(wrap, visibles[this.indiceActivo]);
        }

        if (event.key === "Enter") {
            if (this.indiceActivo >= 0 && visibles[this.indiceActivo]) {
                event.preventDefault();
                this.seleccionarItem(wrap, visibles[this.indiceActivo]);
            }
        }
    }

    marcarActivo(wrap, itemActivo) {
        this.limpiarActivo(wrap);

        itemActivo.classList.add("activo");
        itemActivo.scrollIntoView({
            block: "nearest",
        });
    }

    limpiarActivo(wrap) {
        wrap.querySelectorAll(".apple-dropdown-item.activo").forEach((item) => {
            item.classList.remove("activo");
        });
    }

    seleccionarItem(wrap, item) {
        const input = wrap.querySelector(".apple-dropdown-input");
        const hidden = wrap.querySelector(".apple-dropdown-hidden");
        const menu = wrap.querySelector(".apple-dropdown-menu");

        if (!input || !hidden || !item) return;

        input.value = item.dataset.nombre || item.textContent.trim();
        hidden.value = item.dataset.id || "";

        if (menu) {
            menu.style.display = "none";
        }

        input.dispatchEvent(new Event("change", { bubbles: true }));
        hidden.dispatchEvent(new Event("change", { bubbles: true }));
    }

    cargarValorInicial(wrap) {
        const input = wrap.querySelector(".apple-dropdown-input");
        const hidden = wrap.querySelector(".apple-dropdown-hidden");

        if (!input || !hidden || !hidden.value) return;

        const item = wrap.querySelector(
            `.apple-dropdown-item[data-id="${hidden.value}"]`
        );

        if (item) {
            input.value = item.dataset.nombre || item.textContent.trim();
        }
    }

    agregarOpcion(tipo, id, nombre, seleccionar = true) {
        const dropdowns = document.querySelectorAll(
            `.apple-dropdown[data-dropdown-tipo="${tipo}"]`
        );

        dropdowns.forEach((wrap) => {
            const input = wrap.querySelector(".apple-dropdown-input");
            const hidden = wrap.querySelector(".apple-dropdown-hidden");
            const menu = wrap.querySelector(".apple-dropdown-menu");

            if (!input || !hidden || !menu) return;

            let item = menu.querySelector(
                `.apple-dropdown-item[data-id="${id}"]`
            );

            if (!item) {
                item = document.createElement("div");
                item.className = "apple-dropdown-item";
                item.dataset.id = id;
                item.dataset.nombre = nombre;
                item.textContent = nombre;

                const noResult = menu.querySelector(".apple-dropdown-no-result");

                if (noResult) {
                    menu.insertBefore(item, noResult);
                } else {
                    menu.appendChild(item);
                }

                this.conectarItems(wrap);
            }

            if (seleccionar) {
                input.value = nombre;
                hidden.value = id;
                menu.style.display = "none";

                input.dispatchEvent(new Event("change", { bubbles: true }));
                hidden.dispatchEvent(new Event("change", { bubbles: true }));
            }
        });
    }

    seleccionar(tipo, id) {
        const dropdowns = document.querySelectorAll(
            `.apple-dropdown[data-dropdown-tipo="${tipo}"]`
        );

        dropdowns.forEach((wrap) => {
            const item = wrap.querySelector(
                `.apple-dropdown-item[data-id="${id}"]`
            );

            if (item) {
                this.seleccionarItem(wrap, item);
            }
        });
    }

    refrescar() {
        document.querySelectorAll(".apple-dropdown").forEach((wrap) => {
            this.inicializarDropdown(wrap);
            this.conectarItems(wrap);
        });
    }
}

window.AppleDropdown = new AppleDropdownManager();

document.addEventListener("DOMContentLoaded", () => {
    window.AppleDropdown.inicializar();
});

function inicializarDropdownsApple() {
    window.AppleDropdown.refrescar();
}

function agregarOpcionADropdowns(tipo, id, nombre, seleccionar = true) {
    window.AppleDropdown.agregarOpcion(tipo, id, nombre, seleccionar);
}