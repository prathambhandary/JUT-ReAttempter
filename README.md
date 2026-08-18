# JUT ReAttempter

> *"Every JUT you've already taken deserves one more attempt."*

An independent, unofficial practice platform built by **Jnanasudha Institutions alumni** for current students.

JUT ReAttempter transforms any combination of previous **Jnanasudha Unit Tests (JUTs)** into a fresh, randomized **JEE Main-style Computer Based Test (CBT)**. Instead of being limited to a single attempt on the official portal, students can revise the same concepts through unlimited randomized papers generated exclusively from the JUTs they choose.

--- 

## Why JUT ReAttempter?

The official JUT platform allows each paper to be attempted only once.

For competitive exams like **JEE Main**, revision is just as important as learning. Re-solving previous papers helps identify mistakes, improve speed, and strengthen weak chapters—but without an official reattempt option, that opportunity disappears after one sitting.

JUT ReAttempter was built to solve exactly that problem.

---

## Features

- 🎯 Reattempt any previous JUT
- 🔀 Randomized papers every single attempt
- 📚 Combine multiple JUTs into one custom mock
- 💻 NTA-style Computer Based Test interface
- ⏱️ Strict 3-hour countdown timer
- 📊 Instant server-verified scorecards
- 📖 Complete answer review with solutions
- 🌙 Light & Dark themes
- 🔒 Anonymous — no personal data collection
- 🆓 Completely free

---

## How it works

1. Select one or more JUT test numbers.
2. Questions are collected only from the selected tests.
3. The app assembles a completely fresh paper containing:
   - **20 MCQs + 5 Numerical Value Questions**
   - Physics
   - Chemistry
   - Mathematics
4. Attempt the paper in a familiar NTA-style CBT interface.
5. Receive an instant scorecard with subject-wise analysis and solutions.

Because questions are shuffled randomly, **no two attempts are exactly the same**, even when selecting the same JUTs again.

---

## Scoring

The marking scheme follows the current **JEE Main** pattern.

| Question Type | Correct | Incorrect | Unattempted |
|---------------|---------|-----------|-------------|
| MCQ | +4 | −1 | 0 |
| Numerical | +4 | −1 | 0 |

Scoring is performed **server-side**, ensuring that answer keys remain hidden until submission and results cannot be manipulated.

---

## Tech Stack

- Flask
- HTML5
- CSS3
- Vanilla JavaScript
- MathJax
- JSON Question Bank

No database required.

---

# Quick Start

Install dependencies

```bash
pip install -r requirements.txt
```

Run the application

```bash
python app.py
```

Open

```
http://127.0.0.1:5000
```

That's it.

---

# Project Structure

```
.
├── app.py
├── generate_sample_data.py
├── requirements.txt
├── data/
│   └── questions.json
├── templates/
│   ├── index.html
│   ├── select.html
│   ├── test.html
│   └── result.html
├── static/
│   ├── css/
│   ├── js/
│   └── images/
└── README.md
```

---

# Using your own Question Bank

The project includes a synthetic sample question bank so that it works immediately after cloning.

To use your own data, simply replace

```
data/questions.json
```

with your exported question bank using the same schema.

Example:

```json
{
    "exam": "JEE",
    "exam_type": "JUT",
    "exam_number": "01",
    "exam_id": 9460,
    "question_number": 1,
    "subject": "Physics",
    "question_type": "MCQ",
    "question_html": "...",
    "question_text": "...",
    "options": [
        {
            "html": "...",
            "text": "Option A"
        }
    ],
    "correct_answer": "1",
    "solution_html": "...",
    "solution_text": "..."
}
```

The backend automatically:

- Groups questions by `exam_type` and `exam_number`
- Detects MCQs and Numerical questions
- Builds randomized papers
- Generates server-verified scorecards

Restart Flask after replacing the file.

---

# Browser Support

Tested on modern versions of

- Chrome
- Edge
- Firefox
- Safari

Math rendering is handled using **MathJax**, allowing questions and solutions to contain native MathML.

---

# Philosophy

JUT ReAttempter is not meant to replace your college's testing system.

Its purpose is simple:

> **Give students the opportunity to learn from yesterday's mistakes.**

Every feature—from randomized papers to the familiar CBT interface—exists to make revision more effective while preserving the experience of the real JEE Main examination.

---

## License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0).

The source code is free to use, modify, and distribute under the terms of the AGPL. If you modify and deploy this project as a public web service, you must also make your modified source code available under the same license.

See the [LICENSE](LICENSE) file for the complete license text.

---

# Disclaimer
 
JUT ReAttempter is an **independent, unofficial educational project** created by alumni of **Jnanasudha Institutions**.

It is **not affiliated with, endorsed by, or operated by**:

- Jnanasudha Institutions
- National Testing Agency (NTA)

The platform exists solely to help current students revise previous JUT papers more effectively.

---

## Built with by Jnanasudha Alumni

*"From the Alumni, to the Aspirants."*
