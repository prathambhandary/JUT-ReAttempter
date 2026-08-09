import requests
from bs4 import BeautifulSoup
import csv
import time
import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()

LOGIN_URL      = "https://jnanasudha.com/index/userlogin"
RESULT_URL_FMT = "https://jnanasudha.com/quiz/view_result?id={}"

ID = os.getenv("JEE_USERNAME")
PASSWORD = os.getenv("JEE_PASSWORD")

sub = {'P': 'Physics', 'C': 'Chemistry', 'M': 'Mathematics', 'B': 'Biology'}

session = requests.Session()
login_data = {"org": "1", "user": ID, "pass": PASSWORD}
headers = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/x-www-form-urlencoded"
}

resp = session.post(LOGIN_URL, data=login_data, headers=headers)

def fetch_test(test_id):
    resp = session.get(RESULT_URL_FMT.format(test_id), headers=headers)
    soup = BeautifulSoup(resp.text, "html.parser")

    # save html page full
    with open(f"webpages/test_{test_id}.html", "w", encoding="utf-8") as f:
        f.write(str(soup))

def main(sequence, exam_id, jut_no, exam_type="JUT"):

    fetch_test(exam_id)


    with open(f"webpages/test_{exam_id}.html",encoding="utf-8") as f:
        soup=BeautifulSoup(f,"html.parser")

    question_bank=[]
    q_no = "N/A"

    for div in soup.select("div[class^=classans]"):
        h3=div.find("h3")
        if not h3:
            continue
        try:
            q_no=int(h3.get_text(strip=True).replace("Question No:",""))
            if q_no<=25:
                subject=sub[sequence[0]]
            elif q_no<=50:
                subject=sub[sequence[1]]
            elif q_no<=75:
                subject=sub[sequence[2]]
        except:
            continue
        h4=div.find("h4")
        question_html=h4.decode_contents().strip() if h4 else ""
        question_text=h4.get_text(" ",strip=True) if h4 else ""
        options=[]
        question_type="INTEGER"
        option_table=div.select_one("table.table-borderless")
        if option_table:
            tds=option_table.find_all("td")
            if len(tds)==4:
                question_type="MCQ"
                for td in tds:
                    options.append({
                        "html":td.decode_contents().strip(),
                        "text":td.get_text(" ",strip=True)
                    })
        your_answer=None
        correct_answer=None
        for p in div.find_all("p"):
            text=p.get_text(" ",strip=True)
            if text.startswith("Your Option"):
                your_answer=text.split(":",1)[1].strip()
            elif text.startswith("Correct Option"):
                correct_answer=text.split(":",1)[1].strip()
            elif text.startswith("Your Answer"):
                your_answer=text.split(":",1)[1].strip()
            elif text.startswith("Correct Answer"):
                correct_answer=text.split(":",1)[1].strip()
        solution_html=""
        solution_text=""
        for p in div.find_all("p"):
            text=p.get_text(" ",strip=True)
            if "Detailed Answer" in text:
                solution_html=p.decode_contents().strip()
                solution_text=text
                break
        question_bank.append({
            "exam": "JEE",
            "exam_type": exam_type,
            "exam_number": jut_no,
            "exam_id": exam_id,
            "question_number":q_no,
            "subject": subject,
            "question_type":question_type,
            "question_html":question_html,
            "question_text":question_text,
            "options":options,
            "correct_answer":correct_answer,
            "your_answer":your_answer,
            "solution_html":solution_html,
            "solution_text":solution_text
        })
    existing_data=[]

    try:
        with open("data/question_bank.json","r",encoding="utf-8") as f:
            existing_data=json.load(f)
    except (FileNotFoundError,json.JSONDecodeError):
        pass

    existing_keys={
        (q["exam_id"],q["question_number"])
        for q in existing_data
    }

    for q in question_bank:
        key=(q["exam_id"],q["question_number"])
        if key not in existing_keys:
            existing_data.append(q)
            existing_keys.add(key)

    with open("data/question_bank.json","w",encoding="utf-8") as f:
        json.dump(existing_data,f,ensure_ascii=False,indent=4)

    print(f"Database now contains {len(existing_data)} questions.")


if __name__ == "__main__":
    
    try:
        f = open("data/question_bank.json", "r", encoding="utf-8")
        question_bank_data = json.load(f)
        unique_exam_ids = set(q["exam_id"] for q in question_bank_data)
    except Exception as e:
        print(f"Error occurred while reading question bank data: {e}")
        unique_exam_ids = set()

    with open("data/test_download_data.json", "r") as f:

        test_data = json.load(f)

        for i in test_data:
            exam_id = i["exam_id"]
            sequence = i["sequence"]

            exam_type = i["exam_type"]
            exam_number = i["exam_number"]


            if exam_id in unique_exam_ids:
                continue

            print(f"Fetching test {exam_number} with exam ID {exam_id} and sequence {sequence}...")

            if exam_type == "JUT":
                if exam_number < 10:
                    main(sequence, exam_id, f"0{exam_number}")
                else:
                    main(sequence, exam_id, str(exam_number))

            if exam_type == "CT":
                if exam_number<10:
                    main(sequence, exam_id, f"CT 0{exam_number}")
                else:
                    main(sequence, exam_id, f"CT {exam_number}")
            
            time.sleep(1)

      
