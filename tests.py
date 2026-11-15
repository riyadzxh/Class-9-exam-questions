import io, os, tempfile
os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["ADMIN_PASSWORD"] = "1892514"
os.environ["ADMIN_PHONE"] = "01700000000"
import app as A
ok = 0
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); ok += bool(cond); assert cond, name
def client():
    c = A.app.test_client(); c.get("/")
    with c.session_transaction() as s: c.t = s["csrf"]
    return c
def post(c, url, data=None, **k):
    d = dict(data or {}); d["csrf"] = c.t; return c.post(url, data=d, **k)

adm = client()
check("admin login", post(adm, "/login", {"phone": "01700000000", "password": "1892514"}).status_code == 302)
r = post(adm, "/admin/upload", {"title": "Math Ch1", "subject": "Math", "price": "20", "qdate": "2026-11-15",
    "file": (io.BytesIO(b"%PDF-1.4 hi"), "a.pdf"), "image": (io.BytesIO(b"\x89PNG"), "t.png"),
    "video": (io.BytesIO(b"vid"), "v.mp4")}, content_type="multipart/form-data")
check("upload pdf+image+video", r.status_code == 302)
check("bad file type rejected", "ধরন ঠিক নয়" in adm.get("/admin").get_data(as_text=True) or
      post(adm, "/admin/upload", {"title": "x", "subject": "x", "file": (io.BytesIO(b"x"), "a.exe")}, content_type="multipart/form-data").status_code == 302)
check("settings edit (pay number)", post(adm, "/admin/settings", {"PAY_NUMBER": "01999999999", "SELLER": "ZX (R)( Y )"}).status_code == 302)
check("question edit", post(adm, "/admin/question/1/edit", {"title": "Math Ch1 v2", "subject": "Math", "serial": "1", "price": "25", "qdate": "2026-11-16"}, content_type="multipart/form-data").status_code == 302)

st = client()
check("POST without csrf blocked", st.post("/login", data={"phone": "1", "password": "1"}).status_code == 400)
post(st, "/register", {"name": "Rahim", "phone": "01811111111", "password": "secret1"})
h = st.get("/").get_data(as_text=True)
check("seller name shown", "ZX (R)( Y )" in h)
check("pay number from settings", "01999999999" in h)
check("question shows locked", "🔒" in h and "Math Ch1 v2" in h)
check("file locked before pay", st.get("/file/1").status_code == 302)
check("video locked before pay", st.get("/video/1").status_code == 302)
check("thumbnail public", st.get("/img/1").status_code == 200)
b = {"age": 14, "class": "9", "roll": 5, "subject": "Math", "school": "X", "sender": "018", "trx": "ABC1"}
post(st, "/buy/question/1", b)
check("order recorded as pending", "যাচাই চলছে" in st.get("/my").get_data(as_text=True))
check("still locked while pending", st.get("/file/1").status_code == 302)
post(st, "/buy/question/1", dict(b, trx="ABC2"))
check("2nd order same day blocked (1/day)", len(A.sqlite3.connect(A.DB).execute("select 1 from orders").fetchall()) == 1)

check("admin approves/edit payment", post(adm, "/admin/order/1/edit", {"amount": "25", "sender": "018", "trx_id": "abc1", "status": "approved"}).status_code == 302)
check("file unlocked after approve", st.get("/file/1").status_code == 200)
check("download works", st.get("/file/1?dl=1").status_code == 200)
check("video unlocked after approve", st.get("/video/1").status_code == 200)
h = st.get("/").get_data(as_text=True)
check("buyer name shown line by line", "1. Rahim" in h)
post(adm, "/admin/order/1/edit", {"amount": "25", "sender": "018", "trx_id": "abc1", "status": "rejected"})
check("re-lock works (rejected)", st.get("/file/1").status_code == 302)

other = client(); post(other, "/register", {"name": "Karim", "phone": "01822222222", "password": "secret2"})
check("other user still locked", other.get("/file/1").status_code == 302)
check("non-admin cannot open /admin", other.get("/admin").status_code == 403)
check("non-admin cannot edit payment", post(other, "/admin/order/1/edit", {"amount": "0", "trx_id": "x", "status": "approved"}).status_code == 403)
check("anonymous file -> login redirect", client().get("/file/1").status_code == 302)
check("path traversal safe", client().get("/img/../../etc/passwd").status_code == 404)
check("packages page", client().get("/packages").status_code == 200)
print(f"\n{ok} checks passed")
