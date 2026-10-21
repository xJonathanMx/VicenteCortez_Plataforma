from django.urls import path

from . import views

app_name = "clientes"
urlpatterns = [
    path("", views.buscar, name="buscar"),
    path("nuevo/", views.nuevo, name="nuevo"),
    path("<str:run>/", views.detalle, name="detalle"),
    path("<str:run>/editar/", views.editar, name="editar"),
    path("<str:run>/estilista/", views.estilista, name="estilista"),
    path("<str:run>/estado/", views.estado, name="estado"),
]
