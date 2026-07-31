document.addEventListener('DOMContentLoaded', function() {
    const toggleBtn = document.getElementById('darkModeToggle');
    const darkIcon = document.getElementById('darkIcon');
    const html = document.documentElement;

    // Check stored preference
    const storedTheme = localStorage.getItem('theme');
    if (storedTheme) {
        html.setAttribute('data-bs-theme', storedTheme);
        updateIcon(storedTheme);
    } else {
        // System preference
        if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
            html.setAttribute('data-bs-theme', 'dark');
            updateIcon('dark');
        }
    }

    toggleBtn.addEventListener('click', function() {
        const current = html.getAttribute('data-bs-theme');
        const next = current === 'light' ? 'dark' : 'light';
        html.setAttribute('data-bs-theme', next);
        localStorage.setItem('theme', next);
        updateIcon(next);
    });

    function updateIcon(theme) {
        if (theme === 'dark') {
            darkIcon.className = 'fas fa-sun';
        } else {
            darkIcon.className = 'fas fa-moon';
        }
    }

    // Auto-render KaTeX on dynamic content (accordion)
    // The base template already calls renderMathInElement on DOMContentLoaded,
    // but after accordion opens we need to re-render.
    document.addEventListener('shown.bs.collapse', function (e) {
        const target = e.target;
        if (typeof renderMathInElement === 'function') {
            renderMathInElement(target, {
                delimiters: [
                    {left: '$$', right: '$$', display: true},
                    {left: '\\[', right: '\\]', display: true},
                    {left: '$', right: '$', display: false},
                    {left: '\\(', right: '\\)', display: false}
                ],
                throwOnError: false
            });
        }
    });
});