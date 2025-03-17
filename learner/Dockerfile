FROM python:3.9-slim

WORKDIR /app

# Copy common module first
COPY ./common/src /app/common/

# Copy learner code
COPY ./learner/src /app/

# Install required packages
RUN pip install --no-cache-dir flask flask_cors requests uuid

# Create volume for learner data
VOLUME /data

# Expose the port the learner will run on
EXPOSE 7000

# Set entrypoint
CMD ["python", "-m", "main"]
