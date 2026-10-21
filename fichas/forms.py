from django import forms
from django.utils import timezone

from catalogo.models import VARIANTES, Insumo, Servicio
from clientes.models import Cliente
from core.forms import CampoRun, FormEstilo, ModelFormEstilo, col
from core.models import Usuario

from .models import DetalleAtencionServicio, FichaAtencion


class ClienteRunField(CampoRun):
    def clean(self, value):
        datos = super().clean(value)
        if not datos:
            return None
        cliente = Cliente.objects.filter(run=datos[0]).first()
        if cliente is None:
            raise forms.ValidationError("No hay un cliente con ese RUN. Regístralo primero o abre la ficha sin cliente.")
        if not cliente.activo:
            raise forms.ValidationError("Ese cliente está deshabilitado.")
        return cliente


class NuevaFichaForm(FormEstilo):
    cliente = ClienteRunField(label="RUN del cliente", required=False,
                              help_text="Si llega por primera vez o sin hora, puedes dejarlo vacío y vincularlo después.")
    nombre_provisorio = forms.CharField(label="Nombre del cliente (si no tiene RUN registrado)", max_length=80,
                                        required=False)
    diagnostico = forms.CharField(label="Diagnóstico inicial", required=False, widget=forms.Textarea(attrs={
        "rows": 3, "placeholder": "Lo que observas a simple vista: largo, estado, color base, canas…"}))

    def clean(self):
        d = super().clean()
        if not d.get("cliente") and not d.get("nombre_provisorio") and not self.errors:
            self.add_error("nombre_provisorio", "Indica el RUN del cliente o al menos su nombre.")
        return d


class AgregarServicioForm(FormEstilo):
    servicio = forms.ModelChoiceField(Servicio.objects.none(), label="Servicio")
    variante = forms.ChoiceField(choices=VARIANTES, label="Calidad")
    peluquero = forms.ModelChoiceField(Usuario.objects.none(), label="Peluquero a cargo")
    sesiones_totales = forms.IntegerField(label="Sesiones del tratamiento", min_value=1, max_value=12, initial=1,
                                          help_text="Más de 1 si el tratamiento requiere varias visitas.")
    continuar = forms.ModelChoiceField(DetalleAtencionServicio.objects.none(), required=False,
                                       label="O continúa un tratamiento en curso",
                                       empty_label="No, es un servicio nuevo")

    def __init__(self, *args, ficha=None, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["servicio"].queryset = Servicio.objects.filter(activo=True, tipo__activo=True).select_related("tipo")
        pelus = Usuario.objects.filter(is_active=True, roles__codigo="peluquero").distinct()
        if usuario and not usuario.tiene_privilegio("asignar_peluquero"):
            pelus = pelus.filter(pk=usuario.pk)  # sin privilegio, solo se asigna a sí mismo
        self.fields["peluquero"].queryset = pelus
        if ficha and ficha.cliente and ficha.cliente.estilista_fijo_id and pelus.filter(pk=ficha.cliente.estilista_fijo_id).exists():
            self.fields["peluquero"].initial = ficha.cliente.estilista_fijo_id  # RF-FA-03
        elif usuario and usuario.es_peluquero:
            self.fields["peluquero"].initial = usuario.pk
        self.fields["servicio"].widget.attrs.update({
            "data-sugerir-url": "/fichas/api/sugeridos/",
            "data-cliente": ficha.cliente_id if ficha and ficha.cliente_id else ""})
        for n in ["servicio", "peluquero"]:
            self.fields[n].widget.attrs.update(col(6))
        for n in ["variante", "sesiones_totales"]:
            self.fields[n].widget.attrs.update(col(6))
        abiertos = DetalleAtencionServicio.objects.none()
        if ficha and ficha.cliente_id:
            candidatos = (DetalleAtencionServicio.objects
                          .filter(ficha__cliente=ficha.cliente, sesiones_totales__gt=1, tratamiento_origen__isnull=True)
                          .exclude(ficha=ficha).exclude(ficha__estado="anulada").select_related("servicio"))
            ids = [c.pk for c in candidatos if c.sesiones_siguientes.count() + 1 < c.sesiones_totales]
            abiertos = DetalleAtencionServicio.objects.filter(pk__in=ids).select_related("servicio", "ficha")
        self.fields["continuar"].queryset = abiertos
        self.fields["continuar"].label_from_instance = (
            lambda d: f"{d.servicio.nombre}, iniciado el {timezone.localtime(d.ficha.fecha_hora_inicio):%d-%m-%Y} "
                      f"(sesión {d.sesiones_siguientes.count() + 2} de {d.sesiones_totales})")
        if not abiertos.exists():
            del self.fields["continuar"]

    def clean(self):
        d = super().clean()
        cont = d.get("continuar")
        if cont:
            d["servicio"] = cont.servicio
            self.errors.pop("servicio", None)
        return d


class InsumoUsadoForm(FormEstilo):
    insumo = forms.ModelChoiceField(Insumo.objects.filter(activo=True), label="Insumo")
    cant_usada = forms.DecimalField(label="Cantidad", required=False, min_value=0, decimal_places=2,
                                    widget=forms.NumberInput(attrs={"inputmode": "decimal", "step": "any"}))
    observacion = forms.CharField(label="Observación", required=False, max_length=255)


class NotasServicioForm(ModelFormEstilo):
    class Meta:
        model = DetalleAtencionServicio
        fields = ["formula", "observacion_producto"]
        widgets = {"formula": forms.Textarea(attrs={"rows": 2, "placeholder": "Ej. 7.1 + 7.0 (1:1) con oxidante 20 vol, 35 min"}),
                   "observacion_producto": forms.Textarea(attrs={"rows": 2})}


class FichaNotasForm(ModelFormEstilo):
    class Meta:
        model = FichaAtencion
        fields = ["diagnostico", "observaciones"]


class CierreManualForm(FormEstilo):
    hora_termino = forms.DateTimeField(label="Hora real de término", widget=forms.DateTimeInput(
        attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"), input_formats=["%Y-%m-%dT%H:%M"])
    motivo = forms.CharField(label="Motivo", max_length=255)


class VincularForm(FormEstilo):
    cliente = ClienteRunField(label="RUN del cliente")


class FiltroFichasForm(FormEstilo):
    desde = forms.DateField(required=False, label="Desde", widget=forms.DateInput(attrs={"type": "date"}))
    hasta = forms.DateField(required=False, label="Hasta", widget=forms.DateInput(attrs={"type": "date"}))
    estado = forms.ChoiceField(required=False, label="Estado", choices=[
        ("", "Todos"), ("abierta", "Abierta"), ("en_atencion", "En atención"), ("cerrada", "Cerrada (por validar)"),
        ("validada", "Validada"), ("anulada", "Anulada")])
    peluquero = forms.ModelChoiceField(Usuario.objects.filter(roles__codigo="peluquero").distinct(), required=False,
                                       label="Peluquero", empty_label="Todos")
    q = forms.CharField(required=False, label="Cliente", widget=forms.TextInput(attrs={"placeholder": "Nombre o RUN"}))
