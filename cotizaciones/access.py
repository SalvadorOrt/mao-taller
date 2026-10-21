"""Branch scope follows the ERP's operational-branch session and permissions."""
from django.core.exceptions import PermissionDenied
from ordenes_de_trabajo.models import Sucursal
from .models import SolicitudCotizacion


def sucursal_activa(request):
    user = request.user
    can_switch = user.is_superuser or user.has_perm('inventario.cambiar_sucursal_operativa')
    if can_switch and request.session.get('sucursal_activa_id'):
        branch = Sucursal.objects.filter(pk=request.session['sucursal_activa_id'], activa=True).first()
        if branch:
            return branch
    return Sucursal.objects.filter(pk=user.sucursal_id, activa=True).first() if user.sucursal_id else None


def solicitudes_visibles(request):
    qs = SolicitudCotizacion.objects.select_related('orden', 'sucursal', 'creada_por')
    if request.user.is_superuser or request.user.has_perm('inventario.cambiar_sucursal_operativa'):
        return qs
    branch = sucursal_activa(request)
    return qs.filter(sucursal=branch) if branch else qs.none()


def comprobar_operacion(request, solicitud):
    branch = sucursal_activa(request)
    if not branch or branch.pk != solicitud.sucursal_id:
        raise PermissionDenied('Selecciona la sucursal operativa de esta solicitud para modificarla.')
    if solicitud.estado == 'CANCELADA' or solicitud.orden.estado == 'ANULADA':
        raise PermissionDenied('Esta solicitud u orden está cancelada.')
