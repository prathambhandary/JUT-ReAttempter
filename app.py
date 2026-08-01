"""
JUT ReAttempter -- Flask backend.

Endpoints
---------
GET  /                       -> landing page
GET  /select                 -> choose-test page
GET  /test                   -> CBT exam page
GET  /result/<session_id>    -> result page (reads score from disk cache)

GET  /api/tests              -> list of available JUT test numbers found in data/questions.json
POST /api/generate           -> { tests: ["01","02"], candidate_name, roll_number }
                                 -> builds a fresh 75-question paper (20 MCQ + 5 Numerical
                                    per subject), stores the answer key server-side, and
                                    returns only the question content to the client.
POST /api/submit             -> { session_id, answers: {qid: {value, status}} }
                                 -> validates against the server-side answer key, applies
                                    NTA-style marking, stores + returns a full scorecard.
GET  /api/result/<sid>       -> re-fetch a previously computed scorecard (survives refresh).

Swap in your real question bank any time -- just replace data/questions.json,
keeping the same field names used in your original export
(exam, exam_type, exam_number, exam_id, question_number, subject,
question_type, question_html, question_text, options, correct_answer,
solution_html, solution_text).
"""

import json
import random
import time
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "data" / "questions.json"

SUBJECT_ORDER = ["Physics", "Chemistry", "Mathematics"]
MCQ_PER_SUBJECT = 20
INT_PER_SUBJECT = 5
TEST_DURATION_SECONDS = 3 * 60 * 60  # strict 3 hour JEE Main style timer

MARKS_MCQ_CORRECT = 4
MARKS_MCQ_WRONG = -1
MARKS_INT_CORRECT = 4
MARKS_INT_WRONG = -1  # NTA does not penalise wrong numerical answers
 
app = Flask(__name__)

# ---------------------------------------------------------------------------
# In-memory stores (fine for a local/single-instance practice app).
# ---------------------------------------------------------------------------
SESSIONS = {}   # session_id -> { created_at, expires_at, questions: {qid: meta}, candidate }
RESULTS = {}    # session_id -> scorecard dict


def is_numeric_type(q):
    qt = (q.get("question_type") or "").strip().lower()
    if qt in ("mcq", "single correct", "single_correct"):
        return False
    if qt in ("numerical", "integer", "sa", "numeric", "integer type", "numerical value"):
        return True
    # fall back: no options => treat as numerical entry
    return not q.get("options")


def load_bank():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    bank = []
    for q in raw:
        qid = f"{q.get('exam_id')}-{q.get('question_number')}"
        bank.append({
            "qid": qid,
            "exam_type": q.get("exam_type", "JUT"),
            "exam_number": str(q.get("exam_number", "")).strip(),
            "exam_id": q.get("exam_id"),
            "subject": q.get("subject", "General"),
            "is_numeric": is_numeric_type(q),
            "question_html": q.get("question_html") or q.get("question_text") or "",
            "options": q.get("options") or [],
            "correct_answer": str(q.get("correct_answer", "")).strip(),
            "solution_html": q.get("solution_html") or q.get("solution_text") or "",
        })
    return bank


QUESTION_BANK = load_bank()


def available_tests():
    seen = {}
    for q in QUESTION_BANK:
        key = (q["exam_type"], q["exam_number"])
        if key not in seen:
            seen[key] = {"exam_type": q["exam_type"], "exam_number": q["exam_number"], "count": 0}
        seen[key]["count"] += 1
    items = sorted(seen.values(), key=lambda x: (x["exam_type"], x["exam_number"]))
    for item in items:
        item["code"] = f"{item['exam_type']}{item['exam_number']}"
        item["label"] = f"{item['exam_type']} - {item['exam_number']}"
    return items


def cleanup_sessions():
    now = time.time()
    expired = [sid for sid, s in SESSIONS.items() if now > s["expires_at"] + 3600]
    for sid in expired:
        SESSIONS.pop(sid, None)


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/select")
def select():
    return render_template("select.html")


@app.route("/test")
def test_page():
    return render_template("test.html")


@app.route("/result/<session_id>")
def result_page(session_id):
    return render_template("result.html", session_id=session_id)


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.route("/api/tests")
def api_tests():
    return jsonify({"tests": available_tests()})


@app.route("/api/generate", methods=["POST"])
def api_generate():
    cleanup_sessions()
    payload = request.get_json(force=True, silent=True) or {}
    chosen = [str(t).strip() for t in payload.get("tests", []) if str(t).strip()]
    candidate_name = (payload.get("candidate_name") or "Candidate").strip()[:60]
    roll_number = (payload.get("roll_number") or "").strip()[:30]

    if not chosen:
        return jsonify({"error": "Select at least one JUT test to generate a paper."}), 400

    pool = [q for q in QUESTION_BANK if q["exam_number"] in chosen]
    if not pool:
        return jsonify({"error": "No questions found for the selected tests."}), 400

    session_id = uuid.uuid4().hex
    selected_questions = []
    warnings = []

    for subject in SUBJECT_ORDER:
        subj_pool = [q for q in pool if q["subject"] == subject]
        mcq_pool = [q for q in subj_pool if not q["is_numeric"]]
        int_pool = [q for q in subj_pool if q["is_numeric"]]

        random.shuffle(mcq_pool)
        random.shuffle(int_pool)

        take_mcq = mcq_pool[:MCQ_PER_SUBJECT]
        take_int = int_pool[:INT_PER_SUBJECT]

        if len(take_mcq) < MCQ_PER_SUBJECT:
            warnings.append(
                f"Only {len(take_mcq)}/{MCQ_PER_SUBJECT} {subject} MCQs available in the selected tests."
            )
        if len(take_int) < INT_PER_SUBJECT:
            warnings.append(
                f"Only {len(take_int)}/{INT_PER_SUBJECT} {subject} numerical questions available in the selected tests."
            )

        selected_questions.extend(take_mcq)
        selected_questions.extend(take_int)

    if not selected_questions:
        return jsonify({"error": "Could not assemble a paper from the selected tests."}), 400

    # Build answer key (server-only) + public payload (no answers/solutions)
    answer_key = {}
    public_questions = []
    display_no = 1
    # group by subject in fixed order so client can render section-wise, but keep
    # MCQ-section-then-numerical-section ordering within each subject (NTA style)
    by_subject = {s: {"mcq": [], "int": []} for s in SUBJECT_ORDER}
    for q in selected_questions:
        by_subject[q["subject"]]["mcq" if not q["is_numeric"] else "int"].append(q)

    for subject in SUBJECT_ORDER:
        for group_key in ("mcq", "int"):
            for q in by_subject[subject][group_key]:
                answer_key[q["qid"]] = {
                    "correct_answer": q["correct_answer"],
                    "is_numeric": q["is_numeric"],
                    "subject": q["subject"],
                    "solution_html": q["solution_html"],
                    "question_html": q["question_html"],
                    "options": q["options"],
                }
                public_questions.append({
                    "qid": q["qid"],
                    "display_number": display_no,
                    "subject": q["subject"],
                    "section": "B" if q["is_numeric"] else "A",
                    "type": "Numerical" if q["is_numeric"] else "MCQ",
                    "question_html": q["question_html"],
                    "options": q["options"],
                })
                display_no += 1

    now = time.time()
    SESSIONS[session_id] = {
        "created_at": now,
        "expires_at": now + TEST_DURATION_SECONDS,
        "duration": TEST_DURATION_SECONDS,
        "questions": answer_key,
        "candidate_name": candidate_name,
        "roll_number": roll_number,
        "tests": chosen,
    }

    return jsonify({
        "session_id": session_id,
        "duration_seconds": TEST_DURATION_SECONDS,
        "server_time": now,
        "candidate_name": candidate_name,
        "roll_number": roll_number,
        "tests": chosen,
        "questions": public_questions,
        "warnings": warnings,
    })


@app.route("/api/submit", methods=["POST"])
def api_submit():
    payload = request.get_json(force=True, silent=True) or {}
    session_id = payload.get("session_id")
    answers = payload.get("answers", {}) or {}

    session = SESSIONS.get(session_id)
    if not session:
        return jsonify({"error": "This test session has expired or was not found. Please start a new test."}), 404

    subject_stats = {s: {"correct": 0, "wrong": 0, "unattempted": 0, "marks": 0, "total": 0} for s in SUBJECT_ORDER}
    review = []

    for qid, meta in session["questions"].items():
        subject = meta["subject"]
        subject_stats[subject]["total"] += 1
        ans_entry = answers.get(qid, {})
        status = ans_entry.get("status", "not_answered")
        value = str(ans_entry.get("value", "")).strip()

        attempted = status in ("answered", "answered_marked") and value != ""
        correct_answer = meta["correct_answer"]

        is_correct = False
        if attempted:
            if meta["is_numeric"]:
                is_correct = _numeric_match(value, correct_answer)
            else:
                is_correct = value == correct_answer

        if not attempted:
            subject_stats[subject]["unattempted"] += 1
            marks = 0
        elif is_correct:
            subject_stats[subject]["correct"] += 1
            marks = MARKS_INT_CORRECT if meta["is_numeric"] else MARKS_MCQ_CORRECT
        else:
            subject_stats[subject]["wrong"] += 1
            marks = MARKS_INT_WRONG if meta["is_numeric"] else MARKS_MCQ_WRONG

        subject_stats[subject]["marks"] += marks

        review.append({
            "qid": qid,
            "subject": subject,
            "type": "Numerical" if meta["is_numeric"] else "MCQ",
            "question_html": meta["question_html"],
            "options": meta["options"],
            "correct_answer": correct_answer,
            "your_answer": value if attempted else None,
            "status": status,
            "is_correct": is_correct if attempted else None,
            "marks": marks,
            "solution_html": meta["solution_html"],
        })

    total_marks = sum(s["marks"] for s in subject_stats.values())
    max_marks = sum(s["total"] for s in subject_stats.values()) * MARKS_MCQ_CORRECT
    total_correct = sum(s["correct"] for s in subject_stats.values())
    total_wrong = sum(s["wrong"] for s in subject_stats.values())
    total_unattempted = sum(s["unattempted"] for s in subject_stats.values())

    time_taken = min(int(time.time() - session["created_at"]), session["duration"])

    scorecard = {
        "session_id": session_id,
        "candidate_name": session["candidate_name"],
        "roll_number": session["roll_number"],
        "tests": session["tests"],
        "total_marks": total_marks,
        "max_marks": max_marks,
        "total_correct": total_correct,
        "total_wrong": total_wrong,
        "total_unattempted": total_unattempted,
        "total_questions": total_correct + total_wrong + total_unattempted,
        "time_taken_seconds": time_taken,
        "subject_stats": subject_stats,
        "review": review,
        "submitted_at": time.time(),
    }
    RESULTS[session_id] = scorecard
    return jsonify(scorecard)


@app.route("/api/result/<session_id>")
def api_result(session_id):
    scorecard = RESULTS.get(session_id)
    if not scorecard:
        return jsonify({"error": "No result found for this session."}), 404
    return jsonify(scorecard)


def _numeric_match(value, correct_answer):
    try:
        return abs(float(value) - float(correct_answer)) < 1e-6
    except (TypeError, ValueError):
        return value == correct_answer


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
