"""Populate HGDB memberships and add any FCs not in the source data."""
import sqlite3

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

# FCs to insert if not already in feature_classes (canonical name, badge)
NEW_FCS = [
    ("NamedLocP", "Added"),
]

conn = sqlite3.connect("db/schemas.db")

for name, badge in NEW_FCS:
    exists = conn.execute(
        "SELECT 1 FROM feature_classes WHERE canonical_name=?", (name,)
    ).fetchone()
    if not exists:
        conn.execute(
            "INSERT INTO feature_classes(canonical_name, badge) VALUES(?, ?)",
            (name, badge),
        )
        print(f"  Inserted new FC: {name} ({badge})")
    else:
        print(f"  Already exists: {name}")

conn.execute("DELETE FROM fc_membership WHERE scale='hdm'")
added, skipped = 0, []
for name in HGDB_CLASSES:
    row = conn.execute(
        "SELECT id FROM feature_classes WHERE canonical_name=?", (name,)
    ).fetchone()
    if row:
        conn.execute(
            "INSERT INTO fc_membership(fc_id, scale, display_name) VALUES(?, 'hdm', ?)",
            (row[0], name),
        )
        added += 1
    else:
        skipped.append(name)

conn.commit()
conn.close()
print(f"Added {added} HGDB memberships.")
if skipped:
    print(f"Not found in DB: {', '.join(skipped)}")
