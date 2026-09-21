from datetime import datetime
from io import BytesIO

from django.core.files.base import ContentFile
from django.utils import timezone

from PIL import (
    Image,
    ImageDraw,
    ImageFont,
    ImageOps,
)


# =========================================================
# NOMBRES DE MARCACIONES
# =========================================================

NOMBRES_MARCACION = {
    "ENTRADA": "ENTRADA",
    "INICIO_ALMUERZO": "INICIO DE ALMUERZO",
    "FIN_ALMUERZO": "FIN DE ALMUERZO",
    "SALIDA": "SALIDA",
}


# =========================================================
# FUENTES
# =========================================================

def _cargar_fuente(
    tamano,
    negrita=False,
):
    """
    Intenta utilizar una fuente disponible tanto
    en Windows como en Ubuntu.

    Si ninguna existe, usa la fuente por defecto.
    """

    candidatos = []

    if negrita:

        candidatos = [
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "DejaVuSans-Bold.ttf",
        ]

    else:

        candidatos = [
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "DejaVuSans.ttf",
        ]

    for ruta in candidatos:

        try:

            return ImageFont.truetype(
                ruta,
                tamano,
            )

        except Exception:

            continue

    return ImageFont.load_default()


# =========================================================
# FECHA Y HORA QUE APARECERÁ EN LA FOTO
# =========================================================

def _obtener_fecha_hora_registro(
    registro,
):
    """
    ONLINE:
        usa la fecha/hora registrada por Django.

    OFFLINE:
        usa fecha_hora_dispositivo, porque esa fue
        la hora capturada por la terminal.
    """

    # =====================================================
    # OFFLINE
    # =====================================================

    if getattr(
        registro,
        "es_offline",
        False,
    ):

        fecha_hora_dispositivo = getattr(
            registro,
            "fecha_hora_dispositivo",
            None,
        )

        if fecha_hora_dispositivo:

            if timezone.is_aware(
                fecha_hora_dispositivo
            ):

                return timezone.localtime(
                    fecha_hora_dispositivo
                )

            return timezone.make_aware(
                fecha_hora_dispositivo,
                timezone.get_current_timezone(),
            )

    # =====================================================
    # FECHA/HORA SEPARADAS
    # =====================================================

    fecha = getattr(
        registro,
        "fecha",
        None,
    )

    hora = getattr(
        registro,
        "hora",
        None,
    )

    if fecha and hora:

        fecha_hora = datetime.combine(
            fecha,
            hora,
        )

        if timezone.is_naive(
            fecha_hora
        ):

            fecha_hora = timezone.make_aware(
                fecha_hora,
                timezone.get_current_timezone(),
            )

        return timezone.localtime(
            fecha_hora
        )

    # =====================================================
    # FALLBACK
    # =====================================================

    return timezone.localtime(
        timezone.now()
    )


# =========================================================
# DATOS DEL REGISTRO
# =========================================================

def _obtener_nombre_usuario(
    registro,
):

    usuario = getattr(
        registro,
        "usuario",
        None,
    )

    if not usuario:

        return "Trabajador"

    try:

        nombre = (
            usuario.get_full_name()
            .strip()
        )

        if nombre:
            return nombre

    except Exception:
        pass

    return getattr(
        usuario,
        "username",
        "Trabajador",
    )


def _obtener_nombre_sucursal(
    registro,
):

    sucursal = getattr(
        registro,
        "sucursal",
        None,
    )

    if not sucursal:

        return "MAO"

    nombre = getattr(
        sucursal,
        "nombre",
        None,
    )

    if nombre:
        return str(
            nombre
        )

    codigo = getattr(
        sucursal,
        "codigo",
        None,
    )

    if codigo:
        return str(
            codigo
        )

    return "MAO"


# =========================================================
# SELLAR FOTOGRAFÍA
# =========================================================

def preparar_fotografia_sellada(
    registro,
    fotografia,
):
    """
    Recibe la foto subida por la terminal y devuelve
    una nueva fotografía JPEG con marca de agua.

    NO modifica todavía el ImageField del modelo.
    """

    fotografia.seek(
        0
    )

    with Image.open(
        fotografia
    ) as imagen_original:

        # =================================================
        # CORREGIR ORIENTACIÓN EXIF
        # =================================================

        imagen = ImageOps.exif_transpose(
            imagen_original
        )

        # =================================================
        # RGB
        # =================================================

        if imagen.mode != "RGB":

            imagen = imagen.convert(
                "RGB"
            )

        ancho, alto = imagen.size

        # =================================================
        # TAMAÑOS RESPONSIVOS
        # =================================================

        escala = max(
            1.0,
            ancho / 1280.0,
        )

        margen = int(
            24 * escala
        )

        separacion = int(
            7 * escala
        )

        fuente_titulo = _cargar_fuente(
            int(
                28 * escala
            ),
            negrita=True,
        )

        fuente_normal = _cargar_fuente(
            int(
                20 * escala
            ),
            negrita=False,
        )

        fuente_pequena = _cargar_fuente(
            int(
                17 * escala
            ),
            negrita=False,
        )

        # =================================================
        # INFORMACIÓN
        # =================================================

        tipo = getattr(
            registro,
            "tipo",
            "",
        )

        tipo_texto = NOMBRES_MARCACION.get(
            tipo,
            str(
                tipo
            ).replace(
                "_",
                " ",
            ),
        )

        es_offline = bool(
            getattr(
                registro,
                "es_offline",
                False,
            )
        )

        modo = (
            " | OFFLINE"
            if es_offline
            else ""
        )

        fecha_hora = (
            _obtener_fecha_hora_registro(
                registro
            )
        )

        sucursal = (
            _obtener_nombre_sucursal(
                registro
            )
        )

        nombre = (
            _obtener_nombre_usuario(
                registro
            )
        )

        uuid_registro = str(
            getattr(
                registro,
                "uuid_marcacion",
                "",
            )
        )

        referencia = (
            uuid_registro.split(
                "-"
            )[0]
            if uuid_registro
            else "SIN-REF"
        )

        linea_1 = (
            f"MAO | {tipo_texto}{modo}"
        )

        linea_2 = (
            f"{fecha_hora:%d/%m/%Y} | "
            f"{fecha_hora:%H:%M:%S} | "
            f"{sucursal}"
        )

        linea_3 = (
            f"{nombre} | Ref: {referencia}"
        )

        # =================================================
        # CALCULAR ALTURA DE LA FRANJA
        # =================================================

        medicion = ImageDraw.Draw(
            imagen
        )

        bbox_1 = medicion.textbbox(
            (0, 0),
            linea_1,
            font=fuente_titulo,
        )

        bbox_2 = medicion.textbbox(
            (0, 0),
            linea_2,
            font=fuente_normal,
        )

        bbox_3 = medicion.textbbox(
            (0, 0),
            linea_3,
            font=fuente_pequena,
        )

        alto_1 = (
            bbox_1[3]
            - bbox_1[1]
        )

        alto_2 = (
            bbox_2[3]
            - bbox_2[1]
        )

        alto_3 = (
            bbox_3[3]
            - bbox_3[1]
        )

        alto_franja = (
            margen
            + alto_1
            + separacion
            + alto_2
            + separacion
            + alto_3
            + margen
        )

        # =================================================
        # OVERLAY SEMITRANSPARENTE
        # =================================================

        imagen_rgba = imagen.convert(
            "RGBA"
        )

        overlay = Image.new(
            "RGBA",
            imagen_rgba.size,
            (
                0,
                0,
                0,
                0,
            ),
        )

        dibujar = ImageDraw.Draw(
            overlay
        )

        inicio_y = (
            alto
            - alto_franja
        )

        dibujar.rectangle(
            (
                0,
                inicio_y,
                ancho,
                alto,
            ),
            fill=(
                0,
                0,
                0,
                185,
            ),
        )

        # =================================================
        # TEXTO
        # =================================================

        x = margen

        y = (
            inicio_y
            + margen
        )

        dibujar.text(
            (
                x,
                y,
            ),
            linea_1,
            font=fuente_titulo,
            fill=(
                255,
                255,
                255,
                255,
            ),
        )

        y += (
            alto_1
            + separacion
        )

        dibujar.text(
            (
                x,
                y,
            ),
            linea_2,
            font=fuente_normal,
            fill=(
                255,
                255,
                255,
                255,
            ),
        )

        y += (
            alto_2
            + separacion
        )

        dibujar.text(
            (
                x,
                y,
            ),
            linea_3,
            font=fuente_pequena,
            fill=(
                220,
                220,
                220,
                255,
            ),
        )

        # =================================================
        # COMBINAR
        # =================================================

        resultado = Image.alpha_composite(
            imagen_rgba,
            overlay,
        ).convert(
            "RGB"
        )

        # =================================================
        # JPEG
        # =================================================

        salida = BytesIO()

        resultado.save(
            salida,
            format="JPEG",
            quality=90,
            optimize=True,
        )

        salida.seek(
            0
        )

        nombre = (
            f"{registro.uuid_marcacion}.jpg"
        )

        contenido = ContentFile(
            salida.read(),
            name=nombre,
        )

        return (
            nombre,
            contenido,
        )