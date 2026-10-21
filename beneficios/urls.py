from django.urls import path

from . import views

app_name = "beneficios"
urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("giftcards/nueva/", views.giftcard_nueva, name="giftcard_nueva"),
    path("giftcards/<int:pk>/", views.giftcard, name="giftcard"),
    path("giftcards/<int:pk>/deshabilitar/", views.giftcard_deshabilitar, name="giftcard_deshabilitar"),
    path("promociones/nueva/", views.promocion_form, name="promocion_nueva"),
    path("promociones/<int:pk>/editar/", views.promocion_form, name="promocion_editar"),
    path("promociones/<int:pk>/estado/", views.promocion_estado, name="promocion_estado"),
    path("promociones/vender/", views.vender_promocion, name="vender_promocion"),
    path("adquiridas/<int:pk>/", views.cliente_promocion, name="cliente_promocion"),
    path("adquiridas/<int:pk>/deshabilitar/", views.cliente_promocion_deshabilitar, name="cliente_promocion_deshabilitar"),
    path("fichas/<int:ficha_pk>/giftcard/", views.usar_giftcard, name="usar_giftcard"),
    path("fichas/<int:ficha_pk>/promocion/", views.usar_promocion, name="usar_promocion"),
]
