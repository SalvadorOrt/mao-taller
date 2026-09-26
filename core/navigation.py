from accesos.modulos import usuario_tiene_modulo


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

    if usuario_tiene_modulo(
        user,
        "operacion_taller",
    ):

        items_operacion = []

        if user.has_perm(
            "ordenes_de_trabajo.view_ordentrabajo"
        ):
            items_operacion.append({
                "label": "Dashboard Taller",
                "url_name": "dashboard",
                "icon": "bi-house-door",
            })

        if user.has_perm(
            "ordenes_de_trabajo.add_ordentrabajo"
        ):
            items_operacion.append({
                "label": "Nueva Orden",
                "url_name": "crear_orden",
                "icon": "bi-plus-circle",
            })

        if user.has_perm(
            "ordenes_de_trabajo.view_ordentrabajo"
        ):
            items_operacion.append({
                "label": "Órdenes de Trabajo",
                "url_name": "lista_ordenes",
                "icon": "bi-list-ul",
            })

        if (
            user.is_staff
            and user.has_perm(
                "ordenes_de_trabajo.view_expedientevehiculo"
            )
        ):
            items_operacion.append({
                "label": "Vehículos / Expedientes",
                "url": (
                    "/admin/"
                    "ordenes_de_trabajo/"
                    "expedientevehiculo/"
                ),
                "icon": "bi-car-front",
            })

        if user.has_perm(
            "ordenes_de_trabajo.view_cliente"
        ):
            items_operacion.append({
                "label": "Clientes",
                "url_name": "lista_clientes",
                "icon": "bi-people",
            })

        if items_operacion:
            menu.append({
                "titulo": "Operación Taller",
                "items": items_operacion,
            })


    # =====================================================
    # COTIZACIONES / PROFORMAS
    # =====================================================

    if usuario_tiene_modulo(
        user,
        "cotizaciones",
    ):

        items_cotizaciones = []

        if user.has_perm(
            "ordenes_de_trabajo.view_cotizacion"
        ):
            items_cotizaciones.append({
                "label": "Ver Proformas",
                "url_name": "lista_cotizaciones",
                "icon": "bi-file-earmark-text",
            })

        if user.has_perm(
            "ordenes_de_trabajo.add_cotizacion"
        ):
            items_cotizaciones.append({
                "label": "Nueva Proforma",
                "url_name": "crear_cotizacion",
                "icon": "bi-plus-circle",
            })

        if items_cotizaciones:
            menu.append({
                "titulo": "Cotizaciones",
                "items": items_cotizaciones,
            })


    # =====================================================
    # AVALÚOS
    # =====================================================

    if usuario_tiene_modulo(
        user,
        "avaluos",
    ):

        items_avaluos = []

        if user.has_perm(
            "avaluos.view_avaluomecanico"
        ):
            items_avaluos.append({
                "label": "Órdenes pendientes",
                "url_name":
                    "avaluos:ordenes_pendientes",
                "icon":
                    "bi-clipboard2-pulse",
            })

        if items_avaluos:
            menu.append({
                "titulo": "Avalúos",
                "items": items_avaluos,
            })


    # =====================================================
    # INVENTARIO
    # =====================================================

    if usuario_tiene_modulo(
        user,
        "inventario",
    ):

        items_inventario = []

        if user.has_perm(
            "inventario.view_stocksucursal"
        ):
            items_inventario.append({
                "label":
                    "Dashboard Inventario",
                "url_name":
                    "inventario_dashboard",
                "icon":
                    "bi-speedometer2",
            })

        if user.has_perm(
            "inventario.view_producto"
        ):
            items_inventario.append({
                "label": "Catálogo",
                "url_name":
                    "inventario_catalogo",
                "icon": "bi-box-seam",
            })

        if user.has_perm(
            "inventario.view_stocksucursal"
        ):
            items_inventario.append({
                "label": "Stock",
                "url_name":
                    "inventario_stock",
                "icon": "bi-stack",
            })

        if user.has_perm(
            "inventario.view_movimientostock"
        ):
            items_inventario.append({
                "label": "Movimientos",
                "url_name":
                    "inventario_movimientos",
                "icon":
                    "bi-arrow-left-right",
            })

        if user.has_perm(
            "inventario.view_inventariofisico"
        ):
            items_inventario.append({
                "label": "Inventario Físico",
                "url_name":
                    "inventario_fisico",
                "icon":
                    "bi-clipboard-check",
            })

        if items_inventario:
            menu.append({
                "titulo": "Inventario",
                "items": items_inventario,
            })


    # =====================================================
    # FACTURACIÓN
    # =====================================================

    if usuario_tiene_modulo(
        user,
        "facturacion",
    ):

        items_facturacion = []

        if user.has_perm(
            "facturacion.view_facturaventa"
        ):
            items_facturacion.append({
                "label":
                    "Dashboard Facturación",
                "url_name":
                    "facturacion:dashboard",
                "icon":
                    "bi-receipt",
            })

        if user.has_perm(
            "facturacion.add_facturaventa"
        ):
            items_facturacion.append({
                "label":
                    "Factura manual",
                "url_name":
                    "facturacion:nueva_factura_manual",
                "icon":
                    "bi-file-earmark-plus",
            })

        if items_facturacion:
            menu.append({
                "titulo": "Facturación",
                "items": items_facturacion,
            })


    # =====================================================
    # ADMINISTRACIÓN
    # =====================================================

    if usuario_tiene_modulo(
        user,
        "administracion",
    ) or user.is_staff:

        items_administracion = []

        if user.has_perm(
            "accesos.view_rol"
        ):
            items_administracion.append({
                "label":
                    "Roles y permisos",
                "url_name":
                    "accesos:roles_lista",
                "icon":
                    "bi-shield-lock",
            })

        if user.has_perm(
            "inventario.view_usuario"
        ):
            items_administracion.append({
                "label":
                    "Personal y Accesos",
                "url_name":
                    "lista_usuarios",
                "icon":
                    "bi-people-fill",
            })

        if user.is_staff:
            items_administracion.append({
                "label": "Panel Admin",
                "url": "/admin/",
                "icon": "bi-sliders",
            })

        if items_administracion:
            menu.append({
                "titulo":
                    "Administración",
                "items":
                    items_administracion,
            })


    # =====================================================
    # NOTA SOBRE ASISTENCIA
    # =====================================================
    #
    # La app Asistencia actual expone endpoints API para
    # terminales. No se agregan al menú lateral.
    #
    # Cuando exista un panel administrativo de asistencia,
    # se agrega aquí condicionado por:
    #
    # usuario_tiene_modulo(user, "asistencia")
    #
    # El terminal físico NO debe depender de permisos del ERP.
    # =====================================================


    return menu
