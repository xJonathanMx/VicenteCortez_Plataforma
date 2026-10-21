from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm

from catalogo.models import Servicio
from . import rut as rututil
from .models import Especialidad, Privilegio, Rol, TipoContrato, Usuario


class Estilo:
    """Agrega las clases de Bootstrap a todos los campos del formulario."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            w = f.widget
            if isinstance(w, (forms.CheckboxInput, forms.CheckboxSelectMultiple, forms.RadioSelect)):
                if isinstance(w, forms.CheckboxInput):
                    w.attrs.setdefault("class", "form-check-input")
                continue
            clase = "form-select" if isinstance(w, (forms.Select, forms.SelectMultiple)) else "form-control"
            w.attrs["class"] = (w.attrs.get("class", "") + " " + clase).strip()
            if isinstance(w, forms.Textarea) and str(w.attrs.get("rows")) in ("10", "None"):
                w.attrs["rows"] = 3  # Django usa 10 filas por defecto; demasiado alto en celular


class FormEstilo(Estilo, forms.Form):
    pass


class ModelFormEstilo(Estilo, forms.ModelForm):
    pass


def col(n):
    """Ancho de columna en escritorio (las columnas se apilan en celular)."""
    return {"col": f"col-12 col-md-{n}"}


class CampoRun(forms.CharField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("label", "RUN")
        kwargs.setdefault("max_length", 12)
        kwargs.setdefault("help_text", "Con dígito verificador, ej. 12.345.678-5")
        super().__init__(*args, **kwargs)
        self.widget.attrs.update({"autocomplete": "off", "inputmode": "text", "placeholder": "12.345.678-5"})

    def clean(self, value):
        value = super().clean(value)
        if not value:
            return value
        return rututil.validar(value)  # (cuerpo, dv)


class LoginForm(Estilo, AuthenticationForm):
    """RF-AS-03: un único mensaje genérico, no revela si el RUN existe."""
    username = forms.CharField(label="RUN", max_length=12, widget=forms.TextInput(attrs={
        "autofocus": True, "autocomplete": "username", "placeholder": "12.345.678-5"}))
    error_messages = {
        "invalid_login": "RUN o contraseña incorrectos.",
        "inactive": "RUN o contraseña incorrectos.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Django copia el largo del campo run (8, sin DV); el usuario escribe hasta 12.345.678-9.
        self.fields["username"].max_length = 12
        self.fields["username"].widget.attrs["maxlength"] = 12


class UsuarioForm(ModelFormEstilo):
    run_completo = CampoRun()
    especialidades_sel = forms.ModelMultipleChoiceField(
        Especialidad.objects.filter(activo=True), required=False, label="Especialidades",
        widget=forms.CheckboxSelectMultiple)
    especialidad_principal = forms.ModelChoiceField(Especialidad.objects.filter(activo=True), required=False,
                                                    label="Especialidad principal")
    servicios_sel = forms.ModelMultipleChoiceField(
        Servicio.objects.filter(activo=True).select_related("tipo"), required=False,
        label="Servicios habilitados", widget=forms.CheckboxSelectMultiple,
        help_text="Solo podrá ser asignado a estos servicios.")
    password1 = forms.CharField(label="Contraseña inicial", widget=forms.PasswordInput, required=False,
                                help_text="Mínimo 8 caracteres. Déjala vacía al editar para no cambiarla.")

    class Meta:
        model = Usuario
        fields = ["nombre", "ap_paterno", "ap_materno", "correo", "telefono", "genero", "contrato", "roles"]
        widgets = {"roles": forms.CheckboxSelectMultiple}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        orden = ["run_completo", "nombre", "ap_paterno", "ap_materno", "correo", "telefono", "genero", "contrato",
                 "roles", "especialidades_sel", "especialidad_principal", "servicios_sel", "password1"]
        self.order_fields(orden)
        for n in ["nombre", "ap_paterno", "ap_materno", "correo", "telefono", "genero", "contrato"]:
            self.fields[n].widget.attrs.update(col(6 if n != "ap_materno" else 6))
        self.fields["run_completo"].widget.attrs.update(col(6))
        self.fields["contrato"].required = True
        self.fields["roles"].help_text = "Un usuario puede tener más de un rol (ej. peluquero y recepción)."
        if self.instance.pk:
            self.fields["run_completo"].initial = self.instance.run_formateado
            self.fields["run_completo"].disabled = True
            self.fields["especialidades_sel"].initial = self.instance.especialidades.all()
            principal = self.instance.usuarioespecialidad_set.filter(es_principal=True).first()
            self.fields["especialidad_principal"].initial = principal.especialidad if principal else None
            self.fields["servicios_sel"].initial = Servicio.objects.filter(
                habilitados__usuario=self.instance, habilitados__activo=True)
        else:
            self.fields["password1"].required = True

    def clean_run_completo(self):
        if self.instance.pk:
            return (self.instance.run, self.instance.dv)
        cuerpo, dv = self.cleaned_data["run_completo"]
        if Usuario.objects.filter(run=cuerpo).exists():
            raise forms.ValidationError("Ya existe un usuario con ese RUN.")
        return cuerpo, dv

    def clean_password1(self):
        p = self.cleaned_data.get("password1")
        if p:
            password_validation.validate_password(p, self.instance)
        return p

    def clean(self):
        datos = super().clean()
        principal = datos.get("especialidad_principal")
        if principal and principal not in (datos.get("especialidades_sel") or []):
            self.add_error("especialidad_principal", "Marca también esta especialidad en la lista.")
        return datos


class MotivoForm(FormEstilo):
    motivo = forms.CharField(label="Motivo", max_length=255, widget=forms.Textarea(attrs={"rows": 2}))


class ClaveAdminForm(FormEstilo):
    """RF-PA-06: el administrador fija una contraseña temporal."""
    password1 = forms.CharField(label="Nueva contraseña", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Repite la contraseña", widget=forms.PasswordInput)

    def __init__(self, usuario, *args, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)

    def clean(self):
        d = super().clean()
        if d.get("password1") and d.get("password1") != d.get("password2"):
            raise forms.ValidationError("Las contraseñas no coinciden.")
        if d.get("password1"):
            password_validation.validate_password(d["password1"], self.usuario)
        return d


class ContactoForm(ModelFormEstilo):
    """RF-URP-10: cada usuario actualiza su correo y teléfono."""

    class Meta:
        model = Usuario
        fields = ["correo", "telefono"]


class RolForm(ModelFormEstilo):
    class Meta:
        model = Rol
        fields = ["nombre", "codigo", "privilegios"]
        widgets = {"privilegios": forms.CheckboxSelectMultiple}


class PrivilegioForm(ModelFormEstilo):
    class Meta:
        model = Privilegio
        fields = ["nombre", "codigo"]


class EspecialidadForm(ModelFormEstilo):
    class Meta:
        model = Especialidad
        fields = ["nombre", "activo"]


class TipoContratoForm(ModelFormEstilo):
    class Meta:
        model = TipoContrato
        fields = ["nombre", "aplica_comision"]


from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm  # noqa: E402


class RecuperarForm(Estilo, PasswordResetForm):
    """RF-AS-05: enlace al correo registrado."""


class NuevaClaveForm(Estilo, SetPasswordForm):
    pass
