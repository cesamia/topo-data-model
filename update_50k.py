"""Replace the 50k feature class membership list in db/schemas.db."""
import sqlite3

SCALE_50K = [
    "AerofacA",   "AerofacP",   "AgristrA",   "AgristrP",   "AquedctC",
    "AquedctL",   "AsphaltA",   "BarrierL",   "BluffL",     "BndvoidA",
    "BridgeC",    "BridgeL",    "BuildA",     "BuildL",     "BuildP",
    "BuiltupA",   "CisternP",   "CoastA",     "CoastL",     "CommA",
    "CommP",      "ContourL",   "CropA",      "CulvertC",   "DamA",
    "DamC",       "DamL",       "DangerA",    "DangerL",    "DangerP",
    "DepthL",     "DisposeA",   "ElevoidA",   "ElevP",      "EmbankA",
    "EmbankL",    "ExtractA",   "ExtractP",   "FerryC",     "FerryL",
    "FirebrkL",   "FordC",      "FordL",      "FortA",      "FortP",
    "GrassA",     "GroundA",    "GroundP",    "GroundTxt",  "HarborA",
    "HarborP",    "HedgeL",     "HydroP",     "HydroTxt",   "HydvoidA",
    "IndL",       "IndvoidA",   "InterL",     "InundA",     "LakeresA",
    "LandfrmL",   "LandfrmP",   "LandmrkA",   "LandmrkL",   "LandmrkP",
    "LiftL",      "Lndfrm1A",   "Lndfrm2A",   "LockA",      "MarkersP",
    "MisaeroP",   "MiscA",      "MiscL",      "MiscP",      "MispopA",
    "MispopP",    "MobileA",    "MtnP",       "NuclearA",   "ObstrP",
    "OrchardA",   "PhyvoidA",   "PierA",      "PierL",      "PipeL",
    "PlazaA",     "PolbndA",    "PolbndL",    "PolbndP",    "PopvoidA",
    "PowerA",     "PowerL",     "PowerP",     "ProcessA",   "ProcessP",
    "PumpingA",   "PumpingP",   "RailrdL",    "RampL",      "RapidsC",
    "RapidsL",    "RestA",      "RigwellP",   "RoadL",      "RouteP",
    "RrturnC",    "RryardA",    "RryardP",    "RuinsA",     "RuinsP",
    "RunwayA",    "SeastrtA",   "SeastrtL",   "ShedC",      "ShedL",
    "SportA",     "StoragA",    "StorageA",   "StorageP",   "SubstatA",
    "SubstatP",   "SwampA",     "TeethA",     "TeethL",     "TeleL",
    "ThermalP",   "TlmbndC",    "TlmBndL",    "TlmhydroA",  "TlmhydroC",
    "TlmhydroL",  "TlmhydroP",  "TlmindP",    "TlmphysA",   "TlmpopA",
    "TlmpopP",    "TlmtransA",  "TlmtransC",  "TlmtransL",  "TlmtransP",
    "TlmutilP",   "TlmvegA",    "TowerP",     "TrackL",     "TrailL",
    "TravoidA",   "TreatA",     "TreesA",     "TreesP",     "TundraA",
    "TunnelC",    "TunnelL",    "UtivoidA",   "VegvoidA",   "WatrcrsA",
    "WatrcrsL",   "WellsprP",
]

conn = sqlite3.connect("db/schemas.db")

conn.execute("DELETE FROM fc_membership WHERE scale='50k'")

added, new_fcs = 0, []
for name in SCALE_50K:
    row = conn.execute(
        "SELECT id FROM feature_classes WHERE canonical_name=?", (name,)
    ).fetchone()
    if not row:
        cur = conn.execute(
            "INSERT INTO feature_classes(canonical_name, badge) VALUES(?, 'Removed')",
            (name,),
        )
        fc_id = cur.lastrowid
        new_fcs.append(name)
    else:
        fc_id = row[0]

    conn.execute(
        "INSERT INTO fc_membership(fc_id, scale, display_name) VALUES(?, '50k', ?)",
        (fc_id, name),
    )
    added += 1

conn.commit()
conn.close()
print(f"50k membership updated: {added} entries.")
if new_fcs:
    print(f"New FCs inserted ({len(new_fcs)}): {', '.join(new_fcs)}")
