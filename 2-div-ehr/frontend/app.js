const API_URL = "http://localhost:5002";
const SHARED_DB_URL = "http://localhost:6000";
let token = null;
let myId = null;
let myRole = null;
let patientList = [];

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

function showRecords(records, container) {
  if (!records.length) {
    container.innerHTML = "<p>No records found.</p>";
    return;
  }
  container.innerHTML = records.map(r => `
    <div>
      <strong>${formatDate(r.visit_date)}</strong> - ${r.diagnosis}<br>
      Doctor: ${r.doctor_name}<br>
      Treatment: ${r.treatment}<br>
      Notes: ${r.notes}<br>
      Allergies: ${r.allergies}
    </div>
    <hr>
  `).join("");
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
  const resp = await fetch(`${SHARED_DB_URL}/patients`);
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
      <td><button onclick="viewPatient(${p.patient_id}, '${p.first_name} ${p.last_name}')">View</button></td>
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
  document.getElementById("patient-detail").style.display = "block";
  document.getElementById("detail-patient-name").textContent = patientName;

  const recordsResp = await fetch(`${API_URL}/records/${patientId}?token=${token}`);
  const records = await recordsResp.json();
  showRecords(records, document.getElementById("detail-records"));

  const requestsResp = await fetch(`${API_URL}/change_requests/${patientId}?token=${token}`);
  const requests = await requestsResp.json();
  const box = document.getElementById("detail-requests");
  box.innerHTML = requests.map(r => `
    <div>
      ${r.request_type} - ${r.request_details} - <strong>${r.status}</strong>
      ${r.status === "pending" ? `<button onclick="approveRequest(${r.id}, ${patientId}, '${patientName}')">Approve</button>` : ""}
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

async function askBot() {
  const question = document.getElementById("chat-question").value.trim();
  const box = document.getElementById("chat-result");
  if (!question) return;

  box.textContent = "Thinking...";
  const formData = new FormData();
  formData.append("question", question);

  const resp = await fetch(`${API_URL}/ask`, { method: "POST", body: formData });
  box.innerHTML = await resp.text();
}

async function askBotWithContext() {
  const question = document.getElementById("chat-question").value.trim();
  const box = document.getElementById("chat-result");
  if (!question) return;

  box.textContent = "Thinking with context...";
  const formData = new FormData();
  formData.append("question", question);

  const resp = await fetch(`${API_URL}/ask-with-context`, { method: "POST", body: formData });
  box.innerHTML = await resp.text();
}

document.addEventListener("DOMContentLoaded", () => {
  start();

  document.getElementById("req-details").addEventListener("keypress", (e) => {
    if (e.key === "Enter") sendChangeRequest();
  });

  document.getElementById("patient-search").addEventListener("keypress", (e) => {
    if (e.key === "Enter") filterPatients();
  });

  document.getElementById("chat-question").addEventListener("keypress", (e) => {
    if (e.key === "Enter") askBot();
  });
});