### Build privacyidea container including gssapi (Kerberos) and hsm

### build stage
###
FROM cgr.dev/chainguard/wolfi-base AS builder

ARG PYVERSION=3.12

ENV LANG=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/ort/.poetry/bin:${PATH}"



WORKDIR /ort
RUN apk add python-${PYVERSION} wget && \
        chown -R nonroot:nonroot /ort/

USER nonroot


RUN wget -O get-poetry.py https://install.python-poetry.org && \
    export POETRY_HOME=/ort/.poetry && python3 get-poetry.py && \
    rm get-poetry.py

COPY poetry.lock pyproject.toml README.md ./
COPY app/ /ort/app

ENV PATH="/ort/.poetry/bin:${PATH}"
RUN poetry config virtualenvs.in-project true && \
    poetry install --no-root


COPY .env /ort/.env

### final stage
###
FROM cgr.dev/chainguard/wolfi-base

ARG PYVERSION=3.12
ENV PYTHONUNBUFFERED=1
ENV PATH="/ort/.poetry/bin:${PATH}"
ENV POETRY_HOME="/ort/.poetry"
LABEL maintainer="Marco Moenig <info@moenig.it>"
#LABEL org.opencontainers.image.source="https://github.com/gpappsoft/"
#LABEL org.opencontainers.image.url="https://github.com/gpappsoft/"
LABEL org.opencontainers.image.description="ORT - open route tracker"


WORKDIR /ort

RUN apk add python-${PYVERSION} 

COPY --from=builder /ort/ /ort
USER nonroot
EXPOSE ${PORT}


ENTRYPOINT ["poetry", "run","uvicorn", "--workers", "4", "--host", "0.0.0.0", "--port", "5000", "app.main:app"]