/**
 * Simple Chat Card
 * Internal chat between all Home Assistant users.
 * Add to a dashboard with:
 *   type: custom:simple-chat-card
 *   title: Chat            # optional
 *   height: 480             # optional, px
 */

const USER_COLORS = [
  "#60a5fa", "#f472b6", "#34d399", "#fbbf24",
  "#a78bfa", "#fb7185", "#38bdf8", "#4ade80",
];

function colorForUser(userId) {
  let hash = 0;
  for (let i = 0; i < userId.length; i++) {
    hash = userId.charCodeAt(i) + ((hash << 5) - hash);
  }
  return USER_COLORS[Math.abs(hash) % USER_COLORS.length];
}

function initials(name) {
  return (name || "?")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join("");
}

function formatTime(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatDay(ts) {
  const d = new Date(ts * 1000);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  const sameDay = (a, b) =>
    a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  if (sameDay(d, today)) return "Dnes";
  if (sameDay(d, yesterday)) return "Včera";
  return d.toLocaleDateString([], { day: "numeric", month: "long", year: "numeric" });
}

class SimpleChatCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._messages = [];
    this._typingUsers = new Map(); // user_id -> timeout handle
    this._unsub = null;
    this._initialized = false;
  }

  setConfig(config) {
    this._config = {
      title: "Chat",
      height: 480,
      ...config,
    };
    this._render();
  }

  getCardSize() {
    return Math.round((this._config?.height || 480) / 50);
  }

  set hass(hass) {
    const firstRun = !this._hass;
    this._hass = hass;
    if (firstRun) {
      this._currentUserId = hass.user?.id;
      this._init();
    }
  }

  async _init() {
    if (this._initialized) return;
    this._initialized = true;

    const result = await this._hass.callWS({ type: "simple_chat/get_messages", limit: 100 });
    this._messages = result.messages || [];
    this._renderMessages();
    this._markVisibleAsRead();

    this._unsub = await this._hass.connection.subscribeMessage(
      (msg) => this._handleEvent(msg),
      { type: "simple_chat/subscribe" }
    );
  }

  disconnectedCallback() {
    if (this._unsub) this._unsub();
  }

  _handleEvent(msg) {
    const { event, data } = msg;
    if (event === "simple_chat_new_message") {
      const idx = this._messages.findIndex((m) => m.id === data.id);
      if (idx >= 0) this._messages[idx] = data;
      else this._messages.push(data);
      this._typingUsers.delete(data.user_id);
      this._renderMessages();
      this._markVisibleAsRead();
    } else if (event === "simple_chat_message_deleted") {
      this._messages = this._messages.filter((m) => m.id !== data.id);
      this._renderMessages();
    } else if (event === "simple_chat_messages_read") {
      for (const m of this._messages) {
        if (data.message_ids.includes(m.id) && !m.read_by.includes(data.user_id)) {
          m.read_by.push(data.user_id);
        }
      }
      this._renderReceipts();
    } else if (event === "simple_chat_reaction") {
      const idx = this._messages.findIndex((m) => m.id === data.id);
      if (idx >= 0) this._messages[idx] = data;
      this._renderMessages();
    } else if (event === "simple_chat_typing") {
      if (data.user_id === this._currentUserId) return;
      clearTimeout(this._typingUsers.get(data.user_id));
      this._typingUsers.set(
        data.user_id,
        setTimeout(() => {
          this._typingUsers.delete(data.user_id);
          this._renderTyping();
        }, 4000)
      );
      this._renderTyping();
    }
  }

  _markVisibleAsRead() {
    const unread = this._messages
      .filter((m) => !m.read_by.includes(this._currentUserId))
      .map((m) => m.id);
    if (unread.length) {
      this._hass.callWS({ type: "simple_chat/mark_read", message_ids: unread });
    }
  }

  async _send(text) {
    if (!text.trim()) return;
    await this._hass.callWS({ type: "simple_chat/send_message", text: text.trim() });
  }

  async _delete(id) {
    await this._hass.callWS({ type: "simple_chat/delete_message", message_id: id });
  }

  async _react(id, emoji) {
    await this._hass.callWS({ type: "simple_chat/toggle_reaction", message_id: id, emoji });
  }

  _notifyTyping() {
    const now = Date.now();
    if (this._lastTypingSent && now - this._lastTypingSent < 2000) return;
    this._lastTypingSent = now;
    this._hass.callWS({ type: "simple_chat/typing" });
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          --sc-bg: linear-gradient(135deg, #1a1f2e 0%, #1e2438 100%);
          --sc-accent: #60a5fa;
          --sc-radius: 16px;
          font-family: var(--paper-font-body1_-_font-family, "Roboto", sans-serif);
        }
        .card {
          background: var(--sc-bg);
          border-radius: var(--sc-radius);
          overflow: hidden;
          display: flex;
          flex-direction: column;
          height: ${this._config.height}px;
          box-shadow: 0 4px 20px rgba(0,0,0,0.25);
        }
        .header {
          padding: 14px 18px;
          font-size: 16px;
          font-weight: 600;
          color: #fff;
          border-bottom: 1px solid rgba(255,255,255,0.08);
          display: flex;
          align-items: center;
          justify-content: space-between;
        }
        .header .unread {
          background: var(--sc-accent);
          color: #0f1420;
          font-size: 11px;
          font-weight: 700;
          border-radius: 999px;
          padding: 2px 8px;
          display: none;
        }
        .messages {
          flex: 1;
          overflow-y: auto;
          padding: 12px 14px;
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .messages::-webkit-scrollbar { width: 6px; }
        .messages::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 3px; }
        .day-divider {
          text-align: center;
          color: rgba(255,255,255,0.4);
          font-size: 11px;
          margin: 10px 0 4px;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }
        .row {
          display: flex;
          gap: 8px;
          align-items: flex-end;
          margin-top: 6px;
        }
        .row.own { flex-direction: row-reverse; }
        .avatar {
          width: 28px;
          height: 28px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 11px;
          font-weight: 700;
          color: #0f1420;
          flex-shrink: 0;
        }
        .bubble-wrap { max-width: 74%; display: flex; flex-direction: column; }
        .row.own .bubble-wrap { align-items: flex-end; }
        .sender-name {
          font-size: 11px;
          color: rgba(255,255,255,0.5);
          margin: 0 4px 2px;
        }
        .bubble {
          position: relative;
          padding: 8px 12px;
          border-radius: var(--sc-radius);
          color: #fff;
          font-size: 14px;
          line-height: 1.4;
          background: rgba(255,255,255,0.08);
          word-break: break-word;
          cursor: default;
        }
        .row.own .bubble {
          background: var(--sc-accent);
          color: #0f1420;
          border-bottom-right-radius: 4px;
        }
        .row:not(.own) .bubble { border-bottom-left-radius: 4px; }
        .meta {
          font-size: 10px;
          color: rgba(255,255,255,0.35);
          margin: 2px 4px 0;
          display: flex;
          gap: 4px;
          align-items: center;
        }
        .row.own .meta { color: rgba(255,255,255,0.45); }
        .edited { font-style: italic; }
        .reactions { display: flex; gap: 4px; margin-top: 3px; flex-wrap: wrap; }
        .row.own .reactions { justify-content: flex-end; }
        .reaction-chip {
          background: rgba(255,255,255,0.1);
          border-radius: 999px;
          padding: 1px 6px;
          font-size: 11px;
          color: #fff;
          cursor: pointer;
          user-select: none;
        }
        .reaction-chip.mine { background: var(--sc-accent); color: #0f1420; }
        .bubble-actions {
          display: none;
          gap: 6px;
          position: absolute;
          top: -18px;
          right: 0;
        }
        .row.own .bubble:hover .bubble-actions { display: flex; }
        .bubble-actions span {
          cursor: pointer;
          font-size: 13px;
          opacity: 0.7;
        }
        .bubble-actions span:hover { opacity: 1; }
        .typing {
          font-size: 12px;
          color: rgba(255,255,255,0.45);
          padding: 2px 14px 6px;
          min-height: 16px;
          font-style: italic;
        }
        .input-bar {
          display: flex;
          gap: 8px;
          padding: 10px 12px;
          border-top: 1px solid rgba(255,255,255,0.08);
        }
        .input-bar input {
          flex: 1;
          background: rgba(255,255,255,0.08);
          border: none;
          border-radius: var(--sc-radius);
          padding: 10px 14px;
          color: #fff;
          font-size: 14px;
          outline: none;
        }
        .input-bar input::placeholder { color: rgba(255,255,255,0.35); }
        .input-bar button {
          background: var(--sc-accent);
          color: #0f1420;
          border: none;
          border-radius: var(--sc-radius);
          padding: 0 18px;
          font-weight: 700;
          font-size: 14px;
          cursor: pointer;
        }
        .input-bar button:disabled { opacity: 0.4; cursor: default; }
        .empty {
          color: rgba(255,255,255,0.35);
          font-size: 13px;
          text-align: center;
          margin-top: 30px;
        }
      </style>
      <div class="card">
        <div class="header">
          <span>${this._config.title}</span>
          <span class="unread" id="unread-badge"></span>
        </div>
        <div class="messages" id="messages"></div>
        <div class="typing" id="typing"></div>
        <div class="input-bar">
          <input id="text-input" type="text" placeholder="Napíš správu…" autocomplete="off" />
          <button id="send-btn">Odoslať</button>
        </div>
      </div>
    `;

    const input = this.shadowRoot.getElementById("text-input");
    const sendBtn = this.shadowRoot.getElementById("send-btn");

    const doSend = () => {
      this._send(input.value);
      input.value = "";
    };
    sendBtn.addEventListener("click", doSend);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") doSend();
    });
    input.addEventListener("input", () => this._notifyTyping());
  }

  _renderMessages() {
    const container = this.shadowRoot?.getElementById("messages");
    if (!container) return;

    if (!this._messages.length) {
      container.innerHTML = `<div class="empty">Zatiaľ žiadne správy. Napíš prvú!</div>`;
      return;
    }

    let html = "";
    let lastDay = null;
    let lastSender = null;

    for (const m of this._messages) {
      const day = formatDay(m.timestamp);
      if (day !== lastDay) {
        html += `<div class="day-divider">${day}</div>`;
        lastDay = day;
        lastSender = null;
      }
      const isOwn = m.user_id === this._currentUserId;
      const color = m.color || colorForUser(m.user_id);
      const showAvatar = lastSender !== m.user_id;
      lastSender = m.user_id;

      const reactionsHtml = Object.entries(m.reactions || {})
        .map(([emoji, users]) => {
          const mine = users.includes(this._currentUserId) ? "mine" : "";
          return `<span class="reaction-chip ${mine}" data-react="${m.id}:${emoji}">${emoji} ${users.length}</span>`;
        })
        .join("");

      html += `
        <div class="row ${isOwn ? "own" : ""}">
          ${
            showAvatar
              ? `<div class="avatar" style="background:${color}">${initials(m.user_name)}</div>`
              : `<div class="avatar" style="visibility:hidden"></div>`
          }
          <div class="bubble-wrap">
            ${!isOwn && showAvatar ? `<div class="sender-name">${m.user_name}</div>` : ""}
            <div class="bubble">
              ${isOwn ? `<div class="bubble-actions">
                <span data-del="${m.id}" title="Zmazať">🗑</span>
                <span data-emoji="${m.id}" title="Reakcia">🙂</span>
              </div>` : ""}
              ${this._escape(m.text)}
            </div>
            <div class="meta">
              <span>${formatTime(m.timestamp)}</span>
              ${m.edited ? `<span class="edited">upravené</span>` : ""}
              ${isOwn ? `<span class="read-state" data-read-for="${m.id}">${this._readLabel(m)}</span>` : ""}
              ${!isOwn ? `<span data-emoji="${m.id}" style="cursor:pointer">🙂</span>` : ""}
            </div>
            <div class="reactions">${reactionsHtml}</div>
          </div>
        </div>
      `;
    }

    const wasAtBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight < 60;
    container.innerHTML = html;
    if (wasAtBottom || lastSender === this._currentUserId) {
      container.scrollTop = container.scrollHeight;
    }

    container.querySelectorAll("[data-del]").forEach((el) =>
      el.addEventListener("click", () => this._delete(el.dataset.del))
    );
    container.querySelectorAll("[data-emoji]").forEach((el) =>
      el.addEventListener("click", () => this._react(el.dataset.emoji, "👍"))
    );
    container.querySelectorAll("[data-react]").forEach((el) =>
      el.addEventListener("click", () => {
        const [id, emoji] = el.dataset.react.split(":");
        this._react(id, emoji);
      })
    );

    this._updateUnreadBadge();
  }

  _renderReceipts() {
    const container = this.shadowRoot?.getElementById("messages");
    if (!container) return;
    for (const m of this._messages) {
      const el = container.querySelector(`[data-read-for="${m.id}"]`);
      if (el) el.textContent = this._readLabel(m);
    }
  }

  _readLabel(message) {
    const others = message.read_by.filter((id) => id !== message.user_id);
    return others.length ? `✓✓ videné` : `✓ odoslané`;
  }

  _renderTyping() {
    const el = this.shadowRoot?.getElementById("typing");
    if (!el) return;
    const names = [...this._typingUsers.keys()];
    el.textContent = names.length ? `píše…` : "";
  }

  _updateUnreadBadge() {
    const badge = this.shadowRoot?.getElementById("unread-badge");
    if (!badge) return;
    const unread = this._messages.filter(
      (m) => !m.read_by.includes(this._currentUserId)
    ).length;
    if (unread > 0) {
      badge.textContent = unread;
      badge.style.display = "inline-block";
    } else {
      badge.style.display = "none";
    }
  }

  _escape(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }
}

customElements.define("simple-chat-card", SimpleChatCard);

// Register in the Lovelace card picker
window.customCards = window.customCards || [];
window.customCards.push({
  type: "simple-chat-card",
  name: "Simple Chat",
  description: "Interný chat medzi všetkými užívateľmi Home Assistant.",
});
