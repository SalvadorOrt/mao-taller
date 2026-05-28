from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.contrib import messages

# Importamos el modelo y el nuevo formulario
from ..models import Cliente 
from ..forms import ClienteForm

# ==========================================
# 1. LISTA DE CLIENTES
# ==========================================

@login_required
def lista_clientes(request):
    query = request.GET.get('q', '').strip()
    
    # Traemos TODOS los clientes y contamos sus vehículos (Quitamos el filter activo=True)
    clientes = Cliente.objects.annotate(
        num_vehiculos=Count('expedientes')
    ).order_by('-id')

    if query:
        clientes = clientes.filter(
            Q(identificacion__icontains=query) |
            Q(nombre_completo__icontains=query) |
            Q(telefono__icontains=query) |
            Q(email__icontains=query)
        )

    paginator = Paginator(clientes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'lista_clientes.html', {
        'page_obj': page_obj,
        'query': query,
    })
# ==========================================
# 2. CREAR CLIENTE
# ==========================================
@login_required
def crear_cliente(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            nuevo_cliente = form.save()
            messages.success(request, f"Cliente {nuevo_cliente.nombre_completo} registrado con éxito.")
            return redirect('lista_clientes')
        else:
            messages.error(request, "Por favor corrige los errores en el formulario.")
    else:
        form = ClienteForm()
        
    return render(request, 'formulario_cliente.html', {
        'form': form, 
        'accion': 'Nuevo Cliente'
    })

# ==========================================
# 3. EDITAR CLIENTE
# ==========================================
@login_required
def editar_cliente(request, cliente_id):
    # Buscamos el cliente, si no existe devuelve error 404
    cliente = get_object_or_404(Cliente, id=cliente_id)
    
    if request.method == 'POST':
        # Le pasamos la 'instance' para que Django sepa que estamos actualizando, no creando uno nuevo
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, "Datos del cliente actualizados correctamente.")
            return redirect('lista_clientes')
        else:
            messages.error(request, "Por favor corrige los errores en el formulario.")
    else:
        # Cargamos el formulario lleno con los datos actuales del cliente
        form = ClienteForm(instance=cliente)
        
    return render(request, 'formulario_cliente.html', {
        'form': form, 
        'cliente': cliente, 
        'accion': 'Editar Cliente'
    })