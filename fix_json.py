import json
import os

FILE = "data/question_bank.json"
DATA_FILE_JEE = "data/test_download_data.json"
DATA_FILE_KCET = "data/test_download_data_kcet.json"
EXAM_NUMBER = "32"
EXAM = "KCET"
EXAM_TYPE = "JUT"

DATA_FILE = DATA_FILE_KCET
if EXAM == "JEE": DATA_FILE = DATA_FILE_JEE

with open(DATA_FILE, 'r', encoding="utf-8") as g:
    indexes = json.load(g)

TEST_IDS = [
    obj for obj in indexes
    if obj.get("exam_number") == int(EXAM_NUMBER) and obj.get("exam_type") == EXAM_TYPE
]

for obj in TEST_IDS:
    id = str(obj['exam_id'])
    web_file_path = "webpages/test_" + id
    if os.path.exists(web_file_path):
        os.remove(web_file_path)


# with open(FILE, "r", encoding="utf-8") as f:
#     data = json.load(f)

# ini = len(data)

# data = [
#     item for item in data
#     if item.get("exam_number") != EXAM_NUMBER or item.get("exam") != EXAM
# ]

# fin = len(data)

# with open(FILE, "w", encoding="utf-8") as f:
#     json.dump(data, f, indent=4, ensure_ascii=False)

# print(f"Deleted elements with exam_number == {EXAM_NUMBER}, {ini-fin}")