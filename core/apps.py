from django.apps import AppConfig, apps


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Núcleo"

    def ready(self):
        from django.contrib.auth.signals import user_logged_in, user_login_failed

        from . import senales

        user_logged_in.connect(senales.acceso_exitoso)
        user_login_failed.connect(senales.acceso_fallido)
        documentar_columnas()


def documentar_columnas():
    """
    RNF Documentación-01: copia el nombre legible y la ayuda de cada campo como
    comentario de la columna en la base de datos (COMMENT ON COLUMN en Postgres).
    Así el diccionario de datos vive también dentro de Supabase.
    """
    propias = {"core", "clientes", "catalogo", "fichas", "seguimiento", "metas", "beneficios"}
    for modelo in apps.get_models():
        if modelo._meta.app_label not in propias:
            continue
        if not modelo._meta.db_table_comment:
            doc = (modelo.__doc__ or "").strip()
            if not doc or doc.startswith(modelo.__name__ + "("):
                doc = str(modelo._meta.verbose_name).capitalize()
            modelo._meta.db_table_comment = doc.split("\n")[0][:250]
            modelo._meta.original_attrs["db_table_comment"] = modelo._meta.db_table_comment
        for campo in modelo._meta.local_fields:
            if not getattr(campo, "db_comment", None):
                texto = str(campo.verbose_name).capitalize()
                if campo.help_text:
                    texto += f". {campo.help_text}"
                campo.db_comment = texto[:250]
