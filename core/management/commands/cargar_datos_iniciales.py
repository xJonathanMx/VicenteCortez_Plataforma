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

from catalogo.models import Comision, Insumo, Servicio, TipoServicio, UsuarioServicio
from core.models import (Especialidad, NivelHabilidad, Privilegio, Rol, TipoContrato, TipoEstado, Usuario,
                         UsuarioEspecialidad)
from core.permisos import PRIVILEGIOS, ROLES_BASE
from metas.models import NivelIncentivo
from seguimiento.models import CanalComunicacion, Plantilla
from seguimiento.servicios import TEXTOS_POR_DEFECTO

ESPECIALIDADES = ["Colorimetría", "Corte", "Alisados", "Tratamientos capilares", "Peinados"]

# tipo: (regla de valoración, comisión externos %, [(servicio, precio, plus, ultra, minutos, días renovación, especialidad)])
CATALOGO = {
    "Corte": ("corte", 40, [
        ("Corte dama", 18000, 22000, 28000, 45, None, "Corte"),
        ("Corte varón", 12000, 15000, None, 30, None, "Corte"),
        ("Corte infantil", 9000, None, None, 25, None, "Corte"),
    ]),
    "Colorimetría": ("tratamiento", 35, [
        ("Balayage", 85000, 110000, 140000, 180, 90, "Colorimetría"),
        ("Visos", 60000, 75000, 95000, 120, 75, "Colorimetría"),
        ("Raíz", 35000, 42000, 52000, 75, 35, "Colorimetría"),
        ("Tintura completa", 45000, 55000, 70000, 90, 45, "Colorimetría"),
    ]),
    "Alisados": ("tratamiento", 30, [
        ("Alisado keratina", 70000, 90000, 120000, 150, 120, "Alisados"),
        ("Botox capilar", 45000, 58000, 75000, 90, 60, "Tratamientos capilares"),
    ]),
    "Tratamientos": ("tratamiento", 30, [
        ("Hidratación profunda", 25000, 32000, 40000, 45, 30, "Tratamientos capilares"),
        ("Reconstrucción", 38000, 48000, 60000, 60, 30, "Tratamientos capilares"),
    ]),
    "Peinados": ("ninguno", 40, [
        ("Brushing", 15000, 18000, None, 40, None, "Peinados"),
        ("Peinado de evento", 35000, 45000, None, 60, None, "Peinados"),
    ]),
}

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

        for tipo_nombre, (regla, pct, servicios) in CATALOGO.items():
            tipo, _ = TipoServicio.objects.get_or_create(nombre=tipo_nombre, defaults={"seguimiento": regla})
            Comision.objects.get_or_create(tipo_servicio=tipo, contrato=externo, defaults={"porcentaje": pct})
            Comision.objects.get_or_create(tipo_servicio=tipo, contrato=interno, defaults={"porcentaje": 0})
            for nombre, precio, plus, ultra, minutos, renov, esp in servicios:
                s, _ = Servicio.objects.get_or_create(tipo=tipo, nombre=nombre, defaults={
                    "precio": precio, "precio_plus": plus, "precio_ultra_plus": ultra,
                    "tiempo_estimado": minutos, "dia_renovacion": renov})
                s.especialidades.add(Especialidad.objects.get(nombre=esp))
        for nombre, marca, calidad, unidad in INSUMOS:
            Insumo.objects.get_or_create(nombre=nombre, marca=marca, calidad=calidad, defaults={"unidad_medida": unidad})

        self.stdout.write(self.style.SUCCESS("Catálogos base cargados."))
        if opts["demo"]:
            self.demo(interno, externo)

    def demo(self, interno, externo):
        from clientes.models import Cliente
        from fichas import servicios as fs
        from metas.models import MetaMensual

        admin_rol = Rol.objects.get(codigo="administrador")
        pelu_rol = Rol.objects.get(codigo="peluquero")
        recep_rol = Rol.objects.get(codigo="recepcion")
        clave = "Peluqueria2026"

        def usuario(cuerpo, nombre, ap, genero, contrato, roles):
            u = Usuario.objects.filter(run=str(cuerpo)).first()
            if not u:
                u = Usuario.objects.create_user(run_valido(cuerpo), clave, nombre=nombre, ap_paterno=ap,
                                                correo=f"{nombre.lower()}@vicentecortez.cl",
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
                telefono=f"+5699{random.randint(1000000, 9999999)}", correo=f"{nombre.lower()}.{ap.lower()}@correo.cl",
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
            det = fs.agregar_servicio(ficha, Servicio.objects.get(nombre="Raíz"), peluqueros[0], "plus", admin)
            fs.iniciar_servicio(det, admin)

        for p in peluqueros:
            MetaMensual.objects.get_or_create(peluquero=p, mes=hoy.month, anio=hoy.year,
                                              defaults={"meta_cliente": 25, "incentivo_base": 80000})
        self.stdout.write(self.style.SUCCESS(
            f"Demo lista. Clave de todos: «{clave}». Administrador {admin.run_formateado}; "
            f"recepción {Usuario.objects.get(run='15555555').run_formateado}; "
            f"peluqueros {', '.join(p.run_formateado for p in peluqueros)}."))
