# inventario/services/creacion_producto.py

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from compras.models import DetalleFacturaNormalizado, DetalleFacturaOriginal
from inventario.models import (
    AliasProducto,
    AprendizajeProducto,
    Categoria,
    CodigoProducto,
    MarcaRepuesto,
    Producto,
)

from .aprendizaje import AprendizajeProductoService
from .normalizacion import normalizar_codigo, normalizar_texto


CERO = Decimal("0.00")


class CreacionProductoService:
    """
    Servicio central para crear:

    - productos individuales;
    - productos desde factura;
    - códigos equivalentes;
    - vínculos entre factura y producto existente.

    Consultar sugerencias NO genera aprendizaje.

    El aprendizaje solo se registra cuando existe una decisión
    confirmada por el usuario.
    """

    ORIGENES_VALIDOS = {
        "INDIVIDUAL",
        "FACTURA",
        "MOSTRADOR",
    }

    # =====================================================
    # VALIDACIONES
    # =====================================================

    @staticmethod
    def _decimal(valor, *, default=None, nombre="valor"):
        if valor in {None, ""}:
            return default

        try:
            return Decimal(str(valor))
        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ) as error:
            raise ValidationError(
                f"{nombre} debe ser un número válido."
            ) from error

    @classmethod
    def _validar_origen(cls, origen):
        origen = str(
            origen or "INDIVIDUAL"
        ).strip().upper()

        if origen not in cls.ORIGENES_VALIDOS:
            raise ValidationError(
                f"Origen inválido: {origen}."
            )

        return origen

    @staticmethod
    def _validar_categoria(categoria):
        if not isinstance(
            categoria,
            Categoria,
        ):
            raise ValidationError(
                "Debe proporcionar una categoría válida."
            )

        return categoria

    @staticmethod
    def _validar_marca(marca):
        if not isinstance(
            marca,
            MarcaRepuesto,
        ):
            raise ValidationError(
                "Debe proporcionar una marca válida."
            )

        return marca

    @staticmethod
    def _validar_producto(producto):
        if not isinstance(
            producto,
            Producto,
        ):
            raise ValidationError(
                "Debe proporcionar un producto válido."
            )

        return producto

    @staticmethod
    def _validar_codigo_producto(codigo_producto):
        if not isinstance(
            codigo_producto,
            CodigoProducto,
        ):
            raise ValidationError(
                "Debe proporcionar un código de producto válido."
            )

        return codigo_producto

    @staticmethod
    def _validar_detalle_original(detalle_original):
        if not isinstance(
            detalle_original,
            DetalleFacturaOriginal,
        ):
            raise ValidationError(
                "Debe proporcionar un detalle original "
                "de factura válido."
            )

        return detalle_original

    @staticmethod
    def _validar_texto(nombre_base):
        nombre = str(
            nombre_base or ""
        ).strip()

        if not nombre:
            raise ValidationError(
                "El nombre base del producto es obligatorio."
            )

        return nombre

    @staticmethod
    def _validar_codigo(codigo):
        codigo = str(
            codigo or ""
        ).strip()

        if not codigo:
            raise ValidationError(
                "El código comercial es obligatorio."
            )

        if not normalizar_codigo(codigo):
            raise ValidationError(
                "El código comercial no contiene "
                "caracteres válidos."
            )

        return codigo

    # =====================================================
    # DUPLICADOS
    # =====================================================

    @staticmethod
    def _buscar_codigo_existente(codigo, marca):
        codigo_normalizado = normalizar_codigo(
            codigo
        )

        if not codigo_normalizado:
            return None

        return (
            CodigoProducto.objects
            .select_related(
                "producto",
                "producto__categoria",
                "marca",
            )
            .filter(
                codigo_normalizado=codigo_normalizado,
                marca=marca,
            )
            .order_by("id")
            .first()
        )

    @staticmethod
    def _buscar_producto_similar_exacto(
        nombre_base,
        categoria,
    ):
        nombre_normalizado = normalizar_texto(
            nombre_base
        )

        if not nombre_normalizado:
            return None

        productos = (
            Producto.objects
            .select_for_update()
            .filter(
                categoria=categoria,
                activo=True,
                descontinuado=False,
            )
            .only(
                "id",
                "nombre_base",
                "categoria_id",
                "sku_interno",
            )
        )

        for producto in productos:
            if (
                normalizar_texto(
                    producto.nombre_base
                )
                == nombre_normalizado
            ):
                return producto

        return None

    @classmethod
    def _validar_codigo_no_asignado_otro_producto(
        cls,
        *,
        codigo,
        marca,
        producto=None,
    ):
        existente = cls._buscar_codigo_existente(
            codigo=codigo,
            marca=marca,
        )

        if existente is None:
            return None

        if (
            producto is not None
            and existente.producto_id
            == producto.pk
        ):
            return existente

        raise ValidationError(
            "Ya existe un código equivalente con la misma marca: "
            f"{existente.marca.nombre} {existente.codigo}. "
            f"Pertenece al producto {existente.producto}."
        )

    # =====================================================
    # CREACIÓN DE PRODUCTO
    # =====================================================

    @classmethod
    def _crear_producto(
        cls,
        *,
        categoria,
        nombre_base,
        descripcion=None,
        origen="INDIVIDUAL",
        usuario=None,
        datos_incompletos=False,
        detalle_origen_creacion=None,
        permitir_producto_existente=False,
    ):
        categoria = cls._validar_categoria(
            categoria
        )

        nombre_base = cls._validar_texto(
            nombre_base
        )

        origen = cls._validar_origen(
            origen
        )

        # =================================================
        # TRAZABILIDAD DE FACTURA
        # =================================================

        if origen == "FACTURA":

            if detalle_origen_creacion is None:
                raise ValidationError(
                    "Un producto creado desde factura debe "
                    "conservar el detalle original que dio "
                    "origen a su creación."
                )

            detalle_origen_creacion = (
                cls._validar_detalle_original(
                    detalle_origen_creacion
                )
            )

        elif detalle_origen_creacion is not None:
            raise ValidationError(
                "El detalle de origen solo puede asignarse "
                "a productos creados desde factura."
            )

        # =================================================
        # PRODUCTO EXISTENTE
        # =================================================

        if permitir_producto_existente:
            producto_existente = (
                cls._buscar_producto_similar_exacto(
                    nombre_base=nombre_base,
                    categoria=categoria,
                )
            )

            if producto_existente is not None:
                return (
                    producto_existente,
                    False,
                )

        # =================================================
        # NUEVO PRODUCTO
        # =================================================

        producto = Producto(
            categoria=categoria,
            nombre_base=nombre_base,
            descripcion=(
                str(descripcion).strip()
                if descripcion
                else None
            ),
            origen=origen,
            detalle_origen_creacion=(
                detalle_origen_creacion
            ),
            creado_por=usuario,
            datos_incompletos=bool(
                datos_incompletos
            ),
            activo=True,
            descontinuado=False,
        )

        producto.full_clean()
        producto.save()

        return producto, True

    # =====================================================
    # CREACIÓN INTERNA DE CÓDIGO
    # =====================================================

    @classmethod
    def _crear_codigo_producto(
        cls,
        *,
        producto,
        marca,
        codigo,
        tipo_codigo="aftermarket",
        codigo_barras=None,
        nombre_comercial=None,
        presentacion_cantidad=None,
        presentacion_unidad=None,
        precio_compra=None,
        precio_venta=None,
        margen_ganancia_porcentaje=Decimal(
            "100.00"
        ),
        porcentaje_iva_costo=Decimal(
            "0.00"
        ),
        permitir_codigo_existente=False,
    ):
        producto = cls._validar_producto(
            producto
        )

        marca = cls._validar_marca(
            marca
        )

        codigo = cls._validar_codigo(
            codigo
        )

        existente = (
            cls._validar_codigo_no_asignado_otro_producto(
                codigo=codigo,
                marca=marca,
                producto=producto,
            )
        )

        if existente is not None:

            if permitir_codigo_existente:
                return existente, False

            raise ValidationError(
                "Este código ya está registrado "
                "en el producto seleccionado."
            )

        precio_compra = cls._decimal(
            precio_compra,
            default=None,
            nombre="El precio de compra",
        )

        precio_venta = cls._decimal(
            precio_venta,
            default=None,
            nombre="El precio de venta",
        )

        presentacion_cantidad = cls._decimal(
            presentacion_cantidad,
            default=None,
            nombre="La cantidad de presentación",
        )

        margen = cls._decimal(
            margen_ganancia_porcentaje,
            default=Decimal("100.00"),
            nombre="El margen de ganancia",
        )

        porcentaje_iva = cls._decimal(
            porcentaje_iva_costo,
            default=CERO,
            nombre="El porcentaje de IVA",
        )

        if (
            precio_compra is not None
            and precio_compra < CERO
        ):
            raise ValidationError(
                "El precio de compra no puede ser negativo."
            )

        if (
            precio_venta is not None
            and precio_venta < CERO
        ):
            raise ValidationError(
                "El precio de venta no puede ser negativo."
            )

        if (
            presentacion_cantidad is not None
            and presentacion_cantidad <= CERO
        ):
            raise ValidationError(
                "La cantidad de presentación "
                "debe ser mayor que cero."
            )

        if margen < CERO:
            raise ValidationError(
                "El margen de ganancia no puede ser negativo."
            )

        if porcentaje_iva < CERO:
            raise ValidationError(
                "El porcentaje de IVA no puede ser negativo."
            )

        codigo_producto = CodigoProducto(
            producto=producto,
            marca=marca,
            codigo=codigo,
            tipo_codigo=tipo_codigo,
            codigo_barras=(
                str(codigo_barras).strip()
                if codigo_barras
                else None
            ),
            nombre_comercial=(
                str(nombre_comercial).strip()
                if nombre_comercial
                else None
            ),
            presentacion_cantidad=(
                presentacion_cantidad
            ),
            presentacion_unidad=(
                str(
                    presentacion_unidad
                ).strip().upper()
                if presentacion_unidad
                else None
            ),
            precio_compra=precio_compra,
            precio_venta=precio_venta,
            margen_ganancia_porcentaje=margen,
            porcentaje_iva_costo=porcentaje_iva,
            activo=True,
        )

        codigo_producto.full_clean()
        codigo_producto.save()

        return codigo_producto, True

    # =====================================================
    # NUEVO CÓDIGO EQUIVALENTE - API PÚBLICA
    # =====================================================

    @classmethod
    @transaction.atomic
    def agregar_codigo_equivalente(
        cls,
        *,
        producto,
        marca,
        codigo,
        tipo_codigo="aftermarket",
        codigo_barras=None,
        nombre_comercial=None,
        presentacion_cantidad=None,
        presentacion_unidad=None,
        precio_compra=None,
        precio_venta=None,
        margen_ganancia_porcentaje=Decimal(
            "100.00"
        ),
        porcentaje_iva_costo=Decimal(
            "0.00"
        ),
        activo=True,
        usuario=None,
        texto_original=None,
        registrar_aprendizaje=False,
        confianza=100,
        permitir_codigo_existente=False,
    ):
        """
        Agrega una referencia comercial equivalente a un Producto
        ya existente.

        Esta es la API pública que deben utilizar las vistas.

        Evita que las vistas llamen directamente a
        _crear_codigo_producto().

        También centraliza:

        - validación de marca;
        - normalización del código;
        - detección de duplicados;
        - precios;
        - presentación;
        - IVA;
        - estado;
        - aprendizaje opcional.
        """

        producto = cls._validar_producto(
            producto
        )

        codigo_producto, codigo_creado = (
            cls._crear_codigo_producto(
                producto=producto,
                marca=marca,
                codigo=codigo,
                tipo_codigo=tipo_codigo,
                codigo_barras=codigo_barras,
                nombre_comercial=nombre_comercial,
                presentacion_cantidad=(
                    presentacion_cantidad
                ),
                presentacion_unidad=(
                    presentacion_unidad
                ),
                precio_compra=precio_compra,
                precio_venta=precio_venta,
                margen_ganancia_porcentaje=(
                    margen_ganancia_porcentaje
                ),
                porcentaje_iva_costo=(
                    porcentaje_iva_costo
                ),
                permitir_codigo_existente=(
                    permitir_codigo_existente
                ),
            )
        )

        # =================================================
        # ESTADO
        # =================================================

        activo = bool(activo)

        if codigo_producto.activo != activo:
            codigo_producto.activo = activo

            codigo_producto.save(
                update_fields=[
                    "activo",
                    "actualizado_en",
                ]
            )

        # =================================================
        # APRENDIZAJE OPCIONAL
        # =================================================

        aprendizaje = None

        if registrar_aprendizaje:
            texto_aprendizaje = str(
                texto_original
                or nombre_comercial
                or producto.nombre_base
                or ""
            ).strip()

            aprendizaje = (
                cls._registrar_aprendizaje(
                    texto_original=(
                        texto_aprendizaje
                    ),
                    codigo_original=codigo,
                    producto=producto,
                    codigo_producto=(
                        codigo_producto
                    ),
                    origen="INDIVIDUAL",
                    usuario=usuario,
                    confianza=confianza,
                )
            )

        return {
            "producto": producto,
            "codigo_producto": codigo_producto,
            "codigo_creado": codigo_creado,
            "aprendizaje": aprendizaje,
        }

    # =====================================================
    # APRENDIZAJE
    # =====================================================

    @classmethod
    def _registrar_aprendizaje(
        cls,
        *,
        texto_original,
        codigo_original,
        producto,
        codigo_producto,
        origen,
        usuario=None,
        proveedor=None,
        detalle_original=None,
        sugerencia=None,
        confianza=100,
    ):
        texto_original = str(
            texto_original or ""
        ).strip()

        codigo_original = str(
            codigo_original or ""
        ).strip()

        if not texto_original and not codigo_original:
            return None

        producto = cls._validar_producto(
            producto
        )

        codigo_producto = (
            cls._validar_codigo_producto(
                codigo_producto
            )
        )

        if (
            codigo_producto.producto_id
            != producto.pk
        ):
            raise ValidationError(
                "El código seleccionado no pertenece "
                "al producto indicado."
            )

        origen = cls._validar_origen(
            origen
        )

        if sugerencia is not None:
            return (
                AprendizajeProductoService
                .confirmar_sugerencia(
                    sugerencia=sugerencia,
                    producto=producto,
                    categoria=producto.categoria,
                    codigo_producto=(
                        codigo_producto
                    ),
                    marca=codigo_producto.marca,
                    usuario=usuario,
                )
            )

        return AprendizajeProductoService.registrar(
            texto_original=texto_original,
            codigo_original=codigo_original,
            producto=producto,
            categoria=producto.categoria,
            codigo_producto=codigo_producto,
            marca=codigo_producto.marca,
            proveedor=proveedor,
            detalle_original=detalle_original,
            origen=origen,
            usuario=usuario,
            confianza=confianza,
            crear_alias=bool(
                texto_original
            ),
        )

    # =====================================================
    # CREACIÓN INDIVIDUAL
    # =====================================================

    @classmethod
    @transaction.atomic
    def crear_individual(
        cls,
        *,
        categoria,
        nombre_base,
        marca,
        codigo,
        texto_original=None,
        descripcion=None,
        nombre_comercial=None,
        tipo_codigo="aftermarket",
        codigo_barras=None,
        presentacion_cantidad=None,
        presentacion_unidad=None,
        precio_compra=None,
        precio_venta=None,
        margen_ganancia_porcentaje=Decimal(
            "100.00"
        ),
        porcentaje_iva_costo=Decimal(
            "0.00"
        ),
        usuario=None,
        sugerencia=None,
        registrar_aprendizaje=True,
        confianza=100,
        permitir_producto_existente=False,
        permitir_codigo_existente=False,
    ):
        producto, producto_creado = (
            cls._crear_producto(
                categoria=categoria,
                nombre_base=nombre_base,
                descripcion=descripcion,
                origen="INDIVIDUAL",
                usuario=usuario,
                datos_incompletos=False,
                detalle_origen_creacion=None,
                permitir_producto_existente=(
                    permitir_producto_existente
                ),
            )
        )

        codigo_producto, codigo_creado = (
            cls._crear_codigo_producto(
                producto=producto,
                marca=marca,
                codigo=codigo,
                tipo_codigo=tipo_codigo,
                codigo_barras=codigo_barras,
                nombre_comercial=(
                    nombre_comercial
                    or nombre_base
                ),
                presentacion_cantidad=(
                    presentacion_cantidad
                ),
                presentacion_unidad=(
                    presentacion_unidad
                ),
                precio_compra=precio_compra,
                precio_venta=precio_venta,
                margen_ganancia_porcentaje=(
                    margen_ganancia_porcentaje
                ),
                porcentaje_iva_costo=(
                    porcentaje_iva_costo
                ),
                permitir_codigo_existente=(
                    permitir_codigo_existente
                ),
            )
        )

        aprendizaje = None

        if registrar_aprendizaje:
            texto_aprendizaje = (
                str(
                    texto_original
                ).strip()
                if texto_original
                else (
                    nombre_comercial
                    or nombre_base
                )
            )

            aprendizaje = (
                cls._registrar_aprendizaje(
                    texto_original=(
                        texto_aprendizaje
                    ),
                    codigo_original=codigo,
                    producto=producto,
                    codigo_producto=(
                        codigo_producto
                    ),
                    origen="INDIVIDUAL",
                    usuario=usuario,
                    sugerencia=sugerencia,
                    confianza=confianza,
                )
            )

        return {
            "producto": producto,
            "codigo_producto": codigo_producto,
            "producto_creado": producto_creado,
            "codigo_creado": codigo_creado,
            "aprendizaje": aprendizaje,
        }

    # =====================================================
    # CREACIÓN DESDE FACTURA
    # =====================================================

    @classmethod
    @transaction.atomic
    def crear_desde_factura(
        cls,
        *,
        detalle_original,
        categoria,
        nombre_base,
        marca,
        codigo=None,
        descripcion=None,
        nombre_comercial=None,
        tipo_codigo="aftermarket",
        codigo_barras=None,
        presentacion_cantidad=None,
        presentacion_unidad=None,
        precio_venta=None,
        margen_ganancia_porcentaje=Decimal(
            "100.00"
        ),
        usuario=None,
        sugerencia=None,
        registrar_aprendizaje=True,
        confianza=100,
        permitir_producto_existente=False,
        permitir_codigo_existente=False,
        vincular_detalle_normalizado=True,
    ):
        """
        Crea un producto desde una línea de factura.

        - DetalleFacturaOriginal conserva evidencia original.
        - Producto conserva qué detalle originó su creación.
        - DetalleFacturaNormalizado conserva la interpretación.
        - AprendizajeProducto aprende del nombre/código original.
        """

        detalle_original = (
            cls._validar_detalle_original(
                detalle_original
            )
        )

        codigo_final = str(
            codigo
            or detalle_original.codigo_proveedor
            or ""
        ).strip()

        if not codigo_final:
            raise ValidationError(
                "La factura no contiene código de proveedor. "
                "Debe ingresar un código comercial."
            )

        descripcion_original = str(
            detalle_original.descripcion_proveedor
            or ""
        ).strip()

        # =================================================
        # PRODUCTO
        # =================================================

        producto, producto_creado = (
            cls._crear_producto(
                categoria=categoria,
                nombre_base=nombre_base,
                descripcion=(
                    descripcion
                    or descripcion_original
                ),
                origen="FACTURA",
                usuario=usuario,
                datos_incompletos=False,
                detalle_origen_creacion=(
                    detalle_original
                ),
                permitir_producto_existente=(
                    permitir_producto_existente
                ),
            )
        )

        # =================================================
        # CÓDIGO
        # =================================================

        codigo_producto, codigo_creado = (
            cls._crear_codigo_producto(
                producto=producto,
                marca=marca,
                codigo=codigo_final,
                tipo_codigo=tipo_codigo,
                codigo_barras=codigo_barras,
                nombre_comercial=(
                    nombre_comercial
                    or descripcion_original
                    or nombre_base
                ),
                presentacion_cantidad=(
                    presentacion_cantidad
                ),
                presentacion_unidad=(
                    presentacion_unidad
                ),
                precio_compra=(
                    detalle_original.precio_unitario
                ),
                precio_venta=precio_venta,
                margen_ganancia_porcentaje=(
                    margen_ganancia_porcentaje
                ),
                porcentaje_iva_costo=(
                    detalle_original.porcentaje_iva
                    if detalle_original.aplica_iva
                    else CERO
                ),
                permitir_codigo_existente=(
                    permitir_codigo_existente
                ),
            )
        )

        # =================================================
        # DETALLE NORMALIZADO
        # =================================================

        detalle_normalizado = None

        if vincular_detalle_normalizado:
            detalle_normalizado = (
                cls._vincular_detalle_normalizado(
                    detalle_original=(
                        detalle_original
                    ),
                    producto=producto,
                    codigo_producto=(
                        codigo_producto
                    ),
                )
            )

        # =================================================
        # APRENDIZAJE
        # =================================================

        aprendizaje = None

        if registrar_aprendizaje:
            proveedor = getattr(
                detalle_original.factura,
                "proveedor_rel",
                None,
            )

            aprendizaje = (
                cls._registrar_aprendizaje(
                    texto_original=(
                        descripcion_original
                    ),
                    codigo_original=(
                        codigo_final
                    ),
                    producto=producto,
                    codigo_producto=(
                        codigo_producto
                    ),
                    origen="FACTURA",
                    usuario=usuario,
                    proveedor=proveedor,
                    detalle_original=(
                        detalle_original
                    ),
                    sugerencia=sugerencia,
                    confianza=confianza,
                )
            )

        return {
            "producto": producto,
            "codigo_producto": codigo_producto,
            "detalle_normalizado": detalle_normalizado,
            "producto_creado": producto_creado,
            "codigo_creado": codigo_creado,
            "aprendizaje": aprendizaje,
        }

    # =====================================================
    # VINCULAR PRODUCTO EXISTENTE DESDE FACTURA
    # =====================================================

    @classmethod
    @transaction.atomic
    def vincular_existente_desde_factura(
        cls,
        *,
        detalle_original,
        producto,
        codigo_producto,
        usuario=None,
        sugerencia=None,
        confianza=100,
        registrar_aprendizaje=True,
    ):
        detalle_original = (
            cls._validar_detalle_original(
                detalle_original
            )
        )

        producto = cls._validar_producto(
            producto
        )

        codigo_producto = (
            cls._validar_codigo_producto(
                codigo_producto
            )
        )

        if (
            codigo_producto.producto_id
            != producto.pk
        ):
            raise ValidationError(
                "El código no pertenece al "
                "producto seleccionado."
            )

        detalle_normalizado = (
            cls._vincular_detalle_normalizado(
                detalle_original=detalle_original,
                producto=producto,
                codigo_producto=codigo_producto,
            )
        )

        aprendizaje = None

        if registrar_aprendizaje:
            proveedor = getattr(
                detalle_original.factura,
                "proveedor_rel",
                None,
            )

            aprendizaje = (
                cls._registrar_aprendizaje(
                    texto_original=(
                        detalle_original
                        .descripcion_proveedor
                    ),
                    codigo_original=(
                        detalle_original
                        .codigo_proveedor
                    ),
                    producto=producto,
                    codigo_producto=(
                        codigo_producto
                    ),
                    origen="FACTURA",
                    usuario=usuario,
                    proveedor=proveedor,
                    detalle_original=(
                        detalle_original
                    ),
                    sugerencia=sugerencia,
                    confianza=confianza,
                )
            )

        return {
            "producto": producto,
            "codigo_producto": codigo_producto,
            "detalle_normalizado": detalle_normalizado,
            "aprendizaje": aprendizaje,
        }

    # =====================================================
    # DETALLE NORMALIZADO
    # =====================================================

    @staticmethod
    def _vincular_detalle_normalizado(
        *,
        detalle_original,
        producto,
        codigo_producto,
    ):
        """
        Crea o actualiza la interpretación MAO de una línea
        de factura.

        DetalleFacturaOriginal NO se modifica.
        """

        normalizado, _ = (
            DetalleFacturaNormalizado.objects
            .select_for_update()
            .get_or_create(
                detalle_original=detalle_original,
                defaults={
                    "tipo_destino": "INVENTARIO",
                    "aplica_iva": (
                        detalle_original.aplica_iva
                    ),
                    "porcentaje_iva": (
                        detalle_original
                        .porcentaje_iva
                    ),
                    "codigo_sistema": (
                        codigo_producto.codigo
                    ),
                    "nombre_limpio": (
                        producto.nombre_base
                    ),
                    "marca_limpia": (
                        codigo_producto.marca.nombre
                    ),
                    "categoria_limpia": (
                        producto.categoria.nombre
                    ),
                    "codigo_barras": (
                        codigo_producto.codigo_barras
                    ),
                    "producto_rel": producto,
                    "codigo_producto_rel": (
                        codigo_producto
                    ),
                    "cantidad": (
                        detalle_original.cantidad
                    ),
                    "costo_unitario": (
                        detalle_original
                        .precio_unitario
                    ),
                    "descuento": (
                        detalle_original.descuento
                    ),
                    "ingresado_al_inventario": (
                        False
                    ),
                },
            )
        )

        normalizado.tipo_destino = (
            "INVENTARIO"
        )

        normalizado.aplica_iva = (
            detalle_original.aplica_iva
        )

        normalizado.porcentaje_iva = (
            detalle_original.porcentaje_iva
        )

        normalizado.codigo_sistema = (
            codigo_producto.codigo
        )

        normalizado.nombre_limpio = (
            producto.nombre_base
        )

        normalizado.marca_limpia = (
            codigo_producto.marca.nombre
        )

        normalizado.categoria_limpia = (
            producto.categoria.nombre
        )

        normalizado.codigo_barras = (
            codigo_producto.codigo_barras
        )

        normalizado.producto_rel = (
            producto
        )

        normalizado.codigo_producto_rel = (
            codigo_producto
        )

        normalizado.cantidad = (
            detalle_original.cantidad
        )

        normalizado.costo_unitario = (
            detalle_original.precio_unitario
        )

        normalizado.descuento = (
            detalle_original.descuento
        )

        normalizado.full_clean()
        normalizado.save()

        return normalizado

    # =====================================================
    # CAMBIO DE CATEGORÍA
    # =====================================================

    @staticmethod
    @transaction.atomic
    def corregir_categoria(
        *,
        producto,
        nueva_categoria,
    ):
        if not isinstance(
            producto,
            Producto,
        ):
            raise ValidationError(
                "Debe proporcionar un producto válido."
            )

        if not isinstance(
            nueva_categoria,
            Categoria,
        ):
            raise ValidationError(
                "Debe proporcionar una categoría válida."
            )

        producto = (
            Producto.objects
            .select_for_update()
            .get(
                pk=producto.pk
            )
        )

        if (
            producto.categoria_id
            == nueva_categoria.pk
        ):
            return producto

        producto.categoria = nueva_categoria

        producto.full_clean()
        producto.save()

        # =================================================
        # NORMALIZACIONES DE FACTURA
        # =================================================

        (
            DetalleFacturaNormalizado.objects
            .filter(
                producto_rel=producto
            )
            .update(
                categoria_limpia=(
                    nueva_categoria.nombre
                )
            )
        )

        # =================================================
        # ALIAS
        # =================================================

        (
            AliasProducto.objects
            .filter(
                producto=producto
            )
            .update(
                categoria=nueva_categoria
            )
        )

        # =================================================
        # APRENDIZAJE
        # =================================================

        (
            AprendizajeProducto.objects
            .filter(
                producto_confirmado=producto
            )
            .update(
                categoria_confirmada=(
                    nueva_categoria
                )
            )
        )

        return producto