# Plataforma Vicente Cortez: ficha digital

Django 5.2 + Bootstrap 5 + Supabase (Postgres). Mobile-first, con el estilo neumórfico del mockup.

## Estilo visual

**Neumorfismo monocromático**, tomado del mockup aprobado. La interfaz usa una sola superficie de color y los elementos se distinguen por relieve, con luz desde arriba a la izquierda: las tarjetas y botones "salen" de la superficie, y los campos de texto y la fecha están "hundidos". El único acento es el color opuesto al fondo (negro en modo claro, blanco en modo oscuro). Así el logo de Vicente Cortez, que es negro y caligráfico, es lo que más destaca, y la interfaz no compite con él.

Reglas:
- **El color solo comunica estado** (verde = terminado o vigente, ámbar = por revisar, rojo = error o deshabilitado). Nada es de color por decoración.
- **El acento marca la acción principal o lo que está activo:** el menú seleccionado, el botón principal y el servicio en curso.
- **Botones táctiles grandes** (56 px de alto) para iniciar y terminar servicios con un solo toque (RNF Usabilidad-02).
- **Tipografía:** [Hanken Grotesk](https://fonts.google.com/specimen/Hanken+Grotesk), una grotesca limpia y legible en celular que no compite con el logo manuscrito.
- **Íconos:** [Lucide](https://lucide.dev), de línea fina como los del mockup.
- **Mobile-first:** en celular el menú lateral pasa a un botón hamburguesa y las tablas se apilan como fichas.

### Paleta

| Token | Modo claro | Modo oscuro | Uso |
|---|---|---|---|
| `--bg` | `#E6E6E9` gris perla | `#26262B` grafito | Superficie única |
| `--luz` | `#FFFFFF` | `#323238` | Brillo del relieve (arriba-izquierda) |
| `--sombra` | `#C2C2C8` | `#18181B` | Sombra del relieve (abajo-derecha) |
| `--tinta` | `#000000` negro | `#F4F4F6` blanco | Acento, títulos y botón principal |
| `--tinta-2` | `#2E2E33` | `#D4D4D9` | Texto normal |
| `--apagado` | `#6F6F76` | `#9B9BA3` | Texto secundario |
| `--ok` | `#2F6E4A` | `#8FD1A8` | Terminado, vigente, disponible |
| `--alerta` | `#8A5A12` | `#E8C27C` | Por validar, enviada, vencida |
| `--error` | `#9B3328` | `#F0A397` | Error de envío, deshabilitado |

Los colores están definidos como variables en [`static/css/app.css`](static/css/app.css). Para cambiar la paleta basta editar el bloque `:root` (claro) o `:root[data-theme="dark"]` (oscuro).

### Modo claro / oscuro

El botón con ícono de luna o sol, junto a la fecha (y en la esquina superior del login), cambia entre el modo claro y el oscuro. La elección se guarda en el dispositivo (`localStorage`). La primera vez se usa el modo del sistema del celular o computador. En modo oscuro el logo se invierte a blanco automáticamente.

## Puesta en marcha (local)

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py cargar_datos_iniciales --demo
python manage.py runserver
```

Sin `DATABASE_URL` usa SQLite. Usuarios demo (clave `Peluqueria2026`):

| Rol | RUN |
|---|---|
| Administrador | 11.111.111-1 |
| Recepción | 15.555.555-6 |
| Peluquera externa | 16.666.666-K |
| Peluquero externo | 17.777.777-3 |
| Peluquera interna | 18.888.888-7 |

Sin `--demo` solo se cargan roles, privilegios, estados, canales, plantillas y el catálogo base.
Para crear el primer administrador real: `python manage.py createsuperuser` (pide RUN con DV).

## Supabase

1. En Supabase: *Project Settings → Database → Connection string → URI*.
2. En `.env`: `DATABASE_URL=postgresql://...` y `DB_SSL=True`.
3. `python manage.py migrate` crea todas las tablas **con comentarios en cada tabla y columna** (diccionario de datos dentro de la BD, RNF Documentación).
4. Solo Django se conecta a la BD (RNF Seguridad-02): no expongas la `anon key` en el frontend.

## Envíos automáticos (valoraciones y recordatorios)

```bash
python manage.py procesar_envios
```

Prográmalo cada 15 minutos (Programador de tareas de Windows o cron). También hay un botón «Enviar pendientes ahora» en *Valoraciones*.
**Por ahora todos los mensajes se envían por correo electrónico.** El cliente necesita un correo registrado para recibir valoraciones y recordatorios; si no lo tiene, el envío queda marcado con error para que administración lo complete.
**La cuenta de correo se configura desde la plataforma**: *Valoraciones → Canales y mensajes → Cuenta de correo* (proveedor, correo, contraseña de aplicación y nombre del remitente). Se puede cambiar en cualquier momento sin reiniciar. Mientras «Enviar correos reales» esté apagado, los correos solo se muestran en la consola del servidor. El botón «Enviar correo de prueba» confirma que funciona.
- **Gmail**: verificación en 2 pasos + contraseña de aplicación en myaccount.google.com/apppasswords (las cuentas institucionales como @duocuc.cl no lo permiten).
- **Outlook / Hotmail / Live**: verificación en dos pasos + contraseña de aplicación en account.microsoft.com/security; servidor `smtp-mail.outlook.com`, puerto 587. Microsoft puede bloquear el envío desde programas externos; si pasa, enviar con Gmail y poner el @live en «Responder a».

La contraseña se guarda **cifrada** en la base de datos con una llave derivada de `SECRET_KEY`; si se cambia `SECRET_KEY`, hay que volver a escribir la contraseña en esa pantalla.
WhatsApp está programado pero apagado. Para activarlo más adelante: `CANALES_ENVIO=email,whatsapp` y las credenciales `WHATSAPP_TOKEN` / `WHATSAPP_PHONE_ID`.

## Pruebas

```bash
python manage.py test
```

## Módulos y requerimientos

| App | Cubre |
|---|---|
| `core` | Login por RUN, roles múltiples, privilegios validados en servidor, usuarios, especialidades, servicios habilitados (RF-AS, RF-URP, RF-PA) |
| `clientes` | Registro con validación de RUN, búsqueda, historial, resumen, estilista fijo (RF-C) |
| `catalogo` | Servicios, tipos, precios por calidad, comisiones por contrato, insumos e históricos (RF-CS, RF-I, RF-HT, RF-CI-01..03) |
| `fichas` | Fichas, servicios, iniciar/terminar, cierre manual, multisesión, validación, anulación y versiones (RF-FA, RF-ES) |
| `seguimiento` | Valoraciones 1/2 según regla, recordatorios de renovación, canales, plantillas, reintentos (RF-VS, RF-RC) |
| `metas` | Metas mensuales, escala de incentivos, cierre de mes, comisiones (RF-CI) |
| `beneficios` | Giftcards y promociones (RF-GC, RF-PR) |
| `reportes` | 14 reportes con filtros y exportación a Excel/PDF (RF-RP) |

Decisiones tomadas que conviene confirmar con la peluquería:
- Las valoraciones se programan al **cerrar** la ficha (cuando todos los servicios terminaron), no al abrirla.
- «Atención» para la meta = ficha no anulada en que el peluquero terminó al menos un servicio en el mes.
- Escala de incentivo inicial: desde 80 % → 50 %, 100 % → 100 %, 120 % → 130 % del incentivo base (editable).
- El logo (`static/img/logo.png`) se extrajo del mockup; reemplázalo por el archivo original para máxima nitidez.
