from django.db import migrations

# Copia fija de core/permisos.py al momento de crear la migración: así la historia
# no cambia si mañana se edita ese archivo. Un privilegio nuevo va en otra migración.
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


def crear_roles_base(apps, schema_editor):
    """Crea privilegios y roles si faltan. Si ya existen (BD con datos), no los toca."""
    Privilegio = apps.get_model("core", "Privilegio")
    Rol = apps.get_model("core", "Rol")
    for codigo, nombre in PRIVILEGIOS.items():
        Privilegio.objects.get_or_create(codigo=codigo, defaults={"nombre": nombre})
    for codigo, (nombre, privs) in ROLES_BASE.items():
        rol, nuevo = Rol.objects.get_or_create(codigo=codigo, defaults={"nombre": nombre})
        if nuevo:
            rol.privilegios.set(Privilegio.objects.filter(codigo__in=privs))


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]

    operations = [migrations.RunPython(crear_roles_base, migrations.RunPython.noop)]
