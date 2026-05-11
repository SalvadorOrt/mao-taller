from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Sum

from .models import (
    Categoria,
    MarcaRepuesto,
    Producto,
    CodigoProducto,
    StockSucursal,
    MovimientoStock,
    Atributo,
    ValorAtributoProducto,
    InventarioFisico,
    DetalleInventarioFisico,
    KitProducto,
    ComponenteKit,
    ImagenProducto,
    FusionProducto,
    Auditoria,
    CatalogoMostrador,
    Usuario,
)


# =========================================================
# INLINE STOCK POR SUCURSAL
# =========================================================
class StockSucursalInline(admin.TabularInline):
    model = StockSucursal
    extra = 0
    can_delete = False
    readonly_fields = ("cantidad", "actualizado_en")
    fields = ("sucursal", "cantidad", "ubicacion", "actualizado_en")


class CodigoProductoInline(admin.TabularInline):
    model = CodigoProducto
    extra = 0
    fields = (
        "marca",
        "codigo",
        "codigo_barras",
        "tipo_codigo",
        "precio_compra",
        "precio_venta",
        "activo",
    )
    show_change_link = True


class ValorAtributoProductoInline(admin.TabularInline):
    model = ValorAtributoProducto
    extra = 0


class ComponenteKitInline(admin.TabularInline):
    model = ComponenteKit
    extra = 0
    autocomplete_fields = ("codigo_producto",)


class DetalleInventarioFisicoInline(admin.TabularInline):
    model = DetalleInventarioFisico
    extra = 0
    autocomplete_fields = ("codigo_producto",)


# =========================================================
# USUARIO
# =========================================================
@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    model = Usuario

    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "rol",
        "sucursal",
        "puede_cambiar_sucursal",
        "es_administrador",
        "is_staff",
        "is_superuser",
        "is_active",
    )
    list_filter = (
        "rol",
        "sucursal",
        "puede_cambiar_sucursal",
        "es_administrador",
        "is_staff",
        "is_superuser",
        "is_active",
    )
    search_fields = ("username", "first_name", "last_name", "email", "cedula")
    ordering = ("username",)

    fieldsets = UserAdmin.fieldsets + (
        (
            "Datos MAO",
            {
                "fields": (
                    "rol",
                    "cedula",
                    "es_administrador",
                    "sucursal",
                    "puede_cambiar_sucursal",
                )
            },
        ),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Datos MAO",
            {
                "fields": (
                    "rol",
                    "cedula",
                    "sucursal",
                    "puede_cambiar_sucursal",
                )
            },
        ),
    )

'''
from django.contrib import admin
from django.db.models import Sum

from .models import (
    Categoria,
    MarcaRepuesto,
    Producto,
    CodigoProducto,
    StockSucursal,
    MovimientoStock,
    Atributo,
    ValorAtributoProducto,
    InventarioFisico,
    DetalleInventarioFisico,
    KitProducto,
    ComponenteKit,
    ImagenProducto,
    FusionProducto,
    Auditoria,
    CatalogoMostrador,
    Usuario,
)


# =========================================================
# INLINE STOCK POR SUCURSAL
# =========================================================
class StockSucursalInline(admin.TabularInline):
    model = StockSucursal
    extra = 0
    can_delete = False
    readonly_fields = ("cantidad", "actualizado_en")
    fields = ("sucursal", "cantidad", "ubicacion", "actualizado_en")


class CodigoProductoInline(admin.TabularInline):
    model = CodigoProducto
    extra = 0
    fields = (
        "marca",
        "codigo",
        "codigo_barras",
        "tipo_codigo",
        "precio_compra",
        "precio_venta",
        "activo",
    )
    show_change_link = True


class ValorAtributoProductoInline(admin.TabularInline):
    model = ValorAtributoProducto
    extra = 0


class ComponenteKitInline(admin.TabularInline):
    model = ComponenteKit
    extra = 0
    autocomplete_fields = ("codigo_producto",)


class DetalleInventarioFisicoInline(admin.TabularInline):
    model = DetalleInventarioFisico
    extra = 0
    autocomplete_fields = ("codigo_producto",)


# =========================================================
# USUARIO
# =========================================================
@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "first_name",
        "last_name",
        "rol",
        "sucursal",
        "puede_cambiar_sucursal",
        "es_administrador",
        "is_active",
    )
    list_filter = (
        "rol",
        "sucursal",
        "puede_cambiar_sucursal",
        "es_administrador",
        "is_active",
        "is_staff",
    )
    search_fields = ("username", "first_name", "last_name", "email", "cedula")
    ordering = ("username",)


# =========================================================
# CATEGORIA
# =========================================================
@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "prefijo_sku")
    search_fields = ("nombre", "prefijo_sku")
    ordering = ("nombre",)


# =========================================================
# MARCA
# =========================================================
@admin.register(MarcaRepuesto)
class MarcaRepuestoAdmin(admin.ModelAdmin):
    list_display = ("nombre",)
    search_fields = ("nombre",)
    ordering = ("nombre",)


# =========================================================
# PRODUCTO
# =========================================================
@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = (
        "sku_interno",
        "nombre_base",
        "categoria",
        "activo",
        "descontinuado",
        "datos_incompletos",
        "stock_total",
        "actualizado_en",
    )
    list_filter = ("categoria", "activo", "descontinuado", "datos_incompletos")
    search_fields = ("sku_interno", "nombre_base", "descripcion")
    ordering = ("sku_interno",)
    inlines = [CodigoProductoInline, ValorAtributoProductoInline]

    def stock_total(self, obj):
        total = obj.codigos.aggregate(total=Sum("stocks_por_sucursal__cantidad"))["total"]
        return total or 0
    stock_total.short_description = "Stock total"


# =========================================================
# CODIGO PRODUCTO
# =========================================================
@admin.register(CodigoProducto)
class CodigoProductoAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "producto",
        "marca",
        "tipo_codigo",
        "codigo_barras",
        "precio_compra",
        "precio_venta",
        "ver_stock_total",
        "activo",
    )
    list_filter = ("marca", "tipo_codigo", "activo", "producto__categoria")
    search_fields = (
        "codigo",
        "codigo_normalizado",
        "codigo_barras",
        "nombre_comercial",
        "producto__nombre_base",
        "producto__sku_interno",
    )
    ordering = ("codigo",)
    autocomplete_fields = ("producto", "marca")
    inlines = [StockSucursalInline]

    def ver_stock_total(self, obj):
        total = obj.stocks_por_sucursal.aggregate(total=Sum("cantidad"))["total"]
        return total or 0
    ver_stock_total.short_description = "Stock total"


# =========================================================
# STOCK POR SUCURSAL
# =========================================================
@admin.register(StockSucursal)
class StockSucursalAdmin(admin.ModelAdmin):
    list_display = ("codigo_producto", "sucursal", "cantidad", "ubicacion", "actualizado_en")
    list_filter = ("sucursal",)
    search_fields = (
        "codigo_producto__codigo",
        "codigo_producto__producto__nombre_base",
        "sucursal__nombre",
        "sucursal__codigo",
        "ubicacion",
    )
    ordering = ("codigo_producto__codigo", "sucursal__codigo")
    readonly_fields = ("actualizado_en",)


# =========================================================
# MOVIMIENTO STOCK
# =========================================================
@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    list_display = (
        "codigo_producto",
        "sucursal",
        "tipo_movimiento",
        "cantidad",
        "precio_unitario",
        "referencia",
        "fecha",
    )
    list_filter = ("tipo_movimiento", "sucursal", "fecha")
    search_fields = (
        "codigo_producto__codigo",
        "codigo_producto__producto__nombre_base",
        "sucursal__nombre",
        "sucursal__codigo",
        "referencia",
        "descripcion_proveedor",
        "codigo_proveedor",
    )
    ordering = ("-fecha",)
    autocomplete_fields = ("codigo_producto", "sucursal")


# =========================================================
# ATRIBUTO
# =========================================================
@admin.register(Atributo)
class AtributoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "unidad")
    search_fields = ("nombre", "unidad")
    ordering = ("nombre",)


@admin.register(ValorAtributoProducto)
class ValorAtributoProductoAdmin(admin.ModelAdmin):
    list_display = ("producto", "atributo", "valor")
    search_fields = ("producto__sku_interno", "producto__nombre_base", "atributo__nombre", "valor")
    list_filter = ("atributo",)
    autocomplete_fields = ("producto", "atributo")


# =========================================================
# INVENTARIO FISICO
# =========================================================
@admin.register(InventarioFisico)
class InventarioFisicoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "sucursal", "estado", "fecha_inicio", "fecha_cierre")
    list_filter = ("sucursal", "estado", "fecha_inicio")
    search_fields = ("nombre", "observacion")
    ordering = ("-fecha_inicio",)
    inlines = [DetalleInventarioFisicoInline]


@admin.register(DetalleInventarioFisico)
class DetalleInventarioFisicoAdmin(admin.ModelAdmin):
    list_display = (
        "inventario",
        "codigo_producto",
        "stock_sistema",
        "cantidad_contada",
        "diferencia",
        "escaneado_por_barcode",
    )
    list_filter = ("escaneado_por_barcode", "inventario", "inventario__sucursal")
    search_fields = (
        "inventario__nombre",
        "codigo_producto__codigo",
        "codigo_producto__producto__nombre_base",
    )
    autocomplete_fields = ("inventario", "codigo_producto")


# =========================================================
# KITS
# =========================================================
@admin.register(KitProducto)
class KitProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre", "descripcion")
    inlines = [ComponenteKitInline]


@admin.register(ComponenteKit)
class ComponenteKitAdmin(admin.ModelAdmin):
    list_display = ("kit", "codigo_producto", "cantidad")
    search_fields = ("kit__nombre", "codigo_producto__codigo", "codigo_producto__producto__nombre_base")
    autocomplete_fields = ("kit", "codigo_producto")


# =========================================================
# IMAGENES
# =========================================================
@admin.register(ImagenProducto)
class ImagenProductoAdmin(admin.ModelAdmin):
    list_display = ("codigo_producto", "descripcion")
    search_fields = ("codigo_producto__codigo", "codigo_producto__producto__nombre_base", "descripcion")
    autocomplete_fields = ("codigo_producto",)


# =========================================================
# FUSION
# =========================================================
@admin.register(FusionProducto)
class FusionProductoAdmin(admin.ModelAdmin):
    list_display = ("producto_principal", "producto_duplicado", "fecha")
    search_fields = (
        "producto_principal__sku_interno",
        "producto_principal__nombre_base",
        "producto_duplicado__sku_interno",
        "producto_duplicado__nombre_base",
    )
    autocomplete_fields = ("producto_principal", "producto_duplicado")
    ordering = ("-fecha",)


# =========================================================
# AUDITORIA
# =========================================================
@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ("tabla", "objeto_id", "accion", "usuario", "fecha")
    list_filter = ("tabla", "accion", "fecha")
    search_fields = ("tabla", "accion", "usuario", "descripcion")
    ordering = ("-fecha",)
    readonly_fields = ("tabla", "objeto_id", "accion", "fecha", "usuario", "descripcion")


# =========================================================
# CATALOGO MOSTRADOR (PROXY)
# =========================================================
@admin.register(CatalogoMostrador)
class CatalogoMostradorAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "producto",
        "marca",
        "codigo_barras",
        "precio_venta",
        "ver_stock_total",
        "activo",
    )
    list_filter = ("marca", "activo", "producto__categoria")
    search_fields = (
        "codigo",
        "codigo_normalizado",
        "codigo_barras",
        "nombre_comercial",
        "producto__nombre_base",
        "producto__sku_interno",
    )
    ordering = ("codigo",)

    def ver_stock_total(self, obj):
        total = obj.stocks_por_sucursal.aggregate(total=Sum("cantidad"))["total"]
        return total or 0
    ver_stock_total.short_description = "Stock total"
'''
'''
from django.contrib import admin
from django.utils.safestring import mark_safe
from django.db.models import Sum
from django import forms
from .models import (
    Usuario, Categoria, MarcaRepuesto, Producto, CodigoProducto, 
    Stock, MovimientoStock, FacturaCompraXML, DetalleFacturaTemporal, 
    DetalleFacturaOriginal, CatalogoMostrador
)

# =========================================================
# 1. GESTIÓN DE USUARIOS (MAO CUSTOM USER)
# =========================================================
@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ['username', 'rol', 'cedula', 'is_staff']
    list_filter = ['rol']
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Información Personal', {'fields': ('first_name', 'last_name', 'cedula', 'email')}),
        ('Roles y Permisos', {'fields': ('rol', 'es_administrador', 'is_active', 'is_staff', 'groups')}),
    )

# =========================================================
# 2. CONFIGURACIÓN DE CATÁLOGOS
# =========================================================
@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'prefijo_sku']
    search_fields = ['nombre']

@admin.register(MarcaRepuesto)
class MarcaRepuestoAdmin(admin.ModelAdmin):
    search_fields = ['nombre']

# =========================================================
# 3. PRODUCTOS E INVENTARIO (CON VISTA DE PRECIOS)
# =========================================================
class CodigoProductoInline(admin.TabularInline):
    model = CodigoProducto
    extra = 1
    fields = ['marca', 'codigo', 'codigo_barras', 'precio_compra', 'precio_venta']

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ['nombre_base', 'categoria', 'get_total_stock']
    search_fields = ['nombre_base', 'codigos__codigo']
    inlines = [CodigoProductoInline]

    def get_total_stock(self, obj):
        total = Stock.objects.filter(codigo_producto__producto=obj).aggregate(total=Sum('cantidad'))['total']
        return total or 0
    get_total_stock.short_description = 'Stock Total'

# =========================================================
# 4. CARGA DE FACTURAS SRI (EL MOTOR DEL SISTEMA)
# =========================================================

class DetalleFacturaTemporalInline(admin.TabularInline):
    model = DetalleFacturaTemporal
    extra = 0
    fields = ['estado_visual', 'codigo_sri', 'nombre_limpio', 'marca_limpia', 'cantidad', 'alerta_precio']
    readonly_fields = ['estado_visual', 'codigo_sri', 'cantidad', 'alerta_precio']
    
    def estado_visual(self, obj):
        from .models import CodigoProducto
        existe = CodigoProducto.objects.filter(codigo=obj.codigo_sri).exists()
        if existe:
            return mark_safe("<span style='color:green; font-weight:bold;'>✅ EXISTENTE</span>")
        return mark_safe("<span style='color:orange; font-weight:bold;'>✨ NUEVO</span>")
    estado_visual.short_description = "Estado"

    def alerta_precio(self, obj):
        nuevo = obj.costo_unitario
        viejo = obj.costo_anterior
        if viejo and nuevo > viejo:
            return mark_safe(f"<span style='color:red;'>${nuevo} ⬆️</span>")
        return f"${nuevo}"
    alerta_precio.short_description = "Costo"

@admin.register(FacturaCompraXML)
class FacturaCompraXMLAdmin(admin.ModelAdmin):
    list_display = ['fecha_subida', 'clave_acceso_sri', 'procesado']
    inlines = [DetalleFacturaTemporalInline]
    actions = ['aplicar_ia_normalizacion', 'confirmar_ingreso_inventario']

    # --- ACCIÓN 1: LLAMADA A GEMINI IA ---
    @admin.action(description="🧠 1. Normalizar con IA (Gemini)")
    def aplicar_ia_normalizacion(self, request, queryset):
        for factura in queryset:
            # Aquí va tu lógica de la anterior sesión para llamar a la API de Google
            # y limpiar los nombres de los repuestos.
            pass
        self.message_user(request, "IA procesando nombres de repuestos...")

    # --- ACCIÓN 2: PASAR A STOCK REAL ---
    @admin.action(description="🤖 2. Confirmar Ingreso y Precios")
    def confirmar_ingreso_inventario(self, request, queryset):
        for factura in queryset:
            if not factura.procesado:
                # Aquí se dispara la fórmula: (Costo * 2) * 1.15
                factura.inventariar_final() 
        self.message_user(request, "Stock actualizado y precios calculados.")

# =========================================================
# 5. CATÁLOGO MOSTRADOR (PRECIO SECRETO)
# =========================================================
@admin.register(CatalogoMostrador)
class CatalogoMostradorAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'marca', 'producto', 'get_precio_secreto', 'precio_venta']
    search_fields = ['codigo', 'producto__nombre_base']

    def get_precio_secreto(self, obj):
        if not obj.precio_venta: return "---"
        # Tu clave: 1=M, 2=E, 3=C, 4=A, 5=N, 6=I, 7=O, 8=R, 9=T, 0=S
        clave = {'1':'M', '2':'E', '3':'C', '4':'A', '5':'N', '6':'I', '7':'O', '8':'R', '9':'T', '0':'S', '.':'.'}
        secreto = "".join([clave.get(char, char) for char in f"{obj.precio_venta:.2f}"])
        return mark_safe(f"<strong style='color:#2c3e50;'>{secreto}</strong>")
    get_precio_secreto.short_description = 'Cód. Precio'

# Registro simple para el resto
admin.site.register(Stock)
admin.site.register(MovimientoStock)
'''