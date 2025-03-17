FROM python:3.9-slim

WORKDIR /app

# Install required packages including netcat-openbsd
RUN apt-get update && apt-get install -y netcat-openbsd && apt-get clean

# Copy common module first
COPY ./common/src /app/common/

# Copy client code
COPY ./client/src /app/

# Install required packages
RUN pip install --no-cache-dir flask flask_cors requests uuid

# Expose the port the client will run on
EXPOSE 8000

# Set entrypoint
CMD ["python", "-m", "main"]