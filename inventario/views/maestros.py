from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)

from accesos.permissions import permiso_requerido

from inventario.forms import (
    AtributoForm,
    CategoriaForm,
    MarcaRepuestoForm,
)

from inventario.models import (
    Atributo,
    Categoria,
    CategoriaAtributo,
    FamiliaProducto,
    MarcaRepuesto,
    OpcionCategoriaAtributo,
)


# =========================================================
# CONSTANTES
# =========================================================

TIPOS_DATO_VALIDOS = {
    "TEXTO",
    "ENTERO",
    "DECIMAL",
    "BOOLEANO",
    "OPCION",
}


# =========================================================
# UTILIDADES
# =========================================================

def _obtener_ids_atributos_post(request):
    """
    Devuelve IDs de atributos seleccionados,
    sin duplicados y conservando el orden.
    """

    ids = []

    for atributo_id in request.POST.getlist(
        "atributos_categoria"
    ):
        try:
            atributo_id = int(
                atributo_id
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

        if atributo_id not in ids:
            ids.append(
                atributo_id
            )

    return ids


def _obtener_opciones_post(
    request,
    atributo_id,
):
    """
    Obtiene las opciones de un atributo tipo OPCION.

    Soporta:

    opciones_<id> enviados como múltiples inputs

    o:

    opciones_texto_<id> enviado como textarea,
    una opción por línea.
    """

    clave_lista = (
        f"opciones_{atributo_id}"
    )

    clave_texto = (
        f"opciones_texto_{atributo_id}"
    )

    valores = []

    # -----------------------------------------------------
    # Múltiples inputs
    # -----------------------------------------------------

    for valor in request.POST.getlist(
        clave_lista
    ):
        valor = str(
            valor or ""
        ).strip()

        if (
            valor
            and valor not in valores
        ):
            valores.append(
                valor
            )

    # -----------------------------------------------------
    # Textarea
    # -----------------------------------------------------

    texto = str(
        request.POST.get(
            clave_texto,
            "",
        )
        or ""
    )

    if texto:
        for linea in texto.splitlines():
            valor = linea.strip()

            if (
                valor
                and valor not in valores
            ):
                valores.append(
                    valor
                )

    return valores


def _sincronizar_opciones_categoria(
    request,
    relacion,
):
    """
    Sincroniza las opciones de una relación
    CategoriaAtributo.

    IMPORTANTE:

    Solo modifica opciones si el formulario
    envía:

        opciones_present_<atributo_id> = 1

    Esto evita borrar configuraciones antiguas
    mientras todavía actualizamos el HTML.
    """

    atributo = relacion.atributo

    if atributo.tipo_dato != "OPCION":
        return

    marcador = (
        f"opciones_present_{atributo.pk}"
    )

    if request.POST.get(
        marcador
    ) != "1":
        return

    opciones = (
        _obtener_opciones_post(
            request,
            atributo.pk,
        )
    )

    if not opciones:
        raise ValueError(
            f'El atributo "{atributo.nombre}" '
            "es de tipo lista y debe tener "
            "al menos una opción."
        )

    # -----------------------------------------------------
    # Desactivar opciones que ya no existen
    # -----------------------------------------------------

    (
        relacion.opciones
        .exclude(
            valor__in=opciones
        )
        .update(
            activo=False
        )
    )

    # -----------------------------------------------------
    # Crear / reactivar / ordenar
    # -----------------------------------------------------

    for orden, valor in enumerate(
        opciones
    ):
        OpcionCategoriaAtributo.objects.update_or_create(
            categoria_atributo=relacion,
            valor=valor,
            defaults={
                "orden": orden,
                "activo": True,
            },
        )


def _construir_configuracion_atributos(
    categoria,
    atributos_catalogo,
):
    """
    Estructura preparada para el template
    maestro de categorías.

    Permite mostrar:

    atributo
    tipo
    unidad
    seleccionado
    requerido
    opciones
    """

    relaciones = {}

    if categoria:
        relaciones = {
            relacion.atributo_id: relacion
            for relacion in (
                CategoriaAtributo.objects
                .filter(
                    categoria=categoria
                )
                .select_related(
                    "atributo"
                )
                .prefetch_related(
                    "opciones"
                )
            )
        }

    resultado = []

    for atributo in atributos_catalogo:
        relacion = relaciones.get(
            atributo.pk
        )

        opciones = []

        if relacion:
            opciones = list(
                relacion.opciones
                .filter(
                    activo=True
                )
                .order_by(
                    "orden",
                    "valor",
                )
                .values_list(
                    "valor",
                    flat=True,
                )
            )

        resultado.append({
            "atributo": atributo,
            "seleccionado": bool(
                relacion
                and relacion.activo
            ),
            "requerido": bool(
                relacion
                and relacion.requerido
            ),
            "orden": (
                relacion.orden
                if relacion
                else 0
            ),
            "opciones": opciones,
        })

    return resultado


# =========================================================
# CATEGORÍAS - LISTADO
# =========================================================

@permiso_requerido(
    "inventario.view_categoria"
)
def categoria_lista(request):
    q = (
        request.GET
        .get(
            "q",
            "",
        )
        .strip()
    )

    categorias = (
        Categoria.objects
        .select_related(
            "familia"
        )
        .all()
        .order_by(
            "familia__orden",
            "familia__nombre",
            "nombre",
        )
    )

    if q:
        categorias = categorias.filter(
            Q(
                nombre__icontains=q
            )
            | Q(
                prefijo_sku__icontains=q
            )
            | Q(
                familia__nombre__icontains=q
            )
        )

    return render(
        request,
        "maestros/categoria_lista.html",
        {
            "categorias": categorias,
            "q": q,
        },
    )


# =========================================================
# CATEGORÍAS - CREAR / EDITAR
# =========================================================

@login_required
def categoria_gestionar(
    request,
    pk=None,
):
    permiso_necesario = (
        "inventario.change_categoria"
        if pk
        else "inventario.add_categoria"
    )

    if not request.user.has_perm(
        permiso_necesario
    ):
        messages.error(
            request,
            (
                "No tienes permisos para "
                "gestionar categorías."
            ),
        )

        return redirect(
            "dashboard"
        )

    categoria = (
        get_object_or_404(
            Categoria.objects
            .select_related(
                "familia"
            ),
            pk=pk,
        )
        if pk
        else None
    )

    atributos_catalogo = (
        Atributo.objects
        .all()
        .order_by(
            "nombre",
            "unidad",
        )
    )

    # =====================================================
    # ATRIBUTOS SELECCIONADOS
    # =====================================================

    if request.method == "POST":

        atributos_configurados = set(
            _obtener_ids_atributos_post(
                request
            )
        )

    elif categoria:

        atributos_configurados = set(
            CategoriaAtributo.objects
            .filter(
                categoria=categoria,
                activo=True,
            )
            .values_list(
                "atributo_id",
                flat=True,
            )
        )

    else:
        atributos_configurados = set()

    # =====================================================
    # POST
    # =====================================================

    if request.method == "POST":

        form = CategoriaForm(
            request.POST,
            instance=categoria,
        )

        if form.is_valid():

            try:
                with transaction.atomic():

                    categoria_guardada = (
                        form.save()
                    )

                    # =====================================
                    # CONFIGURACIÓN CATEGORÍA ↔ ATRIBUTOS
                    # =====================================

                    if (
                        request.POST.get(
                            "atributos_categoria_present"
                        )
                        == "1"
                    ):

                        atributos_ids = (
                            _obtener_ids_atributos_post(
                                request
                            )
                        )

                        # ---------------------------------
                        # VALIDAR IDs
                        # ---------------------------------

                        ids_validos = set(
                            Atributo.objects
                            .filter(
                                pk__in=(
                                    atributos_ids
                                )
                            )
                            .values_list(
                                "pk",
                                flat=True,
                            )
                        )

                        # ---------------------------------
                        # DESACTIVAR NO SELECCIONADOS
                        # ---------------------------------

                        (
                            CategoriaAtributo.objects
                            .filter(
                                categoria=(
                                    categoria_guardada
                                ),
                                activo=True,
                            )
                            .exclude(
                                atributo_id__in=(
                                    ids_validos
                                )
                            )
                            .update(
                                activo=False
                            )
                        )

                        # ---------------------------------
                        # CREAR / REACTIVAR / ORDENAR
                        # ---------------------------------

                        orden = 0

                        for atributo_id in (
                            atributos_ids
                        ):

                            if (
                                atributo_id
                                not in ids_validos
                            ):
                                continue

                            atributo = (
                                Atributo.objects
                                .get(
                                    pk=atributo_id
                                )
                            )

                            requerido = (
                                request.POST.get(
                                    f"requerido_{atributo_id}"
                                )
                                in {
                                    "1",
                                    "true",
                                    "on",
                                    "yes",
                                }
                            )

                            relacion, _ = (
                                CategoriaAtributo.objects
                                .update_or_create(
                                    categoria=(
                                        categoria_guardada
                                    ),
                                    atributo_id=(
                                        atributo_id
                                    ),
                                    defaults={
                                        "activo": True,
                                        "requerido": requerido,
                                        "orden": orden,
                                    },
                                )
                            )

                            relacion.atributo = (
                                atributo
                            )

                            # -----------------------------
                            # OPCIONES DE LISTAS
                            # -----------------------------

                            _sincronizar_opciones_categoria(
                                request,
                                relacion,
                            )

                            orden += 1

                    # =====================================
                    # MENSAJE
                    # =====================================

                    if categoria:
                        messages.success(
                            request,
                            (
                                "Categoría actualizada "
                                "correctamente."
                            ),
                        )

                    else:
                        messages.success(
                            request,
                            (
                                "Categoría creada "
                                "correctamente."
                            ),
                        )

                    return redirect(
                        "categoria_lista"
                    )

            except Exception as error:

                messages.error(
                    request,
                    (
                        "No se pudo guardar "
                        f"la categoría: {error}"
                    ),
                )

    # =====================================================
    # GET
    # =====================================================

    else:

        form = CategoriaForm(
            instance=categoria
        )

    # =====================================================
    # CONFIGURACIÓN PARA TEMPLATE
    # =====================================================

    configuracion_atributos = (
        _construir_configuracion_atributos(
            categoria,
            atributos_catalogo,
        )
    )

    return render(
        request,
        "maestros/categoria_form.html",
        {
            "form": form,
            "categoria": categoria,

            # Compatibilidad con template actual
            "atributos_catalogo": (
                atributos_catalogo
            ),

            "atributos_configurados": (
                atributos_configurados
            ),

            # Nueva estructura inteligente
            "configuracion_atributos": (
                configuracion_atributos
            ),
        },
    )


# =========================================================
# MARCAS - LISTADO
# =========================================================

@permiso_requerido(
    "inventario.view_marcarepuesto"
)
def marca_lista(request):

    q = (
        request.GET
        .get(
            "q",
            "",
        )
        .strip()
    )

    marcas = (
        MarcaRepuesto.objects
        .all()
        .order_by(
            "nombre"
        )
    )

    if q:
        marcas = marcas.filter(
            nombre__icontains=q
        )

    return render(
        request,
        "maestros/marca_lista.html",
        {
            "marcas": marcas,
            "q": q,
        },
    )


# =========================================================
# MARCAS - CREAR / EDITAR
# =========================================================

@login_required
def marca_gestionar(
    request,
    pk=None,
):
    permiso_necesario = (
        "inventario.change_marcarepuesto"
        if pk
        else "inventario.add_marcarepuesto"
    )

    if not request.user.has_perm(
        permiso_necesario
    ):
        messages.error(
            request,
            (
                "No tienes permisos "
                "para gestionar marcas."
            ),
        )

        return redirect(
            "dashboard"
        )

    marca = (
        get_object_or_404(
            MarcaRepuesto,
            pk=pk,
        )
        if pk
        else None
    )

    if request.method == "POST":

        form = MarcaRepuestoForm(
            request.POST,
            instance=marca,
        )

        if form.is_valid():

            form.save()

            if marca:
                messages.success(
                    request,
                    (
                        "Marca actualizada "
                        "correctamente."
                    ),
                )

            else:
                messages.success(
                    request,
                    (
                        "Marca creada "
                        "correctamente."
                    ),
                )

            return redirect(
                "marca_lista"
            )

    else:

        form = MarcaRepuestoForm(
            instance=marca
        )

    return render(
        request,
        "maestros/marca_form.html",
        {
            "form": form,
            "marca": marca,
        },
    )


# =========================================================
# ATRIBUTOS TÉCNICOS - LISTADO
# =========================================================

@permiso_requerido(
    "inventario.view_atributo"
)
def atributo_lista(request):

    q = (
        request.GET
        .get(
            "q",
            "",
        )
        .strip()
    )

    atributos = (
        Atributo.objects
        .all()
        .order_by(
            "nombre",
            "unidad",
        )
    )

    if q:
        atributos = atributos.filter(
            Q(
                nombre__icontains=q
            )
            | Q(
                unidad__icontains=q
            )
            | Q(
                tipo_dato__icontains=q
            )
        )

    return render(
        request,
        "maestros/atributo_lista.html",
        {
            "atributos": atributos,
            "q": q,
        },
    )


# =========================================================
# ATRIBUTOS TÉCNICOS - CREAR / EDITAR
# =========================================================

@login_required
def atributo_gestionar(
    request,
    pk=None,
):
    permiso_necesario = (
        "inventario.change_atributo"
        if pk
        else "inventario.add_atributo"
    )

    if not request.user.has_perm(
        permiso_necesario
    ):
        messages.error(
            request,
            (
                "No tienes permisos "
                "para gestionar atributos."
            ),
        )

        return redirect(
            "dashboard"
        )

    atributo = (
        get_object_or_404(
            Atributo,
            pk=pk,
        )
        if pk
        else None
    )

    if request.method == "POST":

        form = AtributoForm(
            request.POST,
            instance=atributo,
        )

        if form.is_valid():

            atributo_guardado = (
                form.save(
                    commit=False
                )
            )

            if (
                atributo_guardado.tipo_dato
                not in TIPOS_DATO_VALIDOS
            ):
                messages.error(
                    request,
                    (
                        "El tipo de dato "
                        "seleccionado no es válido."
                    ),
                )

            else:
                atributo_guardado.save()

                if atributo:
                    messages.success(
                        request,
                        (
                            "Atributo actualizado "
                            "correctamente."
                        ),
                    )

                else:
                    messages.success(
                        request,
                        (
                            "Atributo creado "
                            "correctamente."
                        ),
                    )

                return redirect(
                    "atributo_lista"
                )

    else:

        form = AtributoForm(
            instance=atributo
        )

    return render(
        request,
        "maestros/atributo_form.html",
        {
            "form": form,
            "atributo": atributo,
        },
    )


# =========================================================
# CREACIÓN RÁPIDA - CATEGORÍA
# =========================================================

@login_required
def categoria_crear_rapida(request):
    """
    Esta API puede seguir existiendo para pantallas
    administrativas.

    NO debe mostrarse en Nuevo repuesto.
    """

    if not request.user.has_perm(
        "inventario.add_categoria"
    ):
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "No tienes permisos."
                ),
            },
            status=403,
        )

    if request.method != "POST":
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Método no permitido."
                ),
            },
            status=405,
        )

    familia_id = (
        request.POST.get(
            "familia"
        )
        or request.POST.get(
            "familia_id"
        )
    )

    nombre = str(
        request.POST.get(
            "nombre",
            "",
        )
        or ""
    ).strip()

    prefijo_sku = str(
        request.POST.get(
            "prefijo_sku",
            "",
        )
        or ""
    ).strip().upper()

    # -----------------------------------------------------
    # VALIDACIONES
    # -----------------------------------------------------

    if not familia_id:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Debe seleccionar una familia."
                ),
            },
            status=400,
        )

    familia = (
        FamiliaProducto.objects
        .filter(
            pk=familia_id
        )
        .first()
    )

    if not familia:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "La familia seleccionada "
                    "no existe."
                ),
            },
            status=400,
        )

    if not nombre:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "El nombre es obligatorio."
                ),
            },
            status=400,
        )

    if not prefijo_sku:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "El prefijo SKU "
                    "es obligatorio."
                ),
            },
            status=400,
        )

    # -----------------------------------------------------
    # DUPLICADO POR NOMBRE
    # -----------------------------------------------------

    existente = (
        Categoria.objects
        .filter(
            nombre__iexact=nombre
        )
        .first()
    )

    if existente:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Ya existe una categoría "
                    "con ese nombre."
                ),
                "id": existente.id,
                "nombre": existente.nombre,
            },
            status=400,
        )

    # -----------------------------------------------------
    # DUPLICADO DE PREFIJO
    # -----------------------------------------------------

    if (
        Categoria.objects
        .filter(
            prefijo_sku__iexact=(
                prefijo_sku
            )
        )
        .exists()
    ):
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Ya existe una categoría "
                    "con ese prefijo SKU."
                ),
            },
            status=400,
        )

    # -----------------------------------------------------
    # CREAR
    # -----------------------------------------------------

    categoria = (
        Categoria.objects
        .create(
            familia=familia,
            nombre=nombre,
            prefijo_sku=prefijo_sku,
        )
    )

    return JsonResponse(
        {
            "ok": True,
            "id": categoria.id,
            "nombre": categoria.nombre,
            "prefijo_sku": (
                categoria.prefijo_sku
            ),
            "familia": {
                "id": familia.id,
                "nombre": familia.nombre,
            },
        }
    )


# =========================================================
# CREACIÓN RÁPIDA - MARCA
# =========================================================

@login_required
def marca_crear_rapida(request):

    if not request.user.has_perm(
        "inventario.add_marcarepuesto"
    ):
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "No tienes permisos."
                ),
            },
            status=403,
        )

    if request.method != "POST":
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Método no permitido."
                ),
            },
            status=405,
        )

    nombre = str(
        request.POST.get(
            "nombre",
            "",
        )
        or ""
    ).strip().upper()

    if not nombre:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "El nombre es obligatorio."
                ),
            },
            status=400,
        )

    existente = (
        MarcaRepuesto.objects
        .filter(
            nombre__iexact=nombre
        )
        .first()
    )

    if existente:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Ya existe una marca "
                    "con ese nombre."
                ),
                "id": existente.id,
                "nombre": existente.nombre,
            },
            status=400,
        )

    marca = (
        MarcaRepuesto.objects
        .create(
            nombre=nombre
        )
    )

    return JsonResponse(
        {
            "ok": True,
            "id": marca.id,
            "nombre": marca.nombre,
        }
    )


# =========================================================
# CREACIÓN RÁPIDA - ATRIBUTO
# =========================================================

@login_required
def atributo_crear_rapido(request):
    """
    Esta API queda disponible solamente
    para usuarios con add_atributo.

    NO debe aparecer en Nuevo repuesto.
    """

    if not request.user.has_perm(
        "inventario.add_atributo"
    ):
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "No tienes permisos."
                ),
            },
            status=403,
        )

    if request.method != "POST":
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Método no permitido."
                ),
            },
            status=405,
        )

    nombre = str(
        request.POST.get(
            "nombre",
            "",
        )
        or ""
    ).strip()

    unidad = str(
        request.POST.get(
            "unidad",
            "",
        )
        or ""
    ).strip()

    tipo_dato = str(
        request.POST.get(
            "tipo_dato",
            "TEXTO",
        )
        or "TEXTO"
    ).strip().upper()

    # -----------------------------------------------------
    # VALIDACIONES
    # -----------------------------------------------------

    if not nombre:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "El nombre es obligatorio."
                ),
            },
            status=400,
        )

    if (
        tipo_dato
        not in TIPOS_DATO_VALIDOS
    ):
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "El tipo de dato "
                    "no es válido."
                ),
            },
            status=400,
        )

    # -----------------------------------------------------
    # BUSCAR DUPLICADO
    # -----------------------------------------------------

    duplicados = (
        Atributo.objects
        .filter(
            nombre__iexact=nombre
        )
    )

    if unidad:
        duplicados = (
            duplicados.filter(
                unidad__iexact=unidad
            )
        )

    else:
        duplicados = (
            duplicados.filter(
                Q(
                    unidad__isnull=True
                )
                | Q(
                    unidad=""
                )
            )
        )

    existente = (
        duplicados.first()
    )

    if existente:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Ya existe un atributo "
                    "igual."
                ),
                "id": existente.id,
                "nombre": str(
                    existente
                ),
            },
            status=400,
        )

    # -----------------------------------------------------
    # CREAR
    # -----------------------------------------------------

    atributo = (
        Atributo.objects
        .create(
            nombre=nombre,
            unidad=(
                unidad or None
            ),
            tipo_dato=tipo_dato,
        )
    )

    return JsonResponse(
        {
            "ok": True,
            "id": atributo.id,
            "nombre": str(
                atributo
            ),
            "tipo_dato": (
                atributo.tipo_dato
            ),
            "unidad": (
                atributo.unidad
                or ""
            ),
        }
    )