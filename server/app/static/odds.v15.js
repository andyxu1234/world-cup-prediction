"use strict";

var API = "/api/v1/odds";
var $ = function(sel) { return document.querySelector(sel); };
var $$ = function(sel) { return Array.from(document.querySelectorAll(sel)); };

function getToken() {
  var fromUrl = new URLSearchParams(location.search).get("token");
  if (fromUrl) { localStorage.setItem("odds_token", fromUrl); return fromUrl; }
  return localStorage.getItem("odds_token") || "";
}
function setTokenState() {
  var t = getToken();
  $("#token").value = t;
  var st = $("#tokenState");
  st.textContent = t ? "READY" : "MISSING";
  st.style.color = t ? "var(--green)" : "var(--red)";
}
function toast(msg) {
  var el = $("#toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(function() { el.classList.remove("show"); }, 4000);
}
function fmtMoney(n) {
  if (n == null) return "-";
  var v = Number(n).toFixed(0);
  return (n >= 0 ? "+" : "") + v;
}
function clsMoney(n) {
  if (n == null) return "";
  return n >= 0 ? "pos" : "neg";
}

/* Multi-Select */
function createMultiSelect(container, opts) {
  container.classList.add("ms");
  container.innerHTML =
    '<button type="button" class="ms-toggle"><span class="ms-pill"></span></button>' +
    '<div class="ms-panel" hidden>' +
    '<input type="text" class="ms-search" placeholder="Search..." />' +
    '<div class="ms-actions"><button type="button" data-act="all">All</button><button type="button" data-act="none">Clear</button></div>' +
    '<div class="ms-options"></div></div>';
  var toggle = container.querySelector(".ms-toggle");
  var toggleText = container.querySelector(".ms-pill");
  var panel = container.querySelector(".ms-panel");
  var searchEl = container.querySelector(".ms-search");
  var optionsEl = container.querySelector(".ms-options");
  var selected = new Set();
  var options = [];
  var query = "";

  function renderToggle() {
    if (selected.size === 0) { toggleText.textContent = opts.placeholder || "All"; }
    else if (selected.size === 1) {
      var o = options.find(function(x) { return x.id === [...selected][0]; });
      toggleText.textContent = o ? o.label : "Selected " + selected.size;
    } else { toggleText.textContent = "Selected " + selected.size; }
  }
  function buildOptions() {
    var q = query.trim().toLowerCase();
    var filtered = q ? options.filter(function(o) { return String(o.label).toLowerCase().includes(q); }) : options;
    if (!filtered.length) {
      optionsEl.innerHTML = '<div class="ms-empty">No matches</div>';
      return;
    }
    optionsEl.innerHTML = filtered.map(function(o) {
      var checked = selected.has(o.id) ? "checked" : "";
      return '<label class="ms-opt ' + (checked ? 'checked' : '') + '"><input type="checkbox" value="' + o.id + '" ' + checked + '/> <span>' + o.label + '</span></label>';
    }).join("");
  }
  function sync() { renderToggle(); buildOptions(); }
  toggle.addEventListener("click", function(e) {
    e.stopPropagation();
    panel.hidden = !panel.hidden;
    container.classList.toggle("open", !panel.hidden);
    if (!panel.hidden) { query = ""; searchEl.value = ""; buildOptions(); setTimeout(function() { searchEl.focus(); }, 30); }
  });
  document.addEventListener("click", function(e) {
    if (!container.contains(e.target)) { panel.hidden = true; container.classList.remove("open"); }
  });
  panel.querySelector('[data-act="all"]').addEventListener("click", function() {
    options.forEach(function(o) { selected.add(o.id); }); sync(); if (opts.onChange) opts.onChange();
  });
  panel.querySelector('[data-act="none"]').addEventListener("click", function() {
    selected.clear(); sync(); if (opts.onChange) opts.onChange();
  });
  searchEl.addEventListener("click", function(e) { e.stopPropagation(); });
  searchEl.addEventListener("input", function(e) { query = e.target.value; buildOptions(); });
  optionsEl.addEventListener("change", function(e) {
    var id = Number(e.target.value);
    var label = e.target.closest(".ms-opt");
    if (e.target.checked) { selected.add(id); if (label) label.classList.add("checked"); }
    else { selected.delete(id); if (label) label.classList.remove("checked"); }
    renderToggle(); if (opts.onChange) opts.onChange();
  });
  renderToggle();
  return {
    setOptions: function(list) { options = list; sync(); },
    setSelected: function(ids) { selected.clear(); (ids || []).forEach(function(id) { selected.add(id); }); sync(); },
    getValues: function() { return [...selected]; },
    getParam: function() { return [...selected].join(","); },
  };
}

var msLeague = createMultiSelect($("#ms-league"), { placeholder: "All Leagues" });
var msLeagueBt = createMultiSelect($("#ms-league-bt"), { placeholder: "All Leagues" });

async function loadLeagues() {
  try {
    var data = await api("/leagues");
    var opts = (data || []).map(function(l) {
      return { id: l.id, label: l.cn_name + (l.country ? "(" + l.country + ")" : "") + " #" + l.id };
    });
    msLeague.setOptions(opts);
    msLeagueBt.setOptions(opts);
  } catch (_) {}
}

async function loadBookmakers() {
  try {
    var data = await api("/bookmakers");
    var rows = data || [];
    var sel = $("#bt_bookmaker");
    sel.innerHTML = rows.map(function(b) { return '<option value="' + b.id + '">' + b.name + " (" + b.id + ")</option>"; }).join("");
    if (rows.some(function(b) { return b.id === 4; })) sel.value = "4";
    else if (rows.length) sel.value = String(rows[0].id);
  } catch (_) {}
}

async function api(path, params, method) {
  method = method || "GET";
  var url = new URL(API + path, location.origin);
  if (params) Object.entries(params).forEach(function(_a) {
    var k = _a[0], v = _a[1];
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
  });
  var res = await fetch(url.toString(), {
    method: method,
    headers: { "X-Access-Token": getToken() },
  });
  if (res.status === 401) { toast("Invalid token"); throw new Error("401"); }
  if (!res.ok) {
    var txt = await res.text();
    toast("Request failed: " + res.status + " " + txt.slice(0, 120));
    throw new Error("HTTP " + res.status);
  }
  return res.json();
}

/* Tab Switching */
$$(".tab").forEach(function(btn) {
  btn.addEventListener("click", function() {
    $$(".tab").forEach(function(b) { b.classList.remove("active"); });
    $$(".panel").forEach(function(p) { p.classList.remove("active"); });
    btn.classList.add("active");
    $("#tab-" + btn.dataset.tab).classList.add("active");
  });
});

/* Token */
$("#saveToken").addEventListener("click", function() {
  localStorage.setItem("odds_token", $("#token").value.trim());
  setTokenState();
  toast("Token saved");
});
setTokenState();

/* Theme Toggle */
function initTheme() {
  var saved = localStorage.getItem("odds_theme") || "dark";
  document.body.classList.add(saved);
  updateThemeIcon(saved);
}
function toggleTheme() {
  document.body.classList.add("theme-transitioning");
  var isDark = document.body.classList.contains("dark");
  var removeCls = isDark ? "dark" : "light";
  var addCls = isDark ? "light" : "dark";
  document.body.classList.remove(removeCls);
  document.body.classList.add(addCls);
  localStorage.setItem("odds_theme", addCls);
  updateThemeIcon(addCls);
  setTimeout(function() { document.body.classList.remove("theme-transitioning"); }, 400);
}
function updateThemeIcon(theme) {
  var icon = document.querySelector("#themeToggle .theme-icon");
  if (icon) icon.textContent = theme === "dark" ? "D" : "L";
}
$("#themeToggle").addEventListener("click", toggleTheme);

/* ===== MATCH LIST ===== */
var RESULT_LABEL_CN = { home_win: "Home", draw: "Draw", away_win: "Away" };

function escapeHtml(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, function(c) { return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]; });
}

/* 将 UTC naive 时间字符串转换为北京时间（UTC+8）*/
function toBJTime(utcStr) {
  if (!utcStr) return "-";
  // 按 UTC 解析，避免本地时区干扰
  var m = String(utcStr).match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);
  if (!m) return String(utcStr).slice(0, 16).replace("T", " ");
  var d = new Date(Date.UTC(
    parseInt(m[1], 10), parseInt(m[2], 10) - 1, parseInt(m[3], 10),
    parseInt(m[4], 10), parseInt(m[5], 10)
  ));
  d.setUTCMinutes(d.getUTCMinutes() + 8 * 60); // +8h
  return d.getUTCFullYear() + '-' + String(d.getUTCMonth() + 1).padStart(2, '0') + '-' + String(d.getUTCDate()).padStart(2, '0') + ' ' + String(d.getUTCHours()).padStart(2, '0') + ':' + String(d.getUTCMinutes()).padStart(2, '0');
}

async function loadMatches() {
  var params = {};
  var lg = msLeague.getParam();
  var st = $("#f_status").value;
  var sort = $("#f_sort").value || "asc";
  var sd = $("#f_start_date").value;
  var ed = $("#f_end_date").value;
  if (lg) params.league_id = lg;
  if (st) params.status = st;
  if (sort) params.sort_order = sort;
  if (sd) params.start_date = sd;
  if (ed) params.end_date = ed;

  var container = $("#matchContainer");
  var loading = $("#matchLoading");
  var empty = $("#matchEmpty");
  container.innerHTML = "";
  empty.hidden = true;
  loading.hidden = false;

  try {
    var data = await api("/matches", params);
    loading.hidden = true;
    if (!data.length) {
      empty.hidden = false;
      return;
    }
    renderMatchCards(data);
  } catch (e) {
    loading.hidden = true;
    if (e.message === "401") return;
    container.innerHTML = '<div class="empty-state">Failed to load</div>';
  }
}

function renderConsensusChips(summary) {
  var s = summary || { total: 0, home_win: 0, draw: 0, away_win: 0 };
  if (!s.total) return '<span class="muted" style="color:var(--text-muted);font-size:12px">No AI data</span>';

  var entries = [
    { k: "home_win", n: s.home_win },
    { k: "draw", n: s.draw },
    { k: "away_win", n: s.away_win },
  ];
  var max = Math.max.apply(null, entries.map(function(e) { return e.n; }));
  var maxEntry = entries.find(function(e) { return e.n === max && max > 0; });
  var pct = max > 0 ? Math.round((max / s.total) * 100) : 0;

  var chips = entries.map(function(e) {
    var cls = e.n === max && max > 0 ? "consensus-chip majority" : "consensus-chip";
    return '<span class="' + cls + '">' + RESULT_LABEL_CN[e.k] + ' <b>' + e.n + '</b></span>';
  }).join("");

  var sumPctHome = s.total ? Math.round((s.home_win / s.total) * 100) : 0;
  var sumPctDraw = s.total ? Math.round((s.draw / s.total) * 100) : 0;
  var sumPctAway = s.total ? Math.round((s.away_win / s.total) * 100) : 0;

  return '<div class="consensus-majority-line">'
    + (maxEntry ? '<b>' + RESULT_LABEL_CN[maxEntry.k] + '</b> majority' : "Divided")
    + '<span class="consensus-pct-badge">' + pct + '%</span></div>'
    + '<div class="consensus-chips">' + chips + '</div>'
    + '<div class="consensus-total">' + s.total + ' votes</div>'
    + '<div class="consensus-bar-track">'
    + '<div class="consensus-bar-home" style="width:' + sumPctHome + '%"></div>'
    + '<div class="consensus-bar-draw" style="width:' + sumPctDraw + '%"></div>'
    + '<div class="consensus-bar-away" style="width:' + sumPctAway + '%"></div></div>';
}

function renderMatchCards(rows) {
  var container = $("#matchContainer");
  container.innerHTML = rows.map(function(m, i) {
    var safeHome = escapeHtml(m.home);
    var safeAway = escapeHtml(m.away);
    var status = m.status || "unknown";
    var consensusHtml = renderConsensusChips(m.predictions_summary);
    var timeStr = m.match_time ? m.match_time.slice(0, 16).replace("T", "  ") : "-";
    var leagueStr = m.league_name ? escapeHtml(m.league_name) : "";
    var roundStr = m.round ? escapeHtml(m.round) : "";
    var delay = Math.min(i * 40, 600);

    // 已结束比赛显示比分 + match_id + highlightly_id
    var statusHtml;
    var idLabel = '<span class="match-id-label">#' + m.match_id +
                  (m.highlightly_id ? ' · HL:' + m.highlightly_id : '') + '</span>';
    if (status === "finished" && m.home_score != null && m.away_score != null) {
      statusHtml = '<span class="match-status" data-status="finished">'
        + 'finished ' + m.home_score + ':' + m.away_score
        + ' ' + idLabel + '</span>';
    } else {
      statusHtml = '<span class="match-status" data-status="' + status + '">' + status
        + ' ' + idLabel + '</span>';
    }
    return '<div class="match-card" data-mid="' + m.match_id + '" style="animation-delay:' + delay + 'ms">'
      + '<div class="match-card-header">'
      + '<span class="match-time">'
      + (leagueStr ? '<span class="match-league">' + leagueStr + '</span>' : "")
      + (roundStr ? '<span class="match-round">' + roundStr + '</span> ' : "")
      + timeStr + '</span>'
      + statusHtml + '</div>'
      + '<div class="match-card-body"><div class="match-teams">'
      + '<div class="team-block home"><span class="team-name">' + safeHome + '</span></div>'
      + '<div class="vs-divider"><span class="vs-text">VS</span><span class="vs-line"></span></div>'
      + '<div class="team-block away"><span class="team-name">' + safeAway + '</span></div>'
      + '</div></div>'
      + '<div class="match-card-footer">'
      + '<div class="card-consensus">' + consensusHtml + '</div>'
      + '<button class="btn-dossier" data-mid="' + m.match_id + '" data-action="dossier">'
      + '<span>AI Dossier</span> <span class="dossier-arrow">DOWN</span></button>'
      + '</div></div>'
      + '<div class="ai-dossier" data-mid="' + m.match_id + '" data-open="false">'
      + '<div class="dossier-inner"></div></div>';
  }).join("");

  container.querySelectorAll(".match-card").forEach(function(el) {
    el.addEventListener("click", function() { toggleDossier(el); });
  });
  container.querySelectorAll("[data-action='dossier']").forEach(function(el) {
    el.addEventListener("click", function(e) { e.stopPropagation(); toggleDossier(el); });
  });
}

/* AI Dossier Toggle */
async function toggleDossier(trigger) {
  var mid = Number(trigger.dataset.mid);
  var dossier = document.querySelector('.ai-dossier[data-mid="' + mid + '"]');
  if (!dossier) return;

  var card = trigger.closest(".match-card") || document.querySelector('.match-card[data-mid="' + mid + '"]');
  var btn = trigger.matches("[data-action='dossier']") ? trigger : (card ? card.querySelector("[data-action='dossier']") : null);
  var arrow = btn ? btn.querySelector(".dossier-arrow") : null;
  var textSpan = btn ? btn.querySelector("span:first-child") : null;

  if (dossier.dataset.open === "true") {
    dossier.dataset.open = "false";
    dossier.style.maxHeight = "0";
    if (arrow) arrow.textContent = "DOWN";
    if (textSpan) textSpan.textContent = "AI Dossier";
    if (card) card.classList.remove("is-open");
    return;
  }

  var inner = dossier.querySelector(".dossier-inner");

  if (!dossier.dataset.loaded) {
    if (btn) { btn.disabled = true; btn.innerHTML = '<span>Decrypting...</span>'; }
    try {
      var [detail, pmData] = await Promise.all([
        api('/match/' + mid),
        api('/match/' + mid + '/polymarket')
      ]);
      inner.innerHTML = renderDossier(mid, detail.predictions || [], detail.prediction_summary, detail.odds_1x2, pmData);
      var closeBtn = inner.querySelector(".dossier-close");
      if (closeBtn) {
        closeBtn.addEventListener("click", function() {
          var t = document.querySelector('[data-action="dossier"][data-mid="' + mid + '"]');
          if (t) t.click();
        });
      }
      dossier.dataset.loaded = "1";
    } catch (e) {
      inner.innerHTML = '<p style="color:var(--text-dim);padding:18px;text-align:center">Failed</p>';
      if (btn) btn.disabled = false;
      dossier.dataset.open = "true";
      if (card) card.classList.add("is-open");
      requestAnimationFrame(function() { dossier.style.maxHeight = dossier.scrollHeight + "px"; });
      return;
    }
    if (btn) btn.disabled = false;
  }

  dossier.dataset.open = "true";
  if (card) card.classList.add("is-open");
  requestAnimationFrame(function() { dossier.style.maxHeight = dossier.scrollHeight + "px"; });
  if (arrow) arrow.textContent = "UP";
  if (textSpan) textSpan.textContent = "Close Dossier";
  dossier.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function avatarInitials(name) {
  if (!name) return "AI";
  var s = String(name).trim();
  if (/[一-龥]/.test(s)) {
    var han = s.replace(/[^一-龥]/g, "");
    return han.slice(0, 2) || "AI";
  }
  var parts = s.split(/[\s\-_./]+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  var cleaned = s.replace(/[^A-Za-z0-9]/g, "");
  return (cleaned.slice(0, 2) || "AI").toUpperCase();
}

function renderDossier(mid, preds, summary, odds1x2, pmData) {
  var hasPreds = preds && preds.length > 0;
  var hasPM = pmData && pmData.linked && pmData.data;
  if (!hasPreds && !summary && !odds1x2 && !hasPM) {
    return '<p style="color:var(--text-dim);padding:18px;text-align:center">No data</p>';
  }

  var intelRows = [];

  if (hasPreds) {
    // 软概率分布计算（与后端 Polymarket 分析逻辑一致）
    var PRIOR = { home: 0.45, draw: 0.27, away: 0.28 };
    var RESULT_MAP = { home_win: "home", draw: "draw", away_win: "away" };
    var acc = { home: 0, draw: 0, away: 0 };
    var nValid = 0;
    preds.forEach(function(p) {
      var rk = RESULT_MAP[p.result];
      if (!rk) return;
      nValid++;
      var c = (p.confidence != null && p.confidence !== "") ? Number(p.confidence) / 10.0 : 0.5;
      c = Math.max(0, Math.min(1, c));
      var rem = 1 - c;
      var norm = 1 - PRIOR[rk];
      Object.keys(PRIOR).forEach(function(k) {
        if (k === rk) { acc[k] += c; }
        else { acc[k] += rem * (PRIOR[k] / norm); }
      });
    });
    var total = nValid;
    var pctHome = total ? Math.round((acc.home / total) * 100) : 0;
    var pctDraw = total ? Math.round((acc.draw / total) * 100) : 0;
    var pctAway = total ? Math.round((acc.away / total) * 100) : 0;
    var sortedSoft = Object.entries(acc).sort(function(a, b) { return b[1] - a[1]; });
    var softMajorityVal = sortedSoft[0] ? sortedSoft[0][1] : 0;
    var softMajorityLabel = sortedSoft[0] ? (sortedSoft[0][0] === "home" ? "Home" : sortedSoft[0][0] === "draw" ? "Draw" : "Away") : "Divided";
    var agreementPct = total ? Math.round((softMajorityVal / total) * 100) : 0;

    var consensusScoreHtml = "";
    if (summary && summary.score_home != null && summary.score_away != null) {
      var mainScore = summary.score_home + ':' + summary.score_away;
      var altScore = (summary.score_alt_home != null && summary.score_alt_away != null)
        ? summary.score_alt_home + ':' + summary.score_alt_away : "";
      consensusScoreHtml = '<span class="intel-consensus-score">' + mainScore + '</span>'
        + (altScore ? ' <span class="intel-consensus-alt">alt ' + altScore + '</span>' : '');
    }

    intelRows.push('<div class="intel-row">'
      + '<div class="intel-label">CONSENSUS</div>'
      + '<div class="intel-body">'
      + (consensusScoreHtml ? '<div class="intel-consensus-top">' + consensusScoreHtml + '</div>' : '')
      + '<div class="intel-bar-track">'
      + '<div class="bar-home" style="width:' + pctHome + '%"></div>'
      + '<div class="bar-draw" style="width:' + pctDraw + '%"></div>'
      + '<div class="bar-away" style="width:' + pctAway + '%"></div></div>'
      + '<div class="intel-dist">'
      + '<span class="intel-major">' + escapeHtml(softMajorityLabel) + ' <b>' + agreementPct + '%</b></span>'
      + ' | Home ' + pctHome + '% | Draw ' + pctDraw + '% | Away ' + pctAway + '%'
      + '</div></div></div>');
  }

  /* ── ODDS 独立模块（多日期对比） ── */
  var oddsHtml = odds1x2 && odds1x2.snapshots && odds1x2.snapshots.length ? renderOddsModule(odds1x2) : "";

  if (summary) {
    var parts = [];
    if (summary.short_summary) parts.push('<div class="intel-short">' + escapeHtml(summary.short_summary) + '</div>');
    if (summary.summary) parts.push('<div class="intel-text">' + escapeHtml(summary.summary) + '</div>');
    if (parts.length) {
      intelRows.push('<div class="intel-row intel-row-summary">'
        + '<div class="intel-label">SUMMARY</div>'
        + '<div class="intel-body">' + parts.join("") + '</div></div>');
    }
  }

  var intelHtml = intelRows.length ? '<div class="dossier-intel">' + intelRows.join("") + '</div>' : "";
  var predTableHtml = "";

  if (hasPreds) {
    var items = [];

    // 预测汇总作为第一行
    if (summary && (summary.score_home != null || summary.short_summary)) {
      var sc = (summary.score_home != null && summary.score_away != null) ? summary.score_home + ":" + summary.score_away : "-";
      var scAlt = (summary.score_alt_home != null && summary.score_alt_away != null)
        ? summary.score_alt_home + ":" + summary.score_alt_away : "";
      var smConf = summary.confidence != null ? summary.confidence : null;
      // 从比分推算赛果
      var smResult = null;
      if (summary.score_home != null && summary.score_away != null) {
        smResult = summary.score_home > summary.score_away ? "home_win" : (summary.score_home < summary.score_away ? "away_win" : "draw");
      }
      var smResultCls = smResult ? "result-pill " + smResult : "result-pill";
      var smResultLabel = smResult ? RESULT_LABEL_CN[smResult] : "-";
      var smAnalysis = summary.short_summary
        ? '<div class="dt-analysis">' + escapeHtml(summary.short_summary) + '</div>'
          + (summary.summary ? '<div class="dt-analysis dt-analysis-full">' + escapeHtml(summary.summary) + '</div>' : '')
        : (summary.summary ? '<div class="dt-analysis">' + escapeHtml(summary.summary) + '</div>' : '<div class="dt-analysis dt-analysis-empty">(no analysis)</div>');

      items.push('<tr class="dt-consensus-row">'
        + '<td class="dt-model"><div class="dt-model-inner">'
        + '<span class="dt-model-idx dt-idx-consensus">★</span>'
        + '<span class="dt-model-name dt-name-consensus">AI Consensus</span>'
        + '</div></td>'
        + '<td class="dt-conf dt-conf-consensus">' + (smConf != null ? smConf + '/10' : '-') + '</td>'
        + '<td class="dt-result"><span class="' + smResultCls + '">' + smResultLabel + '</span></td>'
        + '<td class="dt-score">' + sc + '</td>'
        + '<td class="dt-alt">' + scAlt + '</td>'
        + '<td class="dt-analysis-cell">' + smAnalysis + '</td></tr>');
    }

    preds.forEach(function(p, idx) {
      var resultCls = "result-pill " + (p.result || "none");
      var resultLabel = RESULT_LABEL_CN[p.result] || p.result || "-";
      var conf = (p.confidence != null && p.confidence !== "") ? Number(p.confidence) : null;
      var score = (p.score_home != null && p.score_away != null) ? p.score_home + ":" + p.score_away : "-";
      var altScore = (p.alt_score_home != null && p.alt_score_away != null)
        ? p.alt_score_home + ":" + p.alt_score_away + (p.alt_score_prob != null ? " " + Math.round(p.alt_score_prob * 100) + "%" : "") : "-";
      var analysis = p.analysis ? '<div class="dt-analysis">' + escapeHtml(p.analysis) + '</div>' : '<div class="dt-analysis dt-analysis-empty">(no analysis)</div>';

      items.push('<tr>'
        + '<td class="dt-model"><div class="dt-model-inner">'
        + '<span class="dt-model-idx">' + String(idx + 1).padStart(2, "0") + '</span>'
        + '<span class="dt-model-name">' + escapeHtml(p.model_name || "Unnamed") + '</span>'
        + '</div></td>'
        + '<td class="dt-conf">' + (conf != null ? conf + '/10' : '-') + '</td>'
        + '<td class="dt-result"><span class="' + resultCls + '">' + escapeHtml(resultLabel) + '</span></td>'
        + '<td class="dt-score">' + score + '</td>'
        + '<td class="dt-alt">' + altScore + '</td>'
        + '<td class="dt-analysis-cell">' + analysis + '</td></tr>');
    });
    predTableHtml = '<div class="dossier-table-wrap"><table class="dossier-table"><thead><tr>'
      + '<th>Model</th><th>Conf</th><th>Outcome</th><th>Score</th><th>Alt</th><th>Analysis</th>'
      + '</tr></thead><tbody>' + items.join("") + '</tbody></table></div>';
  }

  var pmHtml = hasPM ? renderPMInDossier(pmData.data) : "";
  if (pmData && !pmData.linked) {
    pmHtml = '<div class="dossier-pm-note">◈ Polymarket 市场数据：<span class="muted">未关联</span></div>';
  }

  return '<div class="dossier-header">'
    + '<div class="dossier-header-left">'
    + '<span class="dossier-icon">*</span>'
    + '<span class="dossier-title">AI Model Predictions</span>'
    + (hasPreds ? '<span class="dossier-badge">' + preds.length + ' Models</span>' : "")
    + '</div>'
    + '<button type="button" class="dossier-close" data-mid="' + mid + '">X Close</button></div>'
    + intelHtml + oddsHtml + pmHtml + predTableHtml;
}

/* ── ODDS 多日期对比模块 ── */
function renderOddsModule(odds1x2) {
  var snaps = odds1x2.snapshots;
  if (!snaps || !snaps.length) return "";
  var num = snaps.length;

  // 收集所有博彩公司名
  var bkSet = {};
  snaps.forEach(function(s) { Object.keys(s.bookmakers || {}).forEach(function(n) { bkSet[n] = true; }); });
  var bkNames = Object.keys(bkSet).sort();

  // 渲染单个单元格（含 delta 箭头）
  function cell(val, prev) {
    if (val == null) return '<span class="od-muted">-</span>';
    var d = val.toFixed(2);
    if (prev == null) return d;
    var diff = val - prev;
    if (Math.abs(diff) < 0.005) return d;
    var arrow = diff > 0 ? '↑' : '↓';
    var cls = diff > 0 ? 'od-up' : 'od-down';
    return d + ' <span class="' + cls + '">' + arrow + '</span>';
  }

  // 趋势指示：比较首尾快照
  function trend(vLast, vFirst) {
    if (vLast == null || vFirst == null) return '<span class="od-muted">—</span>';
    var diff = vLast - vFirst;
    if (Math.abs(diff) < 0.005) return '<span class="od-muted">→</span>';
    return diff > 0
      ? '<span class="od-up">↗</span>'
      : '<span class="od-down">↘</span>';
  }

  var html = '<div class="odds-module">'
    + '<div class="odds-module-head">'
    + '<span class="odds-module-title">ODDS</span>'
    + '<span class="odds-module-count">' + bkNames.length + ' bookmakers</span>'
    + '<span class="odds-module-badge">' + num + ' snapshots</span>'
    + '</div>'
    + '<div class="odds-module-tbl-wrap"><table class="odds-module-tbl"><thead>';

  // 第一行表头：日期跨列
  html += '<tr><th rowspan="2">Bookmaker</th>';
  snaps.forEach(function(s, si) {
    var label = s.date.slice(5, 10);
    var cls = si === num - 1 ? ' od-date-latest' : '';
    html += '<th class="od-date' + cls + '" colspan="3">' + label + '</th>';
  });
  html += '<th rowspan="2" class="od-trend-th">Trend</th></tr>';

  // 第二行表头：H/D/A
  html += '<tr>';
  snaps.forEach(function() {
    html += '<th class="od-sub od-sub-h">H</th><th class="od-sub od-sub-d">D</th><th class="od-sub od-sub-a">A</th>';
  });
  html += '</tr></thead><tbody>';

  // 数据行
  bkNames.forEach(function(nm) {
    html += '<tr><td class="od-bk">' + escapeHtml(nm) + '</td>';
    var firstVals = {}, lastVals = {};
    snaps.forEach(function(s, si) {
      var b = (s.bookmakers || {})[nm] || {};
      var prev = si > 0 ? (snaps[si - 1].bookmakers || {})[nm] || {} : {};
      html += '<td class="od-cell od-home">' + cell(b.Home, prev.Home) + '</td>'
        + '<td class="od-cell od-draw">' + cell(b.Draw, prev.Draw) + '</td>'
        + '<td class="od-cell od-away">' + cell(b.Away, prev.Away) + '</td>';
      if (si === 0) { firstVals = { H: b.Home, D: b.Draw, A: b.Away }; }
      if (si === num - 1) { lastVals = { H: b.Home, D: b.Draw, A: b.Away }; }
    });
    html += '<td class="od-trend">'
      + 'H' + trend(lastVals.H, firstVals.H) + ' '
      + 'D' + trend(lastVals.D, firstVals.D) + ' '
      + 'A' + trend(lastVals.A, firstVals.A)
      + '</td></tr>';
  });

  // AVG 行
  html += '<tr class="od-avg-row"><td class="od-bk">AVG</td>';
  snaps.forEach(function(s, si) {
    var avg = s.avg || {};
    var prev = si > 0 ? snaps[si - 1].avg || {} : {};
    html += '<td class="od-cell od-home">' + cell(avg.Home, prev.Home) + '</td>'
      + '<td class="od-cell od-draw">' + cell(avg.Draw, prev.Draw) + '</td>'
      + '<td class="od-cell od-away">' + cell(avg.Away, prev.Away) + '</td>';
  });
  html += '<td class="od-trend"></td></tr>';

  html += '</tbody></table></div></div>';
  return html;
}

/* ── Polymarket 区块渲染（嵌入 dossier） ── */
function renderPMInDossier(d) {
  var html = '<div class="dossier-pm">';

  /* 头部 */
  html += '<div class="dossier-pm-head">'
    + '<span class="dossier-pm-icon">◈</span>'
    + '<span class="dossier-pm-title">Polymarket × AI 对比</span>'
    + '<span class="dossier-pm-count">' + (d.markets ? d.markets.length : 0) + ' Markets</span>'
    + '<span class="dossier-pm-sig"><span class="pm-sig-dot"></span>LINKED</span>'
    + '</div>';

  /* 市场报价卡片 */
  html += '<div class="dossier-pm-quotes">';
  (d.markets || []).forEach(function(mk) {
    var pctStr = mk.price != null ? (mk.price * 100).toFixed(1) + "%" : "-";
    var volStr = mk.volume != null ? '$' + mk.volume.toLocaleString() : "";
    html += '<div class="dpq dpq-' + mk.outcome + '">'
      + '<span class="dpq-lbl">' + paOutcomeLabel(mk.outcome) + '</span>'
      + '<span class="dpq-p">' + pctStr + '</span>'
      + (volStr ? '<span class="dpq-v">' + volStr + '</span>' : '')
      + '</div>';
  });
  html += '</div>';

  /* 对比表 */
  html += '<div class="dossier-pm-tbl-wrap"><table class="dossier-pm-tbl"><thead>'
    + '<tr><th>结果</th><th>AI概率</th><th>市场隐含</th>'
    + '<th class="pmt-yes" colspan="2">YES side</th>'
    + '<th class="pmt-no" colspan="2">NO side</th>'
    + '</tr><tr class="pmt-sub">'
    + '<th></th><th></th><th></th>'
    + '<th>价</th><th>EV</th><th>价</th><th>EV</th>'
    + '</tr></thead><tbody>';
  (d.bets || []).forEach(function(b) {
    if (!b.available) {
      html += '<tr><td class="pmt-o-' + b.outcome + '">' + b.label + '</td><td colspan="6" class="muted">市场无此腿价格</td></tr>';
      return;
    }
    html += '<tr>'
      + '<td class="pmt-o-' + b.outcome + '">' + b.label + '</td>'
      + '<td>' + paPct(b.ai_prob) + '</td>'
      + '<td>' + paPct(b.market_prob) + '</td>'
      + '<td>' + b.yes.price.toFixed(3) + '</td>'
      + (b.yes.ev != null
        ? '<td class="' + (b.yes.ev > 0 ? "pmt-pos" : "pmt-neg") + '">' + (b.yes.ev >= 0 ? "+" : "") + (b.yes.ev * 100).toFixed(1) + '%</td>'
        : '<td class="muted">-</td>')
      + '<td>' + b.no.price.toFixed(3) + '</td>'
      + (b.no.ev != null
        ? '<td class="' + (b.no.ev > 0 ? "pmt-pos" : "pmt-neg") + '">' + (b.no.ev >= 0 ? "+" : "") + (b.no.ev * 100).toFixed(1) + '%</td>'
        : '<td class="muted">-</td>')
      + '</tr>';
  });
  html += '</tbody></table></div>';

  /* 市场信息条 */
  html += '<div class="dossier-pm-info">'
    + 'Overround <b>' + ((d.overround || 0) * 100).toFixed(1) + '%</b>'
    + (d.event ? ' · ' + escapeHtml(d.event.title) : '')
    + '</div>';

  /* 正 EV 信号 */
  if (d.best_bets && d.best_bets.length) {
    html += '<div class="dossier-pm-signals">';
    d.best_bets.forEach(function(x) {
      html += '<div class="dps">'
        + '<span class="dps-pulse"></span>'
        + '<span class="dps-side dps-' + x.side.toLowerCase() + '">' + x.side + '</span>'
        + '<span class="dps-lbl">' + x.label + '</span>'
        + '<span class="dps-prc">@' + x.price.toFixed(3) + '</span>'
        + '<span class="dps-ev">EV ' + (x.ev * 100).toFixed(1) + '%</span>'
        + '<span class="dps-kl">Kelly ' + (x.kelly * 100).toFixed(0) + '%</span>'
        + '</div>';
    });
    html += '</div>';
  }

  html += '<div class="dossier-pm-dsc">⚠️ 非投资建议 · 市场价由真实资金博弈形成</div>';
  html += '</div>';
  return html;
}

$("#btnLoadMatches").addEventListener("click", loadMatches);

/* ===== BACKTEST ===== */
async function runBacktest() {
  var bm = $("#bt_bookmaker").value;
  var lg = msLeagueBt.getParam();
  var sd = $("#bt_start_date").value;
  var ed = $("#bt_end_date").value;
  var strategy = $("#bt_strategy").value;
  var bankroll = Number($("#bt_bankroll").value) || 10000;
  var kellyFrac = Number($("#bt_kelly_frac").value) || 0.25;
  var params = { bookmaker_id: bm, strategy: strategy, initial_bankroll: bankroll, kelly_fraction: kellyFrac };
  if (lg) params.league_id = lg;
  if (sd) params.start_date = sd;
  if (ed) params.end_date = ed;
  try {
    var data = await api("/backtest", params);
    renderBacktest(data);
  } catch (e) {}
}

function renderBacktest(data) {
  var strategy = $("#bt_strategy").value;
  var models = data.models || [];
  var details = data.details || [];
  var dg = data.diagnostics || {};
  var consensus = models.find(function(m) { return m.is_consensus; });
  var activeModels = models.filter(function(m) { return m.matches > 0; });
  var best = activeModels.filter(function(m) { return !m.is_consensus; }).sort(function(a, b) { return b.total_profit - a.total_profit; })[0];

  var showFixed = strategy === "fixed" || strategy === "both";
  var showKelly = strategy === "kelly" || strategy === "both";

  var fixedCards = "";
  if (showFixed) {
    fixedCards = '<div class="bt-card"><div class="k">Bookmaker</div><div class="v">' + (data.bookmaker_name || "#" + data.bookmaker_id) + '</div></div>'
      + '<div class="bt-card"><div class="k">Matches</div><div class="v">' + (dg.match_count ?? details.length) + '</div></div>'
      + '<div class="bt-card"><div class="k">Models</div><div class="v">' + activeModels.length + '</div></div>'
      + '<div class="bt-card"><div class="k">Best Fixed</div><div class="v ' + clsMoney(best ? best.total_profit : 0) + '">' + (best ? best.name + " " + fmtMoney(best.total_profit) : "-") + '</div></div>'
      + '<div class="bt-card"><div class="k">Consensus Fixed</div><div class="v ' + clsMoney(consensus ? consensus.total_profit : 0) + '">' + (consensus ? fmtMoney(consensus.total_profit) : "-") + '</div></div>';
  }

  var kellyCards = "";
  if (showKelly) {
    var bkModels = activeModels.filter(function(m) { return !m.is_consensus; }).sort(function(a, b) { return (b.kelly_profit || 0) - (a.kelly_profit || 0); });
    var bestKelly = bkModels[0];
    var cKelly = consensus ? (consensus.kelly_profit || 0) : 0;
    var bestKellyVal = bestKelly ? (bestKelly.kelly_profit || 0) : 0;
    var kellyBetsCount = activeModels.reduce(function(s, m) { return s + (m.kelly_bets || 0); }, 0);
    kellyCards = '<div class="bt-card"><div class="k">Init Bankroll</div><div class="v">' + Number(data.initial_bankroll || 10000).toFixed(0) + '</div></div>'
      + '<div class="bt-card"><div class="k">Kelly Fraction</div><div class="v">' + (data.kelly_fraction || 0.25) + '</div></div>'
      + '<div class="bt-card"><div class="k">Best Kelly</div><div class="v ' + clsMoney(bestKellyVal) + '">' + (bestKelly ? bestKelly.name + " " + fmtMoney(bestKellyVal) : "-") + '</div></div>'
      + '<div class="bt-card"><div class="k">Consensus Kelly</div><div class="v ' + clsMoney(cKelly) + '">' + (consensus ? fmtMoney(cKelly) : "-") + '</div></div>'
      + '<div class="bt-card"><div class="k">Kelly Bets</div><div class="v">' + kellyBetsCount + '</div></div>';
  }

  if (strategy === "both") {
    $("#btSummary").innerHTML = '<div class="bt-strategy-side">' + fixedCards + '</div><div class="bt-strategy-side">' + kellyCards + '</div>';
  } else if (strategy === "fixed") {
    $("#btSummary").innerHTML = fixedCards;
  } else {
    $("#btSummary").innerHTML = kellyCards;
  }

  var sortedModels = [...models].sort(function(a, b) {
    if (a.matches === 0 && b.matches > 0) return 1;
    if (a.matches > 0 && b.matches === 0) return -1;
    return b.total_profit - a.total_profit;
  });
  var kellyHeaders = showKelly ? '<th>Kelly Bets</th><th>Kelly Stake</th><th>Kelly PnL</th><th>Kelly ROI</th><th>Peak</th><th>DD</th>' : "";
  var rank = '<table><thead><tr><th>#</th><th>Model</th><th>M</th><th>W</th><th>W%</th><th>Stake</th><th>PnL</th><th>ROI</th>' + kellyHeaders + '<th>Curve</th></tr></thead><tbody>';
  sortedModels.forEach(function(m, i) {
    var kellyCells = "";
    if (showKelly) {
      kellyCells += '<td>' + (m.kelly_bets || 0) + '</td>'
        + '<td>' + (m.kelly_total_stake != null ? Number(m.kelly_total_stake).toFixed(0) : "-") + '</td>'
        + '<td class="' + clsMoney(m.kelly_profit) + '">' + fmtMoney(m.kelly_profit) + '</td>'
        + '<td class="' + clsMoney(m.kelly_roi) + '">' + (m.kelly_roi != null ? m.kelly_roi : "-") + '</td>'
        + '<td>' + (m.kelly_peak != null ? Number(m.kelly_peak).toFixed(0) : "-") + '</td>'
        + '<td>' + (m.kelly_dd != null ? m.kelly_dd : "-") + '</td>';
    }
    rank += '<tr>'
      + '<td>' + (m.matches === 0 ? "-" : i + 1) + '</td>'
      + '<td>' + (m.is_consensus ? "C " : "") + m.name + '</td>'
      + '<td>' + m.matches + '</td><td>' + m.correct + '</td><td>' + m.win_rate + '</td>'
      + '<td>' + (m.total_stake != null ? m.total_stake : m.matches * (data.stake || 100)) + '</td>'
      + '<td class="' + clsMoney(m.total_profit) + '">' + fmtMoney(m.total_profit) + '</td>'
      + '<td class="' + clsMoney(m.roi) + '">' + m.roi + '</td>'
      + kellyCells
      + '<td>' + (m.matches === 0 ? "-" : '<span class="clickable" data-name="' + m.name + '">V</span>') + '</td></tr>';
  });
  rank += "</tbody></table>";
  $("#btRankWrap").innerHTML = rank;
  $("#btRankWrap").querySelectorAll(".clickable").forEach(function(el) {
    el.addEventListener("click", function() { focusModel(el.dataset.name); });
  });

  renderBacktestChart(models, details);
  renderDetailTable(models, details);
}

function renderBacktestChart(models, details) {
  var el = $("#btChart");
  if (!details || !details.length) { el.innerHTML = '<p style="color:var(--text-dim);padding:20px;text-align:center">No backtest data</p>'; return; }
  if (el._chart) el._chart.dispose();
  var strategy = $("#bt_strategy").value;
  var showFixed = strategy === "fixed" || strategy === "both";
  var showKelly = strategy === "kelly" || strategy === "both";
  var cats = details.map(function(d) { return (d.match_time || "").slice(0, 10); });
  var palette = ["#b8975a","#e74c3c","#27ae60","#4b7fad","#8e44ad","#e67e22","#1abc9c","#c0392b","#2ecc71","#f39c12","#9b59b6","#16a085"];
  var series = [];
  models.forEach(function(m, idx) {
    var color = palette[idx % palette.length];
    if (showFixed) {
      var map = {};
      (m.cumulative || []).forEach(function(c) { map[c.match_id] = c.running; });
      series.push({ name: m.name, type: "line", showSymbol: false, connectNulls: true,
        lineStyle: { color: color }, itemStyle: { color: color },
        data: details.map(function(d) { return d.match_id in map ? map[d.match_id] : null; }) });
    }
    if (showKelly) {
      var kMap = {};
      (m.kelly_cumulative || []).forEach(function(c) { kMap[c.match_id] = c.running; });
      series.push({ name: m.name + " (Kelly)", type: "line", showSymbol: false, connectNulls: true,
        lineStyle: { type: "dashed", color: color }, itemStyle: { color: color },
        data: details.map(function(d) { return d.match_id in kMap ? kMap[d.match_id] : null; }) });
    }
  });
  var chart = echarts.init(el, "dark");
  var points = cats.length;
  var defaultRange = Math.min(60, points);
  var dataZoomStart = points > defaultRange ? ((points - defaultRange) / points) * 100 : 0;
  var opt = {
    backgroundColor: "transparent",
    tooltip: { trigger: "axis", confine: true },
    legend: { type: "scroll", top: 0, textStyle: { fontSize: 11 } },
    grid: { left: 60, right: 30, bottom: 80, top: 44, containLabel: false },
    xAxis: {
      type: "category", data: cats,
      axisLabel: { rotate: 45, fontSize: 11, interval: Math.floor(cats.length / 8) || 0 },
      axisTick: { alignWithLabel: true },
    },
    yAxis: { type: "value", name: "PnL (¥)", nameTextStyle: { fontSize: 12 }, splitLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } } },
    dataZoom: [
      { type: "inside", start: dataZoomStart, end: 100 },
      { type: "slider", height: 22, bottom: 4, borderColor: "rgba(255,255,255,0.1)",
        fillerColor: "rgba(184,151,90,0.15)", handleStyle: { color: "#b8975a" },
        textStyle: { fontSize: 10, color: "rgba(255,255,255,0.4)" } }
    ],
    series: series,
  };
  chart.setOption(opt);
  window.addEventListener("resize", function() { chart.resize(); });
  el._chart = chart;
}

function renderDetailTable(models, details) {
  var wrap = $("#btDetailWrap");
  var strategy = $("#bt_strategy").value;
  var showKelly = strategy === "kelly" || strategy === "both";
  var headers = models.map(function(m) { return '<th colspan="' + (showKelly ? 2 : 1) + '">' + (m.is_consensus ? "C " : "") + m.name + '</th>'; }).join("");
  var subHeaders = models.map(function(m) { return showKelly ? '<th>Fixed</th><th>Kelly</th>' : '<th>Fixed</th>'; }).join("");
  var html = '<table><thead><tr><th rowspan="2">Date</th><th rowspan="2">Match</th><th rowspan="2">Result</th>' + headers + '</tr><tr>' + subHeaders + '</tr></thead><tbody>';
  var rowsDesc = [...details].reverse();
  for (var di = 0; di < rowsDesc.length; di++) {
    var d = rowsDesc[di];
    html += '<tr><td>' + (d.match_time ? d.match_time.slice(0, 10) : "-") + '</td><td>' + d.home + ' v ' + d.away + '</td><td>' + (d.result || "-") + '</td>';
    for (var mi = 0; mi < models.length; mi++) {
      var m = models[mi];
      var cell = m.is_consensus ? d.consensus : (d.per_model || {})[m.name];
      if (!cell) { html += showKelly ? "<td>-</td><td>-</td>" : "<td>-</td>"; continue; }
      if (cell.no_odds || cell.odd == null) {
        html += showKelly
          ? '<td>' + (cell.pick || "-") + '<br><span style="font-size:10px">no odds</span></td><td>-</td>'
          : '<td>' + (cell.pick || "-") + '<br><span style="font-size:10px">no odds</span></td>';
        continue;
      }
      var fixedCell = '<td class="' + clsMoney(cell.profit) + '">' + cell.pick + '<br>' + cell.odd + '<br>' + (cell.profit >= 0 ? "+" : "") + Number(cell.profit).toFixed(2) + '</td>';
      var kellyHtml = "";
      if (showKelly) {
        if (cell.kelly_skip) {
          kellyHtml = '<td class="muted" style="font-size:11px;color:var(--text-muted)">skip</td>';
        } else {
          var kBetAmt = cell.kelly_bet != null ? Number(cell.kelly_bet).toFixed(0) : "-";
          var kProfit = cell.kelly_profit != null ? cell.kelly_profit : 0;
          kellyHtml = '<td class="' + clsMoney(kProfit) + '" style="font-size:11px">' + kBetAmt + '<br>' + (kProfit >= 0 ? "+" : "") + Number(kProfit).toFixed(2) + '</td>';
        }
      }
      html += fixedCell + kellyHtml;
    }
    html += "</tr>";
  }
  html += "</tbody></table>";
  wrap.innerHTML = html;
}

function focusModel(name) {
  var chart = $("#btChart")._chart;
  if (!chart) return;
  var opt = chart.getOption();
  if (!opt.legend || !opt.legend[0]) return;
  var target = opt.legend[0].data.indexOf(name);
  if (target < 0) return;
  chart.dispatchAction({ type: "legendSelect", name: name });
  opt.legend[0].data.forEach(function(n, i) { if (i !== target) chart.dispatchAction({ type: "legendUnSelect", name: n }); });
  toast("Focused: " + name);
}

$("#btnRunBacktest").addEventListener("click", runBacktest);

/* Strategy toggle */
function toggleKellyVisibility() {
  var s = $("#bt_strategy").value;
  var kp = $("#bt_kelly_params");
  var kf = $("#bt_kelly_fraction_group");
  if (s === "fixed") {
    kp.style.display = "none";
    kf.style.display = "none";
  } else {
    kp.style.display = "";
    kf.style.display = "";
  }
}
$("#bt_strategy").addEventListener("change", toggleKellyVisibility);
toggleKellyVisibility();

/* ===== POLYMARKET LINKAGE ===== */
var pmAllEvents = [];  // 原始数据，用于前端筛选
var pmSeriesOptions = [];

async function loadPMEvents() {
  var linked = $("#pm_linked").value;
  var series = $("#pm_series").value;
  var status = $("#pm_status").value;
  var sort = $("#pm_sort").value || "desc";
  var params = {};
  if (linked) params.linked = linked;
  if (series) params.series_id = series;
  if (status) params.status = status;
  if (sort) params.sort_order = sort;

  var wrap = $("#pmTableWrap");
  wrap.innerHTML = '<div class="loading-state"><div class="loader-ring"></div><span>Loading Polymarket events…</span></div>';

  try {
    var data = await api("/polymarket", params);
    pmAllEvents = data.events || [];
    pmSeriesOptions = data.series_options || [];
    renderPMStats(data);
    renderPMTable(pmAllEvents);
    populatePMSeriesFilter(pmSeriesOptions);
  } catch (e) {
    if (e.message === "401") return;
    wrap.innerHTML = '<div class="empty-state"><span class="empty-icon">◈</span><span class="empty-text">Failed to load</span></div>';
  }
}

function renderPMStats(data) {
  var total = data.total || 0;
  var linkedCount = (data.events || []).filter(function(e) { return e.match_id; }).length;
  var unlinkedCount = total - linkedCount;
  $("#pmStats").innerHTML =
    '<div class="pm-stat-card"><div class="pm-stat-k">TOTAL</div><div class="pm-stat-v">' + total + '</div></div>'
    + '<div class="pm-stat-card pm-stat-linked"><div class="pm-stat-k">LINKED ✓</div><div class="pm-stat-v">' + linkedCount + '</div></div>'
    + '<div class="pm-stat-card pm-stat-unlinked"><div class="pm-stat-k">UNLINKED ✗</div><div class="pm-stat-v">' + unlinkedCount + '</div></div>';
}

function populatePMSeriesFilter(options) {
  var sel = $("#pm_series");
  var currentVal = sel.value;
  sel.innerHTML = '<option value="">All Series</option>'
    + options.map(function(s) { return '<option value="' + s.id + '">' + escapeHtml(s.name) + ' (' + s.count + ')</option>'; }).join("");
  if (currentVal) sel.value = currentVal;
}

function renderPMTable(events) {
  var wrap = $("#pmTableWrap");
  if (!events.length) {
    wrap.innerHTML = '<div class="empty-state"><span class="empty-icon">◈</span><span class="empty-text">No Polymarket events found</span><span class="empty-hint">Try adjusting filters or sync from admin</span></div>';
    return;
  }

  var html = '<table class="pm-table"><thead><tr>'
    + '<th>ID</th><th>PM Event</th><th>Series</th><th>Start Time (BJ)</th>'
    + '<th>Markets</th><th>Status</th><th>Highlightly Match</th><th>Actions</th>'
    + '</tr></thead><tbody>';

  events.forEach(function(ev, i) {
    var isLinked = ev.match_id != null;
    var statusCls = isLinked ? "pm-badge-linked" : "pm-badge-unlinked";
    var statusLabel = isLinked ? "✓ Linked" : "✗ Unlinked";
    var timeStr = toBJTime(ev.game_start_time);
    var titleEsc = escapeHtml(ev.title);
    var seriesEsc = escapeHtml(ev.series_name || ev.series_id || "-");

    // Markets 价格行
    var marketsHtml = "";
    if (ev.markets && ev.markets.length) {
      marketsHtml = '<div class="pm-prices">';
      ev.markets.forEach(function(mk) {
        var priceStr = mk.price != null ? (mk.price * 100).toFixed(1) + "%" : "-";
        var volStr = mk.volume != null ? "$" + mk.volume.toLocaleString() : "";
        var outcomeLabel = mk.outcome === "home" ? "H" : mk.outcome === "draw" ? "D" : "A";
        marketsHtml += '<span class="pm-price-chip pm-price-' + mk.outcome + '">'
          + outcomeLabel + ' <b>' + priceStr + '</b>'
          + (volStr ? '<small>' + volStr + '</small>' : "")
          + '</span>';
      });
      marketsHtml += '</div>';
    } else {
      marketsHtml = '<span class="muted" style="font-size:12px">' + (ev.market_count || 0) + ' legs</span>';
    }

    // 关联的 Highlightly 比赛信息
    var matchHtml = "";
    if (isLinked && ev.linked_match) {
      var m = ev.linked_match;
      matchHtml = '<div class="pm-match-linked">'
        + '<a href="#" class="pm-match-link" data-mid="' + m.match_id + '" onclick="return false;">'
        + '#' + m.match_id + '</a> '
        + escapeHtml(m.home) + ' vs ' + escapeHtml(m.away)
        + (m.league_name ? '<br><small>' + escapeHtml(m.league_name) + '</small>' : "")
        + '<br><small class="muted">' + (m.match_time || "").slice(0, 16) + ' | ' + m.status + '</small>'
        + '</div>';
    } else {
      matchHtml = '<span class="pm-match-empty">Not linked</span>';
    }

    // 操作按钮
    var actionsHtml = '<button class="btn-pm-action btn-pm-analyze" data-eid="' + ev.id + '" data-title="' + titleEsc + '">分析</button>';
    if (isLinked) {
      actionsHtml += ' <button class="btn-pm-action btn-pm-unlink" data-eid="' + ev.id + '" data-mid="' + ev.match_id + '">Unlink</button>';
    } else {
      actionsHtml += ' <button class="btn-pm-action btn-pm-link" data-eid="' + ev.id + '" data-title="' + titleEsc + '">Link…</button>';
    }

    html += '<tr class="' + (isLinked ? "pm-row-linked" : "pm-row-unlinked") + '" data-eid="' + ev.id + '">'
      + '<td class="pm-td-id">' + ev.id + '</td>'
      + '<td class="pm-td-title">'
      + '<div class="pm-event-title">' + titleEsc + '</div>'
      + (ev.home_team_raw ? '<div class="pm-teams-raw">' + escapeHtml(ev.home_team_raw) + ' v ' + escapeHtml(ev.away_team_raw) + '</div>' : "")
      + '</td>'
      + '<td class="pm-td-series">' + seriesEsc + '</td>'
      + '<td class="pm-td-time">' + timeStr + '</td>'
      + '<td class="pm-td-markets">' + marketsHtml + '</td>'
      + '<td class="pm-td-status"><span class="pm-badge ' + statusCls + '">' + statusLabel + '</span></td>'
      + '<td class="pm-td-match">' + matchHtml + '</td>'
      + '<td class="pm-td-actions">' + actionsHtml + '</td>'
      + '</tr>';
    // 分析展开行
    html += '<tr class="pm-analysis-row" data-eid="' + ev.id + '" hidden><td colspan="8"><div class="pm-analysis-inner"></div></td></tr>';
  });

  html += '</tbody></table>';
  wrap.innerHTML = html;

  // 绑定事件
  wrap.querySelectorAll(".btn-pm-link").forEach(function(btn) {
    btn.addEventListener("click", function() { openLinkModal(Number(btn.dataset.eid), btn.dataset.title); });
  });
  wrap.querySelectorAll(".btn-pm-unlink").forEach(function(btn) {
    btn.addEventListener("click", function() { unlinkPMEvent(Number(btn.dataset.eid), Number(btn.dataset.mid)); });
  });
  wrap.querySelectorAll(".btn-pm-analyze").forEach(function(btn) {
    btn.addEventListener("click", function(e) { e.stopPropagation(); togglePMAnalysis(Number(btn.dataset.eid)); });
  });
  // 整行点击展开/收起分析
  wrap.querySelectorAll(".pm-row-linked, .pm-row-unlinked").forEach(function(row) {
    row.style.cursor = "pointer";
    row.addEventListener("click", function() { togglePMAnalysis(Number(row.dataset.eid)); });
  });
}

/* 手动关联弹窗 */
var currentLinkEventId = null;

function openLinkModal(eventId, eventTitle) {
  currentLinkEventId = eventId;
  $("#pmMatchIdInput").value = "";
  $("#pmLinkInfo").innerHTML = '<strong>PM Event #' + eventId + ':</strong> ' + escapeHtml(eventTitle);
  $("#pmLinkModal").hidden = false;
  setTimeout(function() { $("#pmMatchIdInput").focus(); }, 100);
}

function closeLinkModal() {
  $("#pmLinkModal").hidden = true;
  currentLinkEventId = null;
}

$("#pmModalClose").addEventListener("click", closeLinkModal);
$("#pmModalCancel").addEventListener("click", closeLinkModal);
$("#pmLinkModal").addEventListener("click", function(e) {
  if (e.target === e.currentTarget) closeLinkModal();
});

$("#pmModalConfirm").addEventListener("click", async function() {
  if (!currentLinkEventId) return;
  var hlIdVal = parseInt($("#pmMatchIdInput").value, 10);
  if (!hlIdVal || hlIdVal < 1) {
    toast("Please enter a valid Highlightly match_id");
    return;
  }
  $("#pmModalConfirm").disabled = true;
  try {
    await api("/polymarket/" + currentLinkEventId + "/match", { highlightly_id: hlIdVal }, "PUT");
    toast("Linked PM #" + currentLinkEventId + " → Highlightly Match #" + hlIdVal);
    closeLinkModal();
    loadPMEvents();  // 刷新列表
  } catch (e) {
    if (e.message !== "401") toast("Link failed: " + e.message);
  }
  $("#pmModalConfirm").disabled = false;
});

/* 解除关联 */
async function unlinkPMEvent(eventId, oldMatchId) {
  if (!confirm("Unlink PM #" + eventId + " from Match #" + oldMatchId + "?")) return;
  try {
    await api("/polymarket/" + eventId + "/match", { match_id: 0 }, "PUT");
    toast("Unlinked PM #" + eventId);
    loadPMEvents();
  } catch (e) {
    if (e.message !== "401") toast("Unlink failed: " + e.message);
  }
}

/* AI vs 市场 对比分析（行内展开） */
var pmAnalysisCache = {};  // eventId → data 缓存，避免重复请求

function togglePMAnalysis(eventId) {
  var row = document.querySelector('.pm-analysis-row[data-eid="' + eventId + '"]');
  if (!row) return;

  // 已展开 → 收起
  if (!row.hidden) {
    row.hidden = true;
    row.style.maxHeight = "0";
    return;
  }

  // 展开：先显示 loading
  var inner = row.querySelector(".pm-analysis-inner");
  inner.innerHTML = '<div class="loading-state"><div class="loader-ring"></div><span>Analyzing…</span></div>';
  row.hidden = false;
  requestAnimationFrame(function() { row.style.maxHeight = row.scrollHeight + "px"; });

  // 有缓存直接渲染
  if (pmAnalysisCache[eventId]) {
    inner.innerHTML = renderPMAnalysis(pmAnalysisCache[eventId]);
    requestAnimationFrame(function() { row.style.maxHeight = row.scrollHeight + "px"; });
    return;
  }

  // 无缓存则请求 API
  api("/polymarket/" + eventId + "/analysis").then(function(data) {
    pmAnalysisCache[eventId] = data;
    inner.innerHTML = renderPMAnalysis(data);
    requestAnimationFrame(function() { row.style.maxHeight = row.scrollHeight + "px"; });
  }).catch(function(e) {
    if (e && e.message !== "401") {
      inner.innerHTML = '<div class="empty-state"><span class="empty-icon">◈</span><span class="empty-text">Analysis failed</span></div>';
    }
  });
}

function paOutcomeLabel(o) { return o === "home" ? "主胜" : o === "draw" ? "平局" : o === "away" ? "客胜" : o; }
function paPct(v) { return v == null ? "-" : (v * 100).toFixed(1) + "%"; }
function paEvCell(v) {
  if (v == null) return '<td class="muted">-</td>';
  var cls = v > 0 ? "pa-pos" : (v < 0 ? "pa-neg" : "muted");
  return '<td class="' + cls + '">' + (v >= 0 ? "+" : "") + (v * 100).toFixed(1) + "%</td>";
}
function paRoi(v) { return v == null ? "-" : (v >= 0 ? "+" : "") + (v * 100).toFixed(1) + "%"; }
function paKelly(v) { return v == null ? "-" : (v * 100).toFixed(0) + "%"; }
function paBar(label, val, cls) {
  var p = (val || 0) * 100;
  return '<div class="pa-bar-row">'
    + '<span class="pa-bar-label">' + label + "</span>"
    + '<div class="pa-bar-track"><div class="pa-bar-fill pa-bar-' + cls + '" style="width:' + p.toFixed(1) + '%"></div></div>'
    + '<span class="pa-bar-val">' + p.toFixed(0) + "%</span>"
    + "</div>";
}

function renderPMAnalysis(d) {
  var html = "";

  var linked = !!d.match;

  // 英雄区：赛事标题 + 关联状态信号灯
  html += '<div class="pa-hero">';
  html += '<div class="pa-hero-main">';
  html += '<div class="pa-eyebrow">Polymarket × AI Dossier</div>';
  html += '<h3 class="pa-title">' + escapeHtml(d.event.title) + '</h3>';
  if (d.match) {
    html += '<div class="pa-match">' + escapeHtml(d.match.home) + ' <b>vs</b> ' + escapeHtml(d.match.away)
      + (d.match.league_name ? ' · ' + escapeHtml(d.match.league_name) : '')
      + ' · ' + (d.match.match_time || '').slice(0, 16) + ' · ' + escapeHtml(d.match.status) + '</div>';
  } else {
    html += '<div class="pa-match pa-warn">⚠ 未关联比赛 — 仅展示市场价</div>';
  }
  html += '</div>';
  html += '<div class="pa-hero-sig ' + (linked ? 'is-live' : 'is-off') + '">'
    + '<span class="pa-sig-dot"></span><span class="pa-sig-label">' + (linked ? 'MATCH LINKED' : 'UNLINKED') + '</span></div>';
  html += '</div>';

  // AI 共识
  html += '<section class="pa-section pa-ai"><div class="pa-section-head">'
    + '<span class="pa-section-title">AI Consensus</span>'
    + '<span class="pa-count">' + (d.ai ? d.ai.total_models : 0) + ' models</span></div>';
  if (d.ai && d.ai.total_models) {
    var dp = d.ai.distribution_pct;
    html += '<div class="pa-bars">'
      + paBar("主胜", dp.home, "home")
      + paBar("平局", dp.draw, "draw")
      + paBar("客胜", dp.away, "away")
      + "</div>";
    html += '<div class="pa-meta">平均置信度 <b>' + (d.ai.avg_confidence != null ? d.ai.avg_confidence : "-") + "/10</b>"
      + " · 分布 主 " + d.ai.counts.home + " / 平 " + d.ai.counts.draw + " / 客 " + d.ai.counts.away + "</div>";
    if (d.ai.summary) {
      html += '<div class="pa-summary">' + escapeHtml(d.ai.summary) + "</div>";
    }
  } else {
    html += '<div class="pa-empty">暂无 AI 预测数据（需先关联比赛）</div>';
  }
  html += "</section>";

  // 市场价
  html += '<section class="pa-section pa-mkt"><div class="pa-section-head">'
    + '<span class="pa-section-title">Polymarket Quotes</span>'
    + '<span class="pa-count">overround ' + ((d.overround || 0) * 100).toFixed(1) + '%</span></div>';
  html += '<div class="pa-quotes">';
  (d.markets || []).forEach(function(mk) {
    var pctStr = mk.price != null ? (mk.price * 100).toFixed(1) + "%" : "-";
    html += '<div class="pa-quote pa-quote-' + mk.outcome + '">'
      + '<span class="pa-quote-o">' + paOutcomeLabel(mk.outcome) + '</span>'
      + '<b class="pa-quote-p">' + pctStr + '</b>'
      + (mk.volume != null ? '<small>$' + mk.volume.toLocaleString() + ' vol</small>' : '<small>—</small>')
      + '</div>';
  });
  html += "</div>";
  html += '<div class="pa-meta">overround ' + ((d.overround || 0) * 100).toFixed(1) + '% · 越低越高效</div></section>';

  // 对比表
  html += '<section class="pa-section pa-cmp"><div class="pa-section-head"><span class="pa-section-title">AI × Market · Leg Metrics</span></div>';
  html += '<div class="pa-table-wrap"><table class="pa-table"><thead><tr>'
    + '<th class="pa-th-leg">结果</th><th>AI概率</th><th>市场隐含</th>'
    + '<th class="pa-th-yes" colspan="4">YES side</th>'
    + '<th class="pa-th-no" colspan="4">NO side</th>'
    + '</tr><tr class="pa-sub">'
    + '<th></th><th></th><th></th>'
    + '<th>价</th><th>EV</th><th>ROI</th><th>Kelly</th>'
    + '<th>价</th><th>EV</th><th>ROI</th><th>Kelly</th>'
    + '</tr></thead><tbody>';
  (d.bets || []).forEach(function(b) {
    if (!b.available) {
      html += '<tr><td class="pa-o-' + b.outcome + '">' + b.label + '</td><td colspan="10" class="muted">市场无此腿价格</td></tr>';
      return;
    }
    html += "<tr>"
      + '<td class="pa-o-' + b.outcome + '">' + b.label + "</td>"
      + "<td>" + paPct(b.ai_prob) + "</td>"
      + "<td>" + paPct(b.market_prob) + "</td>"
      + "<td>" + b.yes.price.toFixed(3) + "</td>"
      + paEvCell(b.yes.ev) + "<td>" + paRoi(b.yes.roi) + "</td><td>" + paKelly(b.yes.kelly) + "</td>"
      + "<td>" + b.no.price.toFixed(3) + "</td>"
      + paEvCell(b.no.ev) + "<td>" + paRoi(b.no.roi) + "</td><td>" + paKelly(b.no.kelly) + "</td>"
      + "</tr>";
  });
  html += "</tbody></table></div></section>";

  // 正 EV 建议
  html += '<section class="pa-section pa-best-sec"><div class="pa-section-head"><span class="pa-section-title">Positive-EV Signals</span></div>';
  if (d.best_bets && d.best_bets.length) {
    html += '<div class="pa-signals">';
    d.best_bets.forEach(function(x) {
      html += '<div class="pa-signal">'
        + '<span class="pa-signal-pulse"></span>'
        + '<span class="pa-signal-side pa-side-' + x.side.toLowerCase() + '">' + x.side + '</span>'
        + '<span class="pa-signal-label">' + x.label + '</span>'
        + '<span class="pa-signal-price">@' + x.price.toFixed(3) + '</span>'
        + '<span class="pa-signal-ev">EV ' + (x.ev * 100).toFixed(1) + '%</span>'
        + '<span class="pa-signal-kelly">Kelly ' + (x.kelly * 100).toFixed(0) + '%</span>'
        + '</div>';
    });
    html += "</div>";
  } else {
    html += '<div class="pa-empty">当前 AI 概率下无正 EV 下注（市场定价高效）</div>';
  }
  html += "</section>";

  html += '<div class="pa-disclaimer">⚠️ 非投资建议。AI 模型可能同质化，市场价由真实资金博弈形成，单场波动极大。</div>';

  return html;
}

// 扩展 api 方法支持 PUT（原版只支持 GET）
var _apiOrig = api;
api = async function(path, params, method) {
  var url = new URL(API + path, location.origin);
  if (params && (!method || method.toUpperCase() === "GET")) {
    Object.entries(params).forEach(function(_a) {
      var k = _a[0], v = _a[1];
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
    });
  } else if (params && method && method.toUpperCase() !== "GET") {
    // 非 GET：参数走 query string（FastAPI Query 参数）
    Object.entries(params).forEach(function(_a) {
      var k = _a[0], v = _a[1];
      if (v !== undefined && v !== null) url.searchParams.set(k, v);
    });
  }
  var fetchOpts = {
    headers: { "X-Access-Token": getToken() },
    method: method || "GET",
  };
  var res = await fetch(url.toString(), fetchOpts);
  if (res.status === 401) { toast("Invalid token"); throw new Error("401"); }
  if (!res.ok) {
    var txt = await res.text();
    toast("Request failed: " + res.status + " " + txt.slice(0, 120));
    throw new Error("HTTP " + res.status);
  }
  return res.json();
};

$("#btnLoadPM").addEventListener("click", loadPMEvents);

/* ===== STANDALONE MARKETS ===== */
var SA_API = "/api/v1/polymarket/standalone";
var saCategoryOptions = [];

async function loadSAMarkets() {
  var filter = $("#sa_filter").value;
  var sort = $("#sa_sort").value;
  var viewMode = $("#sa_view").value;
  var params = "sort_by=" + sort + "&sort_order=asc&limit=200";

  if (filter === "eligible") params += "&is_eligible=true";

  var wrap = $("#saTableWrap");
  wrap.innerHTML = '<div class="loading-state"><div class="loader-ring"></div><span>Loading markets…</span></div>';

  try {
    var url = SA_API + (filter === "eligible" ? "/markets/eligible" : "/markets") + "?" + params;
    var data = await adminApiUrl(url);
    saAllMarkets = data.markets || [];
    renderSAStats(saAllMarkets);
    if (viewMode === "group") {
      renderSAGrouped(saAllMarkets);
    } else {
      renderSAFlat(saAllMarkets);
    }
  } catch (e) {
    if (e.message === "401") return;
    wrap.innerHTML = '<div class="empty-state"><span class="empty-icon">◈</span><span class="empty-text">Failed to load</span></div>';
  }
}

var saAllMarkets = [];

function renderSAStats(markets) {
  var total = markets.length;
  var eligible = markets.filter(function(m) { return m.is_eligible; }).length;
  var totalVol = 0, totalLiq = 0, priceSum = 0, priceCount = 0;
  markets.forEach(function(m) {
    if (m.volume) totalVol += m.volume;
    if (m.liquidity) totalLiq += m.liquidity;
    if (m.no_price != null) { priceSum += m.no_price; priceCount++; }
  });
  var avgPct = priceCount ? (priceSum / priceCount * 100).toFixed(1) + "¢" : "-";
  var volStr = totalVol >= 1000000 ? "$" + (totalVol/1000000).toFixed(1) + "M" : totalVol >= 1000 ? "$" + (totalVol/1000).toFixed(0) + "K" : "$" + totalVol.toFixed(0);
  var liqStr = totalLiq >= 1000000 ? "$" + (totalLiq/1000000).toFixed(1) + "M" : totalLiq >= 1000 ? "$" + (totalLiq/1000).toFixed(0) + "K" : "$" + totalLiq.toFixed(0);

  $("#saStats").innerHTML =
    '<div class="pm-stat-card"><div class="pm-stat-k">TOTAL</div><div class="pm-stat-v">' + total + '</div></div>'
    + '<div class="pm-stat-card pm-stat-linked"><div class="pm-stat-k">ELIGIBLE</div><div class="pm-stat-v">' + eligible + '</div></div>'
    + '<div class="pm-stat-card"><div class="pm-stat-k">AVG NO</div><div class="pm-stat-v">' + avgPct + '</div></div>'
    + '<div class="pm-stat-card"><div class="pm-stat-k">VOLUME</div><div class="pm-stat-v">' + volStr + '</div></div>'
    + '<div class="pm-stat-card"><div class="pm-stat-k">LIQUIDITY</div><div class="pm-stat-v">' + liqStr + '</div></div>';
}

function fmtVol(v) {
  if (v == null) return "-";
  if (v >= 1000000) return "$" + (v/1000000).toFixed(1) + "M";
  if (v >= 1000) return "$" + (v/1000).toFixed(0) + "K";
  return "$" + v.toFixed(0);
}

function renderSAGrouped(markets) {
  var wrap = $("#saTableWrap");
  if (!markets.length) {
    wrap.innerHTML = '<div class="empty-state"><span class="empty-icon">◈</span><span class="empty-text">No markets found</span><span class="empty-hint">Try syncing or adjust filters</span></div>';
    return;
  }

  // Group by event_slug
  var groups = {};
  markets.forEach(function(m) {
    var key = (m.event_slug || m.category || "Other").trim();
    if (!groups[key]) groups[key] = { event_slug: key, markets: [] };
    groups[key].markets.push(m);
  });

  var sortedGroups = Object.values(groups).sort(function(a, b) {
    var va = a.markets.reduce(function(s, m) { return s + (m.volume || 0); }, 0);
    var vb = b.markets.reduce(function(s, m) { return s + (m.volume || 0); }, 0);
    return vb - va;
  });

  var html = '<div class="sa-groups">';

  sortedGroups.forEach(function(group, gi) {
    group.markets.sort(function(a, b) { return (a.no_price || 1) - (b.no_price || 1); });
    var totalVol = group.markets.reduce(function(s, m) { return s + (m.volume || 0); }, 0);
    var totalLiq = group.markets.reduce(function(s, m) { return s + (m.liquidity || 0); }, 0);
    var minNo = group.markets.reduce(function(m, c) { return Math.min(m, c.no_price || 1); }, 1);
    var eligibleCount = group.markets.filter(function(m) { return m.is_eligible; }).length;
    var maxNoPrice = group.markets[group.markets.length-1].no_price;

    // human-readable name from event_slug
    var displayName = group.event_slug.replace(/-/g, ' ').replace(/\b\w/g, function(c) { return c.toUpperCase(); });
    if (displayName.length > 50) displayName = displayName.slice(0, 50) + '...';

    html += '<div class="sa-group">'
      + '<div class="sa-group-header" data-gi="' + gi + '">'
      + '<span class="sa-group-arrow">▶</span>'
      + '<span class="sa-group-name">' + escapeHtml(displayName) + '</span>'
      + '<span class="sa-group-meta">'
      + group.markets.length + ' tiers | '
      + 'NO ' + (minNo * 100).toFixed(1) + 'cent' + ' - ' + (maxNoPrice != null ? (maxNoPrice*100).toFixed(1) + 'cent' : '?')
      + ' | vol ' + fmtVol(totalVol) + ' | liq ' + fmtVol(totalLiq)
      + (eligibleCount ? ' | <span class="pm-badge-linked">' + eligibleCount + ' eligible</span>' : '')
      + '</span>'
      + '</div>'
      + '<div class="sa-group-body" hidden>'
      + '<table class="pm-table"><thead><tr>'
      + '<th>Price Tier</th><th>Yes</th><th>No</th><th>Volume</th><th>Liquidity</th><th>Status</th>'
      + '</tr></thead><tbody>';

    group.markets.forEach(function(m) {
      var yesPct = m.yes_price != null ? (m.yes_price * 100).toFixed(1) + "%" : "-";
      var noPct = m.no_price != null ? (m.no_price * 100).toFixed(1) + "%" : "-";
      var vol = m.volume != null ? fmtVol(m.volume) : "-";
      var liq = m.liquidity != null ? fmtVol(m.liquidity) : "-";
      var q = escapeHtml(m.question || "").slice(0, 55);
      var statusLabel = m.is_eligible
        ? '<span class="pm-badge-linked">Eligible</span>'
        : '<span class="pm-badge-unlinked">-</span>';

      html += '<tr>'
        + '<td title="' + escapeHtml(m.question || "") + '">' + q + '</td>'
        + '<td class="pm-price-home"><b>' + yesPct + '</b></td>'
        + '<td class="pm-price-away"><b>' + noPct + '</b></td>'
        + '<td>' + vol + '</td>'
        + '<td>' + liq + '</td>'
        + '<td>' + statusLabel + '</td>'
        + '</tr>';
    });

    html += '</tbody></table></div></div>';
  });

  html += '</div>';
  html += '<div class="pm-table-footer">' + markets.length + ' markets in ' + sortedGroups.length + ' groups</div>';
  wrap.innerHTML = html;

  // Click handlers for group expand/collapse
  wrap.querySelectorAll(".sa-group-header").forEach(function(header) {
    header.addEventListener("click", function() {
      var body = this.nextElementSibling;
      var arrow = this.querySelector(".sa-group-arrow");
      body.hidden = !body.hidden;
      arrow.textContent = body.hidden ? "▶" : "▼";
    });
  });
}

function adminApiUrl(url) {
  return fetch(url, { headers: { "X-Access-Token": getToken() } }).then(function(r) {
    if (r.status === 401) throw new Error("401");
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  });
}

$("#btnLoadSA").addEventListener("click", loadSAMarkets);
$("#btnSyncFDV").addEventListener("click", syncFDVMarkets);
$("#sa_filter").addEventListener("change", loadSAMarkets);
$("#sa_sort").addEventListener("change", loadSAMarkets);
$("#sa_view").addEventListener("change", loadSAMarkets);

async function syncFDVMarkets() {
  var btn = $("#btnSyncFDV");
  btn.disabled = true;
  var origTxt = btn.innerHTML;
  btn.innerHTML = '<span class="loader-ring" style="width:14px;height:14px;border-width:1.5px;display:inline-block;vertical-align:middle"></span>';
  try {
    var res = await fetch(SA_API + "/sync-fdv", {
      method: "POST",
      headers: { "X-Access-Token": getToken() },
    });
    if (res.status === 401) { toast("Invalid token"); btn.disabled = false; btn.innerHTML = origTxt; return; }
    if (!res.ok) { toast("FDV sync failed"); btn.disabled = false; btn.innerHTML = origTxt; return; }
    var result = await res.json();
    var detail = result.detail || {};
    toast("FDV Sync OK: " + (detail.events || 0) + " events, " + (detail.markets || 0) + " markets, " + (detail.eligible || 0) + " eligible");
    await loadSAMarkets();
  } catch (e) {
    toast("FDV sync error: " + e.message);
  }
  btn.disabled = false;
  btn.innerHTML = origTxt;
}

function renderSAFlat(markets) {
  var wrap = $("#saTableWrap");
  if (!markets.length) {
    wrap.innerHTML = '<div class="empty-state"><span class="empty-icon">◈</span><span class="empty-text">No markets found</span><span class="empty-hint">Try syncing or adjust filters</span></div>';
    return;
  }
  var html = '<table class="pm-table"><thead><tr>'
    + '<th>Question</th><th>Yes</th><th>No</th><th>Volume</th><th>Liquidity</th><th>Status</th>'
    + '</tr></thead><tbody>';
  markets.forEach(function(m) {
    var yesPct = m.yes_price != null ? (m.yes_price * 100).toFixed(1) + "%" : "-";
    var noPct = m.no_price != null ? (m.no_price * 100).toFixed(1) + "%" : "-";
    var vol = m.volume != null ? fmtVol(m.volume) : "-";
    var liq = m.liquidity != null ? fmtVol(m.liquidity) : "-";
    var q = escapeHtml(m.question || "").slice(0, 70);
    var statusLabel = m.is_eligible
      ? '<span class="pm-badge-linked">Eligible</span>'
      : '<span class="pm-badge-unlinked">-</span>';
    html += '<tr><td title="' + escapeHtml(m.question || "") + '">' + q + '</td>'
      + '<td class="pm-price-home"><b>' + yesPct + '</b></td>'
      + '<td class="pm-price-away"><b>' + noPct + '</b></td>'
      + '<td>' + vol + '</td><td>' + liq + '</td><td>' + statusLabel + '</td></tr>';
  });
  html += '</tbody></table><div class="pm-table-footer">' + markets.length + ' markets</div>';
  wrap.innerHTML = html;
}

/* Bootstrap */
/* ═══════════════════════════════════════════════════════════════
   ADMIN CONSOLE
   ═══════════════════════════════════════════════════════════════ */

var ADMIN_API = "/api/v1/admin";

async function adminApi(action, method, body, params) {
  var url = new URL(ADMIN_API + "/" + action, location.origin);
  if (params) Object.entries(params).forEach(function(_a) {
    var k = _a[0], v = _a[1];
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
  });
  var opts = {
    method: method || "POST",
    headers: { "X-Access-Token": getToken() },
  };
  if (body) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  var res = await fetch(url.toString(), opts);
  if (res.status === 401) { toast("Admin: invalid token"); throw new Error("401"); }
  if (!res.ok) { var txt = await res.text(); toast("Admin failed: " + res.status); throw new Error("HTTP " + res.status); }
  return res.json();
}

function adminLog(msg, type) {
  var el = $("#adminLog");
  var ts = new Date().toLocaleTimeString();
  var cls = type === "ok" ? "log-ok" : type === "err" ? "log-err" : type === "warn" ? "log-warn" : "log-info";
  var entry = document.createElement("div");
  entry.className = "admin-log-entry " + cls;
  entry.innerHTML = '<span class="log-ts">' + ts + '</span> <span class="log-msg">' + escapeHtml(msg) + '</span>';
  el.appendChild(entry);
  el.scrollTop = el.scrollHeight;
}

async function runAdminAction(btn) {
  var action = btn.dataset.action;
  var method = btn.dataset.method || "POST";
  var isSingle = btn.dataset.single;
  btn.disabled = true;
  var origText = btn.textContent;
  btn.innerHTML = '<span class="loader-ring" style="width:14px;height:14px;border-width:1.5px;display:inline-block;vertical-align:middle"></span>';
  try {
    var body = null, params = {};
    if (isSingle) {
      var mid = $("#admin_match_id").value;
      if (!mid) { toast("请输入 match_id"); btn.disabled = false; btn.textContent = origText; return; }
      action = "predictions/generate/" + mid;
    }
    if (action === "odds/sync-league") {
      params.league_id = $("#admin_league_id").value || 1;
    }
    if (action === "leagues/clone") {
      var src = parseInt($("#admin_clone_src").value);
      var season = parseInt($("#admin_clone_season").value);
      if (!src || !season) { toast("请填 src_id 和 season"); btn.disabled = false; btn.textContent = origText; return; }
      body = { source_league_id: src, season: season, is_active: false };
    }
    if (action === "leagues/backfill-season") {
      var srcBf = parseInt($("#admin_bf_src").value);
      var seasonBf = parseInt($("#admin_bf_season").value);
      if (!srcBf || !seasonBf) { toast("请填 src_id 和 season"); btn.disabled = false; btn.textContent = origText; return; }
      body = { source_league_id: srcBf, season: seasonBf, with_players: true, is_active: false };
    }
    if (action === "leagues/create") {
      var cname = $("#admin_create_name").value.trim();
      var ccn = $("#admin_create_cn").value.trim();
      var chl = parseInt($("#admin_create_hl").value);
      var cseason = parseInt($("#admin_create_season").value);
      var ctype = $("#admin_create_type").value.trim() || "league";
      var ccountry = $("#admin_create_country").value.trim() || null;
      if (!cname || !ccn || !chl || !cseason) { toast("请填 英文名/中文名/hl_id/season"); btn.disabled = false; btn.textContent = origText; return; }
      body = { name: cname, cn_name: ccn, highlightly_league_id: chl, season: cseason, type: ctype, country: ccountry, is_active: true };
    }
    var data = await adminApi(action, method, body, params);
    var msg = (data.message || data.status || "OK") + (data.detail ? " " + JSON.stringify(data.detail).slice(0, 200) : "");
    adminLog("[" + action + "] " + msg, "ok");
    toast(action + " OK");
  } catch (e) {
    if (e.message !== "401") adminLog("[" + action + "] " + e.message, "err");
  }
  btn.disabled = false;
  btn.textContent = origText;
}

$$("#tab-admin .btn-admin[data-action]").forEach(function(btn) {
  btn.addEventListener("click", function() { runAdminAction(btn); });
});
$("#adminLogClear").addEventListener("click", function() {
  $("#adminLog").innerHTML = '<div class="admin-log-empty">日志已清空</div>';
});

async function bootstrap() {
  initTheme();
  if (!getToken()) return;
  await loadLeagues();
  await loadBookmakers();
  // 默认日期范围：今天到未来一周
  function fmtDate(d) {
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }
  var today = new Date();
  var nextWeek = new Date(today);
  nextWeek.setDate(today.getDate() + 7);
  $("#f_start_date").value = fmtDate(today);
  $("#f_end_date").value = fmtDate(nextWeek);
  // 默认选 upcoming 并自动加载比赛列表
  $("#f_status").value = "upcoming";
  $("#f_sort").value = "asc";
  $("#pm_sort").value = "desc";
  await loadMatches();
  await runBacktest();
}
bootstrap();
