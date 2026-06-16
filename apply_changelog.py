"""Apply the updated SchemaChangeLog.xlsx as the authoritative source.

  1. Re-imports all changelog entries from the xlsx (replaces existing)
  2. Corrects 10k membership targets based on the changelog mapping decisions
  3. Adds new HDM FCs (RoadA, RoadCasementL) and their HDM memberships
"""
import sqlite3
import openpyxl
from datetime import datetime
from pathlib import Path

XLSX = "temp/SchemaChangeLog.xlsx"
DB   = "db/schemas.db"

# ── Authoritative 10k → HDM corrections ──────────────────────────────────────
# display_name (as it appears in 10k sidebar) → target canonical HDM FC name
CORRECTIONS_10K = {
    "Alley_L":          "RoadL",          # primary mapping (stairways→TrailL is secondary)
    "ComplexOutline_A": "PolbndA",         # CORRECTED from old alias (was BndvoidA)
    "Fort_L":           "FortL",           # maps to new HDM FC FortL (FortA was deleted)
    "Road_A":           "RoadA",           # stub → new HDM FC
    "RoadCasement_L":   "RoadCasementL",   # stub → new HDM FC (user confirmed no underscore)
    "Swamp_A":          "SwampA",          # was wrongly treated as dropped
    "Trans_L":          "BarrierL",        # stub → BarrierL
    "Trees_P":          "TreesP",          # stub → TreesP
    "Wellspr_P":        "WellsprP",        # wrong alias (was RigwellP)
}

# ── New HDM FCs to create and add to HDM membership ──────────────────────────
NEW_HDM_FCS = [
    ("RoadA",        "Added"),
    ("RoadCasementL","Added"),
    ("FortL",        "Added"),   # FortA was deleted; FortL is the new HDM FC
]

# FCs removed from HDM — strip HDM membership, set badge Removed
REMOVED_FROM_HDM = ["FortA", "PolbndL", "PolbndA", "PolbndP"]

# FCs whose badge needs explicit correction (schema/domain changes not auto-detected)
BADGE_CORRECTIONS = {
    "BuildL":   "Modified",  # domain will not be migrated (v6 changelog)
    "PolbndA":  "",          # removed from HDM but model still in progress
    "PolbndP":  "",          # removed from HDM but model still in progress
    # Retained → Modified: have v4 changelog entries (default value / field changes)
    "BuiltupA": "Modified",
    "DamA":     "Modified",
    "DamC":     "Modified",
    "FortP":    "Modified",
    "LockA":    "Modified",
    "RouteP":   "Modified",
    "TunnelC":  "Modified",
    # Retained → Modified: ** subtype renames in changelog
    "LiftL":    "Modified",
    "LandfrmP": "Modified",
    # Badge cleared — Modified in DB but no changelog evidence; status pending review
    "BndvoidA": "",
    "CulvertC": "",
    "CoastL":   "",
    "DangerL":  "",
    "EmbankA":  "",
    "FerryL":   "",
    "OrchardA": "",
    "PierA":    "",
    "PipeL":    "",
    "PowerL":   "",
    "SeastrtA": "",
    "TlmutilP": "",
    "TreatA":   "",
}

# ── Old stubs to remove once their 10k entries are re-pointed ────────────────
REMOVE_STUBS = ["Road_A", "RoadCasement_L"]

# ── Changelog name corrections (Excel name → DB canonical name/s) ─────────────
# List value = one entry applied to multiple FCs; string value = simple rename
NAME_CORRECTIONS = {
    # Typos / alternate spellings in the Excel
    "AerofacA/AerofacP": ["AerofacA", "AerofacP"],
    "Embank_A":           "EmbankA",
    "Embank_L":           "EmbankL",
    "GoundTxt":           "GroundTxt",
    "Landfrm2A":          "Lndfrm2A",
    "WatercrsA":          "WatrcrsA",
    "WatercrsL":          "WatrcrsL",
    "Wellspr_P":          "WellsprP",
    # 10k source FCs not in DB → route changelog to their HDM target
    "AdministrativeBoundary_A": "PolbndA",
    "AdministrativeBoundary_L": "PolbndL",
    "Cemetery_A":               "LandmrkA",
    "Cloud_A":                  "BndvoidA",
    "CoralReef_P":              "DangerP",
    "LakePond_A":               "LakeresA",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_fc_id(conn, name):
    r = conn.execute(
        "SELECT id FROM feature_classes WHERE canonical_name=?", (name,)
    ).fetchone()
    return r[0] if r else None


def ensure_fc(conn, name, badge):
    fid = get_fc_id(conn, name)
    if fid is None:
        cur = conn.execute(
            "INSERT INTO feature_classes(canonical_name, badge) VALUES(?,?)",
            (name, badge),
        )
        fid = cur.lastrowid
        print(f"  Created FC: {name} ({badge})")
    else:
        conn.execute("UPDATE feature_classes SET badge=? WHERE id=?", (badge, fid))
        print(f"  Updated badge: {name} -> {badge}")
    return fid


# ── 1. Re-import changelog ────────────────────────────────────────────────────

def import_changelog(conn):
    wb   = openpyxl.load_workbook(XLSX, read_only=True)
    ws   = wb["List of Changes"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))

    conn.execute("DELETE FROM changelog")
    inserted = skipped = 0
    order: dict[int, int] = {}

    for row in rows:
        raw_fc  = str(row[0]).strip() if row[0] else ""
        change  = str(row[1]).strip() if row[1] else ""
        source  = str(row[2]).strip() if row[2] else ""
        date    = row[3]
        version = str(row[4]).strip() if row[4] else ""

        if not raw_fc or not change or change == "None":
            continue

        if raw_fc.startswith("***"):
            change_type = "***"
        elif raw_fc.startswith("**"):
            change_type = "**"
        elif raw_fc.startswith("*"):
            change_type = "*"
        else:
            change_type = ""

        # Clean FC name: strip stars, strip sub-qualifiers
        clean = raw_fc.lstrip("*").strip()
        clean = clean.split("(")[0].split(":")[0].strip()
        if not clean:
            continue

        date_str = date.strftime("%Y-%m-%d") if isinstance(date, datetime) else (str(date) if date else "")

        # Resolve name correction → may expand to multiple targets
        corrected = NAME_CORRECTIONS.get(clean, clean)
        targets = corrected if isinstance(corrected, list) else [corrected]

        matched = False
        for target in targets:
            fid = get_fc_id(conn, target)
            if fid is None:
                continue
            matched = True
            i = order.get(fid, 0)
            conn.execute(
                "INSERT INTO changelog(fc_id,change_text,source,change_date,version,change_type,sort_order)"
                " VALUES(?,?,?,?,?,?,?)",
                (fid, change, source, date_str, version, change_type, i),
            )
            order[fid] = i + 1
            inserted += 1

        if not matched:
            skipped += 1

    conn.commit()
    print(f"  {inserted} entries imported, {skipped} skipped (FC not in DB)")


# ── 2. Add new HDM FCs ────────────────────────────────────────────────────────

def add_hdm_fcs(conn):
    for name, badge in NEW_HDM_FCS:
        fid = ensure_fc(conn, name, badge)
        exists = conn.execute(
            "SELECT 1 FROM fc_membership WHERE fc_id=? AND scale='hdm'", (fid,)
        ).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO fc_membership(fc_id, scale, display_name) VALUES(?,'hdm',?)",
                (fid, name),
            )
            print(f"  Added {name} to HDM membership")
    conn.commit()


# ── 3. Fix 10k memberships ────────────────────────────────────────────────────

def fix_10k_memberships(conn):
    for display_name, target in CORRECTIONS_10K.items():
        target_fid = get_fc_id(conn, target)
        if target_fid is None:
            print(f"  WARN: target '{target}' not in DB — skipping {display_name}")
            continue
        r = conn.execute(
            "UPDATE fc_membership SET fc_id=? WHERE scale='10k' AND display_name=?",
            (target_fid, display_name),
        )
        if r.rowcount:
            print(f"  {display_name:30s} -> {target}")
        else:
            print(f"  WARN: no 10k row for '{display_name}'")
    conn.commit()


# ── 4. Remove orphaned stubs ──────────────────────────────────────────────────

def remove_stubs(conn):
    for name in REMOVE_STUBS:
        fid = get_fc_id(conn, name)
        if fid is None:
            continue
        # Only delete if no memberships left
        remaining = conn.execute(
            "SELECT COUNT(*) FROM fc_membership WHERE fc_id=?", (fid,)
        ).fetchone()[0]
        if remaining == 0:
            conn.execute("DELETE FROM feature_classes WHERE id=?", (fid,))
            print(f"  Deleted orphaned stub: {name}")
        else:
            print(f"  Kept {name} (still has {remaining} membership row(s))")
    conn.commit()


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not Path(XLSX).exists():
        raise FileNotFoundError(f"{XLSX} not found")

    conn = sqlite3.connect(DB)

    print("=== 1. Re-importing changelog ===")
    import_changelog(conn)

    print("\n=== 2. Adding new HDM FCs ===")
    add_hdm_fcs(conn)

    print("\n=== 3. Fixing 10k memberships ===")
    fix_10k_memberships(conn)

    print("\n=== 4. Removing orphaned stubs ===")
    remove_stubs(conn)

    print("\n=== 5. Removing FCs deleted from HDM ===")
    for name in REMOVED_FROM_HDM:
        fid = get_fc_id(conn, name)
        if fid:
            conn.execute("DELETE FROM fc_membership WHERE fc_id=? AND scale='hdm'", (fid,))
            conn.execute("UPDATE feature_classes SET badge='Removed' WHERE id=?", (fid,))
            print(f"  {name}: removed from HDM, badge -> Removed")
    conn.commit()

    print("\n=== 6. Applying badge corrections ===")
    for name, badge in BADGE_CORRECTIONS.items():
        fid = get_fc_id(conn, name)
        if fid:
            conn.execute("UPDATE feature_classes SET badge=? WHERE id=?", (badge, fid))
            print(f"  {name}: badge -> {badge}")
    conn.commit()

    print("\n=== 7. Converting remaining Retained -> Modified ===")
    r = conn.execute("UPDATE feature_classes SET badge='Modified' WHERE badge='Retained'")
    print(f"  {r.rowcount} FCs updated")
    conn.commit()

    print("\n=== Summary ===")
    for scale in ("hdm", "10k", "50k"):
        n = conn.execute("SELECT COUNT(*) FROM fc_membership WHERE scale=?", (scale,)).fetchone()[0]
        print(f"  fc_membership [{scale}]: {n}")
    print(f"  changelog entries  : {conn.execute('SELECT COUNT(*) FROM changelog').fetchone()[0]}")
    print(f"  feature_classes    : {conn.execute('SELECT COUNT(*) FROM feature_classes').fetchone()[0]}")

    conn.close()
    print("\nDone. Run: python build.py")
