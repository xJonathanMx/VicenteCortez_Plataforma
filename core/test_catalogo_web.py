"""Pruebas por web del catálogo: precios, comisiones, estados e insumos con su histórico."""
from django.urls import reverse

from core.models import (Comision, HistoricoComisionServicio, HistoricoEstadoServicio, HistoricoPrecioServicio,
                         Insumo, Servicio, TipoContrato, TipoServicio)
from core.tests import Base


class CatalogoWebTests(Base):
    def setUp(self):
        self.corte = Servicio.objects.get(nombre="Corte tradicional")

    def _datos_servicio(self, **cambios):
        s = self.corte
        datos = {"tipo": s.tipo_id, "nombre": s.nombre, "precio": s.precio, "tiempo_estimado": s.tiempo_estimado,
                 "descripcion": s.descripcion, "observacion": s.observacion}
        datos.update(cambios)
        return {k: v for k, v in datos.items() if v is not None}

    def test_cambiar_precio_guarda_historico(self):
        self.entrar(self.admin)
        antes = self.corte.precio
        r = self.client.post(reverse("catalogo:servicio_editar", args=[self.corte.pk]),
                             self._datos_servicio(precio=antes + 1000))
        self.assertEqual(r.status_code, 302)
        self.corte.refresh_from_db()
        self.assertEqual(self.corte.precio, antes + 1000)
        h = HistoricoPrecioServicio.objects.filter(servicio=self.corte).latest("fecha_cambio")
        self.assertEqual((h.precio_anterior, h.precio_nuevo, h.responsable), (antes, antes + 1000, self.admin))

    def test_sin_cambio_de_precio_no_crea_historico(self):
        self.entrar(self.admin)
        n = HistoricoPrecioServicio.objects.count()
        self.client.post(reverse("catalogo:servicio_editar", args=[self.corte.pk]),
                         self._datos_servicio(observacion="Solo cambia la observación"))
        self.assertEqual(HistoricoPrecioServicio.objects.count(), n)

    def test_deshabilitar_y_habilitar_servicio_deja_historial(self):
        self.entrar(self.admin)
        url = reverse("catalogo:servicio_estado", args=[self.corte.pk])
        self.client.post(url, {"motivo": "Ya no se ofrece"})
        self.corte.refresh_from_db()
        self.assertFalse(self.corte.activo)
        self.client.post(url, {"motivo": "Vuelve a ofrecerse"})
        self.corte.refresh_from_db()
        self.assertTrue(self.corte.activo)
        self.assertEqual(HistoricoEstadoServicio.objects.filter(servicio=self.corte).count(), 2)
        self.assertTrue(Servicio.objects.filter(pk=self.corte.pk).exists())  # nunca se borra

    def test_cambiar_comision_guarda_historico(self):
        self.entrar(self.admin)
        tipo = self.corte.tipo
        contrato = TipoContrato.objects.filter(aplica_comision=True).first()
        anterior = tipo.porcentaje_para(contrato)
        datos = {"nombre": tipo.nombre, "seguimiento": tipo.seguimiento, "descripcion": tipo.descripcion}
        for c in TipoContrato.objects.filter(aplica_comision=True):
            datos[f"comision_{c.pk}"] = tipo.porcentaje_para(c)
        datos[f"comision_{contrato.pk}"] = 47.5
        self.client.post(reverse("catalogo:tipo_editar", args=[tipo.pk]), datos)
        self.assertEqual(float(Comision.objects.get(tipo_servicio=tipo, contrato=contrato).porcentaje), 47.5)
        h = HistoricoComisionServicio.objects.filter(tipo_servicio=tipo, contrato=contrato).latest("fecha_cambio")
        self.assertEqual(float(h.porcentaje_nuevo), 47.5)
        self.assertEqual(float(h.porcentaje_anterior or 0), float(anterior or 0))

    def test_historial_de_comisiones_se_puede_ver(self):
        self.entrar(self.admin)
        r = self.client.get(reverse("catalogo:tipo_historial", args=[self.corte.tipo.pk]))
        self.assertEqual(r.status_code, 200)

    def test_crear_insumo_y_rechazar_duplicado(self):
        self.entrar(self.admin)
        datos = {"nombre": "Tinte prueba", "marca": "MarcaX", "calidad": "Premium", "unidad_medida": "ml"}
        self.client.post(reverse("catalogo:insumo_nuevo"), datos)
        self.assertEqual(Insumo.objects.filter(nombre="Tinte prueba").count(), 1)
        # RF-I-04: mismo insumo con otras mayúsculas y espacios = duplicado
        r = self.client.post(reverse("catalogo:insumo_nuevo"), {**datos, "nombre": "  TINTE PRUEBA "})
        self.assertEqual(r.status_code, 200)  # vuelve al formulario con el error
        self.assertEqual(Insumo.objects.filter(nombre__iexact="Tinte prueba").count(), 1)

    def test_desactivar_insumo_no_lo_borra(self):
        self.entrar(self.admin)
        i = Insumo.objects.first()
        self.client.post(reverse("catalogo:insumo_estado", args=[i.pk]))
        i.refresh_from_db()
        self.assertFalse(i.activo)
        self.assertTrue(Insumo.objects.filter(pk=i.pk).exists())

    def test_peluquero_no_accede_al_catalogo(self):
        self.entrar(self.pelu)
        self.assertEqual(self.client.get(reverse("catalogo:servicios")).status_code, 403)
