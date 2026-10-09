
"""HealthCare Demo Portal - extended with core healthcare-domain features.

Added: secure login (hashed passwords, tokens, lockout), role-based access,
doctor slots + double-booking prevention, appointment status workflow,
medical records, prescriptions with allergy checks, vitals, billing,
audit log (HIPAA-style PHI access tracking) and a dashboard.
"""
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, jsonify, request, render_template_string, g
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# ---------- in-memory data (swap for a real DB in production) ----------
doctors = [
    {"id": 1, "name": "Dr. Smith", "specialty": "Cardiology", "available": True,
     "hours": ["09:00", "10:00", "11:00", "14:00", "15:00"]},
    {"id": 2, "name": "Dr. Jones", "specialty": "Dermatology", "available": False,
     "hours": ["10:00", "11:00", "13:00"]},
]
patients = [{"id": 1, "name": "Demo Patient", "email": "patient@example.com", "doctor": "Dr. Smith",
             "dob": "1990-05-14", "phone": "", "blood_group": "O+", "allergies": ["penicillin"]}]
appointments, records, prescriptions, vitals, invoices, audit_log = [], [], [], [], [], []

pw = lambda p: generate_password_hash(p)
USERS = {
    "patient@example.com": {"password": pw("Password123"), "role": "patient", "patient_id": 1},
    "doctor@example.com": {"password": pw("Password123"), "role": "doctor", "doctor_id": 1},
    "admin@example.com": {"password": pw("Password123"), "role": "admin"},
}
SESSIONS = {}          # token -> {email, expires}
FAILED = {}            # email -> {count, locked_until}
MAX_FAILS, LOCK_MIN, TOKEN_HOURS = 5, 15, 8

# appointment status workflow: allowed transitions
FLOW = {"BOOKED": {"CONFIRMED", "CANCELLED", "RESCHEDULED"},
        "RESCHEDULED": {"CONFIRMED", "CANCELLED"},
        "CONFIRMED": {"COMPLETED", "CANCELLED", "NO_SHOW"},
        "COMPLETED": set(), "CANCELLED": set(), "NO_SHOW": set()}


# ---------- helpers ----------
def now():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def log(action, target=""):
    audit_log.append({"time": now(), "user": getattr(g, "user", {}).get("email", "anonymous"),
                      "action": action, "target": target})


def auth(*roles):
    """Require a valid bearer token and (optionally) one of the given roles."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            s = SESSIONS.get(token)
            if not s or s["expires"] < datetime.utcnow():
                return jsonify({"error": "Authentication required"}), 401
            g.user = {"email": s["email"], **USERS[s["email"]]}
            if roles and g.user["role"] not in roles:
                log("ACCESS_DENIED", request.path)
                return jsonify({"error": "Forbidden for your role"}), 403
            return fn(*a, **kw)
        return wrapper
    return deco


def can_view_patient(pid):
    u = g.user
    return u["role"] in ("admin", "doctor") or u.get("patient_id") == pid


def find(lst, _id):
    return next((x for x in lst if x["id"] == _id), None)


def missing(data, keys):
    return [k for k in keys if not data.get(k)]


def valid_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def slot_taken(doctor_id, date, time, ignore=None):
    return any(a["doctor_id"] == doctor_id and a["date"] == date and a.get("time") == time
               and a["status"] not in ("CANCELLED", "NO_SHOW") and a["id"] != ignore
               for a in appointments)


# ---------- UI ----------
HTML = '''
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HealthCare Demo</title>
<style>
:root{--ink:#16302f;--mut:#5d7472;--bg:#f3f7f6;--card:#fff;--acc:#0f766e;--bad:#b42318;--line:#d5e2df}
@media(prefers-color-scheme:dark){:root{--ink:#e3f0ee;--mut:#9ab5b1;--bg:#0f1b1a;--card:#162826;--acc:#2dd4bf;--bad:#f97066;--line:#27423f}}
*{box-sizing:border-box}body{margin:0;font:16px/1.5 "Source Sans 3",system-ui,sans-serif;background:var(--bg);color:var(--ink)}
main{max-width:860px;margin:0 auto;padding:24px 16px}
h1{font-size:1.7rem;margin:0 0 4px}h2{font-size:1.1rem;margin:0 0 10px}
section{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:16px;margin:16px 0}
input,select,button{font:inherit;padding:8px 10px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--ink)}
button{background:var(--acc);color:#fff;border:0;cursor:pointer}button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
.row{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}.row>*{flex:1 1 150px}
table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:6px;border-bottom:1px solid var(--line)}
#message{color:var(--mut)}.err{color:var(--bad)!important}.hide{display:none}
.patient-shell{max-width:1180px;margin:20px auto;display:grid;grid-template-columns:230px minmax(0,1fr);gap:22px;padding:0 18px}
.patient-side,.patient-content{background:var(--card);border:1px solid var(--line);border-radius:16px}
.patient-side{padding:20px;height:max-content;position:sticky;top:16px}.brand{font-weight:750;font-size:1.15rem;margin:4px 0 22px;color:var(--acc)}
.patient-nav{display:grid;gap:6px}.patient-nav button{background:transparent;color:var(--ink);text-align:left;border-radius:9px;padding:10px 12px}
.patient-nav button:hover,.patient-nav button.active{background:#dff3ef;color:#075e57}.patient-content{padding:26px;min-height:560px}
.patient-top{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:20px}.patient-top h1{font-size:1.65rem}
.patient-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:12px;margin:18px 0}
.patient-card{padding:16px;background:var(--card);border:1px solid var(--line);border-radius:14px}.patient-card strong{font-size:1.5rem;display:block;color:var(--acc)}
.patient-card span,.subtle{color:var(--mut)}.patient-content table{margin-top:12px}.patient-content input,.patient-content select{background:var(--card)}
.pill{display:inline-block;border-radius:99px;background:#e4f4ef;padding:3px 10px;font-size:.85rem}
@media(max-width:700px){.patient-shell{grid-template-columns:1fr;margin:10px auto}.patient-side{position:static;padding:12px}.brand{margin:2px 0 10px}.patient-nav{display:flex;overflow:auto}.patient-nav button{white-space:nowrap}.patient-content{padding:18px}}
body:has(#patient-app:not(.hide)) main{max-width:none;padding:20px 0}
</style></head><body><main>
<h1>HealthCare Demo Portal</h1>
<p id="message">Sign in to manage appointments, records and billing.</p>

<section id="login-box"><form id="login-form" class="row">
<input id="email" placeholder="Email" autocomplete="username">
<input id="password" type="password" placeholder="Password" autocomplete="current-password">
<button type="submit">Sign in</button></form></section>

<div id="app" class="hide">
<div id="patient-app" class="patient-shell hide">
  <aside class="patient-side"><div class="brand">✚ HealthCare</div><div class="patient-nav" id="patient-nav">
    <button class="active" data-page="home">⌂ &nbsp; Overview</button><button data-page="appointments">▦ &nbsp; Appointments</button>
    <button data-page="records">▤ &nbsp; Medical records</button><button data-page="vitals">♥ &nbsp; Vitals</button>
    <button data-page="medications">＋ &nbsp; Prescriptions</button><button data-page="billing">＄ &nbsp; Billing</button>
    <button data-page="profile">● &nbsp; My profile</button></div>
  </aside>
  <section class="patient-content"><div class="patient-top"><div><p class="subtle" id="patient-greeting">PATIENT PORTAL</p><h1 id="page-title">Your health overview</h1></div><button id="patient-logout">Sign out</button></div>
    <div id="patient-page"></div></section>
</div>
<div id="staff-app">
<section><h2>Overview</h2><div id="stats"></div><button id="logout">Sign out</button></section>
<section><h2>Book an appointment</h2><div class="row">
<select id="doc"></select><input id="date" type="date"><select id="slot"></select>
<input id="reason" placeholder="Reason for visit"><button id="book">Book</button></div></section>
<section><h2>Appointments</h2><table id="appts"></table></section>
<section id="allergy-box" class="hide"><h2>My allergies</h2>
<p>Keep this list current so your care team can check it before prescribing.</p>
<form id="allergy-form" class="row"><input id="allergy-list" aria-label="Allergies" placeholder="Comma-separated allergies">
<button type="submit">Save allergies</button></form><p id="allergy-status" aria-live="polite"></p></section>
</div>
</div>

<script>
let token = "", me = null;
const $ = id => document.getElementById(id);
const say = (t, bad) => { $("message").innerText = t; $("message").className = bad ? "err" : ""; };
async function api(path, method = "GET", body) {
  const r = await fetch(path, {method, headers: {"Content-Type": "application/json", "Authorization": "Bearer " + token},
    body: body ? JSON.stringify(body) : undefined});
  const d = await r.json(); if (!r.ok) throw new Error(d.error || "Request failed"); return d;
}
$("login-form").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    const r = await fetch("/api/login", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({email: $("email").value, password: $("password").value})});
    const d = await r.json(); if (!r.ok) throw new Error(d.error);
    token = d.token; me = d; say(d.message + " as " + d.role);
    $("login-box").classList.add("hide"); $("app").classList.remove("hide"); load();
  } catch (err) { say(err.message, true); }
});
$("logout").onclick = async () => { await api("/api/logout", "POST"); location.reload(); };
async function load() {
  if (me.role === "patient") {
    $("staff-app").classList.add("hide"); $("patient-app").classList.remove("hide");
    $("patient-greeting").innerText = "SIGNED IN AS " + me.email.toUpperCase();
    await showPatientPage("home"); return;
  }
  const docs = await api("/api/doctors");
  $("doc").innerHTML = docs.filter(d => d.available).map(d => `<option value="${d.id}">${d.name} (${d.specialty})</option>`).join("");
  refresh();
  if (me.role !== "patient") { const s = await api("/api/dashboard"); $("stats").innerText = Object.entries(s).map(([k, v]) => k.replaceAll("_", " ") + ": " + v).join("  |  "); }
}
const patientTitles = {home:"Your health overview",appointments:"Appointments",records:"Medical records",vitals:"Vitals",medications:"Prescriptions",billing:"Billing",profile:"My profile"};
function esc(value) { const node = document.createElement("span"); node.textContent = value ?? ""; return node.innerHTML; }
async function showPatientPage(page) {
  $("page-title").innerText = patientTitles[page] || patientTitles.home;
  document.querySelectorAll("#patient-nav button").forEach(b => b.classList.toggle("active", b.dataset.page === page));
  const pid = me.patient_id;
  try {
    const [profile, appointments, records, vitals, prescriptions, invoices] = await Promise.all([
      api(`/api/patients/${pid}`), api("/api/appointments"), api(`/api/patients/${pid}/records`),
      api(`/api/patients/${pid}/vitals`), api(`/api/patients/${pid}/prescriptions`), api("/api/invoices")
    ]);
    const upcoming = appointments.filter(a => !["CANCELLED","COMPLETED","NO_SHOW"].includes(a.status));
    const table = (headers, rows) => `<div style="overflow-x:auto"><table><tr>${headers.map(h=>`<th>${h}</th>`).join("")}</tr>${rows.length ? rows.map(row=>`<tr>${row.map(c=>`<td>${c}</td>`).join("")}</tr>`).join("") : `<tr><td colspan="${headers.length}" class="subtle">Nothing here yet.</td></tr>`}</table></div>`;
    let html = "";
    if (page === "home") html = `<p>Welcome back, <b>${esc(profile.name)}</b>. Here is a snapshot of your care.</p><div class="patient-grid"><div class="patient-card"><strong>${appointments.length}</strong><span>Appointments</span></div><div class="patient-card"><strong>${records.length}</strong><span>Medical records</span></div><div class="patient-card"><strong>${prescriptions.length}</strong><span>Prescriptions</span></div><div class="patient-card"><strong>${invoices.filter(i=>i.status==="UNPAID").length}</strong><span>Unpaid invoices</span></div></div><h2>Upcoming appointments</h2>${table(["Date","Time","Status"],upcoming.slice(0,5).map(a=>[esc(a.date),esc(a.time||"—"),`<span class="pill">${esc(a.status)}</span>`]))}<p class="subtle">Your care information is private to your account.</p>`;
    if (page === "appointments") html = `<h2>Book a visit</h2><div class="row"><select id="doc"></select><input id="date" type="date"><select id="slot"></select><input id="reason" placeholder="Reason for visit"><button id="book">Find and book</button></div><h2>Your appointments</h2>${table(["Date","Time","Status","Action"],appointments.map(a=>[esc(a.date),esc(a.time||"—"),esc(a.status),["BOOKED","CONFIRMED"].includes(a.status)?`<button onclick="cancel(${a.id})">Cancel</button>`:"—"]))}`;
    if (page === "records") html = `<p class="subtle">Visit notes and diagnoses shared by your care team.</p>${table(["Date","Diagnosis","Notes"],records.map(r=>[esc(r.date),esc(r.diagnosis),esc(r.notes||"—")]))}`;
    if (page === "vitals") html = `<p class="subtle">Measurements recorded by your care team.</p>${table(["Recorded","Heart rate","Blood pressure","Temperature","Alerts"],vitals.map(v=>[esc(v.recorded_at),`${esc(v.heart_rate)} bpm`,`${esc(v.systolic)}/${esc(v.diastolic)}`,`${esc(v.temperature_c)} °C`,esc((v.alerts||[]).join(", ")||"None")]))}`;
    if (page === "medications") html = `<p class="subtle">Your current prescription information.</p>${table(["Medication","Dosage","Duration","Issued"],prescriptions.map(r=>[esc(r.medication),esc(r.dosage),`${esc(r.duration_days)} days`,esc(r.issued_at)]))}`;
    if (page === "billing") html = `<p class="subtle">Invoices linked to your patient account.</p>${table(["Description","Amount","Status","Created"],invoices.map(i=>[esc(i.description||"Care service"),`$${Number(i.amount).toFixed(2)}`,esc(i.status),esc(i.created_at)]))}`;
    if (page === "profile") html = `<h2>Personal details</h2><div class="patient-grid"><div class="patient-card"><span>Name</span><b>${esc(profile.name)}</b></div><div class="patient-card"><span>Email</span><b>${esc(profile.email)}</b></div><div class="patient-card"><span>Date of birth</span><b>${esc(profile.dob||"Not provided")}</b></div><div class="patient-card"><span>Blood group</span><b>${esc(profile.blood_group||"Not provided")}</b></div></div><h2>Allergies</h2><p class="subtle">Keep this list current so your care team can check it before prescribing.</p><form id="allergy-form" class="row"><input id="allergy-list" aria-label="Allergies" value="${esc((profile.allergies||[]).join(", "))}" placeholder="Comma-separated allergies"><button type="submit">Save allergies</button></form><p id="allergy-status" aria-live="polite"></p>`;
    $("patient-page").innerHTML = html;
    if (page === "appointments") { const docs=await api("/api/doctors"); $("doc").innerHTML=docs.filter(d=>d.available).map(d=>`<option value="${d.id}">${esc(d.name)} (${esc(d.specialty)})</option>`).join(""); $("date").onchange=slots; $("doc").onchange=slots; $("book").onclick=async()=>{try{await api("/api/appointments","POST",{patient_id:pid,doctor_id:+$("doc").value,date:$("date").value,time:$("slot").value,reason:$("reason").value});say("Appointment booked");showPatientPage("appointments");}catch(e){say(e.message,true);}}; }
    if (page === "profile") $("allergy-form").onsubmit=async e=>{e.preventDefault();try{const updated=await api(`/api/patients/${pid}/allergies`,"PUT",{allergies:$("allergy-list").value.split(",").map(x=>x.trim()).filter(Boolean)});$("allergy-list").value=updated.allergies.join(", ");$("allergy-status").innerText="Allergy list updated.";}catch(err){$("allergy-status").innerText=err.message;}};
  } catch(e) { $("patient-page").innerText = e.message; }
}
$("patient-nav").onclick=e=>{const button=e.target.closest("button[data-page]");if(button)showPatientPage(button.dataset.page);};
$("patient-logout").onclick=async()=>{await api("/api/logout","POST");location.reload();};
async function refresh() {
  const list = await api("/api/appointments");
  $("appts").innerHTML = "<tr><th>Date</th><th>Time</th><th>Status</th><th></th></tr>" + list.map(a =>
    `<tr><td>${a.date}</td><td>${a.time || ""}</td><td>${a.status}</td><td>${["BOOKED","CONFIRMED"].includes(a.status) ? `<button onclick="cancel(${a.id})">Cancel</button>` : ""}</td></tr>`).join("");
}
async function cancel(id) { try { await api("/api/appointments/" + id, "DELETE"); say("Appointment cancelled"); if (me.role === "patient") showPatientPage("appointments"); else refresh(); } catch (e) { say(e.message, true); } }
async function slots() {
  if (!$("date").value) return;
  try { const s = await api(`/api/doctors/${$("doc").value}/slots?date=${$("date").value}`);
    $("slot").innerHTML = s.free.map(t => `<option>${t}</option>`).join("") || "<option value=''>No free slots</option>"; }
  catch (e) { say(e.message, true); }
}
$("date").onchange = slots; $("doc").onchange = slots;
$("book").onclick = async () => {
  try { await api("/api/appointments", "POST", {patient_id: me.patient_id || 1, doctor_id: +$("doc").value,
    date: $("date").value, time: $("slot").value, reason: $("reason").value});
    say("Appointment booked"); refresh(); slots(); } catch (e) { say(e.message, true); }
};
$("allergy-form").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    const allergies = $("allergy-list").value.split(",").map(value => value.trim()).filter(Boolean);
    const profile = await api(`/api/patients/${me.patient_id}/allergies`, "PUT", {allergies});
    $("allergy-list").value = profile.allergies.join(", ");
    $("allergy-status").innerText = "Allergy list updated.";
  } catch (err) { $("allergy-status").innerText = err.message; }
});
</script></main></body></html>
'''


@app.get("/")
def home():
    return render_template_string(HTML)


# ---------- authentication ----------
@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    f = FAILED.get(email, {"count": 0, "locked_until": None})
    if f["locked_until"] and f["locked_until"] > datetime.utcnow():
        return jsonify({"error": "Account locked. Try again later."}), 423
    user = USERS.get(email)
    if not user or not check_password_hash(user["password"], data.get("password") or ""):
        f["count"] += 1
        if f["count"] >= MAX_FAILS:
            f = {"count": 0, "locked_until": datetime.utcnow() + timedelta(minutes=LOCK_MIN)}
        FAILED[email] = f
        return jsonify({"error": "Invalid credentials"}), 401
    FAILED.pop(email, None)
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {"email": email, "expires": datetime.utcnow() + timedelta(hours=TOKEN_HOURS)}
    g.user = {"email": email}
    log("LOGIN")
    return jsonify({"message": "Login successful", "role": user["role"], "email": email, "token": token,
                    "patient_id": user.get("patient_id"), "doctor_id": user.get("doctor_id")})


@app.post("/api/logout")
@auth()
def logout():
    SESSIONS.pop(request.headers["Authorization"].removeprefix("Bearer ").strip(), None)
    log("LOGOUT")
    return jsonify({"message": "Logged out"})


@app.get("/api/me")
@auth()
def me():
    return jsonify({k: v for k, v in g.user.items() if k != "password"})


# ---------- doctors & availability ----------
@app.get("/api/doctors")
def list_doctors():
    spec = request.args.get("specialty", "").lower()
    return jsonify([{k: v for k, v in d.items() if k != "hours"} for d in doctors
                    if spec in d["specialty"].lower()])


@app.get("/api/doctors/<int:doctor_id>/slots")
def doctor_slots(doctor_id):
    d = find(doctors, doctor_id)
    if not d:
        return jsonify({"error": "Doctor not found"}), 404
    date = request.args.get("date", "")
    if not valid_date(date):
        return jsonify({"error": "date must be YYYY-MM-DD"}), 400
    free = [t for t in d["hours"] if d["available"] and not slot_taken(doctor_id, date, t)]
    return jsonify({"doctor_id": doctor_id, "date": date, "free": free})


# ---------- patients ----------
@app.get("/api/patients")
@auth("doctor", "admin")
def get_patients():
    q = request.args.get("q", "").lower()
    log("VIEW_PATIENT_LIST")
    return jsonify([p for p in patients if q in p["name"].lower() or q in p["email"].lower()])


@app.post("/api/patients")
@auth("doctor", "admin")
def create_patient():
    data = request.get_json(silent=True) or {}
    if missing(data, ["name", "email"]):
        return jsonify({"error": "name and email are required"}), 400
    if "@" not in data["email"]:
        return jsonify({"error": "email is invalid"}), 400
    if any(p["email"].lower() == data["email"].lower() for p in patients):
        return jsonify({"error": "patient with this email already exists"}), 409
    patient = {"id": len(patients) + 1, "name": data["name"], "email": data["email"],
               "doctor": data.get("doctor", ""), "dob": data.get("dob", ""), "phone": data.get("phone", ""),
               "blood_group": data.get("blood_group", ""), "allergies": data.get("allergies", [])}
    patients.append(patient)
    log("CREATE_PATIENT", str(patient["id"]))
    return jsonify(patient), 201


@app.get("/api/patients/<int:pid>")
@auth()
def get_patient(pid):
    p = find(patients, pid)
    if not p:
        return jsonify({"error": "Patient not found"}), 404
    if not can_view_patient(pid):
        return jsonify({"error": "Forbidden for your role"}), 403
    log("VIEW_PATIENT", str(pid))
    return jsonify(p)


@app.put("/api/patients/<int:pid>/allergies")
@auth()
def update_patient_allergies(pid):
    patient = find(patients, pid)
    if not patient:
        return jsonify({"error": "Patient not found"}), 404
    if g.user["role"] != "patient" or g.user.get("patient_id") != pid:
        log("ACCESS_DENIED", f"/api/patients/{pid}/allergies")
        return jsonify({"error": "Only the patient can update their own allergy list"}), 403
    data = request.get_json(silent=True) or {}
    allergies = data.get("allergies")
    if not isinstance(allergies, list) or any(not isinstance(item, str) or not item.strip() for item in allergies):
        return jsonify({"error": "allergies must be a list of non-empty strings"}), 400
    cleaned = []
    seen = set()
    for item in allergies:
        value = item.strip()
        key = value.casefold()
        if key not in seen:
            cleaned.append(value)
            seen.add(key)
    patient["allergies"] = cleaned
    log("UPDATE_ALLERGIES", str(pid))
    return jsonify({"patient_id": pid, "allergies": cleaned})


# ---------- appointments ----------
@app.get("/api/appointments")
@auth()
def get_appointments():
    u = g.user
    items = appointments
    if u["role"] == "patient":
        items = [a for a in items if a["patient_id"] == u["patient_id"]]
    elif u["role"] == "doctor":
        items = [a for a in items if a["doctor_id"] == u["doctor_id"]]
    if request.args.get("status"):
        items = [a for a in items if a["status"] == request.args["status"].upper()]
    return jsonify(items)


@app.post("/api/appointments")
@auth()
def create_appointment():
    data = request.get_json(silent=True) or {}
    if missing(data, ["patient_id", "doctor_id", "date"]):
        return jsonify({"error": "patient_id, doctor_id and date are required"}), 400
    d = valid_date(data["date"])
    if not d:
        return jsonify({"error": "date must be YYYY-MM-DD"}), 400
    if d.date() < datetime.utcnow().date():
        return jsonify({"error": "Cannot book an appointment in the past"}), 400
    if g.user["role"] == "patient":
        data["patient_id"] = g.user["patient_id"]
    if not find(patients, data["patient_id"]):
        return jsonify({"error": "Patient not found"}), 404
    doc = find(doctors, data["doctor_id"])
    if not doc:
        return jsonify({"error": "Doctor not found"}), 404
    if not doc["available"]:
        return jsonify({"error": "Doctor is not available"}), 409
    if data.get("time") and data["time"] not in doc["hours"]:
        return jsonify({"error": "Time is outside doctor's working hours"}), 400
    if slot_taken(data["doctor_id"], data["date"], data.get("time")):
        return jsonify({"error": "Slot already booked"}), 409
    appt = {"id": len(appointments) + 1, "patient_id": data["patient_id"], "doctor_id": data["doctor_id"],
            "date": data["date"], "time": data.get("time", ""), "reason": data.get("reason", ""),
            "status": "BOOKED", "created_at": now()}
    appointments.append(appt)
    log("BOOK_APPOINTMENT", str(appt["id"]))
    return jsonify(appt), 201


@app.put("/api/appointments/<int:appointment_id>")
@auth()
def update_appointment(appointment_id):
    appt = find(appointments, appointment_id)
    if not appt:
        return jsonify({"error": "Appointment not found"}), 404
    if not can_view_patient(appt["patient_id"]):
        return jsonify({"error": "Forbidden for your role"}), 403
    data = request.get_json(silent=True) or {}
    new = data.get("status")
    if new and new != appt["status"]:
        if new not in FLOW.get(appt["status"], set()):
            return jsonify({"error": f"Cannot change status from {appt['status']} to {new}"}), 409
        if g.user["role"] == "patient" and new != "CANCELLED":
            return jsonify({"error": "Patients can only cancel"}), 403
    date, time = data.get("date", appt["date"]), data.get("time", appt["time"])
    if (date, time) != (appt["date"], appt["time"]):
        if not valid_date(date):
            return jsonify({"error": "date must be YYYY-MM-DD"}), 400
        if slot_taken(appt["doctor_id"], date, time, ignore=appt["id"]):
            return jsonify({"error": "Slot already booked"}), 409
        appt["status"] = "RESCHEDULED" if not new else new
    appt.update({k: v for k, v in data.items() if k in ("date", "time", "reason", "status")})
    log("UPDATE_APPOINTMENT", str(appointment_id))
    return jsonify(appt)


@app.delete("/api/appointments/<int:appointment_id>")
@auth()
def delete_appointment(appointment_id):
    appt = find(appointments, appointment_id)
    if not appt:
        return jsonify({"error": "Appointment not found"}), 404
    if not can_view_patient(appt["patient_id"]):
        return jsonify({"error": "Forbidden for your role"}), 403
    if appt["status"] in ("COMPLETED", "CANCELLED"):
        return jsonify({"error": f"Appointment already {appt['status']}"}), 409
    appt["status"] = "CANCELLED"   # soft delete: medical history is never erased
    log("CANCEL_APPOINTMENT", str(appointment_id))
    return jsonify(appt)


# ---------- clinical: records, vitals, prescriptions ----------
@app.route("/api/patients/<int:pid>/records", methods=["GET", "POST"])
@auth()
def patient_records(pid):
    if not find(patients, pid):
        return jsonify({"error": "Patient not found"}), 404
    if not can_view_patient(pid):
        return jsonify({"error": "Forbidden for your role"}), 403
    if request.method == "POST":
        if g.user["role"] != "doctor":
            return jsonify({"error": "Only doctors can add medical records"}), 403
        data = request.get_json(silent=True) or {}
        if missing(data, ["diagnosis"]):
            return jsonify({"error": "diagnosis is required"}), 400
        rec = {"id": len(records) + 1, "patient_id": pid, "doctor_id": g.user["doctor_id"],
               "diagnosis": data["diagnosis"], "notes": data.get("notes", ""), "date": now()}
        records.append(rec)
        log("ADD_RECORD", str(pid))
        return jsonify(rec), 201
    log("VIEW_RECORDS", str(pid))
    return jsonify([r for r in records if r["patient_id"] == pid])


@app.route("/api/patients/<int:pid>/vitals", methods=["GET", "POST"])
@auth()
def patient_vitals(pid):
    if not find(patients, pid):
        return jsonify({"error": "Patient not found"}), 404
    if not can_view_patient(pid):
        return jsonify({"error": "Forbidden for your role"}), 403
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        try:
            hr, sys_bp, dia_bp = int(data["heart_rate"]), int(data["systolic"]), int(data["diastolic"])
            temp = float(data["temperature_c"])
        except (KeyError, ValueError, TypeError):
            return jsonify({"error": "heart_rate, systolic, diastolic, temperature_c must be numbers"}), 400
        if not (20 <= hr <= 250 and 40 <= sys_bp <= 300 and 20 <= dia_bp <= 200 and 30 <= temp <= 45):
            return jsonify({"error": "Vital values are outside plausible range"}), 400
        alerts = []
        if hr > 100 or hr < 50: alerts.append("Abnormal heart rate")
        if sys_bp >= 140 or dia_bp >= 90: alerts.append("High blood pressure")
        if temp >= 38: alerts.append("Fever")
        v = {"id": len(vitals) + 1, "patient_id": pid, "heart_rate": hr, "systolic": sys_bp,
             "diastolic": dia_bp, "temperature_c": temp, "alerts": alerts, "recorded_at": now()}
        vitals.append(v)
        log("ADD_VITALS", str(pid))
        return jsonify(v), 201
    return jsonify([v for v in vitals if v["patient_id"] == pid])


@app.route("/api/patients/<int:pid>/prescriptions", methods=["GET", "POST"])
@auth()
def patient_prescriptions(pid):
    p = find(patients, pid)
    if not p:
        return jsonify({"error": "Patient not found"}), 404
    if not can_view_patient(pid):
        return jsonify({"error": "Forbidden for your role"}), 403
    if request.method == "POST":
        if g.user["role"] != "doctor":
            return jsonify({"error": "Only doctors can prescribe"}), 403
        data = request.get_json(silent=True) or {}
        if missing(data, ["medication", "dosage", "duration_days"]):
            return jsonify({"error": "medication, dosage and duration_days are required"}), 400
        if data["medication"].lower() in [a.lower() for a in p["allergies"]]:
            return jsonify({"error": f"Patient is allergic to {data['medication']}"}), 409
        rx = {"id": len(prescriptions) + 1, "patient_id": pid, "doctor_id": g.user["doctor_id"],
              "medication": data["medication"], "dosage": data["dosage"],
              "duration_days": data["duration_days"], "issued_at": now()}
        prescriptions.append(rx)
        log("ISSUE_PRESCRIPTION", str(pid))
        return jsonify(rx), 201
    return jsonify([r for r in prescriptions if r["patient_id"] == pid])


# ---------- billing ----------
@app.route("/api/invoices", methods=["GET", "POST"])
@auth()
def invoices_route():
    u = g.user
    if request.method == "POST":
        if u["role"] not in ("admin", "doctor"):
            return jsonify({"error": "Forbidden for your role"}), 403
        data = request.get_json(silent=True) or {}
        try:
            amount = round(float(data["amount"]), 2)
            assert amount > 0
        except (KeyError, ValueError, TypeError, AssertionError):
            return jsonify({"error": "amount must be a positive number"}), 400
        if not find(patients, data.get("patient_id")):
            return jsonify({"error": "Patient not found"}), 404
        inv = {"id": len(invoices) + 1, "patient_id": data["patient_id"], "amount": amount,
               "description": data.get("description", ""), "status": "UNPAID", "created_at": now()}
        invoices.append(inv)
        log("CREATE_INVOICE", str(inv["id"]))
        return jsonify(inv), 201
    items = invoices if u["role"] != "patient" else [i for i in invoices if i["patient_id"] == u["patient_id"]]
    return jsonify(items)


@app.post("/api/invoices/<int:invoice_id>/pay")
@auth()
def pay_invoice(invoice_id):
    inv = find(invoices, invoice_id)
    if not inv:
        return jsonify({"error": "Invoice not found"}), 404
    if not can_view_patient(inv["patient_id"]):
        return jsonify({"error": "Forbidden for your role"}), 403
    if inv["status"] == "PAID":
        return jsonify({"error": "Invoice already paid"}), 409
    inv.update(status="PAID", paid_at=now())
    log("PAY_INVOICE", str(invoice_id))
    return jsonify(inv)


# ---------- admin: dashboard & audit ----------
@app.get("/api/dashboard")
@auth("doctor", "admin")
def dashboard():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return jsonify({
        "total_patients": len(patients),
        "appointments_today": sum(a["date"] == today and a["status"] != "CANCELLED" for a in appointments),
        "pending_confirmation": sum(a["status"] == "BOOKED" for a in appointments),
        "cancelled": sum(a["status"] == "CANCELLED" for a in appointments),
        "unpaid_revenue": round(sum(i["amount"] for i in invoices if i["status"] == "UNPAID"), 2),
    })


@app.get("/api/audit")
@auth("admin")
def audit():
    return jsonify(audit_log[-200:])


@app.get("/api/health")
def health():
    return jsonify({"status": "UP", "time": now()})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
