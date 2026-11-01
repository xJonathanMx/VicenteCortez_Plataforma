from django.db import migrations

# Descripciones completas de los documentos de la peluquería ("Conoce tus servicios y
# precios de lista"). Reemplazan las versiones cortas de 0005. Blue Diamond y Novias no
# aparecen en esos documentos y conservan su descripción.
DESCRIPCIONES = {
    # Corte de cabello
    "Tijeras calientes": (
        "Innovador corte realizado con tijeras térmicas que sellan la cutícula con calor en el momento exacto "
        "del corte. Previene la aparición de puntas abiertas y retiene la humedad natural de la hebra."),
    "Corte elaborado": (
        "Cambio de look completo o diseño de corte avanzado que requiere técnicas específicas de texturizado, "
        "capas conectadas, asimetrías o adaptación morfológica a las facciones del cliente."),
    "Corte tradicional": (
        "Corte clásico de mantenimiento para devolver la forma, estructura y frescura a tu estilo actual, "
        "manteniendo tu diseño de peinado preferido."),
    "Corte de puntas": (
        "Mantenimiento esencial enfocado exclusivamente en sanear el cabello eliminando las puntas abiertas, "
        "maltratadas o resecas, conservando al máximo el largo actual de tu melena. No incluye lavado."),
    # Estilismo
    "Peinados": (
        "Servicio de diseño capilar ideal para eventos especiales, fiestas o para el día a día. Incluye desde "
        "ondas, trenzas y semi-recogidos, hasta moños estructurados, adaptando siempre el estilo para resaltar "
        "las facciones de cada clienta."),
    "Lavado + Brushing": (
        "El dúo perfecto para un acabado de salón impecable. Consiste en un lavado profesional, seguido de un "
        "secado y moldeado térmico con cepillo que pule la fibra capilar, controla el volumen y deja una melena "
        "suelta, extremadamente suave y con mucho movimiento."),
    # Alisados
    "Coffee Premium": (
        "Sistema de alisado intensivo a base de queratina y extractos de café, especialmente diseñado para "
        "alisar incluso los cabellos más rebeldes, gruesos o muy rizados, aportando nutrición profunda."),
    "Real Coffee / Diamond Coffee Colágeno": (
        "Tratamiento de alisado e hidratación profunda que combina el poder reparador de los extractos de café "
        "con las propiedades estructurales del colágeno. Reduce el volumen, regenera la fibra, aportando fuerza, "
        "máxima elasticidad y un liso de aspecto saludable."),
    "Alisado progresivo Açaí Verde Pra Você": (
        "Tratamiento que busca dejar el cabello liso, brillante, sin frizz y con un movimiento natural. Utiliza "
        "una tecnología especial que combina colágeno vegetal, açaí verde y vitamina C, logrando transformar la "
        "textura del cabello mientras lo protege y nutre."),
    "Thermic Liss": (
        "Tratamiento disciplinante termo-activo que relaja la onda y controla el frizz. Facilita el peinado "
        "diario y se activa con el calor del secador o la plancha, protegiendo el pelo de las altas temperaturas."),
    # Botox capilar
    "Botox H-Brush": (
        "Sistema reconstructor intensivo que elimina el encrespamiento y el frizz, regenerando el pelo para "
        "recuperar su estructura natural. Funciona como un regenerador celular desde la raíz hasta las puntas "
        "gracias a sus ingredientes activos como la queratina, el té verde y el aceite de pracaxi. Devuelve la "
        "elasticidad y el brillo al cabello dañado."),
    "Reconstrucción y rejuvenecimiento Açaí Pra Você (Botox matizante)": (
        "Tratamiento de reconstrucción profunda diseñado para reparar, nutrir y dar brillo a cabellos dañados, "
        "secos o con frizz. Actúa directamente sobre la cutícula del cabello, aprovechando los beneficios del "
        "colágeno vegetal y el açaí para rejuvenecer la hebra capilar. Además, su efecto matizante corrige y "
        "enfría los tonos oxidados o amarillentos."),
    # Colorimetría
    "Balayage": (
        "Técnica de degradado a mano alzada que crea un efecto de iluminación natural. Mantiene la raíz de tu "
        "color natural o más oscura y aclara suavemente hacia las puntas, permitiendo un crecimiento sin marcas "
        "de raíz."),
    "Babylights + Baño de color": (
        "Reflejos ultrafinos y delicados que imitan el brillo natural del cabello de un bebé. Se complementa con "
        "un baño de color para unificar el tono, matizar y aportar un brillo extraordinario."),
    "Full babylight (Full Barbie)": (
        "Técnica de aclarado máximo que consiste en aplicar una cantidad muy abundante de micro-reflejos "
        "finísimos por toda la cabeza, desde la raíz hasta las puntas. El objetivo es lograr un rubio global "
        "extra claro, radiante y espectacular, pero manteniendo una delicada dimensión que evita el efecto "
        "artificial de una decoloración completa."),
    "Barrido de color": (
        "Técnica correctiva diseñada para extraer pigmentos artificiales no deseados del cabello. Ideal para "
        "aclarar ligeramente un tinte, eliminar reflejos estancados o preparar el lienzo del cabello antes de "
        "aplicar un nuevo color. Generalmente, es un proceso más suave y rápido que una decoloración tradicional "
        "o un decapado profundo."),
    "Reflejos en cabello natural": (
        "Técnica de iluminación suave diseñada específicamente para cabellos vírgenes. Consiste en aclarar "
        "sutilmente mechones seleccionados para aportar destellos de luz, dimensión y movimiento, simulando el "
        "aclarado natural que produce el sol. Es un servicio muy respetuoso con la fibra capilar, ideal para "
        "quienes buscan un primer cambio de look luminoso, sin alterar drásticamente su color de base."),
    "Shades EQ Redken": (
        "Coloración semipermanente que combina hidratación profunda con un extraordinario brillo efecto espejo. "
        "Es la alternativa perfecta para revitalizar tonos deslavados, neutralizar reflejos indeseados y matizar "
        "las canas aportándoles luz y dimensión. Todo esto garantizando el máximo cuidado de la fibra capilar, ya "
        "que no altera tu tono natural de base."),
    "Solo contorno": (
        "Iluminación enfocada en los mechones frontales alrededor del rostro. Sirve para realzar tus facciones y "
        "dar luz inmediata sin necesidad de decolorar todo el cabello."),
    "Color generalizado": (
        "Aplicación de tinte en todo el cabello de raíz a puntas. Ideal para cambiar de color por completo, "
        "emparejar tonos o cubrir canas en su totalidad con un acabado uniforme."),
    "Tintura visada": (
        "Combinación de color de base junto con iluminación (visos). Permite cubrir canas o cambiar tu tono base "
        "mientras se agregan destellos de luz para dar profundidad y movimiento en una sola sesión."),
    "Baño de color": (
        "Tratamiento suave que devuelve la vida, el brillo y la intensidad a cabellos teñidos que han perdido "
        "color con los lavados, neutralizando tonos no deseados."),
    "Babylights + Balayage": (
        "La combinación perfecta para máxima luminosidad. Mezcla la delicadeza de las babylights en la parte "
        "superior o raíz, con un degradado balayage hacia las puntas para un rubio radiante."),
    "Decapado": (
        "Proceso técnico para eliminar o barrer pigmentos de tintes anteriores. Es el paso previo indispensable "
        "cuando deseas pasar de un tono oscuro teñido a un color mucho más claro."),
    "Escondido": (
        "Iluminación o color fantasía aplicado únicamente en las capas inferiores y ocultas del cabello. El color "
        "solo se revela al mover el pelo, pasarlo tras la oreja o llevar un peinado recogido."),
    "Visos": (
        "Reflejos tradicionales y definidos que aportan luz y contraste desde el crecimiento hasta las puntas, "
        "ideal para romper con la monotonía de un solo color y dar sensación de mayor volumen."),
    "Adicional por tinturas INOA": (
        "Opción premium de coloración de L'Oréal. Es una tintura de lujo permanente, sin amoníaco y a base de "
        "aceites, ideal para cueros cabelludos sensibles, sin olor y con un máximo respeto por la hidratación del "
        "cabello."),
    "Diseños en fantasía": (
        "Aplicación de tonos vibrantes y creativos. Generalmente requiere decoloración previa para lucir un tono "
        "intenso y fiel al diseño personalizado."),
    "Mechas con papel": (
        "Técnica de iluminación utilizando papel aluminio para aislar los mechones. Permite lograr aclarados más "
        "precisos, intensos y definidos desde la raíz hasta las puntas."),
    "Raíz + Baño de color": (
        "Mantenimiento ideal que consiste en retocar el crecimiento de la raíz y aplicar un baño de color en los "
        "largos y puntas para refrescar el tono y devolver el brillo perdido."),
    # Aditivos protectores
    "Metal Detox": (
        "Aditivo de L'Oréal que neutraliza y elimina las micropartículas de metales acumuladas dentro de la fibra "
        "capilar. Evita el quiebre durante la decoloración y asegura un color final real y sin manchas."),
    "Olaplex": (
        "Se añade al tratamiento químico para proteger y reconstruir los enlaces internos del cabello en tiempo "
        "real, previniendo el daño y la rotura durante procesos como decoloración o tinturas."),
    # Masajes capilares y tratamientos de reposición
    "Máscara L'Oréal": (
        "Máscaras profesionales de hidratación y nutrición profunda adaptadas a la necesidad específica de tu "
        "cabello, dejándolo suave, desenredado y brillante de forma instantánea."),
    "Acidic Concentrate Redken": (
        "Tratamiento intensivo de Redken que equilibra, sella la cutícula y refuerza los puentes debilitados del "
        "cabello después de procesos químicos, devolviéndole su fuerza natural."),
    "Ritual de lujo Fusio-Dose Kérastase": (
        "Tratamiento molecular personalizado de Kérastase. Se mezcla un concentrado con un booster en el momento "
        "exacto para solucionar dos problemas a la vez con resultados inmediatos."),
    "Olaplex stand alone": (
        "Terapia de reconstrucción profunda en dos pasos, aplicada sin procesos de color. Diseñada para reparar "
        "cabellos severamente dañados, elásticos o procesados en exceso."),
    "4 en 1 Olaplex": (
        "Mascarilla altamente concentrada que aporta cuatro beneficios en un solo servicio: hidratación profunda, "
        "suavidad extrema, brillo intenso y cuerpo, sin aportar peso al cabello."),
    "Premiere Kérastase": (
        "Tratamiento de doble acción que elimina la acumulación de calcio que vuelve el pelo rígido y "
        "quebradizo, para luego reparar los enlaces de queratina desde el interior."),
    "Ampolla Mottita": (
        "Tratamiento ultra concentrado de acción rápida. Aporta una dosis intensa y directa de nutrientes, brillo "
        "y suavidad para revitalizar el cabello fatigado al instante."),
    "Adicionar ampolla Mottita a otro servicio": (
        "Complemento ideal para potenciar un corte o tintura. Se añade el contenido nutritivo de la ampolla en el "
        "lavapelos para sellar la fibra capilar tras tu servicio principal."),
    "Masaje Metal Detox adicional a otro servicio": (
        "Aplicación de la mascarilla y tratamiento detoxificante como cierre de otro servicio, protegiendo el "
        "cabello contra la opacidad y el quiebre causados por el agua y la contaminación diaria."),
}


def poner_descripciones(apps, schema_editor):
    Servicio = apps.get_model("core", "Servicio")
    for nombre, descripcion in DESCRIPCIONES.items():
        Servicio.objects.filter(nombre=nombre).update(descripcion=descripcion)


class Migration(migrations.Migration):
    dependencies = [("core", "0005_catalogo_carta")]

    operations = [migrations.RunPython(poner_descripciones, migrations.RunPython.noop)]
