FROM python:3.10-slim
WORKDIR /app
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*
COPY . .
RUN pip install --no-cache-dir -r backend/requirements.txt
RUN pip install --no-cache-dir gdown
RUN chmod +x backend/startup.sh
EXPOSE 7860
CMD ["/bin/bash", "backend/startup.sh"]
