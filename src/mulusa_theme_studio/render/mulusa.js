/* Mulusa Theme Studio: the studio's own page behaviour. Written by the studio, never by a site's content.
   Countdowns: every element with data-mts-countdown="<ISO date>" shows the time left, once a second. */
(function () {
  "use strict";
  function pad(n) { return n < 10 ? "0" + n : String(n); }
  function tick() {
    var all = document.querySelectorAll("[data-mts-countdown]");
    for (var i = 0; i < all.length; i++) {
      var el = all[i], target = Date.parse(el.getAttribute("data-mts-countdown") || "");
      if (isNaN(target)) continue;
      var left = Math.max(0, Math.floor((target - Date.now()) / 1000));
      var values = { days: Math.floor(left / 86400), hours: pad(Math.floor(left / 3600) % 24), minutes: pad(Math.floor(left / 60) % 60), seconds: pad(left % 60) };
      var cells = el.querySelectorAll("[data-u]");
      for (var j = 0; j < cells.length; j++) {
        var v = String(values[cells[j].getAttribute("data-u")]);
        if (cells[j].textContent !== v) cells[j].textContent = v;
      }
      if (left === 0 && !el.hasAttribute("data-mts-done")) {
        el.setAttribute("data-mts-done", "");
        var when = el.querySelector(".mts-cd-when");
        if (when) when.textContent = el.getAttribute("data-done") || "";
      }
    }
  }
  tick();
  setInterval(tick, 1000);
})();
