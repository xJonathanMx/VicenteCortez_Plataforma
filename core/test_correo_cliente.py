"""Correo manual desde el perfil del cliente (por ejemplo, para enviar los cuidados de un tratamiento)."""
from django.core import mail
from django.urls import reverse

from core.models import Cliente, EnvioMensaje
from core.tests import Base


class CorreoClienteTests(Base):
    def setUp(self):
        self.c = Cliente.objects.exclude(correo="").first() or self.cliente
        if not self.c.correo:
            self.c.correo = "cliente@correo.cl"
            self.c.save(update_fields=["correo"])
        self.url = reverse("clientes:correo", args=[self.c.run])

    def test_el_perfil_muestra_el_boton(self):
        self.entrar(self.admin)
        r = self.client.get(reverse("clientes:detalle", args=[self.c.run]))
        self.assertContains(r, self.url)

    def test_el_formulario_viene_con_un_borrador(self):
        self.entrar(self.admin)
        r = self.client.get(self.url)
        self.assertContains(r, f"Hola {self.c.nombre}")
        self.assertContains(r, self.c.correo)

    def test_envia_solo_al_correo_del_cliente(self):
        self.entrar(self.admin)
        r = self.client.post(self.url, {"asunto": "Cuidados para tu tintura",
                                        "mensaje": "Usa shampoo sin sulfatos por 15 días."})
        self.assertRedirects(r, reverse("clientes:detalle", args=[self.c.run]))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.c.correo])
        self.assertEqual(mail.outbox[0].cc, [])
        self.assertEqual(mail.outbox[0].bcc, [])
        self.assertIn("sin sulfatos", mail.outbox[0].body)
        self.assertTrue(EnvioMensaje.objects.filter(destino=self.c.correo, exitoso=True,
                                                    valoracion=None, recordatorio=None).exists())

    def test_exige_asunto_y_mensaje(self):
        self.entrar(self.admin)
        r = self.client.post(self.url, {"asunto": "", "mensaje": ""})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_cliente_sin_correo_no_envia(self):
        self.c.correo = ""
        self.c.save(update_fields=["correo"])
        self.entrar(self.admin)
        r = self.client.post(self.url, {"asunto": "Hola", "mensaje": "Hola"})
        self.assertRedirects(r, reverse("clientes:detalle", args=[self.c.run]))
        self.assertEqual(len(mail.outbox), 0)
        r = self.client.get(reverse("clientes:detalle", args=[self.c.run]))
        self.assertNotContains(r, self.url)

    def test_peluquero_no_puede_escribir_a_clientes_ajenos(self):
        ajeno = Cliente.objects.exclude(pk__in=Cliente.objects.visibles_para(self.pelu)).first()
        if ajeno is None:
            self.skipTest("Todos los clientes demo son visibles para el peluquero.")
        self.entrar(self.pelu)
        r = self.client.post(reverse("clientes:correo", args=[ajeno.run]), {"asunto": "x", "mensaje": "x"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)


class CorreoDesdeFichaTests(Base):
    def setUp(self):
        from fichas import servicios as fs
        from core.models import Servicio
        self.c = self.cliente
        self.c.correo = "cliente@correo.cl"
        self.c.save(update_fields=["correo"])
        self.ficha = fs.abrir_ficha(self.admin, self.c)
        self.servicio = Servicio.objects.get(nombre="Corte tradicional")
        fs.agregar_servicio(self.ficha, self.servicio, self.pelu, "basico", self.admin)
        self.url = reverse("clientes:correo", args=[self.c.run]) + f"?ficha={self.ficha.pk}"

    def test_la_ficha_muestra_el_boton(self):
        self.entrar(self.admin)
        r = self.client.get(reverse("fichas:detalle", args=[self.ficha.pk]))
        self.assertContains(r, f"?ficha={self.ficha.pk}")

    def test_borrador_usa_los_servicios_de_la_ficha_y_vuelve_a_ella(self):
        self.entrar(self.admin)
        r = self.client.get(self.url)
        self.assertContains(r, f"Cuidados para tu {self.servicio.nombre.lower()}")
        r = self.client.post(self.url, {"asunto": "Cuidados", "mensaje": "Evita el agua caliente."})
        self.assertRedirects(r, reverse("fichas:detalle", args=[self.ficha.pk]), fetch_redirect_response=False)
        self.assertEqual(mail.outbox[-1].to, [self.c.correo])

    def test_ficha_de_otro_cliente_se_ignora(self):
        otro = Cliente.objects.exclude(pk=self.c.pk).first()
        self.entrar(self.admin)
        url = reverse("clientes:correo", args=[otro.run]) + f"?ficha={self.ficha.pk}"
        if not otro.correo:
            otro.correo = "otro@correo.cl"
            otro.save(update_fields=["correo"])
        r = self.client.post(url, {"asunto": "x", "mensaje": "x"})
        self.assertRedirects(r, reverse("clientes:detalle", args=[otro.run]), fetch_redirect_response=False)
