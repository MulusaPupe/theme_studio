/* MULUSA THEME STUDIO canvas script. Editor mode only: never part of a preview or export.
   It reports what the person does. It never changes the design: Python owns the document,
   and checks every request again. RULES is generated from core/structure.py. */
(function () {
  'use strict';
  var RULES = __MTS_RULES__;
  var GOLD = '#E8B04B', RED = '#E5484D', BLUE = '#5B8DEF', INK = '#17130A';
  var bridge = null, queue = [];

  function send(method, args) {
    if (bridge) bridge[method].apply(bridge, args); else queue.push([method, args]);
  }
  if (window.QWebChannel && window.qt && qt.webChannelTransport) {
    new QWebChannel(qt.webChannelTransport, function (channel) {
      bridge = channel.objects.bridge;
      queue.splice(0).forEach(function (item) { bridge[item[0]].apply(bridge, item[1]); });
      window.mtsReady = true;
      bridge.reportReady();
    });
  }

  var sheet = document.createElement('style');
  sheet.textContent =
    'html{scroll-behavior:auto!important}' +
    'body *{cursor:default}' +
    'main:empty{display:block;min-height:320px;outline:2px dashed #9aa0aa;outline-offset:-14px;position:relative}' +
    'main:empty::before{content:"Drag a section here";position:absolute;inset:0;display:grid;place-items:center;color:#7b818c;font:500 18px system-ui,sans-serif}' +
    '.mts-container:empty,.mts-columns:empty,.mts-row:empty{min-height:40px;outline:1px dashed rgba(127,127,140,.7);outline-offset:-1px}';
  document.head.appendChild(sheet);

  function layer(id, css) {
    var el = document.createElement('div');
    el.id = id;
    el.style.cssText = 'position:absolute;pointer-events:none;z-index:99999;display:none;box-sizing:border-box;' + css;
    document.documentElement.appendChild(el);
    return el;
  }
  // Editor marks stay the same size on screen at any zoom: --mts-k is the inverse of the zoom.
  var TAG = 'font:600 calc(12px*var(--mts-k,1))/1.5 system-ui,sans-serif;padding:calc(1px*var(--mts-k,1)) calc(7px*var(--mts-k,1));border-radius:calc(3px*var(--mts-k,1));white-space:nowrap;';
  var zoomK = 1;
  var hoverBox = layer('mts-hover', 'outline:calc(1px*var(--mts-k,1)) solid ' + BLUE + ';outline-offset:calc(-1px*var(--mts-k,1))');
  var parentBox = layer('mts-parent', 'outline:calc(1px*var(--mts-k,1)) dashed ' + GOLD + ';outline-offset:calc(-1px*var(--mts-k,1));opacity:.75');
  var selBox = layer('mts-selection', 'outline:calc(2px*var(--mts-k,1)) solid ' + GOLD + ';outline-offset:calc(-2px*var(--mts-k,1));background:rgba(232,176,75,.09)');
  var selTag = layer('mts-selection-tag', TAG + 'background:' + GOLD + ';color:' + INK);
  var line = layer('mts-drop-line', 'background:' + GOLD + ';box-shadow:0 0 0 calc(1px*var(--mts-k,1)) #fff,0 0 0 calc(2px*var(--mts-k,1)) rgba(23,19,10,.75);border-radius:2px');
  var dropBox = layer('mts-drop-parent', 'outline:calc(2px*var(--mts-k,1)) dashed ' + GOLD + ';outline-offset:calc(-2px*var(--mts-k,1));background:rgba(232,176,75,.07)');
  var dropTag = layer('mts-drop-tag', TAG + 'background:' + GOLD + ';color:' + INK);
  var ghost = layer('mts-drag-ghost', TAG + 'position:fixed;background:' + INK + ';color:#fff;opacity:.92;box-shadow:0 4px 14px rgba(0,0,0,.35)');

  function place(box, el) {
    var r = el.getBoundingClientRect();
    box.style.left = (r.left + scrollX) + 'px';
    box.style.top = (r.top + scrollY) + 'px';
    box.style.width = r.width + 'px';
    box.style.height = r.height + 'px';
    box.style.display = 'block';
  }
  function hide() { for (var i = 0; i < arguments.length; i++) arguments[i].style.display = 'none'; }
  function nodeOf(el) { return el && el.closest ? el.closest('[data-mts-id]') : null; }
  function idOf(el) { return el.getAttribute('data-mts-id'); }
  function typeOf(el) { return el.getAttribute('data-mts-type'); }
  function find(id) { return id ? document.querySelector('[data-mts-id="' + CSS.escape(id) + '"]') : null; }
  function kids(el) {
    return Array.prototype.filter.call(el.children, function (c) { return c.hasAttribute('data-mts-id'); });
  }
  function allows(parentType, childType) {
    var list = parentType === null ? RULES.root : RULES.children[parentType];
    return !!list && list.indexOf(childType) >= 0;
  }

  // Selection --------------------------------------------------------------
  var current = null, currentId = '', currentLabel = '', editable = false;
  var chip = layer('mts-replace-chip', TAG + 'background:' + INK + ';color:#fff;box-shadow:0 2px 10px rgba(0,0,0,.35)');
  chip.textContent = 'Click to choose an image';
  function isPlaceholder(el) { return !!el && el.isConnected && el.hasAttribute('data-mts-placeholder'); }
  function showChip(el) {
    // Over a placeholder, or on the selected one, so the way to replace it is always in view.
    if (!isPlaceholder(el)) el = current;
    if (!editable || !isPlaceholder(el)) { hide(chip); return; }
    var r = el.getBoundingClientRect();
    chip.style.display = 'block';
    chip.style.left = (r.left + scrollX + r.width / 2 - chip.offsetWidth / 2) + 'px';
    chip.style.top = (r.top + scrollY + r.height / 2 - chip.offsetHeight / 2) + 'px';
  }

  function draw() {
    if (!current || !current.isConnected) { hide(selBox, selTag, parentBox, chip); return; }
    showChip(null);
    place(selBox, current);
    var r = current.getBoundingClientRect();
    selTag.textContent = currentLabel;
    selTag.style.display = 'block';
    selTag.style.left = (r.left + scrollX) + 'px';
    var top = r.top + scrollY - 21 * zoomK;
    selTag.style.top = (top < scrollY ? r.top + scrollY + 3 : top) + 'px';
    var parent = nodeOf(current.parentElement);
    if (parent) place(parentBox, parent); else hide(parentBox);
  }
  window.mtsSelect = function (id, mode, label) {
    current = find(id);
    currentId = current ? id : '';
    currentLabel = label || (current ? typeOf(current) : '');
    if (current && (mode === true || mode === 'center')) current.scrollIntoView({ block: 'center', behavior: 'instant' });
    if (current && mode === 'nearest') current.scrollIntoView({ block: 'nearest', behavior: 'instant' });
    hide(hoverBox);
    draw();
    return !!current;
  };
  window.mtsEditable = function (value) { editable = !!value; };
  // Live updates: only what differs is replaced, so an edit does not disturb the rest of the page.
  function same(a, b) {
    if (a.attributes.length !== b.attributes.length) return false;
    for (var i = 0; i < a.attributes.length; i++) {
      if (b.getAttribute(a.attributes[i].name) !== a.attributes[i].value) return false;
    }
    return true;
  }
  function patch(parent, fresh) {
    var old = Array.prototype.filter.call(parent.children, function (c) { return c.tagName !== 'SCRIPT'; });
    var next = Array.prototype.slice.call(fresh.children);
    if (old.length !== next.length) {
      old.forEach(function (c) { parent.removeChild(c); });
      var anchor = parent.querySelector(':scope > script');
      next.forEach(function (c) { parent.insertBefore(c, anchor); });
      return;
    }
    old.forEach(function (a, i) {
      var b = next[i];
      if (a.isEqualNode(b)) return;
      if (a.tagName === b.tagName && same(a, b) && a.children.length && a.children.length === b.children.length && a.childNodes.length === b.childNodes.length) patch(a, b);
      else parent.replaceChild(b, a);
    });
  }
  window.mtsPatch = function (body, cssHref, bodyClass) {
    var holder = document.createElement('template');
    holder.innerHTML = body;
    patch(document.body, holder.content);
    document.body.className = bodyClass;
    var links = document.querySelectorAll('link[rel=stylesheet]');
    if (links[links.length - 1].getAttribute('href') !== cssHref) {
      var fresh = document.createElement('link');
      fresh.rel = 'stylesheet';
      fresh.href = cssHref;
      fresh.onload = function () {
        // Older sheets go only once the new one is in, so nothing flashes unstyled.
        var all = document.querySelectorAll('link[rel=stylesheet]');
        for (var i = 0; i < all.length - 1; i++) { if (all[i] !== fresh) all[i].remove(); }
        draw();
      };
      document.head.appendChild(fresh);
    }
    current = find(currentId);
    draw();
    return true;
  };
  window.mtsZoom = function (zoom) {
    zoomK = 1 / (zoom || 1);
    document.documentElement.style.setProperty('--mts-k', String(zoomK));
    draw();
  };
  addEventListener('resize', draw);
  addEventListener('load', draw);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(draw);
  if (window.ResizeObserver) new ResizeObserver(draw).observe(document.documentElement);

  // Working out where a drop would land -------------------------------------
  function isRowLike(el) {
    var s = getComputedStyle(el);
    if (s.display.indexOf('grid') >= 0) return s.gridTemplateColumns.split(' ').length > 1;
    return s.display.indexOf('flex') >= 0 && s.flexDirection.indexOf('row') === 0;
  }
  function indexAt(parent, x, y, horizontal, skip) {
    var list = kids(parent);
    for (var i = 0; i < list.length; i++) {
      if (list[i] === skip) continue;
      var r = list[i].getBoundingClientRect();
      if (y < r.top) return i;
      if (y <= r.bottom && (horizontal ? x < r.left + r.width / 2 : y < r.top + r.height / 2)) return i;
    }
    return list.length;
  }
  function distance(el, x, y) {
    var r = el.getBoundingClientRect();
    var dx = Math.max(r.left - x, 0, x - r.right), dy = Math.max(r.top - y, 0, y - r.bottom);
    return dx * dx + dy * dy;
  }
  // Inside something that cannot hold the element, look for the nearest thing within that can:
  // a heading dropped on a section's padding belongs in that section's container.
  function descend(el, type, skip, x, y, depth) {
    if (depth > 6) return null;
    var list = kids(el).filter(function (k) { return k !== skip; })
      .sort(function (a, b) { return distance(a, x, y) - distance(b, x, y); });
    for (var i = 0; i < list.length; i++) {
      if (allows(typeOf(list[i]), type)) return list[i];
      var inner = descend(list[i], type, skip, x, y, depth + 1);
      if (inner) return inner;
    }
    return null;
  }
  function targetAt(x, y, type, skip) {
    var main = document.querySelector('main');
    var el = nodeOf(document.elementFromPoint(x, y));
    if (el && skip && (el === skip || skip.contains(el))) el = nodeOf(skip.parentElement);
    var start = el;
    while (el) {
      if (allows(typeOf(el), type)) return result(el, idOf(el));
      if (el === start) {
        var inner = descend(el, type, skip, x, y, 0);
        if (inner) return result(inner, idOf(inner));
      }
      el = nodeOf(el.parentElement);
    }
    if (allows(null, type) && main) return result(main, 'root');
    return { ok: false };

    function result(parent, ref) {
      var horizontal = isRowLike(parent);
      return { ok: true, parent: parent, ref: ref, horizontal: horizontal, index: indexAt(parent, x, y, horizontal, skip) };
    }
  }
  function drawTarget(t, label) {
    if (!t.ok) { hide(line, dropBox, dropTag); return; }
    var list = kids(t.parent), parentRect = t.parent.getBoundingClientRect();
    place(dropBox, t.parent);
    hide(line);
    if (list.length) {
      var after = t.index >= list.length, near = list[after ? list.length - 1 : t.index].getBoundingClientRect();
      if (t.horizontal) {
        line.style.left = ((after ? near.right : near.left) + scrollX - 2 * zoomK) + 'px';
        line.style.top = (near.top + scrollY) + 'px';
        line.style.width = (4 * zoomK) + 'px';
        line.style.height = near.height + 'px';
      } else {
        line.style.left = (near.left + scrollX) + 'px';
        line.style.top = ((after ? near.bottom : near.top) + scrollY - 2 * zoomK) + 'px';
        line.style.width = near.width + 'px';
        line.style.height = (4 * zoomK) + 'px';
      }
      line.style.display = 'block';
    }
    dropTag.textContent = label;
    dropTag.style.background = GOLD;
    dropTag.style.color = INK;
    dropTag.style.left = (Math.max(parentRect.left, 0) + scrollX + 4) + 'px';
    dropTag.style.top = (Math.max(parentRect.top, 0) + scrollY + 4) + 'px';
    dropTag.style.display = 'block';
  }
  function drawInvalid(x, y, label) {
    hide(line, dropBox);
    var el = nodeOf(document.elementFromPoint(x, y));
    if (el) {
      place(dropBox, el);
      dropBox.style.outlineColor = RED;
      dropBox.style.background = 'rgba(229,72,77,.08)';
    }
    dropTag.textContent = label + ' cannot go here';
    dropTag.style.background = RED;
    dropTag.style.color = '#fff';
    dropTag.style.left = (x + scrollX + 14) + 'px';
    dropTag.style.top = (y + scrollY + 14) + 'px';
    dropTag.style.display = 'block';
  }

  // One drag at a time, whether from the library or of an existing element --
  var drag = null, scroller = null, lastY = 0;

  function beginDrag(spec) {
    drag = spec;
    hide(hoverBox);
    scroller = setInterval(function () {
      if (!drag) return;
      if (lastY < 56) scrollBy(0, -18); else if (lastY > innerHeight - 56) scrollBy(0, 18);
    }, 30);
  }
  function over(x, y) {
    lastY = y;
    drag.target = targetAt(x, y, drag.type, drag.el || null);
    dropBox.style.outlineColor = GOLD;
    dropBox.style.background = 'rgba(232,176,75,.07)';
    if (drag.target.ok) drawTarget(drag.target, drag.label); else drawInvalid(x, y, drag.label);
    return !!drag.target.ok;
  }
  function endDrag() {
    drag = null;
    clearInterval(scroller);
    hide(line, dropBox, dropTag, ghost);
    document.documentElement.style.cursor = '';
  }
  // Called by Python while a library component is dragged over the canvas.
  window.mtsDragBegin = function (type, label, preset) { beginDrag({ kind: 'new', type: type, label: label, preset: preset }); };
  window.mtsDragOver = function (x, y) { return drag ? over(x, y) : false; };
  window.mtsDragDrop = function (x, y) {
    if (!drag) return false;
    var ok = over(x, y);
    if (ok) send('requestInsert', [drag.preset, drag.target.ref, drag.target.index]);
    else send('reportRefused', [drag.label + ' cannot go there.']);
    endDrag();
    return ok;
  };
  window.mtsDragEnd = function () { if (drag) endDrag(); };
  window.mtsScrollTo = function (y) { scrollTo({ top: y, behavior: 'instant' }); };

  // Mouse ------------------------------------------------------------------
  var pressed = null;

  function block(event) { event.preventDefault(); event.stopPropagation(); }
  addEventListener('mousedown', function (event) {
    block(event);
    if (event.button !== 0) return;
    pressed = { x: event.clientX, y: event.clientY, el: nodeOf(event.target) };
  }, true);
  addEventListener('mousemove', function (event) {
    var x = event.clientX, y = event.clientY;
    if (drag && drag.kind === 'move') {
      over(x, y);
      ghost.style.left = (x + 12) + 'px';
      ghost.style.top = (y + 12) + 'px';
      ghost.style.display = 'block';
      return;
    }
    if (pressed && editable && pressed.el && Math.abs(x - pressed.x) + Math.abs(y - pressed.y) > 6) {
      // Dragging inside the selected element moves it, which is how a whole section is moved.
      var mover = current && current.contains(pressed.el) ? current : pressed.el;
      var type = typeOf(mover);
      if (type !== 'header' && type !== 'footer') {
        var name = mover === current ? currentLabel : type.replace('_', ' ');
        hide(chip);
        beginDrag({ kind: 'move', type: type, label: name, el: mover });
        ghost.textContent = 'Moving ' + name;
        document.documentElement.style.cursor = 'grabbing';
        return;
      }
    }
    if (drag || pressed) return;
    var el = nodeOf(event.target);
    if (el && el !== current) place(hoverBox, el); else hide(hoverBox);
    showChip(el);
  }, true);
  addEventListener('mouseup', function (event) {
    block(event);
    if (event.button !== 0) return;
    var was = pressed;
    pressed = null;
    if (drag && drag.kind === 'move') {
      var ok = over(event.clientX, event.clientY), spec = drag;
      if (ok) send('requestMove', [idOf(spec.el), spec.target.ref, spec.target.index]);
      else send('reportRefused', [spec.label + ' cannot go there.']);
      endDrag();
      return;
    }
    if (!was) return;
    var el = nodeOf(event.target);
    if (el) {
      send('selectNode', [idOf(el)]);
      if (editable && el.hasAttribute('data-mts-placeholder')) send('requestMediaPicker', [idOf(el)]);
    } else send('clearSelection', []);
  }, true);
  document.documentElement.addEventListener('mouseleave', function () { hide(hoverBox); showChip(null); });

  // The website must not react while it is being edited.
  ['click', 'dblclick', 'auxclick', 'contextmenu', 'submit', 'dragstart', 'selectstart'].forEach(function (name) {
    addEventListener(name, block, true);
  });
  addEventListener('focusin', function (event) { if (event.target.blur) event.target.blur(); }, true);
})();
