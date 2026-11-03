FROM python:3.12-slim AS app
WORKDIR /app
RUN pip install --no-cache-dir fastapi==0.115.6 'uvicorn[standard]==0.34.0' 'boto3>=1.34,<2'
COPY src/lambdas/api_handler/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY src/ /app/src/
COPY local/ /app/local/
COPY scripts/ /app/scripts/
ENV PYTHONPATH=/app/src/lambdas/api_handler:/app
ENV PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["sh", "/app/local/start.sh"]

FROM app AS test
COPY requirements-dev.txt /app/requirements-dev.txt
RUN pip install --no-cache-dir -r /app/requirements-dev.txt
COPY tests/ /app/tests/
COPY deployment_resources.json /app/deployment_resources.json
COPY syndicate/syndicate_aliases.yml /app/syndicate/syndicate_aliases.yml
CMD ["sh", "-c", "python -m unittest discover -s tests -v && python -m unittest local.test_local scripts.test_cloud -v"]
