from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.models import Session
from django.utils import timezone


def cerrar_sesiones_de_usuario(usuario):
    """
    Cierra todas las sesiones activas pertenecientes
    al usuario indicado.
    """

    sesiones_ids = []

    sesiones = Session.objects.filter(
        expire_date__gte=timezone.now()
    )

    for sesion in sesiones.iterator():
        try:
            datos = sesion.get_decoded()
        except Exception:
            continue

        usuario_id = datos.get(
            SESSION_KEY
        )

        if str(usuario_id) == str(usuario.pk):
            sesiones_ids.append(
                sesion.pk
            )

    cantidad = len(
        sesiones_ids
    )

    if sesiones_ids:
        Session.objects.filter(
            pk__in=sesiones_ids
        ).delete()

    return cantidad


def cerrar_todas_las_sesiones():
    """
    Cierra absolutamente todas las sesiones
    almacenadas por Django.
    """

    cantidad = (
        Session.objects
        .count()
    )

    Session.objects.all().delete()

    return cantidad