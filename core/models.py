"""
Usuarios, roles, privilegios y catálogos base.

Nombres de tablas según el modelo relacional V3.1 (USUARIO, ROL, PRIVILEGIO...).
Ningún registro se elimina físicamente (RNF Integridad-01): se desactiva y el
cambio queda en un histórico con motivo, fecha y responsable.
"""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone

from . import rut as rututil

GENEROS = [("F", "Femenino"), ("M", "Masculino"), ("O", "Otro"), ("N", "Prefiere no decir")]


class SoloInsercion(models.Model):
    """Registros históricos: se crean y nunca se editan ni borran (RNF Integridad-02)."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValueError("Los registros históricos no se pueden modificar.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Los registros históricos no se pueden eliminar.")


class TipoContrato(models.Model):
    nombre = models.CharField("nombre del contrato", max_length=30, unique=True, db_column="nom_contrato")
    aplica_comision = models.BooleanField("aplica comisión", default=False,
                                          help_text="Solo los contratos externos reciben comisión (RF-CI-05).")

    class Meta:
        db_table = "tipo_contrato"
        verbose_name = "tipo de contrato"
        verbose_name_plural = "tipos de contrato"

    def __str__(self):
        return self.nombre


class Especialidad(models.Model):
    nombre = models.CharField("nombre de la especialidad", max_length=60, unique=True, db_column="nombre_esp")
    activo = models.BooleanField("activa", default=True)

    class Meta:
        db_table = "especialidad"
        verbose_name_plural = "especialidades"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Privilegio(models.Model):
    codigo = models.SlugField("código", max_length=40, unique=True,
                              help_text="Identificador que usa el sistema para validar permisos.")
    nombre = models.CharField("nombre del privilegio", max_length=80, db_column="nombre_privilegio")

    class Meta:
        db_table = "privilegio"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Rol(models.Model):
    nombre = models.CharField("nombre del rol", max_length=40, unique=True, db_column="nombre_rol")
    codigo = models.SlugField("código", max_length=40, unique=True)
    privilegios = models.ManyToManyField(Privilegio, blank=True, db_table="rol_privilegio",
                                         verbose_name="privilegios")

    class Meta:
        db_table = "rol"
        verbose_name_plural = "roles"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class TipoEstado(models.Model):
    nombre = models.CharField("nombre del estado", max_length=30, unique=True, db_column="nombre_estado")

    class Meta:
        db_table = "tipo_estado"

    def __str__(self):
        return self.nombre

    @classmethod
    def de(cls, activo):
        return cls.objects.get_or_create(nombre="Activo" if activo else "Inactivo")[0]


class NivelHabilidad(models.Model):
    nombre = models.CharField("nombre del nivel", max_length=40, unique=True, db_column="nombre_nivel")
    descripcion = models.CharField("descripción", max_length=200, blank=True, db_column="descripcion_nivel")
    activo = models.BooleanField("activo", default=True, db_column="es_activo")

    class Meta:
        db_table = "nivel_habilidad"
        verbose_name = "nivel de habilidad"
        verbose_name_plural = "niveles de habilidad"

    def __str__(self):
        return self.nombre


class UsuarioManager(BaseUserManager):
    def create_user(self, run, password=None, **extra):
        cuerpo, dv = rututil.validar(run)
        extra.pop("dv", None)
        user = self.model(run=cuerpo, dv=dv, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, run, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        user = self.create_user(run, password, **extra)
        admin = Rol.objects.filter(codigo="administrador").first()
        if admin:
            user.roles.add(admin)
        return user


class Usuario(AbstractBaseUser):
    run = models.CharField("RUN", max_length=8, primary_key=True, db_column="run_usuario",
                           help_text="RUN sin puntos ni dígito verificador.")
    dv = models.CharField("dígito verificador", max_length=1)
    nombre = models.CharField("nombre", max_length=60)
    ap_paterno = models.CharField("apellido paterno", max_length=60)
    ap_materno = models.CharField("apellido materno", max_length=60, blank=True)
    correo = models.EmailField("correo", max_length=120)
    telefono = models.CharField("teléfono", max_length=15)
    genero = models.CharField("género", max_length=1, choices=GENEROS)
    contrato = models.ForeignKey(TipoContrato, on_delete=models.PROTECT, null=True, blank=True,
                                 db_column="id_contrato", verbose_name="tipo de contrato")
    roles = models.ManyToManyField(Rol, blank=True, db_table="usuario_rol", verbose_name="roles")
    especialidades = models.ManyToManyField(Especialidad, through="UsuarioEspecialidad", blank=True)
    is_active = models.BooleanField("activo", default=True, db_column="u_activo")
    is_staff = models.BooleanField("acceso al admin de Django", default=False)
    is_superuser = models.BooleanField("superusuario", default=False)
    creado_en = models.DateTimeField("creado en", auto_now_add=True)
    password = models.CharField("contraseña (hash)", max_length=250, db_column="contrasena_hash")

    objects = UsuarioManager()
    USERNAME_FIELD = "run"
    EMAIL_FIELD = "correo"
    REQUIRED_FIELDS = ["nombre", "ap_paterno", "correo", "telefono", "genero"]

    class Meta:
        db_table = "usuario"
        ordering = ["nombre", "ap_paterno"]

    def __str__(self):
        return self.nombre_corto

    @property
    def nombre_completo(self):
        return " ".join(p for p in [self.nombre, self.ap_paterno, self.ap_materno] if p)

    @property
    def nombre_corto(self):
        return f"{self.nombre} {self.ap_paterno}"

    @property
    def run_formateado(self):
        return rututil.formatear(self.run, self.dv)

    @property
    def inicial(self):
        return (self.nombre or "?")[0].upper()

    # --- Roles y privilegios (RF-AS-06, RF-AS-07) ---
    def codigos_roles(self):
        if not hasattr(self, "_roles_cache"):
            self._roles_cache = set(self.roles.values_list("codigo", flat=True))
        return self._roles_cache

    def privilegios(self):
        if not hasattr(self, "_priv_cache"):
            if self.is_superuser:
                self._priv_cache = set(Privilegio.objects.values_list("codigo", flat=True))
            else:
                self._priv_cache = set(
                    Privilegio.objects.filter(rol__usuario=self).values_list("codigo", flat=True))
        return self._priv_cache

    def tiene_privilegio(self, codigo):
        return self.is_active and (self.is_superuser or codigo in self.privilegios())

    @property
    def es_admin(self):
        return self.is_superuser or "administrador" in self.codigos_roles()

    @property
    def es_peluquero(self):
        return "peluquero" in self.codigos_roles()

    @property
    def ve_todos_los_clientes(self):
        """RF-AS-02: un peluquero solo ve sus clientes; recepción y administración ven todos."""
        return self.tiene_privilegio("ver_todos_clientes")

    @property
    def descripcion_roles(self):
        return ", ".join(self.roles.values_list("nombre", flat=True)) or "Sin rol"

    # Compatibilidad con el admin de Django.
    def has_perm(self, perm, obj=None):
        return self.is_active and self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_active and self.is_superuser

    @property
    def cobra_comision(self):
        return bool(self.contrato and self.contrato.aplica_comision)


class UsuarioEspecialidad(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, db_column="run_usuario")
    especialidad = models.ForeignKey(Especialidad, on_delete=models.PROTECT, db_column="id_especialidad")
    es_principal = models.BooleanField("es principal", default=False)

    class Meta:
        db_table = "usuario_especialidad"
        unique_together = [("usuario", "especialidad")]


class HistoricoEstadoUsuario(SoloInsercion):
    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="historial_estados",
                                db_column="run_usuario")
    tipo_estado = models.ForeignKey(TipoEstado, on_delete=models.PROTECT, db_column="id_tipo_estado")
    motivo = models.CharField("motivo", max_length=255)
    fecha_cambio = models.DateTimeField("fecha del cambio", default=timezone.now)
    responsable = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="+", null=True,
                                    verbose_name="administrador responsable")

    class Meta:
        db_table = "historico_estado_usuario"
        ordering = ["-fecha_cambio"]


class RegistroAcceso(SoloInsercion):
    """Intentos de inicio de sesión, para el reporte de accesos (RF-RP-13)."""
    run_ingresado = models.CharField("RUN ingresado", max_length=20)
    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, null=True, blank=True)
    exitoso = models.BooleanField("exitoso")
    fecha = models.DateTimeField("fecha", default=timezone.now)
    ip = models.GenericIPAddressField("IP", null=True, blank=True)

    class Meta:
        db_table = "registro_acceso"
        ordering = ["-fecha"]


class Auditado(models.Model):
    """Quién y cuándo creó o modificó el registro (RNF Integridad-03)."""
    creado_en = models.DateTimeField("creado en", auto_now_add=True)
    modificado_en = models.DateTimeField("modificado en", auto_now=True)
    creado_por = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="+", null=True, blank=True,
                                   verbose_name="creado por")
    modificado_por = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="+", null=True,
                                       blank=True, verbose_name="modificado por")

    class Meta:
        abstract = True
