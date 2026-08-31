from __future__ import annotations

"""
Firma electrónica XAdES para comprobantes del SRI.

Archivo:
    facturacion/sri/firma_xades.py

Responsabilidad:
    - Leer el XML generado de FacturaVenta.
    - Leer la firma electrónica PKCS#12 (.p12 / .pfx).
    - Extraer clave privada, certificado y cadena.
    - Validar que el certificado esté vigente.
    - Firmar el XML con XAdES de forma enveloped.
    - Verificar localmente la firma generada.
    - Guardar factura.xml_firmado.
    - Cambiar FacturaVenta.estado a FIRMADO.

NO:
    - genera el XML tributario;
    - envía el comprobante al SRI;
    - consulta autorización.

Dependencias:
    pip install "signxml>=5.1,<6" "cryptography>=45"

Notas:
    - El SRI exige firma electrónica XAdES-BES para sus comprobantes.
    - No se debe hacer pretty-print del XML después de firmarlo.
    - La contraseña del .p12/.pfx nunca se registra en logs ni mensajes.
"""

from io import BytesIO
from datetime import datetime, timezone as dt_timezone
from typing import Iterable

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from lxml import etree

from signxml import (
    CanonicalizationMethod,
    DigestAlgorithm,
    SignatureMethod,
    methods,
)
from signxml.xades import (
    XAdESSigner,
    XAdESVerifier,
)

from .excepciones import (
    CertificadoFirmaError,
    EstadoFacturaSRIError,
    FirmaXADESError,
    ValidacionSRIError,
)
from .validaciones import validar_factura_para_firma


# =========================================================
# CONSTANTES
# =========================================================

ID_COMPROBANTE = "comprobante"

# Canonicalización XML 1.0 sin comentarios.
# Es una opción ampliamente interoperable para XMLDSig/XAdES.
C14N_ALGORITHM = (
    CanonicalizationMethod.CANONICAL_XML_1_0
)

# Se usa SHA-256 para firma y digest.
SIGNATURE_ALGORITHM = SignatureMethod.RSA_SHA256
DIGEST_ALGORITHM = DigestAlgorithm.SHA256


# =========================================================
# HELPERS
# =========================================================

def _texto(valor) -> str:
    return "" if valor is None else str(valor).strip()


def _leer_filefield(campo_archivo, nombre: str) -> bytes:
    """
    Lee un FileField sin asumir que el storage es local.

    Funciona tanto con FileSystemStorage como con otros
    backends de almacenamiento compatibles con Django.
    """

    if not campo_archivo:
        raise ValidacionSRIError(
            f"No existe {nombre}."
        )

    try:
        campo_archivo.open("rb")

        try:
            contenido = campo_archivo.read()
        finally:
            campo_archivo.close()

    except Exception as exc:
        raise ValidacionSRIError(
            f"No se pudo leer {nombre}."
        ) from exc

    if not contenido:
        raise ValidacionSRIError(
            f"{nombre.capitalize()} está vacío."
        )

    return contenido


def _crear_parser_seguro() -> etree.XMLParser:
    """
    Parser XML defensivo.

    No resuelve entidades externas, no permite red y no
    carga DTDs.
    """

    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        remove_blank_text=False,
        recover=False,
        huge_tree=False,
    )


def _parsear_xml(xml_bytes: bytes) -> etree._Element:
    if not isinstance(
        xml_bytes,
        (bytes, bytearray),
    ):
        raise ValidacionSRIError(
            "El XML debe recibirse como bytes."
        )

    if not xml_bytes:
        raise ValidacionSRIError(
            "El XML está vacío."
        )

    try:
        parser = _crear_parser_seguro()

        tree = etree.parse(
            BytesIO(bytes(xml_bytes)),
            parser,
        )

    except (
        etree.XMLSyntaxError,
        ValueError,
        TypeError,
    ) as exc:
        raise ValidacionSRIError(
            f"El XML no es válido: {exc}"
        ) from exc

    # Un comprobante SRI no necesita DTD.
    if tree.docinfo.doctype:
        raise ValidacionSRIError(
            "El XML contiene un DOCTYPE. "
            "No se permite firmar XML con DTD."
        )

    root = tree.getroot()

    if root is None:
        raise ValidacionSRIError(
            "No se pudo obtener la raíz del XML."
        )

    return root


def _local_name(elemento: etree._Element) -> str:
    try:
        return etree.QName(elemento).localname
    except Exception:
        tag = _texto(getattr(elemento, "tag", ""))
        return tag.rsplit("}", 1)[-1]


def _buscar_texto(
    root: etree._Element,
    nombre_local: str,
) -> str:
    for nodo in root.iter():
        if _local_name(nodo) == nombre_local:
            return _texto(nodo.text)

    return ""


def _validar_xml_factura(
    root: etree._Element,
    factura=None,
) -> None:
    """
    Valida el vínculo entre el XML y la FacturaVenta antes
    y después de aplicar la firma criptográfica.

    Si se recibe una FacturaVenta, los datos fiscales críticos
    deben existir tanto en el XML como en el snapshot fiscal y
    deben coincidir exactamente.
    """

    if _local_name(root) != "factura":
        raise ValidacionSRIError(
            "El XML no corresponde a una factura."
        )

    id_raiz = _texto(
        root.get("id")
    )

    if id_raiz != ID_COMPROBANTE:
        raise ValidacionSRIError(
            "La raíz <factura> debe contener "
            'id="comprobante".'
        )

    if factura is None:
        return

    clave_factura = _texto(
        getattr(
            factura,
            "clave_acceso",
            "",
        )
    )
    clave_xml = _buscar_texto(
        root,
        "claveAcceso",
    )

    if not clave_factura:
        raise ValidacionSRIError(
            "La factura no tiene clave de acceso."
        )

    if not clave_xml:
        raise ValidacionSRIError(
            "El XML no contiene clave de acceso."
        )

    if clave_xml != clave_factura:
        raise ValidacionSRIError(
            "La clave de acceso del XML no coincide "
            "con la clave de acceso de la factura."
        )

    ruc_factura = _texto(
        getattr(
            factura.empresa,
            "ruc",
            "",
        )
    )
    ruc_xml = _buscar_texto(
        root,
        "ruc",
    )

    if not ruc_factura:
        raise ValidacionSRIError(
            "La empresa emisora no tiene RUC."
        )

    if not ruc_xml:
        raise ValidacionSRIError(
            "El XML no contiene el RUC del emisor."
        )

    if ruc_xml != ruc_factura:
        raise ValidacionSRIError(
            "El RUC emisor del XML no coincide "
            "con la empresa de la factura."
        )

    ambiente_factura = _texto(
        getattr(
            factura,
            "ambiente",
            "",
        )
    )
    ambiente_xml = _buscar_texto(
        root,
        "ambiente",
    )

    if not ambiente_xml:
        raise ValidacionSRIError(
            "El XML no contiene el ambiente."
        )

    if ambiente_xml != ambiente_factura:
        raise ValidacionSRIError(
            "El ambiente del XML no coincide "
            "con el ambiente de la factura."
        )

    establecimiento_factura = _texto(
        getattr(
            factura,
            "establecimiento",
            "",
        )
    )
    establecimiento_xml = _buscar_texto(
        root,
        "estab",
    )

    if not establecimiento_xml:
        raise ValidacionSRIError(
            "El XML no contiene el establecimiento."
        )

    if establecimiento_xml != establecimiento_factura:
        raise ValidacionSRIError(
            "El establecimiento del XML no coincide "
            "con la factura."
        )

    punto_emision_factura = _texto(
        getattr(
            factura,
            "punto_emision",
            "",
        )
    )
    punto_emision_xml = _buscar_texto(
        root,
        "ptoEmi",
    )

    if not punto_emision_xml:
        raise ValidacionSRIError(
            "El XML no contiene el punto de emisión."
        )

    if punto_emision_xml != punto_emision_factura:
        raise ValidacionSRIError(
            "El punto de emisión del XML no coincide "
            "con la factura."
        )

    secuencial_factura = _texto(
        getattr(
            factura,
            "secuencial",
            "",
        )
    )
    secuencial_xml = _buscar_texto(
        root,
        "secuencial",
    )

    if not secuencial_xml:
        raise ValidacionSRIError(
            "El XML no contiene el secuencial."
        )

    if secuencial_xml != secuencial_factura:
        raise ValidacionSRIError(
            "El secuencial del XML no coincide "
            "con la factura."
        )


def _validar_firma_modelo(
    firma,
    factura=None,
) -> None:
    if firma is None:
        raise CertificadoFirmaError(
            "No hay firma electrónica asignada."
        )

    if not getattr(
        firma,
        "archivo_firma",
        None,
    ):
        raise CertificadoFirmaError(
            "La firma electrónica no tiene "
            "archivo .p12/.pfx."
        )

    if not _texto(
        getattr(
            firma,
            "password_firma",
            "",
        )
    ):
        raise CertificadoFirmaError(
            "La firma electrónica no tiene "
            "contraseña configurada."
        )

    if hasattr(
        firma,
        "esta_vigente",
    ):
        if not firma.esta_vigente():
            raise CertificadoFirmaError(
                "La firma electrónica no está "
                "activa o vigente."
            )

    if factura is not None:
        if (
            firma.empresa_id
            != factura.empresa_id
        ):
            raise CertificadoFirmaError(
                "La firma electrónica no pertenece "
                "a la empresa emisora de la factura."
            )

        ruc_firma = _texto(
            getattr(
                firma,
                "ruc",
                "",
            )
        )

        ruc_empresa = _texto(
            getattr(
                factura.empresa,
                "ruc",
                "",
            )
        )

        if (
            ruc_firma
            and ruc_empresa
            and ruc_firma != ruc_empresa
        ):
            raise CertificadoFirmaError(
                "El RUC configurado en la firma "
                "no coincide con el RUC emisor."
            )


def _cargar_pkcs12(
    contenido: bytes,
    password: str,
) -> tuple[
    rsa.RSAPrivateKey,
    x509.Certificate,
    list[x509.Certificate],
]:
    """
    Abre el PKCS#12 y devuelve:
        clave privada,
        certificado del firmante,
        certificados adicionales.
    """

    password_bytes = password.encode(
        "utf-8"
    )

    try:
        private_key, certificate, extras = (
            pkcs12.load_key_and_certificates(
                contenido,
                password_bytes,
            )
        )

    except Exception as exc:
        # No propagamos datos sensibles ni la contraseña.
        raise CertificadoFirmaError(
            "No se pudo abrir el archivo .p12/.pfx. "
            "Verifica que el archivo y la contraseña "
            "sean correctos."
        ) from exc

    if private_key is None:
        raise CertificadoFirmaError(
            "El archivo de firma no contiene "
            "una clave privada."
        )

    if certificate is None:
        raise CertificadoFirmaError(
            "El archivo de firma no contiene "
            "un certificado X.509."
        )

    # Para esta implementación orientada al SRI
    # se requiere una clave RSA.
    if not isinstance(
        private_key,
        rsa.RSAPrivateKey,
    ):
        raise CertificadoFirmaError(
            "El certificado usa un tipo de clave "
            "no soportado por esta implementación. "
            "Se requiere una clave RSA."
        )

    extras_lista = list(
        extras or []
    )

    return (
        private_key,
        certificate,
        extras_lista,
    )


def _validar_vigencia_certificado(
    certificado: x509.Certificate,
) -> None:
    ahora = datetime.now(
        dt_timezone.utc
    )

    # cryptography >= 42 expone estas propiedades UTC.
    inicio = (
        certificado.not_valid_before_utc
    )

    fin = (
        certificado.not_valid_after_utc
    )

    if ahora < inicio:
        raise CertificadoFirmaError(
            "El certificado todavía no está vigente."
        )

    if ahora > fin:
        raise CertificadoFirmaError(
            "El certificado está vencido."
        )


def _cadena_certificados(
    certificado: x509.Certificate,
    adicionales: Iterable[x509.Certificate],
) -> list[x509.Certificate]:
    """
    SignXML admite el certificado del firmante más
    certificados intermedios.
    """

    resultado = [
        certificado
    ]

    huellas = {
        certificado.fingerprint(
            hashes.SHA256()
        )
    }

    for cert in adicionales:
        huella = cert.fingerprint(
            hashes.SHA256()
        )

        if huella in huellas:
            continue

        huellas.add(
            huella
        )

        resultado.append(
            cert
        )

    return resultado


def _huella_sha256(
    certificado: x509.Certificate,
) -> str:
    return certificado.fingerprint(
        hashes.SHA256()
    ).hex().upper()


# =========================================================
# FIRMA XAdES
# =========================================================

def firmar_xml_xades(
    xml_bytes: bytes,
    firma_electronica,
    *,
    factura=None,
) -> tuple[
    bytes,
    x509.Certificate,
]:
    """
    Firma un XML de factura usando el .p12/.pfx almacenado
    en FirmaElectronica.

    Devuelve:
        (xml_firmado_bytes, certificado_firmante)

    Esta función NO guarda nada en base de datos.
    """

    _validar_firma_modelo(
        firma_electronica,
        factura=factura,
    )

    root = _parsear_xml(
        xml_bytes
    )

    _validar_xml_factura(
        root,
        factura=factura,
    )

    contenido_pkcs12 = (
        _leer_filefield(
            firma_electronica.archivo_firma,
            "el archivo de firma electrónica",
        )
    )

    (
        private_key,
        certificado,
        certificados_adicionales,
    ) = _cargar_pkcs12(
        contenido_pkcs12,
        firma_electronica.password_firma,
    )

    _validar_vigencia_certificado(
        certificado
    )

    cadena = _cadena_certificados(
        certificado,
        certificados_adicionales,
    )

    try:
        signer = XAdESSigner(
            method=methods.enveloped,
            signature_algorithm=(
                SIGNATURE_ALGORITHM
            ),
            digest_algorithm=(
                DIGEST_ALGORITHM
            ),
            c14n_algorithm=(
                C14N_ALGORITHM
            ),
        )

        # XAdES-BES tradicional usa SigningCertificate.
        # SignXML actual usa SigningCertificateV2 por defecto;
        # esta opción conserva la forma legacy para mejorar
        # interoperabilidad con validadores que esperan el
        # perfil XAdES-BES clásico.
        signer.use_deprecated_legacy_signing_certificate = (
            True
        )

        signed_root = signer.sign(
            root,
            key=private_key,
            cert=cadena,
            reference_uri=(
                f"#{ID_COMPROBANTE}"
            ),
            id_attribute="id",
            always_add_key_value=False,
        )

    except Exception as exc:
        raise FirmaXADESError(
            "No se pudo generar la firma XAdES "
            "del comprobante."
        ) from exc

    # -----------------------------------------------------
    # VERIFICACIÓN LOCAL
    # -----------------------------------------------------

    try:
        XAdESVerifier().verify(
            signed_root,
            x509_cert=certificado,
        )

    except Exception as exc:
        raise FirmaXADESError(
            "La firma XAdES fue generada, pero "
            "falló la verificación criptográfica local."
        ) from exc

    try:
        xml_firmado = etree.tostring(
            signed_root,
            encoding="UTF-8",
            xml_declaration=True,
            pretty_print=False,
        )

    except Exception as exc:
        raise FirmaXADESError(
            "No se pudo serializar el XML firmado."
        ) from exc

    if not xml_firmado:
        raise FirmaXADESError(
            "El resultado de la firma está vacío."
        )

    root_final = _parsear_xml(
        xml_firmado
    )

    _validar_xml_factura(
        root_final,
        factura=factura,
    )

    return (
        xml_firmado,
        certificado,
    )


# =========================================================
# INTEGRACIÓN CON FacturaVenta
# =========================================================

def _validar_factura_para_firma(
    factura,
) -> None:
    """
    Mantiene una única puerta de validación para la firma.

    Las reglas tributarias/estado se centralizan en
    sri.validaciones.validar_factura_para_firma().
    Aquí únicamente añadimos la comprobación específica del
    certificado que utilizará este módulo.
    """
    validar_factura_para_firma(
        factura
    )

    _validar_firma_modelo(
        factura.firma_electronica,
        factura=factura,
    )


@transaction.atomic
def firmar_factura(
    factura,
):
    """
    Firma factura.xml_generado y guarda factura.xml_firmado.

    Flujo:
        GENERADO
            ↓
        firma XAdES
            ↓
        verificación local
            ↓
        guarda xml_firmado
            ↓
        FIRMADO
    """

    if factura is None or not getattr(factura, "pk", None):
        raise ValidacionSRIError(
            "La factura debe existir y estar guardada."
        )

    factura = (
        factura.__class__.objects
        .select_for_update()
        .select_related(
            "empresa",
            "firma_electronica",
        )
        .get(pk=factura.pk)
    )

    _validar_factura_para_firma(
        factura
    )

    firma = (
        factura.firma_electronica
    )

    try:
        xml_original = _leer_filefield(
            factura.xml_generado,
            "el XML generado",
        )

        (
            xml_firmado,
            certificado,
        ) = firmar_xml_xades(
            xml_original,
            firma,
            factura=factura,
        )

        huella = _huella_sha256(
            certificado
        )

        nombre = (
            f"{factura.clave_acceso}"
            "_firmado.xml"
        )

        factura.xml_firmado.save(
            nombre,
            ContentFile(
                xml_firmado
            ),
            save=False,
        )

        factura.estado = "FIRMADO"
        factura.fecha_firma = (
            timezone.now()
        )
        factura.huella_firma = (
            huella
        )
        factura.mensaje_firma = (
            "XML firmado electrónicamente "
            "con XAdES y verificado localmente."
        )

        factura.save(
            update_fields=[
                "xml_firmado",
                "estado",
                "fecha_firma",
                "huella_firma",
                "mensaje_firma",
                "updated_at",
            ]
        )

        factura.refresh_from_db()

        return factura

    except (
        FirmaXADESError,
        CertificadoFirmaError,
        ValidacionSRIError,
        EstadoFacturaSRIError,
    ) as exc:

        try:
            factura.marcar_error_firma(
                str(exc)
            )
        except Exception:
            pass

        raise

    except ValidationError as exc:

        try:
            factura.marcar_error_firma(
                str(exc)
            )
        except Exception:
            pass

        raise ValidacionSRIError(
            str(exc)
        ) from exc

    except Exception as exc:

        mensaje = (
            "Ocurrió un error inesperado "
            "durante la firma electrónica."
        )

        try:
            factura.marcar_error_firma(
                mensaje
            )
        except Exception:
            pass

        raise FirmaXADESError(
            mensaje
        ) from exc


# =========================================================
# UTILIDADES DE DIAGNÓSTICO
# =========================================================

def informacion_certificado(
    firma_electronica,
) -> dict:
    """
    Comprueba un .p12/.pfx sin firmar una factura.

    No devuelve la clave privada ni la contraseña.
    """

    _validar_firma_modelo(
        firma_electronica
    )

    contenido = _leer_filefield(
        firma_electronica.archivo_firma,
        "el archivo de firma electrónica",
    )

    (
        _private_key,
        certificado,
        adicionales,
    ) = _cargar_pkcs12(
        contenido,
        firma_electronica.password_firma,
    )

    _validar_vigencia_certificado(
        certificado
    )

    return {
        "subject":
            certificado.subject.rfc4514_string(),

        "issuer":
            certificado.issuer.rfc4514_string(),

        "serial_number":
            str(certificado.serial_number),

        "not_valid_before":
            certificado.not_valid_before_utc,

        "not_valid_after":
            certificado.not_valid_after_utc,

        "sha256":
            _huella_sha256(
                certificado
            ),

        "certificados_adicionales":
            len(adicionales),
    }


__all__ = [
    "firmar_xml_xades",
    "firmar_factura",
    "informacion_certificado",
]