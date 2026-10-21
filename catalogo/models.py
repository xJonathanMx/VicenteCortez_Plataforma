"""Catálogo de servicios, comisiones, insumos e históricos de precio/comisión/estado."""
from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import Especialidad, NivelHabilidad, SoloInsercion, TipoContrato, TipoEstado

VARIANTES = [("basico", "Básico"), ("plus", "Plus"), ("ultra_plus", "Ultra plus")]

SEGUIMIENTO = [
    ("corte", "Corte: 1 valoración al día siguiente"),
    ("tratamiento", "Tratamiento: valoración al día siguiente y a fin de mes"),
    ("ninguno", "Sin valoración"),
]


class TipoServicio(models.Model):
    nombre = models.CharField("nombre", max_length=60, unique=True, db_column="nombre_servicio")
    descripcion = models.CharField("descripción", max_length=255, blank=True)
    seguimiento = models.CharField("regla de valoración", max_length=12, choices=SEGUIMIENTO, default="corte",
                                   help_text="Define cuántas valoraciones se programan (RF-VS-02 a 04).")
    activo = models.BooleanField("activo", default=True, db_column="estado_tipo_servicio")

    class Meta:
        db_table = "tipo_servicio"
        verbose_name = "tipo de servicio"
        verbose_name_plural = "tipos de servicio"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def porcentaje_para(self, contrato):
        if not contrato:
            return 0
        c = self.comisiones.filter(contrato=contrato).first()
        return c.porcentaje if c else 0


class Comision(models.Model):
    """Porcentaje de comisión vigente por tipo de servicio y tipo de contrato."""
    tipo_servicio = models.ForeignKey(TipoServicio, on_delete=models.PROTECT, related_name="comisiones",
                                      db_column="id_tipo_servicio")
    contrato = models.ForeignKey(TipoContrato, on_delete=models.PROTECT, db_column="id_contrato")
    porcentaje = models.DecimalField("porcentaje", max_digits=5, decimal_places=2)

    class Meta:
        db_table = "comision"
        unique_together = [("tipo_servicio", "contrato")]


class HistoricoComisionServicio(SoloInsercion):
    tipo_servicio = models.ForeignKey(TipoServicio, on_delete=models.PROTECT, related_name="historial_comisiones",
                                      db_column="id_tipo_servicio")
    contrato = models.ForeignKey(TipoContrato, on_delete=models.PROTECT, db_column="tipo_contrato")
    porcentaje_anterior = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    porcentaje_nuevo = models.DecimalField(max_digits=5, decimal_places=2)
    fecha_cambio = models.DateTimeField(default=timezone.now)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")

    class Meta:
        db_table = "historico_comision_servicio"
        ordering = ["-fecha_cambio"]


class Servicio(models.Model):
    tipo = models.ForeignKey(TipoServicio, on_delete=models.PROTECT, related_name="servicios",
                             db_column="id_tipo_servicio", verbose_name="tipo de servicio")
    nombre = models.CharField("nombre", max_length=80)
    precio = models.PositiveIntegerField("precio básico")
    precio_plus = models.PositiveIntegerField("precio plus", null=True, blank=True)
    precio_ultra_plus = models.PositiveIntegerField("precio ultra plus", null=True, blank=True)
    tiempo_estimado = models.PositiveIntegerField("tiempo estimado (minutos)", default=60)
    descripcion = models.TextField("descripción", blank=True, db_column="descripcion_servicio")
    observacion = models.CharField("observación", max_length=255, blank=True)
    costo_estimado = models.PositiveIntegerField("costo estimado", null=True, blank=True)
    dia_renovacion = models.PositiveIntegerField(
        "días para renovación", null=True, blank=True,
        help_text="Si se indica, se programa un recordatorio de renovación (ej. tinturas).")
    especialidades = models.ManyToManyField(Especialidad, blank=True, db_table="servicio_especialidad",
                                            verbose_name="especialidades requeridas")
    activo = models.BooleanField("activo", default=True, db_column="estado_actual_servicio")

    class Meta:
        db_table = "servicio"
        ordering = ["tipo__nombre", "nombre"]
        unique_together = [("tipo", "nombre")]

    def __str__(self):
        return f"{self.nombre} ({self.tipo.nombre})"

    def precio_de(self, variante):
        return {"plus": self.precio_plus, "ultra_plus": self.precio_ultra_plus}.get(variante) or self.precio


class HistoricoPrecioServicio(SoloInsercion):
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, related_name="historial_precios",
                                 db_column="id_servicio")
    variante = models.CharField(max_length=12, choices=VARIANTES, default="basico")
    precio_anterior = models.PositiveIntegerField(null=True)
    precio_nuevo = models.PositiveIntegerField(null=True)
    fecha_cambio = models.DateTimeField(default=timezone.now)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")

    class Meta:
        db_table = "historico_precio_servicio"
        ordering = ["-fecha_cambio"]


class HistoricoEstadoServicio(SoloInsercion):
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, related_name="historial_estados",
                                 db_column="id_servicio")
    tipo_estado = models.ForeignKey(TipoEstado, on_delete=models.PROTECT, db_column="id_tipo_estado")
    motivo = models.CharField(max_length=255, blank=True)
    fecha_cambio = models.DateTimeField(default=timezone.now)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")

    class Meta:
        db_table = "historico_estado_servicio"
        ordering = ["-fecha_cambio"]


class UsuarioServicio(models.Model):
    """Servicios que cada peluquero tiene habilitados y su nivel (RF-FA-04)."""
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="servicios_habilitados", db_column="run_usuario")
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, related_name="habilitados",
                                 db_column="id_servicio")
    nivel = models.ForeignKey(NivelHabilidad, on_delete=models.PROTECT, null=True, blank=True,
                              db_column="id_nivel_hab", verbose_name="nivel de habilidad")
    activo = models.BooleanField("habilitado", default=True, db_column="es_activo")

    class Meta:
        db_table = "usuario_servicio"
        unique_together = [("usuario", "servicio")]


class Insumo(models.Model):
    nombre = models.CharField("nombre", max_length=80, db_column="nombre_insumo")
    marca = models.CharField("marca", max_length=60)
    calidad = models.CharField("calidad", max_length=40)
    unidad_medida = models.CharField("unidad de medida", max_length=20, default="ml")
    activo = models.BooleanField("activo", default=True, db_column="estado")

    class Meta:
        db_table = "insumo"
        ordering = ["nombre", "marca"]
        constraints = [models.UniqueConstraint(fields=["nombre", "marca", "calidad"], name="insumo_unico")]

    def __str__(self):
        return f"{self.nombre}, {self.marca} ({self.calidad})"
