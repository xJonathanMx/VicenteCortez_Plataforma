"""
Control de acceso por privilegios, validado en el servidor en cada acción
(RNF Seguridad-03). Ocultar botones en la interfaz es solo comodidad.
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

PRIVILEGIOS = {
    "gestionar_usuarios": "Gestionar usuarios y peluqueros",
    "gestionar_roles": "Gestionar roles y privilegios",
    "gestionar_catalogo": "Gestionar servicios, tipos e insumos",
    "editar_precios": "Editar precios y comisiones",
    "gestionar_clientes": "Editar y deshabilitar clientes",
    "ver_todos_clientes": "Ver todos los clientes",
    "abrir_fichas": "Abrir fichas de atención",
    "asignar_peluquero": "Asignar peluquero a un servicio",
    "validar_fichas": "Validar, anular y corregir fichas",
    "cerrar_servicios": "Cerrar servicios abiertos de otros",
    "ver_valoraciones": "Ver valoraciones de todos",
    "gestionar_metas": "Definir metas y cerrar el mes",
    "ver_comisiones": "Ver comisiones de todos",
    "gestionar_beneficios": "Registrar y usar giftcards y promociones",
    "ver_reportes": "Ver y exportar reportes",
    "configurar_canales": "Configurar canales y plantillas",
}

ROLES_BASE = {
    "administrador": ("Administrador", list(PRIVILEGIOS)),
    "recepcion": ("Recepción", ["ver_todos_clientes", "abrir_fichas", "asignar_peluquero", "gestionar_clientes"]),
    "peluquero": ("Peluquero", ["abrir_fichas"]),
}


def privilegio_requerido(*codigos):
    """Permite la vista si el usuario tiene al menos uno de los privilegios indicados."""
    def decorador(vista):
        @login_required
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not any(request.user.tiene_privilegio(c) for c in codigos):
                raise PermissionDenied("No tienes permiso para esta acción.")
            return vista(request, *args, **kwargs)
        return envoltura
    return decorador


def exigir(usuario, codigo):
    if not usuario.tiene_privilegio(codigo):
        raise PermissionDenied("No tienes permiso para esta acción.")
