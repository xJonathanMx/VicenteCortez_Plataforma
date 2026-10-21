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
    incentivo_base = models.PositiveIntegerField(
        "incentivo en dinero ($)", default=0,
        help_text="Suma de los incentivos en dinero de la lista; se calcula sola al guardar.")
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


class IncentivoMeta(models.Model):
    """Cada incentivo de la meta: dinero (proporcional al avance) o un regalo/beneficio (al cumplir)."""
    TIPOS = [("dinero", "Dinero"), ("regalo", "Regalo o producto"), ("otro", "Otro beneficio")]

    meta = models.ForeignKey(MetaMensual, on_delete=models.CASCADE, related_name="incentivos", db_column="id_meta")
    tipo = models.CharField("tipo", max_length=10, choices=TIPOS)
    descripcion = models.CharField("descripción", max_length=120, blank=True,
                                   help_text="Ej. Kit de productos Kérastase, día libre.")
    monto = models.PositiveIntegerField("monto ($)", null=True, blank=True)

    class Meta:
        db_table = "incentivo_meta"
        ordering = ["id"]
        verbose_name = "incentivo de la meta"
        verbose_name_plural = "incentivos de la meta"

    def __str__(self):
        if self.tipo == "dinero":
            return f"${self.monto or 0:,}".replace(",", ".") + (f" ({self.descripcion})" if self.descripcion else "")
        return self.descripcion
