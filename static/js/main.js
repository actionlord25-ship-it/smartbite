/* SmartBite front-end. CSP-safe: no inline handlers; page data arrives via data-* attributes and JSON script tags. */
(function () {
  'use strict';
  var THEME_KEY = 'sb_theme', SIDEBAR_KEY = 'sb_sidebar';
  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } }
  function applyTheme(t) { document.documentElement.setAttribute('data-theme', t === 'dark' ? 'dark' : 'light'); }
  applyTheme(store(THEME_KEY) || 'light');

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  function csrf() { var m = $('meta[name="csrf-token"]'); return m ? m.content : ''; }
  function post(url, data) {
    var body = data instanceof FormData ? data : new URLSearchParams(data || {});
    return fetch(url, { method: 'POST', body: body, credentials: 'same-origin', headers: { 'X-CSRFToken': csrf(), 'X-Requested-With': 'fetch' } })
      .then(function (r) { return r.json().catch(function () { return { ok: false, message: 'Unexpected response from the server.' }; }).then(function (j) { j._status = r.status; return j; }); })
      .catch(function () { return { ok: false, message: 'Network problem. Check your connection and try again.' }; });
  }

  /* Toasts --------------------------------------------------------------------------- */
  var TOAST_ICONS = {
    success: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M8 12.5l3 3 5-6"/></svg>',
    error: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18v.5"/></svg>',
    info: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/></svg>'
  };
  function toast(message, type) {
    type = TOAST_ICONS[type] ? type : 'info';
    var box = $('#toasts');
    if (!box) { box = document.createElement('div'); box.id = 'toasts'; box.setAttribute('aria-live', 'polite'); document.body.appendChild(box); }
    var el = document.createElement('div');
    el.className = 'toast ' + type; el.setAttribute('role', type === 'error' ? 'alert' : 'status');
    el.innerHTML = TOAST_ICONS[type] + '<span></span>';
    el.lastChild.textContent = message;
    box.appendChild(el);
    setTimeout(function () { el.classList.add('out'); setTimeout(function () { el.remove(); }, 260); }, 3000);
  }
  window.SB = { toast: toast, post: post };

  /* Confirm dialog ------------------------------------------------------------------- */
  function confirmBox(message, onYes) {
    var wrap = document.createElement('div');
    wrap.className = 'modal open';
    wrap.innerHTML = '<div class="modal-box" role="alertdialog" aria-modal="true"><h3>Are you sure?</h3><p class="muted"></p><div class="modal-actions"><button type="button" class="btn btn-ghost" data-no>Cancel</button><button type="button" class="btn btn-primary" data-yes>Yes, continue</button></div></div>';
    $('p', wrap).textContent = message;
    document.body.appendChild(wrap);
    function close() { wrap.remove(); }
    $('[data-no]', wrap).addEventListener('click', close);
    $('[data-yes]', wrap).addEventListener('click', function () { close(); onYes(); });
    wrap.addEventListener('click', function (e) { if (e.target === wrap) close(); });
    $('[data-yes]', wrap).focus();
  }
  function submitWith(form, btn) {
    if (form.requestSubmit) { form.requestSubmit(btn || undefined); return; }
    if (btn && btn.name) { var h = document.createElement('input'); h.type = 'hidden'; h.name = btn.name; h.value = btn.value; form.appendChild(h); }
    form.submit();
  }
  document.addEventListener('click', function (e) {
    var el = e.target.closest('[data-confirm]');
    if (!el || el.tagName === 'FORM') return;
    if (el.dataset.confirmed === '1') { el.dataset.confirmed = ''; return; }
    e.preventDefault();
    confirmBox(el.dataset.confirm, function () {
      if (el.form) { el.dataset.confirmed = '1'; submitWith(el.form, el); }
      else if (el.href) { window.location.href = el.href; }
    });
  });
  document.addEventListener('submit', function (e) {
    var f = e.target;
    if (f.dataset && f.dataset.confirm && !f.dataset.ok) {
      e.preventDefault();
      confirmBox(f.dataset.confirm, function () { f.dataset.ok = '1'; f.submit(); });
    }
  });

  /* Generic modals ------------------------------------------------------------------- */
  document.addEventListener('click', function (e) {
    var open = e.target.closest('[data-modal-open]');
    if (open) { var m = document.getElementById(open.dataset.modalOpen); if (m) m.classList.add('open'); return; }
    var close = e.target.closest('[data-modal-close]');
    if (close) { var mm = close.closest('.modal'); if (mm) mm.classList.remove('open'); return; }
    if (e.target.classList && e.target.classList.contains('modal') && e.target.id) e.target.classList.remove('open');
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') $$('.modal.open').forEach(function (m) { m.classList.remove('open'); }); });

  /* Ready ---------------------------------------------------------------------------- */
  document.addEventListener('DOMContentLoaded', function () {
    // Flash messages -> toasts
    var flash = $('#flash-data');
    if (flash) { try { JSON.parse(flash.textContent).forEach(function (m) { toast(m[1], m[0] === 'success' || m[0] === 'error' ? m[0] : 'info'); }); } catch (e) { } }

    // Sidebar
    if (window.innerWidth > 980 && store(SIDEBAR_KEY) === 'collapsed') document.body.classList.add('sidebar-collapsed');
    $$('[data-sidebar-toggle]').forEach(function (b) {
      b.addEventListener('click', function () {
        if (window.innerWidth <= 980) document.body.classList.toggle('sidebar-open');
        else { document.body.classList.toggle('sidebar-collapsed'); store(SIDEBAR_KEY, document.body.classList.contains('sidebar-collapsed') ? 'collapsed' : 'open'); }
      });
    });
    $$('[data-sidebar-close]').forEach(function (b) { b.addEventListener('click', function () { document.body.classList.remove('sidebar-open'); }); });

    // Public nav
    $$('[data-nav-toggle]').forEach(function (b) {
      b.addEventListener('click', function () { var l = $('.nav-links'); if (l) l.classList.toggle('open'); });
    });
    $$('.nav-links a').forEach(function (a) { a.addEventListener('click', function () { var l = $('.nav-links'); if (l) l.classList.remove('open'); }); });

    // Theme
    function markTheme() { var t = document.documentElement.getAttribute('data-theme'); $$('[data-theme-set]').forEach(function (b) { b.classList.toggle('active', b.dataset.themeSet === t); b.setAttribute('aria-pressed', b.dataset.themeSet === t); }); }
    $$('[data-theme-set]').forEach(function (b) { b.addEventListener('click', function () { store(THEME_KEY, b.dataset.themeSet); applyTheme(b.dataset.themeSet); markTheme(); toast('Theme set to ' + b.dataset.themeSet + ' mode.', 'info'); if (window.SBCharts) window.SBCharts(); }); });
    markTheme();

    // Tabs (client side)
    $$('[data-tabs]').forEach(function (group) {
      var tabs = $$('[data-tab]', group);
      function show(id) { tabs.forEach(function (t) { var on = t.dataset.tab === id; t.classList.toggle('active', on); t.setAttribute('aria-selected', on); }); $$('.tab-panel[data-panel]').forEach(function (p) { if (group.dataset.tabs && p.dataset.group !== group.dataset.tabs) return; p.hidden = p.dataset.panel !== id; }); }
      tabs.forEach(function (t) { t.addEventListener('click', function () { show(t.dataset.tab); }); });
    });

    // Password visibility
    $$('[data-toggle-password]').forEach(function (b) {
      b.addEventListener('click', function () { var i = $('input', b.closest('.pw-wrap')); var show = i.type === 'password'; i.type = show ? 'text' : 'password'; b.textContent = show ? 'Hide' : 'Show'; });
    });

    // Image preview
    $$('input[type=file][data-preview]').forEach(function (inp) {
      inp.addEventListener('change', function () {
        var target = document.getElementById(inp.dataset.preview), f = inp.files && inp.files[0];
        if (!f) return;
        if (f.size > 5 * 1024 * 1024) { toast('That image is larger than 5 MB.', 'error'); inp.value = ''; return; }
        if (!/^image\/(jpeg|png)$/.test(f.type)) { toast('Please choose a JPG or PNG image.', 'error'); inp.value = ''; return; }
        if (target) target.src = URL.createObjectURL(f);
      });
    });

    // Signup role toggle
    $$('select[data-role-toggle]').forEach(function (sel) {
      function sync() { $$('[data-role-show]').forEach(function (el) { var on = el.dataset.roleShow === sel.value; el.classList.toggle('hide', !on); $$('input', el).forEach(function (i) { i.required = on; }); }); }
      sel.addEventListener('change', sync); sync();
    });

    // Geolocation helper
    $$('[data-geo]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (!navigator.geolocation) { toast('Your browser does not support location.', 'error'); return; }
        btn.disabled = true;
        navigator.geolocation.getCurrentPosition(function (pos) {
          var f = btn.closest('form'); $('[name=lat]', f).value = pos.coords.latitude.toFixed(6); $('[name=lng]', f).value = pos.coords.longitude.toFixed(6);
          var s = $('[data-geo-status]', f); if (s) s.textContent = 'Location saved (' + pos.coords.latitude.toFixed(4) + ', ' + pos.coords.longitude.toFixed(4) + ')';
          toast('Location captured.', 'success'); btn.disabled = false;
        }, function () { toast('We could not get your location. Allow location access and try again.', 'error'); btn.disabled = false; }, { enableHighAccuracy: true, timeout: 12000 });
      });
    });

    // Copy to clipboard
    $$('[data-copy]').forEach(function (b) {
      b.addEventListener('click', function () { if (navigator.clipboard) navigator.clipboard.writeText(b.dataset.copy).then(function () { toast('Copied to clipboard.', 'success'); }); });
    });

    // Quantity steppers
    $$('[data-qty-step]').forEach(function (b) {
      b.addEventListener('click', function () { var i = $('input', b.closest('.qty')); i.value = Math.min(20, Math.max(1, (parseInt(i.value, 10) || 1) + parseInt(b.dataset.qtyStep, 10))); });
    });

    // Add to cart (AJAX)
    function setCart(n) { $$('[data-cart-count]').forEach(function (c) { c.textContent = n > 0 ? n : ''; c.dataset.zero = n > 0 ? '0' : '1'; }); }
    $$('form.js-cart-add').forEach(function (form) {
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        var btn = $('button[type=submit]', form); btn.disabled = true;
        function send(extra) {
          var fd = new FormData(form); if (extra) fd.append('replace', '1');
          post(form.action, fd).then(function (j) {
            btn.disabled = false;
            if (j.ok) { toast(j.message, 'success'); setCart(j.count); }
            else if (j.code === 'other_restaurant') confirmBox(j.message, function () { btn.disabled = true; send(true); });
            else toast(j.message || 'Could not add to cart.', 'error');
          });
        }
        send(false);
      });
    });

    // Favourites
    $$('.fav-btn[data-fav]').forEach(function (b) {
      b.addEventListener('click', function (e) {
        e.preventDefault();
        post(b.dataset.url, { kind: b.dataset.fav, id: b.dataset.id }).then(function (j) {
          if (j.ok) { b.classList.toggle('active', j.active); toast(j.message, 'success'); if (b.dataset.remove && !j.active) { var c = b.closest('.card'); if (c) c.remove(); } }
          else toast(j.message || 'Could not update favorites.', 'error');
        });
      });
    });

    // Checkout payment panel
    var bank = $('#bank-panel');
    if (bank) { $$('input[name=payment_method]').forEach(function (r) { r.addEventListener('change', function () { bank.classList.toggle('hide', r.value !== 'online' || !r.checked); }); }); }

    // Paystack
    var pb = $('#paystack-btn');
    if (pb) pb.addEventListener('click', function () {
      if (!window.PaystackPop) { toast('Paystack could not load. Pay by bank transfer instead.', 'error'); return; }
      var handler = window.PaystackPop.setup({
        key: pb.dataset.key, email: pb.dataset.email, amount: parseInt(pb.dataset.amount, 10) * 100, currency: 'NGN', ref: pb.dataset.ref,
        callback: function (resp) { post(pb.dataset.refUrl, { reference: resp.reference }).then(function (j) { toast(j.message || 'Payment received.', j.ok ? 'success' : 'error'); var f = $('#proof-form'); if (f) f.scrollIntoView({ behavior: 'smooth' }); }); },
        onClose: function () { toast('Payment window closed.', 'info'); }
      });
      handler.openIframe();
    });

    // Notification polling
    if (document.body.dataset.auth === '1' && document.body.dataset.notifUrl) {
      var lastId = null;
      var poll = function () {
        if (document.hidden) return;
        fetch(document.body.dataset.notifUrl, { credentials: 'same-origin' }).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
          if (!j) return;
          $$('[data-notif-count]').forEach(function (c) { c.textContent = j.count > 0 ? j.count : ''; c.dataset.zero = j.count > 0 ? '0' : '1'; });
          if (lastId !== null && j.latest_id > lastId) toast(j.latest_title || 'You have a new notification.', 'info');
          lastId = j.latest_id;
        }).catch(function () { });
      };
      poll(); setInterval(poll, 30000);
    }

    // Live order tracking
    var STEPS = ['placed', 'confirmed', 'preparing', 'out_for_delivery', 'delivered'];
    $$('.tracker[data-track-order]').forEach(function (ol) {
      var id = ol.dataset.trackOrder, url = ol.dataset.url;
      function paint(status) {
        var idx = STEPS.indexOf(status);
        $$('[data-step]', ol).forEach(function (li, i) { li.className = i < idx ? 'done' : (i === idx ? 'current' : ''); });
        var fill = $('.fill', ol); if (fill) fill.style.width = (idx / (STEPS.length - 1) * 90) + '%';
        $$('[data-status-label="' + id + '"]').forEach(function (b) { b.textContent = status.replace(/_/g, ' ').replace(/^./, function (c) { return c.toUpperCase(); }); });
      }
      paint(ol.dataset.status);
      if (!url || ol.dataset.status === 'delivered') return;
      setInterval(function () {
        if (document.hidden) return;
        fetch(url, { credentials: 'same-origin' }).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
          if (!j) return;
          if (j.status === 'cancelled') { window.location.reload(); return; }
          if (j.status !== ol.dataset.status) { ol.dataset.status = j.status; paint(j.status); toast('Order #' + id + ': ' + j.label, 'info'); if (j.status === 'delivered') setTimeout(function () { window.location.reload(); }, 1500); }
        }).catch(function () { });
      }, 15000);
    });

    renderCharts();
    initMap();
  });

  /* Charts --------------------------------------------------------------------------- */
  var PALETTE = ['#FF8C42', '#4CAF7D', '#2D2D2D', '#F5B301', '#3B82C4', '#D9534F', '#9B6BCC'];
  var chartRefs = [];
  function buildChart(cfg) {
    var circ = cfg.type === 'doughnut';
    var datasets = cfg.datasets.map(function (d, i) {
      var color = d.color || PALETTE[i % PALETTE.length], o = { label: d.label, data: d.data };
      if (circ) { o.backgroundColor = cfg.labels.map(function (_, j) { return PALETTE[j % PALETTE.length]; }); o.borderWidth = 0; }
      else if (cfg.type === 'line') { o.borderColor = color; o.backgroundColor = color + '33'; o.fill = true; o.tension = 0.35; o.pointRadius = 2; }
      else { o.backgroundColor = color; o.borderRadius = 6; if (cfg.overlap) o.grouped = false; }
      return o;
    });
    var moneyTick = function (v) { return '\u20a6' + Number(v).toLocaleString(); };
    var opts = { responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
      plugins: { legend: { display: datasets.length > 1 || circ, position: 'bottom' }, tooltip: { callbacks: {} } } };
    if (cfg.money) opts.plugins.tooltip.callbacks.label = function (c) { return c.dataset.label + ': ' + moneyTick(c.parsed.y !== undefined && !cfg.horizontal ? c.parsed.y : c.parsed.x); };
    if (!circ) {
      var val = { beginAtZero: true, stacked: !!cfg.stacked, ticks: cfg.money ? { callback: moneyTick } : { precision: 0 } };
      var cat = { grid: { display: false }, stacked: !!cfg.stacked };
      if (cfg.horizontal) { opts.indexAxis = 'y'; opts.scales = { x: val, y: cat }; } else { opts.scales = { x: cat, y: val }; }
    }
    return { type: cfg.type, data: { labels: cfg.labels, datasets: datasets }, options: opts };
  }
  function renderCharts() {
    if (!window.Chart) return;
    var cs = getComputedStyle(document.documentElement);
    window.Chart.defaults.color = cs.getPropertyValue('--muted').trim() || '#6B6B6B';
    window.Chart.defaults.borderColor = cs.getPropertyValue('--border').trim() || '#EDE6DD';
    window.Chart.defaults.font.family = cs.getPropertyValue('--font-b').trim() || 'sans-serif';
    chartRefs.forEach(function (c) { c.destroy(); }); chartRefs = [];
    $$('canvas[data-chart]').forEach(function (cv) {
      var node = document.getElementById('chart-' + cv.dataset.chart); if (!node) return;
      try { chartRefs.push(new window.Chart(cv, buildChart(JSON.parse(node.textContent)))); } catch (e) { }
    });
  }
  window.SBCharts = renderCharts;

  /* Rider route map (AI 5) ----------------------------------------------------------- */
  function km(a, b) {
    var R = 6371, r = Math.PI / 180, dLat = (b[0] - a[0]) * r, dLng = (b[1] - a[1]) * r;
    var x = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(a[0] * r) * Math.cos(b[0] * r) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
    return 2 * R * Math.asin(Math.sqrt(x));
  }
  function geocode(address) {
    var key = 'sb_geo_' + address, cached = store(key);
    if (cached) { try { return Promise.resolve(JSON.parse(cached)); } catch (e) { } }
    return fetch('https://nominatim.openstreetmap.org/search?format=json&limit=1&q=' + encodeURIComponent(address), { headers: { 'Accept': 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (j) { if (j && j[0]) { var p = [parseFloat(j[0].lat), parseFloat(j[0].lon)]; store(key, JSON.stringify(p)); return p; } return null; })
      .catch(function () { return null; });
  }
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function initMap() {
    var el = document.getElementById('route-map'), dataNode = document.getElementById('route-data');
    if (!el || !dataNode || !window.L) return;
    var orders = JSON.parse(dataNode.textContent), summary = $('#route-summary'), list = $('#route-stops');
    var map = window.L.map(el).setView([9.082, 8.6753], 6);
    window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap contributors' }).addTo(map);
    if (!orders.length) { summary.textContent = 'No active deliveries to route yet.'; return; }

    var stops = [];
    orders.forEach(function (o) {
      if (!o.picked) stops.push({ type: 'pickup', order: o.id, name: o.restaurant.name, address: o.restaurant.address, phone: o.restaurant.phone, pos: o.restaurant.lat != null && o.restaurant.lng != null ? [o.restaurant.lat, o.restaurant.lng] : null });
      stops.push({ type: 'drop', order: o.id, name: o.customer.name, address: o.customer.address, phone: o.customer.phone, needs: o.picked ? null : o.id, pos: o.customer.lat != null && o.customer.lng != null ? [o.customer.lat, o.customer.lng] : null });
    });
    summary.textContent = 'Locating stops...';
    var chain = Promise.resolve();
    stops.forEach(function (s) { if (!s.pos) chain = chain.then(function () { return geocode(s.address).then(function (p) { s.pos = p; return sleep(1100); }); }); });
    var me = null;
    var locate = new Promise(function (res) { if (!navigator.geolocation) return res(null); navigator.geolocation.getCurrentPosition(function (p) { res([p.coords.latitude, p.coords.longitude]); }, function () { res(null); }, { timeout: 8000 }); });
    Promise.all([chain, locate]).then(function (r) {
      me = r[1];
      var usable = stops.filter(function (s) { return s.pos; }), missing = stops.length - usable.length;
      if (!usable.length) { summary.textContent = 'We could not find these addresses on the map. Ask the customer for a nearby landmark.'; return; }
      // Nearest-neighbour ordering; a drop-off only becomes available after its pickup.
      var cur = me || usable[0].pos, done = {}, route = [];
      while (route.length < usable.length) {
        var best = null, bd = Infinity;
        usable.forEach(function (s) {
          if (route.indexOf(s) > -1) return;
          if (s.type === 'drop' && s.needs && !done[s.needs] && usable.some(function (p) { return p.type === 'pickup' && p.order === s.needs; })) return;
          var d = km(cur, s.pos); if (d < bd) { bd = d; best = s; }
        });
        if (!best) break;
        route.push(best); cur = best.pos; if (best.type === 'pickup') done[best.order] = true;
      }
      var pts = (me ? [me] : []).concat(route.map(function (s) { return s.pos; })), bounds = window.L.latLngBounds(pts);
      if (me) window.L.marker(me, { icon: window.L.divIcon({ className: '', html: '<div class="map-pin me">You</div>', iconSize: [32, 32], iconAnchor: [16, 16] }) }).addTo(map).bindPopup('Your location');
      list.innerHTML = '';
      route.forEach(function (s, i) {
        window.L.marker(s.pos, { icon: window.L.divIcon({ className: '', html: '<div class="map-pin ' + (s.type === 'drop' ? 'drop' : '') + '">' + (i + 1) + '</div>', iconSize: [32, 32], iconAnchor: [16, 16] }) })
          .addTo(map).bindPopup((s.type === 'pickup' ? 'Pick up: ' : 'Deliver to: ') + s.name + '<br>Order #' + s.order);
        var li = document.createElement('li'), n = document.createElement('span'), body = document.createElement('div');
        n.className = 'stop-n' + (s.type === 'drop' ? ' drop' : ''); n.textContent = i + 1;
        var t = document.createElement('strong'); t.textContent = (s.type === 'pickup' ? 'Pick up at ' : 'Deliver to ') + s.name + ' (order #' + s.order + ')';
        var a = document.createElement('div'); a.className = 'small muted'; a.textContent = s.address;
        body.appendChild(t); body.appendChild(a);
        if (s.phone) { var p = document.createElement('a'); p.href = 'tel:' + s.phone.replace(/[^0-9+]/g, ''); p.className = 'small orange strong'; p.textContent = s.phone; body.appendChild(p); }
        li.appendChild(n); li.appendChild(body); list.appendChild(li);
      });
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
      function straight() {
        var d = 0; for (var i = 1; i < pts.length; i++) d += km(pts[i - 1], pts[i]);
        window.L.polyline(pts, { color: '#FF8C42', weight: 5, dashArray: '8 8' }).addTo(map);
        show(d * 1.3, d * 1.3 / 25 * 60, true);
      }
      function show(distKm, mins, approx) {
        summary.innerHTML = '';
        var strong = document.createElement('strong'); strong.textContent = distKm.toFixed(1) + ' km';
        summary.appendChild(strong); summary.appendChild(document.createTextNode(' optimised route - about ' + Math.max(1, Math.round(mins)) + ' min' + (approx ? ' (estimate)' : '') + (missing ? ' - ' + missing + ' stop(s) could not be located' : '')));
      }
      if (pts.length < 2) { show(0, 0, true); return; }
      var coords = pts.map(function (p) { return p[1] + ',' + p[0]; }).join(';');
      fetch('https://router.project-osrm.org/route/v1/driving/' + coords + '?overview=full&geometries=geojson').then(function (r) { return r.json(); }).then(function (j) {
        if (!j.routes || !j.routes[0]) return straight();
        window.L.geoJSON(j.routes[0].geometry, { style: { color: '#FF8C42', weight: 5 } }).addTo(map);
        show(j.routes[0].distance / 1000, j.routes[0].duration / 60, false);
      }).catch(straight);
    });
  }
})();
