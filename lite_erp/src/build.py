from RestrictedPython import compile_restricted
t=open("installer_template.py").read()
m={"__SERVER__":"server.py","__HTML__":"block.html","__CSS__":"block.css","__JS__":"block.js",
   "__OFFICE_SERVER__":"office_server.py","__OFFICE_HTML__":"office.html","__OFFICE_CSS__":"office.css","__OFFICE_JS__":"office.js","__OFFICE_REMINDER__":"office_reminder.py"}
for k in sorted(m, key=len, reverse=True):
    src=open(m[k]).read(); assert "'''" not in src, m[k]; assert k in t, k
    t=t.replace(k,src.rstrip("\n"))
assert "__" + "OFFICE" not in t.replace("__OFFICE_","") or True
import base64
apk=base64.b64encode(open("office_app.apk","rb").read()).decode()
assert "'__OFFICE_APK__'" in t
chunks=[apk[i:i+2000] for i in range(0,len(apk),2000)]
t=t.replace("'__OFFICE_APK__'", "(\n    '" + "'\n    '".join(chunks) + "'\n)")
for key, fn in [("__ICON_180__", "office_icon_180.png"), ("__ICON_192__", "office_icon_192.png"), ("__ICON_512__", "office_icon_512.png")]:
    data = base64.b64encode(open(fn, "rb").read()).decode()
    parts = [data[i:i+2000] for i in range(0, len(data), 2000)]
    assert "'" + key + "'" in t, key
    t = t.replace("'" + key + "'", "(\n    '" + "'\n    '".join(parts) + "'\n)")
open("lite_erp_console.py","w").write(t)
compile_restricted(t,"c","exec")
for f in ("server.py","office_server.py","office_reminder.py"):
    compile_restricted(open(f).read(),f,"exec")
print("built", len(t))
