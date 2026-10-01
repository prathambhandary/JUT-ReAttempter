"""
JUT ReAttempter -- Flask backend (stateless / serverless-safe).

Two independent exam modes are served from this one app:

  JEE mode  (existing, unchanged behaviour)
  ----------------------------------------
  GET  /select                  -> choose which JUT test numbers to pool from
  GET  /test                    -> CBT exam page (75 Q: 20 MCQ + 5 Numerical x3 subjects)
  GET  /result/<session_id>     -> result page shell
  POST /api/generate            -> builds a 75-question paper from selected tests
  POST /api/submit              -> grades a JEE session token

  KCET mode  (new)
  -----------------
  GET  /select_kcet             -> choose ONE subject (Physics/Chemistry/Mathematics)
  GET  /test_kcet                -> CBT exam page, single subject, 60 Q, 60 min, no negative marking
  GET  /result_kcet/<session_id> -> result page shell
  POST /api/generate_kcet       -> builds a 60-question single-subject paper
  POST /api/submit_kcet         -> grades a KCET session token

Shared
------
GET  /api/tests        -> JEE test numbers found in the question bank (exam == "JEE")
GET  /api/tests_kcet   -> KCET test numbers found in the question bank (exam == "KCET")
                          (kept for admin/back-compat use; the KCET UI itself picks a
                          SUBJECT, not a test number -- see /api/subjects_kcet below)
GET  /api/subjects_kcet -> KCET subjects with how many questions are available for each,
                           used to render the subject-selection cards on /select_kcet

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
the browser as an opaque token at /api/generate (or /api/generate_kcet). The
browser sends that same token back at submit time. The server verifies the
signature (so the client can't forge or tamper with it) and grades using the
answer key embedded in the token -- no shared storage required anywhere. The
full scorecard is likewise returned directly in the submit response and
cached by the browser (sessionStorage) for the result page, instead of asking
the server to "remember" it under a session id.

Both modes share one signed-token scheme; a "mode" field inside the token
payload ("jee" or "kcet") tells /api/submit* which token it's allowed to
accept, so a JEE token can't be replayed at /api/submit_kcet and vice versa.

Swap in your real question bank any time -- just replace
data/question_bank.json, keeping the same field names used in your original
export (exam, exam_type, exam_number, exam_id, question_number, subject,
question_type, question_html, question_text, options, correct_answer,
solution_html, solution_text). The KCET rows use the exact same shape, just
with "exam": "KCET" -- load_bank() below is already exam-agnostic.
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

# ---------------------------------------------------------------------------
# JEE mode config (unchanged)
# ---------------------------------------------------------------------------
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
# KCET mode config (new)
# ---------------------------------------------------------------------------
KCET_SUBJECTS = ["Physics", "Chemistry", "Mathematics"]
KCET_QUESTIONS_PER_TEST = 60
KCET_DURATION_SECONDS = 60 * 60      # strict 60 minute timer, single subject
KCET_SUBMIT_GRACE_SECONDS = 5 * 60   # tolerate slow/late network submits by this much
KCET_MARKS_CORRECT = 1
KCET_MARKS_WRONG = 0                 # no negative marking

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
        "select_kcet",
        "test_page_kcet",
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
            "exam": q.get("exam"),
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


def available_tests(exam):
    seen = {}
    for q in QUESTION_BANK:
        if q["exam"] == exam:
            key = (q["exam_type"], q["exam_number"])
            if key not in seen:
                seen[key] = {"exam_type": q["exam_type"], "exam_number": q["exam_number"], "count": 0}
            seen[key]["count"] += 1
    items = sorted(seen.values(), key=lambda x: (x["exam_type"], x["exam_number"]))
    for item in items:
        item["code"] = f"{item['exam_type']}{item['exam_number']}"
        item["label"] = f"{item['exam_type']} - {item['exam_number']}"
    return items


def available_subjects(exam, subjects):
    """Question counts per subject for a given exam -- powers the KCET
    subject-selection cards (no test-number picking in that flow)."""
    pool = [q for q in QUESTION_BANK if q["exam"] == exam]
    items = []
    for subject in subjects:
        count = sum(1 for q in pool if q["subject"] == subject)
        items.append({"subject": subject, "count": count})
    return items


def _numeric_match(value, correct_answer):
    try:
        return abs(float(value) - float(correct_answer)) < 1e-6
    except (TypeError, ValueError):
        return value == correct_answer


# ---------------------------------------------------------------------------
# Page routes -- JEE
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


@app.route("/add_test", methods=['GET', 'POST'])
def add_page():
    return jsonify({"message": "This endpoint is currently disabled, fuck off :)  "}), 403
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
# Page routes -- KCET
# ---------------------------------------------------------------------------

@app.route("/select_kcet")
def select_kcet():
    return render_template("select_kcet.html")


@app.route("/test_kcet")
def test_page_kcet():
    return render_template("test_kcet.html")


@app.route("/result_kcet/<session_id>")
def result_page_kcet(session_id):
    print("=========================")
    print(session_id)
    print("=========================")
    return render_template("result_kcet.html", session_id=session_id)


# ---------------------------------------------------------------------------
# API routes -- shared / listing
# ---------------------------------------------------------------------------

@app.route("/api/tests")
def api_tests():
    return jsonify({"tests": available_tests(exam="JEE")})


@app.route("/api/tests_kcet")
def api_tests_kcet():
    # Kept for back-compat / admin tooling. The KCET UI itself does not use
    # this -- it selects a SUBJECT via /api/subjects_kcet instead.
    return jsonify({"tests": available_tests(exam="KCET")})


@app.route("/api/subjects_kcet")
def api_subjects_kcet():
    return jsonify({"subjects": available_subjects(exam="KCET", subjects=KCET_SUBJECTS)})


# ---------------------------------------------------------------------------
# API routes -- JEE generate / submit (unchanged)
# ---------------------------------------------------------------------------

@app.route("/api/generate", methods=["POST"])
def api_generate():
    payload = request.get_json(force=True, silent=True) or {}
    chosen = [str(t).strip() for t in payload.get("tests", []) if str(t).strip()]
    candidate_name = (payload.get("candidate_name") or "Candidate").strip()[:60]
    roll_number = (payload.get("roll_number") or "").strip()[:30]

    if not chosen:
        return jsonify({"error": "Select at least one JUT test to generate a paper."}), 400

    pool = [q for q in QUESTION_BANK if q["exam"] == "JEE" and q["exam_number"] in chosen]
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
        "mode": "jee",
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

    if data.get("mode") not in (None, "jee"):
        # None kept for tokens issued before "mode" existed.
        return jsonify({"error": "This session token is not a JEE session. Please start a new test."}), 400

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



# ---------------------------------------------------------------------------
# API routes -- KCET generate / submit (new)
#
# Business rules (per spec):
#   - one subject only per session (Physics / Chemistry / Mathematics)
#   - exactly 60 questions, drawn at random from that subject's whole pool
#     (all KCET tests pooled together -- there is no test-number picker here)
#   - 60 minute fixed timer
#   - +1 correct / 0 wrong / 0 unattempted, no negative marking
#   - the signed token records "subject" and "mode": "kcet" so a KCET token
#     can never be replayed against the JEE endpoints or vice versa, and so
#     switching subjects requires generating a brand new session
# ---------------------------------------------------------------------------

@app.route("/api/generate_kcet", methods=["POST"])
def api_generate_kcet():
    print("\n========== KCET MOCK GENERATION START ==========")

    payload = request.get_json(force=True, silent=True) or {}
    print(f"[KCET] Received payload: {payload}")

    subject = (payload.get("subject") or "").strip()
    candidate_name = (payload.get("candidate_name") or "Candidate").strip()[:60]
    # roll_number = (payload.get("roll_number") or "").strip()[:30]
    roll_number = "25000"

    print(f"[KCET] Subject: {subject}")
    print(f"[KCET] Candidate name: {candidate_name}")
    print(f"[KCET] Roll number: {roll_number}")

    # Validate subject
    if subject not in KCET_SUBJECTS:
        print(f"[KCET] ERROR: Invalid subject: {subject}")
        print(f"[KCET] Allowed subjects: {KCET_SUBJECTS}")
        return jsonify({
            "error": "Select a valid subject (Physics, Chemistry or Mathematics) to start a mock test."
        }), 400

    print(f"[KCET] Subject validation passed: {subject}")

    # Find questions
    print("[KCET] Searching question bank...")

    pool = [
        q for q in QUESTION_BANK
        if q["exam"] == "KCET" and q["subject"] == subject
    ]

    print(f"[KCET] Found {len(pool)} questions for subject {subject} in KCET question bank.")

    if not pool:
        print(f"[KCET] ERROR: No questions available for {subject}")
        return jsonify({
            "error": f"No {subject} questions found in the KCET question bank."
        }), 400

    # Shuffle and select
    print(f"[KCET] Shuffling {len(pool)} available questions...")
    random.shuffle(pool)

    selected_questions = pool[:KCET_QUESTIONS_PER_TEST]

    print(
        f"[KCET] Selected {len(selected_questions)} questions "
        f"(requested: {KCET_QUESTIONS_PER_TEST})"
    )

    warnings = []

    if len(selected_questions) < KCET_QUESTIONS_PER_TEST:
        warning = (
            f"Only {len(selected_questions)}/{KCET_QUESTIONS_PER_TEST} "
            f"{subject} questions are available right now, so this paper "
            "will be shorter than the usual 60."
        )

        warnings.append(warning)
        print(f"[KCET] WARNING: {warning}")

    # Create session
    session_id = uuid.uuid4().hex

    print(f"[KCET] Generated session ID: {session_id}")

    answer_key = {}
    public_questions = []

    print("[KCET] Building question data...")

    for i, q in enumerate(selected_questions, start=1):
        print(
            f"[KCET] Processing question {i}/{len(selected_questions)} "
            f"| qid={q.get('qid')} "
            f"| type={'Numerical' if q.get('is_numeric') else 'MCQ'}"
        )

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
            "display_number": i,
            "subject": q["subject"],
            "type": "Numerical" if q["is_numeric"] else "MCQ",
            "question_html": q["question_html"],
            "options": q["options"],
        })

    print(f"[KCET] Answer key created: {len(answer_key)} questions")
    print(f"[KCET] Public question list created: {len(public_questions)} questions")

    # Create token
    now = time.time()

    print(f"[KCET] Creating session token...")
    print(f"[KCET] Session creation timestamp: {now}")
    print(f"[KCET] Duration: {KCET_DURATION_SECONDS} seconds")

    token_payload = {
        "mode": "kcet",
        "session_id": session_id,
        "created_at": now,
        "duration": KCET_DURATION_SECONDS,
        "candidate_name": candidate_name,
        "roll_number": roll_number,
        "subject": subject,
        "answer_key": answer_key,
    }

    session_token = serializer.dumps(token_payload)

    print("[KCET] Session token generated successfully")
    print(f"[KCET] Token length: {len(session_token)} characters")

    response_data = {
        "session_id": session_id,
        "session_token": session_token,
        "duration_seconds": KCET_DURATION_SECONDS,
        "server_time": now,
        "candidate_name": candidate_name,
        "roll_number": roll_number,
        "subject": subject,
        "questions": public_questions,
        "warnings": warnings,
    }

    print(
        f"[KCET] Returning response | "
        f"session_id={session_id} | "
        f"questions={len(public_questions)} | "
        f"warnings={len(warnings)}"
    )

    print("========== KCET MOCK GENERATION END ==========\n")

    return jsonify(response_data)



@app.route("/api/submit_kcet", methods=["POST"])
def api_submit_kcet():
    payload = request.get_json(force=True, silent=True) or {}
    token = payload.get("session_token")
    answers = payload.get("answers", {}) or {}

    if not token:
        return jsonify({"error": "Missing session token. Please start a new test."}), 400

    try:
        data = serializer.loads(token, max_age=KCET_DURATION_SECONDS + KCET_SUBMIT_GRACE_SECONDS)
    except SignatureExpired:
        return jsonify({"error": "This test's time window has expired. Please start a new test."}), 410
    except BadData:
        return jsonify({"error": "This test session is invalid or corrupted. Please start a new test."}), 400

    if data.get("mode") != "kcet":
        return jsonify({"error": "This session token is not a KCET session. Please start a new test."}), 400

    answer_key = data["answer_key"]
    review = []
    correct = wrong = unattempted = 0

    for qid, meta in answer_key.items():
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
            unattempted += 1
            marks = 0
        elif is_correct:
            correct += 1
            marks = KCET_MARKS_CORRECT
        else:
            wrong += 1
            marks = KCET_MARKS_WRONG

        review.append({
            "qid": qid,
            "subject": meta["subject"],
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

    total_marks = correct * KCET_MARKS_CORRECT + wrong * KCET_MARKS_WRONG
    max_marks = len(answer_key) * KCET_MARKS_CORRECT
    time_taken = min(int(time.time() - data["created_at"]), data["duration"])

    scorecard = {
        "session_id": data["session_id"],
        "candidate_name": data["candidate_name"],
        "roll_number": data["roll_number"],
        "subject": data["subject"],
        "total_marks": total_marks,
        "max_marks": max_marks,
        "total_correct": correct,
        "total_wrong": wrong,
        "total_unattempted": unattempted,
        "total_questions": correct + wrong + unattempted,
        "time_taken_seconds": time_taken,
        "review": review,
        "submitted_at": time.time(),
    }
    return jsonify(scorecard)



@app.route("/debug/receive", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def debug_receive():
    print("\n========== DEBUG REQUEST ==========")
    print("Method:", request.method)
    print("URL:", request.url)
    print("Headers:", dict(request.headers))
    print("Args:", request.args.to_dict())
    print("Form:", request.form.to_dict())
    print("JSON:", request.get_json(silent=True))
    print("Raw body:", request.get_data(as_text=True))
    print("========== END DEBUG ==========\n")

    return jsonify({
        "success": True,
        "message": "Request received"
    })


@app.route("/testing")
def testroute():
  return {"msg": "Still Alive...", "status": "live"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
