from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from servicios.models import (
    ServicioCatalogo,
    PrecioServicio,
    ServicioProcedimiento,
)


def d(valor):
    return Decimal(str(valor)).quantize(Decimal("0.01"))


SERVICIOS = [
    {
        "codigo": "MEC_CAMBIO_ACEITE_FILTRO",
        "descripcion": "CAMBIO DE ACEITE Y FILTRO DE MOTOR",
        "categoria": "MEC",
        "precio": 15,
        "requiere_tipo_tarifa": False,
        "requiere_variante": False,
        "procedimientos": [
            "CAMBIO FILTRO AIRE MOTOR",
            "REVISION DE NIVELES Y LUCES",
            "LAVADA DE CARROCERIA",
        ],
    },
    {
        "codigo": "MEC_ABC_FRENOS",
        "descripcion": "ABC INTEGRAL DE FRENOS",
        "categoria": "MEC",
        "precio": 36,
        "requiere_tipo_tarifa": False,
        "requiere_variante": False,
        "procedimientos": [
            "DESMONTAJE DE RUEDAS",
            "LIMPIEZA DE SISTEMA DE FRENOS",
            "REGULACION DE FRENOS",
            "LUBRICACION DE CALIPERS",
            "REVISION DE LIQUIDO DE FRENOS",
        ],
    },
    {
        "codigo": "MEC_SCANNER_MOTOR",
        "descripcion": "DIAGNOSTICO CON SCANNER DE MOTOR",
        "categoria": "MEC",
        "precio": 15,
        "requiere_tipo_tarifa": False,
        "requiere_variante": False,
        "procedimientos": [
            "CONEXION DE SCANNER",
            "LECTURA DE CODIGOS DE FALLA",
            "BORRADO DE CODIGOS SI APLICA",
            "PRUEBA DE FUNCIONAMIENTO",
        ],
    },
    {
        "codigo": "MEC_REVISION_NIVELES_LUCES",
        "descripcion": "REVISION DE NIVELES Y LUCES",
        "categoria": "MEC",
        "precio": 0,
        "requiere_tipo_tarifa": False,
        "requiere_variante": False,
        "procedimientos": [
            "REVISION NIVEL ACEITE MOTOR",
            "REVISION NIVEL REFRIGERANTE",
            "REVISION NIVEL LIQUIDO DE FRENOS",
            "REVISION LUCES EXTERIORES",
        ],
    },
]


PINTURA_INTEGRAL = [
    ("AUTO_5P", 600),
    ("AUTO_3P", 500),
    ("SUV_5P", 700),
    ("SUV_3P", 600),
    ("CAMIONETA_DC", 800),
    ("CAMIONETA_CS", 600),
]


class Command(BaseCommand):
    help = "Carga servicios MAO con precios y procedimientos incluidos."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Cargando servicios MAO...")

        for data in SERVICIOS:
            servicio, _ = ServicioCatalogo.objects.update_or_create(
                codigo=data["codigo"],
                defaults={
                    "descripcion": data["descripcion"],
                    "categoria": data["categoria"],
                    "precio_sugerido": d(data["precio"]),
                    "requiere_tipo_tarifa": data["requiere_tipo_tarifa"],
                    "requiere_variante": data["requiere_variante"],
                    "activo": True,
                },
            )

            PrecioServicio.objects.update_or_create(
                servicio=servicio,
                sucursal=None,
                tipo_tarifa_vehiculo="NO_APLICA",
                variante_precio="NORMAL",
                defaults={
                    "precio": d(data["precio"]),
                },
            )

            ServicioProcedimiento.objects.filter(servicio=servicio).delete()

            for orden, descripcion in enumerate(data["procedimientos"], start=1):
                ServicioProcedimiento.objects.create(
                    servicio=servicio,
                    descripcion=descripcion,
                    orden=orden,
                    obligatorio=True,
                    visible_en_ot=True,
                )

            self.stdout.write(f"OK: {servicio.codigo}")

        servicio_pintura, _ = ServicioCatalogo.objects.update_or_create(
            codigo="PIN_PINTURA_INTEGRAL",
            defaults={
                "descripcion": "PINTURA INTEGRAL DE VEHICULO",
                "categoria": "PIN",
                "precio_sugerido": d(0),
                "requiere_tipo_tarifa": True,
                "requiere_variante": False,
                "activo": True,
            },
        )

        for tipo_tarifa, precio in PINTURA_INTEGRAL:
            PrecioServicio.objects.update_or_create(
                servicio=servicio_pintura,
                sucursal=None,
                tipo_tarifa_vehiculo=tipo_tarifa,
                variante_precio="NORMAL",
                defaults={
                    "precio": d(precio),
                },
            )

        self.stdout.write(self.style.SUCCESS("Semilla cargada correctamente."))


#py manage.py seed_servicios_mao