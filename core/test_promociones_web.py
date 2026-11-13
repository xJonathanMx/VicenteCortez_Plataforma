"""Pruebas por web de promociones: catálogo, venta, uso en una ficha y deshabilitar."""
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from core import rut
from core.models import ClientePromocion, Promocion, PromocionServicio, Servicio
from core.tests import Base
from fichas import servicios as fs


class PromocionWebTests(Base):
    def setUp(self):
        self.corte = Servicio.objects.get(nombre="Corte tradicional")

    def _promo(self, usos=2):
        p = Promocion.objects.create(nombre="Pack cortes", precio=20000)
        PromocionServicio.objects.create(promocion=p, servicio=self.corte, cantidad_total=usos)
        return p

    def _vendida(self, promo, dias=30):
        return ClientePromocion.objects.create(
            promocion=promo, comprador=self.cliente, beneficiario=self.cliente,
            fecha_vencimiento=timezone.localdate() + timedelta(days=dias), creada_por=self.admin)

    def test_crear_promocion_en_catalogo(self):
        self.entrar(self.admin)
        r = self.client.post(reverse("beneficios:promocion_nueva"), {
            "nombre": "Pack brushing", "precio": 30000, "servicio_0": self.corte.pk, "cantidad_0": 4})
        self.assertEqual(r.status_code, 302)
        p = Promocion.objects.get(nombre="Pack brushing")
        self.assertEqual(p.servicios.get().cantidad_total, 4)

    def test_activar_y_desactivar_promocion_del_catalogo(self):
        self.entrar(self.admin)
        p = self._promo()
        self.client.post(reverse("beneficios:promocion_estado", args=[p.pk]))
        p.refresh_from_db()
        self.assertFalse(p.activo)
        self.client.post(reverse("beneficios:promocion_estado", args=[p.pk]))
        p.refresh_from_db()
        self.assertTrue(p.activo)

    def test_vender_promocion_a_un_cliente(self):
        self.entrar(self.admin)
        p = self._promo()
        hoy = timezone.localdate()
        self.client.post(reverse("beneficios:vender_promocion"), {
            "promocion": p.pk,
            "comprador": rut.formatear(self.cliente.run, rut.calcular_dv(self.cliente.run)),
            "fecha_compra": hoy.isoformat(),
            "fecha_vencimiento": (hoy + timedelta(days=90)).isoformat()})
        cp = ClientePromocion.objects.get(promocion=p)
        self.assertEqual(cp.comprador, self.cliente)
        self.assertEqual(cp.estado, "vigente")

    def test_usar_promocion_en_ficha_registra_el_uso(self):
        self.entrar(self.admin)
        cp = self._vendida(self._promo(usos=2))
        ficha = fs.abrir_ficha(self.admin, self.cliente)
        fs.agregar_servicio(ficha, self.corte, self.pelu, "basico", self.admin)
        self.client.post(reverse("beneficios:usar_promocion", args=[ficha.pk]), {"uso": f"{cp.pk}-{self.corte.pk}"})
        self.assertEqual(cp.usos.count(), 1)

    def test_deshabilitar_promocion_vendida_exige_motivo(self):
        self.entrar(self.admin)
        cp = self._vendida(self._promo())
        url = reverse("beneficios:cliente_promocion_deshabilitar", args=[cp.pk])
        self.client.post(url, {"motivo": ""})
        cp.refresh_from_db()
        self.assertNotEqual(cp.estado, "deshabilitada")
        self.client.post(url, {"motivo": "Error de registro"})
        cp.refresh_from_db()
        self.assertEqual(cp.estado, "deshabilitada")
        self.assertTrue(ClientePromocion.objects.filter(pk=cp.pk).exists())

    def test_peluquero_no_puede_vender_promociones(self):
        self.entrar(self.pelu)
        self.assertEqual(self.client.get(reverse("beneficios:vender_promocion")).status_code, 403)
