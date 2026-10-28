"""
Pruebas de sistema: recorren pantallas y reglas de negocio clave.
    python manage.py test
"""
import io
import logging
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from beneficios.models import Giftcard
from beneficios.servicios import usar_giftcard
from catalogo.models import Servicio
from clientes.models import Cliente
from core import rut
from core.models import Usuario
from fichas import servicios as fs
from fichas.models import DetalleAtencionServicio  # noqa: F401
from fichas.models import FichaAtencion
from seguimiento.models import Valoracion
from seguimiento.servicios import procesar_pendientes
from reportes.generadores import REPORTES

CLAVE = "Peluqueria2026"
logging.disable(logging.INFO)  # oculta los envíos simulados durante las pruebas


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_datos_iniciales", "--demo", stdout=io.StringIO())
        cls.admin = Usuario.objects.get(run="11111111")
        cls.pelu = Usuario.objects.get(run="16666666")
        cls.cliente = Cliente.objects.first()

    def entrar(self, u):
        self.client.force_login(u)


class RutTests(TestCase):
    def test_valida_digito(self):
        self.assertTrue(rut.es_valido("11.111.111-1"))
        self.assertTrue(rut.es_valido(f"16666666-{rut.calcular_dv(16666666)}"))
        self.assertFalse(rut.es_valido("11.111.111-2"))
        self.assertEqual(rut.formatear("12345678"), "12.345.678-5")


class AccesoTests(Base):
    def test_login_con_run_formateado(self):
        r = self.client.post(reverse("login"), {"username": "11.111.111-1", "password": CLAVE})
        self.assertRedirects(r, reverse("inicio"))

    def test_login_sin_dv_ni_guion(self):
        for escrito in ["11111111", "111111111", "11.111.111", "16666666", "16666666K"]:
            self.client.logout()
            r = self.client.post(reverse("login"), {"username": escrito, "password": CLAVE})
            self.assertRedirects(r, reverse("inicio"), msg_prefix=escrito)

    def test_mensaje_generico(self):
        r1 = self.client.post(reverse("login"), {"username": "11.111.111-1", "password": "mala"})
        r2 = self.client.post(reverse("login"), {"username": "22.222.222-2", "password": "mala"})
        self.assertContains(r1, "RUN o contraseña incorrectos.")
        self.assertContains(r2, "RUN o contraseña incorrectos.")

    def test_peluquero_sin_admin(self):
        self.entrar(self.pelu)
        for nombre in ["core:usuarios", "catalogo:servicios", "reportes:inicio", "beneficios:inicio", "metas:panel"]:
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 403, nombre)

    def test_deshabilitado_no_entra(self):
        self.pelu.is_active = False
        self.pelu.save()
        r = self.client.post(reverse("login"), {"username": rut.formatear("16666666"), "password": CLAVE})
        self.assertContains(r, "RUN o contraseña incorrectos.")


class PantallasTests(Base):
    def test_todas_las_pantallas_admin(self):
        self.entrar(self.admin)
        ficha = FichaAtencion.objects.first()
        s = Servicio.objects.first()
        urls = [reverse("inicio"), reverse("ajustes"), reverse("core:usuarios"), reverse("core:usuario_nuevo"),
                reverse("core:usuario", args=[self.pelu.run]), reverse("core:usuario_editar", args=[self.pelu.run]),
                reverse("core:catalogo_acceso", args=["roles"]), reverse("core:catalogo_acceso", args=["privilegios"]),
                reverse("clientes:buscar") + "?q=camila", reverse("clientes:nuevo"),
                reverse("clientes:detalle", args=[self.cliente.run]), reverse("clientes:editar", args=[self.cliente.run]),
                reverse("catalogo:servicios"), reverse("catalogo:servicio", args=[s.pk]),
                reverse("catalogo:servicio_editar", args=[s.pk]), reverse("catalogo:tipos"),
                reverse("catalogo:tipo_editar", args=[s.tipo_id]), reverse("catalogo:insumos"),
                reverse("fichas:lista"), reverse("fichas:lista") + "?desde=hoy", reverse("fichas:nueva"),
                reverse("fichas:detalle", args=[ficha.pk]), reverse("seguimiento:valoraciones"),
                reverse("seguimiento:recordatorios"), reverse("seguimiento:canales"), reverse("metas:mias"),
                reverse("metas:panel"), reverse("beneficios:inicio"), reverse("beneficios:inicio") + "?vista=catalogo",
                reverse("beneficios:giftcard_nueva"), reverse("beneficios:promocion_nueva"),
                reverse("beneficios:vender_promocion"), reverse("reportes:inicio")]
        urls += [reverse("reportes:reporte", args=[k]) for k in REPORTES]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_exportaciones(self):
        self.entrar(self.admin)
        for k in REPORTES:
            for fmt in ("xlsx", "pdf"):
                r = self.client.get(reverse("reportes:reporte", args=[k]) + f"?formato={fmt}")
                self.assertEqual(r.status_code, 200, f"{k} {fmt}")

    def test_peluquero_ve_su_inicio(self):
        self.entrar(self.pelu)
        self.assertContains(self.client.get(reverse("inicio")), "Mis servicios de hoy")
        self.assertEqual(self.client.get(reverse("metas:mias")).status_code, 200)


class FichaTests(Base):
    def nueva_ficha(self, nombre_servicio):
        ficha = fs.abrir_ficha(self.admin, self.cliente)
        d = fs.agregar_servicio(ficha, Servicio.objects.get(nombre=nombre_servicio), self.pelu, "plus", self.admin)
        return ficha, d

    def test_flujo_completo_corte(self):
        ficha, d = self.nueva_ficha("Corte tradicional")
        self.assertEqual(d.precio_cobrado, Servicio.objects.get(nombre="Corte tradicional").precio_de("plus"))
        self.assertTrue(d.aplica_comision)  # Andrea es externa
        with self.assertRaises(ValidationError):
            fs.terminar_servicio(d, self.pelu)  # no se puede terminar sin iniciar
        fs.iniciar_servicio(d, self.pelu)
        with self.assertRaises(ValidationError):
            fs.iniciar_servicio(d, self.pelu)
        fs.terminar_servicio(d, self.pelu)
        fs.cerrar_ficha(ficha, self.pelu)
        self.assertEqual(list(ficha.valoraciones.values_list("tipo", flat=True)), ["dia_siguiente"])

    def test_tratamiento_dos_valoraciones(self):
        ficha, d = self.nueva_ficha("Balayage")
        fs.iniciar_servicio(d, self.pelu)
        fs.terminar_servicio(d, self.pelu)
        fs.cerrar_ficha(ficha, self.pelu)
        self.assertEqual(ficha.valoraciones.count(), 2)
        self.assertTrue(d.recordatorios.filter(tipo="renovacion").exists())

    def test_no_cierra_con_servicios_abiertos(self):
        ficha, d = self.nueva_ficha("Corte tradicional")
        with self.assertRaises(ValidationError):
            fs.cerrar_ficha(ficha, self.admin)

    def test_precio_congelado(self):
        ficha, d = self.nueva_ficha("Corte tradicional")
        precio = d.precio_cobrado
        Servicio.objects.filter(nombre="Corte tradicional").update(precio=99999)
        d.refresh_from_db()
        self.assertEqual(d.precio_cobrado, precio)

    def test_peluquero_no_habilitado(self):
        from catalogo.models import UsuarioServicio
        UsuarioServicio.objects.filter(usuario=self.pelu).update(activo=False)
        ficha = fs.abrir_ficha(self.admin, self.cliente)
        with self.assertRaises(ValidationError):
            fs.agregar_servicio(ficha, Servicio.objects.get(nombre="Corte tradicional"), self.pelu, "basico", self.admin)

    def test_anular_guarda_version(self):
        ficha, d = self.nueva_ficha("Corte tradicional")
        fs.anular_ficha(ficha, self.admin, "Ficha duplicada")
        self.assertEqual(ficha.estado_id, "anulada")
        self.assertEqual(ficha.versiones.count(), 1)

    def test_botones_por_web(self):
        ficha, d = self.nueva_ficha("Corte tradicional")
        self.entrar(self.pelu)
        # Andrea ya tiene otro servicio en curso en los datos demo: se confirma el inicio simultáneo.
        self.client.post(reverse("fichas:iniciar", args=[d.pk]), {"confirmar": "1"})
        self.client.post(reverse("fichas:terminar", args=[d.pk]))
        self.client.post(reverse("fichas:cerrar", args=[ficha.pk]))
        ficha.refresh_from_db()
        self.assertEqual(ficha.estado_id, "cerrada")


class SeguimientoTests(Base):
    def test_envio_y_respuesta(self):
        ficha = fs.abrir_ficha(self.admin, self.cliente)
        d = fs.agregar_servicio(ficha, Servicio.objects.get(nombre="Corte tradicional"), self.pelu, "basico", self.admin)
        fs.iniciar_servicio(d, self.pelu)
        fs.terminar_servicio(d, self.pelu)
        fs.cerrar_ficha(ficha, self.pelu)
        v = ficha.valoraciones.get()
        procesar_pendientes(hoy=timezone.localdate() + timedelta(days=1))
        v.refresh_from_db()
        self.assertEqual(v.estado, "enviada")
        # Por ahora todo sale por correo, aunque el cliente tenga teléfono.
        from django.core import mail
        correo = next(m for m in mail.outbox if v.token in m.body)
        self.assertEqual(correo.to, [self.cliente.correo])
        self.assertEqual(v.envios.get().canal.codigo, "email")
        r = self.client.post(reverse("valorar", args=[v.token]), {"calificacion": "5", "comentario": "Excelente"})
        self.assertContains(r, "Gracias")
        v.refresh_from_db()
        self.assertEqual((v.estado, v.calificacion), ("respondida", 5))

    def test_sin_correo_marca_error(self):
        self.cliente.correo = ""
        self.cliente.save()
        ficha = fs.abrir_ficha(self.admin, self.cliente)
        d = fs.agregar_servicio(ficha, Servicio.objects.get(nombre="Corte tradicional"), self.pelu, "basico", self.admin)
        fs.iniciar_servicio(d, self.pelu)
        fs.terminar_servicio(d, self.pelu)
        fs.cerrar_ficha(ficha, self.pelu)
        procesar_pendientes(hoy=timezone.localdate() + timedelta(days=1))
        self.assertEqual(ficha.valoraciones.get().estado, "error")

    def test_sin_duplicados(self):
        ficha = FichaAtencion.objects.filter(estado="validada", cliente__isnull=False).first()
        from seguimiento.servicios import programar_seguimiento
        antes = Valoracion.objects.count()
        programar_seguimiento(ficha)
        self.assertEqual(Valoracion.objects.count(), antes)


class GiftcardTests(Base):
    def test_no_supera_saldo(self):
        g = Giftcard.objects.create(beneficiario=self.cliente, monto_inicial=10000, saldo_actual=10000,
                                    fecha_vencimiento=timezone.localdate() + timedelta(days=30), creada_por=self.admin)
        ficha = FichaAtencion.objects.first()
        with self.assertRaises(ValidationError):
            usar_giftcard(g, ficha, 20000, self.admin)
        usar_giftcard(g, ficha, 10000, self.admin)
        g.refresh_from_db()
        self.assertEqual((g.saldo_actual, g.estado), (0, "agotada"))

    def test_vencida(self):
        g = Giftcard.objects.create(beneficiario=self.cliente, monto_inicial=10000, saldo_actual=10000,
                                    fecha_vencimiento=timezone.localdate() - timedelta(days=1), creada_por=self.admin)
        with self.assertRaises(ValidationError):
            usar_giftcard(g, FichaAtencion.objects.first(), 1000, self.admin)


class MetasTests(Base):
    def test_guardar_metas_con_lista_de_incentivos(self):
        """Regresión del año '2 026' + lista de incentivos (dinero y regalos)."""
        from metas.models import MetaMensual
        from metas.servicios import avance
        self.entrar(self.admin)
        hoy = timezone.localdate()
        r = self.client.get(reverse("metas:panel"))
        self.assertContains(r, f'name="anio" value="{hoy.year}"')
        run = self.pelu.pk
        r = self.client.post(reverse("metas:guardar"), {
            "mes": hoy.month, "anio": hoy.year, f"meta_{run}": "30",
            f"inc_{run}_tipo": ["dinero", "regalo", "otro", "dinero"],
            f"inc_{run}_desc": ["Bono", "Kit Kérastase", "Día libre", ""],
            f"inc_{run}_monto": ["$80.000", "", "", ""],  # la última fila vacía se ignora
            "meta_17777777": "20"})  # meta sin incentivos
        self.assertEqual(r.status_code, 302)
        m = MetaMensual.objects.get(peluquero=self.pelu, mes=hoy.month, anio=hoy.year)
        self.assertEqual(m.meta_cliente, 30)
        self.assertEqual(m.incentivo_base, 80000)
        self.assertEqual(list(m.incentivos.values_list("tipo", "descripcion", "monto")),
                         [("dinero", "Bono", 80000), ("regalo", "Kit Kérastase", None), ("otro", "Día libre", None)])
        a = avance(m)
        self.assertTrue(isinstance(a["barra"], int))
        self.assertEqual(len(a["incentivos"]), 3)
        m2 = MetaMensual.objects.get(peluquero_id="17777777", mes=hoy.month, anio=hoy.year)
        self.assertEqual((m2.incentivo_base, m2.incentivos.count()), (0, 0))

    def test_regalo_sin_descripcion_da_error(self):
        from metas.models import MetaMensual
        self.entrar(self.admin)
        hoy = timezone.localdate()
        run = self.pelu.pk
        antes = MetaMensual.objects.get(peluquero=self.pelu, mes=hoy.month, anio=hoy.year).incentivos.count()
        r = self.client.post(reverse("metas:guardar"), {
            "mes": hoy.month, "anio": hoy.year, f"meta_{run}": "30",
            f"inc_{run}_tipo": ["regalo"], f"inc_{run}_desc": [""], f"inc_{run}_monto": ["5000"]}, follow=True)
        self.assertContains(r, "describe el regalo o producto")
        self.assertEqual(MetaMensual.objects.get(peluquero=self.pelu, mes=hoy.month, anio=hoy.year).incentivos.count(), antes)

class UsuarioFormTests(Base):
    def test_crear_peluquero_con_especialidad_y_servicios(self):
        from catalogo.models import UsuarioServicio
        from core.models import Especialidad, Rol, TipoContrato
        self.entrar(self.admin)
        color = Especialidad.objects.get(nombre="Colorimetría")
        servicios = list(Servicio.objects.filter(tipo__nombre="Colorimetría"))
        r = self.client.post(reverse("core:usuario_nuevo"), {
            "run_completo": rut.formatear("19999999"), "nombre": "Daniela", "ap_paterno": "Soto",
            "correo": "daniela@vicentecortez.cl", "telefono": "+56911112222", "genero": "F",
            "contrato": TipoContrato.objects.get(nombre="Externo").pk,
            "roles": [Rol.objects.get(codigo="peluquero").pk],
            "especialidades_sel": [color.pk], "especialidad_principal": color.pk,
            "servicios_sel": [s.pk for s in servicios], "password1": "TijeraDorada2026"})
        self.assertEqual(r.status_code, 302, r.content[:500])
        u = Usuario.objects.get(run="19999999")
        self.assertTrue(u.es_peluquero)
        self.assertEqual(UsuarioServicio.objects.filter(usuario=u, activo=True).count(), len(servicios))

    def test_rol_obligatorio(self):
        self.entrar(self.admin)
        r = self.client.post(reverse("core:usuario_nuevo"), {"run_completo": rut.formatear("19999999")})
        self.assertContains(r, "Elige al menos un rol.")


class SimultaneosTests(Base):
    def test_pide_confirmacion_si_hay_otro_en_curso(self):
        f1 = fs.abrir_ficha(self.admin, self.cliente)
        d1 = fs.agregar_servicio(f1, Servicio.objects.get(nombre="Balayage"), self.pelu, "basico", self.admin)
        d2 = fs.agregar_servicio(f1, Servicio.objects.get(nombre="Corte tradicional"), self.pelu, "basico", self.admin)
        fs.iniciar_servicio(d1, self.pelu)
        self.entrar(self.pelu)
        self.client.post(reverse("fichas:iniciar", args=[d2.pk]), {"confirmar": ""})
        d2.refresh_from_db()
        self.assertEqual(d2.estado, "pendiente")  # no inicia sin confirmar
        self.client.post(reverse("fichas:iniciar", args=[d2.pk]), {"confirmar": "1"})
        d2.refresh_from_db()
        self.assertEqual(d2.estado, "en_proceso")  # confirmado: se permite en paralelo

    def test_sin_otros_inicia_directo(self):
        from catalogo.models import UsuarioServicio
        carla = Usuario.objects.get(run="18888888")
        fs.DetalleAtencionServicio.objects.filter(peluquero=carla, estado="en_proceso").update(estado="terminado")
        f = fs.abrir_ficha(self.admin, self.cliente)
        d = fs.agregar_servicio(f, Servicio.objects.get(nombre="Corte tradicional"), carla, "basico", self.admin)
        self.assertEqual(fs.aviso_simultaneo(d), "")
        self.entrar(carla)
        self.client.post(reverse("fichas:iniciar", args=[d.pk]))
        d.refresh_from_db()
        self.assertEqual(d.estado, "en_proceso")


class PromocionEnFichaTests(Base):
    def test_promocion_solo_para_servicios_de_la_ficha(self):
        from beneficios.models import ClientePromocion, Promocion, PromocionServicio
        tintura = Servicio.objects.get(nombre="Color generalizado")
        corte = Servicio.objects.get(nombre="Corte tradicional")
        promo = Promocion.objects.create(nombre="Pack color", precio=90000)
        PromocionServicio.objects.create(promocion=promo, servicio=tintura, cantidad_total=2)
        PromocionServicio.objects.create(promocion=promo, servicio=corte, cantidad_total=1)
        cp = ClientePromocion.objects.create(promocion=promo, comprador=self.cliente, creada_por=self.admin,
                                             fecha_vencimiento=timezone.localdate() + timedelta(days=30))
        ficha = fs.abrir_ficha(self.admin, self.cliente)
        d = fs.agregar_servicio(ficha, tintura, self.pelu, "basico", self.admin)
        self.entrar(self.admin)
        r = self.client.get(reverse("fichas:detalle", args=[ficha.pk]))
        self.assertContains(r, "Agrega Corte tradicional a la ficha para usarlo.")  # corte no está en la ficha
        self.assertContains(r, "Quedan <strong>2 de 2</strong>", html=False)
        self.client.post(reverse("beneficios:usar_promocion", args=[ficha.pk]), {"uso": f"{cp.pk}-{corte.pk}"})
        self.assertEqual(cp.usos.count(), 0)  # rechazado: no está en la ficha
        self.client.post(reverse("beneficios:usar_promocion", args=[ficha.pk]), {"uso": f"{cp.pk}-{tintura.pk}"})
        uso = cp.usos.get()
        self.assertEqual(uso.detalle, d)  # queda ligado al servicio de la ficha
        r = self.client.get(reverse("fichas:detalle", args=[ficha.pk]))
        self.assertContains(r, "Cubierto por promoción")
        self.assertContains(r, "Aplicada")


class CorreoPruebaTests(Base):
    def test_boton_correo_de_prueba(self):
        from django.core import mail
        self.entrar(self.admin)
        r = self.client.post(reverse("seguimiento:canales"), {"probar_correo": "prueba@vicentecortez.cl"}, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(mail.outbox[-1].to, ["prueba@vicentecortez.cl"])
        r = self.client.post(reverse("seguimiento:canales"), {"probar_correo": "no-es-correo"}, follow=True)
        self.assertContains(r, "no es un correo válido")


class ConfiguracionCorreoTests(Base):
    def test_guardar_cuenta_cifra_la_clave(self):
        from seguimiento.models import ConfiguracionCorreo
        self.entrar(self.admin)
        datos = {"guardar_correo": "1", "correo-proveedor": "gmail", "correo-usuario": "peluqueria@gmail.com",
                 "correo-clave": "abcd efgh ijkl mnop", "correo-remitente_nombre": "Peluquería Vicente Cortez",
                 "correo-servidor": "smtp.gmail.com", "correo-puerto": "587", "correo-seguridad": "tls",
                 "correo-activo": "on"}
        r = self.client.post(reverse("seguimiento:canales"), datos)
        self.assertEqual(r.status_code, 302)
        conf = ConfiguracionCorreo.actual()
        self.assertTrue(conf.lista)
        self.assertNotIn("abcd", conf.clave_cifrada)            # no queda en texto plano
        self.assertEqual(conf.clave(), "abcd efgh ijkl mnop")   # pero se puede usar para enviar
        # Guardar de nuevo sin escribir la clave la mantiene.
        datos["correo-clave"] = ""
        datos["correo-remitente_nombre"] = "VC"
        self.client.post(reverse("seguimiento:canales"), datos)
        self.assertEqual(ConfiguracionCorreo.actual().clave(), "abcd efgh ijkl mnop")
        # La pantalla nunca muestra la clave.
        self.assertNotContains(self.client.get(reverse("seguimiento:canales")), "abcd efgh")

    def test_no_activa_sin_clave(self):
        self.entrar(self.admin)
        r = self.client.post(reverse("seguimiento:canales"), {
            "guardar_correo": "1", "correo-usuario": "peluqueria@gmail.com", "correo-clave": "",
            "correo-remitente_nombre": "VC", "correo-servidor": "smtp.gmail.com", "correo-puerto": "587",
            "correo-seguridad": "tls", "correo-activo": "on"})
        self.assertContains(r, "Falta la contraseña de aplicación.")

    def test_backend_usa_la_cuenta_guardada(self):
        from unittest import mock
        from django.core.mail import EmailMessage
        from core.correo import BackendConfigurable
        from seguimiento.models import ConfiguracionCorreo
        conf = ConfiguracionCorreo.actual()
        conf.usuario, conf.activo = "peluqueria@gmail.com", True
        conf.fijar_clave("secreta")
        conf.save()
        with mock.patch("core.correo.SMTPBackend") as smtp:
            smtp.return_value.send_messages.return_value = 1
            m = EmailMessage("Hola", "Cuerpo", None, ["cliente@correo.cl"])
            BackendConfigurable().send_messages([m])
        kwargs = smtp.call_args.kwargs
        self.assertEqual((kwargs["host"], kwargs["username"], kwargs["password"], kwargs["use_tls"]),
                         ("smtp.gmail.com", "peluqueria@gmail.com", "secreta", True))
        self.assertIn("peluqueria@gmail.com", m.from_email)

    def test_apagado_va_a_consola(self):
        from unittest import mock
        from core.correo import BackendConfigurable
        with mock.patch("core.correo.SMTPBackend") as smtp, mock.patch("core.correo.ConsolaBackend") as consola:
            BackendConfigurable().send_messages([])
        smtp.assert_not_called()
        consola.assert_called_once()


class ResponderATests(Base):
    def test_respuestas_van_al_correo_live(self):
        from unittest import mock
        from django.core.mail import EmailMessage
        from core.correo import BackendConfigurable
        from seguimiento.models import ConfiguracionCorreo
        conf = ConfiguracionCorreo.actual()
        conf.usuario, conf.activo, conf.responder_a = "peluqueria@gmail.com", True, "vicentecortez@live.cl"
        conf.fijar_clave("secreta")
        conf.save()
        with mock.patch("core.correo.SMTPBackend"):
            m = EmailMessage("Hola", "Cuerpo", None, ["cliente@correo.cl"])
            BackendConfigurable().send_messages([m])
        self.assertEqual(m.reply_to, ["vicentecortez@live.cl"])
        self.assertIn("peluqueria@gmail.com", m.from_email)


class CorreoEstrellasTests(Base):
    def test_valoracion_va_con_estrellas_y_texto(self):
        from django.core import mail
        ficha = fs.abrir_ficha(self.admin, self.cliente)
        d = fs.agregar_servicio(ficha, Servicio.objects.get(nombre="Corte tradicional"), self.pelu, "basico", self.admin)
        fs.iniciar_servicio(d, self.admin)
        fs.terminar_servicio(d, self.admin)
        fs.cerrar_ficha(ficha, self.admin)
        v = ficha.valoraciones.get()
        procesar_pendientes(hoy=timezone.localdate() + timedelta(days=1))
        correo = next(m for m in mail.outbox if v.token in m.body)
        html = correo.alternatives[0][0]
        for n in range(1, 6):
            self.assertIn(f"/valorar/{v.token}/?nota={n}", html)   # 5 estrellas
        self.assertIn(v.enlace, correo.body)                         # versión de texto con el enlace

    def test_estrella_llega_marcada_y_no_guarda_sola(self):
        v = Valoracion.objects.filter(estado="pendiente", ficha__cliente__isnull=False).exclude(ficha__estado="anulada").first()
        r = self.client.get(reverse("valorar", args=[v.token]) + "?nota=4")
        self.assertContains(r, 'value="4" checked')
        v.refresh_from_db()
        self.assertEqual(v.estado, "pendiente")  # abrir el enlace no registra la nota

    def test_pagina_y_correo_de_ejemplo(self):
        from django.core import mail
        self.assertContains(self.client.get("/valorar/ejemplo/?nota=5"), 'value="5" checked')
        self.assertContains(self.client.post("/valorar/ejemplo/", {"calificacion": "5"}), "Gracias")
        self.entrar(self.admin)
        self.client.post(reverse("seguimiento:canales"), {"probar_correo": "yo@vicentecortez.cl", "ejemplo": "valoracion"})
        self.assertIn("/valorar/ejemplo/?nota=3", mail.outbox[-1].alternatives[0][0])


class VistaPreviaCorreoTests(Base):
    def test_vista_previa_solo_admin(self):
        url = reverse("seguimiento:vista_previa_valoracion")
        self.entrar(self.admin)
        r = self.client.get(url)
        self.assertContains(r, "Toca una estrella")
        self.entrar(self.pelu)
        self.assertEqual(self.client.get(url).status_code, 403)
