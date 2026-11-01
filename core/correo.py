"""
Envío de correos configurable desde la plataforma.

`BackendConfigurable` es el EMAIL_BACKEND del proyecto: en cada envío lee la
ConfiguracionCorreo guardada. Si está activa, envía por SMTP con esa cuenta;
si no, deja el correo en la consola (modo prueba). Así la cuenta se puede
cambiar desde la pantalla sin tocar archivos ni reiniciar el servidor.

La contraseña SMTP se guarda cifrada (Fernet) con una llave derivada de SECRET_KEY.
Si se cambia SECRET_KEY, hay que volver a escribir la contraseña en la pantalla.
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.backends.console import EmailBackend as ConsolaBackend
from django.core.mail.backends.smtp import EmailBackend as SMTPBackend


def _fernet():
    llave = hashlib.sha256(("correo:" + settings.SECRET_KEY).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(llave))


def cifrar(texto):
    return _fernet().encrypt(texto.encode()).decode() if texto else ""


def descifrar(texto):
    if not texto:
        return ""
    try:
        return _fernet().decrypt(texto.encode()).decode()
    except InvalidToken:
        return ""  # la SECRET_KEY cambió: hay que volver a ingresar la contraseña


def configuracion():
    from core.models import ConfiguracionCorreo
    try:
        return ConfiguracionCorreo.actual()
    except Exception:  # base de datos aún sin migrar
        return None


def envia_de_verdad():
    conf = configuracion()
    return bool(conf and conf.lista)


class BackendConfigurable(BaseEmailBackend):
    def send_messages(self, mensajes):
        conf = configuracion()
        if not (conf and conf.lista):
            return ConsolaBackend(fail_silently=self.fail_silently).send_messages(mensajes)
        smtp = SMTPBackend(
            host=conf.servidor, port=conf.puerto, username=conf.usuario, password=conf.clave(),
            use_tls=conf.seguridad == "tls", use_ssl=conf.seguridad == "ssl", timeout=20,
            fail_silently=self.fail_silently)
        for m in mensajes:
            # Gmail/Outlook exigen que el remitente sea la misma cuenta autenticada.
            if not m.from_email or m.from_email == settings.DEFAULT_FROM_EMAIL:
                m.from_email = conf.remitente
            # Las respuestas del cliente llegan al correo habitual de la peluquería (ej. @live).
            if conf.responder_a and not m.reply_to:
                m.reply_to = [conf.responder_a]
        return smtp.send_messages(mensajes)
