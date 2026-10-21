from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

from core import views as core_views
from core.forms import NuevaClaveForm, RecuperarForm
from seguimiento import views as seg_views

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="inicio", permanent=False)),
    path("ingresar/", core_views.Login.as_view(), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("recuperar/", auth_views.PasswordResetView.as_view(form_class=RecuperarForm), name="password_reset"),
    path("recuperar/enviado/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("recuperar/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(form_class=NuevaClaveForm),
         name="password_reset_confirm"),
    path("recuperar/listo/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    path("inicio/", core_views.inicio, name="inicio"),
    path("ajustes/", core_views.ajustes, name="ajustes"),
    path("usuarios/", include("core.urls")),
    path("clientes/", include("clientes.urls")),
    path("catalogo/", include("catalogo.urls")),
    path("fichas/", include("fichas.urls")),
    path("seguimiento/", include("seguimiento.urls")),
    path("metas/", include("metas.urls")),
    path("beneficios/", include("beneficios.urls")),
    path("reportes/", include("reportes.urls")),
    # Enlace público que recibe el cliente para valorar su atención (sin sesión).
    path("valorar/<str:token>/", seg_views.valorar_publico, name="valorar"),
    path("admin-django/", admin.site.urls),
]
