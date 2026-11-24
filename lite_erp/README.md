# SBI Lite ERP + SBI Office

ERPNext v16 customisation for Shiv Bharat Infrastructures (erp.shiv-bharat.com).

## Folders
- `src/` – source: Lite ERP API (`server.py`), page (`block.html/.css/.js`), SBI Office punch app (`office_*`), installer template and `build.py`.
- `dist/` – ready to run: `lite_erp_console.py` (full installer), `run_big_installer.py` (System Console loader), small update scripts, the Android APK and sample sheets.
- `assets/` – app icons.

## Install / update on the site (automatic)
The deploy installs it. `sbi_projects/setup/lite_erp_setup.py` runs after every migrate:
- runs `dist/lite_erp_console.py` whenever that file has changed (the last run's log is in the global default `sbi_lite_erp_installer_log`),
- puts back the Lite ERP workspace and the Lite ERP / SBI Office desktop icons that the migrate clean-up removes.

So to update: replace `dist/lite_erp_console.py`, commit, `git push origin main`, then on Frappe Cloud: Update Now, then In-Place Migrate.

Manual way (only if needed): upload `dist/lite_erp_console.py` at /app/file, then run `dist/run_big_installer.py` in System Console.

## Rebuild the installer after editing `src/`
`build.py` expects the source files and icons in one folder:
copy `assets/*.png` and `dist/SBI-Office-v1.0.apk` (as `office_app.apk`) next to `src/*`, then run `python build.py`.

## Not in this repo
The APK signing key (`sbi-office.keystore`) is kept out of git on purpose. Keep it safe; it is needed to publish app updates.
