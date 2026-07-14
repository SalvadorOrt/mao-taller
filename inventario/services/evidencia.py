# inventario/services/evidencia.py

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Q

from inventario.models import Producto

from .normalizacion import tokenizar_texto


CERO = Decimal("0.00")
CIEN = Decimal("100.00")
DOS_DECIMALES = Decimal("0.01")


class MotorEvidenciaCategoria:
    def __init__(
        self,
        *,
        limite_tokens=8,
        minimo_coincidencias=1,
    ):
        self.limite_tokens = max(
            int(limite_tokens),
            1,
        )

        self.minimo_coincidencias = max(
            int(minimo_coincidencias),
            1,
        )

    def analizar(self, texto):
        tokens = tokenizar_texto(texto)[
            :self.limite_tokens
        ]

        if not tokens:
            return []

        evidencia_categorias = defaultdict(
            lambda: {
                "categoria": None,
                "puntaje": Decimal("0.00"),
                "tokens": {},
                "coincidencias": 0,
            }
        )

        for token in tokens:
            estadisticas = self._estadisticas_token(
                token
            )

            total_token = sum(
                item["cantidad"]
                for item in estadisticas
            )

            if total_token < self.minimo_coincidencias:
                continue

            for item in estadisticas:
                categoria = item["categoria"]
                cantidad = item["cantidad"]

                concentracion = (
                    Decimal(cantidad)
                    / Decimal(total_token)
                )

                especificidad = self._peso_especificidad(
                    token=token,
                    total_coincidencias=total_token,
                )

                puntaje_token = (
                    concentracion
                    * especificidad
                    * CIEN
                )

                grupo = evidencia_categorias[
                    categoria.pk
                ]

                grupo["categoria"] = categoria
                grupo["puntaje"] += puntaje_token
                grupo["coincidencias"] += cantidad

                grupo["tokens"][token] = {
                    "cantidad": cantidad,
                    "total": total_token,
                    "concentracion": float(
                        concentracion.quantize(
                            DOS_DECIMALES,
                            rounding=ROUND_HALF_UP,
                        )
                    ),
                    "puntaje": float(
                        puntaje_token.quantize(
                            DOS_DECIMALES,
                            rounding=ROUND_HALF_UP,
                        )
                    ),
                }

        resultados = []

        for grupo in evidencia_categorias.values():
            cantidad_tokens = len(
                grupo["tokens"]
            )

            if cantidad_tokens == 0:
                continue

            promedio = (
                grupo["puntaje"]
                / Decimal(cantidad_tokens)
            )

            resultados.append({
                "categoria": grupo["categoria"],
                "puntaje": min(
                    promedio,
                    CIEN,
                ).quantize(
                    DOS_DECIMALES,
                    rounding=ROUND_HALF_UP,
                ),
                "coincidencias": grupo[
                    "coincidencias"
                ],
                "tokens": grupo["tokens"],
            })

        resultados.sort(
            key=lambda item: (
                item["puntaje"],
                item["coincidencias"],
            ),
            reverse=True,
        )

        return resultados

    @staticmethod
    def _peso_especificidad(
        *,
        token,
        total_coincidencias,
    ):
        """
        Un token poco frecuente y específico pesa más.

        Los tokens con números suelen contener referencias,
        viscosidades, medidas o códigos, pero no se asignan
        manualmente a ninguna categoría.
        """
        peso = Decimal("1.00")

        if any(
            caracter.isdigit()
            for caracter in token
        ):
            peso += Decimal("0.35")

        if len(token) >= 6:
            peso += Decimal("0.10")

        # Los tokens que aparecen en demasiados productos
        # son menos discriminantes.
        if total_coincidencias >= 100:
            peso *= Decimal("0.50")

        elif total_coincidencias >= 50:
            peso *= Decimal("0.70")

        elif total_coincidencias >= 20:
            peso *= Decimal("0.85")

        return peso

    @staticmethod
    def _estadisticas_token(token):
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
            .distinct()
        )

        conteo = defaultdict(
            lambda: {
                "categoria": None,
                "cantidad": 0,
            }
        )

        for producto in productos:
            categoria = producto.categoria

            conteo[categoria.pk][
                "categoria"
            ] = categoria

            conteo[categoria.pk][
                "cantidad"
            ] += 1

        return list(conteo.values())