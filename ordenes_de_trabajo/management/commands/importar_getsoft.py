from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ordenes_de_trabajo.models import (
    Cliente,
    ExpedienteVehiculo,
    OrdenInsumoHistorico,
    OrdenServicioHistorico,
    OrdenSintoma,
    OrdenTrabajo,
    Sucursal,
)


Q2 = Decimal("0.01")


def dec(valor) -> Decimal:
    if valor in (None, ""):
        return Decimal("0.00")

    texto = str(valor).strip().replace(",", "")

    try:
        return Decimal(texto).quantize(
            Q2,
            rounding=ROUND_HALF_UP,
        )
    except (InvalidOperation, ValueError):
        raise ValueError(
            f"Valor decimal inválido: {valor!r}"
        )


def texto(valor) -> str:
    if valor is None:
        return ""
    return str(valor).strip()


def placa_normalizada(valor) -> str:
    return (
        texto(valor)
        .upper()
        .replace("-", "")
        .replace(" ", "")
    )


def construir_vehiculo(data: dict) -> str:
    marca = texto(data.get("marca")).upper()
    modelo = texto(data.get("modelo")).upper()

    if marca and modelo:
        # Evita "MAZDA MAZDA3..." pero conserva marca
        # cuando Getsoft solo entrega "TRACKER...", etc.
        if modelo.startswith(marca):
            return modelo
        return f"{marca} {modelo}"

    return modelo or marca


def parse_fecha_iso(valor) -> date:
    valor = texto(valor)

    if not valor:
        raise ValueError("La OT no tiene fecha.")

    try:
        return date.fromisoformat(valor)
    except ValueError as exc:
        raise ValueError(
            f"Fecha inválida: {valor!r}"
        ) from exc


def fecha_ingreso_desde_fecha(fecha: date):
    """
    Getsoft solo entrega la fecha, no la hora.
    Se usa 00:00 local como valor técnico y fecha_origen
    conserva explícitamente la fecha histórica.
    """
    naive = datetime.combine(fecha, time.min)

    if timezone.is_aware(naive):
        return naive

    return timezone.make_aware(
        naive,
        timezone.get_current_timezone(),
    )


def porcentaje_iva_desde_fuente(
    subtotal: Decimal,
    descuento: Decimal,
    iva: Decimal,
) -> Decimal:
    base = subtotal - descuento

    if base <= Decimal("0.00") or iva <= Decimal("0.00"):
        return Decimal("0.00")

    return (
        iva
        * Decimal("100")
        / base
    ).quantize(
        Q2,
        rounding=ROUND_HALF_UP,
    )


def porcentaje_descuento_equivalente(
    subtotal: Decimal,
    descuento: Decimal,
) -> Decimal:
    if subtotal <= Decimal("0.00") or descuento <= Decimal("0.00"):
        return Decimal("0.00")

    return (
        descuento
        * Decimal("100")
        / subtotal
    ).quantize(
        Q2,
        rounding=ROUND_HALF_UP,
    )


def numero_interno(
    sucursal: Sucursal,
    fecha: date,
    numero_origen: str,
    placa: str,
) -> str:
    """
    numero_orden es unique=True.
    Se genera un identificador estable y suficientemente específico
    para no confundir visitas del mismo vehículo.
    """
    numero_origen = (
        texto(numero_origen)
        .upper()
        .replace(" ", "")
    )
    placa = placa_normalizada(placa) or "SINPLACA"

    resultado = (
        f"MIG-{sucursal.codigo}-"
        f"{fecha.strftime('%Y%m%d')}-"
        f"{numero_origen}-"
        f"{placa}"
    )

    if len(resultado) > 50:
        raise ValueError(
            "El número interno generado supera 50 caracteres: "
            f"{resultado}"
        )

    return resultado


class Command(BaseCommand):
    help = (
        "Importa históricos de Getsoft a MAO respetando "
        "OrdenTrabajo y los modelos históricos."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--archivo",
            required=True,
            help=(
                "Ruta de ordenes_getsoft_limpias.json."
            ),
        )

        parser.add_argument(
            "--sucursal",
            required=True,
            help=(
                "Código de la sucursal destino, por ejemplo NORTE."
            ),
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Ejecuta todas las validaciones e inserciones "
                "dentro de una transacción y revierte todo al final."
            ),
        )

        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help=(
                "Procesa solo las primeras N OTs. "
                "Útil para una prueba inicial."
            ),
        )

    def handle(self, *args, **options):
        ruta = Path(options["archivo"]).expanduser()
        codigo_sucursal = texto(
            options["sucursal"]
        ).upper()
        dry_run = bool(options["dry_run"])
        limite = options["limit"]

        if not ruta.exists():
            raise CommandError(
                f"No existe el archivo: {ruta}"
            )

        if limite is not None and limite <= 0:
            raise CommandError(
                "--limit debe ser mayor que 0."
            )

        sucursales = list(
            Sucursal.objects.filter(
                codigo__iexact=codigo_sucursal,
                activa=True,
            )
        )

        if len(sucursales) != 1:
            raise CommandError(
                "Debe existir exactamente una sucursal activa "
                f"con código {codigo_sucursal!r}. "
                f"Encontradas: {len(sucursales)}"
            )

        sucursal = sucursales[0]

        try:
            ordenes_fuente = json.loads(
                ruta.read_text(
                    encoding="utf-8"
                )
            )
        except Exception as exc:
            raise CommandError(
                f"No se pudo leer el JSON: {exc}"
            ) from exc

        if not isinstance(ordenes_fuente, list):
            raise CommandError(
                "El JSON debe contener una lista de órdenes."
            )

        if limite is not None:
            ordenes_fuente = (
                ordenes_fuente[:limite]
            )

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "=" * 72
            )
        )
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "IMPORTACIÓN GETSOFT → MAO"
            )
        )
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "=" * 72
            )
        )

        self.stdout.write(
            f"Sucursal: "
            f"{sucursal.id} | "
            f"{sucursal.codigo} | "
            f"{sucursal.nombre}"
        )
        self.stdout.write(
            f"Archivo: {ruta}"
        )
        self.stdout.write(
            f"Órdenes fuente a procesar: "
            f"{len(ordenes_fuente)}"
        )
        self.stdout.write(
            f"Modo: "
            f"{'DRY-RUN (ROLLBACK)' if dry_run else 'IMPORTACIÓN REAL'}"
        )
        self.stdout.write("")

        stats = Counter()
        errores = []

        clientes_existentes = set()
        clientes_creados = set()
        expedientes_existentes = set()
        expedientes_creados = set()
        expedientes_ambiguos = set()

        # Una sola transacción:
        # - dry-run: todo se revierte.
        # - real: si aparece un error, al final se revierte todo.
        with transaction.atomic():
            for indice, data in enumerate(
                ordenes_fuente,
                start=1,
            ):
                try:
                    # Savepoint por OT: permite recopilar todos
                    # los errores sin romper la transacción exterior.
                    with transaction.atomic():
                        resultado = self._importar_orden(
                            data=data,
                            sucursal=sucursal,
                            stats=stats,
                            clientes_existentes=clientes_existentes,
                            clientes_creados=clientes_creados,
                            expedientes_existentes=expedientes_existentes,
                            expedientes_creados=expedientes_creados,
                            expedientes_ambiguos=expedientes_ambiguos,
                        )

                    if indice % 100 == 0:
                        self.stdout.write(
                            f"[{indice}/{len(ordenes_fuente)}] "
                            f"procesadas..."
                        )

                    if resultado == "EXISTENTE":
                        stats["ot_existentes"] += 1

                    elif resultado == "LEGACY":
                        stats["ot_legacy"] += 1

                except Exception as exc:
                    stats["errores"] += 1

                    errores.append({
                        "indice": indice,
                        "placa": texto(
                            data.get("placa")
                        ),
                        "ot": texto(
                            data.get(
                                "numero_orden_origen"
                            )
                        ),
                        "fecha": texto(
                            data.get("fecha")
                        ),
                        "error": str(exc),
                    })

                    self.stderr.write(
                        self.style.ERROR(
                            f"[{indice}] "
                            f"{data.get('placa', '')} / "
                            f"OT {data.get('numero_orden_origen', '')}: "
                            f"{exc}"
                        )
                    )

            # Si hubo cualquier error, nunca dejamos una importación parcial.
            if errores:
                transaction.set_rollback(True)

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "=" * 72
            )
        )
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "RESUMEN"
            )
        )
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "=" * 72
            )
        )

        self.stdout.write(
            f"OT fuente: {len(ordenes_fuente)}"
        )
        self.stdout.write(
            f"OT nuevas validadas: "
            f"{stats['ot_nuevas']}"
        )
        self.stdout.write(
            f"OT ya existentes por migración: "
            f"{stats['ot_existentes']}"
        )
        self.stdout.write(
            f"OT Getsoft preexistentes/legacy omitidas: "
            f"{stats['ot_legacy']}"
        )
        self.stdout.write(
            f"CERRADAS nuevas: "
            f"{stats['cerradas']}"
        )
        self.stdout.write(
            f"ANULADAS: "
            f"{stats['anuladas']}"
        )
        self.stdout.write(
            f"OT sin items: "
            f"{stats['ot_sin_items']}"
        )
        self.stdout.write("")

        self.stdout.write(
            f"Clientes existentes utilizados: "
            f"{len(clientes_existentes)}"
        )
        self.stdout.write(
            f"Clientes nuevos validados: "
            f"{len(clientes_creados)}"
        )

        self.stdout.write(
            f"Expedientes existentes utilizados: "
            f"{len(expedientes_existentes)}"
        )
        self.stdout.write(
            f"Expedientes nuevos validados: "
            f"{len(expedientes_creados)}"
        )
        self.stdout.write(
            f"Placas con expediente ambiguo: "
            f"{len(expedientes_ambiguos)}"
        )
        self.stdout.write("")

        self.stdout.write(
            f"REP históricos: "
            f"{stats['rep']}"
        )
        self.stdout.write(
            f"MO históricos: "
            f"{stats['mo']}"
        )
        self.stdout.write(
            f"MOE históricos: "
            f"{stats['moe']}"
        )
        self.stdout.write(
            f"Síntomas históricos: "
            f"{stats['sintomas']}"
        )
        self.stdout.write("")

        self.stdout.write(
            f"OT marcadas para revisión: "
            f"{stats['ot_revision']}"
        )
        self.stdout.write(
            f"Emails fuente inválidos: "
            f"{stats['email_invalido']}"
        )
        self.stdout.write(
            f"Descuentos anómalos preservados: "
            f"{stats['descuento_anomalo']}"
        )
        self.stdout.write(
            f"Subtotales negativos preservados en JSON: "
            f"{stats['subtotal_negativo']}"
        )
        self.stdout.write(
            f"Cantidades <= 0 preservadas en JSON: "
            f"{stats['cantidad_anomala']}"
        )
        self.stdout.write("")

        self.stdout.write(
            f"Errores: {len(errores)}"
        )

        if errores:
            self.stdout.write("")
            self.stdout.write(
                self.style.ERROR(
                    "La importación fue revertida. "
                    "No se guardó ningún cambio."
                )
            )

            self.stdout.write(
                self.style.ERROR(
                    "Primeros errores:"
                )
            )

            for error in errores[:20]:
                self.stdout.write(
                    self.style.ERROR(
                        f"  #{error['indice']} | "
                        f"{error['placa']} | "
                        f"OT {error['ot']} | "
                        f"{error['fecha']} | "
                        f"{error['error']}"
                    )
                )

            if len(errores) > 20:
                self.stdout.write(
                    self.style.ERROR(
                        f"  ... y "
                        f"{len(errores) - 20} "
                        f"errores adicionales."
                    )
                )

            raise CommandError(
                "Hay errores de compatibilidad. "
                "La base no fue modificada."
            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "DRY-RUN correcto: "
                    "TODOS los cambios fueron revertidos."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "IMPORTACIÓN COMPLETADA."
                )
            )

    def _importar_orden(
        self,
        *,
        data: dict,
        sucursal: Sucursal,
        stats: Counter,
        clientes_existentes: set,
        clientes_creados: set,
        expedientes_existentes: set,
        expedientes_creados: set,
        expedientes_ambiguos: set,
    ):
        if not isinstance(data, dict):
            raise ValueError(
                "La entrada de la OT no es un objeto JSON."
            )

        numero_origen = texto(
            data.get("numero_orden_origen")
        ).upper()

        if not numero_origen:
            raise ValueError(
                "Falta numero_orden_origen."
            )

        fecha = parse_fecha_iso(
            data.get("fecha")
        )

        placa = placa_normalizada(
            data.get("placa")
        )

        fingerprint = texto(
            data.get("fingerprint")
        ).lower()

        if len(fingerprint) != 64:
            raise ValueError(
                "fingerprint/hash_migracion inválido."
            )

        # ------------------------------------------------------
        # IDEMPOTENCIA
        # ------------------------------------------------------

        existente_hash = (
            OrdenTrabajo.objects
            .filter(
                hash_migracion=fingerprint
            )
            .first()
        )

        if existente_hash:
            if (
                existente_hash.sucursal_id
                != sucursal.id
            ):
                raise ValueError(
                    "El hash ya existe en otra sucursal: "
                    f"OT {existente_hash.numero_orden}"
                )

            return "EXISTENTE"

        # Compatibilidad con importaciones históricas anteriores
        # que quizá no tenían hash_migracion.
        existente_natural = (
            OrdenTrabajo.objects
            .filter(
                es_migrada=True,
                sucursal=sucursal,
                numero_orden_origen=numero_origen,
                fecha_origen=fecha,
                placa=placa or None,
            )
            .first()
        )

        if existente_natural:
            return "EXISTENTE"

        # ------------------------------------------------------
        # COMPATIBILIDAD CON OTs GETSOFT YA CARGADAS ANTES
        # ------------------------------------------------------
        #
        # En producción existen algunas OTs de Getsoft que fueron
        # cargadas previamente como órdenes "Normales", por ejemplo
        # con números del tipo OT-2874. Esas órdenes pueden no tener:
        #   - es_migrada=True
        #   - numero_orden_origen
        #   - hash_migracion
        #
        # No debemos duplicarlas al importar todo el histórico.
        #
        # La coincidencia legacy exige:
        #   1) misma sucursal,
        #   2) número equivalente al número Getsoft,
        #   3) misma fecha histórica,
        #   4) misma placa cuando la fuente tiene placa.
        #
        # Si hay exactamente una coincidencia, NO se modifica:
        # simplemente se omite la nueva creación para conservar
        # cualquier trabajo realizado después en MAO.
        numero_sin_ceros = (
            numero_origen.lstrip("0")
            or "0"
        )

        numeros_legacy = {
            numero_origen,
            numero_sin_ceros,
            f"OT-{numero_origen}",
            f"OT-{numero_sin_ceros}",
        }

        candidatos_legacy = (
            OrdenTrabajo.objects
            .filter(
                sucursal=sucursal,
                numero_orden__in=numeros_legacy,
            )
            .filter(
                Q(fecha_origen=fecha)
                | Q(fecha_ingreso__date=fecha)
            )
        )

        if placa:
            candidatos_legacy = (
                candidatos_legacy.filter(
                    placa__iexact=placa
                )
            )

        coincidencias_legacy = list(
            candidatos_legacy[:3]
        )

        if len(coincidencias_legacy) == 1:
            legacy = coincidencias_legacy[0]

            self.stdout.write(
                self.style.WARNING(
                    "[LEGACY OMITIDA] "
                    f"Getsoft {numero_origen} | "
                    f"{placa or 'SIN PLACA'} | "
                    f"{fecha.isoformat()} "
                    f"-> existente {legacy.numero_orden} "
                    f"({legacy.estado})"
                )
            )

            return "LEGACY"

        if len(coincidencias_legacy) > 1:
            encontrados = ", ".join(
                f"{ot.numero_orden}#{ot.pk}"
                for ot in coincidencias_legacy
            )

            raise ValueError(
                "Coincidencia legacy ambigua en producción. "
                f"Getsoft {numero_origen} / {placa} / {fecha}: "
                f"{encontrados}"
            )

        numero_orden = numero_interno(
            sucursal=sucursal,
            fecha=fecha,
            numero_origen=numero_origen,
            placa=placa,
        )

        colision = (
            OrdenTrabajo.objects
            .filter(
                numero_orden=numero_orden
            )
            .first()
        )

        if colision:
            raise ValueError(
                "Colisión de numero_orden con una OT "
                f"diferente: {numero_orden}"
            )

        # ------------------------------------------------------
        # CLIENTE MAESTRO
        # ------------------------------------------------------

        requiere_revision = False

        cliente_data = (
            data.get("cliente")
            if isinstance(
                data.get("cliente"),
                dict,
            )
            else {}
        )

        cliente_nombre = texto(
            cliente_data.get("nombre")
        )

        identificacion = texto(
            cliente_data.get("identificacion")
        ).upper()

        telefono = texto(
            cliente_data.get("telefono")
        )

        email_original = texto(
            cliente_data.get("correo")
        ).lower()

        email = None

        if email_original:
            try:
                validate_email(email_original)
                email = email_original
            except ValidationError:
                # El valor original se conserva íntegro en json_origen.
                # No intentamos meter listas, textos o correos mal
                # formados en EmailField.
                requiere_revision = True
                stats["email_invalido"] += 1

        direccion = texto(
            cliente_data.get("domicilio")
        )

        cliente = None

        if identificacion:
            cliente = (
                Cliente.objects
                .filter(
                    identificacion__iexact=
                        identificacion
                )
                .first()
            )

            if cliente:
                clientes_existentes.add(
                    cliente.pk
                )
            else:
                if not cliente_nombre:
                    raise ValueError(
                        "Hay identificación histórica, "
                        "pero el cliente no tiene nombre."
                    )

                cliente = Cliente(
                    identificacion=identificacion,
                    nombre_completo=cliente_nombre,
                    telefono=telefono or None,
                    email=email or None,
                    direccion=direccion or None,
                )

                # Cliente.save() ya ejecuta full_clean().
                cliente.save()

                clientes_creados.add(
                    cliente.identificacion
                )

        # Si Getsoft no dio identificación, NO se crea un
        # Cliente PROV aleatorio: la OT conserva el snapshot
        # histórico y cliente queda NULL.
        # Esto evita duplicados maestros en reintentos.

        # ------------------------------------------------------
        # EXPEDIENTE
        # ------------------------------------------------------

        expediente = None

        vehiculo = construir_vehiculo(
            data
        )

        anio = data.get("anio")

        if anio in ("", None):
            anio = None
        else:
            anio = int(anio)

        color = texto(
            data.get("color")
        )

        if placa:
            expedientes = list(
                ExpedienteVehiculo.objects
                .filter(
                    placa__iexact=placa
                )
                .order_by("id")[:3]
            )

            if len(expedientes) == 1:
                expediente = expedientes[0]
                expedientes_existentes.add(
                    expediente.pk
                )

            elif len(expedientes) == 0:
                expediente = ExpedienteVehiculo(
                    cliente=cliente,
                    cliente_respaldo=(
                        cliente_nombre
                        or None
                    ),
                    placa=placa,
                    vehiculo=(
                        vehiculo
                        or None
                    ),
                    anio_vehiculo=anio,
                    marca_api=(
                        texto(
                            data.get("marca")
                        )
                        or None
                    ),
                    modelo_api=(
                        texto(
                            data.get("modelo")
                        )
                        or None
                    ),
                )

                expediente.save()

                expedientes_creados.add(
                    placa
                )

            else:
                # No seleccionamos arbitrariamente uno.
                requiere_revision = True
                expedientes_ambiguos.add(
                    placa
                )

        # ------------------------------------------------------
        # ECONOMÍA FUENTE
        # ------------------------------------------------------

        subtotal_fuente = dec(
            data.get(
                "subtotal_sin_impuestos"
            )
        )

        descuento_fuente = dec(
            data.get("descuento")
        )

        iva_fuente = dec(
            data.get("iva_valor")
        )

        total_fuente = dec(
            data.get("valor_total")
        )

        if descuento_fuente < Decimal("0.00"):
            raise ValueError(
                "Descuento histórico negativo."
            )

        # En 19 OTs Getsoft reporta un "descuento" mayor que el
        # subtotal, pero el total final coincide con subtotal + IVA.
        # Ese valor no puede aplicarse al modelo económico de MAO
        # sin falsear el total. Se conserva exactamente en json_origen,
        # se marca la OT para revisión y, para los campos económicos
        # normalizados, se considera descuento aplicado = 0.
        descuento_aplicable = descuento_fuente

        if (
            subtotal_fuente >= Decimal("0.00")
            and descuento_fuente > subtotal_fuente
        ):
            descuento_aplicable = Decimal("0.00")
            requiere_revision = True
            stats["descuento_anomalo"] += 1

        porcentaje_iva = (
            porcentaje_iva_desde_fuente(
                subtotal=subtotal_fuente,
                descuento=descuento_aplicable,
                iva=iva_fuente,
            )
        )

        porcentaje_descuento = (
            porcentaje_descuento_equivalente(
                subtotal=subtotal_fuente,
                descuento=descuento_aplicable,
            )
        )

        # ------------------------------------------------------
        # CREAR OT ABIERTA TEMPORALMENTE
        # ------------------------------------------------------

        es_anulada = bool(
            data.get(
                "es_anulada_origen",
                False,
            )
        )

        orden = OrdenTrabajo(
            numero_orden=numero_orden,
            sucursal=sucursal,
            expediente=expediente,

            es_migrada=True,
            numero_orden_origen=numero_origen,
            archivo_origen=(
                texto(
                    data.get(
                        "archivo_origen"
                    )
                )
                or None
            ),
            hoja_origen="GETSOFT_HTML",
            anio_origen_migracion=fecha.year,
            json_origen=data,
            requiere_revision_migracion=
                requiere_revision,
            hash_migracion=fingerprint,
            facturable_en_mao=False,

            cliente=cliente,
            cliente_respaldo=(
                cliente_nombre
                or None
            ),
            identificacion_cliente_respaldo=(
                identificacion
                or None
            ),
            telefono_respaldo=(
                telefono
                or None
            ),
            # Getsoft no entregó estos dos teléfonos
            # en el HTML histórico analizado.
            telefono_secundario_respaldo=None,
            telefono_trabajo_respaldo=None,
            email_respaldo=(
                email
                or None
            ),
            direccion_respaldo=(
                direccion
                or None
            ),

            color=color or None,
            placa=placa or None,
            vehiculo=vehiculo or None,
            anio_vehiculo=anio,
            fecha_origen=fecha,
            kilometraje=(
                int(data["kilometraje"])
                if data.get("kilometraje")
                is not None
                else None
            ),

            observaciones_recepcion=None,
            sintomas_cliente=(
                texto(
                    data.get(
                        "reporte_cliente"
                    )
                )
                or None
            ),
            observaciones_tecnicas=(
                texto(
                    data.get(
                        "observaciones"
                    )
                )
                or None
            ),

            # Temporalmente ABIERTA porque los modelos
            # históricos exigen orden editable.
            estado="ABIERTA",
            fecha_ingreso=
                fecha_ingreso_desde_fecha(
                    fecha
                ),

            # Durante la carga de detalles dejamos descuento 0.
            # Los valores exactos de Getsoft se fijan al final.
            tipo_descuento="PORCENTAJE",
            descuento_ingresado=
                Decimal("0.00"),
            sumar_iva_al_total=True,
        )

        orden.save()

        # ------------------------------------------------------
        # SÍNTOMA / REPORTE DEL CLIENTE
        # ------------------------------------------------------

        reporte_cliente = texto(
            data.get("reporte_cliente")
        )

        if reporte_cliente:
            sintoma = OrdenSintoma(
                orden=orden,
                descripcion=
                    reporte_cliente[:255],
                orden_item=1,
            )

            sintoma.full_clean()
            OrdenSintoma.objects.bulk_create(
                [sintoma]
            )
            stats["sintomas"] += 1

            if len(reporte_cliente) > 255:
                orden.requiere_revision_migracion = True

        # ------------------------------------------------------
        # REPUESTOS HISTÓRICOS
        # ------------------------------------------------------

        rep_objetos = []

        for posicion, item in enumerate(
            data.get("repuestos") or [],
            start=1,
        ):
            cantidad = dec(
                item.get("cantidad")
            )

            cantidad_guardar = cantidad

            if cantidad <= Decimal("0.00"):
                # Dato histórico anómalo de Getsoft.
                # El modelo histórico permite cantidad NULL.
                # Se conserva el valor original en json_origen
                # y la OT queda marcada para revisión.
                cantidad_guardar = None
                orden.requiere_revision_migracion = True
                stats["cantidad_anomala"] += 1

            subtotal_item = dec(
                item.get("subtotal")
            )

            subtotal_guardar = subtotal_item
            requiere_revision_item = False

            if subtotal_item < Decimal("0.00"):
                # El modelo histórico no admite subtotales negativos.
                # No inventamos un valor positivo: guardamos NULL en
                # subtotal, mantenemos cantidad/PU y el dato crudo
                # permanece en json_origen de la OT.
                subtotal_guardar = None
                requiere_revision_item = True
                orden.requiere_revision_migracion = True
                stats["subtotal_negativo"] += 1

            rep = OrdenInsumoHistorico(
                orden=orden,
                descripcion_original=(
                    texto(
                        item.get(
                            "descripcion_original"
                        )
                    )
                    or texto(
                        item.get(
                            "descripcion"
                        )
                    )
                ),
                codigo_original=(
                    texto(
                        item.get("codigo")
                    )
                    or None
                ),
                cantidad=cantidad_guardar,
                precio_unitario=dec(
                    item.get(
                        "precio_unitario"
                    )
                ),
                subtotal=subtotal_guardar,
                orden_item=int(
                    item.get(
                        "numero_item",
                        posicion,
                    )
                    or posicion
                ),
                requiere_revision=requiere_revision_item,
            )

            rep.full_clean()
            rep_objetos.append(rep)

        if rep_objetos:
            OrdenInsumoHistorico.objects.bulk_create(
                rep_objetos
            )
            stats["rep"] += len(
                rep_objetos
            )

        # ------------------------------------------------------
        # MO / MOE HISTÓRICOS
        # ------------------------------------------------------

        servicio_objetos = []

        def agregar_servicios(
            lista,
            tipo_servicio,
        ):
            for posicion, item in enumerate(
                lista or [],
                start=1,
            ):
                cantidad = dec(
                    item.get("cantidad")
                )

                cantidad_guardar = cantidad

                if cantidad <= Decimal("0.00"):
                    # Getsoft puede traer líneas históricas con
                    # cantidad 0. El valor crudo queda en json_origen;
                    # en el detalle histórico usamos NULL porque el
                    # modelo no admite cantidades <= 0.
                    cantidad_guardar = None
                    orden.requiere_revision_migracion = True
                    stats["cantidad_anomala"] += 1

                descripcion = (
                    texto(
                        item.get(
                            "descripcion_original"
                        )
                    )
                    or texto(
                        item.get(
                            "descripcion"
                        )
                    )
                )

                subtotal_item = dec(
                    item.get("subtotal")
                )

                subtotal_guardar = subtotal_item

                if subtotal_item < Decimal("0.00"):
                    subtotal_guardar = None
                    orden.requiere_revision_migracion = True
                    stats["subtotal_negativo"] += 1

                servicio = (
                    OrdenServicioHistorico(
                        orden=orden,
                        tipo=tipo_servicio,
                        descripcion_original=
                            descripcion,
                        cantidad=cantidad_guardar,
                        precio_unitario=dec(
                            item.get(
                                "precio_unitario"
                            )
                        ),
                        subtotal=subtotal_guardar,
                        es_cortesia=(
                            subtotal_item
                            == Decimal("0.00")
                        ),
                        orden_item=int(
                            item.get(
                                "numero_item",
                                posicion,
                            )
                            or posicion
                        ),
                        procedimientos=[],
                    )
                )

                servicio.full_clean()
                servicio_objetos.append(
                    servicio
                )

        agregar_servicios(
            data.get("mano_obra"),
            "MO",
        )
        agregar_servicios(
            data.get(
                "servicios_terceros"
            ),
            "MOE",
        )

        if servicio_objetos:
            OrdenServicioHistorico.objects.bulk_create(
                servicio_objetos
            )

            stats["mo"] += sum(
                1
                for item in servicio_objetos
                if item.tipo == "MO"
            )
            stats["moe"] += sum(
                1
                for item in servicio_objetos
                if item.tipo == "MOE"
            )

        if (
            not rep_objetos
            and not servicio_objetos
        ):
            stats["ot_sin_items"] += 1

        # ------------------------------------------------------
        # CONGELAR ECONOMÍA ORIGINAL DE GETSOFT
        # ------------------------------------------------------

        orden.total_general = (
            subtotal_fuente
        )
        orden.subtotal_sin_iva = (
            subtotal_fuente
        )

        if descuento_aplicable > Decimal("0.00"):
            orden.tipo_descuento = (
                "VALOR_FIJO"
            )
            orden.descuento_ingresado = (
                descuento_aplicable
            )
        else:
            orden.tipo_descuento = (
                "PORCENTAJE"
            )
            orden.descuento_ingresado = (
                Decimal("0.00")
            )

        orden.descuento_porcentaje = (
            porcentaje_descuento
        )
        orden.valor_descuento = (
            descuento_aplicable
        )

        # No enlazamos a la configuración tributaria actual:
        # la tasa se deriva del documento histórico.
        orden.configuracion_iva = None
        orden.porcentaje_iva = (
            porcentaje_iva
        )
        orden.valor_iva = iva_fuente
        orden.total_final = total_fuente
        orden.sumar_iva_al_total = True

        orden.estado = (
            "ANULADA"
            if es_anulada
            else "CERRADA"
        )

        # El estado anterior en DB es ABIERTA, por lo que este
        # cierre/anulación final es válido con el modelo actual.
        orden.save()

        stats["ot_nuevas"] += 1

        if orden.requiere_revision_migracion:
            stats["ot_revision"] += 1

        if es_anulada:
            stats["anuladas"] += 1
        else:
            stats["cerradas"] += 1

        return "NUEVA"
