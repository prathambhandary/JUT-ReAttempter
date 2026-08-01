// Dark/light theme toggle, shared across every page.
// The actual initial theme is applied by a tiny inline script in <head>
// (see base template) so there is no flash-of-wrong-theme on load.
(function () {
  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("jut-theme", theme);
  }

  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") || "light";
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const next = currentTheme() === "dark" ? "light" : "dark";
        applyTheme(next);
      });
    });
  });
})();
