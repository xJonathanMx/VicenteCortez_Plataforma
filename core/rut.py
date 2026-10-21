"""Utilidades para RUN/RUT chileno (módulo 11)."""
import re

from django.core.exceptions import ValidationError


def limpiar(valor):
    """'12.345.678-k' -> ('12345678', 'K'). Devuelve (None, None) si no tiene forma de RUN."""
    if not valor:
        return None, None
    v = re.sub(r"[^0-9kK]", "", str(valor)).upper()
    if len(v) < 2:
        return None, None
    return v[:-1].lstrip("0"), v[-1]


def calcular_dv(cuerpo):
    suma, factor = 0, 2
    for d in reversed(str(cuerpo)):
        suma += int(d) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - (suma % 11)
    return {11: "0", 10: "K"}.get(resto, str(resto))


def es_valido(valor):
    cuerpo, dv = limpiar(valor)
    return bool(cuerpo) and cuerpo.isdigit() and 6 <= len(cuerpo) <= 8 and calcular_dv(cuerpo) == dv


def validar(valor):
    if not es_valido(valor):
        raise ValidationError("El RUN no es válido. Revisa los números y el dígito verificador.")
    return limpiar(valor)


def formatear(cuerpo, dv=None):
    if not cuerpo:
        return ""
    if dv is None:
        dv = calcular_dv(cuerpo)
    return f"{int(cuerpo):,}".replace(",", ".") + f"-{dv}"
