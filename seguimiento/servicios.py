"""
Motor de seguimiento: programa valoraciones y recordatorios, y los envía por
correo (por ahora el único canal habilitado, ver CANALES_ENVIO) o WhatsApp. Se ejecuta con `python manage.py procesar_envios`
(programarlo cada 15 minutos con el Programador de tareas o cron).
"""
import calendar
import json
import logging
import re
import urllib.error
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from core.models import CanalComunicacion, EnvioMensaje, Plantilla, Recordatorio, Valoracion

log = logging.getLogger("seguimiento")

TEXTOS_POR_DEFECTO = {
    "valoracion": ("¿Cómo te fue en Vicente Cortez?",
                   "Hola {nombre}, gracias por visitarnos. ¿Cómo quedaste con tu atención ({servicio})? "
                   "Califica a {peluquero} del 1 al 5 aquí: {enlace}"),
    "renovacion": ("Es momento de renovar tu {servicio}",
                   "Hola {nombre}, ya pasó el tiempo recomendado desde tu {servicio}. "
                   "Para mantener el resultado te sugerimos agendar tu renovación. ¡Te esperamos!"),
    "giftcard": ("Tu giftcard está por vencer",
                 "Hola {nombre}, tu giftcard {codigo} tiene un saldo de ${saldo} y vence el {fecha}. ¡Aprovéchala!"),
}


# ---------------------------------------------------------------- programación

def fin_de_mes(fecha):
    return fecha.replace(day=calendar.monthrange(fecha.year, fecha.month)[1])


@transaction.atomic
def programar_seguimiento(ficha):
    """
    RF-VS-01 a RF-VS-04: corte -> 1 valoración (día siguiente);
    tratamiento (o ficha mixta con al menos un tratamiento) -> 2 (día siguiente y fin de mes).
    También programa los recordatorios de renovación de cada servicio.
    """
    if not ficha.cliente_id or ficha.estado_id == "anulada":
        return []
    servicios = list(ficha.servicios.select_related("servicio__tipo", "peluquero"))
    if not servicios:
        return []
    fecha_atencion = timezone.localtime(ficha.fecha_hora_termino or ficha.fecha_hora_inicio).date()
    reglas = {s.servicio.tipo.seguimiento for s in servicios}
    principal = next((s for s in servicios if s.servicio.tipo.seguimiento == "tratamiento"),
                     next((s for s in servicios if s.servicio.tipo.seguimiento == "corte"), servicios[0]))

    programadas = []
    if reglas & {"corte", "tratamiento"}:
        programadas.append(("dia_siguiente", fecha_atencion + timedelta(days=1)))
    if "tratamiento" in reglas:
        cierre = fin_de_mes(fecha_atencion)
        if cierre <= fecha_atencion + timedelta(days=1):
            cierre = fin_de_mes(cierre + timedelta(days=1))
        programadas.append(("fin_mes", cierre))

    # En una atención registrada con atraso, lo que ya debió enviarse no se envía tarde.
    hoy = timezone.localdate()
    programadas = [(tipo, fecha) for tipo, fecha in programadas if fecha >= hoy]
    creadas = []
    for tipo, fecha in programadas:
        # RF-VS-11: la restricción única impide duplicados; get_or_create no reenvía.
        v, nueva = Valoracion.objects.get_or_create(
            ficha=ficha, tipo=tipo, defaults={"fecha_programada": fecha, "peluquero": principal.peluquero})
        if nueva:
            creadas.append(v)

    for s in servicios:
        dias = s.servicio.dia_renovacion
        if dias and s.hora_termino and not s.recordatorios.filter(tipo="renovacion").exists():
            fecha = timezone.localtime(s.hora_termino).date() + timedelta(days=dias)
            if fecha >= hoy:
                Recordatorio.objects.create(tipo="renovacion", cliente=ficha.cliente, detalle=s, fecha_programada=fecha)
    return creadas


def programar_avisos_giftcards(hoy=None):
    """RF-GC-16: avisa una vez cuando la giftcard está próxima a vencer."""
    from core.models import Giftcard

    hoy = hoy or timezone.localdate()
    limite = hoy + timedelta(days=settings.AVISO_VENCIMIENTO_DIAS)
    n = 0
    for g in Giftcard.objects.filter(estado="vigente", fecha_vencimiento__range=(hoy, limite)):
        if not g.recordatorios.exists():
            Recordatorio.objects.create(tipo="giftcard", cliente=g.beneficiario, giftcard=g, fecha_programada=hoy)
            n += 1
    return n


# ---------------------------------------------------------------- envío

class ErrorEnvio(Exception):
    def __init__(self, mensaje, definitivo=False):
        super().__init__(mensaje)
        self.definitivo = definitivo  # dato inválido: no tiene sentido reintentar


def normalizar_telefono(telefono):
    digitos = re.sub(r"\D", "", telefono or "")
    if len(digitos) == 9 and digitos.startswith("9"):
        digitos = "56" + digitos
    if len(digitos) == 8:
        digitos = "569" + digitos
    if not re.fullmatch(r"569\d{8}", digitos):
        raise ErrorEnvio(f"Número de WhatsApp inválido: «{telefono or 'vacío'}»", definitivo=True)
    return digitos


def elegir_canal(cliente):
    activos = {c.codigo: c for c in CanalComunicacion.objects.filter(activo=True, codigo__in=settings.CANALES_ENVIO)}
    if list(activos) == ["email"]:  # configuración actual: todo por correo
        if not cliente.correo:
            raise ErrorEnvio("El cliente no tiene correo registrado.", definitivo=True)
        return activos["email"]
    preferido = cliente.canal_preferido
    if preferido == "whatsapp" and not cliente.telefono and cliente.correo:
        preferido = "email"
    if preferido == "email" and not cliente.correo and cliente.telefono:
        preferido = "whatsapp"
    canal = activos.get(preferido) or next(iter(activos.values()), None)
    if canal is None:
        raise ErrorEnvio("No hay canales de comunicación activos.")
    return canal


def armar_mensaje(tipo, canal, contexto):
    p = Plantilla.objects.filter(tipo=tipo, canal=canal).first()
    asunto, cuerpo = (p.asunto, p.cuerpo) if p else TEXTOS_POR_DEFECTO[tipo]
    asunto = asunto or TEXTOS_POR_DEFECTO[tipo][0]
    try:
        return asunto.format(**contexto), cuerpo.format(**contexto)
    except (KeyError, IndexError) as e:
        raise ErrorEnvio(f"La plantilla usa una variable desconocida: {e}", definitivo=True)


def modo_prueba_correo():
    """True si los correos solo se muestran en consola (no hay cuenta de correo activa)."""
    from core.correo import envia_de_verdad
    if settings.EMAIL_BACKEND == "core.correo.BackendConfigurable":
        return not envia_de_verdad()
    return settings.EMAIL_BACKEND.endswith(("console.EmailBackend", "locmem.EmailBackend"))


def enviar(canal, cliente, asunto, cuerpo, html=None):
    """Devuelve (destino, simulado). Lanza ErrorEnvio si falla. `html` es la versión con diseño del correo."""
    if canal.codigo == "email":
        try:
            validate_email(cliente.correo)
        except ValidationError:
            raise ErrorEnvio(f"Correo inválido: «{cliente.correo or 'vacío'}»", definitivo=True)
        try:
            correo = EmailMultiAlternatives(asunto, cuerpo, None, [cliente.correo])
            if html:
                correo.attach_alternative(html, "text/html")
            correo.send()
        except Exception as e:  # SMTP caído, credenciales, etc.
            raise ErrorEnvio(f"Fallo SMTP: {e}"[:250])
        return cliente.correo, modo_prueba_correo()

    numero = normalizar_telefono(cliente.telefono)
    if not settings.WHATSAPP_TOKEN:
        log.info("[WhatsApp simulado] a %s: %s", numero, cuerpo)
        return numero, True
    url = f"https://graph.facebook.com/v21.0/{settings.WHATSAPP_PHONE_ID}/messages"
    datos = json.dumps({"messaging_product": "whatsapp", "to": numero, "type": "text",
                        "text": {"body": cuerpo}}).encode()
    req = urllib.request.Request(url, data=datos, method="POST", headers={
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            r.read()
    except urllib.error.HTTPError as e:
        raise ErrorEnvio(f"WhatsApp respondió {e.code}: {e.read()[:150]!r}", definitivo=400 <= e.code < 500)
    except Exception as e:
        raise ErrorEnvio(f"WhatsApp no disponible: {e}"[:250])
    return numero, False


def _intentar(objeto, tipo, cliente, contexto, estado_ok, estado_error, html=None, **fk):
    canal = None
    try:
        canal = elegir_canal(cliente)
        asunto, cuerpo = armar_mensaje(tipo, canal, contexto)
        destino, simulado = enviar(canal, cliente, asunto, cuerpo, html=html if canal.codigo == "email" else None)
    except ErrorEnvio as e:
        objeto.intentos += 1
        objeto.ultimo_error = str(e)[:255]
        # RNF Confiabilidad-02: hasta N intentos; un dato inválido falla de inmediato.
        if e.definitivo or objeto.intentos >= settings.ENVIO_MAX_INTENTOS:
            objeto.estado = estado_error
        objeto.save()
        if canal:
            EnvioMensaje.objects.create(canal=canal, destino=_destino(canal, cliente), exitoso=False,
                                        error=str(e)[:255], **fk)
        return False
    objeto.intentos += 1
    objeto.estado = estado_ok
    objeto.fecha_envio = timezone.now()
    objeto.ultimo_error = ""
    objeto.save()
    EnvioMensaje.objects.create(canal=canal, destino=destino, exitoso=True, simulado=simulado, **fk)
    return True


def _destino(canal, cliente):
    return (cliente.correo if canal.codigo == "email" else cliente.telefono) or "(vacío)"


def enviar_valoracion(v):
    if v.estado == "respondida":  # RF-VS-11
        return False
    f = v.ficha
    servicio = ", ".join(s.servicio.nombre.lower() for s in f.servicios.all()[:2])
    ctx = {"nombre": f.cliente.nombre, "servicio": servicio, "peluquero": v.peluquero.nombre,
           "enlace": v.enlace, "fecha": "", "codigo": "", "saldo": ""}
    return _intentar(v, "valoracion", f.cliente, ctx, "enviada", "error", html=html_valoracion(v, ctx), valoracion=v)


def html_valoracion(v, ctx):
    """Correo con 5 estrellas: cada una abre la página de valoración con esa nota ya marcada."""
    sitio = settings.SITIO_URL.rstrip("/")
    estrellas = [{"nota": n, "url": f"{v.enlace}?nota={n}"} for n in range(1, 6)]
    return render_to_string("correos/valoracion.html", {
        **ctx, "estrellas": estrellas, "logo": f"{sitio}/static/img/logo.png", "fecha": v.ficha.fecha_hora_inicio})


def enviar_recordatorio(r):
    ctx = {"nombre": r.cliente.nombre, "servicio": "", "peluquero": "", "enlace": "", "fecha": "",
           "codigo": "", "saldo": ""}
    if r.detalle_id:
        ctx["servicio"] = r.detalle.servicio.nombre.lower()
        ctx["peluquero"] = r.detalle.peluquero.nombre
    if r.giftcard_id:
        ctx.update(codigo=r.giftcard.codigo, saldo=f"{r.giftcard.saldo_actual:,}".replace(",", "."),
                   fecha=r.giftcard.fecha_vencimiento.strftime("%d-%m-%Y"))
    return _intentar(r, r.tipo, r.cliente, ctx, "enviado", "fallido", recordatorio=r)


def procesar_pendientes(hoy=None):
    """Una pasada completa del motor. Devuelve un resumen."""
    from core.models import ClientePromocion, Giftcard

    hoy = hoy or timezone.localdate()
    resumen = {"valoraciones": 0, "recordatorios": 0, "fallidos": 0, "sin_respuesta": 0, "avisos_giftcard": 0}

    for g in Giftcard.objects.filter(estado__in=["vigente", "agotada"]):
        g.actualizar_estado()
    for p in ClientePromocion.objects.filter(estado="vigente"):
        p.actualizar_estado()
    resumen["avisos_giftcard"] = programar_avisos_giftcards(hoy)

    for v in Valoracion.objects.filter(estado="pendiente", fecha_programada__lte=hoy,
                                       ficha__cliente__isnull=False).select_related("ficha__cliente", "peluquero"):
        ok = enviar_valoracion(v)
        resumen["valoraciones" if ok else "fallidos"] += 1

    for r in Recordatorio.objects.filter(estado="pendiente", fecha_programada__lte=hoy).select_related("cliente"):
        ok = enviar_recordatorio(r)
        resumen["recordatorios" if ok else "fallidos"] += 1

    # RF-VS-10: sin respuesta tras el plazo.
    limite = timezone.now() - timedelta(days=settings.VALORACION_PLAZO_DIAS)
    resumen["sin_respuesta"] = Valoracion.objects.filter(estado="enviada", fecha_envio__lt=limite).update(
        estado="sin_respuesta")
    return resumen


def reintentar(objeto):
    """El administrador corrige el dato del cliente y vuelve a intentar un envío fallido."""
    objeto.estado = "pendiente"
    objeto.intentos = 0
    objeto.save()
    return enviar_valoracion(objeto) if isinstance(objeto, Valoracion) else enviar_recordatorio(objeto)
