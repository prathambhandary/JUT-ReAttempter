(function () {
  const shell = document.getElementById("result-shell");
  let SCORE = null;
  let activeFilter = "all";

  function fetchResult() {
    // The scorecard was cached in sessionStorage right after /api/submit_kcet
    // returned it -- nothing is stored server-side (see app.py). This is
    // what makes results work reliably on serverless hosts, where a fresh
    // GET request has no guarantee of hitting the same instance that
    // handled the submit.
    const raw = sessionStorage.getItem("kcet-result");
    const parsed = raw ? JSON.parse(raw) : null;

    if (parsed && parsed.session_id === window.KCET_SESSION_ID) {
      SCORE = parsed;
      render();
      return;
    }

    shell.innerHTML =
      '<div style="text-align:center;padding:60px 0;">' +
      '<p style="color:var(--red);font-weight:600;margin-bottom:10px;">This result isn&rsquo;t available in this browser session.</p>' +
      '<p style="color:var(--text-muted);margin-bottom:22px;max-width:44ch;margin-left:auto;margin-right:auto;">Scorecards live only in your browser right after you submit — reopening this link in a new tab, a different browser, or after clearing site data won&rsquo;t have it. Please start a new test.</p>' +
      '<a class="btn btn-primary" href="/select_kcet">Start a new test</a>' +
      "</div>";
  }

  function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return m + "m " + s + "s";
  }

  function render() {
    const pct = SCORE.max_marks ? Math.max(0, Math.round((SCORE.total_marks / SCORE.max_marks) * 100)) : 0;
    const circumference = 2 * Math.PI * 54;
    const offset = circumference - (Math.max(0, pct) / 100) * circumference;

    shell.innerHTML =
      '<div class="result-hero">' +
        '<div class="score-ring">' +
          '<svg viewBox="0 0 120 120">' +
            '<circle class="track" cx="60" cy="60" r="54" fill="none" stroke-width="10"/>' +
            '<circle class="fill" cx="60" cy="60" r="54" fill="none" stroke-width="10" stroke-dasharray="' + circumference + '" stroke-dashoffset="' + offset + '"/>' +
          '</svg>' +
          '<div class="ring-label"><b>' + pct + '%</b><span>Score</span></div>' +
        '</div>' +
        '<div class="result-hero-mid">' +
          '<h1>' + escapeHtml(SCORE.candidate_name) + '&rsquo;s scorecard</h1>' +
          '<p>' + SCORE.total_questions + ' KCET ' + escapeHtml(SCORE.subject) + ' questions attempted &middot; no negative marking.</p>' +
          '<div class="test-tags"><span class="test-tag">KCET &middot; ' + escapeHtml(SCORE.subject) + '</span></div>' +
        '</div>' +
        '<div class="result-hero-stats">' +
          '<div class="stat-line"><b>' + SCORE.total_marks + ' / ' + SCORE.max_marks + '</b><span>Total marks</span></div>' +
          '<div class="stat-line"><b>' + formatTime(SCORE.time_taken_seconds) + '</b><span>Time taken</span></div>' +
        '</div>' +
      '</div>' +

      '<div class="summary-grid">' +
        '<div class="summary-card correct"><b>' + SCORE.total_correct + '</b><span>Correct</span></div>' +
        '<div class="summary-card wrong"><b>' + SCORE.total_wrong + '</b><span>Incorrect</span></div>' +
        '<div class="summary-card unattempted"><b>' + SCORE.total_unattempted + '</b><span>Unattempted</span></div>' +
        '<div class="summary-card"><b>' + (SCORE.total_questions ? Math.round((SCORE.total_correct / SCORE.total_questions) * 100) : 0) + '%</b><span>Accuracy</span></div>' +
      '</div>' +

      '<div class="review-shell">' +
        '<div class="review-head">' +
          '<h2>Question review</h2>' +
          '<div class="review-filters" id="review-filters">' +
            '<button class="rfilter active" data-filter="all">All</button>' +
            '<button class="rfilter" data-filter="correct">Correct</button>' +
            '<button class="rfilter" data-filter="wrong">Incorrect</button>' +
            '<button class="rfilter" data-filter="skipped">Unattempted</button>' +
          '</div>' +
        '</div>' +
        '<div id="review-list"></div>' +
      '</div>' +

      '<div class="result-actions">' +
        '<a class="btn btn-ghost" href="/select_kcet">New subject</a>' +
        '<a class="btn btn-primary" href="/">Back to home</a>' +
      '</div>';

    wireFilters();
    renderReviewList();
    typeset(shell);
  }

  function wireFilters() {
    document.querySelectorAll(".rfilter").forEach(function (btn) {
      btn.addEventListener("click", function () {
        activeFilter = btn.getAttribute("data-filter");
        document.querySelectorAll(".rfilter").forEach(function (b) { b.classList.remove("active"); });
        btn.classList.add("active");
        renderReviewList();
      });
    });
  }

  function matchesFilter(item) {
    if (activeFilter === "all") return true;
    if (activeFilter === "correct") return item.is_correct === true;
    if (activeFilter === "wrong") return item.is_correct === false;
    if (activeFilter === "skipped") return item.your_answer === null;
    return true;
  }

  function renderReviewList() {
    const list = document.getElementById("review-list");
    const filtered = SCORE.review.filter(matchesFilter);
    if (!filtered.length) {
      list.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:30px 0;">No questions in this filter.</p>';
      return;
    }
    list.innerHTML = filtered.map(reviewItemHtml).join("");

    list.querySelectorAll(".solution-toggle").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const body = btn.nextElementSibling;
        const nowOpen = !body.classList.contains("open");
        body.classList.toggle("open", nowOpen);
        btn.classList.toggle("open", nowOpen);
        if (nowOpen) typeset(body);
      });
    });
    typeset(list);
  }

  function reviewItemHtml(item) {
    let statusTag, marksTag;
    if (item.your_answer === null) {
      statusTag = '<span class="rtag skipped">Unattempted</span>';
      marksTag = '<span class="rtag marks-zero">0 marks</span>';
    } else if (item.is_correct) {
      statusTag = '<span class="rtag correct">Correct</span>';
      marksTag = '<span class="rtag marks-pos">+' + item.marks + ' marks</span>';
    } else {
      statusTag = '<span class="rtag wrong">Incorrect</span>';
      marksTag = '<span class="rtag marks-zero">0 marks</span>';
    }

    let optsHtml = "";
    if (item.type !== "Numerical" && item.options && item.options.length) {
      optsHtml = '<div style="display:flex;flex-direction:column;gap:6px;margin-bottom:12px;">' +
        item.options.map(function (o) {
          const label = (o.text.match(/^\s*(\d+)\s*\)/) || [null, ""])[1];
          let style = "";
          if (label === item.correct_answer) style = "color:var(--green);font-weight:700;";
          else if (label === item.your_answer) style = "color:var(--red);font-weight:700;";
          return '<div style="' + style + '">' + (o.html || o.text) + "</div>";
        }).join("") +
        "</div>";
    }

    const answerRows =
      '<div class="review-answers">' +
      '<div class="review-answer-row"><span class="ra-label">Your answer</span><span class="ra-value">' + (item.your_answer === null ? "— not attempted —" : escapeHtml(item.your_answer)) + '</span></div>' +
      '<div class="review-answer-row"><span class="ra-label">Correct answer</span><span class="ra-value" style="color:var(--green);font-weight:700;">' + escapeHtml(item.correct_answer) + '</span></div>' +
      "</div>";

    return (
      '<div class="review-item">' +
        '<div class="review-item-head">' +
          '<div class="review-tags"><span class="rtag subj">' + item.type + '</span>' + statusTag + '</div>' +
          marksTag +
        '</div>' +
        '<div class="review-q-body">' + item.question_html + '</div>' +
        optsHtml +
        (item.type === "Numerical" ? answerRows : "") +
        '<button class="solution-toggle"><span>View solution</span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg></button>' +
        '<div class="solution-body">' + (item.type !== "Numerical" ? answerRows : "") + (item.solution_html || "No solution available.") + '</div>' +
      "</div>"
    );
  }

  function escapeHtml(v) {
    if (v === null || v === undefined) return "";
    return String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function typeset(container) {
    if (window.MathJax && window.MathJax.typesetPromise) {
      window.MathJax.typesetPromise([container]).catch(function () {});
    }
  }

  fetchResult();
})();