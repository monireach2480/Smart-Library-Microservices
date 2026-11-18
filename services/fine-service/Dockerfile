FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8007
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd --create-home app && chown -R app /srv
USER app
EXPOSE 8007
HEALTHCHECK --interval=20s --timeout=4s --start-period=25s --retries=3 \
  CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ['PORT'], timeout=3)"]
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
