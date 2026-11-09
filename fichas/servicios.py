"""
Reglas de negocio de las fichas de atención y la ejecución de servicios.
Las vistas solo llaman a estas funciones; así las reglas se cumplen igual
desde cualquier pantalla.
"""
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.forms.models import model_to_dict
from django.utils import timezone

from core.models import (
    DetalleAtencionServicio, DetalleFichaInsumo, EstadoFicha, FichaAtencion, HistorialEstadoFicha, MetaMensual,
    Usuario, UsuarioServicio,
)


def cambiar_estado(ficha, codigo, usuario, motivo=""):
    if ficha.estado_id == codigo:
        return
    anterior = ficha.estado_id
    ficha.estado_id = codigo
    ficha.modificado_por = usuario
    ficha.save()
    HistorialEstadoFicha.objects.create(ficha=ficha, estado_anterior_id=anterior, estado_id=codigo,
                                        usuario=usuario, motivo=motivo)


def mes_cerrado(momento):
    """True si el mes de ese momento ya tiene metas cerradas (sus comisiones e incentivos quedaron congelados)."""
    local = timezone.localtime(momento)
    return MetaMensual.objects.filter(mes=local.month, anio=local.year, cerrada=True).exists()


@transaction.atomic
def abrir_ficha(usuario, cliente=None, nombre_provisorio="", diagnostico="", fecha_hora_inicio=None, motivo_atraso=""):
    """RF-FA-01 / RF-FA-02: registra quién la abrió y cuándo; el cliente puede quedar pendiente.
    Con fecha_hora_inicio, administración carga una atención pasada: la ficha queda marcada como
    registro atrasado, con el motivo, y el historial guarda cuándo se cargó realmente."""
    datos = {}
    if fecha_hora_inicio:
        if not usuario.tiene_privilegio("validar_fichas"):
            raise PermissionDenied("Solo administración puede registrar atenciones pasadas.")
        if fecha_hora_inicio > timezone.now():
            raise ValidationError("La fecha de la atención no puede ser futura.")
        if not motivo_atraso.strip():
            raise ValidationError("Indica por qué se registra con otra fecha.")
        if mes_cerrado(fecha_hora_inicio):
            raise ValidationError("Ese mes ya está cerrado en metas; no se pueden agregar atenciones.")
        datos = {"fecha_hora_inicio": fecha_hora_inicio, "registro_atrasado": True, "motivo_atraso": motivo_atraso.strip()}
    ficha = FichaAtencion.objects.create(cliente=cliente, abierta_por=usuario, nombre_provisorio=nombre_provisorio,
                                         diagnostico=diagnostico, creado_por=usuario, modificado_por=usuario, **datos)
    motivo = "Ficha abierta"
    if ficha.registro_atrasado:
        motivo = (f"Registro atrasado de la atención del {timezone.localtime(fecha_hora_inicio):%d-%m-%Y %H:%M}: "
                  f"{ficha.motivo_atraso}")
    HistorialEstadoFicha.objects.create(ficha=ficha, estado_id="abierta", usuario=usuario, motivo=motivo)
    return ficha


def peluquero_habilitado(peluquero, servicio):
    return UsuarioServicio.objects.filter(usuario=peluquero, servicio=servicio, activo=True).exists()


def peluqueros_sugeridos(servicio, cliente=None):
    """
    RF-URP-09 / RF-FA-03: primero el estilista fijo del cliente, luego quienes tienen
    la especialidad del servicio, y dentro de cada grupo los disponibles primero.
    Solo se ofrecen peluqueros activos con el servicio habilitado (RF-FA-04).
    """
    candidatos = Usuario.objects.filter(is_active=True, roles__codigo="peluquero",
                                        servicios_habilitados__servicio=servicio,
                                        servicios_habilitados__activo=True).distinct()
    especialidades = set(servicio.especialidades.values_list("id", flat=True))
    ocupados = set(DetalleAtencionServicio.objects.filter(estado="en_proceso").values_list("peluquero_id", flat=True))
    resultado = []
    for p in candidatos.prefetch_related("especialidades"):
        tiene_esp = bool(especialidades & {e.id for e in p.especialidades.all()})
        es_fijo = bool(cliente and cliente.estilista_fijo_id == p.pk)
        resultado.append({"usuario": p, "especialista": tiene_esp, "fijo": es_fijo, "ocupado": p.pk in ocupados})
    resultado.sort(key=lambda r: (not r["fijo"], not r["especialista"], r["ocupado"], r["usuario"].nombre))
    return resultado


@transaction.atomic
def agregar_servicio(ficha, servicio, peluquero, variante, usuario, sesiones_totales=1, tratamiento_origen=None):
    if not ficha.editable:
        raise ValidationError("La ficha ya está cerrada; no se pueden agregar servicios.")
    if not servicio.activo:
        raise ValidationError("El servicio está deshabilitado.")
    if not peluquero.is_active:
        raise ValidationError("El peluquero está deshabilitado.")
    if not peluquero_habilitado(peluquero, servicio):
        raise ValidationError(f"{peluquero.nombre_corto} no tiene habilitado el servicio {servicio.nombre}.")
    # RF-FA-11 / RF-CI-04 / RF-CI-05: precio y comisión vigentes quedan congelados.
    aplica = peluquero.cobra_comision
    porcentaje = servicio.tipo.porcentaje_para(peluquero.contrato) if aplica else 0
    sesion = 1
    if tratamiento_origen:
        sesion = tratamiento_origen.sesiones_siguientes.count() + 2
        sesiones_totales = tratamiento_origen.sesiones_totales
    return DetalleAtencionServicio.objects.create(
        ficha=ficha, servicio=servicio, peluquero=peluquero, variante=variante,
        precio_cobrado=servicio.precio_de(variante), porc_comision_guardado=porcentaje, aplica_comision=aplica,
        sesiones_totales=max(1, sesiones_totales), sesion_numero=sesion, tratamiento_origen=tratamiento_origen,
        creado_por=usuario, modificado_por=usuario)


def _puede_operar(detalle, usuario):
    if detalle.peluquero_id != usuario.pk and not usuario.tiene_privilegio("cerrar_servicios"):
        raise PermissionDenied("Solo el peluquero a cargo puede iniciar o terminar este servicio.")


def otros_en_curso(peluquero, excluir=None):
    """Servicios que el peluquero ya tiene en proceso (puede ser válido: tiempos de espera de productos)."""
    qs = (DetalleAtencionServicio.objects.filter(peluquero=peluquero, estado="en_proceso")
          .select_related("servicio", "ficha__cliente").order_by("hora_inicio"))
    return list(qs.exclude(pk=excluir.pk) if excluir else qs)


def aviso_simultaneo(detalle):
    """Texto de confirmación si el peluquero ya tiene otro servicio en curso; vacío si no."""
    otros = otros_en_curso(detalle.peluquero, detalle)
    if not otros:
        return ""
    lista = "; ".join(f"{o.servicio.nombre} con {o.ficha.nombre_cliente} desde las "
                      f"{timezone.localtime(o.hora_inicio):%H:%M}" for o in otros)
    return (f"{detalle.peluquero.nombre_corto} ya tiene en proceso: {lista}. "
            f"¿Iniciar {detalle.servicio.nombre} de todas formas?")


@transaction.atomic
def iniciar_servicio(detalle, usuario):
    """RF-ES-01 / RF-ES-03."""
    _puede_operar(detalle, usuario)
    if detalle.estado != "pendiente":
        raise ValidationError("Este servicio ya fue iniciado.")
    if not detalle.ficha.editable:
        raise ValidationError("La ficha está cerrada.")
    if detalle.ficha.registro_atrasado:
        raise ValidationError("Es una atención pasada: registra su tiempo a mano.")
    detalle.estado = "en_proceso"
    detalle.hora_inicio = timezone.now()
    detalle.modificado_por = usuario
    detalle.save()
    cambiar_estado(detalle.ficha, "en_atencion", usuario, f"Inicio de {detalle.servicio.nombre}")


@transaction.atomic
def terminar_servicio(detalle, usuario):
    """RF-ES-02 / RF-ES-03."""
    _puede_operar(detalle, usuario)
    if detalle.estado != "en_proceso":
        raise ValidationError("Solo se puede terminar un servicio que está en proceso.")
    detalle.estado = "terminado"
    detalle.hora_termino = timezone.now()
    detalle.modificado_por = usuario
    detalle.save()


@transaction.atomic
def registrar_tiempo_manual(detalle, usuario, hora_inicio, minutos, motivo):
    """RF-ES-05: registra a mano el inicio y la duración cuando no se pudo marcar en vivo
    (ej. se cortó la luz). Sirve para servicios pendientes o en proceso y los deja terminados.
    Queda marcado como manual, con el motivo y quién lo registró."""
    _puede_operar(detalle, usuario)
    if not detalle.ficha.editable:
        raise ValidationError("La ficha está cerrada.")
    if detalle.estado not in ("pendiente", "en_proceso"):
        raise ValidationError("Este servicio ya está terminado.")
    if not motivo.strip():
        raise ValidationError("Indica el motivo del registro manual.")
    if minutos < 1:
        raise ValidationError("Indica cuánto duró el servicio.")
    termino = hora_inicio + timedelta(minutes=minutos)
    if termino > timezone.now():
        raise ValidationError("Según esa hora y duración, el servicio todavía no termina. Revisa los datos.")
    ficha = detalle.ficha
    if ficha.registro_atrasado:
        dia = timezone.localtime(ficha.fecha_hora_inicio)
        if timezone.localtime(hora_inicio).date() != dia.date() or hora_inicio < ficha.fecha_hora_inicio:
            raise ValidationError(f"El servicio debe empezar el {dia:%d-%m-%Y}, desde las {dia:%H:%M} "
                                  "(la fecha y hora de la atención).")
        if mes_cerrado(termino):
            raise ValidationError("Ese mes ya está cerrado en metas; no se pueden agregar atenciones.")
    detalle.estado = "terminado"
    detalle.hora_inicio = hora_inicio
    detalle.hora_termino = termino
    detalle.cierre_manual = True
    detalle.motivo_cierre = f"{motivo.strip()} (registrado por {usuario.nombre_corto})"
    detalle.modificado_por = usuario
    detalle.save()
    cambiar_estado(detalle.ficha, "en_atencion", usuario, f"Registro manual de {detalle.servicio.nombre}")


@transaction.atomic
def cerrar_ficha(ficha, usuario):
    """RF-FA-12: solo con todos los servicios terminados. Programa el seguimiento (RF-VS-01)."""
    from seguimiento.servicios import programar_seguimiento

    if not ficha.editable:
        raise ValidationError("La ficha ya está cerrada.")
    if not ficha.todos_terminados:
        raise ValidationError("Para cerrar la ficha, todos sus servicios deben estar terminados.")
    ficha.fecha_hora_termino = max(s.hora_termino for s in ficha.servicios.all())
    cambiar_estado(ficha, "cerrada", usuario, "Todos los servicios terminados")
    programar_seguimiento(ficha)


@transaction.atomic
def validar_ficha(ficha, usuario):
    """RF-FA-13."""
    if not usuario.tiene_privilegio("validar_fichas"):
        raise PermissionDenied
    if ficha.estado_id != "cerrada":
        raise ValidationError("Solo se validan fichas cerradas.")
    ficha.validada_por = usuario
    ficha.fecha_validacion = timezone.now()
    cambiar_estado(ficha, "validada", usuario, "Revisada por administración")


def snapshot(ficha):
    datos = model_to_dict(ficha, exclude=["id"])
    datos["estado"] = ficha.estado_id
    datos["servicios"] = []
    for s in ficha.servicios.all():
        d = model_to_dict(s, exclude=["ficha"])
        d["insumos"] = [model_to_dict(i, exclude=["detalle"]) for i in s.insumos.all()]
        datos["servicios"].append(d)
    import json

    from django.core.serializers.json import DjangoJSONEncoder
    return json.loads(json.dumps(datos, cls=DjangoJSONEncoder))


@transaction.atomic
def anular_ficha(ficha, usuario, motivo):
    """RF-FA-14: con motivo obligatorio; se conserva la versión original."""
    from core.models import VersionFicha

    if not usuario.tiene_privilegio("validar_fichas"):
        raise PermissionDenied
    if not motivo.strip():
        raise ValidationError("El motivo es obligatorio.")
    VersionFicha.objects.create(ficha=ficha, contenido=snapshot(ficha), motivo=f"Anulación: {motivo}", usuario=usuario)
    ficha.motivo_anulacion = motivo
    cambiar_estado(ficha, "anulada", usuario, motivo)
    ficha.valoraciones.filter(estado="pendiente").update(estado="sin_respuesta", ultimo_error="Ficha anulada")


@transaction.atomic
def reabrir_para_correccion(ficha, usuario, motivo):
    """RF-FA-14: guarda la versión original y deja la ficha editable para corregirla."""
    from core.models import VersionFicha

    if not usuario.tiene_privilegio("validar_fichas"):
        raise PermissionDenied
    if not motivo.strip():
        raise ValidationError("El motivo es obligatorio.")
    if ficha.estado_id == "anulada":
        raise ValidationError("Una ficha anulada no se puede corregir.")
    VersionFicha.objects.create(ficha=ficha, contenido=snapshot(ficha), motivo=f"Corrección: {motivo}", usuario=usuario)
    ficha.validada_por = None
    ficha.fecha_validacion = None
    nuevo = "en_atencion" if ficha.servicios.exclude(estado="pendiente").exists() else "abierta"
    cambiar_estado(ficha, nuevo, usuario, f"Reabierta para corrección: {motivo}")


def agregar_insumo(detalle, insumo, cantidad, observacion):
    """RF-I-05 / RF-I-06: solo insumos activos, varios por servicio."""
    if not insumo.activo:
        raise ValidationError("Ese insumo está desactivado.")
    return DetalleFichaInsumo.objects.create(detalle=detalle, insumo=insumo, cant_usada=cantidad,
                                             observacion=observacion)


def estado_peluqueros():
    """RF-ES-04: disponible u ocupado, calculado desde los servicios en curso."""
    en_curso = {}
    for d in DetalleAtencionServicio.objects.filter(estado="en_proceso").select_related("servicio", "ficha__cliente"):
        en_curso.setdefault(d.peluquero_id, []).append(d)
    filas = []
    for p in Usuario.objects.filter(is_active=True, roles__codigo="peluquero").distinct():
        filas.append({"usuario": p, "servicios": en_curso.get(p.pk, []), "ocupado": p.pk in en_curso})
    filas.sort(key=lambda f: (f["ocupado"], f["usuario"].nombre))
    return filas


ESTADOS_INICIALES = [
    ("abierta", "Abierta", 1), ("en_atencion", "En atención", 2), ("cerrada", "Cerrada", 3),
    ("validada", "Validada", 4), ("anulada", "Anulada", 5),
]


def asegurar_estados():
    for codigo, nombre, orden in ESTADOS_INICIALES:
        EstadoFicha.objects.update_or_create(codigo=codigo, defaults={"nombre": nombre, "orden": orden})
