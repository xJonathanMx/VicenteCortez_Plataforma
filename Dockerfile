# Imagen de la plataforma Ficha Digital – Peluquería Vicente Cortez (FD-VC).
# Construir:  docker build -t fdvc .
# Normalmente se usa a través de docker-compose.yml (ver README).

# 1. Base: Python liviano, la misma versión con la que desarrolla el equipo.
FROM python:3.14-slim

# 2. Python sin archivos .pyc y con salida inmediata a los logs del contenedor.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 3. Dependencias primero: Docker reutiliza esta capa mientras requirements.txt no cambie.
COPY requirements.txt .
RUN pip install -r requirements.txt

# 4. Código del proyecto (lo que excluye .dockerignore no entra a la imagen).
COPY . .

# 5. Archivos estáticos (CSS, JS, imágenes) listos para servirlos con WhiteNoise.
#    La clave es solo para este paso de construcción; la real llega por variable de entorno.
RUN SECRET_KEY=solo-para-collectstatic DEBUG=False python manage.py collectstatic --noinput

# 6. Usuario sin privilegios: si alguien vulnera la app, no es root dentro del contenedor.
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# 7. Al arrancar: aplica migraciones pendientes y levanta Gunicorn (servidor de producción).
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 60 --access-logfile -"]
