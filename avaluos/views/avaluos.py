from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from ordenes_de_trabajo.models import OrdenTrabajo


@login_required
def ordenes_pendientes(request):
    ordenes = (
        OrdenTrabajo.objects
        .filter(
            estado="ABIERTA",
            avaluo_mecanico__isnull=True,
        )
        .select_related(
            "sucursal",
            "cliente",
            "expediente",
        )
        .prefetch_related(
            "tecnicos",
        )
        .order_by("-fecha_ingreso")
    )

    if request.user.rol != "ADMIN":
        ordenes = ordenes.filter(
            sucursal=request.user.sucursal
        )

    return render(
        request,
        "avaluos/ordenes_pendientes.html",
        {
            "ordenes": ordenes,
        },
    )


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect

from avaluos.models import AvaluoMecanico
from ordenes_de_trabajo.models import OrdenTrabajo


@login_required
def iniciar_avaluo(request, orden_id):
    orden = get_object_or_404(
        OrdenTrabajo.objects.select_related(
            "sucursal",
            "cliente",
            "expediente",
        ),
        pk=orden_id,
        estado="ABIERTA",
    )

    # Los usuarios que no sean ADMIN solo pueden trabajar
    # con órdenes de su propia sucursal.
    if (
        request.user.rol != "ADMIN"
        and orden.sucursal_id != request.user.sucursal_id
    ):
        messages.error(
            request,
            "No tienes permiso para evaluar una orden de otra sucursal.",
        )
        return redirect("avaluos:ordenes_pendientes")

    # Evita crear dos avalúos para la misma OT.
    avaluo, creado = AvaluoMecanico.objects.get_or_create(
        orden=orden,
        defaults={
            "creado_por": request.user,
            "actualizado_por": request.user,
            "solicitado_por": orden.nombre_cliente_final,
        },
    )

    # Si ya existía, simplemente se abre el mismo avalúo.
    return redirect(
        "avaluos:detalle_avaluo",
        pk=avaluo.pk,
    )


@login_required
def detalle_avaluo(request, pk):
    avaluo = get_object_or_404(
        AvaluoMecanico.objects.select_related(
            "orden",
            "orden__sucursal",
            "orden__cliente",
            "orden__expediente",
            "creado_por",
            "evaluador",
        ),
        pk=pk,
    )

    if (
        request.user.rol != "ADMIN"
        and avaluo.orden.sucursal_id != request.user.sucursal_id
    ):
        messages.error(
            request,
            "No tienes permiso para ver este avalúo.",
        )
        return redirect("avaluos:ordenes_pendientes")

    return render(
        request,
        "avaluos/detalle_avaluo.html",
        {
            "avaluo": avaluo,
            "orden": avaluo.orden,
        },
    )