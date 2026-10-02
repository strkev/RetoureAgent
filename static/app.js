/**
 * app.js - Frontend-Logik für den Retouren-Agent Prototyp
 * Behandelt Chat-Interaktion, Markdown-Rendering, State-Inspector und API-Konfiguration.
 */

const INITIAL_WELCOME = "Guten Tag! Wie kann ich Ihnen mit Ihrer Bestellung oder Retoure weiterhelfen?";

let currentSessionId = "session-" + Math.random().toString(36).substring(2, 9);
let chatHistory = [
  {
    id: "msg-welcome",
    role: "bot",
    content: INITIAL_WELCOME,
    time: formatCurrentTime()
  }
];

let apiConfig = {
  apiKey: localStorage.getItem('retouren_api_key') || '',
  apiUrl: localStorage.getItem('retouren_api_url') || '',
  model: localStorage.getItem('retouren_model') || ''
};

function formatCurrentTime() {
  const now = new Date();
  return now.getHours().toString().padStart(2, '0') + ':' + now.getMinutes().toString().padStart(2, '0');
}

// Ansichtswechsel (1 = Split Auditor, 2 = Floating Widget)
function switchView(viewIndex) {
  document.querySelectorAll('.view-container').forEach(el => el.classList.remove('active'));

  const targetView = document.getElementById('view' + viewIndex);
  if (targetView) targetView.classList.add('active');

  setTimeout(() => {
    const inp = document.getElementById('input-v' + viewIndex);
    if (inp) inp.focus();
    scrollToBottom();
  }, 50);
}

function scrollToBottom() {
  [1, 2].forEach(id => {
    const el = document.getElementById('messages-v' + id);
    if (el) el.scrollTop = el.scrollHeight;
  });
}

function renderMarkdown(content) {
  if (!content) return '';
  if (window.marked && typeof window.marked.parse === 'function') {
    try {
      return window.marked.parse(content, { breaks: true, gfm: true });
    } catch (e) {
      console.warn("Markdown parsing fallback", e);
    }
  }
  return escapeHtml(content).replace(/\n/g, '<br>');
}

// Rendert alle Chat-Nachrichten in beiden Ansichten
function renderMessages() {
  // Garantiere, dass die Anfangsnachricht genau einmal zu Beginn vorhanden ist
  if (chatHistory.length === 0) {
    chatHistory.push({
      id: "msg-welcome",
      role: "bot",
      content: INITIAL_WELCOME,
      time: formatCurrentTime()
    });
  } else if (!chatHistory.some(m => m.id === "msg-welcome") && chatHistory[0].role === "user") {
    chatHistory.unshift({
      id: "msg-welcome",
      role: "bot",
      content: INITIAL_WELCOME,
      time: formatCurrentTime()
    });
  }

  const htmlContent = chatHistory.map(msg => {
    const isUser = msg.role === 'user';
    const actionCardHtml = msg.action_card ? renderActionCard(msg.action_card, msg.id) : '';

    if (!isUser && (msg.loading || (!msg.content && !msg.action_card))) {
      return `
        <div class="message bot">
          <div class="bubble loading" title="Antwort wird generiert..."></div>
          <div class="meta">${escapeHtml(msg.time || formatCurrentTime())}</div>
        </div>
      `;
    }

    const bodyHtml = renderMarkdown(msg.content);

    return `
      <div class="message ${isUser ? 'user' : 'bot'}">
        <div class="bubble">${bodyHtml}${actionCardHtml}</div>
        <div class="meta">${escapeHtml(msg.time || formatCurrentTime())}</div>
      </div>
    `;
  }).join('');

  [1, 2].forEach(id => {
    const container = document.getElementById('messages-v' + id);
    if (container) container.innerHTML = htmlContent;
  });

  scrollToBottom();

  setTimeout(() => {
    document.querySelectorAll('.card-return-confirm').forEach(card => {
      const firstCb = card.querySelector('.return-item-checkbox');
      if (firstCb) updateReturnSummary(firstCb);
    });
  }, 30);
}

function escapeHtml(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Rendert interaktive Action-Cards (Retourenlabel, Support-Ticket, Login-Widget, Profildaten)
function renderActionCard(card, msgId) {
  if (!card) return '';

  if (card.type === 'account_login') {
    return `
      <div class="card-action card-auth" data-msg-id="${msgId}">
        <div class="card-action-header-row">
          <div class="card-action-header">
            <i class="fa-solid fa-arrow-right-to-bracket" style="color: var(--secondary);"></i>
            <span class="card-action-title">${escapeHtml(card.title)}</span>
          </div>
          <button type="button" class="card-dismiss-btn" onclick="cancelAccountWidget(this)" title="Abbrechen">
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>
        <div class="card-action-meta">${escapeHtml(card.meta)}</div>
        <div class="card-auth-form">
          <div class="card-form-row">
            <input type="text" class="card-input auth-login-input" placeholder="E-Mail oder ID" autocomplete="username" onkeydown="if(event.key==='Enter') submitAccountLogin(this)">
          </div>
          <div class="card-form-row">
            <input type="password" class="card-input auth-pwd-input" placeholder="Passwort" autocomplete="current-password" onkeydown="if(event.key==='Enter') submitAccountLogin(this)">
          </div>
          <div class="card-form-actions">
            <button type="button" class="card-action-btn-primary auth-submit-btn" onclick="submitAccountLogin(this)">
              <span>Anmelden</span>
              <i class="fa-solid fa-arrow-right"></i>
            </button>
          </div>
          <div class="card-feedback-error"></div>
          <div class="card-feedback-msg"></div>
        </div>
      </div>
    `;
  }

  if (card.type === 'account_profile') {
    const acc = card.account || {};
    return `
      <div class="card-action card-profile" data-msg-id="${msgId}">
        <div class="card-action-header-row">
          <div class="card-action-header">
            <i class="fa-solid fa-id-card" style="color: var(--text-main);"></i>
            <span class="card-action-title">${escapeHtml(card.title)}</span>
          </div>
          <button type="button" class="card-dismiss-btn" onclick="cancelAccountWidget(this)" title="Schließen">
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>
        <div class="card-action-meta">${escapeHtml(card.meta)}</div>
        <div class="card-profile-form">
          <div class="card-form-grid">
            <div class="card-form-field">
              <label class="card-field-label">Vorname</label>
              <input type="text" class="card-input prof-name-input" value="${escapeHtml(acc.name || '')}" placeholder="Vorname">
            </div>
            <div class="card-form-field">
              <label class="card-field-label">Nachname</label>
              <input type="text" class="card-input prof-nachname-input" value="${escapeHtml(acc.nachname || '')}" placeholder="Nachname">
            </div>
          </div>
          <div class="card-form-field">
            <label class="card-field-label">Lieferadresse</label>
            <input type="text" class="card-input prof-adresse-input" value="${escapeHtml(acc.adresse || '')}" placeholder="Adresse">
          </div>
          <div class="card-form-grid">
            <div class="card-form-field">
              <label class="card-field-label">Land</label>
              <input type="text" class="card-input prof-land-input" value="${escapeHtml(acc.land || 'Deutschland')}" placeholder="Land">
            </div>
            <div class="card-form-field">
              <label class="card-field-label">Telefon</label>
              <input type="text" class="card-input prof-phone-input" value="${escapeHtml(acc.telefonnummer || '')}" placeholder="Telefon">
            </div>
          </div>
          <div class="card-form-field">
            <label class="card-field-label"><i class="fa-solid fa-lock"></i> E-Mail (geschützt)</label>
            <input type="text" class="card-input card-input-locked" value="${escapeHtml(acc.email || '')}" placeholder="E-Mail" disabled>
          </div>
          <div class="card-form-field">
            <label class="card-field-label"><i class="fa-solid fa-lock"></i> Account-ID (geschützt)</label>
            <input type="text" class="card-input card-input-locked" value="${escapeHtml(acc.account_id || '')}" placeholder="Account-ID" disabled>
          </div>
          <div class="card-form-actions">
            <button type="button" class="card-action-btn-primary prof-submit-btn" onclick="submitProfileUpdate(this)">
              <span>Änderungen speichern</span>
              <i class="fa-solid fa-check"></i>
            </button>
          </div>
          <div class="card-feedback-error"></div>
          <div class="card-feedback-msg"></div>
        </div>
      </div>
    `;
  }

  if (card.type === 'return_selection_confirm') {
    const items = card.items || [];
    const isRefund = card.return_type === 'refund';
    const policyDesc = card.policy_desc || (isRefund ? 'Volle Kaufpreiserstattung (14-Tage-Frist)' : 'Store-Credit Warengutschein (15-30 Tage Kulanz)');
    const orderId = card.order_id || '';

    const itemsHtml = items.map((it, idx) => {
      const itId = it.item_id || `ART-${idx + 1}`;
      const itName = it.name || it.bezeichnung || String(it);
      const itPrice = typeof it.price === 'number' ? it.price : (typeof it.preis === 'number' ? it.preis : 0.0);
      return `
        <label class="return-item-row" data-item-id="${escapeHtml(itId)}" data-item-price="${itPrice}">
          <input type="checkbox" class="return-item-checkbox" checked onchange="updateReturnSummary(this)">
          <div class="return-item-info">
            <span class="return-item-name">${escapeHtml(itName)}</span>
            <span class="return-item-sub">Art.-Nr.: ${escapeHtml(itId)}</span>
          </div>
          <div class="return-item-price">${itPrice.toFixed(2)} €</div>
        </label>
      `;
    }).join('');

    return `
      <div class="card-action card-return-confirm" data-msg-id="${msgId}" data-order-id="${escapeHtml(orderId)}" data-return-type="${escapeHtml(card.return_type || 'refund')}">
        <div class="card-action-header-row">
          <div class="card-action-header">
            <i class="fa-solid fa-boxes-packing" style="color: var(--secondary);"></i>
            <span class="card-action-title">${escapeHtml(card.title)}</span>
          </div>
          <button type="button" class="card-dismiss-btn" onclick="cancelReturnWidget(this)" title="Abbrechen">
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>
        <div class="card-action-meta">${escapeHtml(card.meta)}</div>
        <div class="card-policy-pill"><i class="fa-solid fa-shield-halved"></i> ${escapeHtml(policyDesc)}</div>
        
        <div class="return-items-list">
          ${itemsHtml}
        </div>

        <div class="return-summary-box">
          <div class="return-summary-row">
            <span>Ausgewählte Artikel:</span>
            <strong class="return-selected-count">${items.length} von ${items.length}</strong>
          </div>
          <div class="return-summary-row return-summary-total">
            <span>${isRefund ? 'Erstattungsbetrag:' : 'Store-Guthaben:'}</span>
            <strong class="return-total-amount">0.00 €</strong>
          </div>
        </div>

        <div class="card-form-actions">
          <button type="button" class="card-action-btn-primary return-submit-btn" onclick="submitReturnConfirmation(this)">
            <i class="fa-solid fa-check"></i>
            <span>Retoure verbindlich abschließen</span>
          </button>
        </div>
        <div class="card-feedback-error"></div>
      </div>
    `;
  }

  let cardClass = 'card-action';
  if (card.type.includes('refund')) cardClass += ' card-refund';
  else if (card.type.includes('credit')) cardClass += ' card-credit';
  else if (card.type.includes('escalation')) cardClass += ' card-escalation';

  return `
    <div class="${cardClass}">
      <div class="card-action-title">${escapeHtml(card.title)}</div>
      <div class="card-action-meta">${escapeHtml(card.meta).replace(/\n/g, '<br>')}</div>
      ${card.link_url && card.link_url !== '#' ? `<a href="${card.link_url}" target="_blank" class="card-action-btn">${escapeHtml(card.link_text)}</a>` : ''}
    </div>
  `;
}

// Bricht das Login- bzw. Profildaten-Widget ab und blendet es aus
function cancelAccountWidget(triggerEl) {
  const card = triggerEl ? triggerEl.closest('.card-action') : null;
  const msgId = card ? card.getAttribute('data-msg-id') : null;

  if (msgId) {
    const item = chatHistory.find(m => m.id === msgId);
    if (item) item.action_card = null;
  } else {
    for (let i = chatHistory.length - 1; i >= 0; i--) {
      if (chatHistory[i].action_card && (chatHistory[i].action_card.type === 'account_login' || chatHistory[i].action_card.type === 'account_profile')) {
        chatHistory[i].action_card = null;
        break;
      }
    }
  }

  renderMessages();

  // Backend informieren, damit das Login-Widget im Session-State abgemeldet/geschlossen wird
  fetch('/api/auth/cancel', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: currentSessionId })
  }).catch(err => console.warn("Widget cancel failed:", err));
}

function mergeMessagesPreservingCards(backendMessages) {
  if (!backendMessages || !Array.isArray(backendMessages)) return [];
  return backendMessages.map((newMsg, idx) => {
    // Falls Backend auf früheren Nachrichten keine Action-Card hat, aber im Frontend eine permanente Card vorlag (z.B. Download-Label)
    if (!newMsg.action_card && chatHistory[idx] && chatHistory[idx].action_card) {
      const oldType = chatHistory[idx].action_card.type;
      if (oldType !== 'account_login' && oldType !== 'account_profile' && oldType !== 'return_selection_confirm') {
        return { ...newMsg, action_card: chatHistory[idx].action_card };
      }
    }
    return newMsg;
  });
}

// Aktualisiert Live-Summe und Zähler in der Retouren-Auswahl-Karte
function updateReturnSummary(triggerEl) {
  const card = triggerEl ? triggerEl.closest('.card-return-confirm') : document.querySelector('.card-return-confirm');
  if (!card) return;

  const rows = card.querySelectorAll('.return-item-row');
  let selectedCount = 0;
  let totalAmount = 0.0;

  rows.forEach(row => {
    const cb = row.querySelector('.return-item-checkbox');
    const price = parseFloat(row.getAttribute('data-item-price')) || 0.0;
    if (cb && cb.checked) {
      selectedCount++;
      totalAmount += price;
      row.classList.add('selected');
    } else {
      row.classList.remove('selected');
    }
  });

  const countEl = card.querySelector('.return-selected-count');
  if (countEl) countEl.textContent = `${selectedCount} von ${rows.length}`;

  const amountEl = card.querySelector('.return-total-amount');
  if (amountEl) amountEl.textContent = `${totalAmount.toFixed(2)} €`;

  const submitBtn = card.querySelector('.return-submit-btn');
  const errEl = card.querySelector('.card-feedback-error');
  if (submitBtn) {
    submitBtn.disabled = selectedCount === 0;
    if (selectedCount === 0 && errEl) {
      errEl.textContent = 'Bitte wählen Sie mindestens einen Artikel zur Rücksendung aus.';
      errEl.style.display = 'block';
    } else if (errEl) {
      errEl.style.display = 'none';
    }
  }
}

// Verbindliche Retourenbestätigung absenden
async function submitReturnConfirmation(triggerEl) {
  const card = triggerEl ? triggerEl.closest('.card-return-confirm') : null;
  if (!card) return;

  const orderId = card.getAttribute('data-order-id') || '';
  const rows = card.querySelectorAll('.return-item-row');
  const selectedIds = [];

  rows.forEach(row => {
    const cb = row.querySelector('.return-item-checkbox');
    const itId = row.getAttribute('data-item-id');
    if (cb && cb.checked && itId) {
      selectedIds.push(itId);
    }
  });

  const errEl = card.querySelector('.card-feedback-error');
  if (selectedIds.length === 0) {
    if (errEl) {
      errEl.textContent = 'Bitte wählen Sie mindestens einen Artikel aus.';
      errEl.style.display = 'block';
    }
    return;
  }

  const submitBtn = card.querySelector('.return-submit-btn');
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i><span>Retoure wird gebucht...</span>';
  }

  try {
    const res = await fetch('/api/return/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: currentSessionId,
        order_id: orderId,
        selected_items: selectedIds
      })
    });
    const data = await res.json();

    if (data.messages) {
      chatHistory = data.messages;
      renderMessages();
      updateInspector(data.state);
    }
  } catch (err) {
    if (errEl) {
      errEl.textContent = 'Fehler beim Bestätigen der Retoure: ' + err.message;
      errEl.style.display = 'block';
    }
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<i class="fa-solid fa-check"></i><span>Retoure verbindlich abschließen</span>';
    }
  }
}

// Bricht die Retourenauswahl ab
async function cancelReturnWidget(triggerEl) {
  const card = triggerEl ? triggerEl.closest('.card-return-confirm') : null;
  const msgId = card ? card.getAttribute('data-msg-id') : null;

  if (msgId) {
    const item = chatHistory.find(m => m.id === msgId);
    if (item) item.action_card = null;
  }

  renderMessages();

  try {
    const res = await fetch('/api/return/cancel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: currentSessionId })
    });
    const data = await res.json();
    if (data.messages) {
      chatHistory = data.messages;
      renderMessages();
      updateInspector(data.state);
    }
  } catch (e) {
    console.warn("Cancel return failed:", e);
  }
}

// Absenden des interaktiven Logins direkt an das Backend (Zero-LLM-Leakage)
async function submitAccountLogin(triggerEl) {
  const card = triggerEl ? triggerEl.closest('.card-action') : null;
  if (!card) return;

  const loginInput = card.querySelector('.auth-login-input');
  const pwdInput = card.querySelector('.auth-pwd-input');
  const submitBtn = card.querySelector('.auth-submit-btn');
  const errEl = card.querySelector('.card-feedback-error');
  const msgEl = card.querySelector('.card-feedback-msg');

  const loginVal = loginInput ? loginInput.value.trim() : '';
  const pwdVal = pwdInput ? pwdInput.value.trim() : '';

  if (errEl) { errEl.textContent = ''; errEl.style.display = 'none'; }
  if (msgEl) { msgEl.textContent = ''; msgEl.style.display = 'none'; }

  if (!loginVal || !pwdVal) {
    if (errEl) {
      errEl.textContent = 'Bitte geben Sie E-Mail/Account-ID und Passwort ein.';
      errEl.style.display = 'block';
    }
    return;
  }

  // Sofortiges Feedback: Ladeanzeige auf Button
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i><span>Anmelden...</span>';
  }

  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: currentSessionId,
        login: loginVal,
        password: pwdVal
      })
    });
    const data = await res.json();

    if (!data.success) {
      if (errEl) {
        errEl.textContent = data.message || 'Anmeldung fehlgeschlagen. Bitte Zugangsdaten prüfen.';
        errEl.style.display = 'block';
      }
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span>Anmelden</span><i class="fa-solid fa-arrow-right"></i>';
      }
      return;
    }

    // Erfolgs-Feedback
    if (msgEl) {
      msgEl.textContent = 'Erfolgreich angemeldet. Lade Profildaten...';
      msgEl.style.display = 'block';
    }

    setTimeout(() => {
      chatHistory = data.messages || [];
      renderMessages();
      updateInspector(data.state);
    }, 350);

  } catch (e) {
    if (errEl) {
      errEl.textContent = 'Verbindungsfehler: ' + e.message;
      errEl.style.display = 'block';
    }
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<span>Anmelden</span><i class="fa-solid fa-arrow-right"></i>';
    }
  }
}

// Absenden von Profiländerungen direkt an das Backend
async function submitProfileUpdate(triggerEl) {
  const card = triggerEl ? triggerEl.closest('.card-action') : null;
  if (!card) return;

  const nameInput = card.querySelector('.prof-name-input');
  const nachnameInput = card.querySelector('.prof-nachname-input');
  const adresseInput = card.querySelector('.prof-adresse-input');
  const landInput = card.querySelector('.prof-land-input');
  const phoneInput = card.querySelector('.prof-phone-input');
  const submitBtn = card.querySelector('.prof-submit-btn');
  const errEl = card.querySelector('.card-feedback-error');
  const msgEl = card.querySelector('.card-feedback-msg');

  if (errEl) { errEl.textContent = ''; errEl.style.display = 'none'; }
  if (msgEl) { msgEl.textContent = ''; msgEl.style.display = 'none'; }

  const updates = {
    name: nameInput ? nameInput.value.trim() : '',
    nachname: nachnameInput ? nachnameInput.value.trim() : '',
    adresse: adresseInput ? adresseInput.value.trim() : '',
    land: landInput ? landInput.value.trim() : '',
    telefonnummer: phoneInput ? phoneInput.value.trim() : ''
  };

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i><span>Speichern...</span>';
  }

  try {
    const res = await fetch('/api/account/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: currentSessionId,
        updates: updates
      })
    });
    const data = await res.json();

    if (!data.success) {
      if (errEl) {
        errEl.textContent = data.message || 'Aktualisierung fehlgeschlagen.';
        errEl.style.display = 'block';
      }
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span>Änderungen speichern</span><i class="fa-solid fa-check"></i>';
      }
      return;
    }

    if (msgEl) {
      msgEl.textContent = 'Profildaten erfolgreich gespeichert!';
      msgEl.style.display = 'block';
    }

    setTimeout(() => {
      // Automatisch einklappen: alle offenen account_profile Action-Cards aus Historie entfernen
      chatHistory = (data.messages || []).map(m => {
        if (m.action_card && m.action_card.type === 'account_profile') {
          return { ...m, action_card: null };
        }
        return m;
      });
      renderMessages();
      updateInspector(data.state);
    }, 300);

  } catch (e) {
    if (errEl) {
      errEl.textContent = 'Verbindungsfehler: ' + e.message;
      errEl.style.display = 'block';
    }
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<span>Änderungen speichern</span><i class="fa-solid fa-check"></i>';
    }
  }
}

// Aktualisiert den State Inspector im rechten Panel (Ansicht 1)
function updateInspector(state) {
  if (!state) return;

  document.getElementById('thread-id-display').textContent = `Thread: #${currentSessionId}`;

  const intentEl = document.getElementById('badge-intent');
  if (intentEl) {
    const it = state.current_intent || (state.decision_logic && state.decision_logic.intent) || 'Initialisierung';
    intentEl.textContent = `intent: ${it}`;
    intentEl.removeAttribute('style');
    intentEl.className = 'state-badge';
  }

  const confEl = document.getElementById('badge-intent-confidence');
  if (confEl) {
    if (state.intent_confidence != null) {
      const pct = Math.round(state.intent_confidence * 100);
      confEl.textContent = `confidence: ${pct} %`;
      confEl.style.display = '';
    } else {
      confEl.style.display = 'none';
    }
  }

  const nodeEl = document.getElementById('badge-active-node');
  if (nodeEl) {
    const rawNode = state.last_active_node || 'node_process_input';
    const cleanNode = rawNode.replace(/^node_/, '');
    nodeEl.textContent = `node: ${cleanNode}`;
    nodeEl.removeAttribute('style');
    if (rawNode === 'node_escalate') {
      nodeEl.className = 'state-badge locked';
    } else {
      nodeEl.className = 'state-badge';
    }
  }

  const authEl = document.getElementById('badge-auth-status');
  if (authEl) {
    authEl.textContent = `auth_status: ${state.auth_status} (Attempts: ${state.auth_attempts || 0}/3)`;
    authEl.removeAttribute('style');
    if (state.auth_status) {
      authEl.className = 'state-badge verified';
    } else if (state.auth_attempts >= 3) {
      authEl.className = 'state-badge locked';
    } else {
      authEl.className = 'state-badge';
    }
  }

  const lockEl = document.getElementById('badge-tool-lock');
  if (lockEl) {
    lockEl.removeAttribute('style');
    if (state.tools_locked) {
      lockEl.className = 'state-badge locked';
      lockEl.textContent = 'tools_locked: true (Schreibende Tools gesperrt!)';
    } else {
      lockEl.className = 'state-badge';
      lockEl.textContent = 'tools_locked: false (Schreibzugriff aktiv)';
    }
  }

  const emotionEl = document.getElementById('badge-emotion-status');
  if (emotionEl) {
    const count = state.emotional_messages_count || 0;
    const isFrust = Boolean(state.is_frustrated);
    emotionEl.removeAttribute('style');
    if (count >= 3) {
      emotionEl.className = 'state-badge locked';
      emotionEl.textContent = `frustration: eskaliert (${count}/3)`;
    } else if (isFrust || count > 0) {
      emotionEl.className = 'state-badge locked';
      emotionEl.textContent = `frustration: verärgert (${count}/3)`;
    } else {
      emotionEl.className = 'state-badge';
      emotionEl.textContent = `frustration: neutral (${count}/3)`;
    }
  }

  const isEscalated = Boolean(state.handoff_payload);
  [1, 2].forEach(id => {
    const dot = document.getElementById('dot-v' + id);
    const txt = document.getElementById('status-text-v' + id);
    if (dot && txt) {
      if (isEscalated) {
        dot.className = 'status-dot escalated';
        txt.textContent = 'Eskaliert (Support)';
      } else {
        dot.className = 'status-dot';
        txt.textContent = 'Online';
      }
    }
  });

  const decisionEl = document.getElementById('json-decision-logic');
  if (state.decision_logic && Object.keys(state.decision_logic).length > 0) {
    decisionEl.textContent = JSON.stringify(state.decision_logic, null, 2);
  } else {
    decisionEl.textContent = '{\n  "status": "In Prüfung..."\n}';
  }

  const toolEl = document.getElementById('json-tool-execution');
  toolEl.textContent = state.tool_execution || 'Keine schreibenden Tool-Aufrufe aktiv.';

  const logEl = document.getElementById('log-stream');
  if (state.execution_logs && state.execution_logs.length > 0) {
    logEl.textContent = state.execution_logs.join('\n');
  }
}

// Nachricht an Backend senden
function updateStreamingBubble(content) {
  [1, 2].forEach(id => {
    const container = document.getElementById('messages-v' + id);
    if (!container) return;
    const bubbles = container.querySelectorAll('.message.bot .bubble');
    if (bubbles.length > 0) {
      const lastBubble = bubbles[bubbles.length - 1];
      if (lastBubble.classList.contains('loading')) {
        lastBubble.classList.remove('loading');
        lastBubble.removeAttribute('title');
      }
      lastBubble.innerHTML = renderMarkdown(content);
    }
  });
  scrollToBottom();
}

async function sendMessage(text) {
  const trimmed = (text || '').trim();
  if (!trimmed) return;

  const timeStr = formatCurrentTime();
  chatHistory.push({
    role: "user",
    content: trimmed,
    time: timeStr
  });

  // Temporäre Bot-Nachricht mit Lade-Animation (graues Pulsieren) vor dem Eintreffen der Tokens
  const botMsg = {
    role: "bot",
    content: "",
    loading: true,
    time: timeStr
  };
  chatHistory.push(botMsg);
  renderMessages();

  [1, 2].forEach(id => {
    const inp = document.getElementById('input-v' + id);
    const btn = document.getElementById('send-v' + id);
    const txt = document.getElementById('status-text-v' + id);
    if (inp) {
      inp.value = '';
      inp.placeholder = 'KI generiert Antwort...';
      inp.disabled = true;
    }
    if (btn) btn.disabled = true;
    if (txt) txt.textContent = 'Antwortet...';
  });

  try {
    const payload = {
      session_id: currentSessionId,
      message: trimmed
    };

    if (apiConfig.apiKey) payload.api_key = apiConfig.apiKey;
    if (apiConfig.apiUrl) payload.api_url = apiConfig.apiUrl;
    if (apiConfig.model) payload.model = apiConfig.model;

    if (apiConfig.apiKey) {
      // Token-für-Token Streaming für echtes KI API Modell
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error('Server-Fehler: ' + response.statusText);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const rawData = line.slice(6).trim();
            if (!rawData) continue;
            try {
              const evt = JSON.parse(rawData);
              if (evt.type === 'token') {
                botMsg.loading = false;
                botMsg.content += evt.token;
                updateStreamingBubble(botMsg.content);
              } else if (evt.type === 'done') {
                const data = evt.payload;
                chatHistory = mergeMessagesPreservingCards(data.messages);
                renderMessages();
                updateInspector(data.state);
              }
            } catch (e) {
              console.warn("Stream parse error", e);
            }
          }
        }
      }
    } else {
      // Mock-Modus: Elegante Ladeanimation bis zur vollständigen Antwort
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error('Server-Fehler: ' + response.statusText);
      }

      const data = await response.json();
      chatHistory = mergeMessagesPreservingCards(data.messages);
      renderMessages();
      updateInspector(data.state);
    }

  } catch (err) {
    console.error(err);
    chatHistory = chatHistory.filter(m => !m.loading);
    chatHistory.push({
      role: "bot",
      content: "Verbindungsfehler zum Backend. Bitte stellen Sie sicher, dass der Server läuft.",
      time: formatCurrentTime()
    });
    renderMessages();
  } finally {
    [1, 2].forEach(id => {
      const inp = document.getElementById('input-v' + id);
      const btn = document.getElementById('send-v' + id);
      const txt = document.getElementById('status-text-v' + id);
      if (inp) {
        inp.disabled = false;
        inp.placeholder = id === 1
          ? "Ihre Nachricht schreiben... (z. B. 'Retoure für ORD-1001, kunde1@example.com')"
          : "Antworten...";
      }
      if (btn) btn.disabled = false;
      if (txt && txt.textContent === 'Antwortet...') {
        txt.textContent = 'Online';
      }
    });
  }
}

function sendMessageFrom(viewIndex) {
  const inp = document.getElementById('input-v' + viewIndex);
  if (inp) sendMessage(inp.value);
}

function handleKeyDown(event, viewIndex) {
  if (event.key === 'Enter') {
    event.preventDefault();
    sendMessageFrom(viewIndex);
  }
}

// Testfälle T1, T2, T3, T4 aus der Sidebar ausführen
async function runTestCase(caseNumber) {
  document.querySelectorAll('.scenario-btn').forEach(b => b.classList.remove('active'));
  const activeBtn = document.getElementById('btn-t' + caseNumber);
  if (activeBtn) activeBtn.classList.add('active');

  await resetChat();
  closeSidebar();

  if (caseNumber === 1) {
    sendMessage("Hallo, ich möchte meine Bestellung ORD-1001 zurückgeben. Meine Mail ist kunde1@example.com.");
  } else if (caseNumber === 2) {
    sendMessage("Guten Tag, ich möchte Artikel aus ORD-1002 zurücksenden. Mail: kunde2@example.com");
  } else if (caseNumber === 3) {
    sendMessage("Ich möchte die Bestellung ORD-1003 reklamieren und zurückgeben. Meine E-Mail lautet kunde3@example.com.");
  } else if (caseNumber === 4) {
    // Versuch 1: Fehlversuch 1/3
    await sendMessage("Hallo, ich will retournieren: ORD-9999 mit falschemail@example.com");
    setTimeout(async () => {
      // Versuch 2: Fehlversuch 2/3
      await sendMessage("Oh Verzeihung, ich meinte ORD-8888 und nochmalkorrupt@example.com");
      setTimeout(() => {
        // Versuch 3: Fehlversuch 3/3 -> Eskalation an menschlichen Support
        sendMessage("Letzter Versuch: ORD-7777 mit drittversuchfalsch@example.com");
      }, 1100);
    }, 1100);
  } else if (caseNumber === 5) {
    sendMessage("Ich möchte meine Kundendaten und Lieferadresse anpassen.");
  } else if (caseNumber === 6) {
    sendMessage("Welche Rückgabefristen und AGBs gelten für meine Retoure?");
  }
}

// Reset Chat & Session
async function resetChat() {
  try {
    const response = await fetch('/api/reset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: currentSessionId })
    });
    const data = await response.json();
    currentSessionId = data.session_id;
    chatHistory = [data.welcome_message];
    renderMessages();
    updateInspector({
      last_active_node: "node_process_input",
      auth_status: false,
      auth_attempts: 0,
      tools_locked: false,
      decision_logic: { status: "Warte auf Nutzereingabe..." },
      tool_execution: "Keine schreibenden Tool-Aufrufe aktiv.",
      execution_logs: ["[LOG] Neue Session gestartet: #" + currentSessionId]
    });
  } catch (e) {
    console.error("Reset fehlgeschlagen", e);
  }
}

// Sidebar Steuerung
function openSidebar() {
  document.getElementById('setting-api-key').value = apiConfig.apiKey || '';
  document.getElementById('setting-api-url').value = apiConfig.apiUrl || '';
  document.getElementById('setting-model').value = apiConfig.model || '';
  hideBanner();

  document.getElementById('sidebar-overlay').classList.add('open');
  document.getElementById('sidebar').classList.add('open');
}

function closeSidebar() {
  document.getElementById('sidebar-overlay').classList.remove('open');
  document.getElementById('sidebar').classList.remove('open');
}

function saveSettings() {
  apiConfig.apiKey = document.getElementById('setting-api-key').value.trim();
  apiConfig.apiUrl = document.getElementById('setting-api-url').value.trim();
  apiConfig.model = document.getElementById('setting-model').value.trim();

  localStorage.setItem('retouren_api_key', apiConfig.apiKey);
  localStorage.setItem('retouren_api_url', apiConfig.apiUrl);
  localStorage.setItem('retouren_model', apiConfig.model);

  updateHeaderStatusDot();
  showBanner("success", "Einstellungen erfolgreich gespeichert!");
  setTimeout(closeSidebar, 900);
}

function clearSettings() {
  apiConfig.apiKey = '';
  apiConfig.apiUrl = '';
  apiConfig.model = '';

  localStorage.removeItem('retouren_api_key');
  localStorage.removeItem('retouren_api_url');
  localStorage.removeItem('retouren_model');

  document.getElementById('setting-api-key').value = '';
  document.getElementById('setting-api-url').value = '';
  document.getElementById('setting-model').value = '';

  updateHeaderStatusDot();
  showBanner("success", "Zurückgesetzt auf Mock-Modus.");
  setTimeout(closeSidebar, 900);
}

async function testConnection() {
  const key = document.getElementById('setting-api-key').value.trim();
  const url = document.getElementById('setting-api-url').value.trim();
  const model = document.getElementById('setting-model').value.trim();

  if (!key) {
    showBanner("error", "Bitte geben Sie zuerst einen API-Key ein.");
    return;
  }

  showBanner("success", "Teste Verbindung...");

  try {
    const response = await fetch('/api/test-connection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: key,
        api_url: url || null,
        model: model || null
      })
    });

    const data = await response.json();
    if (data.success) {
      showBanner("success", data.message);
    } else {
      showBanner("error", data.message);
    }
  } catch (err) {
    showBanner("error", "Verbindungsaufbau fehlgeschlagen: " + err.message);
  }
}

function showBanner(type, message) {
  const banner = document.getElementById('api-status-banner');
  banner.className = 'api-status-banner ' + type;
  banner.textContent = message;
}

function hideBanner() {
  const banner = document.getElementById('api-status-banner');
  banner.className = 'api-status-banner';
  banner.textContent = '';
}

function updateHeaderStatusDot() {
  const dot = document.getElementById('header-api-dot');
  if (apiConfig.apiKey) {
    dot.className = 'api-status-dot active';
    dot.title = 'Custom API Key konfiguriert';
  } else {
    dot.className = 'api-status-dot';
    dot.title = 'Mock-Modus aktiv';
  }
}

// Initialisierung
window.addEventListener('DOMContentLoaded', () => {
  renderMessages();
  updateHeaderStatusDot();
  document.getElementById('thread-id-display').textContent = `Thread: #${currentSessionId}`;
});
