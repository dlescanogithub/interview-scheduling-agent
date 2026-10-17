FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY data ./data
COPY scenarios ./scenarios

RUN pip install --no-cache-dir .

USER nobody
ENTRYPOINT ["python", "-m", "scheduling_agent"]
CMD ["demo"]
