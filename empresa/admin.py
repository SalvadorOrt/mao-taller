from django.contrib import admin

from .models import (
    EmpresaEmisora,
    FirmaElectronica,
)


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


@admin.register(FirmaElectronica)
class FirmaElectronicaAdmin(admin.ModelAdmin):

    list_display = (
        "nombre",
        "empresa",
        "titular",
        "ruc",
        "fecha_inicio_vigencia",
        "fecha_fin_vigencia",
        "estado",
    )

    search_fields = (
        "nombre",
        "titular",
        "ruc",
        "empresa__razon_social",
    )

    list_filter = (
        "estado",
        "empresa",
    )