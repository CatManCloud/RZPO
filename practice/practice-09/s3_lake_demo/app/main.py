from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import boto3
import os
import json
from typing import List, Any
from botocore.exceptions import ClientError

app = FastAPI(title="S3 Data Lake Service")

# Конфигурация S3 из переменных окружения
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://minio:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin123")
S3_BUCKET = os.getenv("S3_BUCKET", "data-lake-bucket")

# Создание клиента S3
s3_client = boto3.client(
    's3',
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    region_name='us-east-1'
)


class S3Object(BaseModel):
    key: str
    size: int
    last_modified: str


@app.get("/")
async def root():
    return {"message": "S3 Data Lake Service is running!"}


@app.get("/buckets/")
async def list_buckets():
    """Получение списка всех бакетов"""
    try:
        response = s3_client.list_buckets()
        return {"buckets": [b['Name'] for b in response['Buckets']]}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/objects/")
async def list_objects(prefix: str = "", file_type: str = ""):
    """Получение списка объектов в бакете (с фильтром по расширению)"""
    try:
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)
        objects = []
        for obj in response.get('Contents', []):
            # Фильтрация на стороне сервиса по расширению
            if file_type and not obj['Key'].lower().endswith('.' + file_type.lower()):
                continue
            objects.append(S3Object(
                key=obj['Key'],
                size=obj['Size'],
                last_modified=obj['LastModified'].isoformat()
            ))
        return {"objects": objects, "count": len(objects)}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/objects/{key}")
async def get_object(key: str):
    """Получение содержимого объекта по ключу"""
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=key)
        content = response['Body'].read().decode('utf-8')

        # Попытка распарсить JSON
        try:
            data = json.loads(content)
            return {"key": key, "data": data, "content_type": "json"}
        except json.JSONDecodeError:
            return {"key": key, "data": content, "content_type": "text"}
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            raise HTTPException(status_code=404, detail=f"Object '{key}' not found")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload/")
async def upload_object(key: str, content: str):
    """Загрузка объекта в бакет"""
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=content.encode('utf-8')
        )
        return {"message": f"Object '{key}' uploaded successfully"}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/aggregate/")
async def aggregate_data():
    """Чтение всех JSON-файлов из бакета и агрегация"""
    try:
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET)
        results = []
        for obj in response.get('Contents', []):
            key = obj['Key']
            if key.endswith('.json'):
                resp = s3_client.get_object(Bucket=S3_BUCKET, Key=key)
                content = resp['Body'].read().decode('utf-8')
                try:
                    data = json.loads(content)
                    results.append({"file": key, "data": data})
                except json.JSONDecodeError:
                    results.append({"file": key, "error": "Invalid JSON"})
        return {"files_processed": len(results), "data": results}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


from fastapi.responses import StreamingResponse


@app.get("/download/{key}")
async def download_object(key: str):
    """Скачивание файла из S3 как вложения"""
    try:
        obj = s3_client.get_object(Bucket=S3_BUCKET, Key=key)
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            raise HTTPException(status_code=404, detail=f"Object '{key}' not found")
        raise HTTPException(status_code=500, detail=str(e))

    return StreamingResponse(
        obj['Body'].iter_chunks(chunk_size=8192),
        media_type=obj.get('ContentType', 'application/octet-stream'),
        headers={"Content-Disposition": f'attachment; filename="{key}"'}
    )


from fastapi import UploadFile, File
from boto3.s3.transfer import TransferConfig


class ProgressLogger:
    """Простой прогресс-бар: печатает проценты в лог контейнера"""
    def __init__(self, total):
        self.total = total
        self.uploaded = 0

    def __call__(self, bytes_amount):
        self.uploaded += bytes_amount
        percent = self.uploaded / self.total * 100 if self.total else 100
        print(f"Upload progress: {percent:.1f}%", flush=True)


@app.post("/upload-file/")
async def upload_file(file: UploadFile = File(...)):
    """Загрузка файла в S3 частями (multipart, несколько потоков)"""
    config = TransferConfig(
        multipart_threshold=5 * 1024 * 1024,   # файлы > 5 МБ грузятся частями
        multipart_chunksize=5 * 1024 * 1024,   # размер одной части
        max_concurrency=4,
        use_threads=True,
    )
    # Определяем размер файла для прогресса
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    try:
        s3_client.upload_fileobj(
            file.file,
            S3_BUCKET,
            file.filename,
            Config=config,
            ExtraArgs={"ContentType": file.content_type or "application/octet-stream"},
            Callback=ProgressLogger(size),
        )
        return {"message": f"File '{file.filename}' uploaded", "size_bytes": size}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))
