let calendarInstance = null;

function initCalendar(currentFilters) {
  if (calendarInstance) {
    calendarInstance.destroy();
    calendarInstance = null;
  }
  const el = document.getElementById('calendar-container');
  if (!el) return;

  calendarInstance = new FullCalendar.Calendar(el, {
    initialView: 'dayGridMonth',
    locale: currentLang,
    direction: currentDir,
    height: 'auto',
    headerToolbar: {
      left: 'prev,next today',
      center: 'title',
      right: 'dayGridMonth,timeGridWeek'
    },
    events: async function(info, successCb, failureCb) {
      try {
        const params = new URLSearchParams({
          date_from: info.startStr,
          date_to: info.endStr,
          status_filter: 'upcoming',
          ...(currentFilters || {})
        });
        const token = localStorage.getItem('token');
        const res = await fetch(`/api/sessions?${params}`, {
          headers: token ? { 'Authorization': `Bearer ${token}` } : {}
        });
        const sessions = await res.json();
        const events = sessions.map(s => {
          const count = s.booking_count || 0;
          const max = s.max_participants || 1;
          const ratio = count / max;
          let color = '#22c55e';
          if (s.is_cancelled) color = '#6b7280';
          else if (ratio >= 1) color = '#ef4444';
          else if (ratio >= 0.7) color = '#f59e0b';
          return {
            id: s.id,
            title: s.title,
            start: s.session_date,
            backgroundColor: color,
            borderColor: color,
            textColor: '#fff',
            extendedProps: { session: s }
          };
        });
        successCb(events);
      } catch(e) {
        failureCb(e);
      }
    },
    eventClick: function(info) {
      if (window.openSessionModal) {
        window.openSessionModal(info.event.extendedProps.session);
      }
    },
    eventContent: function(arg) {
      const s = arg.event.extendedProps.session;
      const cancelled = s && s.is_cancelled;
      return {
        html: `<div style="padding:2px 4px;font-size:0.75rem;${cancelled ? 'text-decoration:line-through;opacity:0.6' : ''}">${arg.event.title}</div>`
      };
    }
  });
  calendarInstance.render();
}

function destroyCalendar() {
  if (calendarInstance) {
    calendarInstance.destroy();
    calendarInstance = null;
  }
}

window.onLangChange = function() {
  if (calendarInstance) {
    const filters = window.getCurrentFilters ? window.getCurrentFilters() : {};
    initCalendar(filters);
  }
};
