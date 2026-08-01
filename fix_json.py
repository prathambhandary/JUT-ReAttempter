import json

# Read the original question bank
with open("question_bank.json", "r", encoding="utf-8") as f:
    questions_json = json.load(f)

def delete_by_exam_type(data_list: list, target_exam_type: str = "JCT") -> list:
    """
    Deletes all dictionary items from a list where 'exam_type' matches target_exam_type.
    """
    return [item for item in data_list if item.get("exam_type") != target_exam_type]

# Filter out JCT questions
filtered_json = delete_by_exam_type(questions_json, target_exam_type="JCT")

# Print summary of items removed
removed_count = len(questions_json) - len(filtered_json)
print(f"Removed {removed_count} questions with exam_type 'JCT'.")
print(f"Remaining questions: {len(filtered_json)}")

# Save updated list back to file
with open("question_bank.json", "w", encoding="utf-8") as f:
    json.dump(filtered_json, f, ensure_ascii=False, indent=4)