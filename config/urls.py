"""
Todas las URLs de la plataforma en un solo archivo.

Cada sección mantiene su "namespace" (core:, clientes:, fichas:...) para que
los {% url 'fichas:detalle' ... %} de las plantillas y los reverse() del código
sigan funcionando igual que antes.
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

from beneficios import views as beneficios
from catalogo import views as catalogo
from clientes import views as clientes
from core import views as core
from core.forms import NuevaClaveForm, RecuperarForm
from fichas import views as fichas
from metas import views as metas
from reportes import views as reportes
from seguimiento import views as seguimiento

# ============================================================================
# 1. USUARIOS  (/usuarios/ — namespace "core")
# ============================================================================
urls_core = [
    path("", core.usuarios, name="usuarios"),
    path("nuevo/", core.usuario_form, name="usuario_nuevo"),
    path("acceso/<str:cual>/", core.catalogo_acceso, name="catalogo_acceso"),
    path("acceso/<str:cual>/nuevo/", core.catalogo_acceso_form, name="catalogo_acceso_nuevo"),
    path("acceso/<str:cual>/<int:pk>/", core.catalogo_acceso_form, name="catalogo_acceso_editar"),
    path("<str:run>/", core.usuario_detalle, name="usuario"),
    path("<str:run>/editar/", core.usuario_form, name="usuario_editar"),
    path("<str:run>/estado/", core.usuario_estado, name="usuario_estado"),
    path("<str:run>/clave/", core.usuario_clave, name="usuario_clave"),
]

# ============================================================================
# 2. CLIENTES  (/clientes/)
# ============================================================================
urls_clientes = [
    path("", clientes.buscar, name="buscar"),
    path("nuevo/", clientes.nuevo, name="nuevo"),
    path("<str:run>/", clientes.detalle, name="detalle"),
    path("<str:run>/editar/", clientes.editar, name="editar"),
    path("<str:run>/estilista/", clientes.estilista, name="estilista"),
    path("<str:run>/estado/", clientes.estado, name="estado"),
]

# ============================================================================
# 3. CATÁLOGO  (/catalogo/)
# ============================================================================
urls_catalogo = [
    path("", catalogo.servicios, name="servicios"),
    path("servicios/nuevo/", catalogo.servicio_form, name="servicio_nuevo"),
    path("servicios/<int:pk>/", catalogo.servicio_detalle, name="servicio"),
    path("servicios/<int:pk>/editar/", catalogo.servicio_form, name="servicio_editar"),
    path("servicios/<int:pk>/estado/", catalogo.servicio_estado, name="servicio_estado"),
    path("tipos/", catalogo.tipos, name="tipos"),
    path("tipos/nuevo/", catalogo.tipo_form, name="tipo_nuevo"),
    path("tipos/<int:pk>/editar/", catalogo.tipo_form, name="tipo_editar"),
    path("tipos/<int:pk>/historial/", catalogo.tipo_historial, name="tipo_historial"),
    path("tipos/<int:pk>/estado/", catalogo.tipo_estado, name="tipo_estado"),
    path("insumos/", catalogo.insumos, name="insumos"),
    path("insumos/nuevo/", catalogo.insumo_form, name="insumo_nuevo"),
    path("insumos/<int:pk>/editar/", catalogo.insumo_form, name="insumo_editar"),
    path("insumos/<int:pk>/estado/", catalogo.insumo_estado, name="insumo_estado"),
]

# ============================================================================
# 4. FICHAS DE ATENCIÓN  (/fichas/)
# ============================================================================
urls_fichas = [
    path("", fichas.lista, name="lista"),
    path("nueva/", fichas.nueva, name="nueva"),
    path("api/sugeridos/", fichas.api_sugeridos, name="sugeridos"),
    path("<int:pk>/", fichas.detalle, name="detalle"),
    path("<int:pk>/notas/", fichas.notas, name="notas"),
    path("<int:pk>/servicios/", fichas.agregar_servicio, name="agregar_servicio"),
    path("<int:pk>/cerrar/", fichas.cerrar, name="cerrar"),
    path("<int:pk>/validar/", fichas.validar, name="validar"),
    path("<int:pk>/anular/", fichas.anular, name="anular"),
    path("<int:pk>/corregir/", fichas.corregir, name="corregir"),
    path("<int:pk>/vincular/", fichas.vincular, name="vincular"),
    path("<int:pk>/versiones/<int:vid>/", fichas.version, name="version"),
    path("servicio/<int:pk>/iniciar/", fichas.iniciar, name="iniciar"),
    path("servicio/<int:pk>/terminar/", fichas.terminar, name="terminar"),
    path("servicio/<int:pk>/tiempo-manual/", fichas.tiempo_manual, name="tiempo_manual"),
    path("servicio/<int:pk>/quitar/", fichas.quitar_servicio, name="quitar_servicio"),
    path("servicio/<int:pk>/notas/", fichas.notas_servicio, name="notas_servicio"),
    path("servicio/<int:pk>/insumos/", fichas.agregar_insumo, name="agregar_insumo"),
    path("insumo/<int:pk>/quitar/", fichas.quitar_insumo, name="quitar_insumo"),
]

# ============================================================================
# 5. SEGUIMIENTO  (/seguimiento/)
# ============================================================================
urls_seguimiento = [
    path("", seguimiento.valoraciones, name="valoraciones"),
    path("recordatorios/", seguimiento.recordatorios, name="recordatorios"),
    path("procesar/", seguimiento.procesar, name="procesar"),
    path("reintentar/<str:tipo>/<int:pk>/", seguimiento.reintentar, name="reintentar"),
    path("canales/", seguimiento.canales, name="canales"),
    path("canales/vista-previa-valoracion/", seguimiento.vista_previa_valoracion, name="vista_previa_valoracion"),
]

# ============================================================================
# 6. METAS E INCENTIVOS  (/metas/)
# ============================================================================
urls_metas = [
    path("mias/", metas.mias, name="mias"),
    path("panel/", metas.panel, name="panel"),
    path("panel/guardar/", metas.guardar_metas, name="guardar"),
    path("panel/cerrar/", metas.cerrar, name="cerrar"),
    path("panel/niveles/", metas.niveles, name="niveles"),
]

# ============================================================================
# 7. BENEFICIOS: GIFTCARDS Y PROMOCIONES  (/beneficios/)
# ============================================================================
urls_beneficios = [
    path("", beneficios.inicio, name="inicio"),
    path("giftcards/nueva/", beneficios.giftcard_nueva, name="giftcard_nueva"),
    path("giftcards/<int:pk>/", beneficios.giftcard, name="giftcard"),
    path("giftcards/<int:pk>/deshabilitar/", beneficios.giftcard_deshabilitar, name="giftcard_deshabilitar"),
    path("promociones/nueva/", beneficios.promocion_form, name="promocion_nueva"),
    path("promociones/<int:pk>/editar/", beneficios.promocion_form, name="promocion_editar"),
    path("promociones/<int:pk>/estado/", beneficios.promocion_estado, name="promocion_estado"),
    path("promociones/vender/", beneficios.vender_promocion, name="vender_promocion"),
    path("adquiridas/<int:pk>/", beneficios.cliente_promocion, name="cliente_promocion"),
    path("adquiridas/<int:pk>/deshabilitar/", beneficios.cliente_promocion_deshabilitar,
         name="cliente_promocion_deshabilitar"),
    path("fichas/<int:ficha_pk>/giftcard/", beneficios.usar_giftcard, name="usar_giftcard"),
    path("fichas/<int:ficha_pk>/promocion/", beneficios.usar_promocion, name="usar_promocion"),
]

# ============================================================================
# 8. REPORTES  (/reportes/)
# ============================================================================
urls_reportes = [
    path("", reportes.inicio, name="inicio"),
    path("<slug:slug>/", reportes.reporte, name="reporte"),
]

# ============================================================================
# RUTAS PRINCIPALES
# ============================================================================
urlpatterns = [
    path("", RedirectView.as_view(pattern_name="inicio", permanent=False)),
    # Acceso y contraseña
    path("ingresar/", core.Login.as_view(), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("recuperar/", auth_views.PasswordResetView.as_view(form_class=RecuperarForm), name="password_reset"),
    path("recuperar/enviado/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("recuperar/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(form_class=NuevaClaveForm),
         name="password_reset_confirm"),
    path("recuperar/listo/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    path("inicio/", core.inicio, name="inicio"),
    path("ajustes/", core.ajustes, name="ajustes"),
    # Secciones (cada una con su namespace)
    path("usuarios/", include((urls_core, "core"))),
    path("clientes/", include((urls_clientes, "clientes"))),
    path("catalogo/", include((urls_catalogo, "catalogo"))),
    path("fichas/", include((urls_fichas, "fichas"))),
    path("seguimiento/", include((urls_seguimiento, "seguimiento"))),
    path("metas/", include((urls_metas, "metas"))),
    path("beneficios/", include((urls_beneficios, "beneficios"))),
    path("reportes/", include((urls_reportes, "reportes"))),
    # Enlace público que recibe el cliente para valorar su atención (sin sesión).
    path("valorar/<str:token>/", seguimiento.valorar_publico, name="valorar"),
    path("admin-django/", admin.site.urls),
]
