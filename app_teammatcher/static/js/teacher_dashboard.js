/* teacher_dashboard.js
 *
 * Workflow:
 *   1. Teacher picks a CSVGeneration from the dropdown → Load button
 *   2. Backend parses the CSV and returns teams grouped by "cp" column
 *   3. Teacher drags students between team cards
 *   4. Export button POSTs the adjusted state → downloads LMS-ready CSV
 *
 * Endpoints used:
 *   GET  /teacher/dashboard/api/load/?generation_id=ID  → { teams, max_size }
 *   POST /teacher/dashboard/api/export/                 → CSV file download
 */

document.addEventListener("DOMContentLoaded", () => {

  // ── Refs ────────────────────────────────────────────────
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

  // ── State ───────────────────────────────────────────────
  let state = {
    generationId: null,
    teams: [],          // [{ name, members: ["s-001076", …] }]
    maxSize: 5,
    originalSnapshot: null,   // JSON snapshot for reset
    dirty: false,
  };

  // ── Load ────────────────────────────────────────────────
  btnLoad.addEventListener("click", async () => {
    const id = generationSelect.value;
    if (!id) { alert("Please select a matching result first."); return; }

    btnLoad.disabled    = true;
    btnLoad.textContent = "Loading…";

    try {
      const res  = await fetch(`/teacher/dashboard/api/load/?generation_id=${id}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();   // { teams: [{name, members:[…]}], max_size }

      state.generationId    = id;
      state.teams           = data.teams;
      state.maxSize         = data.max_size ?? 5;
      state.originalSnapshot = JSON.stringify(data.teams);
      state.dirty           = false;

      renderTeams();
      setStatus(`Loaded ${data.teams.length} teams · ${countMembers()} students`);
      sectionTeams.hidden  = false;
      sectionExport.hidden = false;
      statusUnsaved.hidden = true;
    } catch (err) {
      alert(`Error loading: ${err.message}`);
      console.error(err);
    } finally {
      btnLoad.disabled    = false;
      btnLoad.textContent = "Load";
      btnLoad.innerHTML   = `<svg viewBox="0 0 24 24" fill="currentColor" style="width:1rem;height:1rem">
        <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg> Load`;
    }
  });

  // ── Reset ───────────────────────────────────────────────
  btnReset.addEventListener("click", () => {
    if (!state.dirty) return;
    if (!confirm("Discard all changes and reload the original result?")) return;
    state.teams = JSON.parse(state.originalSnapshot);
    state.dirty = false;
    statusUnsaved.hidden = true;
    renderTeams();
    setStatus(`Reset · ${state.teams.length} teams · ${countMembers()} students`);
  });

  // ── Export ──────────────────────────────────────────────
  btnExport.addEventListener("click", async () => {
    btnExport.disabled    = true;
    btnExport.textContent = "Exporting…";

    try {
      const res = await fetch("/teacher/dashboard/api/export/", {
        method:  "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken":  csrfToken(),
        },
        body: JSON.stringify({
          generation_id: state.generationId,
          teams:         state.teams,
        }),
      });

      if (!res.ok) throw new Error(await res.text());

      // Trigger file download from the blob response
      const blob     = await res.blob();
      const url      = URL.createObjectURL(blob);
      const a        = document.createElement("a");
      a.href         = url;
      a.download     = `teams_adjusted_${new Date().toISOString().slice(0,10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);

      state.dirty          = false;
      statusUnsaved.hidden = true;
      setStatus("Exported ✓");
    } catch (err) {
      alert(`Export failed: ${err.message}`);
      console.error(err);
    } finally {
      btnExport.disabled = false;
      btnExport.innerHTML = `<svg viewBox="0 0 24 24" fill="currentColor" style="width:1rem;height:1rem">
        <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg> Export CSV for LMS`;
    }
  });

  // ── Render all team cards ───────────────────────────────
  function renderTeams() {
    teamsContainer.innerHTML = state.teams.map(team => {
      const count  = team.members.length;
      const max    = state.maxSize;
      const pct    = Math.min(100, Math.round((count / max) * 100));
      const isFull = count >= max;
      const barCol = isFull ? "var(--danger)" : pct >= 80 ? "var(--warning)" : "var(--success)";

      const chipsHtml = count > 0
        ? team.members.map(id => `
            <div class="student-chip"
                 draggable="true"
                 data-student="${escHtml(id)}"
                 data-team="${escHtml(team.name)}">
              <span class="chip-dot"></span>
              <span class="chip-label">${escHtml(id)}</span>
            </div>`).join("")
        : `<div class="drop-zone--empty">Drop students here</div>`;

      return `
        <div class="team-card ${isFull ? "team-card--full" : ""}"
             data-team="${escHtml(team.name)}">
          <div class="team-card-header">
            <span class="team-card-name">${escHtml(team.name)}</span>
            ${isFull ? '<span class="team-badge-full">FULL</span>' : ""}
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

  // ── Drag & Drop ─────────────────────────────────────────
  let dragStudent = null;
  let dragFromTeam = null;

  function attachDragDrop() {
    // Draggable chips
    document.querySelectorAll(".student-chip").forEach(chip => {
      chip.addEventListener("dragstart", e => {
        dragStudent  = chip.dataset.student;
        dragFromTeam = chip.dataset.team;
        chip.classList.add("dragging");
        e.dataTransfer.effectAllowed = "move";
      });
      chip.addEventListener("dragend", () => {
        chip.classList.remove("dragging");
      });
    });

    // Drop zones
    document.querySelectorAll(".drop-zone").forEach(zone => {
      zone.addEventListener("dragover", e => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        zone.closest(".team-card").classList.add("team-card--over");
      });
      zone.addEventListener("dragleave", e => {
        if (!zone.contains(e.relatedTarget)) {
          zone.closest(".team-card").classList.remove("team-card--over");
        }
      });
      zone.addEventListener("drop", e => {
        e.preventDefault();
        zone.closest(".team-card").classList.remove("team-card--over");

        const toTeam = zone.dataset.team;
        if (!dragStudent || toTeam === dragFromTeam) return;

        const from = state.teams.find(t => t.name === dragFromTeam);
        const to   = state.teams.find(t => t.name === toTeam);
        if (!from || !to) return;

        // Hard block — refuse drop if target is full
        if (to.members.length >= state.maxSize) {
          alert(`Team "${toTeam}" is full (${state.maxSize} members max).`);
          return;
        }

        from.members = from.members.filter(m => m !== dragStudent);
        if (!to.members.includes(dragStudent)) to.members.push(dragStudent);

        markDirty();
        renderTeams();
      });
    });
  }

  // ── Helpers ─────────────────────────────────────────────
  function markDirty() {
    state.dirty          = true;
    statusUnsaved.hidden = false;
  }

  function setStatus(msg) {
    loadStatus.hidden = false;
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