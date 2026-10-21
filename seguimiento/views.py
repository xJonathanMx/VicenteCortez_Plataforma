from django import forms
from django.contrib import messages
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.forms import FormEstilo, ModelFormEstilo
from core.models import Usuario
from core.permisos import privilegio_requerido

from . import servicios as ss
from .models import CanalComunicacion, Plantilla, Recordatorio, Valoracion


class FiltroValoracionesForm(FormEstilo):
    peluquero = forms.ModelChoiceField(Usuario.objects.filter(roles__codigo="peluquero").distinct(), required=False,
                                       empty_label="Todos", label="Peluquero")
    estado = forms.ChoiceField(choices=[("", "Todos")] + Valoracion.ESTADOS, required=False, label="Estado")
    desde = forms.DateField(required=False, label="Desde", widget=forms.DateInput(attrs={"type": "date"}))
    hasta = forms.DateField(required=False, label="Hasta", widget=forms.DateInput(attrs={"type": "date"}))


class PlantillaForm(ModelFormEstilo):
    class Meta:
        model = Plantilla
        fields = ["asunto", "cuerpo"]
        widgets = {"cuerpo": forms.Textarea(attrs={"rows": 4})}


class RespuestaForm(forms.Form):
    calificacion = forms.TypedChoiceField(choices=[(i, i) for i in range(1, 6)], coerce=int,
                                          widget=forms.RadioSelect, label="Calificación")
    comentario = forms.CharField(required=False, max_length=255, label="Comentario",
                                 widget=forms.Textarea(attrs={"rows": 3, "class": "form-control",
                                                              "placeholder": "¿Cómo se ve y se siente tu cabello?"}))


@privilegio_requerido("ver_valoraciones")
def valoraciones(request):
    form = FiltroValoracionesForm(request.GET or None)
    qs = Valoracion.objects.select_related("ficha__cliente", "peluquero")
    if form.is_valid():
        d = form.cleaned_data
        if d["peluquero"]:
            qs = qs.filter(peluquero=d["peluquero"])
        if d["estado"]:
            qs = qs.filter(estado=d["estado"])
        if d["desde"]:
            qs = qs.filter(fecha_programada__gte=d["desde"])
        if d["hasta"]:
            qs = qs.filter(fecha_programada__lte=d["hasta"])
    # RF-VS-14: promedio de calidad por peluquero (sobre las respondidas del filtro).
    promedios = (qs.filter(estado="respondida").values("peluquero__nombre", "peluquero__ap_paterno")
                 .annotate(promedio=Avg("calificacion"), n=Count("id")).order_by("-promedio"))
    conteo = dict(qs.values_list("estado").annotate(n=Count("id")))
    return render(request, "seguimiento/valoraciones.html", {
        "form": form, "valoraciones": qs[:200], "promedios": promedios, "conteo": conteo,
        "estados": Valoracion.ESTADOS})


@privilegio_requerido("ver_valoraciones")
def recordatorios(request):
    estado = request.GET.get("estado", "")
    qs = Recordatorio.objects.select_related("cliente", "detalle__servicio", "giftcard")
    if estado:
        qs = qs.filter(estado=estado)
    return render(request, "seguimiento/recordatorios.html", {"recordatorios": qs[:200], "estado": estado,
                                                               "estados": Recordatorio.ESTADOS})


@privilegio_requerido("ver_valoraciones")
@require_POST
def procesar(request):
    r = ss.procesar_pendientes()
    messages.success(request, f"Envíos procesados: {r['valoraciones']} valoraciones y {r['recordatorios']} recordatorios "
                              f"enviados; {r['fallidos']} con error.")
    return redirect(request.POST.get("volver") or "seguimiento:valoraciones")


@privilegio_requerido("ver_valoraciones")
@require_POST
def reintentar(request, tipo, pk):
    obj = get_object_or_404(Valoracion if tipo == "valoracion" else Recordatorio, pk=pk)
    if ss.reintentar(obj):
        messages.success(request, "Mensaje enviado.")
    else:
        messages.error(request, f"Sigue fallando: {obj.ultimo_error}. Corrige el teléfono o correo del cliente.")
    return redirect("seguimiento:valoraciones" if tipo == "valoracion" else "seguimiento:recordatorios")


@privilegio_requerido("configurar_canales")
def canales(request):
    """RF-PA-13: canales disponibles y plantillas de mensajes."""
    if request.method == "POST":
        if "canal" in request.POST:
            c = get_object_or_404(CanalComunicacion, pk=request.POST["canal"])
            c.activo = not c.activo
            c.save(update_fields=["activo"])
            messages.success(request, f"Canal {c} {'activado' if c.activo else 'desactivado'}.")
        else:
            p = get_object_or_404(Plantilla, pk=request.POST["plantilla"])
            form = PlantillaForm(request.POST, instance=p, prefix=f"p{p.pk}")
            if form.is_valid():
                form.save()
                messages.success(request, f"Plantilla «{p}» guardada.")
        return redirect("seguimiento:canales")
    plantillas = [(p, PlantillaForm(instance=p, prefix=f"p{p.pk}"))
                  for p in Plantilla.objects.select_related("canal").order_by("tipo", "canal__nombre")]
    return render(request, "seguimiento/canales.html", {"canales": CanalComunicacion.objects.all(),
                                                         "plantillas": plantillas})


def valorar_publico(request, token):
    """RF-VS-08 / RF-VS-09: el cliente responde sin iniciar sesión, con el enlace único."""
    v = get_object_or_404(Valoracion.objects.select_related("ficha__cliente", "peluquero"), token=token)
    if v.estado == "respondida":
        return render(request, "seguimiento/valorar.html", {"v": v, "listo": True})
    if v.estado == "sin_respuesta" or v.ficha.estado_id == "anulada":
        return render(request, "seguimiento/valorar.html", {"v": v, "cerrada": True})
    form = RespuestaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        v.calificacion = form.cleaned_data["calificacion"]
        v.respuesta = form.cleaned_data["comentario"]
        v.fecha_respuesta = timezone.now()
        v.estado = "respondida"
        v.save()
        return render(request, "seguimiento/valorar.html", {"v": v, "listo": True})
    servicios = ", ".join(s.servicio.nombre.lower() for s in v.ficha.servicios.select_related("servicio"))
    return render(request, "seguimiento/valorar.html", {"v": v, "form": form, "servicios": servicios})
