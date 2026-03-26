FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir uv \
    && uv pip install --system --no-cache -r requirements.txt \
    && uv pip install --system --no-cache gunicorn

COPY . .

EXPOSE 5001

CMD ["gunicorn", "--workers", "2", "--threads", "4", "--bind", "0.0.0.0:5001", "run:app"]
