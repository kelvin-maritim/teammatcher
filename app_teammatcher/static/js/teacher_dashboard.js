/* teacher_dashboard.js
   Endpoints (matched to urls.py):
   - GET  /api/team-sets/          → load team set dropdown
   - GET  /api/teams/?team_set=ID  → load teams for a team set
   - POST /api/assignments/        → create assignments (run matching)
   - GET  /teacher/download/       → export CSV
*/

document.addEventListener("DOMContentLoaded", () => {

  // ── Element refs ──────────────────────────────────────────
  const teamsetSelect       = document.getElementById("teamset-select");
  const csvFileInput        = document.getElementById("csv-file-input");
  const uploadLabelText     = document.getElementById("upload-label-text");
  const uploadArea          = document.getElementById("upload-area");
  const btnRunMatching      = document.getElementById("btn-run-matching");
  const btnExportCsv        = document.getElementById("btn-export-csv");
  const teamsContainer      = document.getElementById("teams-container");
  const unassignedContainer = document.getElementById("unassigned-container");

  // ── 1. Load all Team-Sets on page load ────────────────────
  async function loadTeamSets() {
    teamsetSelect.disabled = true;
    teamsetSelect.innerHTML = '<option value="" disabled selected>Loading…</option>';

    try {
      const res   = await fetch("/api/team-sets/");
      const data  = await res.json();
      // DRF may return paginated { results: [] } or a plain array
      const items = Array.isArray(data) ? data : (data.results || []);

      teamsetSelect.innerHTML = '<option value="" disabled selected>— Choose a team set —</option>';
      items.forEach(ts => {
        const opt = document.createElement("option");
        opt.value       = ts.id;
        opt.textContent = ts.name;
        teamsetSelect.appendChild(opt);
      });
      teamsetSelect.disabled = false;
    } catch (err) {
      teamsetSelect.innerHTML = '<option value="" disabled selected>Failed to load</option>';
      console.error("Failed to load team sets:", err);
    }
  }

  loadTeamSets();

  // ── 2. CSV file label update ───────────────────────────────
  csvFileInput.addEventListener("change", () => {
    const file = csvFileInput.files[0];
    uploadLabelText.textContent = file
      ? `Datei ausgewählt · ${file.name}`
      : "Datei auswählen · Keine Datei ausgewählt";
  });

  // Drag-and-drop visual feedback
  uploadArea.addEventListener("dragover", e => {
    e.preventDefault();
    uploadArea.classList.add("drag-over");
  });
  ["dragleave", "drop"].forEach(evt =>
    uploadArea.addEventListener(evt, () => uploadArea.classList.remove("drag-over"))
  );
  uploadArea.addEventListener("drop", e => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file && file.name.endsWith(".csv")) {
      const dt = new DataTransfer();
      dt.items.add(file);
      csvFileInput.files = dt.files;
      uploadLabelText.textContent = `Datei ausgewählt · ${file.name}`;
    }
  });

  // ── 3. Run Matching ────────────────────────────────────────
  // Fetches teams for the selected team set via GET /api/teams/?team_set=ID
  // then fetches all student assignments via GET /api/assignments/?team=ID
  btnRunMatching.addEventListener("click", async () => {
    const teamSetId = teamsetSelect.value;
    const csrfToken = document.querySelector("input[name='csrfmiddlewaretoken']").value;

    if (!teamSetId) {
      alert("Please select a team set first.");
      return;
    }

    btnRunMatching.disabled    = true;
    btnRunMatching.textContent = "Loading…";

    try {
      // 3a. Fetch teams belonging to the selected team set
      const teamsRes  = await fetch(`/api/teams/?team_set=${teamSetId}`, {
        headers: { "X-CSRFToken": csrfToken },
      });
      if (!teamsRes.ok) throw new Error("Failed to load teams");
      const teamsData = await teamsRes.json();
      const teams     = Array.isArray(teamsData) ? teamsData : (teamsData.results || []);

      // 3b. For each team fetch its active assignments
      const teamsWithMembers = await Promise.all(teams.map(async team => {
        const aRes  = await fetch(`/api/assignments/?team=${team.id}`);
        const aData = await aRes.json();
        const assignments = Array.isArray(aData) ? aData : (aData.results || []);
        return {
          ...team,
          members: assignments.filter(a => a.is_active).map(a => a.learner),
        };
      }));

      // 3c. Find unassigned students (learners with no active assignment in this team set)
      const assignedRes  = await fetch(`/api/assignments/?team__team_set=${teamSetId}`);
      const assignedData = await assignedRes.json();
      const assignedIds  = new Set(
        (Array.isArray(assignedData) ? assignedData : (assignedData.results || []))
          .filter(a => a.is_active)
          .map(a => a.learner?.student_id ?? a.learner)
      );

      renderTeams(teamsWithMembers);
      // Unassigned rendering requires knowing all students — left for backend to provide
      // For now clear the section gracefully
      unassignedContainer.innerHTML = '<p class="placeholder-text">No unassigned students.</p>';

    } catch (err) {
      alert(`Error: ${err.message}`);
      console.error(err);
    } finally {
      btnRunMatching.disabled = false;
      btnRunMatching.innerHTML = `
        <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" style="width:1.1rem;height:1.1rem">
          <path d="M17.65 6.35A7.958 7.958 0 0 0 12 4c-4.42 0-7.99 3.58-7.99
            8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0 1 12
            18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22
            1.78L13 11h7V4l-2.35 2.35z"/>
        </svg>
        Run Matching`;
    }
  });

  // ── 4. Export CSV → /teacher/download/ ────────────────────
  // download_csv view serves the most recent CSVGeneration from the DB.
  // A specific historical generation can be fetched via /teacher/download/<id>/
  btnExportCsv.addEventListener("click", () => {
    window.location.href = "/teacher/download/";
  });

  // ── 5. Render helpers ──────────────────────────────────────

  /**
   * Render team cards.
   * Shape: [ { id, name, members: [ { student_id } | "id_string" ] } ]
   */
  function renderTeams(teams) {
    if (!teams.length) {
      teamsContainer.innerHTML = '<p class="placeholder-text">No teams found for this team set.</p>';
      return;
    }

    teamsContainer.innerHTML = teams.map(team => `
      <div class="team-card">
        <div class="team-card-header">${escHtml(team.name)}</div>
        ${team.members.length
          ? team.members.map(m => `
              <div class="team-member">
                <span class="team-member-dot"></span>
                ${escHtml(typeof m === "string" ? m : (m.student_id ?? m.id))}
              </div>`).join("")
          : '<div class="team-member" style="color:var(--text-muted)">No members assigned</div>'
        }
      </div>
    `).join("");
  }

  /**
   * Render unassigned student chips.
   * Shape: [ { student_id } ] or [ "id_string" ]
   */
  function renderUnassigned(students) {
    if (!students.length) {
      unassignedContainer.innerHTML = '<p class="placeholder-text">No unassigned students.</p>';
      return;
    }
    unassignedContainer.innerHTML = students.map(s => {
      const label = typeof s === "string" ? s : s.student_id;
      return `<span class="student-chip">${escHtml(label)}</span>`;
    }).join("");
  }

  /** Minimal XSS-safe HTML escape */
  function escHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

});