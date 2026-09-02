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
  } else {
    document.getElementById("staff-section").style.display = "block";
    loadPatients();
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
        ${editable ? `<br><button onclick='startEdit(${escAttr(JSON.stringify(r))})'>Edit</button>` : ""}
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
    <div>${r.request_type} - ${r.request_details} - <strong>${r.status}</strong></div>
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

   start();