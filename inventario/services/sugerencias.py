# inventario/services/sugerencias.py

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from difflib import SequenceMatcher

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from .evidencia import MotorEvidenciaCategoria
from compras.models import (
    DetalleFacturaNormalizado,
    DetalleFacturaOriginal,
)
from inventario.models import (
    AliasProducto,
    AprendizajeProducto,
    Categoria,
    CodigoProducto,
    Producto,
    SugerenciaProducto,
)

from .normalizacion import (
    normalizar_codigo,
    normalizar_texto,
    tokenizar_texto,
)


CERO = Decimal("0.00")
CIEN = Decimal("100.00")
DOS_DECIMALES = Decimal("0.01")


class MotorSugerenciasProducto:
    """
    Genera sugerencias usando exclusivamente información existente
    y confirmada en la base de datos.

    Fuentes consultadas:

    1. Código exacto.
    2. Aprendizajes confirmados.
    3. Alias confirmados.
    4. Compras históricas normalizadas.
    5. Productos y códigos comerciales existentes.
    """

    ORIGENES_VALIDOS = {
        "FACTURA",
        "INDIVIDUAL",
        "CODIGO",
        "MOSTRADOR",
        "IMPORTACION",
    }

    def __init__(
        self,
        *,
        limite_resultados=5,
        limite_candidatos=300,
        umbral_minimo=25,
    ):
        self.limite_resultados = max(
            int(limite_resultados),
            1,
        )   
        self.motor_evidencia = MotorEvidenciaCategoria()
        self.limite_candidatos = max(
            int(limite_candidatos),
            20,
        )

        self.umbral_minimo = self._decimal(
            umbral_minimo,
            default=Decimal("25.00"),
        )

    # =====================================================
    # UTILIDADES
    # =====================================================

    @staticmethod
    def _decimal(
        valor,
        *,
        default=CERO,
    ):
        try:
            resultado = Decimal(
                str(
                    default
                    if valor is None
                    else valor
                )
            )
        except Exception:
            return Decimal(default)

        return resultado.quantize(
            DOS_DECIMALES,
            rounding=ROUND_HALF_UP,
        )

    @staticmethod
    def _limitar_porcentaje(valor):
        valor = Decimal(str(valor or 0))

        return min(
            max(valor, CERO),
            CIEN,
        ).quantize(
            DOS_DECIMALES,
            rounding=ROUND_HALF_UP,
        )

    @staticmethod
    def _validar_origen(origen):
        origen = str(
            origen or "INDIVIDUAL"
        ).strip().upper()

        if origen not in (
            MotorSugerenciasProducto.ORIGENES_VALIDOS
        ):
            raise ValidationError(
                f"Origen de sugerencia inválido: {origen}."
            )

        return origen

    @staticmethod
    def _similitud_texto(texto_a, texto_b):
        texto_a = normalizar_texto(texto_a)
        texto_b = normalizar_texto(texto_b)

        if not texto_a or not texto_b:
            return CERO

        secuencia = Decimal(
            str(
                SequenceMatcher(
                    None,
                    texto_a,
                    texto_b,
                ).ratio()
            )
        )

        tokens_a = set(tokenizar_texto(texto_a))
        tokens_b = set(tokenizar_texto(texto_b))

        interseccion = tokens_a & tokens_b
        union = tokens_a | tokens_b

        jaccard = (
            Decimal(len(interseccion))
            / Decimal(len(union))
            if union
            else CERO
        )

        cobertura = (
            Decimal(len(interseccion))
            / Decimal(len(tokens_a))
            if tokens_a
            else CERO
        )

        # Tokens con números suelen ser más específicos:
        # 10W30, 5W40, FC8625, 4L, 1GAL, etc.
        tokens_especificos = {
            token
            for token in tokens_a
            if any(caracter.isdigit() for caracter in token)
        }

        especificos_coincidentes = (
            tokens_especificos & tokens_b
        )

        coincidencia_especifica = (
            Decimal(len(especificos_coincidentes))
            / Decimal(len(tokens_especificos))
            if tokens_especificos
            else CERO
        )

        puntaje = (
            secuencia * Decimal("0.20")
            + jaccard * Decimal("0.20")
            + cobertura * Decimal("0.25")
            + coincidencia_especifica * Decimal("0.35")
        ) * CIEN

        # Penaliza candidatos que ignoran todos los tokens
        # específicos escritos por el usuario.
        if (
            tokens_especificos
            and not especificos_coincidentes
        ):
            puntaje *= Decimal("0.65")

        return MotorSugerenciasProducto._limitar_porcentaje(
            puntaje
        )

    @staticmethod
    def _ponderar(*valores):
        """
        Calcula el promedio usando únicamente fuentes que realmente
        encontraron evidencia.

        Una fuente con puntaje 0 no debe reducir artificialmente
        la confianza de las demás.
        """
        total = CERO
        pesos_activos = CERO

        for puntaje, peso in valores:
            puntaje = Decimal(str(puntaje or 0))
            peso = Decimal(str(peso or 0))

            if puntaje <= CERO or peso <= CERO:
                continue

            total += puntaje * peso
            pesos_activos += peso

        if pesos_activos <= CERO:
            return CERO

        return (
            total / pesos_activos
        ).quantize(
            DOS_DECIMALES,
            rounding=ROUND_HALF_UP,
        )

    @staticmethod
    def _clave_resultado(
        producto,
        codigo_producto=None,
    ):
        return (
            producto.pk,
            (
                codigo_producto.pk
                if codigo_producto
                else None
            ),
        )

    @staticmethod
    def _estructura_resultado(
        *,
        producto,
        codigo_producto=None,
    ):
        marca = (
            codigo_producto.marca
            if codigo_producto
            else None
        )

        return {
            "producto": producto,
            "categoria": producto.categoria,
            "codigo_producto": codigo_producto,
            "marca": marca,

            "puntaje_codigo": CERO,
            "puntaje_texto": CERO,
            "puntaje_compras": CERO,
            "puntaje_aprendizaje": CERO,
            "puntaje_alias": CERO,
            "puntaje_proveedor": CERO,

            "confianza": CERO,
            "fuentes": set(),
        }

    # =====================================================
    # REDUCCIÓN DE CANDIDATOS
    # =====================================================

    def _filtro_por_tokens(
        self,
        texto,
        *,
        campos,
    ):
        """
        Construye un Q dinámico usando tokens ingresados.

        No contiene vocabulario automotriz quemado.
        """
        tokens = tokenizar_texto(texto)

        consulta = Q()

        for token in tokens[:6]:
            if len(token) < 2:
                continue

            for campo in campos:
                consulta |= Q(
                    **{
                        f"{campo}__icontains": token
                    }
                )

        return consulta

    # =====================================================
    # RESULTADOS POR CÓDIGO
    # =====================================================

    def _buscar_por_codigo(
        self,
        *,
        codigo_normalizado,
        resultados,
    ):
        if not codigo_normalizado:
            return

        codigos = (
            CodigoProducto.objects
            .filter(activo=True)
            .select_related(
                "producto",
                "producto__categoria",
                "marca",
            )
            .filter(
                Q(
                    codigo_normalizado=
                    codigo_normalizado
                )
                | Q(
                    codigo_barras=
                    codigo_normalizado
                )
            )[:self.limite_candidatos]
        )

        for codigo_producto in codigos:
            producto = codigo_producto.producto

            clave = self._clave_resultado(
                producto,
                codigo_producto,
            )

            resultado = resultados.setdefault(
                clave,
                self._estructura_resultado(
                    producto=producto,
                    codigo_producto=codigo_producto,
                ),
            )

            resultado["puntaje_codigo"] = CIEN
            resultado["fuentes"].add(
                "CODIGO_EXACTO"
            )

    # =====================================================
    # RESULTADOS DESDE APRENDIZAJE
    # =====================================================

    def _buscar_en_aprendizajes(
        self,
        *,
        texto,
        codigo_normalizado,
        proveedor,
        resultados,
    ):
        queryset = (
            AprendizajeProducto.objects
            .filter(activo=True)
            .select_related(
                "producto_confirmado",
                "producto_confirmado__categoria",
                "codigo_producto_confirmado",
                "codigo_producto_confirmado__marca",
                "proveedor",
            )
        )

        filtro = self._filtro_por_tokens(
            texto,
            campos=[
                "texto_normalizado",
            ],
        )

        if codigo_normalizado:
            filtro |= Q(
                codigo_normalizado=
                codigo_normalizado
            )

        if filtro:
            queryset = queryset.filter(filtro)

        queryset = queryset.order_by(
            "-veces_confirmado",
            "-ultima_confirmacion_en",
        )[:self.limite_candidatos]

        for aprendizaje in queryset:
            producto = (
                aprendizaje.producto_confirmado
            )

            codigo_producto = (
                aprendizaje
                .codigo_producto_confirmado
            )

            clave = self._clave_resultado(
                producto,
                codigo_producto,
            )

            resultado = resultados.setdefault(
                clave,
                self._estructura_resultado(
                    producto=producto,
                    codigo_producto=codigo_producto,
                ),
            )

            puntaje_texto = self._similitud_texto(
                texto,
                aprendizaje.texto_original,
            )

            puntaje_codigo = CERO

            if codigo_normalizado:
                if (
                    aprendizaje.codigo_normalizado
                    == codigo_normalizado
                ):
                    puntaje_codigo = CIEN
                elif aprendizaje.codigo_normalizado:
                    puntaje_codigo = (
                        self._similitud_texto(
                            codigo_normalizado,
                            aprendizaje.codigo_normalizado,
                        )
                    )

            fuerza_confirmacion = min(
                Decimal(
                    aprendizaje.veces_confirmado
                )
                * Decimal("4.00"),
                Decimal("20.00"),
            )

            puntaje_aprendizaje = min(
                max(
                    puntaje_texto,
                    puntaje_codigo,
                )
                + fuerza_confirmacion,
                CIEN,
            )

            resultado["puntaje_aprendizaje"] = max(
                resultado[
                    "puntaje_aprendizaje"
                ],
                puntaje_aprendizaje,
            )

            resultado["puntaje_texto"] = max(
                resultado["puntaje_texto"],
                puntaje_texto,
            )

            resultado["puntaje_codigo"] = max(
                resultado["puntaje_codigo"],
                puntaje_codigo,
            )

            if (
                proveedor
                and aprendizaje.proveedor_id
                == proveedor.pk
            ):
                resultado["puntaje_proveedor"] = max(
                    resultado[
                        "puntaje_proveedor"
                    ],
                    Decimal("100.00"),
                )

                resultado["fuentes"].add(
                    "MISMO_PROVEEDOR"
                )

            resultado["fuentes"].add(
                "APRENDIZAJE"
            )

    # =====================================================
    # RESULTADOS DESDE ALIAS
    # =====================================================

    def _buscar_en_alias(
        self,
        *,
        texto,
        resultados,
    ):
        filtro = self._filtro_por_tokens(
            texto,
            campos=[
                "alias_normalizado",
            ],
        )

        queryset = AliasProducto.objects.filter(
            activo=True
        )

        if filtro:
            queryset = queryset.filter(filtro)

        queryset = (
            queryset
            .select_related(
                "producto",
                "producto__categoria",
                "codigo_producto",
                "codigo_producto__marca",
            )
            .order_by(
                "-veces_confirmado",
                "-actualizado_en",
            )[:self.limite_candidatos]
        )

        for alias in queryset:
            producto = alias.producto
            codigo_producto = alias.codigo_producto

            clave = self._clave_resultado(
                producto,
                codigo_producto,
            )

            resultado = resultados.setdefault(
                clave,
                self._estructura_resultado(
                    producto=producto,
                    codigo_producto=codigo_producto,
                ),
            )

            puntaje = self._similitud_texto(
                texto,
                alias.alias_original,
            )

            fuerza = min(
                Decimal(alias.veces_confirmado)
                * Decimal("3.00"),
                Decimal("15.00"),
            )

            puntaje = min(
                puntaje + fuerza,
                CIEN,
            )

            resultado["puntaje_alias"] = max(
                resultado["puntaje_alias"],
                puntaje,
            )

            resultado["puntaje_texto"] = max(
                resultado["puntaje_texto"],
                self._similitud_texto(
                    texto,
                    alias.alias_original,
                ),
            )

            resultado["fuentes"].add(
                "ALIAS"
            )

    # =====================================================
    # RESULTADOS DESDE COMPRAS HISTÓRICAS
    # =====================================================

    def _buscar_en_compras(
        self,
        *,
        texto,
        codigo_normalizado,
        proveedor,
        excluir_detalle=None,
        resultados,
    ):
        queryset = (
            DetalleFacturaNormalizado.objects
            .filter(
                producto_rel__isnull=False,
                ingresado_al_inventario=True,
            )
            .select_related(
                "detalle_original",
                "detalle_original__factura",
                "detalle_original__factura__proveedor_rel",
                "producto_rel",
                "producto_rel__categoria",
                "codigo_producto_rel",
                "codigo_producto_rel__marca",
            )
        )

        if excluir_detalle is not None:
            queryset = queryset.exclude(
                detalle_original=excluir_detalle
            )

        filtro = self._filtro_por_tokens(
            texto,
            campos=[
                "detalle_original__descripcion_proveedor",
                "nombre_limpio",
            ],
        )

        if codigo_normalizado:
            filtro |= Q(
                detalle_original__codigo_proveedor__icontains=
                codigo_normalizado
            )

        if filtro:
            queryset = queryset.filter(filtro)

        queryset = queryset.order_by(
            "-actualizado_en",
        )[:self.limite_candidatos]

        for normalizado in queryset:
            detalle = normalizado.detalle_original

            if detalle is None:
                continue

            producto = normalizado.producto_rel
            codigo_producto = (
                normalizado.codigo_producto_rel
            )

            clave = self._clave_resultado(
                producto,
                codigo_producto,
            )

            resultado = resultados.setdefault(
                clave,
                self._estructura_resultado(
                    producto=producto,
                    codigo_producto=codigo_producto,
                ),
            )

            puntaje_texto = self._similitud_texto(
                texto,
                detalle.descripcion_proveedor,
            )

            puntaje_codigo = CERO

            codigo_historico = normalizar_codigo(
                detalle.codigo_proveedor
            )

            if (
                codigo_normalizado
                and codigo_historico
            ):
                if (
                    codigo_normalizado
                    == codigo_historico
                ):
                    puntaje_codigo = CIEN
                else:
                    puntaje_codigo = (
                        self._similitud_texto(
                            codigo_normalizado,
                            codigo_historico,
                        )
                    )

            puntaje_compra = max(
                puntaje_texto,
                puntaje_codigo,
            )

            resultado["puntaje_compras"] = max(
                resultado["puntaje_compras"],
                puntaje_compra,
            )

            resultado["puntaje_texto"] = max(
                resultado["puntaje_texto"],
                puntaje_texto,
            )

            resultado["puntaje_codigo"] = max(
                resultado["puntaje_codigo"],
                puntaje_codigo,
            )

            proveedor_historico = (
                detalle.factura.proveedor_rel
            )

            if (
                proveedor
                and proveedor_historico
                and proveedor_historico.pk
                == proveedor.pk
            ):
                resultado["puntaje_proveedor"] = max(
                    resultado[
                        "puntaje_proveedor"
                    ],
                    Decimal("100.00"),
                )

                resultado["fuentes"].add(
                    "MISMO_PROVEEDOR"
                )

            resultado["fuentes"].add(
                "COMPRA_CONFIRMADA"
            )

    # =====================================================
    # RESULTADOS DESDE CATÁLOGO
    # =====================================================

    def _buscar_en_catalogo(
        self,
        *,
        texto,
        codigo_normalizado,
        resultados,
    ):
        filtro_productos = self._filtro_por_tokens(
            texto,
            campos=[
                "nombre_base",
                "descripcion",
                "codigos__nombre_comercial",
            ],
        )

        productos = (
            Producto.objects
            .filter(
                activo=True,
                descontinuado=False,
            )
            .select_related("categoria")
            .prefetch_related(
                "codigos",
                "codigos__marca",
            )
            .distinct()
        )

        if filtro_productos:
            productos = productos.filter(
                filtro_productos
            )

        productos = productos[
            :self.limite_candidatos
        ]

        for producto in productos:
            puntaje_producto = max(
                self._similitud_texto(
                    texto,
                    producto.nombre_base,
                ),
                self._similitud_texto(
                    texto,
                    producto.descripcion,
                ),
            )

            codigos = list(
                producto.codigos.all()
            )

            if not codigos:
                clave = self._clave_resultado(
                    producto,
                    None,
                )

                resultado = resultados.setdefault(
                    clave,
                    self._estructura_resultado(
                        producto=producto,
                    ),
                )

                resultado["puntaje_texto"] = max(
                    resultado["puntaje_texto"],
                    puntaje_producto,
                )

                resultado["fuentes"].add(
                    "CATALOGO"
                )

                continue

            for codigo_producto in codigos:
                puntaje_comercial = (
                    self._similitud_texto(
                        texto,
                        codigo_producto.nombre_comercial,
                    )
                )

                puntaje_codigo = CERO

                if codigo_normalizado:
                    codigo_catalogo = (
                        codigo_producto
                        .codigo_normalizado
                    )

                    if (
                        codigo_catalogo
                        == codigo_normalizado
                    ):
                        puntaje_codigo = CIEN

                    elif codigo_catalogo:
                        puntaje_codigo = (
                            self._similitud_texto(
                                codigo_normalizado,
                                codigo_catalogo,
                            )
                        )

                clave = self._clave_resultado(
                    producto,
                    codigo_producto,
                )

                resultado = resultados.setdefault(
                    clave,
                    self._estructura_resultado(
                        producto=producto,
                        codigo_producto=codigo_producto,
                    ),
                )

                resultado["puntaje_texto"] = max(
                    resultado["puntaje_texto"],
                    puntaje_producto,
                    puntaje_comercial,
                )

                resultado["puntaje_codigo"] = max(
                    resultado["puntaje_codigo"],
                    puntaje_codigo,
                )

                resultado["fuentes"].add(
                    "CATALOGO"
                )

    # =====================================================
    # CÁLCULO FINAL
    # =====================================================

    def _calcular_confianza(self, resultado):
        codigo = resultado["puntaje_codigo"]
        aprendizaje = resultado["puntaje_aprendizaje"]
        compras = resultado["puntaje_compras"]
        alias = resultado["puntaje_alias"]
        texto = resultado["puntaje_texto"]
        proveedor = resultado["puntaje_proveedor"]

        # Coincidencia exacta de código.
        if codigo >= Decimal("99.00"):
            if (
                proveedor >= Decimal("90.00")
                or aprendizaje >= Decimal("80.00")
                or compras >= Decimal("80.00")
            ):
                return CIEN

            return Decimal("98.00")

        confianza = self._ponderar(
            (codigo, Decimal("0.30")),
            (aprendizaje, Decimal("0.25")),
            (compras, Decimal("0.20")),
            (alias, Decimal("0.15")),
            (texto, Decimal("0.10")),
            (proveedor, Decimal("0.05")),
        )

        fuentes_fuertes = sum([
            codigo >= Decimal("70.00"),
            aprendizaje >= Decimal("70.00"),
            compras >= Decimal("70.00"),
            alias >= Decimal("70.00"),
            texto >= Decimal("70.00"),
        ])

        if fuentes_fuertes >= 2:
            confianza += Decimal("7.00")

        elif fuentes_fuertes == 1:
            confianza += Decimal("3.00")

        return self._limitar_porcentaje(confianza)

    def _ordenar_resultados(
        self,
        resultados,
    ):
        lista = []

        for resultado in resultados.values():
            resultado["confianza"] = (
                self._calcular_confianza(
                    resultado
                )
            )

            if (
                resultado["confianza"]
                < self.umbral_minimo
            ):
                continue

            resultado["fuentes"] = sorted(
                resultado["fuentes"]
            )

            lista.append(resultado)

        lista.sort(
            key=lambda item: (
                item["confianza"],
                item["puntaje_codigo"],
                item["puntaje_aprendizaje"],
                item["puntaje_compras"],
                item["puntaje_alias"],
                item["puntaje_texto"],
            ),
            reverse=True,
        )

        # No limitar todavía.
        # La agrupación de categorías necesita más candidatos.
        return lista

    @staticmethod
    def _agrupar_categorias(resultados):
        acumulado = defaultdict(
            lambda: {
                "categoria": None,
                "productos": {},
            }
        )

        for resultado in resultados:
            categoria = resultado["categoria"]
            producto = resultado["producto"]

            if categoria is None or producto is None:
                continue

            grupo = acumulado[categoria.pk]
            grupo["categoria"] = categoria

            confianza = resultado["confianza"]

            # Un mismo producto puede aparecer por varios códigos.
            # Conservamos únicamente su mejor coincidencia.
            confianza_anterior = grupo["productos"].get(
                producto.pk
            )

            if (
                confianza_anterior is None
                or confianza > confianza_anterior
            ):
                grupo["productos"][producto.pk] = confianza

        categorias = []

        pesos = [
            Decimal("1.00"),
            Decimal("0.85"),
            Decimal("0.70"),
            Decimal("0.55"),
            Decimal("0.45"),
            Decimal("0.35"),
            Decimal("0.30"),
            Decimal("0.25"),
            Decimal("0.20"),
            Decimal("0.15"),
        ]

        for grupo in acumulado.values():
            puntajes = sorted(
                grupo["productos"].values(),
                reverse=True,
            )

            if not puntajes:
                continue

            total = CERO
            total_pesos = CERO

            for indice, puntaje in enumerate(
                puntajes[:len(pesos)]
            ):
                peso = pesos[indice]
                total += puntaje * peso
                total_pesos += peso

            promedio = (
                total / total_pesos
            ).quantize(
                DOS_DECIMALES,
                rounding=ROUND_HALF_UP,
            )

            cantidad = len(puntajes)

            # Una categoría respaldada por varios productos
            # recibe una bonificación moderada.
            bonificacion = min(
                Decimal(max(cantidad - 1, 0))
                * Decimal("3.00"),
                Decimal("18.00"),
            )

            puntaje_categoria = min(
                promedio + bonificacion,
                CIEN,
            ).quantize(
                DOS_DECIMALES,
                rounding=ROUND_HALF_UP,
            )

            categorias.append({
                "categoria": grupo["categoria"],
                "puntaje": puntaje_categoria,
                "coincidencias": cantidad,
            })

        categorias.sort(
            key=lambda item: (
                item["puntaje"],
                item["coincidencias"],
            ),
            reverse=True,
        )

        return categorias

    # =====================================================
    # API PRINCIPAL
    # =====================================================
    def sugerir(
        self,
        *,
        texto,
        codigo=None,
        proveedor=None,
        detalle_original=None,
        origen="INDIVIDUAL",
    ):
        origen = self._validar_origen(origen)

        if detalle_original is not None:
            if not isinstance(
                detalle_original,
                DetalleFacturaOriginal,
            ):
                raise ValidationError(
                    "El detalle original no es válido."
                )

            texto = (
                texto
                or detalle_original.descripcion_proveedor
            )

            codigo = (
                codigo
                or detalle_original.codigo_proveedor
            )

            proveedor = (
                proveedor
                or detalle_original.factura.proveedor_rel
            )

            origen = "FACTURA"

        texto_original = str(texto or "").strip()
        codigo_original = str(codigo or "").strip().upper()

        texto_normalizado = normalizar_texto(
            texto_original
        )

        codigo_normalizado = normalizar_codigo(
            codigo_original
        )

        if not texto_normalizado and not codigo_normalizado:
            raise ValidationError(
                "Debe escribir una descripción o un código."
            )

        resultados = {}

        # 1. Coincidencias exactas por código.
        self._buscar_por_codigo(
            codigo_normalizado=codigo_normalizado,
            resultados=resultados,
        )

        # 2. Historial de aprendizajes confirmados.
        self._buscar_en_aprendizajes(
            texto=texto_normalizado,
            codigo_normalizado=codigo_normalizado,
            proveedor=proveedor,
            resultados=resultados,
        )

        # 3. Alias confirmados.
        self._buscar_en_alias(
            texto=texto_normalizado,
            resultados=resultados,
        )

        # 4. Compras históricas confirmadas.
        self._buscar_en_compras(
            texto=texto_normalizado,
            codigo_normalizado=codigo_normalizado,
            proveedor=proveedor,
            excluir_detalle=detalle_original,
            resultados=resultados,
        )

        # 5. Catálogo actual.
        self._buscar_en_catalogo(
            texto=texto_normalizado,
            codigo_normalizado=codigo_normalizado,
            resultados=resultados,
        )

        # Ordena todos los candidatos, sin limitarlos todavía.
        todos_los_resultados = self._ordenar_resultados(
            resultados
        )

        # Categorías obtenidas por similitud de productos.
        categorias_similitud = self._agrupar_categorias(
            todos_los_resultados
        )

        # Categorías obtenidas por frecuencia y concentración
        # de los tokens en la propia base de datos.
        categorias_evidencia = (
            self.motor_evidencia.analizar(
                texto_normalizado
            )
        )

        # Combina ambos enfoques.
        categorias = self._combinar_categorias(
            categorias_similitud,
            categorias_evidencia,
        )

        # Solo ahora limitamos los productos que se mostrarán.
        coincidencias = todos_los_resultados[
            :self.limite_resultados
        ]

        mejor_producto_resultado = (
            coincidencias[0]
            if coincidencias
            else None
        )

        mejor_categoria_resultado = (
            categorias[0]
            if categorias
            else None
        )

        return {
            "origen": origen,

            "texto_original": texto_original,
            "texto_normalizado": texto_normalizado,

            "codigo_original": codigo_original,
            "codigo_normalizado": codigo_normalizado,

            "proveedor": proveedor,
            "detalle_original": detalle_original,

            "mejor_producto": (
                mejor_producto_resultado["producto"]
                if mejor_producto_resultado
                else None
            ),

            "mejor_categoria": (
                mejor_categoria_resultado["categoria"]
                if mejor_categoria_resultado
                else (
                    mejor_producto_resultado["categoria"]
                    if mejor_producto_resultado
                    else None
                )
            ),

            "mejor_codigo_producto": (
                mejor_producto_resultado[
                    "codigo_producto"
                ]
                if mejor_producto_resultado
                else None
            ),

            "mejor_marca": (
                mejor_producto_resultado["marca"]
                if mejor_producto_resultado
                else None
            ),

            # Confianza del producto individual.
            "confianza": (
                mejor_producto_resultado["confianza"]
                if mejor_producto_resultado
                else CERO
            ),

            # Confianza de la categoría combinando similitud
            # y evidencia colectiva.
            "confianza_categoria": (
                mejor_categoria_resultado["puntaje"]
                if mejor_categoria_resultado
                else CERO
            ),

            "coincidencias": coincidencias,
            "categorias": categorias,

            # Útil para depurar y mostrar de dónde salió
            # la categoría sugerida.
            "categorias_similitud": categorias_similitud,
            "categorias_evidencia": categorias_evidencia,
        }
    @staticmethod
    def _combinar_categorias(
        categorias_similitud,
        categorias_evidencia,
    ):
        acumulado = {}

        for item in categorias_similitud:
            categoria = item["categoria"]

            acumulado[categoria.pk] = {
                "categoria": categoria,
                "puntaje_similitud": item["puntaje"],
                "puntaje_evidencia": CERO,
                "coincidencias": item["coincidencias"],
            }

        for item in categorias_evidencia:
            categoria = item["categoria"]

            grupo = acumulado.setdefault(
                categoria.pk,
                {
                    "categoria": categoria,
                    "puntaje_similitud": CERO,
                    "puntaje_evidencia": CERO,
                    "coincidencias": 0,
                },
            )

            grupo["puntaje_evidencia"] = (
                item["puntaje"]
            )

            grupo["coincidencias"] += (
                item["coincidencias"]
            )

        resultado = []

        for grupo in acumulado.values():
            similitud = grupo[
                "puntaje_similitud"
            ]

            evidencia = grupo[
                "puntaje_evidencia"
            ]

            fuentes_activas = []

            if similitud > CERO:
                fuentes_activas.append(
                    (
                        similitud,
                        Decimal("0.45"),
                    )
                )

            if evidencia > CERO:
                fuentes_activas.append(
                    (
                        evidencia,
                        Decimal("0.55"),
                    )
                )

            total = sum(
                puntaje * peso
                for puntaje, peso in fuentes_activas
            )

            pesos = sum(
                peso
                for _, peso in fuentes_activas
            )

            puntaje_final = (
                total / pesos
                if pesos
                else CERO
            )

            resultado.append({
                "categoria": grupo["categoria"],
                "puntaje": min(
                    puntaje_final,
                    CIEN,
                ).quantize(
                    DOS_DECIMALES,
                    rounding=ROUND_HALF_UP,
                ),
                "puntaje_similitud": similitud,
                "puntaje_evidencia": evidencia,
                "coincidencias": grupo[
                    "coincidencias"
                ],
            })

        resultado.sort(
            key=lambda item: (
                item["puntaje"],
                item["puntaje_evidencia"],
                item["coincidencias"],
            ),
            reverse=True,
        )

        return resultado
    # =====================================================
    # GUARDAR SUGERENCIA
    # =====================================================

    @transaction.atomic
    def generar_y_guardar(
        self,
        *,
        texto=None,
        codigo=None,
        proveedor=None,
        detalle_original=None,
        origen="INDIVIDUAL",
    ):
        resultado = self.sugerir(
            texto=texto,
            codigo=codigo,
            proveedor=proveedor,
            detalle_original=detalle_original,
            origen=origen,
        )

        mejor_producto = resultado[
            "mejor_producto"
        ]

        mejor_categoria = resultado[
            "mejor_categoria"
        ]

        mejor_codigo = resultado[
            "mejor_codigo_producto"
        ]

        mejor_marca = resultado[
            "mejor_marca"
        ]

        mejor_resultado = (
            resultado["coincidencias"][0]
            if resultado["coincidencias"]
            else {}
        )

        sugerencia = SugerenciaProducto.objects.create(
            detalle_original=detalle_original,
            proveedor=resultado["proveedor"],
            origen=resultado["origen"],

            texto_entrada=(
                resultado["texto_original"]
            ),
            codigo_entrada=(
                resultado["codigo_original"]
                or None
            ),

            producto_sugerido=mejor_producto,
            categoria_sugerida=mejor_categoria,
            codigo_producto_sugerido=(
                mejor_codigo
            ),
            marca_sugerida=mejor_marca,

            confianza=resultado["confianza"],

            puntaje_codigo=mejor_resultado.get(
                "puntaje_codigo",
                CERO,
            ),
            puntaje_texto=mejor_resultado.get(
                "puntaje_texto",
                CERO,
            ),
            puntaje_compras=mejor_resultado.get(
                "puntaje_compras",
                CERO,
            ),
            puntaje_aprendizaje=(
                mejor_resultado.get(
                    "puntaje_aprendizaje",
                    CERO,
                )
            ),
            puntaje_alias=mejor_resultado.get(
                "puntaje_alias",
                CERO,
            ),
            puntaje_proveedor=(
                mejor_resultado.get(
                    "puntaje_proveedor",
                    CERO,
                )
            ),

            estado="PENDIENTE",
        )

        resultado["sugerencia"] = sugerencia

        return resultado

    # =====================================================
    # FORMATO JSON
    # =====================================================

    @staticmethod
    def convertir_a_dict(resultado):
        """
        Convierte el resultado del motor en datos aptos
        para JsonResponse.
        """

        def producto_dict(item):
            producto = item["producto"]
            categoria = item["categoria"]
            codigo = item["codigo_producto"]
            marca = item["marca"]

            return {
                "producto_id": producto.pk,
                "producto": producto.nombre_base,
                "sku": producto.sku_interno,

                "categoria_id": (
                    categoria.pk
                    if categoria
                    else None
                ),
                "categoria": (
                    categoria.nombre
                    if categoria
                    else None
                ),

                "codigo_producto_id": (
                    codigo.pk
                    if codigo
                    else None
                ),
                "codigo": (
                    codigo.codigo
                    if codigo
                    else None
                ),

                "marca_id": (
                    marca.pk
                    if marca
                    else None
                ),
                "marca": (
                    marca.nombre
                    if marca
                    else None
                ),

                "confianza": float(
                    item["confianza"]
                ),

                "puntajes": {
                    "codigo": float(
                        item["puntaje_codigo"]
                    ),
                    "texto": float(
                        item["puntaje_texto"]
                    ),
                    "compras": float(
                        item["puntaje_compras"]
                    ),
                    "aprendizaje": float(
                        item[
                            "puntaje_aprendizaje"
                        ]
                    ),
                    "alias": float(
                        item["puntaje_alias"]
                    ),
                    "proveedor": float(
                        item[
                            "puntaje_proveedor"
                        ]
                    ),
                },

                "fuentes": item["fuentes"],
            }

        categorias = []

        for item in resultado["categorias"]:
            categoria = item["categoria"]

            categorias.append({
                "id": categoria.pk,
                "nombre": categoria.nombre,
                "confianza": float(
                    item["puntaje"]
                ),
                "coincidencias": (
                    item["coincidencias"]
                ),
            })

        datos = {
            "texto": resultado[
                "texto_original"
            ],

            "codigo": resultado[
                "codigo_original"
            ],

            "confianza": float(
                resultado["confianza"]
            ),

            "confianza_categoria": float(
                resultado.get(
                    "confianza_categoria",
                    CERO,
                )
            ),

            "categorias": categorias,

            "productos": [
                producto_dict(item)
                for item in resultado[
                    "coincidencias"
                ]
            ],
        }

        if resultado.get("sugerencia"):
            datos["sugerencia_id"] = (
                resultado["sugerencia"].pk
            )

        return datos