from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import ClientePromocion, Giftcard, UsoGiftcard, UsoPromocion


def _exigir_admin(usuario):
    if not usuario.tiene_privilegio("gestionar_beneficios"):  # RF-GC-15 / RF-PR-15
        raise PermissionDenied


def _fecha_uso(ficha):
    """En una atención pasada el uso queda con la fecha de la atención, para que los reportes lo cuenten ahí."""
    return ficha.fecha_hora_inicio if ficha.registro_atrasado else timezone.now()


def _validar_vigencia(obj, nombre):
    estado = obj.actualizar_estado()
    if estado == "deshabilitada":
        raise ValidationError(f"La {nombre} está deshabilitada.")
    if estado == "vencida":
        raise ValidationError(f"La {nombre} venció el {obj.fecha_vencimiento:%d-%m-%Y}.")
    if estado == "agotada":
        raise ValidationError(f"La {nombre} ya no tiene saldo o usos disponibles.")


@transaction.atomic
def usar_giftcard(giftcard, ficha, monto, usuario, detalle=None):
    """RF-GC-07 a RF-GC-11."""
    _exigir_admin(usuario)
    giftcard = Giftcard.objects.select_for_update().get(pk=giftcard.pk)
    _validar_vigencia(giftcard, "giftcard")
    if monto <= 0:
        raise ValidationError("El monto debe ser mayor a cero.")
    if monto > giftcard.saldo_actual:
        raise ValidationError(f"El monto supera el saldo disponible (${giftcard.saldo_actual:,}).".replace(",", "."))
    uso = UsoGiftcard.objects.create(giftcard=giftcard, ficha=ficha, detalle=detalle, monto_usado=monto,
                                     fecha_uso=_fecha_uso(ficha), registrado_por=usuario)
    giftcard.saldo_actual -= monto
    giftcard.save(update_fields=["saldo_actual"])
    giftcard.actualizar_estado()
    return uso


@transaction.atomic
def usar_promocion(cliente_promocion, servicio, ficha, usuario, detalle=None):
    """RF-PR-07 a RF-PR-11."""
    _exigir_admin(usuario)
    cp = ClientePromocion.objects.select_for_update().get(pk=cliente_promocion.pk)
    _validar_vigencia(cp, "promoción")
    fila = next((f for f in cp.detalle_usos() if f["servicio"].pk == servicio.pk), None)
    if fila is None:
        raise ValidationError(f"{servicio.nombre} no está incluido en la promoción.")
    if fila["disponibles"] <= 0:
        raise ValidationError(f"Ya se usaron todas las veces de {servicio.nombre} en esta promoción.")
    uso = UsoPromocion.objects.create(cliente_promocion=cp, servicio=servicio, ficha=ficha, detalle=detalle,
                                      fecha_uso=_fecha_uso(ficha), registrado_por=usuario)
    cp.actualizar_estado()
    return uso


def deshabilitar(obj, motivo, usuario):
    """RF-GC-13 / RF-PR-13: sin eliminar, conservando historial."""
    _exigir_admin(usuario)
    if not motivo.strip():
        raise ValidationError("Indica el motivo.")
    obj.estado = "deshabilitada"
    obj.motivo_deshabilitacion = motivo
    obj.save(update_fields=["estado", "motivo_deshabilitacion"])
