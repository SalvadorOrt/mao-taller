from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from servicios.models import ServicioCatalogo, PrecioServicio, ServicioProcedimiento

def d(valor):
    return Decimal(str(valor)).quantize(Decimal("0.01"))

def s(codigo, descripcion, precio, procedimientos, categoria="MEC", tipo="PAQUETE"):
    return {
        "codigo": codigo,
        "descripcion": descripcion,
        "categoria": categoria,
        "tipo_servicio": tipo,
        "precio": precio,
        "requiere_tipo_tarifa": False,
        "requiere_variante": False,
        "procedimientos": procedimientos,
    }

SERVICIOS = [
    s("MEC-ABC-MOT-GAS", "ABC INTEGRAL DEL MOTOR GASOLINA", 45, [
        "DESMONTAJE/MONTAJE DEL RIEL DE INYECTORES DE COMBUSTIBLE",
        "LIMPIEZA ULTRASONICA DE INYECTORES",
        "CAMBIO MICROFILTROS DE INYECTORES",
        "DESMONTAJE/MONTAJE CUERPO DE ACELERACION",
        "LAVADA DEL CUERPO DE ACELERACION",
        "LIMPIEZA Y LUBRICACION DE VALVULA IAC",
        "REVISION BUJIAS DE ENCENDIDO",
        "CAMBIO FILTRO DE AIRE Y COMBUSTIBLE",
        "DESMONTAJE Y LAVADO CUERPO DE ACELERACION, CADA 50.000 KMS",
    ]),
    s("MEC-ABC-MOT-GAS-SUM", "ABC INTEGRAL DEL MOTOR GASOLINA CON FILTRO SUMERGIBLE", 60, [
        "DESMONTAJE/MONTAJE DEL MULTIPLE DE ADMISION",
        "DESMONTAJE/MONTAJE DEL RIEL DE INYECTORES DE COMBUSTIBLE",
        "LIMPIEZA ULTRASONICA DE INYECTORES",
        "CAMBIO MICROFILTROS DE INYECTORES",
        "DESMONTAJE/MONTAJE CUERPO DE ACELERACION",
        "LAVADA DEL CUERPO DE ACELERACION",
        "LIMPIEZA Y LUBRICACION DE VALVULA IAC",
        "CAMBIO BUJIAS DE ENCENDIDO",
        "CAMBIO FILTRO DE AIRE Y COMBUSTIBLE",
        "CAMBIO FILTRO COMBUSTIBLE SUMERGIBLE",
        "DIAGNOSTICO CON SCANNER GSCAN 2",
    ]),
    s("MEC-ABC-MOT-TIIDA", "ABC INTEGRAL DEL MOTOR NISSAN TIIDA", 60, [
        "DESMONTAJE/MONTAJE DEL MULTIPLE DE ADMISION",
        "DESMONTAJE/MONTAJE DEL RIEL DE INYECTORES DE COMBUSTIBLE",
        "LIMPIEZA ULTRASONICA DE INYECTORES",
        "CAMBIO MICROFILTROS DE INYECTORES",
        "DESMONTAJE/MONTAJE CUERPO DE ACELERACION",
        "LAVADA DEL CUERPO DE ACELERACION",
        "LIMPIEZA Y LUBRICACION DE VALVULA IAC",
        "CAMBIO BUJIAS DE ENCENDIDO",
        "CAMBIO FILTRO DE AIRE Y COMBUSTIBLE",
        "CAMBIO FILTRO COMBUSTIBLE SUMERGIBLE",
        "DIAGNOSTICO CON SCANNER GSCAN 2",
    ]),
    s("MEC-CAM-FILT-COMB-SUM", "CAMBIO FILTRO DE COMBUSTIBLE SUMERGIBLE", 15, [
        "DESMONTAJE DE ACCESO A BOMBA DE COMBUSTIBLE",
        "CAMBIO DE FILTRO COMBUSTIBLE SUMERGIBLE",
        "PRUEBA DE ENCENDIDO",
    ], tipo="SIMPLE"),
    s("MEC-SCAN-MOT", "DIAGNOSTICO CON SCANNER DE MOTOR", 15, [
        "CONEXION DE SCANNER",
        "LECTURA DE CODIGOS DE FALLA",
        "REVISION DE PARAMETROS",
        "BORRADO DE CODIGOS SI APLICA",
    ], tipo="SIMPLE"),
    s("MEC-CAM-ACE-MOT-5000", "CAMBIO DE ACEITE Y FILTRO DE MOTOR 5000 K", 26, [
        "DRENAJE DE ACEITE",
        "CAMBIO DE FILTRO",
        "COLOCACION DE ACEITE NUEVO",
        "REVISION GENERAL",
    ], tipo="SIMPLE"),
    s("MEC-FILTRO", "FILTRO", 7, [
        "SUMINISTRO O CAMBIO DE FILTRO SEGUN APLIQUE",
    ], tipo="SIMPLE"),
    s("MEC-1000K", "REVISION 1000 K", 7, [
        "REVISION GENERAL POSTERIOR AL MANTENIMIENTO",
        "REVISION DE NIVELES",
        "REVISION DE FUGAS",
    ], tipo="SIMPLE"),

    s("MEC-ABC-MOT-DIE", "ABC INTEGRAL DEL MOTOR DIESEL", 120, [
        "CALIBRACION DE VALVULAS EN FRIO",
        "DIAGNOSTICO CON SCANNER GSCAN 2",
        "CAMBIO FILTRO DE COMBUSTIBLE",
        "CAMBIO FILTRO COMBUSTIBLE/LLENADO LIQUIDO HIDRAULICO MTTO. SISTEMA INYECCION",
        "CAMBIO FILTRO DE AIRE",
        "LAVADA DEL CUERPO DE ACELERACION",
        "DESMONTAJE/MONTAJE DE VALVULA EGR",
        "LIMPIEZA DEL SENSOR MAF",
        "LIMPIEZA Y CAMBIO DE FILTRO - VALVULAS CONTROL DEL TURBO",
        "DESMONTAJE/MONTAJE DEL INTERCOOLER",
        "LAVADA DEL INTERCOOLER",
    ]),
    s("MEC-ABC-BAS-DIE", "ABC BASICO DE MOTOR DIESEL", 0, [
        "CAMBIO DE ACEITE Y FILTRO DE MOTOR",
        "CAMBIO FILTRO DE AIRE",
        "LIMPIEZA DE TRAMPA DE AGUA",
        "CAMBIO FILTRO COMBUSTIBLE/LLENADO LIQUIDO HIDRAULICO MTTO. SISTEMA INYECCION",
    ]),

    s("MEC-ABC-FRE", "ABC INTEGRAL DE FRENOS", 36, [
        "CAMBIO DE LIQUIDO DE FRENOS",
        "LIMPIEZA Y REGULACION DE FRENOS",
        "DESMONTAJE/MONTAJE DE RUEDAS DELANTERAS",
        "LUBRICACION DE PASADORES DE CALIPERS DE FRENO",
        "CAMBIO PASTILLAS DE FRENO",
        "CAMBIO DE ZAPATAS DE FRENO",
        "DESMONTAJE/MONTAJE DE DISCOS DE FRENO",
        "CAMBIO CILINDROS DE FRENO",
        "CAMBIO CABLES DEL FRENO DE MANO",
        "CAMBIO SELLOS Y GUARDAPOLVOS DE MORDAZAS DE FRENO",
        "CAMBIO BOMBA PRINCIPAL DE FRENOS",
    ]),
    s("MEC-CAM-LIQ-FRE", "CAMBIO DE LIQUIDO DE FRENOS", 80, [
        "DRENAJE DE LIQUIDO DE FRENOS",
        "LLENADO DE LIQUIDO NUEVO",
        "PURGA DEL SISTEMA",
        "PRUEBA DE FRENO",
    ], tipo="SIMPLE"),
    s("MEC-EMP-ZAP-PEQ", "EMPACADA Y REMACHADA DE ZAPATAS PEQUEÑOS", 20, [
        "DESMONTAJE DE ZAPATAS",
        "EMPACADA Y REMACHADA",
        "MONTAJE Y REGULACION",
    ], tipo="SIMPLE"),
    s("MEC-EMP-ZAP-GRA", "EMPACADA Y REMACHADA DE ZAPATAS GRANDES", 24, [
        "DESMONTAJE DE ZAPATAS",
        "EMPACADA Y REMACHADA",
        "MONTAJE Y REGULACION",
    ], tipo="SIMPLE"),

    s("MEC-ABC-REF", "ABC INTEGRAL DEL SISTEMA DE REFRIGERACION DE MOTOR", 60, [
        "PRUEBAS DE PRESION AL SISTEMA DE REFRIGERACION",
        "CAMBIO DEPOSITO DE RADIADOR",
        "LIMPIEZA DEL SISTEMA DE REFRIGERACION CON ADITIVO",
        "CAMBIO REFRIGERANTE DE MOTOR",
        "CAMBIO TERMOSTATO DE MOTOR",
        "CAMBIO TAPA DEL RADIADOR",
        "CAMBIO MANGUERA SUPERIOR E INFERIOR DEL RADIADOR",
        "CAMBIO MANGUERAS DE CALEFACCION",
        "CAMBIO RADIADOR DE MOTOR",
    ]),
    s("MEC-TAN-COMB", "DESMONTAJE/MONTAJE TANQUE DE COMBUSTIBLE", 60, [
        "LAVADO INTERIOR DEL TANQUE DE COMBUSTIBLE",
        "CAMBIO BOMBA DE ALTA PRESION DE COMBUSTIBLE",
        "CAMBIO FILTRO DE COMBUSTIBLE SUMERGIBLE",
        "MEDICION CON MANOMETRO DE PRESION DE COMBUSTIBLE",
        "SCANEO DE SISTEMA ELECTRONICO DE MOTOR",
    ]),
    s("MEC-CAJ-DES", "DESMONTAJE/MONTAJE CAJA DE CAMBIOS", 180, [
        "CAMBIO KIT EMBRAGUE",
        "CAMBIO DE ACEITE CAJA DE CAMBIOS",
        "CAMBIO DE ACEITE DIFERENCIAL POSTERIOR",
        "CAMBIO RETENEDOR POSTERIOR DEL CIGÜEÑAL",
        "CAMBIO DE CABLE DE EMBRAGUE",
        "CAMBIO BOMBA PRINCIPAL Y AUXILIAR DE EMBRAGUE",
        "REPARACION INTEGRAL DE CAJA DE CAMBIOS",
        "CAMBIO DE RULIMANES DE CAJA DE CAMBIOS",
    ]),
    s("MEC-CAM-ACE-CAJ", "CAMBIO DE ACEITE CAJA DE CAMBIOS", 90, [
        "DRENAJE DE ACEITE DE CAJA",
        "COLOCACION DE ACEITE NUEVO",
        "REVISION DE FUGAS",
    ], tipo="SIMPLE"),
    s("MEC-ACE-DIF-POST", "CAMBIO DE ACEITE DEL DIFERENCIAL POSTERIOR", 0, [
        "DRENAJE DE ACEITE DIFERENCIAL POSTERIOR",
        "COLOCACION DE ACEITE NUEVO",
        "REVISION DE FUGAS",
    ], tipo="SIMPLE"),
    s("MEC-ACE-DIF-DEL", "CAMBIO DE ACEITE DEL DIFERENCIAL DELANTERO", 0, [
        "DRENAJE DE ACEITE DIFERENCIAL DELANTERO",
        "COLOCACION DE ACEITE NUEVO",
        "REVISION DE FUGAS",
    ], tipo="SIMPLE"),
    s("MEC-ACE-TRANSF-4X4", "CAMBIO DE ACEITE CAJA DE TRANSFERENCIA 4X4", 0, [
        "DRENAJE DE ACEITE CAJA TRANSFERENCIA",
        "COLOCACION DE ACEITE NUEVO",
        "REVISION DE FUGAS",
    ], tipo="SIMPLE"),
    s("MEC-ACE-DIR-HID", "CAMBIO ACEITE HIDRAULICO DE DIRECCION", 0, [
        "DRENAJE DE ACEITE HIDRAULICO",
        "COLOCACION DE ACEITE NUEVO",
        "PURGA DEL SISTEMA",
    ], tipo="SIMPLE"),
    s("MEC-REF-MOT", "CAMBIO DE REFRIGERANTE DE MOTOR", 0, [
        "DRENAJE DE REFRIGERANTE",
        "LLENADO CON REFRIGERANTE",
        "PURGA DEL SISTEMA",
        "REVISION DE FUGAS",
    ], tipo="SIMPLE"),
    s("MEC-REAJ-SUSP", "REAJUSTE DE SUSPENSION", 0, [
        "REVISION DE SUSPENSION",
        "REAJUSTE DE ELEMENTOS",
        "PRUEBA DE RUTA SI APLICA",
    ], tipo="SIMPLE"),
    s("MEC-TERM-DIR", "CAMBIO TERMINALES DE DIRECCION LH Y RH", 0, [
        "DESMONTAJE DE TERMINALES",
        "CAMBIO DE TERMINALES",
        "REVISION FINAL",
    ], tipo="SIMPLE"),
    s("MEC-ROT-MESA-DEL", "CAMBIO DE ROTULA DE MESAS DELANTERAS", 0, [
        "DESMONTAJE DE ROTULA",
        "CAMBIO DE ROTULA",
        "REVISION DE SUSPENSION",
    ], tipo="SIMPLE"),
    s("MEC-BUJ-MESA-DEL", "CAMBIO BUJES DE MESA DELANTERA", 0, [
        "DESMONTAJE DE BUJES",
        "CAMBIO DE BUJES",
        "REVISION DE SUSPENSION",
    ], tipo="SIMPLE"),
    s("MEC-RUL-PUNTA-EJE", "CAMBIO DE RULIMAN PUNTA DE EJE LH", 0, [
        "DESMONTAJE DE RULIMAN",
        "CAMBIO DE RULIMAN",
        "PRUEBA FINAL",
    ], tipo="SIMPLE"),
    s("MEC-RUL-PUNTA-POST", "CAMBIO Y LUBRICACION DE RULIMANES INT. Y EXT. PUNTA EJE POSTERIOR", 0, [
        "DESMONTAJE DE RULIMANES",
        "CAMBIO Y LUBRICACION",
        "MONTAJE Y REVISION",
    ], tipo="SIMPLE"),
    s("MEC-RET-TAMBOR", "CAMBIO DE RETENEDOR DE TAMBOR", 0, [
        "DESMONTAJE DE TAMBOR",
        "CAMBIO DE RETENEDOR",
        "MONTAJE Y REVISION",
    ], tipo="SIMPLE"),
    s("MEC-PLAT-AMORT", "CAMBIO PLATILLOS SUPERIORES DE AMORTIGUADORES", 0, [
        "DESMONTAJE DE AMORTIGUADOR",
        "CAMBIO DE PLATILLOS",
        "MONTAJE Y REVISION",
    ], tipo="SIMPLE"),
    s("MEC-JUNTA-HOM", "CAMBIO, LIMPIEZA Y LUBRICACION DE GUARDAPOLVOS JUNTA HOMOCINETICA", 0, [
        "DESMONTAJE DE GUARDAPOLVOS",
        "LIMPIEZA DE JUNTA HOMOCINETICA",
        "LUBRICACION",
        "MONTAJE",
    ], tipo="SIMPLE"),
    s("MEC-NIV-LUCES", "REVISION DE NIVELES Y LUCES", 0, [
        "REVISION DE NIVEL DE ACEITE",
        "REVISION DE REFRIGERANTE",
        "REVISION DE LIQUIDO DE FRENOS",
        "REVISION DE LUCES EXTERIORES",
    ], tipo="SIMPLE"),
    s("MEC-LUB-PUERTAS", "LUBRICACION DE PUERTAS", 0, [
        "LUBRICACION DE BISAGRAS",
        "REVISION DE CERRADURAS",
    ], tipo="SIMPLE"),
    s("MEC-LAV-EXPRESS", "LAVADA EXPRESS EN SECO Y DESINFECCION", 0, [
        "LAVADA EXPRESS EN SECO",
        "DESINFECCION INTERIOR",
    ], tipo="SIMPLE"),
    s("MEC-RECT-DISC-DEL", "RECTIFICACION DE DISCOS DELANTEROS", 24, [
        "DESMONTAJE DE DISCOS",
        "RECTIFICACION DE DISCOS",
        "MONTAJE Y PRUEBA",
    ], tipo="SIMPLE"),
    s("MEC-COMP-MOT", "MEDIR COMPRESION DE MOTOR", 15, [
        "RETIRO DE BUJIAS O CALENTADORES",
        "MEDICION DE COMPRESION",
        "REGISTRO DE RESULTADOS",
    ], tipo="SIMPLE"),
    s("MEC-REV-COMPRA", "REVISION PARA COMPRA DE VEHICULO", 45, [
        "REVISION MECANICA GENERAL",
        "REVISION DE FUGAS",
        "REVISION DE SUSPENSION",
        "REVISION DE FRENOS",
        "PRUEBA DE RUTA SI APLICA",
    ], tipo="SIMPLE"),
    s("MEC-FUGA-REF", "PRUEBA FUGA DE REFRIGERANTE", 15, [
        "PRESURIZACION DEL SISTEMA",
        "INSPECCION DE FUGAS",
        "INFORME DE RESULTADO",
    ], tipo="SIMPLE"),
    s("MEC-FAROS-UV", "RESTAURACION DE FAROS DELANTEROS - TRATAMIENTO UV", 45, [
        "LIJADO PROGRESIVO",
        "PULIDO",
        "APLICACION DE TRATAMIENTO UV",
    ], tipo="SIMPLE"),
    s("MEC-FAROS-NORMAL", "RESTAURACION DE FAROS DELANTEROS - NORMAL", 25, [
        "LIJADO PROGRESIVO",
        "PULIDO",
        "LIMPIEZA FINAL",
    ], tipo="SIMPLE"),
]

PINTURA_INTEGRAL = [
    ("AUTO_5P", 600),
    ("AUTO_3P", 500),
    ("SUV_5P", 700),
    ("SUV_3P", 600),
    ("CAMIONETA_DC", 800),
    ("CAMIONETA_CS", 600),
]

RECUBRIMIENTO_CABINA = [
    ("CAMIONETA_CS", "NORMAL", 180),
    ("CAMIONETA_DC", "NORMAL", 180),
    ("CAMIONETA_CS", "ESPECIAL", 280),
    ("CAMIONETA_DC", "ESPECIAL", 280),
]

TRATAMIENTOS_CERAMICOS = [
    ("NO_APLICA", "NORMAL", 150),
    ("NO_APLICA", "ESPECIAL", 210),
]

class Command(BaseCommand):
    help = "Carga servicios MAO con precios y procedimientos."

    @transaction.atomic
    def handle(self, *args, **options):
        for data in SERVICIOS:
            servicio, _ = ServicioCatalogo.objects.update_or_create(
                codigo=data["codigo"],
                defaults={
                    "descripcion": data["descripcion"],
                    "categoria": data["categoria"],
                    "tipo_servicio": data["tipo_servicio"],
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
                defaults={"precio": d(data["precio"])},
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

        self.crear_tarifado_tipo(
            "PIN-PINTURA-INTEGRAL",
            "PINTURA INTEGRAL DE VEHICULO",
            "PIN",
            PINTURA_INTEGRAL,
        )

        self.crear_tarifado_tipo_variante(
            "PIN-RECUB-CABINA",
            "RECUBRIMIENTO DE CABINA",
            "PIN",
            RECUBRIMIENTO_CABINA,
        )

        self.crear_tarifado_tipo_variante(
            "PIN-TRAT-CERAMICO",
            "TRATAMIENTO CERAMICO DE PINTURA",
            "PIN",
            TRATAMIENTOS_CERAMICOS,
        )

        self.stdout.write(self.style.SUCCESS("Semilla cargada correctamente."))

    def crear_tarifado_tipo(self, codigo, descripcion, categoria, tarifas):
        servicio, _ = ServicioCatalogo.objects.update_or_create(
            codigo=codigo,
            defaults={
                "descripcion": descripcion,
                "categoria": categoria,
                "tipo_servicio": "VARIABLE",
                "precio_sugerido": d(0),
                "requiere_tipo_tarifa": True,
                "requiere_variante": False,
                "activo": True,
            },
        )

        for tipo_tarifa, precio in tarifas:
            PrecioServicio.objects.update_or_create(
                servicio=servicio,
                sucursal=None,
                tipo_tarifa_vehiculo=tipo_tarifa,
                variante_precio="NORMAL",
                defaults={"precio": d(precio)},
            )

    def crear_tarifado_tipo_variante(self, codigo, descripcion, categoria, tarifas):
        servicio, _ = ServicioCatalogo.objects.update_or_create(
            codigo=codigo,
            defaults={
                "descripcion": descripcion,
                "categoria": categoria,
                "tipo_servicio": "VARIABLE",
                "precio_sugerido": d(0),
                "requiere_tipo_tarifa": True,
                "requiere_variante": True,
                "activo": True,
            },
        )

        for tipo_tarifa, variante, precio in tarifas:
            PrecioServicio.objects.update_or_create(
                servicio=servicio,
                sucursal=None,
                tipo_tarifa_vehiculo=tipo_tarifa,
                variante_precio=variante,
                defaults={"precio": d(precio)},
            )
#py manage.py seed_servicios_mao