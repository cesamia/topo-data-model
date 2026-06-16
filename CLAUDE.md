# Schema Harmonization — Claude Instructions

## Pipeline overview

```
temp/SchemaChangeLog.xlsx
        ↓ apply_changelog.py
db/schemas.db
        ↓ build.py
docs/          ← deployed to GitHub Pages
```

Always run scripts from the repo root: `python apply_changelog.py` then `python build.py`.

---

## Change checklists

### FC badge change (Retained / Modified / Added / Removed / clear)
1. `apply_changelog.py` — add FC to `BADGE_CORRECTIONS` (use `""` to clear) or `REMOVED_FROM_HDM`
2. Run `python apply_changelog.py`
3. Run `python build.py`
4. Commit: `apply_changelog.py` + `db/schemas.db` + `docs/`

### New changelog entries from Excel
1. Run `python apply_changelog.py` (re-imports all entries from `temp/SchemaChangeLog.xlsx`)
2. Check if any new entries imply badge changes — update `BADGE_CORRECTIONS` / `REMOVED_FROM_HDM` if so
3. Run `python build.py`
4. Commit: `apply_changelog.py` + `db/schemas.db` + `docs/`

### 10k/50k membership fix (wrong mapping target)
1. `apply_changelog.py` — add or update entry in `CORRECTIONS_10K`
2. Run `python apply_changelog.py`
3. Run `python build.py`
4. Commit: `apply_changelog.py` + `db/schemas.db` + `docs/`

### New HDM FC
1. `apply_changelog.py` — add to `NEW_HDM_FCS`
2. Run `python apply_changelog.py`
3. Run `python build.py`
4. Commit: `apply_changelog.py` + `db/schemas.db` + `docs/`

### Label / wording change (e.g. badge text, header text)
1. `build.py` — update `badge_label` filter if it's a badge label
2. `templates/base.html` — update `BADGE_LABELS` JS object and/or legend HTML
3. Run `python build.py`
4. Commit: `build.py` + `templates/base.html` + `docs/`

### Template / layout change
1. Edit relevant file in `templates/`
2. Run `python build.py`
3. Commit: `templates/` + `docs/`

### CSS change
1. Edit `static/style.css`
2. Run `python build.py` (copies CSS to `docs/static/style.css`)
3. Commit: `static/style.css` + `docs/static/style.css`

### Nav data change (sidebar structure / JS logic)
1. Edit `templates/base.html` (JS) and/or `build.py` (`write_nav_data`)
2. Run `python build.py`
3. Commit: `templates/base.html` + `build.py` + `docs/`

---

## Key files

| File | Purpose |
|------|---------|
| `apply_changelog.py` | Authoritative script — imports changelog, sets badges, fixes memberships |
| `build.py` | Generates all HTML from `db/schemas.db` into `docs/` |
| `templates/base.html` | Shared layout + sidebar JS (includes `BADGE_LABELS`) |
| `templates/fc_detail.html` | FC detail page template |
| `templates/index.html` | Landing page template |
| `static/style.css` | Source CSS (copied to `docs/static/` on build) |
| `docs/static/nav-data.js` | Generated sidebar data — do not edit manually |
| `db/schemas.db` | SQLite database — source of truth for all FC data |

## Badge values

| Value | Label | Meaning |
|-------|-------|---------|
| `Retained` | RET | FC carried over from source unchanged |
| `Modified` | MOD | FC exists in source, changed in HDM |
| `Added` | ADD | New FC in HDM, not in source |
| `Removed` | DEL | FC was in HDM, now removed |
| `""` (empty) | *(none)* | Status not yet confirmed |
| `Mapped` | MTCH | 10k/50k FC matched to an HDM FC |
| `Deleted` | DEL | 10k/50k FC has no HDM equivalent |

## After any change — always end with
```
git add .
git commit -m "..."
git push
```
