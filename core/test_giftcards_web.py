"""Pruebas por web de giftcards: registrar, usar en una ficha y deshabilitar."""
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from core import rut
from core.models import FichaAtencion, Giftcard
from core.tests import Base


class GiftcardWebTests(Base):
    def _crear_giftcard(self, monto=10000):
        return Giftcard.objects.create(
            beneficiario=self.cliente, monto_inicial=monto, saldo_actual=monto,
            fecha_vencimiento=timezone.localdate() + timedelta(days=30), creada_por=self.admin)

    def test_registrar_giftcard_por_formulario(self):
        self.entrar(self.admin)
        hoy = timezone.localdate()
        r = self.client.post(reverse("beneficios:giftcard_nueva"), {
            "beneficiario": rut.formatear(self.cliente.run, rut.calcular_dv(self.cliente.run)),
            "monto_inicial": 15000,
            "fecha_compra": hoy.isoformat(),
            "fecha_vencimiento": (hoy + timedelta(days=60)).isoformat(),
        })
        g = Giftcard.objects.get(monto_inicial=15000)
        self.assertRedirects(r, reverse("beneficios:giftcard", args=[g.pk]))
        self.assertEqual(g.saldo_actual, 15000)  # saldo inicial = monto inicial
        self.assertEqual(g.estado, "vigente")
        self.assertEqual(g.comprador, g.beneficiario)  # sin comprador, compra el mismo beneficiario

    def test_usar_giftcard_en_ficha_descuenta_saldo(self):
        self.entrar(self.admin)
        g = self._crear_giftcard(10000)
        ficha = FichaAtencion.objects.filter(cliente=self.cliente).first() or FichaAtencion.objects.first()
        g.beneficiario = ficha.cliente
        g.save()
        self.client.post(reverse("beneficios:usar_giftcard", args=[ficha.pk]), {"giftcard": g.pk, "monto": 4000})
        g.refresh_from_db()
        self.assertEqual(g.saldo_actual, 6000)
        self.assertEqual(g.usos.count(), 1)

    def test_deshabilitar_exige_motivo_y_conserva_historial(self):
        self.entrar(self.admin)
        g = self._crear_giftcard()
        url = reverse("beneficios:giftcard_deshabilitar", args=[g.pk])
        self.client.post(url, {"motivo": ""})
        g.refresh_from_db()
        self.assertNotEqual(g.estado, "deshabilitada")  # sin motivo no se deshabilita
        self.client.post(url, {"motivo": "Solicitud del cliente"})
        g.refresh_from_db()
        self.assertEqual(g.estado, "deshabilitada")
        self.assertTrue(Giftcard.objects.filter(pk=g.pk).exists())  # no se borra

    def test_peluquero_no_puede_registrar_giftcards(self):
        self.entrar(self.pelu)
        r = self.client.get(reverse("beneficios:giftcard_nueva"))
        self.assertEqual(r.status_code, 403)  # RF-GC-15: solo administrador
