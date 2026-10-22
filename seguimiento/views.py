from django import forms
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.conf import settings
from django.contrib import messages
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.forms import FormEstilo, ModelFormEstilo
from core.models import Usuario
from core.permisos import privilegio_requerido

from . import servicios as ss
from .models import CanalComunicacion, ConfiguracionCorreo, Plantilla, Recordatorio, Valoracion


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


class ConfiguracionCorreoForm(ModelFormEstilo):
    PROVEEDORES = [("gmail", "Gmail"), ("outlook", "Outlook, Hotmail o Live"), ("otro", "Otro")]
    proveedor = forms.ChoiceField(choices=PROVEEDORES, label="Proveedor", required=False)
    clave = forms.CharField(label="Contraseña de aplicación", required=False, strip=True,
                            widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}))

    class Meta:
        model = ConfiguracionCorreo
        fields = ["activo", "usuario", "remitente_nombre", "responder_a", "servidor", "puerto", "seguridad"]
        labels = {"usuario": "Correo de la cuenta"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(["proveedor", "usuario", "clave", "remitente_nombre", "responder_a", "servidor", "puerto",
                           "seguridad", "activo"])
        self.fields["responder_a"].widget.attrs.update({"inputmode": "email", "placeholder": "peluqueria@live.cl"})
        servidor = (self.instance.servidor or "").lower()
        self.fields["proveedor"].initial = ("gmail" if "gmail" in servidor else
                                            "outlook" if "outlook" in servidor or "office365" in servidor else "otro")
        self.fields["usuario"].widget = forms.EmailInput(attrs={"class": "form-control", "inputmode": "email",
                                                                "placeholder": "peluqueria@gmail.com"})
        self.fields["usuario"].nota_etiqueta = False  # necesario para enviar
        if self.instance.tiene_clave:
            self.fields["clave"].nota_etiqueta = "ya guardada"
            self.fields["clave"].help_text = "Déjalo vacío para mantener la actual. Escribe una nueva solo si la quieres cambiar."
            self.fields["clave"].widget.attrs["placeholder"] = "•••••••• (guardada)"
        else:
            self.fields["clave"].nota_etiqueta = False  # obligatoria para enviar: no decir "opcional"
            self.fields["clave"].widget.attrs["aria-required"] = "true"
            self.fields["clave"].help_text = "No es tu contraseña normal de Gmail: crea una «contraseña de aplicación» (ver guía abajo)."
        self.fields["activo"].help_text = "Apagado: modo prueba, los correos solo se muestran en la consola."

    def clean(self):
        d = super().clean()
        if d.get("activo"):
            if not d.get("usuario"):
                self.add_error("usuario", "Indica el correo de la cuenta para poder enviar.")
            if not d.get("clave") and not self.instance.tiene_clave:
                self.add_error("clave", "Falta la contraseña de aplicación.")
        return d


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
        if "probar_correo" in request.POST:
            return probar_correo(request)
        if "guardar_correo" in request.POST:
            form = ConfiguracionCorreoForm(request.POST, instance=ConfiguracionCorreo.actual(), prefix="correo")
            if form.is_valid():
                conf = form.save(commit=False)
                if form.cleaned_data.get("clave"):
                    conf.fijar_clave(form.cleaned_data["clave"])
                conf.actualizado_por = request.user
                conf.save()
                messages.success(request, "Cuenta de correo guardada. " + (
                    "Los correos ya se envían de verdad: prueba con el botón de abajo." if conf.lista
                    else "Sigue en modo prueba hasta que actives «Enviar correos reales»."))
                return redirect(f"{reverse('seguimiento:canales')}#correo")
            return _render_canales(request, form)
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
    return _render_canales(request)


def _render_canales(request, correo_form=None):
    conf = ConfiguracionCorreo.actual()
    plantillas = [(p, PlantillaForm(instance=p, prefix=f"p{p.pk}"))
                  for p in Plantilla.objects.filter(canal__codigo__in=settings.CANALES_ENVIO)
                  .select_related("canal").order_by("tipo", "canal__nombre")]
    return render(request, "seguimiento/canales.html", {
        "canales": CanalComunicacion.objects.all(), "plantillas": plantillas, "habilitados": settings.CANALES_ENVIO,
        "correo_real": not ss.modo_prueba_correo(), "conf_correo": conf,
        "correo_form": correo_form or ConfiguracionCorreoForm(instance=conf, prefix="correo")})


def probar_correo(request):
    """Envía un correo de prueba con la configuración actual y muestra el resultado o el error."""
    destino = request.POST.get("probar_correo", "").strip()
    try:
        validate_email(destino)
    except ValidationError:
        messages.error(request, f"«{destino or 'vacío'}» no es un correo válido.")
        return redirect("seguimiento:canales")
    if request.POST.get("ejemplo") == "valoracion":
        return enviar_ejemplo_valoracion(request, destino)
    try:
        send_mail("Prueba de correo: Peluquería Vicente Cortez",
                  f"Hola, este es un correo de prueba enviado desde la plataforma por {request.user.nombre_corto}.\n"
                  "Si lo recibiste, los recordatorios y valoraciones también van a llegar.",
                  None, [destino])
    except Exception as e:  # credenciales, servidor caído, etc.
        messages.error(request, f"No se pudo enviar: {e}. Revisa el correo, la contraseña de aplicación y el servidor "
                                f"en «Cuenta de correo».")
        return redirect("seguimiento:canales")
    if ss.modo_prueba_correo():
        messages.warning(request, "El correo se generó, pero el sistema está en modo prueba: aparece en la consola del "
                                  "servidor y no llega a la bandeja. Configura la cuenta en «Cuenta de correo» y activa "
                                  "«Enviar correos reales».")
    else:
        messages.success(request, f"Correo enviado a {destino}. Revisa la bandeja de entrada (y spam).")
    return redirect("seguimiento:canales")


def _valoracion_ejemplo(nombre="Camila"):
    """Objeto de muestra con la misma forma que una Valoración real (no se guarda)."""
    from types import SimpleNamespace
    ahora = timezone.now()
    ficha = SimpleNamespace(cliente=SimpleNamespace(nombre=nombre), fecha_hora_inicio=ahora, estado_id="cerrada")
    return SimpleNamespace(ficha=ficha, peluquero=SimpleNamespace(nombre="Andrea"), estado="enviada",
                           enlace=f"{settings.SITIO_URL.rstrip('/')}/valorar/ejemplo/")


def enviar_ejemplo_valoracion(request, destino):
    """Envía al administrador el correo de valoración tal como lo recibe un cliente, con datos de ejemplo."""
    from django.core.mail import EmailMultiAlternatives
    v = _valoracion_ejemplo(request.user.nombre)
    ctx = {"nombre": request.user.nombre, "servicio": "corte dama", "peluquero": "Andrea", "enlace": v.enlace,
           "fecha": "", "codigo": "", "saldo": ""}
    canal = CanalComunicacion.objects.filter(codigo="email").first()
    asunto, cuerpo = ss.armar_mensaje("valoracion", canal, ctx)
    try:
        correo = EmailMultiAlternatives(f"[Ejemplo] {asunto}", cuerpo, None, [destino])
        correo.attach_alternative(ss.html_valoracion(v, ctx), "text/html")
        correo.send()
    except Exception as e:
        messages.error(request, f"No se pudo enviar: {e}.")
        return redirect("seguimiento:canales")
    if ss.modo_prueba_correo():
        messages.warning(request, "El ejemplo se generó, pero el sistema está en modo prueba: no llega a la bandeja.")
    else:
        messages.success(request, f"Ejemplo de valoración enviado a {destino}. Las estrellas abren una página de muestra que no guarda nada.")
    return redirect("seguimiento:canales")


def valorar_publico(request, token):
    """RF-VS-08 / RF-VS-09: el cliente responde sin iniciar sesión, con el enlace único."""
    if token == "ejemplo":  # página de muestra para el correo de ejemplo: no guarda nada
        v = _valoracion_ejemplo()
        if request.method == "POST":
            return render(request, "seguimiento/valorar.html", {"v": v, "listo": True})
        nota = request.GET.get("nota")
        form = RespuestaForm(initial={"calificacion": int(nota)} if nota in {"1", "2", "3", "4", "5"} else {})
        return render(request, "seguimiento/valorar.html", {"v": v, "form": form, "servicios": "corte dama"})
    v = get_object_or_404(Valoracion.objects.select_related("ficha__cliente", "peluquero"), token=token)
    if v.estado == "respondida":
        return render(request, "seguimiento/valorar.html", {"v": v, "listo": True})
    if v.estado == "sin_respuesta" or v.ficha.estado_id == "anulada":
        return render(request, "seguimiento/valorar.html", {"v": v, "cerrada": True})
    # La estrella tocada en el correo llega como ?nota=N y queda marcada; el cliente igual confirma
    # (algunos antivirus abren los enlaces solos y no deben registrar una nota).
    nota = request.GET.get("nota")
    inicial = {"calificacion": int(nota)} if nota in {"1", "2", "3", "4", "5"} else {}
    form = RespuestaForm(request.POST or None, initial=inicial)
    if request.method == "POST" and form.is_valid():
        v.calificacion = form.cleaned_data["calificacion"]
        v.respuesta = form.cleaned_data["comentario"]
        v.fecha_respuesta = timezone.now()
        v.estado = "respondida"
        v.save()
        return render(request, "seguimiento/valorar.html", {"v": v, "listo": True})
    servicios = ", ".join(s.servicio.nombre.lower() for s in v.ficha.servicios.select_related("servicio"))
    return render(request, "seguimiento/valorar.html", {"v": v, "form": form, "servicios": servicios})
