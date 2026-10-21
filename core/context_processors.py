import os

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]

# (texto, nombre de url, ícono lucide, privilegio requerido o None, prefijo de ruta activa)
MENU_PRINCIPAL = [
    ("Inicio", "inicio", "house", None, "/inicio"),
    ("Crear ficha", "fichas:nueva", "user-plus", "abrir_fichas", "/fichas/nueva"),
    ("Buscar cliente", "clientes:buscar", "search", None, "/clientes"),
    ("Historial de atenciones", "fichas:lista", "history", None, "/fichas/"),
    ("Mis metas y comisiones", "metas:mias", "target", None, "/metas/mias"),
]
MENU_ADMIN = [
    ("Usuarios", "core:usuarios", "users", "gestionar_usuarios", "/usuarios"),
    ("Servicios e insumos", "catalogo:servicios", "scissors", "gestionar_catalogo", "/catalogo"),
    ("Valoraciones", "seguimiento:valoraciones", "star", "ver_valoraciones", "/seguimiento"),
    ("Metas", "metas:panel", "trophy", "gestionar_metas", "/metas/panel"),
    ("Giftcards y promociones", "beneficios:inicio", "gift", "gestionar_beneficios", "/beneficios"),
    ("Reportes", "reportes:inicio", "chart-column", "ver_reportes", "/reportes"),
]


def fecha_larga(fecha):
    return f"{DIAS[fecha.weekday()]}, {fecha.day} de {MESES[fecha.month - 1]}"


def _items(usuario, menu, ruta):
    salida = []
    for texto, url, icono, priv, prefijo in menu:
        if priv and not usuario.tiene_privilegio(priv):
            continue
        salida.append({"texto": texto, "url": reverse(url), "icono": icono, "prefijo": prefijo, "activo": False})
    return salida


def _marcar_activo(items, ruta):
    """Marca solo la opción más específica: /fichas/nueva/ es «Crear ficha», no también «Historial»."""
    coinciden = [i for i in items if ruta.startswith(i["prefijo"])]
    if coinciden:
        max(coinciden, key=lambda i: len(i["prefijo"]))["activo"] = True


def version_estaticos():
    """Cambia cuando cambian app.css o app.js, para que el navegador no use una copia vieja."""
    marcas = []
    for archivo in ("css/app.css", "js/app.js"):
        try:
            marcas.append(int(os.path.getmtime(settings.BASE_DIR / "static" / archivo)))
        except OSError:
            pass
    return max(marcas, default=0)


def navegacion(request):
    hoy = timezone.localdate()
    ctx = {"fecha_hoy": fecha_larga(hoy), "v": version_estaticos()}
    if request.user.is_authenticated:
        ruta = request.path
        ctx["menu_principal"] = _items(request.user, MENU_PRINCIPAL, ruta)
        ctx["menu_admin"] = _items(request.user, MENU_ADMIN, ruta)
        _marcar_activo(ctx["menu_principal"] + ctx["menu_admin"], ruta)
        ctx["ajustes_activo"] = ruta.startswith("/ajustes")
    return ctx
