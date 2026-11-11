(function () {
  "use strict";

  window.makeSearchable = function (sel, opts) {
    if (!sel || sel._ss) return;
    sel._ss = true;
    opts = opts || {};

    var wrap = document.createElement("div");
    wrap.className = "ss-wrap";
    ["flex", "maxWidth", "minWidth"].forEach(function (p) {
      if (sel.style[p]) wrap.style[p] = sel.style[p];
    });
    if (sel.style.flex) wrap.style.flex = sel.style.flex;

    sel.parentNode.insertBefore(wrap, sel);
    wrap.appendChild(sel);
    sel.style.cssText = "position:absolute;opacity:0;pointer-events:none;height:0;width:0;";

    var input = document.createElement("input");
    input.type = "text";
    input.className = "search-input ss-input";
    input.placeholder = opts.placeholder || sel.options[0]?.text || "Search…";
    input.autocomplete = "off";
    wrap.appendChild(input);

    var dd = document.createElement("div");
    dd.className = "ss-dd";
    wrap.appendChild(dd);

    var hl = -1;

    function render(filter) {
      dd.innerHTML = "";
      var f = (filter || "").toLowerCase();
      hl = -1;
      var n = 0;

      for (var i = 0; i < sel.options.length; i++) {
        var o = sel.options[i];
        if (!o.value && i === 0) continue;
        var txt = o.text;
        if (f && txt.toLowerCase().indexOf(f) === -1) continue;

        var el = document.createElement("div");
        el.className = "ss-item" + (i === sel.selectedIndex ? " ss-cur" : "");
        el.textContent = txt;
        el.dataset.i = i;
        el.onmousedown = (function (idx) {
          return function (e) {
            e.preventDefault();
            pick(idx);
          };
        })(i);
        dd.appendChild(el);
        n++;
      }

      if (!n) {
        var empty = document.createElement("div");
        empty.className = "ss-empty";
        empty.textContent = "No matches";
        dd.appendChild(empty);
      }
    }

    function pick(i) {
      sel.selectedIndex = i;
      input.value = sel.options[i].text;
      sel.dispatchEvent(new Event("change", { bubbles: true }));
      shut();
    }

    function show() {
      render(input.value);
      dd.classList.add("ss-open");
    }

    function shut() {
      dd.classList.remove("ss-open");
      hl = -1;
    }

    function setHl(idx) {
      var items = dd.querySelectorAll(".ss-item");
      items.forEach(function (el) {
        el.classList.remove("ss-hl");
      });
      if (idx >= 0 && idx < items.length) {
        items[idx].classList.add("ss-hl");
        items[idx].scrollIntoView({ block: "nearest" });
        hl = idx;
      }
    }

    if (sel.selectedIndex > 0) {
      input.value = sel.options[sel.selectedIndex].text;
    }

    input.addEventListener("focus", function () {
      this.select();
      show();
    });
    input.addEventListener("input", function () {
      render(this.value);
      dd.classList.add("ss-open");
    });
    input.addEventListener("blur", function () {
      setTimeout(shut, 180);
    });
    input.addEventListener("keydown", function (e) {
      var items = dd.querySelectorAll(".ss-item");
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setHl(Math.min(hl + 1, items.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setHl(Math.max(hl - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (hl >= 0 && items[hl]) pick(parseInt(items[hl].dataset.i));
      } else if (e.key === "Escape") {
        shut();
        input.blur();
      }
    });

    return wrap;
  };

  window.enhanceSearchable = function (root) {
    (root || document)
      .querySelectorAll("select.searchable")
      .forEach(function (s) {
        makeSearchable(s);
      });
  };
})();
