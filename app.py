from flask import Flask, render_template, request, session, redirect, url_for
import json
import random
import math
from collections import defaultdict

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # change in production

with open("question_bank.json", encoding="utf-8") as f:
    ALL_QUESTIONS = json.load(f)

def get_available_juts():
    """Return sorted list of unique exam_number values."""
    return sorted({q["exam_number"] for q in ALL_QUESTIONS if q.get("exam_number")})

def select_questions(selected_juts):
    """Select 20 MCQ + 5 Integer per subject from the selected JUTs."""
    filtered = [q for q in ALL_QUESTIONS if q["exam_number"] in selected_juts]
    if not filtered:
        filtered = ALL_QUESTIONS  # fallback to all

    # Group by subject and question_type
    groups = defaultdict(lambda: defaultdict(list))
    for q in filtered:
        groups[q["subject"]][q["question_type"]].append(q)

    selected = []
    for subject in ["Physics", "Chemistry", "Mathematics"]:
        subject_data = groups.get(subject, {})
        mcqs = subject_data.get("MCQ", [])
        ints = subject_data.get("INTEGER", [])

        # Shuffle and take required counts (if not enough, take all)
        random.shuffle(mcqs)
        random.shuffle(ints)
        selected.extend(mcqs[:20])
        selected.extend(ints[:5])

    # Shuffle overall to mix subjects
    random.shuffle(selected)
    return selected

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/choose", methods=["GET", "POST"])
def choose():
    if request.method == "POST":
        selected = request.form.getlist("juts")
        if selected:
            session["selected_juts"] = selected
        else:
            session["selected_juts"] = get_available_juts()  # fallback all
        return redirect(url_for("test"))
    juts = get_available_juts()
    return render_template("choose.html", juts=juts)

# app.py (excerpt)
@app.route("/test")
def test():
    selected = session.get("selected_juts", get_available_juts())
    questions = select_questions(selected)
    session["test_questions"] = questions
    # Convert questions to JSON for JavaScript
    questions_json = json.dumps(questions, default=str)  # handle any non-serializable
    return render_template("test.html", questions=questions, questions_json=questions_json)

@app.route("/submit", methods=["POST"])
def submit():
    questions = session.get("test_questions", [])
    score = 0
    results = []

    for q in questions:
        qno = q["question_number"]
        submitted = request.form.get(f"q{qno}")
        correct = q["correct_answer"]

        if submitted is None:
            status = "Not Attempted"
            score += 0
        elif submitted.strip() == correct.strip():
            status = "Correct"
            score += 4
        else:
            status = "Wrong"
            score -= 1

        results.append({
            "question": q["question_text"],
            "chosen": submitted if submitted is not None else "",
            "correct": correct,
            "status": status,
            "solution_html": q["solution_html"],
            "question_html": q["question_html"],
            "options": q.get("options", [])
        })

    # clear session after result
    session.pop("test_questions", None)
    return render_template("result.html", score=score, results=results, total=len(questions))

if __name__ == "__main__":
    app.run(debug=True)