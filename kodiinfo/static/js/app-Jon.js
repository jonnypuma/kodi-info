(() => {
  const TOKEN_KEY = "kodiinfo_connection_token";
  const TOKEN_MAP_KEY = "kodiinfo_server_tokens_v1";
  const RECENT_CUSTOM_KEY = "kodiinfo_recent_custom_v1";
  const RECENT_CUSTOM_MAX = 10;
  const CACHE_DB = "kodiinfo_dashboard_cache";
  const CACHE_STORE = "dashboards";
  const CACHE_TTL_MS = 3 * 24 * 60 * 60 * 1000; // 3 days
  const POLL_MS = 2000;
  const STATUS_HIDE_MS = 20000;
  const BTN_OK_MS = 4000;
  const BTN_ERR_MS = 12000;

  let config = { presets: [], default_recent_limit: 10, recent_limit_options: [5, 10, 20, 50] };
  let pollTimer = null;
  let statusTimer = null;
  let currentToken = null;
  let currentCacheKey = null;
  let lastLoadBody = null;
  let actionsReady = false;
  let loadFinished = false;
  let loadInProgress = false;
  let activeJobId = null;
  let operationTimer = null;
  let operationReloaded = {};

  const $ = (id) => document.getElementById(id);

  function showView(name) {
    const views = {
      login: $("view-login"),
      overview: $("view-overview"),
      loading: $("view-loading"),
      dashboard: $("view-dashboard"),
    };
    Object.keys(views).forEach((key) => {
      const el = views[key];
      if (!el) return;
      const on = key === name;
      el.hidden = !on;
      el.style.display = on ? "" : "none";
    });
  }

  function getToken() {
    return currentToken || sessionStorage.getItem(TOKEN_KEY) || "";
  }

  function setToken(tok) {
    currentToken = tok || null;
    if (tok) sessionStorage.setItem(TOKEN_KEY, tok);
    else sessionStorage.removeItem(TOKEN_KEY);
  }

  function readTokenMap() {
    try {
      const raw = sessionStorage.getItem(TOKEN_MAP_KEY);
      const obj = raw ? JSON.parse(raw) : {};
      return obj && typeof obj === "object" ? obj : {};
    } catch (e) {
      return {};
    }
  }

  function rememberTokenForKey(cacheKey, tok) {
    if (!cacheKey || !tok) return;
    try {
      const map = readTokenMap();
      map[cacheKey] = tok;
      sessionStorage.setItem(TOKEN_MAP_KEY, JSON.stringify(map));
    } catch (e) {}
  }

  function tokenForKey(cacheKey) {
    if (!cacheKey) return "";
    const map = readTokenMap();
    return map[cacheKey] || "";
  }

  function makeCacheKey(body) {
    if (!body || typeof body !== "object") return null;
    if (body.custom) {
      const host = String(body.host || "").trim().toLowerCase();
      if (!host) return null;
      let port = parseInt(body.port, 10);
      if (!Number.isFinite(port)) port = 8080;
      const scheme = String(body.scheme || "http").toLowerCase() === "https" ? "https" : "http";
      return "custom:" + scheme + "://" + host + ":" + port;
    }
    if (body.preset != null && String(body.preset).trim() !== "" && String(body.preset) !== "custom") {
      return "preset:" + String(body.preset).trim();
    }
    if (body.connection_token && currentCacheKey) return currentCacheKey;
    return null;
  }

  function openCacheDb() {
    return new Promise((resolve, reject) => {
      if (!window.indexedDB) {
        reject(new Error("no indexedDB"));
        return;
      }
      const req = indexedDB.open(CACHE_DB, 1);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(CACHE_STORE)) {
          db.createObjectStore(CACHE_STORE, { keyPath: "cacheKey" });
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error || new Error("idb open failed"));
    });
  }

  async function cacheGet(cacheKey) {
    if (!cacheKey) return null;
    try {
      const db = await openCacheDb();
      return await new Promise((resolve, reject) => {
        const tx = db.transaction(CACHE_STORE, "readonly");
        const req = tx.objectStore(CACHE_STORE).get(cacheKey);
        req.onsuccess = () => resolve(req.result || null);
        req.onerror = () => reject(req.error);
      });
    } catch (e) {
      try {
        const raw = localStorage.getItem(CACHE_DB + ":" + cacheKey);
        return raw ? JSON.parse(raw) : null;
      } catch (e2) {
        return null;
      }
    }
  }

  async function cacheSet(cacheKey, data) {
    if (!cacheKey || !data) return;
    const safe = JSON.parse(JSON.stringify(data));
    delete safe.connection_token;
    delete safe.fromCache;
    delete safe.cachedAt;
    const entry = { cacheKey, cachedAt: Date.now(), data: safe };
    try {
      const db = await openCacheDb();
      await new Promise((resolve, reject) => {
        const tx = db.transaction(CACHE_STORE, "readwrite");
        tx.objectStore(CACHE_STORE).put(entry);
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
      });
    } catch (e) {
      try {
        localStorage.setItem(CACHE_DB + ":" + cacheKey, JSON.stringify(entry));
      } catch (e2) {}
    }
  }

  async function cacheDelete(cacheKey) {
    if (!cacheKey) return;
    try {
      const db = await openCacheDb();
      await new Promise((resolve, reject) => {
        const tx = db.transaction(CACHE_STORE, "readwrite");
        tx.objectStore(CACHE_STORE).delete(cacheKey);
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
      });
    } catch (e) {
      try {
        localStorage.removeItem(CACHE_DB + ":" + cacheKey);
      } catch (e2) {}
    }
  }

  function cacheIsFresh(entry) {
    if (!entry || !entry.cachedAt || !entry.data) return false;
    return Date.now() - Number(entry.cachedAt) < CACHE_TTL_MS;
  }

  function formatCacheAge(cachedAt) {
    const ageMs = Math.max(0, Date.now() - Number(cachedAt || 0));
    const mins = Math.floor(ageMs / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return mins + "m ago";
    const hours = Math.floor(mins / 60);
    if (hours < 48) return hours + "h ago";
    const days = Math.floor(hours / 24);
    return days + "d ago";
  }

  function fmt(n) {
    return Number(n || 0).toLocaleString();
  }

  function formatActionTime(iso) {
    if (!iso) return "never";
    try {
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) return iso;
      return d.toLocaleString();
    } catch (e) {
      return iso;
    }
  }

  function updateLibraryMeta(actions) {
    const el = $("library-meta");
    if (!el) return;
    const a = actions || {};
    el.textContent =
      "Last video scan: " + formatActionTime(a.last_video_scan) +
      " · Last video clean: " + formatActionTime(a.last_video_clean) +
      " · Last audio scan: " + formatActionTime(a.last_audio_scan) +
      " · Last music clean: " + formatActionTime(a.last_music_clean);
  }

  function setProgressBars(stats) {
    const mp = Math.max(0, Math.min(100, Number(stats.movie_watch_pct || 0)));
    const ep = Math.max(0, Math.min(100, Number(stats.episode_watch_pct || 0)));
    $("movie-watch-bar").style.width = mp + "%";
    $("episode-watch-bar").style.width = ep + "%";
    $("movie-watch-pct-label").textContent = mp.toFixed(1) + "%";
    $("episode-watch-pct-label").textContent = ep.toFixed(1) + "%";
  }

  function renderRecentList(containerId, items, cssClass) {
    const box = $(containerId);
    if (!box) return;
    box.innerHTML = "";
    (items || []).forEach((item) => {
      const row = document.createElement("div");
      row.className = "recent-entry";
      let media;
      if (item.image) {
        media = document.createElement("img");
        media.src = item.image;
        media.alt = item.title || "";
        media.className = cssClass + " zoomable";
      } else {
        media = document.createElement("div");
        media.className = "no-image";
        media.textContent = item.icon || "•";
      }
      const content = document.createElement("div");
      content.className = "content";
      const title = document.createElement("div");
      title.className = "title";
      title.textContent = item.title || "";
      content.appendChild(title);
      if (item.subtitle) {
        const sub = document.createElement("div");
        sub.className = "subtitle";
        sub.textContent = item.subtitle;
        content.appendChild(sub);
      }
      if (item.date) {
        const date = document.createElement("div");
        date.className = "date";
        date.textContent = item.date;
        content.appendChild(date);
      }
      row.appendChild(media);
      row.appendChild(content);
      box.appendChild(row);
    });
    bindZoom();
  }

  function setLibraryActionsEnabled(enabled) {
    actionsReady = !!enabled;
    ["update-video-btn", "update-audio-btn", "clean-video-btn", "clean-music-btn", "refresh-btn"].forEach((id) => {
      const el = $(id);
      if (!el) return;
      if (id === "refresh-btn") {
        el.style.opacity = enabled ? "" : "0.45";
        el.style.pointerEvents = enabled ? "" : "none";
        return;
      }
      el.disabled = !enabled;
    });
  }

  function activeServerLabel() {
    const el = $("kodi-display");
    const t = el ? String(el.textContent || "") : "";
    return t.replace(/^Connected to:\s*/i, "").trim() || "current server";
  }

  function renderDashboard(data, opts) {
    opts = opts || {};
    clearStatus();
    loadInProgress = false;
    const loadBtn = $("load-btn");
    if (loadBtn) loadBtn.disabled = false;
    if (opts.cacheKey) currentCacheKey = opts.cacheKey;
    const stats = data.stats || {};
    $("kodi-display").textContent = "Connected to: " + (data.kodi_display || "—");
    let updated = "Last updated: " + (data.last_updated || "—");
    if (opts.fromCache) {
      updated += " · cached (" + formatCacheAge(opts.cachedAt) + ", max 3d)";
    }
    $("last-updated").textContent = updated;
    updateLibraryMeta(data.library_actions);

    $("stat-total-movies").textContent = fmt(stats.total_movies);
    $("stat-watched-movies").textContent = fmt(stats.watched_movies);
    $("stat-unwatched-movies").textContent = fmt(
      Math.max(0, (stats.total_movies || 0) - (stats.watched_movies || 0))
    );
    $("stat-total-shows").textContent = fmt(stats.total_tv_shows);
    $("stat-total-episodes").textContent = fmt(stats.total_episodes);
    $("stat-watched-episodes").textContent = fmt(stats.watched_episodes);
    $("stat-total-artists").textContent = fmt(stats.total_artists);
    $("stat-total-albums").textContent = fmt(stats.total_albums);
    $("stat-total-songs").textContent = fmt(stats.total_songs);
    setProgressBars(stats);

    const limit = stats.recent_limit || data.recent_limit || config.default_recent_limit || 10;
    const sel = $("recent-limit-select");
    if (sel) sel.value = String(limit);

    const recent = stats.recently_added || {};
    renderRecentList("recent-movies", recent.movies, "movie-poster");
    renderRecentList("recent-episodes", recent.episodes, "episode-thumb");
    renderRecentList("recent-albums", recent.albums, "album-cover");
    showView("dashboard");
    if (opts.actionsReady === false) {
      setLibraryActionsEnabled(false);
    } else {
      setLibraryActionsEnabled(true);
      startOperationPolling();
    }
  }

  function bindZoom() {
    const overlay = $("image-overlay");
    const overlayImg = $("overlay-image");
    document.querySelectorAll(".zoomable").forEach((img) => {
      if (img.dataset.zoomBound) return;
      img.dataset.zoomBound = "1";
      img.addEventListener("click", (ev) => {
        ev.stopPropagation();
        overlay.classList.toggle("episode-zoom", img.classList.contains("episode-thumb"));
        overlayImg.src = img.src;
        overlay.classList.add("visible");
      });
    });
  }

  function updateLoading(progress, message) {
    const pct = Math.min(100, Math.max(0, Math.round(progress || 0)));
    $("loading-progress").style.width = pct + "%";
    $("loading-text").textContent = (message || "Loading") + " " + pct + "%";
  }

  function showLoadError(msg) {
    loadFinished = true;
    loadInProgress = false;
    stopPolling();
    const loadBtn = $("load-btn");
    if (loadBtn) loadBtn.disabled = false;
    const loader = document.querySelector("#view-loading .loader");
    if (loader) loader.style.display = "none";
    const bar = $("loading-bar");
    if (bar) bar.style.display = "none";
    $("loading-text").hidden = true;
    $("load-error-panel").hidden = false;
    $("load-error-message").textContent = msg || "Could not load library.";
    showView("loading");
  }

  function resetLoadError() {
    const loader = document.querySelector("#view-loading .loader");
    if (loader) loader.style.display = "";
    const bar = document.querySelector("#view-loading .loading-bar");
    if (bar) bar.style.display = "";
    $("loading-text").hidden = false;
    $("load-error-panel").hidden = true;
    $("load-error-message").textContent = "";
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function formatDuration(seconds) {
    const total = Math.max(0, Math.floor(Number(seconds) || 0));
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    return (h ? String(h).padStart(2, "0") + ":" : "") +
      String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
  }

  function renderOperation(job) {
    const el = $("operation-status");
    if (!el) return;
    if (!job) {
      el.hidden = true;
      return;
    }
    const started = Date.parse(job.started_at || "") || Date.now();
    const end = job.finished_at ? (Date.parse(job.finished_at) || Date.now()) : Date.now();
    const elapsed = Math.max(0, Math.floor((end - started) / 1000));
    const state = String(job.state || "requested").replace("_", " ");
    el.hidden = false;
    el.textContent = job.operation + " · " + state + " · " + formatDuration(elapsed) +
      (job.message ? " — " + job.message : "");
  }

  function renderOperationHistory(history) {
    const details = $("operation-history");
    const list = $("operation-history-list");
    if (!details || !list) return;
    const items = Array.isArray(history) ? history : [];
    details.hidden = items.length === 0;
    list.textContent = "";
    items.slice(0, 10).forEach((job) => {
      const row = document.createElement("div");
      row.className = "history-row";
      row.textContent = job.operation + " · " + job.state + " · " +
        formatActionTime(job.started_at) + " · " + formatDuration(job.elapsed_seconds);
      list.appendChild(row);
    });
  }

  function stopOperationPolling() {
    if (operationTimer) {
      clearInterval(operationTimer);
      operationTimer = null;
    }
  }

  async function refreshOperationState() {
    if (!actionsReady) return;
    try {
      const res = await fetch("/api/library-operation-history", { credentials: "same-origin" });
      if (!res.ok) return;
      const data = await res.json();
      const job = data.current;
      renderOperation(job);
      renderOperationHistory(data.history);
      if (!job) return;
      if (job.state === "accepted" && !operationReloaded[job.job_id]) {
        operationReloaded[job.job_id] = true;
        // HTTP JSON-RPC confirms acceptance, not scanner completion. Reload
        // shortly so newly indexed items appear without claiming completion.
        setTimeout(() => refreshDashboard(), 1500);
      }
    } catch (e) {}
  }

  function startOperationPolling() {
    stopOperationPolling();
    refreshOperationState();
    operationTimer = setInterval(refreshOperationState, POLL_MS);
  }

  async function pollJob(jobId) {
    stopPolling();
    activeJobId = jobId;
    const tick = async () => {
      if (loadFinished || activeJobId !== jobId) return;
      try {
        const res = await fetch("/api/load-status/" + jobId);
        if (res.status === 404) {
          loadInProgress = false;
          showLoadError("Loading job missing — choose a server and try again.");
          return;
        }
        if (!res.ok) throw new Error("HTTP " + res.status);
        const data = await res.json();
        updateLoading(data.progress || 0, data.message || "Loading");
        if (data.status === "done") {
          loadFinished = true;
          stopPolling();
          try {
            const dash = await fetch("/api/dashboard/" + jobId);
            const body = await dash.json();
            if (!dash.ok || !body.success) {
              loadInProgress = false;
              showLoadError((body && body.message) || "Failed to load dashboard");
              return;
            }
            if (body.data.connection_token) {
              setToken(body.data.connection_token);
              if (currentCacheKey) rememberTokenForKey(currentCacheKey, body.data.connection_token);
            }
            loadInProgress = false;
            renderDashboard(body.data, { cacheKey: currentCacheKey, fromCache: false, actionsReady: true });
            if (currentCacheKey) {
              cacheSet(currentCacheKey, body.data).catch(() => {});
            }
          } catch (dashErr) {
            loadInProgress = false;
            showLoadError(
              (dashErr && dashErr.message) || "Failed to load dashboard data"
            );
          }
          return;
        }
        if (data.status === "error") {
          loadInProgress = false;
          showLoadError(data.message || "Error loading");
        }
      } catch (e) {
        /* transient poll failure — keep trying */
      }
    };
    await tick();
    if (!loadFinished && activeJobId === jobId) {
      pollTimer = setInterval(tick, POLL_MS);
    }
  }

  async function ensureConnection(body, cacheKey) {
    const payload = Object.assign({}, body || {});
    // Only reuse a token bound to THIS cache key — never the previous server's token.
    const mapped = tokenForKey(cacheKey);
    if (mapped) {
      payload.connection_token = mapped;
    } else {
      delete payload.connection_token;
    }
    try {
      const res = await fetch("/api/ensure-connection", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.success) {
        return { ok: false, message: (data && data.message) || ("HTTP " + res.status) };
      }
      if (data.connection_token) {
        setToken(data.connection_token);
        if (cacheKey) rememberTokenForKey(cacheKey, data.connection_token);
      }
      return { ok: true, token: data.connection_token, host: data.host || "" };
    } catch (e) {
      return { ok: false, message: (e && e.message) || String(e) };
    }
  }

  async function startLoad(body, opts) {
    opts = opts || {};
    const forceRefresh = !!opts.forceRefresh;
    if (loadInProgress) return;
    clearStatus();
    lastLoadBody = body ? Object.assign({}, body) : null;
    const cacheKey = makeCacheKey(body);
    if (cacheKey) currentCacheKey = cacheKey;

    if (!forceRefresh && cacheKey) {
      const entry = await cacheGet(cacheKey);
      if (cacheIsFresh(entry)) {
        // Do not keep the previous server's token; wait until this server is ensured.
        setToken(tokenForKey(cacheKey) || "");
        setLibraryActionsEnabled(false);
        renderDashboard(entry.data, {
          cacheKey,
          fromCache: true,
          cachedAt: entry.cachedAt,
          actionsReady: false,
        });
        const ensured = await ensureConnection(body, cacheKey);
        if (ensured.ok) {
          setLibraryActionsEnabled(true);
        } else {
          setLibraryActionsEnabled(false);
          showStatus(
            "err",
            "Cached library shown — actions disabled",
            "Could not bind connection for this server: " + (ensured.message || "unknown error")
          );
        }
        return;
      }
    }

    if (forceRefresh && cacheKey) {
      await cacheDelete(cacheKey);
    }

    loadInProgress = true;
    setLibraryActionsEnabled(false);
    resetLoadError();
    loadFinished = false;
    stopPolling();
    activeJobId = null;
    showView("loading");
    updateLoading(0, "Starting");
    const loadBtn = $("load-btn");
    if (loadBtn) loadBtn.disabled = true;
    try {
      const res = await fetch("/api/start-load", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const text = await res.text();
      let data = {};
      try { data = text ? JSON.parse(text) : {}; } catch (e) {}
      if (!res.ok) {
        loadInProgress = false;
        if (loadBtn) loadBtn.disabled = false;
        showLoadError((data && data.message) || text || ("HTTP " + res.status));
        return;
      }
      if (data.connection_token) {
        setToken(data.connection_token);
        if (cacheKey) rememberTokenForKey(cacheKey, data.connection_token);
      }
      await pollJob(data.job_id);
    } catch (e) {
      loadInProgress = false;
      if (loadBtn) loadBtn.disabled = false;
      showLoadError((e && e.message) || String(e));
    }
  }

  function buildCustomServerPayload() {
    const recentLimit = Number(($("recent-limit-select") && $("recent-limit-select").value) || config.default_recent_limit || 10);
    return {
      custom: true,
      host: ($("custom-host") && $("custom-host").value) || "",
      port: ($("custom-port") && $("custom-port").value) || 8080,
      scheme: ($("custom-scheme") && $("custom-scheme").value) || "http",
      username: ($("custom-user") && $("custom-user").value) || "",
      password: ($("custom-pass") && $("custom-pass").value) || "",
      recent_limit: recentLimit,
    };
  }

  function recentCustomLoad() {
    try {
      const raw = localStorage.getItem(RECENT_CUSTOM_KEY);
      const arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr.slice(0, RECENT_CUSTOM_MAX) : [];
    } catch (e) {
      return [];
    }
  }

  function recentCustomSave(body) {
    if (!body || !body.custom) return;
    const host = String(body.host || "").trim();
    if (!host) return;
    let port = parseInt(body.port, 10);
    if (!Number.isFinite(port)) port = 8080;
    const scheme = String(body.scheme || "http").toLowerCase() === "https" ? "https" : "http";
    const username = String(body.username || "").trim();
    const entry = { h: host, p: port, s: scheme, u: username };
    try {
      let list = recentCustomLoad().filter(
        (e) => !(e.h.toLowerCase() === host.toLowerCase() && e.p === port && e.s === scheme && e.u === username)
      );
      list.unshift(entry);
      localStorage.setItem(RECENT_CUSTOM_KEY, JSON.stringify(list.slice(0, RECENT_CUSTOM_MAX)));
    } catch (e) {}
  }

  function refreshRecentDropdown() {
    const box = $("custom-recent-dropdown");
    if (!box) return;
    const list = recentCustomLoad();
    box.innerHTML = "";
    if (!list.length) {
      box.hidden = true;
      return;
    }
    const hdr = document.createElement("div");
    hdr.className = "recent-dropdown-header";
    hdr.textContent = "Recent (this browser)";
    box.appendChild(hdr);
    list.forEach((e) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "recent-dropdown-item";
      btn.textContent = e.h + ":" + e.p + " (" + e.s + ")" + (e.u ? " · " + e.u : "");
      btn.addEventListener("click", () => {
        $("custom-host").value = e.h;
        $("custom-port").value = String(e.p);
        $("custom-scheme").value = e.s;
        $("custom-user").value = e.u || "";
        $("custom-pass").value = "";
        box.hidden = true;
      });
      box.appendChild(btn);
    });
  }

  function clearStatus() {
    if (statusTimer) {
      clearTimeout(statusTimer);
      statusTimer = null;
    }
    const box = $("library-action-status");
    const body = $("library-action-status-body");
    if (!box) return;
    box.hidden = true;
    if (body) body.textContent = "";
    box.className = "action-status";
  }

  function showStatus(level, summary, detail) {
    const box = $("library-action-status");
    const body = $("library-action-status-body");
    if (!box || !body) return;
    if (statusTimer) clearTimeout(statusTimer);
    body.textContent =
      "[" + new Date().toLocaleTimeString() + "] " + summary + (detail ? "\n" + detail : "");
    box.hidden = false;
    box.className = "action-status visible " + (level === "ok" ? "ok" : "err");
    statusTimer = setTimeout(clearStatus, STATUS_HIDE_MS);
  }

  async function libraryAction(endpoint, label, button) {
    if (!actionsReady) return;
    clearStatus();
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Working…";
    try {
      // Always bind to the active dashboard's server before calling Kodi.
      if (lastLoadBody) {
        const ensured = await ensureConnection(lastLoadBody, currentCacheKey);
        if (!ensured.ok) {
          throw new Error(ensured.message || "Could not bind connection for this server");
        }
      }
      let tok = (currentCacheKey && tokenForKey(currentCacheKey)) || getToken();
      if (!tok) {
        throw new Error("No connection for this server — choose it again from the list");
      }
      setToken(tok);

      const res = await fetch(endpoint, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-Connection-Token": tok,
        },
        body: JSON.stringify({ connection_token: tok }),
      });
      const text = await res.text();
      let data = {};
      try { data = text ? JSON.parse(text) : {}; } catch (e) {}
      if (!res.ok || !data.success) {
        throw new Error((data && data.message) || ("HTTP " + res.status));
      }
      button.textContent = "Started";
      button.style.background = "#28a745";
      const server = activeServerLabel();
      showStatus(
        "ok",
        label + " started (" + server + ")",
        data.message || "Tracking operation status"
      );
      startOperationPolling();
      setTimeout(() => {
        button.disabled = !actionsReady;
        button.textContent = original;
        button.style.background = "";
      }, BTN_OK_MS);
    } catch (err) {
      button.textContent = "Failed — details below";
      button.style.background = "#dc3545";
      showStatus(
        "err",
        label + " failed (" + activeServerLabel() + ")",
        (err && err.message) || String(err)
      );
      setTimeout(() => {
        button.disabled = !actionsReady;
        button.textContent = original;
        button.style.background = "";
      }, BTN_ERR_MS);
    }
  }

  async function refreshDashboard() {
    if (!actionsReady) return;
    const tok = (currentCacheKey && tokenForKey(currentCacheKey)) || getToken();
    if (!tok && !lastLoadBody) {
      showOverview();
      return;
    }
    const recentLimit = Number(($("recent-limit-select") && $("recent-limit-select").value) || config.default_recent_limit || 10);
    // Keep preset/custom identity so a later Scan still targets this server.
    const body = lastLoadBody
      ? Object.assign({}, lastLoadBody, { recent_limit: recentLimit })
      : { connection_token: tok, recent_limit: recentLimit };
    if (tok) body.connection_token = tok;
    await startLoad(body, { forceRefresh: true });
  }

  async function changeRecentLimit() {
    if (!actionsReady) return;
    const tok = (currentCacheKey && tokenForKey(currentCacheKey)) || getToken();
    if (!tok) return;
    const limit = Number($("recent-limit-select").value || 10);
    try {
      const res = await fetch("/api/recent", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-Connection-Token": tok,
        },
        body: JSON.stringify({ connection_token: tok, recent_limit: limit }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.message || "Failed");
      renderRecentList("recent-movies", data.recently_added.movies, "movie-poster");
      renderRecentList("recent-episodes", data.recently_added.episodes, "episode-thumb");
      renderRecentList("recent-albums", data.recently_added.albums, "album-cover");
      if (currentCacheKey) {
        const entry = await cacheGet(currentCacheKey);
        if (entry && entry.data && entry.data.stats) {
          entry.data.stats.recently_added = data.recently_added;
          entry.data.stats.recent_limit = limit;
          entry.data.recent_limit = limit;
          await cacheSet(currentCacheKey, entry.data);
        }
      }
    } catch (e) {
      showStatus("err", "Could not update recently added", (e && e.message) || String(e));
    }
  }

  const OVERVIEW_ACTIONS = [
    ["/api/update-video-library", "Scan video", "update-video-btn"],
    ["/api/update-audio-library", "Scan music", "update-audio-btn"],
    ["/api/clean-video-library", "Clean video", "clean-video-btn"],
    ["/api/clean-music-library", "Clean music", "clean-music-btn"],
  ];

  async function runOverviewAction(server, endpoint, label, card) {
    const buttons = card.querySelectorAll("button");
    buttons.forEach((button) => { button.disabled = true; });
    const status = card.querySelector(".server-operation-status");
    if (status) status.textContent = label + " starting…";
    const body = { preset: String(server.id) };
    const cacheKey = "preset:" + String(server.id);
    try {
      const ensured = await ensureConnection(body, cacheKey);
      if (!ensured.ok) throw new Error(ensured.message || "Could not connect");
      const token = ensured.token || tokenForKey(cacheKey) || getToken();
      const res = await fetch(endpoint, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-Connection-Token": token,
        },
        body: JSON.stringify({ connection_token: token }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.success) throw new Error(data.message || ("HTTP " + res.status));
      if (status) status.textContent = label + " accepted · tracking duration";
      setTimeout(() => showOverview(), 1500);
    } catch (error) {
      if (status) status.textContent = label + " failed: " + ((error && error.message) || error);
      buttons.forEach((button) => { button.disabled = false; });
    }
  }

  async function openOverviewServer(server, forceRefresh) {
    const body = { preset: String(server.id), recent_limit: config.default_recent_limit || 10 };
    await startLoad(body, { forceRefresh: !!forceRefresh });
  }

  async function showOverview() {
    showView("overview");
    const grid = $("server-overview-grid");
    if (!grid) return;
    grid.textContent = "Checking configured servers…";
    try {
      const res = await fetch("/api/server-overview", { credentials: "same-origin" });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.message || "Unable to load overview");
      grid.textContent = "";
      (data.servers || []).forEach((server) => {
        const card = document.createElement("article");
        card.className = "server-overview-card " + (server.reachable ? "online" : "offline");
        const state = server.reachable ? "Online" : "Offline";
        const current = server.current_operation;
        card.innerHTML =
          "<h2></h2><p class=\"muted\"></p><p class=\"server-state\">" + state +
          (server.kodi_version ? " · " + server.kodi_version : "") + "</p>" +
          (current ? "<p class=\"muted\">" + current.operation + " · " + current.state + "</p>" : "") +
          "<div class=\"server-operation-status\"></div>" +
          "<div class=\"server-actions\"></div>";
        card.querySelector("h2").textContent = server.label || server.host;
        card.querySelector("p.muted").textContent = server.host;
        const actions = card.querySelector(".server-actions");
        const open = document.createElement("button");
        open.type = "button";
        open.className = "btn btn-primary";
        open.textContent = "Open dashboard";
        open.addEventListener("click", () => openOverviewServer(server, false));
        actions.appendChild(open);
        OVERVIEW_ACTIONS.forEach(([endpoint, label]) => {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "btn";
          button.textContent = label;
          button.addEventListener("click", () => runOverviewAction(server, endpoint, label, card));
          actions.appendChild(button);
        });
        const refresh = document.createElement("button");
        refresh.type = "button";
        refresh.className = "btn";
        refresh.textContent = "Refresh";
        refresh.addEventListener("click", () => openOverviewServer(server, true));
        actions.appendChild(refresh);
        grid.appendChild(card);
      });
    } catch (e) {
      grid.textContent = (e && e.message) || "Unable to load server overview";
    }
  }

  async function checkAuth() {
    try {
      const res = await fetch("/api/auth-status", { credentials: "same-origin" });
      const data = await res.json();
      if (data.enabled && !data.authenticated) {
        showView("login");
        return false;
      }
      const logout = $("logout-btn");
      if (logout) logout.hidden = !data.enabled;
      return true;
    } catch (e) {
      showView("login");
      return false;
    }
  }

  async function init() {
    const loginForm = $("login-form");
    if (loginForm) {
      loginForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const error = $("login-error");
        const res = await fetch("/api/login", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: $("login-user").value,
            password: $("login-pass").value,
          }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data.success) {
          error.textContent = data.message || "Login failed";
          error.hidden = false;
          return;
        }
        error.hidden = true;
        location.reload();
      });
    }
    const authenticated = await checkAuth();
    if (!authenticated) return;
    try {
      const res = await fetch("/api/config");
      config = await res.json();
    } catch (e) {
      config = { presets: [], default_recent_limit: 10, recent_limit_options: [5, 10, 20, 50] };
    }
    const sel = $("recent-limit-select");
    if (sel && config.default_recent_limit) sel.value = String(config.default_recent_limit);

    $("load-btn").addEventListener("click", async () => {
      if (loadInProgress) return;
      const body = buildCustomServerPayload();
      recentCustomSave(body);
      try {
        await startLoad(body);
      } catch (e) {
        loadInProgress = false;
        showLoadError((e && e.message) || String(e));
      }
    });
    $("load-error-home-btn").addEventListener("click", () => {
      resetLoadError();
      loadInProgress = false;
      clearStatus();
      const loadBtn = $("load-btn");
      if (loadBtn) loadBtn.disabled = false;
      showOverview();
    });
    $("switch-server-link").addEventListener("click", (e) => {
      e.preventDefault();
      loadInProgress = false;
      stopPolling();
      clearStatus();
      setLibraryActionsEnabled(false);
      const loadBtn = $("load-btn");
      if (loadBtn) loadBtn.disabled = false;
      showOverview();
    });
    $("refresh-btn").addEventListener("click", () => refreshDashboard());
    $("update-video-btn").addEventListener("click", () =>
      libraryAction("/api/update-video-library", "Update Video Library", $("update-video-btn"))
    );
    $("update-audio-btn").addEventListener("click", () =>
      libraryAction("/api/update-audio-library", "Update Audio Library", $("update-audio-btn"))
    );
    $("clean-video-btn").addEventListener("click", () =>
      libraryAction("/api/clean-video-library", "Clean Video Library", $("clean-video-btn"))
    );
    $("clean-music-btn").addEventListener("click", () =>
      libraryAction("/api/clean-music-library", "Clean Music Library", $("clean-music-btn"))
    );
    $("library-action-status-close").addEventListener("click", clearStatus);
    $("recent-limit-select").addEventListener("change", changeRecentLimit);
    $("logout-btn").addEventListener("click", async () => {
      await fetch("/api/logout", { method: "POST", credentials: "same-origin" });
      setToken("");
      showView("login");
    });

    const hostEl = $("custom-host");
    const wrap = document.querySelector(".custom-host-wrap");
    const dd = $("custom-recent-dropdown");
    if (hostEl && wrap && dd) {
      hostEl.addEventListener("focus", () => {
        refreshRecentDropdown();
        dd.hidden = recentCustomLoad().length === 0;
      });
      hostEl.addEventListener("keydown", (ev) => {
        if (ev.key === "Escape") dd.hidden = true;
      });
      wrap.addEventListener("focusout", () => {
        setTimeout(() => {
          if (!wrap.matches(":focus-within")) dd.hidden = true;
        }, 0);
      });
    }

    const overlay = $("image-overlay");
    overlay.addEventListener("click", () => {
      overlay.classList.remove("visible", "episode-zoom");
      $("overlay-image").src = "";
    });
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape" && overlay.classList.contains("visible")) {
        overlay.classList.remove("visible", "episode-zoom");
        $("overlay-image").src = "";
      }
    });

    // 24h auto-refresh
    setTimeout(() => {
      if (getToken()) refreshDashboard();
    }, 24 * 60 * 60 * 1000);

    // Hash #reload uses stored token
    if (location.hash === "#reload" && getToken()) {
      history.replaceState(null, "", location.pathname);
      await refreshDashboard();
      return;
    }

    await showOverview();
  }

  init();
})();
