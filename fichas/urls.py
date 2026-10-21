from django.urls import path

from . import views

app_name = "fichas"
urlpatterns = [
    path("", views.lista, name="lista"),
    path("nueva/", views.nueva, name="nueva"),
    path("api/sugeridos/", views.api_sugeridos, name="sugeridos"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/notas/", views.notas, name="notas"),
    path("<int:pk>/servicios/", views.agregar_servicio, name="agregar_servicio"),
    path("<int:pk>/cerrar/", views.cerrar, name="cerrar"),
    path("<int:pk>/validar/", views.validar, name="validar"),
    path("<int:pk>/anular/", views.anular, name="anular"),
    path("<int:pk>/corregir/", views.corregir, name="corregir"),
    path("<int:pk>/vincular/", views.vincular, name="vincular"),
    path("<int:pk>/versiones/<int:vid>/", views.version, name="version"),
    path("servicio/<int:pk>/iniciar/", views.iniciar, name="iniciar"),
    path("servicio/<int:pk>/terminar/", views.terminar, name="terminar"),
    path("servicio/<int:pk>/cierre-manual/", views.cierre_manual, name="cierre_manual"),
    path("servicio/<int:pk>/quitar/", views.quitar_servicio, name="quitar_servicio"),
    path("servicio/<int:pk>/notas/", views.notas_servicio, name="notas_servicio"),
    path("servicio/<int:pk>/insumos/", views.agregar_insumo, name="agregar_insumo"),
    path("insumo/<int:pk>/quitar/", views.quitar_insumo, name="quitar_insumo"),
]
