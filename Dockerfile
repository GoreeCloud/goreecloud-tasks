# GoreeCloud Tasks application image.
# The exact Python release and multi-platform image digest are intentionally pinned.
FROM python:3.13.14-slim-bookworm@sha256:9d7f287598e1a5a978c015ee176d8216435aaf335ed69ac3c38dd1bbb10e8d64

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --requirement requirements.txt

RUN useradd \
    --create-home \
    --uid 10001 \
    --shell /usr/sbin/nologin \
    goreecloud

COPY --chown=goreecloud:goreecloud . /app

USER goreecloud

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/', timeout=3)"]

CMD ["gunicorn", "goreecloud_tasks.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "--error-logfile", "-"]
