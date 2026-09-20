// Chat page: WebSocket client, channel switching, and DM start.
//
// Page-specific values arrive as data-* attributes on #chat-layout rather
// than being templated into script text, which the Content-Security-Policy
// would refuse to run.
const layout = document.getElementById('chat-layout');
const sidebar = document.getElementById('chat-sidebar');
const msgDiv = document.getElementById('chat-messages');
const msgInput = document.getElementById('msg-input');
const chatHeading = document.getElementById('chat-heading');
const isAdmin = layout.dataset.admin === 'true';
const csrfToken = layout.dataset.csrf;
let currentChannel = layout.dataset.channel;
let ws = null;
let connected = false;
let reconnectDelay = 1000;
const MAX_RECONNECT_DELAY = 30000;

function connect() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${proto}//${location.host}/ws/chat`);

    ws.onopen = () => {
        connected = true;
        reconnectDelay = 1000;
        if (currentChannel !== 'lobby') {
            ws.send(JSON.stringify({ type: 'switch', channel: currentChannel }));
        }
    };

    ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.type === 'ping') {
            ws.send(JSON.stringify({ type: 'pong' }));
            return;
        }
        if (data.type === 'history') {
            msgDiv.innerHTML = '';
            for (const msg of data.messages) {
                appendMessage(msg);
            }
            return;
        }
        if (data.type === 'error') {
            appendSystem(data.message || 'Error');
            return;
        }
        if (data.type === 'announcement') {
            appendAnnouncement(data);
            return;
        }
        appendMessage(data);
    };

    ws.onclose = (e) => {
        connected = false;
        if (e.code === 4001) {
            // Session ended (logout, expiry); reconnecting would only loop.
            location.href = '/';
            return;
        }
        appendSystem('Disconnected. Reconnecting...');
        scheduleReconnect();
    };

    ws.onerror = () => {
        ws.close();
    };
}

function scheduleReconnect() {
    setTimeout(() => {
        connect();
        reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY);
    }, reconnectDelay);
}

function appendMessage(data) {
    const div = document.createElement('div');
    if (data.id) div.dataset.msgId = data.id;
    const time = data.timestamp ? data.timestamp.substring(11, 19) : '';
    let delBtn = '';
    if (isAdmin && data.id) {
        delBtn = ` <form method="post" action="/admin/chat/${Number(data.id)}/delete" class="inline-form ml-5">`
            + `<input type="hidden" name="csrf_token" value="${escapeHtml(csrfToken)}">`
            + `<button type="submit" class="btn-danger btn-small">Del</button></form>`;
    }
    div.innerHTML = `<span class="msg-time">[${escapeHtml(time || data.created_at || '')}]</span> <span class="msg-user">&lt;${escapeHtml(data.username)}&gt;</span> ${escapeHtml(data.message)}${delBtn}`;
    msgDiv.appendChild(div);
    msgDiv.scrollTop = msgDiv.scrollHeight;
}

function appendAnnouncement(data) {
    const div = document.createElement('div');
    div.className = 'chat-announcement';
    const time = data.timestamp ? data.timestamp.substring(11, 19) : '';
    div.innerHTML = `<span class="msg-time">[${escapeHtml(time)}]</span> <strong>[ANNOUNCE]</strong> &lt;${escapeHtml(data.username)}&gt; ${escapeHtml(data.message)}`;
    msgDiv.appendChild(div);
    msgDiv.scrollTop = msgDiv.scrollHeight;
}

function appendSystem(text) {
    const div = document.createElement('div');
    div.className = 'chat-system';
    div.textContent = '*** ' + text;
    msgDiv.appendChild(div);
    msgDiv.scrollTop = msgDiv.scrollHeight;
}

function sendMessage() {
    const text = msgInput.value.trim();
    if (!text || !connected) return;
    ws.send(JSON.stringify({ message: text }));
    msgInput.value = '';
}

function switchChannel(name) {
    if (name === currentChannel) return;
    currentChannel = name;
    chatHeading.textContent = 'Chat - #' + name;
    document.querySelectorAll('.channel-item').forEach((el) => {
        const isTarget = el.dataset.channel === name;
        el.classList.toggle('active', isTarget);
        // Opening a DM clears its unread highlight.
        if (isTarget) el.classList.remove('unread');
    });
    if (connected) {
        ws.send(JSON.stringify({ type: 'switch', channel: name }));
    }
}

function startDM(userId) {
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/chat/dm/' + Number(userId);
    const token = document.createElement('input');
    token.type = 'hidden';
    token.name = 'csrf_token';
    token.value = csrfToken;
    form.appendChild(token);
    document.body.appendChild(form);
    form.submit();
}

function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML.replace(/"/g, '&quot;');
}

// One delegated listener for the sidebar. [data-switch] marks what is
// clickable (for a named channel that is the label, not the whole row, so
// the admin's delete button next to it does not also switch channels); the
// channel name itself lives on the enclosing .channel-item.
sidebar.addEventListener('click', (e) => {
    const switcher = e.target.closest('[data-switch]');
    if (switcher) {
        switchChannel(switcher.closest('.channel-item').dataset.channel);
        return;
    }
    const dmUser = e.target.closest('[data-dm-user]');
    if (dmUser) {
        startDM(dmUser.dataset.dmUser);
    }
});

document.getElementById('send-btn').addEventListener('click', sendMessage);
msgInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendMessage();
});

connect();
