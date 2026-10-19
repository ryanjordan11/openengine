import sqlite3, json, os
from flask import Flask, render_template, request

import engine

app = Flask(__name__)
DB = os.path.join(os.path.dirname(__file__), "history.db")

def init_db():
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS scans (id INTEGER PRIMARY KEY, url TEXT, score INTEGER, grade TEXT, scanned_at TEXT, data TEXT)")
    con.commit(); con.close()

def save_scan(result):
    con = sqlite3.connect(DB)
    con.execute("INSERT INTO scans (url, score, grade, scanned_at, data) VALUES (?,?,?,?,?)",
                (result["final_url"], result["score"], result["grade"], result["scanned_at"], json.dumps(result)))
    con.commit(); con.close()

def recent_scans(limit=6):
    con = sqlite3.connect(DB)
    rows = con.execute("SELECT url, score, grade, scanned_at FROM scans ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    con.close()
    return rows

init_db()


@app.get("/")
def index():
    return render_template("index.html", result=None, history=recent_scans())


@app.route("/scan", methods=["POST"])
def scan():
    url = (request.form.get("url") or "").strip()
    result = None
    error = None
    if not url:
        error = "Enter a URL to scan."
    else:
        try:
            result = engine.run_scan(url)
            save_scan(result)
        except ValueError as e:
            error = "Invalid URL." if str(e) == "invalid url" else (
                "Empty URL." if str(e) == "empty url" else "Could not reach that domain (private or blocked host)."
            )
        except Exception:
            error = "Could not reach that domain."
    return render_template("index.html", result=result, error=error, url=url, history=recent_scans())




@app.route("/compare", methods=["GET","POST"])
def compare():
    r1 = r2 = None
    u1 = u2 = ""
    if request.method == "POST":
        u1 = (request.form.get("url1") or "").strip()
        u2 = (request.form.get("url2") or "").strip()
        try:
            if u1: r1 = engine.run_scan(u1)
        except Exception as e:
            r1 = {"error": str(e)}
        try:
            if u2: r2 = engine.run_scan(u2)
        except Exception as e:
            r2 = {"error": str(e)}
    return render_template("compare.html", r1=r1, r2=r2, u1=u1, u2=u2)

@app.get("/tools")
def tools():
    return render_template("tools.html")

if __name__ == "__main__":
    app.run(debug=True, port=8000)
