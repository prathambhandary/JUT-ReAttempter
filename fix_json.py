import json,os
 
FILE="data/question_bank.json"
DATA_FILE_JEE="data/test_download_data.json"
DATA_FILE_KCET="data/test_download_data_kcet.json"

EXAM_NUMBER="37" 
EXAM="JEE"
EXAM_TYPE="JUT"
 
DATA_FILE=DATA_FILE_JEE if EXAM=="JEE" else DATA_FILE_KCET

print("="*60)
print("Starting cleanup")
print(f"Exam       : {EXAM}")
print(f"Exam number: {EXAM_NUMBER}")
print(f"Exam type  : {EXAM_TYPE}")
print("="*60)

print(f"[1/4] Loading test data: {DATA_FILE}")

with open(DATA_FILE,"r",encoding="utf-8") as g:
    indexes=json.load(g)

TEST_IDS=[
    obj for obj in indexes
    if obj.get("exam_number")==int(EXAM_NUMBER)
    and obj.get("exam_type")==EXAM_TYPE
]

print(f"      Found {len(TEST_IDS)} matching tests")

deleted=0
missing=0
errors=0

print("[2/4] Removing webpage files...")

for obj in TEST_IDS:
    test_id=str(obj["exam_id"])
    web_file_path=f"webpages/test_{test_id}.html"

    if os.path.exists(web_file_path):
        try:
            os.remove(web_file_path)
            deleted+=1
            print(f"      [DELETED] {web_file_path}")
        except Exception as e:
            errors+=1
            print(f"      [ERROR]   {web_file_path}: {e}")
    else:
        missing+=1
        print(f"      [MISSING] {web_file_path}")

print(f"      Deleted: {deleted}")
print(f"      Missing: {missing}")
print(f"      Errors : {errors}")

print(f"[3/4] Updating {FILE}")

with open(FILE,"r",encoding="utf-8") as f:
    data=json.load(f)

ini=len(data)

data=[
    item for item in data
    if item.get("exam_number")!=EXAM_NUMBER
    or item.get("exam")!=EXAM
]

fin=len(data)
removed=ini-fin

with open(FILE,"w",encoding="utf-8") as f:
    json.dump(data,f,indent=4,ensure_ascii=False)

print(f"      Initial entries: {ini}")
print(f"      Removed entries: {removed}")
print(f"      Remaining entries: {fin}")

print("[4/4] Cleanup complete")
print("="*60)
print(f"Summary: {deleted} files deleted, {removed} JSON entries removed")
print("="*60)
