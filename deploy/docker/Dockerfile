# Policy service image (Phase 8). oss profile: Python standard library only, no
# third-party install needed, so the image is small and builds offline.
FROM python:3.11-slim

LABEL org.opencontainers.image.title="ai-semantic-guardrails-eu policy service" \
      org.opencontainers.image.description="Semantic Guard + /v1/check policy service (oss profile)." \
      org.opencontainers.image.source="https://github.com/Mirmansoorahmed/ai-semantic-guardrails-eu"

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    GUARDRAILS_HOST=0.0.0.0 \
    GUARDRAILS_PORT=8080 \
    ACA_PROFILE=oss

WORKDIR /app

# Copy the source and policy data needed at runtime.
COPY src/ ./src/
COPY policy/ ./policy/
COPY exemplars/ ./exemplars/
COPY config/ ./config/
COPY fixtures/ ./fixtures/
COPY pyproject.toml ./

# Run as a non-root user.
RUN useradd --create-home --uid 10001 guardrails && chown -R guardrails /app
USER guardrails

EXPOSE 8080

# Container healthcheck hits /healthz.
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD python3 -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2)" || exit 1

CMD ["python3", "-m", "aca.guard.api"]
