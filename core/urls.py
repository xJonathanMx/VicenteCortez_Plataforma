from django.urls import path

from . import views

app_name = "core"
urlpatterns = [
    path("", views.usuarios, name="usuarios"),
    path("nuevo/", views.usuario_form, name="usuario_nuevo"),
    path("acceso/<str:cual>/", views.catalogo_acceso, name="catalogo_acceso"),
    path("acceso/<str:cual>/nuevo/", views.catalogo_acceso_form, name="catalogo_acceso_nuevo"),
    path("acceso/<str:cual>/<int:pk>/", views.catalogo_acceso_form, name="catalogo_acceso_editar"),
    path("<str:run>/", views.usuario_detalle, name="usuario"),
    path("<str:run>/editar/", views.usuario_form, name="usuario_editar"),
    path("<str:run>/estado/", views.usuario_estado, name="usuario_estado"),
    path("<str:run>/clave/", views.usuario_clave, name="usuario_clave"),
]
