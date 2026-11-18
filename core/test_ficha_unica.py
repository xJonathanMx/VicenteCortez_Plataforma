"""Un cliente no puede tener dos fichas abiertas a la vez (atención de hoy)."""
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from core.models import FichaAtencion
from core.tests import Base
from fichas import servicios as fs


class FichaUnicaTests(Base):
    def setUp(self):
        FichaAtencion.objects.filter(cliente=self.cliente, estado_id__in=("abierta", "en_atencion")).update(
            estado_id="anulada")

    def test_no_abre_una_segunda_ficha_para_el_mismo_cliente(self):
        f1 = fs.abrir_ficha(self.admin, self.cliente)
        with self.assertRaisesMessage(ValidationError, f"ficha N° {f1.pk}"):
            fs.abrir_ficha(self.admin, self.cliente)

    def test_si_la_anterior_se_anula_se_puede_abrir_otra(self):
        f1 = fs.abrir_ficha(self.admin, self.cliente)
        fs.anular_ficha(f1, self.admin, "Error de registro")
        self.assertTrue(fs.abrir_ficha(self.admin, self.cliente).pk)

    def test_sin_cliente_se_pueden_abrir_varias(self):
        fs.abrir_ficha(self.admin, None, "Clienta de pelo largo")
        fs.abrir_ficha(self.admin, None, "Cliente de barba")

    def test_registro_atrasado_convive_con_la_ficha_de_hoy(self):
        fs.abrir_ficha(self.admin, self.cliente)
        ayer = timezone.now() - timedelta(days=1)
        f = fs.abrir_ficha(self.admin, self.cliente, fecha_hora_inicio=ayer, motivo_atraso="Sin sistema")
        self.assertTrue(f.registro_atrasado)

    def test_vincular_cliente_con_ficha_abierta_se_rechaza(self):
        f1 = fs.abrir_ficha(self.admin, self.cliente)
        f2 = fs.abrir_ficha(self.admin, None, "Sin identificar")
        self.entrar(self.admin)
        r = self.client.post(reverse("fichas:vincular", args=[f2.pk]), {"cliente": self.cliente.run_formateado},
                             follow=True)
        f2.refresh_from_db()
        self.assertIsNone(f2.cliente_id)
        self.assertContains(r, f"ficha N° {f1.pk}")
