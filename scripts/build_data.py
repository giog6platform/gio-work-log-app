"""Build public/data.json from the task inventory and the scrum board export.

Status reports in data/reports/*.json are merged too.
Usage: python3 scripts/build_data.py [task_context.json] [board_dir]
Writes data/out/data.json (gitignored). In production it is uploaded as a Render secret file.
Strips emails, phone numbers and source links so nothing identifying ships with the site.
"""
import glob, json, os, re, sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INV = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data/task_context.json")
BOARD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "data/board")
OUT = os.path.join(ROOT, "data/out/data.json")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
PHONE = re.compile(r"(?<![\w-])\+?1?[\s.(-]*\d{3}[\s.)-]*\d{3}[\s.-]*\d{4}(?!\d)")
TOKEN = re.compile(r"\b(sk|pk|pit|gho|ghp|AKIA)[-_A-Za-z0-9]{12,}\b")

def clean(s):
    if not s:
        return ""
    s = EMAIL.sub("[email]", str(s))
    s = PHONE.sub("[phone]", s)
    return TOKEN.sub("[secret]", s).strip()

def iso_ms(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z") if ms else None

KIND_RULES = [
    ("Fix", r"\b(fix|bug|broken|error|repair|wrong|incident|breach|drops?|junk|bad|failing|fail)"),
    ("Security", r"\b(security|pentest|clerk|password|credential|key rotation|mfa|2fa|access|cve)"),
    ("Migration", r"\b(migrat|import|backfill|transfer|move)"),
    ("Update", r"\b(update|revise|refresh|change|adjust|cleanup|clean up)"),
    ("Support", r"\b(help|support|question|request|onboard|training|login|account)"),
    ("Build", r"\b(build|create|set ?up|launch|new|dashboard|agent|workflow|sequence|automation|integration)"),
]

def kind_of(text):
    t = text.lower()
    for k, rx in KIND_RULES:
        if re.search(rx, t):
            return k
    return "Update"

STATUS = {
    "done": "Done", "in progress": "In Progress", "improved": "In Progress", "not started": "Planned",
    "planned": "Planned", "paused": "Paused", "deprecated": "Deprecated", "unconfirmed": "Unconfirmed",
    "not mine": "Not Mine",
}
LANE_STATUS = {"Blocked": "Waiting", "On hold": "Paused", "Parked": "Paused", "Active": "In Progress"}
BUCKET_STATUS = {
    "done": "Done", "today": "In Progress", "docket": "Planned", "will": "Planned", "waiting": "Waiting",
    "keep": "Monitoring", "paused": "Paused", "team": "Teammate",
}
AREA_MAP = {
    "Deliverability": "Email & outreach", "Dashboard": "Dashboards & reporting", "Brighton": "CRM & migrations",
    "DDN": "CRM & migrations", "GHL": "CRM & migrations", "Prime": "CRM & migrations",
    "Data and Keap": "CRM & migrations", "Fleet": "Automation & AI", "JustCall": "Calls & messaging",
    "Builds": "Commerce & operations", "": "Current work",
}

GIO = re.compile(r"\b(gio|giovanny|gv)\b", re.I)

def role_of(owner):
    """mine: Gio is the first-named owner. involved: Gio is named but secondary. other: Gio isn't named."""
    owner = owner or ""
    if not GIO.search(owner):
        return "other"
    first = re.split(r"[;,/+(]| and ", owner, 1)[0]
    if GIO.search(first) and not re.search(r"assist|handoff|copied|requester", owner, re.I):
        return "mine"
    return "involved"

def words(t):
    return {w for w in re.findall(r"[a-z0-9]+", t.lower()) if len(w) > 2}

inv = json.load(open(INV))
items = []
for i in inv["items"]:
    status = STATUS.get(i["user_status"], "Unconfirmed")
    if i.get("board_lane") in LANE_STATUS and status not in ("Done",):
        status = LANE_STATUS[i["board_lane"]]
    role = "other" if i["ownership"] == "Other owner / team / vendor" or i["user_status"] == "not mine" else role_of(i.get("owner"))
    tasks = [{
        "title": clean(r.get("title")), "detail": clean(r.get("request")), "owner": clean(r.get("owner")),
        "start": r.get("first_date"), "end": r.get("last_date"),
    } for r in i.get("historical_requests", [])]
    tasks.sort(key=lambda t: t["start"] or "")
    title = clean(i["title"])
    items.append({
        "id": f"T{i['id']}", "ref": i["id"], "source": "Inventory", "title": title,
        "area": i["project"] if i["project"] != "CRM & attribution" else "CRM & migrations",
        "status": status, "kind": kind_of(title + " " + " ".join(t["title"] for t in tasks)),
        "role": role, "owner": clean(i.get("owner")), "onBoard": bool(i.get("current_board")),
        "lane": i.get("board_lane"), "description": clean(i.get("user_notes")) or clean(i.get("historical_evidence_summary")),
        "evidence": clean(i.get("historical_evidence_summary")), "start": i.get("first_date"),
        "end": i.get("last_date"), "doneAt": i.get("last_date") if status == "Done" else None, "tasks": tasks,
    })

# Board cards: attach done dates to matching inventory items, add the rest as their own items.
by_words = [(it, words(it["title"])) for it in items]
for f in sorted(glob.glob(os.path.join(BOARD, "*.json"))):
    c = json.load(open(f))
    if c.get("id", "").startswith("tpl-") or os.path.basename(f).startswith("tpl-"):
        continue
    title = clean(c.get("title"))
    status = BUCKET_STATUS.get(c.get("bucket"), "Planned")
    w = words(title)
    match = None
    for it, iw in by_words:
        if w and iw and len(w & iw) / min(len(w), len(iw)) >= 0.75:
            match = it
            break
    done_at = iso_ms(c.get("doneAt")) if status == "Done" else None
    if match:
        match["onBoard"] = True
        if done_at and match["status"] == "Done":
            match["doneAt"] = done_at
        continue
    items.append({
        "id": "B-" + os.path.basename(f)[:-5], "ref": None, "source": "Scrum Board", "title": title,
        "area": AREA_MAP.get(c.get("area", ""), "Current work"), "status": status,
        "kind": kind_of(title + " " + (c.get("summary") or "")), "role": "mine" if c.get("owner") == "Gio" else "other",
        "owner": clean(c.get("owner")), "onBoard": True, "lane": c.get("bucket"),
        "description": clean(c.get("summary")), "evidence": clean(c.get("notes")),
        "start": iso_ms(c.get("createdAt")), "end": iso_ms(c.get("updatedAt")) or iso_ms(c.get("createdAt")),
        "doneAt": done_at, "due": c.get("due"), "tasks": [],
    })

# Status reports Gio wrote (data/reports/*.json): items dated at the report's end date.
for f in sorted(glob.glob(os.path.join(ROOT, "data/reports/*.json"))):
    r = json.load(open(f))
    slug = os.path.basename(f)[:-5]
    for n, x in enumerate(r["items"]):
        title = clean(x["title"])
        items.append({
            "id": f"R-{slug}-{n}", "ref": None, "source": r["source"], "title": title,
            "area": x["area"], "status": x["status"], "kind": x.get("kind") or kind_of(title), "role": role_of(x.get("owner") or "Gio"),
            "owner": clean(x.get("owner")) or "Gio", "onBoard": False, "lane": None, "description": clean(x.get("description")),
            "evidence": clean(x.get("note")), "impact": clean(x.get("impact")), "start": x.get("start") or r["start"],
            "end": x.get("doneAt") or r["date"], "doneAt": (x.get("doneAt") or r["date"]) if x["status"] == "Done" else None,
            "tasks": [{"title": clean(t["title"]), "detail": clean(t.get("detail")), "owner": "", "start": r["start"], "end": r["date"]}
                      for t in x.get("tasks", [])],
        })

# Gio's own status calls (data/overrides.json) win over everything above.
ov_path = os.path.join(ROOT, "data/overrides.json")
overrides = json.load(open(ov_path)) if os.path.exists(ov_path) else {}
for it in items:
    o = overrides.get(it["id"])
    if not o:
        continue
    for k in ("status", "doneAt", "area", "kind", "ongoingFrom", "ongoingTo", "handedTo"):
        if k in o:
            it[k] = o[k]
    if "mine" in o:
        it["role"] = o["mine"]
    if o.get("note"):
        it["gioNote"] = clean(o["note"])
    for n, st in (o.get("tasks") or {}).items():
        if int(n) < len(it["tasks"]):
            it["tasks"][int(n)]["status"] = st
    if it["status"] == "Done" and not it.get("doneAt"):
        it["doneAt"] = it["end"]

# Report items that duplicate an inventory item (data/merges.json) fold into it.
# Status: Gio's call wins, then a Done from either side, then the inventory status.
mp = os.path.join(ROOT, "data/merges.json")
merges = json.load(open(mp)) if os.path.exists(mp) else {}
by_id = {it["id"]: it for it in items}
DONE = ("Done", "Likely Done")
for rid, iid in merges.items():
    r, it = by_id.get(rid), by_id.get(iid)
    if not r or not it:
        continue
    if it.get("gioNote"):
        pass
    elif r.get("gioNote"):
        it["status"], it["doneAt"], it["gioNote"] = r["status"], r.get("doneAt"), r["gioNote"]
        for k in ("ongoingFrom", "ongoingTo", "handedTo"):
            if r.get(k):
                it[k] = r[k]
    elif r["status"] in DONE and it["status"] not in DONE:
        it["status"], it["doneAt"] = r["status"], r.get("doneAt") or it["end"]
    it["evidence"] = " ".join(x for x in (it.get("description"), it.get("evidence")) if x)
    it["description"] = r["description"]
    it["impact"] = r.get("impact") or it.get("impact", "")
    it["source"] = f'{it["source"]} + {r["source"]}'
    it["tasks"] = it["tasks"] + r["tasks"]
    if it["role"] == "other":
        it["role"] = r["role"]
    items.remove(r)

# Unconfirmed items whose email evidence clearly reads as finished (hand-checked list).
lp = os.path.join(ROOT, "data/likely_done.json")
likely = set(json.load(open(lp))) if os.path.exists(lp) else set()
for it in items:
    if it["id"] in likely and it["status"] == "Unconfirmed":
        it["status"], it["doneAt"] = "Likely Done", it["end"]
    # Standing responsibilities rather than one-off tasks.
    if it["status"] == "In Progress" and (it.get("description") or "").startswith("Continuous monitoring"):
        it["status"] = "Monitoring"

# Drop repeated text: evidence that repeats the description, tasks that only restate the item.
for it in items:
    if it.get("evidence") and it["evidence"] in (it.get("description") or ""):
        it["evidence"] = ""
    if it.get("description") and it.get("evidence") and it["description"] in it["evidence"]:
        it["description"], it["evidence"] = it["evidence"], ""
    for t in it["tasks"]:
        if t.get("detail") == t.get("title"):
            t["detail"] = ""
        if t.get("owner") == it.get("owner"):
            t["owner"] = ""
    it["tasks"] = [t for t in it["tasks"] if t.get("detail") or t.get("status") or t["title"] != it["title"]]
    it["mine"] = it["role"] == "mine"

meta = inv["metadata"]
out = {
    "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "snapshot": meta.get("latest_user_confirmation"),
    "coverage": [meta.get("coverage_start"), meta.get("coverage_end")],
    "items": items,
}
json.dump(out, open(OUT, "w"), separators=(",", ":"))
print(f"{len(items)} items -> {OUT} ({os.path.getsize(OUT)//1024} KB)")
