import re
from datetime import date

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.forms import FormEstilo
from core.models import IncentivoMeta, MetaMensual, NivelIncentivo, Usuario
from core.permisos import privilegio_requerido

from . import servicios as ms


class PeriodoForm(FormEstilo):
    desde = forms.DateField(label="Desde", widget=forms.DateInput(attrs={"type": "date"}))
    hasta = forms.DateField(label="Hasta", widget=forms.DateInput(attrs={"type": "date"}))


def _periodo(request):
    hoy = timezone.localdate()
    inicial = {"desde": hoy.replace(day=1), "hasta": hoy}
    form = PeriodoForm(request.GET or None, initial=inicial)
    if form.is_valid():
        return form, form.cleaned_data["desde"], form.cleaned_data["hasta"]
    return PeriodoForm(initial=inicial), inicial["desde"], inicial["hasta"]


def _mes(request):
    hoy = timezone.localdate()
    try:
        anio, mes = map(int, request.GET.get("mes", f"{hoy.year}-{hoy.month}").split("-"))
        date(anio, mes, 1)
    except ValueError:
        anio, mes = hoy.year, hoy.month
    return mes, anio


@login_required
def mias(request):
    """RF-CI-08 / RF-CI-12 / RF-CI-13: lo que ve el propio peluquero."""
    u = request.user
    form, desde, hasta = _periodo(request)
    metas = [ms.avance(m) for m in MetaMensual.objects.filter(peluquero=u)[:12]]
    hoy = timezone.localdate()
    actual = next((a for a in metas if a["meta"].mes == hoy.month and a["meta"].anio == hoy.year), None)
    com = ms.comisiones(desde, hasta, u) if u.cobra_comision else []
    return render(request, "metas/mias.html", {"metas": metas, "actual": actual, "form": form,
                                               "comision": com[0] if com else None, "MESES": ms.MESES})


@privilegio_requerido("gestionar_metas", "ver_comisiones")
def panel(request):
    mes, anio = _mes(request)
    form, desde, hasta = _periodo(request)
    peluqueros = Usuario.objects.filter(is_active=True, roles__codigo="peluquero").distinct()
    metas = {m.peluquero_id: m for m in MetaMensual.objects.filter(mes=mes, anio=anio)}
    avances = {a["meta"].peluquero_id: a for a in ms.avances_del_mes(mes, anio)}
    filas = [{"p": p, "meta": metas.get(p.pk), "avance": avances.get(p.pk)} for p in peluqueros]
    hoy = timezone.localdate()
    meses = []
    a, m = hoy.year, hoy.month
    for _ in range(12):
        meses.append((f"{a}-{m}", f"{ms.MESES[m].capitalize()} {a}"))
        m -= 1
        if m == 0:
            a, m = a - 1, 12
    return render(request, "metas/panel.html", {
        "filas": filas, "mes": mes, "anio": anio, "nombre_mes": f"{ms.MESES[mes]} {anio}", "meses": meses,
        "mes_sel": f"{anio}-{mes}", "cerrado": any(x.cerrada for x in metas.values()),
        "puede_cerrar": (anio, mes) < (hoy.year, hoy.month), "niveles": NivelIncentivo.objects.all(),
        "comisiones": ms.comisiones(desde, hasta), "form": form})


@privilegio_requerido("gestionar_metas")
@require_POST
@transaction.atomic
def guardar_metas(request):
    """RF-CI-09 / RF-PA-11: meta de atenciones y lista de incentivos de cada peluquero."""
    mes, anio = int(request.POST["mes"]), int(request.POST["anio"])
    n, errores = 0, []
    for p in Usuario.objects.filter(is_active=True, roles__codigo="peluquero").distinct():
        meta_txt = re.sub(r"\D", "", request.POST.get(f"meta_{p.pk}", ""))
        if not meta_txt:
            continue
        existente = MetaMensual.objects.filter(peluquero=p, mes=mes, anio=anio).first()
        if existente and existente.cerrada:
            continue
        incentivos, error = leer_incentivos(request.POST, p.pk)
        if error:
            errores.append(f"{p.nombre_corto}: {error}")
            continue
        total_dinero = sum(i["monto"] or 0 for i in incentivos if i["tipo"] == "dinero")
        meta, _ = MetaMensual.objects.update_or_create(
            peluquero=p, mes=mes, anio=anio,
            defaults={"meta_cliente": max(int(meta_txt), 1), "incentivo_base": total_dinero})
        meta.incentivos.all().delete()
        IncentivoMeta.objects.bulk_create(IncentivoMeta(meta=meta, **i) for i in incentivos)
        n += 1
    for e in errores:
        messages.error(request, e)
    if n:
        messages.success(request, f"Metas guardadas para {n} peluquero{'s' if n != 1 else ''}.")
    return redirect(f"{reverse('metas:panel')}?mes={anio}-{mes}")


def leer_incentivos(datos, run):
    """Lee las filas «tipo / descripción / monto» de un peluquero. Las filas vacías se ignoran."""
    tipos = datos.getlist(f"inc_{run}_tipo")
    descripciones = datos.getlist(f"inc_{run}_desc")
    montos = datos.getlist(f"inc_{run}_monto")
    validos = dict(IncentivoMeta.TIPOS)
    salida = []
    for tipo, desc, monto_txt in zip(tipos, descripciones, montos):
        desc = desc.strip()[:120]
        monto = int(re.sub(r"\D", "", monto_txt)) if re.sub(r"\D", "", monto_txt) else None
        if tipo not in validos or (not desc and not monto):
            continue
        if tipo == "dinero" and not monto:
            return [], "un incentivo en dinero necesita un monto."
        if tipo != "dinero" and not desc:
            return [], f"describe el {validos[tipo].lower()} (ej. kit de productos)."
        salida.append({"tipo": tipo, "descripcion": desc, "monto": monto if tipo == "dinero" else None})
    return salida, None


@privilegio_requerido("gestionar_metas")
@require_POST
def cerrar(request):
    """RF-CI-15."""
    mes, anio = int(request.POST["mes"]), int(request.POST["anio"])
    try:
        n = ms.cerrar_mes(mes, anio, request.user)
        messages.success(request, f"Mes cerrado: {n} metas congeladas.")
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    return redirect(f"{reverse('metas:panel')}?mes={anio}-{mes}")


@privilegio_requerido("gestionar_metas")
@require_POST
def niveles(request):
    for n in NivelIncentivo.objects.all():
        valor = request.POST.get(f"nivel_{n.pk}")
        if valor and valor.isdigit():
            n.porcentaje_pago = int(valor)
            n.save()
    messages.success(request, "Escala de incentivos actualizada.")
    return redirect("metas:panel")
