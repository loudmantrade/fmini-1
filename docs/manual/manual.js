/* SPDX-License-Identifier: GPL-3.0-only
 * FMini-1 manual: the language (PT / EN, the same choice as the site and the emulator: localStorage "fmini-lang") */
(function () {
  var root = document.documentElement;
  function read() { try { var v = localStorage.getItem("fmini-lang"); if (v === "pt" || v === "en") return v; } catch (e) { /* no storage */ } return null; }
  function write(v) { try { localStorage.setItem("fmini-lang", v); } catch (e) { /* no storage */ } }
  function apply(l) {
    root.classList.remove("lang-pt", "lang-en");
    root.classList.add("lang-" + l);
    root.setAttribute("lang", l === "pt" ? "pt-BR" : "en");
    var b = document.getElementById("lang");
    if (b) { b.textContent = l === "pt" ? "PT" : "EN"; b.setAttribute("aria-label", l === "pt" ? "Idioma: português" : "Language: English"); }
    document.title = root.getAttribute("data-title-" + l) || document.title;
  }
  var cur = read() || (/^pt/i.test(navigator.language || "") ? "pt" : "en");
  apply(cur);
  var b = document.getElementById("lang");
  if (b) b.addEventListener("click", function () { cur = cur === "pt" ? "en" : "pt"; write(cur); apply(cur); });
})();
