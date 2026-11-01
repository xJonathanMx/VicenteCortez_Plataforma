from django.db import migrations

# Carta de servicios de la peluquería (noviembre 2026). Copia fija: si cambia un
# precio más adelante, se hace desde la pantalla de servicios o en otra migración.
# tipo: (regla de valoración, comisión externos %, especialidad,
#        [(servicio, precio desde, precio hasta, minutos, días renovación, descripción)])
CATALOGO = {
    'Corte': ('corte', 40, 'Corte', [
        ('Tijeras calientes', 45000, None, 60, None,
         'Corte con tijeras térmicas que sellan la cutícula al cortar; previene puntas abiertas y retiene la humedad.'),
        ('Corte elaborado', 35000, None, 60, None,
         'Cambio de look o diseño avanzado: texturizado, capas conectadas, asimetrías o adaptación a las facciones.'),
        ('Corte tradicional', 25990, None, 45, None,
         'Corte clásico de mantenimiento que devuelve forma y frescura al estilo actual.'),
        ('Corte de puntas', 15000, None, 20, None,
         'Elimina puntas abiertas o resecas conservando el largo. No incluye lavado.'),
    ]),
    'Estilismo': ('ninguno', 40, 'Peinados', [
        ('Peinados', 45000, None, 60, None,
         'Diseño capilar para eventos o el día a día: ondas, trenzas, semi-recogidos y moños estructurados.'),
        ('Lavado + Brushing', 35000, None, 45, None,
         'Lavado profesional con secado y moldeado térmico con cepillo: pule la fibra y controla el volumen.'),
    ]),
    'Colorimetría': ('tratamiento', 35, 'Colorimetría', [
        ('Balayage', 95000, 130000, 180, 90,
         'Degradado a mano alzada con efecto de iluminación natural; mantiene la raíz y aclara hacia las puntas.'),
        ('Babylights + Baño de color', 75000, 110000, 150, 75,
         'Reflejos ultrafinos complementados con un baño de color que unifica y matiza el tono.'),
        ('Full babylight (Full Barbie)', 110000, 180000, 240, 90,
         'Aclarado máximo con abundantes micro-reflejos de raíz a puntas para un rubio global extra claro.'),
        ('Barrido de color', 150000, None, 180, None,
         'Técnica correctiva que extrae pigmentos artificiales no deseados; más suave que un decapado profundo.'),
        ('Reflejos en cabello natural', 45000, 65000, 90, 75,
         'Iluminación suave para cabellos vírgenes: aclara mechones seleccionados para dar luz y dimensión.'),
        ('Shades EQ Redken', 65000, None, 60, 35,
         'Coloración semipermanente con hidratación y brillo espejo; revive tonos, neutraliza reflejos y matiza canas.'),
        ('Solo contorno', 55000, None, 90, 75,
         'Iluminación en los mechones frontales alrededor del rostro, sin decolorar todo el cabello.'),
        ('Color generalizado', 42000, 55000, 90, 45,
         'Tinte en todo el cabello de raíz a puntas para cambiar de color, emparejar o cubrir canas.'),
        ('Tintura visada', 65000, 85000, 120, 60,
         'Color de base más iluminación (visos) en una sola sesión.'),
        ('Baño de color', 35990, None, 45, 35,
         'Devuelve vida, brillo e intensidad a cabellos teñidos y neutraliza tonos no deseados.'),
        ('Babylights + Balayage', 110000, 150000, 210, 90,
         'Babylights en la parte superior o raíz con degradado balayage hacia las puntas.'),
        ('Decapado', 200000, None, 240, None,
         'Elimina pigmentos de tintes anteriores; paso previo para pasar de un tono oscuro teñido a uno mucho más claro.'),
        ('Escondido', 85000, None, 120, 75,
         'Iluminación o color fantasía solo en las capas inferiores y ocultas del cabello.'),
        ('Visos', 55000, 75000, 120, 75,
         'Reflejos tradicionales y definidos que aportan luz, contraste y sensación de volumen.'),
        ('Adicional por tinturas INOA', 18990, None, 0, None,
         "Adicional premium L'Oréal: tintura permanente sin amoníaco y a base de aceites, para cueros cabelludos sensibles."),
        ('Diseños en fantasía', 75000, 120000, 180, None,
         'Tonos vibrantes y creativos; generalmente requiere decoloración previa.'),
        ('Mechas con papel', 95000, 180000, 180, 75,
         'Iluminación con papel aluminio que aísla los mechones para aclarados más precisos e intensos.'),
        ('Raíz + Baño de color', 42000, 65000, 90, 35,
         'Retoque del crecimiento de la raíz más baño de color en largos y puntas para refrescar el tono.'),
    ]),
    'Alisados': ('tratamiento', 30, 'Alisados', [
        ('Coffee Premium', 85000, None, 150, 120,
         'Alisado intensivo a base de queratina y extractos de café, para cabellos rebeldes, gruesos o muy rizados.'),
        ('Real Coffee / Diamond Coffee Colágeno', 55000, 75000, 150, 120,
         'Alisado e hidratación profunda con café y colágeno: reduce volumen, regenera la fibra y da elasticidad.'),
        ('Alisado progresivo Açaí Verde Pra Você', 55000, 85000, 150, 120,
         'Cabello liso, brillante y sin frizz con colágeno vegetal, açaí verde y vitamina C.'),
        ('Thermic Liss', 45000, 65000, 120, 90,
         'Tratamiento disciplinante termo-activo que relaja la onda y controla el frizz; se activa con calor.'),
    ]),
    'Botox capilar': ('tratamiento', 30, 'Tratamientos capilares', [
        ('Blue Diamond', 45990, 75000, 90, 60,
         'Botox capilar que elimina el frizz y devuelve hidratación, suavidad y brillo.'),
        ('Botox H-Brush', 45990, 75000, 90, 60,
         'Reconstructor intensivo con queratina, té verde y aceite de pracaxi; elimina el frizz y devuelve elasticidad y brillo.'),
        ('Reconstrucción y rejuvenecimiento Açaí Pra Você (Botox matizante)', 55000, 85000, 90, 60,
         'Reconstrucción profunda con colágeno vegetal y açaí; además matiza y enfría tonos oxidados o amarillentos.'),
    ]),
    'Aditivos protectores': ('ninguno', 30, 'Tratamientos capilares', [
        ('Metal Detox', 20000, 20000, 20, None,
         "Aditivo L'Oréal que elimina micropartículas de metales de la fibra; evita el quiebre al decolorar."),
        ('Olaplex', 25000, 25000, 20, None,
         'Se añade al proceso químico para proteger y reconstruir los enlaces internos del cabello.'),
    ]),
    'Masajes y tratamientos de reposición': ('tratamiento', 30, 'Tratamientos capilares', [
        ("Máscara L'Oréal", 35990, None, 30, 30,
         'Máscaras profesionales de hidratación y nutrición profunda según la necesidad del cabello.'),
        ('Acidic Concentrate Redken', 55990, None, 45, 30,
         'Tratamiento intensivo que equilibra, sella la cutícula y refuerza los puentes tras procesos químicos.'),
        ('Ritual de lujo Fusio-Dose Kérastase', 65000, None, 45, 30,
         'Tratamiento molecular personalizado: concentrado más booster mezclados al momento.'),
        ('Olaplex stand alone', 75000, None, 60, 45,
         'Reconstrucción profunda en dos pasos, sin proceso de color, para cabellos severamente dañados.'),
        ('4 en 1 Olaplex', 55000, None, 45, 30,
         'Mascarilla concentrada: hidratación, suavidad, brillo y cuerpo sin aportar peso.'),
        ('Premiere Kérastase', 55000, None, 45, 30,
         'Doble acción: elimina la acumulación de calcio y repara los enlaces de queratina.'),
        ('Ampolla Mottita', 25000, None, 30, 30,
         'Tratamiento ultra concentrado de acción rápida: nutrientes, brillo y suavidad.'),
        ('Adicionar ampolla Mottita a otro servicio', 15000, None, 10, None,
         'Se añade la ampolla en el lavapelos para sellar la fibra tras el servicio principal.'),
        ('Masaje Metal Detox adicional a otro servicio', 15990, None, 15, None,
         'Mascarilla y tratamiento detoxificante como cierre de otro servicio.'),
    ]),
    'Novias': ('ninguno', 40, 'Peinados', [
        ('Novias (Pack Salón)', 180000, None, 180, None,
         'Pack para novias con atención en el salón.'),
        ('Novias (Pack Privado)', 250000, None, 240, None,
         'Pack para novias con atención privada.'),
    ]),
}

ESPECIALIDADES = ["Colorimetría", "Corte", "Alisados", "Tratamientos capilares", "Peinados"]

# Nombres anteriores (cargar_datos_iniciales) que cambian según la carta.
RENOMBRES = {("Alisados", "Coffee Premium Colágeno"): "Real Coffee / Diamond Coffee Colágeno"}


def pesos(n):
    return "$" + f"{n:,}".replace(",", ".")


def precio_lista(desde, hasta):
    if hasta is None:
        return f"Precio lista desde {pesos(desde)}"
    if hasta == desde:
        return f"Precio lista {pesos(desde)}"
    return f"Precio lista {pesos(desde)} a {pesos(hasta)}"


def cargar_carta(apps, schema_editor):
    """Crea lo que falta y pone el precio de la carta a lo que ya existe (dejando historial).
    Los servicios que no están en la carta no se tocan."""
    Especialidad = apps.get_model("core", "Especialidad")
    TipoContrato = apps.get_model("core", "TipoContrato")
    TipoServicio = apps.get_model("core", "TipoServicio")
    Comision = apps.get_model("core", "Comision")
    Servicio = apps.get_model("core", "Servicio")
    HistoricoPrecioServicio = apps.get_model("core", "HistoricoPrecioServicio")

    for nombre in ESPECIALIDADES:
        Especialidad.objects.get_or_create(nombre=nombre)
    interno = TipoContrato.objects.get(nombre="Interno")
    externo = TipoContrato.objects.get(nombre="Externo")

    for (tipo_nombre, anterior), nuevo in RENOMBRES.items():
        if not Servicio.objects.filter(tipo__nombre=tipo_nombre, nombre=nuevo).exists():
            Servicio.objects.filter(tipo__nombre=tipo_nombre, nombre=anterior).update(nombre=nuevo)

    for tipo_nombre, (regla, pct, esp, servicios) in CATALOGO.items():
        tipo, _ = TipoServicio.objects.get_or_create(nombre=tipo_nombre, defaults={"seguimiento": regla})
        Comision.objects.get_or_create(tipo_servicio=tipo, contrato=externo, defaults={"porcentaje": pct})
        Comision.objects.get_or_create(tipo_servicio=tipo, contrato=interno, defaults={"porcentaje": 0})
        especialidad = Especialidad.objects.get(nombre=esp)
        for nombre, desde, hasta, minutos, renov, descripcion in servicios:
            s, creado = Servicio.objects.get_or_create(tipo=tipo, nombre=nombre, defaults={
                "precio": desde, "tiempo_estimado": minutos, "dia_renovacion": renov,
                "descripcion": descripcion, "observacion": precio_lista(desde, hasta)})
            if not creado:
                if s.precio != desde:
                    HistoricoPrecioServicio.objects.create(servicio=s, variante="basico",
                                                           precio_anterior=s.precio, precio_nuevo=desde)
                s.precio = desde
                s.observacion = precio_lista(desde, hasta)
                s.save(update_fields=["precio", "observacion"])
            s.especialidades.add(especialidad)


class Migration(migrations.Migration):
    dependencies = [("core", "0004_tipos_contrato")]

    operations = [migrations.RunPython(cargar_carta, migrations.RunPython.noop)]
