from collections import defaultdict

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
api_key = "io-v2-eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJvd25lciI6ImVjYmQ2ZDk3LTE5MGItNDU2Mi04ZTY1LWJjMTJhNGJlNjkwOSIsImV4cCI6NDkwMTA5MjYyNX0.dLmBbWToUQzJ3fUPHS0qMYn10MO9E6yFIKreNBa5YtGMaAFWD6GoV__3ajTxo2m-hcEtgb58LMobsDXhgtFIIg"
AI_MODEL = "deepseek-ai/DeepSeek-R1" # v3 R1

url = "https://api.intelligence.io.solutions/api/v1/chat/completions"

headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer " + api_key
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
    api_key = "io-v2-eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJvd25lciI6ImVjYmQ2ZDk3LTE5MGItNDU2Mi04ZTY1LWJjMTJhNGJlNjkwOSIsImV4cCI6NDkwMTA5MjYyNX0.dLmBbWToUQzJ3fUPHS0qMYn10MO9E6yFIKreNBa5YtGMaAFWD6GoV__3ajTxo2m-hcEtgb58LMobsDXhgtFIIg"
    ai_model = "deepseek-ai/DeepSeek-R1"

    url = "https://api.intelligence.io.solutions/api/v1/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + api_key
    }

    data = {
        "model": ai_model,
        "messages": [
            {
                "role": "system",
                "content": request.prompt,
            },
            {
                "role": "user",
                "content": request.message
            }
        ]
    }

    response = requests.post(url, headers=headers, json=data)
    data = response.json()

    print(data)

    text = data['choices'][0]['message']['content']
    bot_text = text.split('</think>\n\n')[1]

    print(bot_text)

    return bot_text

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
                response = requests.post(url, headers=headers, json=data)
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

class ParsedLogEntry(BaseModel):
    package: str
    error_type: str
    programming_language: str
    description: str

@app.post("/cluster_format")
async def cluster_logs_by_error_type():
    file_path = "merged.json"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="merged.json not found")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        parsed_logs: List[ParsedLogEntry] = [ParsedLogEntry(**item) for item in raw_data]

        # Группируем не просто названия пакетов, а (название, язык)
        grouped_packages: defaultdict[str, List[Tuple[str, str]]] = defaultdict(list)
        error_descriptions = {}

        for entry in parsed_logs:
            error_types = [etype.strip() for etype in entry.error_type.split(",")]
            for etype in error_types:
                grouped_packages[etype].append((entry.package, entry.programming_language))
                if etype not in error_descriptions:
                    error_descriptions[etype] = entry.description  # первое описание

        clusters = []
        for i, (error_type, packages) in enumerate(grouped_packages.items()):
            cluster = {
                "id": i,
                "name": error_type,
                "description": error_descriptions.get(error_type, ""),
                "packages": [
                    {"id": j, "name": pkg_name, "programming_language": lang}
                    for j, (pkg_name, lang) in enumerate(packages)
                ]
            }
            clusters.append(cluster)

        return {
            "status": "NEW",
            "clusters": clusters
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {e}")