from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone
from empresa.models import EmpresaEmisora
from decimal import Decimal, ROUND_HALF_UP
import uuid
from django.db import models
from django.core.exceptions import ValidationError
from datetime import datetime
from django.utils.dateparse import parse_date

TIPOS_TARIFA_VEHICULO = [
        ("NO_APLICA", "No aplica"),
        ("AUTO", "Auto"),
        ("AUTO_3P", "Auto 3 puertas"),
        ("AUTO_5P", "Auto 5 puertas"),
        ("SUV_3P", "SUV 3 puertas"),
        ("SUV_5P", "SUV 5 puertas"),
        ("CAMIONETA_CS", "Camioneta cabina sencilla"),
        ("CAMIONETA_DC", "Camioneta doble cabina"),
        ("CAMIONETA_GRANDE", "Camioneta grande"),
    ]
GAMAS_VEHICULO = [
        ("NO_APLICA", "No aplica"),
        ("ECONOMICA", "Económica"),
        ("MEDIA", "Media"),
        ("MEDIA_ALTA", "Media alta"),
        ("ALTA", "Alta"),
        ("PREMIUM", "Premium"),
        ("LUJO", "Lujo"),
        ("COMERCIAL", "Comercial"),
        ("DEPORTIVA", "Deportiva"),
    ]
# ==========================================
# 1. SUCURSALES
# ==========================================
class Sucursal(models.Model):
    
    empresa = models.ForeignKey(
        EmpresaEmisora, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="sucursales",
    )

    nombre = models.CharField(max_length=100, unique=True)
    codigo = models.CharField(max_length=20, unique=True)
    direccion = models.CharField(max_length=255, null=True, blank=True)
    telefono = models.CharField(max_length=50, null=True, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Sucursal"
        verbose_name_plural = "Sucursales"

    def save(self, *args, **kwargs):
        if self.nombre:
            self.nombre = self.nombre.strip()
        if self.codigo:
            self.codigo = self.codigo.strip().upper()
        if self.direccion:
            self.direccion = self.direccion.strip()
        if self.telefono:
            self.telefono = self.telefono.strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


# ==========================================
# 2. TÉCNICOS (Personal del Taller - No Usuarios)
# ==========================================
class Tecnico(models.Model):
    cedula = models.CharField(max_length=15, unique=True, null=True, blank=True, verbose_name="Cédula / Identificación")
    nombre = models.CharField(max_length=100)
    especialidad = models.CharField(max_length=50, blank=True, null=True)
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.SET_NULL,
        related_name="tecnicos",
        null=True,
        blank=True,
    )
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Técnico"
        verbose_name_plural = "Técnicos"

    def save(self, *args, **kwargs):
        if self.nombre:
            self.nombre = self.nombre.strip()
        if self.especialidad:
            self.especialidad = self.especialidad.strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre

# ==========================================
# CLIENTE
# ==========================================
class Cliente(models.Model):

    TIPOS_DOC = [
        ("C", "Cédula"),
        ("R", "RUC"),
        ("P", "Pasaporte"),
        ("S", "Sin Documento"),
    ]

    tipo_documento = models.CharField(
        max_length=1,
        choices=TIPOS_DOC,
        default="S",
    )

    identificacion = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Identificación",
    )

    nombre_completo = models.CharField(
        max_length=200
    )

    # ==========================================
    # CONTACTO
    # ==========================================
    telefono = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Teléfono Principal",
    )

    telefono_secundario = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Teléfono Familiar/Alternativo",
    )

    telefono_trabajo = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Teléfono Trabajo/Fijo",
    )

    email = models.EmailField(
        null=True,
        blank=True,
    )

    direccion = models.TextField(
        null=True,
        blank=True,
    )

    # ==========================================
    # DATOS PERSONALES
    # ==========================================
    genero = models.CharField(
        max_length=30,
        null=True,
        blank=True,
    )

    sexo = models.CharField(
        max_length=30,
        null=True,
        blank=True,
    )

    estado_civil = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )

    conyuge = models.CharField(
        max_length=200,
        null=True,
        blank=True,
    )

    nacionalidad = models.CharField(
        max_length=80,
        null=True,
        blank=True,
    )

    fecha_nacimiento = models.DateField(
        null=True,
        blank=True,
    )

    fecha_cedulacion = models.DateField(
        null=True,
        blank=True,
    )

    lugar_nacimiento = models.CharField(
        max_length=250,
        null=True,
        blank=True,
    )

    instruccion = models.CharField(
        max_length=150,
        null=True,
        blank=True,
    )

    profesion = models.CharField(
        max_length=150,
        null=True,
        blank=True,
    )

    tipo_sangre = models.CharField(
        max_length=10,
        null=True,
        blank=True,
    )

    # ==========================================
    # PADRES
    # ==========================================
    nombre_madre = models.CharField(
        max_length=200,
        null=True,
        blank=True,
    )

    nombre_padre = models.CharField(
        max_length=200,
        null=True,
        blank=True,
    )

    # ==========================================
    # DOMICILIO
    # ==========================================
    lugar_domicilio = models.CharField(
        max_length=250,
        null=True,
        blank=True,
    )

    calle_domicilio = models.CharField(
        max_length=250,
        null=True,
        blank=True,
    )

    numeracion_domicilio = models.CharField(
        max_length=80,
        null=True,
        blank=True,
    )

    provincia = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    canton = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    parroquia = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    otras_direcciones = models.JSONField(
        default=list,
        blank=True,
    )

    # ==========================================
    # LICENCIA
    # ==========================================
    licencia_tipo = models.CharField(
        max_length=10,
        null=True,
        blank=True,
    )

    licencia_fecha_desde = models.DateField(
        null=True,
        blank=True,
    )

    licencia_fecha_hasta = models.DateField(
        null=True,
        blank=True,
    )

    licencia_puntos = models.CharField(
        max_length=20,
        null=True,
        blank=True,
    )

    licencia_restricciones = models.TextField(
        null=True,
        blank=True,
    )

    licencia_todos = models.JSONField(
        default=list,
        blank=True,
    )

    # ==========================================
    # DISCAPACIDAD
    # ==========================================
    carnet_conadis = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    discapacidad = models.BooleanField(
        null=True,
        blank=True,
    )

    porcentaje_discapacidad = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )

    # ==========================================
    # DATOS SRI / RUC
    # ==========================================
    razon_social = models.CharField(
        max_length=250,
        null=True,
        blank=True,
    )

    estado_contribuyente_ruc = models.CharField(
        max_length=80,
        null=True,
        blank=True,
    )

    actividad_economica_principal = models.TextField(
        null=True,
        blank=True,
    )

    tipo_contribuyente = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    regimen = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    categoria = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    obligado_llevar_contabilidad = models.CharField(
        max_length=10,
        null=True,
        blank=True,
    )

    agente_retencion = models.CharField(
        max_length=10,
        null=True,
        blank=True,
    )

    contribuyente_especial = models.CharField(
        max_length=10,
        null=True,
        blank=True,
    )

    contribuyente_fantasma = models.CharField(
        max_length=10,
        null=True,
        blank=True,
    )

    transacciones_inexistentes = models.CharField(
        max_length=10,
        null=True,
        blank=True,
    )

    representantes_legales = models.JSONField(
        default=list,
        blank=True,
    )

    establecimientos = models.JSONField(
        default=list,
        blank=True,
    )

    # ==========================================
    # CONTROL API
    # ==========================================
    datos_full_consultados = models.BooleanField(
        default=False
    )

    datos_api_originales = models.JSONField(
        default=dict,
        blank=True,
    )

    fecha_ultima_consulta_api = models.DateTimeField(
        null=True,
        blank=True,
    )
    def actualizar_campo(self, campo, valor_api):
        """
        Actualiza el atributo solo si la API trae un valor válido,
        preservando lo que ya tenemos en base de datos.
        """
        if valor_api not in [None, "", [], {}]:
            # Si es string, limpiamos espacios, si no, asignamos directo
            valor = str(valor_api).strip() if isinstance(valor_api, str) else valor_api
            setattr(self, campo, valor)
    def actualizar_desde_diccionario(self, data, es_ruc=False, full=False):
        """
        Lógica unificada: Solo actualiza campos si la API trae datos 
        y mantiene los que ya existen si la API devuelve vacío.
        """
        if es_ruc:
            self.cargar_desde_api_ruc(data)
        else:
            self.cargar_desde_api_persona(data, full=full)
        
        self.fecha_ultima_consulta_api = timezone.now()
        self.save()
    def aplicar_datos_api(self, data, es_ruc=False, full=False):
        """
        Actualiza solo los campos que están vacíos en la BDD,
        o que la API trae como valor nuevo.
        """
        # Guardamos el estado original para comparar si es necesario
        if es_ruc:
            self.cargar_desde_api_ruc(data)
        else:
            self.cargar_desde_api_persona(data, full=full)
            
        self.fecha_ultima_consulta_api = timezone.now()
    # En models.py, dentro de tu clase Cliente:
    def actualizar_datos_inteligente(self, data, es_ruc=False, full=False):
        """
        Fusiona datos de API sin sobrescribir información manual crítica.
        """
        if es_ruc:
            self.cargar_desde_api_ruc(data)
        else:
            # Usamos los métodos existentes que ya tienen lógica de respaldo
            self.cargar_desde_api_persona(data, full=full)
        
        self.fecha_ultima_consulta_api = timezone.now()
        if full:
            self.datos_full_consultados = True
        self.save()
    # ==========================================
    # META
    # ==========================================
    class Meta:
        ordering = ["nombre_completo"]

        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"

        indexes = [
            models.Index(fields=["nombre_completo"]),
            models.Index(fields=["identificacion"]),
            models.Index(fields=["tipo_documento"]),
        ]

    # ==========================================
    # DETECTAR TIPO DOCUMENTO
    # ==========================================
    def detectar_tipo_documento(self):

        if not self.identificacion:
            return "S"

        valor = self.identificacion.strip().upper()

        if (
            valor.startswith("PROV-")
            or valor.startswith("HIST")
        ):
            return "S"

        if valor.isdigit():

            if len(valor) == 10:
                return "C"

            if len(valor) == 13:
                return "R"

        return "P"

    # ==========================================
    # NORMALIZAR DATOS
    # ==========================================
    def normalizar_datos(self):

        if self.identificacion:
            self.identificacion = (
                self.identificacion
                .strip()
                .upper()
            )

        else:
            uuid_corto = str(uuid.uuid4())[:6].upper()
            self.identificacion = f"PROV-{uuid_corto}"

        self.tipo_documento = (
            self.detectar_tipo_documento()
        )

        campos_upper = [
            "nombre_completo",
            "direccion",
            "genero",
            "sexo",
            "estado_civil",
            "conyuge",
            "nacionalidad",
            "nombre_madre",
            "nombre_padre",
            "lugar_nacimiento",
            "lugar_domicilio",
            "calle_domicilio",
            "numeracion_domicilio",
            "provincia",
            "canton",
            "parroquia",
            "instruccion",
            "profesion",
            "razon_social",
            "estado_contribuyente_ruc",
            "actividad_economica_principal",
            "tipo_contribuyente",
            "regimen",
            "categoria",
        ]

        for campo in campos_upper:
            valor = getattr(self, campo, None)

            if valor:
                setattr(
                    self,
                    campo,
                    str(valor).strip().upper()
                )

        telefonos = [
            "telefono",
            "telefono_secundario",
            "telefono_trabajo",
        ]

        for campo in telefonos:
            valor = getattr(self, campo, None)

            if valor:
                setattr(
                    self,
                    campo,
                    str(valor).strip()
                )

        if self.email:
            self.email = (
                self.email
                .strip()
                .lower()
            )

    # ==========================================
    # VALIDACIONES
    # ==========================================
    def clean(self):

        self.normalizar_datos()

        if (
            not self.nombre_completo
            or not self.nombre_completo.strip()
        ):
            raise ValidationError(
                "El nombre completo es obligatorio."
            )

        if not self.identificacion:
            raise ValidationError(
                "No se pudo generar identificación."
            )

        es_codigo_especial = (
            self.identificacion.startswith("PROV-")
            or self.identificacion.startswith("HIST")
        )

        if (
            es_codigo_especial
            or self.tipo_documento == "S"
        ):
            return

        if self.tipo_documento in {"C", "R"}:

            if not self.identificacion.isdigit():
                raise ValidationError(
                    "La identificación debe contener solo números."
                )

        if (
            self.tipo_documento == "C"
            and len(self.identificacion) != 10
        ):
            raise ValidationError(
                "La cédula debe tener 10 dígitos."
            )

        if (
            self.tipo_documento == "R"
            and len(self.identificacion) != 13
        ):
            raise ValidationError(
                "El RUC debe tener 13 dígitos."
            )

        if (
            self.tipo_documento == "P"
            and len(self.identificacion) < 3
        ):
            raise ValidationError(
                "Pasaporte inválido."
            )

    # ==========================================
    # CARGAR PERSONA API
    # ==========================================
    def parsear_fecha_api(self, valor):
        if not valor:
            return None

        valor = str(valor).strip()

        try:
            if "/" in valor:
                return datetime.strptime(valor, "%d/%m/%Y").date()
        except Exception:
            return None

        return parse_date(valor)


    def cargar_desde_api_persona(self, data, full=False):
        persona = data.get("persona", data)
        fechas = persona.get("fechas", {})
        direccion = persona.get("direccion", {})
        licencia = data.get("licencia", {})

        self.identificacion = persona.get("cedula") or data.get("cedula") or self.identificacion
        self.nombre_completo = persona.get("nombre") or data.get("nombre") or self.nombre_completo

        self.telefono = persona.get("celular") or self.telefono
        self.telefono_trabajo = persona.get("telefono") or self.telefono_trabajo
        self.email = persona.get("email") or self.email

        self.genero = persona.get("genero") or data.get("genero") or self.genero
        self.sexo = persona.get("sexo") or data.get("sexo") or self.sexo
        self.estado_civil = persona.get("estadoCivil") or data.get("estadoCivil") or self.estado_civil
        self.conyuge = persona.get("conyuge") or data.get("conyuge") or self.conyuge
        self.nacionalidad = persona.get("nacionalidad") or data.get("nacionalidad") or self.nacionalidad

        self.nombre_madre = persona.get("nombreMadre") or data.get("nombreMadre") or self.nombre_madre
        self.nombre_padre = persona.get("nombrePadre") or data.get("nombrePadre") or self.nombre_padre

        self.fecha_nacimiento = self.parsear_fecha_api(
            fechas.get("nacimiento") or data.get("fechaNacimiento")
        ) or self.fecha_nacimiento

        self.fecha_cedulacion = self.parsear_fecha_api(
            fechas.get("cedulacion") or data.get("fechaCedulacion")
        ) or self.fecha_cedulacion

        self.lugar_nacimiento = persona.get("lugarNacimiento") or data.get("lugarNacimiento") or self.lugar_nacimiento

        self.lugar_domicilio = direccion.get("domicilio") or data.get("lugarDomicilio") or self.lugar_domicilio
        self.calle_domicilio = direccion.get("calle") or data.get("calleDomicilio") or self.calle_domicilio
        self.numeracion_domicilio = direccion.get("numeroCasa") or data.get("numeracionDomicilio") or self.numeracion_domicilio

        self.provincia = direccion.get("provincia") or self.provincia
        self.canton = direccion.get("canton") or self.canton
        self.parroquia = direccion.get("parroquia") or self.parroquia
        self.otras_direcciones = direccion.get("otrasDirecciones") or self.otras_direcciones

        if not self.direccion:
            partes = [
                self.lugar_domicilio,
                self.calle_domicilio,
                self.numeracion_domicilio,
            ]
            self.direccion = " / ".join([p for p in partes if p])

        self.instruccion = persona.get("instruccion") or data.get("instruccion") or self.instruccion
        self.profesion = persona.get("profesion") or data.get("profesion") or self.profesion
        self.tipo_sangre = persona.get("tipoSangre") or data.get("tipoSangre") or self.tipo_sangre

        self.licencia_tipo = licencia.get("tipo") or self.licencia_tipo
        self.licencia_fecha_desde = self.parsear_fecha_api(licencia.get("fechaDesde")) or self.licencia_fecha_desde
        self.licencia_fecha_hasta = self.parsear_fecha_api(licencia.get("fechaHasta")) or self.licencia_fecha_hasta
        self.licencia_puntos = licencia.get("puntos") or self.licencia_puntos
        self.licencia_restricciones = licencia.get("restricciones") or self.licencia_restricciones
        self.licencia_todos = licencia.get("todos") or self.licencia_todos

        self.carnet_conadis = persona.get("carnetConadis") or self.carnet_conadis

        if persona.get("discapacidad") is not None:
            self.discapacidad = persona.get("discapacidad")

        self.porcentaje_discapacidad = persona.get("porcentajeDiscapacidad") or self.porcentaje_discapacidad

        self.datos_full_consultados = full or bool(licencia) or self.datos_full_consultados
        self.datos_api_originales = data
        self.normalizar_datos()

    # ==========================================
    # CARGAR RUC API
    # ==========================================
    def cargar_desde_api_ruc(self, data):

        self.identificacion = (
            data.get("numeroRuc")
            or self.identificacion
        )

        self.nombre_completo = (
            data.get("razonSocial")
            or self.nombre_completo
        )

        self.razon_social = (
            data.get("razonSocial")
            or self.razon_social
        )

        self.estado_contribuyente_ruc = (
            data.get("estadoContribuyenteRuc")
            or self.estado_contribuyente_ruc
        )

        self.actividad_economica_principal = (
            data.get("actividadEconomicaPrincipal")
            or self.actividad_economica_principal
        )

        self.tipo_contribuyente = (
            data.get("tipoContribuyente")
            or self.tipo_contribuyente
        )

        self.regimen = (
            data.get("regimen")
            or self.regimen
        )

        self.categoria = (
            data.get("categoria")
            or self.categoria
        )

        self.obligado_llevar_contabilidad = (
            data.get("obligadoLlevarContabilidad")
            or self.obligado_llevar_contabilidad
        )

        self.agente_retencion = (
            data.get("agenteRetencion")
            or self.agente_retencion
        )

        self.contribuyente_especial = (
            data.get("contribuyenteEspecial")
            or self.contribuyente_especial
        )

        self.contribuyente_fantasma = (
            data.get("contribuyenteFantasma")
            or self.contribuyente_fantasma
        )

        self.transacciones_inexistentes = (
            data.get("transaccionesInexistente")
            or self.transacciones_inexistentes
        )

        self.representantes_legales = (
            data.get("representantesLegales")
            or self.representantes_legales
            or []
        )

        self.establecimientos = (
            data.get("establecimientos")
            or self.establecimientos
            or []
        )

        # ======================================
        # DIRECCIÓN MATRIZ
        # ======================================
        matriz = next(
            (
                est
                for est in self.establecimientos
                if est.get("matriz") == "SI"
            ),
            None
        )

        if matriz:

            direccion_matriz = matriz.get(
                "direccionCompleta"
            )

            if direccion_matriz:

                self.direccion = direccion_matriz

        self.datos_api_originales = data

        self.normalizar_datos()

    # ==========================================
    # SAVE
    # ==========================================
    def save(self, *args, **kwargs):

        self.normalizar_datos()

        self.full_clean()

        super().save(*args, **kwargs)

    # ==========================================
    # STRING
    # ==========================================
    def __str__(self):

        return (
            f"{self.identificacion} | "
            f"{self.nombre_completo}"
        )
# ==========================================
# 4. EXPEDIENTE / HISTORIAL ACUMULADO DEL VEHÍCULO
# ==========================================
class ExpedienteVehiculo(models.Model):
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        related_name="expedientes",
        null=True,
        blank=True,
    )

    cliente_respaldo = models.CharField(
        max_length=200,
        null=True,
        blank=True,
    )

    placa = models.CharField(
        max_length=15,
        db_index=True,
        null=True,
        blank=True,
    )

    vehiculo = models.CharField(
        max_length=150,
        null=True,
        blank=True,
    )

    anio_vehiculo = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )
    clave_encendido = models.CharField(
        max_length=50, 
        null=True, 
        blank=True, 
        verbose_name="Clave/PIN de Encendido"
    )
    # ==========================================
    # DATOS API PLACA
    # ==========================================
    marca_api = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    modelo_api = models.CharField(
        max_length=250,
        null=True,
        blank=True,
    )

    descripcion_api = models.CharField(
        max_length=300,
        null=True,
        blank=True,
    )

    tipo_vehiculo_api = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    subtipo_vehiculo_api = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    numero_chasis = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Número de chasis / VIN",
    )

    imagen_url_api = models.URLField(
        max_length=500,
        null=True,
        blank=True,
    )

    datos_api_placa = models.JSONField(
        default=dict,
        blank=True,
    )

    fecha_ultima_consulta_placa = models.DateTimeField(
        null=True,
        blank=True,
    )

    activo = models.BooleanField(default=True)

    observacion = models.TextField(
        null=True,
        blank=True,
    )

    creado_en = models.DateTimeField(
        default=timezone.now,
        editable=False,
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["placa", "vehiculo", "id"]

        verbose_name = "Expediente de vehículo"
        verbose_name_plural = "Expedientes de vehículos"

        indexes = [
            models.Index(fields=["placa"]),
            models.Index(fields=["vehiculo"]),
            models.Index(fields=["cliente_respaldo"]),
            models.Index(fields=["marca_api"]),
            models.Index(fields=["modelo_api"]),
        ]

    @property
    def nombre_cliente_final(self):
        if self.cliente:
            return self.cliente.nombre_completo

        return (
            self.cliente_respaldo
            if self.cliente_respaldo
            else "SIN NOMBRE"
        )

    @property
    def descripcion_vehiculo_final(self):
        return (
            self.vehiculo           
            or self.descripcion_api 
            or "SIN VEHÍCULO"
        )

    def cargar_desde_api_placa(self, data):
        self.marca_api = (
            data.get("CarMake", {})
            .get("CurrentTextValue")
            or self.marca_api
        )

        self.modelo_api = (
            data.get("CarModel", {})
            .get("CurrentTextValue")
            or data.get("ModelDescription", {})
            .get("CurrentTextValue")
            or self.modelo_api
        )

        self.descripcion_api = (
            data.get("Description")
            or self.descripcion_api
        )

        self.vehiculo = (
            data.get("Description")
            or self.vehiculo
        )

        anio = data.get("Year")

        if anio:
            try:
                self.anio_vehiculo = int(anio)
            except Exception:
                pass

        self.tipo_vehiculo_api = (
            data.get("Type")
            or self.tipo_vehiculo_api
        )

        self.subtipo_vehiculo_api = (
            data.get("Subtype")
            or self.subtipo_vehiculo_api
        )

        self.numero_chasis = (
            data.get("VehicleIdentificationNumber")
            or self.numero_chasis
        )

        self.imagen_url_api = (
            data.get("ImageUrl")
            or self.imagen_url_api
        )

        self.datos_api_placa = data or self.datos_api_placa

    def clean(self):
        if self.placa:
            self.placa = (
                self.placa
                .strip()
                .upper()
                .replace("-", "")
                .replace(" ", "")
            )

        if self.vehiculo:
            self.vehiculo = self.vehiculo.strip().upper()
        if self.clave_encendido:
            self.clave_encendido = self.clave_encendido.strip().upper()
        if self.cliente_respaldo:
            self.cliente_respaldo = self.cliente_respaldo.strip().upper()

        if self.observacion:
            self.observacion = self.observacion.strip()

        if self.marca_api:
            self.marca_api = self.marca_api.strip().upper()

        if self.modelo_api:
            self.modelo_api = self.modelo_api.strip().upper()

        if self.descripcion_api:
            self.descripcion_api = self.descripcion_api.strip().upper()

        if self.tipo_vehiculo_api:
            self.tipo_vehiculo_api = self.tipo_vehiculo_api.strip().upper()

        if self.subtipo_vehiculo_api:
            self.subtipo_vehiculo_api = self.subtipo_vehiculo_api.strip().upper()

        if self.numero_chasis:
            self.numero_chasis = (
                self.numero_chasis
                .strip()
                .upper()
                .replace(" ", "")
            )

        if self.anio_vehiculo and self.anio_vehiculo < 1900:
            raise ValidationError("El año del vehículo no es válido.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        placa = self.placa if self.placa else "SIN PLACA"
        vehiculo = self.descripcion_vehiculo_final
        return f"{placa} | {vehiculo} | {self.nombre_cliente_final}"

class ConfiguracionTributaria(models.Model):
    nombre = models.CharField(max_length=100)
    porcentaje_iva = models.DecimalField(max_digits=5, decimal_places=2)
    activa = models.BooleanField(default=True)
    fecha_inicio = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_inicio", "-id"]

    def __str__(self):
        return f"{self.nombre} - {self.porcentaje_iva}%"



class OrdenTrabajo(models.Model):
    ESTADOS = [
        ("ABIERTA", "En Taller / Abierta"),
        ("CERRADA", "Entregado / Pagada"),
        ("ANULADA", "Anulada"),
    ]

    NIVELES_COMBUSTIBLE = [
        ("E", "Vacío"),
        ("1/4", "1/4"),
        ("1/2", "1/2"),
        ("3/4", "3/4"),
        ("F", "Lleno"),
    ]

    numero_orden = models.CharField(max_length=50, unique=True)

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.PROTECT,
        related_name="ordenes",
    )

    expediente = models.ForeignKey(
        ExpedienteVehiculo,
        on_delete=models.SET_NULL,
        related_name="ordenes",
        null=True,
        blank=True,
    )

    es_migrada = models.BooleanField(default=False)
    numero_orden_origen = models.CharField(max_length=50, null=True, blank=True)
    archivo_origen = models.CharField(max_length=255, null=True, blank=True)
    hoja_origen = models.CharField(max_length=50, null=True, blank=True)
    anio_origen_migracion = models.PositiveSmallIntegerField(null=True, blank=True)
    json_origen = models.JSONField(null=True, blank=True)
    requiere_revision_migracion = models.BooleanField(default=False)

    hash_migracion = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
    )

    usuario_receptor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ordenes_recibidas",
        null=True,
        blank=True,
    )

    tecnicos = models.ManyToManyField(
        Tecnico,
        blank=True,
        related_name="ordenes_asignadas",
        verbose_name="Técnicos encargados",
    )

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        related_name="ordenes",
        null=True,
        blank=True,
    )

    cliente_respaldo = models.CharField(max_length=200, null=True, blank=True)

    color = models.CharField(max_length=50, null=True, blank=True)
    color_hex = models.CharField(max_length=7, default="#1d1d1f")

    placa = models.CharField(max_length=15, db_index=True, null=True, blank=True)
    vehiculo = models.CharField(max_length=150, null=True, blank=True)
    anio_vehiculo = models.PositiveSmallIntegerField(null=True, blank=True)

    clave_encendido = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Clave/PIN de Encendido",
    )

    fecha_origen = models.DateField(null=True, blank=True)
    kilometraje = models.PositiveIntegerField(null=True, blank=True)
    proximo_mantenimiento_km = models.PositiveIntegerField(null=True, blank=True)

    observaciones_recepcion = models.TextField(null=True, blank=True)
    sintomas_cliente = models.TextField(null=True, blank=True)
    observaciones_tecnicas = models.TextField(null=True, blank=True)

    tipo_tarifa_vehiculo = models.CharField(
        max_length=20,
        choices=TIPOS_TARIFA_VEHICULO,
        default="NO_APLICA",
    )

    gama_vehiculo = models.CharField(
        max_length=20,
        default="NO_APLICA",
    )

    estado = models.CharField(max_length=15, choices=ESTADOS, default="ABIERTA")
    fecha_ingreso = models.DateTimeField(default=timezone.now)
    estado = models.CharField(max_length=15, choices=ESTADOS, default="ABIERTA")
    fecha_ingreso = models.DateTimeField(default=timezone.now)

    actualizado_en = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)
 
    total_general = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    configuracion_iva = models.ForeignKey(
        ConfiguracionTributaria,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ordenes_trabajo",
    )

    porcentaje_iva = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )

    subtotal_sin_iva = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    descuento_porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    valor_descuento = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    valor_iva = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    total_final = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    nivel_combustible = models.CharField(
        max_length=10,
        choices=NIVELES_COMBUSTIBLE,
        null=True,
        blank=True,
    )

    checklist_confirmado_cliente = models.BooleanField(default=False)

    firma_cliente = models.ImageField(
        upload_to="ordenes/firmas/%Y/%m/",
        null=True,
        blank=True,
    )

    fecha_firma = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_ingreso"]
        verbose_name = "Orden de Trabajo"
        verbose_name_plural = "Órdenes de Trabajo"
        indexes = [
            models.Index(fields=["sucursal", "estado"]),
            models.Index(fields=["placa", "fecha_ingreso"]),
            models.Index(fields=["estado", "fecha_ingreso"]),
            models.Index(fields=["es_migrada", "anio_origen_migracion"]),
            models.Index(fields=["numero_orden_origen"]),
            models.Index(fields=["fecha_origen"]),
        ]

    @property
    def nombre_cliente_final(self):
        if self.cliente:
            return self.cliente.nombre_completo
        return self.cliente_respaldo if self.cliente_respaldo else "SIN NOMBRE"

    @property
    def badge_origen(self):
        return "MIGRADA" if self.es_migrada else "NORMAL"


    def esta_bloqueada(self):
        return self.estado in ["CERRADA", "ANULADA"]


    def puede_editarse(self):
        return self.estado == "ABIERTA"


    def puede_cerrarse(self):
        if self.estado != "ABIERTA":
            return False, "Solo se pueden cerrar órdenes abiertas."

        if not self.tecnicos.exists():
            return False, "Debe asignar al menos un técnico antes de cerrar la orden."

        return True, None


    def _estado_anterior(self):
        if not self.pk:
            return None

        return (
            OrdenTrabajo.objects
            .filter(pk=self.pk)
            .values_list("estado", flat=True)
            .first()
        )

    def _campos_modificados(self):
        if not self.pk:
            return []

        anterior = OrdenTrabajo.objects.filter(pk=self.pk).first()

        if not anterior:
            return []

        ignorar = {
            "id",
            "total_general",
            "subtotal_sin_iva",
            "valor_descuento",
            "valor_iva",
            "total_final",
            "configuracion_iva",
            "porcentaje_iva",
            "actualizado_en",
            "version",
        }

        modificados = []

        for field in self._meta.concrete_fields:
            nombre = field.name

            if nombre in ignorar:
                continue

            valor_anterior = getattr(anterior, nombre)
            valor_actual = getattr(self, nombre)

            if valor_anterior != valor_actual:
                modificados.append(nombre)

        return modificados

    def validar_bloqueo_edicion(self):
        estado_anterior = self._estado_anterior()

        if not estado_anterior:
            return

        if estado_anterior not in ["CERRADA", "ANULADA"]:
            return

        campos_modificados = self._campos_modificados()

        if not campos_modificados:
            return

        # Única excepción: reabrir la orden.
        if campos_modificados == ["estado"] and self.estado == "ABIERTA":
            return

        raise ValidationError(
            "No se puede modificar una orden cerrada o anulada. "
            "Primero debe reabrirse."
        )

    def obtener_configuracion_iva_activa(self):
        return ConfiguracionTributaria.objects.filter(
            activa=True
        ).order_by("-fecha_inicio", "-id").first()

    def _normalizar_campos_texto(self):
        if self.numero_orden:
            self.numero_orden = self.numero_orden.strip().upper()

        if self.numero_orden_origen:
            self.numero_orden_origen = self.numero_orden_origen.strip().upper()

        if self.placa:
            self.placa = self.placa.strip().upper()

        if self.vehiculo:
            self.vehiculo = self.vehiculo.strip()

        if self.color:
            self.color = self.color.strip()

        if self.clave_encendido:
            self.clave_encendido = self.clave_encendido.strip().upper()

        if self.cliente_respaldo:
            self.cliente_respaldo = self.cliente_respaldo.strip()

        if self.observaciones_recepcion:
            self.observaciones_recepcion = self.observaciones_recepcion.strip()

        if self.sintomas_cliente:
            self.sintomas_cliente = self.sintomas_cliente.strip()

        if self.observaciones_tecnicas:
            self.observaciones_tecnicas = self.observaciones_tecnicas.strip()

        if self.archivo_origen:
            self.archivo_origen = self.archivo_origen.strip()

        if self.hoja_origen:
            self.hoja_origen = self.hoja_origen.strip()

    def _calcular_color_hex(self):
        if self.color_hex and self.color_hex != "#1d1d1f":
            return

        self.color_hex = "#1d1d1f"

        if not self.color:
            return

        color_lower = self.color.lower()

        mapa_colores = {
            "blanco": "#F5F5F7",
            "negro": "#212121",
            "plata": "#BDBDBD",
            "plateado": "#BDBDBD",
            "gris": "#757575",
            "plomo": "#424242",
            "rojo": "#D32F2F",
            "vino": "#880E4F",
            "tinto": "#880E4F",
            "azul": "#1976D2",
            "celeste": "#03A9F4",
            "verde": "#388E3C",
            "amarillo": "#FBC02D",
            "dorado": "#CBA135",
            "oro": "#CBA135",
            "naranja": "#F57C00",
            "cafe": "#5D4037",
            "marrón": "#5D4037",
            "marron": "#5D4037",
            "beige": "#D7CCC8",
            "crema": "#FFF9C4",
        }

        for clave, hex_code in mapa_colores.items():
            if clave in color_lower:
                self.color_hex = hex_code
                break

    def calcular_total(self):
        servicios = self.servicios_detalles.aggregate(total=Sum("subtotal"))["total"] or Decimal("0.00")
        insumos = self.insumos_detalles.aggregate(total=Sum("subtotal"))["total"] or Decimal("0.00")
        servicios_historicos = self.servicios_historicos.aggregate(total=Sum("subtotal"))["total"] or Decimal("0.00")
        insumos_historicos = self.insumos_historicos.aggregate(total=Sum("subtotal"))["total"] or Decimal("0.00")

        subtotal_sin_iva = (
            servicios +
            insumos +
            servicios_historicos +
            insumos_historicos
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if self.porcentaje_iva is None:
            config = self.obtener_configuracion_iva_activa()

            if config:
                self.configuracion_iva = config
                self.porcentaje_iva = config.porcentaje_iva
            else:
                self.porcentaje_iva = Decimal("0.00")

        descuento_porcentaje = self.descuento_porcentaje or Decimal("0.00")

        valor_descuento = (
            subtotal_sin_iva *
            Decimal(str(descuento_porcentaje)) /
            Decimal("100")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        base_imponible = subtotal_sin_iva - valor_descuento

        if base_imponible < Decimal("0.00"):
            base_imponible = Decimal("0.00")

        valor_iva = (
            base_imponible *
            Decimal(str(self.porcentaje_iva)) /
            Decimal("100")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        total_final = (
            base_imponible + valor_iva
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        self.total_general = subtotal_sin_iva
        self.subtotal_sin_iva = subtotal_sin_iva
        self.valor_descuento = valor_descuento
        self.valor_iva = valor_iva
        self.total_final = total_final

        if self.pk:
            OrdenTrabajo.objects.filter(pk=self.pk).update(
                total_general=subtotal_sin_iva,
                configuracion_iva=self.configuracion_iva,
                porcentaje_iva=self.porcentaje_iva,
                subtotal_sin_iva=subtotal_sin_iva,
                descuento_porcentaje=descuento_porcentaje,
                valor_descuento=valor_descuento,
                valor_iva=valor_iva,
                total_final=total_final,
            )

    def clean(self):
        self._normalizar_campos_texto()
        self.validar_bloqueo_edicion()

        if not self.numero_orden or not self.numero_orden.strip():
            raise ValidationError("El número de orden es obligatorio.")

        if not self.sucursal_id:
            raise ValidationError({"sucursal": "La sucursal es obligatoria."})

        if not self.es_migrada:
            if not self.placa or not self.placa.strip():
                raise ValidationError("La placa es obligatoria para órdenes no migradas.")

        if self.anio_vehiculo and self.anio_vehiculo < 1900:
            raise ValidationError("El año del vehículo no es válido.")

        if self.es_migrada and not self.numero_orden_origen:
            raise ValidationError({
                "numero_orden_origen": "Las OT migradas deben guardar el número original extraído."
            })

        if self.descuento_porcentaje < Decimal("0.00"):
            raise ValidationError({
                "descuento_porcentaje": "El descuento no puede ser negativo."
            })

        if self.descuento_porcentaje > Decimal("100.00"):
            raise ValidationError({
                "descuento_porcentaje": "El descuento no puede ser mayor al 100%."
            })

    def save(self, *args, **kwargs):
        self._normalizar_campos_texto()
        self._calcular_color_hex()

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        placa = self.placa if self.placa else "SIN PLACA"

        if self.es_migrada and self.numero_orden_origen:
            return (
                f"[{self.sucursal.codigo}] OT {self.numero_orden} | "
                f"ORIGEN {self.numero_orden_origen} - {placa} "
                f"({self.nombre_cliente_final})"
            )

        return f"[{self.sucursal.codigo}] OT {self.numero_orden} - {placa} ({self.nombre_cliente_final})"
# ==========================================
# 6. RECEPCIÓN
# ==========================================
class TrabajoRecepcionCatalogo(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    activo = models.BooleanField(default=True)
    orden_visual = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["orden_visual", "nombre"]
        verbose_name = "Trabajo sugerido de recepción"
        verbose_name_plural = "Trabajos sugeridos de recepción"

    def clean(self):
        if not self.nombre or not self.nombre.strip():
            raise ValidationError("El nombre del trabajo sugerido es obligatorio.")

    def save(self, *args, **kwargs):
        if self.nombre:
            self.nombre = self.nombre.strip()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre

class OrdenTrabajoSolicitado(models.Model):
    orden = models.ForeignKey(
        OrdenTrabajo,
        related_name="trabajos_solicitados_items",
        on_delete=models.CASCADE,
    )

    trabajo_catalogo = models.ForeignKey(
        TrabajoRecepcionCatalogo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    descripcion_manual = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    orden_item = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["orden_item", "id"]
        verbose_name = "Trabajo solicitado"
        verbose_name_plural = "Trabajos solicitados"

    def validar_orden_editable(self):
        if self.orden and self.orden.estado in ["CERRADA", "ANULADA"]:
            raise ValidationError(
                "No se pueden modificar trabajos solicitados de una orden cerrada o anulada. Primero debe reabrirse."
            )

    def clean(self):
        self.validar_orden_editable()

        descripcion = (self.descripcion_manual or "").strip()

        if not self.trabajo_catalogo and not descripcion:
            raise ValidationError(
                "Debe seleccionar un trabajo del catálogo o ingresar una descripción manual."
            )

    def save(self, *args, **kwargs):
        self.validar_orden_editable()

        if self.descripcion_manual:
            self.descripcion_manual = self.descripcion_manual.strip()

        self.full_clean()

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.validar_orden_editable()

        super().delete(*args, **kwargs)

    def __str__(self):
        return (
            self.trabajo_catalogo.nombre
            if self.trabajo_catalogo
            else (self.descripcion_manual or "Trabajo")
        )
class OrdenSintoma(models.Model):
    orden = models.ForeignKey(
        OrdenTrabajo,
        related_name="sintomas_items",
        on_delete=models.CASCADE,
    )

    descripcion = models.CharField(max_length=255)

    orden_item = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["orden_item", "id"]
        verbose_name = "Síntoma de cliente"
        verbose_name_plural = "Síntomas de cliente"

    def validar_orden_editable(self):
        if self.orden and self.orden.estado in ["CERRADA", "ANULADA"]:
            raise ValidationError(
                "No se pueden modificar los síntomas de una orden cerrada o anulada. Primero debe reabrirse."
            )

    def clean(self):
        self.validar_orden_editable()

        if not self.descripcion or not self.descripcion.strip():
            raise ValidationError(
                "La descripción del síntoma es obligatoria."
            )

    def save(self, *args, **kwargs):
        self.validar_orden_editable()

        if self.descripcion:
            self.descripcion = self.descripcion.strip()

        self.full_clean()

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.validar_orden_editable()

        super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.orden_item}. {self.descripcion}"

# ==========================================
# 7. CHECKLIST Y RECEPCIÓN
# ==========================================
class OrdenChecklistRecepcion(models.Model):
    orden = models.OneToOneField(
        OrdenTrabajo,
        related_name="checklist_recepcion",
        on_delete=models.CASCADE,
    )

    matricula = models.BooleanField(default=False)
    plumas = models.BooleanField(default=False)
    radio = models.BooleanField(default=False)
    pantalla = models.BooleanField(default=False)
    tuerca_seguridad = models.BooleanField(default=False)
    encendedor_cig = models.BooleanField(default=False)
    triangulos = models.BooleanField(default=False)
    gata = models.BooleanField(default=False)
    herramientas = models.BooleanField(default=False)
    llanta_emergencia = models.BooleanField(default=False)
    faros_lunas = models.BooleanField(default=False)
    tapacubos = models.BooleanField(default=False)
    antena = models.BooleanField(default=False)
    adicionales_reportados = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Checklist de recepción"
        verbose_name_plural = "Checklists de recepción"

    def validar_orden_editable(self):
        if self.orden and self.orden.estado in ["CERRADA", "ANULADA"]:
            raise ValidationError(
                "No se puede modificar el checklist de una orden cerrada o anulada. Primero debe reabrirse."
            )

    def clean(self):
        self.validar_orden_editable()

    def save(self, *args, **kwargs):
        self.validar_orden_editable()

        if self.adicionales_reportados:
            self.adicionales_reportados = self.adicionales_reportados.strip()

        self.full_clean()

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.validar_orden_editable()

        super().delete(*args, **kwargs)

    def __str__(self):
        return f"Checklist OT {self.orden.numero_orden}"
class OrdenObjetoAdicional(models.Model):
    orden = models.ForeignKey(
        OrdenTrabajo,
        related_name="objetos_adicionales",
        on_delete=models.CASCADE,
    )

    descripcion = models.CharField(max_length=255)
    cantidad = models.PositiveIntegerField(default=1)
    observacion = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Objeto adicional"
        verbose_name_plural = "Objetos adicionales"

    def validar_orden_editable(self):
        if self.orden and self.orden.estado in ["CERRADA", "ANULADA"]:
            raise ValidationError(
                "No se pueden modificar objetos adicionales de una orden cerrada o anulada. Primero debe reabrirse."
            )

    def clean(self):
        self.validar_orden_editable()

        if not self.descripcion or not self.descripcion.strip():
            raise ValidationError(
                "La descripción del objeto adicional es obligatoria."
            )

        if self.cantidad <= 0:
            raise ValidationError(
                "La cantidad debe ser mayor que 0."
            )

    def save(self, *args, **kwargs):
        self.validar_orden_editable()

        if self.descripcion:
            self.descripcion = self.descripcion.strip()

        if self.observacion:
            self.observacion = self.observacion.strip()

        self.full_clean()

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.validar_orden_editable()

        super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.descripcion} - OT {self.orden.numero_orden}"

class FotoRecepcionVehiculo(models.Model):
    orden = models.ForeignKey(
        OrdenTrabajo,
        related_name="fotos_recepcion",
        on_delete=models.CASCADE,
    )

    imagen = models.ImageField(upload_to="ordenes/recepcion/")

    tipo_foto = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )

    descripcion = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    fecha_subida = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_subida"]
        verbose_name = "Foto de recepción"
        verbose_name_plural = "Fotos de recepción"

    def validar_orden_editable(self):
        if self.orden and self.orden.estado in ["CERRADA", "ANULADA"]:
            raise ValidationError(
                "No se pueden modificar fotografías de una orden cerrada o anulada. Primero debe reabrirse."
            )

    def clean(self):
        self.validar_orden_editable()

    def save(self, *args, **kwargs):
        self.validar_orden_editable()

        if self.tipo_foto:
            self.tipo_foto = self.tipo_foto.strip()

        if self.descripcion:
            self.descripcion = self.descripcion.strip()

        self.full_clean()

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.validar_orden_editable()

        super().delete(*args, **kwargs)

    def __str__(self):
        return f"Foto OT {self.orden.numero_orden}"

class OrdenCroquisDanio(models.Model):
    orden = models.OneToOneField(
        OrdenTrabajo,
        related_name="croquis_danio",
        on_delete=models.CASCADE,
    )

    trazos = models.JSONField(
        default=list,
        blank=True,
    )

    imagen_generada = models.ImageField(
        upload_to="ordenes/croquis/",
        null=True,
        blank=True,
    )

    observacion = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Croquis de daño"
        verbose_name_plural = "Croquis de daños"

    def validar_orden_editable(self):
        if self.orden and self.orden.estado in ["CERRADA", "ANULADA"]:
            raise ValidationError(
                "No se puede modificar el croquis de una orden cerrada o anulada. Primero debe reabrirse."
            )

    def clean(self):
        self.validar_orden_editable()

    def save(self, *args, **kwargs):
        self.validar_orden_editable()

        if self.observacion:
            self.observacion = self.observacion.strip()

        self.full_clean()

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.validar_orden_editable()

        super().delete(*args, **kwargs)

    def __str__(self):
        return f"Croquis OT {self.orden.numero_orden}"
class OrdenServicioDetalle(models.Model):
    VARIANTES_PRECIO = [
        ("NORMAL", "Normal"),
        ("REPINTADO", "Repintado"),
        ("NUEVO", "Nuevo"),
        ("TRICAPA", "Tricapa / Candys"),
        ("ESPECIAL", "Color especial"),
    ]

    TIPOS_SERVICIO = [
        ("MEC", "Mano de Obra Interna"),
        ("EXT", "Mano de Obra Externa"),
    ]

    orden = models.ForeignKey(
        OrdenTrabajo,
        related_name="servicios_detalles",
        on_delete=models.CASCADE,
    )

    servicio = models.ForeignKey(
        "servicios.ServicioCatalogo",
        on_delete=models.SET_NULL,
        related_name="ordenes_detalle",
        null=True,
        blank=True,
    )

    tipo_servicio = models.CharField(
        max_length=10,
        choices=TIPOS_SERVICIO,
        default="MEC",
    )

    tecnico_responsable = models.ForeignKey(
        Tecnico,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    cantidad = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("1.00"),
    )

    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        editable=False,
    )

    orden_item = models.PositiveIntegerField(default=1)

    tipo_tarifa_aplicada = models.CharField(
        max_length=20,
        default="NO_APLICA",
    )

    variante_precio_aplicada = models.CharField(
        max_length=20,
        choices=VARIANTES_PRECIO,
        default="NORMAL",
    )

    descripcion_servicio = models.CharField(
        max_length=255,
        blank=False,
    )

    creado_en = models.DateTimeField(
        default=timezone.now,
        editable=False,
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["orden_item", "id"]
        verbose_name = "Detalle de servicio"
        verbose_name_plural = "Detalles de servicios"

    def validar_orden_editable(self):
        if self.orden and self.orden.estado in ["CERRADA", "ANULADA"]:
            raise ValidationError(
                "No se pueden modificar servicios de una orden cerrada o anulada. Primero debe reabrirse."
            )

    def clean(self):
        self.validar_orden_editable()

        if self.cantidad is None or self.cantidad <= 0:
            raise ValidationError(
                "La cantidad del servicio debe ser mayor que 0."
            )

        if self.precio_unitario is None or self.precio_unitario < 0:
            raise ValidationError(
                "El precio unitario del servicio no puede ser negativo."
            )

        if not self.descripcion_servicio and not self.servicio:
            raise ValidationError(
                "Debe proporcionar una descripción o seleccionar un servicio del catálogo."
            )

    def save(self, *args, **kwargs):
        self.validar_orden_editable()

        if not self.tipo_tarifa_aplicada:
            self.tipo_tarifa_aplicada = (
                self.orden.tipo_tarifa_vehiculo or "NO_APLICA"
            )

        if not self.variante_precio_aplicada:
            self.variante_precio_aplicada = "NORMAL"

        if self.servicio and not self.descripcion_servicio:
            self.descripcion_servicio = self.servicio.descripcion

        self.subtotal = (
            Decimal(str(self.cantidad)) * Decimal(str(self.precio_unitario))
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        self.full_clean()

        with transaction.atomic():
            super().save(*args, **kwargs)
            self.orden.calcular_total()

    def delete(self, *args, **kwargs):
        self.validar_orden_editable()

        orden = self.orden

        with transaction.atomic():
            super().delete(*args, **kwargs)
            orden.calcular_total()

    def __str__(self):
        return (
            f"[{self.tipo_servicio}] "
            f"{self.descripcion_servicio} - OT {self.orden.numero_orden}"
        )
class OrdenInsumoDetalle(models.Model):
    orden = models.ForeignKey(
        "OrdenTrabajo",
        related_name="insumos_detalles",
        on_delete=models.CASCADE,
    )

    producto = models.ForeignKey(
        "inventario.CodigoProducto",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    descripcion_factura = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Descripción para el Cliente",
    )

    cantidad = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("1.00"),
    )

    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        editable=False,
    )

    orden_item = models.PositiveIntegerField(default=1)

    categoria_referencia = models.ForeignKey(
        "inventario.Categoria",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    codigo_empaque_referencia = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Código de empaque referencial",
    )

    codigo_barras_referencia = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    creado_en = models.DateTimeField(
        default=timezone.now,
        editable=False,
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["orden_item", "id"]
        verbose_name = "Detalle de insumo"
        verbose_name_plural = "Detalles de insumos"

    def validar_orden_editable(self):
        if self.orden and self.orden.estado in ["CERRADA", "ANULADA"]:
            raise ValidationError(
                "No se pueden modificar repuestos de una orden cerrada o anulada. Primero debe reabrirse."
            )

    def clean(self):
        self.validar_orden_editable()

        if self.cantidad is None or self.cantidad <= 0:
            raise ValidationError("La cantidad del insumo debe ser mayor que 0.")

        if self.precio_unitario is None or self.precio_unitario < 0:
            raise ValidationError("El precio unitario del insumo no puede ser negativo.")

        if not self.producto and not (self.descripcion_factura or "").strip():
            raise ValidationError(
                "Debe seleccionar un repuesto del inventario o escribir una descripción manual."
            )

    def _registrar_movimiento_stock(self, codigo_producto, cantidad, tipo, referencia):
        from inventario.models import MovimientoStock

        MovimientoStock.objects.create(
            codigo_producto=codigo_producto,
            sucursal=self.orden.sucursal,
            tipo_movimiento=tipo,
            cantidad=cantidad,
            referencia=referencia,
        )

    def save(self, *args, **kwargs):
        self.validar_orden_editable()

        if not self.descripcion_factura and self.producto:
            self.descripcion_factura = str(self.producto)

        self.subtotal = (
            Decimal(str(self.cantidad)) * self.precio_unitario
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        self.full_clean()

        placa_ref = self.orden.placa if self.orden.placa else "SIN PLACA"
        referencia = f"OT: {self.orden.numero_orden} | Placa: {placa_ref}"
        es_edicion = self.pk is not None

        with transaction.atomic():
            cambio_stock = False
            producto_anterior = None
            cantidad_anterior = Decimal("0.00")

            if es_edicion:
                anterior = (
                    OrdenInsumoDetalle.objects
                    .select_for_update()
                    .get(pk=self.pk)
                )

                producto_anterior = anterior.producto
                cantidad_anterior = anterior.cantidad

                producto_anterior_id = producto_anterior.id if producto_anterior else None
                producto_actual_id = self.producto.id if self.producto else None

                cambio_stock = (
                    producto_anterior_id != producto_actual_id
                    or cantidad_anterior != self.cantidad
                )

                if cambio_stock and producto_anterior:
                    self._registrar_movimiento_stock(
                        codigo_producto=producto_anterior,
                        cantidad=cantidad_anterior,
                        tipo="entrada",
                        referencia=f"REVERSA {referencia}",
                    )

            super().save(*args, **kwargs)

            if self.producto:
                if not es_edicion or cambio_stock:
                    self._registrar_movimiento_stock(
                        codigo_producto=self.producto,
                        cantidad=self.cantidad,
                        tipo="salida",
                        referencia=referencia,
                    )

            self.orden.calcular_total()

    def delete(self, *args, **kwargs):
        self.validar_orden_editable()

        placa_ref = self.orden.placa if self.orden.placa else "SIN PLACA"
        referencia = f"REVERSA OT: {self.orden.numero_orden} | Placa: {placa_ref}"

        orden = self.orden
        producto = self.producto
        cantidad = self.cantidad

        with transaction.atomic():
            if producto:
                self._registrar_movimiento_stock(
                    codigo_producto=producto,
                    cantidad=cantidad,
                    tipo="entrada",
                    referencia=referencia,
                )

            super().delete(*args, **kwargs)
            orden.calcular_total()

    def __str__(self):
        return f"{self.descripcion_factura} (x{self.cantidad}) - OT {self.orden.numero_orden}"

class OrdenServicioProcedimientoDetalle(models.Model):

    detalle_servicio = models.ForeignKey(
        OrdenServicioDetalle,
        on_delete=models.CASCADE,
        related_name="procedimientos_detalle",
    )

    descripcion = models.CharField(
        max_length=300
    )

    orden_item = models.PositiveIntegerField(
        default=1
    )

    creado_en = models.DateTimeField(
        auto_now_add=True
    )

    actualizado_en = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["orden_item", "id"]
        verbose_name = "Procedimiento aplicado en OT"
        verbose_name_plural = "Procedimientos aplicados en OT"

    def validar_orden_editable(self):
        if (
            self.detalle_servicio
            and self.detalle_servicio.orden.estado in ["CERRADA", "ANULADA"]
        ):
            raise ValidationError(
                "No se pueden modificar procedimientos de una orden cerrada o anulada. Primero debe reabrirse."
            )

    def clean(self):
        self.validar_orden_editable()

        if not self.descripcion or not self.descripcion.strip():
            raise ValidationError(
                "La descripción del procedimiento es obligatoria."
            )

    def save(self, *args, **kwargs):
        self.validar_orden_editable()

        if self.descripcion:
            self.descripcion = self.descripcion.strip().upper()

        self.full_clean()

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.validar_orden_editable()

        super().delete(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.detalle_servicio.descripcion_servicio} "
            f"- {self.descripcion}"
        )
# ==========================================
# 9. DETALLES HISTÓRICOS MIGRADOS
# ==========================================
class OrdenServicioHistorico(models.Model):
    TIPOS = [
        ("MO", "Mano de obra"),
        ("MOE", "Mano de obra externa"),
    ]

    orden = models.ForeignKey(
        OrdenTrabajo,
        related_name="servicios_historicos",
        on_delete=models.CASCADE,
    )

    tipo = models.CharField(max_length=3, choices=TIPOS)
    descripcion_original = models.TextField()
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    es_cortesia = models.BooleanField(default=False)
    orden_item = models.PositiveIntegerField(default=1)

    procedimientos = models.JSONField(
        default=list,
        blank=True,
    )

    class Meta:
        ordering = ["tipo", "orden_item", "id"]
        verbose_name = "Servicio histórico migrado"
        verbose_name_plural = "Servicios históricos migrados"

    def validar_orden_editable(self):
        if self.orden and self.orden.estado in ["CERRADA", "ANULADA"]:
            raise ValidationError(
                "No se pueden modificar servicios históricos de una orden cerrada o anulada. Primero debe reabrirse."
            )

    def clean(self):
        self.validar_orden_editable()

        if not self.descripcion_original or not self.descripcion_original.strip():
            raise ValidationError("La descripción histórica es obligatoria.")

        if self.cantidad is not None and self.cantidad <= 0:
            raise ValidationError("La cantidad histórica debe ser mayor que 0.")

        if self.precio_unitario is not None and self.precio_unitario < 0:
            raise ValidationError("El precio unitario histórico no puede ser negativo.")

        if self.subtotal is not None and self.subtotal < 0:
            raise ValidationError("El subtotal histórico no puede ser negativo.")

    def save(self, *args, **kwargs):
        self.validar_orden_editable()

        if self.descripcion_original:
            self.descripcion_original = self.descripcion_original.strip()

        self.full_clean()

        with transaction.atomic():
            super().save(*args, **kwargs)
            self.orden.calcular_total()

    def delete(self, *args, **kwargs):
        self.validar_orden_editable()

        orden = self.orden

        with transaction.atomic():
            super().delete(*args, **kwargs)
            orden.calcular_total()

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.descripcion_original}"
class OrdenInsumoHistorico(models.Model):
    orden = models.ForeignKey(
        OrdenTrabajo,
        related_name="insumos_historicos",
        on_delete=models.CASCADE,
    )

    descripcion_original = models.TextField()

    codigo_original = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    cantidad = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    precio_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    orden_item = models.PositiveIntegerField(default=1)

    requiere_revision = models.BooleanField(default=False)

    class Meta:
        ordering = ["orden_item", "id"]
        verbose_name = "Insumo histórico migrado"
        verbose_name_plural = "Insumos históricos migrados"

    def validar_orden_editable(self):
        if self.orden and self.orden.estado in ["CERRADA", "ANULADA"]:
            raise ValidationError(
                "No se pueden modificar insumos históricos de una orden cerrada o anulada. Primero debe reabrirse."
            )

    def clean(self):

        self.validar_orden_editable()

        if not self.descripcion_original or not self.descripcion_original.strip():
            raise ValidationError(
                "La descripción histórica del insumo es obligatoria."
            )

        if self.cantidad is not None and self.cantidad <= 0:
            raise ValidationError(
                "La cantidad histórica debe ser mayor que 0."
            )

        if self.precio_unitario is not None and self.precio_unitario < 0:
            raise ValidationError(
                "El precio unitario histórico no puede ser negativo."
            )

        if self.subtotal is not None and self.subtotal < 0:
            raise ValidationError(
                "El subtotal histórico no puede ser negativo."
            )

    def save(self, *args, **kwargs):

        self.validar_orden_editable()

        if self.descripcion_original:
            self.descripcion_original = self.descripcion_original.strip()

        if self.codigo_original:
            self.codigo_original = self.codigo_original.strip().upper()

        self.full_clean()

        with transaction.atomic():
            super().save(*args, **kwargs)
            self.orden.calcular_total()

    def delete(self, *args, **kwargs):

        self.validar_orden_editable()

        orden = self.orden

        with transaction.atomic():
            super().delete(*args, **kwargs)
            orden.calcular_total()

    def __str__(self):
        return self.descripcion_original

# ==========================================
# 10. COTIZACIONES / PROFORMAS (MÓDULO HÍBRIDO)
# ==========================================
class Cotizacion(models.Model):
    ESTADOS_COTIZACION = [
        ("PENDIENTE", "Pendiente / Entregada"),
        ("APROBADA", "Aprobada (Trasladada a OT)"),
        ("RECHAZADA", "Rechazada / Caducada"),
    ]

    numero_cotizacion = models.CharField(max_length=50, unique=True)
    sucursal = models.ForeignKey(Sucursal, on_delete=models.PROTECT, related_name="cotizaciones")
    
    orden = models.OneToOneField( # Cambiado de ForeignKey a OneToOneField
        'OrdenTrabajo', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name="cotizacion_vinculada", # Cambiado a singular
    
    )
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True, related_name="cotizaciones")
    cliente_respaldo = models.CharField(max_length=200, null=True, blank=True)
    placa = models.CharField(max_length=15, db_index=True) # <-- ESTE FUE EL CAMBIO QUE DETECTÓ DJANGO
    vehiculo = models.CharField(max_length=150, null=True, blank=True)
    anio_vehiculo = models.PositiveSmallIntegerField(null=True, blank=True)

    # Control de la Cotización
    estado = models.CharField(max_length=15, choices=ESTADOS_COTIZACION, default="PENDIENTE")
    fecha_creacion = models.DateTimeField(default=timezone.now)
    validez_dias = models.PositiveIntegerField(default=15)
    
    total_general = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    observaciones = models.TextField(null=True, blank=True)

    # Si la cotización era de mostrador y se aprueba, aquí se guarda la OT que nació de ella.
    orden_generada = models.OneToOneField(
        'OrdenTrabajo', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="cotizacion_origen",
       
    )

    class Meta:
        ordering = ["-fecha_creacion"]
        verbose_name = "Cotización"
        verbose_name_plural = "Cotizaciones"

    @property
    def nombre_cliente_final(self):
        if self.cliente:
            return self.cliente.nombre_completo
        return self.cliente_respaldo if self.cliente_respaldo else "SIN NOMBRE"

    def calcular_total(self):
        servicios = self.servicios_cotizados.aggregate(total=Sum("subtotal"))["total"] or Decimal("0.00")
        insumos = self.insumos_cotizados.aggregate(total=Sum("subtotal"))["total"] or Decimal("0.00")
        nuevo_total = servicios + insumos

        if self.total_general != nuevo_total:
            self.total_general = nuevo_total
            if self.pk:
                Cotizacion.objects.filter(pk=self.pk).update(total_general=nuevo_total)

    def save(self, *args, **kwargs):
       
        if self.orden:
            self.placa = self.orden.placa
            self.vehiculo = self.orden.vehiculo
            self.cliente = self.orden.cliente
            self.cliente_respaldo = self.orden.cliente_respaldo
            self.anio_vehiculo = self.orden.anio_vehiculo
        
        if self.placa:
            self.placa = self.placa.strip().upper()
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"COT {self.numero_cotizacion} - {self.placa} ({self.nombre_cliente_final})"


class CotizacionServicioDetalle(models.Model):
    cotizacion = models.ForeignKey(Cotizacion, related_name="servicios_cotizados", on_delete=models.CASCADE)
    servicio = models.ForeignKey("servicios.ServicioCatalogo", on_delete=models.SET_NULL, null=True, blank=True)
    
    tipo_servicio = models.CharField(max_length=10, choices=OrdenServicioDetalle.TIPOS_SERVICIO, default="MEC")
    descripcion_servicio = models.CharField(max_length=255)
    
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    orden_item = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["orden_item", "id"]

    def save(self, *args, **kwargs):
        self.subtotal = (Decimal(str(self.cantidad)) * self.precio_unitario).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        super().save(*args, **kwargs)
        self.cotizacion.calcular_total()

    def delete(self, *args, **kwargs):
        cotizacion = self.cotizacion
        super().delete(*args, **kwargs)
        cotizacion.calcular_total()

class CotizacionInsumoDetalle(models.Model):
    cotizacion = models.ForeignKey(Cotizacion, related_name="insumos_cotizados", on_delete=models.CASCADE)
    producto = models.ForeignKey("inventario.CodigoProducto", on_delete=models.PROTECT, null=True, blank=True)
    
    descripcion_factura = models.CharField(max_length=255, blank=True)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    orden_item = models.PositiveIntegerField(default=1)


    categoria_referencia = models.ForeignKey(
        "inventario.Categoria",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    codigo_empaque_referencia = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )
    codigo_barras_referencia = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["orden_item", "id"]

    # Nota: Aquí NO hay def _registrar_movimiento_stock() porque es solo una proforma tentativa.
    def save(self, *args, **kwargs):
        if not self.descripcion_factura and self.producto:
            self.descripcion_factura = str(self.producto)
            
        self.subtotal = (Decimal(str(self.cantidad)) * self.precio_unitario).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        super().save(*args, **kwargs)
        self.cotizacion.calcular_total()

    def delete(self, *args, **kwargs):
        cotizacion = self.cotizacion
        super().delete(*args, **kwargs)
        cotizacion.calcular_total()


class CotizacionProcedimientoDetalle(models.Model):
    servicio_cotizado = models.ForeignKey(
        CotizacionServicioDetalle, 
        related_name='procedimientos_detalle', 
        on_delete=models.CASCADE
    )
    descripcion = models.CharField(max_length=255)
    
  
    orden_item = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["orden_item", "id"]

    def __str__(self):
        return f"{self.servicio_cotizado.descripcion_servicio} - {self.descripcion}"
    
class PlantillaRecomendacion(models.Model):
    titulo = models.CharField(max_length=150, db_index=True)
    texto = models.TextField()
    servicios = models.ManyToManyField(
        "servicios.ServicioCatalogo",
        blank=True,
        related_name="recomendaciones_sugeridas",
    )
    activo = models.BooleanField(default=True, db_index=True)
    orden_visual = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["orden_visual", "titulo"]

    def save(self, *args, **kwargs):
        if self.titulo:
            self.titulo = self.titulo.strip().upper()
        if self.texto:
            self.texto = self.texto.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.titulo
    

class OrdenRecomendacion(models.Model):

    orden = models.ForeignKey(
        "OrdenTrabajo",
        related_name="recomendaciones_items",
        on_delete=models.CASCADE,
    )

    plantilla = models.ForeignKey(
        PlantillaRecomendacion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    titulo = models.CharField(
        max_length=150
    )

    texto = models.TextField()

    orden_item = models.PositiveIntegerField(
        default=1
    )

    creado_en = models.DateTimeField(
        auto_now_add=True
    )

    actualizado_en = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["orden_item", "id"]
        verbose_name = "Recomendación de orden"
        verbose_name_plural = "Recomendaciones de órdenes"

    def validar_orden_editable(self):
        if self.orden and self.orden.estado in ["CERRADA", "ANULADA"]:
            raise ValidationError(
                "No se pueden modificar las recomendaciones de una orden cerrada o anulada. Primero debe reabrirse."
            )

    def clean(self):
        self.validar_orden_editable()

        if not self.titulo or not self.titulo.strip():
            raise ValidationError(
                "El título de la recomendación es obligatorio."
            )

        if not self.texto or not self.texto.strip():
            raise ValidationError(
                "El texto de la recomendación es obligatorio."
            )

    def save(self, *args, **kwargs):
        self.validar_orden_editable()

        if self.titulo:
            self.titulo = self.titulo.strip().upper()

        if self.texto:
            self.texto = self.texto.strip().upper()

        self.full_clean()

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.validar_orden_editable()

        super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.orden.numero_orden} | {self.titulo}"