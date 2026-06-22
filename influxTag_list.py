from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import pyodbc
import subprocess
import sys

import requests

from config.config import *

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def get_conn():
    return pyodbc.connect(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={SQL_SERVER};DATABASE={SQL_DB};UID={SQL_USER};PWD={SQL_PASS};"
    )


def build_tree(rows, used_tagids=None):
    used_tagids = used_tagids or set()
    tree = {}

    for tagid, path, dtype in rows:
        parts = path.split("/")
        node = tree

        for p in parts[:-1]:
            node = node.setdefault(p, {})

        node[parts[-1]] = {
            "tagid": tagid,
            "datatype": dtype,
            "fullpath": path,
            "used": tagid in used_tagids,
            "_leaf": True
        }

    return tree


def influx_measurements(db):
    """Return the list of measurement (old-tag) names in an InfluxDB 1.x database."""
    auth = (INFLUX_USER, INFLUX_PASS) if INFLUX_USER else None

    resp = requests.get(
        f"http://{INFLUX_HOST}:{INFLUX_PORT}/query",
        params={"db": db, "q": "SHOW MEASUREMENTS"},
        auth=auth,
        timeout=10,
    )
    resp.raise_for_status()

    data = resp.json()
    names = []

    for result in data.get("results", []):
        for series in result.get("series", []):
            for value in series.get("values", []):
                if value:
                    names.append(value[0])

    return sorted(names)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    conn = get_conn()
    cur = conn.cursor()

    # new tags already mapped (shown greyed-out in the tree, not selectable)
    cur.execute("SELECT TagId FROM InfluxTag_Lists")
    used_tagids = {r.TagId for r in cur.fetchall()}

    cur.execute("""
        SELECT TagId, Path, DataType
        FROM TagMaster
        WHERE IsActive = 1
        ORDER BY Path
    """)
    tags = cur.fetchall()

    tree = build_tree(tags, used_tagids)

    cur.execute("""
        SELECT InfluxId, TagId, TagPath, Influx_db, Influx_oldTag
        FROM InfluxTag_Lists
        ORDER BY TagPath
    """)
    mappings = cur.fetchall()

    conn.close()

    return templates.TemplateResponse(request, "influxTag_list.html", {
        "request": request,
        "tree": tree,
        "mappings": mappings,
        "influx_dbs": INFLUX_DBS,
    })


@app.get("/measurements")
def measurements(db: str):
    # old-tag suggestions for the datalist; db must be one of the configured ones
    if db not in INFLUX_DBS:
        return JSONResponse({"error": "unknown db"}, status_code=400)

    try:
        return JSONResponse({"measurements": influx_measurements(db)})
    except Exception as ex:
        return JSONResponse({"error": str(ex), "measurements": []}, status_code=200)


@app.post("/save")
def save_mapping(
    influxid: str = Form(""),
    tagid: int = Form(...),
    tagpath: str = Form(...),
    influx_db: str = Form(...),
    influx_oldtag: str = Form(...),
):
    conn = get_conn()
    cur = conn.cursor()

    # prevent mapping the same new tag twice (on insert only)
    if not influxid:
        cur.execute("SELECT COUNT(*) FROM InfluxTag_Lists WHERE TagId = ?", (tagid,))
        if cur.fetchone()[0] > 0:
            conn.close()
            return RedirectResponse("/", status_code=303)

    if influxid:
        cur.execute("""
            UPDATE InfluxTag_Lists
            SET TagId = ?,
                TagPath = ?,
                Influx_db = ?,
                Influx_oldTag = ?,
                UpdatedTime = GETDATE()
            WHERE InfluxId = ?
        """, (
            tagid,
            tagpath,
            influx_db,
            influx_oldtag,
            int(influxid),
        ))
    else:
        cur.execute("""
            INSERT INTO InfluxTag_Lists (
                TagId,
                TagPath,
                Influx_db,
                Influx_oldTag,
                CreatedTime,
                UpdatedTime
            )
            VALUES (?, ?, ?, ?, GETDATE(), GETDATE())
        """, (
            tagid,
            tagpath,
            influx_db,
            influx_oldtag,
        ))

    conn.commit()
    conn.close()

    return RedirectResponse("/", status_code=303)


@app.post("/delete/{influx_id}")
def delete_mapping(influx_id: int):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("DELETE FROM InfluxTag_Lists WHERE InfluxId = ?", (influx_id,))

    conn.commit()
    conn.close()

    return RedirectResponse("/", status_code=303)


@app.post("/refresh")
def refresh_browser():
    # rebuild the OPC tag tree (e.g. after adding a machine). Optional: only runs
    # when BROWSER_SCRIPT is configured. Does NOT touch InfluxTag_Lists.
    if BROWSER_SCRIPT:
        subprocess.run([sys.executable, BROWSER_SCRIPT])

    return RedirectResponse("/", status_code=303)
