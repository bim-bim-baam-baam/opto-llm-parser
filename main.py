from dotenv import load_dotenv
import os
import re
import requests
import json
import logging
import asyncio

# Загружаем переменные из .env файла
load_dotenv()
API_KEY = os.getenv("API_KEY")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AI_MODEL = "deepseek-ai/DeepSeek-R1"

API_URL = "https://api.intelligence.io.solutions/api/v1/chat/completions"
# AI_MODEL = "deepseek-chat"
LOGS_DIR = "logs/"  # путь к папке с логами

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
    "Отвечай только в этом формате и только на английском языке. error_type часто будет cmake, поэтому детальнее указывай"
    "error_type. Нам важно потом в другом сервисе выделять кластеры по этим error_type."
)


def extract_package_name(text):
    match = re.search(r"\[ PACKAGE: ([^\]]+) \]", text)
    return match.group(1) if match else "unknown-package"


async def process_logs_and_query_deepseek():
    for filename in os.listdir(LOGS_DIR):
        if not filename.endswith(".txt"):
            continue

        filepath = os.path.join(LOGS_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as file:
            log_text = file.read()

        # Подготовка запроса
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
            json_data = response.json()

            ai_reply = json_data["choices"][0]["message"]["content"]
            if "</think>" in ai_reply:
                ai_reply = ai_reply.split("</think>\n\n")[-1]

            # Печать или запись в файл
            print(ai_reply)
            print()

            result_filename = filename.split('.')[0]

            # Можно сохранить в файл
            with open(f"results/{result_filename}.json", "w", encoding="utf-8") as out:
                out.write(ai_reply)

        except Exception as e:
            logging.error(f"Ошибка при обращении к API по файлу {filename}: {e}")


# Запуск
if __name__ == "__main__":
    asyncio.run(process_logs_and_query_deepseek())
