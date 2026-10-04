FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8006
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd --create-home app && chown -R app /srv
USER app
EXPOSE 8006
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
