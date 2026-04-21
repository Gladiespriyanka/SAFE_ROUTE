FROM python:3.11-slim

# 1) System deps so numpy/pandas/scikit-learn/shap can build if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    python3-dev \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2) Copy only requirements first (better cache)
COPY backend/requirements.txt backend/requirements.txt

# 3) Upgrade pip and install Python deps
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r backend/requirements.txt

# 4) Copy the rest of your code
COPY . .

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]