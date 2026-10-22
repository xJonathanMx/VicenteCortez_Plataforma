from django.urls import path

from . import views

app_name = "seguimiento"
urlpatterns = [
    path("", views.valoraciones, name="valoraciones"),
    path("recordatorios/", views.recordatorios, name="recordatorios"),
    path("procesar/", views.procesar, name="procesar"),
    path("reintentar/<str:tipo>/<int:pk>/", views.reintentar, name="reintentar"),
    path("canales/", views.canales, name="canales"),
    path("canales/vista-previa-valoracion/", views.vista_previa_valoracion, name="vista_previa_valoracion"),
]
