from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core import rut as rututil
from core.forms import MotivoForm
from core.models import CanalComunicacion, Cliente, ConsultaHistorial, EnvioMensaje, HistoricoEstadoCliente, TipoEstado
from core.permisos import privilegio_requerido
from seguimiento import servicios as ss

from .forms import ClienteForm, CorreoClienteForm, EstilistaForm


def buscar_clientes(q, usuario):
    """RF-C-04: por RUN (con o sin formato) o por nombre y apellido."""
    qs = Cliente.objects.visibles_para(usuario)
    q = (q or "").strip()
    if not q:
        return qs.none()
    cuerpo, _ = rututil.limpiar(q)
    if cuerpo and cuerpo.isdigit() and any(c.isdigit() for c in q[:3]):
        solo_digitos = "".join(c for c in q if c.isdigit())
        return qs.filter(Q(run=cuerpo) | Q(run__startswith=solo_digitos))
    filtro = Q()
    for palabra in q.split():
        filtro &= Q(nombre__icontains=palabra) | Q(ap_paterno__icontains=palabra) | Q(ap_materno__icontains=palabra)
    return qs.filter(filtro)


def cliente_visible(request, run):
    cliente = get_object_or_404(Cliente, run=run)
    if not Cliente.objects.visibles_para(request.user).filter(pk=cliente.pk).exists():
        raise PermissionDenied("Este cliente no está entre tus atenciones.")  # RF-AS-02
    return cliente


@login_required
def buscar(request):
    q = request.GET.get("q", "")
    resultados = (buscar_clientes(q, request.user)
                  .annotate(visitas=Count("fichas", filter=~Q(fichas__estado="anulada"), distinct=True),
                            ultima=Max("fichas__fecha_hora_inicio"))
                  .select_related("estilista_fijo")[:50])
    recientes = None
    if not q:
        recientes = (Cliente.objects.visibles_para(request.user).filter(activo=True)
                     .annotate(ultima=Max("fichas__fecha_hora_inicio")).exclude(ultima=None)
                     .order_by("-ultima")[:8])
    return render(request, "clientes/buscar.html", {"q": q, "resultados": resultados, "recientes": recientes})


@login_required
def nuevo(request):
    if not (request.user.tiene_privilegio("abrir_fichas") or request.user.tiene_privilegio("gestionar_clientes")):
        raise PermissionDenied
    inicial = {}
    if request.GET.get("run"):
        inicial["run_completo"] = request.GET["run"]
    form = ClienteForm(request.POST or None, initial=inicial,
                       puede_fijar=request.user.tiene_privilegio("asignar_peluquero"))
    if request.method == "POST" and form.is_valid():
        c = form.save(commit=False)
        c.run, c.dv = form.cleaned_data["run_completo"]
        c.creado_por = request.user
        c.save()
        messages.success(request, f"Cliente {c.nombre_completo} registrado.")
        siguiente = request.GET.get("siguiente")
        if siguiente and siguiente.startswith("/fichas/"):
            return redirect(f"{siguiente}?cliente={c.run}")
        return redirect("clientes:detalle", run=c.run)
    return render(request, "form.html", {"form": form, "titulo": "Nuevo cliente", "boton": "Registrar cliente",
                                         "subtitulo": "El RUN se valida con su dígito verificador.",
                                         "volver": reverse("clientes:buscar")})


@login_required
def detalle(request, run):
    cliente = cliente_visible(request, run)
    ConsultaHistorial.objects.create(usuario=request.user, cliente=cliente)  # RF-RP-12
    fichas = (cliente.fichas.select_related("estado", "abierta_por")
              .prefetch_related("servicios__servicio", "servicios__peluquero", "servicios__insumos__insumo",
                                "valoraciones"))
    from core.models import ClientePromocion, Giftcard
    giftcards = [g for g in Giftcard.objects.filter(beneficiario=cliente, estado="vigente") if g.actualizar_estado() == "vigente"]
    promociones = [p for p in ClientePromocion.objects.filter(Q(comprador=cliente) | Q(beneficiario=cliente),
                                                              estado="vigente").select_related("promocion")
                   if p.actualizar_estado() == "vigente"]
    return render(request, "clientes/detalle.html", {
        "c": cliente, "resumen": cliente.resumen(), "fichas": fichas, "giftcards": giftcards,
        "promociones": promociones, "estilista_form": EstilistaForm(instance=cliente), "motivo_form": MotivoForm(),
        "historial_estado": cliente.historial_estados.select_related("tipo_estado", "responsable")})


@login_required
def editar(request, run):
    """RF-C-01 / RF-C-03: recepción o el peluquero completan los datos después de la atención."""
    cliente = cliente_visible(request, run)
    form = ClienteForm(request.POST or None, instance=cliente,
                       puede_fijar=request.user.tiene_privilegio("asignar_peluquero"))
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Datos del cliente actualizados.")
        return redirect("clientes:detalle", run=run)
    return render(request, "form.html", {"form": form, "titulo": f"Editar a {cliente.nombre_completo}",
                                         "volver": reverse("clientes:detalle", args=[run])})


def borrador_correo(cliente, usuario, ficha=None):
    """Texto inicial del correo manual: nombra los servicios de la ficha (o de la última) para escribir los cuidados."""
    ultima = ficha or (cliente.fichas.exclude(estado="anulada").order_by("-fecha_hora_inicio")
                       .prefetch_related("servicios__servicio").first())
    nombres = [s.servicio.nombre.lower() for s in ultima.servicios.all()] if ultima else []
    servicio = " y ".join(nombres[:2])
    asunto = f"Cuidados para tu {servicio}" if servicio else "Un mensaje de Peluquería Vicente Cortez"
    intro = (f"Te escribimos con algunas recomendaciones para cuidar tu {servicio}:" if servicio
             else "Te escribimos desde Peluquería Vicente Cortez:")
    mensaje = (f"Hola {cliente.nombre},\n\n{intro}\n\n- \n- \n- \n\n"
               f"Si tienes dudas, responde este correo o escríbenos.\n\n"
               f"{usuario.nombre_corto}\nPeluquería Vicente Cortez")
    return {"asunto": asunto, "mensaje": mensaje}


@login_required
def correo(request, run):
    """Correo escrito a mano y enviado solo a este cliente (por ejemplo, los cuidados de un tratamiento)."""
    cliente = cliente_visible(request, run)
    # Desde una ficha (?ficha=N): el borrador usa sus servicios y al terminar se vuelve a la ficha.
    ficha = None
    if (request.GET.get("ficha") or "").isdigit():
        ficha = cliente.fichas.filter(pk=request.GET["ficha"]).first()
    volver = reverse("fichas:detalle", args=[ficha.pk]) if ficha else reverse("clientes:detalle", args=[run])
    if not cliente.correo:
        messages.error(request, "Este cliente no tiene correo registrado. Agrégalo en «Editar datos».")
        return redirect(volver)
    form = CorreoClienteForm(request.POST or None, initial=borrador_correo(cliente, request.user, ficha))
    if request.method == "POST" and form.is_valid():
        canal = CanalComunicacion.objects.filter(codigo="email").first()
        if canal is None:
            messages.error(request, "El canal de correo no está configurado.")
            return redirect(volver)
        try:
            destino, simulado = ss.enviar(canal, cliente, form.cleaned_data["asunto"], form.cleaned_data["mensaje"])
        except ss.ErrorEnvio as e:
            EnvioMensaje.objects.create(canal=canal, destino=cliente.correo, exitoso=False, error=str(e)[:255])
            messages.error(request, f"No se pudo enviar el correo: {e}")
            return render(request, "form.html", contexto_correo(form, cliente, volver))
        EnvioMensaje.objects.create(canal=canal, destino=destino, exitoso=True, simulado=simulado)
        if simulado:
            messages.warning(request, "El correo se generó, pero el sistema está en modo prueba: no llega a la bandeja. "
                                      "Actívalo en Valoraciones › Canales y mensajes.")
        else:
            messages.success(request, f"Correo enviado a {destino}.")
        return redirect(volver)
    return render(request, "form.html", contexto_correo(form, cliente, volver))


def contexto_correo(form, cliente, volver):
    return {"form": form, "titulo": f"Enviar correo a {cliente.nombre_completo}", "boton": "Enviar correo",
            "subtitulo": f"Se envía solo a {cliente.correo}. Nadie más lo recibe ni ve la dirección.",
            "volver": volver}


@privilegio_requerido("asignar_peluquero")
@require_POST
def estilista(request, run):
    cliente = get_object_or_404(Cliente, run=run)
    form = EstilistaForm(request.POST, instance=cliente)
    if form.is_valid():
        form.save()
        messages.success(request, "Estilista fijo actualizado.")
    return redirect("clientes:detalle", run=run)


@privilegio_requerido("gestionar_clientes")
@require_POST
@transaction.atomic
def estado(request, run):
    """RF-PA-14: deshabilitar con motivo, conservando historial."""
    cliente = get_object_or_404(Cliente, run=run)
    form = MotivoForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Indica el motivo del cambio de estado.")
        return redirect("clientes:detalle", run=run)
    cliente.activo = not cliente.activo
    cliente.save(update_fields=["activo"])
    HistoricoEstadoCliente.objects.create(cliente=cliente, tipo_estado=TipoEstado.de(cliente.activo),
                                          observacion=form.cleaned_data["motivo"], responsable=request.user,
                                          fecha_cambio=timezone.now())
    messages.success(request, f"Cliente {'habilitado' if cliente.activo else 'deshabilitado'}.")
    return redirect("clientes:detalle", run=run)
