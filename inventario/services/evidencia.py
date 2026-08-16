# inventario/services/evidencia.py

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from math import log

from django.db.models import Q

from inventario.models import (
    AliasProducto,
    AprendizajeProducto,
    Categoria,
    Producto,
    TerminoCategoria,
)

from .normalizacion import normalizar_texto, tokenizar_texto


CERO = Decimal("0.00")
CIEN = Decimal("100.00")
DOS_DECIMALES = Decimal("0.01")


class MotorEvidenciaCategoria:
    """
    Calcula evidencia para determinar la categoría más probable.

    No contiene vocabulario automotriz ni listas de palabras
    predefinidas.

    La importancia de cada token se calcula dinámicamente
    según su frecuencia real dentro de la base de datos.

    Fuentes:

    1. Nombre de categorías.
    2. Términos configurados.
    3. Alias confirmados.
    4. Aprendizajes confirmados.
    5. Catálogo existente.
    6. Compras históricas confirmadas.
    """

    def __init__(
        self,
        *,
        limite_tokens=10,
        minimo_coincidencias=1,
        limite_resultados=20,
    ):
        self.limite_tokens = max(int(limite_tokens), 1)
        self.minimo_coincidencias = max(int(minimo_coincidencias), 1)
        self.limite_resultados = max(int(limite_resultados), 1)

        # Cache por instancia.
        # Una misma consulta puede necesitar calcular el peso
        # del mismo token varias veces.
        self._cache_pesos = {}
        self._total_documentos_cache = None

    # =====================================================
    # API PRINCIPAL
    # =====================================================

    def analizar(self, texto):
        texto_normalizado = normalizar_texto(texto)

        tokens = self._tokens_unicos(
            texto_normalizado
        )[:self.limite_tokens]

        if not tokens:
            return []

        # Peso estadístico de cada palabra según la BD.
        pesos_tokens = {
            token: self._peso_token(token)
            for token in tokens
        }

        evidencia = defaultdict(
            lambda: {
                "categoria": None,
                "puntaje_directo": CERO,
                "coincidencias": 0,
                "tokens": {},
                "fuentes": set(),
            }
        )

        # =================================================
        # 1. NOMBRE REAL DE LAS CATEGORÍAS
        # =================================================

        self._evidencia_nombre_categoria(
            texto_normalizado=texto_normalizado,
            tokens=tokens,
            pesos_tokens=pesos_tokens,
            evidencia=evidencia,
        )

        # =================================================
        # 2. RESTO DE FUENTES
        # =================================================

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

        # =================================================
        # RESULTADO FINAL
        # =================================================

        resultados = []

        peso_total_consulta = sum(
            pesos_tokens.values(),
            CERO,
        )

        # Si la base todavía no tiene suficiente información
        # estadística, todos los tokens reciben peso equivalente.
        if peso_total_consulta <= CERO:
            pesos_tokens = {
                token: Decimal("1.00")
                for token in tokens
            }

            peso_total_consulta = Decimal(
                len(tokens)
            )

        for grupo in evidencia.values():
            categoria = grupo["categoria"]

            if categoria is None:
                continue

            if (
                grupo["coincidencias"] < self.minimo_coincidencias
                and grupo["puntaje_directo"] <= CERO
            ):
                continue

            suma_ponderada = CERO
            peso_coincidente = CERO

            for token in tokens:
                peso_token = pesos_tokens[token]
                info = grupo["tokens"].get(token)

                if not info:
                    continue

                puntaje_token = Decimal(
                    str(info["puntaje"] or 0)
                )

                puntaje_token = min(
                    max(
                        puntaje_token,
                        Decimal("-100.00"),
                    ),
                    CIEN,
                )

                suma_ponderada += (
                    puntaje_token
                    * peso_token
                )

                if puntaje_token > CERO:
                    peso_coincidente += peso_token

            puntaje_evidencia = (
                suma_ponderada
                / peso_total_consulta
                if peso_total_consulta > CERO
                else CERO
            )

            puntaje_evidencia = (
                self._limitar_porcentaje(
                    puntaje_evidencia
                )
            )

            cobertura = (
                peso_coincidente
                / peso_total_consulta
                if peso_total_consulta > CERO
                else CERO
            )

            # La cobertura ya está ponderada por importancia.
            # No necesitamos listas de stopwords.
            puntaje_evidencia *= cobertura

            puntaje_evidencia = (
                self._limitar_porcentaje(
                    puntaje_evidencia
                )
            )

            # Una coincidencia directa contra el nombre
            # real de una categoría puede superar la
            # evidencia estadística general.
            puntaje_final = max(
                puntaje_evidencia,
                grupo["puntaje_directo"],
            )

            resultados.append({
                "categoria": categoria,
                "puntaje": self._limitar_porcentaje(
                    puntaje_final
                ),
                "coincidencias": grupo["coincidencias"],
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
    # NOMBRE DE CATEGORÍA
    # =====================================================

    def _evidencia_nombre_categoria(
        self,
        *,
        texto_normalizado,
        tokens,
        pesos_tokens,
        evidencia,
    ):
        tokens_consulta = set(tokens)

        categorias = Categoria.objects.all()

        for categoria in categorias:
            nombre_normalizado = normalizar_texto(
                categoria.nombre
            )

            if not nombre_normalizado:
                continue

            tokens_categoria = self._tokens_unicos(
                nombre_normalizado
            )

            if not tokens_categoria:
                continue

            tokens_categoria_set = set(
                tokens_categoria
            )

            interseccion = (
                tokens_categoria_set
                & tokens_consulta
            )

            if not interseccion:
                continue

            # =============================================
            # COINCIDENCIA EXACTA
            # =============================================

            if texto_normalizado == nombre_normalizado:
                puntaje = CIEN

            else:
                # =========================================
                # SIMILITUD PONDERADA
                #
                # No todas las palabras valen igual.
                #
                # Su peso viene de la frecuencia observada
                # en la base de datos.
                # =========================================

                peso_categoria = CERO
                peso_categoria_coincidente = CERO

                for token in tokens_categoria:
                    peso = self._peso_token(token)

                    peso_categoria += peso

                    if token in tokens_consulta:
                        peso_categoria_coincidente += peso

                peso_consulta = sum(
                    pesos_tokens.values(),
                    CERO,
                )

                peso_consulta_coincidente = sum(
                    (
                        pesos_tokens[token]
                        for token in interseccion
                        if token in pesos_tokens
                    ),
                    CERO,
                )

                cobertura_categoria = (
                    peso_categoria_coincidente
                    / peso_categoria
                    if peso_categoria > CERO
                    else CERO
                )

                cobertura_consulta = (
                    peso_consulta_coincidente
                    / peso_consulta
                    if peso_consulta > CERO
                    else CERO
                )

                # Para categorizar interesa principalmente
                # saber si la categoría está contenida en
                # la descripción del producto.
                puntaje = (
                    (
                        cobertura_categoria
                        * Decimal("0.90")
                    )
                    +
                    (
                        cobertura_consulta
                        * Decimal("0.10")
                    )
                ) * CIEN

                puntaje = self._limitar_porcentaje(
                    puntaje
                )

            grupo = evidencia[categoria.pk]

            grupo["categoria"] = categoria

            grupo["puntaje_directo"] = max(
                grupo["puntaje_directo"],
                puntaje,
            )

            grupo["fuentes"].add(
                "NOMBRE_CATEGORIA"
            )

            grupo["coincidencias"] += 1

            for token in interseccion:
                self._registrar(
                    evidencia=evidencia,
                    categoria=categoria,
                    token=token,
                    puntaje=puntaje,
                    cantidad=0,
                    fuente="NOMBRE_CATEGORIA",
                )

    # =====================================================
    # TÉRMINOS CONFIGURADOS
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
                categoria=termino.categoria,
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
        aliases = (
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

        for alias in aliases:
            confirmaciones = Decimal(
                alias.veces_confirmado or 1
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
                aprendizaje.veces_confirmado or 1
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
        productos = list(
            Producto.objects
            .filter(
                activo=True,
                descontinuado=False,
            )
            .filter(
                Q(nombre_base__icontains=token)
                | Q(descripcion__icontains=token)
                | Q(
                    codigos__nombre_comercial__icontains=token
                )
                | Q(
                    codigos__codigo__icontains=token
                )
                | Q(
                    codigos__marca__nombre__icontains=token
                )
            )
            .select_related("categoria")
            .distinct()[:300]
        )

        total_productos = len(productos)

        if total_productos == 0:
            return

        conteo = defaultdict(
            lambda: {
                "categoria": None,
                "cantidad": 0,
            }
        )

        for producto in productos:
            categoria = producto.categoria

            if categoria is None:
                continue

            grupo = conteo[categoria.pk]

            grupo["categoria"] = categoria
            grupo["cantidad"] += 1

        for grupo in conteo.values():
            categoria = grupo["categoria"]
            cantidad = grupo["cantidad"]

            concentracion = (
                Decimal(cantidad)
                / Decimal(total_productos)
            )

            puntaje = (
                concentracion
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
    # COMPRAS HISTÓRICAS
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
            .filter(
                Q(nombre_limpio__icontains=token)
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
                "-actualizado_en"
            )[:300]
        )

        for detalle in detalles:
            producto = detalle.producto_rel

            if (
                not producto
                or not producto.categoria_id
            ):
                continue

            factura = None

            if (
                detalle.detalle_original_id
                and detalle.detalle_original
            ):
                factura = (
                    detalle.detalle_original.factura
                )

            elif detalle.factura_manual_id:
                factura = detalle.factura_manual

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
    # REGISTRAR EVIDENCIA
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

        grupo["coincidencias"] += int(
            cantidad or 0
        )

        grupo["fuentes"].add(
            fuente
        )

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

        token_info["fuentes"].add(
            fuente
        )

    # =====================================================
    # TOKENS
    # =====================================================

    @staticmethod
    def _tokens_unicos(texto):
        resultado = []

        for token in tokenizar_texto(texto):
            token = str(
                token or ""
            ).strip().upper()

            if not token:
                continue

            if token not in resultado:
                resultado.append(token)

        return resultado

    # =====================================================
    # TOTAL DE DOCUMENTOS DEL CORPUS
    # =====================================================

    def _total_documentos(self):
        if self._total_documentos_cache is not None:
            return self._total_documentos_cache

        from compras.models import (
            DetalleFacturaNormalizado,
        )

        total = (
            Categoria.objects.count()
            + Producto.objects.filter(
                activo=True,
                descontinuado=False,
            ).count()
            + AliasProducto.objects.filter(
                activo=True
            ).count()
            + AprendizajeProducto.objects.filter(
                activo=True
            ).count()
            + DetalleFacturaNormalizado.objects.filter(
                tipo_destino="INVENTARIO",
            ).count()
        )

        self._total_documentos_cache = max(
            int(total),
            1,
        )

        return self._total_documentos_cache

    # =====================================================
    # FRECUENCIA DOCUMENTAL DE UN TOKEN
    # =====================================================

    def _frecuencia_token(self, token):
        from compras.models import (
            DetalleFacturaNormalizado,
        )

        categorias = (
            Categoria.objects
            .filter(
                nombre__icontains=token
            )
            .count()
        )

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
                    codigos__nombre_comercial__icontains=token
                )
                | Q(
                    codigos__codigo__icontains=token
                )
                | Q(
                    codigos__marca__nombre__icontains=token
                )
            )
            .distinct()
            .count()
        )

        aliases = (
            AliasProducto.objects
            .filter(
                activo=True,
                alias_normalizado__icontains=token,
            )
            .count()
        )

        aprendizajes = (
            AprendizajeProducto.objects
            .filter(
                activo=True,
            )
            .filter(
                Q(texto_normalizado__icontains=token)
                | Q(
                    codigo_normalizado__icontains=token
                )
            )
            .count()
        )

        compras = (
            DetalleFacturaNormalizado.objects
            .filter(
                tipo_destino="INVENTARIO",
            )
            .filter(
                Q(nombre_limpio__icontains=token)
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
            .count()
        )

        return (
            categorias
            + productos
            + aliases
            + aprendizajes
            + compras
        )

    # =====================================================
    # PESO ESTADÍSTICO DEL TOKEN
    # =====================================================

    def _peso_token(self, token):
        """
        Calcula un peso tipo IDF usando exclusivamente
        los datos reales almacenados.

        Token muy frecuente:
            peso bajo

        Token poco frecuente:
            peso alto

        No existe ninguna lista de palabras especiales.
        """

        if token in self._cache_pesos:
            return self._cache_pesos[token]

        total = self._total_documentos()
        frecuencia = self._frecuencia_token(token)

        if total <= 1:
            peso = Decimal("1.00")

        else:
            numerador = log(
                (total + 1)
                / (frecuencia + 1)
            )

            denominador = log(
                total + 1
            )

            valor = (
                numerador / denominador
                if denominador > 0
                else 1
            )

            peso = Decimal(
                str(valor)
            )

        peso = min(
            max(peso, CERO),
            Decimal("1.00"),
        ).quantize(
            Decimal("0.0001"),
            rounding=ROUND_HALF_UP,
        )

        self._cache_pesos[token] = peso

        return peso

    # =====================================================
    # LIMITAR PORCENTAJE
    # =====================================================

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