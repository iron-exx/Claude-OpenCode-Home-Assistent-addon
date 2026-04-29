ARG BUILD_FROM=python:3.11-slim
FROM ${BUILD_FROM}

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for layer caching
COPY app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ /app/

# Make run script executable
COPY run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 8099

CMD ["/run.sh"]
