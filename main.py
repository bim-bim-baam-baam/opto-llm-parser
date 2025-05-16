import logging
import requests
import asyncio
from fastapi import FastAPI
from fastapi import UploadFile, File
from typing import List
from models import AnalysisResult
from database import database, results
import redis.asyncio as redis
import os
import json
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")
REDIS_CACHE_KEY = "cached_results"
REDIS_TTL = 60

redis_client = redis.from_url(REDIS_URL)
app = FastAPI()

API_KEY = os.getenv("API_KEY")
API_URL = "https://api.intelligence.io.solutions/api/v1/chat/completions"
AI_MODEL = "deepseek-ai/DeepSeek-R1"

LOGS_DIR = "logs/"
RESULTS_DIR = "results/"

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

SYSTEM_PROMPT = (
    "Ты эксперт в анализе логов сборки Linux-пакетов. "
    "Тебе даются фрагменты логов пакетов с фрагментами ошибок. "
    "На их основе сформируй краткий JSON-ответ с 5 полями:\n"
    "1. path - путь к логу, \n"
    "2. package — имя пакета,\n"
    "3. error_type — узкая категория ошибки. если получено несколько ошибок разных категорий для одного пакета,"
    " то может быть указано несколько категорий через запятую,\n"
    "4. programming_language - фильтрация по языку программирования, \n"
    "5. description — подробное описание ошибки, включая основную причину сбоя и её контекст.\n"
    "Пример ответа:\n"
    "{\n"
    "  \"path\": \"https://git.altlinux.org/beehive/logs/Sisyphus/i586/latest/error/example-pkg\", \n"
    "  \"package\": \"example-pkg\",\n"
    "  \"error_type\": \"cmake\",\n"
    "  \"programming_language\": \"C++\", \n"
    "  \"description\": \"Ошибка конфигурации CMake: недопустимый аргумент в cmake_minimum_required."
    " Версия CMake слишком старая.\"\n"
    "}\n"
    "Отвечай только в этом формате и только на английском языке. error_type часто будет cmake, "
    "поэтому детальнее указывай error_type. Нам важно потом в другом сервисе выделять кластеры по этим error_type."
)

@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


async def save_result_to_db(result: AnalysisResult):
    query = results.select().where(results.c.path == result.path)
    existing = await database.fetch_one(query)
    if existing:
        logging.info(f"Уже есть: {result.path}")
        return False
    query = results.insert().values(**result.dict())
    await database.execute(query)
    logging.info(f"Сохранили: {result.path}")
    return True


@app.post("/upload_log_and_analyze")
async def upload_log_and_analyze(file: UploadFile = File(...)):
    content = await file.read()
    filename = file.filename
    logs_path = os.path.join(LOGS_DIR, filename)

    # Сохраняем файл (если уже существует — обновляется)
    with open(logs_path, "wb") as f:
        f.write(content)

    # После сохранения файла — можно запустить анализ
    await process_log_and_query_ai(filename)

    return {"status": "uploaded", "filename": filename}


@app.post("/upload_log")
async def upload_log(file: UploadFile = File(...)):
    content = await file.read()
    filename = file.filename
    logs_path = os.path.join(LOGS_DIR, filename)

    # Сохраняем файл (если уже существует — обновляется)
    with open(logs_path, "wb") as f:
        f.write(content)

    return {"status": "uploaded", "filename": filename}


async def process_log_and_query_ai(filename: str):
    await database.connect()

    filepath = os.path.join(LOGS_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        log_text = f.read()

    data = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": log_text}
        ]
    }

    try:
        response = requests.post(API_URL, headers=HEADERS, json=data)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        if "</think>" in content:
            content = content.split("</think>\n\n")[-1]
        parsed = json.loads(content)
        result = AnalysisResult(**parsed)
        await save_result_to_db(result)
        with open(f"{RESULTS_DIR}/{filename.replace('.txt', '.json')}", "w", encoding="utf-8") as out:
            out.write(json.dumps(parsed, ensure_ascii=False, indent=2))
    except Exception as e:
        logging.error(f"Ошибка {filename}: {e}")

    await database.disconnect()


async def process_all_logs_and_query_ai():
    await database.connect()

    for filename in os.listdir(LOGS_DIR):
        if not filename.endswith(".txt"):
            return

        await process_log_and_query_ai(filename)

    await database.disconnect()


@app.get("/results", response_model=List[AnalysisResult])
async def get_results():
    await database.connect()

    cached = await redis_client.get(REDIS_CACHE_KEY)
    if cached:
        await database.disconnect()
        return json.loads(cached)

    await process_all_logs_and_query_ai()

    query = results.select()
    all_results = await database.fetch_all(query)
    result_list = [AnalysisResult(**dict(r)) for r in all_results]
    serialized = json.dumps([r.dict() for r in result_list], ensure_ascii=False)

    await redis_client.set(REDIS_CACHE_KEY, serialized, ex=REDIS_TTL)
    await database.disconnect()
    return result_list
