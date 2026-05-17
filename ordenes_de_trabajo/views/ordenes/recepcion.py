from django.shortcuts import  redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from ...models import (
    OrdenTrabajo,
    FotoRecepcionVehiculo,
    OrdenCroquisDanio,
    OrdenSintoma,
    OrdenTrabajoSolicitado,
)
from ..utils import (
     cargar_json_lista, procesar_imagen_base64,
    
    puede_operar_orden_desde_sucursal_activa
)
# =========================================================
# EDITAR RECEPCIÓN DE ORDEN (MODAL RÁPIDO COMPLETO)
# =========================================================
@login_required
def editar_recepcion_orden(request, pk):
    import uuid
    from django.db import transaction

    orden = get_object_or_404(OrdenTrabajo, pk=pk)

    if not puede_operar_orden_desde_sucursal_activa(request, orden):
        messages.error(request, "No tienes permiso para editar órdenes de otra sucursal.")
        return redirect("lista_ordenes")

    if orden.estado != "ABIERTA":
        messages.error(request, "No se puede editar la recepción de una orden cerrada o anulada.")
        return redirect("detalle_orden", pk=pk)

    if request.method == "POST":
        orden.observaciones_recepcion = request.POST.get(
            "observaciones_recepcion",
            orden.observaciones_recepcion or ""
        ).strip()

        sintomas_json = cargar_json_lista(request.POST.get("sintomas_json", ""))
        trabajos_json = cargar_json_lista(request.POST.get("trabajos_json", ""))
        croquis_base64 = request.POST.get("imagen_croquis_base64", "").strip()

        # Nuevas fotos desde el modal
        fotos_nuevas = request.FILES.getlist("fotos_recepcion")
        descripcion_fotos = request.POST.get("descripcion_fotos", "").strip()

        # Fotos a eliminar desde el modal
        fotos_eliminar = request.POST.getlist("fotos_eliminar")

        with transaction.atomic():
            orden.save()

            # Síntomas
            orden.sintomas_items.all().delete()
            for idx, item in enumerate(sintomas_json, start=1):
                desc = str(item.get("descripcion", "")).strip()
                if desc:
                    OrdenSintoma.objects.create(
                        orden=orden,
                        descripcion=desc,
                        orden_item=idx
                    )

            # Trabajos solicitados
            orden.trabajos_solicitados_items.all().delete()
            for idx, item in enumerate(trabajos_json, start=1):
                desc = str(item.get("descripcion", "")).strip()
                if desc:
                    OrdenTrabajoSolicitado.objects.create(
                        orden=orden,
                        descripcion_manual=desc,
                        orden_item=idx
                    )

            # Croquis
            if croquis_base64:
                archivo_croquis = procesar_imagen_base64(croquis_base64)
                if archivo_croquis:
                    croquis_obj, _ = OrdenCroquisDanio.objects.get_or_create(orden=orden)

                    if croquis_obj.imagen_generada:
                        croquis_obj.imagen_generada.delete(save=False)

                    nombre_archivo = f"croquis_upd_{orden.numero_orden}_{uuid.uuid4().hex[:8]}.png"
                    croquis_obj.imagen_generada.save(
                        nombre_archivo,
                        archivo_croquis,
                        save=True
                    )

            # Eliminar fotos marcadas
            if fotos_eliminar:
                fotos_queryset = FotoRecepcionVehiculo.objects.filter(
                    orden=orden,
                    id__in=fotos_eliminar
                )

                for foto in fotos_queryset:
                    if foto.imagen:
                        foto.imagen.delete(save=False)
                    foto.delete()

            # Agregar nuevas fotos
            for foto in fotos_nuevas:
                FotoRecepcionVehiculo.objects.create(
                    orden=orden,
                    imagen=foto,
                    descripcion=descripcion_fotos
                )

        messages.success(request, "Recepción, croquis y fotos actualizados con éxito.")

    return redirect("detalle_orden", pk=orden.pk)