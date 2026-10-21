from django.urls import path

from . import views

app_name = "catalogo"
urlpatterns = [
    path("", views.servicios, name="servicios"),
    path("servicios/nuevo/", views.servicio_form, name="servicio_nuevo"),
    path("servicios/<int:pk>/", views.servicio_detalle, name="servicio"),
    path("servicios/<int:pk>/editar/", views.servicio_form, name="servicio_editar"),
    path("servicios/<int:pk>/estado/", views.servicio_estado, name="servicio_estado"),
    path("tipos/", views.tipos, name="tipos"),
    path("tipos/nuevo/", views.tipo_form, name="tipo_nuevo"),
    path("tipos/<int:pk>/editar/", views.tipo_form, name="tipo_editar"),
    path("tipos/<int:pk>/historial/", views.tipo_historial, name="tipo_historial"),
    path("tipos/<int:pk>/estado/", views.tipo_estado, name="tipo_estado"),
    path("insumos/", views.insumos, name="insumos"),
    path("insumos/nuevo/", views.insumo_form, name="insumo_nuevo"),
    path("insumos/<int:pk>/editar/", views.insumo_form, name="insumo_editar"),
    path("insumos/<int:pk>/estado/", views.insumo_estado, name="insumo_estado"),
]
