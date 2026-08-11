
# add 10 to all jut numbers in test_download_data.json file
 
import json

FILE = "data/question_bank.json"
EXAM_NUMBER = "29"

with open(FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

data = [
    item for item in data
    if item.get("exam_number") != EXAM_NUMBER
]

with open(FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

print(f"Deleted elements with exam_number == {EXAM_NUMBER}")