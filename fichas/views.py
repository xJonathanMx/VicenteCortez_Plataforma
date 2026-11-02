from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import Cliente, DetalleAtencionServicio, DetalleFichaInsumo, FichaAtencion, Servicio
from core import rut as rututil
from core.forms import MotivoForm
from core.permisos import exigir, privilegio_requerido

from . import servicios as fs
from .forms import (AgregarServicioForm, FichaNotasForm, FiltroFichasForm, InsumoUsadoForm, NotasServicioForm,
                    NuevaFichaForm, TiempoManualForm, VincularForm)


def fichas_visibles(usuario):
    qs = FichaAtencion.objects.all()
    if usuario.ve_todos_los_clientes:
        return qs
    return qs.filter(Q(abierta_por=usuario) | Q(servicios__peluquero=usuario)).distinct()  # RF-AS-02


def ficha_visible(request, pk):
    ficha = get_object_or_404(FichaAtencion, pk=pk)
    if not fichas_visibles(request.user).filter(pk=pk).exists():
        raise PermissionDenied("Esta ficha no te corresponde.")
    return ficha


def _error(request, e):
    messages.error(request, " ".join(e.messages) if isinstance(e, ValidationError) else str(e))


@login_required
def lista(request):
    datos = request.GET.copy()
    if datos.get("desde") == "hoy":
        datos["desde"] = datos["hasta"] = timezone.localdate().isoformat()
    form = FiltroFichasForm(datos or None)
    qs = (fichas_visibles(request.user).select_related("cliente", "estado", "abierta_por")
          .prefetch_related("servicios__servicio", "servicios__peluquero"))
    if form.is_valid():
        d = form.cleaned_data
        if d["desde"]:
            qs = qs.filter(fecha_hora_inicio__date__gte=d["desde"])
        if d["hasta"]:
            qs = qs.filter(fecha_hora_inicio__date__lte=d["hasta"])
        if d["estado"]:
            qs = qs.filter(estado_id=d["estado"])
        if d["peluquero"]:
            qs = qs.filter(servicios__peluquero=d["peluquero"]).distinct()
        if d["q"]:
            cuerpo, _ = rututil.limpiar(d["q"])
            filtro = Q(nombre_provisorio__icontains=d["q"])
            for palabra in d["q"].split():
                filtro |= Q(cliente__nombre__icontains=palabra) | Q(cliente__ap_paterno__icontains=palabra)
            if cuerpo and cuerpo.isdigit():
                filtro |= Q(cliente__run=cuerpo)
            qs = qs.filter(filtro)
    pagina = Paginator(qs, 25).get_page(request.GET.get("pagina"))
    return render(request, "fichas/lista.html", {"form": form, "pagina": pagina})


@privilegio_requerido("abrir_fichas")
def nueva(request):
    inicial = {}
    cliente = None
    if request.GET.get("cliente"):
        cliente = Cliente.objects.filter(run=request.GET["cliente"], activo=True).first()
        if cliente:
            inicial["cliente"] = cliente.run_formateado
    form = NuevaFichaForm(request.POST or None, initial=inicial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        ficha = fs.abrir_ficha(request.user, d["cliente"], d["nombre_provisorio"], d["diagnostico"])
        messages.success(request, f"Ficha N° {ficha.pk} abierta. Agrega los servicios.")
        return redirect("fichas:detalle", pk=ficha.pk)
    return render(request, "fichas/nueva.html", {"form": form, "cliente": cliente})


@login_required
def detalle(request, pk):
    ficha = ficha_visible(request, pk)
    servicios = (ficha.servicios.select_related("servicio__tipo", "peluquero", "tratamiento_origen")
                 .prefetch_related("insumos__insumo"))
    u = request.user
    ctx = {
        "f": ficha, "servicios": _con_aviso(servicios),
        "puede_editar": ficha.editable and (u.tiene_privilegio("abrir_fichas")),
        "historial": ficha.historial.select_related("estado", "estado_anterior", "usuario"),
        "versiones": ficha.versiones.select_related("usuario"),
        "valoraciones": ficha.valoraciones.select_related("peluquero"),
        "notas_form": FichaNotasForm(instance=ficha),
        "motivo_form": MotivoForm(),
        "vincular_form": VincularForm(),
        "insumo_form": InsumoUsadoForm(),
    }
    for d in ctx["servicios"]:
        if d.estado in ("pendiente", "en_proceso"):
            d.tiempo_form = _tiempo_form(d)
    if ctx["puede_editar"]:
        ctx["agregar_form"] = AgregarServicioForm(ficha=ficha, usuario=u)
    if u.tiene_privilegio("gestionar_beneficios") and ficha.cliente_id and ficha.estado_id != "anulada":
        from beneficios.forms import UsoGiftcardForm, UsoPromocionForm
        usos_gc = list(ficha.usos_giftcard.select_related("giftcard", "registrado_por"))
        usos_pr = list(ficha.usos_promocion.select_related("cliente_promocion__promocion", "servicio", "detalle",
                                                            "registrado_por"))
        pagado_gc = sum(u.monto_usado for u in usos_gc)
        cubierto_pr = sum(u.detalle.precio_cobrado for u in usos_pr if u.detalle_id)
        por_pagar = max(ficha.total - pagado_gc - cubierto_pr, 0)
        gc_form = UsoGiftcardForm(cliente=ficha.cliente)
        ctx.update({
            "uso_gc_form": gc_form, "giftcards": list(gc_form.fields["giftcard"].queryset),
            "uso_pr_form": UsoPromocionForm(cliente=ficha.cliente, ficha=ficha),
            "usos_gc": usos_gc, "usos_pr": usos_pr, "pagado_gc": pagado_gc, "cubierto_pr": cubierto_pr,
            "por_pagar": por_pagar,
        })
    return render(request, "fichas/detalle.html", ctx)


@privilegio_requerido("abrir_fichas")
@require_POST
def notas(request, pk):
    ficha = ficha_visible(request, pk)
    if not ficha.editable:
        messages.error(request, "La ficha está cerrada. Pide a administración que la reabra para corregir.")
        return redirect("fichas:detalle", pk=pk)
    form = FichaNotasForm(request.POST, instance=ficha)
    if form.is_valid():
        f = form.save(commit=False)
        f.modificado_por = request.user
        f.save()
        return redirect(f"{reverse('fichas:detalle', args=[pk])}?guardado=diagnostico#diagnostico")
    messages.error(request, "No se pudo guardar el diagnóstico. Revisa el texto.")
    return redirect("fichas:detalle", pk=pk)


@privilegio_requerido("abrir_fichas")
@require_POST
def agregar_servicio(request, pk):
    ficha = ficha_visible(request, pk)
    form = AgregarServicioForm(request.POST, ficha=ficha, usuario=request.user)
    if form.is_valid():
        d = form.cleaned_data
        try:
            fs.agregar_servicio(ficha, d["servicio"], d["peluquero"], d["variante"], request.user,
                                sesiones_totales=d["sesiones_totales"], tratamiento_origen=d.get("continuar"))
            messages.success(request, f"{d['servicio'].nombre} agregado a la ficha.")
        except ValidationError as e:
            _error(request, e)
    else:
        messages.error(request, "Revisa el servicio: " + "; ".join(e for errs in form.errors.values() for e in errs))
    return redirect("fichas:detalle", pk=pk)


def _con_aviso(servicios):
    """Agrega a cada servicio pendiente el aviso de servicios simultáneos para la confirmación."""
    servicios = list(servicios)
    for s in servicios:
        s.aviso_simultaneo = fs.aviso_simultaneo(s) if s.estado == "pendiente" else ""
    return servicios


def _tiempo_form(d, data=None):
    """Formulario de registro manual, sugiriendo el inicio real (si se inició) y la duración estimada."""
    estimado = d.servicio.tiempo_estimado
    inicio = d.hora_inicio or timezone.now() - timedelta(minutes=estimado)
    return TiempoManualForm(data, prefix=f"t{d.pk}", initial={
        "hora_inicio": timezone.localtime(inicio).replace(second=0, microsecond=0),
        "horas": estimado // 60, "minutos": estimado % 60})


def _detalle(request, pk):
    d = get_object_or_404(DetalleAtencionServicio.objects.select_related("ficha", "servicio"), pk=pk)
    ficha_visible(request, d.ficha_id)
    return d


def _volver(request, d):
    return redirect("inicio") if request.POST.get("volver") == "inicio" else redirect("fichas:detalle", pk=d.ficha_id)


@login_required
@require_POST
def iniciar(request, pk):
    d = _detalle(request, pk)
    aviso = fs.aviso_simultaneo(d)
    if aviso and request.POST.get("confirmar") != "1":
        messages.warning(request, aviso + " Vuelve a tocar «Iniciar servicio» y confirma.")
        return _volver(request, d)
    try:
        fs.iniciar_servicio(d, request.user)
        messages.success(request, f"{d.servicio.nombre} iniciado a las {timezone.localtime():%H:%M}.")
    except (ValidationError, PermissionDenied) as e:
        _error(request, e)
    return _volver(request, d)


@login_required
@require_POST
def terminar(request, pk):
    d = _detalle(request, pk)
    try:
        fs.terminar_servicio(d, request.user)
        messages.success(request, f"{d.servicio.nombre} terminado ({d.duracion_min} min).")
        if d.ficha.todos_terminados:
            messages.info(request, "Todos los servicios están terminados: ya puedes cerrar la ficha.")
    except (ValidationError, PermissionDenied) as e:
        _error(request, e)
    return _volver(request, d)


@login_required
@require_POST
def tiempo_manual(request, pk):
    """RF-ES-05 / RF-FA-09: el peluquero a cargo o administración registra el tiempo a mano."""
    d = _detalle(request, pk)
    form = _tiempo_form(d, request.POST)
    if form.is_valid():
        c = form.cleaned_data
        try:
            fs.registrar_tiempo_manual(d, request.user, c["hora_inicio"], c["duracion"], c["motivo"])
            messages.success(request, f"{d.servicio.nombre} registrado a mano: duró {c['horas']} h {c['minutos']:02d} min.")
            if d.ficha.todos_terminados:
                messages.info(request, "Todos los servicios están terminados: ya puedes cerrar la ficha.")
        except (ValidationError, PermissionDenied) as e:
            _error(request, e)
    else:
        messages.error(request, "Revisa el registro manual: " + "; ".join(e for errs in form.errors.values() for e in errs))
    return redirect(f"{reverse('fichas:detalle', args=[d.ficha_id])}#s{d.pk}")


@login_required
@require_POST
def quitar_servicio(request, pk):
    d = _detalle(request, pk)
    exigir(request.user, "abrir_fichas")
    if d.estado != "pendiente" or not d.ficha.editable:
        messages.error(request, "Solo se puede quitar un servicio que aún no se inicia.")
    elif d.peluquero_id != request.user.pk and not request.user.tiene_privilegio("asignar_peluquero"):
        raise PermissionDenied
    else:
        d.delete()
        messages.success(request, "Servicio quitado de la ficha.")
    return redirect("fichas:detalle", pk=d.ficha_id)


@login_required
@require_POST
def notas_servicio(request, pk):
    d = _detalle(request, pk)
    if not d.ficha.editable:
        raise PermissionDenied
    form = NotasServicioForm(request.POST, instance=d)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.modificado_por = request.user
        obj.save()
        return redirect(f"{reverse('fichas:detalle', args=[d.ficha_id])}?guardado=s{d.pk}#s{d.pk}")
    return redirect("fichas:detalle", pk=d.ficha_id)


@login_required
@require_POST
def agregar_insumo(request, pk):
    d = _detalle(request, pk)
    if not d.ficha.editable:
        raise PermissionDenied
    form = InsumoUsadoForm(request.POST)
    if form.is_valid():
        try:
            fs.agregar_insumo(d, form.cleaned_data["insumo"], form.cleaned_data["cant_usada"],
                              form.cleaned_data["observacion"])
            messages.success(request, "Insumo registrado.")
        except ValidationError as e:
            _error(request, e)
    else:
        messages.error(request, "Elige un insumo de la lista.")
    return redirect("fichas:detalle", pk=d.ficha_id)


@login_required
@require_POST
def quitar_insumo(request, pk):
    i = get_object_or_404(DetalleFichaInsumo.objects.select_related("detalle__ficha"), pk=pk)
    ficha_visible(request, i.detalle.ficha_id)
    if not i.detalle.ficha.editable:
        raise PermissionDenied
    i.delete()
    return redirect("fichas:detalle", pk=i.detalle.ficha_id)


@login_required
@require_POST
def cerrar(request, pk):
    ficha = ficha_visible(request, pk)
    try:
        fs.cerrar_ficha(ficha, request.user)
        n = ficha.valoraciones.count()
        messages.success(request, f"Ficha cerrada. {'Se programaron ' + str(n) + ' valoraciones de seguimiento.' if n else ''}")
    except ValidationError as e:
        _error(request, e)
    return redirect("fichas:detalle", pk=pk)


@privilegio_requerido("validar_fichas")
@require_POST
def validar(request, pk):
    ficha = get_object_or_404(FichaAtencion, pk=pk)
    try:
        fs.validar_ficha(ficha, request.user)
        messages.success(request, f"Ficha N° {pk} validada.")
    except ValidationError as e:
        _error(request, e)
    siguiente = FichaAtencion.objects.filter(estado="cerrada").exclude(pk=pk).order_by("fecha_hora_inicio").first()
    if request.POST.get("siguiente") and siguiente:
        return redirect("fichas:detalle", pk=siguiente.pk)
    return redirect("fichas:detalle", pk=pk)


@privilegio_requerido("validar_fichas")
@require_POST
def anular(request, pk):
    ficha = get_object_or_404(FichaAtencion, pk=pk)
    form = MotivoForm(request.POST)
    if form.is_valid():
        try:
            fs.anular_ficha(ficha, request.user, form.cleaned_data["motivo"])
            messages.success(request, "Ficha anulada. La versión original quedó guardada.")
        except ValidationError as e:
            _error(request, e)
    else:
        messages.error(request, "El motivo es obligatorio para anular.")
    return redirect("fichas:detalle", pk=pk)


@privilegio_requerido("validar_fichas")
@require_POST
def corregir(request, pk):
    ficha = get_object_or_404(FichaAtencion, pk=pk)
    form = MotivoForm(request.POST)
    if form.is_valid():
        try:
            fs.reabrir_para_correccion(ficha, request.user, form.cleaned_data["motivo"])
            messages.success(request, "Ficha reabierta para corregir. La versión anterior quedó guardada.")
        except ValidationError as e:
            _error(request, e)
    else:
        messages.error(request, "El motivo es obligatorio para corregir.")
    return redirect("fichas:detalle", pk=pk)


@login_required
@require_POST
def vincular(request, pk):
    """RF-FA-02: vincular el cliente después de la atención."""
    ficha = ficha_visible(request, pk)
    if ficha.cliente_id:
        messages.error(request, "La ficha ya tiene cliente.")
        return redirect("fichas:detalle", pk=pk)
    form = VincularForm(request.POST)
    if form.is_valid():
        ficha.cliente = form.cleaned_data["cliente"]
        ficha.modificado_por = request.user
        ficha.save()
        if ficha.estado_id in ("cerrada", "validada"):
            from seguimiento.servicios import programar_seguimiento
            programar_seguimiento(ficha)
        messages.success(request, f"Ficha vinculada a {ficha.cliente.nombre_completo}.")
    else:
        messages.error(request, " ".join(e for errs in form.errors.values() for e in errs))
    return redirect("fichas:detalle", pk=pk)


@login_required
def version(request, pk, vid):
    ficha = ficha_visible(request, pk)
    v = get_object_or_404(ficha.versiones, pk=vid)
    servicios = {s.pk: s for s in Servicio.objects.filter(pk__in=[x["servicio"] for x in v.contenido.get("servicios", [])])}
    for s in v.contenido.get("servicios", []):
        s["servicio_nombre"] = servicios.get(s["servicio"]).nombre if servicios.get(s["servicio"]) else s["servicio"]
    return render(request, "fichas/version.html", {"f": ficha, "v": v})


@login_required
def api_sugeridos(request):
    """Peluqueros sugeridos para un servicio (RF-URP-09)."""
    servicio = get_object_or_404(Servicio, pk=request.GET.get("servicio"))
    cliente = Cliente.objects.filter(run=request.GET.get("cliente")).first() if request.GET.get("cliente") else None
    filas = fs.peluqueros_sugeridos(servicio, cliente)
    if not request.user.tiene_privilegio("asignar_peluquero"):
        filas = [f for f in filas if f["usuario"].pk == request.user.pk]
    return JsonResponse({"peluqueros": [
        {"run": f["usuario"].pk, "nombre": f["usuario"].nombre_corto, "especialista": f["especialista"],
         "fijo": f["fijo"], "ocupado": f["ocupado"]} for f in filas]})
