from django.contrib import admin
from .models import Sucursal


@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "telefono", "activa")
    search_fields = ("nombre", "codigo", "telefono")
    list_filter = ("activa",)
    ordering = ("nombre",)