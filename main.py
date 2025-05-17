from fastapi import FastAPI, Request, HTTPException
import logging
import requests
import asyncio
import os
import json
from dotenv import load_dotenv
from typing import List
from pydantic import BaseModel
from typing import List


class LogEntry(BaseModel):
    # link: str
    package: str
    errors: str


load_dotenv()
app = FastAPI()

API_KEY = os.getenv("API_KEY")
API_URL = "https://api.intelligence.io.solutions/api/v1/chat/completions"
AI_MODEL = "deepseek-ai/DeepSeek-R1" # v3 R1

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

SYSTEM_PROMPT = (
    "Ты эксперт в анализе логов сборки Linux-пакетов. "
    "Тебе даются фрагменты логов пакетов с фрагментами ошибок. "
    "На их основе сформируй краткий JSON-ответ с 5 полями:\n"
    "1. link - путь к логу, \n"
    "2. package — имя пакета,\n"
    "3. error_type — узкая категория ошибки. если получено несколько ошибок разных категорий для одного пакета,"
    " то может быть указано несколько категорий через запятую,\n"
    "4. programming_language - фильтрация по языку программирования, \n"
    "5. description — подробное описание ошибки, включая основную причину сбоя и её контекст.\n"
    "Пример ответа:\n"
    "{\n"
    "  \"link\": \"https://git.altlinux.org/beehive/logs/Sisyphus/i586/latest/error/yajl-2.1.0-alt3\", \n"
    "  \"package\": \"yajl-2.1.0-alt3\",\n"
    "  \"error_type\": \"cmake\",\n"
    "  \"programming_language\": \"C++\", \n"
    "  \"description\": \"Ошибка конфигурации CMake: недопустимый аргумент в cmake_minimum_required."
    " Версия CMake слишком старая.\"\n"
    "}\n"
    "Отвечай только в этом формате и только на английском языке. error_type часто будет cmake, "
    "поэтому детальнее указывай error_type. Нам важно потом в другом сервисе выделять кластеры по этим error_type."
)

# ---------- ЧАТ-ЭНДПОИНТ ----------


class ChatRequest(BaseModel):
    prompt: str
    message: str


@app.post("/chat")
async def chat_with_deepseek(request: ChatRequest):
    try:
        data = {
            "model": AI_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": f"Ты эксперт в ALT-Linux. Ты помогаешь с решением ошибок сборки:"
                               f" объясняешь и предлагаешь решения. Проанализируй это: {request.prompt}",
                },
                {
                    "role": "user",
                    "content": request.message
                }
            ]
        }

        response = requests.post(API_URL, headers=HEADERS, json=data)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]

        if "</think>" in content:
            content = content.split("</think>\n\n")[-1]

        return {"response": content}
    except Exception as e:
        logging.error(f"Ошибка в чат-запросе: {e}")
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

def split_batches(logs: List[dict], batch_size: int = 1) -> List[List[dict]]:
    """Разбиваем большой список логов на порции по batch_size"""
    return [logs[i:i + batch_size] for i in range(0, len(logs), batch_size)]


def format_batch_for_prompt(batch: List[dict]) -> str:
    """Форматирует один батч логов для отправки в prompt"""
    formatted = []
    for entry in batch:
        # link = entry.get("link")
        package = entry.get("package")
        errors = entry.get("errors")
        formatted.append(f"Package: {package}\nErrors:\n{errors}")
    return "\n\n".join(formatted)


@app.get("/get_llm_parsed_data")
async def get_llm_parsed_data():
    file_path = "merged.json"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {e}")


@app.post("/llm_parse")
async def llm_parse(logs: List[LogEntry]):
    try:
        BATCH_SIZE = 10  # руками подбираем

        # logs — List[LogEntry], но дальше split_batches ждёт List[dict], поэтому преобразуем:
        logs_dicts = [log.dict() for log in logs]
        all_results = []
        batches = split_batches(logs_dicts, batch_size=BATCH_SIZE)

        count = 1  # TODO: 26

        for batch in batches:
            log_text = format_batch_for_prompt(batch)
            # print(log_text)
            print(batch)
            print()

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
                all_results.append(parsed)

                print("=======================\n")
                print(parsed)
                print()
                print()

                # вот тут еще сохраняем в /results json result{count}.json parsed
                with open(f"results/result{count}.json", "w", encoding="utf-8") as f:
                    json.dump(parsed, f, ensure_ascii=False, indent=2)
                count += 1

            except Exception as e:
                logging.error(f"Ошибка при обработке батча: {e}")
                all_results.append({"error": str(e), "input_batch": batch})

        return all_results

    except Exception as e:
        logging.error(f"Ошибка на уровне запроса: {e}")
        return {"error": str(e)}

