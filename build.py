#!/usr/bin/env python3
"""Build static site from db/schemas.db → docs/"""
import json
import re
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


_DEL_PAT = re.compile(r'\b(?:deleted|dropped|removed|unmapped|not collected|unassigned)\b')
_ADD_PAT = re.compile(r'\b(?:added|created|mapped to|assigned)\b')

def cl_meta(change_type: str | None, change_text: str = "") -> dict:
    t = (change_text or "").lower()
    if change_type == "*":
        return {"label": "MTCH", "cls": "cl-mapping"}
    if change_type == "***":
        return {"label": "MOD",  "cls": "cl-domain"}
    if _DEL_PAT.search(t):
        return {"label": "DEL", "cls": "cl-delete"}
    if _ADD_PAT.search(t):
        return {"label": "ADD", "cls": "cl-add"}
    return {"label": "MOD", "cls": "cl-mod"}


def format_date(d: str | None) -> str:
    if not d or d in ("nan", "NaT"):
        return "—"
    return d.replace(" 00:00:00", "")


def badge_label(badge: str | None) -> str:
    return {
        "Modified": "MOD",
        "Added":    "ADD",
        "Removed":  "DEL",
        "Deleted":  "DEL",
        "Mapped":   "MTCH",
        "Retained": "RET",
    }.get(badge or "", "")


# ── Queries ───────────────────────────────────────────────────────────────────

def get_sidebar_items(conn: sqlite3.Connection) -> list[dict]:
    """Flat sidebar list ordered HDM → 10k → 50k.

    HDM items show the harmonised badge (Retained/Modified/Added).
    10k/50k items show Mapped (FC exists in HDM) or Deleted (not in HDM),
    but always link to the canonical HDM detail page.
    """
    hdm_set = {
        r["canonical_name"]
        for r in conn.execute(
            """
            SELECT fc.canonical_name
              FROM fc_membership m
              JOIN feature_classes fc ON fc.id = m.fc_id
             WHERE m.scale = 'hdm'
            """
        ).fetchall()
    }

    items = []
    for scale in ("hdm", "10k", "50k"):
        rows = conn.execute(
            """
            SELECT fc.canonical_name, fc.badge, m.display_name
              FROM fc_membership m
              JOIN feature_classes fc ON fc.id = m.fc_id
             WHERE m.scale = ?
             ORDER BY m.display_name COLLATE NOCASE
            """,
            (scale,),
        ).fetchall()
        for r in rows:
            if scale == "hdm":
                display_badge = r["badge"]          # Retained / Modified / Added
            else:
                display_badge = (
                    "Mapped" if r["canonical_name"] in hdm_set else "Deleted"
                )
            items.append(
                {
                    "canonical_name": r["canonical_name"],
                    "display_name":   r["display_name"],
                    "badge":          r["badge"],        # raw DB badge
                    "display_badge":  display_badge,     # shown in sidebar
                    "scale":          scale,
                }
            )
    return items


def get_fc_detail(conn: sqlite3.Connection, fc_row: sqlite3.Row) -> dict:
    fid = fc_row["id"]

    aliases_10k = [r[0] for r in conn.execute(
        "SELECT alias FROM fc_aliases WHERE fc_id=? AND scale='10k'", (fid,)
    ).fetchall()]
    aliases_50k = [r[0] for r in conn.execute(
        "SELECT alias FROM fc_aliases WHERE fc_id=? AND scale='50k'", (fid,)
    ).fetchall()]

    # Authoritative lineage from fc_membership (covers new FCs not in fc_aliases)
    sources_10k = [r[0] for r in conn.execute(
        "SELECT display_name FROM fc_membership WHERE fc_id=? AND scale='10k'", (fid,)
    ).fetchall()]
    sources_50k = [r[0] for r in conn.execute(
        "SELECT display_name FROM fc_membership WHERE fc_id=? AND scale='50k'", (fid,)
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
        "sources_10k": sources_10k,
        "sources_50k": sources_50k,
        "subtypes": subtypes,
        "changelog": changelog,
        "domains": domains,
    }


# ── Nav data ──────────────────────────────────────────────────────────────────

def write_nav_data(sidebar_items: list[dict], out_dir: Path) -> None:
    items = [
        {
            "name":      item["display_name"].lower(),
            "display":   item["display_name"],
            "canonical": item["canonical_name"],
            "badge":     item["display_badge"],
            "list":      item["scale"],
        }
        for item in sidebar_items
    ]
    js = "const NAV_DATA = " + json.dumps(items, ensure_ascii=False) + ";\n"
    (out_dir / "static" / "nav-data.js").write_text(js, encoding="utf-8")
    print("Built static/nav-data.js")


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

    sidebar_items = get_sidebar_items(conn)
    write_nav_data(sidebar_items, OUT_DIR)

    all_badges = conn.execute("SELECT badge FROM feature_classes").fetchall()
    counts = {
        "total":    len(all_badges),
        "retained": sum(1 for r in all_badges if r["badge"] == "Retained"),
        "modified": sum(1 for r in all_badges if r["badge"] == "Modified"),
        "removed":  sum(1 for r in all_badges if r["badge"] == "Removed"),
        "added":    sum(1 for r in all_badges if r["badge"] == "Added"),
    }

    # index.html
    tmpl = env.get_template("index.html")
    (OUT_DIR / "index.html").write_text(
        tmpl.render(counts=counts, active=None, static_prefix=""),
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
            fc=fc,
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
