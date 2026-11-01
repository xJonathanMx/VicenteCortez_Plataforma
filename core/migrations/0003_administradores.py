from django.contrib.auth.hashers import make_password
from django.db import migrations

# Administradores que deben existir siempre. Datos provisorios ("1"): se reemplazan
# desde la pantalla de usuarios. Se crean sin contraseña; cada uno la define con
#     python manage.py changepassword <RUN sin dv>
ADMINISTRADORES = [
    # (RUN, dv, nombre)
    ("1111111", "4", "Vicente"),
    ("2222222", "8", "Violeta"),
]


def crear_administradores(apps, schema_editor):
    """Crea a los administradores si faltan. Si ya existen, no los toca."""
    Usuario = apps.get_model("core", "Usuario")
    Rol = apps.get_model("core", "Rol")
    admin = Rol.objects.get(codigo="administrador")
    for run, dv, nombre in ADMINISTRADORES:
        u, nuevo = Usuario.objects.get_or_create(run=run, defaults={
            "dv": dv, "nombre": nombre, "ap_paterno": "1", "correo": "1@1.cl", "telefono": "1", "genero": "N",
            "is_staff": True, "is_superuser": True, "password": make_password(None)})
        if nuevo:
            u.roles.add(admin)


class Migration(migrations.Migration):
    dependencies = [("core", "0002_roles_base")]

    operations = [migrations.RunPython(crear_administradores, migrations.RunPython.noop)]
