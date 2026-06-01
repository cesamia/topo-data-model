"""Replace the 10k feature class membership list in db/schemas.db."""
import sqlite3

SCALE_10K = [
    "AdministrativeBoundary_A", "AdministrativeBoundary_L", "AirportAirfield_A",
    "Alley_L",          "Bridge_L",         "Bridge_P",         "Building_A",
    "Building_P",       "Canal_L",          "Cemetery_A",       "Cemetery_P",
    "Cloud_A",          "Coast_A",          "Coast_L",          "CommunicationTower_P",
    "ComplexOutline_A", "Contour_L",        "CoralReef_A",      "CoralReef_L",
    "CoralReef_P",      "Crop_A",           "Dam_L",            "Ditch_A",
    "Ditch_L",          "Fence_L",          "Ferry_L",          "Fort_L",
    "Grass_A",          "Grid",             "Ground_A",         "Heliport_P",
    "ICMHydro_P",       "IndexMap",         "LakePond_A",       "LakePond_L",
    "Lighthouse_P",     "Markers_P",        "Military_P",       "Mine_P",
    "Misc_L",           "Monument_P",       "Mtn_P",            "Orchard_A",
    "Park_P",           "Pavement_A",       "Pier_A",           "Pipe_L",
    "PowerLine_L",      "Quarry_A",         "Quarry_L",         "Railroad_L",
    "RiverStream_A",    "RiverStream_L",    "Road_A",           "Road_L",
    "RoadCasement_L",   "RoadMedian_A",     "Ruins_A",          "SideWalk_L",
    "Slope_A",          "Sport_A",          "SpotElevation_P",  "Swamp_A",
    "Tank_A",           "Tank_P",           "Tower_P",          "Trail_L",
    "Trans_L",          "Treat_A",          "Treat_L",          "Trees_A",
    "Trees_P",          "Tunnel_L",         "Veg_A",            "Veg_L",
    "Wellspr_P",
]

assert len(SCALE_10K) == 76, f"Expected 76, got {len(SCALE_10K)}"

conn = sqlite3.connect("db/schemas.db")

conn.execute("DELETE FROM fc_membership WHERE scale='10k'")

added, new_fcs, alias_hits = 0, [], []
for name in SCALE_10K:
    # 1. Check fc_aliases — catches renamed mappings (e.g. Heliport_P → AerofacP)
    row = conn.execute(
        "SELECT fc_id FROM fc_aliases WHERE LOWER(alias) = LOWER(?) AND scale = '10k'",
        (name,),
    ).fetchone()
    if row:
        fc_id = row[0]
        canonical = conn.execute(
            "SELECT canonical_name FROM feature_classes WHERE id=?", (fc_id,)
        ).fetchone()[0]
        if canonical != name:
            alias_hits.append(f"{name} -> {canonical}")
    else:
        # 2. Direct name match in feature_classes
        row = conn.execute(
            "SELECT id FROM feature_classes WHERE canonical_name = ?", (name,)
        ).fetchone()
        if row:
            fc_id = row[0]
        else:
            # 3. Not in DB at all — insert as a new FC
            cur = conn.execute(
                "INSERT INTO feature_classes(canonical_name, badge) VALUES(?, 'Removed')",
                (name,),
            )
            fc_id = cur.lastrowid
            new_fcs.append(name)

    conn.execute(
        "INSERT INTO fc_membership(fc_id, scale, display_name) VALUES(?, '10k', ?)",
        (fc_id, name),
    )
    added += 1

conn.commit()
conn.close()

print(f"10k membership updated: {added} entries.")
if alias_hits:
    print(f"Alias mappings resolved ({len(alias_hits)}):")
    for h in alias_hits:
        print(f"  {h}")
if new_fcs:
    print(f"New FCs inserted ({len(new_fcs)}): {', '.join(new_fcs)}")
