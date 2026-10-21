from django.conf import settings
from django.db import models
from django.utils import timezone

from core import rut as rututil
from core.models import GENEROS, SoloInsercion, TipoEstado

CANALES = [("whatsapp", "WhatsApp"), ("email", "Correo electrónico")]


class ClienteQuerySet(models.QuerySet):
    def visibles_para(self, usuario):
        """RF-AS-02: el peluquero accede solo a la información de sus propios clientes."""
        if usuario.ve_todos_los_clientes:
            return self
        return self.filter(
            models.Q(estilista_fijo=usuario) | models.Q(fichas__servicios__peluquero=usuario)
            | models.Q(creado_por=usuario) | models.Q(fichas__abierta_por=usuario)
        ).distinct()


class Cliente(models.Model):
    run = models.CharField("RUN", max_length=8, primary_key=True, db_column="run_cliente")
    dv = models.CharField("dígito verificador", max_length=1)
    nombre = models.CharField("nombres", max_length=60)
    ap_paterno = models.CharField("apellido paterno", max_length=60)
    ap_materno = models.CharField("apellido materno", max_length=60, blank=True)
    telefono = models.CharField("teléfono", max_length=15, blank=True)
    correo = models.EmailField("correo", max_length=120, blank=True)
    fecha_nac = models.DateField("fecha de nacimiento", null=True, blank=True)
    genero = models.CharField("género", max_length=1, choices=GENEROS, blank=True)
    canal_preferido = models.CharField("canal de contacto", max_length=10, choices=CANALES, default="email")
    estilista_fijo = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="clientes_fijos", verbose_name="estilista fijo")
    activo = models.BooleanField("activo", default=True, db_column="c_activo")
    creado_en = models.DateTimeField("registrado en", auto_now_add=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True,
                                   related_name="+", verbose_name="registrado por")

    objects = ClienteQuerySet.as_manager()

    class Meta:
        db_table = "cliente"
        ordering = ["nombre", "ap_paterno"]

    def __str__(self):
        return self.nombre_completo

    @property
    def nombre_completo(self):
        return " ".join(p for p in [self.nombre, self.ap_paterno, self.ap_materno] if p)

    @property
    def run_formateado(self):
        return rututil.formatear(self.run, self.dv)

    @property
    def inicial(self):
        return (self.nombre or "?")[0].upper()

    @property
    def datos_completos(self):
        """Tiene cómo recibir valoraciones y recordatorios con los canales habilitados."""
        if "whatsapp" in settings.CANALES_ENVIO:
            return bool(self.telefono or self.correo)
        return bool(self.correo)

    def resumen(self):
        """RF-C-06: última visita, cantidad de visitas y estilista fijo."""
        fichas = self.fichas.exclude(estado="anulada")
        ultima = fichas.order_by("-fecha_hora_inicio").first()
        return {
            "visitas": fichas.count(),
            "ultima_visita": ultima.fecha_hora_inicio if ultima else None,
            "estilista_fijo": self.estilista_fijo,
        }


class HistoricoEstadoCliente(SoloInsercion):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="historial_estados",
                                db_column="run_cliente")
    tipo_estado = models.ForeignKey(TipoEstado, on_delete=models.PROTECT, db_column="id_tipo_estado")
    observacion = models.CharField("motivo", max_length=255)
    fecha_cambio = models.DateTimeField("fecha del cambio", default=timezone.now)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True,
                                    related_name="+")

    class Meta:
        db_table = "historico_estado_cliente"
        ordering = ["-fecha_cambio"]


class ConsultaHistorial(SoloInsercion):
    """Cada vez que un usuario abre el historial de un cliente (RF-RP-12)."""
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="+")
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "consulta_historial"
