// OnboardEase HR — theme, collapsible sidebar, resizeable tables, confirm, chart hover.
(function () {
  'use strict';

  // ── Theme switcher (dark / light) ──────────────────────────────────────
  function setTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    try { localStorage.setItem('oeh-theme', t); } catch (e) {}
    const btn = document.getElementById('theme-toggle');
    if (btn) btn.setAttribute('aria-label', t === 'dark' ? 'Switch to light' : 'Switch to dark');
  }
  window.toggleTheme = function () {
    setTheme(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
  };

  // ── Collapsible sidebar ────────────────────────────────────────────────
  window.toggleSidebar = function () {
    const c = document.documentElement.classList.toggle('sidebar-collapsed');
    try { localStorage.setItem('oeh-sidebar', c ? '1' : '0'); } catch (e) {}
  };

  // ── Resizeable table columns (persisted) ───────────────────────────────
  function initResizableTables() {
    document.querySelectorAll('table.data-table[data-key]').forEach(function (table) {
      const key = 'oeh-cols-' + table.dataset.key;
      const ths = Array.from(table.tHead.rows[0].cells);
      let saved = null;
      try { saved = JSON.parse(localStorage.getItem(key) || 'null'); } catch (e) {}

      let cg = table.querySelector('colgroup');
      if (!cg) {
        cg = document.createElement('colgroup');
        ths.forEach(function (th, i) {
          const col = document.createElement('col');
          col.style.width = (saved && saved[i]) ? saved[i] + 'px' : (th.offsetWidth || 140) + 'px';
          cg.appendChild(col);
        });
        table.insertBefore(cg, table.tHead);
      }
      const cols = Array.from(cg.children);

      ths.forEach(function (th, i) {
        if (i === ths.length - 1) return;
        const handle = document.createElement('span');
        handle.className = 'col-resizer';
        th.appendChild(handle);
        handle.addEventListener('pointerdown', function (e) {
          e.preventDefault();
          const startX = e.clientX, startW = cols[i].offsetWidth;
          document.body.style.cursor = 'col-resize';
          function move(ev) { cols[i].style.width = Math.max(64, startW + ev.clientX - startX) + 'px'; }
          function up() {
            document.removeEventListener('pointermove', move);
            document.removeEventListener('pointerup', up);
            document.body.style.cursor = '';
            try { localStorage.setItem(key, JSON.stringify(cols.map(c => c.offsetWidth))); } catch (e) {}
          }
          document.addEventListener('pointermove', move);
          document.addEventListener('pointerup', up);
        });
      });
    });
  }

  // ── Confirm modal (for [data-confirm] forms/links) ─────────────────────
  function initConfirm() {
    document.querySelectorAll('[data-confirm]').forEach(function (el) {
      el.addEventListener('submit', guard, true);
      if (el.tagName === 'A') el.addEventListener('click', guard, true);
    });
    function guard(e) {
      const el = e.currentTarget;
      if (el.dataset.confirmed) return;
      e.preventDefault();
      showConfirm(el.dataset.confirm || 'Are you sure?', function () {
        el.dataset.confirmed = '1';
        if (el.tagName === 'FORM') el.submit();
        else window.location = el.href;
      });
    }
  }
  function showConfirm(message, onYes) {
    // Build DOM with textContent so dynamic values can never inject markup.
    const ov = document.createElement('div');
    ov.className = 'confirm-overlay';
    const box = document.createElement('div');
    box.className = 'confirm-box';
    const p = document.createElement('p');
    p.textContent = message;
    const actions = document.createElement('div');
    actions.className = 'confirm-actions';
    const no = document.createElement('button');
    no.className = 'btn btn-ghost';
    no.textContent = 'Cancel';
    const yes = document.createElement('button');
    yes.className = 'btn btn-danger';
    yes.textContent = 'Confirm';
    actions.append(no, yes);
    box.append(p, actions);
    ov.append(box);
    document.body.appendChild(ov);
    no.onclick = () => ov.remove();
    ov.addEventListener('mousedown', (e) => { if (e.target === ov) ov.remove(); });
    yes.onclick = () => { ov.remove(); onYes(); };
  }

  // ── Chart hover tooltips (bars with data-label/data-value) ─────────────
  function initChartHover() {
    let tip;
    document.querySelectorAll('[data-chart]').forEach(function (chart) {
      chart.querySelectorAll('[data-value]').forEach(function (seg) {
        seg.addEventListener('mouseenter', function () {
          tip = document.createElement('div');
          tip.className = 'chart-tip';
          const strong = document.createElement('strong');
          strong.textContent = seg.dataset.label;
          tip.append(strong, document.createTextNode(seg.dataset.value));
          document.body.appendChild(tip);
        });
        seg.addEventListener('mousemove', function (e) {
          if (tip) { tip.style.left = e.clientX + 12 + 'px'; tip.style.top = e.clientY - 10 + 'px'; }
        });
        seg.addEventListener('mouseleave', function () { if (tip) { tip.remove(); tip = null; } });
      });
    });
  }

  // ── Flash auto-dismiss ─────────────────────────────────────────────────
  function initFlash() {
    document.querySelectorAll('.flash').forEach(function (f) {
      setTimeout(() => { f.style.transition = 'opacity .4s'; f.style.opacity = '0'; setTimeout(() => f.remove(), 400); }, 4500);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    initResizableTables();
    initConfirm();
    initChartHover();
    initFlash();
  });
})();
