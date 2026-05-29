from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.contrib import messages

# Importamos el modelo y el nuevo formulario
from ..models import Cliente 
from ..forms import ClienteForm



from django.db import transaction

@login_required
def guardar_cliente_seguro(request, data_form, es_api=False, data_api=None):
    """
    Función maestra para guardar clientes evitando duplicados.
    """
    identificacion = data_form.get('identificacion')
    
    # 1. BUSCAR CANDADO: ¿Existe ya esta identificación en la BDD?
    with transaction.atomic():
        cliente = Cliente.objects.filter(identificacion=identificacion).first()
        
        if cliente:
            # SI YA EXISTE: Solo actualizamos los datos básicos
            cliente.nombre_completo = data_form.get('nombre_completo')
            cliente.telefono = data_form.get('telefono')
            cliente.email = data_form.get('email')
            # ... (demás campos)
            
            # Si viene de la API, le inyectamos los datos nuevos SIN crear otro registro
            if es_api and data_api:
                cliente.cargar_desde_api_persona(data_api, full=True)
                cliente.datos_full_consultados = True
            
            cliente.save()
            return cliente, False # False = No se creó, se actualizó
        
        else:
            # SI NO EXISTE: Creamos uno nuevo
            nuevo_cliente = Cliente(**data_form)
            if es_api and data_api:
                nuevo_cliente.cargar_desde_api_persona(data_api, full=True)
            nuevo_cliente.save()
            return nuevo_cliente, True # True = Se creó nuevo


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
import requests
from django.utils import timezone
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
# Asegúrate de importar tu formulario y tu modelo
from ..forms import ClienteForm
from ..models import Cliente

# Tu token de la API
CEDULA_API_TOKEN = "yKGE-7wqa-kwNp-3AvU"
# ==========================================
# 2. CREAR CLIENTE (HÍBRIDO: MANUAL + API)
# ==========================================
@login_required
def crear_cliente(request):
    if request.method == 'POST':
        # 1. Recuperamos identificación para validación de seguridad
        identificacion = request.POST.get('identificacion', '').strip()
        
        # SEGURIDAD: Evitar duplicados antes de procesar nada
        if identificacion and Cliente.objects.filter(identificacion=identificacion).exists():
            messages.warning(request, f"El cliente con identificación {identificacion} ya existe.")
            cliente_existente = Cliente.objects.get(identificacion=identificacion)
            return redirect('editar_cliente', cliente_id=cliente_existente.id)

        form = ClienteForm(request.POST)
        
        if form.is_valid():
            # Creamos la instancia sin guardar en BDD aún
            nuevo_cliente = form.save(commit=False)
            
            # 2. CONSUMO DE API (Solo si es identificación válida)
            if identificacion.isdigit() and len(identificacion) in [10, 13]:
                es_ruc = len(identificacion) == 13
                url = f"https://apiconsult.zampisoft.com/api/consultar?identificacion={identificacion}&token={CEDULA_API_TOKEN}"
                
                # Si es cédula, pedimos el detalle completo (full=true)
                if not es_ruc:
                    url += "&full=true"
                    
                try:
                    respuesta = requests.get(url, timeout=10, headers={"Accept": "application/json"})
                    
                    if respuesta.status_code == 200:
                        data = respuesta.json()
                        if not data.get("error"):
                            # Inyectamos TODOS los datos del API al modelo
                            if es_ruc:
                                nuevo_cliente.cargar_desde_api_ruc(data)
                            else:
                                nuevo_cliente.cargar_desde_api_persona(data, full=True)
                            
                            nuevo_cliente.fecha_ultima_consulta_api = timezone.now()
                            nuevo_cliente.datos_full_consultados = True
                except Exception as e:
                    # Si falla la API, el sistema NO se detiene, continúa con lo manual
                    print(f"Error al consultar API en crear_cliente: {e}")

            # 3. PRIORIDAD MANUAL
            # Si el usuario llenó algo a mano, eso prevalece sobre lo que trajo la API
            # (Ej: el usuario corrigió el número de teléfono o la dirección)
            if form.cleaned_data.get('telefono'):
                nuevo_cliente.telefono = form.cleaned_data.get('telefono')
            if form.cleaned_data.get('telefono_secundario'):
                nuevo_cliente.telefono_secundario = form.cleaned_data.get('telefono_secundario')
            if form.cleaned_data.get('email'):
                nuevo_cliente.email = form.cleaned_data.get('email')
            if form.cleaned_data.get('direccion'):
                nuevo_cliente.direccion = form.cleaned_data.get('direccion')

            # 4. GUARDADO FINAL SEGURO
            with transaction.atomic():
                nuevo_cliente.save()
            
            messages.success(request, f"Cliente {nuevo_cliente.nombre_completo} registrado correctamente.")
            return redirect('lista_clientes')
        else:
            messages.error(request, "El formulario tiene errores, por favor verifique.")
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
@login_required
def detalle_cliente(request, cliente_id):
    # Buscamos al cliente por ID
    cliente = get_object_or_404(Cliente, id=cliente_id)
    
    # Obtenemos sus vehículos asociados a través del related_name 'expedientes'
    vehiculos = cliente.expedientes.all().order_by('-actualizado_en')
    
    return render(request, 'detalle_cliente.html', {
        'cliente': cliente,
        'vehiculos': vehiculos,
    })