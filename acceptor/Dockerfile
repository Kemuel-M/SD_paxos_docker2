FROM python:3.9-slim

WORKDIR /app

# Copy common module first
COPY ./common/src /app/common/

# Copy acceptor code
COPY ./acceptor/src /app/

# Install required packages
RUN pip install --no-cache-dir flask flask_cors requests uuid

# Create volume for acceptor data
VOLUME /data

# Expose the port the acceptor will run on
EXPOSE 5000

# Set entrypoint
CMD ["python", "-m", "main"]
