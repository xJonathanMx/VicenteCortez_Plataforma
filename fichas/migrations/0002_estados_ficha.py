from django.db import migrations

ESTADOS = [("abierta", "Abierta", 1), ("en_atencion", "En atención", 2), ("cerrada", "Cerrada", 3),
           ("validada", "Validada", 4), ("anulada", "Anulada", 5)]


def crear(apps, schema_editor):
    EstadoFicha = apps.get_model("fichas", "EstadoFicha")
    for codigo, nombre, orden in ESTADOS:
        EstadoFicha.objects.update_or_create(codigo=codigo, defaults={"nombre": nombre, "orden": orden})


class Migration(migrations.Migration):
    dependencies = [("fichas", "0001_initial")]
    operations = [migrations.RunPython(crear, migrations.RunPython.noop)]
