FROM python:3.13-slim

# Install Node.js and npx for Filesystem MCP server
RUN apt-get update && \
    apt-get install -y nodejs npm && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Create reports directory
RUN mkdir -p /app/reports

# Set reports directory for Cloud Run
ENV REPORTS_DIR=/app/reports

EXPOSE 5000

CMD ["python", "app/server.py"]
