"""
Modelos de la Plataforma Vicente Cortez — todos en un solo archivo.

Toda la base de datos (Supabase/Postgres) queda definida aquí, ordenada por
secciones. Los nombres de las tablas (db_table) no cambian respecto a la
versión anterior, así que la base de datos existente sigue funcionando igual.

Nombres de tablas según el modelo relacional V3.1 (USUARIO, ROL, PRIVILEGIO...).
Ningún registro se elimina físicamente (RNF Integridad-01): se desactiva y el
cambio queda en un histórico con motivo, fecha y responsable.

Secciones:
    1. USUARIOS, ROLES, PRIVILEGIOS Y CATÁLOGOS BASE
    2. CLIENTES
    3. CATÁLOGO: SERVICIOS, COMISIONES E INSUMOS
    4. FICHAS DE ATENCIÓN
    5. SEGUIMIENTO: VALORACIONES, RECORDATORIOS Y ENVÍOS
    6. METAS E INCENTIVOS
    7. BENEFICIOS: GIFTCARDS Y PROMOCIONES
"""
import secrets

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone

from . import rut as rututil


# ============================================================================
# 1. USUARIOS, ROLES, PRIVILEGIOS Y CATÁLOGOS BASE
# ============================================================================

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


# ============================================================================
# 2. CLIENTES
# ============================================================================

CANALES = [("whatsapp", "WhatsApp"), ("email", "Correo electrónico")]


class ClienteQuerySet(models.QuerySet):
    def visibles_para(self, usuario):
        """RF-AS-02: el peluquero accede solo a la información de sus propios clientes."""
        if usuario.ve_todos_los_clientes:
            return self
        return self.filter(
            models.Q(estilista_fijo=usuario) | models.Q(fichas__servicios__peluquero=usuario)
            | models.Q(creado_por=usuario) | models.Q(fichas__abierta_por=usuario)
        ).distinct()


class Cliente(models.Model):
    run = models.CharField("RUN", max_length=8, primary_key=True, db_column="run_cliente")
    dv = models.CharField("dígito verificador", max_length=1)
    nombre = models.CharField("nombres", max_length=60)
    ap_paterno = models.CharField("apellido paterno", max_length=60)
    ap_materno = models.CharField("apellido materno", max_length=60, blank=True)
    telefono = models.CharField("teléfono", max_length=15, blank=True)
    correo = models.EmailField("correo", max_length=120, blank=True)
    fecha_nac = models.DateField("fecha de nacimiento", null=True, blank=True)
    genero = models.CharField("género", max_length=1, choices=GENEROS, blank=True)
    canal_preferido = models.CharField("canal de contacto", max_length=10, choices=CANALES, default="email")
    estilista_fijo = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="clientes_fijos", verbose_name="estilista fijo")
    activo = models.BooleanField("activo", default=True, db_column="c_activo")
    creado_en = models.DateTimeField("registrado en", auto_now_add=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True,
                                   related_name="+", verbose_name="registrado por")

    objects = ClienteQuerySet.as_manager()

    class Meta:
        db_table = "cliente"
        ordering = ["nombre", "ap_paterno"]

    def __str__(self):
        return self.nombre_completo

    @property
    def nombre_completo(self):
        return " ".join(p for p in [self.nombre, self.ap_paterno, self.ap_materno] if p)

    @property
    def run_formateado(self):
        return rututil.formatear(self.run, self.dv)

    @property
    def inicial(self):
        return (self.nombre or "?")[0].upper()

    @property
    def datos_completos(self):
        """Tiene cómo recibir valoraciones y recordatorios con los canales habilitados."""
        if "whatsapp" in settings.CANALES_ENVIO:
            return bool(self.telefono or self.correo)
        return bool(self.correo)

    def resumen(self):
        """RF-C-06: última visita, cantidad de visitas y estilista fijo."""
        fichas = self.fichas.exclude(estado="anulada")
        ultima = fichas.order_by("-fecha_hora_inicio").first()
        return {
            "visitas": fichas.count(),
            "ultima_visita": ultima.fecha_hora_inicio if ultima else None,
            "estilista_fijo": self.estilista_fijo,
        }


class HistoricoEstadoCliente(SoloInsercion):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="historial_estados",
                                db_column="run_cliente")
    tipo_estado = models.ForeignKey(TipoEstado, on_delete=models.PROTECT, db_column="id_tipo_estado")
    observacion = models.CharField("motivo", max_length=255)
    fecha_cambio = models.DateTimeField("fecha del cambio", default=timezone.now)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True,
                                    related_name="+")

    class Meta:
        db_table = "historico_estado_cliente"
        ordering = ["-fecha_cambio"]


class ConsultaHistorial(SoloInsercion):
    """Cada vez que un usuario abre el historial de un cliente (RF-RP-12)."""
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="+")
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "consulta_historial"


# ============================================================================
# 3. CATÁLOGO: SERVICIOS, COMISIONES E INSUMOS
#    Catálogo de servicios, comisiones, insumos e históricos de precio/comisión/estado.
# ============================================================================

VARIANTES = [("basico", "Básico"), ("plus", "Plus"), ("ultra_plus", "Ultra plus")]

SEGUIMIENTO = [
    ("corte", "Corte: 1 valoración al día siguiente"),
    ("tratamiento", "Tratamiento: valoración al día siguiente y a fin de mes"),
    ("ninguno", "Sin valoración"),
]


class TipoServicio(models.Model):
    nombre = models.CharField("nombre", max_length=60, unique=True, db_column="nombre_servicio")
    descripcion = models.CharField("descripción", max_length=255, blank=True)
    seguimiento = models.CharField("regla de valoración", max_length=12, choices=SEGUIMIENTO, default="corte",
                                   help_text="Define cuántas valoraciones se programan (RF-VS-02 a 04).")
    activo = models.BooleanField("activo", default=True, db_column="estado_tipo_servicio")

    class Meta:
        db_table = "tipo_servicio"
        verbose_name = "tipo de servicio"
        verbose_name_plural = "tipos de servicio"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def porcentaje_para(self, contrato):
        if not contrato:
            return 0
        c = self.comisiones.filter(contrato=contrato).first()
        return c.porcentaje if c else 0


class Comision(models.Model):
    """Porcentaje de comisión vigente por tipo de servicio y tipo de contrato."""
    tipo_servicio = models.ForeignKey(TipoServicio, on_delete=models.PROTECT, related_name="comisiones",
                                      db_column="id_tipo_servicio")
    contrato = models.ForeignKey(TipoContrato, on_delete=models.PROTECT, db_column="id_contrato")
    porcentaje = models.DecimalField("porcentaje", max_digits=5, decimal_places=2)

    class Meta:
        db_table = "comision"
        unique_together = [("tipo_servicio", "contrato")]


class HistoricoComisionServicio(SoloInsercion):
    tipo_servicio = models.ForeignKey(TipoServicio, on_delete=models.PROTECT, related_name="historial_comisiones",
                                      db_column="id_tipo_servicio")
    contrato = models.ForeignKey(TipoContrato, on_delete=models.PROTECT, db_column="tipo_contrato")
    porcentaje_anterior = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    porcentaje_nuevo = models.DecimalField(max_digits=5, decimal_places=2)
    fecha_cambio = models.DateTimeField(default=timezone.now)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")

    class Meta:
        db_table = "historico_comision_servicio"
        ordering = ["-fecha_cambio"]


class Servicio(models.Model):
    tipo = models.ForeignKey(TipoServicio, on_delete=models.PROTECT, related_name="servicios",
                             db_column="id_tipo_servicio", verbose_name="tipo de servicio")
    nombre = models.CharField("nombre", max_length=80)
    precio = models.PositiveIntegerField("precio básico")
    precio_plus = models.PositiveIntegerField("precio plus", null=True, blank=True)
    precio_ultra_plus = models.PositiveIntegerField("precio ultra plus", null=True, blank=True)
    tiempo_estimado = models.PositiveIntegerField("tiempo estimado (minutos)", default=60)
    descripcion = models.TextField("descripción", blank=True, db_column="descripcion_servicio")
    observacion = models.CharField("observación", max_length=255, blank=True)
    costo_estimado = models.PositiveIntegerField("costo estimado", null=True, blank=True)
    dia_renovacion = models.PositiveIntegerField(
        "días para renovación", null=True, blank=True,
        help_text="Si se indica, se programa un recordatorio de renovación (ej. tinturas).")
    especialidades = models.ManyToManyField(Especialidad, blank=True, db_table="servicio_especialidad",
                                            verbose_name="especialidades requeridas")
    activo = models.BooleanField("activo", default=True, db_column="estado_actual_servicio")

    class Meta:
        db_table = "servicio"
        ordering = ["tipo__nombre", "nombre"]
        unique_together = [("tipo", "nombre")]

    def __str__(self):
        return f"{self.nombre} ({self.tipo.nombre})"

    def precio_de(self, variante):
        return {"plus": self.precio_plus, "ultra_plus": self.precio_ultra_plus}.get(variante) or self.precio


class HistoricoPrecioServicio(SoloInsercion):
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, related_name="historial_precios",
                                 db_column="id_servicio")
    variante = models.CharField(max_length=12, choices=VARIANTES, default="basico")
    precio_anterior = models.PositiveIntegerField(null=True)
    precio_nuevo = models.PositiveIntegerField(null=True)
    fecha_cambio = models.DateTimeField(default=timezone.now)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")

    class Meta:
        db_table = "historico_precio_servicio"
        ordering = ["-fecha_cambio"]


class HistoricoEstadoServicio(SoloInsercion):
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, related_name="historial_estados",
                                 db_column="id_servicio")
    tipo_estado = models.ForeignKey(TipoEstado, on_delete=models.PROTECT, db_column="id_tipo_estado")
    motivo = models.CharField(max_length=255, blank=True)
    fecha_cambio = models.DateTimeField(default=timezone.now)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")

    class Meta:
        db_table = "historico_estado_servicio"
        ordering = ["-fecha_cambio"]


class UsuarioServicio(models.Model):
    """Servicios que cada peluquero tiene habilitados y su nivel (RF-FA-04)."""
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="servicios_habilitados", db_column="run_usuario")
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, related_name="habilitados",
                                 db_column="id_servicio")
    nivel = models.ForeignKey(NivelHabilidad, on_delete=models.PROTECT, null=True, blank=True,
                              db_column="id_nivel_hab", verbose_name="nivel de habilidad")
    activo = models.BooleanField("habilitado", default=True, db_column="es_activo")

    class Meta:
        db_table = "usuario_servicio"
        unique_together = [("usuario", "servicio")]


class Insumo(models.Model):
    nombre = models.CharField("nombre", max_length=80, db_column="nombre_insumo")
    marca = models.CharField("marca", max_length=60)
    calidad = models.CharField("calidad", max_length=40)
    unidad_medida = models.CharField("unidad de medida", max_length=20, default="ml")
    activo = models.BooleanField("activo", default=True, db_column="estado")

    class Meta:
        db_table = "insumo"
        ordering = ["nombre", "marca"]
        constraints = [models.UniqueConstraint(fields=["nombre", "marca", "calidad"], name="insumo_unico")]

    def __str__(self):
        return f"{self.nombre}, {self.marca} ({self.calidad})"


# ============================================================================
# 4. FICHAS DE ATENCIÓN
#    Fichas de atención, servicios realizados, insumos usados y trazabilidad.
# ============================================================================

ESTADOS_SERVICIO = [("pendiente", "Pendiente"), ("en_proceso", "En proceso"), ("terminado", "Terminado")]


class EstadoFicha(models.Model):
    codigo = models.SlugField("código", max_length=20, primary_key=True, db_column="id_estado_ficha")
    nombre = models.CharField("nombre", max_length=30)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "estado_ficha"
        ordering = ["orden"]

    def __str__(self):
        return self.nombre


class FichaAtencion(Auditado):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, null=True, blank=True, related_name="fichas",
                                db_column="run_cliente", help_text="Puede quedar vacío y vincularse después (RF-FA-02).")
    abierta_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="fichas_abiertas",
                                    db_column="run_usuario", verbose_name="abierta por")
    nombre_provisorio = models.CharField("nombre provisorio del cliente", max_length=80, blank=True)
    fecha_hora_inicio = models.DateTimeField("inicio", default=timezone.now)
    fecha_hora_termino = models.DateTimeField("término", null=True, blank=True)
    diagnostico = models.TextField("diagnóstico inicial", blank=True)
    observaciones = models.TextField("observaciones", blank=True)
    estado = models.ForeignKey(EstadoFicha, on_delete=models.PROTECT, default="abierta", db_column="id_estado_ficha")
    validada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                     related_name="+")
    fecha_validacion = models.DateTimeField(null=True, blank=True)
    motivo_anulacion = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "ficha_atencion"
        ordering = ["-fecha_hora_inicio"]
        verbose_name = "ficha de atención"
        verbose_name_plural = "fichas de atención"

    def __str__(self):
        return f"Ficha N° {self.pk}"

    @property
    def nombre_cliente(self):
        return self.cliente.nombre_completo if self.cliente else (self.nombre_provisorio or "Cliente sin identificar")

    @property
    def total(self):
        return sum(s.precio_cobrado for s in self.servicios.all())

    @property
    def todos_terminados(self):
        servicios = list(self.servicios.all())
        return bool(servicios) and all(s.estado == "terminado" for s in servicios)

    @property
    def editable(self):
        return self.estado_id in ("abierta", "en_atencion")

    @property
    def peluqueros(self):
        return {s.peluquero for s in self.servicios.all()}

    @property
    def datos_completos(self):
        """RF-RP-11: cliente, peluquero, servicio, fecha y hora."""
        return bool(self.cliente_id and self.servicios.exists() and self.fecha_hora_inicio)


class DetalleAtencionServicio(Auditado):
    ficha = models.ForeignKey(FichaAtencion, on_delete=models.PROTECT, related_name="servicios", db_column="id_ficha")
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, related_name="atenciones", db_column="id_servicio")
    peluquero = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="atenciones",
                                  db_column="run_u_realiza_servicio")
    variante = models.CharField("calidad", max_length=12, choices=VARIANTES, default="basico")
    # Valores congelados al momento del registro (RF-FA-11, RF-CI-04).
    precio_cobrado = models.PositiveIntegerField("precio cobrado")
    porc_comision_guardado = models.DecimalField("comisión (%)", max_digits=5, decimal_places=2, default=0)
    aplica_comision = models.BooleanField("aplica comisión", default=False)
    estado = models.CharField("estado", max_length=12, choices=ESTADOS_SERVICIO, default="pendiente",
                              db_column="estado_atencion")
    hora_inicio = models.DateTimeField("hora de inicio", null=True, blank=True, db_column="hora_inicio_servicio")
    hora_termino = models.DateTimeField("hora de término", null=True, blank=True, db_column="hora_termino_servicio")
    cierre_manual = models.BooleanField(default=False)
    motivo_cierre = models.CharField("motivo de cierre manual", max_length=255, blank=True)
    formula = models.TextField("mezcla o fórmula", blank=True)
    observacion_producto = models.TextField("producto usado (observación)", blank=True)
    sesion_numero = models.PositiveSmallIntegerField("sesión", default=1)
    sesiones_totales = models.PositiveSmallIntegerField("sesiones totales", default=1)
    tratamiento_origen = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True,
                                           related_name="sesiones_siguientes",
                                           help_text="Primera sesión de un tratamiento multisesión (RF-FA-10).")

    class Meta:
        db_table = "detalle_atencion_servicio"
        ordering = ["id"]

    def __str__(self):
        return f"{self.servicio.nombre} ({self.get_variante_display()})"

    @property
    def monto_comision(self):
        """RF-CI-06: precio guardado × porcentaje guardado, solo para externos."""
        if not self.aplica_comision:
            return 0
        return round(self.precio_cobrado * float(self.porc_comision_guardado) / 100)

    @property
    def duracion_min(self):
        if self.hora_inicio and self.hora_termino:
            return int((self.hora_termino - self.hora_inicio).total_seconds() // 60)
        if self.hora_inicio:
            return int((timezone.now() - self.hora_inicio).total_seconds() // 60)
        return None

    @property
    def excedido(self):
        """RF-ES-06: abierto por más tiempo del estimado."""
        return self.estado == "en_proceso" and (self.duracion_min or 0) > self.servicio.tiempo_estimado

    @property
    def es_multisesion(self):
        return self.sesiones_totales > 1


class DetalleFichaInsumo(models.Model):
    detalle = models.ForeignKey(DetalleAtencionServicio, on_delete=models.CASCADE, related_name="insumos",
                                db_column="id_detalle_aten_s")
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name="usos", db_column="id_insumo")
    cant_usada = models.DecimalField("cantidad usada", max_digits=8, decimal_places=2, null=True, blank=True)
    observacion = models.CharField("observación", max_length=255, blank=True)

    class Meta:
        db_table = "detalle_ficha_insumo"


class HistorialEstadoFicha(SoloInsercion):
    ficha = models.ForeignKey(FichaAtencion, on_delete=models.PROTECT, related_name="historial", db_column="id_ficha")
    estado_anterior = models.ForeignKey(EstadoFicha, on_delete=models.PROTECT, null=True, related_name="+")
    estado = models.ForeignKey(EstadoFicha, on_delete=models.PROTECT, related_name="+", db_column="id_estado_ficha")
    fecha_hora_cambio = models.DateTimeField(default=timezone.now)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")
    motivo = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "historial_estado_ficha"
        ordering = ["-fecha_hora_cambio", "-id"]


class VersionFicha(SoloInsercion):
    """Copia de la ficha antes de una corrección o anulación (RF-FA-14)."""
    ficha = models.ForeignKey(FichaAtencion, on_delete=models.PROTECT, related_name="versiones")
    contenido = models.JSONField()
    motivo = models.CharField(max_length=255)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "version_ficha"
        ordering = ["-fecha"]


# ============================================================================
# 5. SEGUIMIENTO: VALORACIONES, RECORDATORIOS Y ENVÍOS
#    Valoraciones de seguimiento, recordatorios programados y canales de envío.
# ============================================================================

TIPOS_MENSAJE = [
    ("valoracion", "Valoración de seguimiento"),
    ("renovacion", "Recordatorio de renovación"),
    ("giftcard", "Giftcard por vencer"),
]


def nuevo_token():
    return secrets.token_urlsafe(24)


class CanalComunicacion(models.Model):
    codigo = models.SlugField(max_length=20, unique=True)
    nombre = models.CharField("nombre del medio", max_length=40, db_column="nombre_medio")
    activo = models.BooleanField("activo", default=True)

    class Meta:
        db_table = "canal_comunicacion"
        verbose_name = "canal de comunicación"
        verbose_name_plural = "canales de comunicación"

    def __str__(self):
        return self.nombre


class Plantilla(models.Model):
    """Texto de cada mensaje. Variables: {nombre}, {servicio}, {peluquero}, {enlace}, {fecha}, {codigo}, {saldo}."""
    tipo = models.CharField("tipo de mensaje", max_length=12, choices=TIPOS_MENSAJE)
    canal = models.ForeignKey(CanalComunicacion, on_delete=models.PROTECT, related_name="plantillas")
    asunto = models.CharField("asunto (solo correo)", max_length=120, blank=True)
    cuerpo = models.TextField("mensaje")

    class Meta:
        db_table = "plantilla_mensaje"
        unique_together = [("tipo", "canal")]

    def __str__(self):
        return f"{self.get_tipo_display()} por {self.canal}"


class Valoracion(models.Model):
    ESTADOS = [("pendiente", "Pendiente"), ("enviada", "Enviada"), ("respondida", "Respondida"),
               ("sin_respuesta", "Sin respuesta"), ("error", "Error de envío")]
    TIPOS = [("dia_siguiente", "Día siguiente"), ("fin_mes", "Fin de mes")]

    ficha = models.ForeignKey(FichaAtencion, on_delete=models.PROTECT, related_name="valoraciones",
                              db_column="id_ficha")
    peluquero = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="valoraciones")
    tipo = models.CharField(max_length=15, choices=TIPOS)
    fecha_programada = models.DateField("fecha programada")
    estado = models.CharField(max_length=15, choices=ESTADOS, default="pendiente", db_column="estado_recibida")
    token = models.CharField(max_length=40, unique=True, default=nuevo_token)
    fecha_envio = models.DateTimeField(null=True, blank=True)
    fecha_respuesta = models.DateTimeField(null=True, blank=True)
    calificacion = models.PositiveSmallIntegerField(null=True, blank=True)
    respuesta = models.CharField("comentario", max_length=255, blank=True)
    intentos = models.PositiveSmallIntegerField(default=0)
    ultimo_error = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "valoracion"
        ordering = ["-fecha_programada"]
        # RF-VS-11 / RF-RC-03: no se duplican valoraciones de una misma ficha.
        constraints = [models.UniqueConstraint(fields=["ficha", "tipo"], name="valoracion_unica_por_ficha")]

    def __str__(self):
        return f"Valoración {self.get_tipo_display().lower()} de la ficha {self.ficha_id}"

    @property
    def enlace(self):
        return f"{settings.SITIO_URL.rstrip('/')}/valorar/{self.token}/"


class Recordatorio(models.Model):
    ESTADOS = [("pendiente", "Pendiente"), ("enviado", "Enviado"), ("fallido", "Fallido"), ("cancelado", "Cancelado")]

    tipo = models.CharField(max_length=12, choices=TIPOS_MENSAJE)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="recordatorios")
    detalle = models.ForeignKey(DetalleAtencionServicio, on_delete=models.PROTECT, null=True, blank=True,
                                related_name="recordatorios", db_column="id_detalle_aten_s")
    giftcard = models.ForeignKey("Giftcard", on_delete=models.PROTECT, null=True, blank=True,
                                 related_name="recordatorios")
    fecha_programada = models.DateField()
    fecha_envio = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default="pendiente", db_column="estado_enviado")
    intentos = models.PositiveSmallIntegerField(default=0)
    ultimo_error = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "recordatorio"
        ordering = ["-fecha_programada"]


class EnvioMensaje(models.Model):
    """Cada intento de envío, exitoso o fallido (RF-RP-08, RNF Confiabilidad-02)."""
    canal = models.ForeignKey(CanalComunicacion, on_delete=models.PROTECT, db_column="id_medio_comunicacion")
    destino = models.CharField(max_length=120)
    valoracion = models.ForeignKey(Valoracion, on_delete=models.PROTECT, null=True, blank=True, related_name="envios")
    recordatorio = models.ForeignKey(Recordatorio, on_delete=models.PROTECT, null=True, blank=True,
                                     related_name="envios")
    exitoso = models.BooleanField()
    simulado = models.BooleanField(default=False)
    error = models.CharField(max_length=255, blank=True)
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "envio_mensaje"
        ordering = ["-fecha"]


class ConfiguracionCorreo(models.Model):
    """Cuenta de correo con que se envían los mensajes. Se edita desde la plataforma (un solo registro)."""
    SEGURIDAD = [("tls", "STARTTLS (puerto 587)"), ("ssl", "SSL (puerto 465)"), ("ninguna", "Sin cifrado")]

    activo = models.BooleanField("enviar correos reales", default=False,
                                 help_text="Apagado: los correos solo se muestran en la consola del servidor.")
    servidor = models.CharField("servidor SMTP", max_length=120, default="smtp.gmail.com")
    puerto = models.PositiveIntegerField("puerto", default=587)
    seguridad = models.CharField("seguridad", max_length=10, choices=SEGURIDAD, default="tls")
    usuario = models.CharField("correo de la cuenta", max_length=120, blank=True)
    clave_cifrada = models.TextField("contraseña (cifrada)", blank=True)
    remitente_nombre = models.CharField("nombre del remitente", max_length=80, default="Peluquería Vicente Cortez")
    responder_a = models.EmailField("responder a", max_length=120, blank=True,
                                    help_text="Si el cliente contesta un correo, la respuesta llega a esta dirección "
                                              "(ej. el @live de la peluquería). Vacío = a la misma cuenta.")
    actualizado_en = models.DateTimeField(auto_now=True)
    actualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                        related_name="+")

    class Meta:
        db_table = "configuracion_correo"
        verbose_name = "configuración de correo"

    @classmethod
    def actual(cls):
        return cls.objects.get_or_create(pk=1)[0]

    @property
    def tiene_clave(self):
        return bool(self.clave_cifrada)

    @property
    def remitente(self):
        return f"{self.remitente_nombre} <{self.usuario}>" if self.usuario else ""

    def fijar_clave(self, clave):
        from core.correo import cifrar
        self.clave_cifrada = cifrar(clave)

    def clave(self):
        from core.correo import descifrar
        return descifrar(self.clave_cifrada)

    @property
    def lista(self):
        """Tiene todo lo necesario para enviar de verdad."""
        return self.activo and bool(self.servidor and self.usuario and self.clave_cifrada)


# ============================================================================
# 6. METAS E INCENTIVOS
#    Metas mensuales e incentivos informativos (no se procesan pagos, RF-CI-14).
# ============================================================================

class NivelIncentivo(models.Model):
    """Escala de incentivo según % de cumplimiento (RF-CI-11)."""
    porcentaje_minimo = models.PositiveSmallIntegerField("cumplimiento mínimo (%)", unique=True)
    porcentaje_pago = models.PositiveSmallIntegerField("% del incentivo base que se informa")

    class Meta:
        db_table = "nivel_incentivo"
        ordering = ["porcentaje_minimo"]

    def __str__(self):
        return f"Desde {self.porcentaje_minimo}%: {self.porcentaje_pago}% del incentivo"


class MetaMensual(models.Model):
    peluquero = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="metas",
                                  db_column="run_usuario")
    mes = models.PositiveSmallIntegerField("mes")
    anio = models.PositiveSmallIntegerField("año")
    meta_cliente = models.PositiveIntegerField("meta de atenciones")
    incentivo_base = models.PositiveIntegerField(
        "incentivo en dinero ($)", default=0,
        help_text="Suma de los incentivos en dinero de la lista; se calcula sola al guardar.")
    # Se congelan al cerrar el mes (RF-CI-13, RF-CI-15).
    cerrada = models.BooleanField(default=False)
    resultado_logrado = models.PositiveIntegerField("atenciones logradas", null=True, blank=True)
    porcentaje_logrado = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    incentivo_calculado = models.PositiveIntegerField(null=True, blank=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    cerrada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                    related_name="+")

    class Meta:
        db_table = "meta"
        ordering = ["-anio", "-mes", "peluquero__nombre"]
        unique_together = [("peluquero", "mes", "anio")]

    def __str__(self):
        return f"Meta {self.mes:02d}/{self.anio} de {self.peluquero}"


class IncentivoMeta(models.Model):
    """Cada incentivo de la meta: dinero (proporcional al avance) o un regalo/beneficio (al cumplir)."""
    TIPOS = [("dinero", "Dinero"), ("regalo", "Regalo o producto"), ("otro", "Otro beneficio")]

    meta = models.ForeignKey(MetaMensual, on_delete=models.CASCADE, related_name="incentivos", db_column="id_meta")
    tipo = models.CharField("tipo", max_length=10, choices=TIPOS)
    descripcion = models.CharField("descripción", max_length=120, blank=True,
                                   help_text="Ej. Kit de productos Kérastase, día libre.")
    monto = models.PositiveIntegerField("monto ($)", null=True, blank=True)

    class Meta:
        db_table = "incentivo_meta"
        ordering = ["id"]
        verbose_name = "incentivo de la meta"
        verbose_name_plural = "incentivos de la meta"

    def __str__(self):
        if self.tipo == "dinero":
            return f"${self.monto or 0:,}".replace(",", ".") + (f" ({self.descripcion})" if self.descripcion else "")
        return self.descripcion


# ============================================================================
# 7. BENEFICIOS: GIFTCARDS Y PROMOCIONES
#    Giftcards y promociones, solo informativas: no se procesan pagos.
# ============================================================================

ESTADOS = [("vigente", "Vigente"), ("agotada", "Agotada"), ("vencida", "Vencida"), ("deshabilitada", "Deshabilitada")]


def generar_codigo(prefijo, modelo):
    while True:
        codigo = f"{prefijo}-{secrets.token_hex(3).upper()}"
        if not modelo.objects.filter(codigo=codigo).exists():
            return codigo


class Giftcard(models.Model):
    codigo = models.CharField("código", max_length=20, unique=True, editable=False)
    comprador = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="giftcards_compradas",
                                  db_column="comprador_run_cliente", null=True, blank=True)
    beneficiario = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="giftcards",
                                     db_column="beneficiario_run_cliente")
    monto_inicial = models.PositiveIntegerField("monto inicial")
    saldo_actual = models.PositiveIntegerField("saldo actual")
    fecha_compra = models.DateField("fecha de compra", default=timezone.localdate)
    fecha_vencimiento = models.DateField("fecha de vencimiento")
    estado = models.CharField(max_length=15, choices=ESTADOS, default="vigente", db_column="estado_giftcard")
    motivo_deshabilitacion = models.CharField(max_length=255, blank=True)
    creada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "giftcard"
        ordering = ["-fecha_compra"]

    def __str__(self):
        return self.codigo

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = generar_codigo("GC", Giftcard)          # RF-GC-02
        if self.saldo_actual is None:
            self.saldo_actual = self.monto_inicial                 # RF-GC-04
        super().save(*args, **kwargs)

    def actualizar_estado(self):
        """RF-GC-11: agotada al llegar a cero, vencida al pasar la fecha."""
        if self.estado == "deshabilitada":
            return self.estado
        if self.saldo_actual == 0:
            nuevo = "agotada"
        elif self.fecha_vencimiento < timezone.localdate():
            nuevo = "vencida"
        else:
            nuevo = "vigente"
        if nuevo != self.estado:
            self.estado = nuevo
            self.save(update_fields=["estado"])
        return self.estado


class UsoGiftcard(models.Model):
    giftcard = models.ForeignKey(Giftcard, on_delete=models.PROTECT, related_name="usos", db_column="id_giftcard")
    ficha = models.ForeignKey(FichaAtencion, on_delete=models.PROTECT, related_name="usos_giftcard",
                              db_column="id_ficha")
    detalle = models.ForeignKey(DetalleAtencionServicio, on_delete=models.PROTECT, null=True, blank=True,
                                db_column="id_detalle_aten_s")
    monto_usado = models.PositiveIntegerField("monto usado")
    fecha_uso = models.DateTimeField(default=timezone.now)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        db_table = "uso_giftcard"
        ordering = ["-fecha_uso"]


class Promocion(models.Model):
    """Promoción del catálogo (ej. 'Pack 4 brushing')."""
    nombre = models.CharField("nombre", max_length=80, db_column="nombre_promocion")
    precio = models.PositiveIntegerField("precio")
    activo = models.BooleanField("activa", default=True, db_column="estado_promocion")

    class Meta:
        db_table = "promocion"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class PromocionServicio(models.Model):
    promocion = models.ForeignKey(Promocion, on_delete=models.CASCADE, related_name="servicios",
                                  db_column="id_promocion")
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, db_column="id_servicio")
    cantidad_total = models.PositiveSmallIntegerField("cantidad de usos", default=1)

    class Meta:
        db_table = "promocion_servicio"
        unique_together = [("promocion", "servicio")]


class ClientePromocion(models.Model):
    """Promoción adquirida por un cliente; aquí se controlan sus usos."""
    codigo = models.CharField("código", max_length=20, unique=True, editable=False)
    promocion = models.ForeignKey(Promocion, on_delete=models.PROTECT, related_name="ventas", db_column="id_promocion")
    comprador = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="promociones",
                                  db_column="run_cliente_comprador")
    beneficiario = models.ForeignKey(Cliente, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
                                     db_column="run_cliente_beneficiario")
    fecha_compra = models.DateField("fecha de compra", default=timezone.localdate)
    fecha_vencimiento = models.DateField("fecha de vencimiento")
    estado = models.CharField(max_length=15, choices=ESTADOS, default="vigente", db_column="estado_compra_promocion")
    motivo_deshabilitacion = models.CharField(max_length=255, blank=True)
    creada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cliente_promocion"
        ordering = ["-fecha_compra"]

    def __str__(self):
        return f"{self.codigo} ({self.promocion})"

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = generar_codigo("PR", ClientePromocion)
        super().save(*args, **kwargs)

    def detalle_usos(self):
        """Por cada servicio incluido: total, usados y disponibles (RF-PR-05)."""
        usados = {}
        for u in self.usos.all():
            usados[u.servicio_id] = usados.get(u.servicio_id, 0) + u.cantidad_usada
        filas = []
        for ps in self.promocion.servicios.select_related("servicio"):
            u = usados.get(ps.servicio_id, 0)
            filas.append({"servicio": ps.servicio, "total": ps.cantidad_total, "usados": u,
                          "disponibles": max(ps.cantidad_total - u, 0)})
        return filas

    def actualizar_estado(self):
        if self.estado == "deshabilitada":
            return self.estado
        filas = self.detalle_usos()
        if filas and all(f["disponibles"] == 0 for f in filas):
            nuevo = "agotada"
        elif self.fecha_vencimiento < timezone.localdate():
            nuevo = "vencida"
        else:
            nuevo = "vigente"
        if nuevo != self.estado:
            self.estado = nuevo
            self.save(update_fields=["estado"])
        return self.estado


class UsoPromocion(models.Model):
    cliente_promocion = models.ForeignKey(ClientePromocion, on_delete=models.PROTECT, related_name="usos",
                                          db_column="id_cliente_promocion")
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, db_column="id_servicio")
    ficha = models.ForeignKey(FichaAtencion, on_delete=models.PROTECT, related_name="usos_promocion",
                              db_column="id_ficha")
    detalle = models.ForeignKey(DetalleAtencionServicio, on_delete=models.PROTECT, null=True, blank=True,
                                db_column="id_detalle_aten_s")
    cantidad_usada = models.PositiveSmallIntegerField(default=1)
    fecha_uso = models.DateTimeField(default=timezone.now)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        db_table = "uso_promocion"
        ordering = ["-fecha_uso"]
