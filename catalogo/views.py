from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.models import (
    VARIANTES, Comision, HistoricoComisionServicio, HistoricoEstadoServicio, HistoricoPrecioServicio, Insumo,
    Servicio, TipoEstado, TipoServicio,
)
from core.permisos import privilegio_requerido

from .forms import CAMPOS_PRECIO, EstadoForm, InsumoForm, ServicioForm, TipoServicioForm

VARIANTE_DE_CAMPO = dict(zip(CAMPOS_PRECIO, [v for v, _ in VARIANTES]))


def _pestanas(activa):
    return {"pestana": activa}


@privilegio_requerido("gestionar_catalogo")
def servicios(request):
    ver = request.GET.get("ver", "activos")
    tipos = TipoServicio.objects.prefetch_related("servicios__especialidades").order_by("nombre")
    grupos = []
    for t in tipos:
        lista = [s for s in t.servicios.all() if ver == "todos" or s.activo]
        if lista or ver == "todos":
            grupos.append((t, lista))
    return render(request, "catalogo/servicios.html", {"grupos": grupos, "ver": ver, **_pestanas("servicios")})


@privilegio_requerido("gestionar_catalogo")
@transaction.atomic
def servicio_form(request, pk=None):
    servicio = get_object_or_404(Servicio, pk=pk) if pk else None
    antes = {c: getattr(servicio, c) for c in CAMPOS_PRECIO} if servicio else {}
    form = ServicioForm(request.POST or None, instance=servicio,
                        puede_precios=request.user.tiene_privilegio("editar_precios"))
    if request.method == "POST" and form.is_valid():
        s = form.save()
        # RF-PA-09 / RF-HT-02 / RF-HT-03: cada cambio de precio queda en el histórico.
        for campo in CAMPOS_PRECIO:
            nuevo = getattr(s, campo)
            if servicio is None or antes.get(campo) != nuevo:
                if servicio is None and nuevo is None:
                    continue
                HistoricoPrecioServicio.objects.create(servicio=s, variante=VARIANTE_DE_CAMPO[campo],
                                                       precio_anterior=antes.get(campo), precio_nuevo=nuevo,
                                                       responsable=request.user)
        messages.success(request, f"Servicio {s.nombre} guardado.")
        return redirect("catalogo:servicio", pk=s.pk)
    return render(request, "form.html", {"form": form, "titulo": f"Editar {servicio.nombre}" if servicio else "Nuevo servicio",
                                         "subtitulo": "Precio por calidad, tiempo estimado y días hasta la renovación.",
                                         "volver": reverse("catalogo:servicios")})


@privilegio_requerido("gestionar_catalogo")
def servicio_detalle(request, pk):
    s = get_object_or_404(Servicio.objects.select_related("tipo"), pk=pk)
    return render(request, "catalogo/servicio.html", {
        "s": s, "precios": s.historial_precios.select_related("responsable"),
        "estados": s.historial_estados.select_related("tipo_estado", "responsable"),
        "habilitados": s.habilitados.filter(activo=True).select_related("usuario", "nivel"),
        "form_estado": EstadoForm(), **_pestanas("servicios")})


@privilegio_requerido("gestionar_catalogo")
@require_POST
@transaction.atomic
def servicio_estado(request, pk):
    """RF-CS-01 / RF-CS-05 / RF-PA-17: habilitar y deshabilitar sin borrar."""
    s = get_object_or_404(Servicio, pk=pk)
    s.activo = not s.activo
    s.save(update_fields=["activo"])
    HistoricoEstadoServicio.objects.create(servicio=s, tipo_estado=TipoEstado.de(s.activo),
                                           motivo=request.POST.get("motivo", "")[:255], responsable=request.user)
    messages.success(request, f"{s.nombre} {'habilitado' if s.activo else 'deshabilitado'}.")
    return redirect("catalogo:servicio", pk=pk)


@privilegio_requerido("gestionar_catalogo")
def tipos(request):
    lista = TipoServicio.objects.annotate(n=Count("servicios")).prefetch_related("comisiones__contrato")
    return render(request, "catalogo/tipos.html", {"tipos": lista, **_pestanas("tipos")})


@privilegio_requerido("gestionar_catalogo")
@transaction.atomic
def tipo_form(request, pk=None):
    tipo = get_object_or_404(TipoServicio, pk=pk) if pk else None
    puede = request.user.tiene_privilegio("editar_precios")
    form = TipoServicioForm(request.POST or None, instance=tipo, puede_precios=puede)
    if request.method == "POST" and form.is_valid():
        t = form.save()
        if puede:
            for c in form.contratos:
                nuevo = form.cleaned_data[f"comision_{c.pk}"]
                com = Comision.objects.filter(tipo_servicio=t, contrato=c).first()
                anterior = com.porcentaje if com else None
                if anterior != nuevo:
                    # RF-CI-02 / RF-CI-03: histórico; las fichas pasadas guardan su propio porcentaje.
                    Comision.objects.update_or_create(tipo_servicio=t, contrato=c, defaults={"porcentaje": nuevo})
                    HistoricoComisionServicio.objects.create(tipo_servicio=t, contrato=c, porcentaje_anterior=anterior,
                                                             porcentaje_nuevo=nuevo, responsable=request.user)
        messages.success(request, f"Tipo {t.nombre} guardado.")
        return redirect("catalogo:tipos")
    return render(request, "form.html", {"form": form, "titulo": f"Editar {tipo.nombre}" if tipo else "Nuevo tipo de servicio",
                                         "subtitulo": "La regla de valoración define cuántos mensajes de seguimiento recibe el cliente.",
                                         "volver": reverse("catalogo:tipos")})


@privilegio_requerido("gestionar_catalogo")
def tipo_historial(request, pk):
    t = get_object_or_404(TipoServicio, pk=pk)
    return render(request, "catalogo/tipo_historial.html", {
        "t": t, "historial": t.historial_comisiones.select_related("contrato", "responsable"), **_pestanas("tipos")})


@privilegio_requerido("gestionar_catalogo")
@require_POST
def tipo_estado(request, pk):
    t = get_object_or_404(TipoServicio, pk=pk)
    t.activo = not t.activo
    t.save(update_fields=["activo"])
    messages.success(request, f"Tipo {t.nombre} {'habilitado' if t.activo else 'deshabilitado'}.")
    return redirect("catalogo:tipos")


@privilegio_requerido("gestionar_catalogo")
def insumos(request):
    ver = request.GET.get("ver", "activos")
    qs = Insumo.objects.annotate(usos_n=Count("usos"))
    if ver != "todos":
        qs = qs.filter(activo=True)
    return render(request, "catalogo/insumos.html", {"insumos": qs, "ver": ver, **_pestanas("insumos")})


@privilegio_requerido("gestionar_catalogo")
def insumo_form(request, pk=None):
    insumo = get_object_or_404(Insumo, pk=pk) if pk else None
    form = InsumoForm(request.POST or None, instance=insumo)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Insumo guardado.")
        return redirect("catalogo:insumos")
    return render(request, "form.html", {"form": form, "titulo": "Editar insumo" if insumo else "Nuevo insumo",
                                         "subtitulo": "Solo registro informativo: no se controla stock.",
                                         "volver": reverse("catalogo:insumos")})


@privilegio_requerido("gestionar_catalogo")
@require_POST
def insumo_estado(request, pk):
    """RF-I-03: desactivar sin borrar; sigue apareciendo en fichas pasadas."""
    i = get_object_or_404(Insumo, pk=pk)
    i.activo = not i.activo
    i.save(update_fields=["activo"])
    messages.success(request, f"Insumo {'activado' if i.activo else 'desactivado'}.")
    return redirect("catalogo:insumos")
