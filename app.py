from flask import Flask, render_template, request

import engine

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html", result=None)


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
        except ValueError as e:
            error = "Invalid URL." if str(e) == "invalid url" else (
                "Empty URL." if str(e) == "empty url" else "Could not reach that domain (private or blocked host)."
            )
        except Exception:
            error = "Could not reach that domain."
    return render_template("index.html", result=result, error=error, url=url)


if __name__ == "__main__":
    app.run(debug=True, port=8000)
