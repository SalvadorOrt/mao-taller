# ordenes_de_trabajo/services/pdf_ficha.py

from playwright.sync_api import sync_playwright


def generar_pdf_desde_html(
    *,
    html,
    base_url,
):
    """
    Convierte HTML ya renderizado por Django en un PDF.

    Se utiliza Chromium para conservar:
    - CSS
    - Grid
    - tamaños A4
    - imágenes
    - estilos de impresión

    IMPORTANTE:
    No esperamos "networkidle" porque la ficha puede cargar
    recursos externos (por ejemplo Google Fonts) y eso puede
    bloquear innecesariamente la generación del PDF.

    Devuelve los bytes del PDF.
    """

    if not html:
        raise ValueError(
            "No se recibió contenido HTML para generar el PDF."
        )

    if not base_url:
        raise ValueError(
            "No se recibió la URL base para resolver recursos."
        )

    # =========================================================
    # BASE URL
    # =========================================================

    base_tag = (
        f'<base href="{base_url}">'
    )

    if "<head>" in html:
        html = html.replace(
            "<head>",
            f"<head>{base_tag}",
            1,
        )

    # =========================================================
    # CHROMIUM
    # =========================================================

    with sync_playwright() as playwright:

        browser = playwright.chromium.launch(
            headless=True,
        )

        try:

            page = browser.new_page(
                viewport={
                    "width": 1240,
                    "height": 1754,
                }
            )

            # =================================================
            # CARGAR HTML
            # =================================================
            #
            # NO usar networkidle.
            #
            # Solo necesitamos que el DOM esté construido.
            # Fuentes e imágenes se esperan por separado
            # con límites controlados.
            # =================================================

            page.set_content(
                html,
                wait_until="domcontentloaded",
                timeout=15000,
            )

            # =================================================
            # MODO IMPRESIÓN
            # =================================================

            page.emulate_media(
                media="print",
            )

            # =================================================
            # ESPERAR FUENTES
            # =================================================
            #
            # Máximo 5 segundos.
            #
            # Si Google Fonts u otra fuente externa tarda,
            # continuamos utilizando las fuentes fallback.
            # =================================================

            page.evaluate(
                """
                async () => {

                    if (
                        !document.fonts ||
                        !document.fonts.ready
                    ) {
                        return;
                    }

                    await Promise.race([
                        document.fonts.ready,

                        new Promise(
                            resolve =>
                                setTimeout(
                                    resolve,
                                    5000
                                )
                        )
                    ]);
                }
                """
            )

            # =================================================
            # ESPERAR IMÁGENES
            # =================================================
            #
            # Máximo 10 segundos.
            #
            # Una imagen problemática no debe detener todo
            # el envío de WhatsApp.
            # =================================================

            page.evaluate(
                """
                async () => {

                    const esperarImagenes =
                        async () => {

                            const imagenes =
                                Array.from(
                                    document.images
                                );

                            await Promise.all(
                                imagenes.map(
                                    imagen => {

                                        if (
                                            imagen.complete
                                        ) {
                                            return Promise.resolve();
                                        }

                                        return new Promise(
                                            resolve => {

                                                imagen.addEventListener(
                                                    'load',
                                                    resolve,
                                                    {
                                                        once: true
                                                    }
                                                );

                                                imagen.addEventListener(
                                                    'error',
                                                    resolve,
                                                    {
                                                        once: true
                                                    }
                                                );
                                            }
                                        );
                                    }
                                )
                            );
                        };


                    await Promise.race([
                        esperarImagenes(),

                        new Promise(
                            resolve =>
                                setTimeout(
                                    resolve,
                                    10000
                                )
                        )
                    ]);
                }
                """
            )

            # =================================================
            # GENERAR PDF
            # =================================================

            pdf_bytes = page.pdf(
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
            )

            return pdf_bytes

        finally:

            browser.close()