from django.urls import path

from . import views


app_name = "integraciones"


urlpatterns = [

    # Usuario ERP autenticado -> MAO Asistente
    path(
        "asistente/entrar/",
        views.entrar_asistente,
        name="entrar_asistente",
    ),

    # MAO Asistente -> ERP (servidor a servidor)
    path(
        "asistente/api/sso/canjear/",
        views.canjear_codigo_asistente,
        name="canjear_codigo_asistente",
    ),

]