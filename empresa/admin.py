from django.contrib import admin

from .models import (
    EmpresaEmisora,
    FirmaElectronica,
)


# =========================================================
# FIRMA ELECTRÓNICA DENTRO DE EMPRESA
# =========================================================

class FirmaElectronicaInline(admin.StackedInline):
    model = FirmaElectronica

    extra = 0

    fields = (
        "nombre",
        "titular",
        "ruc",
        "archivo_firma",
        "password_firma",
        "entidad_certificadora",
        "fecha_inicio_vigencia",
        "fecha_fin_vigencia",
        "estado",
        "observaciones",
    )


# =========================================================
# EMPRESA EMISORA
# =========================================================

@admin.register(EmpresaEmisora)
class EmpresaEmisoraAdmin(admin.ModelAdmin):

    list_display = (
        "razon_social",
        "ruc",
        "nombre_comercial",
        "establecimiento",
        "punto_emision",
        "activo",
    )

    search_fields = (
        "razon_social",
        "nombre_comercial",
        "ruc",
    )

    list_filter = (
        "activo",
        "obligado_contabilidad",
        "agente_retencion",
    )

    fieldsets = (
        (
            "Identidad",
            {
                "fields": (
                    "logo",
                    "razon_social",
                    "nombre_comercial",
                    "ruc",
                )
            },
        ),
        (
            "Direcciones",
            {
                "fields": (
                    "dir_matriz",
                    "dir_establecimiento",
                )
            },
        ),
        (
            "Facturación electrónica",
            {
                "fields": (
                    "establecimiento",
                    "punto_emision",
                )
            },
        ),
        (
            "Información tributaria",
            {
                "fields": (
                    "contribuyente_especial",
                    "obligado_contabilidad",
                    "agente_retencion",
                    "resolucion_agente_retencion",
                )
            },
        ),
        (
            "Contacto",
            {
                "fields": (
                    "telefono",
                    "email",
                    "sitio_web",
                )
            },
        ),
        (
            "Estado",
            {
                "fields": (
                    "activo",
                )
            },
        ),
    )

    inlines = [
        FirmaElectronicaInline,
    ]