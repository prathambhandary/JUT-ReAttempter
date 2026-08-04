"""
JUT ReAttempter -- Flask backend (stateless / serverless-safe).

Endpoints
---------
GET  /                       -> landing page
GET  /select                 -> choose-test page
GET  /test                   -> CBT exam page
GET  /result/<session_id>    -> result page shell (data comes from the client, see below)

GET  /api/tests               -> list of available JUT test numbers found in data/question_bank.json
POST /api/generate            -> { tests: ["01","02"], candidate_name, roll_number }
                                  -> builds a fresh 75-question paper (20 MCQ + 5 Numerical
                                     per subject) and returns a *signed session_token*
                                     containing the answer key, plus the question content
                                     (no answers) for the client to render.
POST /api/submit              -> { session_token, answers: {qid: {value, status}} }
                                  -> verifies the token's signature + expiry, grades the
                                     answers against the answer key *inside the token*,
                                     and returns the full scorecard directly in the response.

Why no server-side session store
---------------------------------
This app is designed to run on serverless platforms (e.g. Vercel's free tier),
where two requests from the same browser can be handled by two completely
different, memory-isolated function instances -- there is no shared process
memory to keep a SESSIONS/RESULTS dict in. Storing "answer key" state in a
plain Python dict works when you run `python app.py` yourself (one long-lived
process) but silently breaks the moment it's deployed serverless: /api/submit
(or the result page) ends up asking an instance that never saw /api/generate.

Instead, the answer key is signed (HMAC, via itsdangerous) and handed back to
the browser as an opaque token at /api/generate. The browser sends that same
token back at /api/submit. The server verifies the signature (so the client
can't forge or tamper with it) and grades using the answer key embedded in
the token -- no shared storage required anywhere. The full scorecard is
likewise returned directly in the /api/submit response and cached by the
browser (sessionStorage) for the result page, instead of asking the server
to "remember" it under a session id.

If you deploy this behind a *stateful* host (a single long-running server,
or you add Redis/Postgres later), you can simplify back to a session-id
lookup -- but the token approach works everywhere, including here, so it's
the default.

Swap in your real question bank any time -- just replace
data/question_bank.json, keeping the same field names used in your original
export (exam, exam_type, exam_number, exam_id, question_number, subject,
question_type, question_html, question_text, options, correct_answer,
solution_html, solution_text).
"""

import json
import os
import random
import time
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, Response, url_for
from itsdangerous import BadData, SignatureExpired, URLSafeTimedSerializer
from github import update_github_json

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "data" / "question_bank.json"
LEGACY_DATA_FILE = BASE_DIR / "data" / "questions.json"  # older filename, still supported

SUBJECT_ORDER = ["Physics", "Chemistry", "Mathematics"]
MCQ_PER_SUBJECT = 20
INT_PER_SUBJECT = 5
TEST_DURATION_SECONDS = 3 * 60 * 60  # strict 3 hour JEE Main style timer
SUBMIT_GRACE_SECONDS = 10 * 60       # tolerate slow/late network submits by this much

MARKS_MCQ_CORRECT = 4
MARKS_MCQ_WRONG = -1
MARKS_INT_CORRECT = 4
MARKS_INT_WRONG = -1
# ---------------------------------------------------------------------------
# Secret key -- REQUIRED to be a fixed value in production (set the SECRET_KEY
# env var on Vercel/wherever you deploy). If it changes between requests
# (e.g. a random default regenerated per cold start) every token becomes
# unverifiable and you're back to the exact same "results fail" symptom,
# just for a different reason. The fallback below is fine for local dev only.
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-me")
if SECRET_KEY == "dev-only-insecure-key-change-me" and os.environ.get("VERCEL"):
    # Loud but non-fatal: better a visible log line than a silent, confusing
    # "results fail" bug reappearing for a different reason.
    print("WARNING: SECRET_KEY env var is not set. Set it in your Vercel project "
          "settings, or tokens issued by different cold starts may fail to verify.")

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
serializer = URLSafeTimedSerializer(SECRET_KEY, salt="jut-reattempter-session")

@app.route("/sitemap.xml")
def sitemap():
    pages = [
        "index",
        "select",
        "test_page",
    ]

    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    for page in pages:
        xml.append("  <url>")
        xml.append(f"    <loc>{url_for(page, _external=True)}</loc>")
        xml.append("    <changefreq>weekly</changefreq>")
        xml.append("    <priority>0.8</priority>")
        xml.append("  </url>")

    xml.append("</urlset>")

    return Response("\n".join(xml), mimetype="application/xml")

def is_numeric_type(q):
    qt = (q.get("question_type") or "").strip().lower()
    if qt in ("mcq", "single correct", "single_correct"):
        return False
    if qt in ("numerical", "integer", "sa", "numeric", "integer type", "numerical value"):
        return True
    # fall back: no options => treat as numerical entry
    return not q.get("options")


def load_bank():
    path = DATA_FILE if DATA_FILE.exists() else LEGACY_DATA_FILE
    with open(path, "r", encoding="utf-8") as f:
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
    # The page itself carries no data -- result.js pulls the scorecard the
    # browser cached right after /api/submit. See the module docstring.
    return render_template("result.html", session_id=session_id)

@app.route("/add_test", methods=['GET', 'POST'])
def add_page(): 
    return jsonify({"message": "This endpoint is currently disabled, fuck off :)"}), 403
    # if request.method == 'POST':
    #     data = request.get_json() 

    #     if data is None or not all(k in data for k in ("exam_id", "exam_type", "sequence", "exam_number")):
    #         return jsonify({"error": "Invalid data. Required fields: exam_id, exam_type, sequence, exam_number."}), 400

    #     resp = update_github_json({
    #         "exam_id": data["exam_id"],
    #         "exam_type": data["exam_type"],
    #         "sequence": data["sequence"],       
    #         "exam_number": data["exam_number"]
    #     })

    #     if resp["success"]:
    #         return jsonify({"success": True, "message": resp["message"]}), 200

    #     return jsonify({"success": False, "message": resp["message"]}), 400

    # return render_template("add_test.html")


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.route("/api/tests")
def api_tests():
    return jsonify({"tests": available_tests()})


@app.route("/api/generate", methods=["POST"])
def api_generate():
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

    # Build the answer key (goes only into the signed token) + the public
    # payload (question content only, no answers/solutions).
    answer_key = {}
    public_questions = []
    display_no = 1
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
    token_payload = {
        "session_id": session_id,
        "created_at": now,
        "duration": TEST_DURATION_SECONDS,
        "candidate_name": candidate_name,
        "roll_number": roll_number,
        "tests": chosen,
        "answer_key": answer_key,
    }
    session_token = serializer.dumps(token_payload)

    return jsonify({
        "session_id": session_id,
        "session_token": session_token,
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
    token = payload.get("session_token")
    answers = payload.get("answers", {}) or {}

    if not token:
        return jsonify({"error": "Missing session token. Please start a new test."}), 400

    try:
        data = serializer.loads(token, max_age=TEST_DURATION_SECONDS + SUBMIT_GRACE_SECONDS)
    except SignatureExpired:
        return jsonify({"error": "This test's time window has expired. Please start a new test."}), 410
    except BadData:
        return jsonify({"error": "This test session is invalid or corrupted. Please start a new test."}), 400

    answer_key = data["answer_key"]
    subject_stats = {s: {"correct": 0, "wrong": 0, "unattempted": 0, "marks": 0, "total": 0} for s in SUBJECT_ORDER}
    review = []

    for qid, meta in answer_key.items():
        subject = meta["subject"]
        subject_stats[subject]["total"] += 1
        ans_entry = answers.get(qid, {})
        status = ans_entry.get("status", "not_answered")
        value = str(ans_entry.get("value", "")).strip()

        attempted = status in ("answered", "marked_answered") and value != ""
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

    time_taken = min(int(time.time() - data["created_at"]), data["duration"])

    scorecard = {
        "session_id": data["session_id"],
        "candidate_name": data["candidate_name"],
        "roll_number": data["roll_number"],
        "tests": data["tests"],
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
    return jsonify(scorecard)


def _numeric_match(value, correct_answer):
    try:
        return abs(float(value) - float(correct_answer)) < 1e-6
    except (TypeError, ValueError):
        return value == correct_answer


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
