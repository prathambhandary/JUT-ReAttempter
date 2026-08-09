(function () {
  const SUBJECT_ORDER = ["Physics", "Chemistry", "Mathematics"];

  const loadingEl = document.getElementById("exam-loading");
  const subjectBar = document.getElementById("subject-bar");
  const sectionBar = document.getElementById("section-bar");
  const paletteGroups = document.getElementById("palette-groups");
  const paletteWrap = document.getElementById("palette-wrap");
  const paletteToggle = document.getElementById("palette-toggle");
  const examMain = document.getElementById("exam-main");

  const qNumberBadge = document.getElementById("q-number-badge");
  const qTypeBadge = document.getElementById("q-type-badge");
  const marksHint = document.getElementById("marks-hint");
  const qBody = document.getElementById("q-body");
  const answerArea = document.getElementById("answer-area");
  const questionScroll = document.getElementById("question-scroll");

  const timerValueEl = document.getElementById("timer-value");
  const timerBox = document.getElementById("exam-timer");

  let SESSION = null;
  let PROGRESS = null;
  let activeSubject = null;
  let timerInterval = null;
  let submitting = false;

  // -------------------------------------------------------------------
  // Bootstrap
  // -------------------------------------------------------------------

function boot() {
    const raw = sessionStorage.getItem("kcet-session");

    if (!raw) {
        window.location.href = "/select";
        return;
    }

    try {
        SESSION = JSON.parse(raw);
    } catch (e) {
        console.error("[KCET] Invalid session:", e);
        window.location.href = "/select";
        return;
    }

    if (!SESSION.questions || !SESSION.questions.length) {
        window.location.href = "/select";
        return;
    }

    const hdrCandidate = document.getElementById("hdr-candidate-name");
    const paletteCandidate = document.getElementById("palette-candidate-name");

    if (hdrCandidate) {
        hdrCandidate.textContent = SESSION.candidate_name || "Candidate";
    }

    if (paletteCandidate) {
        paletteCandidate.textContent = SESSION.candidate_name || "Candidate";
    }

    const hdrSubject = document.getElementById("hdr-subject-name");
    const paletteSubject = document.getElementById("palette-subject-name");

    const subject = SESSION.subject || SESSION.questions[0].subject;

    if (hdrSubject) {
        hdrSubject.textContent = subject;
    }

    if (paletteSubject) {
        paletteSubject.textContent = subject;
    }

    initProgress();

    activeSubject = subject;

    renderQuestion(PROGRESS.currentQid);
    startTimer();
    wireStaticControls();

    loadingEl.style.display = "none";

    console.log("[KCET] Exam loaded:", SESSION.questions.length, "questions");
}

  function initProgress() {
    const stored = sessionStorage.getItem("jut-progress");
    if (stored) {
      const parsed = JSON.parse(stored);
      if (parsed.session_id === SESSION.session_id) {
        PROGRESS = parsed;
        return;
      }
    }
    const answers = {};
    SESSION.questions.forEach(function (q) {
      answers[q.qid] = { value: "", status: "not_visited" };
    });
    PROGRESS = {
      session_id: SESSION.session_id,
      end_time_ms: Date.now() + SESSION.duration_seconds * 1000,
      answers: answers,
      currentQid: SESSION.questions[0].qid,
    };
    saveProgress();
  }

  function saveProgress() {
    sessionStorage.setItem("jut-progress", JSON.stringify(PROGRESS));
  }

  function questionsFor(subject) {
    return SESSION.questions.filter(function (q) { return q.subject === subject; });
  }

  // -------------------------------------------------------------------
  // Subject / section navigation
  // -------------------------------------------------------------------

  function renderSubjectTabs() {
    const subjectsPresent = SUBJECT_ORDER.filter(function (s) { return questionsFor(s).length; });
    subjectBar.innerHTML = subjectsPresent.map(function (s) {
      return (
        '<button class="subject-tab" data-subject="' + s + '">' +
        s + ' <span class="sub-count">' + questionsFor(s).length + '</span>' +
        '</button>'
      );
    }).join("");
    subjectBar.querySelectorAll(".subject-tab").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const subject = btn.getAttribute("data-subject");
        const qs = questionsFor(subject);
        setActiveSubject(subject);
        goToQuestion(qs[0].qid);
      });
    });
  }

  function setActiveSubject(subject) {
    activeSubject = subject;
    subjectBar.querySelectorAll(".subject-tab").forEach(function (btn) {
      btn.classList.toggle("active", btn.getAttribute("data-subject") === subject);
    });
    renderSectionBar();
    renderPalette();
  }

  function renderSectionBar() {
    const qs = questionsFor(activeSubject);
    const hasA = qs.some(function (q) { return q.section === "A"; });
    const hasB = qs.some(function (q) { return q.section === "B"; });
    const currentQ = SESSION.questions.find(function (q) { return q.qid === PROGRESS.currentQid; });
    const currentSection = currentQ ? currentQ.section : "A";
    let html = "";
    if (hasA) html += '<button class="section-chip' + (currentSection === "A" ? " active" : "") + '" data-section="A">Section A · MCQ</button>';
    if (hasB) html += '<button class="section-chip' + (currentSection === "B" ? " active" : "") + '" data-section="B">Section B · Numerical</button>';
    sectionBar.innerHTML = html;
    sectionBar.querySelectorAll(".section-chip").forEach(function (chip) {
      chip.addEventListener("click", function () {
        const section = chip.getAttribute("data-section");
        const target = qs.find(function (q) { return q.section === section; });
        if (target) goToQuestion(target.qid);
      });
    });
  }

  // -------------------------------------------------------------------
  // Palette
  // -------------------------------------------------------------------

  function statusOf(qid) {
    return PROGRESS.answers[qid].status;
  }

  function statusClass(status) {
    switch (status) {
      case "answered": return "answered";
      case "not_answered": return "not-answered";
      case "marked": return "marked";
      case "marked_answered": return "marked-answered";
      default: return "";
    }
  }

  function renderPalette() {
      const qs = SESSION.questions;

      function grid(list) {
          return '<div class="palette-grid">' +
              list.map(function (q) {
                  const cls = statusClass(statusOf(q.qid));
                  const current = q.qid === PROGRESS.currentQid ? " current" : "";

                  return (
                      '<button class="pcell ' +
                      cls +
                      current +
                      '" data-qid="' +
                      q.qid +
                      '" title="Question ' +
                      q.display_number +
                      '">' +
                      q.display_number +
                      '</button>'
                  );
              }).join("") +
              "</div>";
      }

      paletteGroups.innerHTML = grid(qs);

      paletteGroups.querySelectorAll(".pcell").forEach(function (cell) {
          cell.addEventListener("click", function () {
              const qid = cell.getAttribute("data-qid");

              console.log("[KCET] Palette clicked:", qid);

              goToQuestion(qid);
          });
      });
  }

  // -------------------------------------------------------------------
  // Question rendering
  // -------------------------------------------------------------------

  function currentQuestionData(qid) {
    return SESSION.questions.find(function (q) { return q.qid === qid; });
  }

  function goToQuestion(qid) {
      const q = currentQuestionData(qid);

      if (!q) {
          console.error("[KCET] Question not found:", qid);
          return;
      }

      PROGRESS.currentQid = qid;
      activeSubject = q.subject;

      renderQuestion(qid);
  }

  function renderQuestion(qid) {
    const q = currentQuestionData(qid);
    if (!q) return;

    // Visiting a fresh question marks it "not answered" (red) until saved —
    // matches the NTA convention shown in the palette legend.
    if (PROGRESS.answers[qid].status === "not_visited") {
      PROGRESS.answers[qid].status = "not_answered";
    }

    qNumberBadge.textContent = "Q" + q.display_number;
    qTypeBadge.textContent = q.type === "Numerical" ? "Numerical" : "MCQ";
    marksHint.innerHTML = q.type === "Numerical"
      ? '<span class="pos">+4</span> if correct, <span class="zero" style="color:var(--text-faint);font-weight:700;">0</span> if incorrect'
      : '<span class="pos">+4</span> if correct, <span class="neg">−1</span> if incorrect';

    qBody.innerHTML = q.question_html;

    const saved = PROGRESS.answers[qid].value;
    if (q.type === "Numerical") {
      answerArea.innerHTML =
        '<div class="numeric-answer">' +
        '<label for="numeric-input">Enter your numeric answer</label>' +
        '<input type="text" inputmode="decimal" id="numeric-input" placeholder="e.g. 42 or 3.14" value="' + escapeAttr(saved) + '">' +
        '<div class="numeric-hint">Only the numeric value is checked — units and extra text are ignored.</div>' +
        "</div>";
      const input = document.getElementById("numeric-input");
      input.addEventListener("input", function () {
        PROGRESS.answers[qid].value = input.value.trim();
        saveProgress();
      });
    } else {
      answerArea.innerHTML =
        '<div class="options-list">' +
        (q.options || []).map(function (opt, idx) {
          const label = extractLabel(opt.text, idx);
          const selected = saved === label;
          return (
            '<label class="option-row' + (selected ? " selected" : "") + '" data-label="' + label + '">' +
            '<input type="radio" name="opt-' + qid + '" value="' + label + '"' + (selected ? " checked" : "") + '>' +
            '<span class="opt-radio"></span>' +
            '<span class="opt-content">' + (opt.html || opt.text) + "</span>" +
            "</label>"
          );
        }).join("") +
        "</div>";

      answerArea.querySelectorAll(".option-row").forEach(function (row) {
        row.addEventListener("click", function () {
          const label = row.getAttribute("data-label");
          PROGRESS.answers[qid].value = label;
          answerArea.querySelectorAll(".option-row").forEach(function (r) { r.classList.remove("selected"); });
          row.classList.add("selected");
          saveProgress();
        });
      });
    }

    renderPalette();
    typeset();
    questionScroll.scrollTop = 0;
    saveProgress();
  }

  function extractLabel(text, idx) {
    const m = (text || "").match(/^\s*(\d+)\s*\)/);
    if (m) return m[1];
    return String(idx + 1);
  }

  function escapeAttr(v) {
    return (v || "").replace(/"/g, "&quot;");
  }

  function typeset(container) {
    if (window.MathJax && window.MathJax.typesetPromise) {
      window.MathJax.typesetPromise(container ? [container] : undefined).catch(function () {});
    }
  }

  // -------------------------------------------------------------------
  // Footer actions
  // -------------------------------------------------------------------

  function nextQid(qid) {
    const idx = SESSION.questions.findIndex(function (q) { return q.qid === qid; });
    if (idx === -1 || idx === SESSION.questions.length - 1) return qid;
    return SESSION.questions[idx + 1].qid;
  }

  function wireStaticControls() {
    document.getElementById("icon-flag").innerHTML = ICONS.flag;
    document.getElementById("icon-clear").innerHTML = ICONS.minus;
    document.getElementById("icon-save").innerHTML = ICONS.check;
    document.getElementById("icon-submit").innerHTML = ICONS.check;

    document.getElementById("btn-save").addEventListener("click", function () {
      const qid = PROGRESS.currentQid;
      const val = PROGRESS.answers[qid].value;
      const wasMarked = statusOf(qid) === "marked" || statusOf(qid) === "marked_answered";
      PROGRESS.answers[qid].status = val ? (wasMarked ? "marked_answered" : "answered") : "not_answered";
      saveProgress();
      goToQuestion(nextQid(qid));
    });

    document.getElementById("btn-clear").addEventListener("click", function () {
      const qid = PROGRESS.currentQid;
      PROGRESS.answers[qid].value = "";
      PROGRESS.answers[qid].status = "not_answered";
      saveProgress();
      renderQuestion(qid);
    });

    document.getElementById("btn-mark").addEventListener("click", function () {
      const qid = PROGRESS.currentQid;
      const val = PROGRESS.answers[qid].value;
      PROGRESS.answers[qid].status = val ? "marked_answered" : "marked";
      saveProgress();
      goToQuestion(nextQid(qid));
    });

    document.getElementById("btn-submit").addEventListener("click", openSubmitConfirm);
    document.getElementById("btn-confirm-submit").addEventListener("click", function () {
      submitTest(false);
    });

    document.getElementById("btn-question-paper").addEventListener("click", openQuestionPaper);
    document.getElementById("btn-instructions").addEventListener("click", function () { openModal("modal-instructions"); });

    document.querySelectorAll("[data-close-modal]").forEach(function (btn) {
      btn.addEventListener("click", function () { closeModal(btn.getAttribute("data-close-modal")); });
    });
    document.querySelectorAll(".modal-overlay").forEach(function (overlay) {
      overlay.addEventListener("click", function (e) {
        if (e.target === overlay) closeModal(overlay.id);
      });
    });

    paletteToggle.addEventListener("click", function () {
      if (window.innerWidth <= 980) {
        paletteWrap.classList.toggle("mobile-open");
      } else {
        paletteWrap.classList.toggle("collapsed");
        examMain.classList.toggle("palette-collapsed");
      }
    });

    window.addEventListener("beforeunload", function (e) {
      if (submitting) return;
      e.preventDefault();
      e.returnValue = "";
    });
  }

  function openModal(id) { document.getElementById(id).classList.add("open"); }
  function closeModal(id) { document.getElementById(id).classList.remove("open"); }

  function openQuestionPaper() {
    const body = document.getElementById("qp-body");
    body.innerHTML = SESSION.questions.map(function (q) {
      let optsHtml = "";
      if (q.type !== "Numerical") {
        optsHtml = '<div style="margin-top:10px;display:flex;flex-direction:column;gap:6px;">' +
          (q.options || []).map(function (o) { return '<div>' + (o.html || o.text) + '</div>'; }).join("") +
          "</div>";
      }
      return (
        '<div class="qp-item">' +
        '<span class="qp-num">Q' + q.display_number + ' · ' + q.subject + ' · ' + q.type + '</span>' +
        '<div>' + q.question_html + '</div>' +
        optsHtml +
        "</div>"
      );
    }).join("");
    openModal("modal-qp");
    typeset(body);
  }

  function openSubmitConfirm() {
    const tally = { answered: 0, not_answered: 0, marked_family: 0, not_visited: 0 };
    SESSION.questions.forEach(function (q) {
      const s = statusOf(q.qid);
      if (s === "answered" || s === "marked_answered") tally.answered++;
      else if (s === "marked") tally.marked_family++;
      else if (s === "not_answered") tally.not_answered++;
      else tally.not_visited++;
    });
    document.getElementById("confirm-stats").innerHTML =
      '<div class="confirm-stat"><b style="color:var(--green);">' + tally.answered + '</b><span>Answered</span></div>' +
      '<div class="confirm-stat"><b style="color:var(--red);">' + tally.not_answered + '</b><span>Not answered</span></div>' +
      '<div class="confirm-stat"><b style="color:var(--purple);">' + tally.marked_family + '</b><span>Marked, unanswered</span></div>' +
      '<div class="confirm-stat"><b style="color:var(--text-faint);">' + tally.not_visited + '</b><span>Not visited</span></div>';
    openModal("modal-submit");
  }

  document.getElementById("btn-prev").addEventListener("click", function () {
      const qid = PROGRESS.currentQid;
      const idx = SESSION.questions.findIndex(function (q) {
          return q.qid === qid;
      });

      if (idx > 0) {
          goToQuestion(SESSION.questions[idx - 1].qid);
      }
  });

  document.getElementById("btn-next").addEventListener("click", function () {
      const qid = PROGRESS.currentQid;
      const idx = SESSION.questions.findIndex(function (q) {
          return q.qid === qid;
      });

      if (idx < SESSION.questions.length - 1) {
          goToQuestion(SESSION.questions[idx + 1].qid);
      }
  });

  // -------------------------------------------------------------------
  // Timer
  // -------------------------------------------------------------------

  function startTimer() {
    updateTimerDisplay();
    timerInterval = setInterval(function () {
      const remaining = PROGRESS.end_time_ms - Date.now();
      if (remaining <= 0) {
        clearInterval(timerInterval);
        timerValueEl.textContent = "00:00:00";
        submitTest(true);
        return;
      }
      updateTimerDisplay(remaining);
    }, 1000);
  }

  function updateTimerDisplay(remainingArg) {
    const remaining = remainingArg !== undefined ? remainingArg : PROGRESS.end_time_ms - Date.now();
    const totalSec = Math.max(0, Math.floor(remaining / 1000));
    const h = String(Math.floor(totalSec / 3600)).padStart(2, "0");
    const m = String(Math.floor((totalSec % 3600) / 60)).padStart(2, "0");
    const s = String(totalSec % 60).padStart(2, "0");
    timerValueEl.textContent = h + ":" + m + ":" + s;
    timerBox.classList.toggle("low-time", totalSec <= 300);
  }

  // -------------------------------------------------------------------
  // Submission
  // -------------------------------------------------------------------

  function submitTest(isAutoSubmit) {
    if (submitting) return;
    submitting = true;
    closeModal("modal-submit");

    const answersPayload = {};
    Object.keys(PROGRESS.answers).forEach(function (qid) {
      answersPayload[qid] = {
        value: PROGRESS.answers[qid].value,
        status: PROGRESS.answers[qid].status,
      };
    });

    loadingEl.style.display = "flex";
    loadingEl.querySelector("p").textContent = isAutoSubmit
      ? "Time's up — submitting your test…"
      : "Submitting your test…";

    fetch("/api/submit_kcet", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_token: SESSION.session_token, answers: answersPayload }),
    })
      .then(function (r) { return r.json().then(function (body) { return { ok: r.ok, body: body }; }); })
      .then(function (res) {
        if (!res.ok) {
          submitting = false;
          loadingEl.style.display = "none";
          alert(res.body.error || "Could not submit your test. Please try again.");
          return;
        }
        // The full scorecard comes back directly in this response — cache it
        // so the result page can render without any further server call.
        // (Nothing is stored server-side; see app.py's module docstring.)
        sessionStorage.setItem("jut-result", JSON.stringify(res.body));
        sessionStorage.removeItem("jut-progress");
        sessionStorage.removeItem("jut-session");
        window.location.href = "/result_kcet/" + res.body.session_id;
      })
      .catch(function () {
        submitting = false;
        loadingEl.style.display = "none";
        alert("Could not submit your test — please check your connection and try again.");
      });
  }

  if (document.readyState === "complete" || document.readyState === "interactive") {
    boot();
  } else {
    document.addEventListener("DOMContentLoaded", boot);
  }
})();
