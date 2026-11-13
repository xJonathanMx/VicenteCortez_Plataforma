"""Pruebas del comando procesar_envios (cron cada 15 minutos)."""
import io

from django.core.management import call_command

from core.tests import Base


class ProcesarEnviosTests(Base):
    def test_comando_corre_y_reporta_el_resumen(self):
        salida = io.StringIO()
        call_command("procesar_envios", stdout=salida)
        texto = salida.getvalue()
        self.assertIn("Valoraciones enviadas:", texto)
        self.assertIn("recordatorios enviados:", texto)
        self.assertIn("fallidos:", texto)

    def test_es_idempotente(self):
        # Una segunda pasada no debe reenviar nada (RF-VS-11).
        call_command("procesar_envios", stdout=io.StringIO())
        salida = io.StringIO()
        call_command("procesar_envios", stdout=salida)
        self.assertIn("Valoraciones enviadas: 0", salida.getvalue())
