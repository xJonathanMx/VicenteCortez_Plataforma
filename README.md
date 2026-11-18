# Ficha Digital – Peluquería Vicente Cortez (FD-VC)

Proyecto Capstone de Ingeniería en Informática, Duoc UC (sección 004D), 2026.

Sistema web para la Peluquería Vicente Cortez: fichas digitales de atención, seguimiento post-tratamiento por correo, metas e incentivos de peluqueros, giftcards, promociones y reportes.

## Descripción

**Problema.** La peluquería registra las atenciones en fichas de papel. Con unos 30 peluqueros, la información de cada cliente (servicios, productos, fórmulas y observaciones) queda dispersa o se pierde. No se puede consultar el historial al atender, no hay seguimiento de la satisfacción después del servicio y el cálculo de comisiones y metas es manual.

**Para quién.** Los peluqueros (internos y externos), recepción y la administración de la peluquería. La clienta es Violeta, de la Peluquería Vicente Cortez.

**Qué hace.** Cada peluquero registra la ficha desde el navegador de su celular: abre la atención, inicia y termina cada servicio con un toque y anota lo que usó. El sistema guarda el historial del cliente, envía por correo la valoración al día siguiente, calcula comisiones y metas con valores congelados y genera reportes en Excel y PDF.

## Equipo

| Integrante        | Rol Scrum            |
| ----------------- | -------------------- |
| Jonathan Molina   | Product Owner        |
| Benjamín Monsalve | Scrum Master         |
| Josefa Quirilao   | Equipo de Desarrollo |

Docentes: Mabel Herrera y Juan Pablo Mellado.

## Metodología

**Scrum.** Proyecto del 13/08/2026 al 14/12/2026, organizado en sprints. Cada ~15 días hay una reunión de seguimiento con la clienta, que funciona como Sprint Review. Cada historia se cierra con la [Definition of Done](https://github.com/xJonathanMx/Capstone_G5_VicenteCortez) del equipo: criterios de aceptación cumplidos, integrada por pull request y revisada por otro integrante, con pruebas aprobadas y documentación al día.

## Tecnologías

| Capa                | Tecnología                                                   |
| ------------------- | ------------------------------------------------------------ |
| Lenguaje            | Python 3.14                                                  |
| Backend             | Django 5.2 (ORM, autenticación, plantillas)                  |
| Frontend            | Plantillas de Django, Bootstrap 5.3, JavaScript, Lucide 0.460 |
| Base de datos       | PostgreSQL 16 (Supabase en la nube; contenedor local con Docker) |
| Servidor web        | Gunicorn 23 + WhiteNoise (archivos estáticos)                |
| Correo              | SMTP (Gmail u Outlook, configurable desde la plataforma)     |
| Reportes            | openpyxl (Excel) y ReportLab (PDF)                           |
| Despliegue          | Docker y Docker Compose                                      |
| Pruebas             | Django TestCase (109 pruebas)                                |

## Arquitectura

Arquitectura **cliente-servidor en capas**, como **monolito modular**: una sola aplicación Django dividida en módulos por área de requerimientos. Solo Django accede a la base de datos, a través del ORM.

```text
 Celular / navegador del peluquero
          │  HTTPS
          ▼
 ┌──────────────────────── Contenedor web ────────────────────────┐
 │ Gunicorn → Django                                               │
 │  Presentación: plantillas + Bootstrap (templates/, static/)     │
 │  Aplicación:   vistas y formularios por módulo                  │
 │                (clientes, fichas, catalogo, seguimiento,        │
 │                 metas, beneficios, reportes, core)              │
 │  Negocio:      servicios.py (reglas: precio congelado,          │
 │                permisos por rol, estados de ficha)              │
 │  Datos:        ORM de Django (core/models.py)                   │
 └───────────────┬─────────────────────────────────────────────────┘
                 │ SQL
                 ▼
 PostgreSQL (Supabase o contenedor db)
                 ▲
 ┌───────────────┴──── Contenedor envios ────┐        ┌──────────┐
 │ procesar_envios cada 15 minutos           │──SMTP─▶│ Correo   │
 │ (valoraciones y recordatorios)            │        │ cliente  │
 └───────────────────────────────────────────┘        └──────────┘
```

La documentación del proyecto (visión, historias de usuario, DAS, plan de pruebas, manual técnico y evidencias) está en el repositorio **[Capstone_G5_VicenteCortez](https://github.com/xJonathanMx/Capstone_G5_VicenteCortez)**.

---

## Funcionalidades

### Acceso y usuarios (`core`)

- **Inicio de sesión con RUN** (con o sin puntos, guion o dígito verificador) y contraseña. El error es siempre genérico («RUN o contraseña incorrectos») para no revelar si el RUN existe.
- **Recuperar contraseña** con un enlace enviado al correo registrado.
- **Roles múltiples**: Administrador, Recepción y Peluquero. Un usuario puede tener más de uno. Cada rol agrupa **privilegios** y el servidor los valida en cada acción (no basta con ocultar botones).
- **Crear y editar usuarios** en 4 secciones explicadas: datos personales, rol y acceso, especialidades y servicios que puede realizar (agrupados por tipo, con «Marcar todos»).
- **Deshabilitar y habilitar** usuarios con motivo obligatorio. No se eliminan y queda el historial de quién y cuándo.
- El administrador puede **restablecer la contraseña** de un usuario.
- Cada usuario actualiza su correo, teléfono y contraseña en **Ajustes**.
- **Inicio**:
  - Peluquero: sus servicios del día con botón grande de iniciar/terminar y cronómetro, más su meta del mes con la lista de incentivos.
  - Administración: resumen del día (atenciones, servicios en curso, fichas por validar, valoraciones pendientes), estado del equipo (disponible u ocupado) y alertas (servicios que exceden su tiempo, envíos fallidos, giftcards y promociones por vencer).

### Clientes (`clientes`)

- Registro con **validación de RUN y dígito verificador**. Si el RUN ya existe, muestra el cliente registrado.
- **Búsqueda** por RUN, nombre o apellido. Un peluquero solo ve a los clientes que ha atendido o registrado.
- **Ficha del cliente**: resumen (visitas, última visita, estilista fijo), giftcards y promociones vigentes, e **historial de atenciones** con servicios, peluquero, insumos, fórmula, observaciones y valoraciones.
- Asociar, cambiar o quitar el **estilista fijo**.
- Deshabilitar clientes con motivo, conservando su historial.

### Catálogo (`catalogo`)

- **Servicios** con precio por calidad (Básico, Plus, Ultra plus), tiempo estimado, días hasta la renovación y especialidades requeridas.
- **Tipos de servicio** con su regla de valoración (corte: 1 valoración; tratamiento: 2) y la **comisión por tipo de contrato**.
- **Insumos** (nombre, marca, calidad, unidad), sin control de stock y sin duplicados.
- **Históricos** que no se pueden editar ni borrar: cambios de precio, de comisión y de estado, con fecha y responsable.

### Fichas de atención (`fichas`)

- **Abrir ficha** desde recepción o por el peluquero. Si el cliente llega sin registro, se abre con un nombre provisorio y se **vincula después**.
- **Diagnóstico inicial** y observaciones, con confirmación «Guardado» junto al botón y aviso de «Cambios sin guardar».
- **Agregar servicios** a la ficha:
  - Primero se sugieren el estilista fijo y los especialistas, indicando si están disponibles u ocupados.
  - Solo aparecen peluqueros que tienen ese servicio habilitado.
  - Admite **tratamientos de varias sesiones**.
- **Precio y comisión congelados** al agregar el servicio: si después cambian en el catálogo, la ficha conserva los valores originales.
- **Iniciar y terminar** cada servicio con un botón grande; las horas quedan registradas solas.
  - Solo puede hacerlo el peluquero a cargo o administración.
  - Si el peluquero ya tiene otro servicio en curso, pide confirmación, porque se permite trabajar en paralelo por los tiempos de espera de los productos.
- **Insumos usados**, mezcla o fórmula y producto, por cada servicio.
- **Cierre manual** por administración (hora real y motivo) cuando un peluquero olvida terminar un servicio.
- **Estados de la ficha**: abierta → en atención → cerrada → validada (o anulada). Solo se cierra con todos los servicios terminados.
- **Validar**, **corregir** o **anular** con motivo obligatorio. Antes de cada cambio se guarda una copia de la ficha.
- **Trazabilidad**: cada cambio de estado con fecha, hora y usuario.
- **Giftcards y promociones en la ficha**: se eligen como tarjetas (código, saldo o usos restantes, vencimiento), con un resumen de total, pagado con giftcard, cubierto por promoción y lo que queda por pagar.

### Seguimiento (`seguimiento`)

- **Valoraciones automáticas** al cerrar la ficha: corte = 1 (día siguiente); tratamiento = 2 (día siguiente y fin de mes).
- **Correo con 5 estrellas**: cada estrella abre una página con esa nota ya marcada. El cliente confirma y puede dejar un comentario. Abrir el enlace no registra la nota, para evitar votos de antivirus que abren enlaces solos.
- **Recordatorios de renovación** (ej. tintura a los 45 días) y aviso de **giftcard por vencer**.
- Estados: pendiente, enviada, respondida, sin respuesta (a los 7 días) y error de envío. Hasta **3 reintentos**; los envíos fallidos se pueden reintentar a mano.
- Listado de valoraciones con filtros y **promedio por peluquero**.
- **Canales y mensajes**:
  - Plantillas editables.
  - **Cuenta de correo configurable desde la página**: Gmail, Outlook/Hotmail/Live u otro, con contraseña cifrada, nombre del remitente y «Responder a».
  - Correo de prueba, ejemplo de valoración y vista previa del correo.
- **Por ahora todo se envía por correo.** WhatsApp está programado pero apagado.

### Metas e incentivos (`metas`)

- **Meta mensual** de atenciones por peluquero, con una **lista de incentivos** («+ Agregar incentivo»):
  - **Dinero**: se informa proporcional al avance según la escala.
  - **Regalo o producto** (ej. kit de productos): se gana al cumplir el 100%.
  - **Otro beneficio** (ej. día libre): se gana al cumplir el 100%.
- **Escala de incentivo** editable (desde 80% → 50% del dinero, 100% → 100%, 120% → 130%).
- **Cerrar el mes** congela los resultados.
- **Comisiones** informativas de los peluqueros externos, calculadas con el precio y el porcentaje guardados en cada atención.
- Cada peluquero ve **su meta, su avance, sus incentivos y sus comisiones**.

### Giftcards y promociones (`beneficios`)

- **Giftcards** con código único, monto, comprador, beneficiario y vencimiento. Se descuentan desde la ficha validando saldo y vigencia, y pasan solas a agotada o vencida.
- **Promociones**: un catálogo (ej. «Pack Tintura» = 3 tinturas + 1 corte) y las promociones vendidas a cada cliente, con usos por servicio.
- Deshabilitar con motivo, conservando el historial. Todo es informativo: **no se procesan pagos**.

### Reportes (`reportes`)

14 reportes con filtros por fecha, peluquero y servicio, exportables a **Excel y PDF**:

- Atenciones, atenciones por peluquero y servicios más realizados.
- Uso de insumos, comisiones, metas e incentivos.
- Calidad de atención, recordatorios (tasa de entrega) y valoraciones.
- Digitalización de fichas, fichas con datos completos, uso del historial y accesos al sistema.
- Giftcards y promociones.

---

## Estilo visual

**Neumorfismo monocromático**, tomado del mockup aprobado. La interfaz usa una sola superficie de color y los elementos se distinguen por relieve, con luz desde arriba a la izquierda: las tarjetas y botones «salen» de la superficie, y los campos de texto «se hunden». El único acento es el color opuesto al fondo (negro en modo claro, blanco en modo oscuro). Así el logo de Vicente Cortez, negro y caligráfico, es lo que más destaca, y la interfaz no compite con él.

Reglas:

- **El color solo comunica estado** (verde = terminado o vigente, ámbar = por revisar, rojo = error o deshabilitado). Nada es de color por decoración.
- **El acento marca la acción principal o lo que está activo:** el menú seleccionado, el botón principal, el servicio en curso y las opciones elegidas.
- **Botones táctiles grandes** (56 px de alto) para iniciar y terminar servicios con un solo toque (RNF Usabilidad-02).
- **Tipografía:** [Hanken Grotesk](https://fonts.google.com/specimen/Hanken+Grotesk), una grotesca limpia y legible en celular que no compite con el logo manuscrito.
- **Íconos:** [Lucide](https://lucide.dev), de línea fina como los del mockup.
- **Mobile-first:** en celular el menú lateral pasa a un botón hamburguesa y las tablas se apilan como fichas.

### Componentes

| Componente              | Cómo se ve                                                        | Dónde                                                    |
| ----------------------- | ----------------------------------------------------------------- | -------------------------------------------------------- |
| Tarjetas                | En relieve, esquinas muy redondeadas                              | Todo el sistema                                          |
| Campos de texto         | Hundidos en la superficie                                         | Formularios                                              |
| Botón principal         | Negro (blanco en modo oscuro) con sombra                          | Guardar, Iniciar servicio                                |
| Botón secundario        | Mismo color de la superficie, en relieve                          | Volver, Filtrar, Editar                                  |
| Casillas                | Redondas y hundidas; al marcarse se rellenan con el acento y un ✓ | Roles, especialidades, servicios                         |
| Opciones                | Pastillas que se resaltan al elegirlas                            | Listas de selección múltiple                             |
| Tarjetas seleccionables | Con círculo de selección y borde del acento                       | Giftcards y promociones en la ficha                      |
| Estados                 | Pastilla pequeña con punto de color                               | Estado de fichas, servicios y envíos                     |
| Diálogo de confirmación | Tarjeta en relieve sobre fondo difuminado                         | Anular, quitar servicio, cerrar mes, iniciar en paralelo |
| Estrellas               | Hundidas sin marcar, en el acento al marcarlas                    | Página de valoración                                     |
| Correo de valoración    | Logo, saludo, 5 estrellas y botón negro                           | Correo al cliente                                        |

### Paleta

| Token       | Modo claro           | Modo oscuro       | Uso                                   |
| ----------- | -------------------- | ----------------- | ------------------------------------- |
| `--bg`      | `#E6E6E9` gris perla | `#26262B` grafito | Superficie única                      |
| `--luz`     | `#FFFFFF`            | `#323238`         | Brillo del relieve (arriba-izquierda) |
| `--sombra`  | `#C2C2C8`            | `#18181B`         | Sombra del relieve (abajo-derecha)    |
| `--tinta`   | `#000000` negro      | `#F4F4F6` blanco  | Acento, títulos y botón principal     |
| `--tinta-2` | `#2E2E33`            | `#D4D4D9`         | Texto normal                          |
| `--apagado` | `#6F6F76`            | `#9B9BA3`         | Texto secundario                      |
| `--ok`      | `#2F6E4A`            | `#8FD1A8`         | Terminado, vigente, disponible        |
| `--alerta`  | `#8A5A12`            | `#E8C27C`         | Por validar, enviada, vencida         |
| `--error`   | `#9B3328`            | `#F0A397`         | Error de envío, deshabilitado         |

Los colores están definidos como variables en [`static/css/app.css`](static/css/app.css). Para cambiar la paleta basta editar el bloque `:root` (claro) o `:root[data-theme="dark"]` (oscuro).

### Modo claro / oscuro

El botón con ícono de luna o sol, junto a la fecha (y en la esquina superior del login), cambia entre el modo claro y el oscuro. La elección se guarda en el dispositivo (`localStorage`). La primera vez se usa el modo del sistema del celular o computador. En modo oscuro el logo se invierte a blanco automáticamente.

---

## Levantar con Docker (recomendado)

Requisito: [Docker Desktop](https://www.docker.com/products/docker-desktop/) abierto («Engine running»).

```bash
copy .env.example .env
docker compose up -d --build
docker compose exec web python manage.py cargar_datos_iniciales --demo
```

En el `.env` cambia al menos `SECRET_KEY` y `POSTGRES_PASSWORD`. Luego abre http://localhost:8000 y entra con los usuarios demo de la tabla de abajo.

Se levantan 3 contenedores:

| Servicio | Qué hace                                                                  |
| -------- | ------------------------------------------------------------------------- |
| `web`    | La plataforma (Django + Gunicorn) en el puerto 8000. Aplica las migraciones al arrancar. |
| `db`     | PostgreSQL 16 local. Los datos quedan en el volumen `datos_postgres`.     |
| `envios` | Ejecuta `procesar_envios` cada 15 minutos (valoraciones y recordatorios). |

Comandos útiles:

```bash
docker compose ps                      # estado de los contenedores
docker compose logs -f web             # ver lo que pasa en la plataforma
docker compose exec web python manage.py test     # ejecutar las pruebas
docker compose exec web python manage.py createsuperuser
docker compose down                    # apagar (los datos se conservan)
docker compose down -v                 # apagar y BORRAR la base local
```

Para usar **Supabase** en vez del Postgres local, define `DATABASE_URL` y `DB_SSL=True` en el `.env`. Ojo: debe ir la misma `SECRET_KEY` con la que se guardó la contraseña del correo.

Para producción: `DEBUG=False`, `SECURE_SSL_REDIRECT=True`, el dominio en `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS`, y un proxy con certificado HTTPS delante del puerto 8000.

## Puesta en marcha sin Docker (local)

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

| Rol               | RUN          |
| ----------------- | ------------ |
| Administrador     | 11.111.111-1 |
| Recepción         | 15.555.555-6 |
| Peluquera externa | 16.666.666-K |
| Peluquero externo | 17.777.777-3 |
| Peluquera interna | 18.888.888-7 |

`migrate` ya deja creados, sin correr nada más: los roles y privilegios base, los administradores
Vicente y Violeta (sin contraseña: `python manage.py changepassword <RUN sin DV>`), los tipos de
contrato Interno/Externo y la carta de servicios con sus precios (migraciones `core/0002` a `0005`).
Sin `--demo`, `cargar_datos_iniciales` solo agrega estados, niveles, canales, plantillas e insumos.
Para crear otro administrador: `python manage.py createsuperuser` (pide el RUN completo, con DV).

Después de un `git pull` con cambios, ejecuta `pip install -r requirements.txt` y `python manage.py migrate`.

## Supabase

1. En Supabase: _Project Settings → Database → Connection string → URI_.
2. En `.env`: `DATABASE_URL=postgresql://...` y `DB_SSL=True`.
3. `python manage.py migrate` crea todas las tablas **con comentarios en cada tabla y columna** (diccionario de datos dentro de la BD, RNF Documentación).
4. Solo Django se conecta a la BD (RNF Seguridad-02): no expongas la `anon key` en el frontend.

## Correo, valoraciones y recordatorios

**Por ahora todos los mensajes se envían por correo electrónico.** El cliente necesita un correo registrado para recibir valoraciones y recordatorios; si no lo tiene, el envío queda con error para que administración lo complete.

**La cuenta de correo se configura desde la plataforma**: _Valoraciones → Canales y mensajes → Cuenta de correo_ (proveedor, correo, contraseña de aplicación, remitente y «Responder a»). Se puede cambiar en cualquier momento sin reiniciar. Mientras «Enviar correos reales» esté apagado, los correos solo se muestran en la consola del servidor.

- **Gmail**: verificación en 2 pasos + contraseña de aplicación en myaccount.google.com/apppasswords (las cuentas institucionales como @duocuc.cl no lo permiten).
- **Outlook / Hotmail / Live**: verificación en dos pasos + contraseña de aplicación en account.microsoft.com/security; servidor `smtp-mail.outlook.com`, puerto 587. Microsoft puede bloquear el envío desde programas externos; si pasa, enviar con Gmail y poner el @live en «Responder a».

La contraseña se guarda **cifrada** con una llave derivada de `SECRET_KEY`; si se cambia `SECRET_KEY`, hay que volver a escribirla en esa pantalla.

Los envíos programados se procesan con:

```bash
python manage.py procesar_envios
```

Con Docker esto ya lo hace el servicio `envios`. Sin Docker, prográmalo cada 15 minutos (Programador de tareas de Windows o cron). También está el botón «Enviar pendientes ahora» en _Valoraciones_.

Los enlaces de los correos usan `SITIO_URL` del `.env`. En local apuntan a `127.0.0.1` y solo funcionan en ese computador; al publicar la plataforma hay que poner su dirección pública.

WhatsApp está programado pero apagado. Para activarlo más adelante: `CANALES_ENVIO=email,whatsapp` y las credenciales `WHATSAPP_TOKEN` / `WHATSAPP_PHONE_ID`.

## Pruebas

```bash
python manage.py test
```

## Organización del código

Toda la base de datos y todas las direcciones están centralizadas:

- **`core/models.py`**: TODOS los modelos (tablas) del sistema en un solo archivo, ordenados por secciones (usuarios, clientes, catálogo, fichas, seguimiento, metas y beneficios). Hay una sola app de Django (`core`): la migración `0001_initial` crea las tablas y las siguientes solo cargan datos base.
- **`config/urls.py`**: TODAS las URLs en un solo archivo, separadas por sección. Cada sección conserva su *namespace* (`fichas:detalle`, `clientes:buscar`...).

El resto de las carpetas agrupan la lógica de cada módulo de requerimientos:

| Carpeta       | Módulos de requerimientos                                                                              |
| ------------- | ------------------------------------------------------------------------------------------------------ |
| `core`        | Autenticación (RF-AS), usuarios, roles y privilegios (RF-URP), panel de administración (RF-PA)         |
| `clientes`    | Clientes (RF-C)                                                                                        |
| `catalogo`    | Catálogo de servicios (RF-CS), insumos (RF-I), históricos (RF-HT), comisiones por tipo (RF-CI-01 a 03) |
| `fichas`      | Fichas de atención (RF-FA), ejecución del servicio (RF-ES)                                             |
| `seguimiento` | Valoraciones (RF-VS), recordatorios y canales (RF-RC)                                                  |
| `metas`       | Comisiones e incentivos (RF-CI)                                                                        |
| `beneficios`  | Giftcards (RF-GC), promociones (RF-PR)                                                                 |
| `reportes`    | Reportería (RF-RP)                                                                                     |

Dentro de cada carpeta: `forms.py` (formularios y validaciones), `views.py` (pantallas) y, en algunas, `servicios.py` (reglas de negocio). Las pantallas están en `templates/<app>/` y el estilo en `static/css/app.css`.

## Reglas de negocio a confirmar con la peluquería

- Las valoraciones se programan al **cerrar** la ficha (con todos los servicios terminados), no al abrirla.
- «Atención» para la meta = ficha no anulada en que el peluquero terminó al menos un servicio en el mes.
- Escala de incentivo inicial: desde 80% → 50%, 100% → 100%, 120% → 130% del dinero (editable).
- Solo el peluquero a cargo o administración inician y terminan un servicio. Si recepción también debe hacerlo, se le da el privilegio correspondiente.
- Un peluquero puede tener servicios en paralelo (tiempos de espera); el sistema pide confirmación.
- Los mensajes a clientes salen solo por correo.
- El logo (`static/img/logo.png`) se extrajo del mockup; reemplázalo por el archivo original para máxima nitidez.
