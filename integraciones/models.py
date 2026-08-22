import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


class CodigoAccesoAsistente(models.Model):
    """
    Código temporal de un solo uso para permitir que un usuario
    autenticado en el ERP ingrese a MAO Asistente sin volver
    a introducir sus credenciales.

    Nunca se almacena el código original, únicamente su SHA-256.

    La sucursal se guarda en el momento de generar el código SSO,
    de modo que usuarios que pueden cambiar de sucursal trabajen
    en MAO Asistente con la sucursal operativa seleccionada.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="codigos_acceso_asistente",
    )

    # =========================================================
    # SUCURSAL OPERATIVA AL GENERAR EL SSO
    # =========================================================

    sucursal = models.ForeignKey(
        "ordenes_de_trabajo.Sucursal",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="codigos_acceso_asistente",
    )

    # =========================================================
    # CÓDIGO
    # =========================================================

    codigo_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
    )

    # =========================================================
    # VIGENCIA
    # =========================================================

    creado_en = models.DateTimeField(
        auto_now_add=True,
    )

    expira_en = models.DateTimeField(
        db_index=True,
    )

    usado_en = models.DateTimeField(
        null=True,
        blank=True,
    )

    # =========================================================
    # META
    # =========================================================

    class Meta:
        verbose_name = "Código de acceso a MAO Asistente"
        verbose_name_plural = "Códigos de acceso a MAO Asistente"
        ordering = ["-creado_en"]

    # =========================================================
    # REPRESENTACIÓN
    # =========================================================

    def __str__(self):
        estado = "USADO" if self.usado_en else "PENDIENTE"

        sucursal = (
            self.sucursal.codigo
            if self.sucursal_id
            else "SIN-SUCURSAL"
        )

        return (
            f"SSO usuario={self.usuario_id} "
            f"sucursal={sucursal} "
            f"[{estado}]"
        )

    # =========================================================
    # ESTADO
    # =========================================================

    @property
    def esta_vigente(self):
        return (
            self.usado_en is None
            and timezone.now() < self.expira_en
        )

    # =========================================================
    # GENERACIÓN DEL CÓDIGO
    # =========================================================

    @staticmethod
    def generar_codigo():
        """
        Genera un token criptográficamente seguro.

        El valor original viajará una sola vez por el navegador.
        """
        return secrets.token_urlsafe(32)

    # =========================================================
    # HASH
    # =========================================================

    @staticmethod
    def calcular_hash(codigo):
        return hashlib.sha256(
            codigo.encode("utf-8")
        ).hexdigest()