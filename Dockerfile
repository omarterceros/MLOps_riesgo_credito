# Imagen del servicio de inferencia (API FastAPI + cliente MLflow).
# El modelo no va dentro de la imagen: se carga desde el Model Registry al arrancar.
FROM python:3.13-slim

WORKDIR /app

# 1) Dependencias fijadas por version (capa cacheada mientras no cambie el archivo)
COPY requirements-servicio.txt .
RUN pip install --no-cache-dir -r requirements-servicio.txt

# 2) Codigo: el esquema compartido y el servicio
COPY comun/ comun/
COPY servicio/ servicio/

# 3) Usuario sin privilegios (MLflow necesita un HOME escribible para descargar el modelo)
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

ENV MLFLOW_TRACKING_URI=http://host.docker.internal:5050 \
    MODELO_NOMBRE=riesgo-credito \
    MODELO_ALIAS=champion \
    PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "servicio.api:app", "--host", "0.0.0.0", "--port", "8000"]
