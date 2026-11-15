import os, re, secrets, sqlite3, datetime
from functools import wraps
from flask import (Flask, g, render_template, request, redirect, url_for,
                   session, flash, send_from_directory, abort)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import config

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("DATA_DIR", BASE)   # deploy e persistent folder dite parba
DB = os.path.join(DATA, "data.db")
UP = os.path.join(DATA, "uploads")
os.makedirs(UP, exist_ok=True)

app = Flask(__name__)
def _secret():
    if os.environ.get("SECRET_KEY"): return os.environ["SECRET_KEY"]
    p = os.path.join(DATA, "secret.key")
    if not os.path.exists(p):
        open(p, "w").write(secrets.token_hex(32))
    return open(p).read().strip()
app.secret_key = _secret()
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=os.environ.get("HTTPS") == "1",
                  PERMANENT_SESSION_LIFETIME=datetime.timedelta(days=7))

SCHEMA = """
create table if not exists users(
 id integer primary key autoincrement, name text, phone text unique, pw text,
 age integer, class text, roll text, school text, is_admin integer default 0);
create table if not exists packages(
 id integer primary key autoincrement, name text, price integer,
 description text, schools text);
create table if not exists questions(
 id integer primary key autoincrement, serial integer, title text, subject text,
 class text default '9', price integer default 0, package_id integer,
 filename text, created text);
create table if not exists settings(k text primary key, v text);
create table if not exists orders(
 id integer primary key autoincrement, user_id integer, kind text, target_id integer,
 amount integer, trx_id text unique, sender text, age integer, class text,
 roll text, subject text, school text, status text default 'pending',
 day text, created text);
"""

@app.before_request
def csrf_protect():
    if request.endpoint == "static": return
    if "csrf" not in session: session["csrf"] = secrets.token_hex(16)
    if request.method == "POST":
        if not secrets.compare_digest(request.form.get("csrf", ""), session["csrf"]): abort(400)

@app.after_request
def add_csrf(resp):
    if resp.mimetype == "text/html" and not resp.direct_passthrough and "csrf" in session:
        html = resp.get_data(as_text=True)
        html = re.sub(r'(<form[^>]*method="post"[^>]*>)',
                      lambda m: m.group(1) + '<input type="hidden" name="csrf" value="%s">' % session["csrf"], html)
        resp.set_data(html)
    return resp

def now():  # Bangladesh time
    return datetime.datetime.utcnow() + datetime.timedelta(hours=6)

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close(e=None):
    d = g.pop("db", None)
    if d: d.close()

def q(sql, args=(), one=False):
    cur = db().execute(sql, args)
    rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows

def ex(sql, args=()):
    cur = db().execute(sql, args); db().commit(); return cur.lastrowid

def init_db():
    c = sqlite3.connect(DB); c.executescript(SCHEMA)
    if not c.execute("select 1 from users where is_admin=1").fetchone():
        c.execute("insert into users(name,phone,pw,is_admin) values(?,?,?,1)",
                  ("Admin", config.ADMIN_PHONE, generate_password_hash(config.ADMIN_PASSWORD)))
    c.commit(); c.close()
    c=sqlite3.connect(DB)
    for col in ("image text","video text","is_free integer default 0","qdate text"):
        try: c.execute("alter table questions add column "+col)
        except sqlite3.OperationalError: pass
    c.commit(); c.close()
init_db()

def cur_user():
    if "uid" in session:
        return q("select * from users where id=?", (session["uid"],), one=True)

DEFAULTS = {"SITE_NAME": config.SITE_NAME, "PAY_NUMBER": config.PAY_NUMBER,
            "PAY_METHOD": config.PAY_METHOD, "SELLER": "ZX (R)( Y )"}

def get_settings():
    d = dict(DEFAULTS)
    for r in q("select k,v from settings"): d[r["k"]] = r["v"]
    return d

@app.context_processor
def inject():
    return dict(me=cur_user(), cfg=get_settings())

def buyers(qu):
    return [r["name"] for r in q("""select u.name from orders o join users u on u.id=o.user_id
        where o.status='approved' and ((o.kind='question' and o.target_id=?) or
        (o.kind='package' and o.target_id=? and ? is not null)) group by u.id order by min(o.id)""",
        (qu["id"], qu["package_id"], qu["package_id"]))]

def save_upload(f, exts):
    if not f or not f.filename: return None
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in exts: return "BAD"
    name = now().strftime("%Y%m%d%H%M%S%f") + "_" + secure_filename(f.filename)
    f.save(os.path.join(UP, name)); return name

def rm(name):
    if name:
        try: os.remove(os.path.join(UP, name))
        except OSError: pass

DOC = (".pdf", ".jpg", ".jpeg", ".png", ".docx")
IMG = (".jpg", ".jpeg", ".png", ".webp")
VID = (".mp4", ".webm", ".mov")

def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not cur_user():
            flash("আগে লগইন করো।"); return redirect(url_for("login", next=request.path))
        return f(*a, **k)
    return w

def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        u = cur_user()
        if not u or not u["is_admin"]: abort(403)
        return f(*a, **k)
    return w

def has_access(u, qu):
    if qu["is_free"]: return True
    if not u: return False
    if u["is_admin"]: return True
    r = q("""select 1 from orders where user_id=? and status='approved' and
            ((kind='question' and target_id=?) or (kind='package' and target_id=? and ? is not null))
            limit 1""", (u["id"], qu["id"], qu["package_id"], qu["package_id"]), one=True)
    return bool(r)

# ---------- public ----------
@app.route("/healthz")
def healthz():
    return {"status": "ok"}, 200

@app.route("/")
def index():
    u = cur_user()
    subj = request.args.get("subject", "")
    rows = q("select * from questions where (?='' or subject=?) order by serial desc, id desc", (subj, subj))
    items = [dict(r, open=has_access(u, r), buyers=buyers(r)) for r in rows]
    subjects = [r["subject"] for r in q("select distinct subject from questions order by subject")]
    return render_template("index.html", items=items, subjects=subjects, subj=subj)

@app.route("/packages")
def packages():
    pk = q("select * from packages order by price")
    cnt = {p["id"]: q("select count(*) c from questions where package_id=?", (p["id"],), one=True)["c"] for p in pk}
    return render_template("packages.html", pk=pk, cnt=cnt)

# ---------- auth ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form
        name, phone, pw = f["name"].strip(), f["phone"].strip(), f["password"]
        if not (name and phone.isdigit() and len(phone) >= 10 and len(pw) >= 6):
            flash("নাম, সঠিক ফোন নম্বর ও ৬+ অক্ষরের পাসওয়ার্ড দাও।"); return render_template("register.html")
        if q("select 1 from users where phone=?", (phone,), one=True):
            flash("এই নম্বর দিয়ে আগেই অ্যাকাউন্ট আছে।"); return render_template("register.html")
        uid = ex("insert into users(name,phone,pw,age,class,roll,school) values(?,?,?,?,?,?,?)",
                 (name, phone, generate_password_hash(pw), f.get("age") or None,
                  f.get("class", "9"), f.get("roll"), f.get("school")))
        session["uid"] = uid; return redirect(url_for("index"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = q("select * from users where phone=?", (request.form["phone"].strip(),), one=True)
        if u and check_password_hash(u["pw"], request.form["password"]):
            session["uid"] = u["id"]
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("index"))
        flash("ফোন বা পাসওয়ার্ড ভুল।")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("index"))

# ---------- buy ----------
@app.route("/buy/<kind>/<int:tid>", methods=["GET", "POST"])
@login_required
def buy(kind, tid):
    u = cur_user()
    if kind == "question":
        item = q("select * from questions where id=?", (tid,), one=True)
        if item and has_access(u, item): flash("এটা তোমার আগেই কেনা।"); return redirect(url_for("index"))
    elif kind == "package":
        item = q("select * from packages where id=?", (tid,), one=True)
    else: abort(404)
    if not item: abort(404)
    price = item["price"]
    title = item["title"] if kind == "question" else item["name"]
    subjects = [r["subject"] for r in q("select distinct subject from questions")]
    if request.method == "POST":
        f = request.form
        today = now().date().isoformat()
        if q("select 1 from orders where user_id=? and day=? and status!='rejected'", (u["id"], today), one=True):
            flash("একটা অ্যাকাউন্ট থেকে দিনে মাত্র একবার কেনা যায়। কাল আবার চেষ্টা করো।")
            return redirect(url_for("my_orders"))
        need = [f.get(k, "").strip() for k in ("age", "class", "roll", "subject", "school", "sender", "trx")]
        if not all(need):
            flash("সব ঘর পূরণ করো।"); return render_template("buy.html", item=item, kind=kind, title=title, price=price, subjects=subjects)
        if q("select 1 from orders where trx_id=?", (f["trx"].strip().upper(),), one=True):
            flash("এই TrxID আগেই ব্যবহার হয়েছে।"); return render_template("buy.html", item=item, kind=kind, title=title, price=price, subjects=subjects)
        ex("""insert into orders(user_id,kind,target_id,amount,trx_id,sender,age,class,roll,subject,school,day,created)
              values(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
           (u["id"], kind, tid, price, f["trx"].strip().upper(), f["sender"].strip(), f["age"], f["class"],
            f["roll"], f["subject"], f["school"], today, now().strftime("%Y-%m-%d %H:%M")))
        flash("অর্ডার জমা হয়েছে। পেমেন্ট যাচাই হলে ডাউনলোড খুলে যাবে।")
        return redirect(url_for("my_orders"))
    return render_template("buy.html", item=item, kind=kind, title=title, price=price, subjects=subjects, u=u)

@app.route("/my")
@login_required
def my_orders():
    rows = q("select * from orders where user_id=? order by id desc", (session["uid"],))
    return render_template("my.html", rows=rows)

# ---------- protected download ----------
def guard(qid):
    qu = q("select * from questions where id=?", (qid,), one=True)
    if not qu: abort(404)
    if not has_access(cur_user(), qu): return None
    return qu

@app.route("/img/<int:qid>")
def img(qid):  # thumbnail: sobar jonno dekha jay
    qu = q("select * from questions where id=?", (qid,), one=True)
    if not qu or not qu["image"]: abort(404)
    return send_from_directory(UP, qu["image"])

@app.route("/file/<int:qid>")
@login_required
def file(qid):
    qu = guard(qid)
    if not qu or not qu["filename"]:
        flash("এটা লক করা। আগে কিনে নাও।"); return redirect(url_for("index"))
    return send_from_directory(UP, qu["filename"], as_attachment=request.args.get("dl") == "1")

@app.route("/video/<int:qid>")
@login_required
def video(qid):
    qu = guard(qid)
    if not qu or not qu["video"]:
        flash("এটা লক করা।"); return redirect(url_for("index"))
    return send_from_directory(UP, qu["video"])

# ---------- admin ----------
@app.route("/admin")
@admin_required
def admin():
    pend = q("""select o.*, u.name uname, u.phone uphone from orders o join users u on u.id=o.user_id
                where status='pending' order by o.id""")
    done = q("""select o.*, u.name uname, u.phone uphone from orders o join users u on u.id=o.user_id
                where status!='pending' order by o.id desc limit 60""")
    qs = [dict(r, buyers=buyers(r)) for r in q("select * from questions order by serial desc, id desc")]
    pk = q("select * from packages")
    return render_template("admin.html", pend=pend, done=done, qs=qs, pk=pk)

@app.route("/admin/order/<int:oid>/<act>", methods=["POST"])
@admin_required
def order_act(oid, act):
    if act in ("approve", "reject", "pending"):
        ex("update orders set status=? where id=?", ({"approve": "approved", "reject": "rejected", "pending": "pending"}[act], oid))
    return redirect(url_for("admin"))

@app.route("/admin/order/<int:oid>/edit", methods=["POST"])
@admin_required
def order_edit(oid):
    f = request.form
    st = f.get("status", "pending")
    if st not in ("pending", "approved", "rejected"): st = "pending"
    ex("update orders set amount=?, trx_id=?, sender=?, status=? where id=?",
       (int(f.get("amount") or 0), f["trx_id"].strip().upper(), f.get("sender", ""), st, oid))
    flash("পেমেন্ট এডিট হয়েছে।"); return redirect(url_for("admin"))

@app.route("/admin/settings", methods=["POST"])
@admin_required
def settings():
    for k in DEFAULTS:
        if k in request.form:
            ex("insert or replace into settings(k,v) values(?,?)", (k, request.form[k].strip()))
    flash("সেটিংস সেভ হয়েছে।"); return redirect(url_for("admin"))

@app.route("/admin/upload", methods=["POST"])
@admin_required
def upload():
    f = request.form
    fn = save_upload(request.files.get("file"), DOC)
    im = save_upload(request.files.get("image"), IMG)
    vd = save_upload(request.files.get("video"), VID)
    if "BAD" in (fn, im, vd): flash("ফাইলের ধরন ঠিক নয়।"); return redirect(url_for("admin"))
    if not (fn or vd): flash("প্রশ্নের ফাইল বা ভিডিও দাও।"); return redirect(url_for("admin"))
    last = q("select max(serial) m from questions", one=True)["m"] or 0
    ex("""insert into questions(serial,title,subject,price,package_id,filename,image,video,is_free,qdate,created)
          values(?,?,?,?,?,?,?,?,?,?,?)""",
       (int(f.get("serial") or last + 1), f["title"], f["subject"], int(f.get("price") or 0),
        f.get("package_id") or None, fn, im, vd, 1 if f.get("is_free") else 0,
        f.get("qdate") or now().strftime("%Y-%m-%d"), now().strftime("%Y-%m-%d")))
    flash("আপলোড হয়েছে।"); return redirect(url_for("admin"))

@app.route("/admin/question/<int:qid>/edit", methods=["GET", "POST"])
@admin_required
def edit_q(qid):
    r = q("select * from questions where id=?", (qid,), one=True)
    if not r: abort(404)
    pk = q("select * from packages")
    if request.method == "POST":
        f = request.form
        fn = save_upload(request.files.get("file"), DOC)
        im = save_upload(request.files.get("image"), IMG)
        vd = save_upload(request.files.get("video"), VID)
        if "BAD" in (fn, im, vd): flash("ফাইলের ধরন ঠিক নয়।"); return redirect(request.url)
        filename, image, video = r["filename"], r["image"], r["video"]
        if fn: rm(filename); filename = fn
        if im: rm(image); image = im
        if vd: rm(video); video = vd
        if f.get("remove_image"): rm(image); image = None
        if f.get("remove_video"): rm(video); video = None
        ex("""update questions set title=?,subject=?,serial=?,price=?,package_id=?,qdate=?,is_free=?,
              filename=?,image=?,video=? where id=?""",
           (f["title"], f["subject"], int(f.get("serial") or 0), int(f.get("price") or 0),
            f.get("package_id") or None, f.get("qdate"), 1 if f.get("is_free") else 0,
            filename, image, video, qid))
        flash("এডিট সেভ হয়েছে।"); return redirect(url_for("admin"))
    return render_template("edit_q.html", r=r, pk=pk)

@app.route("/admin/question/<int:qid>/delete", methods=["POST"])
@admin_required
def del_q(qid):
    r = q("select * from questions where id=?", (qid,), one=True)
    if r:
        for n in (r["filename"], r["image"], r["video"]): rm(n)
        ex("delete from questions where id=?", (qid,))
    return redirect(url_for("admin"))

@app.route("/admin/package", methods=["POST"])
@admin_required
def add_pkg():
    f = request.form
    ex("insert into packages(name,price,description,schools) values(?,?,?,?)",
       (f["name"], int(f["price"]), f["description"], f["schools"]))
    return redirect(url_for("admin"))

@app.route("/admin/package/<int:pid>/delete", methods=["POST"])
@admin_required
def del_pkg(pid):
    ex("delete from packages where id=?", (pid,)); ex("update questions set package_id=null where package_id=?", (pid,))
    return redirect(url_for("admin"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
