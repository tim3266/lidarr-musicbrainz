// ==UserScript==
// @name         MusicBrainz Helper (Lidarr)
// @namespace    https://github.com/tim3266/lidarr-musicbrainz
// @version      1.3.0
// @description  Raccourci Lidarr → lidarr-musicbrainz (release group depuis la fiche album)
// @author       tim3266
// @match        *://192.168.1.27:8686/*
// @match        *://192.168.1.27/*
// @match        *://127.0.0.1:8686/*
// @match        *://localhost:8686/*
// @icon         https://lidarr.audio/img/logo-lidarr.png
// @grant        none
// ==/UserScript==

(function () {
  "use strict";

  /** Page app servie par le conteneur lidarr-musicbrainz (8787) */
  const MB_APP_URL = "http://192.168.1.27:8787/app.html";

  /**
   * Clé API Lidarr (Settings → General) — optionnelle.
   * Permet de lire l’édition surveillée via GET /api/v1/album?foreignAlbumId=…
   */
  const LIDARR_API_KEY = "";

  const UUID =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

  const SIDEBAR_ID = "lmb-sidebar-item";
  const PANEL_ID = "lmb-plugins-panel";
  const ALBUM_BAR_ID = "lmb-album-bar";
  const LABEL = "MusicBrainz Helper";
  const ALBUM_BTN = "Analyser MB";

  function openApp(extraQuery) {
    const url = new URL(MB_APP_URL);
    if (extraQuery) {
      Object.entries(extraQuery).forEach(([k, v]) => {
        if (v) url.searchParams.set(k, v);
      });
    }
    window.open(url.href, "_blank", "noopener,noreferrer");
  }

  /** Lidarr route : /album/{foreignAlbumId} ou /{urlBase}/album/… */
  function releaseGroupFromPage() {
    const fromPath = location.pathname.match(/\/album\/([^/?#]+)/i);
    if (fromPath && UUID.test(fromPath[1])) return fromPath[1];

    const mb = document.querySelector('a[href*="musicbrainz.org/release-group/"]');
    if (mb) {
      const href = mb.getAttribute("href") || "";
      const fromLink = href.match(/release-group\/([^/?#]+)/i);
      if (fromLink && UUID.test(fromLink[1])) return fromLink[1];
    }
    return null;
  }

  function isAlbumPage() {
    return /\/album\/[^/?#]+/i.test(location.pathname);
  }

  async function fetchAlbumFromLidarr(releaseGroupMbid) {
    if (!LIDARR_API_KEY) return null;
    try {
      const res = await fetch(
        `/api/v1/album?foreignAlbumId=${encodeURIComponent(releaseGroupMbid)}`,
        { headers: { "X-Api-Key": LIDARR_API_KEY, Accept: "application/json" } }
      );
      if (!res.ok) return null;
      const data = await res.json();
      return Array.isArray(data)
        ? data.find((a) => a.foreignAlbumId === releaseGroupMbid) || data[0]
        : data;
    } catch {
      return null;
    }
  }

  async function monitoredReleaseInfo(releaseGroupMbid) {
    const album = await fetchAlbumFromLidarr(releaseGroupMbid);
    if (!album) return null;
    const releases = album.releases || [];
    const picked = releases.find((r) => r.monitored) || releases[0];
    if (!picked?.foreignReleaseId || !UUID.test(picked.foreignReleaseId)) return null;
    return {
      id: picked.foreignReleaseId,
      title: picked.title || picked.disambiguation || "",
    };
  }

  async function monitoredReleaseMbid(releaseGroupMbid) {
    const info = await monitoredReleaseInfo(releaseGroupMbid);
    return info?.id || null;
  }

  function copyToClipboard(text, button) {
    if (!text) return;
    const done = () => {
      const prev = button.textContent;
      button.textContent = "Copié";
      window.setTimeout(() => {
        button.textContent = prev;
      }, 1200);
    };
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(() => {});
      return;
    }
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand("copy");
      done();
    } finally {
      document.body.removeChild(ta);
    }
  }

  function idRow(label, value, placeholder) {
    const row = document.createElement("div");
    row.style.cssText =
      "display:flex;flex-wrap:wrap;align-items:center;gap:0.4rem;width:100%;";
    const lab = document.createElement("span");
    lab.textContent = label;
    lab.style.cssText = "color:#9aa3ad;min-width:6.5rem;font-size:12px;";
    const input = document.createElement("input");
    input.type = "text";
    input.readOnly = true;
    input.value = value || "";
    input.placeholder = placeholder || "";
    input.style.cssText =
      "flex:1;min-width:14rem;padding:0.3rem 0.45rem;font-family:ui-monospace,monospace;font-size:11px;background:#1a1d21;border:1px solid #3a3f47;color:#e6e6e6;border-radius:3px;";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "Copier";
    btn.style.cssText =
      "padding:0.3rem 0.55rem;border-radius:3px;border:1px solid #3a3f47;background:#343a42;color:#e6e6e6;cursor:pointer;font-size:12px;";
    btn.addEventListener("click", () => copyToClipboard(input.value.trim(), btn));
    row.appendChild(lab);
    row.appendChild(input);
    row.appendChild(btn);
    return { row, input };
  }

  async function openAppForAlbum(releaseGroupMbid) {
    const rg = releaseGroupMbid || releaseGroupFromPage();
    const query = {};
    if (rg) query.rg = rg;
    if (rg) {
      const release = await monitoredReleaseMbid(rg);
      if (release) query.release = release;
    }
    openApp(query);
  }

  function findPluginsChildLink() {
    return (
      document.querySelector('a[href="/system/plugins"]') ||
      document.querySelector('a[href$="/system/plugins"]') ||
      document.querySelector('a[href*="/system/plugins"]')
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
      void openAppForAlbum();
    });

    item.parentElement.insertBefore(clone, item.nextSibling);
  }

  async function fillReleaseField(bar, rg) {
    const input = bar.querySelector("#lmb-release-input");
    const hint = bar.querySelector("#lmb-release-hint");
    if (!input) return;
    if (!LIDARR_API_KEY) {
      input.placeholder = "Renseigne LIDARR_API_KEY dans le script";
      if (hint) hint.textContent = "";
      return;
    }
    input.placeholder = "Chargement…";
    const info = await monitoredReleaseInfo(rg);
    if (bar.dataset.rg !== rg) return;
    if (!info) {
      input.value = "";
      input.placeholder = "Release introuvable (API Lidarr)";
      if (hint) hint.textContent = "";
      return;
    }
    input.value = info.id;
    input.placeholder = "";
    if (hint) {
      hint.textContent = info.title ? `(${info.title})` : "";
    }
  }

  /**
   * Bandeau visible sur la fiche album (le lien MB natif est dans le tooltip « Links »).
   */
  function injectAlbumBar() {
    if (!isAlbumPage()) {
      document.getElementById(ALBUM_BAR_ID)?.remove();
      return;
    }

    const rg = releaseGroupFromPage();
    let bar = document.getElementById(ALBUM_BAR_ID);

    if (!rg) {
      if (!bar) {
        const host =
          document.querySelector('[class*="PageContentBody"]') ||
          document.querySelector('[class*="PageContent"]');
        if (!host) return;
        bar = document.createElement("div");
        bar.id = ALBUM_BAR_ID;
        bar.style.cssText =
          "margin:0 0 1rem;padding:0.75rem 1rem;border:1px solid #6b5200;border-radius:4px;background:#3d2f00;color:#ffe8a3;font-size:13px;";
        bar.textContent =
          "MusicBrainz Helper : ouvre un album via Library (URL /album/… avec MBID) ou attends le chargement complet.";
        host.prepend(bar);
      }
      return;
    }

    if (bar && bar.dataset.rg === rg) {
      void fillReleaseField(bar, rg);
      return;
    }
    bar?.remove();

    const host =
      document.querySelector('[class*="PageContentBody"]') ||
      document.querySelector('[class*="PageContent"]');
    if (!host) return;

    bar = document.createElement("div");
    bar.id = ALBUM_BAR_ID;
    bar.dataset.rg = rg;
    bar.style.cssText =
      "margin:0 0 1rem;padding:0.65rem 1rem;border:1px solid #3a3f47;border-radius:4px;background:#262a2f;color:#e6e6e6;font-size:13px;display:flex;flex-wrap:wrap;align-items:center;gap:0.6rem;";

    const top = document.createElement("div");
    top.style.cssText = "display:flex;flex-wrap:wrap;align-items:center;gap:0.6rem;width:100%;";
    const title = document.createElement("span");
    title.textContent = "MusicBrainz Helper";
    title.style.color = "#9aa3ad";
    const mb = document.createElement("a");
    mb.href = `https://musicbrainz.org/release-group/${rg}`;
    mb.target = "_blank";
    mb.rel = "noopener noreferrer";
    mb.textContent = "MusicBrainz";
    mb.style.cssText =
      "color:#5d9cec;text-decoration:none;padding:0.35rem 0.6rem;border:1px solid #3a3f47;border-radius:3px;";
    const analyse = document.createElement("button");
    analyse.type = "button";
    analyse.textContent = ALBUM_BTN;
    analyse.style.cssText =
      "padding:0.35rem 0.65rem;border-radius:3px;border:1px solid #4a7eb5;background:#3a6ea5;color:#fff;cursor:pointer;";
    analyse.addEventListener("click", () => void openAppForAlbum(rg));
    top.appendChild(title);
    top.appendChild(mb);
    top.appendChild(analyse);

    const ids = document.createElement("div");
    ids.style.cssText =
      "width:100%;display:flex;flex-direction:column;gap:0.35rem;margin-top:0.15rem;";
    const rgRow = idRow("Release group", rg);
    const relRow = idRow("Release", "", "Clé API Lidarr…");
    relRow.input.id = "lmb-release-input";
    const hint = document.createElement("span");
    hint.id = "lmb-release-hint";
    hint.style.cssText = "color:#9aa3ad;font-size:11px;margin-left:6.9rem;";
    ids.appendChild(rgRow.row);
    ids.appendChild(relRow.row);
    ids.appendChild(hint);

    bar.appendChild(top);
    bar.appendChild(ids);
    host.prepend(bar);
    void fillReleaseField(bar, rg);
  }

  function injectPluginsPanel() {
    if (document.getElementById(PANEL_ID)) return;
    if (!/\/system\/plugins\/?$/i.test(location.pathname)) return;

    const host =
      document.querySelector('[class*="PageContentBody"]') ||
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
      "Sur une fiche album, un bandeau « MusicBrainz Helper » apparaît en haut (Lidarr cache ses liens dans le tooltip « Links »)." +
      "</p>" +
      "<button type=\"button\" id=\"lmb-open-app\" style=\"padding:0.45rem 0.9rem;border-radius:4px;border:1px solid #4a7eb5;background:#3a6ea5;color:#fff;cursor:pointer\">" +
      "Ouvrir MusicBrainz Helper" +
      "</button>";
    host.prepend(panel);
    document.getElementById("lmb-open-app").addEventListener("click", () => {
      void openAppForAlbum();
    });
  }

  let debounce = null;
  function schedule() {
    if (debounce) return;
    debounce = window.setTimeout(() => {
      debounce = null;
      injectSidebarLink();
      injectPluginsPanel();
      injectAlbumBar();
    }, 200);
  }

  const obs = new MutationObserver(schedule);
  obs.observe(document.documentElement, { childList: true, subtree: true });
  schedule();
})();
