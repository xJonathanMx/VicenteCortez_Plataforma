from datetime import date

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.forms import FormEstilo
from core.models import Usuario
from core.permisos import privilegio_requerido

from . import servicios as ms
from .models import MetaMensual, NivelIncentivo


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
def guardar_metas(request):
    """RF-CI-09 / RF-PA-11."""
    mes, anio = int(request.POST["mes"]), int(request.POST["anio"])
    n = 0
    for p in Usuario.objects.filter(is_active=True, roles__codigo="peluquero").distinct():
        meta_txt = request.POST.get(f"meta_{p.pk}", "").strip()
        base_txt = request.POST.get(f"base_{p.pk}", "").strip().replace(".", "")
        if not meta_txt:
            continue
        existente = MetaMensual.objects.filter(peluquero=p, mes=mes, anio=anio).first()
        if existente and existente.cerrada:
            continue
        try:
            meta, base = int(meta_txt), int(base_txt or 0)
        except ValueError:
            messages.error(request, f"Revisa los números de {p.nombre_corto}.")
            continue
        MetaMensual.objects.update_or_create(peluquero=p, mes=mes, anio=anio,
                                             defaults={"meta_cliente": max(meta, 1), "incentivo_base": base})
        n += 1
    messages.success(request, f"Metas guardadas para {n} peluquero{'s' if n != 1 else ''}.")
    return redirect(f"{reverse('metas:panel')}?mes={anio}-{mes}")


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
