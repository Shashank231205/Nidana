# Multi-stage. The runtime image carries no build toolchain.
#
# ENGINEERING_RULES section 6 requires base images pinned by digest rather than
# tag. PYTHON_IMAGE below is a tag, and must be replaced with the digest of a
# verified image before this builds anything a clinic runs:
#
#   docker pull python:3.11-slim-bookworm
#   docker inspect --format='{{index .RepoDigests 0}}' python:3.11-slim-bookworm
#
# A digest written from memory would be unverifiable and probably wrong, so the
# tag is left visible rather than a plausible-looking hash committed in its
# place.
ARG PYTHON_IMAGE=python:3.11-slim-bookworm

FROM ${PYTHON_IMAGE} AS build
WORKDIR /build
COPY pyproject.toml README.md ./
COPY spine ./spine
COPY services ./services
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
 && /opt/venv/bin/pip install --no-cache-dir .

FROM ${PYTHON_IMAGE} AS runtime

# Non-root. The application never needs to write outside its own data volume.
RUN groupadd --system --gid 1001 nidana \
 && useradd --system --uid 1001 --gid nidana --create-home nidana

COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY --chown=nidana:nidana spine ./spine
COPY --chown=nidana:nidana services ./services

USER nidana
EXPOSE 8000

# Fails the container rather than serving a half-configured deployment.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "services.consult.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
