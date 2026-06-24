// ── State ──────────────────────────────────────────────
let currentUser = null;
let token = localStorage.getItem('token');
let activeTab = 'sessions';
let sessionViewMode = localStorage.getItem('sessionView') || 'list';
let deferredInstallPrompt = null;
let telegramRefreshInterval = null;

// ── Utilities ──────────────────────────────────────────
function apiFetch(url, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return fetch(url, { ...opts, headers });
}

function showToast(msg, type = 'info') {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.className = `toast show ${type}`;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.remove('show'), 3500);
}

function showLoading(show) {
  const el = document.getElementById('loading-overlay');
  if (el) el.style.display = show ? 'flex' : 'none';
}

function fmtDate(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString(currentLang === 'he' ? 'he-IL' : 'en-US', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch (e) { return iso; }
}

function starsHtml(avg, count) {
  if (!avg) return '';
  const full = Math.round(avg);
  let s = '';
  for (let i = 1; i <= 5; i++) s += i <= full ? '★' : '☆';
  return `<span class="stars" title="${avg}">${s}</span> <span class="review-count">(${count || 0})</span>`;
}

// ── Auth ───────────────────────────────────────────────
function isLoggedIn() { return !!token && !!currentUser; }

async function loadCurrentUser() {
  if (!token) return null;
  try {
    const res = await apiFetch('/api/users/me');
    if (res.ok) {
      currentUser = await res.json();
      return currentUser;
    }
  } catch (e) {}
  return null;
}

async function logout() {
  token = null;
  currentUser = null;
  localStorage.removeItem('token');
  showAuthScreen();
}

// ── Navigation ─────────────────────────────────────────
function showAuthScreen() {
  document.getElementById('app').style.display = 'none';
  document.getElementById('auth-screen').style.display = 'flex';
  renderLoginForm();
}

function showApp() {
  document.getElementById('auth-screen').style.display = 'none';
  document.getElementById('app').style.display = 'flex';
  renderNav();
  navigateTo(activeTab);
}

function renderNav() {
  const nav = document.getElementById('nav-tabs');
  const isAdmin = currentUser && currentUser.role === 'admin';
  const isInstructor = currentUser && currentUser.role === 'instructor';

  nav.innerHTML = `
    <button class="nav-btn" data-tab="sessions" onclick="navigateTo('sessions')">
      🏠 <span data-i18n="nav_sessions">${t('nav_sessions')}</span>
    </button>
    <button class="nav-btn" data-tab="activities" onclick="navigateTo('activities')">
      📋 <span data-i18n="nav_activities">${t('nav_activities')}</span>
    </button>
    <button class="nav-btn" data-tab="bookings" onclick="navigateTo('bookings')">
      📅 <span data-i18n="nav_bookings">${t('nav_bookings')}</span>
    </button>
    <button class="nav-btn" data-tab="profile" onclick="navigateTo('profile')">
      👤 <span data-i18n="nav_profile">${t('nav_profile')}</span>
    </button>
    ${isAdmin || isInstructor ? `
    <button class="nav-btn" data-tab="admin" onclick="navigateTo('admin')">
      📊 <span data-i18n="nav_admin">${t('nav_admin')}</span>
    </button>
    <button class="nav-btn" data-tab="analytics" onclick="navigateTo('analytics')">
      📈 <span data-i18n="nav_analytics">${t('nav_analytics')}</span>
    </button>
    ` : ''}
    <button class="nav-btn logout-btn" onclick="logout()">
      🚪 <span data-i18n="logout">${t('logout')}</span>
    </button>
  `;
}

function navigateTo(tab) {
  activeTab = tab;
  document.querySelectorAll('.nav-btn[data-tab]').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === tab);
  });
  const content = document.getElementById('main-content');
  content.innerHTML = '';
  destroyCalendar && destroyCalendar();

  switch (tab) {
    case 'sessions': renderSessionsTab(); break;
    case 'activities': renderActivitiesTab(); break;
    case 'bookings': renderBookingsTab(); break;
    case 'profile': renderProfileTab(); break;
    case 'admin': renderAdminPanel(); break;
    case 'analytics': renderAnalyticsTab(); break;
    default: renderSessionsTab();
  }
}

// ── Auth Screens ───────────────────────────────────────
function renderLoginForm() {
  document.getElementById('auth-content').innerHTML = `
    <div class="auth-logo" id="auth-logo-area"></div>
    <h2 data-i18n="login">${t('login')}</h2>
    <form id="login-form" onsubmit="submitLogin(event)">
      <input type="tel" id="login-phone" placeholder="${t('phone')}" required>
      <input type="password" id="login-password" placeholder="${t('password')}" required>
      <button type="submit" class="btn-primary" data-i18n="login">${t('login')}</button>
    </form>
    <p class="auth-link">
      <a href="#" onclick="renderRegisterForm()">${t('register')}</a> |
      <a href="#" onclick="renderForgotPassword()">${t('forgot_password')}</a>
    </p>
  `;
  loadAuthLogo();
}

async function loadAuthLogo() {
  try {
    const res = await fetch('/api/settings/logo');
    if (res.ok) {
      const data = await res.json();
      if (data.logo_filename) {
        document.getElementById('auth-logo-area').innerHTML = `<img src="/uploads/logo/${data.logo_filename}" alt="logo" style="max-height:80px;max-width:200px">`;
      }
    }
  } catch (e) {}
}

function renderRegisterForm() {
  document.getElementById('auth-content').innerHTML = `
    <h2 data-i18n="register">${t('register')}</h2>
    <form id="register-form" onsubmit="submitRegister(event)">
      <input type="text" id="reg-first" placeholder="${t('first_name')}" required>
      <input type="text" id="reg-last" placeholder="${t('last_name')}" required>
      <input type="tel" id="reg-phone" placeholder="${t('phone')}" required>
      <input type="password" id="reg-pass" placeholder="${t('password')}" required minlength="6">
      <input type="password" id="reg-pass2" placeholder="${t('confirm_password')}" required>
      <button type="submit" class="btn-primary">${t('register')}</button>
    </form>
    <p class="auth-link"><a href="#" onclick="renderLoginForm()">${t('login')}</a></p>
  `;
}

function renderForgotPassword() {
  document.getElementById('auth-content').innerHTML = `
    <h2>${t('forgot_password')}</h2>
    <form onsubmit="submitForgotPassword(event)">
      <input type="tel" id="fp-phone" placeholder="${t('phone')}" required>
      <button type="submit" class="btn-primary">${t('reset_send_code')}</button>
    </form>
    <p class="auth-link"><a href="#" onclick="renderLoginForm()">${t('login')}</a></p>
  `;
}

async function submitLogin(e) {
  e.preventDefault();
  const phone = document.getElementById('login-phone').value;
  const password = document.getElementById('login-password').value;
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone, password }),
    });
    const data = await res.json();
    if (res.status === 202 && data.requires_2fa) {
      render2FAScreen(data.temp_token);
    } else if (res.ok && data.access_token) {
      token = data.access_token;
      localStorage.setItem('token', token);
      await loadCurrentUser();
      showApp();
    } else {
      showToast(data.detail || t('error_generic'), 'error');
    }
  } catch (e) {
    showToast(t('error_generic'), 'error');
  }
}

async function submitRegister(e) {
  e.preventDefault();
  const pass = document.getElementById('reg-pass').value;
  const pass2 = document.getElementById('reg-pass2').value;
  if (pass !== pass2) { showToast(t('error_generic'), 'error'); return; }
  try {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        first_name: document.getElementById('reg-first').value,
        last_name: document.getElementById('reg-last').value,
        phone: document.getElementById('reg-phone').value,
        password: pass,
      }),
    });
    const data = await res.json();
    if (res.ok) {
      token = data.access_token;
      localStorage.setItem('token', token);
      await loadCurrentUser();
      showApp();
    } else {
      showToast(data.detail || t('error_generic'), 'error');
    }
  } catch (e) {
    showToast(t('error_generic'), 'error');
  }
}

function render2FAScreen(tempToken) {
  document.getElementById('auth-content').innerHTML = `
    <h2>${t('twofa_title')}</h2>
    <p>${t('twofa_sent')}</p>
    <form onsubmit="submit2FA(event, '${tempToken}')">
      <input type="text" id="twofa-code" placeholder="${t('twofa_enter')}" maxlength="6" required inputmode="numeric">
      <button type="submit" class="btn-primary">${t('twofa_verify')}</button>
    </form>
  `;
}

async function submit2FA(e, tempToken) {
  e.preventDefault();
  const code = document.getElementById('twofa-code').value;
  try {
    const res = await apiFetch('/api/auth/verify-2fa', {
      method: 'POST',
      body: JSON.stringify({ temp_token: tempToken, code }),
    });
    const data = await res.json();
    if (res.ok) {
      token = data.access_token;
      localStorage.setItem('token', token);
      await loadCurrentUser();
      showApp();
    } else {
      showToast(t('twofa_invalid'), 'error');
    }
  } catch (e) {
    showToast(t('error_generic'), 'error');
  }
}

async function submitForgotPassword(e) {
  e.preventDefault();
  const phone = document.getElementById('fp-phone').value;
  await fetch('/api/auth/forgot-password', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone }),
  });
  document.getElementById('auth-content').innerHTML = `
    <h2>${t('forgot_password')}</h2>
    <p>${t('reset_code_sent')}</p>
    <form onsubmit="submitResetPassword(event, '${phone}')">
      <input type="text" id="rp-code" placeholder="${t('reset_enter_code')}" maxlength="6" required>
      <input type="password" id="rp-pass" placeholder="${t('reset_new_password')}" required minlength="6">
      <input type="password" id="rp-pass2" placeholder="${t('reset_confirm_password')}" required>
      <button type="submit" class="btn-primary">${t('reset_submit')}</button>
    </form>
    <p class="auth-link"><a href="#" onclick="renderLoginForm()">${t('login')}</a></p>
  `;
}

async function submitResetPassword(e, phone) {
  e.preventDefault();
  const code = document.getElementById('rp-code').value;
  const pass = document.getElementById('rp-pass').value;
  const pass2 = document.getElementById('rp-pass2').value;
  if (pass !== pass2) { showToast(t('error_generic'), 'error'); return; }
  try {
    const res = await fetch('/api/auth/reset-password', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone, code, new_password: pass }),
    });
    if (res.ok) {
      showToast(t('reset_success'), 'success');
      renderLoginForm();
    } else {
      const d = await res.json();
      showToast(d.detail || t('error_generic'), 'error');
    }
  } catch (e) {
    showToast(t('error_generic'), 'error');
  }
}

// ── Sessions Tab ───────────────────────────────────────
let sessionFilters = {};

function getCurrentFilters() { return sessionFilters; }
window.getCurrentFilters = getCurrentFilters;

async function renderSessionsTab() {
  const content = document.getElementById('main-content');
  const isAdmin = currentUser && (currentUser.role === 'admin' || currentUser.role === 'instructor');

  content.innerHTML = `
    <div class="tab-header">
      <h2 data-i18n="nav_sessions">${t('nav_sessions')}</h2>
      <div class="view-toggle">
        <button id="btn-list-view" class="btn-sm ${sessionViewMode === 'list' ? 'active' : ''}" onclick="setSessionView('list')">☰ ${t('list_view')}</button>
        <button id="btn-cal-view" class="btn-sm ${sessionViewMode === 'calendar' ? 'active' : ''}" onclick="setSessionView('calendar')">📅 ${t('calendar_view')}</button>
      </div>
    </div>
    <div class="filter-bar">
      <input type="text" id="filter-search" placeholder="${t('search_placeholder')}" oninput="debounceFilter()">
      <select id="filter-type" onchange="applyFilters()">
        <option value="">${t('filter_type')}: ${t('filter_all')}</option>
      </select>
      <input type="date" id="filter-date-from" onchange="applyFilters()">
      <input type="date" id="filter-date-to" onchange="applyFilters()">
      <input type="text" id="filter-location" placeholder="${t('filter_location')}" oninput="debounceFilter()">
      <select id="filter-avail" onchange="applyFilters()">
        <option value="">${t('filter_availability')}: ${t('filter_all')}</option>
        <option value="available">${t('filter_available')}</option>
        <option value="full">${t('filter_full')}</option>
      </select>
      <button class="btn-sm" onclick="clearFilters()">${t('filter_clear')}</button>
    </div>
    <div id="sessions-content"></div>
  `;

  await loadActivityTypeFilter();
  await renderSessionsContent();
}

async function loadActivityTypeFilter() {
  try {
    const res = await fetch('/api/activity-types');
    if (!res.ok) return;
    const types = await res.json();
    const sel = document.getElementById('filter-type');
    if (!sel) return;
    types.forEach(at => {
      const opt = document.createElement('option');
      opt.value = at.id;
      opt.textContent = `${t('filter_type')}: ${at.name}`;
      sel.appendChild(opt);
    });
  } catch (e) {}
}

let filterDebounce;
function debounceFilter() {
  clearTimeout(filterDebounce);
  filterDebounce = setTimeout(applyFilters, 350);
}

function applyFilters() {
  sessionFilters = {
    search: document.getElementById('filter-search')?.value || '',
    activity_type_id: document.getElementById('filter-type')?.value || '',
    date_from: document.getElementById('filter-date-from')?.value || '',
    date_to: document.getElementById('filter-date-to')?.value || '',
    location: document.getElementById('filter-location')?.value || '',
    availability: document.getElementById('filter-avail')?.value || '',
  };
  renderSessionsContent();
}

function clearFilters() {
  sessionFilters = {};
  ['filter-search','filter-location'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  ['filter-type','filter-avail'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  ['filter-date-from','filter-date-to'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  renderSessionsContent();
}

async function renderSessionsContent() {
  if (sessionViewMode === 'calendar') {
    document.getElementById('sessions-content').innerHTML = `<div id="calendar-container"></div>`;
    const filters = {};
    if (sessionFilters.activity_type_id) filters.activity_type_id = sessionFilters.activity_type_id;
    initCalendar(filters);
    return;
  }

  const params = new URLSearchParams({ status_filter: 'upcoming' });
  Object.entries(sessionFilters).forEach(([k, v]) => { if (v) params.set(k, v); });

  try {
    const res = await apiFetch(`/api/sessions?${params}`);
    if (!res.ok) return;
    const sessions = await res.json();

    let myBookings = [];
    if (token) {
      try {
        const br = await apiFetch('/api/bookings/my');
        if (br.ok) myBookings = await br.json();
      } catch (e) {}
    }
    const bookedIds = new Set(myBookings.map(b => b.session_id));

    const container = document.getElementById('sessions-content');
    if (!sessions.length) {
      container.innerHTML = `<p class="empty-state">${t('no_upcoming')}</p>`;
      return;
    }

    container.innerHTML = `<div class="sessions-grid">` +
      sessions.map(s => renderSessionCard(s, bookedIds.has(s.id))).join('') +
      `</div>`;
  } catch (e) {
    showToast(t('error_generic'), 'error');
  }
}

function setSessionView(mode) {
  sessionViewMode = mode;
  localStorage.setItem('sessionView', mode);
  document.getElementById('btn-list-view')?.classList.toggle('active', mode === 'list');
  document.getElementById('btn-cal-view')?.classList.toggle('active', mode === 'calendar');
  renderSessionsContent();
}

function renderSessionCard(s, isBooked) {
  const spots = s.max_participants - (s.booking_count || 0);
  const isFull = spots <= 0;
  const ratio = (s.booking_count || 0) / s.max_participants;
  const barColor = ratio >= 1 ? '#ef4444' : ratio >= 0.7 ? '#f59e0b' : '#22c55e';
  const pct = Math.min(100, Math.round(ratio * 100));

  const coverHtml = s.cover_image_url
    ? `<img src="${s.cover_image_url}" class="session-cover" onerror="this.style.display='none'">`
    : `<div class="session-cover-placeholder" style="background:${barColor}20"></div>`;

  const badges = [
    s.is_cancelled ? `<span class="badge badge-cancelled">${t('session_cancelled_badge')}</span>` : '',
    s.online_link ? `<span class="badge badge-online">${t('online_badge')}</span>` : '',
    s.is_restricted ? `<span class="badge badge-group">${t('group_restricted_badge')}</span>` : '',
    s.activity_type ? `<span class="badge badge-type">${s.activity_type.name}</span>` : '',
  ].filter(Boolean).join('');

  let actionBtn = '';
  if (!s.is_cancelled) {
    if (isBooked) {
      actionBtn = `<button class="btn-danger" onclick="cancelBooking(${s.id})">${t('cancel_booking')}</button>`;
    } else if (isFull) {
      actionBtn = `<button class="btn-secondary" onclick="joinWaitlist(${s.id})">${t('waitlist')}</button>`;
    } else {
      actionBtn = `<button class="btn-primary" onclick="bookSession(${s.id})">${t('book')}</button>`;
    }
  }

  const calDropdown = isBooked ? `
    <div class="dropdown">
      <button class="btn-sm">📅 ${t('add_to_calendar')}</button>
      <div class="dropdown-menu">
        <a href="${s.google_calendar_url}" target="_blank">${t('google_calendar')}</a>
        <a href="/api/sessions/${s.id}/ics" download>${t('download_ics')}</a>
      </div>
    </div>
  ` : '';

  const joinBtn = (isBooked && s.online_link) ? `<a href="${s.online_link}" target="_blank" class="btn-sm btn-online">${t('join_session')}</a>` : '';

  return `
    <div class="session-card ${s.is_cancelled ? 'cancelled' : ''}">
      ${coverHtml}
      <div class="session-card-body">
        <div class="badges">${badges}</div>
        <h3 class="session-title" onclick="openSessionDetail(${s.id})">${s.title}</h3>
        <div class="session-meta">
          <span>📅 ${fmtDate(s.session_date)}</span>
          ${s.location ? `<span>📍 ${s.location}</span>` : ''}
          ${s.instructor ? `<span>🏋️ ${s.instructor.first_name} ${s.instructor.last_name}</span>` : ''}
          ${s.avg_rating ? `<span>${starsHtml(s.avg_rating, 1)}</span>` : ''}
        </div>
        <div class="spots-bar-container">
          <div class="spots-bar"><div class="spots-fill" style="width:${pct}%;background:${barColor}"></div></div>
          <span class="spots-text">${isFull ? t('full') : `${spots} ${t('spots_left')}`}</span>
        </div>
        <div class="card-actions">
          ${actionBtn}
          ${calDropdown}
          ${joinBtn}
        </div>
      </div>
    </div>
  `;
}

async function bookSession(sessionId) {
  if (!token) { showToast(t('login'), 'error'); return; }
  try {
    const res = await apiFetch('/api/bookings', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId }),
    });
    const data = await res.json();
    if (res.ok) {
      showToast(t('booking_success'), 'success');
      renderSessionsContent();
    } else {
      showToast(data.detail || t('error_generic'), 'error');
    }
  } catch (e) {
    showToast(t('error_generic'), 'error');
  }
}

async function cancelBooking(sessionId) {
  if (!confirm(t('confirm_cancel'))) return;
  try {
    const res = await apiFetch(`/api/bookings/${sessionId}`, { method: 'DELETE' });
    const data = await res.json();
    if (res.ok) {
      showToast(t('booking_cancelled'), 'success');
      renderSessionsContent();
    } else {
      showToast(data.detail || t('error_generic'), 'error');
    }
  } catch (e) {
    showToast(t('error_generic'), 'error');
  }
}

async function joinWaitlist(sessionId) {
  if (!token) { showToast(t('login'), 'error'); return; }
  try {
    const res = await apiFetch(`/api/waitlist/${sessionId}`, { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      showToast(`${t('waitlist_joined')} - ${t('waitlist_position')}: ${data.position}`, 'info');
      renderSessionsContent();
    } else {
      showToast(data.detail || t('error_generic'), 'error');
    }
  } catch (e) {
    showToast(t('error_generic'), 'error');
  }
}

async function openSessionDetail(sessionId) {
  try {
    const res = await apiFetch(`/api/sessions/${sessionId}`);
    if (!res.ok) return;
    const s = await res.json();
    window.openSessionModal && window.openSessionModal(s);
    showSessionModal(s);
  } catch (e) {}
}

window.openSessionModal = function(s) { showSessionModal(s); };

function showSessionModal(s) {
  const modal = document.getElementById('modal-overlay');
  const body = document.getElementById('modal-body');
  if (!modal || !body) return;

  const spots = s.max_participants - (s.booking_count || 0);
  const isFull = spots <= 0;

  body.innerHTML = `
    <div class="modal-session">
      ${s.cover_image_url ? `<img src="${s.cover_image_url}" class="modal-cover">` : ''}
      <h2>${s.title}</h2>
      ${s.is_cancelled ? `<span class="badge badge-cancelled">${t('session_cancelled_badge')}</span>` : ''}
      ${s.activity_type ? `<p><strong>${t('activity_type_label')}:</strong> ${s.activity_type.name}</p>` : ''}
      <p>📅 ${fmtDate(s.session_date)}</p>
      ${s.location ? `<p>📍 ${s.location}
        <a href="https://waze.com/ul?ll=${s.location_lat},${s.location_lng}&navigate=yes" target="_blank" class="nav-link">${t('waze_link')}</a>
        <a href="https://maps.google.com/?q=${s.location_lat},${s.location_lng}" target="_blank" class="nav-link">${t('maps_link')}</a>
      </p>` : ''}
      ${s.instructor ? `<p>🏋️ ${s.instructor.first_name} ${s.instructor.last_name}</p>` : ''}
      ${s.requirements ? `<p>📝 ${s.requirements}</p>` : ''}
      ${s.description ? `<p>${s.description}</p>` : ''}
      ${s.online_link ? `<p>🔗 <a href="${s.online_link}" target="_blank">${t('join_session')}</a></p>` : ''}
      <p>${isFull ? `<strong style="color:#ef4444">${t('full')}</strong>` : `${spots} ${t('spots_left')}`}</p>
      ${s.avg_rating ? `<p>${starsHtml(s.avg_rating, s.review_count)}</p>` : ''}
    </div>
  `;

  modal.style.display = 'flex';
}

// ── Activities Tab ─────────────────────────────────────
async function renderActivitiesTab() {
  const content = document.getElementById('main-content');
  content.innerHTML = `<h2 data-i18n="activities_tab">${t('activities_tab')}</h2><div id="activities-list" class="activities-grid"></div>`;

  try {
    const res = await fetch('/api/activity-types');
    if (!res.ok) return;
    const types = await res.json();
    const el = document.getElementById('activities-list');
    if (!types.length) {
      el.innerHTML = `<p class="empty-state">${t('activity_no_items')}</p>`;
      return;
    }
    el.innerHTML = types.map(at => `
      <div class="activity-card">
        <h3>${at.name}</h3>
        ${at.description ? `<p>${at.description}</p>` : ''}
      </div>
    `).join('');
  } catch (e) {}
}

// ── Bookings Tab ───────────────────────────────────────
async function renderBookingsTab() {
  const content = document.getElementById('main-content');
  content.innerHTML = `<h2>${t('my_bookings')}</h2><div id="bookings-list"></div>`;

  try {
    const res = await apiFetch('/api/bookings/my');
    if (!res.ok) return;
    const bookings = await res.json();
    const el = document.getElementById('bookings-list');

    const upcoming = bookings.filter(b => b.is_upcoming && !b.session.is_cancelled);
    const past = bookings.filter(b => !b.is_upcoming || b.session.is_cancelled);

    let html = '';
    if (upcoming.length) {
      html += `<h3>${t('dashboard_upcoming')}</h3>`;
      html += upcoming.map(b => renderBookingCard(b, true)).join('');
    }
    if (past.length) {
      html += `<h3>${t('history')}</h3>`;
      html += past.map(b => renderBookingCard(b, false)).join('');
    }
    if (!bookings.length) html = `<p class="empty-state">${t('history_empty')}</p>`;
    el.innerHTML = html;
  } catch (e) {}
}

function renderBookingCard(b, isUpcoming) {
  const s = b.session;
  const calBtn = isUpcoming ? `
    <div class="dropdown">
      <button class="btn-sm">📅 ${t('add_to_calendar')}</button>
      <div class="dropdown-menu">
        <a href="https://calendar.google.com/calendar/render?action=TEMPLATE&text=${encodeURIComponent(s.title)}&dates=${formatICSDate(s.session_date)}" target="_blank">${t('google_calendar')}</a>
        <a href="/api/sessions/${s.id}/ics" download>${t('download_ics')}</a>
      </div>
    </div>
  ` : '';

  const cancelBtn = isUpcoming ? `<button class="btn-danger" onclick="cancelBooking(${s.id}); renderBookingsTab()">${t('cancel_booking')}</button>` : '';
  const joinBtn = (isUpcoming && s.online_link) ? `<a href="${s.online_link}" target="_blank" class="btn-sm btn-online">${t('join_session')}</a>` : '';
  const rateBtn = (!isUpcoming && !b.review_submitted) ? `<button class="btn-sm" onclick="openReviewModal(${s.id})">${t('review_title')} ⭐</button>` : '';

  return `
    <div class="booking-card">
      <div class="booking-info">
        <strong>${s.title}</strong>
        <span>${fmtDate(s.session_date)}</span>
        ${s.location ? `<span>📍 ${s.location}</span>` : ''}
        ${s.is_cancelled ? `<span class="badge badge-cancelled">${t('session_cancelled_badge')}</span>` : ''}
      </div>
      <div class="card-actions">${cancelBtn}${calBtn}${joinBtn}${rateBtn}</div>
    </div>
  `;
}

function formatICSDate(iso) {
  return new Date(iso).toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
}

function openReviewModal(sessionId) {
  const modal = document.getElementById('modal-overlay');
  const body = document.getElementById('modal-body');
  let stars = 5;
  body.innerHTML = `
    <h2>${t('review_title')}</h2>
    <div class="star-picker" id="star-picker">
      ${[1,2,3,4,5].map(i => `<span class="star ${i <= stars ? 'active' : ''}" onclick="setReviewStars(${i})" data-star="${i}">★</span>`).join('')}
    </div>
    <textarea id="review-comment" placeholder="${t('review_comment')}" maxlength="500" rows="3" style="width:100%"></textarea>
    <button class="btn-primary" onclick="submitReview(${sessionId})">${t('review_submit')}</button>
  `;
  window._reviewStars = 5;
  modal.style.display = 'flex';
}

function setReviewStars(n) {
  window._reviewStars = n;
  document.querySelectorAll('#star-picker .star').forEach((el, i) => {
    el.classList.toggle('active', i < n);
  });
}

async function submitReview(sessionId) {
  const comment = document.getElementById('review-comment')?.value || '';
  const stars = window._reviewStars || 5;
  try {
    const res = await apiFetch(`/api/reviews/${sessionId}`, {
      method: 'POST',
      body: JSON.stringify({ stars, comment }),
    });
    if (res.ok) {
      showToast(t('review_thanks'), 'success');
      closeModal();
      renderBookingsTab();
    } else {
      const d = await res.json();
      showToast(d.detail || t('error_generic'), 'error');
    }
  } catch (e) {
    showToast(t('error_generic'), 'error');
  }
}

function closeModal() {
  document.getElementById('modal-overlay').style.display = 'none';
}

// ── Profile Tab ────────────────────────────────────────
async function renderProfileTab() {
  if (!currentUser) return;
  const content = document.getElementById('main-content');

  let statsHtml = '';
  try {
    const res = await apiFetch('/api/users/me/stats');
    if (res.ok) {
      const stats = await res.json();
      statsHtml = `
        <div class="stats-row">
          <div class="stat-card"><div class="stat-val">${stats.total_sessions}</div><div class="stat-lbl">${t('stats_total')}</div></div>
          <div class="stat-card"><div class="stat-val">${stats.favorite_activity || '-'}</div><div class="stat-lbl">${t('stats_favorite')}</div></div>
        </div>
      `;
    }
  } catch (e) {}

  let telegramSection = '';
  if (currentUser.telegram_chat_id) {
    telegramSection = `<p class="badge badge-success">${t('telegram_connected')}</p>`;
  } else {
    telegramSection = `
      <button class="btn-secondary" onclick="connectTelegram()">${t('telegram_connect')}</button>
      <p class="hint">${t('telegram_connect_hint')}</p>
      <div id="telegram-link-area"></div>
    `;
  }

  const twofaSection = currentUser.twofa_enabled
    ? `<p class="badge badge-success">${t('twofa_enabled_badge')}</p>
       <button class="btn-secondary" onclick="init2FADisable()">${t('twofa_disable')}</button>`
    : `<button class="btn-secondary" onclick="init2FAEnable()">${t('twofa_enable')}</button>`;

  content.innerHTML = `
    <h2>${t('profile')}</h2>
    ${statsHtml}
    <form onsubmit="saveProfile(event)" class="profile-form">
      <input type="text" id="prof-first" value="${currentUser.first_name}" placeholder="${t('first_name')}" required>
      <input type="text" id="prof-last" value="${currentUser.last_name}" placeholder="${t('last_name')}" required>
      <input type="tel" id="prof-phone" value="${currentUser.phone}" placeholder="${t('phone')}" required>
      <button type="submit" class="btn-primary">${t('profile_save')}</button>
    </form>

    <div class="profile-section">
      <h3>${t('telegram_connect')}</h3>
      ${telegramSection}
    </div>

    <div class="profile-section">
      <h3>${t('twofa_title')}</h3>
      ${twofaSection}
      <div id="twofa-action-area"></div>
    </div>
  `;
}

async function saveProfile(e) {
  e.preventDefault();
  try {
    const res = await apiFetch('/api/users/me', {
      method: 'PUT',
      body: JSON.stringify({
        first_name: document.getElementById('prof-first').value,
        last_name: document.getElementById('prof-last').value,
        phone: document.getElementById('prof-phone').value,
      }),
    });
    if (res.ok) {
      currentUser = await res.json();
      showToast(t('profile_saved'), 'success');
    } else {
      const d = await res.json();
      showToast(d.detail || t('error_generic'), 'error');
    }
  } catch (e) {
    showToast(t('error_generic'), 'error');
  }
}

async function connectTelegram() {
  try {
    const res = await apiFetch('/api/telegram/link');
    if (res.ok) {
      const data = await res.json();
      const area = document.getElementById('telegram-link-area');
      if (area) {
        area.innerHTML = `<a href="${data.link}" target="_blank" class="btn-primary">${t('telegram_connect')}</a>`;
        // Auto-refresh status
        if (telegramRefreshInterval) clearInterval(telegramRefreshInterval);
        let attempts = 0;
        telegramRefreshInterval = setInterval(async () => {
          attempts++;
          if (attempts > 24) { clearInterval(telegramRefreshInterval); return; }
          const r = await apiFetch('/api/telegram/status');
          if (r.ok) {
            const d = await r.json();
            if (d.connected) {
              clearInterval(telegramRefreshInterval);
              await loadCurrentUser();
              renderProfileTab();
            }
          }
        }, 5000);
      }
    }
  } catch (e) {}
}

async function init2FAEnable() {
  await apiFetch('/api/users/me/2fa/send-code?purpose=2fa_enable', { method: 'POST' });
  const area = document.getElementById('twofa-action-area');
  if (area) {
    area.innerHTML = `
      <p>${t('twofa_sent')}</p>
      <form onsubmit="submit2FAEnable(event)">
        <input type="text" id="twofa-en-code" placeholder="${t('twofa_enter')}" maxlength="6" required>
        <button type="submit" class="btn-primary">${t('twofa_verify')}</button>
      </form>
    `;
  }
}

async function submit2FAEnable(e) {
  e.preventDefault();
  const code = document.getElementById('twofa-en-code')?.value;
  const res = await apiFetch('/api/users/me/2fa/enable', { method: 'POST', body: JSON.stringify({ code }) });
  if (res.ok) {
    showToast(t('twofa_enabled_badge'), 'success');
    await loadCurrentUser();
    renderProfileTab();
  } else {
    const d = await res.json();
    showToast(d.detail || t('twofa_invalid'), 'error');
  }
}

async function init2FADisable() {
  await apiFetch('/api/users/me/2fa/send-code?purpose=2fa_disable', { method: 'POST' });
  const area = document.getElementById('twofa-action-area');
  if (area) {
    area.innerHTML = `
      <p>${t('twofa_sent')}</p>
      <form onsubmit="submit2FADisable(event)">
        <input type="text" id="twofa-dis-code" placeholder="${t('twofa_enter')}" maxlength="6" required>
        <button type="submit" class="btn-danger">${t('twofa_disable')}</button>
      </form>
    `;
  }
}

async function submit2FADisable(e) {
  e.preventDefault();
  const code = document.getElementById('twofa-dis-code')?.value;
  const res = await apiFetch('/api/users/me/2fa/disable', { method: 'POST', body: JSON.stringify({ code }) });
  if (res.ok) {
    showToast(t('twofa_disable'), 'info');
    await loadCurrentUser();
    renderProfileTab();
  } else {
    const d = await res.json();
    showToast(d.detail || t('twofa_invalid'), 'error');
  }
}

// ── Analytics Tab ──────────────────────────────────────
async function renderAnalyticsTab() {
  const content = document.getElementById('main-content');
  content.innerHTML = `
    <h2>${t('analytics')}</h2>
    <div class="time-range-btns">
      <button class="btn-sm active" onclick="setAnalyticsWeeks(4);this.closest('.time-range-btns').querySelectorAll('.btn-sm').forEach(b=>b.classList.remove('active'));this.classList.add('active')">4${t('analytics_week')}</button>
      <button class="btn-sm active" onclick="setAnalyticsWeeks(12);this.closest('.time-range-btns').querySelectorAll('.btn-sm').forEach(b=>b.classList.remove('active'));this.classList.add('active')">12${t('analytics_week')}</button>
      <button class="btn-sm" onclick="setAnalyticsWeeks(26);this.closest('.time-range-btns').querySelectorAll('.btn-sm').forEach(b=>b.classList.remove('active'));this.classList.add('active')">6m</button>
    </div>
    <div class="analytics-section">
      <h3>${t('analytics_fill_trend')}</h3>
      <div id="chart-fill-trend" class="chart-container"></div>
    </div>
    ${currentUser?.role === 'admin' ? `
    <div class="analytics-section">
      <h3>${t('analytics_top_users')}</h3>
      <div id="chart-top-users" class="chart-container"></div>
    </div>
    ` : ''}
    <div class="analytics-section">
      <h3>${t('analytics_cancel_timing')}</h3>
      <div id="chart-cancel-timing" class="chart-container" style="position:relative"></div>
    </div>
  `;
  await renderAnalytics();
}

// ── Admin Panel ────────────────────────────────────────
async function renderAdminPanel() {
  const content = document.getElementById('main-content');
  const isAdmin = currentUser?.role === 'admin';
  const sections = [
    { id: 'dashboard', label: `🏠 ${t('dashboard')}` },
    { id: 'sessions-admin', label: `📋 ${t('sessions')}` },
    { id: 'create-session', label: `➕ ${t('create_session')}` },
    ...(isAdmin ? [
      { id: 'users', label: `👥 ${t('participants')}` },
      { id: 'groups', label: `🔷 ${t('user_groups')}` },
      { id: 'blocked-dates', label: `🚫 ${t('blocked_dates')}` },
      { id: 'activity-types-admin', label: `🏷 ${t('activity_types')}` },
      { id: 'logo', label: `🖼 ${t('logo_upload')}` },
      { id: 'settings-admin', label: `⚙️ ${t('sessions')}` },
      { id: 'broadcast', label: `📢 ${t('broadcast')}` },
      { id: 'audit', label: `📜 ${t('audit_log')}` },
    ] : [])
  ];

  content.innerHTML = `
    <div class="admin-layout">
      <div class="admin-sidebar">
        ${sections.map(s => `<button class="admin-nav-btn" onclick="showAdminSection('${s.id}')">${s.label}</button>`).join('')}
      </div>
      <div class="admin-main" id="admin-section-content">
        <p class="empty-state">${t('dashboard')}</p>
      </div>
    </div>
  `;
  showAdminSection('dashboard');
}

async function showAdminSection(section) {
  document.querySelectorAll('.admin-nav-btn').forEach(b => {
    b.classList.toggle('active', b.textContent.includes(section) || b.onclick?.toString().includes(section));
  });
  const el = document.getElementById('admin-section-content');
  el.innerHTML = '<div class="loading-spinner"></div>';

  switch (section) {
    case 'dashboard': await renderAdminDashboard(el); break;
    case 'sessions-admin': await renderAdminSessions(el); break;
    case 'create-session': renderCreateSessionForm(el); break;
    case 'users': await renderAdminUsers(el); break;
    case 'groups': await renderAdminGroups(el); break;
    case 'blocked-dates': await renderAdminBlockedDates(el); break;
    case 'activity-types-admin': await renderAdminActivityTypes(el); break;
    case 'logo': await renderAdminLogo(el); break;
    case 'settings-admin': await renderAdminSettings(el); break;
    case 'broadcast': renderAdminBroadcast(el); break;
    case 'audit': await renderAdminAudit(el); break;
    default: el.innerHTML = '';
  }
}

async function renderAdminDashboard(el) {
  try {
    const res = await apiFetch('/api/admin/dashboard');
    if (!res.ok) { el.innerHTML = t('error_generic'); return; }
    const data = await res.json();
    el.innerHTML = `
      <h2>${t('dashboard')}</h2>
      <div class="stats-row">
        <div class="stat-card"><div class="stat-val">${data.total_users}</div><div class="stat-lbl">${t('participants')}</div></div>
        <div class="stat-card"><div class="stat-val">${data.avg_fill_rate}%</div><div class="stat-lbl">${t('dashboard_fill_rate')}</div></div>
      </div>
      <h3>${t('dashboard_upcoming')}</h3>
      <table class="admin-table">
        <thead><tr><th>${t('sessions')}</th><th>${t('date_time')}</th><th>${t('participants')}</th><th>%</th></tr></thead>
        <tbody>
          ${data.upcoming_sessions.map(s => `
            <tr>
              <td>${s.title}</td>
              <td>${fmtDate(s.session_date)}</td>
              <td>${s.booking_count}/${s.max_participants}</td>
              <td>${s.fill_pct}%</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } catch (e) { el.innerHTML = t('error_generic'); }
}

async function renderAdminSessions(el) {
  let filter = 'upcoming';
  async function load() {
    try {
      const isInstructor = currentUser?.role === 'instructor';
      const params = new URLSearchParams({ status_filter: filter });
      if (isInstructor) params.set('my_only', 'true');
      const res = await apiFetch(`/api/sessions?${params}`);
      if (!res.ok) return;
      const sessions = await res.json();
      el.innerHTML = `
        <h2>${t('sessions')}</h2>
        <div class="filter-tabs">
          <button class="btn-sm ${filter === 'upcoming' ? 'active' : ''}" onclick="filter='upcoming';load()">${t('session_filter_upcoming')}</button>
          <button class="btn-sm ${filter === 'past' ? 'active' : ''}" onclick="filter='past';load()">${t('session_filter_past')}</button>
          <button class="btn-sm ${filter === 'cancelled' ? 'active' : ''}" onclick="filter='cancelled';load()">${t('session_filter_cancelled')}</button>
        </div>
        <table class="admin-table">
          <thead><tr><th>${t('session_title')}</th><th>${t('date_time')}</th><th>${t('participants')}</th><th>${t('edit')}</th></tr></thead>
          <tbody>
            ${sessions.map(s => `
              <tr>
                <td>${s.title} ${s.is_cancelled ? `<span class="badge badge-cancelled">${t('session_cancelled_badge')}</span>` : ''}</td>
                <td>${fmtDate(s.session_date)}</td>
                <td>${s.booking_count}/${s.max_participants}</td>
                <td class="action-cell">
                  <button class="btn-sm" onclick="openEditSession(${s.id})">${t('edit')}</button>
                  ${!s.is_cancelled ? `<button class="btn-sm btn-danger" onclick="adminCancelSession(${s.id})">${t('cancel_session')}</button>` : ''}
                  <a href="/api/sessions/${s.id}/export/csv" class="btn-sm">${t('export_csv')}</a>
                  <a href="/api/sessions/${s.id}/export/excel" class="btn-sm">${t('export_excel')}</a>
                  <a href="/api/sessions/${s.id}/pdf/attendance" class="btn-sm" target="_blank">${t('pdf_attendance')}</a>
                  <a href="/api/sessions/${s.id}/pdf/card" class="btn-sm" target="_blank">${t('pdf_session_card')}</a>
                  <button class="btn-sm" onclick="openAttendance(${s.id})">${t('attendance')}</button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    } catch (e) { el.innerHTML = t('error_generic'); }
  }
  load();
}

async function adminCancelSession(id) {
  if (!confirm(t('cancel_session_confirm'))) return;
  const res = await apiFetch(`/api/sessions/${id}/cancel`, { method: 'POST' });
  if (res.ok) { showToast(t('session_cancelled_badge'), 'info'); showAdminSection('sessions-admin'); }
  else { const d = await res.json(); showToast(d.detail || t('error_generic'), 'error'); }
}

async function openAttendance(sessionId) {
  try {
    const res = await apiFetch(`/api/sessions/${sessionId}/attendance`);
    if (!res.ok) return;
    const bookings = await res.json();
    const modal = document.getElementById('modal-overlay');
    const body = document.getElementById('modal-body');
    body.innerHTML = `
      <h2>${t('attendance')}</h2>
      <table class="admin-table">
        <thead><tr><th>${t('first_name')}</th><th>${t('last_name')}</th><th>${t('phone')}</th><th>${t('attendance')}</th></tr></thead>
        <tbody>
          ${bookings.map(b => `
            <tr>
              <td>${b.first_name}</td>
              <td>${b.last_name}</td>
              <td>${b.phone}</td>
              <td>
                <button class="btn-sm ${b.attended ? 'btn-success' : ''}" onclick="markAttendance(${sessionId},${b.user_id},true)">${t('mark_attended')}</button>
                <button class="btn-sm ${b.attended === false ? 'btn-danger' : ''}" onclick="markAttendance(${sessionId},${b.user_id},false)">${t('mark_absent')}</button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
    modal.style.display = 'flex';
  } catch (e) {}
}

async function markAttendance(sessionId, userId, attended) {
  await apiFetch(`/api/sessions/${sessionId}/attendance/${userId}`, {
    method: 'POST',
    body: JSON.stringify({ attended }),
  });
  openAttendance(sessionId);
}

function renderCreateSessionForm(el, existingSession) {
  const s = existingSession || {};
  const isEdit = !!s.id;

  el.innerHTML = `
    <h2>${isEdit ? t('edit') : t('create_session')}</h2>
    <form onsubmit="${isEdit ? `submitEditSession(event,${s.id})` : 'submitCreateSession(event)'}" class="session-form">
      <label>${t('session_title')}</label>
      <input type="text" id="sf-title" value="${s.title || ''}" required>

      <label>${t('activity_type_label')}</label>
      <select id="sf-type"><option value="">${t('activity_select')}</option></select>

      <label>${t('date_time')}</label>
      <input type="datetime-local" id="sf-date" value="${s.session_date ? s.session_date.slice(0,16) : ''}" required>

      <label>${t('max_participants')}</label>
      <input type="number" id="sf-max" value="${s.max_participants || 10}" min="1" required>

      <label>${t('location')}</label>
      <input type="text" id="sf-location" value="${s.location || ''}">

      <label>${t('description')}</label>
      <textarea id="sf-desc">${s.description || ''}</textarea>

      <label>${t('requirements')}</label>
      <textarea id="sf-req">${s.requirements || ''}</textarea>

      <label>${t('online_link')}</label>
      <input type="url" id="sf-online" value="${s.online_link || ''}" placeholder="${t('online_link_placeholder')}">
      <small>${t('online_link_hint')}</small>

      ${currentUser?.role === 'admin' ? `
      <label>${t('instructor_role')}</label>
      <select id="sf-instructor"><option value="">${t('filter_all')}</option></select>
      ` : ''}

      <label>${t('session_groups')}</label>
      <div id="sf-groups-area"></div>

      ${!isEdit ? `
      <label><input type="checkbox" id="sf-recurring" onchange="toggleRecurring()"> ${t('recurring')}</label>
      <div id="recurring-options" style="display:none">
        <label>${t('recurring_freq')}</label>
        <select id="sf-freq">
          <option value="weekly">${t('every_week')}</option>
          <option value="biweekly">${t('every_two_weeks')}</option>
        </select>
        <label>${t('recurring_until')}</label>
        <input type="date" id="sf-until">
      </div>
      ` : ''}

      <button type="submit" class="btn-primary">${t('save')}</button>
    </form>
  `;
  loadSessionFormSelects(s);
}

async function loadSessionFormSelects(s) {
  try {
    const atRes = await fetch('/api/activity-types');
    if (atRes.ok) {
      const types = await atRes.json();
      const sel = document.getElementById('sf-type');
      if (sel) types.forEach(at => {
        const opt = new Option(at.name, at.id);
        if (s.activity_type_id == at.id) opt.selected = true;
        sel.add(opt);
      });
    }
  } catch (e) {}

  if (currentUser?.role === 'admin') {
    try {
      const uRes = await apiFetch('/api/admin/users');
      if (uRes.ok) {
        const users = await uRes.json();
        const sel = document.getElementById('sf-instructor');
        if (sel) users.filter(u => u.role !== 'user').forEach(u => {
          const opt = new Option(`${u.first_name} ${u.last_name}`, u.id);
          if (s.instructor_id == u.id) opt.selected = true;
          sel.add(opt);
        });
      }
    } catch (e) {}
  }

  try {
    const gRes = await apiFetch('/api/user-groups');
    if (gRes.ok) {
      const groups = await gRes.json();
      const area = document.getElementById('sf-groups-area');
      if (area) {
        area.innerHTML = groups.map(g => `
          <label style="display:flex;gap:6px;align-items:center">
            <input type="checkbox" name="group" value="${g.id}" ${(s.group_ids || []).includes(g.id) ? 'checked' : ''}>
            ${g.name}
          </label>
        `).join('');
      }
    }
  } catch (e) {}
}

function toggleRecurring() {
  const checked = document.getElementById('sf-recurring')?.checked;
  const opts = document.getElementById('recurring-options');
  if (opts) opts.style.display = checked ? 'block' : 'none';
}

async function submitCreateSession(e) {
  e.preventDefault();
  const groupIds = [...document.querySelectorAll('input[name=group]:checked')].map(c => parseInt(c.value));
  const recurring = document.getElementById('sf-recurring')?.checked;
  const body = {
    title: document.getElementById('sf-title').value,
    activity_type_id: document.getElementById('sf-type').value || null,
    session_date: document.getElementById('sf-date').value,
    max_participants: parseInt(document.getElementById('sf-max').value),
    location: document.getElementById('sf-location').value || null,
    description: document.getElementById('sf-desc').value || null,
    requirements: document.getElementById('sf-req').value || null,
    online_link: document.getElementById('sf-online').value || null,
    instructor_id: document.getElementById('sf-instructor')?.value || null,
    allowed_group_ids: groupIds,
    recurring_freq: recurring ? document.getElementById('sf-freq').value : null,
    recurring_until: recurring ? document.getElementById('sf-until').value || null : null,
  };
  try {
    const res = await apiFetch('/api/sessions', { method: 'POST', body: JSON.stringify(body) });
    const data = await res.json();
    if (res.ok) {
      showToast(t('booking_success'), 'success');
      showAdminSection('sessions-admin');
    } else {
      showToast(data.detail || t('error_generic'), 'error');
    }
  } catch (e) {
    showToast(t('error_generic'), 'error');
  }
}

async function openEditSession(id) {
  try {
    const res = await apiFetch(`/api/sessions/${id}`);
    if (!res.ok) return;
    const s = await res.json();
    const el = document.getElementById('admin-section-content');
    renderCreateSessionForm(el, s);
  } catch (e) {}
}

async function submitEditSession(e, id) {
  e.preventDefault();
  const groupIds = [...document.querySelectorAll('input[name=group]:checked')].map(c => parseInt(c.value));
  const body = {
    title: document.getElementById('sf-title').value,
    activity_type_id: document.getElementById('sf-type').value || null,
    session_date: document.getElementById('sf-date').value,
    max_participants: parseInt(document.getElementById('sf-max').value),
    location: document.getElementById('sf-location').value || null,
    description: document.getElementById('sf-desc').value || null,
    requirements: document.getElementById('sf-req').value || null,
    online_link: document.getElementById('sf-online').value || null,
    instructor_id: document.getElementById('sf-instructor')?.value || null,
    allowed_group_ids: groupIds,
  };
  try {
    const res = await apiFetch(`/api/sessions/${id}`, { method: 'PUT', body: JSON.stringify(body) });
    const data = await res.json();
    if (res.ok) {
      showToast(t('profile_saved'), 'success');
      showAdminSection('sessions-admin');
    } else {
      showToast(data.detail || t('error_generic'), 'error');
    }
  } catch (e) {
    showToast(t('error_generic'), 'error');
  }
}

async function renderAdminUsers(el) {
  try {
    const res = await apiFetch('/api/admin/users');
    if (!res.ok) { el.innerHTML = t('error_generic'); return; }
    const users = await res.json();
    el.innerHTML = `
      <h2>${t('participants')}</h2>
      <table class="admin-table">
        <thead><tr><th>${t('first_name')} ${t('last_name')}</th><th>${t('phone')}</th><th>Role</th><th>Telegram</th><th>2FA</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>
          ${users.map(u => `
            <tr>
              <td>${u.first_name} ${u.last_name}</td>
              <td>${u.phone}</td>
              <td>
                <select onchange="changeUserRole(${u.id}, this.value)">
                  ${['user','instructor','admin'].map(r => `<option ${u.role===r?'selected':''} value="${r}">${t('role_'+r)}</option>`).join('')}
                </select>
              </td>
              <td>${u.telegram_chat_id ? '✓' : '✗'}</td>
              <td>${u.twofa_enabled ? '✓' : '✗'}</td>
              <td>${u.is_blocked ? `<span class="badge badge-cancelled">${t('blocked_badge')}</span>` : '✓'}</td>
              <td>
                ${u.is_blocked
                  ? `<button class="btn-sm" onclick="adminUnblockUser(${u.id})">${t('unblock_user')}</button>`
                  : `<button class="btn-sm btn-danger" onclick="adminBlockUser(${u.id})">${t('block_user')}</button>`}
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } catch (e) { el.innerHTML = t('error_generic'); }
}

async function changeUserRole(userId, role) {
  await apiFetch(`/api/admin/users/${userId}/role`, { method: 'PUT', body: JSON.stringify({ role }) });
  showToast(t('profile_saved'), 'success');
}

async function adminBlockUser(userId) {
  const reason = prompt(t('block_reason'));
  if (!reason) return;
  const res = await apiFetch(`/api/admin/users/${userId}/block`, { method: 'POST', body: JSON.stringify({ reason }) });
  if (res.ok) { showToast(t('blocked_badge'), 'info'); renderAdminUsers(document.getElementById('admin-section-content')); }
}

async function adminUnblockUser(userId) {
  const res = await apiFetch(`/api/admin/users/${userId}/unblock`, { method: 'POST' });
  if (res.ok) { showToast(t('unblock_user'), 'success'); renderAdminUsers(document.getElementById('admin-section-content')); }
}

async function renderAdminGroups(el) {
  try {
    const res = await apiFetch('/api/user-groups');
    if (!res.ok) { el.innerHTML = t('error_generic'); return; }
    const groups = await res.json();
    el.innerHTML = `
      <h2>${t('user_groups')}</h2>
      <form onsubmit="createGroup(event)" style="display:flex;gap:8px;margin-bottom:16px">
        <input type="text" id="new-group-name" placeholder="${t('group_name')}" required>
        <input type="text" id="new-group-desc" placeholder="${t('description')}">
        <button type="submit" class="btn-primary">${t('group_add')}</button>
      </form>
      <div id="groups-list">
        ${groups.map(g => `
          <div class="group-row">
            <strong>${g.name}</strong>
            ${g.description ? `<span>${g.description}</span>` : ''}
            <button class="btn-sm" onclick="openGroupMembers(${g.id},'${g.name}')">${t('group_members')}</button>
            <button class="btn-sm btn-danger" onclick="deleteGroup(${g.id})">${t('delete')}</button>
          </div>
        `).join('')}
      </div>
    `;
  } catch (e) { el.innerHTML = t('error_generic'); }
}

async function createGroup(e) {
  e.preventDefault();
  const name = document.getElementById('new-group-name').value;
  const desc = document.getElementById('new-group-desc').value;
  const res = await apiFetch('/api/user-groups', { method: 'POST', body: JSON.stringify({ name, description: desc }) });
  if (res.ok) { renderAdminGroups(document.getElementById('admin-section-content')); }
  else { const d = await res.json(); showToast(d.detail || t('error_generic'), 'error'); }
}

async function deleteGroup(id) {
  if (!confirm(t('group_delete_confirm'))) return;
  await apiFetch(`/api/user-groups/${id}`, { method: 'DELETE' });
  renderAdminGroups(document.getElementById('admin-section-content'));
}

async function openGroupMembers(groupId, groupName) {
  try {
    const res = await apiFetch(`/api/user-groups/${groupId}/members`);
    if (!res.ok) return;
    const members = await res.json();
    const usersRes = await apiFetch('/api/admin/users');
    const users = usersRes.ok ? await usersRes.json() : [];
    const modal = document.getElementById('modal-overlay');
    const body = document.getElementById('modal-body');
    body.innerHTML = `
      <h2>${t('group_members')} - ${groupName}</h2>
      <div style="display:flex;gap:8px;margin-bottom:16px">
        <select id="add-member-select">
          ${users.map(u => `<option value="${u.id}">${u.first_name} ${u.last_name} (${u.phone})</option>`).join('')}
        </select>
        <button class="btn-primary" onclick="addGroupMember(${groupId})">${t('group_add_member')}</button>
      </div>
      <table class="admin-table">
        <thead><tr><th>${t('first_name')}</th><th>${t('last_name')}</th><th>${t('phone')}</th><th></th></tr></thead>
        <tbody>
          ${members.map(m => `
            <tr>
              <td>${m.first_name}</td>
              <td>${m.last_name}</td>
              <td>${m.phone}</td>
              <td><button class="btn-sm btn-danger" onclick="removeGroupMember(${groupId},${m.user_id})">${t('group_remove_member')}</button></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
    modal.style.display = 'flex';
  } catch (e) {}
}

async function addGroupMember(groupId) {
  const userId = document.getElementById('add-member-select')?.value;
  if (!userId) return;
  await apiFetch(`/api/user-groups/${groupId}/members`, { method: 'POST', body: JSON.stringify({ user_id: parseInt(userId) }) });
  const groupName = document.querySelector('#modal-body h2')?.textContent?.split(' - ')[1] || '';
  openGroupMembers(groupId, groupName);
}

async function removeGroupMember(groupId, userId) {
  await apiFetch(`/api/user-groups/${groupId}/members/${userId}`, { method: 'DELETE' });
  const groupName = document.querySelector('#modal-body h2')?.textContent?.split(' - ')[1] || '';
  openGroupMembers(groupId, groupName);
}

async function renderAdminBlockedDates(el) {
  try {
    const res = await apiFetch('/api/blocked-dates');
    if (!res.ok) { el.innerHTML = t('error_generic'); return; }
    const dates = await res.json();
    el.innerHTML = `
      <h2>${t('blocked_dates')}</h2>
      <p class="hint">${t('recurring_skip_blocked')}</p>
      <form onsubmit="createBlockedDate(event)" style="display:flex;gap:8px;margin-bottom:16px">
        <input type="date" id="bd-date" required>
        <input type="text" id="bd-label" placeholder="${t('blocked_date_label')}" required>
        <button type="submit" class="btn-primary">${t('blocked_date_add')}</button>
      </form>
      <table class="admin-table">
        <thead><tr><th>${t('filter_date')}</th><th>${t('description')}</th><th></th></tr></thead>
        <tbody>
          ${dates.map(d => `<tr><td>${d.date}</td><td>${d.label}</td><td><button class="btn-sm btn-danger" onclick="deleteBlockedDate(${d.id})">${t('delete')}</button></td></tr>`).join('')}
        </tbody>
      </table>
    `;
  } catch (e) { el.innerHTML = t('error_generic'); }
}

async function createBlockedDate(e) {
  e.preventDefault();
  const date = document.getElementById('bd-date').value;
  const label = document.getElementById('bd-label').value;
  const res = await apiFetch('/api/blocked-dates', { method: 'POST', body: JSON.stringify({ date, label }) });
  if (res.ok) renderAdminBlockedDates(document.getElementById('admin-section-content'));
  else { const d = await res.json(); showToast(d.detail || t('error_generic'), 'error'); }
}

async function deleteBlockedDate(id) {
  if (!confirm(t('blocked_date_confirm'))) return;
  await apiFetch(`/api/blocked-dates/${id}`, { method: 'DELETE' });
  renderAdminBlockedDates(document.getElementById('admin-section-content'));
}

async function renderAdminActivityTypes(el) {
  try {
    const res = await fetch('/api/activity-types');
    if (!res.ok) { el.innerHTML = t('error_generic'); return; }
    const types = await res.json();
    el.innerHTML = `
      <h2>${t('activity_types')}</h2>
      <form onsubmit="createActivityType(event)" style="display:flex;gap:8px;margin-bottom:16px">
        <input type="text" id="at-name" placeholder="${t('activity_name')}" required>
        <input type="text" id="at-desc" placeholder="${t('activity_desc')}">
        <input type="number" id="at-order" placeholder="Order" value="0" style="width:70px">
        <button type="submit" class="btn-primary">${t('activity_add')}</button>
      </form>
      <table class="admin-table">
        <thead><tr><th>${t('activity_name')}</th><th>${t('description')}</th><th></th></tr></thead>
        <tbody>
          ${types.map(at => `<tr><td>${at.name}</td><td>${at.description || ''}</td><td>
            <button class="btn-sm btn-danger" onclick="deleteActivityType(${at.id})">${t('delete')}</button>
          </td></tr>`).join('')}
        </tbody>
      </table>
    `;
  } catch (e) { el.innerHTML = t('error_generic'); }
}

async function createActivityType(e) {
  e.preventDefault();
  const res = await apiFetch('/api/activity-types', {
    method: 'POST',
    body: JSON.stringify({ name: document.getElementById('at-name').value, description: document.getElementById('at-desc').value, sort_order: parseInt(document.getElementById('at-order').value) || 0 }),
  });
  if (res.ok) renderAdminActivityTypes(document.getElementById('admin-section-content'));
  else { const d = await res.json(); showToast(d.detail || t('error_generic'), 'error'); }
}

async function deleteActivityType(id) {
  if (!confirm(t('activity_delete_confirm'))) return;
  const res = await apiFetch(`/api/activity-types/${id}`, { method: 'DELETE' });
  if (res.ok) renderAdminActivityTypes(document.getElementById('admin-section-content'));
  else { const d = await res.json(); showToast(d.detail || t('error_generic'), 'error'); }
}

async function renderAdminLogo(el) {
  try {
    const res = await apiFetch('/api/settings/logo');
    const data = res.ok ? await res.json() : {};
    el.innerHTML = `
      <h2>${t('logo_upload')}</h2>
      ${data.logo_filename ? `
        <div id="current-logo">
          <p>${t('logo_current')}</p>
          <img src="/uploads/logo/${data.logo_filename}" style="max-height:80px;max-width:200px;border:1px solid #e2e8f0;border-radius:8px;padding:8px">
          <button class="btn-sm btn-danger" onclick="removeLogo()">${t('logo_remove')}</button>
        </div>
      ` : ''}
      <form onsubmit="uploadLogo(event)">
        <input type="file" id="logo-file" accept="image/*" required>
        <small>${t('logo_hint')}</small>
        <button type="submit" class="btn-primary">${t('logo_upload')}</button>
      </form>
    `;
  } catch (e) { el.innerHTML = t('error_generic'); }
}

async function uploadLogo(e) {
  e.preventDefault();
  const file = document.getElementById('logo-file').files[0];
  if (!file) return;
  const form = new FormData();
  form.append('file', file);
  const res = await fetch('/api/settings/logo', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` },
    body: form,
  });
  if (res.ok) { showToast(t('profile_saved'), 'success'); renderAdminLogo(document.getElementById('admin-section-content')); }
  else { const d = await res.json(); showToast(d.detail || t('error_generic'), 'error'); }
}

async function removeLogo() {
  await apiFetch('/api/settings/logo', { method: 'DELETE' });
  renderAdminLogo(document.getElementById('admin-section-content'));
}

async function renderAdminSettings(el) {
  try {
    const res = await apiFetch('/api/settings/config');
    if (!res.ok) { el.innerHTML = t('error_generic'); return; }
    const cfg = await res.json();
    const widgetCode = `<div id="training-widget"\n     data-url="${window.location.origin}"\n     data-limit="5"\n     data-lang="${currentLang}"\n     data-theme="auto">\n</div>\n<script src="${window.location.origin}/static/widget.js" defer><\/script>`;
    el.innerHTML = `
      <h2>⚙️ ${t('sessions')}</h2>
      <form onsubmit="saveSettings(event)" class="settings-form">
        <label>${t('app_name_setting')}</label>
        <input type="text" id="cfg-appname" value="${cfg.app_name}">

        <label>${t('primary_color_setting')}</label>
        <input type="color" id="cfg-color" value="${cfg.primary_color}">

        <label>${t('cancel_hours_setting')}</label>
        <input type="number" id="cfg-cancel" value="${cfg.cancel_hours_limit}" min="0">

        <label>${t('waitlist_minutes_setting')}</label>
        <input type="number" id="cfg-waitlist" value="${cfg.waitlist_hold_minutes}" min="5">

        <label>${t('support_chat')}</label>
        <input type="text" id="cfg-support" value="${cfg.support_telegram_username || ''}" placeholder="@username">

        <button type="submit" class="btn-primary">${t('save')}</button>
      </form>

      <h3>${t('widget_embed_code')}</h3>
      <textarea readonly style="width:100%;height:120px;font-family:monospace;font-size:12px" id="widget-code">${widgetCode}</textarea>
      <button class="btn-sm" onclick="copyWidgetCode()">${t('widget_copy')}</button>
      <h3>${t('widget_preview')}</h3>
      <iframe src="data:text/html;charset=utf-8,${encodeURIComponent(`<!DOCTYPE html><html><head><meta charset=utf-8></head><body style='margin:0'><div id='training-widget' data-url='${window.location.origin}' data-limit='3' data-lang='${currentLang}' data-theme='auto'></div><script src='${window.location.origin}/static/widget.js' defer></sc`+'ript></body></html>')}" style="width:100%;height:280px;border:1px solid #e2e8f0;border-radius:8px"></iframe>
    `;
  } catch (e) { el.innerHTML = t('error_generic'); }
}

async function saveSettings(e) {
  e.preventDefault();
  const body = {
    app_name: document.getElementById('cfg-appname').value,
    primary_color: document.getElementById('cfg-color').value,
    cancel_hours_limit: parseInt(document.getElementById('cfg-cancel').value),
    waitlist_hold_minutes: parseInt(document.getElementById('cfg-waitlist').value),
    support_telegram_username: document.getElementById('cfg-support').value || null,
  };
  const res = await apiFetch('/api/settings/config', { method: 'PUT', body: JSON.stringify(body) });
  if (res.ok) showToast(t('profile_saved'), 'success');
  else { const d = await res.json(); showToast(d.detail || t('error_generic'), 'error'); }
}

function copyWidgetCode() {
  const code = document.getElementById('widget-code')?.value;
  if (code) {
    navigator.clipboard.writeText(code).then(() => showToast(t('widget_copied'), 'success'));
  }
}

function renderAdminBroadcast(el) {
  el.innerHTML = `
    <h2>${t('broadcast')}</h2>
    <form onsubmit="previewBroadcast(event)">
      <textarea id="broadcast-msg" placeholder="${t('broadcast_message')}" rows="5" style="width:100%" required></textarea>
      <button type="submit" class="btn-primary">${t('broadcast_send')}</button>
    </form>
    <div id="broadcast-preview"></div>
  `;
}

async function previewBroadcast(e) {
  e.preventDefault();
  const msg = document.getElementById('broadcast-msg').value;
  try {
    const res = await apiFetch('/api/admin/broadcast', { method: 'POST', body: JSON.stringify({ message: msg, confirm: false }) });
    const data = await res.json();
    document.getElementById('broadcast-preview').innerHTML = `
      <p>${t('broadcast_confirm').replace('{count}', data.recipient_count)}</p>
      <button class="btn-danger" onclick="confirmBroadcast('${encodeURIComponent(msg)}')">${t('broadcast_send')}</button>
    `;
  } catch (e) { showToast(t('error_generic'), 'error'); }
}

async function confirmBroadcast(encoded) {
  const msg = decodeURIComponent(encoded);
  const res = await apiFetch('/api/admin/broadcast', { method: 'POST', body: JSON.stringify({ message: msg, confirm: true }) });
  const data = await res.json();
  showToast(t('broadcast_sent').replace('{count}', data.recipient_count), 'success');
}

async function renderAdminAudit(el) {
  let page = 1;
  let actionType = 'all';
  async function load() {
    try {
      const res = await apiFetch(`/api/admin/audit-log?page=${page}&action_type=${actionType}`);
      if (!res.ok) { el.innerHTML = t('error_generic'); return; }
      const data = await res.json();
      el.innerHTML = `
        <h2>${t('audit_log')}</h2>
        <div class="filter-tabs">
          ${['all','bookings','users','sessions','admin'].map(f => `<button class="btn-sm ${actionType===f?'active':''}" onclick="actionType='${f}';page=1;load()">${t('audit_filter_'+f)}</button>`).join('')}
        </div>
        <table class="admin-table audit-table">
          <thead><tr><th>${t('audit_time')}</th><th>${t('audit_user')}</th><th>${t('audit_action')}</th><th>${t('audit_details')}</th></tr></thead>
          <tbody>
            ${data.items.map(r => {
              let cls = '';
              if (r.action.startsWith('booking.')) cls = 'audit-booking';
              else if (r.action.includes('fail') || r.action.includes('blocked')) cls = 'audit-danger';
              else if (r.action.startsWith('user.blocked')) cls = 'audit-warn';
              else if (r.action.startsWith('session.cancelled')) cls = 'audit-warn';
              else if (r.action.startsWith('admin.')) cls = 'audit-admin';
              return `<tr class="${cls}">
                <td>${fmtDate(r.created_at)}</td>
                <td>${r.actor_name}</td>
                <td><code>${r.action}</code></td>
                <td><small>${r.target_label || ''} ${r.details ? `<details><summary>+</summary><pre>${r.details}</pre></details>` : ''}</small></td>
              </tr>`;
            }).join('')}
          </tbody>
        </table>
        <div class="pagination">
          ${page > 1 ? `<button class="btn-sm" onclick="page--;load()">◀</button>` : ''}
          <span>${page} / ${data.pages}</span>
          ${page < data.pages ? `<button class="btn-sm" onclick="page++;load()">▶</button>` : ''}
        </div>
      `;
    } catch (e) { el.innerHTML = t('error_generic'); }
  }
  load();
}

// ── Support Chat Button ────────────────────────────────
async function renderSupportButton() {
  try {
    const res = await fetch('/api/settings/logo');
    const cfg = res.ok ? await res.json() : {};
  } catch (e) {}
  try {
    const res = await apiFetch('/api/settings/config');
    if (res.ok) {
      const cfg = await res.json();
      const btn = document.getElementById('support-chat-btn');
      if (btn && cfg.support_telegram_username) {
        btn.href = `https://t.me/${cfg.support_telegram_username.replace('@','')}`;
        btn.style.display = 'flex';
        btn.title = t('support_chat');
      }
    }
  } catch (e) {}
}

// ── PWA Install ────────────────────────────────────────
window.addEventListener('beforeinstallprompt', e => {
  e.preventDefault();
  deferredInstallPrompt = e;
  const banner = document.getElementById('pwa-banner');
  if (banner) banner.style.display = 'flex';
});

function installPWA() {
  if (deferredInstallPrompt) {
    deferredInstallPrompt.prompt();
    deferredInstallPrompt.userChoice.then(() => {
      deferredInstallPrompt = null;
      const banner = document.getElementById('pwa-banner');
      if (banner) banner.style.display = 'none';
    });
  }
}

// ── Service Worker ─────────────────────────────────────
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/sw.js').catch(() => {});
  });
}

// ── Init ───────────────────────────────────────────────
async function init() {
  applyLang(currentLang);

  // Modal close on outside click
  document.getElementById('modal-overlay')?.addEventListener('click', e => {
    if (e.target === document.getElementById('modal-overlay')) closeModal();
  });

  if (token) {
    const user = await loadCurrentUser();
    if (user) {
      showApp();
      await renderSupportButton();
    } else {
      token = null;
      localStorage.removeItem('token');
      showAuthScreen();
    }
  } else {
    showAuthScreen();
  }

  // Hash routing
  const hash = window.location.hash;
  if (hash.startsWith('#rate/') && currentUser) {
    const sid = parseInt(hash.split('/')[1]);
    if (sid) setTimeout(() => openReviewModal(sid), 500);
  }
}

document.addEventListener('DOMContentLoaded', init);
