from django.core.management.base import BaseCommand

from seguimiento.servicios import procesar_pendientes


class Command(BaseCommand):
    help = "Envía valoraciones y recordatorios programados para hoy o antes, y actualiza estados vencidos."

    def handle(self, *args, **opts):
        r = procesar_pendientes()
        self.stdout.write(self.style.SUCCESS(
            f"Valoraciones enviadas: {r['valoraciones']}; recordatorios enviados: {r['recordatorios']}; "
            f"fallidos: {r['fallidos']}; marcadas sin respuesta: {r['sin_respuesta']}; "
            f"avisos de giftcard programados: {r['avisos_giftcard']}."))
