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
        form = ClienteForm(request.POST)
        identificacion = request.POST.get('identificacion', '').strip()
        
        # 1. Seguridad: Si ya existe, redirigir a edición
        cliente_existente = Cliente.objects.filter(identificacion=identificacion).first()
        if cliente_existente:
            messages.warning(request, f"El cliente {identificacion} ya existe.")
            return redirect('editar_cliente', cliente_id=cliente_existente.id)

        if form.is_valid():
            nuevo_cliente = form.save(commit=False)
            solicitar_full = form.cleaned_data.get('consultar_full', False)
            
            # 2. CONSUMO DE API (Solo si no existe en BD)
            if identificacion.isdigit() and len(identificacion) in [10, 13]:
                es_ruc = len(identificacion) == 13
                url = f"https://apiconsult.zampisoft.com/api/consultar?identificacion={identificacion}&token={CEDULA_API_TOKEN}"
                if not es_ruc and solicitar_full:
                    url += "&full=true"
                    
                try:
                    respuesta = requests.get(url, timeout=10, headers={"Accept": "application/json"})
                    if respuesta.status_code == 200:
                        data = respuesta.json()
                        if not data.get("error"):
                            nuevo_cliente.aplicar_datos_api(data, es_ruc=es_ruc, full=solicitar_full)
                except Exception as e:
                    print(f"API Falló, guardando datos manuales: {e}")

            nuevo_cliente.save()
            messages.success(request, "Cliente registrado correctamente.")
            return redirect('lista_clientes')
            
    else:
        form = ClienteForm()
        
    return render(request, 'formulario_cliente.html', {'form': form, 'accion': 'Nuevo Cliente'})
@login_required
def editar_cliente(request, cliente_id):
    """
    Vista de edición con capacidad de refresco manual desde API.
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)
    
    # 1. Lógica de REFRESCO MANUAL (Si el usuario pulsa un botón de actualizar)
    if request.method == "POST" and "actualizar_api" in request.POST:
        identificacion = cliente.identificacion
        es_ruc = len(identificacion) == 13
        
        try:
            # Reutilizamos la lógica de consulta
            url = f"https://apiconsult.zampisoft.com/api/consultar?identificacion={identificacion}&token={CEDULA_API_TOKEN}"
            if not es_ruc:
                url += "&full=true"
                
            respuesta = requests.get(url, timeout=10, headers={"Accept": "application/json"})
            if respuesta.status_code == 200:
                data = respuesta.json()
                if not data.get("error"):
                    # Usamos el método robusto que definimos en el modelo
                    cliente.actualizar_datos_inteligente(data, es_ruc=es_ruc, full=True)
                    messages.success(request, "Datos actualizados exitosamente desde la API.")
                else:
                    messages.error(request, "La API respondió con un error.")
            else:
                messages.error(request, "Error de conexión con la API.")
        except Exception as e:
            messages.error(request, f"Error al actualizar: {str(e)}")
            
        return redirect('editar_cliente', cliente_id=cliente.id)

    # 2. Lógica de GUARDADO NORMAL
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, "Cambios guardados correctamente.")
            return redirect('lista_clientes')
        else:
            messages.error(request, "Por favor corrija los errores en el formulario.")
    else:
        # Carga inicial
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