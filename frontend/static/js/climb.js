// The Long Climb: keyboard shortcuts.
//
// Every choice on the page is an ordinary form button, so the game works
// without this file. With it, pressing a choice's letter presses its button,
// or, for a choice that takes a number, puts the cursor in its box.
document.addEventListener('keydown', (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey || e.repeat) return;
    const typing = e.target.closest('input, textarea, select');
    if (typing) return;
    const key = e.key.toLowerCase();
    if (key.length !== 1) return;
    const target = document.querySelector(`.climb-choices [data-key="${CSS.escape(key)}"]`);
    if (!target) return;
    e.preventDefault();
    if (target.tagName === 'BUTTON') {
        target.click();
    } else {
        target.focus();
    }
});
