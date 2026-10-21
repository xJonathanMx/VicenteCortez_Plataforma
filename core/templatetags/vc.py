from django import template
from django.utils import timezone

register = template.Library()

CLASES_ESTADO = {
    # fichas
    "abierta": "", "en_atencion": "negro vivo", "cerrada": "alerta", "validada": "ok", "anulada": "error",
    # servicios
    "pendiente": "", "en_proceso": "negro vivo", "terminado": "ok",
    # valoraciones / recordatorios
    "enviada": "alerta", "enviado": "ok", "respondida": "ok", "sin_respuesta": "", "error": "error",
    "fallido": "error", "cancelado": "",
    # beneficios
    "vigente": "ok", "agotada": "", "vencida": "alerta", "deshabilitada": "error",
}


@register.filter
def pesos(valor):
    """12345 -> $12.345"""
    if valor in (None, ""):
        return "—"
    try:
        return "$" + f"{int(round(float(valor))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return valor


@register.filter
def clase_estado(codigo):
    return CLASES_ESTADO.get(str(codigo), "")


@register.filter
def minutos(valor):
    if valor in (None, ""):
        return "—"
    valor = int(valor)
    return f"{valor // 60} h {valor % 60:02d} min" if valor >= 60 else f"{valor} min"


@register.filter
def iso(fecha):
    return timezone.localtime(fecha).isoformat() if fecha else ""


@register.simple_tag(takes_context=True)
def puede(context, codigo):
    user = context["request"].user
    return user.is_authenticated and user.tiene_privilegio(codigo)


@register.inclusion_tag("parciales/campo.html")
def campo(field, col=""):
    return {"field": field, "col": col}


@register.simple_tag(takes_context=True)
def url_con(context, **kwargs):
    """Mantiene los filtros actuales en la URL y cambia los indicados (ej. formato=xlsx)."""
    q = context["request"].GET.copy()
    for k, v in kwargs.items():
        q[k] = v
    return "?" + q.urlencode()
