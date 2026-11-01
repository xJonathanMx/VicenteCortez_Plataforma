from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.forms import MotivoForm
from core.permisos import privilegio_requerido
from core.models import ClientePromocion, FichaAtencion, Giftcard, Promocion, PromocionServicio

from . import servicios as bs
from .forms import (FiltroBeneficiosForm, GiftcardForm, PromocionForm, UsoGiftcardForm, UsoPromocionForm,
                    VentaPromocionForm)

PRIV = "gestionar_beneficios"  # RF-GC-15 / RF-PR-15


def _filtrar(qs, form, campos_cliente):
    if not form.is_valid():
        return qs
    d = form.cleaned_data
    if d["estado"]:
        qs = qs.filter(estado=d["estado"])
    if d["q"]:
        f = Q(codigo__iexact=d["q"].strip())
        for c in campos_cliente:
            f |= Q(**{f"{c}__nombre__icontains": d["q"]}) | Q(**{f"{c}__ap_paterno__icontains": d["q"]}) | Q(
                **{f"{c}__run": d["q"].replace(".", "").split("-")[0]})
        qs = qs.filter(f)
    if d["desde"]:
        qs = qs.filter(fecha_compra__gte=d["desde"])
    if d["hasta"]:
        qs = qs.filter(fecha_compra__lte=d["hasta"])
    return qs


@privilegio_requerido(PRIV)
def inicio(request):
    vista = request.GET.get("vista", "giftcards")
    form = FiltroBeneficiosForm(request.GET or None)
    for g in Giftcard.objects.filter(estado__in=["vigente"]):
        g.actualizar_estado()
    ctx = {"vista": vista, "form": form}
    if vista == "giftcards":
        ctx["items"] = _filtrar(Giftcard.objects.select_related("beneficiario"), form, ["beneficiario", "comprador"])
    elif vista == "promociones":
        for p in ClientePromocion.objects.filter(estado="vigente"):
            p.actualizar_estado()
        ctx["items"] = _filtrar(ClientePromocion.objects.select_related("promocion", "comprador"), form,
                                ["comprador", "beneficiario"])
    else:
        ctx["items"] = Promocion.objects.prefetch_related("servicios__servicio")
    return render(request, "beneficios/inicio.html", ctx)


@privilegio_requerido(PRIV)
def giftcard_nueva(request):
    form = GiftcardForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        g = form.save(commit=False)
        g.beneficiario = form.cleaned_data["beneficiario"]
        g.comprador = form.cleaned_data["comprador"] or g.beneficiario
        g.saldo_actual = g.monto_inicial
        g.creada_por = request.user
        g.save()
        messages.success(request, f"Giftcard {g.codigo} registrada por ${g.monto_inicial:,}.".replace(",", "."))
        return redirect("beneficios:giftcard", pk=g.pk)
    return render(request, "form.html", {"form": form, "titulo": "Nueva giftcard", "boton": "Registrar giftcard",
                                         "subtitulo": "Registro informativo: el pago se hace fuera del sistema.",
                                         "volver": reverse("beneficios:inicio")})


@privilegio_requerido(PRIV)
def giftcard(request, pk):
    g = get_object_or_404(Giftcard.objects.select_related("beneficiario", "comprador", "creada_por"), pk=pk)
    g.actualizar_estado()
    return render(request, "beneficios/giftcard.html", {
        "g": g, "usos": g.usos.select_related("ficha", "registrado_por"), "motivo_form": MotivoForm()})


@privilegio_requerido(PRIV)
@require_POST
def giftcard_deshabilitar(request, pk):
    g = get_object_or_404(Giftcard, pk=pk)
    form = MotivoForm(request.POST)
    try:
        bs.deshabilitar(g, form.data.get("motivo", ""), request.user)
        messages.success(request, "Giftcard deshabilitada. Su historial se conserva.")
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    return redirect("beneficios:giftcard", pk=pk)


@privilegio_requerido(PRIV)
@transaction.atomic
def promocion_form(request, pk=None):
    promo = get_object_or_404(Promocion, pk=pk) if pk else None
    form = PromocionForm(request.POST or None, instance=promo)
    if request.method == "POST" and form.is_valid():
        p = form.save()
        items = form.items()
        if promo and p.ventas.exists():
            messages.warning(request, "La promoción ya tiene ventas: se actualizaron nombre y precio, no los servicios.")
        else:
            p.servicios.exclude(servicio__in=items.keys()).delete()
            for s, n in items.items():
                PromocionServicio.objects.update_or_create(promocion=p, servicio=s, defaults={"cantidad_total": n})
            messages.success(request, f"Promoción {p.nombre} guardada.")
        return redirect(f"{reverse('beneficios:inicio')}?vista=catalogo")
    return render(request, "form.html", {"form": form, "titulo": "Editar promoción" if promo else "Nueva promoción",
                                         "subtitulo": "Define qué servicios incluye y cuántas veces se puede usar cada uno.",
                                         "volver": f"{reverse('beneficios:inicio')}?vista=catalogo"})


@privilegio_requerido(PRIV)
@require_POST
def promocion_estado(request, pk):
    p = get_object_or_404(Promocion, pk=pk)
    p.activo = not p.activo
    p.save(update_fields=["activo"])
    return redirect(f"{reverse('beneficios:inicio')}?vista=catalogo")


@privilegio_requerido(PRIV)
def vender_promocion(request):
    form = VentaPromocionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cp = form.save(commit=False)
        cp.comprador = form.cleaned_data["comprador"]
        cp.beneficiario = form.cleaned_data["beneficiario"]
        cp.creada_por = request.user
        cp.save()
        messages.success(request, f"Promoción registrada con el código {cp.codigo}.")
        return redirect("beneficios:cliente_promocion", pk=cp.pk)
    return render(request, "form.html", {"form": form, "titulo": "Registrar promoción adquirida", "boton": "Registrar",
                                         "subtitulo": "Registro informativo: el pago se hace fuera del sistema.",
                                         "volver": f"{reverse('beneficios:inicio')}?vista=promociones"})


@privilegio_requerido(PRIV)
def cliente_promocion(request, pk):
    cp = get_object_or_404(ClientePromocion.objects.select_related("promocion", "comprador", "beneficiario"), pk=pk)
    cp.actualizar_estado()
    return render(request, "beneficios/cliente_promocion.html", {
        "cp": cp, "filas": cp.detalle_usos(), "usos": cp.usos.select_related("servicio", "ficha", "registrado_por"),
        "motivo_form": MotivoForm()})


@privilegio_requerido(PRIV)
@require_POST
def cliente_promocion_deshabilitar(request, pk):
    cp = get_object_or_404(ClientePromocion, pk=pk)
    try:
        bs.deshabilitar(cp, request.POST.get("motivo", ""), request.user)
        messages.success(request, "Promoción deshabilitada. Su historial se conserva.")
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    return redirect("beneficios:cliente_promocion", pk=pk)


@privilegio_requerido(PRIV)
@require_POST
def usar_giftcard(request, ficha_pk):
    ficha = get_object_or_404(FichaAtencion, pk=ficha_pk)
    form = UsoGiftcardForm(request.POST, cliente=ficha.cliente)
    if form.is_valid():
        try:
            g = form.cleaned_data["giftcard"]
            bs.usar_giftcard(g, ficha, form.cleaned_data["monto"], request.user)
            messages.success(request, f"Se descontaron ${form.cleaned_data['monto']:,} de la giftcard {g.codigo}.".replace(",", "."))
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
    else:
        messages.error(request, " ".join(e for errs in form.errors.values() for e in errs))
    return redirect(f"{reverse('fichas:detalle', args=[ficha_pk])}#beneficios")


@privilegio_requerido(PRIV)
@require_POST
def usar_promocion(request, ficha_pk):
    ficha = get_object_or_404(FichaAtencion, pk=ficha_pk)
    form = UsoPromocionForm(request.POST, cliente=ficha.cliente, ficha=ficha)
    if form.is_valid():
        cp, servicio, detalle = form.cleaned_data["uso"]
        try:
            bs.usar_promocion(cp, servicio, ficha, request.user, detalle=detalle)
            messages.success(request, f"Se usó {servicio.nombre} de la promoción {cp.promocion} ({cp.codigo}).")
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
    else:
        messages.error(request, " ".join(e for errs in form.errors.values() for e in errs))
    return redirect(f"{reverse('fichas:detalle', args=[ficha_pk])}#beneficios")
