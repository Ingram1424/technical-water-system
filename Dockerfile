FROM python:3.10-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and folders
COPY api/ ./api/
COPY static/ ./static/
COPY templates/ ./templates/

# Expose the production port
EXPOSE 8000

# Run the app with uvicorn
CMD ["uvicorn", "api.index:app", "--host", "0.0.0.0", "--port", "8000"]
