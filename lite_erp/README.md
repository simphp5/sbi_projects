# SBI Lite ERP + SBI Office

ERPNext v16 customisation for Shiv Bharat Infrastructures (erp.shiv-bharat.com).

## Folders
- `src/` – source: Lite ERP API (`server.py`), page (`block.html/.css/.js`), SBI Office punch app (`office_*`), installer template and `build.py`.
- `dist/` – ready to run: `lite_erp_console.py` (full installer), `run_big_installer.py` (System Console loader), small update scripts, the Android APK and sample sheets.
- `assets/` – app icons.

## Install / update on the site
1. Open `/app/file` and upload `dist/lite_erp_console.py` (or the same file renamed `.txt`).
2. Paste `dist/run_big_installer.py` into System Console and Execute.
3. Reload the browser (Ctrl+Shift+R).

## Rebuild the installer after editing `src/`
`build.py` expects the source files and icons in one folder:
copy `assets/*.png` and `dist/SBI-Office-v1.0.apk` (as `office_app.apk`) next to `src/*`, then run `python build.py`.

## Not in this repo
The APK signing key (`sbi-office.keystore`) is kept out of git on purpose. Keep it safe; it is needed to publish app updates.
