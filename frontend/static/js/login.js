// Login / New User tab switching on the landing page.
const panels = {
    login: document.getElementById('login-form'),
    register: document.getElementById('register-form'),
};

function showTab(name) {
    for (const [key, panel] of Object.entries(panels)) {
        panel.classList.toggle('hidden', key !== name);
    }
    document.querySelectorAll('.tab').forEach((tab) => {
        tab.classList.toggle('active', tab.dataset.tab === name);
    });
}

document.querySelectorAll('.tab').forEach((tab) => {
    tab.addEventListener('click', () => showTab(tab.dataset.tab));
});
