import os, sqlite3, uuid
from datetime import datetime
from flask import Flask, request, redirect, url_for, session, flash, render_template_string, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-demo-secret")
DB_PATH = os.environ.get("DB_PATH", "/data/campus.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

USERS = [
    ("admin", "admin123", "Administrator"),
    ("manager", "manager123", "Facility Manager"),
    ("tech", "tech123", "Technician"),
    ("approver", "approve123", "Approver"),
    ("student", "student123", "Student"),
]

def connect():
    c = sqlite3.connect(DB_PATH, timeout=20, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=20000")
    return c

def init_db():
    c = connect()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY, password TEXT NOT NULL, role TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS facilities(id INTEGER PRIMARY KEY, name TEXT NOT NULL, restricted INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS bookings(id INTEGER PRIMARY KEY AUTOINCREMENT, facility_id INTEGER NOT NULL, username TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS tickets(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT NOT NULL, category TEXT NOT NULL, priority TEXT NOT NULL, assigned_to TEXT, status TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, idempotency_key TEXT UNIQUE, created_at TEXT NOT NULL, inspection TEXT DEFAULT '', resolution TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS approvals(id INTEGER PRIMARY KEY AUTOINCREMENT, booking_id INTEGER NOT NULL, approver TEXT NOT NULL, decision TEXT NOT NULL, note TEXT DEFAULT '', created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL, action TEXT NOT NULL, item_type TEXT NOT NULL, item_id INTEGER NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL);
    """)
    for u,p,r in USERS:
        c.execute("INSERT OR IGNORE INTO users VALUES(?,?,?)", (u,p,r))
    for name,restricted in [("Central Seminar Hall",0),("Computer Laboratory 1",1),("Library Discussion Room",0),("Robotics Lab",1)]:
        c.execute("INSERT OR IGNORE INTO facilities(name,restricted) SELECT ?,? WHERE NOT EXISTS(SELECT 1 FROM facilities WHERE name=?)", (name,restricted,name))
    c.close()

def audit(actor, action, typ, item_id, detail):
    c = connect()
    c.execute("INSERT INTO audit(actor,action,item_type,item_id,detail,created_at) VALUES(?,?,?,?,?,?)",
              (actor,action,typ,item_id,detail,datetime.now().isoformat(timespec="seconds")))
    c.close()

def current_user():
    return session.get("username")

def role():
    return session.get("role","")

PAGE = r"""
<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smart Campus Platform</title>
<style>
body{font-family:Arial,sans-serif;background:#f3f6fa;margin:0;color:#182230}header{background:#183b66;color:white;padding:18px 5%;display:flex;justify-content:space-between;align-items:center}
main{max-width:1100px;margin:24px auto;padding:0 16px}.card{background:white;border-radius:12px;padding:18px;margin:14px 0;box-shadow:0 2px 9px #0001}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}
input,select,textarea,button{padding:10px;margin:5px 0;border:1px solid #cbd5e1;border-radius:7px;width:100%;box-sizing:border-box}
button{background:#1d5fa7;color:white;border:0;font-weight:bold;cursor:pointer}button:hover{background:#174b85}
small,.muted{color:#64748b}.pill{padding:4px 8px;border-radius:20px;background:#e5eef9;font-size:12px}
table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:9px;border-bottom:1px solid #e5e7eb;font-size:14px}
a{color:#dcecff}.notice{padding:10px;background:#fff3cd;border-radius:8px;margin:8px 0}.success{background:#dff5e6}
form.inline{display:inline}form.inline button{width:auto;padding:7px 10px}
</style></head><body>
<header><div><b>Smart Campus</b><br><small style="color:#dcecff">Facility Booking & Maintenance Platform</small></div>
<div>{% if user %}{{user}} ({{role}}) · <a href="/logout">Logout</a>{% endif %}</div></header>
<main>
{% with messages=get_flashed_messages() %}{% for m in messages %}<div class="notice">{{m}}</div>{% endfor %}{% endwith %}
{% if not user %}
<div class="card" style="max-width:430px;margin:55px auto"><h2>Sign in</h2><form method="post" action="/login">
<label>Username</label><input name="username" required><label>Password</label><input type="password" name="password" required><button>Login</button></form>
<p class="muted">Demo users: admin/admin123 · manager/manager123 · tech/tech123 · approver/approve123 · student/student123</p></div>
{% else %}
<div class="grid">
<div class="card"><h3>Facilities</h3><h2>{{facilities|length}}</h2><small>Available campus spaces</small></div>
<div class="card"><h3>Bookings</h3><h2>{{bookings|length}}</h2><small>Recorded reservations</small></div>
<div class="card"><h3>Maintenance tickets</h3><h2>{{tickets|length}}</h2><small>Tracked service requests</small></div>
<div class="card"><h3>Audit events</h3><h2>{{audits|length}}</h2><small>Recorded actions</small></div></div>
<div class="grid">
<div class="card"><h3>Request a facility booking</h3><form method="post" action="/book">
<label>Facility</label><select name="facility_id">{% for f in facilities %}<option value="{{f.id}}">{{f.name}} {% if f.restricted %}(approval required){% endif %}</option>{% endfor %}</select>
<label>Start time</label><input type="datetime-local" name="start_time" required>
<label>End time</label><input type="datetime-local" name="end_time" required><button>Submit booking</button></form></div>
<div class="card"><h3>Create maintenance ticket</h3><form method="post" action="/ticket">
<label>Issue title</label><input name="title" required><label>Description</label><textarea name="description" required></textarea>
<label>Category</label><select name="category"><option>Electrical</option><option>Plumbing</option><option>Equipment</option><option>Cleaning</option><option>Other</option></select>
<label>Priority</label><select name="priority"><option>Low</option><option>Medium</option><option>High</option><option>Critical</option></select>
<button>Create ticket</button></form></div></div>
<div class="card"><h3>Facility booking records</h3><table><tr><th>ID</th><th>Facility</th><th>Requested by</th><th>Time</th><th>Status</th><th>Action</th></tr>
{% for b in bookings %}<tr><td>{{b.id}}</td><td>{{b.facility}}</td><td>{{b.username}}</td><td>{{b.start_time}} – {{b.end_time}}</td><td><span class="pill">{{b.status}}</span></td><td>
{% if role in ['Approver','Administrator','Facility Manager'] and b.status=='Pending Approval' %}
<form class="inline" method="post" action="/booking/{{b.id}}/decision"><input type="hidden" name="decision" value="Approved"><button>Approve</button></form>
<form class="inline" method="post" action="/booking/{{b.id}}/decision"><input type="hidden" name="decision" value="Rejected"><button style="background:#a33">Reject</button></form>
{% endif %}</td></tr>{% endfor %}</table></div>
<div class="card"><h3>Maintenance queue</h3><table><tr><th>ID</th><th>Issue</th><th>Category / priority</th><th>Assigned</th><th>Status</th><th>Update</th></tr>
{% for t in tickets %}<tr><td>{{t.id}}</td><td>{{t.title}}<br><small>{{t.description}}</small></td><td>{{t.category}} / {{t.priority}}</td><td>{{t.assigned_to or 'Unassigned'}}</td><td>{{t.status}} (v{{t.version}})</td><td>
{% if role in ['Facility Manager','Administrator'] %}<form method="post" action="/ticket/{{t.id}}/assign"><select name="assigned_to"><option>tech</option><option>manager</option></select><button>Assign</button></form>{% endif %}
{% if role in ['Technician','Facility Manager','Administrator'] %}<form method="post" action="/ticket/{{t.id}}/update"><input name="version" type="hidden" value="{{t.version}}"><select name="status"><option>Inspected</option><option>Pending Vendor</option><option>Resolved</option><option>Closed</option></select><input name="inspection" placeholder="Inspection notes"><input name="resolution" placeholder="Resolution notes"><button>Save update</button></form>{% endif %}
</td></tr>{% endfor %}</table></div>
<div class="card"><h3>Recent audit history</h3><table><tr><th>When</th><th>Actor</th><th>Action</th><th>Item</th><th>Details</th></tr>{% for a in audits %}<tr><td>{{a.created_at}}</td><td>{{a.actor}}</td><td>{{a.action}}</td><td>{{a.item_type}} #{{a.item_id}}</td><td>{{a.detail}}</td></tr>{% endfor %}</table></div>
{% endif %}</main></body></html>
"""

@app.route("/")
def home():
    if not current_user():
        return render_template_string(PAGE,user=None,role="")
    c=connect()
    facilities=c.execute("SELECT * FROM facilities ORDER BY id").fetchall()
    bookings=c.execute("""SELECT b.*,f.name facility FROM bookings b JOIN facilities f ON f.id=b.facility_id ORDER BY b.id DESC""").fetchall()
    tickets=c.execute("SELECT * FROM tickets ORDER BY id DESC").fetchall()
    audits=c.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 30").fetchall()
    c.close()
    return render_template_string(PAGE,user=current_user(),role=role(),facilities=facilities,bookings=bookings,tickets=tickets,audits=audits)

@app.post("/login")
def login():
    c=connect(); u=c.execute("SELECT * FROM users WHERE username=? AND password=?",(request.form["username"],request.form["password"])).fetchone(); c.close()
    if not u: flash("Invalid username or password"); return redirect("/")
    session["username"]=u["username"]; session["role"]=u["role"]; audit(u["username"],"LOGIN","user",0,"Successful login")
    return redirect("/")

@app.route("/logout")
def logout():
    session.clear(); return redirect("/")

@app.post("/book")
def book():
    if not current_user(): return redirect("/")
    try:
        start=request.form["start_time"]; end=request.form["end_time"]
        if datetime.fromisoformat(end)<=datetime.fromisoformat(start): raise ValueError()
        c=connect()
        # BEGIN IMMEDIATE serializes competing writers; overlap is checked inside the transaction.
        c.execute("BEGIN IMMEDIATE")
        f=c.execute("SELECT * FROM facilities WHERE id=?",(request.form["facility_id"],)).fetchone()
        clash=c.execute("""SELECT id FROM bookings WHERE facility_id=? AND status NOT IN ('Rejected','Cancelled','Completed')
          AND start_time < ? AND end_time > ?""",(f["id"],end,start)).fetchone()
        if clash:
            c.rollback(); c.close(); flash("Booking rejected: this facility is already reserved for an overlapping time."); return redirect("/")
        status="Pending Approval" if f["restricted"] else "Confirmed"
        cur=c.execute("INSERT INTO bookings(facility_id,username,start_time,end_time,status,created_at) VALUES(?,?,?,?,?,?)",
          (f["id"],current_user(),start,end,status,datetime.now().isoformat(timespec="seconds")))
        bid=cur.lastrowid; c.commit(); c.close()
        audit(current_user(),"BOOKING_CREATED","booking",bid,status); flash("Booking submitted: "+status)
    except Exception:
        flash("Booking could not be saved. Check the selected facility and time.")
    return redirect("/")

@app.post("/booking/<int:bid>/decision")
def decision(bid):
    if role() not in ["Approver","Administrator","Facility Manager"]: flash("Not authorised to approve bookings"); return redirect("/")
    d=request.form["decision"]
    c=connect(); c.execute("BEGIN IMMEDIATE")
    row=c.execute("SELECT * FROM bookings WHERE id=?",(bid,)).fetchone()
    if not row or row["status"]!="Pending Approval":
        c.rollback(); c.close(); flash("Invalid booking state transition"); return redirect("/")
    if d=="Approved":
        conflict=c.execute("""SELECT id FROM bookings WHERE facility_id=? AND id<>? AND status IN ('Confirmed','Approved','In Use')
        AND start_time < ? AND end_time > ?""",(row["facility_id"],bid,row["end_time"],row["start_time"])).fetchone()
        if conflict: c.rollback(); c.close(); flash("Approval rejected: time slot now conflicts"); return redirect("/")
    new="Approved" if d=="Approved" else "Rejected"
    c.execute("UPDATE bookings SET status=? WHERE id=?",(new,bid))
    c.execute("INSERT INTO approvals(booking_id,approver,decision,note,created_at) VALUES(?,?,?,?,?)",(bid,current_user(),new,"Decision recorded",datetime.now().isoformat(timespec="seconds")))
    c.commit(); c.close(); audit(current_user(),"BOOKING_"+new.upper(),"booking",bid,"Approval decision"); flash("Booking "+new.lower())
    return redirect("/")

@app.post("/ticket")
def ticket():
    if not current_user(): return redirect("/")
    title=request.form["title"].strip(); desc=request.form["description"].strip()
    category=request.form["category"]; priority=request.form["priority"]
    # Explainable suggestion: keyword-based category/priority hint; user selection is retained.
    suggestion="Electrical" if any(x in (title+" "+desc).lower() for x in ["wire","power","light","electric"]) else ("Plumbing" if any(x in (title+" "+desc).lower() for x in ["water","pipe","tap","leak"]) else "General")
    key=request.form.get("idempotency_key") or str(uuid.uuid4())
    c=connect()
    c.execute("INSERT OR IGNORE INTO tickets(title,description,category,priority,status,idempotency_key,created_at) VALUES(?,?,?,?,?,?,?)",
      (title,desc,category,priority,"New",key,datetime.now().isoformat(timespec="seconds")))
    row=c.execute("SELECT id FROM tickets WHERE idempotency_key=?",(key,)).fetchone(); c.close()
    audit(current_user(),"TICKET_CREATED","ticket",row["id"],"Category suggestion: "+suggestion+"; chosen: "+category)
    flash("Maintenance ticket recorded. Explainable category hint: "+suggestion)
    return redirect("/")

@app.post("/ticket/<int:tid>/assign")
def assign(tid):
    if role() not in ["Facility Manager","Administrator"]: flash("Not authorised to assign tickets"); return redirect("/")
    c=connect(); c.execute("UPDATE tickets SET assigned_to=?,status='Assigned',version=version+1 WHERE id=?",(request.form["assigned_to"],tid)); c.close()
    audit(current_user(),"TICKET_ASSIGNED","ticket",tid,"Assigned to "+request.form["assigned_to"]); flash("Ticket assigned"); return redirect("/")

@app.post("/ticket/<int:tid>/update")
def update_ticket(tid):
    if role() not in ["Technician","Facility Manager","Administrator"]: flash("Not authorised to update tickets"); return redirect("/")
    c=connect(); c.execute("BEGIN IMMEDIATE")
    row=c.execute("SELECT * FROM tickets WHERE id=?",(tid,)).fetchone()
    expected=int(request.form["version"])
    if not row or row["version"]!=expected:
        c.rollback(); c.close(); flash("Update rejected: ticket changed by another user. Refresh and try again."); return redirect("/")
    new=request.form["status"]
    allowed={"New":["Inspected"],"Assigned":["Inspected"],"Inspected":["Pending Vendor","Resolved"],"Pending Vendor":["Inspected","Resolved"],"Resolved":["Closed"],"Closed":[]}
    if new not in allowed.get(row["status"],[]):
        c.rollback(); c.close(); flash("Illegal ticket state transition rejected"); return redirect("/")
    c.execute("UPDATE tickets SET status=?,inspection=?,resolution=?,version=version+1 WHERE id=? AND version=?",
      (new,request.form.get("inspection",""),request.form.get("resolution",""),tid,expected))
    if c.total_changes==0: c.rollback(); c.close(); flash("Concurrent update rejected"); return redirect("/")
    c.commit(); c.close(); audit(current_user(),"TICKET_"+new.upper(),"ticket",tid,"Version "+str(expected+1)); flash("Ticket updated to "+new); return redirect("/")

@app.get("/health")
def health(): return jsonify(status="ok",service="smart-campus")

@app.get("/api/facilities")
def api_facilities():
    c=connect(); rows=[dict(x) for x in c.execute("SELECT * FROM facilities")]; c.close(); return jsonify(rows)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0",port=5000,debug=False)
