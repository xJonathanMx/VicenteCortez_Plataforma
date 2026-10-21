"""Valoraciones de seguimiento, recordatorios programados y canales de envío."""
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from clientes.models import Cliente
from fichas.models import DetalleAtencionServicio, FichaAtencion

TIPOS_MENSAJE = [
    ("valoracion", "Valoración de seguimiento"),
    ("renovacion", "Recordatorio de renovación"),
    ("giftcard", "Giftcard por vencer"),
]


def nuevo_token():
    return secrets.token_urlsafe(24)


class CanalComunicacion(models.Model):
    codigo = models.SlugField(max_length=20, unique=True)
    nombre = models.CharField("nombre del medio", max_length=40, db_column="nombre_medio")
    activo = models.BooleanField("activo", default=True)

    class Meta:
        db_table = "canal_comunicacion"
        verbose_name = "canal de comunicación"
        verbose_name_plural = "canales de comunicación"

    def __str__(self):
        return self.nombre


class Plantilla(models.Model):
    """Texto de cada mensaje. Variables: {nombre}, {servicio}, {peluquero}, {enlace}, {fecha}, {codigo}, {saldo}."""
    tipo = models.CharField("tipo de mensaje", max_length=12, choices=TIPOS_MENSAJE)
    canal = models.ForeignKey(CanalComunicacion, on_delete=models.PROTECT, related_name="plantillas")
    asunto = models.CharField("asunto (solo correo)", max_length=120, blank=True)
    cuerpo = models.TextField("mensaje")

    class Meta:
        db_table = "plantilla_mensaje"
        unique_together = [("tipo", "canal")]

    def __str__(self):
        return f"{self.get_tipo_display()} por {self.canal}"


class Valoracion(models.Model):
    ESTADOS = [("pendiente", "Pendiente"), ("enviada", "Enviada"), ("respondida", "Respondida"),
               ("sin_respuesta", "Sin respuesta"), ("error", "Error de envío")]
    TIPOS = [("dia_siguiente", "Día siguiente"), ("fin_mes", "Fin de mes")]

    ficha = models.ForeignKey(FichaAtencion, on_delete=models.PROTECT, related_name="valoraciones",
                              db_column="id_ficha")
    peluquero = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="valoraciones")
    tipo = models.CharField(max_length=15, choices=TIPOS)
    fecha_programada = models.DateField("fecha programada")
    estado = models.CharField(max_length=15, choices=ESTADOS, default="pendiente", db_column="estado_recibida")
    token = models.CharField(max_length=40, unique=True, default=nuevo_token)
    fecha_envio = models.DateTimeField(null=True, blank=True)
    fecha_respuesta = models.DateTimeField(null=True, blank=True)
    calificacion = models.PositiveSmallIntegerField(null=True, blank=True)
    respuesta = models.CharField("comentario", max_length=255, blank=True)
    intentos = models.PositiveSmallIntegerField(default=0)
    ultimo_error = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "valoracion"
        ordering = ["-fecha_programada"]
        # RF-VS-11 / RF-RC-03: no se duplican valoraciones de una misma ficha.
        constraints = [models.UniqueConstraint(fields=["ficha", "tipo"], name="valoracion_unica_por_ficha")]

    def __str__(self):
        return f"Valoración {self.get_tipo_display().lower()} de la ficha {self.ficha_id}"

    @property
    def enlace(self):
        return f"{settings.SITIO_URL.rstrip('/')}/valorar/{self.token}/"


class Recordatorio(models.Model):
    ESTADOS = [("pendiente", "Pendiente"), ("enviado", "Enviado"), ("fallido", "Fallido"), ("cancelado", "Cancelado")]

    tipo = models.CharField(max_length=12, choices=TIPOS_MENSAJE)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="recordatorios")
    detalle = models.ForeignKey(DetalleAtencionServicio, on_delete=models.PROTECT, null=True, blank=True,
                                related_name="recordatorios", db_column="id_detalle_aten_s")
    giftcard = models.ForeignKey("beneficios.Giftcard", on_delete=models.PROTECT, null=True, blank=True,
                                 related_name="recordatorios")
    fecha_programada = models.DateField()
    fecha_envio = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default="pendiente", db_column="estado_enviado")
    intentos = models.PositiveSmallIntegerField(default=0)
    ultimo_error = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "recordatorio"
        ordering = ["-fecha_programada"]


class EnvioMensaje(models.Model):
    """Cada intento de envío, exitoso o fallido (RF-RP-08, RNF Confiabilidad-02)."""
    canal = models.ForeignKey(CanalComunicacion, on_delete=models.PROTECT, db_column="id_medio_comunicacion")
    destino = models.CharField(max_length=120)
    valoracion = models.ForeignKey(Valoracion, on_delete=models.PROTECT, null=True, blank=True, related_name="envios")
    recordatorio = models.ForeignKey(Recordatorio, on_delete=models.PROTECT, null=True, blank=True,
                                     related_name="envios")
    exitoso = models.BooleanField()
    simulado = models.BooleanField(default=False)
    error = models.CharField(max_length=255, blank=True)
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "envio_mensaje"
        ordering = ["-fecha"]
