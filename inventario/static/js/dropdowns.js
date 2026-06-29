// static/inventario/js/dropdowns.js

function inicializarDropdownsApple() {
    document.querySelectorAll(".apple-dropdown").forEach((wrap) => {
        const input = wrap.querySelector(".apple-dropdown-input");
        const hidden = wrap.querySelector(".apple-dropdown-hidden");
        const menu = wrap.querySelector(".apple-dropdown-menu");
        const items = wrap.querySelectorAll(".apple-dropdown-item");
        const noResult = wrap.querySelector(".apple-dropdown-no-result");

        if (!input || !hidden || !menu) return;

        function mostrar() {
            menu.style.display = "block";
            filtrar();
        }

        function ocultar() {
            menu.style.display = "none";
        }

        function filtrar() {
            const filtro = input.value.toLowerCase().trim();
            let visibles = 0;

            items.forEach((item) => {
                const texto = item.dataset.nombre.toLowerCase();

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

            menu.style.display = "block";
        }

        input.addEventListener("focus", mostrar);
        input.addEventListener("click", mostrar);
        input.addEventListener("input", () => {
            hidden.value = "";
            filtrar();
        });

        items.forEach((item) => {
            item.addEventListener("click", () => {
                input.value = item.dataset.nombre;
                hidden.value = item.dataset.id;
                ocultar();
            });
        });

        document.addEventListener("click", (event) => {
            if (!wrap.contains(event.target)) {
                ocultar();
            }
        });
    });
}

document.addEventListener("DOMContentLoaded", inicializarDropdownsApple);