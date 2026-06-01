#!/usr/bin/env python3
"""Parse schema_harmonization_pretty_json.html → db/schemas.db"""
import json
import re
import sqlite3
from pathlib import Path

HTML_FILE = "schema_harmonization_pretty_json.html"
DB_FILE = "db/schemas.db"

HGDB_CLASSES = [
    "AerofacA",  "AerofacP",  "AquedctC",  "AquedctL",  "BarrierL",
    "BluffL",    "BndvoidA",  "BridgeC",   "BridgeL",   "BuildA",
    "BuildL",    "BuildP",    "BuiltupA",  "CoastA",    "CoastL",
    "CommP",     "ContourL",  "CropA",     "CulvertC",  "DamA",
    "DamC",      "DamL",      "DangerA",   "DangerL",   "DangerP",
    "DepthL",    "DisposeA",  "ElevP",     "EmbankA",   "EmbankL",
    "ExtractA",  "ExtractP",  "FerryL",    "FordC",     "FordL",
    "FortA",     "FortP",     "GrassA",    "GroundA",   "HarborP",
    "InterL",    "LakeresA",  "LandfrmL",  "LandfrmP",  "LandmrkA",
    "LandmrkL",  "LandmrkP",  "LiftL",     "Lndfrm2A",  "LockA",
    "MarkersP",  "MisaeroP",  "MiscL",     "MtnP",      "NamedLocP",
    "OrchardA",  "PierA",     "PierL",     "PipeL",     "PolbndA",
    "PolbndL",   "PolbndP",   "PowerA",    "PowerL",    "PowerP",
    "RailrdL",   "RapidsC",   "RigwellP",  "RoadL",     "RouteP",
    "RuinsA",    "RuinsP",    "RunwayA",   "SeastrtA",  "SeastrtL",
    "SportA",    "StorageA",  "StorageP",  "SubstatA",  "SubstatP",
    "SwampA",    "ThermalP",  "TlmhydroP", "TlmutilP",  "TrackL",
    "TrailL",    "TreatA",    "TreesA",    "TreesP",    "TunnelC",
    "TunnelL",   "WatrcrsA",  "WatrcrsL",  "WellsprP",
]

SCHEMA = """
CREATE TABLE feature_classes (
    id             INTEGER PRIMARY KEY,
    canonical_name TEXT UNIQUE NOT NULL,
    badge          TEXT NOT NULL DEFAULT 'Retained'
);
CREATE TABLE fc_aliases (
    id    INTEGER PRIMARY KEY,
    fc_id INTEGER REFERENCES feature_classes(id),
    alias TEXT NOT NULL,
    scale TEXT NOT NULL
);
CREATE TABLE fc_membership (
    id           INTEGER PRIMARY KEY,
    fc_id        INTEGER REFERENCES feature_classes(id),
    scale        TEXT NOT NULL,
    display_name TEXT NOT NULL
);
CREATE TABLE subtypes (
    id           INTEGER PRIMARY KEY,
    fc_id        INTEGER REFERENCES feature_classes(id),
    fcode        TEXT,
    subtype_name TEXT,
    tms_action   TEXT,
    hgdb_action  TEXT,
    remarks      TEXT,
    sort_order   INTEGER
);
CREATE TABLE changelog (
    id          INTEGER PRIMARY KEY,
    fc_id       INTEGER REFERENCES feature_classes(id),
    change_text TEXT,
    source      TEXT,
    change_date TEXT,
    version     TEXT,
    change_type TEXT,
    sort_order  INTEGER
);
CREATE TABLE domains (
    id          INTEGER PRIMARY KEY,
    fc_id       INTEGER REFERENCES feature_classes(id),
    field_name  TEXT,
    field_alias TEXT,
    sort_order  INTEGER
);
CREATE TABLE domain_rows (
    id          INTEGER PRIMARY KEY,
    domain_id   INTEGER REFERENCES domains(id),
    cd_code     TEXT,
    cd_name     TEXT,
    pd_code     TEXT,
    pd_name     TEXT,
    harm_code   TEXT,
    harm_name   TEXT,
    harm_status TEXT,
    remarks     TEXT,
    sort_order  INTEGER
);
"""


def extract_js_object(content: str, var_name: str):
    """Extract a JS object/array literal assigned to a const and parse it as JSON."""
    marker = f"const {var_name} = "
    start = content.index(marker) + len(marker)
    depth = 0
    in_str = False
    esc = False
    str_char = None
    i = start
    while i < len(content):
        ch = content[i]
        if esc:
            esc = False
        elif in_str:
            if ch == "\\":
                esc = True
            elif ch == str_char:
                in_str = False
        elif ch in ('"', "'"):
            in_str = True
            str_char = ch
        elif ch in ("{", "["):
            depth += 1
        elif ch in ("}", "]"):
            depth -= 1
            if depth == 0:
                raw = content[start : i + 1]
                # Normalise single-quoted JS keys → JSON double-quoted keys
                raw = re.sub(r"'([^']+)'(\s*:)", r'"\1"\2', raw)
                return json.loads(raw)
        i += 1
    raise ValueError(f"Could not find closing brace for {var_name}")


def populate(conn: sqlite3.Connection, fc_data: dict, alias_index: dict, lists: dict):
    fc_ids: dict[str, int] = {}

    for name, fc in fc_data.items():
        cur = conn.execute(
            "INSERT OR REPLACE INTO feature_classes (canonical_name, badge) VALUES (?, ?)",
            (name, fc.get("badge", "Retained")),
        )
        fid = cur.lastrowid
        fc_ids[name] = fid

        for alias in fc.get("aliases_10k", []):
            conn.execute("INSERT INTO fc_aliases(fc_id, alias, scale) VALUES(?, ?, '10k')", (fid, alias))
        for alias in fc.get("aliases_50k", []):
            conn.execute("INSERT INTO fc_aliases(fc_id, alias, scale) VALUES(?, ?, '50k')", (fid, alias))

        for i, st in enumerate(fc.get("subtypes", [])):
            conn.execute(
                "INSERT INTO subtypes(fc_id, fcode, subtype_name, tms_action, hgdb_action, remarks, sort_order)"
                " VALUES(?, ?, ?, ?, ?, ?, ?)",
                (fid, st.get("fcode"), st.get("subtype"), st.get("tms_action"),
                 st.get("hgdb_action"), st.get("remarks"), i),
            )

        for i, cl in enumerate(fc.get("changelog", [])):
            conn.execute(
                "INSERT INTO changelog(fc_id, change_text, source, change_date, version, change_type, sort_order)"
                " VALUES(?, ?, ?, ?, ?, ?, ?)",
                (fid, cl.get("change"), cl.get("source"), cl.get("date"),
                 cl.get("version"), cl.get("type"), i),
            )

        for j, dom in enumerate(fc.get("domains", [])):
            dcur = conn.execute(
                "INSERT INTO domains(fc_id, field_name, field_alias, sort_order) VALUES(?, ?, ?, ?)",
                (fid, dom.get("field"), dom.get("alias"), j),
            )
            did = dcur.lastrowid
            for k, row in enumerate(dom.get("rows", [])):
                def _str(v):
                    return None if v is None else str(v)
                conn.execute(
                    "INSERT INTO domain_rows"
                    "(domain_id, cd_code, cd_name, pd_code, pd_name, harm_code, harm_name, harm_status, remarks, sort_order)"
                    " VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (did, _str(row.get("cd_code")), row.get("cd_name"),
                     _str(row.get("pd_code")), row.get("pd_name"),
                     _str(row.get("harm_code")), row.get("harm_name"),
                     row.get("harm_status"), row.get("remarks"), k),
                )

    for scale, names in lists.items():
        for display_name in names:
            canonical = alias_index.get(display_name.lower(), display_name)
            fid = fc_ids.get(canonical)
            if fid:
                conn.execute(
                    "INSERT INTO fc_membership(fc_id, scale, display_name) VALUES(?, ?, ?)",
                    (fid, scale, display_name),
                )

    for name in HGDB_CLASSES:
        fid = fc_ids.get(name)
        if fid:
            conn.execute(
                "INSERT INTO fc_membership(fc_id, scale, display_name) VALUES(?, 'hdm', ?)",
                (fid, name),
            )

    conn.commit()


if __name__ == "__main__":
    content = Path(HTML_FILE).read_text(encoding="utf-8")

    print("Extracting FC_DATA …")
    fc_data = extract_js_object(content, "FC_DATA")
    print(f"  {len(fc_data)} feature classes")

    alias_index = extract_js_object(content, "ALIAS_INDEX")
    lists = extract_js_object(content, "LISTS")

    Path("db").mkdir(exist_ok=True)
    db_path = Path(DB_FILE)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(DB_FILE)
    conn.executescript(SCHEMA)
    populate(conn, fc_data, alias_index, lists)
    conn.close()
    print(f"Database written -> {DB_FILE}")
