#!/usr/bin/env python3
"""Build static site from db/schemas.db → docs/"""
import shutil
import sqlite3
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

DB_FILE = "db/schemas.db"
OUT_DIR = Path("docs")
STATIC_DIR = Path("static")


# ── Jinja2 filters ────────────────────────────────────────────────────────────

def action_chip_class(action: str | None) -> str:
    if not action or action.strip().lower() in ("", "nan"):
        return ""
    a = action.lower()
    if a == "ok" or "retain" in a:
        return "ac-retain"
    if "remove" in a:
        return "ac-remove"
    if a.startswith("add") or "add in" in a:
        return "ac-add"
    if any(k in a for k in ("edit", "rename", "change", "merge")):
        return "ac-edit"
    if "tbda" in a or a == "tbd":
        return "ac-tbda"
    return "ac-other"


def cl_meta(change_type: str | None) -> dict:
    return {
        "***": {"label": "domain change",  "cls": "cl-domain"},
        "**":  {"label": "fc deleted",     "cls": "cl-fcdelete"},
        "*":   {"label": "10k mapping",    "cls": "cl-mapping"},
    }.get(change_type or "", {"label": "schema change", "cls": "cl-schema"})


def format_date(d: str | None) -> str:
    if not d or d in ("nan", "NaT"):
        return "—"
    return d.replace(" 00:00:00", "")


def badge_label(badge: str) -> str:
    return {"Removed": "DEL", "Modified": "MOD", "Added": "ADD"}.get(badge, "RET")


# ── Queries ───────────────────────────────────────────────────────────────────

def get_fc_list(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, canonical_name, badge FROM feature_classes ORDER BY canonical_name"
    ).fetchall()
    result = []
    for r in rows:
        scales = [s[0] for s in conn.execute(
            "SELECT DISTINCT scale FROM fc_membership WHERE fc_id=?", (r["id"],)
        ).fetchall()]
        result.append({"id": r["id"], "canonical_name": r["canonical_name"],
                       "badge": r["badge"], "scales": scales})
    return result


def get_fc_detail(conn: sqlite3.Connection, fc_row: sqlite3.Row) -> dict:
    fid = fc_row["id"]

    aliases_10k = [r[0] for r in conn.execute(
        "SELECT alias FROM fc_aliases WHERE fc_id=? AND scale='10k'", (fid,)
    ).fetchall()]
    aliases_50k = [r[0] for r in conn.execute(
        "SELECT alias FROM fc_aliases WHERE fc_id=? AND scale='50k'", (fid,)
    ).fetchall()]

    subtypes = [dict(r) for r in conn.execute(
        "SELECT fcode, subtype_name, tms_action, hgdb_action, remarks"
        " FROM subtypes WHERE fc_id=? ORDER BY sort_order", (fid,)
    ).fetchall()]

    changelog = [dict(r) for r in conn.execute(
        "SELECT change_text, source, change_date, version, change_type"
        " FROM changelog WHERE fc_id=? ORDER BY sort_order", (fid,)
    ).fetchall()]

    domains_raw = conn.execute(
        "SELECT id, field_name, field_alias FROM domains WHERE fc_id=? ORDER BY sort_order", (fid,)
    ).fetchall()
    domains = []
    for dom in domains_raw:
        dr = [dict(r) for r in conn.execute(
            "SELECT cd_code, cd_name, pd_code, pd_name, harm_code, harm_name, harm_status, remarks"
            " FROM domain_rows WHERE domain_id=? ORDER BY sort_order", (dom["id"],)
        ).fetchall()]
        domains.append({"field_name": dom["field_name"], "field_alias": dom["field_alias"], "rows": dr})

    return {
        "canonical_name": fc_row["canonical_name"],
        "badge": fc_row["badge"],
        "aliases_10k": aliases_10k,
        "aliases_50k": aliases_50k,
        "subtypes": subtypes,
        "changelog": changelog,
        "domains": domains,
    }


# ── Build ─────────────────────────────────────────────────────────────────────

def main():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row

    env = Environment(loader=FileSystemLoader("templates"), autoescape=True)
    env.filters["action_chip_class"] = action_chip_class
    env.filters["cl_meta"] = cl_meta
    env.filters["format_date"] = format_date
    env.filters["badge_label"] = badge_label

    (OUT_DIR / "fc").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "static").mkdir(parents=True, exist_ok=True)

    fc_list = get_fc_list(conn)

    counts = {
        "total":    len(fc_list),
        "retained": sum(1 for f in fc_list if f["badge"] == "Retained"),
        "modified": sum(1 for f in fc_list if f["badge"] == "Modified"),
        "removed":  sum(1 for f in fc_list if f["badge"] == "Removed"),
        "added":    sum(1 for f in fc_list if f["badge"] == "Added"),
    }

    # index.html
    tmpl = env.get_template("index.html")
    (OUT_DIR / "index.html").write_text(
        tmpl.render(fc_list=fc_list, counts=counts, active=None, static_prefix=""),
        encoding="utf-8",
    )
    print("Built index.html")

    # fc/*.html
    detail_tmpl = env.get_template("fc_detail.html")
    all_fcs = conn.execute(
        "SELECT id, canonical_name, badge FROM feature_classes ORDER BY canonical_name"
    ).fetchall()
    for fc_row in all_fcs:
        fc = get_fc_detail(conn, fc_row)
        safe = fc["canonical_name"].replace("/", "_")
        html = detail_tmpl.render(
            fc=fc, fc_list=fc_list,
            active=fc["canonical_name"],
            static_prefix="../",
        )
        (OUT_DIR / "fc" / f"{safe}.html").write_text(html, encoding="utf-8")
        print(f"  Built fc/{safe}.html")

    # static assets
    shutil.copy(STATIC_DIR / "style.css", OUT_DIR / "static" / "style.css")

    conn.close()
    print(f"\nDone - site in {OUT_DIR}/")
    print("GitHub Pages: Settings -> Pages -> Deploy from branch -> main -> /docs")


if __name__ == "__main__":
    main()
