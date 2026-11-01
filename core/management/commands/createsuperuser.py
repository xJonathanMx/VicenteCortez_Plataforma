from django.contrib.auth.management.commands import createsuperuser
from django.core.exceptions import ValidationError

from core import rut


class Command(createsuperuser.Command):
    """createsuperuser de Django, pero el RUN se escribe completo (12.345.678-5)."""

    def get_input_data(self, field, message, default=None):
        if field is not self.username_field:
            return super().get_input_data(field, message, default)
        return input(message.replace("RUN", "RUN (ej. 12.345.678-5)", 1)).strip() or None

    def _validate_username(self, username, verbose_field_name, database):
        try:
            cuerpo, _ = rut.validar(username)
        except ValidationError as e:
            return "; ".join(e.messages)
        if self.UserModel._default_manager.db_manager(database).filter(run=cuerpo).exists():
            return "Error: ya existe un usuario con ese RUN."
