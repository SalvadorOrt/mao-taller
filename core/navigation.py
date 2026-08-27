def get_menu_lateral(user):
    menu = []

    # =====================================================
    # USUARIO NO AUTENTICADO
    # =====================================================

    if not user.is_authenticated:
        return menu


    # =====================================================
    # OPERACIÓN TALLER
    # =====================================================

    items_operacion = []


    # -----------------------------------------------------
    # DASHBOARD TALLER
    # -----------------------------------------------------

    if user.has_perm(
        "ordenes_de_trabajo.view_ordentrabajo"
    ):
        items_operacion.append({
            "label": "Dashboard Taller",
            "url_name": "dashboard",
            "icon": "bi-house-door",
        })


    # -----------------------------------------------------
    # NUEVA ORDEN
    # -----------------------------------------------------

    if user.has_perm(
        "ordenes_de_trabajo.add_ordentrabajo"
    ):
        items_operacion.append({
            "label": "Nueva Orden",
            "url_name": "crear_orden",
            "icon": "bi-plus-circle",
        })


    # -----------------------------------------------------
    # NUEVA COTIZACIÓN
    # -----------------------------------------------------

    if user.has_perm(
        "ordenes_de_trabajo.add_cotizacion"
    ):
        items_operacion.append({
            "label": "Nueva Cotización",
            "url_name": "crear_cotizacion",
            "icon": "bi-file-earmark-plus",
        })


    # -----------------------------------------------------
    # ÓRDENES DE TRABAJO
    # -----------------------------------------------------

    if user.has_perm(
        "ordenes_de_trabajo.view_ordentrabajo"
    ):
        items_operacion.append({
            "label": "Órdenes de Trabajo",
            "url_name": "lista_ordenes",
            "icon": "bi-list-ul",
        })


    # -----------------------------------------------------
    # VEHÍCULOS / EXPEDIENTES
    #
    # Esta URL pertenece al Django Admin.
    # Por eso además del permiso necesita is_staff.
    # -----------------------------------------------------

    if (
        user.is_staff
        and user.has_perm(
            "ordenes_de_trabajo.view_expedientevehiculo"
        )
    ):
        items_operacion.append({
            "label": "Vehículos / Expedientes",
            "url": "/admin/ordenes_de_trabajo/expedientevehiculo/",
            "icon": "bi-car-front",
        })


    # -----------------------------------------------------
    # CLIENTES
    # -----------------------------------------------------

    if user.has_perm(
        "ordenes_de_trabajo.view_cliente"
    ):
        items_operacion.append({
            "label": "Clientes",
            "url_name": "lista_clientes",
            "icon": "bi-people",
        })


    # -----------------------------------------------------
    # AGREGAR SECCIÓN
    # -----------------------------------------------------

    if items_operacion:
        menu.append({
            "titulo": "Operación Taller",
            "items": items_operacion,
        })


    # =====================================================
    # AVALÚOS
    # =====================================================

    items_avaluos = []


    if user.has_perm(
        "avaluos.view_avaluomecanico"
    ):
        items_avaluos.append({
            "label": "Órdenes pendientes",
            "url_name": "avaluos:ordenes_pendientes",
            "icon": "bi-clipboard2-pulse",
        })


    if items_avaluos:
        menu.append({
            "titulo": "Avalúos",
            "items": items_avaluos,
        })


    # =====================================================
    # INVENTARIO
    # =====================================================

    items_inventario = []


    # -----------------------------------------------------
    # DASHBOARD INVENTARIO
    # -----------------------------------------------------

    if user.has_perm(
        "inventario.view_stocksucursal"
    ):
        items_inventario.append({
            "label": "Dashboard Inventario",
            "url_name": "inventario_dashboard",
            "icon": "bi-speedometer2",
        })


    # -----------------------------------------------------
    # CATÁLOGO
    # -----------------------------------------------------

    if user.has_perm(
        "inventario.view_producto"
    ):
        items_inventario.append({
            "label": "Catálogo",
            "url_name": "inventario_catalogo",
            "icon": "bi-box-seam",
        })


    # -----------------------------------------------------
    # STOCK
    # -----------------------------------------------------

    if user.has_perm(
        "inventario.view_stocksucursal"
    ):
        items_inventario.append({
            "label": "Stock",
            "url_name": "inventario_stock",
            "icon": "bi-stack",
        })


    # -----------------------------------------------------
    # MOVIMIENTOS
    # -----------------------------------------------------

    if user.has_perm(
        "inventario.view_movimientostock"
    ):
        items_inventario.append({
            "label": "Movimientos",
            "url_name": "inventario_movimientos",
            "icon": "bi-arrow-left-right",
        })


    # -----------------------------------------------------
    # INVENTARIO FÍSICO
    # -----------------------------------------------------

    if user.has_perm(
        "inventario.view_inventariofisico"
    ):
        items_inventario.append({
            "label": "Inventario Físico",
            "url_name": "inventario_fisico",
            "icon": "bi-clipboard-check",
        })


    # -----------------------------------------------------
    # AGREGAR SECCIÓN
    # -----------------------------------------------------

    if items_inventario:
        menu.append({
            "titulo": "Inventario",
            "items": items_inventario,
        })


    # =====================================================
    # FACTURACIÓN
    # =====================================================

    items_facturacion = []


    # -----------------------------------------------------
    # DASHBOARD FACTURACIÓN
    # -----------------------------------------------------

    if user.has_perm(
        "facturacion.view_facturaventa"
    ):
        items_facturacion.append({
            "label": "Dashboard Facturación",
            "url_name": "facturacion:dashboard",
            "icon": "bi-receipt",
        })


    # -----------------------------------------------------
    # AGREGAR SECCIÓN
    # -----------------------------------------------------

    if items_facturacion:
        menu.append({
            "titulo": "Facturación",
            "items": items_facturacion,
        })


    # =====================================================
    # ADMINISTRACIÓN
    # =====================================================

    items_administracion = []


    # -----------------------------------------------------
    # ROLES Y PERMISOS
    # -----------------------------------------------------

    if user.has_perm(
        "accesos.view_rol"
    ):
        items_administracion.append({
            "label": "Roles y permisos",
            "url_name": "accesos:roles_lista",
            "icon": "bi-shield-lock",
        })


    # -----------------------------------------------------
    # PERSONAL Y ACCESOS
    # -----------------------------------------------------

    if user.has_perm(
        "inventario.view_usuario"
    ):
        items_administracion.append({
            "label": "Personal y Accesos",
            "url_name": "lista_usuarios",
            "icon": "bi-people-fill",
        })


    # -----------------------------------------------------
    # PANEL ADMIN DJANGO
    # -----------------------------------------------------

    if user.is_staff:
        items_administracion.append({
            "label": "Panel Admin",
            "url": "/admin/",
            "icon": "bi-sliders",
        })


    # -----------------------------------------------------
    # AGREGAR SECCIÓN
    # -----------------------------------------------------

    if items_administracion:
        menu.append({
            "titulo": "Administración",
            "items": items_administracion,
        })


    # =====================================================
    # RESULTADO
    # =====================================================

    return menu