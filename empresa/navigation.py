def get_menu_lateral(user):
    menu = []

    if user.rol in ["CAJA", "ADMIN"]:
        menu.append({
            "titulo": "Operación Taller",
            "items": [
                {"label": "Dashboard Taller", "url_name": "dashboard", "icon": "bi-house-door"},
                {"label": "Nueva Orden", "url_name": "crear_orden", "icon": "bi-plus-circle"},
                {"label": "Órdenes de Trabajo", "url_name": "lista_ordenes", "icon": "bi-list-ul"},
                {"label": "Vehículos / Expedientes", "url": "/admin/ordenes_de_trabajo/expedientevehiculo/", "icon": "bi-car-front"},
                
                {"label": "Clientes", "url": "/clientes/", "icon": "bi-people"},
            ]
        })

    if user.rol in ["BODEGA", "ADMIN"]:
        menu.append({
            "titulo": "Inventario",
            "items": [
                {"label": "Productos Base", "url": "/admin/inventario/producto/", "icon": "bi-box-seam"},
                {"label": "Productos y Códigos", "url": "/admin/inventario/codigoproducto/", "icon": "bi-upc-scan"},
                {"label": "Stock", "url": "/admin/inventario/stocksucursal/", "icon": "bi-stack"},
                {"label": "Movimientos", "url": "/admin/inventario/movimientostock/", "icon": "bi-arrow-left-right"},
            ]
        })

    if user.rol == "ADMIN":
        menu.append({
            "titulo": "Administración",
            "items": [
                {"label": "Personal y Accesos", "url_name": "lista_usuarios", "icon": "bi-people-fill"},
                {"label": "Auditoría", "url": "/admin/inventario/auditoria/", "icon": "bi-clock-history"},
                {"label": "Panel Admin", "url": "/admin/", "icon": "bi-sliders"},
            ]
        })

    return menu