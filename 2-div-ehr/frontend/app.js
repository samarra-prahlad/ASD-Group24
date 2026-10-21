const API_URL = "http://localhost:5002";
let token = null;
let myId = null;
let myRole = null;
let summaryPatientId = null;
let patientList = [];

function escAttr(str) {
  return String(str).replace(/'/g, "&#39;");
}

function setupNavLinks() {
  document.getElementById("nav-appointments").href = `http://localhost:3001?token=${token}`;
  document.getElementById("nav-ehr").href = `http://localhost:3002?token=${token}`;
  document.getElementById("nav-pharmacy").href = `http://localhost:3003?token=${token}`;
  document.getElementById("nav-billing").href = `http://localhost:3004?token=${token}`;
  document.getElementById("nav-labtests").href = `http://localhost:3005?token=${token}`;
  document.getElementById("nav-wardbed").href = `http://localhost:3006?token=${token}`;
}

async function start() {
  const params = new URLSearchParams(window.location.search);
  token = params.get("token");

  if (!token) {
    document.body.innerHTML = "<p>No session found. Please <a href='http://localhost:5000/login'>log in</a> first.</p>";
    return;
  }

  const resp = await fetch(`${API_URL}/whoami?token=${token}`);
  if (!resp.ok) {
    document.body.innerHTML = "<p>Session expired. Please <a href='http://localhost:5000/login'>log in</a> again.</p>";
    return;
  }

  const me = await resp.json();
  myId = me.patient_id;
  myRole = me.role;

  setupNavLinks();

  if (myRole === "patient") {
    document.getElementById("patient-section").style.display = "block";
    loadMyRecords();
    loadMyRequests();

    summaryPatientId = myId;
    document.getElementById("assistant-target").textContent = "Summarizing: your own records";
} else {
    document.getElementById("staff-section").style.display = "block";
    loadPatients();
    document.getElementById("multiagent-section").style.display = "block";
    loadMultiAgentHistory();
}
}

function formatDate(dateStr) {
  if (!dateStr) return "";
  const [year, month, day] = dateStr.split("-");
  return `${day}/${month}/${year}`;
}

function showRecords(records, container, editable = false) {
  if (!records.length) {
    container.innerHTML = "<p>No records found.</p>";
    return;
  }
  container.innerHTML = records.map(r => `
    <div id="record-${r.id}">
      <div id="record-view-${r.id}">
        <strong>${formatDate(r.visit_date)}</strong> - ${r.diagnosis}<br>
        Doctor: ${r.doctor_name}<br>
        Treatment: ${r.treatment}<br>
        Notes: ${r.notes}<br>
        Allergies: ${r.allergies}
        ${editable ? `
          <br><button onclick='startEdit(${escAttr(JSON.stringify(r))})'>Edit</button>
          <button onclick="deleteRecord(${r.id}, ${r.patient_id})">Delete</button>
        ` : ""}      
    </div>
    </div>
  `).join("");
}

function startEdit(record) {
  const container = document.getElementById(`record-view-${record.id}`);
  container.innerHTML = `
    <input id="edit-date-${record.id}" type="date" value="${record.visit_date}">
    <input id="edit-diagnosis-${record.id}" value="${record.diagnosis}" placeholder="Diagnosis">
    <input id="edit-doctor-${record.id}" value="${record.doctor_name}" placeholder="Doctor">
    <input id="edit-treatment-${record.id}" value="${record.treatment}" placeholder="Treatment">
    <input id="edit-notes-${record.id}" value="${record.notes}" placeholder="Notes">
    <input id="edit-allergies-${record.id}" value="${record.allergies}" placeholder="Allergies">
    <button onclick="saveEdit(${record.id})">Save</button>
    <button onclick="viewPatient(${record.patient_id}, document.getElementById('detail-patient-name').textContent)">Cancel</button>
  `;
}

async function saveEdit(recordId) {
  const resp = await fetch(`${API_URL}/records/${recordId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      token: token,
      visit_date: document.getElementById(`edit-date-${recordId}`).value,
      diagnosis: document.getElementById(`edit-diagnosis-${recordId}`).value,
      doctor_name: document.getElementById(`edit-doctor-${recordId}`).value,
      treatment: document.getElementById(`edit-treatment-${recordId}`).value,
      notes: document.getElementById(`edit-notes-${recordId}`).value,
      allergies: document.getElementById(`edit-allergies-${recordId}`).value
    })
  });

  if (resp.ok) {
    const patientName = document.getElementById("detail-patient-name").textContent;
    const currentId = summaryPatientId;
    viewPatient(currentId, patientName);
  } else {
    alert("Failed to save changes.");
  }
}

async function deleteRecord(recordId, patientId) {
  const confirmed = confirm("Delete this record? This cannot be undone.");
  if (!confirmed) return;

  const resp = await fetch(`${API_URL}/records/${recordId}?token=${token}`, {
    method: "DELETE"
  });

  if (resp.ok) {
    const patientName = document.getElementById("detail-patient-name").textContent;
    viewPatient(patientId, patientName);
  } else {
    alert("Failed to delete record.");
  }
}

async function loadMyRecords() {
  const resp = await fetch(`${API_URL}/records/${myId}?token=${token}`);
  const records = await resp.json();
  showRecords(records, document.getElementById("patient-records"));
}

async function loadMyRequests() {
  const resp = await fetch(`${API_URL}/change_requests/${myId}?token=${token}`);
  const requests = await resp.json();
  const box = document.getElementById("patient-requests");
  box.innerHTML = requests.map(r => `
    <div><strong>#${r.id}</strong> ${r.request_type} - ${r.request_details} - <strong>${r.status}</strong></div>
  `).join("") || "<p>No requests yet.</p>";
}

async function sendChangeRequest() {
  const type = document.getElementById("req-type").value;
  const details = document.getElementById("req-details").value.trim();
  const status = document.getElementById("req-status");

  const resp = await fetch(`${API_URL}/change_requests`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      token: token,
      patient_id: myId,
      request_type: type,
      request_details: details
    })
  });

  if (resp.ok) {
    status.textContent = "Request submitted.";
    loadMyRequests();
  } else {
    const err = await resp.json();
    status.textContent = "Error: " + (err.error || "unknown");
  }
}

async function loadPatients() {
  const resp = await fetch(`${API_URL}/patients?token=${token}`);
  const patients = await resp.json();
  patientList = patients.filter(p => !p.email_address.toLowerCase().endsWith("@admin.com"));
  showPatients(patientList);
}

function showPatients(patients) {
  const tbody = document.getElementById("patient-table-body");
  tbody.innerHTML = patients.map(p => `
    <tr>
      <td>${p.patient_id}</td>
      <td>${p.first_name} ${p.last_name}</td>
      <td><button onclick="viewPatient(${p.patient_id}, '${escAttr(`${p.first_name} ${p.last_name}`)}')">View</button></td>
    </tr>
  `).join("");
}

function filterPatients() {
  const query = document.getElementById("patient-search").value.trim().toLowerCase();
  if (!query) {
    showPatients(patientList);
    return;
  }
  const matches = patientList.filter(p =>
    p.patient_id.toString() === query ||
    `${p.first_name} ${p.last_name}`.toLowerCase().includes(query)
  );
  showPatients(matches);
}

async function viewPatient(patientId, patientName) {
  summaryPatientId = patientId;
  document.getElementById("ma-patient-id").value = patientId;
  document.getElementById("assistant-target").textContent = `Summarizing: ${patientName}`;
  document.getElementById("patient-detail").style.display = "block";
  document.getElementById("detail-patient-name").textContent = patientName;

  const recordsResp = await fetch(`${API_URL}/records/${patientId}?token=${token}`);
  const records = await recordsResp.json();
  showRecords(records, document.getElementById("detail-records"), true);

  const requestsResp = await fetch(`${API_URL}/change_requests/${patientId}?token=${token}`);
  const requests = await requestsResp.json();
  const box = document.getElementById("detail-requests");
  box.innerHTML = requests.map(r => `
    <div>
      ${r.request_type} - ${r.request_details} - <strong>${r.status}</strong>
      ${r.status === "pending" ? `<button onclick="approveRequest(${r.id}, ${patientId}, '${escAttr(patientName)}')">Approve</button>` : ""}
      <button onclick="deleteChangeRequest(${r.id}, ${patientId}, '${escAttr(patientName)}')">Delete</button>
    </div>
  `).join("") || "<p>No requests found.</p>";
}

function closePatientView() {
  document.getElementById("patient-detail").style.display = "none";
}

async function approveRequest(id, patientId, patientName) {
  await fetch(`${API_URL}/change_requests/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token: token, status: "approved" })
  });
  viewPatient(patientId, patientName);
}

async function deleteChangeRequest(id, patientId, patientName) {
  const confirmed = confirm("Delete this change request? This cannot be undone.");
  if (!confirmed) return;

  const resp = await fetch(`${API_URL}/change_requests/${id}?token=${token}`, {
    method: "DELETE"
  });

  if (resp.ok) {
    viewPatient(patientId, patientName);
  } else {
    alert("Failed to delete change request.");
  }
}

async function addRecord() {
  const status = document.getElementById("add-status");
  const resp = await fetch(`${API_URL}/records`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      token: token,
      patient_id: parseInt(document.getElementById("add-patient-id").value),
      visit_date: document.getElementById("add-visit-date").value,
      diagnosis: document.getElementById("add-diagnosis").value,
      doctor_name: document.getElementById("add-doctor").value,
      treatment: document.getElementById("add-treatment").value,
      notes: document.getElementById("add-notes").value,
      allergies: document.getElementById("add-allergies").value
    })
  });

  if (resp.ok) {
    status.textContent = "Record added.";
  } else {
    const err = await resp.json();
    status.textContent = "Error: " + (err.error || "unknown");
  }
}

async function summarizeHistory() {
  const question = document.getElementById("chat-question").value.trim();
  const box = document.getElementById("chat-result");

  if (!summaryPatientId) {
    box.textContent = "Select a patient first.";
    return;
  }

  box.textContent = "Thinking...";

  const resp = await fetch(`${API_URL}/summarize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token: token, patient_id: summaryPatientId, question: question })
  });

  const data = await resp.json();
  box.textContent = data.reply || data.error || "Something went wrong.";
}

   async function checkChangeRequestStatus() {
  const requestId = document.getElementById("mcp-request-id").value.trim();
  const box = document.getElementById("mcp-result");

  if (!requestId) {
    box.textContent = "Enter a request ID.";
    return;
  }

  box.textContent = "Checking via MCP...";

  const resp = await fetch(`${API_URL}/change_requests/mcp-status/${requestId}?token=${token}`);
  const data = await resp.json();

  if (!resp.ok) {
    box.textContent = "Error: " + (data.error || "unknown");
    return;
  }

  box.innerHTML = `
    Request #${data.request_id} - <strong>${data.status}</strong><br>
    Type: ${data.request_type}
  `;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text == null ? "" : String(text);
  return div.innerHTML;
}

async function askKnowledgeBase() {
  const question = document.getElementById("rag-question").value.trim();
  const box = document.getElementById("rag-result");

  if (!question) {
    box.textContent = "Enter a question.";
    return;
  }

  box.textContent = "Searching knowledge base...";

  const resp = await fetch(`${API_URL}/ask-rag`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token: token, question: question })
  });

  const data = await resp.json();

  if (!resp.ok) {
    box.textContent = "Error: " + (data.error || "unknown");
    return;
  }

  const confidence = data.confidence_category || "";
  const badge = confidence
    ? ` <span class="confidence-badge confidence-${confidence.toLowerCase()}">${escapeHtml(confidence)}</span>`
    : "";

  if (confidence === "Insufficient" || data.status === "insufficient_context") {
        box.innerHTML = `<div class="chat-msg chat-insufficient">${escapeHtml(data.answer)}${badge}</div>`;
    return;
  }

  const sources = [...new Set((data.citations || []).map(c => c.source_id))];
  const sourceList = sources.length
    ? `<ul class="citation-list">${sources.map(s => `<li>${escapeHtml(s)}</li>`).join("")}</ul>`
    : "";

  box.innerHTML = `<div class="chat-msg chat-bot">${escapeHtml(data.answer)}${badge}${sourceList}</div>`;
}

// ---------- Multi-Agent record review (staff only) ----------

let currentWorkflow = null;

function maStatusBadge(status) {
  const cls = {
    awaiting_human_review: "ma-pending",
    approved: "ma-ok",
    partially_approved: "ma-ok",
    corrected: "ma-ok",
    rejected: "ma-bad",
    failed: "ma-bad"
  }[status] || "ma-pending";
  return `<span class="ma-badge ${cls}">${escapeHtml(String(status).replace(/_/g, " "))}</span>`;
}

function maRiskBadge(risk) {
  const level = (risk || "UNKNOWN").toUpperCase();
  const cls = { LOW: "ma-ok", MEDIUM: "ma-warn", HIGH: "ma-bad" }[level] || "ma-pending";
  return `<span class="ma-badge ${cls}">Risk: ${escapeHtml(level)}</span>`;
}

function maAgentBlock(title, step) {
  if (!step) return "";
  const body = step.status === "completed"
    ? escapeHtml(step.output)
    : `<em>${escapeHtml(step.status)}${step.error ? ": " + step.error : ""}</em>`;
  return `
    <div class="ma-agent">
      <h4>${escapeHtml(title)} <span class="ma-model">${escapeHtml(step.model || "")}</span></h4>
      <div class="ma-output">${body}</div>
    </div>`;
}

function renderWorkflow(wf) {
  currentWorkflow = wf;
  const box = document.getElementById("ma-result");
  const steps = wf.steps || {};
  const reviewer = steps.reviewer || {};
  const decided = wf.status !== "awaiting_human_review";

  let decisionHtml = "";
  if (wf.status === "awaiting_human_review") {
    decisionHtml = `
      <h4>Your Decision</h4>
      <input id="ma-notes" type="text" placeholder="Notes (optional)">
      <textarea id="ma-correction" placeholder="Correction (required only for 'Correct')"></textarea>
      <div class="button-row">
        <button onclick="submitMultiAgentDecision('approve')">Approve</button>
        <button onclick="submitMultiAgentDecision('partially_accept')">Partially accept</button>
        <button onclick="submitMultiAgentDecision('correct')">Correct</button>
        <button class="ma-reject" onclick="submitMultiAgentDecision('reject')">Reject</button>
      </div>`;
  } else if (wf.human_review) {
    const hr = wf.human_review;
    decisionHtml = `
      <h4>Decision recorded</h4>
      <div class="ma-output">
        ${escapeHtml(String(hr.decision).replace(/_/g, " "))} by ${escapeHtml(hr.reviewer)}
        ${hr.notes ? "<br>Notes: " + escapeHtml(hr.notes) : ""}
        ${wf.final_output ? "<br><br><strong>Final output:</strong><br>" + escapeHtml(wf.final_output) : ""}
      </div>`;
  }

  const governance = (reviewer.governance_notes || []).length
    ? `<ul class="citation-list">${reviewer.governance_notes.map(n => `<li>${escapeHtml(n)}</li>`).join("")}</ul>`
    : "";

  box.innerHTML = `
    <div class="ma-header">
      <strong>${escapeHtml(wf.workflow_id)}</strong>
      ${maStatusBadge(wf.status)}
      ${reviewer.risk_level ? maRiskBadge(reviewer.risk_level) : ""}
      <span class="ma-model">${escapeHtml(wf.evidence_count)} record(s) used as evidence</span>
    </div>
    ${maAgentBlock("Planner", steps.planner)}
    ${maAgentBlock("Worker", steps.worker)}
    ${maAgentBlock("Reviewer", steps.reviewer)}
    ${reviewer.recommendation ? `<p><strong>Reviewer recommendation:</strong> ${escapeHtml(reviewer.recommendation)}</p>` : ""}
    ${governance}
    ${decided && !wf.human_review ? "" : decisionHtml}
  `;
  box.style.display = "block";
}

async function runMultiAgentWorkflow() {
  const status = document.getElementById("ma-status");
  const btn = document.getElementById("ma-run-btn");
  const patientId = document.getElementById("ma-patient-id").value.trim();
  const userRequest = document.getElementById("ma-request").value.trim();

  if (!patientId) {
    status.textContent = "Enter a patient ID (or click View on a patient).";
    return;
  }
  if (!userRequest) {
    status.textContent = "Enter a request for the agents.";
    return;
  }

  btn.disabled = true;
  status.textContent = "Running Planner, Worker and Reviewer... this can take up to a minute.";
  document.getElementById("ma-result").style.display = "none";

  try {
    const resp = await fetch(`${API_URL}/multi-agent/workflow`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: token, patient_id: patientId, user_request: userRequest })
    });
    const data = await resp.json();

    if (data.status === "disabled") {
      status.textContent = "Multi-Agent is disabled on this deployment.";
      return;
    }
    if (!resp.ok && !data.steps) {
      status.textContent = "Error: " + (data.error || "unknown");
      return;
    }

    status.textContent = data.status === "failed"
      ? "The workflow failed before it could be reviewed."
      : "";
    renderWorkflow(data);
    loadMultiAgentHistory();
  } catch (err) {
    status.textContent = "Could not reach the EHR backend.";
  } finally {
    btn.disabled = false;
  }
}

async function submitMultiAgentDecision(decision) {
  const status = document.getElementById("ma-status");
  if (!currentWorkflow) return;

  const correction = document.getElementById("ma-correction").value.trim();
  if (decision === "correct" && !correction) {
    status.textContent = "Enter a correction before choosing 'Correct'.";
    return;
  }

  status.textContent = "Recording decision...";
  try {
    const resp = await fetch(`${API_URL}/multi-agent/workflow/${currentWorkflow.workflow_id}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token: token,
        decision: decision,
        notes: document.getElementById("ma-notes").value.trim(),
        correction: correction
      })
    });
    const data = await resp.json();

    if (!resp.ok) {
      status.textContent = "Error: " + (data.error || "unknown");
      return;
    }

    status.textContent = "Decision recorded.";
    renderWorkflow(data);
    loadMultiAgentHistory();
  } catch (err) {
    status.textContent = "Could not reach the EHR backend.";
  }
}

async function loadMultiAgentHistory() {
  const box = document.getElementById("ma-history");
  try {
    const resp = await fetch(`${API_URL}/multi-agent/history?token=${token}`);
    const data = await resp.json();

    if (data.status === "disabled") {
      box.textContent = "Multi-Agent is disabled on this deployment.";
      return;
    }
    if (!resp.ok) {
      box.textContent = "History unavailable: " + (data.error || "unknown");
      return;
    }

    const items = data.workflows || [];
    box.innerHTML = items.length
      ? items.map(w => `
          <div class="ma-history-item">
            <strong>${escapeHtml(w.workflow_id)}</strong> ${maStatusBadge(w.status)}
            ${w.steps && w.steps.reviewer && w.steps.reviewer.risk_level ? maRiskBadge(w.steps.reviewer.risk_level) : ""}
            <br>${escapeHtml(w.user_request || "")}
            ${w.human_review ? `<br><span class="ma-model">Decided by ${escapeHtml(w.human_review.reviewer)}</span>` : ""}
          </div>`).join("")
      : "No reviews yet.";
  } catch (err) {
    box.textContent = "History unavailable.";
  }
}

start();