# Task 2: containerize the Task 1 data-processing app (data_analysis.py).
# Multi-stage build keeps the final image small.

FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install \
    pandas matplotlib seaborn

FROM python:3.11-slim
WORKDIR /app
RUN useradd --create-home appuser
COPY --from=builder /install /usr/local
COPY data_analysis.py ./
COPY All_Diets.csv ./
USER appuser
CMD ["python", "data_analysis.py"]
