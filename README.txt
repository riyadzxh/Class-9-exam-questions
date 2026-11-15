CLASS 9 QUESTION BANK — DEPLOYMENT GUIDE

LOCAL TEST
1) Python 3.10+ install করো।
2) Terminal/CMD-তে এই ফোল্ডারে ঢুকে চালাও: pip install -r requirements.txt
3) প্রথমবার চালানোর আগে Environment Variables সেট করো:
   ADMIN_PHONE=তোমার_অ্যাডমিন_ফোন
   ADMIN_PASSWORD=1892514
   SECRET_KEY=লম্বা_র‍্যান্ডম_সিক্রেট
   PAY_NUMBER=তোমার_bKash_বা_Nagad_নম্বর
4) চালাও: python app.py
5) খুলবে: http://127.0.0.1:5000
6) টেস্ট: python tests.py

GITHUB
- GitHub-এ class9site ফোল্ডারের ভেতরের ফাইলগুলো repository root-এ আপলোড করো।
- .env, data.db, secret.key, uploads-এর ব্যক্তিগত ফাইল এবং কোনো পাসওয়ার্ড GitHub-এ দেবে না।
- Public repository-তে কখনো আসল পাসওয়ার্ড বা পেমেন্ট তথ্য রাখবে না।

RENDER FREE WEB SERVICE
1) https://render.com এ GitHub দিয়ে লগইন করো।
2) New > Web Service > তোমার repository নির্বাচন করো।
3) Root Directory: ফাঁকা রাখো (যদি class9site ফোল্ডারের ভেতরের ফাইলগুলো repo root-এ আপলোড করো)।
4) Runtime: Python 3
5) Build Command: pip install -r requirements.txt
6) Start Command: gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120
7) Environment Variables-এ যোগ করো:
   ADMIN_PHONE = তোমার অ্যাডমিন ফোন নম্বর
   ADMIN_PASSWORD = 1892514
   SECRET_KEY = নিজে তৈরি করা দীর্ঘ random secret
   PAY_NUMBER = তোমার bKash/Nagad নম্বর
   HTTPS = 1
   DATA_DIR = /var/data  (শুধু persistent disk যুক্ত থাকলে)
8) Deploy চাপো। /healthz খুলে {"status":"ok"} দেখলে সার্ভার চলছে।

গুরুত্বপূর্ণ সীমাবদ্ধতা
- Render Free Web Service-এ ফ্রি persistent disk নাও থাকতে পারে। ডিস্ক ছাড়া redeploy/restart হলে SQLite database ও uploads হারিয়ে যেতে পারে।
- শিক্ষার্থীর রেজিস্ট্রেশন, অর্ডার, পেমেন্ট রেকর্ড ও প্রশ্নের ফাইল বাস্তবে ব্যবহারের আগে persistent database/storage যুক্ত করো এবং নিয়মিত backup রাখো।
- 1892514 ছোট/অনুমানযোগ্য পাসওয়ার্ড। তুমি এটি চেয়েছ বলে সেট করার নির্দেশনা দেওয়া হয়েছে, কিন্তু নিরাপত্তার জন্য লাইভ করার আগে দীর্ঘ ও শক্তিশালী পাসওয়ার্ড ব্যবহার করাই ভালো।
- প্রথমবার admin তৈরি হওয়ার সময়ই ADMIN_PASSWORD কার্যকর হয়। ডাটাবেসে admin আগে তৈরি হয়ে গেলে শুধু Environment Variable পাল্টালে পুরোনো পাসওয়ার্ড বদলাবে না।
