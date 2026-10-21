from .models import RegistroAcceso


def _ip(request):
    if request is None:
        return None
    return request.META.get("REMOTE_ADDR")


def acceso_exitoso(sender, request, user, **kwargs):
    RegistroAcceso.objects.create(run_ingresado=user.run, usuario=user, exitoso=True, ip=_ip(request))


def acceso_fallido(sender, credentials, request=None, **kwargs):
    RegistroAcceso.objects.create(run_ingresado=(credentials.get("username") or "")[:20], exitoso=False,
                                  ip=_ip(request))
