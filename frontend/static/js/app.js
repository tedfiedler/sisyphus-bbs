// Site-wide behaviour. Loaded on every page.
//
// The Content-Security-Policy does not allow inline scripts or on* handlers,
// so destructive buttons declare their prompt with data-confirm="..." and
// this one listener asks the question for all of them.
document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-confirm]');
    if (el && !window.confirm(el.dataset.confirm)) {
        e.preventDefault();
    }
});
