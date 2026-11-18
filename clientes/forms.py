from django import forms
from django.conf import settings
from django.urls import reverse
from django.utils.html import format_html

from core.forms import CampoRun, FormEstilo, ModelFormEstilo, col
from core.models import Cliente, Usuario


def peluqueros_activos():
    return Usuario.objects.filter(is_active=True, roles__codigo="peluquero").distinct()


class ClienteForm(ModelFormEstilo):
    run_completo = CampoRun()

    class Meta:
        model = Cliente
        fields = ["nombre", "ap_paterno", "ap_materno", "telefono", "correo", "fecha_nac", "genero",
                  "canal_preferido", "estilista_fijo"]
        widgets = {"fecha_nac": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *args, puede_fijar=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(["run_completo"] + self.Meta.fields)
        for n in self.fields:
            self.fields[n].widget.attrs.update(col(6))
        self.fields["telefono"].widget.attrs.update({"inputmode": "tel", "placeholder": "+56 9 1234 5678"})
        self.fields["correo"].widget.attrs["inputmode"] = "email"
        self.fields["estilista_fijo"].queryset = peluqueros_activos()
        self.fields["estilista_fijo"].empty_label = "Sin estilista fijo"
        self.fields["canal_preferido"].help_text = "Por aquí le llegan las valoraciones y recordatorios."
        if "whatsapp" not in settings.CANALES_ENVIO:
            del self.fields["canal_preferido"]  # por ahora todo se envía por correo
            self.fields["correo"].help_text = "Necesario para enviarle valoraciones y recordatorios."
        if not puede_fijar:
            del self.fields["estilista_fijo"]
        if self.instance.pk:
            self.fields["run_completo"].initial = self.instance.run_formateado
            self.fields["run_completo"].disabled = True

    def clean_run_completo(self):
        if self.instance.pk:
            return (self.instance.run, self.instance.dv)
        cuerpo, dv = self.cleaned_data["run_completo"]
        existente = Cliente.objects.filter(run=cuerpo).first()
        if existente:  # RF-C-02: muestra el cliente ya registrado
            raise forms.ValidationError(format_html(
                'Este RUN ya está registrado: <a href="{}">{}</a>.',
                reverse("clientes:detalle", args=[existente.run]), existente.nombre_completo))
        return cuerpo, dv

    def clean(self):
        d = super().clean()
        canal = d.get("canal_preferido", "email")
        if canal == "whatsapp" and not d.get("telefono") and d.get("correo"):
            d["canal_preferido"] = "email"
        return d


class EstilistaForm(ModelFormEstilo):
    """RF-C-07: asociar, cambiar o quitar el estilista fijo."""

    class Meta:
        model = Cliente
        fields = ["estilista_fijo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estilista_fijo"].queryset = peluqueros_activos()
        self.fields["estilista_fijo"].empty_label = "Sin estilista fijo"


class CorreoClienteForm(FormEstilo):
    """Correo escrito a mano para un cliente (por ejemplo, los cuidados después de un tratamiento)."""
    asunto = forms.CharField(label="Asunto", max_length=150)
    mensaje = forms.CharField(label="Mensaje", max_length=5000, widget=forms.Textarea(attrs={"rows": 12}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for n in self.fields:
            self.fields[n].widget.attrs.update(col(12))
