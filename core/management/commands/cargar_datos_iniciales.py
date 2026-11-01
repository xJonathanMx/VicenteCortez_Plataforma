"""
Carga catálogos base. Se puede ejecutar varias veces sin duplicar datos.

    python manage.py cargar_datos_iniciales          # solo catálogos
    python manage.py cargar_datos_iniciales --demo   # + usuarios, clientes y fichas de prueba
"""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import (
    CanalComunicacion, Especialidad, HistoricoEstadoServicio, Insumo,
    NivelHabilidad, NivelIncentivo, Plantilla, Privilegio, Rol, Servicio, TipoContrato, TipoEstado,
    TipoServicio, Usuario, UsuarioEspecialidad, UsuarioServicio,
)
from core.permisos import PRIVILEGIOS, ROLES_BASE
from seguimiento.servicios import TEXTOS_POR_DEFECTO

ESPECIALIDADES = ["Colorimetría", "Corte", "Alisados", "Tratamientos capilares", "Peinados"]

# El catálogo de servicios y precios (la carta) lo crea la migración core/0005_catalogo_carta.

EJEMPLOS_ANTIGUOS = {
    "Corte": ["Corte dama", "Corte varón", "Corte infantil"],
    "Colorimetría": ["Raíz", "Tintura completa"],
    "Alisados": ["Alisado keratina", "Botox capilar"],
    "Tratamientos": ["Hidratación profunda", "Reconstrucción"],
    "Peinados": ["Brushing", "Peinado de evento"],
}
TIPOS_ANTIGUOS = ["Tratamientos", "Peinados"]


INSUMOS = [
    ("Tintura", "L'Oréal Majirel", "Profesional", "g"),
    ("Tintura", "Wella Koleston", "Profesional", "g"),
    ("Decolorante", "Schwarzkopf BlondMe", "Premium", "g"),
    ("Oxidante 20 vol", "L'Oréal", "Profesional", "ml"),
    ("Oxidante 30 vol", "Wella", "Profesional", "ml"),
    ("Matizador violeta", "Redken", "Premium", "ml"),
    ("Keratina", "Inoar", "Premium", "ml"),
    ("Olaplex N°1", "Olaplex", "Premium", "ml"),
    ("Mascarilla hidratante", "Kérastase", "Premium", "ml"),
]

NOMBRES = [("Camila", "Rojas", "F"), ("Valentina", "Muñoz", "F"), ("Diego", "Soto", "M"), ("Fernanda", "Díaz", "F"),
           ("Javiera", "Pérez", "F"), ("Matías", "Contreras", "M"), ("Constanza", "Silva", "F"),
           ("Ignacia", "Morales", "F"), ("Tomás", "Fuentes", "M"), ("Catalina", "Araya", "F")]


def sin_tildes(texto):
    """Los correos no deben llevar tildes ni ñ: 'Pérez' -> 'perez'."""
    import unicodedata
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def run_valido(cuerpo):
    from core.rut import calcular_dv
    return f"{cuerpo}-{calcular_dv(cuerpo)}"


class Command(BaseCommand):
    help = "Carga roles, privilegios, catálogos y (opcional) datos de demostración."

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true", help="Crea usuarios, clientes y fichas de prueba.")

    @transaction.atomic
    def handle(self, *args, **opts):
        for codigo, nombre in PRIVILEGIOS.items():
            Privilegio.objects.update_or_create(codigo=codigo, defaults={"nombre": nombre})
        for codigo, (nombre, privs) in ROLES_BASE.items():
            rol, nuevo = Rol.objects.get_or_create(codigo=codigo, defaults={"nombre": nombre})
            if nuevo or codigo == "administrador":
                rol.privilegios.set(Privilegio.objects.filter(codigo__in=privs))

        interno, _ = TipoContrato.objects.get_or_create(nombre="Interno", defaults={"aplica_comision": False})
        externo, _ = TipoContrato.objects.get_or_create(nombre="Externo", defaults={"aplica_comision": True})
        for e in ("Activo", "Inactivo"):
            TipoEstado.objects.get_or_create(nombre=e)
        for n, d in [("Aprendiz", "En formación, requiere supervisión"), ("Estilista", "Realiza el servicio de forma autónoma"),
                     ("Senior", "Referente técnico del salón")]:
            NivelHabilidad.objects.get_or_create(nombre=n, defaults={"descripcion": d})
        for nombre in ESPECIALIDADES:
            Especialidad.objects.get_or_create(nombre=nombre)
        for minimo, pago in [(80, 50), (100, 100), (120, 130)]:
            NivelIncentivo.objects.get_or_create(porcentaje_minimo=minimo, defaults={"porcentaje_pago": pago})

        canales = {}
        for codigo, nombre in [("whatsapp", "WhatsApp"), ("email", "Correo electrónico")]:
            canales[codigo], _ = CanalComunicacion.objects.get_or_create(
                codigo=codigo, defaults={"nombre": nombre, "activo": codigo == "email"})  # por ahora solo correo
        for tipo, (asunto, cuerpo) in TEXTOS_POR_DEFECTO.items():
            for canal in canales.values():
                Plantilla.objects.get_or_create(tipo=tipo, canal=canal, defaults={"asunto": asunto, "cuerpo": cuerpo})

        self.retirar_ejemplos()
        for nombre, marca, calidad, unidad in INSUMOS:
            Insumo.objects.get_or_create(nombre=nombre, marca=marca, calidad=calidad, defaults={"unidad_medida": unidad})

        self.stdout.write(self.style.SUCCESS("Catálogos base cargados."))
        if opts["demo"]:
            self.demo(interno, externo)

    def retirar_ejemplos(self):
        """Desactiva (con historial) los servicios y tipos de ejemplo de la primera versión."""
        inactivo = TipoEstado.objects.get(nombre="Inactivo")
        for tipo_nombre, nombres in EJEMPLOS_ANTIGUOS.items():
            for s in Servicio.objects.filter(tipo__nombre=tipo_nombre, nombre__in=nombres, activo=True):
                s.activo = False
                s.save(update_fields=["activo"])
                HistoricoEstadoServicio.objects.create(
                    servicio=s, tipo_estado=inactivo,
                    motivo="Reemplazado por el catálogo real de la peluquería")
        TipoServicio.objects.filter(nombre__in=TIPOS_ANTIGUOS, activo=True).exclude(
            servicios__activo=True).update(activo=False)

    def demo(self, interno, externo):
        from core.models import Cliente
        from fichas import servicios as fs
        from core.models import MetaMensual

        admin_rol = Rol.objects.get(codigo="administrador")
        pelu_rol = Rol.objects.get(codigo="peluquero")
        recep_rol = Rol.objects.get(codigo="recepcion")
        clave = "Peluqueria2026"

        def usuario(cuerpo, nombre, ap, genero, contrato, roles):
            u = Usuario.objects.filter(run=str(cuerpo)).first()
            if not u:
                u = Usuario.objects.create_user(run_valido(cuerpo), clave, nombre=nombre, ap_paterno=ap,
                                                correo=f"{sin_tildes(nombre)}@vicentecortez.cl",
                                                telefono="+56912345678", genero=genero, contrato=contrato)
            u.roles.add(*roles)
            return u

        admin = usuario(11111111, "Vicente", "Cortez", "M", interno, [admin_rol])
        admin.is_staff = admin.is_superuser = True
        admin.save()
        usuario(15555555, "Paula", "Recepción", "F", interno, [recep_rol])
        peluqueros = [
            usuario(16666666, "Andrea", "Lagos", "F", externo, [pelu_rol]),
            usuario(17777777, "Bastián", "Vera", "M", externo, [pelu_rol]),
            usuario(18888888, "Carla", "Núñez", "F", interno, [pelu_rol]),
        ]
        especialidades = list(Especialidad.objects.all())
        nivel = NivelHabilidad.objects.get(nombre="Estilista")
        for i, p in enumerate(peluqueros):
            UsuarioEspecialidad.objects.get_or_create(usuario=p, especialidad=especialidades[i % len(especialidades)],
                                                      defaults={"es_principal": True})
            for s in Servicio.objects.all():
                UsuarioServicio.objects.get_or_create(usuario=p, servicio=s, defaults={"nivel": nivel})

        hoy = timezone.localdate()
        clientes = []
        for i, (nombre, ap, g) in enumerate(NOMBRES):
            cuerpo = 20000000 + i * 1371
            c = Cliente.objects.filter(run=str(cuerpo)).first() or Cliente.objects.create(
                run=str(cuerpo), dv=run_valido(cuerpo)[-1], nombre=nombre, ap_paterno=ap, genero=g,
                telefono=f"+5699{random.randint(1000000, 9999999)}", correo=f"{sin_tildes(nombre)}.{sin_tildes(ap)}@correo.cl",
                fecha_nac=hoy - timedelta(days=365 * random.randint(20, 55)),
                estilista_fijo=peluqueros[i % 3] if i % 2 == 0 else None, creado_por=admin)
            clientes.append(c)

        if not fs.FichaAtencion.objects.exists():
            random.seed(7)
            servicios = list(Servicio.objects.all())
            for d in range(40, 0, -1):
                for _ in range(random.randint(1, 3)):
                    momento = timezone.now() - timedelta(days=d, hours=random.randint(1, 6))
                    cliente = random.choice(clientes)
                    ficha = fs.abrir_ficha(admin, cliente, diagnostico="Cabello medio, puntas resecas.")
                    ficha.fecha_hora_inicio = momento
                    ficha.save()
                    pel = cliente.estilista_fijo or random.choice(peluqueros)
                    det = fs.agregar_servicio(ficha, random.choice(servicios), pel,
                                              random.choice(["basico", "plus", "ultra_plus"]), admin)
                    det.estado, det.hora_inicio = "terminado", momento
                    det.hora_termino = momento + timedelta(minutes=det.servicio.tiempo_estimado + random.randint(-10, 25))
                    det.save()
                    fs.cerrar_ficha(ficha, admin)
                    if d > 3:
                        fs.validar_ficha(ficha, admin)
            # Un servicio en curso para ver el estado "ocupado".
            ficha = fs.abrir_ficha(admin, clientes[0], diagnostico="Raíz de 3 cm, canas 30%.")
            det = fs.agregar_servicio(ficha, Servicio.objects.get(nombre="Raíz + Baño de color"), peluqueros[0], "plus", admin)
            fs.iniciar_servicio(det, admin)

        for p in peluqueros:
            meta, nueva = MetaMensual.objects.get_or_create(peluquero=p, mes=hoy.month, anio=hoy.year,
                                                            defaults={"meta_cliente": 25, "incentivo_base": 80000})
            if nueva:
                meta.incentivos.create(tipo="dinero", monto=80000)
                meta.incentivos.create(tipo="regalo", descripcion="Kit de productos Kérastase")
        self.stdout.write(self.style.SUCCESS(
            f"Demo lista. Clave de todos: «{clave}». Administrador {admin.run_formateado}; "
            f"recepción {Usuario.objects.get(run='15555555').run_formateado}; "
            f"peluqueros {', '.join(p.run_formateado for p in peluqueros)}."))
