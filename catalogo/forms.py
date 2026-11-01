from django import forms

from core.forms import FormEstilo, ModelFormEstilo, col
from core.models import Insumo, Servicio, TipoContrato, TipoServicio


CAMPOS_PRECIO = ["precio", "precio_plus", "precio_ultra_plus"]


class ServicioForm(ModelFormEstilo):
    class Meta:
        model = Servicio
        fields = ["tipo", "nombre", "precio", "precio_plus", "precio_ultra_plus", "tiempo_estimado",
                  "dia_renovacion", "costo_estimado", "especialidades", "descripcion", "observacion"]
        widgets = {"especialidades": forms.CheckboxSelectMultiple}

    def __init__(self, *args, puede_precios=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tipo"].queryset = TipoServicio.objects.filter(activo=True)
        for n in ["tipo", "nombre"]:
            self.fields[n].widget.attrs.update(col(6))
        for n in CAMPOS_PRECIO + ["tiempo_estimado", "dia_renovacion", "costo_estimado"]:
            self.fields[n].widget.attrs.update({**col(4), "inputmode": "numeric"})
        self.fields["precio_plus"].help_text = "Vacío = mismo precio básico."
        if not puede_precios and self.instance.pk:
            for n in CAMPOS_PRECIO:
                self.fields[n].disabled = True
                self.fields[n].help_text = "Necesitas el privilegio «Editar precios» para cambiarlo."


class TipoServicioForm(ModelFormEstilo):
    class Meta:
        model = TipoServicio
        fields = ["nombre", "seguimiento", "descripcion"]

    def __init__(self, *args, puede_precios=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.contratos = list(TipoContrato.objects.filter(aplica_comision=True))
        for c in self.contratos:
            actual = self.instance.porcentaje_para(c) if self.instance.pk else 0
            self.fields[f"comision_{c.pk}"] = forms.DecimalField(
                label=f"Comisión contrato {c.nombre.lower()} (%)", min_value=0, max_value=100, decimal_places=2,
                initial=actual, disabled=not puede_precios,
                help_text="Solo aplica a atenciones registradas desde el cambio.",
                widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.5", **col(6)}))


class InsumoForm(ModelFormEstilo):
    class Meta:
        model = Insumo
        fields = ["nombre", "marca", "calidad", "unidad_medida"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for n in self.fields:
            self.fields[n].widget.attrs.update(col(6))

    def clean(self):
        d = super().clean()
        # RF-I-04: sin duplicados aunque cambien mayúsculas o espacios.
        if d.get("nombre") and d.get("marca") and d.get("calidad"):
            dup = Insumo.objects.filter(nombre__iexact=d["nombre"].strip(), marca__iexact=d["marca"].strip(),
                                        calidad__iexact=d["calidad"].strip()).exclude(pk=self.instance.pk)
            if dup.exists():
                raise forms.ValidationError("Ya existe un insumo con ese nombre, marca y calidad.")
        return d


class EstadoForm(FormEstilo):
    motivo = forms.CharField(label="Motivo", max_length=255, required=False)
