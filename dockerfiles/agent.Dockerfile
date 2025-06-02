FROM python:3.11-slim
WORKDIR /app
COPY ../agent.py .
RUN pip install dockerfiles requests prometheus_client
CMD ["python", "agent.py"]
