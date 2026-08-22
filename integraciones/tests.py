import json
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ordenes_de_trabajo.models import Sucursal

from .models import CodigoAccesoAsistente
from .services import (
    CodigoSSOInvalido,
    canjear_codigo_sso,
    generar_codigo_sso,
)


User = get_user_model()


class BaseSSOTestCase(TestCase):

    def setUp(self):
        self.sucursal = Sucursal.objects.create(
            codigo="NORTE",
            nombre="MAO Norte",
            activa=True,
        )

        self.usuario = User.objects.create_user(
            username="salvador",
            password="password-prueba",
            first_name="Salvador",
            last_name="Ortega",
            sucursal=self.sucursal,
        )


# =========================================================
# SERVICIO SSO
# =========================================================


class CodigoSSOServiceTests(BaseSSOTestCase):

    def test_generar_codigo_guarda_solo_hash(self):
        codigo, registro = generar_codigo_sso(
            self.usuario
        )

        self.assertTrue(codigo)

        self.assertNotEqual(
            registro.codigo_hash,
            codigo,
        )

        self.assertEqual(
            registro.codigo_hash,
            CodigoAccesoAsistente.calcular_hash(
                codigo
            ),
        )

        self.assertIsNone(
            registro.usado_en
        )

        self.assertTrue(
            registro.expira_en > timezone.now()
        )

    def test_canjear_codigo_valido_devuelve_identidad(self):
        codigo, registro = generar_codigo_sso(
            self.usuario
        )

        identidad = canjear_codigo_sso(
            codigo
        )

        self.assertEqual(
            identidad["erp_user_id"],
            self.usuario.pk,
        )

        self.assertEqual(
            identidad["username"],
            "salvador",
        )

        self.assertEqual(
            identidad["first_name"],
            "Salvador",
        )

        self.assertEqual(
            identidad["last_name"],
            "Ortega",
        )

        self.assertTrue(
            identidad["activo"]
        )

        self.assertEqual(
            identidad["sucursal"]["erp_sucursal_id"],
            self.sucursal.pk,
        )

        self.assertEqual(
            identidad["sucursal"]["codigo"],
            "NORTE",
        )

        registro.refresh_from_db()

        self.assertIsNotNone(
            registro.usado_en
        )

    def test_codigo_es_de_un_solo_uso(self):
        codigo, registro = generar_codigo_sso(
            self.usuario
        )

        canjear_codigo_sso(
            codigo
        )

        with self.assertRaises(
            CodigoSSOInvalido
        ):
            canjear_codigo_sso(
                codigo
            )

        registro.refresh_from_db()

        self.assertIsNotNone(
            registro.usado_en
        )

    def test_codigo_expirado_es_rechazado(self):
        codigo, registro = generar_codigo_sso(
            self.usuario
        )

        registro.expira_en = (
            timezone.now()
            - timedelta(seconds=1)
        )

        registro.save(
            update_fields=[
                "expira_en",
            ]
        )

        with self.assertRaises(
            CodigoSSOInvalido
        ):
            canjear_codigo_sso(
                codigo
            )

    def test_codigo_inexistente_es_rechazado(self):
        with self.assertRaises(
            CodigoSSOInvalido
        ):
            canjear_codigo_sso(
                "codigo-que-no-existe"
            )

    def test_usuario_inactivo_es_rechazado_y_codigo_se_consume(self):
        codigo, registro = generar_codigo_sso(
            self.usuario
        )

        # El usuario estaba activo cuando obtuvo el código,
        # pero fue desactivado antes de utilizarlo.
        self.usuario.is_active = False

        self.usuario.save(
            update_fields=[
                "is_active",
            ]
        )

        with self.assertRaises(
            CodigoSSOInvalido
        ):
            canjear_codigo_sso(
                codigo
            )

        registro.refresh_from_db()

        # Es fundamental que el código quede consumido.
        self.assertIsNotNone(
            registro.usado_en
        )

    def test_no_genera_codigo_para_usuario_inactivo(self):
        self.usuario.is_active = False

        self.usuario.save(
            update_fields=[
                "is_active",
            ]
        )

        with self.assertRaises(
            ValueError
        ):
            generar_codigo_sso(
                self.usuario
            )


# =========================================================
# ENDPOINT SERVER-TO-SERVER
# =========================================================


@override_settings(
    MAO_ASISTENTE_HABILITADO=True,
    ASISTENTE_SSO_EXCHANGE_SECRET="secreto-prueba-sso",
)
class CanjeSSOEndpointTests(BaseSSOTestCase):

    def setUp(self):
        super().setUp()

        self.url = reverse(
            "integraciones:canjear_codigo_asistente"
        )

    def test_secret_incorrecto_devuelve_401(self):
        codigo, _ = generar_codigo_sso(
            self.usuario
        )

        response = self.client.post(
            self.url,
            data=json.dumps(
                {
                    "code": codigo,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=(
                "Bearer secreto-incorrecto"
            ),
        )

        self.assertEqual(
            response.status_code,
            401,
        )

    def test_sin_secret_devuelve_401(self):
        codigo, _ = generar_codigo_sso(
            self.usuario
        )

        response = self.client.post(
            self.url,
            data=json.dumps(
                {
                    "code": codigo,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            401,
        )

    def test_secret_correcto_y_codigo_valido_devuelve_identidad(self):
        codigo, registro = generar_codigo_sso(
            self.usuario
        )

        response = self.client.post(
            self.url,
            data=json.dumps(
                {
                    "code": codigo,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=(
                "Bearer secreto-prueba-sso"
            ),
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        payload = response.json()

        self.assertTrue(
            payload["ok"]
        )

        self.assertEqual(
            payload["identidad"]["erp_user_id"],
            self.usuario.pk,
        )

        self.assertEqual(
            payload["identidad"]["username"],
            "salvador",
        )

        self.assertEqual(
            payload["identidad"]["sucursal"]["codigo"],
            "NORTE",
        )

        registro.refresh_from_db()

        self.assertIsNotNone(
            registro.usado_en
        )

    def test_codigo_invalido_devuelve_400_generico(self):
        response = self.client.post(
            self.url,
            data=json.dumps(
                {
                    "code": "codigo-invalido",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=(
                "Bearer secreto-prueba-sso"
            ),
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        payload = response.json()

        self.assertFalse(
            payload["ok"]
        )

        self.assertEqual(
            payload["error"],
            "Código inválido o vencido.",
        )

    def test_json_invalido_devuelve_400(self):
        response = self.client.post(
            self.url,
            data="{json-invalido",
            content_type="application/json",
            HTTP_AUTHORIZATION=(
                "Bearer secreto-prueba-sso"
            ),
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        payload = response.json()

        self.assertFalse(
            payload["ok"]
        )

        self.assertEqual(
            payload["error"],
            "Solicitud inválida.",
        )

    def test_json_valido_pero_no_objeto_devuelve_400(self):
        """
        JSON válido como [] no debe provocar un error 500.

        El endpoint SSO espera un objeto JSON que pueda contener
        la propiedad "code".
        """

        response = self.client.post(
            self.url,
            data=json.dumps([]),
            content_type="application/json",
            HTTP_AUTHORIZATION=(
                "Bearer secreto-prueba-sso"
            ),
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        payload = response.json()

        self.assertFalse(
            payload["ok"]
        )

        self.assertEqual(
            payload["error"],
            "Solicitud inválida.",
        )


# =========================================================
# ENTRADA DESDE EL ERP
# =========================================================


@override_settings(
    DEBUG=True,
    MAO_ASISTENTE_HABILITADO=True,
    ASISTENTE_SSO_CALLBACK_URL=(
        "http://127.0.0.1:8001/"
        "integraciones/mao-erp/sso/entrada/"
    ),
)
class EntradaAsistenteTests(BaseSSOTestCase):

    def setUp(self):
        super().setUp()

        self.url = reverse(
            "integraciones:entrar_asistente"
        )

    def test_usuario_anonimo_es_enviado_al_login(self):
        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertIn(
            settings.LOGIN_URL,
            response.url,
        )

    def test_usuario_autenticado_recibe_redireccion_con_codigo(self):
        self.client.force_login(
            self.usuario
        )

        session = self.client.session
        session["sucursal_activa_id"] = self.sucursal.pk
        session.save()

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        parsed = urlparse(
            response.url
        )

        parametros = parse_qs(
            parsed.query
        )

        self.assertIn(
            "code",
            parametros,
        )

        codigo = parametros[
            "code"
        ][0]

        self.assertTrue(
            codigo
        )

        codigo_hash = (
            CodigoAccesoAsistente.calcular_hash(
                codigo
            )
        )

        registro = CodigoAccesoAsistente.objects.get(
            usuario=self.usuario,
            codigo_hash=codigo_hash,
            usado_en__isnull=True,
        )

        # Ahora también verificamos que el código SSO
        # haya conservado la sucursal operativa activa.
        self.assertEqual(
            registro.sucursal_id,
            self.sucursal.pk,
        )

        # El código original jamás debe almacenarse.
        self.assertFalse(
            CodigoAccesoAsistente.objects.filter(
                codigo_hash=codigo
            ).exists()
        )