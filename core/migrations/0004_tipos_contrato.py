from django.db import migrations

TIPOS_CONTRATO = {"Interno": False, "Externo": True}  # nombre: aplica comisión
ADMINISTRADORES = ["1111111", "2222222"]  # Vicente y Violeta (0003)


def crear_tipos_contrato(apps, schema_editor):
    """Crea Interno y Externo si faltan, y deja a los administradores sin contrato como Interno."""
    TipoContrato = apps.get_model("core", "TipoContrato")
    Usuario = apps.get_model("core", "Usuario")
    for nombre, aplica in TIPOS_CONTRATO.items():
        TipoContrato.objects.get_or_create(nombre=nombre, defaults={"aplica_comision": aplica})
    interno = TipoContrato.objects.get(nombre="Interno")
    Usuario.objects.filter(run__in=ADMINISTRADORES, contrato__isnull=True).update(contrato=interno)


class Migration(migrations.Migration):
    dependencies = [("core", "0003_administradores")]

    operations = [migrations.RunPython(crear_tipos_contrato, migrations.RunPython.noop)]
