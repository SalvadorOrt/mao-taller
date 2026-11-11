"""Vistas de clientes de MAO, compatibles con ApiConsult 2026.

No se realizan consultas de identificación implícitas al guardar formularios.
La búsqueda y el refresco manual utilizan el servicio compartido de views.api.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Count
from django.shortcuts import render, redirect, get_object_or_404

from ..forms import ClienteForm
from ..models import Cliente
from .api import (
    ApiConsultError,
    aplicar_datos_zampisoft,
    consultar_zampisoft,
    validar_identificacion_api,
)


@login_required
def guardar_cliente_seguro(request, data_form, es_api=False, data_api=None):
    """Conserva la función usada en MAO evitando duplicados por identificación."""
    identificacion = data_form.get("identificacion")
    with transaction.atomic():
        cliente = (
            Cliente.objects.select_for_update()
            .filter(identificacion=identificacion)
            .first()
        )
        if cliente:
            # Mantiene la lógica original de recibir las modificaciones del formulario.
            for campo in ("nombre_completo", "telefono", "email"):
                if campo in data_form:
                    setattr(cliente, campo, data_form[campo])
            if es_api and data_api:
                aplicar_datos_zampisoft(
                    cliente, data_api, es_ruc=len(str(identificacion or "")) == 13
                )
            cliente.save()
            return cliente, False

        nuevo_cliente = Cliente(**data_form)
        if es_api and data_api:
            aplicar_datos_zampisoft(
                nuevo_cliente, data_api, es_ruc=len(str(identificacion or "")) == 13
            )
        nuevo_cliente.save()
        return nuevo_cliente, True


# ==========================================
# 1. LISTA DE CLIENTES
# ==========================================

@login_required
def lista_clientes(request):
    query = request.GET.get("q", "").strip()
    clientes = (
        Cliente.objects.annotate(num_vehiculos=Count("expedientes"))
        .order_by("-id")
    )
    if query:
        clientes = clientes.filter(
            Q(identificacion__icontains=query)
            | Q(nombre_completo__icontains=query)
            | Q(telefono__icontains=query)
            | Q(email__icontains=query)
        )

    paginator = Paginator(clientes, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "lista_clientes.html", {
        "page_obj": page_obj,
        "query": query,
    })


# ==========================================
# 2. CREAR CLIENTE (FORMULARIO MANUAL + BÚSQUEDA EXPLÍCITA)
# ==========================================

@login_required
def crear_cliente(request):
    if request.method == "POST":
        identificacion = request.POST.get("identificacion", "").strip()
        existente = (
            Cliente.objects.filter(identificacion=identificacion).first()
            if identificacion else None
        )
        # Si el botón "Buscar" ya creó el cliente desde la API,
        # guardar sus nuevos datos manuales como una actualización.
        form = ClienteForm(request.POST, instance=existente)
        if form.is_valid():
            cliente = form.save()
            if existente:
                messages.success(request, "Datos del cliente actualizados correctamente.")
            else:
                messages.success(request, "Cliente registrado correctamente.")
            return redirect("lista_clientes")
        messages.error(request, "Corrige los errores del formulario.")
    else:
        form = ClienteForm()

    return render(request, "formulario_cliente.html", {
        "form": form,
        "accion": "Nuevo Cliente",
    })


# ==========================================
# 3. EDITAR CLIENTE / REFRESCO EXPLÍCITO DESDE API
# ==========================================

@login_required
def editar_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)

    if request.method == "POST" and "actualizar_api" in request.POST:
        identificacion = str(cliente.identificacion or "").strip()
        if not validar_identificacion_api(identificacion):
            messages.error(request, "La cédula o RUC no es válido para consultar la API.")
            return redirect("editar_cliente", cliente_id=cliente.id)

        try:
            # Una solicitud sólo si el usuario pulsó el botón de refresco.
            data = consultar_zampisoft(identificacion)
            with transaction.atomic():
                cliente = Cliente.objects.select_for_update().get(pk=cliente.pk)
                aplicar_datos_zampisoft(
                    cliente, data, es_ruc=len(identificacion) == 13
                )
                cliente.save()
            messages.success(request, "Datos actualizados desde ApiConsult.")
        except ApiConsultError as exc:
            mensaje = str(exc)
            if exc.retry_after:
                mensaje += f" Espera {exc.retry_after} antes de reintentar."
            messages.error(request, mensaje)
        except Exception:
            messages.error(request, "No se pudieron guardar los datos de la API.")
        return redirect("editar_cliente", cliente_id=cliente.id)

    if request.method == "POST":
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, "Cambios guardados correctamente.")
            return redirect("lista_clientes")
        messages.error(request, "Por favor corrige los errores en el formulario.")
    else:
        form = ClienteForm(instance=cliente)

    return render(request, "formulario_cliente.html", {
        "form": form,
        "cliente": cliente,
        "accion": "Editar Cliente",
    })


# ==========================================
# 4. DETALLE DE CLIENTE
# ==========================================

@login_required
def detalle_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    vehiculos = cliente.expedientes.all().order_by("-actualizado_en")
    return render(request, "detalle_cliente.html", {
        "cliente": cliente,
        "vehiculos": vehiculos,
    })