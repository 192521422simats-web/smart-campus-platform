FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
RUN mkdir -p /data
ENV DB_PATH=/data/campus.db
EXPOSE 5000
CMD ["python", "app.py"]
