"""
Datos de prueba para presentar los reportes con ejemplos completos.

    python manage.py cargar_demo_reportes            # carga ~3,5 meses de actividad
    python manage.py cargar_demo_reportes --borrar   # quita todo lo cargado por este comando

Todo lo de prueba queda identificado para poder retirarlo:
  - Usuarios con RUN 30.000.001 a 30.000.005 (clave «Peluqueria2026»).
  - Clientes con RUN desde 30.100.000 y correo @example.com (dominio reservado: nunca recibe correos).
  - Fichas abiertas por esos usuarios; promociones con nombre que termina en «(demo)».
No deja valoraciones ni recordatorios pendientes, así que procesar_envios no envía nada nuevo.
"""
import random
from datetime import date, datetime, time, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.models import (
    CanalComunicacion, Cliente, ClientePromocion, Comision, ConsultaHistorial, DetalleAtencionServicio,
    DetalleFichaInsumo, EnvioMensaje, Especialidad, FichaAtencion, Giftcard, HistoricoEstadoCliente,
    HistoricoEstadoUsuario, HistorialEstadoFicha, IncentivoMeta, Insumo, MetaMensual, NivelHabilidad, Promocion,
    PromocionServicio, Recordatorio, RegistroAcceso, Rol, Servicio, TipoContrato, UsoGiftcard, UsoPromocion,
    Usuario, UsuarioEspecialidad, UsuarioServicio, Valoracion, VersionFicha,
)
from core.rut import calcular_dv
from metas import servicios as ms
from seguimiento.servicios import fin_de_mes

CLAVE = "Peluqueria2026"
INICIO = date(2026, 8, 1)
RUN_USUARIOS = [str(30000001 + i) for i in range(5)]
RUN_CLIENTE_BASE = 30100000
SUFIJO_PROMO = " (demo)"

# run, nombre, apellido, género, contrato, rol, peso de trabajo, calidad media, uso del historial, especialidad
EQUIPO = [
    (RUN_USUARIOS[0], "Andrea", "Lagos", "F", "Externo", "peluquero", 1.35, 4.7, 0.85, "Colorimetría"),
    (RUN_USUARIOS[1], "Bastián", "Vera", "M", "Externo", "peluquero", 1.0, 4.2, 0.45, "Corte"),
    (RUN_USUARIOS[2], "Carla", "Núñez", "F", "Interno", "peluquero", 1.15, 4.5, 0.6, "Alisados"),
    (RUN_USUARIOS[3], "Daniela", "Fuentes", "F", "Interno", "peluquero", 0.75, 3.8, 0.1, "Tratamientos capilares"),
    (RUN_USUARIOS[4], "Paula", "Saavedra", "F", "Interno", "recepcion", 0, 0, 0, None),
]

NOMBRES_F = ["Camila", "Valentina", "Fernanda", "Javiera", "Constanza", "Ignacia", "Catalina", "Antonia", "Isidora",
             "Francisca", "Josefa", "Martina", "Florencia", "Daniela", "Macarena", "Paz", "Trinidad", "Sofía",
             "Carolina", "Alejandra", "Paulina", "Bárbara", "Rocío", "Gabriela", "María José", "Pía", "Tamara",
             "Natalia", "Andrea", "Claudia", "Loreto", "Verónica", "Marcela", "Romina", "Maite", "Agustina",
             "Emilia", "Amanda", "Renata", "Elisa", "Monserrat", "Cecilia", "Victoria"]
NOMBRES_M = ["Diego", "Matías", "Tomás", "Benjamín", "Joaquín", "Nicolás", "Felipe", "Sebastián", "Cristóbal",
             "Ignacio", "Vicente", "Martín", "Lucas", "Rodrigo", "Gonzalo", "Andrés", "Pablo"]
APELLIDOS = ["Rojas", "Muñoz", "Soto", "Díaz", "Pérez", "Contreras", "Silva", "Morales", "Fuentes", "Araya",
             "González", "Sepúlveda", "Espinoza", "Valenzuela", "Castillo", "Tapia", "Reyes", "Gutiérrez",
             "Castro", "Pizarro", "Álvarez", "Vásquez", "Sánchez", "Fernández", "Ramírez", "Carrasco", "Cortés",
             "Herrera", "Núñez", "Jara", "Vergara", "Rivera", "Figueroa", "Riquelme", "García", "Miranda",
             "Bravo", "Vera", "Molina", "Vega", "Campos", "Sandoval", "Orellana", "Olivares", "Salazar"]

# Peso de cada tipo de servicio al elegir el servicio principal de una atención.
PESO_TIPO = {"Corte": 30, "Colorimetría": 30, "Estilismo": 14, "Masajes y tratamientos de reposición": 11,
             "Alisados": 7, "Botox capilar": 6, "Aditivos protectores": 1, "Novias": 1}
# Servicios que se suman como segundo servicio de la misma ficha.
SEGUNDO = {"Colorimetría": ["Masajes y tratamientos de reposición", "Aditivos protectores", "Estilismo"],
           "Corte": ["Estilismo", "Masajes y tratamientos de reposición", "Colorimetría"],
           "Alisados": ["Corte"], "Botox capilar": ["Corte"],
           "Masajes y tratamientos de reposición": ["Estilismo", "Corte"], "Estilismo": ["Corte"],
           "Aditivos protectores": ["Colorimetría"], "Novias": ["Estilismo"]}
# insumo (nombre, marca), cantidad mínima, máxima, probabilidad
INSUMOS_POR_TIPO = {
    "Colorimetría": [(("Tintura", "L'Oréal Majirel"), 40, 90, 0.55), (("Tintura", "Wella Koleston"), 40, 90, 0.4),
                     (("Oxidante 20 vol", "L'Oréal"), 60, 120, 0.7), (("Oxidante 30 vol", "Wella"), 60, 120, 0.3),
                     (("Decolorante", "Schwarzkopf BlondMe"), 30, 80, 0.35),
                     (("Matizador violeta", "Redken"), 20, 50, 0.3), (("Olaplex N°1", "Olaplex"), 5, 15, 0.2)],
    "Alisados": [(("Keratina", "Inoar"), 80, 150, 1.0), (("Mascarilla hidratante", "Kérastase"), 20, 40, 0.3)],
    "Botox capilar": [(("Keratina", "Inoar"), 40, 80, 0.6), (("Mascarilla hidratante", "Kérastase"), 30, 60, 0.7)],
    "Masajes y tratamientos de reposición": [(("Mascarilla hidratante", "Kérastase"), 20, 50, 0.7),
                                             (("Olaplex N°1", "Olaplex"), 10, 20, 0.35)],
    "Aditivos protectores": [(("Olaplex N°1", "Olaplex"), 5, 15, 1.0)],
}
DIAGNOSTICOS = ["Cabello medio, puntas resecas.", "Raíz de 3 cm, canas 30%.", "Cabello fino, quiere más volumen.",
                "Cabello teñido, medios porosos.", "Frizz en largos, cuero cabelludo sano.",
                "Mechas antiguas, busca matizar.", "Cabello grueso y ondulado.", "Quiere un cambio de look."]
COMENTARIOS = {5: ["Excelente atención, quedé feliz.", "Me encantó el resultado.", "Muy profesional, volveré.", ""],
               4: ["Muy bien, solo esperé un poco.", "Buen resultado.", ""],
               3: ["El color quedó un poco distinto a lo que pedí.", "Bien, pero demoró más de lo esperado."],
               2: ["No quedé conforme con el corte."], 1: ["Mala experiencia."]}


def run_dv(cuerpo):
    return str(cuerpo), calcular_dv(cuerpo)


def sin_tildes(texto):
    import unicodedata
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower().replace(" ", "")


class Command(BaseCommand):
    help = "Carga (o borra con --borrar) datos de prueba para que los reportes se vean completos."

    def add_arguments(self, parser):
        parser.add_argument("--borrar", action="store_true", help="Quita los datos de prueba cargados.")
        parser.add_argument("--semilla", type=int, default=2026)

    def handle(self, *args, **opts):
        if opts["borrar"]:
            self.borrar()
            return
        if Usuario.objects.filter(run__in=RUN_USUARIOS).exists():
            raise CommandError("Los datos de prueba ya están cargados. Usa --borrar primero si quieres regenerarlos.")
        self.rnd = random.Random(opts["semilla"])
        self.tz = timezone.get_current_timezone()
        self.ahora = timezone.now()
        self.hoy = timezone.localdate()
        with transaction.atomic():
            self.cargar()

    # ------------------------------------------------------------------ utilidades
    def momento(self, dia, hora, minuto=0):
        return timezone.make_aware(datetime.combine(dia, time(hora, minuto)), self.tz)

    def dias_habiles(self):
        d = INICIO
        while d <= self.hoy:
            if d.weekday() != 6:  # domingo cerrado
                yield d
            d += timedelta(days=1)

    def log(self, texto):
        self.stdout.write(f"  {texto}")

    # ------------------------------------------------------------------ carga
    def cargar(self):
        r = self.rnd
        self.stdout.write("Cargando datos de prueba...")
        externo = TipoContrato.objects.get(nombre="Externo")
        interno = TipoContrato.objects.get(nombre="Interno")
        contratos = {"Externo": externo, "Interno": interno}
        roles = {x.codigo: x for x in Rol.objects.all()}
        nivel = NivelHabilidad.objects.filter(nombre="Estilista").first()
        servicios = list(Servicio.objects.filter(activo=True).select_related("tipo"))
        por_tipo = {}
        for s in servicios:
            por_tipo.setdefault(s.tipo.nombre, []).append(s)
        comision = {(c.tipo_servicio_id, c.contrato_id): c.porcentaje for c in Comision.objects.all()}
        insumos = {(i.nombre, i.marca): i for i in Insumo.objects.all()}
        email = CanalComunicacion.objects.get(codigo="email")

        # --- Equipo
        self.peluqueros, perfil = [], {}
        for run, nombre, ap, genero, contrato, rol, peso, calidad, historial, esp in EQUIPO:
            u = Usuario.objects.create_user(f"{run}-{calcular_dv(run)}", CLAVE, nombre=nombre, ap_paterno=ap,
                                            correo=f"{sin_tildes(nombre)}.{sin_tildes(ap)}@example.com",
                                            telefono="+56911111111", genero=genero, contrato=contratos[contrato])
            u.roles.add(roles[rol])
            if rol == "peluquero":
                self.peluqueros.append(u)
                perfil[u.pk] = (peso, calidad, historial)
                e = Especialidad.objects.filter(nombre=esp).first()
                if e:
                    UsuarioEspecialidad.objects.create(usuario=u, especialidad=e, es_principal=True)
                UsuarioServicio.objects.bulk_create(
                    [UsuarioServicio(usuario=u, servicio=s, nivel=nivel) for s in servicios])
            else:
                self.recepcion = u
        equipo = self.peluqueros + [self.recepcion]
        self.log(f"Equipo: {len(equipo)} usuarios")

        # --- Clientes (40% registrados antes del período, el resto durante)
        clientes, usados = [], set()
        for i in range(70):
            g = "F" if r.random() < 0.75 else "M"
            while True:
                nombre = r.choice(NOMBRES_F if g == "F" else NOMBRES_M)
                ap, am = r.sample(APELLIDOS, 2)
                if (nombre, ap) not in usados:
                    usados.add((nombre, ap))
                    break
            run, dv = run_dv(RUN_CLIENTE_BASE + i * 1371)
            if i < 28:
                registro = self.momento(date(2026, r.randint(3, 7), r.randint(1, 28)), r.randint(10, 18))
            else:
                dia = INICIO + timedelta(days=int((self.hoy - INICIO).days * (i - 28) / 42))
                registro = self.momento(dia, r.randint(10, 18), r.choice([0, 15, 30, 45]))
            clientes.append(Cliente(
                run=run, dv=dv, nombre=nombre, ap_paterno=ap, ap_materno=am, genero=g,
                telefono=f"+5699{r.randint(1000000, 9999999)}",
                correo=f"{sin_tildes(nombre)}.{sin_tildes(ap)}{i}@example.com" if r.random() < 0.92 else "",
                fecha_nac=date(r.randint(1965, 2005), r.randint(1, 12), r.randint(1, 28)),
                estilista_fijo=r.choice(self.peluqueros) if r.random() < 0.5 else None,
                creado_por=self.recepcion, canal_preferido="email"))
            clientes[-1]._registro = registro
        Cliente.objects.bulk_create(clientes)
        for c in clientes:
            c.creado_en = c._registro
        Cliente.objects.bulk_update(clientes, ["creado_en"])
        self.log(f"Clientes: {len(clientes)}")

        # --- Fichas y servicios
        pesos_pel = [perfil[p.pk][0] for p in self.peluqueros]
        tipos = [t for t in PESO_TIPO if t in por_tipo]
        fichas, detalles_por_ficha = [], {}
        en_curso = 0
        for dia in self.dias_habiles():
            disponibles = [c for c in clientes if c._registro.date() <= dia]
            n = r.randint(3, 6) + (2 if dia.weekday() == 5 else 0)
            for _ in range(n):
                inicio = self.momento(dia, r.randint(10, 18), r.choice([0, 15, 30, 45]))
                if inicio > self.ahora:
                    continue
                sin_cliente = r.random() < 0.08
                cliente = None if sin_cliente else r.choice(disponibles)
                if cliente and cliente.estilista_fijo and r.random() < 0.65:
                    pel = cliente.estilista_fijo
                else:
                    pel = r.choices(self.peluqueros, weights=pesos_pel)[0]
                tipo = r.choices(tipos, weights=[PESO_TIPO[t] for t in tipos])[0]
                elegidos = [(r.choice(por_tipo[tipo]), pel)]
                if r.random() < 0.3:
                    t2 = r.choice([t for t in SEGUNDO.get(tipo, []) if t in por_tipo] or [tipo])
                    pel2 = pel if r.random() < 0.7 else r.choice(self.peluqueros)
                    s2 = r.choice(por_tipo[t2])
                    if s2 != elegidos[0][0]:
                        elegidos.append((s2, pel2))
                # Detalles con horario continuo.
                t, dets = inicio, []
                for s, p in elegidos:
                    dur = max(10, s.tiempo_estimado + r.randint(-10, 25))
                    aplica = p.cobra_comision
                    dets.append(DetalleAtencionServicio(
                        servicio=s, peluquero=p, variante="basico", precio_cobrado=s.precio,
                        porc_comision_guardado=comision.get((s.tipo_id, p.contrato_id), 0) if aplica else 0,
                        aplica_comision=aplica, estado="terminado", hora_inicio=t,
                        hora_termino=t + timedelta(minutes=dur), creado_por=self.recepcion,
                        modificado_por=self.recepcion))
                    t += timedelta(minutes=dur)
                termino = dets[-1].hora_termino
                es_hoy = dia == self.hoy
                if es_hoy and termino > self.ahora:
                    if en_curso >= 2 or not cliente:
                        continue
                    # Servicio en curso hoy: se ve en el estado de los peluqueros.
                    en_curso += 1
                    dets = dets[:1]
                    dets[0].estado, dets[0].hora_termino = "en_proceso", None
                    estado = "en_atencion"
                elif r.random() < 0.02:
                    estado = "anulada"
                else:
                    estado = "validada" if (self.hoy - dia).days > 3 else "cerrada"
                ficha = FichaAtencion(
                    cliente=cliente, abierta_por=self.recepcion if r.random() < 0.6 else pel,
                    nombre_provisorio=f"{r.choice(NOMBRES_F)} (sin registro)" if sin_cliente else "",
                    fecha_hora_inicio=inicio, fecha_hora_termino=None if estado == "en_atencion" else termino,
                    diagnostico=r.choice(DIAGNOSTICOS), estado_id=estado,
                    motivo_anulacion="Cliente no se presentó; ficha abierta por error." if estado == "anulada" else "",
                    creado_por=self.recepcion, modificado_por=self.recepcion)
                if estado == "validada":
                    ficha.validada_por = self.recepcion
                    ficha.fecha_validacion = termino + timedelta(days=r.randint(1, 3))
                fichas.append(ficha)
                detalles_por_ficha[id(ficha)] = dets
        FichaAtencion.objects.bulk_create(fichas)
        detalles, historial = [], []
        for f in fichas:
            for d in detalles_por_ficha[id(f)]:
                d.ficha = f
                detalles.append(d)
            historial.append(HistorialEstadoFicha(ficha=f, estado_id="abierta", fecha_hora_cambio=f.fecha_hora_inicio,
                                                  usuario=f.abierta_por, motivo="Ficha abierta"))
            if f.estado_id == "en_atencion":
                historial.append(HistorialEstadoFicha(ficha=f, estado_anterior_id="abierta", estado_id="en_atencion",
                                                      fecha_hora_cambio=f.fecha_hora_inicio, usuario=f.abierta_por))
            elif f.estado_id == "anulada":
                historial.append(HistorialEstadoFicha(ficha=f, estado_anterior_id="abierta", estado_id="anulada",
                                                      fecha_hora_cambio=f.fecha_hora_inicio + timedelta(minutes=20),
                                                      usuario=self.recepcion, motivo=f.motivo_anulacion))
            else:
                historial.append(HistorialEstadoFicha(ficha=f, estado_anterior_id="abierta", estado_id="cerrada",
                                                      fecha_hora_cambio=f.fecha_hora_termino, usuario=f.abierta_por,
                                                      motivo="Todos los servicios terminados"))
                if f.estado_id == "validada":
                    historial.append(HistorialEstadoFicha(ficha=f, estado_anterior_id="cerrada", estado_id="validada",
                                                          fecha_hora_cambio=f.fecha_validacion, usuario=self.recepcion,
                                                          motivo="Revisada por administración"))
        DetalleAtencionServicio.objects.bulk_create(detalles)
        HistorialEstadoFicha.objects.bulk_create(historial)
        self.log(f"Fichas: {len(fichas)} con {len(detalles)} servicios")

        # --- Insumos usados
        usos = []
        for d in detalles:
            for clave, mn, mx, prob in INSUMOS_POR_TIPO.get(d.servicio.tipo.nombre, []):
                if clave in insumos and r.random() < prob:
                    usos.append(DetalleFichaInsumo(detalle=d, insumo=insumos[clave], cant_usada=r.randint(mn, mx)))
        DetalleFichaInsumo.objects.bulk_create(usos)
        self.log(f"Insumos registrados: {len(usos)}")

        # --- Valoraciones y recordatorios (solo con fecha ya pasada: nada queda pendiente de envío)
        valoraciones, envios_v, recordatorios = [], [], []
        for f in fichas:
            if not f.cliente or f.estado_id in ("anulada", "en_atencion"):
                continue
            dets = detalles_por_ficha[id(f)]
            reglas = {d.servicio.tipo.seguimiento for d in dets}
            principal = next((d for d in dets if d.servicio.tipo.seguimiento == "tratamiento"),
                             next((d for d in dets if d.servicio.tipo.seguimiento == "corte"), dets[0]))
            fecha = timezone.localtime(f.fecha_hora_termino).date()
            programadas = []
            if reglas & {"corte", "tratamiento"}:
                programadas.append(("dia_siguiente", fecha + timedelta(days=1)))
            if "tratamiento" in reglas:
                cierre = fin_de_mes(fecha)
                if cierre <= fecha + timedelta(days=1):
                    cierre = fin_de_mes(cierre + timedelta(days=1))
                programadas.append(("fin_mes", cierre))
            calidad = perfil[principal.peluquero_id][1]
            for tipo, prog in programadas:
                if prog >= self.hoy:
                    continue
                v = Valoracion(ficha=f, peluquero=principal.peluquero, tipo=tipo, fecha_programada=prog)
                envio = self.momento(prog, 10, r.randint(0, 59))
                x = r.random()
                destino = f.cliente.correo or f.cliente.telefono
                if x < 0.04 or not f.cliente.correo:
                    v.estado, v.intentos, v.ultimo_error = "error", 3, "El servidor rechazó el destinatario."
                    for k in range(3):
                        envios_v.append((v, EnvioMensaje(canal=email, destino=destino, exitoso=False,
                                                         error=v.ultimo_error, fecha=envio + timedelta(hours=k))))
                    valoraciones.append(v)
                    continue
                v.fecha_envio, v.intentos = envio, 1
                envios_v.append((v, EnvioMensaje(canal=email, destino=destino, exitoso=True, fecha=envio)))
                if x < 0.66:
                    resp = envio + timedelta(minutes=r.randint(20, 60 * 40))
                    if resp > self.ahora:
                        v.estado = "enviada"
                    else:
                        nota = max(1, min(5, round(r.gauss(calidad, 0.7))))
                        v.estado, v.fecha_respuesta, v.calificacion = "respondida", resp, nota
                        v.respuesta = r.choice(COMENTARIOS[nota])
                elif (self.hoy - prog).days > 3:
                    v.estado = "sin_respuesta"
                else:
                    v.estado = "enviada"
                valoraciones.append(v)
            for d in dets:
                if d.servicio.dia_renovacion:
                    prog = timezone.localtime(d.hora_termino).date() + timedelta(days=d.servicio.dia_renovacion)
                    if prog < self.hoy and f.cliente.correo:
                        recordatorios.append(Recordatorio(tipo="renovacion", cliente=f.cliente, detalle=d,
                                                          fecha_programada=prog))
        Valoracion.objects.bulk_create(valoraciones)
        envios = []
        for v, e in envios_v:
            e.valoracion = v
            envios.append(e)
        for rec in recordatorios:
            envio = self.momento(rec.fecha_programada, 9, r.randint(0, 59))
            destino = rec.cliente.correo or rec.cliente.telefono
            if r.random() < 0.012:
                rec.estado, rec.intentos, rec.ultimo_error = "fallido", 2, "Buzón inexistente."
                for k in range(2):
                    envios.append((rec, EnvioMensaje(canal=email, destino=destino, exitoso=False,
                                                     error=rec.ultimo_error, fecha=envio + timedelta(hours=k))))
            else:
                rec.estado, rec.intentos, rec.fecha_envio = "enviado", 1, envio
                envios.append((rec, EnvioMensaje(canal=email, destino=destino, exitoso=True, fecha=envio)))
        Recordatorio.objects.bulk_create(recordatorios)
        lista_envios = []
        for e in envios:
            if isinstance(e, tuple):
                e[1].recordatorio = e[0]
                lista_envios.append(e[1])
            else:
                lista_envios.append(e)
        EnvioMensaje.objects.bulk_create(lista_envios)
        self.log(f"Valoraciones: {len(valoraciones)}, recordatorios: {len(recordatorios)}, "
                 f"intentos de envío: {len(lista_envios)}")

        # --- Metas e incentivos (agosto y septiembre cerrados; octubre y noviembre abiertos)
        objetivos = [1.22, 1.04, 0.86, 0.71]  # para que haya metas cumplidas, a medias y bajo el mínimo
        meses = []
        m = INICIO
        while (m.year, m.month) <= (self.hoy.year, self.hoy.month):
            meses.append((m.month, m.year))
            m = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
        regalos = ["Kit de productos Kérastase", "Día libre", "Curso de colorimetría", "Gift card $30.000"]
        for mes, anio in meses:
            conteo = ms.atenciones_del_mes(mes, anio)
            actual = (anio, mes) == (self.hoy.year, self.hoy.month)
            for i, p in enumerate(self.peluqueros):
                logradas = conteo.get(p.pk, 0)
                ratio = objetivos[(i + mes) % 4]
                if actual:  # mes en curso: el avance se proyecta al mes completo
                    import calendar
                    ratio *= self.hoy.day / calendar.monthrange(anio, mes)[1]
                meta_n = max(5, round(logradas / ratio)) if logradas else 20
                base = r.choice([60000, 80000, 100000])
                meta = MetaMensual.objects.create(peluquero=p, mes=mes, anio=anio, meta_cliente=meta_n,
                                                  incentivo_base=base)
                IncentivoMeta.objects.create(meta=meta, tipo="dinero", monto=base, descripcion="Bono por cumplimiento")
                IncentivoMeta.objects.create(meta=meta, tipo="regalo", descripcion=regalos[(i + mes) % 4])
                if (anio, mes) < (2026, 10):
                    a = ms.avance(meta, logradas)
                    meta.cerrada, meta.resultado_logrado = True, logradas
                    meta.porcentaje_logrado, meta.incentivo_calculado = a["porcentaje"], a["incentivo"]
                    meta.fecha_cierre = self.momento(date(anio, mes, 1) + timedelta(days=33), 18)
                    meta.save()
        self.log(f"Metas: {len(meses) * len(self.peluqueros)}")

        # --- Giftcards
        fichas_cliente = {}
        for f in fichas:
            if f.cliente and f.estado_id not in ("anulada", "en_atencion"):
                fichas_cliente.setdefault(f.cliente_id, []).append(f)
        con_fichas = [c for c in clientes if len(fichas_cliente.get(c.pk, [])) >= 2]
        n_gc = 0
        for k in range(16):
            benef = r.choice(con_fichas)
            comprador = r.choice(clientes) if r.random() < 0.7 else None
            monto = r.choice([30000, 50000, 50000, 80000, 100000])
            if k < 3:  # compradas hace tiempo y ya vencidas
                compra = date(2026, r.randint(1, 4), r.randint(1, 28))
            else:
                compra = INICIO + timedelta(days=r.randint(0, max(1, (self.hoy - INICIO).days - 10)))
            gc = Giftcard.objects.create(comprador=comprador, beneficiario=benef, monto_inicial=monto,
                                         saldo_actual=monto, fecha_compra=compra,
                                         fecha_vencimiento=compra + timedelta(days=180), creada_por=self.recepcion)
            saldo = monto
            for f in [f for f in fichas_cliente[benef.pk] if timezone.localtime(f.fecha_hora_inicio).date() >= compra]:
                if saldo == 0 or k < 3 or r.random() < 0.45:  # las antiguas quedan sin usar y vencen
                    continue
                total = sum(d.precio_cobrado for d in detalles_por_ficha[id(f)])
                usado = min(saldo, total)
                UsoGiftcard.objects.create(giftcard=gc, ficha=f, detalle=detalles_por_ficha[id(f)][0],
                                           monto_usado=usado, fecha_uso=f.fecha_hora_termino,
                                           registrado_por=self.recepcion)
                saldo -= usado
            gc.saldo_actual = saldo
            if k == 5:
                gc.estado, gc.motivo_deshabilitacion = "deshabilitada", "Código extraviado; se emitió uno nuevo."
            gc.save()
            gc.actualizar_estado()
            n_gc += 1
        self.log(f"Giftcards: {n_gc}")

        # --- Promociones
        def serv(nombre):
            return next(s for s in servicios if s.nombre == nombre)

        packs = [("Pack 4 Lavado + Brushing" + SUFIJO_PROMO, 120000, [("Lavado + Brushing", 4)]),
                 ("Pack Color + Tratamiento" + SUFIJO_PROMO, 70000,
                  [("Raíz + Baño de color", 1), ("Máscara L'Oréal", 1)]),
                 ("Pack 3 Cortes" + SUFIJO_PROMO, 65000, [("Corte tradicional", 3)])]
        promos = []
        for nombre, precio, items in packs:
            pr = Promocion.objects.create(nombre=nombre, precio=precio)
            for sn, cant in items:
                PromocionServicio.objects.create(promocion=pr, servicio=serv(sn), cantidad_total=cant)
            promos.append(pr)
        n_cp = 0
        for k in range(12):
            pr = promos[k % 3]
            comprador = r.choice(con_fichas)
            compra = (date(2026, 3, r.randint(1, 28)) if k < 2
                      else INICIO + timedelta(days=r.randint(0, max(1, (self.hoy - INICIO).days - 15))))
            cp = ClientePromocion.objects.create(promocion=pr, comprador=comprador, fecha_compra=compra,
                                                 fecha_vencimiento=compra + timedelta(days=120),
                                                 creada_por=self.recepcion)
            items = list(pr.servicios.all())
            restantes = {ps.servicio_id: ps.cantidad_total for ps in items}
            for f in fichas_cliente[comprador.pk]:
                if k < 2 or timezone.localtime(f.fecha_hora_inicio).date() < compra or r.random() < 0.3:
                    continue
                ps = r.choice(items)
                if restantes[ps.servicio_id] == 0:
                    continue
                restantes[ps.servicio_id] -= 1
                UsoPromocion.objects.create(cliente_promocion=cp, servicio=ps.servicio, ficha=f,
                                            fecha_uso=f.fecha_hora_termino, registrado_por=self.recepcion)
            if k == 7:
                cp.estado, cp.motivo_deshabilitacion = "deshabilitada", "Devolución acordada con la clienta."
                cp.save()
            cp.actualizar_estado()
            n_cp += 1
        self.log(f"Promociones vendidas: {n_cp}")

        # --- Consultas de historial y accesos al sistema
        consultas, accesos = [], []
        for dia in self.dias_habiles():
            for p in self.peluqueros:
                if r.random() < perfil[p.pk][2]:
                    for _ in range(r.randint(1, 3)):
                        consultas.append(ConsultaHistorial(usuario=p, cliente=r.choice(clientes),
                                                           fecha=self.momento(dia, r.randint(10, 18), r.randint(0, 59))))
            for u in equipo:
                if r.random() < 0.06:
                    for _ in range(r.randint(1, 2)):
                        accesos.append(RegistroAcceso(run_ingresado=f"{u.run}-{u.dv}", exitoso=False,
                                                      fecha=self.momento(dia, 9, r.randint(30, 50)),
                                                      ip=f"192.168.1.{r.randint(10, 60)}"))
                if r.random() < 0.9:
                    accesos.append(RegistroAcceso(run_ingresado=u.run, usuario=u, exitoso=True,
                                                  fecha=self.momento(dia, 9, r.randint(50, 59)),
                                                  ip=f"192.168.1.{r.randint(10, 60)}"))
        consultas = [c for c in consultas if c.fecha <= self.ahora]
        accesos = [a for a in accesos if a.fecha <= self.ahora]
        ConsultaHistorial.objects.bulk_create(consultas)
        RegistroAcceso.objects.bulk_create(accesos)
        self.log(f"Consultas de historial: {len(consultas)}, registros de acceso: {len(accesos)}")

        self.stdout.write(self.style.SUCCESS(
            f"Datos de prueba listos desde el {INICIO:%d-%m-%Y}. Usuarios de prueba (clave «{CLAVE}»): "
            + ", ".join(f"{u.nombre_corto} {u.run_formateado}" for u in equipo) + "."))

    # ------------------------------------------------------------------ borrado
    @transaction.atomic
    def borrar(self):
        usuarios = Usuario.objects.filter(run__in=RUN_USUARIOS)
        clientes = Cliente.objects.filter(run__gte=str(RUN_CLIENTE_BASE), run__lt="30200000")
        fichas = FichaAtencion.objects.filter(
            Q(abierta_por__in=usuarios) | Q(cliente__in=clientes) | Q(servicios__peluquero__in=usuarios)).distinct()
        fichas_ids = list(fichas.values_list("id", flat=True))
        detalles = DetalleAtencionServicio.objects.filter(ficha_id__in=fichas_ids)
        giftcards = Giftcard.objects.filter(Q(beneficiario__in=clientes) | Q(comprador__in=clientes))
        promos = Promocion.objects.filter(nombre__endswith=SUFIJO_PROMO)
        cps = ClientePromocion.objects.filter(Q(comprador__in=clientes) | Q(promocion__in=promos))
        recordatorios = Recordatorio.objects.filter(Q(cliente__in=clientes) | Q(detalle__in=detalles))
        valoraciones = Valoracion.objects.filter(Q(ficha_id__in=fichas_ids) | Q(peluquero__in=usuarios))

        # QuerySet.delete no pasa por el delete() de los históricos (que lo prohíbe a propósito).
        pasos = [
            ("usos de giftcard", UsoGiftcard.objects.filter(Q(giftcard__in=giftcards) | Q(ficha_id__in=fichas_ids))),
            ("usos de promoción", UsoPromocion.objects.filter(Q(cliente_promocion__in=cps) | Q(ficha_id__in=fichas_ids))),
            ("envíos", EnvioMensaje.objects.filter(Q(valoracion__in=valoraciones) | Q(recordatorio__in=recordatorios))),
            ("recordatorios", recordatorios),
            ("valoraciones", valoraciones),
            ("giftcards", giftcards),
            ("promociones vendidas", cps),
            ("promociones", promos),
            ("insumos usados", DetalleFichaInsumo.objects.filter(detalle__in=detalles)),
            ("historial de fichas", HistorialEstadoFicha.objects.filter(ficha_id__in=fichas_ids)),
            ("versiones de fichas", VersionFicha.objects.filter(ficha_id__in=fichas_ids)),
            ("servicios de fichas", detalles),
            ("fichas", FichaAtencion.objects.filter(id__in=fichas_ids)),
            ("consultas de historial", ConsultaHistorial.objects.filter(Q(usuario__in=usuarios) | Q(cliente__in=clientes))),
            ("registros de acceso", RegistroAcceso.objects.filter(
                Q(usuario__in=usuarios) | Q(run_ingresado__in=[f"{x}-{calcular_dv(x)}" for x in RUN_USUARIOS]))),
            ("metas", MetaMensual.objects.filter(peluquero__in=usuarios)),
            ("historial de clientes", HistoricoEstadoCliente.objects.filter(cliente__in=clientes)),
        ]
        for nombre, qs in pasos:
            n, _ = qs.delete()
            if n:
                self.log(f"{nombre}: {n}")
        Cliente.objects.filter(estilista_fijo__in=usuarios).update(estilista_fijo=None)
        n, _ = clientes.delete()
        self.log(f"clientes: {n}")
        HistoricoEstadoUsuario.objects.filter(usuario__in=usuarios).delete()
        UsuarioServicio.objects.filter(usuario__in=usuarios).delete()
        UsuarioEspecialidad.objects.filter(usuario__in=usuarios).delete()
        n, _ = usuarios.delete()
        self.log(f"usuarios: {n}")
        self.stdout.write(self.style.SUCCESS("Datos de prueba eliminados."))
