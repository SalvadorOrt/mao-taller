import json
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.db import transaction

from ordenes_de_trabajo.models import Sucursal

from inventario.models import (
    Categoria,
    MarcaRepuesto,
    Producto,
    CodigoProducto,
    StockSucursal,
)


CODIGO_SUCURSAL_SUR = "SUR"
CODIGO_SUCURSAL_NORTE = "NORTE"


class Command(BaseCommand):
    help = "Importa repuestos, limpia BD opcionalmente, deja precios vacíos y stock inicial en 0."

    def add_arguments(self, parser):
        parser.add_argument("archivo_json", type=str)

        parser.add_argument(
            "--clear",
            action="store_true",
            help="Elimina todo el inventario antes de importar.",
        )

    def limpiar_texto(self, valor, default=None):
        if valor in (None, "", "null"):
            return default
        texto = str(valor).strip()
        return texto if texto else default

    def to_decimal(self, valor):
        if valor in (None, "", "null"):
            return None
        try:
            return Decimal(str(valor).strip())
        except (InvalidOperation, TypeError, ValueError):
            return None

    def obtener_o_crear_sucursal(self, codigo, nombre):
        sucursal = Sucursal.objects.filter(codigo__iexact=codigo).first()

        if sucursal:
            return sucursal, False

        sucursal = Sucursal.objects.create(
            nombre=nombre,
            codigo=codigo,
            activa=True,
        )

        return sucursal, True

    def obtener_o_crear_categoria(self, prefijo, nombre=None):
        prefijo = self.limpiar_texto(prefijo, "SIN-CAT").upper()
        nombre = self.limpiar_texto(nombre, prefijo)

        categoria = (
            Categoria.objects.filter(prefijo_sku__iexact=prefijo).first()
            or Categoria.objects.filter(nombre__iexact=nombre).first()
        )

        if categoria:
            return categoria, False

        return Categoria.objects.create(
            prefijo_sku=prefijo,
            nombre=nombre,
        ), True

    def obtener_o_crear_marca(self, nombre):
        nombre = self.limpiar_texto(nombre, "SIN-MARCA")

        marca = MarcaRepuesto.objects.filter(nombre__iexact=nombre).first()

        if marca:
            return marca, False

        return MarcaRepuesto.objects.create(nombre=nombre), True

    def asegurar_stock_en_todas_las_sucursales(self, codigo_producto):
        sucursales = Sucursal.objects.filter(activa=True)

        for sucursal in sucursales:
            stock_obj, creado = StockSucursal.objects.get_or_create(
                codigo_producto=codigo_producto,
                sucursal=sucursal,
                defaults={
                    "cantidad": 0,
                    "ubicacion": None,
                },
            )

            if not creado:
                stock_obj.cantidad = 0
                stock_obj.save(update_fields=["cantidad"])

    @transaction.atomic
    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write(self.style.WARNING("Iniciando purga de datos de inventario..."))

            StockSucursal.objects.all().delete()
            CodigoProducto.objects.all().delete()
            Producto.objects.all().delete()
            MarcaRepuesto.objects.all().delete()
            Categoria.objects.all().delete()

            self.stdout.write(self.style.SUCCESS("✔ Inventario eliminado por completo."))

        archivo = options["archivo_json"]

        with open(archivo, "r", encoding="utf-8") as f:
            data = json.load(f)

        sucursal_sur, creada_sur = self.obtener_o_crear_sucursal(
            CODIGO_SUCURSAL_SUR,
            "MAO Sur",
        )

        sucursal_norte, creada_norte = self.obtener_o_crear_sucursal(
            CODIGO_SUCURSAL_NORTE,
            "MAO Norte",
        )

        if creada_sur:
            self.stdout.write(self.style.WARNING("⚠ Se creó automáticamente la sucursal SUR"))

        if creada_norte:
            self.stdout.write(self.style.WARNING("⚠ Se creó automáticamente la sucursal NORTE"))

        categorias_creadas = 0
        marcas_creadas = 0
        productos_creados = 0
        codigos_creados = 0
        stocks_actualizados = 0
        stocks_creados_en_sucursales = 0
        codigos_sin_producto = 0

        # ======================
        # CATEGORÍAS
        # ======================
        for c in data.get("categorias", []):
            prefijo = self.limpiar_texto(c.get("prefijo_sku"))
            nombre = self.limpiar_texto(c.get("nombre"), prefijo)

            if not prefijo:
                continue

            _, creada = self.obtener_o_crear_categoria(prefijo, nombre)

            if creada:
                categorias_creadas += 1

        # ======================
        # MARCAS
        # ======================
        for m in data.get("marcas_repuesto", []):
            nombre = self.limpiar_texto(m.get("nombre"))

            if not nombre:
                continue

            _, creada = self.obtener_o_crear_marca(nombre)

            if creada:
                marcas_creadas += 1

        # ======================
        # PRODUCTOS
        # ======================
        for p in data.get("productos", []):
            nombre_base = self.limpiar_texto(
                p.get("nombre_base"),
                "PRODUCTO SIN NOMBRE",
            )

            categoria, _ = self.obtener_o_crear_categoria(
                p.get("categoria_prefijo"),
                p.get("categoria_nombre"),
            )

            sku = self.limpiar_texto(p.get("sku_interno"))

            if not sku:
                sku = f"TEMP-{nombre_base}".upper().replace(" ", "-")

            producto, creado = Producto.objects.update_or_create(
                sku_interno=sku,
                defaults={
                    "categoria": categoria,
                    "nombre_base": nombre_base,
                    "descripcion": self.limpiar_texto(p.get("descripcion")),
                    "activo": p.get("activo", True),
                    "descontinuado": p.get("descontinuado", False),
                    "datos_incompletos": p.get("datos_incompletos", False),
                },
            )

            if creado:
                productos_creados += 1

        # ======================
        # CÓDIGOS DE PRODUCTO
        # ======================
        codigos_por_codigo = {}

        for cp in data.get("codigos_producto", []):
            producto_sku = self.limpiar_texto(cp.get("producto_sku"))

            if not producto_sku:
                codigos_sin_producto += 1
                continue

            producto = Producto.objects.filter(
                sku_interno__iexact=producto_sku
            ).first()

            if not producto:
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠ Producto no encontrado para código {cp.get('codigo')}: {producto_sku}"
                    )
                )
                codigos_sin_producto += 1
                continue

            marca, _ = self.obtener_o_crear_marca(cp.get("marca"))

            codigo_valor = self.limpiar_texto(cp.get("codigo"))

            if not codigo_valor:
                continue

            codigo_producto, creado = CodigoProducto.objects.update_or_create(
                producto=producto,
                marca=marca,
                codigo=codigo_valor,
                defaults={
                    "tipo_codigo": self.limpiar_texto(
                        cp.get("tipo_codigo"),
                        "aftermarket",
                    ),
                    "codigo_barras": self.limpiar_texto(cp.get("codigo_barras")),
                    "nombre_comercial": self.limpiar_texto(cp.get("nombre_comercial")),
                    "presentacion_cantidad": self.to_decimal(
                        cp.get("presentacion_cantidad")
                    ),
                    "presentacion_unidad": self.limpiar_texto(
                        cp.get("presentacion_unidad")
                    ),

                    # Precios vacíos. Ya no se genera nada aleatorio.
                    "precio_compra": None,
                    "precio_venta": None,

                    "activo": cp.get("activo", True),
                },
            )

            if creado:
                codigos_creados += 1

            antes = StockSucursal.objects.filter(
                codigo_producto=codigo_producto
            ).count()

            self.asegurar_stock_en_todas_las_sucursales(codigo_producto)

            despues = StockSucursal.objects.filter(
                codigo_producto=codigo_producto
            ).count()

            if despues > antes:
                stocks_creados_en_sucursales += despues - antes

            codigos_por_codigo[codigo_valor.upper()] = codigo_producto
            stocks_actualizados += 1

        # ======================
        # STOCK EXTRA
        # ======================
        for s in data.get("stock", []):
            codigo_valor = self.limpiar_texto(s.get("codigo_producto"))

            if not codigo_valor:
                continue

            codigo_producto = (
                codigos_por_codigo.get(codigo_valor.upper())
                or CodigoProducto.objects.filter(codigo__iexact=codigo_valor).first()
            )

            if not codigo_producto:
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠ No se encontró CodigoProducto para stock: {codigo_valor}"
                    )
                )
                continue

            self.asegurar_stock_en_todas_las_sucursales(codigo_producto)

        self.stdout.write(self.style.SUCCESS(" Importación de repuestos completada"))
        self.stdout.write(
            f"Sucursales inicializadas con stock en 0: {sucursal_sur.codigo} y {sucursal_norte.codigo}"
        )
        self.stdout.write("Precios de compra y venta quedaron vacíos")
        self.stdout.write(f"Categorías creadas: {categorias_creadas}")
        self.stdout.write(f"Marcas creadas: {marcas_creadas}")
        self.stdout.write(f"Productos creados: {productos_creados}")
        self.stdout.write(f"Códigos creados: {codigos_creados}")
        self.stdout.write(f"Stocks creados en sucursales faltantes: {stocks_creados_en_sucursales}")
        self.stdout.write(f"Productos procesados con stock inicial en 0: {stocks_actualizados}")
        self.stdout.write(f"Códigos sin producto: {codigos_sin_producto}")
#py manage.py importar_repuestos repuestos_exportados.json --clear