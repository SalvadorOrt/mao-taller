# inventario/services/evidencia.py

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Q

from inventario.models import (
    AliasProducto,
    AprendizajeProducto,
    Producto,
    TerminoCategoria,
)

from .normalizacion import tokenizar_texto


CERO = Decimal("0.00")
CIEN = Decimal("100.00")
DOS_DECIMALES = Decimal("0.01")


class MotorEvidenciaCategoria:
    """
    Calcula evidencia para categorías usando información
    almacenada en la base de datos.

    Fuentes:

    1. Términos configurados por categoría.
    2. Alias confirmados.
    3. Aprendizajes confirmados.
    4. Productos existentes.
    """

    def __init__(
        self,
        *,
        limite_tokens=10,
        minimo_coincidencias=1,
        limite_resultados=20,
    ):
        self.limite_tokens = max(
            int(limite_tokens),
            1,
        )

        self.minimo_coincidencias = max(
            int(minimo_coincidencias),
            1,
        )

        self.limite_resultados = max(
            int(limite_resultados),
            1,
        )

    # =====================================================
    # API PRINCIPAL
    # =====================================================

    def analizar(self, texto):
        tokens = tokenizar_texto(texto)[
            :self.limite_tokens
        ]

        if not tokens:
            return []

        evidencia = defaultdict(
            lambda: {
                "categoria": None,
                "puntaje_total": CERO,
                "coincidencias": 0,
                "tokens": {},
                "fuentes": set(),
            }
        )

        for token in tokens:
            self._evidencia_terminos(
                token=token,
                evidencia=evidencia,
            )

            self._evidencia_alias(
                token=token,
                evidencia=evidencia,
            )

            self._evidencia_aprendizajes(
                token=token,
                evidencia=evidencia,
            )

            self._evidencia_catalogo(
                token=token,
                evidencia=evidencia,
            )
            self._evidencia_compras(
                token=token,
                evidencia=evidencia,
            )
        resultados = []

        for grupo in evidencia.values():
            categoria = grupo["categoria"]

            if categoria is None:
                continue

            if (
                grupo["coincidencias"]
                < self.minimo_coincidencias
            ):
                continue

            cantidad_tokens = max(
                len(grupo["tokens"]),
                1,
            )

            promedio = (
                grupo["puntaje_total"]
                / Decimal(cantidad_tokens)
            )

            puntaje = self._limitar_porcentaje(
                promedio
            )

            resultados.append({
                "categoria": categoria,
                "puntaje": puntaje,
                "coincidencias": grupo[
                    "coincidencias"
                ],
                "tokens": grupo["tokens"],
                "fuentes": sorted(
                    grupo["fuentes"]
                ),
            })

        resultados.sort(
            key=lambda item: (
                item["puntaje"],
                item["coincidencias"],
            ),
            reverse=True,
        )

        return resultados[
            :self.limite_resultados
        ]

    # =====================================================
    # TÉRMINOS CONFIGURADOS POR CATEGORÍA
    # =====================================================

    def _evidencia_terminos(
        self,
        *,
        token,
        evidencia,
    ):
        terminos = (
            TerminoCategoria.objects
            .filter(
                activo=True,
                termino__icontains=token,
            )
            .select_related("categoria")
        )

        for termino in terminos:
            categoria = termino.categoria

            peso = Decimal(
                str(termino.peso or 0)
            )

            if termino.tipo == "NEGATIVO":
                puntaje = -abs(peso)

            elif termino.tipo == "SINONIMO":
                puntaje = (
                    abs(peso)
                    * Decimal("0.90")
                )

            else:
                puntaje = abs(peso)

            self._registrar(
                evidencia=evidencia,
                categoria=categoria,
                token=token,
                puntaje=puntaje,
                cantidad=1,
                fuente="TERMINO_CATEGORIA",
            )

    # =====================================================
    # ALIAS CONFIRMADOS
    # =====================================================

    def _evidencia_alias(
        self,
        *,
        token,
        evidencia,
    ):
        alias_encontrados = (
            AliasProducto.objects
            .filter(
                activo=True,
                alias_normalizado__icontains=token,
            )
            .select_related(
                "categoria",
                "producto",
            )
            .order_by(
                "-veces_confirmado"
            )[:300]
        )

        for alias in alias_encontrados:
            confirmaciones = Decimal(
                alias.veces_confirmado
                or 1
            )

            bonificacion = min(
                confirmaciones
                * Decimal("1.50"),
                Decimal("15.00"),
            )

            puntaje = (
                Decimal("15.00")
                + bonificacion
            )

            self._registrar(
                evidencia=evidencia,
                categoria=alias.categoria,
                token=token,
                puntaje=puntaje,
                cantidad=1,
                fuente="ALIAS",
            )

    # =====================================================
    # APRENDIZAJES CONFIRMADOS
    # =====================================================

    def _evidencia_aprendizajes(
        self,
        *,
        token,
        evidencia,
    ):
        aprendizajes = (
            AprendizajeProducto.objects
            .filter(
                activo=True,
                texto_normalizado__icontains=token,
            )
            .select_related(
                "categoria_confirmada",
                "producto_confirmado",
            )
            .order_by(
                "-veces_confirmado",
                "-ultima_confirmacion_en",
            )[:300]
        )

        for aprendizaje in aprendizajes:
            confirmaciones = Decimal(
                aprendizaje.veces_confirmado
                or 1
            )

            confianza = Decimal(
                str(
                    aprendizaje.confianza_promedio
                    or 0
                )
            )

            bonificacion_confirmaciones = min(
                confirmaciones
                * Decimal("2.00"),
                Decimal("20.00"),
            )

            bonificacion_confianza = (
                confianza
                * Decimal("0.20")
            )

            puntaje = (
                Decimal("20.00")
                + bonificacion_confirmaciones
                + bonificacion_confianza
            )

            self._registrar(
                evidencia=evidencia,
                categoria=(
                    aprendizaje
                    .categoria_confirmada
                ),
                token=token,
                puntaje=puntaje,
                cantidad=1,
                fuente="APRENDIZAJE",
            )

    # =====================================================
    # CATÁLOGO EXISTENTE
    # =====================================================

    def _evidencia_catalogo(
        self,
        *,
        token,
        evidencia,
    ):
        productos = (
            Producto.objects
            .filter(
                activo=True,
                descontinuado=False,
            )
            .filter(
                Q(nombre_base__icontains=token)
                | Q(descripcion__icontains=token)
                | Q(
                    codigos__nombre_comercial__icontains=
                    token
                )
            )
            .select_related("categoria")
            .distinct()[:300]
        )

        total_productos = productos.count()

        if total_productos == 0:
            return

        conteo_categorias = defaultdict(
            lambda: {
                "categoria": None,
                "cantidad": 0,
            }
        )

        for producto in productos:
            categoria = producto.categoria

            grupo = conteo_categorias[
                categoria.pk
            ]

            grupo["categoria"] = categoria
            grupo["cantidad"] += 1

        especificidad = self._peso_especificidad(
            token=token,
            total_coincidencias=total_productos,
        )

        for grupo in conteo_categorias.values():
            categoria = grupo["categoria"]
            cantidad = grupo["cantidad"]

            concentracion = (
                Decimal(cantidad)
                / Decimal(total_productos)
            )

            puntaje = (
                concentracion
                * especificidad
                * Decimal("35.00")
            )

            self._registrar(
                evidencia=evidencia,
                categoria=categoria,
                token=token,
                puntaje=puntaje,
                cantidad=cantidad,
                fuente="CATALOGO",
            )
    # =====================================================
    # COMPRAS CONFIRMADAS
    # =====================================================

    def _evidencia_compras(
        self,
        *,
        token,
        evidencia,
    ):
        from compras.models import (
            DetalleFacturaNormalizado,
        )

        detalles = (
            DetalleFacturaNormalizado.objects
            .filter(
                tipo_destino="INVENTARIO",
                producto_rel__isnull=False,
                producto_rel__activo=True,
                producto_rel__descontinuado=False,
            )
            .exclude(
                factura_manual__estado="ANULADA",
            )
            .filter(
                Q(
                    nombre_limpio__icontains=token
                )
                | Q(
                    descripcion_origen__icontains=token
                )
                | Q(
                    codigo_origen__icontains=token
                )
                | Q(
                    codigo_sistema__icontains=token
                )
                | Q(
                    detalle_original__descripcion_proveedor__icontains=token
                )
                | Q(
                    detalle_original__codigo_proveedor__icontains=token
                )
            )
            .select_related(
                "producto_rel",
                "producto_rel__categoria",
                "detalle_original",
                "detalle_original__factura",
                "factura_manual",
            )
            .order_by(
                "-actualizado_en",
            )[:300]
        )

        for detalle in detalles:
            producto = detalle.producto_rel

            if not producto or not producto.categoria_id:
                continue

            factura = detalle.factura

            if not factura:
                continue

            if factura.estado == "ANULADA":
                continue

            if (
                factura.estado == "PROCESADA"
                and detalle.ingresado_al_inventario
            ):
                puntaje = Decimal("35.00")
                fuente = "COMPRA_PROCESADA"

            elif factura.estado == "PROCESADA":
                puntaje = Decimal("25.00")
                fuente = "COMPRA_CONFIRMADA"

            else:
                continue

            self._registrar(
                evidencia=evidencia,
                categoria=producto.categoria,
                token=token,
                puntaje=puntaje,
                cantidad=1,
                fuente=fuente,
            )
    # =====================================================
    # REGISTRO DE EVIDENCIA
    # =====================================================

    @staticmethod
    def _registrar(
        *,
        evidencia,
        categoria,
        token,
        puntaje,
        cantidad,
        fuente,
    ):
        if categoria is None:
            return

        grupo = evidencia[categoria.pk]

        grupo["categoria"] = categoria
        grupo["puntaje_total"] += Decimal(
            str(puntaje or 0)
        )

        grupo["coincidencias"] += int(
            cantidad or 0
        )

        grupo["fuentes"].add(fuente)

        token_info = grupo["tokens"].setdefault(
            token,
            {
                "puntaje": CERO,
                "coincidencias": 0,
                "fuentes": set(),
            },
        )

        token_info["puntaje"] += Decimal(
            str(puntaje or 0)
        )

        token_info["coincidencias"] += int(
            cantidad or 0
        )

        token_info["fuentes"].add(fuente)

    # =====================================================
    # UTILIDADES
    # =====================================================

    @staticmethod
    def _peso_especificidad(
        *,
        token,
        total_coincidencias,
    ):
        peso = Decimal("1.00")

        if any(
            caracter.isdigit()
            for caracter in token
        ):
            peso += Decimal("0.35")

        if len(token) >= 6:
            peso += Decimal("0.10")

        if total_coincidencias >= 100:
            peso *= Decimal("0.50")

        elif total_coincidencias >= 50:
            peso *= Decimal("0.70")

        elif total_coincidencias >= 20:
            peso *= Decimal("0.85")

        return peso

    @staticmethod
    def _limitar_porcentaje(valor):
        valor = Decimal(
            str(valor or 0)
        )

        return min(
            max(valor, CERO),
            CIEN,
        ).quantize(
            DOS_DECIMALES,
            rounding=ROUND_HALF_UP,
        )