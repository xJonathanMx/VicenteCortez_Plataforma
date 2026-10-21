from django.urls import path

from . import views

app_name = "metas"
urlpatterns = [
    path("mias/", views.mias, name="mias"),
    path("panel/", views.panel, name="panel"),
    path("panel/guardar/", views.guardar_metas, name="guardar"),
    path("panel/cerrar/", views.cerrar, name="cerrar"),
    path("panel/niveles/", views.niveles, name="niveles"),
]
