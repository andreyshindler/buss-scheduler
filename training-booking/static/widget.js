(function() {
  'use strict';

  const W_STRINGS = {
    he: {
      book_now: "הרשמה", view_all: "לכל האימונים",
      spots_left: "מקומות פנויים", full: "מלא",
      online: "אונליין", no_sessions: "אין אימונים קרובים",
      powered_by: "מופעל על ידי", loading: "טוען..."
    },
    en: {
      book_now: "Book now", view_all: "View all sessions",
      spots_left: "spots left", full: "Full",
      online: "Online", no_sessions: "No upcoming sessions",
      powered_by: "Powered by", loading: "Loading..."
    }
  };

  function getStr(lang, key) {
    return (W_STRINGS[lang] || W_STRINGS.he)[key] || key;
  }

  function formatDate(isoStr, lang) {
    try {
      const d = new Date(isoStr);
      const opts = { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' };
      const locale = lang === 'he' ? 'he-IL' : 'en-US';
      return d.toLocaleString(locale, opts);
    } catch (e) {
      return isoStr;
    }
  }

  function getTheme(dataTheme) {
    if (dataTheme === 'dark') return 'dark';
    if (dataTheme === 'light') return 'light';
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark';
    return 'light';
  }

  function buildCSS(primary, theme, dir) {
    const isDark = theme === 'dark';
    const bg = isDark ? '#1e293b' : '#fff';
    const cardBg = isDark ? '#0f172a' : '#f8fafc';
    const text = isDark ? '#f1f5f9' : '#1e293b';
    const sub = isDark ? '#94a3b8' : '#64748b';
    const border = isDark ? '#334155' : '#e2e8f0';

    return `
      :host { all: initial; font-family: system-ui, -apple-system, sans-serif; display: block; }
      .tbw { background: ${bg}; color: ${text}; border-radius: 12px; padding: 16px; border: 1px solid ${border}; direction: ${dir}; max-width: 100%; }
      .tbw-grid { display: grid; grid-template-columns: 1fr; gap: 12px; }
      @media (min-width: 400px) { .tbw-grid { grid-template-columns: 1fr 1fr; } }
      .tbw-card { background: ${cardBg}; border-radius: 8px; overflow: hidden; border: 1px solid ${border}; transition: transform 0.2s; cursor: pointer; }
      .tbw-card:hover { transform: scale(1.02); }
      .tbw-cover { height: 80px; background: ${primary}; position: relative; overflow: hidden; }
      .tbw-cover img { width: 100%; height: 100%; object-fit: cover; }
      .tbw-badge { position: absolute; top: 6px; ${dir === 'rtl' ? 'right' : 'left'}: 6px; background: ${primary}; color: #fff; font-size: 11px; padding: 2px 6px; border-radius: 4px; }
      .tbw-body { padding: 10px; }
      .tbw-activity { font-size: 11px; color: ${primary}; font-weight: 600; margin-bottom: 3px; }
      .tbw-title { font-size: 14px; font-weight: 700; margin-bottom: 4px; }
      .tbw-date { font-size: 12px; color: ${sub}; margin-bottom: 4px; }
      .tbw-spots { font-size: 12px; margin-bottom: 8px; }
      .tbw-spots-bar { height: 4px; background: #e2e8f0; border-radius: 2px; margin-bottom: 8px; }
      .tbw-spots-fill { height: 100%; border-radius: 2px; }
      .tbw-btn { display: block; text-align: center; background: ${primary}; color: #fff; padding: 7px; border-radius: 6px; text-decoration: none; font-size: 13px; font-weight: 600; }
      .tbw-btn.full { background: #6b7280; cursor: default; }
      .tbw-footer { margin-top: 12px; display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: ${sub}; }
      .tbw-footer a { color: ${primary}; text-decoration: none; font-weight: 600; }
      .tbw-empty { text-align: center; padding: 24px; color: ${sub}; }
      .tbw-skeleton { background: ${border}; border-radius: 4px; animation: tbw-pulse 1.5s ease-in-out infinite; }
      @keyframes tbw-pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
    `;
  }

  function spotsColor(left, total) {
    const ratio = left / total;
    if (ratio === 0) return '#ef4444';
    if (ratio < 0.3) return '#f59e0b';
    return '#22c55e';
  }

  function renderSkeleton(shadow, lang) {
    const s = getStr(lang, 'loading');
    shadow.innerHTML = `
      <style>${buildCSS('#2563eb', 'light', 'rtl')}</style>
      <div class="tbw"><div class="tbw-empty" style="animation: tbw-pulse 1.5s infinite">${s}</div></div>
    `;
  }

  function renderError(shadow, lang) {
    shadow.innerHTML = `
      <style>${buildCSS('#2563eb', 'light', 'rtl')}</style>
      <div class="tbw"><div class="tbw-empty">${getStr(lang, 'no_sessions')}</div></div>
    `;
  }

  function renderWidget(shadow, config, sessions, lang, theme, appUrl) {
    const dir = lang === 'he' ? 'rtl' : 'ltr';
    const primary = config.primary_color || '#2563eb';
    const s = (k) => getStr(lang, k);

    let cardsHtml = '';
    if (!sessions || !sessions.length) {
      cardsHtml = `<div class="tbw-empty">${s('no_sessions')}</div>`;
    } else {
      cardsHtml = `<div class="tbw-grid">`;
      for (const sess of sessions) {
        const isFull = sess.is_full;
        const spotsColor_ = spotsColor(sess.spots_left, sess.spots_total);
        const pct = Math.round((sess.spots_taken / sess.spots_total) * 100);
        const dateStr = formatDate(sess.session_date, lang);

        let coverHtml = `<div class="tbw-cover" style="background:${primary};">`;
        if (sess.cover_image_url) {
          coverHtml += `<img src="${sess.cover_image_url}" alt="" onerror="this.style.display='none'">`;
        }
        if (sess.is_online) {
          coverHtml += `<span class="tbw-badge">${s('online')}</span>`;
        }
        coverHtml += `</div>`;

        const spotsText = isFull ? `<span style="color:#ef4444">${s('full')}</span>` : `${sess.spots_left} ${s('spots_left')}`;
        const btnClass = isFull ? 'tbw-btn full' : 'tbw-btn';
        const btnHref = isFull ? '#' : sess.booking_url;
        const btnTarget = isFull ? '' : 'target="_blank" rel="noopener"';

        cardsHtml += `
          <div class="tbw-card">
            ${coverHtml}
            <div class="tbw-body">
              ${sess.activity_type ? `<div class="tbw-activity">${sess.activity_type.name}</div>` : ''}
              <div class="tbw-title">${sess.title}</div>
              <div class="tbw-date">${dateStr}</div>
              <div class="tbw-spots">${spotsText}</div>
              <div class="tbw-spots-bar"><div class="tbw-spots-fill" style="width:${pct}%;background:${spotsColor_}"></div></div>
              <a class="${btnClass}" href="${isFull ? '#' : btnHref}" ${isFull ? '' : btnTarget}>${s('book_now')}</a>
            </div>
          </div>
        `;
      }
      cardsHtml += `</div>`;
    }

    const logoHtml = config.logo_url
      ? `<img src="${config.logo_url}" alt="${config.app_name}" style="height:28px;object-fit:contain;vertical-align:middle"> `
      : '';

    shadow.innerHTML = `
      <style>${buildCSS(primary, theme, dir)}</style>
      <div class="tbw">
        ${cardsHtml}
        <div class="tbw-footer">
          <a href="${appUrl || '/'}" target="_blank" rel="noopener">${s('view_all')}</a>
          <span>${s('powered_by')} ${logoHtml}<strong>${config.app_name || 'Training Booking'}</strong></span>
        </div>
      </div>
    `;
  }

  async function init() {
    const container = document.getElementById('training-widget');
    if (!container) {
      console.warn('[training-widget] Container #training-widget not found');
      return;
    }

    const baseUrl = container.dataset.url;
    if (!baseUrl) {
      console.warn('[training-widget] data-url is required');
      return;
    }

    const limit = Math.min(parseInt(container.dataset.limit || '5'), 20);
    const lang = container.dataset.lang || 'he';
    const activityTypeId = container.dataset.activityType || '';
    const themeAttr = container.dataset.theme || 'auto';
    const theme = getTheme(themeAttr);

    let shadow;
    try {
      shadow = container.attachShadow({ mode: 'open' });
    } catch (e) {
      shadow = container;
    }

    renderSkeleton(shadow, lang);

    try {
      const [configRes, sessionsRes] = await Promise.all([
        fetch(`${baseUrl}/api/public/widget-config`),
        fetch(`${baseUrl}/api/public/upcoming-sessions?limit=${limit}&lang=${lang}${activityTypeId ? `&activity_type_id=${activityTypeId}` : ''}`)
      ]);

      const config = configRes.ok ? await configRes.json() : {};
      const sessionsData = sessionsRes.ok ? await sessionsRes.json() : { sessions: [] };

      renderWidget(shadow, config, sessionsData.sessions || [], lang, theme, config.booking_app_url || baseUrl);
    } catch (e) {
      renderError(shadow, lang);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
