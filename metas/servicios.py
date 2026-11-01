"""Cálculo de metas, incentivos y comisiones. Todo es informativo (RF-CI-14)."""
import calendar
from datetime import datetime, time

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from core.models import DetalleAtencionServicio, MetaMensual, NivelIncentivo


MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]


def rango_mes(mes, anio):
    tz = timezone.get_current_timezone()
    inicio = timezone.make_aware(datetime(anio, mes, 1), tz)
    ultimo = calendar.monthrange(anio, mes)[1]
    fin = timezone.make_aware(datetime.combine(datetime(anio, mes, ultimo), time.max), tz)
    return inicio, fin


def servicios_validos():
    """Servicios terminados de fichas no anuladas: la base de metas y comisiones."""
    return DetalleAtencionServicio.objects.filter(estado="terminado").exclude(ficha__estado="anulada")


def atenciones_del_mes(mes, anio, peluquero=None):
    """RF-CI-10: atenciones = fichas distintas en que el peluquero terminó al menos un servicio."""
    inicio, fin = rango_mes(mes, anio)
    qs = servicios_validos().filter(hora_termino__range=(inicio, fin))
    if peluquero is not None:
        return qs.filter(peluquero=peluquero).values("ficha").distinct().count()
    return dict(qs.values("peluquero").annotate(n=Count("ficha", distinct=True)).values_list("peluquero", "n"))


def incentivo_para(porcentaje, base):
    """RF-CI-11: el nivel más alto alcanzado define qué parte del incentivo base se informa."""
    nivel = NivelIncentivo.objects.filter(porcentaje_minimo__lte=porcentaje).order_by("-porcentaje_minimo").first()
    return round(base * nivel.porcentaje_pago / 100) if nivel else 0


def avance(meta, logradas=None):
    """RF-CI-12: meta, avance y estado del incentivo. Si el mes está cerrado, usa lo congelado."""
    if meta.cerrada:
        logradas, pct, incentivo = meta.resultado_logrado, float(meta.porcentaje_logrado), meta.incentivo_calculado
    else:
        if logradas is None:
            logradas = atenciones_del_mes(meta.mes, meta.anio, meta.peluquero)
        pct = round(logradas * 100 / meta.meta_cliente, 1) if meta.meta_cliente else 0
        incentivo = incentivo_para(pct, meta.incentivo_base)
    cumplida = pct >= 100
    return {
        "meta": meta, "logradas": logradas, "porcentaje": pct, "incentivo": incentivo,
        "cumplida": cumplida, "estado": "Cumplida" if cumplida else ("Cerrada" if meta.cerrada else "En curso"),
        "faltan": max(meta.meta_cliente - logradas, 0),
        # Entero: un decimal con coma ("32,0") dejaba la barra llena porque el CSS no lo entiende.
        "barra": int(min(pct, 100)),
        "incentivos": detalle_incentivos(meta, pct, cumplida),
    }


def detalle_incentivos(meta, pct, cumplida):
    """
    Cada incentivo de la lista con lo que se informa hoy:
    el dinero va proporcional al avance (escala), los regalos y beneficios se ganan al cumplir.
    """
    filas = []
    for inc in meta.incentivos.all():
        if inc.tipo == "dinero":
            filas.append({"inc": inc, "dinero": True, "monto": inc.monto or 0,
                          "informado": incentivo_para(pct, inc.monto or 0), "ganado": cumplida})
        else:
            filas.append({"inc": inc, "dinero": False, "ganado": cumplida})
    return filas


def avances_del_mes(mes, anio):
    conteo = atenciones_del_mes(mes, anio)
    metas = MetaMensual.objects.filter(mes=mes, anio=anio).select_related("peluquero")
    return [avance(m, conteo.get(m.peluquero_id, 0)) for m in metas]


@transaction.atomic
def cerrar_mes(mes, anio, usuario):
    """RF-CI-15: congela resultados para que no cambien si se corrigen fichas después."""
    metas = MetaMensual.objects.select_for_update().filter(mes=mes, anio=anio, cerrada=False)
    if not metas.exists():
        raise ValidationError("No hay metas abiertas para ese mes.")
    hoy = timezone.localdate()
    if (anio, mes) >= (hoy.year, hoy.month):
        raise ValidationError("Solo se puede cerrar un mes que ya terminó.")
    conteo = atenciones_del_mes(mes, anio)
    for m in metas:
        a = avance(m, conteo.get(m.peluquero_id, 0))
        m.resultado_logrado = a["logradas"]
        m.porcentaje_logrado = a["porcentaje"]
        m.incentivo_calculado = a["incentivo"]
        m.cerrada = True
        m.fecha_cierre = timezone.now()
        m.cerrada_por = usuario
        m.save()
    return metas.count()


def comisiones(desde, hasta, peluquero=None):
    """RF-CI-06 / RF-CI-07 / RF-CI-08: usa el precio y porcentaje guardados en cada atención."""
    tz = timezone.get_current_timezone()
    inicio = timezone.make_aware(datetime.combine(desde, time.min), tz)
    fin = timezone.make_aware(datetime.combine(hasta, time.max), tz)
    qs = servicios_validos().filter(aplica_comision=True, hora_termino__range=(inicio, fin)).select_related(
        "servicio__tipo", "peluquero", "ficha__cliente").order_by("peluquero__nombre", "hora_termino")
    if peluquero is not None:
        qs = qs.filter(peluquero=peluquero)
    por_peluquero = {}
    for d in qs:
        fila = por_peluquero.setdefault(d.peluquero_id, {"peluquero": d.peluquero, "servicios": 0, "ventas": 0,
                                                          "comision": 0, "detalle": []})
        fila["servicios"] += 1
        fila["ventas"] += d.precio_cobrado
        fila["comision"] += d.monto_comision
        fila["detalle"].append(d)
    return list(por_peluquero.values())
