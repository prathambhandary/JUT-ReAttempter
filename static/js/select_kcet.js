(function () {
  const grid = document.getElementById("kcet-subject-grid");
  const errorBox = document.getElementById("form-error");
  const nameInput = document.getElementById("candidate-name");
  const modal = document.getElementById("modal-confirm-kcet");
  const confirmTitle = document.getElementById("confirm-kcet-title");
  const confirmBtn = document.getElementById("btn-confirm-start-kcet");

  let SUBJECTS = [];
  let pendingSubject = null;

  function showError(msg) {
    errorBox.textContent = msg;
    errorBox.classList.add("show");
  }
  function clearError() {
    errorBox.classList.remove("show");
    errorBox.textContent = "";
  }

  function subjectIcon(subject) {
    if (subject === "Physics") {
      return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="2.2"/><ellipse cx="12" cy="12" rx="10" ry="4.2"/><ellipse cx="12" cy="12" rx="10" ry="4.2" transform="rotate(60 12 12)"/><ellipse cx="12" cy="12" rx="10" ry="4.2" transform="rotate(120 12 12)"/></svg>';
    }
    if (subject === "Chemistry") {
      return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h6M10 3v6l-5.5 9.5A1.5 1.5 0 0 0 5.8 21h12.4a1.5 1.5 0 0 0 1.3-2.5L14 9V3"/><path d="M8 15h8"/></svg>';
    }
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16v16H4z"/><path d="M8 8h.01M12 8h4M8 12h.01M12 12h4M8 16h.01M12 16h4"/></svg>';
  }

  function renderGrid() {
    if (!SUBJECTS.length) {
      grid.innerHTML = '<p style="color:var(--text-muted);font-size:0.9rem;">No KCET questions were found in the question bank.</p>';
      return;
    }
    grid.innerHTML = SUBJECTS.map(function (s) {
      const disabled = s.count === 0;
      return (
        '<button type="button" class="kcet-subject-card' + (disabled ? " disabled" : "") + '" data-subject="' + s.subject + '"' + (disabled ? " disabled" : "") + '>' +
        '<span class="kcet-subject-icon">' + subjectIcon(s.subject) + '</span>' +
        '<span class="kcet-subject-name">' + s.subject + '</span>' +
        '<span class="kcet-subject-count">' + (disabled ? "No questions yet" : s.count + " questions in pool") + '</span>' +
        '<span class="kcet-subject-cta">' + (disabled ? "Unavailable" : "Attempt random mock — 60 mins") + '</span>' +
        "</button>"
      );
    }).join("");

    grid.querySelectorAll(".kcet-subject-card:not(.disabled)").forEach(function (card) {
      card.addEventListener("click", function () {
        clearError();
        const name = nameInput.value.trim();
        if (!name) { showError("Please enter your name to continue."); nameInput.focus(); return; }
        openConfirm(card.getAttribute("data-subject"));
      });
    });
  }

  function openConfirm(subject) {
    pendingSubject = subject;
    confirmTitle.textContent = "Start " + subject + " mock test?";
    modal.classList.add("open");
  }
  function closeConfirm() {
    modal.classList.remove("open");
    pendingSubject = null;
  }

  document.querySelectorAll("[data-close-modal='modal-confirm-kcet']").forEach(function (btn) {
    btn.addEventListener("click", closeConfirm);
  });
  modal.addEventListener("click", function (e) {
    if (e.target === modal) closeConfirm();
  });

  confirmBtn.addEventListener("click", function () {
    if (!pendingSubject) return;
    const name = nameInput.value.trim();
    const subject = pendingSubject;

    confirmBtn.disabled = true;
    confirmBtn.textContent = "Building your paper…";

    fetch("/api/generate_kcet", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ candidate_name: name, subject: subject }),
    })
      .then(function (r) { return r.json().then(function (body) { return { ok: r.ok, body: body }; }); })
      .then(function (res) {
        confirmBtn.disabled = false;
        confirmBtn.textContent = "Start test";
        if (!res.ok) {
          closeConfirm();
          showError(res.body.error || "Could not generate a test paper.");
          return;
        }
        sessionStorage.setItem("kcet-session", JSON.stringify(res.body));
        sessionStorage.removeItem("kcet-progress");
        window.location.href = "/test_kcet";
      })
      .catch(function () {
        confirmBtn.disabled = false;
        confirmBtn.textContent = "Start test";
        closeConfirm();
        showError("Network error while generating your paper. Please try again.");
      });
  });

  function loadSubjects() {
    fetch("/api/subjects_kcet")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        SUBJECTS = data.subjects || [];
        renderGrid();
      })
      .catch(function () {
        grid.innerHTML = '<p style="color:var(--red);font-size:0.9rem;">Could not reach the server to load subjects. Is the Flask app running?</p>';
      });
  }

  loadSubjects();
})();