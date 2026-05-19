from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count

# Subimos un nivel (..) para acceder a models.py
from ..models import Cliente 

@login_required
def lista_clientes(request):
    query = request.GET.get('q', '').strip()
    
    # Traemos los clientes y contamos sus vehículos
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

    # Django buscará automáticamente 'lista_clientes.html' en tu carpeta templates/
    return render(request, 'lista_clientes.html', {
        'page_obj': page_obj,
        'query': query,
    })