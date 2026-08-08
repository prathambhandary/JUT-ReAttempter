(function () {
  const grid = document.getElementById("test-grid");
  const poolSummary = document.getElementById("pool-summary");
  const errorBox = document.getElementById("form-error");
  const startBtn = document.getElementById("start-btn");
  const nameInput = document.getElementById("candidate-name");
  const rollInput = document.getElementById("roll-number");

  let TESTS = [];

  function showError(msg) {
    errorBox.textContent = msg;
    errorBox.classList.add("show");
  }
  function clearError() {
    errorBox.classList.remove("show");
    errorBox.textContent = "";
  }

  function renderGrid() {
    if (!TESTS.length) {
      grid.innerHTML = '<p style="color:var(--text-muted);font-size:0.9rem;">No JUT tests were found in the question bank. Add data to data/questions.json on the server.</p>';
      return;
    }
    grid.innerHTML = TESTS.map(function (t) {
      const id = "test-" + t.code;
      return (
        '<div class="test-chip">' +
        '<input type="checkbox" id="' + id + '" value="' + t.exam_number + '">' +
        '<label for="' + id + '">' +
        '<span>' + t.exam_type + ' ' + t.exam_number + '</span>' +
        '<span class="count">' + t.count + ' Q</span>' +
        '</label></div>'
      );
    }).join("");

    grid.querySelectorAll("input[type=checkbox]").forEach(function (cb) {
      cb.addEventListener("change", updateSummary);
    });
  }

  function selectedTests() {
    return Array.from(grid.querySelectorAll("input[type=checkbox]:checked")).map(function (cb) {
      return cb.value;
    });
  }

  function updateSummary() {
    const chosen = selectedTests();
    if (!chosen.length) {
      poolSummary.style.display = "none";
      return;
    }
    const totalQ = TESTS.filter(function (t) { return chosen.includes(t.exam_number); })
      .reduce(function (sum, t) { return sum + t.count; }, 0);
    poolSummary.style.display = "flex";
    poolSummary.innerHTML =
      "<span><b>" + chosen.length + "</b> test" + (chosen.length > 1 ? "s" : "") + " selected</span>" +
      "<span><b>" + totalQ + "</b> questions in pool</span>" +
      "<span><b>75</b> will be drawn for your paper</span>";
  }

  document.getElementById("select-all-btn").addEventListener("click", function () {
    grid.querySelectorAll("input[type=checkbox]").forEach(function (cb) { cb.checked = true; });
    updateSummary();
  });
  document.getElementById("clear-all-btn").addEventListener("click", function () {
    grid.querySelectorAll("input[type=checkbox]").forEach(function (cb) { cb.checked = false; });
    updateSummary();
  });

  function loadTests() {
    fetch("/api/tests_kcet")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        TESTS = data.tests || [];
        renderGrid();
      })
      .catch(function () {
        grid.innerHTML = '<p style="color:var(--red);font-size:0.9rem;">Could not reach the server to load available tests. Is the Flask app running?</p>';
      });
  }

  startBtn.addEventListener("click", function () {
    clearError();
    const name = nameInput.value.trim();
    const roll = rollInput.value.trim();
    const chosen = selectedTests();

    if (!name) { showError("Please enter your name to continue."); nameInput.focus(); return; }
    if (!chosen.length) { showError("Select at least one JUT test to build your paper from."); return; }

    startBtn.disabled = true;
    startBtn.textContent = "Building your paper…";

    fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ candidate_name: name, roll_number: roll, tests: chosen }),
    })
      .then(function (r) { return r.json().then(function (body) { return { ok: r.ok, body: body }; }); })
      .then(function (res) {
        if (!res.ok) {
          showError(res.body.error || "Could not generate a test paper.");
          startBtn.disabled = false;
          startBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3l14 9-14 9V3z"/></svg> Generate &amp; start test';
          return;
        }
        sessionStorage.setItem("jut-session", JSON.stringify(res.body));
        sessionStorage.removeItem("jut-progress");
        window.location.href = "/test";
      })
      .catch(function () {
        showError("Network error while generating your paper. Please try again.");
        startBtn.disabled = false;
        startBtn.textContent = "Generate & start test";
      });
  });

  loadTests();
})();
