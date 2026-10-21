import re

from django.contrib.auth.backends import ModelBackend

from . import rut as rututil
from .models import Usuario


def candidatos_run(valor):
    """
    Cuerpos de RUN posibles para lo que escribió el usuario. Con guion es
    inequívoco ('11.111.111-1'). Sin guion ('11111111') puede venir con o sin
    dígito verificador, así que se prueban ambas lecturas.
    """
    texto = (valor or "").strip()
    if "-" in texto:
        cuerpo, _ = rututil.limpiar(texto)
        return [cuerpo] if cuerpo else []
    digitos = re.sub(r"[^0-9kK]", "", texto).upper()
    salida = []
    if rututil.es_valido(digitos):
        salida.append(rututil.limpiar(digitos)[0])  # último carácter = DV
    if digitos.isdigit():
        salida.append(digitos.lstrip("0"))          # escribió solo el cuerpo
    return [c for c in dict.fromkeys(salida) if c]


class RunBackend(ModelBackend):
    """Inicio de sesión con RUN (con o sin puntos, guion o DV) y contraseña (RF-AS-01)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if password is None:
            return None
        usuarios = list(Usuario.objects.filter(run__in=candidatos_run(username)))
        if not usuarios:
            Usuario().set_password(password)  # mismo costo de tiempo exista o no el RUN
            return None
        for user in usuarios:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        return None

    def get_user(self, user_id):
        try:
            return Usuario.objects.get(pk=user_id)
        except Usuario.DoesNotExist:
            return None
