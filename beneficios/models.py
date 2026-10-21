"""Giftcards y promociones, solo informativas: no se procesan pagos."""
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from catalogo.models import Servicio
from clientes.models import Cliente
from fichas.models import DetalleAtencionServicio, FichaAtencion

ESTADOS = [("vigente", "Vigente"), ("agotada", "Agotada"), ("vencida", "Vencida"), ("deshabilitada", "Deshabilitada")]


def generar_codigo(prefijo, modelo):
    while True:
        codigo = f"{prefijo}-{secrets.token_hex(3).upper()}"
        if not modelo.objects.filter(codigo=codigo).exists():
            return codigo


class Giftcard(models.Model):
    codigo = models.CharField("código", max_length=20, unique=True, editable=False)
    comprador = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="giftcards_compradas",
                                  db_column="comprador_run_cliente", null=True, blank=True)
    beneficiario = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="giftcards",
                                     db_column="beneficiario_run_cliente")
    monto_inicial = models.PositiveIntegerField("monto inicial")
    saldo_actual = models.PositiveIntegerField("saldo actual")
    fecha_compra = models.DateField("fecha de compra", default=timezone.localdate)
    fecha_vencimiento = models.DateField("fecha de vencimiento")
    estado = models.CharField(max_length=15, choices=ESTADOS, default="vigente", db_column="estado_giftcard")
    motivo_deshabilitacion = models.CharField(max_length=255, blank=True)
    creada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "giftcard"
        ordering = ["-fecha_compra"]

    def __str__(self):
        return self.codigo

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = generar_codigo("GC", Giftcard)          # RF-GC-02
        if self.saldo_actual is None:
            self.saldo_actual = self.monto_inicial                 # RF-GC-04
        super().save(*args, **kwargs)

    def actualizar_estado(self):
        """RF-GC-11: agotada al llegar a cero, vencida al pasar la fecha."""
        if self.estado == "deshabilitada":
            return self.estado
        if self.saldo_actual == 0:
            nuevo = "agotada"
        elif self.fecha_vencimiento < timezone.localdate():
            nuevo = "vencida"
        else:
            nuevo = "vigente"
        if nuevo != self.estado:
            self.estado = nuevo
            self.save(update_fields=["estado"])
        return self.estado


class UsoGiftcard(models.Model):
    giftcard = models.ForeignKey(Giftcard, on_delete=models.PROTECT, related_name="usos", db_column="id_giftcard")
    ficha = models.ForeignKey(FichaAtencion, on_delete=models.PROTECT, related_name="usos_giftcard",
                              db_column="id_ficha")
    detalle = models.ForeignKey(DetalleAtencionServicio, on_delete=models.PROTECT, null=True, blank=True,
                                db_column="id_detalle_aten_s")
    monto_usado = models.PositiveIntegerField("monto usado")
    fecha_uso = models.DateTimeField(default=timezone.now)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        db_table = "uso_giftcard"
        ordering = ["-fecha_uso"]


class Promocion(models.Model):
    """Promoción del catálogo (ej. 'Pack 4 brushing')."""
    nombre = models.CharField("nombre", max_length=80, db_column="nombre_promocion")
    precio = models.PositiveIntegerField("precio")
    activo = models.BooleanField("activa", default=True, db_column="estado_promocion")

    class Meta:
        db_table = "promocion"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class PromocionServicio(models.Model):
    promocion = models.ForeignKey(Promocion, on_delete=models.CASCADE, related_name="servicios",
                                  db_column="id_promocion")
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, db_column="id_servicio")
    cantidad_total = models.PositiveSmallIntegerField("cantidad de usos", default=1)

    class Meta:
        db_table = "promocion_servicio"
        unique_together = [("promocion", "servicio")]


class ClientePromocion(models.Model):
    """Promoción adquirida por un cliente; aquí se controlan sus usos."""
    codigo = models.CharField("código", max_length=20, unique=True, editable=False)
    promocion = models.ForeignKey(Promocion, on_delete=models.PROTECT, related_name="ventas", db_column="id_promocion")
    comprador = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="promociones",
                                  db_column="run_cliente_comprador")
    beneficiario = models.ForeignKey(Cliente, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
                                     db_column="run_cliente_beneficiario")
    fecha_compra = models.DateField("fecha de compra", default=timezone.localdate)
    fecha_vencimiento = models.DateField("fecha de vencimiento")
    estado = models.CharField(max_length=15, choices=ESTADOS, default="vigente", db_column="estado_compra_promocion")
    motivo_deshabilitacion = models.CharField(max_length=255, blank=True)
    creada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cliente_promocion"
        ordering = ["-fecha_compra"]

    def __str__(self):
        return f"{self.codigo} ({self.promocion})"

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = generar_codigo("PR", ClientePromocion)
        super().save(*args, **kwargs)

    def detalle_usos(self):
        """Por cada servicio incluido: total, usados y disponibles (RF-PR-05)."""
        usados = {}
        for u in self.usos.all():
            usados[u.servicio_id] = usados.get(u.servicio_id, 0) + u.cantidad_usada
        filas = []
        for ps in self.promocion.servicios.select_related("servicio"):
            u = usados.get(ps.servicio_id, 0)
            filas.append({"servicio": ps.servicio, "total": ps.cantidad_total, "usados": u,
                          "disponibles": max(ps.cantidad_total - u, 0)})
        return filas

    def actualizar_estado(self):
        if self.estado == "deshabilitada":
            return self.estado
        filas = self.detalle_usos()
        if filas and all(f["disponibles"] == 0 for f in filas):
            nuevo = "agotada"
        elif self.fecha_vencimiento < timezone.localdate():
            nuevo = "vencida"
        else:
            nuevo = "vigente"
        if nuevo != self.estado:
            self.estado = nuevo
            self.save(update_fields=["estado"])
        return self.estado


class UsoPromocion(models.Model):
    cliente_promocion = models.ForeignKey(ClientePromocion, on_delete=models.PROTECT, related_name="usos",
                                          db_column="id_cliente_promocion")
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, db_column="id_servicio")
    ficha = models.ForeignKey(FichaAtencion, on_delete=models.PROTECT, related_name="usos_promocion",
                              db_column="id_ficha")
    detalle = models.ForeignKey(DetalleAtencionServicio, on_delete=models.PROTECT, null=True, blank=True,
                                db_column="id_detalle_aten_s")
    cantidad_usada = models.PositiveSmallIntegerField(default=1)
    fecha_uso = models.DateTimeField(default=timezone.now)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        db_table = "uso_promocion"
        ordering = ["-fecha_uso"]
