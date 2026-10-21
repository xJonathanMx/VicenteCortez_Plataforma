from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from catalogo.models import Servicio, UsuarioServicio
from fichas.models import DetalleAtencionServicio, FichaAtencion
from fichas.servicios import estado_peluqueros

from .forms import (ClaveAdminForm, ContactoForm, EspecialidadForm, Estilo, LoginForm, MotivoForm, PrivilegioForm,
                    RolForm, TipoContratoForm, UsuarioForm)
from .models import (Especialidad, HistoricoEstadoUsuario, Privilegio, Rol, TipoContrato, TipoEstado, Usuario,
                     UsuarioEspecialidad)
from .permisos import privilegio_requerido


class Login(auth_views.LoginView):
    template_name = "registration/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class CambioClaveForm(Estilo, PasswordChangeForm):
    pass


@login_required
def inicio(request):
    u = request.user
    hoy = timezone.localdate()
    ctx = {}
    # Lo del propio peluquero: servicios en curso y pendientes, y su meta del mes.
    if u.es_peluquero:
        ctx["mis_servicios"] = (DetalleAtencionServicio.objects
                                .filter(peluquero=u, estado__in=["pendiente", "en_proceso"],
                                        ficha__estado__in=["abierta", "en_atencion"])
                                .select_related("servicio", "ficha__cliente").order_by("-estado", "creado_en"))
        from metas.models import MetaMensual
        from metas.servicios import avance
        meta = MetaMensual.objects.filter(peluquero=u, mes=hoy.month, anio=hoy.year).first()
        ctx["mi_meta"] = avance(meta) if meta else None

    # RF-PA-02: resumen del día para la administración.
    if u.tiene_privilegio("validar_fichas"):
        from beneficios.models import ClientePromocion, Giftcard
        from seguimiento.models import Recordatorio, Valoracion
        limite = hoy + timedelta(days=settings.AVISO_VENCIMIENTO_DIAS)
        en_curso = DetalleAtencionServicio.objects.filter(estado="en_proceso").select_related(
            "servicio", "peluquero", "ficha__cliente")
        ctx["resumen"] = {
            "atenciones_hoy": FichaAtencion.objects.filter(fecha_hora_inicio__date=hoy).exclude(estado="anulada").count(),
            "en_curso": en_curso.count(),
            "por_validar": FichaAtencion.objects.filter(estado="cerrada").count(),
            "valoraciones_pendientes": Valoracion.objects.filter(estado__in=["pendiente", "enviada"],
                                                                 fecha_programada__lte=hoy).count(),
            "recordatorios_hoy": Recordatorio.objects.filter(estado="pendiente", fecha_programada__lte=hoy).count(),
        }
        ctx["excedidos"] = [d for d in en_curso if d.excedido]  # RF-ES-06
        ctx["fallidos"] = (list(Valoracion.objects.filter(estado="error").select_related("ficha__cliente")[:5])
                           + list(Recordatorio.objects.filter(estado="fallido").select_related("cliente")[:5]))  # RF-PA-15
        ctx["por_vencer"] = (list(Giftcard.objects.filter(estado="vigente", fecha_vencimiento__lte=limite)
                                  .select_related("beneficiario")[:5])
                             + list(ClientePromocion.objects.filter(estado="vigente", fecha_vencimiento__lte=limite)
                                    .select_related("comprador", "promocion")[:5]))
        ctx["equipo"] = estado_peluqueros()  # RF-ES-04
    return render(request, "core/inicio.html", ctx)


@login_required
def ajustes(request):
    contacto = ContactoForm(request.POST if request.POST.get("accion") == "contacto" else None, instance=request.user,
                            prefix="c")
    clave = CambioClaveForm(request.user, request.POST if request.POST.get("accion") == "clave" else None, prefix="p")
    if request.method == "POST":
        if request.POST.get("accion") == "contacto" and contacto.is_valid():
            contacto.save()
            messages.success(request, "Datos de contacto actualizados.")
            return redirect("ajustes")
        if request.POST.get("accion") == "clave" and clave.is_valid():
            clave.save()
            update_session_auth_hash(request, clave.user)
            messages.success(request, "Contraseña actualizada.")
            return redirect("ajustes")
    return render(request, "core/ajustes.html", {"contacto": contacto, "clave": clave})


# ------------------------------------------------------------------ usuarios

@privilegio_requerido("gestionar_usuarios")
def usuarios(request):
    q = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "activos")
    qs = Usuario.objects.prefetch_related("roles", "especialidades").select_related("contrato")
    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(ap_paterno__icontains=q) | Q(run__startswith=q.replace(".", "")))
    if estado == "activos":
        qs = qs.filter(is_active=True)
    elif estado == "inactivos":
        qs = qs.filter(is_active=False)
    return render(request, "core/usuarios.html", {"usuarios": qs, "q": q, "estado": estado})


def _guardar_relaciones(usuario, form):
    elegidas = list(form.cleaned_data["especialidades_sel"])
    principal = form.cleaned_data.get("especialidad_principal")
    UsuarioEspecialidad.objects.filter(usuario=usuario).exclude(especialidad__in=elegidas).delete()
    for e in elegidas:
        UsuarioEspecialidad.objects.update_or_create(usuario=usuario, especialidad=e,
                                                     defaults={"es_principal": e == principal})
    servicios = set(form.cleaned_data["servicios_sel"])
    for us in UsuarioServicio.objects.filter(usuario=usuario):
        us.activo = us.servicio in servicios
        us.save()
        servicios.discard(us.servicio)
    for s in servicios:
        UsuarioServicio.objects.create(usuario=usuario, servicio=s)


@privilegio_requerido("gestionar_usuarios")
@transaction.atomic
def usuario_form(request, run=None):
    usuario = get_object_or_404(Usuario, run=run) if run else None
    form = UsuarioForm(request.POST or None, instance=usuario)
    if request.method == "POST" and form.is_valid():
        u = form.save(commit=False)
        if not usuario:
            u.run, u.dv = form.cleaned_data["run_completo"]
        if form.cleaned_data.get("password1"):
            u.set_password(form.cleaned_data["password1"])
        u.save()
        form.save_m2m()
        _guardar_relaciones(u, form)
        messages.success(request, f"Usuario {u.nombre_corto} guardado.")
        return redirect("core:usuario", run=u.run)
    return render(request, "form.html", {
        "form": form, "titulo": f"Editar a {usuario.nombre_corto}" if usuario else "Nuevo usuario",
        "subtitulo": "Datos personales, contrato, roles, especialidades y servicios que puede realizar.",
        "volver": reverse("core:usuario", args=[run]) if run else reverse("core:usuarios")})


@privilegio_requerido("gestionar_usuarios")
def usuario_detalle(request, run):
    u = get_object_or_404(Usuario, run=run)
    return render(request, "core/usuario.html", {
        "u": u, "historial": u.historial_estados.select_related("tipo_estado", "responsable"),
        "servicios": UsuarioServicio.objects.filter(usuario=u, activo=True).select_related("servicio__tipo", "nivel"),
        "especialidades": u.usuarioespecialidad_set.select_related("especialidad"),
        "motivo_form": MotivoForm(), "clave_form": ClaveAdminForm(u)})


@privilegio_requerido("gestionar_usuarios")
@require_POST
@transaction.atomic
def usuario_estado(request, run):
    """RF-URP-03 / RF-PA-04: deshabilitar o habilitar con motivo, sin eliminar."""
    u = get_object_or_404(Usuario, run=run)
    form = MotivoForm(request.POST)
    if u == request.user:
        messages.error(request, "No puedes deshabilitar tu propia cuenta.")
    elif form.is_valid():
        u.is_active = not u.is_active
        u.save(update_fields=["is_active"])
        HistoricoEstadoUsuario.objects.create(usuario=u, tipo_estado=TipoEstado.de(u.is_active),
                                              motivo=form.cleaned_data["motivo"], responsable=request.user)
        messages.success(request, f"{u.nombre_corto} quedó {'habilitado' if u.is_active else 'deshabilitado'}.")
    else:
        messages.error(request, "Para cambiar el estado debes indicar el motivo.")
    return redirect("core:usuario", run=run)


@privilegio_requerido("gestionar_usuarios")
@require_POST
def usuario_clave(request, run):
    u = get_object_or_404(Usuario, run=run)
    form = ClaveAdminForm(u, request.POST)
    if form.is_valid():
        u.set_password(form.cleaned_data["password1"])
        u.save(update_fields=["password"])
        messages.success(request, f"Contraseña de {u.nombre_corto} restablecida. Entrégasela de forma segura.")
    else:
        messages.error(request, " ".join(e for errs in form.errors.values() for e in errs))
    return redirect("core:usuario", run=run)


# ------------------------------------------------------------------ catálogos de acceso

CATALOGOS = {
    "roles": (Rol, RolForm, "Roles", "Cada rol agrupa privilegios. Un usuario puede tener varios."),
    "privilegios": (Privilegio, PrivilegioForm, "Privilegios",
                    "Acciones que el sistema controla en el servidor. El código debe coincidir con el que usa el sistema."),
    "especialidades": (Especialidad, EspecialidadForm, "Especialidades",
                       "Se usan para sugerir peluqueros al asignar un servicio."),
    "contratos": (TipoContrato, TipoContratoForm, "Tipos de contrato",
                  "Solo los contratos que aplican comisión la reciben."),
}


@privilegio_requerido("gestionar_roles", "gestionar_usuarios")
def catalogo_acceso(request, cual):
    if cual not in CATALOGOS:
        raise Http404
    modelo, _, titulo, ayuda = CATALOGOS[cual]
    return render(request, "core/catalogo_acceso.html", {
        "items": modelo.objects.all(), "cual": cual, "titulo": titulo, "ayuda": ayuda,
        "pestanas": [(k, v[2]) for k, v in CATALOGOS.items()]})


@privilegio_requerido("gestionar_roles")
def catalogo_acceso_form(request, cual, pk=None):
    if cual not in CATALOGOS:
        raise Http404
    modelo, form_cls, titulo, _ = CATALOGOS[cual]
    obj = get_object_or_404(modelo, pk=pk) if pk else None
    form = form_cls(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Cambios guardados.")
        return redirect("core:catalogo_acceso", cual=cual)
    return render(request, "form.html", {"form": form, "titulo": f"{'Editar' if obj else 'Agregar'}: {titulo.lower()}",
                                         "volver": reverse("core:catalogo_acceso", args=[cual])})
