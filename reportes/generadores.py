"""
Cada reporte recibe los filtros (desde, hasta, peluquero, servicio) y devuelve
un dict con columnas, filas y un resumen opcional. La misma salida se usa para
la pantalla, Excel y PDF (RF-RP-15).
"""
from datetime import datetime, time

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from beneficios.models import ClientePromocion, Giftcard, UsoGiftcard, UsoPromocion
from clientes.models import Cliente, ConsultaHistorial
from core.models import RegistroAcceso, Usuario
from fichas.models import DetalleAtencionServicio, DetalleFichaInsumo, FichaAtencion
from metas import servicios as ms
from metas.models import MetaMensual
from seguimiento.models import EnvioMensaje, Valoracion


def rango(f):
    tz = timezone.get_current_timezone()
    return (timezone.make_aware(datetime.combine(f["desde"], time.min), tz),
            timezone.make_aware(datetime.combine(f["hasta"], time.max), tz))


def pct(a, b):
    return round(a * 100 / b, 1) if b else 0


def servicios_filtrados(f):
    qs = (DetalleAtencionServicio.objects.exclude(ficha__estado="anulada")
          .filter(ficha__fecha_hora_inicio__range=rango(f)))
    if f.get("peluquero"):
        qs = qs.filter(peluquero=f["peluquero"])
    if f.get("servicio"):
        qs = qs.filter(servicio=f["servicio"])
    return qs


def r_atenciones(f):
    qs = servicios_filtrados(f).select_related("ficha__cliente", "peluquero", "servicio").order_by("ficha__fecha_hora_inicio")
    filas = [[timezone.localtime(d.ficha.fecha_hora_inicio).strftime("%d-%m-%Y"),
              timezone.localtime(d.hora_inicio).strftime("%H:%M") if d.hora_inicio else "",
              d.ficha.nombre_cliente, d.peluquero.nombre_corto, d.servicio.nombre, d.get_estado_display(),
              d.precio_cobrado] for d in qs]
    return {"columnas": ["Fecha", "Hora", "Cliente", "Peluquero", "Servicio", "Estado", "Precio"], "filas": filas,
            "moneda": [6], "resumen": [("Servicios", len(filas)), ("Total", sum(r[6] for r in filas))]}


def r_por_peluquero(f):
    qs = (servicios_filtrados(f).values("peluquero__nombre", "peluquero__ap_paterno")
          .annotate(atenciones=Count("ficha", distinct=True), servicios=Count("id"), ventas=Sum("precio_cobrado"))
          .order_by("-atenciones"))
    filas = [[f"{r['peluquero__nombre']} {r['peluquero__ap_paterno']}", r["atenciones"], r["servicios"], r["ventas"] or 0]
             for r in qs]
    return {"columnas": ["Peluquero", "Atenciones", "Servicios", "Ventas"], "filas": filas, "moneda": [3],
            "grafico": (0, 1)}


def r_servicios(f):
    qs = (servicios_filtrados(f).values("servicio__tipo__nombre", "servicio__nombre")
          .annotate(n=Count("id"), ventas=Sum("precio_cobrado")).order_by("-n"))
    filas = [[r["servicio__tipo__nombre"], r["servicio__nombre"], r["n"], r["ventas"] or 0] for r in qs]
    return {"columnas": ["Tipo", "Servicio", "Veces realizado", "Ventas"], "filas": filas, "moneda": [3], "grafico": (1, 2)}


def r_insumos(f):
    qs = DetalleFichaInsumo.objects.filter(detalle__in=servicios_filtrados(f))
    qs = (qs.values("insumo__nombre", "insumo__marca", "insumo__calidad", "insumo__unidad_medida")
          .annotate(veces=Count("id"), cantidad=Sum("cant_usada")).order_by("-veces"))
    filas = [[r["insumo__nombre"], r["insumo__marca"], r["insumo__calidad"], r["veces"],
              f"{r['cantidad'] or 0:g} {r['insumo__unidad_medida']}"] for r in qs]
    return {"columnas": ["Insumo", "Marca", "Calidad", "Veces usado", "Cantidad registrada"], "filas": filas,
            "nota": "Informativo: no se controla stock.", "grafico": (0, 3)}


def r_comisiones(f):
    datos = ms.comisiones(f["desde"], f["hasta"], f.get("peluquero"))
    filas = [[c["peluquero"].nombre_corto, c["servicios"], c["ventas"], c["comision"]] for c in datos]
    return {"columnas": ["Peluquero externo", "Servicios", "Ventas", "Comisión"], "filas": filas, "moneda": [2, 3],
            "nota": "Calculado con el precio y el porcentaje guardados en cada atención. Monto informativo.",
            "resumen": [("Total comisiones", sum(r[3] for r in filas))]}


def r_metas(f):
    qs = MetaMensual.objects.select_related("peluquero").filter(
        anio__gte=f["desde"].year, anio__lte=f["hasta"].year)
    if f.get("peluquero"):
        qs = qs.filter(peluquero=f["peluquero"])
    filas = []
    for m in qs.order_by("anio", "mes", "peluquero__nombre"):
        if not ((f["desde"].year, f["desde"].month) <= (m.anio, m.mes) <= (f["hasta"].year, f["hasta"].month)):
            continue
        a = ms.avance(m)
        filas.append([f"{m.mes:02d}/{m.anio}", m.peluquero.nombre_corto, m.meta_cliente, a["logradas"],
                      f"{a['porcentaje']:.0f}%", a["incentivo"], a["estado"]])
    return {"columnas": ["Mes", "Peluquero", "Meta", "Logradas", "Avance", "Incentivo", "Estado"], "filas": filas,
            "moneda": [5]}


def r_calidad(f):
    qs = Valoracion.objects.filter(estado="respondida", fecha_respuesta__range=rango(f))
    if f.get("peluquero"):
        qs = qs.filter(peluquero=f["peluquero"])
    qs = (qs.values("peluquero__nombre", "peluquero__ap_paterno")
          .annotate(prom=Avg("calificacion"), n=Count("id")).order_by("-prom"))
    filas = [[f"{r['peluquero__nombre']} {r['peluquero__ap_paterno']}", round(r["prom"], 2), r["n"]] for r in qs]
    return {"columnas": ["Peluquero", "Promedio (1 a 5)", "Respuestas"], "filas": filas, "grafico": (0, 1)}


def r_recordatorios(f):
    qs = EnvioMensaje.objects.filter(fecha__range=rango(f), recordatorio__isnull=False)
    filas = []
    for canal in qs.values_list("canal__nombre", flat=True).distinct():
        c = qs.filter(canal__nombre=canal)
        total, ok = c.count(), c.filter(exitoso=True).count()
        filas.append([canal, total, ok, total - ok, f"{pct(ok, total)}%"])
    total, ok = qs.count(), qs.filter(exitoso=True).count()
    return {"columnas": ["Canal", "Intentos", "Entregados", "Fallidos", "Tasa de entrega"], "filas": filas,
            "resumen": [("Tasa de entrega total", f"{pct(ok, total)}%"), ("Objetivo", "95%")]}


def r_valoraciones(f):
    qs = Valoracion.objects.filter(fecha_programada__range=(f["desde"], f["hasta"]))
    if f.get("peluquero"):
        qs = qs.filter(peluquero=f["peluquero"])
    conteo = dict(qs.values_list("estado").annotate(n=Count("id")))
    filas = [[nombre, conteo.get(codigo, 0)] for codigo, nombre in Valoracion.ESTADOS]
    enviadas = sum(conteo.get(k, 0) for k in ("enviada", "respondida", "sin_respuesta"))
    return {"columnas": ["Estado", "Cantidad"], "filas": filas, "grafico": (0, 1),
            "resumen": [("Tasa de respuesta", f"{pct(conteo.get('respondida', 0), enviadas)}%")]}


def r_digitalizacion(f):
    fichas = FichaAtencion.objects.exclude(estado="anulada").filter(fecha_hora_inicio__range=rango(f))
    con_cliente = fichas.filter(cliente__isnull=False)
    atendidos = con_cliente.values("cliente").distinct().count()
    nuevos = Cliente.objects.filter(creado_en__range=rango(f)).count()
    filas = [["Fichas del período", fichas.count()], ["Fichas con cliente registrado", con_cliente.count()],
             ["Clientes distintos atendidos", atendidos], ["Clientes registrados en el período", nuevos],
             ["Clientes registrados en total", Cliente.objects.count()]]
    return {"columnas": ["Indicador", "Valor"], "filas": filas,
            "resumen": [("Fichas digitalizadas con cliente", f"{pct(con_cliente.count(), fichas.count())}%")]}


def r_fichas_completas(f):
    fichas = (FichaAtencion.objects.exclude(estado="anulada").filter(fecha_hora_inicio__range=rango(f))
              .annotate(n=Count("servicios")))
    total = fichas.count()
    completas = fichas.filter(cliente__isnull=False, n__gt=0).count()
    sin_cliente = fichas.filter(cliente__isnull=True).count()
    sin_servicio = fichas.filter(n=0).count()
    filas = [["Fichas", total], ["Completas (cliente, peluquero, servicio, fecha y hora)", completas],
             ["Sin cliente vinculado", sin_cliente], ["Sin servicios", sin_servicio]]
    return {"columnas": ["Indicador", "Cantidad"], "filas": filas,
            "resumen": [("Fichas completas", f"{pct(completas, total)}%")]}


def r_uso_historial(f):
    peluqueros = Usuario.objects.filter(is_active=True, roles__codigo="peluquero").distinct()
    consultas = ConsultaHistorial.objects.filter(fecha__range=rango(f))
    filas, usan = [], 0
    for p in peluqueros:
        n = consultas.filter(usuario=p).count()
        usan += 1 if n else 0
        filas.append([p.nombre_corto, n])
    filas.sort(key=lambda r: -r[1])
    return {"columnas": ["Peluquero", "Consultas de historial"], "filas": filas, "grafico": (0, 1),
            "resumen": [("Peluqueros que usan el historial", f"{pct(usan, len(filas))}%")]}


def r_accesos(f):
    qs = RegistroAcceso.objects.filter(fecha__range=rango(f))
    dias = {}
    for fecha, ok in qs.values_list("fecha", "exitoso"):
        d = timezone.localtime(fecha).strftime("%d-%m-%Y")
        dias.setdefault(d, [0, 0])[0 if ok else 1] += 1
    filas = [[d, v[0], v[1], f"{pct(v[0], sum(v))}%"] for d, v in dias.items()]
    total, ok = qs.count(), qs.filter(exitoso=True).count()
    return {"columnas": ["Día", "Exitosos", "Fallidos", "Tasa de éxito"], "filas": filas,
            "resumen": [("Inicios exitosos", ok), ("Fallidos", total - ok), ("Tasa de éxito", f"{pct(ok, total)}%")]}


def r_beneficios(f):
    filas = []
    for codigo, nombre in Giftcard._meta.get_field("estado").choices:
        filas.append(["Giftcards", nombre, Giftcard.objects.filter(estado=codigo).count()])
    for codigo, nombre in ClientePromocion._meta.get_field("estado").choices:
        filas.append(["Promociones", nombre, ClientePromocion.objects.filter(estado=codigo).count()])
    usos_gc = UsoGiftcard.objects.filter(fecha_uso__range=rango(f))
    usos_pr = UsoPromocion.objects.filter(fecha_uso__range=rango(f))
    return {"columnas": ["Tipo", "Estado", "Cantidad"], "filas": filas,
            "resumen": [("Usos de giftcard en el período", usos_gc.count()),
                        ("Monto descontado", usos_gc.aggregate(s=Sum("monto_usado"))["s"] or 0),
                        ("Usos de promociones en el período", usos_pr.count())]}


REPORTES = {
    "atenciones": ("Atenciones realizadas", "Cliente, peluquero, servicio y hora de cada atención.", r_atenciones),
    "por-peluquero": ("Atenciones por peluquero", "Total de atenciones y servicios por peluquero.", r_por_peluquero),
    "servicios": ("Servicios más realizados", "Agrupados por tipo de servicio.", r_servicios),
    "insumos": ("Uso de insumos", "Veces que se registró cada insumo.", r_insumos),
    "comisiones": ("Comisiones", "Informativo, por peluquero externo.", r_comisiones),
    "metas": ("Metas e incentivos", "Cumplimiento por peluquero y mes.", r_metas),
    "calidad": ("Calidad de atención", "Promedio de valoraciones por peluquero.", r_calidad),
    "recordatorios": ("Recordatorios", "Enviados, entregados, fallidos y tasa de entrega.", r_recordatorios),
    "valoraciones": ("Valoraciones de seguimiento", "Respondidas y sin respuesta.", r_valoraciones),
    "digitalizacion": ("Digitalización de fichas", "Clientes registrados frente a atendidos.", r_digitalizacion),
    "fichas-completas": ("Fichas con datos completos", "Porcentaje de fichas completas.", r_fichas_completas),
    "uso-historial": ("Uso del historial", "Peluqueros que consultan el historial de clientes.", r_uso_historial),
    "accesos": ("Accesos al sistema", "Inicios de sesión exitosos y fallidos.", r_accesos),
    "beneficios": ("Giftcards y promociones", "Estados y usos en el período.", r_beneficios),
}
