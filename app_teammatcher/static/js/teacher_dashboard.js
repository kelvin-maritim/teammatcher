/* teacher_dashboard.js
 *
 * Workflow:
 *   1. Teacher picks a CSVGeneration from the dropdown → Load button
 *   2. Backend parses the CSV and returns teams grouped by "cp" column
 *   3. Teacher drags students between team cards
 *   4. On drop, criteria mismatch is checked via API → warning shown if needed
 *   5. Export button POSTs the adjusted state → downloads LMS-ready CSV
 *
 * Endpoints used:
 *   GET  /teacher/dashboard/api/load/?generation_id=ID       → { teams, max_size }
 *   GET  /teacher/dashboard/api/mismatch/?student=ID&members=ID,ID  → { warnings[] }
 *   POST /teacher/dashboard/api/export/                      → CSV file download
 */

document.addEventListener("DOMContentLoaded", () => {

  // ── Refs ─────────────────────────────────────────────────
  const generationSelect = document.getElementById("generation-select");
  const btnLoad          = document.getElementById("btn-load");
  const loadStatus       = document.getElementById("load-status");
  const statusText       = document.getElementById("status-text");
  const statusUnsaved    = document.getElementById("status-unsaved");
  const sectionTeams     = document.getElementById("section-teams");
  const sectionExport    = document.getElementById("section-export");
  const teamsContainer   = document.getElementById("teams-container");
  const btnExport        = document.getElementById("btn-export");
  const btnReset         = document.getElementById("btn-reset");
  const csrfToken        = () => document.querySelector("input[name='csrfmiddlewaretoken']").value;

  // ── State ─────────────────────────────────────────────────
  let state = {
    generationId:     null,
    teams:            [],
    maxSize:          5,
    originalSnapshot: null,
    dirty:            false,
  };

  // ── Load ──────────────────────────────────────────────────
  btnLoad.addEventListener("click", async () => {
    const id = generationSelect.value;
    if (!id) { showToast("Please select a matching result first.", "error"); return; }

    btnLoad.disabled    = true;
    btnLoad.textContent = "Loading…";

    try {
      const res  = await fetch(`/teacher/dashboard/api/load/?generation_id=${id}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();

      state.generationId     = id;
      state.teams            = data.teams;
      state.maxSize          = data.max_size ?? 5;
      state.originalSnapshot = JSON.stringify(data.teams);
      state.dirty            = false;

      renderTeams();
      setStatus(`Loaded ${data.teams.length} teams · ${countMembers()} students`);
      sectionTeams.hidden  = false;
      sectionExport.hidden = false;
      statusUnsaved.hidden = true;
    } catch (err) {
      showToast(`Error loading: ${err.message}`, "error");
      console.error(err);
    } finally {
      btnLoad.disabled  = false;
      btnLoad.innerHTML = `<svg viewBox="0 0 24 24" fill="currentColor" style="width:1rem;height:1rem">
        <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg> Load`;
    }
  });

  // ── Reset ─────────────────────────────────────────────────
  btnReset.addEventListener("click", () => {
    if (!state.dirty) return;
    if (!confirm("Discard all changes and reload the original result?")) return;
    state.teams = JSON.parse(state.originalSnapshot);
    state.dirty = false;
    statusUnsaved.hidden = true;
    renderTeams();
    setStatus(`Reset · ${state.teams.length} teams · ${countMembers()} students`);
  });

  // ── Export ────────────────────────────────────────────────
  btnExport.addEventListener("click", async () => {
    btnExport.disabled    = true;
    btnExport.textContent = "Exporting…";

    try {
      const res = await fetch("/teacher/dashboard/api/export/", {
        method:  "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        body:    JSON.stringify({ generation_id: state.generationId, teams: state.teams }),
      });

      if (!res.ok) throw new Error(await res.text());

      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href     = url;
      a.download = `teams_adjusted_${new Date().toISOString().slice(0,10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);

      state.dirty          = false;
      statusUnsaved.hidden = true;
      setStatus("Exported ✓");
    } catch (err) {
      showToast(`Export failed: ${err.message}`, "error");
      console.error(err);
    } finally {
      btnExport.disabled  = false;
      btnExport.innerHTML = `<svg viewBox="0 0 24 24" fill="currentColor" style="width:1rem;height:1rem">
        <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg> Export CSV for LMS`;
    }
  });

  // ── Render team cards ─────────────────────────────────────
  function renderTeams() {
    teamsContainer.innerHTML = state.teams.map(team => {
      const count    = team.members.length;
      const max      = state.maxSize;
      const pct      = Math.min(100, Math.round((count / max) * 100));
      const isFull   = count >= max;
      const isSparse = count < 2;
      const barCol   = isSparse ? "var(--danger)" : isFull ? "var(--success)" : pct >= 80 ? "var(--warning)" : "var(--success)";

      const chipsHtml = count > 0
        ? team.members.map(id => `
            <div class="student-chip"
                 draggable="true"
                 data-student="${escHtml(id)}"
                 data-team="${escHtml(team.name)}">
              <span class="chip-dot"></span>
              <span class="chip-label">${escHtml(id)}</span>
            </div>`).join("")
        : `<div class="drop-zone--empty">No members — drop students here</div>`;

      const deleteBtn = count === 0
        ? `<button class="btn-delete-team" data-team="${escHtml(team.name)}" title="Delete empty team">
             <svg viewBox="0 0 24 24" fill="currentColor" style="width:.9rem;height:.9rem">
               <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
             </svg>
             Delete team
           </button>`
        : "";

      return `
        <div class="team-card ${isSparse ? "team-card--sparse" : isFull ? "team-card--full" : ""}"
             data-team="${escHtml(team.name)}">
          <div class="team-card-header">
            <span class="team-card-name">${escHtml(team.name)}</span>
            ${isFull ? '<span class="team-badge-full">FULL</span>' : ""}
            ${deleteBtn}
          </div>
          <div class="team-capacity">
            <span class="team-capacity-label">${count} / ${max} members</span>
            <div class="team-capacity-bar">
              <div class="team-capacity-fill" style="width:${pct}%;background:${barCol}"></div>
            </div>
          </div>
          <div class="drop-zone" data-team="${escHtml(team.name)}">
            ${chipsHtml}
          </div>
        </div>`;
    }).join("");

    attachDragDrop();
  }

  // ── Drag & Drop ───────────────────────────────────────────
  let dragStudent  = null;
  let dragFromTeam = null;

  function attachDragDrop() {
    document.querySelectorAll(".student-chip").forEach(chip => {
      chip.addEventListener("dragstart", e => {
        dragStudent  = chip.dataset.student;
        dragFromTeam = chip.dataset.team;
        chip.classList.add("dragging");
        e.dataTransfer.effectAllowed = "move";
      });
      chip.addEventListener("dragend", () => chip.classList.remove("dragging"));
    });

    // Delete empty team buttons
    document.querySelectorAll(".btn-delete-team").forEach(btn => {
      btn.addEventListener("click", () => {
        const teamName = btn.dataset.team;
        if (!confirm(`Delete empty team "${teamName}"?`)) return;
        state.teams = state.teams.filter(t => t.name !== teamName);
        markDirty();
        renderTeams();
      });
    });

    document.querySelectorAll(".drop-zone").forEach(zone => {
      zone.addEventListener("dragover", e => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        zone.closest(".team-card").classList.add("team-card--over");
      });
      zone.addEventListener("dragleave", e => {
        if (!zone.contains(e.relatedTarget))
          zone.closest(".team-card").classList.remove("team-card--over");
      });
      zone.addEventListener("drop", async e => {
        e.preventDefault();
        zone.closest(".team-card").classList.remove("team-card--over");

        const toTeam = zone.dataset.team;
        if (!dragStudent || toTeam === dragFromTeam) return;

        const from = state.teams.find(t => t.name === dragFromTeam);
        const to   = state.teams.find(t => t.name === toTeam);
        if (!from || !to) return;

        // Hard block: team full
        if (to.members.length >= state.maxSize) {
          showToast(`Team "${toTeam}" is full (${state.maxSize} members max).`, "error");
          return;
        }

        // Criteria mismatch check
        const mismatch = await checkCriteriaMismatch(dragStudent, to.members);

        if (mismatch.warnings.length > 0) {
          showMismatchBanner(dragStudent, toTeam, mismatch.warnings, () => {
            doMove(from, to);
          });
        } else {
          doMove(from, to);

        }
      });
    });
  }

  function doMove(from, to) {
    from.members = from.members.filter(m => m !== dragStudent);
    if (!to.members.includes(dragStudent)) to.members.push(dragStudent);
    markDirty();
    renderTeams();
  }

  // ── Criteria mismatch check ───────────────────────────────
  /**
   * Fetches StudentProfile for the dragged student and each target member,
   * then compares key criteria fields.
   * Returns { warnings: [string], noProfile: bool }
   */
  async function checkCriteriaMismatch(studentId, targetMembers) {
    try {
      // Fetch profile for the dragged student
      // Single API call — backend does all comparisons
      const params = new URLSearchParams({
        student: studentId,
        members: targetMembers.join(","),
      });
      const res = await fetch(`/teacher/dashboard/api/mismatch/?${params}`);
      if (!res.ok) return { warnings: [], noProfile: true };
      const data = await res.json();
      if (data.no_profile) return { warnings: [], noProfile: true };
      return { warnings: data.warnings ?? [], noProfile: false };

    } catch (err) {
      console.warn("Criteria check failed:", err);
      return { warnings: [], noProfile: true };
    }
  }

  // ── Mismatch banner ───────────────────────────────────────
  /**
   * Shows an inline warning banner with a list of criteria issues.
   * Teacher can confirm the move or cancel.
   */
  function showMismatchBanner(studentId, toTeam, warnings, onConfirm) {
    // Remove any existing banner
    document.getElementById("mismatch-banner")?.remove();

    const banner = document.createElement("div");
    banner.id = "mismatch-banner";
    banner.className = "mismatch-banner";
    banner.innerHTML = `
      <div class="mismatch-banner-header">
        <svg viewBox="0 0 24 24" fill="currentColor" style="width:1.2rem;height:1.2rem;flex-shrink:0">
          <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/>
        </svg>
        <strong>Criteria mismatch detected</strong>
        <span class="mismatch-banner-sub">Moving <em>${escHtml(studentId)}</em> → <em>${escHtml(toTeam)}</em></span>
      </div>
      <ul class="mismatch-warning-list">
        ${warnings.map(w => `<li>${escHtml(w)}</li>`).join("")}
      </ul>
      <div class="mismatch-banner-actions">
        <button class="btn btn-ghost btn-sm" id="mismatch-cancel">Cancel</button>
        <button class="btn btn-warn btn-sm" id="mismatch-confirm">Move anyway</button>
      </div>
    `;

    // Insert banner above teams grid
    const section = document.getElementById("section-teams");
    section.insertBefore(banner, section.querySelector(".teams-grid"));

    document.getElementById("mismatch-cancel").addEventListener("click", () => banner.remove());
    document.getElementById("mismatch-confirm").addEventListener("click", () => {
      banner.remove();
      onConfirm();
    });

    // Scroll banner into view
    banner.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // ── Toast notifications ───────────────────────────────────
  function showToast(message, type = "info") {
    let container = document.getElementById("toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = `toast toast--${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    // Animate in
    requestAnimationFrame(() => toast.classList.add("toast--show"));

    // Remove after 4s
    setTimeout(() => {
      toast.classList.remove("toast--show");
      toast.addEventListener("transitionend", () => toast.remove());
    }, 4000);
  }

  // ── Helpers ───────────────────────────────────────────────
  function markDirty() {
    state.dirty          = true;
    statusUnsaved.hidden = false;
  }

  function setStatus(msg) {
    loadStatus.hidden      = false;
    statusText.textContent = msg;
  }

  function countMembers() {
    return state.teams.reduce((n, t) => n + t.members.length, 0);
  }

  function escHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

});