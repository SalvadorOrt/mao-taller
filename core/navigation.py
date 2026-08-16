def get_menu_lateral(user):
    menu = []

    # =====================================================
    # OPERACIÓN TALLER
    # Solo CAJA y ADMIN
    # =====================================================
    if user.rol in ["CAJA", "ADMIN"]:
        menu.append({
            "titulo": "Operación Taller",
            "items": [
                {
                    "label": "Dashboard Taller",
                    "url_name": "dashboard",
                    "icon": "bi-house-door",
                },
                {
                    "label": "Nueva Orden",
                    "url_name": "crear_orden",
                    "icon": "bi-plus-circle",
                },
                {
                    "label": "Nueva Cotización",
                    "url_name": "crear_cotizacion",
                    "icon": "bi-file-earmark-plus",
                },
                {
                    "label": "Órdenes de Trabajo",
                    "url_name": "lista_ordenes",
                    "icon": "bi-list-ul",
                },
                {
                    "label": "Vehículos / Expedientes",
                    "url": "/admin/ordenes_de_trabajo/expedientevehiculo/",
                    "icon": "bi-car-front",
                },
                {
                    "label": "Clientes",
                    "url_name": "lista_clientes",
                    "icon": "bi-people",
                },
            ]
        })

    # =====================================================
    # AVALÚOS
    # Todos los roles pueden acceder.
    #
    # TECNICO:
    # como no entra en las demás condiciones,
    # esta será su única sección visible.
    # =====================================================
    if user.rol in ["ADMIN", "BODEGA", "CAJA", "TECNICO"]:
        menu.append({
            "titulo": "Avalúos",
            "items": [
                {
                    "label": "Órdenes pendientes",
                    "url_name": "avaluos:ordenes_pendientes",
                    "icon": "bi-clipboard2-pulse",
                },
            ],
        })

    # =====================================================
    # INVENTARIO
    # Solo BODEGA y ADMIN
    # =====================================================
    if user.rol in ["BODEGA", "ADMIN"]:
        menu.append({
            "titulo": "Inventario",
            "items": [
                {
                    "label": "Dashboard Inventario",
                    "url_name": "inventario_dashboard",
                    "icon": "bi-speedometer2",
                },
                {
                    "label": "Catálogo",
                    "url_name": "inventario_catalogo",
                    "icon": "bi-box-seam",
                },
                {
                    "label": "Stock",
                    "url_name": "inventario_stock",
                    "icon": "bi-stack",
                },
                {
                    "label": "Movimientos",
                    "url_name": "inventario_movimientos",
                    "icon": "bi-arrow-left-right",
                },
                {
                    "label": "Inventario Físico",
                    "url_name": "inventario_fisico",
                    "icon": "bi-clipboard-check",
                },
            ]
        })

    # =====================================================
    # ADMINISTRACIÓN
    # Solo ADMIN
    # =====================================================
    if user.rol == "ADMIN":
        menu.append({
            "titulo": "Administración",
            "items": [
                {
                    "label": "Personal y Accesos",
                    "url_name": "lista_usuarios",
                    "icon": "bi-people-fill",
                },
                {
                    "label": "Panel Admin",
                    "url": "/admin/",
                    "icon": "bi-sliders",
                },
            ]
        })

    return menu