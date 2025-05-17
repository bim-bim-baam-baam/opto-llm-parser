import os
import json

# Путь к папке с resultN.json файлами
input_dir = "results"
output_file = "merged.json"

# Итоговый список
merged_data = []

# Перебираем все файлы в папке
for filename in os.listdir(input_dir):
    if filename.endswith(".json") and filename.startswith("result"):
        file_path = os.path.join(input_dir, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if isinstance(data, list):
                    merged_data.extend(data)
                else:
                    print(f"⚠️ Пропущен файл (не список): {filename}")
            except json.JSONDecodeError:
                print(f"❌ Ошибка парсинга JSON: {filename}")

# Сохраняем результат
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(merged_data, f, ensure_ascii=False, indent=2)

print(f"✅ Объединено {len(merged_data)} записей в '{output_file}'")
