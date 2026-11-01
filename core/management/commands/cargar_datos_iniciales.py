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
    CanalComunicacion, Comision, Especialidad, HistoricoEstadoServicio, HistoricoPrecioServicio, Insumo,
    NivelHabilidad, NivelIncentivo, Plantilla, Privilegio, Rol, Servicio, TipoContrato, TipoEstado,
    TipoServicio, Usuario, UsuarioEspecialidad, UsuarioServicio,
)
from core.permisos import PRIVILEGIOS, ROLES_BASE
from seguimiento.servicios import TEXTOS_POR_DEFECTO

ESPECIALIDADES = ["Colorimetría", "Corte", "Alisados", "Tratamientos capilares", "Peinados"]

# tipo: (regla de valoración, comisión externos %, [(servicio, precio, plus, ultra, minutos, días renovación, especialidad)])
CATALOGO = {
    "Corte": ("corte", 40, "Corte", [
        ("Tijeras calientes", 45000, None, 60, None,
         "Corte con tijeras térmicas que sellan la cutícula al cortar; previene puntas abiertas y retiene la humedad."),
        ("Corte elaborado", 35000, None, 60, None,
         "Cambio de look o diseño avanzado: texturizado, capas conectadas, asimetrías o adaptación a las facciones."),
        ("Corte tradicional", 25000, None, 45, None,
         "Corte clásico de mantenimiento que devuelve forma y frescura al estilo actual."),
        ("Corte de puntas", 15000, None, 20, None,
         "Elimina puntas abiertas o resecas conservando el largo. No incluye lavado."),
    ]),
    "Estilismo": ("ninguno", 40, "Peinados", [
        ("Peinados", 45000, None, 60, None,
         "Diseño capilar para eventos o el día a día: ondas, trenzas, semi-recogidos y moños estructurados."),
        ("Lavado + Brushing", 35000, None, 45, None,
         "Lavado profesional con secado y moldeado térmico con cepillo: pule la fibra y controla el volumen."),
    ]),
    "Colorimetría": ("tratamiento", 35, "Colorimetría", [
        ("Balayage", 95000, 130000, 180, 90,
         "Degradado a mano alzada con efecto de iluminación natural; mantiene la raíz y aclara hacia las puntas."),
        ("Babylights + Baño de color", 75000, 110000, 150, 75,
         "Reflejos ultrafinos complementados con un baño de color que unifica y matiza el tono."),
        ("Full babylight (Full Barbie)", 110000, 180000, 240, 90,
         "Aclarado máximo con abundantes micro-reflejos de raíz a puntas para un rubio global extra claro."),
        ("Barrido de color", 150000, None, 180, None,
         "Técnica correctiva que extrae pigmentos artificiales no deseados; más suave que un decapado profundo."),
        ("Reflejos en cabello natural", 45000, 65000, 90, 75,
         "Iluminación suave para cabellos vírgenes: aclara mechones seleccionados para dar luz y dimensión."),
        ("Shades EQ Redken", 65000, None, 60, 35,
         "Coloración semipermanente con hidratación y brillo espejo; revive tonos, neutraliza reflejos y matiza canas."),
        ("Solo contorno", 55000, None, 90, 75,
         "Iluminación en los mechones frontales alrededor del rostro, sin decolorar todo el cabello."),
        ("Color generalizado", 42000, 55000, 90, 45,
         "Tinte en todo el cabello de raíz a puntas para cambiar de color, emparejar o cubrir canas."),
        ("Tintura visada", 65000, 85000, 120, 60,
         "Color de base más iluminación (visos) en una sola sesión."),
        ("Baño de color", 35990, None, 45, 35,
         "Devuelve vida, brillo e intensidad a cabellos teñidos y neutraliza tonos no deseados."),
        ("Babylights + Balayage", 110000, 150000, 210, 90,
         "Babylights en la parte superior o raíz con degradado balayage hacia las puntas."),
        ("Decapado", 200000, None, 240, None,
         "Elimina pigmentos de tintes anteriores; paso previo para pasar de un tono oscuro teñido a uno mucho más claro."),
        ("Escondido", 85000, None, 120, 75,
         "Iluminación o color fantasía solo en las capas inferiores y ocultas del cabello."),
        ("Visos", 55000, 75000, 120, 75,
         "Reflejos tradicionales y definidos que aportan luz, contraste y sensación de volumen."),
        ("Adicional por tinturas INOA", 18990, None, 0, None,
         "Adicional premium L'Oréal: tintura permanente sin amoníaco y a base de aceites, para cueros cabelludos sensibles."),
        ("Diseños en fantasía", 75000, 120000, 180, None,
         "Tonos vibrantes y creativos; generalmente requiere decoloración previa."),
        ("Mechas con papel", 95000, 180000, 180, 75,
         "Iluminación con papel aluminio que aísla los mechones para aclarados más precisos e intensos."),
        ("Raíz + Baño de color", 42000, 65000, 90, 35,
         "Retoque del crecimiento de la raíz más baño de color en largos y puntas para refrescar el tono."),
    ]),
    "Alisados": ("tratamiento", 30, "Alisados", [
        ("Coffee Premium", 55000, 85000, 150, 120,
         "Alisado intensivo a base de queratina y extractos de café, para cabellos rebeldes, gruesos o muy rizados."),
        ("Coffee Premium Colágeno", 55000, 85000, 150, 120,
         "Alisado e hidratación profunda con café y colágeno: reduce volumen, regenera la fibra y da elasticidad."),
        ("Alisado progresivo Açaí Verde Pra Você", 55000, 85000, 150, 120,
         "Cabello liso, brillante y sin frizz con colágeno vegetal, açaí verde y vitamina C."),
        ("Thermic Liss", 45000, 65000, 120, 90,
         "Tratamiento disciplinante termo-activo que relaja la onda y controla el frizz; se activa con calor."),
    ]),
    "Botox capilar": ("tratamiento", 30, "Tratamientos capilares", [
        ("Botox H-Brush", 45990, 75000, 90, 60,
         "Reconstructor intensivo con queratina, té verde y aceite de pracaxi; elimina el frizz y devuelve elasticidad y brillo."),
        ("Reconstrucción y rejuvenecimiento Açaí Pra Você (Botox matizante)", 55000, 85000, 90, 60,
         "Reconstrucción profunda con colágeno vegetal y açaí; además matiza y enfría tonos oxidados o amarillentos."),
    ]),
    "Aditivos protectores": ("ninguno", 30, "Tratamientos capilares", [
        ("Metal Detox", 20000, 20000, 20, None,
         "Aditivo L'Oréal que elimina micropartículas de metales de la fibra; evita el quiebre al decolorar."),
        ("Olaplex", 25000, 25000, 20, None,
         "Se añade al proceso químico para proteger y reconstruir los enlaces internos del cabello."),
    ]),
    "Masajes y tratamientos de reposición": ("tratamiento", 30, "Tratamientos capilares", [
        ("Máscara L'Oréal", 35990, None, 30, 30,
         "Máscaras profesionales de hidratación y nutrición profunda según la necesidad del cabello."),
        ("Acidic Concentrate Redken", 55990, None, 45, 30,
         "Tratamiento intensivo que equilibra, sella la cutícula y refuerza los puentes tras procesos químicos."),
        ("Ritual de lujo Fusio-Dose Kérastase", 65000, None, 45, 30,
         "Tratamiento molecular personalizado: concentrado más booster mezclados al momento."),
        ("Olaplex stand alone", 75000, None, 60, 45,
         "Reconstrucción profunda en dos pasos, sin proceso de color, para cabellos severamente dañados."),
        ("4 en 1 Olaplex", 55000, None, 45, 30,
         "Mascarilla concentrada: hidratación, suavidad, brillo y cuerpo sin aportar peso."),
        ("Premiere Kérastase", 55000, None, 45, 30,
         "Doble acción: elimina la acumulación de calcio y repara los enlaces de queratina."),
        ("Ampolla Mottita", 25000, None, 30, 30,
         "Tratamiento ultra concentrado de acción rápida: nutrientes, brillo y suavidad."),
        ("Adicionar ampolla Mottita a otro servicio", 15000, None, 10, None,
         "Se añade la ampolla en el lavapelos para sellar la fibra tras el servicio principal."),
        ("Masaje Metal Detox adicional a otro servicio", 15990, None, 15, None,
         "Mascarilla y tratamiento detoxificante como cierre de otro servicio."),
    ]),
}

EJEMPLOS_ANTIGUOS = {
    "Corte": ["Corte dama", "Corte varón", "Corte infantil"],
    "Colorimetría": ["Raíz", "Tintura completa"],
    "Alisados": ["Alisado keratina", "Botox capilar"],
    "Tratamientos": ["Hidratación profunda", "Reconstrucción"],
    "Peinados": ["Brushing", "Peinado de evento"],
}
TIPOS_ANTIGUOS = ["Tratamientos", "Peinados"]


def pesos(n):
    return "$" + f"{n:,}".replace(",", ".")

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

        for tipo_nombre, (regla, pct, esp, servicios) in CATALOGO.items():
            tipo, _ = TipoServicio.objects.get_or_create(nombre=tipo_nombre, defaults={"seguimiento": regla})
            Comision.objects.get_or_create(tipo_servicio=tipo, contrato=externo, defaults={"porcentaje": pct})
            Comision.objects.get_or_create(tipo_servicio=tipo, contrato=interno, defaults={"porcentaje": 0})
            for nombre, desde, hasta, minutos, renov, descripcion in servicios:
                if hasta is None:
                    obs = f"Precio lista desde {pesos(desde)}"
                elif hasta == desde:
                    obs = f"Precio lista {pesos(desde)}"
                else:
                    obs = f"Precio lista {pesos(desde)} a {pesos(hasta)}"
                datos = {"precio": desde, "precio_plus": None, "precio_ultra_plus": None, "tiempo_estimado": minutos,
                         "dia_renovacion": renov, "descripcion": descripcion, "observacion": obs}
                s, creado = Servicio.objects.get_or_create(tipo=tipo, nombre=nombre, defaults=datos)
                if not creado and not s.observacion:
                    # Servicio de ejemplo viejo con el mismo nombre: se corrige al precio de lista
                    if s.precio != desde:
                        HistoricoPrecioServicio.objects.create(servicio=s, variante="basico",
                                                               precio_anterior=s.precio, precio_nuevo=desde)
                    for campo, valor in datos.items():
                        setattr(s, campo, valor)
                    s.activo = True
                    s.save()
                s.especialidades.add(Especialidad.objects.get(nombre=esp))
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
