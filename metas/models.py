"""Metas mensuales e incentivos informativos (no se procesan pagos, RF-CI-14)."""
from django.conf import settings
from django.db import models


class NivelIncentivo(models.Model):
    """Escala de incentivo según % de cumplimiento (RF-CI-11)."""
    porcentaje_minimo = models.PositiveSmallIntegerField("cumplimiento mínimo (%)", unique=True)
    porcentaje_pago = models.PositiveSmallIntegerField("% del incentivo base que se informa")

    class Meta:
        db_table = "nivel_incentivo"
        ordering = ["porcentaje_minimo"]

    def __str__(self):
        return f"Desde {self.porcentaje_minimo}%: {self.porcentaje_pago}% del incentivo"


class MetaMensual(models.Model):
    peluquero = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="metas",
                                  db_column="run_usuario")
    mes = models.PositiveSmallIntegerField("mes")
    anio = models.PositiveSmallIntegerField("año")
    meta_cliente = models.PositiveIntegerField("meta de atenciones")
    incentivo_base = models.PositiveIntegerField("incentivo base ($)", default=0,
                                                 help_text="Puede ser 0 si el incentivo es solo un premio.")
    premio = models.CharField("premio o regalo", max_length=120, blank=True,
                              help_text="Incentivo no monetario al cumplir la meta (ej. kit de productos).")
    # Se congelan al cerrar el mes (RF-CI-13, RF-CI-15).
    cerrada = models.BooleanField(default=False)
    resultado_logrado = models.PositiveIntegerField("atenciones logradas", null=True, blank=True)
    porcentaje_logrado = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    incentivo_calculado = models.PositiveIntegerField(null=True, blank=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    cerrada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                    related_name="+")

    class Meta:
        db_table = "meta"
        ordering = ["-anio", "-mes", "peluquero__nombre"]
        unique_together = [("peluquero", "mes", "anio")]

    def __str__(self):
        return f"Meta {self.mes:02d}/{self.anio} de {self.peluquero}"
