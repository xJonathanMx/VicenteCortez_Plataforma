"""
Casos del Plan de Pruebas C2 (CP-01 a CP-16) que se pueden automatizar.
Cada clase lleva el ID del caso para citarla como evidencia en el documento.
    python manage.py test core.test_plan_c2 -v 2
"""
from datetime import timedelta
from pathlib import Path
from unittest import mock
import re
import subprocess

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core import rut
from core.forms import CampoRun
from core.models import (Cliente, Comision, DetalleAtencionServicio, EnvioMensaje, HistoricoEstadoCliente, Servicio,
                         Usuario, Valoracion)
from core.tests import CLAVE, Base
from fichas import servicios as fs
from seguimiento.servicios import procesar_pendientes


class CP01ValidacionRunTests(TestCase):
    """CP-01 · Unitaria · RF-C-02, RNF Integridad-04."""

    def test_acepta_run_valido(self):
        for valor in ["12.345.678-5", "12345678-5", "123456785", "11.111.111-1"]:
            self.assertTrue(rut.es_valido(valor), valor)
        self.assertEqual(CampoRun().clean("12.345.678-5"), ("12345678", "5"))

    def test_rechaza_invalidos(self):
        for valor in ["12313212", "", None, "abc", "12.345.678-9", "1-9"]:
            self.assertFalse(rut.es_valido(valor), repr(valor))

    def test_mensaje_claro(self):
        for valor in ["12313212", "abc"]:
            with self.assertRaisesMessage(ValidationError, "El RUN no es válido"):
                CampoRun().clean(valor)
        with self.assertRaises(ValidationError):  # vacío en un campo obligatorio
            CampoRun().clean("")


class CP02PrecioComisionCongeladosTests(Base):
    """CP-02 · Unitaria · RF-FA-11."""

    def test_ficha_anterior_conserva_y_nueva_usa_valores_vigentes(self):
        servicio = Servicio.objects.get(nombre="Corte tradicional")
        contrato = self.pelu.contrato
        self.assertTrue(self.pelu.cobra_comision)  # peluquero externo
        Servicio.objects.filter(pk=servicio.pk).update(precio=20000)
        Comision.objects.update_or_create(tipo_servicio=servicio.tipo, contrato=contrato,
                                          defaults={"porcentaje": 40})
        servicio.refresh_from_db()

        antigua = fs.agregar_servicio(fs.abrir_ficha(self.admin, self.cliente), servicio, self.pelu, "basico",
                                      self.admin)
        self.assertEqual((antigua.precio_cobrado, float(antigua.porc_comision_guardado)), (20000, 40.0))
        self.assertEqual(antigua.precio_cobrado * antigua.porc_comision_guardado / 100, 8000)

        Servicio.objects.filter(pk=servicio.pk).update(precio=25000)
        Comision.objects.filter(tipo_servicio=servicio.tipo, contrato=contrato).update(porcentaje=50)
        servicio.refresh_from_db()

        antigua.refresh_from_db()
        self.assertEqual((antigua.precio_cobrado, float(antigua.porc_comision_guardado)), (20000, 40.0))
        # La atención anterior ya terminó: un cliente no puede tener dos fichas abiertas a la vez.
        type(antigua.ficha).objects.filter(pk=antigua.ficha_id).update(estado_id="validada")
        nueva = fs.agregar_servicio(fs.abrir_ficha(self.admin, self.cliente), servicio, self.pelu, "basico",
                                    self.admin)
        self.assertEqual((nueva.precio_cobrado, float(nueva.porc_comision_guardado)), (25000, 50.0))


class CP04FichaVariosServiciosTests(Base):
    """CP-04 · Integración · RF-FA-01, RF-FA-07, RF-FA-08, RF-ES-01."""

    def test_dos_servicios_con_horas_precio_y_comision(self):
        habilitados = list(Servicio.objects.filter(habilitados__usuario=self.pelu, habilitados__activo=True,
                                                   activo=True).distinct()[:2])
        self.assertEqual(len(habilitados), 2, "el peluquero demo necesita dos servicios habilitados")
        self.entrar(self.pelu)
        r = self.client.post(reverse("fichas:nueva"), {"cliente": self.cliente.run_formateado})
        ficha = self.cliente.fichas.latest("pk")
        self.assertRedirects(r, reverse("fichas:detalle", args=[ficha.pk]))

        for servicio in habilitados:  # se atienden de a uno
            self.client.post(reverse("fichas:agregar_servicio", args=[ficha.pk]), {
                "servicio": servicio.pk, "variante": "basico", "peluquero": self.pelu.pk, "sesiones_totales": 1})
            d = DetalleAtencionServicio.objects.get(ficha=ficha, servicio=servicio)
            self.client.post(reverse("fichas:iniciar", args=[d.pk]), {"confirmar": "1"})
            d.refresh_from_db()
            self.assertEqual(d.estado, "en_proceso")
            self.assertIsNotNone(d.hora_inicio)
            self.client.post(reverse("fichas:terminar", args=[d.pk]))
            d.refresh_from_db()
            self.assertEqual(d.estado, "terminado")
            self.assertGreaterEqual(d.hora_termino, d.hora_inicio)
            self.assertEqual(d.peluquero, self.pelu)
            self.assertEqual(d.precio_cobrado, servicio.precio_de("basico"))
            self.assertEqual(d.porc_comision_guardado, servicio.tipo.porcentaje_para(self.pelu.contrato))

        self.assertEqual(ficha.servicios.count(), 2)


class CP07DeshabilitarClienteTests(Base):
    """CP-07 · Integración · RNF Integridad-01 y 02."""

    def test_deshabilitar_con_motivo_sin_borrar(self):
        self.entrar(self.admin)
        url = reverse("clientes:estado", args=[self.cliente.run])
        self.client.post(url, {"motivo": "Cliente solicita baja"})
        self.cliente.refresh_from_db()
        self.assertFalse(self.cliente.activo)
        h = HistoricoEstadoCliente.objects.filter(cliente=self.cliente).latest("fecha_cambio")
        self.assertEqual((h.observacion, h.responsable), ("Cliente solicita baja", self.admin))
        self.assertIsNotNone(h.fecha_cambio)
        self.assertTrue(Cliente.objects.filter(run=self.cliente.run).exists())
        # La ficha del cliente muestra el historial y no ofrece eliminar.
        r = self.client.get(reverse("clientes:detalle", args=[self.cliente.run]))
        self.assertContains(r, "Cliente solicita baja")
        self.assertNotRegex(r.content.decode(), r"(?i)eliminar cliente")

    def test_sin_motivo_no_cambia(self):
        self.entrar(self.admin)
        self.client.post(reverse("clientes:estado", args=[self.cliente.run]), {"motivo": ""})
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.activo)

    def test_historial_no_se_edita_ni_borra(self):
        self.entrar(self.admin)
        self.client.post(reverse("clientes:estado", args=[self.cliente.run]), {"motivo": "Cliente solicita baja"})
        h = HistoricoEstadoCliente.objects.filter(cliente=self.cliente).latest("fecha_cambio")
        with self.assertRaises(ValueError):
            h.delete()
        with self.assertRaises(ValueError):
            h.save()

    def test_cliente_con_fichas_no_se_puede_borrar(self):
        cliente = Cliente.objects.filter(fichas__isnull=False).first()
        with self.assertRaises(ProtectedError):
            cliente.delete()


class CP08ValoracionCorreoTests(Base):
    """CP-08 · Integración · RF-RC-01, RF-VS-01, RNF Confiabilidad-02."""

    def ficha_cerrada(self):
        ficha = fs.abrir_ficha(self.admin, self.cliente)
        d = fs.agregar_servicio(ficha, Servicio.objects.get(nombre="Corte tradicional"), self.pelu, "basico",
                                self.admin)
        fs.iniciar_servicio(d, self.pelu)
        fs.terminar_servicio(d, self.pelu)
        fs.cerrar_ficha(ficha, self.pelu)
        return ficha

    def test_se_programa_para_el_dia_siguiente(self):
        v = self.ficha_cerrada().valoraciones.get()
        self.assertEqual(v.fecha_programada, timezone.localdate() + timedelta(days=1))
        self.assertEqual(v.estado, "pendiente")

    def test_falla_smtp_reintenta_hasta_3_y_registra_error(self):
        self.assertEqual(settings.ENVIO_MAX_INTENTOS, 3)
        v = self.ficha_cerrada().valoraciones.get()
        manana = timezone.localdate() + timedelta(days=1)
        with mock.patch("seguimiento.servicios.EmailMultiAlternatives.send",
                        side_effect=ConnectionRefusedError("servidor caído")):
            for intento in (1, 2):
                procesar_pendientes(hoy=manana)
                v.refresh_from_db()
                self.assertEqual((v.estado, v.intentos), ("pendiente", intento))
            procesar_pendientes(hoy=manana)
            v.refresh_from_db()
            self.assertEqual((v.estado, v.intentos), ("error", 3))
            procesar_pendientes(hoy=manana)  # no hay un cuarto intento
        v.refresh_from_db()
        self.assertEqual(v.intentos, 3)
        self.assertIn("Fallo SMTP", v.ultimo_error)
        fallidos = EnvioMensaje.objects.filter(valoracion=v, exitoso=False)
        self.assertEqual(fallidos.count(), 3)
        self.assertTrue(all("servidor caído" in e.error for e in fallidos))

    def test_falla_y_luego_se_envia(self):
        v = self.ficha_cerrada().valoraciones.get()
        manana = timezone.localdate() + timedelta(days=1)
        with mock.patch("seguimiento.servicios.EmailMultiAlternatives.send", side_effect=OSError("timeout")):
            procesar_pendientes(hoy=manana)
        procesar_pendientes(hoy=manana)
        v.refresh_from_db()
        self.assertEqual((v.estado, v.intentos, v.ultimo_error), ("enviada", 2, ""))


class CP10PermisosServidorTests(Base):
    """CP-10 · Seguridad · RF-PA-01, RNF Seguridad-03."""

    def test_peluquero_recibe_403_por_get_y_post_directo(self):
        self.entrar(self.pelu)
        otro = Usuario.objects.get(run="17777777")
        self.assertEqual(self.client.get(reverse("core:usuarios")).status_code, 403)
        self.assertEqual(self.client.get(reverse("core:usuario_nuevo")).status_code, 403)
        r = self.client.post(reverse("core:usuario_estado", args=[otro.run]), {"motivo": "intento"})
        self.assertEqual(r.status_code, 403)
        otro.refresh_from_db()
        self.assertTrue(otro.is_active)
        r = self.client.post(reverse("catalogo:servicio_estado", args=[Servicio.objects.first().pk]),
                             {"motivo": "intento"})
        self.assertEqual(r.status_code, 403)

    def test_sin_sesion_redirige_al_login(self):
        login = reverse("login")
        for url in [reverse("core:usuarios"), reverse("fichas:lista"), reverse("clientes:buscar"),
                    reverse("reportes:inicio")]:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertTrue(r["Location"].startswith(login), url)
        r = self.client.post(reverse("clientes:estado", args=[self.cliente.run]), {"motivo": "x"})
        self.assertTrue(r["Location"].startswith(login))
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.activo)


class CP11ContrasenasYRepoTests(Base):
    """CP-11 · Seguridad · RNF Seguridad-01 y 02."""

    def test_todas_las_contrasenas_con_hash(self):
        claves = list(Usuario.objects.exclude(password="").values_list("password", flat=True))
        self.assertTrue(claves)
        for c in claves:
            # Formato de Django: algoritmo$iteraciones$sal$hash, o "!" para "sin contraseña usable".
            self.assertTrue(c.startswith(("pbkdf2_", "argon2", "bcrypt", "scrypt", "!")), c[:12])
            self.assertNotEqual(c, CLAVE)

    def test_login_funciona_con_la_clave_hasheada(self):
        u = Usuario.objects.get(pk=self.pelu.pk)
        self.assertTrue(u.check_password(CLAVE))
        self.assertNotIn(CLAVE, u.password)

    def test_sin_credenciales_en_el_repositorio(self):
        raiz = Path(settings.BASE_DIR)
        try:
            archivos = subprocess.run(["git", "ls-files"], cwd=raiz, capture_output=True, text=True,
                                      check=True).stdout.split()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git no disponible")
        self.assertFalse([a for a in archivos if re.search(r"(^|/)\.env$|\.sqlite3$|\.pem$|\.key$", a)])
        patrones = [
            # cadena de conexión con clave real (se ignoran marcadores como CLAVE, PASSWORD o [TU-CLAVE]
            # y variables ${...} de docker-compose)
            r"postgres(ql)?://[^:\s]+:(?![A-Z_\[\]-]+@)(?![^@\s]*\$\{)[^@\s]{4,}@",
            r"SECRET_KEY\s*=\s*['\"](?!dev-inseguro)[^'\"]{20,}",   # clave de Django fija
            r"EMAIL_HOST_PASSWORD\s*=\s*['\"][^'\"]+['\"]",
            r"eyJhbGciOi[A-Za-z0-9_-]{20,}",                          # JWT / clave de Supabase
            r"sk_live_|AKIA[0-9A-Z]{16}",
        ]
        hallazgos = []
        for a in archivos:
            if not a.endswith((".py", ".html", ".js", ".txt", ".md", ".json", ".yml", ".yaml", ".toml", ".cfg",
                               ".example")) or a.endswith("test_plan_c2.py"):
                continue
            texto = (raiz / a).read_text(encoding="utf-8", errors="ignore")
            hallazgos += [f"{a}: {p}" for p in patrones if re.search(p, texto)]
        self.assertEqual(hallazgos, [])
