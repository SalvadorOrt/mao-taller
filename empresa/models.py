import os
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


# =========================================================
# VALIDADORES
# =========================================================

solo_3_digitos = RegexValidator(
    regex=r"^\d{3}$",
    message="Debe contener exactamente 3 dígitos.",
)

solo_13_digitos = RegexValidator(
    regex=r"^\d{13}$",
    message="Debe contener exactamente 13 dígitos.",
)


def validar_archivo_firma(value):
    if not value:
        return

    extension = os.path.splitext(value.name)[1].lower()
    if extension not in [".p12", ".pfx"]:
        raise ValidationError("La firma electrónica debe ser un archivo .p12 o .pfx")


# =========================================================
# EMPRESA EMISORA
# =========================================================

class EmpresaEmisora(models.Model):
    OBLIGADO_CONTABILIDAD_CHOICES = [
        ("SI", "Sí"),
        ("NO", "No"),
    ]

    logo = models.ImageField(
        upload_to="empresas/logos/",
        blank=True,
        null=True,
    )

    resolucion_agente_retencion = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    razon_social = models.CharField(max_length=300)
    nombre_comercial = models.CharField(max_length=300, blank=True, null=True)
    ruc = models.CharField(max_length=13, unique=True, validators=[solo_13_digitos])

    dir_matriz = models.CharField(max_length=500)
    dir_establecimiento = models.CharField(max_length=500)

    establecimiento = models.CharField(
        max_length=3,
        default="001",
        validators=[solo_3_digitos],
        
    )

    punto_emision = models.CharField(
        max_length=3,
        default="001",
        validators=[solo_3_digitos],
       
    )

    contribuyente_especial = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )

    obligado_contabilidad = models.CharField(
        max_length=2,
        choices=OBLIGADO_CONTABILIDAD_CHOICES,
        default="SI",
    )

    agente_retencion = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)

    telefono = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    sitio_web = models.URLField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Empresa emisora"
        verbose_name_plural = "Empresas emisoras"
        ordering = ["razon_social"]
        indexes = [
            models.Index(fields=["ruc"]),
            models.Index(fields=["activo"]),
            models.Index(fields=["razon_social"]),
        ]

    def __str__(self):
        return f"{self.razon_social} - {self.ruc}"

    def clean(self):
        super().clean()

        if self.razon_social:
            self.razon_social = self.razon_social.strip()

        if self.nombre_comercial:
            self.nombre_comercial = self.nombre_comercial.strip()

        if self.ruc:
            self.ruc = self.ruc.strip()

        if self.dir_matriz:
            self.dir_matriz = self.dir_matriz.strip()

        if self.dir_establecimiento:
            self.dir_establecimiento = self.dir_establecimiento.strip()

        if self.establecimiento:
            self.establecimiento = self.establecimiento.strip()

        if self.punto_emision:
            self.punto_emision = self.punto_emision.strip()

        if self.contribuyente_especial:
            self.contribuyente_especial = self.contribuyente_especial.strip()

        if self.telefono:
            self.telefono = self.telefono.strip()

        if self.email:
            self.email = self.email.strip().lower()

        if self.sitio_web:
            self.sitio_web = self.sitio_web.strip()

        if self.resolucion_agente_retencion:
            self.resolucion_agente_retencion = self.resolucion_agente_retencion.strip()

        if not self.razon_social:
            raise ValidationError({"razon_social": "La razón social es obligatoria."})

        if not self.ruc:
            raise ValidationError({"ruc": "El RUC es obligatorio."})

        if not self.dir_matriz:
            raise ValidationError({"dir_matriz": "La dirección matriz es obligatoria."})

        if not self.dir_establecimiento:
            raise ValidationError({"dir_establecimiento": "La dirección del establecimiento es obligatoria."})

        if not self.nombre_comercial:
            self.nombre_comercial = self.razon_social


    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# =========================================================
# FIRMA ELECTRÓNICA
# =========================================================

class FirmaElectronica(models.Model):
    ESTADOS = [
        ("ACTIVA", "Activa"),
        ("INACTIVA", "Inactiva"),
        ("VENCIDA", "Vencida"),
    ]

    empresa = models.ForeignKey(
        EmpresaEmisora,
        on_delete=models.CASCADE,
        related_name="firmas",
    )

    nombre = models.CharField(
        max_length=100,
       
    )

    titular = models.CharField(
        max_length=200,
        
    )

    ruc = models.CharField(
        max_length=13,
        validators=[solo_13_digitos],
       
    )

    archivo_firma = models.FileField(
        upload_to="firmas_electronicas/",
        validators=[validar_archivo_firma],
       
    )

    password_firma = models.CharField(
        max_length=255,
       
    )

    entidad_certificadora = models.CharField(
        max_length=150,
        blank=True,
        null=True,
    )

    fecha_inicio_vigencia = models.DateField(blank=True, null=True)
    fecha_fin_vigencia = models.DateField(blank=True, null=True)

    estado = models.CharField(
        max_length=10,
        choices=ESTADOS,
        default="ACTIVA",
    )

    observaciones = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Firma electrónica"
        verbose_name_plural = "Firmas electrónicas"
        ordering = ["empresa__razon_social", "nombre", "-id"]
        indexes = [
            models.Index(fields=["ruc"]),
            models.Index(fields=["estado"]),
            models.Index(fields=["empresa", "estado"]),
        ]

    def __str__(self):
        return f"{self.nombre} - {self.ruc}"

    def clean(self):
        super().clean()

        if self.nombre:
            self.nombre = self.nombre.strip()

        if self.titular:
            self.titular = self.titular.strip()

        if self.ruc:
            self.ruc = self.ruc.strip()

        if self.password_firma:
            self.password_firma = self.password_firma.strip()

        if self.entidad_certificadora:
            self.entidad_certificadora = self.entidad_certificadora.strip()

        if self.observaciones:
            self.observaciones = self.observaciones.strip()

        if not self.empresa_id:
            raise ValidationError({"empresa": "La empresa emisora es obligatoria."})

        if not self.nombre:
            raise ValidationError({"nombre": "El nombre interno de la firma es obligatorio."})

        if not self.titular:
            raise ValidationError({"titular": "El titular de la firma es obligatorio."})

        if not self.ruc:
            raise ValidationError({"ruc": "El RUC de la firma es obligatorio."})

        if not self.password_firma:
            raise ValidationError({"password_firma": "La contraseña de la firma es obligatoria."})

        if self.empresa and self.ruc != self.empresa.ruc:
            raise ValidationError({
                "ruc": "El RUC de la firma debe coincidir con el RUC de la empresa emisora."
            })

        if self.fecha_inicio_vigencia and self.fecha_fin_vigencia:
            if self.fecha_inicio_vigencia > self.fecha_fin_vigencia:
                raise ValidationError({
                    "fecha_fin_vigencia": "La fecha fin no puede ser menor que la fecha inicio."
                })

    def save(self, *args, **kwargs):
        hoy = timezone.localdate()

        if self.fecha_fin_vigencia and self.fecha_fin_vigencia < hoy:
            self.estado = "VENCIDA"

        self.full_clean()
        super().save(*args, **kwargs)

    def esta_vigente(self):
        hoy = timezone.localdate()

        if self.estado != "ACTIVA":
            return False

        if self.fecha_inicio_vigencia and hoy < self.fecha_inicio_vigencia:
            return False

        if self.fecha_fin_vigencia and hoy > self.fecha_fin_vigencia:
            return False

        return True