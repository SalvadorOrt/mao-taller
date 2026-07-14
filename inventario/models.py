from decimal import Decimal
import re
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models import Max
from django.contrib.auth.base_user import BaseUserManager
import unicodedata

from django.conf import settings
from django.utils import timezone
import re
import unicodedata
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
# =========================================================
# MANAGER PERSONALIZADO DE USUARIO
# =========================================================
class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, username, email, password, **extra_fields):
        if not username:
            raise ValueError("El username es obligatorio.")

        email = self.normalize_email(email) if email else email
        username = username.strip()

        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)

        # Si no mandan rol, usuario normal = CAJA
        extra_fields.setdefault("rol", "CAJA")

        return self._create_user(username, email, password, **extra_fields)

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("rol", "ADMIN")
        extra_fields.setdefault("es_administrador", True)
        extra_fields.setdefault("puede_cambiar_sucursal", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("El superusuario debe tener is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("El superusuario debe tener is_superuser=True.")

        return self._create_user(username, email, password, **extra_fields)


# =========================================================
# 👤 USUARIO PERSONALIZADO
# =========================================================
class Usuario(AbstractUser):
    ROLES = [
        ("ADMIN", "Administrador (Dueño)"),
        ("BODEGA", "Bodeguero (Maneja IA y Compras)"),
        ("CAJA", "Cajera (Maneja OTs y Pagos)"),
    ]

    rol = models.CharField(max_length=15, choices=ROLES, default="CAJA")
    cedula = models.CharField(max_length=15, unique=True, null=True, blank=True)
    es_administrador = models.BooleanField(default=False)

    sucursal = models.ForeignKey(
        "ordenes_de_trabajo.Sucursal",
        on_delete=models.SET_NULL,
        related_name="usuarios",
        null=True,
        blank=True,
       
    )

    puede_cambiar_sucursal = models.BooleanField(
        default=False,
       
    )

    groups = models.ManyToManyField(
        "auth.Group",
        related_name="inventario_usuario_groups",
        blank=True,
       
        verbose_name="grupos",
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        related_name="inventario_usuario_permissions",
        blank=True,
        
        verbose_name="permisos de usuario",
    )

    objects = UsuarioManager()

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def clean(self):
        super().clean()

        if self.cedula:
            self.cedula = self.cedula.strip()

        if self.username:
            self.username = self.username.strip()

        if self.first_name:
            self.first_name = self.first_name.strip()

        if self.last_name:
            self.last_name = self.last_name.strip()

        if self.email:
            self.email = self.email.strip().lower()

    def save(self, *args, **kwargs):
        if self.username:
            self.username = self.username.strip()

        if self.first_name:
            self.first_name = self.first_name.strip()

        if self.last_name:
            self.last_name = self.last_name.strip()

        if self.email:
            self.email = self.email.strip().lower()

        if self.cedula:
            self.cedula = self.cedula.strip()

        # =====================================================
        # REGLA CENTRAL:
        # si es superusuario, SIEMPRE debe ser ADMIN
        # =====================================================
        if self.is_superuser:
            self.rol = "ADMIN"
            self.es_administrador = True
            self.is_staff = True
            self.puede_cambiar_sucursal = True

        elif self.rol == "ADMIN":
            self.es_administrador = True
            self.is_staff = True
            self.puede_cambiar_sucursal = True

        elif self.rol == "BODEGA":
            self.es_administrador = False
            self.is_superuser = False
            self.is_staff = True
            self.puede_cambiar_sucursal = False

        else:  # CAJA
            self.rol = "CAJA"
            self.es_administrador = False
            self.is_superuser = False
            self.is_staff = True
            self.puede_cambiar_sucursal = False

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        sucursal = self.sucursal.codigo if self.sucursal else "SIN SUCURSAL"
        return f"{self.username} - {self.get_rol_display()} - {sucursal}"

# =========================================================
# CATEGORÍAS
# =========================================================
class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    prefijo_sku = models.CharField(max_length=20, unique=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"

    def clean(self):
        if not self.nombre or not self.nombre.strip():
            raise ValidationError("El nombre de la categoría es obligatorio.")
        if not self.prefijo_sku or not self.prefijo_sku.strip():
            raise ValidationError("El prefijo SKU es obligatorio.")

    def save(self, *args, **kwargs):
        if self.nombre:
            self.nombre = self.nombre.strip()
        if self.prefijo_sku:
            self.prefijo_sku = self.prefijo_sku.strip().upper()

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


# =========================================================
# MARCAS DE FABRICANTE / PRODUCTO
# =========================================================
class MarcaRepuesto(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Marca"
        verbose_name_plural = "Marcas"

    def clean(self):
        if not self.nombre or not self.nombre.strip():
            raise ValidationError("El nombre de la marca es obligatorio.")

    def save(self, *args, **kwargs):
        if self.nombre:
            self.nombre = self.nombre.strip()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre
# =========================================================
# PRODUCTO BASE / FAMILIA FUNCIONAL
# =========================================================

class Producto(models.Model):
    ORIGEN_CHOICES = [
        (
            "INDIVIDUAL",
            "Creación individual desde inventario",
        ),
        (
            "FACTURA",
            "Creado desde factura de compra",
        ),
        (
            "MOSTRADOR",
            "Creación rápida desde mostrador",
        ),
    ]

    sku_interno = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
    )

    categoria = models.ForeignKey(
        "Categoria",
        on_delete=models.PROTECT,
        related_name="productos",
    )

    nombre_base = models.CharField(
        max_length=255,
    )

    descripcion = models.TextField(
        blank=True,
        null=True,
    )

    origen = models.CharField(
        max_length=20,
        choices=ORIGEN_CHOICES,
        default="INDIVIDUAL",
        db_index=True,
    )

    # Solo se llena cuando el producto nació desde una factura.
    detalle_origen_creacion = models.ForeignKey(
        "compras.DetalleFacturaOriginal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="productos_creados",
        help_text=(
            "Detalle original de la factura que dio origen "
            "a la creación del producto."
        ),
    )

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="productos_creados",
    )

    activo = models.BooleanField(
        default=True,
    )

    descontinuado = models.BooleanField(
        default=False,
    )

    datos_incompletos = models.BooleanField(
        default=False,
        help_text=(
            "Indica que el producto fue creado rápidamente "
            "y todavía requiere revisión."
        ),
    )

    creado_en = models.DateTimeField(
        auto_now_add=True,
    )

    actualizado_en = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "sku_interno",
        ]

        verbose_name = "Producto"
        verbose_name_plural = "Productos"

        indexes = [
            models.Index(
                fields=["categoria", "activo"],
            ),
            models.Index(
                fields=["origen", "activo"],
            ),
            models.Index(
                fields=["nombre_base"],
            ),
        ]

    def __str__(self):
        sku = self.sku_interno or "SIN SKU"

        return f"{sku} - {self.nombre_base}"

    def clean(self):
        errores = {}

        if not self.categoria_id:
            errores["categoria"] = (
                "La categoría es obligatoria."
            )

        if (
            not self.nombre_base
            or not self.nombre_base.strip()
        ):
            errores["nombre_base"] = (
                "El nombre base del producto es obligatorio."
            )

        if self.origen == "FACTURA":
            if not self.detalle_origen_creacion_id:
                errores["detalle_origen_creacion"] = (
                    "Un producto creado desde una factura debe "
                    "estar vinculado al detalle original."
                )

        elif self.detalle_origen_creacion_id:
            errores["detalle_origen_creacion"] = (
                "El detalle de origen solo debe asignarse cuando "
                "el producto fue creado desde una factura."
            )

        if (
            self.descontinuado
            and self.activo
        ):
            errores["descontinuado"] = (
                "Un producto descontinuado no debe permanecer activo."
            )

        if errores:
            raise ValidationError(errores)

    def _generar_sku(self):
        if not self.categoria_id:
            raise ValidationError(
                "La categoría es obligatoria para generar el SKU."
            )

        prefijo_categoria = (
            self.categoria.prefijo_sku
            or ""
        ).strip().upper()

        if not prefijo_categoria:
            raise ValidationError(
                "La categoría debe tener un prefijo SKU."
            )

        prefijo = f"MAO-{prefijo_categoria}-"

        with transaction.atomic():
            # Bloquea la categoría para evitar que dos procesos
            # generen el mismo consecutivo al mismo tiempo.
            Categoria.objects.select_for_update().get(
                pk=self.categoria_id
            )

            ultimo_producto = (
                Producto.objects
                .filter(
                    sku_interno__startswith=prefijo,
                )
                .order_by("-sku_interno")
                .first()
            )

            siguiente_numero = 1

            if ultimo_producto:
                coincidencia = re.search(
                    r"(\d+)$",
                    ultimo_producto.sku_interno,
                )

                if coincidencia:
                    siguiente_numero = (
                        int(coincidencia.group(1)) + 1
                    )

            return (
                f"{prefijo}"
                f"{siguiente_numero:04d}"
            )

    def codigo_principal(self):
        codigo_activo = (
            self.codigos
            .filter(activo=True)
            .order_by("id")
            .first()
        )

        if codigo_activo:
            return codigo_activo

        return (
            self.codigos
            .order_by("id")
            .first()
        )

    @property
    def precio_venta_principal(self):
        codigo = self.codigo_principal()

        return (
            codigo.precio_venta
            if codigo
            else None
        )

    @property
    def precio_compra_principal(self):
        codigo = self.codigo_principal()

        return (
            codigo.precio_compra
            if codigo
            else None
        )

    @property
    def precio_secreto(self):
        codigo = self.codigo_principal()

        return (
            codigo.precio_secreto
            if codigo
            else "---"
        )

    @property
    def imagen_principal(self):
        return self.imagenes.first()

    @property
    def total_codigos(self):
        return self.codigos.count()

    @property
    def total_atributos(self):
        return self.valores_atributos.count()

    @property
    def tiene_codigos(self):
        return self.codigos.exists()

    @property
    def tiene_imagenes(self):
        return self.imagenes.exists()

    @property
    def tiene_atributos(self):
        return self.valores_atributos.exists()

    @property
    def fue_creado_desde_factura(self):
        return self.origen == "FACTURA"

    @property
    def necesita_revision(self):
        return self.datos_incompletos

    def save(self, *args, **kwargs):
        if self.sku_interno:
            self.sku_interno = (
                self.sku_interno
                .strip()
                .upper()
            )

        if self.nombre_base:
            self.nombre_base = (
                self.nombre_base
                .strip()
                .upper()
            )

        if self.descripcion:
            self.descripcion = (
                self.descripcion.strip()
            )

        self.origen = (
            self.origen
            or "INDIVIDUAL"
        ).strip().upper()

        if self.descontinuado:
            self.activo = False

        categoria_cambio = False

        if self.pk:
            producto_anterior = (
                Producto.objects
                .filter(pk=self.pk)
                .only("categoria_id")
                .first()
            )

            categoria_cambio = bool(
                producto_anterior
                and producto_anterior.categoria_id
                != self.categoria_id
            )

        self.full_clean()

        sku_generado_automaticamente = False

        if not self.pk and not self.sku_interno:
            self.sku_interno = self._generar_sku()
            sku_generado_automaticamente = True

        elif self.pk and categoria_cambio:
            self.sku_interno = self._generar_sku()
            sku_generado_automaticamente = True

        update_fields = kwargs.get("update_fields")

        if (
            update_fields is not None
            and sku_generado_automaticamente
        ):
            campos = set(update_fields)
            campos.add("sku_interno")
            campos.add("actualizado_en")
            kwargs["update_fields"] = list(campos)

        intentos = 0
        maximo_intentos = 10

        while intentos < maximo_intentos:
            try:
                with transaction.atomic():
                    super().save(*args, **kwargs)

                return

            except IntegrityError:
                if not sku_generado_automaticamente:
                    raise

                intentos += 1

                coincidencia = re.search(
                    r"(\d+)$",
                    self.sku_interno,
                )

                if not coincidencia:
                    raise

                siguiente_numero = (
                    int(coincidencia.group(1)) + 1
                )

                prefijo = self.sku_interno[
                    :coincidencia.start()
                ]

                self.sku_interno = (
                    f"{prefijo}"
                    f"{siguiente_numero:04d}"
                )

        raise IntegrityError(
            "No se pudo generar un SKU único después "
            "de varios intentos."
        )
# =========================================================
# CÓDIGO COMERCIAL / ÍTEM VENDIBLE
# =========================================================
class CodigoProducto(models.Model):
    TIPO_CODIGO_CHOICES = [
        ("aftermarket", "General / Comercial"),
        ("oem", "Original / Fabricante"),
        ("interno", "Interno"),
    ]

    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name="codigos"
    )
    marca = models.ForeignKey(
        "MarcaRepuesto",
        on_delete=models.PROTECT,
        related_name="codigos"
    )

    codigo = models.CharField(max_length=100)
    codigo_normalizado = models.CharField(
        max_length=100,
        blank=True,
        editable=False,
        db_index=True
    )

    tipo_codigo = models.CharField(
        max_length=20,
        choices=TIPO_CODIGO_CHOICES,
        default="aftermarket"
    )

    codigo_barras = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
    )

    nombre_comercial = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    presentacion_cantidad = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True
    )
    presentacion_unidad = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    precio_compra = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True
    )
    precio_venta = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True
    )

    margen_ganancia_porcentaje = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("100.00"),
    )

    porcentaje_iva_costo = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    activo = models.BooleanField(default=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["codigo"]
        verbose_name = "Código de producto"
        verbose_name_plural = "Códigos de producto"
        unique_together = ("producto", "marca", "codigo")

    def __str__(self):
        marca = self.marca.nombre if self.marca_id else "SIN MARCA"
        return f"{marca} - {self.codigo}"

    @staticmethod
    def normalizar_codigo(valor):
        if not valor:
            return ""

        return re.sub(
            r"[^A-Z0-9]",
            "",
            valor.upper()
        )

    @staticmethod
    def convertir_precio_secreto(precio):
        if precio is None:
            return "---"

        clave = {
            "1": "M",
            "2": "E",
            "3": "C",
            "4": "A",
            "5": "N",
            "6": "I",
            "7": "O",
            "8": "R",
            "9": "T",
            "0": "S",
            ".": ".",
        }

        texto = f"{precio:.2f}"

        return "".join(
            clave.get(caracter, caracter)
            for caracter in texto
        )

    @property
    def precio_secreto(self):
        return self.convertir_precio_secreto(
            self.precio_venta
        )

    def clean(self):
        if not self.producto_id:
            raise ValidationError("El producto base es obligatorio.")

        if not self.marca_id:
            raise ValidationError("La marca es obligatoria.")

        if not self.codigo or not self.codigo.strip():
            raise ValidationError("El código del producto es obligatorio.")

        if self.precio_compra is not None and self.precio_compra < 0:
            raise ValidationError("El precio de compra no puede ser negativo.")

        if self.precio_venta is not None and self.precio_venta < 0:
            raise ValidationError("El precio de venta no puede ser negativo.")

        if (
            self.precio_compra is not None
            and self.precio_venta is not None
            and self.precio_venta < self.precio_compra
        ):
            raise ValidationError(
                "El precio de venta no puede ser menor que el precio de compra."
            )

        if (
            self.margen_ganancia_porcentaje is not None
            and self.margen_ganancia_porcentaje < 0
        ):
            raise ValidationError("El margen no puede ser negativo.")

        if (
            self.porcentaje_iva_costo is not None
            and self.porcentaje_iva_costo < 0
        ):
            raise ValidationError("El IVA costo no puede ser negativo.")

        if (
            self.presentacion_cantidad is not None
            and self.presentacion_cantidad <= 0
        ):
            raise ValidationError("La presentación debe ser mayor que 0.")

    def save(self, *args, **kwargs):
        es_nuevo = self.pk is None

        if self.codigo:
            self.codigo = self.codigo.strip().upper()

        self.codigo_normalizado = self.normalizar_codigo(
            self.codigo
        )

        if self.codigo_barras:
            self.codigo_barras = self.codigo_barras.strip()
        else:
            self.codigo_barras = None

        if self.nombre_comercial:
            self.nombre_comercial = self.nombre_comercial.strip()

        if self.presentacion_unidad:
            self.presentacion_unidad = self.presentacion_unidad.strip().upper()

        if self.precio_compra is not None and self.precio_venta is None:
            margen = self.margen_ganancia_porcentaje or Decimal("0.00")
            iva_costo = self.porcentaje_iva_costo or Decimal("0.00")

            costo_con_margen = self.precio_compra * (
                Decimal("1.00") + margen / Decimal("100.00")
            )

            calculo = costo_con_margen * (
                Decimal("1.00") + iva_costo / Decimal("100.00")
            )

            self.precio_venta = calculo.quantize(
                Decimal("0.01")
            )

        self.full_clean()

        super().save(*args, **kwargs)

        if es_nuevo:
            from ordenes_de_trabajo.models import Sucursal
            from inventario.models import StockSucursal

            sucursales_activas = Sucursal.objects.filter(
                activa=True
            )

            stocks_a_crear = []

            for sucursal in sucursales_activas:
                stocks_a_crear.append(
                    StockSucursal(
                        codigo_producto=self,
                        sucursal=sucursal,
                        cantidad=Decimal("0.00"),
                        ubicacion=None,
                    )
                )

            if stocks_a_crear:
                StockSucursal.objects.bulk_create(
                    stocks_a_crear,
                    ignore_conflicts=True
                )
# =========================================================
# ATRIBUTOS TÉCNICOS
# =========================================================
class Atributo(models.Model):
    nombre = models.CharField(max_length=100)
    unidad = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Atributo"
        verbose_name_plural = "Atributos"
        unique_together = ("nombre", "unidad")

    def clean(self):
        if not self.nombre or not self.nombre.strip():
            raise ValidationError("El nombre del atributo es obligatorio.")

    def save(self, *args, **kwargs):
        if self.nombre:
            self.nombre = self.nombre.strip()
        if self.unidad:
            self.unidad = self.unidad.strip()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre if not self.unidad else f"{self.nombre} ({self.unidad})"


class ValorAtributoProducto(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="valores_atributos")
    atributo = models.ForeignKey(Atributo, on_delete=models.CASCADE, related_name="valores_producto")
    valor = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Valor de atributo de producto"
        verbose_name_plural = "Valores de atributos de producto"
        unique_together = ("producto", "atributo")

    def clean(self):
        if not self.valor or not self.valor.strip():
            raise ValidationError("El valor del atributo es obligatorio.")

    def save(self, *args, **kwargs):
        if self.valor:
            self.valor = self.valor.strip()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.producto.sku_interno} - {self.atributo.nombre}: {self.valor}"


# =========================================================
# STOCK POR SUCURSAL
# =========================================================
class StockSucursal(models.Model):
    codigo_producto = models.ForeignKey(
        CodigoProducto,
        on_delete=models.CASCADE,
        related_name="stocks_por_sucursal",
    )
    sucursal = models.ForeignKey(
        "ordenes_de_trabajo.Sucursal",
        on_delete=models.CASCADE,
        related_name="stocks",
    )
    cantidad = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal("0.00"))
    ubicacion = models.CharField(max_length=100, null=True, blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["codigo_producto__codigo", "sucursal__codigo"]
        verbose_name = "Stock por sucursal"
        verbose_name_plural = "Stocks por sucursal"
        unique_together = ("codigo_producto", "sucursal")
        indexes = [
            models.Index(fields=["sucursal", "codigo_producto"]),
        ]

    def clean(self):
        if self.cantidad is None:
            raise ValidationError("La cantidad es obligatoria.")

        if self.ubicacion:
            self.ubicacion = self.ubicacion.strip()

    def save(self, *args, **kwargs):
        if self.ubicacion:
            self.ubicacion = self.ubicacion.strip()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        sucursal = self.sucursal.codigo if self.sucursal else "SIN SUCURSAL"
        return f"{self.codigo_producto.codigo} | {sucursal} | {self.cantidad}"


class MovimientoStock(models.Model):
    TIPO_MOVIMIENTO_CHOICES = [
        ("entrada", "Entrada"),
        ("salida", "Salida"),
        ("ajuste", "Ajuste"),
    ]

    codigo_producto = models.ForeignKey(
        CodigoProducto,
        on_delete=models.CASCADE,
        related_name="movimientos",
    )
    sucursal = models.ForeignKey(
        "ordenes_de_trabajo.Sucursal",
        on_delete=models.PROTECT,
        related_name="movimientos_stock",
        null=True,
        blank=True,
    )
    tipo_movimiento = models.CharField(max_length=10, choices=TIPO_MOVIMIENTO_CHOICES)
    cantidad = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    descripcion_proveedor = models.CharField(max_length=255, blank=True, null=True)
    codigo_proveedor = models.CharField(max_length=100, blank=True, null=True)

    fecha = models.DateTimeField(auto_now_add=True)
    referencia = models.CharField(max_length=100, blank=True, null=True)
    observacion = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "Movimiento de stock"
        verbose_name_plural = "Movimientos de stock"
        indexes = [
            models.Index(fields=["sucursal", "fecha"]),
            models.Index(fields=["codigo_producto", "fecha"]),
        ]

    def __str__(self):
        sucursal = self.sucursal.codigo if self.sucursal else "SIN SUCURSAL"
        return f"{self.tipo_movimiento} - {self.codigo_producto.codigo} - {sucursal} ({self.cantidad})"

    def clean(self):
        if self.cantidad is None or self.cantidad <= 0:
            raise ValidationError("La cantidad del movimiento debe ser mayor que 0.")

        if self.precio_unitario is not None and self.precio_unitario < 0:
            raise ValidationError("El precio unitario no puede ser negativo.")

        if not self.sucursal_id:
            raise ValidationError("La sucursal es obligatoria en el movimiento de stock.")
    def save(self, *args, **kwargs):
        es_nuevo = self.pk is None

        self.full_clean()

        if not es_nuevo:
            raise ValidationError(
                "No se permite editar movimientos de stock existentes."
            )

        with transaction.atomic():
            stock_obj, _ = StockSucursal.objects.select_for_update().get_or_create(
                codigo_producto=self.codigo_producto,
                sucursal=self.sucursal,
                defaults={"cantidad": Decimal("0.00")},
            )

            if self.tipo_movimiento == "entrada":
                nuevo_stock = stock_obj.cantidad + self.cantidad

            elif self.tipo_movimiento == "salida":
                # Permitimos stock negativo.
                # Esto representa descuadre pendiente de regularización.
                nuevo_stock = stock_obj.cantidad - self.cantidad

            elif self.tipo_movimiento == "ajuste":
                nuevo_stock = self.cantidad

            else:
                raise ValidationError("Tipo de movimiento inválido.")

            super().save(*args, **kwargs)

            stock_obj.cantidad = nuevo_stock
            stock_obj.save(
                update_fields=[
                    "cantidad",
                    "actualizado_en",
                ]
            )


# =========================================================
# INVENTARIO FÍSICO Y DETALLES
# =========================================================
class InventarioFisico(models.Model):
    ESTADO_CHOICES = [
        ("borrador", "Borrador"),
        ("en_proceso", "En proceso"),
        ("cerrado", "Cerrado"),
        ("aplicado", "Aplicado"),
    ]

    nombre = models.CharField(max_length=150)
    sucursal = models.ForeignKey(
        "ordenes_de_trabajo.Sucursal",
        on_delete=models.PROTECT,
        related_name="inventarios_fisicos",
        null=True,
        blank=True,
    )
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_cierre = models.DateTimeField(blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="borrador")
    observacion = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-fecha_inicio"]
        verbose_name = "Inventario físico"
        verbose_name_plural = "Inventarios físicos"

    def clean(self):
        if not self.nombre or not self.nombre.strip():
            raise ValidationError("El nombre del inventario físico es obligatorio.")

        if self.observacion:
            self.observacion = self.observacion.strip()

    def save(self, *args, **kwargs):
        if self.nombre:
            self.nombre = self.nombre.strip()
        if self.observacion:
            self.observacion = self.observacion.strip()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        sucursal = self.sucursal.codigo if self.sucursal else "SIN SUCURSAL"
        return f"{self.nombre} - {sucursal} ({self.estado})"


class DetalleInventarioFisico(models.Model):
    inventario = models.ForeignKey(InventarioFisico, on_delete=models.CASCADE, related_name="detalles")
    codigo_producto = models.ForeignKey(CodigoProducto, on_delete=models.PROTECT, related_name="conteos_inventario")
    stock_sistema = models.DecimalField(
    max_digits=12,
    decimal_places=2,
    default=Decimal("0.00")
    )

    cantidad_contada = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )
    diferencia = models.IntegerField(default=0)
    escaneado_por_barcode = models.BooleanField(default=False)
    observacion = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Detalle de inventario físico"
        verbose_name_plural = "Detalles de inventario físico"
        unique_together = ("inventario", "codigo_producto")

    def save(self, *args, **kwargs):
        if self.observacion:
            self.observacion = self.observacion.strip()

        self.diferencia = self.cantidad_contada - self.stock_sistema
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.inventario.nombre} - {self.codigo_producto.codigo} - Dif: {self.diferencia}"


# =========================================================
# KITS
# =========================================================
class KitProducto(models.Model):
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Kit"
        verbose_name_plural = "Kits"

    def clean(self):
        if not self.nombre or not self.nombre.strip():
            raise ValidationError("El nombre del kit es obligatorio.")

    def save(self, *args, **kwargs):
        if self.nombre:
            self.nombre = self.nombre.strip()
        if self.descripcion:
            self.descripcion = self.descripcion.strip()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class ComponenteKit(models.Model):
    kit = models.ForeignKey(KitProducto, on_delete=models.CASCADE, related_name="componentes")
    codigo_producto = models.ForeignKey(CodigoProducto, on_delete=models.PROTECT, related_name="componentes_de_kit")
    cantidad = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("1.00")
    )

    class Meta:
        verbose_name = "Componente de kit"
        verbose_name_plural = "Componentes de kit"
        unique_together = ("kit", "codigo_producto")

    def clean(self):
        if self.cantidad <= 0:
            raise ValidationError("La cantidad del componente debe ser mayor que 0.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.kit.nombre} - {self.codigo_producto.codigo}"

# =========================================================
# IMÁGENES
# =========================================================
class ImagenProducto(models.Model):
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name="imagenes",
        null=True,
        blank=True,
    )

    imagen = models.ImageField(upload_to="productos/")
    descripcion = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        verbose_name = "Imagen de producto"
        verbose_name_plural = "Imágenes de producto"

    def save(self, *args, **kwargs):
        if self.descripcion:
            self.descripcion = self.descripcion.strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Imagen de {self.producto.sku_interno}" if self.producto else "Imagen sin producto"


# =========================================================
# FUSIÓN DE DUPLICADOS
# =========================================================
class FusionProducto(models.Model):
    producto_principal = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="fusiones_principal")
    producto_duplicado = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="fusiones_duplicado")
    fecha = models.DateTimeField(auto_now_add=True)
    observacion = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Fusión de producto"
        verbose_name_plural = "Fusiones de producto"

    def save(self, *args, **kwargs):
        if self.observacion:
            self.observacion = self.observacion.strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.producto_duplicado} → {self.producto_principal}"

    @transaction.atomic
    def ejecutar_fusion(self):
        if self.producto_principal_id == self.producto_duplicado_id:
            raise ValidationError("No se puede fusionar un producto consigo mismo.")

        for codigo_dup in self.producto_duplicado.codigos.all():
            existe = CodigoProducto.objects.filter(
                producto=self.producto_principal,
                marca=codigo_dup.marca,
                codigo=codigo_dup.codigo,
            ).exists()

            if existe:
                codigo_dup.delete()
            else:
                codigo_dup.producto = self.producto_principal
                codigo_dup.save()

        for val in self.producto_duplicado.valores_atributos.all():
            if not ValorAtributoProducto.objects.filter(
                producto=self.producto_principal,
                atributo=val.atributo
            ).exists():
                val.producto = self.producto_principal
                val.save()
            else:
                val.delete()

        self.producto_duplicado.delete()


# =========================================================
# AUDITORÍA BÁSICA
# =========================================================
class Auditoria(models.Model):
    tabla = models.CharField(max_length=100)
    objeto_id = models.IntegerField()
    accion = models.CharField(max_length=50)
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.CharField(max_length=100, blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "Auditoría"
        verbose_name_plural = "Auditoría"

    def save(self, *args, **kwargs):
        if self.tabla:
            self.tabla = self.tabla.strip()
        if self.accion:
            self.accion = self.accion.strip()
        if self.usuario:
            self.usuario = self.usuario.strip()
        if self.descripcion:
            self.descripcion = self.descripcion.strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tabla} {self.accion} {self.objeto_id}"


# =========================================================
# VISTA RÁPIDA DE MOSTRADOR (PROXY)
# =========================================================
class CatalogoMostrador(CodigoProducto):
    class Meta:
        proxy = True
        verbose_name = "Consulta de Mostrador"
        verbose_name_plural = "Consultas de Mostrador"


# =========================================================
# NORMALIZACIÓN PARA BÚSQUEDA Y APRENDIZAJE
# =========================================================

def normalizar_texto(valor):
    """
    Genera una versión comparable sin modificar el texto original.

    Ejemplo:
        "Aceite 10W-30 API SN"
        → "ACEITE 10W 30 API SN"
    """
    texto = str(valor or "").strip().upper()

    if not texto:
        return ""

    texto = unicodedata.normalize("NFD", texto)

    texto = "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )

    texto = re.sub(r"[^A-Z0-9\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


def normalizar_codigo(valor):
    """
    Ejemplos:
        FC-8625
        FC 8625
        fc8625

    Resultado:
        FC8625
    """
    return re.sub(
        r"[^A-Z0-9]",
        "",
        str(valor or "").strip().upper(),
    )


# =========================================================
# ALIAS / VOCABULARIO DE PRODUCTOS
# =========================================================

class AliasProducto(models.Model):
    ORIGENES = [
        ("MANUAL", "Registrado manualmente"),
        ("FACTURA", "Obtenido de factura"),
        ("APRENDIZAJE", "Generado por aprendizaje"),
        ("IMPORTACION", "Importación"),
    ]

    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name="alias",
    )

    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name="alias_productos",
    )

    alias_original = models.CharField(
        max_length=255,
        help_text=(
            "Forma real en que apareció el producto. "
            "Ejemplo: CABIN FILTER, FILT HABITÁCULO o 10W30."
        ),
    )

    alias_normalizado = models.CharField(
        max_length=255,
        blank=True,
        editable=False,
        db_index=True,
    )

    codigo_producto = models.ForeignKey(
        CodigoProducto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alias",
    )

    marca = models.ForeignKey(
        MarcaRepuesto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alias_productos",
    )

    origen = models.CharField(
        max_length=20,
        choices=ORIGENES,
        default="MANUAL",
        db_index=True,
    )

    veces_confirmado = models.PositiveIntegerField(
        default=1,
    )

    activo = models.BooleanField(
        default=True,
    )

    creado_en = models.DateTimeField(
        auto_now_add=True,
    )

    actualizado_en = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-veces_confirmado",
            "alias_normalizado",
        ]

        verbose_name = "Alias de producto"
        verbose_name_plural = "Alias de productos"

        indexes = [
            models.Index(
                fields=["alias_normalizado", "activo"],
            ),
            models.Index(
                fields=["producto", "activo"],
            ),
            models.Index(
                fields=["categoria", "activo"],
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "producto",
                    "alias_normalizado",
                ],
                name="inventario_alias_unico_por_producto",
            ),
            models.CheckConstraint(
                condition=Q(veces_confirmado__gte=1),
                name="inventario_alias_confirmaciones_mayor_cero",
            ),
        ]

    def clean(self):
        errores = {}

        if (
            not self.alias_original
            or not self.alias_original.strip()
        ):
            errores["alias_original"] = (
                "El alias es obligatorio."
            )

        if (
            self.producto_id
            and self.categoria_id
            and self.producto.categoria_id
            != self.categoria_id
        ):
            errores["categoria"] = (
                "La categoría debe coincidir con "
                "la categoría del producto."
            )

        if self.codigo_producto_id:
            if (
                self.producto_id
                and self.codigo_producto.producto_id
                != self.producto_id
            ):
                errores["codigo_producto"] = (
                    "El código seleccionado no pertenece "
                    "al producto."
                )

            if (
                self.marca_id
                and self.codigo_producto.marca_id
                != self.marca_id
            ):
                errores["marca"] = (
                    "La marca no coincide con la marca "
                    "del código seleccionado."
                )

        if self.veces_confirmado < 1:
            errores["veces_confirmado"] = (
                "Debe existir al menos una confirmación."
            )

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        if self.producto_id and not self.categoria_id:
            self.categoria = self.producto.categoria

        if self.codigo_producto_id:
            if not self.producto_id:
                self.producto = self.codigo_producto.producto

            if not self.categoria_id:
                self.categoria = (
                    self.codigo_producto.producto.categoria
                )

            if not self.marca_id:
                self.marca = self.codigo_producto.marca

        self.alias_original = (
            self.alias_original or ""
        ).strip()

        self.alias_normalizado = normalizar_texto(
            self.alias_original
        )

        self.origen = (
            self.origen or "MANUAL"
        ).strip().upper()

        self.full_clean()
        super().save(*args, **kwargs)

    def registrar_confirmacion(self):
        self.veces_confirmado += 1

        self.save(
            update_fields=[
                "veces_confirmado",
                "actualizado_en",
            ]
        )

    def __str__(self):
        return (
            f"{self.alias_original} → "
            f"{self.producto.nombre_base}"
        )


# =========================================================
# APRENDIZAJE CONFIRMADO
# =========================================================

class AprendizajeProducto(models.Model):
    ORIGENES = [
        ("FACTURA", "Factura de compra"),
        ("INDIVIDUAL", "Creación individual"),
        ("MOSTRADOR", "Creación rápida"),
        ("CORRECCION", "Corrección de usuario"),
        ("IMPORTACION", "Importación"),
    ]

    detalle_original = models.ForeignKey(
        "compras.DetalleFacturaOriginal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="aprendizajes_producto",
    )

    proveedor = models.ForeignKey(
        "compras.Proveedor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="aprendizajes_producto",
    )

    origen = models.CharField(
        max_length=20,
        choices=ORIGENES,
        default="INDIVIDUAL",
        db_index=True,
    )

    texto_original = models.TextField(
        help_text=(
            "Texto original que fue confirmado. "
            "No se debe sobrescribir con el nombre limpio."
        ),
    )

    texto_normalizado = models.TextField(
        blank=True,
        editable=False,
        db_index=True,
    )

    codigo_original = models.CharField(
        max_length=150,
        blank=True,
        null=True,
    )

    codigo_normalizado = models.CharField(
        max_length=150,
        blank=True,
        editable=False,
        db_index=True,
    )

    producto_confirmado = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name="aprendizajes_confirmados",
    )

    categoria_confirmada = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name="aprendizajes_confirmados",
    )

    codigo_producto_confirmado = models.ForeignKey(
        CodigoProducto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="aprendizajes_confirmados",
    )

    marca_confirmada = models.ForeignKey(
        MarcaRepuesto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="aprendizajes_confirmados",
    )

    veces_confirmado = models.PositiveIntegerField(
        default=1,
    )

    confianza_promedio = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("100.00"),
    )

    activo = models.BooleanField(
        default=True,
    )

    confirmado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="aprendizajes_confirmados",
    )

    observacion = models.TextField(
        blank=True,
        null=True,
    )

    creado_en = models.DateTimeField(
        auto_now_add=True,
    )

    actualizado_en = models.DateTimeField(
        auto_now=True,
    )

    ultima_confirmacion_en = models.DateTimeField(
        default=timezone.now,
    )

    class Meta:
        ordering = [
            "-veces_confirmado",
            "-ultima_confirmacion_en",
        ]

        verbose_name = "Aprendizaje de producto"
        verbose_name_plural = "Aprendizajes de productos"

        indexes = [
            models.Index(
                fields=[
                    "codigo_normalizado",
                    "proveedor",
                    "activo",
                ]
            ),
            models.Index(
                fields=[
                    "texto_normalizado",
                    "activo",
                ]
            ),
            models.Index(
                fields=[
                    "producto_confirmado",
                    "activo",
                ]
            ),
            models.Index(
                fields=[
                    "categoria_confirmada",
                    "activo",
                ]
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(veces_confirmado__gte=1),
                name="inventario_aprendizaje_confirmaciones_mayor_cero",
            ),
            models.CheckConstraint(
                condition=(
                    Q(confianza_promedio__gte=0)
                    & Q(confianza_promedio__lte=100)
                ),
                name="inventario_aprendizaje_confianza_valida",
            ),
        ]

    def clean(self):
        errores = {}

        if (
            not self.texto_original
            or not self.texto_original.strip()
        ):
            errores["texto_original"] = (
                "El texto original es obligatorio."
            )

        if not self.producto_confirmado_id:
            errores["producto_confirmado"] = (
                "El producto confirmado es obligatorio."
            )

        if not self.categoria_confirmada_id:
            errores["categoria_confirmada"] = (
                "La categoría confirmada es obligatoria."
            )

        if (
            self.producto_confirmado_id
            and self.categoria_confirmada_id
            and self.producto_confirmado.categoria_id
            != self.categoria_confirmada_id
        ):
            errores["categoria_confirmada"] = (
                "La categoría no coincide con "
                "la categoría del producto."
            )

        if self.codigo_producto_confirmado_id:
            codigo = self.codigo_producto_confirmado

            if (
                self.producto_confirmado_id
                and codigo.producto_id
                != self.producto_confirmado_id
            ):
                errores["codigo_producto_confirmado"] = (
                    "El código no pertenece al producto confirmado."
                )

            if (
                self.marca_confirmada_id
                and codigo.marca_id
                != self.marca_confirmada_id
            ):
                errores["marca_confirmada"] = (
                    "La marca no coincide con el código confirmado."
                )

        if (
            self.confianza_promedio < Decimal("0.00")
            or self.confianza_promedio > Decimal("100.00")
        ):
            errores["confianza_promedio"] = (
                "La confianza debe estar entre 0 y 100."
            )

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        if self.detalle_original_id:
            detalle = self.detalle_original

            if not self.texto_original:
                self.texto_original = (
                    detalle.descripcion_proveedor
                )

            if not self.codigo_original:
                self.codigo_original = (
                    detalle.codigo_proveedor
                )

            if not self.proveedor_id:
                self.proveedor = (
                    detalle.factura.proveedor_rel
                )

            self.origen = "FACTURA"

        if self.codigo_producto_confirmado_id:
            codigo = self.codigo_producto_confirmado

            if not self.producto_confirmado_id:
                self.producto_confirmado = codigo.producto

            if not self.categoria_confirmada_id:
                self.categoria_confirmada = (
                    codigo.producto.categoria
                )

            if not self.marca_confirmada_id:
                self.marca_confirmada = codigo.marca

        elif (
            self.producto_confirmado_id
            and not self.categoria_confirmada_id
        ):
            self.categoria_confirmada = (
                self.producto_confirmado.categoria
            )

        self.texto_original = (
            self.texto_original or ""
        ).strip()

        self.texto_normalizado = normalizar_texto(
            self.texto_original
        )

        if self.codigo_original:
            self.codigo_original = (
                self.codigo_original.strip().upper()
            )

        self.codigo_normalizado = normalizar_codigo(
            self.codigo_original
        )

        if self.observacion:
            self.observacion = self.observacion.strip()

        self.full_clean()
        super().save(*args, **kwargs)

    def registrar_confirmacion(
        self,
        usuario=None,
        confianza=None,
    ):
        cantidad_anterior = self.veces_confirmado
        self.veces_confirmado += 1
        self.ultima_confirmacion_en = timezone.now()

        if usuario is not None:
            self.confirmado_por = usuario

        if confianza is not None:
            nueva = Decimal(str(confianza))

            if nueva < 0 or nueva > 100:
                raise ValidationError(
                    "La confianza debe estar entre 0 y 100."
                )

            total = (
                self.confianza_promedio
                * Decimal(cantidad_anterior)
            )

            self.confianza_promedio = (
                (total + nueva)
                / Decimal(self.veces_confirmado)
            ).quantize(Decimal("0.01"))

        self.save()

    def __str__(self):
        return (
            f"{self.texto_original[:70]} → "
            f"{self.producto_confirmado}"
        )


# =========================================================
# SUGERENCIA DEL MOTOR
# =========================================================

class SugerenciaProducto(models.Model):
    ESTADOS = [
        ("PENDIENTE", "Pendiente"),
        ("CONFIRMADA", "Confirmada"),
        ("CORREGIDA", "Corregida"),
        ("RECHAZADA", "Rechazada"),
        ("EXPIRADA", "Expirada"),
    ]

    ORIGENES = [
        ("FACTURA", "Factura de compra"),
        ("INDIVIDUAL", "Creación individual"),
        ("CODIGO", "Creación de código"),
        ("MOSTRADOR", "Creación rápida"),
        ("IMPORTACION", "Importación"),
    ]

    detalle_original = models.ForeignKey(
        "compras.DetalleFacturaOriginal",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sugerencias_producto",
    )

    proveedor = models.ForeignKey(
        "compras.Proveedor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sugerencias_producto",
    )

    origen = models.CharField(
        max_length=20,
        choices=ORIGENES,
        default="INDIVIDUAL",
        db_index=True,
    )

    texto_entrada = models.TextField()

    texto_normalizado = models.TextField(
        blank=True,
        editable=False,
        db_index=True,
    )

    codigo_entrada = models.CharField(
        max_length=150,
        blank=True,
        null=True,
    )

    codigo_normalizado = models.CharField(
        max_length=150,
        blank=True,
        editable=False,
        db_index=True,
    )

    producto_sugerido = models.ForeignKey(
        Producto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sugerencias_recibidas",
    )

    categoria_sugerida = models.ForeignKey(
        Categoria,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sugerencias_recibidas",
    )

    codigo_producto_sugerido = models.ForeignKey(
        CodigoProducto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sugerencias_recibidas",
    )

    marca_sugerida = models.ForeignKey(
        MarcaRepuesto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sugerencias_recibidas",
    )

    confianza = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    puntaje_codigo = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    puntaje_texto = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    puntaje_compras = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    puntaje_aprendizaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    puntaje_alias = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    puntaje_proveedor = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="PENDIENTE",
        db_index=True,
    )

    producto_confirmado = models.ForeignKey(
        Producto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sugerencias_confirmadas",
    )

    categoria_confirmada = models.ForeignKey(
        Categoria,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sugerencias_confirmadas",
    )

    codigo_producto_confirmado = models.ForeignKey(
        CodigoProducto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sugerencias_confirmadas",
    )

    marca_confirmada = models.ForeignKey(
        MarcaRepuesto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sugerencias_confirmadas",
    )

    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sugerencias_revisadas",
    )

    revisado_en = models.DateTimeField(
        null=True,
        blank=True,
    )

    motivo_revision = models.TextField(
        blank=True,
        null=True,
    )

    creado_en = models.DateTimeField(
        auto_now_add=True,
    )

    actualizado_en = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "estado",
            "-confianza",
            "-creado_en",
        ]

        verbose_name = "Sugerencia de producto"
        verbose_name_plural = "Sugerencias de productos"

        indexes = [
            models.Index(
                fields=[
                    "estado",
                    "confianza",
                ]
            ),
            models.Index(
                fields=[
                    "codigo_normalizado",
                    "proveedor",
                ]
            ),
            models.Index(
                fields=[
                    "texto_normalizado",
                    "estado",
                ]
            ),
            models.Index(
                fields=[
                    "origen",
                    "estado",
                ]
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(confianza__gte=0)
                    & Q(confianza__lte=100)
                ),
                name="inventario_sugerencia_confianza_valida",
            ),
        ]

    def clean(self):
        errores = {}

        if (
            not self.texto_entrada
            or not self.texto_entrada.strip()
        ):
            errores["texto_entrada"] = (
                "El texto de entrada es obligatorio."
            )

        campos_puntaje = [
            "confianza",
            "puntaje_codigo",
            "puntaje_texto",
            "puntaje_compras",
            "puntaje_aprendizaje",
            "puntaje_alias",
            "puntaje_proveedor",
        ]

        for campo in campos_puntaje:
            valor = getattr(self, campo)

            if valor < 0 or valor > 100:
                errores[campo] = (
                    "El puntaje debe estar entre 0 y 100."
                )

        if self.codigo_producto_sugerido_id:
            codigo = self.codigo_producto_sugerido

            if (
                self.producto_sugerido_id
                and codigo.producto_id
                != self.producto_sugerido_id
            ):
                errores["codigo_producto_sugerido"] = (
                    "El código no pertenece al producto sugerido."
                )

            if (
                self.marca_sugerida_id
                and codigo.marca_id
                != self.marca_sugerida_id
            ):
                errores["marca_sugerida"] = (
                    "La marca no coincide con el código sugerido."
                )

        if (
            self.producto_sugerido_id
            and self.categoria_sugerida_id
            and self.producto_sugerido.categoria_id
            != self.categoria_sugerida_id
        ):
            errores["categoria_sugerida"] = (
                "La categoría no coincide con el producto sugerido."
            )

        if self.estado in {
            "CONFIRMADA",
            "CORREGIDA",
        }:
            if not self.producto_confirmado_id:
                errores["producto_confirmado"] = (
                    "Debe indicar el producto confirmado."
                )

            if not self.categoria_confirmada_id:
                errores["categoria_confirmada"] = (
                    "Debe indicar la categoría confirmada."
                )

            if not self.revisado_en:
                errores["revisado_en"] = (
                    "Debe registrar la fecha de revisión."
                )

        if (
            self.estado == "RECHAZADA"
            and not self.revisado_en
        ):
            errores["revisado_en"] = (
                "Debe registrar la fecha de rechazo."
            )

        if self.codigo_producto_confirmado_id:
            codigo = self.codigo_producto_confirmado

            if (
                self.producto_confirmado_id
                and codigo.producto_id
                != self.producto_confirmado_id
            ):
                errores["codigo_producto_confirmado"] = (
                    "El código no pertenece al producto confirmado."
                )

            if (
                self.marca_confirmada_id
                and codigo.marca_id
                != self.marca_confirmada_id
            ):
                errores["marca_confirmada"] = (
                    "La marca no coincide con el código confirmado."
                )

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        if self.detalle_original_id:
            detalle = self.detalle_original

            if not self.texto_entrada:
                self.texto_entrada = (
                    detalle.descripcion_proveedor
                )

            if not self.codigo_entrada:
                self.codigo_entrada = (
                    detalle.codigo_proveedor
                )

            if not self.proveedor_id:
                self.proveedor = (
                    detalle.factura.proveedor_rel
                )

            self.origen = "FACTURA"

        if self.codigo_producto_sugerido_id:
            codigo = self.codigo_producto_sugerido

            if not self.producto_sugerido_id:
                self.producto_sugerido = codigo.producto

            if not self.categoria_sugerida_id:
                self.categoria_sugerida = (
                    codigo.producto.categoria
                )

            if not self.marca_sugerida_id:
                self.marca_sugerida = codigo.marca

        elif (
            self.producto_sugerido_id
            and not self.categoria_sugerida_id
        ):
            self.categoria_sugerida = (
                self.producto_sugerido.categoria
            )

        if self.codigo_producto_confirmado_id:
            codigo = self.codigo_producto_confirmado

            if not self.producto_confirmado_id:
                self.producto_confirmado = codigo.producto

            if not self.categoria_confirmada_id:
                self.categoria_confirmada = (
                    codigo.producto.categoria
                )

            if not self.marca_confirmada_id:
                self.marca_confirmada = codigo.marca

        elif (
            self.producto_confirmado_id
            and not self.categoria_confirmada_id
        ):
            self.categoria_confirmada = (
                self.producto_confirmado.categoria
            )

        self.texto_entrada = (
            self.texto_entrada or ""
        ).strip()

        self.texto_normalizado = normalizar_texto(
            self.texto_entrada
        )

        if self.codigo_entrada:
            self.codigo_entrada = (
                self.codigo_entrada.strip().upper()
            )

        self.codigo_normalizado = normalizar_codigo(
            self.codigo_entrada
        )

        if self.motivo_revision:
            self.motivo_revision = (
                self.motivo_revision.strip()
            )

        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def fue_acertada(self):
        if self.estado != "CONFIRMADA":
            return False

        return (
            self.producto_sugerido_id
            == self.producto_confirmado_id
            and self.categoria_sugerida_id
            == self.categoria_confirmada_id
            and self.codigo_producto_sugerido_id
            == self.codigo_producto_confirmado_id
            and self.marca_sugerida_id
            == self.marca_confirmada_id
        )

    def __str__(self):
        resultado = (
            self.producto_sugerido
            or self.categoria_sugerida
            or "SIN SUGERENCIA"
        )

        return (
            f"{self.texto_entrada[:60]} → "
            f"{resultado} ({self.confianza}%)"
        )