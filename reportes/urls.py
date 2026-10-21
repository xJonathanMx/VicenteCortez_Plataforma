from django.urls import path

from . import views

app_name = "reportes"
urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("<slug:slug>/", views.reporte, name="reporte"),
]
