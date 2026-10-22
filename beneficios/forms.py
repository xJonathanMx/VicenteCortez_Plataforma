from datetime import timedelta

from django import forms
from django.db.models import Q
from django.utils import timezone

from catalogo.models import Servicio
from core.forms import FormEstilo, ModelFormEstilo, col
from fichas.forms import ClienteRunField

from .models import ESTADOS, ClientePromocion, Giftcard, Promocion

FECHA = {"widget": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}


class GiftcardForm(ModelFormEstilo):
    beneficiario = ClienteRunField(label="RUN del beneficiario")
    comprador = ClienteRunField(label="RUN de quien la compra", required=False,
                                help_text="Vacío si la compra el mismo beneficiario.")

    class Meta:
        model = Giftcard
        fields = ["monto_inicial", "fecha_compra", "fecha_vencimiento"]
        widgets = {"fecha_compra": FECHA["widget"], "fecha_vencimiento": FECHA["widget"]}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(["beneficiario", "comprador", "monto_inicial", "fecha_compra", "fecha_vencimiento"])
        self.fields["fecha_vencimiento"].initial = timezone.localdate() + timedelta(days=180)
        for n in self.fields:
            self.fields[n].widget.attrs.update(col(6))
        self.fields["monto_inicial"].widget.attrs["inputmode"] = "numeric"

    def clean(self):
        d = super().clean()
        if d.get("fecha_compra") and d.get("fecha_vencimiento") and d["fecha_vencimiento"] <= d["fecha_compra"]:
            self.add_error("fecha_vencimiento", "Debe ser posterior a la fecha de compra.")
        if d.get("monto_inicial") == 0:
            self.add_error("monto_inicial", "El monto debe ser mayor a cero.")
        return d


class PromocionForm(ModelFormEstilo):
    """Catálogo de promociones con hasta 5 servicios incluidos."""
    FILAS = 5

    class Meta:
        model = Promocion
        fields = ["nombre", "precio"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nombre"].widget.attrs.update(col(8))
        self.fields["precio"].widget.attrs.update(col(4))
        actuales = list(self.instance.servicios.all()) if self.instance.pk else []
        servicios = Servicio.objects.filter(activo=True)
        for i in range(self.FILAS):
            ps = actuales[i] if i < len(actuales) else None
            self.fields[f"servicio_{i}"] = forms.ModelChoiceField(
                servicios, required=i == 0, label=f"Servicio incluido {i + 1}", initial=ps.servicio_id if ps else None,
                widget=forms.Select(attrs={"class": "form-select", **col(8)}))
            self.fields[f"cantidad_{i}"] = forms.IntegerField(
                min_value=1, max_value=50, required=False, label="Veces", initial=ps.cantidad_total if ps else 1,
                widget=forms.NumberInput(attrs={"class": "form-control", **col(4)}))

    def items(self):
        vistos = {}
        for i in range(self.FILAS):
            s = self.cleaned_data.get(f"servicio_{i}")
            if s:
                vistos[s] = vistos.get(s, 0) + (self.cleaned_data.get(f"cantidad_{i}") or 1)
        return vistos


class VentaPromocionForm(ModelFormEstilo):
    comprador = ClienteRunField(label="RUN del cliente que la compra")
    beneficiario = ClienteRunField(label="RUN de quien la usará", required=False,
                                   help_text="Vacío si la usa el mismo comprador.")

    class Meta:
        model = ClientePromocion
        fields = ["promocion", "fecha_compra", "fecha_vencimiento"]
        widgets = {"fecha_compra": FECHA["widget"], "fecha_vencimiento": FECHA["widget"]}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["promocion"].queryset = Promocion.objects.filter(activo=True)
        self.order_fields(["promocion", "comprador", "beneficiario", "fecha_compra", "fecha_vencimiento"])
        self.fields["fecha_vencimiento"].initial = timezone.localdate() + timedelta(days=90)
        for n in self.fields:
            self.fields[n].widget.attrs.update(col(6))

    def clean(self):
        d = super().clean()
        if d.get("fecha_compra") and d.get("fecha_vencimiento") and d["fecha_vencimiento"] <= d["fecha_compra"]:
            self.add_error("fecha_vencimiento", "Debe ser posterior a la fecha de compra.")
        return d


class UsoGiftcardForm(FormEstilo):
    """Las giftcards se muestran como tarjetas seleccionables (ver fichas/detalle.html)."""
    giftcard = forms.ModelChoiceField(Giftcard.objects.none(), label="Giftcard",
                                      error_messages={"required": "Elige la giftcard que se va a usar."})
    monto = forms.IntegerField(label="Monto a descontar", min_value=1,
                               error_messages={"required": "Indica el monto a descontar."})

    def __init__(self, *args, cliente=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["giftcard"].queryset = Giftcard.objects.filter(beneficiario=cliente, estado="vigente")


class UsoPromocionForm(FormEstilo):
    """
    Una sola elección: «qué servicio de qué promoción» se usa. Solo se ofrecen los servicios
    que están en esta ficha, que la promoción incluye y que aún tienen usos disponibles.
    """
    uso = forms.ChoiceField(label="Servicio de la promoción",
                            error_messages={"required": "Elige qué servicio de la promoción se usa."})

    def __init__(self, *args, cliente=None, ficha=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.opciones = []
        en_ficha = {}
        if ficha is not None:
            ya_cubiertos = set(ficha.usos_promocion.exclude(detalle=None).values_list("detalle_id", flat=True))
            for d in ficha.servicios.select_related("servicio"):
                if d.pk not in ya_cubiertos:
                    en_ficha.setdefault(d.servicio_id, d)
        vigentes = ClientePromocion.objects.filter(
            Q(comprador=cliente) | Q(beneficiario=cliente), estado="vigente").select_related("promocion")
        for cp in vigentes:
            for fila in cp.detalle_usos():
                detalle = en_ficha.get(fila["servicio"].pk)
                self.opciones.append({
                    "valor": f"{cp.pk}-{fila['servicio'].pk}", "cp": cp, "fila": fila, "detalle": detalle,
                    "disponible": fila["disponibles"] > 0 and detalle is not None})
        self.fields["uso"].choices = [(o["valor"], o["valor"]) for o in self.opciones if o["disponible"]]

    def clean_uso(self):
        o = next(o for o in self.opciones if o["valor"] == self.cleaned_data["uso"])
        return o["cp"], o["fila"]["servicio"], o["detalle"]


class FiltroBeneficiosForm(FormEstilo):
    estado = forms.ChoiceField(choices=[("", "Todos")] + ESTADOS, required=False, label="Estado")
    q = forms.CharField(required=False, label="Código o cliente")
    desde = forms.DateField(required=False, label="Compra desde", **FECHA)
    hasta = forms.DateField(required=False, label="Compra hasta", **FECHA)
