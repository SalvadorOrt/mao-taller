import json
import hashlib
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from empresa.models import EmpresaEmisora
from ordenes_de_trabajo.models import (
    Sucursal,
    Cliente,
    ExpedienteVehiculo,
    OrdenTrabajo,
    OrdenInsumoHistorico,
    OrdenServicioHistorico,
    OrdenServicioDetalle,
    OrdenServicioProcedimientoDetalle,
)


RUC_EMPRESA_SUR = "1713268918001"
RUC_EMPRESA_NORTE = "1726247610001"


class Command(BaseCommand):
    help = "Importa órdenes históricas IA normalizadas hacia el modelo actual de MAO"

    def add_arguments(self, parser):
        parser.add_argument("archivo_json", type=str)
        parser.add_argument("--clear", action="store_true")
        parser.add_argument("--limite", type=int, default=None)
        parser.add_argument("--desde", type=int, default=0)

    # =====================================================
    # HELPERS GENERALES
    # =====================================================
    def limpiar_texto(self, valor, default=None):
        if valor in (None, "", "null", "None"):
            return default
        texto = str(valor).strip()
        return texto if texto else default

    def normalizar_mayus(self, valor, default=None):
        texto = self.limpiar_texto(valor, default)
        return texto.upper() if texto else default
    def limpiar_placa(self, valor):
        texto = self.normalizar_mayus(valor)

        if not texto:
            return None

        texto = texto.replace("-", "").replace(" ", "")

        # Si viene basura larga del Excel, no la guardes como placa.
        if len(texto) > 15:
            return None

        return texto
    def to_decimal(self, valor):
        if valor in (None, "", "null", "None"):
            return None

        try:
            texto = str(valor).replace(",", "").strip()
            numero = Decimal(texto)
            return numero.quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError):
            return None
    def decimal_no_negativo(self, valor, default=Decimal("0.00")):
        numero = self.to_decimal(valor)
        if numero is None or numero < 0:
            return default
        return numero
    def cantidad_historica(self, valor):
        numero = self.to_decimal(valor)
        if numero is None or numero <= 0:
            return Decimal("1.00")
        return numero
    def to_int(self, valor):
        if valor in (None, "", "null", "None"):
            return None

        try:
            return int(Decimal(str(valor).replace(",", "").strip()))
        except Exception:
            return None

    def to_date(self, valor):
        if not valor:
            return None

        texto = str(valor).strip()

        formatos = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
            "%d/%m/%y",
            "%d-%m-%y",
        ]

        for fmt in formatos:
            try:
                return datetime.strptime(texto, fmt).date()
            except ValueError:
                pass

        return None
    def fecha_valida_historica(self, fecha):
        if not fecha:
            return None

        hoy = timezone.now().date()

        # No permitir fechas futuras absurdas
        if fecha.year > hoy.year:
            return None

        # Tus históricos empiezan 2011
        if fecha.year < 2011:
            return None

        return fecha
    def generar_hash_json(self, data):
        contenido = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(contenido.encode("utf-8")).hexdigest()

    def filtrar_campos_modelo(self, modelo, datos):
        campos_validos = {f.name for f in modelo._meta.fields}
        return {k: v for k, v in datos.items() if k in campos_validos}

    # =====================================================
    # EMPRESA / SUCURSAL
    # =====================================================
    def crear_o_actualizar_empresas(self):
        empresa_sur, _ = EmpresaEmisora.objects.update_or_create(
            ruc=RUC_EMPRESA_SUR,
            defaults=self.filtrar_campos_modelo(EmpresaEmisora, {
                "razon_social": "ORTEGA LLIGUICOTA PAUL WILLIAMS",
                "nombre_comercial": "MANTENIMIENTO AUTOMOTRIZ ORTEGA",
                "dir_matriz": "QUITO, SECTOR SUR",
                "dir_establecimiento": "QUITO, SECTOR SUR",
                "obligado_contabilidad": "SI",
                "agente_retencion": True,
                "porcentaje_iva": Decimal("15.00"),
                "activo": True,
            }),
        )

        empresa_norte, _ = EmpresaEmisora.objects.update_or_create(
            ruc=RUC_EMPRESA_NORTE,
            defaults=self.filtrar_campos_modelo(EmpresaEmisora, {
                "razon_social": "ORTEGA MARTINEZ SALVADOR ANDRES",
                "nombre_comercial": "MANTENIMIENTO AUTOMOTRIZ ORTEGA",
                "dir_matriz": "E10 DE LOS JAZMINES N55-76 Y N56 DE LOS FRESNOS",
                "dir_establecimiento": "E10 DE LOS JAZMINES N55-76 Y N56 DE LOS FRESNOS",
                "obligado_contabilidad": "NO",
                "agente_retencion": False,
                "porcentaje_iva": Decimal("15.00"),
                "activo": True,
            }),
        )

        return empresa_sur, empresa_norte

    def obtener_o_crear_sucursal(self, codigo):
        codigo = self.normalizar_mayus(codigo, "SUR")

        empresa_sur = EmpresaEmisora.objects.filter(ruc=RUC_EMPRESA_SUR).first()
        empresa_norte = EmpresaEmisora.objects.filter(ruc=RUC_EMPRESA_NORTE).first()

        if codigo == "NORTE":
            nombre = "MAO Norte"
            empresa = empresa_norte
        else:
            codigo = "SUR"
            nombre = "MAO Sur"
            empresa = empresa_sur

        defaults = self.filtrar_campos_modelo(Sucursal, {
            "nombre": nombre,
            "empresa": empresa,
            "activa": True,
        })

        sucursal, _ = Sucursal.objects.update_or_create(
            codigo=codigo,
            defaults=defaults,
        )

        return sucursal

    # =====================================================
    # CLIENTE / EXPEDIENTE
    # =====================================================
    def obtener_o_crear_cliente(self, cabecera):
        nombre = self.limpiar_texto(cabecera.get("cliente"), "CLIENTE HISTÓRICO")
        telefono = self.limpiar_texto(cabecera.get("telefonos"))
        email = self.limpiar_texto(cabecera.get("email"))
        direccion = None

        if telefono:
            if len(telefono) > 20 or not any(c.isdigit() for c in telefono):
                direccion = telefono
                telefono = None
            else:
                telefono = telefono[:20]

        identificacion = f"HIST{abs(hash(nombre))}"[:13]

        defaults = self.filtrar_campos_modelo(Cliente, {
            "tipo_documento": "P",
            "nombre_completo": nombre,
            "telefono": telefono,
            "direccion": direccion,
            "email": email,
        })

        cliente, _ = Cliente.objects.update_or_create(
            identificacion=identificacion,
            defaults=defaults,
        )

        return cliente

    def obtener_o_crear_expediente(self, cliente, cabecera):
        placa = self.limpiar_placa(cabecera.get("placa"))
        vehiculo = self.limpiar_texto(cabecera.get("vehiculo"))
        cliente_nombre = self.limpiar_texto(cabecera.get("cliente"))
        anio_vehiculo = self.to_int(cabecera.get("anio"))

        if not placa:
            return None

        expediente = ExpedienteVehiculo.objects.filter(placa__iexact=placa).first()

        datos = self.filtrar_campos_modelo(ExpedienteVehiculo, {
            "cliente": cliente,
            "cliente_actual": cliente,
            "cliente_respaldo": cliente_nombre,
            "placa": placa,
            "vehiculo": vehiculo,
            "anio": anio_vehiculo,
            "anio_vehiculo": anio_vehiculo,
            "observacion": "Expediente creado por migración histórica.",
            "activo": True,
        })

        if expediente:
            for campo, valor in datos.items():
                if valor not in (None, "") and not getattr(expediente, campo, None):
                    setattr(expediente, campo, valor)

            expediente.save()
            return expediente

        return ExpedienteVehiculo.objects.create(**datos)

    # =====================================================
    # ORDEN
    # =====================================================
    def crear_numero_migrado(self, sucursal, anio, numero_origen, hoja):
        numero_origen = self.normalizar_mayus(numero_origen, "SIN-NUMERO")
        hoja = self.limpiar_texto(hoja, "1")
        return f"MIG-{sucursal.codigo}-{anio}-{numero_origen}-H{hoja}"

    def importar_orden(self, item):
        cabecera = item.get("cabecera", {}) or {}
        normalizado = item.get("historico_normalizado", {}) or {}
        totales = item.get("totales", {}) or {}

        sucursal = self.obtener_o_crear_sucursal(item.get("sucursal_codigo", "SUR"))
        cliente = self.obtener_o_crear_cliente(cabecera)
        expediente = self.obtener_o_crear_expediente(cliente, cabecera)

        numero_origen = self.normalizar_mayus(cabecera.get("numero_ot"), "SIN-NUMERO")
        anio = (
            self.to_int(item.get("anio"))
            or self.to_int(item.get("anio_carpeta"))
            or timezone.now().year
        )
        hoja = self.limpiar_texto(item.get("hoja"), "1")

        hash_migracion = (
            self.limpiar_texto(item.get("hash_migracion"))
            or self.generar_hash_json(item)
        )

        numero_migrado = self.crear_numero_migrado(
            sucursal=sucursal,
            anio=anio,
            numero_origen=numero_origen,
            hoja=hoja,
        )

        observaciones = normalizado.get("observaciones", []) or []
        recomendaciones = normalizado.get("recomendaciones", []) or []
        sintomas = normalizado.get("sintomas_cliente", []) or []

        texto_observaciones = "\n".join(observaciones + recomendaciones)
        texto_sintomas = "\n".join(sintomas)

        fecha_origen = self.fecha_valida_historica(
    self.to_date(cabecera.get("fecha"))
)

        defaults_orden = self.filtrar_campos_modelo(OrdenTrabajo, {
            "sucursal": sucursal,
            "expediente": expediente,
            "cliente": cliente,
            "cliente_respaldo": self.limpiar_texto(cabecera.get("cliente")),

            "es_migrada": True,
            "numero_orden_origen": numero_origen,
            "archivo_origen": self.limpiar_texto(item.get("archivo")),
            "hoja_origen": hoja,
            "anio_origen_migracion": anio,
            "json_origen": item,
            "hash_migracion": hash_migracion,
            "requiere_revision_migracion": item.get("requiere_revision_migracion", False),

            "placa": self.limpiar_placa(cabecera.get("placa")),
            "vehiculo": self.limpiar_texto(cabecera.get("vehiculo")),
            "anio_vehiculo": self.to_int(cabecera.get("anio")),
            "fecha_origen": fecha_origen,
            "fecha_ingreso": (
                    timezone.make_aware(
                        datetime.combine(fecha_origen, datetime.min.time())
                    )
                    if fecha_origen
                    else timezone.now()
                ),
            "kilometraje": self.to_int(cabecera.get("kms")),
            "proximo_mantenimiento_km": self.to_int(cabecera.get("proximo_mantenimiento")),

            "estado": "CERRADA",
            "sintomas_cliente": texto_sintomas,
            "observaciones_tecnicas": texto_observaciones,

            "tipo_tarifa_vehiculo": "NO_APLICA",
            "gama_vehiculo": "NO_APLICA",

            "subtotal_repuestos": self.to_decimal(totales.get("subtotal_repuestos")),
            "subtotal_mano_obra": self.to_decimal(totales.get("subtotal_mano_obra")),
            "subtotal_mano_obra_externa": self.to_decimal(totales.get("subtotal_mano_obra_externa")),
            "total": self.to_decimal(totales.get("total")),
        })

        orden, creada = OrdenTrabajo.objects.update_or_create(
            numero_orden=numero_migrado,
            defaults=defaults_orden,
        )

        OrdenInsumoHistorico.objects.filter(orden=orden).delete()
        OrdenServicioHistorico.objects.filter(orden=orden).delete()
        OrdenServicioDetalle.objects.filter(orden=orden).delete()
        # =================================================
        # INSUMOS HISTÓRICOS
        # =================================================
        for idx, insumo in enumerate(normalizado.get("insumos_historicos", []) or [], start=1):
            descripcion = self.limpiar_texto(insumo.get("descripcion_original"))

            if not descripcion:
                continue

            datos_insumo = self.filtrar_campos_modelo(OrdenInsumoHistorico, {
                "orden": orden,
                "codigo_original": self.normalizar_mayus(insumo.get("codigo_original")),
                "descripcion_original": descripcion,
                "cantidad": self.cantidad_historica(insumo.get("cantidad")),
                "subtotal": self.decimal_no_negativo(insumo.get("subtotal")),
                "subtotal": self.to_decimal(insumo.get("subtotal")),
                "orden_item": self.to_int(insumo.get("orden_item")) or idx,
                "requiere_revision": insumo.get("requiere_revision", False),
            })

            OrdenInsumoHistorico.objects.create(**datos_insumo)

        # =================================================
        # SERVICIOS HISTÓRICOS + DETALLE OPERATIVO: MO / MOE
        # =================================================
        servicios_historicos = normalizado.get("servicios_historicos", []) or []

        if not servicios_historicos:
            servicios_historicos = []

            for item_mo in (item.get("mano_obra", {}) or {}).get("items", []) or []:
                servicios_historicos.append({
                    "tipo": "MO",
                    "descripcion_original": item_mo.get("descripcion"),
                    "cantidad": item_mo.get("cantidad"),
                    "precio_unitario": item_mo.get("precio_unitario"),
                    "subtotal": item_mo.get("subtotal"),
                    "es_cortesia": item_mo.get("es_cortesia", False),
                    "orden_item": len(servicios_historicos) + 1,
                    "procedimientos": item_mo.get("procedimientos", []),
                })

            for item_moe in (item.get("mano_obra_externa", {}) or {}).get("items", []) or []:
                servicios_historicos.append({
                    "tipo": "MOE",
                    "descripcion_original": item_moe.get("descripcion"),
                    "cantidad": item_moe.get("cantidad"),
                    "precio_unitario": item_moe.get("precio_unitario"),
                    "subtotal": item_moe.get("subtotal"),
                    "es_cortesia": item_moe.get("es_cortesia", False),
                    "orden_item": len(servicios_historicos) + 1,
                    "procedimientos": item_moe.get("procedimientos", []),
                })

        for idx, servicio in enumerate(servicios_historicos, start=1):
            descripcion = self.limpiar_texto(servicio.get("descripcion_original"))

            if not descripcion:
                continue

            tipo = self.normalizar_mayus(servicio.get("tipo"), "MO")
            if tipo not in ["MO", "MOE"]:
                tipo = "MO"

            cantidad = self.cantidad_historica(servicio.get("cantidad"))
            precio_unitario = self.decimal_no_negativo(servicio.get("precio_unitario"))
            subtotal = self.decimal_no_negativo(servicio.get("subtotal"))
            orden_item = self.to_int(servicio.get("orden_item")) or idx
            procedimientos = servicio.get("procedimientos", []) or []

            # 1) Guarda histórico/auditoría
            OrdenServicioHistorico.objects.create(**self.filtrar_campos_modelo(OrdenServicioHistorico, {
                "orden": orden,
                "tipo": tipo,
                "descripcion_original": descripcion,
                "cantidad": cantidad,
                "precio_unitario": precio_unitario,
                "subtotal": subtotal,
                "es_cortesia": servicio.get("es_cortesia", False),
                "orden_item": orden_item,
                "procedimientos": procedimientos,
            }))

            # 2) Guarda en tabla operativa para que se vea en MOI/MOE
            detalle = OrdenServicioDetalle.objects.create(
                orden=orden,
                servicio=None,
                tipo_servicio="MEC" if tipo == "MO" else "EXT",
                descripcion_servicio=descripcion,
                cantidad=cantidad,
                precio_unitario=precio_unitario,
                orden_item=orden_item,
                tipo_tarifa_aplicada="NO_APLICA",
                variante_precio_aplicada="NORMAL",
            )

            # 3) Guarda procedimientos si existen
            for j, proc in enumerate(procedimientos, start=1):
                proc_txt = self.limpiar_texto(proc)
                if proc_txt:
                    OrdenServicioProcedimientoDetalle.objects.create(
                        detalle_servicio=detalle,
                        descripcion=proc_txt,
                        orden_item=j,
                    )
        orden.save()

        return orden, creada
    # =====================================================
    # HANDLE
    # =====================================================
    def handle(self, *args, **options):
        archivo = options["archivo_json"]

        self.stdout.write(self.style.WARNING("Configurando empresas y sucursales..."))

        self.crear_o_actualizar_empresas()
        self.obtener_o_crear_sucursal("SUR")
        self.obtener_o_crear_sucursal("NORTE")

        if options["clear"]:
            self.stdout.write(self.style.WARNING("Eliminando órdenes históricas migradas..."))

            with transaction.atomic():
                OrdenServicioHistorico.objects.all().delete()
                OrdenInsumoHistorico.objects.all().delete()
                OrdenTrabajo.objects.filter(es_migrada=True).delete()

            self.stdout.write(self.style.SUCCESS("Históricos eliminados."))

        with open(archivo, "r", encoding="utf-8") as f:
            data = json.load(f)

        ordenes = data.get("ordenes", [])

        desde = options["desde"] or 0
        limite = options["limite"]

        ordenes = ordenes[desde:]

        if limite:
            ordenes = ordenes[:limite]

        creadas = 0
        actualizadas = 0
        errores = 0

        self.stdout.write(self.style.WARNING(f"Órdenes a procesar: {len(ordenes)}"))

        for item in ordenes:
            try:
                with transaction.atomic():
                    orden, creada = self.importar_orden(item)

                if creada:
                    creadas += 1
                    estado = "CREADA"
                else:
                    actualizadas += 1
                    estado = "ACTUALIZADA"

                self.stdout.write(
                    self.style.SUCCESS(
                        f"{estado}: {orden.numero_orden} | {orden.placa or 'SIN PLACA'} | {orden.nombre_cliente_final}"
                    )
                )

            except Exception as e:
                errores += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"ERROR archivo={item.get('archivo')} hoja={item.get('hoja')}: {e}"
                    )
                )

        self.stdout.write(self.style.SUCCESS("Carga histórica terminada."))
        self.stdout.write(f"Órdenes creadas: {creadas}")
        self.stdout.write(f"Órdenes actualizadas: {actualizadas}")
        self.stdout.write(f"Errores: {errores}")



#py manage.py importar_ots_historicas_ia ordenes_importados.json --limite 20

#py manage.py importar_ots_historicas_ia ordenes_importados.json --clear