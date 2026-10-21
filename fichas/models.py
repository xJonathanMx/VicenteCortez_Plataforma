"""Fichas de atención, servicios realizados, insumos usados y trazabilidad."""
from django.conf import settings
from django.db import models
from django.utils import timezone

from catalogo.models import VARIANTES, Insumo, Servicio
from clientes.models import Cliente
from core.models import Auditado, SoloInsercion

ESTADOS_SERVICIO = [("pendiente", "Pendiente"), ("en_proceso", "En proceso"), ("terminado", "Terminado")]


class EstadoFicha(models.Model):
    codigo = models.SlugField("código", max_length=20, primary_key=True, db_column="id_estado_ficha")
    nombre = models.CharField("nombre", max_length=30)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "estado_ficha"
        ordering = ["orden"]

    def __str__(self):
        return self.nombre


class FichaAtencion(Auditado):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, null=True, blank=True, related_name="fichas",
                                db_column="run_cliente", help_text="Puede quedar vacío y vincularse después (RF-FA-02).")
    abierta_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="fichas_abiertas",
                                    db_column="run_usuario", verbose_name="abierta por")
    nombre_provisorio = models.CharField("nombre provisorio del cliente", max_length=80, blank=True)
    fecha_hora_inicio = models.DateTimeField("inicio", default=timezone.now)
    fecha_hora_termino = models.DateTimeField("término", null=True, blank=True)
    diagnostico = models.TextField("diagnóstico inicial", blank=True)
    observaciones = models.TextField("observaciones", blank=True)
    estado = models.ForeignKey(EstadoFicha, on_delete=models.PROTECT, default="abierta", db_column="id_estado_ficha")
    validada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                     related_name="+")
    fecha_validacion = models.DateTimeField(null=True, blank=True)
    motivo_anulacion = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "ficha_atencion"
        ordering = ["-fecha_hora_inicio"]
        verbose_name = "ficha de atención"
        verbose_name_plural = "fichas de atención"

    def __str__(self):
        return f"Ficha N° {self.pk}"

    @property
    def nombre_cliente(self):
        return self.cliente.nombre_completo if self.cliente else (self.nombre_provisorio or "Cliente sin identificar")

    @property
    def total(self):
        return sum(s.precio_cobrado for s in self.servicios.all())

    @property
    def todos_terminados(self):
        servicios = list(self.servicios.all())
        return bool(servicios) and all(s.estado == "terminado" for s in servicios)

    @property
    def editable(self):
        return self.estado_id in ("abierta", "en_atencion")

    @property
    def peluqueros(self):
        return {s.peluquero for s in self.servicios.all()}

    @property
    def datos_completos(self):
        """RF-RP-11: cliente, peluquero, servicio, fecha y hora."""
        return bool(self.cliente_id and self.servicios.exists() and self.fecha_hora_inicio)


class DetalleAtencionServicio(Auditado):
    ficha = models.ForeignKey(FichaAtencion, on_delete=models.PROTECT, related_name="servicios", db_column="id_ficha")
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, related_name="atenciones", db_column="id_servicio")
    peluquero = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="atenciones",
                                  db_column="run_u_realiza_servicio")
    variante = models.CharField("calidad", max_length=12, choices=VARIANTES, default="basico")
    # Valores congelados al momento del registro (RF-FA-11, RF-CI-04).
    precio_cobrado = models.PositiveIntegerField("precio cobrado")
    porc_comision_guardado = models.DecimalField("comisión (%)", max_digits=5, decimal_places=2, default=0)
    aplica_comision = models.BooleanField("aplica comisión", default=False)
    estado = models.CharField("estado", max_length=12, choices=ESTADOS_SERVICIO, default="pendiente",
                              db_column="estado_atencion")
    hora_inicio = models.DateTimeField("hora de inicio", null=True, blank=True, db_column="hora_inicio_servicio")
    hora_termino = models.DateTimeField("hora de término", null=True, blank=True, db_column="hora_termino_servicio")
    cierre_manual = models.BooleanField(default=False)
    motivo_cierre = models.CharField("motivo de cierre manual", max_length=255, blank=True)
    formula = models.TextField("mezcla o fórmula", blank=True)
    observacion_producto = models.TextField("producto usado (observación)", blank=True)
    sesion_numero = models.PositiveSmallIntegerField("sesión", default=1)
    sesiones_totales = models.PositiveSmallIntegerField("sesiones totales", default=1)
    tratamiento_origen = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True,
                                           related_name="sesiones_siguientes",
                                           help_text="Primera sesión de un tratamiento multisesión (RF-FA-10).")

    class Meta:
        db_table = "detalle_atencion_servicio"
        ordering = ["id"]

    def __str__(self):
        return f"{self.servicio.nombre} ({self.get_variante_display()})"

    @property
    def monto_comision(self):
        """RF-CI-06: precio guardado × porcentaje guardado, solo para externos."""
        if not self.aplica_comision:
            return 0
        return round(self.precio_cobrado * float(self.porc_comision_guardado) / 100)

    @property
    def duracion_min(self):
        if self.hora_inicio and self.hora_termino:
            return int((self.hora_termino - self.hora_inicio).total_seconds() // 60)
        if self.hora_inicio:
            return int((timezone.now() - self.hora_inicio).total_seconds() // 60)
        return None

    @property
    def excedido(self):
        """RF-ES-06: abierto por más tiempo del estimado."""
        return self.estado == "en_proceso" and (self.duracion_min or 0) > self.servicio.tiempo_estimado

    @property
    def es_multisesion(self):
        return self.sesiones_totales > 1


class DetalleFichaInsumo(models.Model):
    detalle = models.ForeignKey(DetalleAtencionServicio, on_delete=models.CASCADE, related_name="insumos",
                                db_column="id_detalle_aten_s")
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name="usos", db_column="id_insumo")
    cant_usada = models.DecimalField("cantidad usada", max_digits=8, decimal_places=2, null=True, blank=True)
    observacion = models.CharField("observación", max_length=255, blank=True)

    class Meta:
        db_table = "detalle_ficha_insumo"


class HistorialEstadoFicha(SoloInsercion):
    ficha = models.ForeignKey(FichaAtencion, on_delete=models.PROTECT, related_name="historial", db_column="id_ficha")
    estado_anterior = models.ForeignKey(EstadoFicha, on_delete=models.PROTECT, null=True, related_name="+")
    estado = models.ForeignKey(EstadoFicha, on_delete=models.PROTECT, related_name="+", db_column="id_estado_ficha")
    fecha_hora_cambio = models.DateTimeField(default=timezone.now)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")
    motivo = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "historial_estado_ficha"
        ordering = ["-fecha_hora_cambio", "-id"]


class VersionFicha(SoloInsercion):
    """Copia de la ficha antes de una corrección o anulación (RF-FA-14)."""
    ficha = models.ForeignKey(FichaAtencion, on_delete=models.PROTECT, related_name="versiones")
    contenido = models.JSONField()
    motivo = models.CharField(max_length=255)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "version_ficha"
        ordering = ["-fecha"]
