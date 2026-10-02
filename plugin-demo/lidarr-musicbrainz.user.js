// ==UserScript==
// @name         MusicBrainz Helper (Lidarr)
// @namespace    https://github.com/tim3266/lidarr-musicbrainz
// @version      1.0.0
// @description  Entrée System → MusicBrainz Helper : ouvre lidarr-musicbrainz dans une nouvelle fenêtre
// @author       tim3266
// @match        http://192.168.1.27:8686/*
// @match        http://127.0.0.1:8686/*
// @match        http://localhost:8686/*
// @icon         https://lidarr.audio/img/logo-lidarr.png
// @grant        none
// ==/UserScript==

(function () {
  "use strict";

  /** URL de la page app (plugin-demo/app.html servie par le conteneur 8787) */
  const MB_APP_URL = "http://192.168.1.27:8787/app.html";

  const SIDEBAR_ID = "lmb-sidebar-item";
  const PANEL_ID = "lmb-plugins-panel";
  const LABEL = "MusicBrainz Helper";

  function openApp(extraQuery) {
    const url = new URL(MB_APP_URL);
    if (extraQuery) {
      Object.entries(extraQuery).forEach(([k, v]) => url.searchParams.set(k, v));
    }
    window.open(url.href, "_blank", "noopener,noreferrer");
  }

  function findPluginsChildLink() {
    return (
      document.querySelector('a[href="/system/plugins"]') ||
      document.querySelector('a[href$="/system/plugins"]')
    );
  }

  function injectSidebarLink() {
    if (document.getElementById(SIDEBAR_ID)) return;
    const plugins = findPluginsChildLink();
    if (!plugins) return;

    const item = plugins.closest("div");
    if (!item || !item.parentElement) return;

    const clone = item.cloneNode(true);
    clone.id = SIDEBAR_ID;
    const link = clone.querySelector("a");
    if (!link) return;

    link.removeAttribute("href");
    link.setAttribute("role", "button");
    link.style.cursor = "pointer";

    const titleEl = link.querySelector("span[class*='noIcon']");
    if (titleEl) titleEl.textContent = LABEL;
    else link.appendChild(document.createTextNode(LABEL));
    clone.querySelectorAll("[class*='status']").forEach((el) => el.remove());

    link.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      openApp();
    });

    item.parentElement.insertBefore(clone, item.nextSibling);
  }

  function injectPluginsPanel() {
    if (document.getElementById(PANEL_ID)) return;
    if (!/\/system\/plugins\/?$/i.test(location.pathname)) return;

    const host =
      document.querySelector("[class*='PageContentBody']") ||
      document.querySelector("main") ||
      document.body;
    if (!host) return;

    const panel = document.createElement("div");
    panel.id = PANEL_ID;
    panel.style.cssText =
      "margin:0 0 1.25rem;padding:1rem 1.25rem;border:1px solid #3a3f47;border-radius:4px;background:#262a2f;color:#e6e6e6;font-size:14px;max-width:960px;";
    panel.innerHTML =
      "<p style=\"margin:0 0 0.5rem;font-weight:600\">" +
      LABEL +
      "</p>" +
      "<p style=\"margin:0 0 0.75rem;color:#9aa3ad;font-size:13px\">" +
      "Raccourci userscript (comme la maquette plugin-demo). Ouvre le service sur le port 8787." +
      "</p>" +
      "<button type=\"button\" id=\"lmb-open-app\" style=\"padding:0.45rem 0.9rem;border-radius:4px;border:1px solid #4a7eb5;background:#3a6ea5;color:#fff;cursor:pointer\">" +
      "Ouvrir MusicBrainz Helper" +
      "</button>";
    host.prepend(panel);
    document.getElementById("lmb-open-app").addEventListener("click", () => openApp());
  }

  let debounce = null;
  function schedule() {
    if (debounce) return;
    debounce = window.setTimeout(() => {
      debounce = null;
      injectSidebarLink();
      injectPluginsPanel();
    }, 200);
  }

  const obs = new MutationObserver(schedule);
  obs.observe(document.documentElement, { childList: true, subtree: true });
  schedule();
})();
