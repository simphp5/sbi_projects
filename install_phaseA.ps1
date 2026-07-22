# install_phaseA.ps1 -- Phase A: app polish (icons, sign out), Aadhaar flow,
#   geo-fence boundary set on the project form, out-of-boundary report.
# Run from inside C:\Users\simph\Downloads\sbi_projects_live

$ErrorActionPreference = "Stop"
$app = "sbi_projects"
$projJs = Join-Path $app "public\js\project.js"
if (-not (Test-Path (Join-Path $app "sbi_projects"))) { Write-Error "Not in sbi_projects_live?"; exit 1 }
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

$c_site_app_html = @'
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#111111">
<link rel="manifest" href="/sbi_site_manifest.json">
<link rel="apple-touch-icon" href="/assets/sbi_projects/site_app/apple-touch-icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
<meta name="apple-mobile-web-app-title" content="SBI Site">
<meta name="mobile-web-app-capable" content="yes">
<title>SBI Site</title>
<style>
:root{
  --ink:#111;--ink-soft:#5a5a5a;--paper:#f2f0ec;--card:#fff;--rule:#d6d2cb;
  --brand:#be1e2d;--brand-dark:#8f1622;--go:#0f6b3f;--wait:#a86a00;--stop:#7a1010;--tap:72px;
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;height:100%}
body{background:var(--paper);color:var(--ink);
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;font-size:17px;line-height:1.35;
  padding-bottom:env(safe-area-inset-bottom)}
h1,h2,h3{margin:0;font-weight:800;letter-spacing:-.02em}
.num{font-variant-numeric:tabular-nums}
.hidden{display:none !important}
.muted{color:var(--ink-soft);font-size:14px}

.top{position:sticky;top:0;z-index:20;background:var(--ink);color:#fff;
  padding:10px 14px;display:flex;align-items:center;gap:12px}
.top .mark{width:10px;height:26px;background:var(--brand);flex:0 0 auto}
.top .site{font-weight:800;font-size:15px;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.top button{background:transparent;border:1px solid #444;color:#fff;padding:8px 12px;
  font-size:14px;font-weight:700;border-radius:2px}
.wrap{max-width:760px;margin:0 auto;padding:14px}

/* login */
.login-shell{min-height:100dvh;display:flex;flex-direction:column;justify-content:center;
  align-items:center;padding:24px;background:var(--ink)}
.login-card{width:100%;max-width:380px;background:var(--card);border-radius:4px;padding:26px 22px}
.login-logo{display:flex;justify-content:center;margin-bottom:8px}
.login-logo img{height:64px}
.login-card h1{text-align:center;font-size:22px;margin-bottom:2px}
.login-card p{text-align:center;color:var(--ink-soft);font-size:14px;margin:0 0 18px}
label{display:block;font-size:12px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
  color:var(--ink-soft);margin:14px 0 5px}
input,select{width:100%;min-height:54px;padding:12px;font-size:17px;font-family:inherit;
  border:2px solid var(--rule);background:var(--card);color:var(--ink);border-radius:0}
input:focus,select:focus,button:focus-visible{outline:3px solid var(--brand);outline-offset:1px}
.primary{width:100%;min-height:var(--tap);margin-top:18px;background:var(--brand);
  border:2px solid var(--brand);color:#fff;font-size:19px;font-weight:800;letter-spacing:.02em}
.primary:active{background:var(--brand-dark)}
.primary:disabled{opacity:.4}

/* home menu */
.home-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:16px}
.tile{min-height:120px;border:2px solid var(--ink);background:var(--card);
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;
  font-size:16px;font-weight:800;color:var(--ink);padding:14px;text-align:center}
.tile:active{transform:translateY(1px)}
.tile .ic{font-size:30px;line-height:1}
.tile[data-accent="brand"]{border-color:var(--brand);color:var(--brand)}
.home-summary{display:flex;gap:14px;margin-top:14px;padding:12px 14px;border:1px solid var(--rule);
  background:var(--card);font-size:14px}
.home-summary b{font-size:20px;display:block;font-variant-numeric:tabular-nums}

/* tabs */
.tabs{display:flex;border-bottom:2px solid var(--ink);margin-bottom:14px}
.tabs button{flex:1;background:transparent;border:0;border-bottom:4px solid transparent;
  padding:14px 6px;font-size:15px;font-weight:800;color:var(--ink-soft);margin-bottom:-2px}
.tabs button[aria-selected="true"]{color:var(--ink);border-bottom-color:var(--brand)}

/* camera */
.stage{position:relative;background:#000;border:2px solid var(--ink);aspect-ratio:4/3;overflow:hidden}
.stage video,.stage img.frozen{width:100%;height:100%;object-fit:cover}
.stage video.mirror{transform:scaleX(-1)}
.stage canvas{display:none}
.reticle{position:absolute;inset:14% 22%;border:3px solid rgba(255,255,255,.55);
  border-radius:50%/42%;pointer-events:none;transition:border-color .18s}
.stage[data-face="yes"] .reticle{border-color:#39d98a}
.cam-tools{position:absolute;top:8px;right:8px;display:flex;gap:6px}
.cam-tools button{background:rgba(0,0,0,.6);color:#fff;border:0;padding:8px 10px;
  font-size:13px;font-weight:700;border-radius:2px}
.badge{position:absolute;left:0;bottom:0;right:0;padding:10px 12px;background:rgba(0,0,0,.72);
  color:#fff;font-weight:700;font-size:15px;display:flex;justify-content:space-between;gap:10px}
.badge .who{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.badge .score{opacity:.75;font-size:13px}

/* day track */
.track{margin:16px 0 6px;border:2px solid var(--ink);background:var(--card)}
.track h3{font-size:12px;letter-spacing:.14em;text-transform:uppercase;padding:9px 12px;
  border-bottom:1px solid var(--rule);color:var(--ink-soft)}
.track ol{list-style:none;margin:0;padding:0;display:flex}
.track li{flex:1;padding:11px 6px;text-align:center;border-right:1px solid var(--rule);
  font-size:11px;font-weight:800;letter-spacing:.06em;color:#b3aea6}
.track li:last-child{border-right:0}
.track li b{display:block;font-size:15px;letter-spacing:0;margin-top:3px;font-variant-numeric:tabular-nums}
.track li[data-done="1"]{color:var(--ink);background:#eceae5}
.track li[data-now="1"]{background:var(--ink);color:#fff}

/* punches */
.punches{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px}
.punch{min-height:var(--tap);border:2px solid var(--ink);background:var(--card);
  font-size:19px;font-weight:800;letter-spacing:.02em;color:var(--ink);
  display:flex;align-items:center;justify-content:center;gap:10px;padding:12px}
.punch:active{transform:translateY(1px)}
.punch[data-kind="in"]{background:var(--go);border-color:var(--go);color:#fff}
.punch[data-kind="out"]{background:var(--stop);border-color:var(--stop);color:#fff}
.punch[data-kind="break"]{background:var(--card);color:var(--wait);border-color:var(--wait)}
.punch:disabled{opacity:.32}
.punch.wide{grid-column:1/-1}

/* notes / status */
.note{padding:12px;border-left:5px solid var(--ink);background:var(--card);margin-top:14px;font-size:15px}
.note[data-tone="ok"]{border-left-color:var(--go)}
.note[data-tone="warn"]{border-left-color:var(--wait)}
.note[data-tone="err"]{border-left-color:var(--brand)}
.queue{position:fixed;left:0;right:0;bottom:0;background:var(--wait);color:#fff;
  padding:9px 14px;font-weight:700;font-size:14px;text-align:center}

/* rows / entry */
.entry-row{display:flex;gap:8px;align-items:flex-end;margin-top:10px}
.entry-row > div{flex:1}
.entry-row .rm{flex:0 0 auto;min-height:54px;width:54px;border:2px solid var(--rule);
  background:var(--card);font-size:22px;color:var(--brand)}
.addbtn{margin-top:10px;width:100%;min-height:54px;border:2px dashed var(--rule);
  background:transparent;font-size:15px;font-weight:700;color:var(--ink-soft)}
.pill{font-size:11px;font-weight:800;letter-spacing:.08em;padding:5px 8px;border:1px solid}
.pill.on{color:var(--go);border-color:var(--go)}
.pill.off{color:var(--ink-soft);border-color:var(--rule)}
.pill.new{color:var(--brand);border-color:var(--brand)}
.roster{margin-top:6px;border:2px solid var(--ink);background:var(--card)}
.person{display:flex;align-items:center;gap:12px;padding:11px 12px;border-bottom:1px solid var(--rule)}
.person:last-child{border-bottom:0}
.avatar{width:44px;height:44px;flex:0 0 auto;background:#ddd8d0;border:1px solid var(--rule);object-fit:cover}
.person .nm{flex:1;font-weight:700;min-width:0;overflow:hidden;text-overflow:ellipsis}
.person .nm small{display:block;font-weight:500;color:var(--ink-soft);font-size:13px}
.chk{display:flex;align-items:center;gap:10px;margin-top:14px;font-size:16px;font-weight:700}
.chk input{width:26px;height:26px;min-height:0}
@media (prefers-reduced-motion:reduce){*{transition:none !important}}
</style>
</head>
<body>

<!-- ============ LOGIN ============ -->
<section id="loginScreen" class="login-shell">
  <div class="login-card">
    <div class="login-logo"><img src="/assets/sbi_projects/site_app/sbi-logo-full.png" alt="Shiv Bharat Infrastructures"></div>
    <h1>Site sign in</h1>
    <p>Enter the login your office gave you.</p>
    <label for="lgUser">Username</label>
    <input id="lgUser" type="text" autocomplete="username" autocapitalize="off" placeholder="name@shiv-bharat.com">
    <label for="lgPass">Password</label>
    <input id="lgPass" type="password" autocomplete="current-password" placeholder="Password">
    <button class="primary" id="btnLogin" type="button">Sign in</button>
    <div class="note hidden" id="loginNote" data-tone="err"></div>
  </div>
</section>

<!-- ============ APP SHELL ============ -->
<div id="appShell" class="hidden">
  <div class="top">
    <span class="mark"></span>
    <span class="site" id="siteLabel">Choose a site</span>
    <button id="btnHome" type="button" class="hidden">Menu</button>
    <button id="btnLogout" type="button">Sign out</button>
  </div>

  <div class="wrap">

    <!-- site chooser -->
    <section id="pickSite">
      <h1 style="font-size:24px;margin-bottom:4px">Choose your site</h1>
      <p class="muted">Pick the site you are working at today.</p>
      <label for="siteSelect">Site</label>
      <select id="siteSelect"></select>
      <button class="primary" id="btnStart" type="button">Continue</button>
    </section>

    <!-- HOME MENU -->
    <section id="homeScreen" class="hidden">
      <div class="home-summary">
        <div><b id="hsPresent" class="num">0</b><span class="muted">On site now</span></div>
        <div><b id="hsHead" class="num">0</b><span class="muted">Enrolled</span></div>
        <div style="margin-left:auto;text-align:right"><b id="hsDate" style="font-size:15px">—</b><span class="muted">Today</span></div>
      </div>
      <div class="home-grid">
        <button class="tile" data-go="attend"><span class="ic"><svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3" fill="currentColor"/></svg></span>Attendance</button>
        <button class="tile" data-go="daily"><span class="ic"><svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 20h16M6 16l9-9 3 3-9 9H6v-3z"/></svg></span>Daily entry</button>
        <button class="tile" data-accent="brand" data-go="enroll"><span class="ic"><svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="8" r="4"/><path d="M3 20c0-3 3-5 6-5s6 2 6 5M18 8v6M21 11h-6"/></svg></span>Add worker</button>
        <button class="tile" data-go="today"><span class="ic"><svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7h16M4 12h16M4 17h16"/></svg></span>Who's in</button>
      </div>
    </section>

    <!-- ATTENDANCE -->
    <section id="attendScreen" class="hidden">
      <div class="stage" id="stage" data-face="no">
        <video id="video" playsinline muted autoplay class="mirror"></video>
        <div class="reticle"></div>
        <div class="cam-tools"><button id="btnFlip" type="button">Flip</button></div>
        <div class="badge"><span class="who" id="who">Looking for a face</span><span class="score" id="score"></span></div>
      </div>
      <canvas id="canvas"></canvas>
      <div class="track" id="track">
        <h3>Today</h3>
        <ol>
          <li data-step="IN">In<b>--:--</b></li>
          <li data-step="TEA">Tea<b>--:--</b></li>
          <li data-step="LUNCH">Lunch<b>--:--</b></li>
          <li data-step="OUT">Out<b>--:--</b></li>
        </ol>
      </div>
      <div class="punches" id="punches"></div>
      <div class="note" id="punchNote" data-tone="">Hold the phone steady and look at the camera.</div>
    </section>

    <!-- ENROLL + AADHAAR -->
    <section id="enrollScreen" class="hidden">
      <div class="stage" id="stage2" data-face="no">
        <video id="video2" playsinline muted autoplay class="mirror"></video>
        <img id="frozen2" class="frozen hidden" alt="">
        <div class="reticle"></div>
        <div class="cam-tools">
          <button id="btnFlip2" type="button">Flip</button>
          <button id="btnFreeze2" type="button">Freeze</button>
        </div>
        <div class="badge"><span class="who" id="who2">Face the camera</span></div>
      </div>
      <label for="enName">Worker name</label>
      <input id="enName" type="text" autocomplete="off" placeholder="Full name">
      <label for="enGender">Gender</label>
      <select id="enGender"></select>
      <label for="enSkill">Skill</label>
      <select id="enSkill"><option value="">Not set</option></select>
      <label for="enWage">Wage type</label>
      <select id="enWage"><option value="">Not set</option></select>
      <label for="enRate">Wage rate</label>
      <input id="enRate" type="number" inputmode="decimal" placeholder="0">
      <label for="enPhone">Phone</label>
      <input id="enPhone" type="tel" inputmode="tel" placeholder="Optional">
      <button class="primary" id="btnEnroll" type="button">Add worker</button>
      <div class="note" id="enrollNote" data-tone="">Freeze a clear face photo, then fill in the name.</div>

      <!-- Aadhaar capture, appears after a worker is added -->
      <section id="aadhaarBlock" class="hidden" style="margin-top:20px;border-top:2px solid var(--ink);padding-top:16px">
        <h2 style="font-size:18px;margin-bottom:4px">Aadhaar for <span id="aaName">worker</span></h2>
        <p class="muted">For salary and records. Capture the front and back of the card.</p>
        <div class="entry-row">
          <div>
            <label>Front</label>
            <div class="stage" style="aspect-ratio:16/10">
              <video id="aaVideo" playsinline muted autoplay></video>
              <img id="aaFrozen" class="frozen hidden" alt="">
              <div class="cam-tools"><button id="aaFreeze" type="button">Capture</button></div>
            </div>
          </div>
        </div>
        <div id="aaBackWrap" class="hidden">
          <label style="margin-top:14px">Back</label>
          <div class="stage" style="aspect-ratio:16/10">
            <video id="aaVideoB" playsinline muted autoplay></video>
            <img id="aaFrozenB" class="frozen hidden" alt="">
            <div class="cam-tools"><button id="aaFreezeB" type="button">Capture</button></div>
          </div>
        </div>
        <label for="aaNumber" style="margin-top:14px">Aadhaar number</label>
        <input id="aaNumber" type="text" inputmode="numeric" maxlength="14" placeholder="Reads from the photo, correct if needed">
        <div class="muted" id="aaOcrNote" style="margin-top:4px"></div>
        <button class="primary" id="btnSaveAadhaar" type="button">Save Aadhaar</button>
        <div class="note" id="aadhaarNote" data-tone="">Capture the front; the number is read for you to check.</div>
      </section>
    </section>

    <!-- DAILY ENTRY -->
    <section id="dailyScreen" class="hidden">
      <label for="dlStage">Stage</label>
      <select id="dlStage"></select>

      <label class="chk" style="margin-top:16px">
        <input type="checkbox" id="dlHoliday"> No work today (holiday / rain)
      </label>

      <div id="dlWorkBlock">
        <h3 style="margin-top:18px;font-size:15px">Work done</h3>
        <div id="progressRows"></div>
        <button class="addbtn" id="btnAddProgress" type="button">+ Add work item</button>

        <h3 style="margin-top:20px;font-size:15px">Petty cash spent</h3>
        <div id="cashRows"></div>
        <button class="addbtn" id="btnAddCash" type="button">+ Add petty cash</button>
      </div>

      <label for="dlRemarks" style="margin-top:18px">Remarks</label>
      <input id="dlRemarks" type="text" placeholder="Anything to note (optional)">

      <button class="primary" id="btnSaveDaily" type="button">Save today's entry</button>
      <div class="note" id="dailyNote" data-tone="">Pick the stage, then record work and any petty cash.</div>
    </section>

    <!-- TODAY / ROSTER -->
    <section id="todayScreen" class="hidden">
      <div class="roster" id="roster"></div>
      <button class="primary" id="btnRefresh" type="button">Refresh</button>
    </section>

  </div>
  <div class="queue hidden" id="queueBar"></div>
</div>
<script src="https://cdn.jsdelivr.net/npm/@vladmandic/face-api/dist/face-api.js"></script>
<script src="https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js"></script>
<script>
(function () {
  "use strict";
  var MODELS = "https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model";
  var CSRF = "{{ csrf_token }}";
  var PROJECTS = {{ projects_json | safe }};
  var QKEY = "sbi_punch_queue";

  var S = {
    project:null, ready:false, busy:false, gps:null,
    descriptor:null, labour:null, labourName:null, allowed:[],
    enrollDescriptor:null, newLabour:null,
    facing:"user", facing2:"user",
    aaFront:null, aaBack:null, aaStep:"front"
  };
  var $ = function(id){return document.getElementById(id);};

  // -------- server call --------
  function call(method, args){
    return fetch("/api/method/sbi_projects.sbi_projects."+method,{
      method:"POST",
      headers:{"Content-Type":"application/json","X-Frappe-CSRF-Token":CSRF},
      body:JSON.stringify(args||{})
    }).then(function(r){
      return r.json().then(function(j){
        if(!r.ok){
          var m=(j&&(j._server_messages||j.exception||j.message))||("HTTP "+r.status);
          try{m=JSON.parse(m)[0];m=JSON.parse(m).message||m;}catch(e){}
          throw new Error(String(m));
        }
        return j.message;
      });
    });
  }
  function note(el,tone,text){el.classList.remove("hidden");el.setAttribute("data-tone",tone);el.textContent=text;}

  // -------- login --------
  function doLogin(){
    var u=$("lgUser").value.trim(), p=$("lgPass").value;
    if(!u||!p){note($("loginNote"),"err","Enter your username and password.");return;}
    $("btnLogin").disabled=true;
    fetch("/api/method/login",{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({usr:u,pwd:p})
    }).then(function(r){
      if(r.ok){location.reload();}       // session set; reload to get server context + projects
      else{throw new Error("Wrong username or password.");}
    }).catch(function(e){
      note($("loginNote"),"err",e.message);
      $("btnLogin").disabled=false;
    });
  }
  function doLogout(){
    fetch("/api/method/logout", {
      method: "GET",
      headers: { "X-Frappe-CSRF-Token": CSRF }
    }).then(function(){
      // clear any local site memory so next user starts fresh
      localStorage.removeItem("sbi_site");
      location.href = "/site_app";
    }).catch(function(){ location.href = "/site_app"; });
  }

  // -------- gps --------
  function watchGps(){
    if(!navigator.geolocation)return;
    navigator.geolocation.watchPosition(
      function(p){S.gps={lat:p.coords.latitude,lng:p.coords.longitude};},
      function(){S.gps=null;},
      {enableHighAccuracy:true,maximumAge:15000,timeout:12000});
  }

  // -------- camera --------
  var streams={};
  function startCamera(videoEl,facing,key){
    stopCamera(key);
    return navigator.mediaDevices.getUserMedia({
      video:{facingMode:facing,width:{ideal:640},height:{ideal:480}},audio:false
    }).then(function(stream){
      streams[key]=stream;videoEl.srcObject=stream;return videoEl.play();
    });
  }
  function stopCamera(key){
    if(streams[key]){streams[key].getTracks().forEach(function(t){t.stop();});delete streams[key];}
  }
  function loadModels(){
    return Promise.all([
      faceapi.nets.tinyFaceDetector.loadFromUri(MODELS),
      faceapi.nets.faceLandmark68TinyNet.loadFromUri(MODELS),
      faceapi.nets.faceRecognitionNet.loadFromUri(MODELS)
    ]).then(function(){S.ready=true;});
  }
  function detect(videoEl){
    var opts=new faceapi.TinyFaceDetectorOptions({inputSize:320,scoreThreshold:0.5});
    return faceapi.detectSingleFace(videoEl,opts).withFaceLandmarks(true).withFaceDescriptor();
  }
  function snapshot(videoEl){
    var c=$("canvas");
    c.width=480;c.height=Math.round(480*(videoEl.videoHeight||480)/(videoEl.videoWidth||640));
    c.getContext("2d").drawImage(videoEl,0,0,c.width,c.height);
    return c.toDataURL("image/jpeg",0.75);
  }

  // -------- attendance loop --------
  var lastLookup=0;
  function punchLoop(){
    if(!S.ready||S.busy||$("attendScreen").classList.contains("hidden")){return setTimeout(punchLoop,700);}
    detect($("video")).then(function(res){
      var stage=$("stage");
      if(!res){stage.setAttribute("data-face","no");$("who").textContent="Looking for a face";
        $("score").textContent="";S.descriptor=null;S.labour=null;renderPunches([]);return;}
      stage.setAttribute("data-face","yes");
      S.descriptor=Array.prototype.slice.call(res.descriptor);
      var now=Date.now();if(now-lastLookup<1800)return;lastLookup=now;
      call("site_api.match_face",{embedding:S.descriptor,project:S.project}).then(function(m){
        if(!m){$("who").textContent="Not enrolled";$("score").textContent="";S.labour=null;
          renderPunches([]);note($("punchNote"),"warn","This face is not enrolled. Use Add worker.");return;}
        S.labour=m.labour;S.labourName=m.labour_name;
        $("who").textContent=m.labour_name;$("score").textContent="match "+Math.round(m.score*100)+"%";
        return refreshDay(m.labour);
      }).catch(function(e){note($("punchNote"),"err",e.message);});
    }).catch(function(){}).then(function(){setTimeout(punchLoop,700);});
  }
  function refreshDay(labour){
    return call("doctype.labour_attendance_log.labour_attendance_log.get_day_status",{labour:labour})
      .then(function(s){S.allowed=s.allowed_next||[];paintTrack(s.punches||[]);renderPunches(S.allowed);
        if(!S.allowed.length){note($("punchNote"),"ok",S.labourName+" has finished for today.");}
        else{note($("punchNote"),"","Tap a button to record the punch.");}});
  }
  function paintTrack(punches){
    var map={"IN":"IN","TEA OUT":"TEA","TEA IN":"TEA","LUNCH OUT":"LUNCH","LUNCH IN":"LUNCH","OUT":"OUT"};
    var seen={};punches.forEach(function(p){var st=map[p.log_type];if(st)seen[st]=String(p.log_datetime).slice(11,16);});
    var last=punches.length?map[punches[punches.length-1].log_type]:null;
    Array.prototype.forEach.call($("track").querySelectorAll("li"),function(li){
      var k=li.getAttribute("data-step");li.setAttribute("data-done",seen[k]?"1":"0");
      li.setAttribute("data-now",k===last?"1":"0");li.querySelector("b").textContent=seen[k]||"--:--";});
  }
  var KIND={"IN":"in","OUT":"out","LUNCH OUT":"break","LUNCH IN":"break","TEA OUT":"break","TEA IN":"break"};
  function renderPunches(allowed){
    var box=$("punches");box.innerHTML="";if(!allowed.length)return;
    allowed.forEach(function(t,i){var b=document.createElement("button");b.type="button";
      b.className="punch"+(allowed.length%2===1&&i===0?" wide":"");
      b.setAttribute("data-kind",KIND[t]||"break");b.textContent=t;
      b.onclick=function(){doPunch(t);};box.appendChild(b);});
  }
  function doPunch(logType){
    if(!S.labour||S.busy)return;S.busy=true;note($("punchNote"),"","Recording "+logType+"...");
    var payload={project:S.project,log_type:logType,embedding:S.descriptor,
      latitude:S.gps?S.gps.lat:null,longitude:S.gps?S.gps.lng:null,
      photo:snapshot($("video")),device_id:deviceId()};
    call("site_api.punch",payload).then(function(r){
      if(!r||!r.matched){note($("punchNote"),"warn",(r&&r.message)||"No match.");return;}
      var extra=r.within_geofence?"":"  Outside the site by "+Math.round(r.distance_from_site)+" m.";
      note($("punchNote"),r.within_geofence?"ok":"warn",
        r.labour_name+" - "+r.log_type+" at "+String(r.time).slice(11,16)+"."+extra);
      return refreshDay(r.labour);
    }).catch(function(e){
      if(!navigator.onLine){queuePush(payload);note($("punchNote"),"warn","No network. Saved on this device.");}
      else{note($("punchNote"),"err",e.message);}
    }).then(function(){S.busy=false;});
  }
  function deviceId(){var k="sbi_device_id";var v=localStorage.getItem(k);
    if(!v){v="dev-"+Math.random().toString(36).slice(2,10);localStorage.setItem(k,v);}return v;}

  // -------- offline queue --------
  function queueRead(){try{return JSON.parse(localStorage.getItem(QKEY)||"[]");}catch(e){return[];}}
  function queuePush(item){var q=queueRead();q.push(item);localStorage.setItem(QKEY,JSON.stringify(q));paintQueue();}
  function paintQueue(){var n=queueRead().length;var bar=$("queueBar");
    bar.classList.toggle("hidden",n===0);bar.textContent=n+" punch"+(n===1?"":"es")+" waiting to send";}
  function queueFlush(){var q=queueRead();if(!q.length||!navigator.onLine)return;
    call("site_api.punch",q[0]).then(function(){var r=queueRead();r.shift();
      localStorage.setItem(QKEY,JSON.stringify(r));paintQueue();queueFlush();}).catch(function(){});}

  // -------- enroll --------
  var enFrozen=false;
  function enrollLoop(){
    if(!S.ready||$("enrollScreen").classList.contains("hidden")||enFrozen){return setTimeout(enrollLoop,800);}
    detect($("video2")).then(function(res){
      var ok=!!res;$("stage2").setAttribute("data-face",ok?"yes":"no");
      $("who2").textContent=ok?"Face detected - tap Freeze":"Face the camera";
    }).catch(function(){}).then(function(){setTimeout(enrollLoop,800);});
  }
  function freezeEnroll(){
    detect($("video2")).then(function(res){
      if(!res){note($("enrollNote"),"warn","No face detected. Try again.");return;}
      S.enrollDescriptor=Array.prototype.slice.call(res.descriptor);
      var img=snapshot($("video2"));
      $("frozen2").src=img;$("frozen2").classList.remove("hidden");$("video2").classList.add("hidden");
      enFrozen=true;$("btnFreeze2").textContent="Retake";$("who2").textContent="Photo captured";
      note($("enrollNote"),"ok","Face captured. Now fill in the name and add the worker.");
    });
  }
  function unfreezeEnroll(){
    enFrozen=false;S.enrollDescriptor=null;
    $("frozen2").classList.add("hidden");$("video2").classList.remove("hidden");
    $("btnFreeze2").textContent="Freeze";
  }
  function doEnroll(){
    var name=$("enName").value.trim();
    if(!name){note($("enrollNote"),"warn","Enter the worker's name.");return;}
    if(!S.enrollDescriptor){note($("enrollNote"),"warn","Freeze a face photo first.");return;}
    $("btnEnroll").disabled=true;note($("enrollNote"),"","Adding "+name+"...");
    call("site_api.enroll_labour",{
      labour_name:name,gender:$("enGender").value,skill_category:$("enSkill").value||null,
      phone:$("enPhone").value.trim()||null,wage_type:$("enWage").value||null,
      wage_rate:$("enRate").value||0,project:S.project,
      embedding:S.enrollDescriptor,photo:$("frozen2").src
    }).then(function(r){
      if(r&&r.duplicate){note($("enrollNote"),"warn","Already enrolled as "+r.labour_name+". Use Attendance.");return;}
      S.newLabour=r.labour;$("aaName").textContent=r.labour_name;
      note($("enrollNote"),"ok",r.labour_name+" added. Now capture the Aadhaar below.");
      $("aadhaarBlock").classList.remove("hidden");
      startAadhaarCam();
      $("aadhaarBlock").scrollIntoView({behavior:"smooth"});
    }).catch(function(e){note($("enrollNote"),"err",e.message);})
    .then(function(){$("btnEnroll").disabled=false;});
  }

  // -------- aadhaar capture + OCR --------
  function startAadhaarCam(){
    startCamera($("aaVideo"),"environment","aaF").catch(function(){});
    startCamera($("aaVideoB"),"environment","aaB").catch(function(){});
  }
  function captureAadhaar(which){
    var vid=which==="front"?$("aaVideo"):$("aaVideoB");
    var img=which==="front"?$("aaFrozen"):$("aaFrozenB");
    var c=$("canvas");
    c.width=800;c.height=Math.round(800*(vid.videoHeight||500)/(vid.videoWidth||800));
    c.getContext("2d").drawImage(vid,0,0,c.width,c.height);
    var data=c.toDataURL("image/jpeg",0.8);
    img.src=data;img.classList.remove("hidden");vid.classList.add("hidden");
    if(which==="front"){
      S.aaFront=data;$("aaBackWrap").classList.remove("hidden");
      runOcr(data);
    }else{S.aaBack=data;}
  }
  function runOcr(dataUrl){
    if(typeof Tesseract==="undefined"){$("aaOcrNote").textContent="Type the number from the card.";return;}
    $("aaOcrNote").textContent="Reading the number from the photo...";
    Tesseract.recognize(dataUrl,"eng").then(function(res){
      var text=(res.data&&res.data.text)||"";
      var digits=text.replace(/[^0-9]/g,"");
      var m=digits.match(/\d{12}/);
      if(m){$("aaNumber").value=m[0].replace(/(\d{4})(\d{4})(\d{4})/,"$1 $2 $3");
        $("aaOcrNote").textContent="Read from the photo - please check it is correct.";}
      else{$("aaOcrNote").textContent="Could not read the number. Please type it.";}
    }).catch(function(){$("aaOcrNote").textContent="Could not read the number. Please type it.";});
  }
  function saveAadhaar(){
    if(!S.newLabour){note($("aadhaarNote"),"warn","Add the worker first.");return;}
    var num=$("aaNumber").value.replace(/[^0-9]/g,"");
    if(num&&num.length!==12){note($("aadhaarNote"),"warn","An Aadhaar number is 12 digits.");return;}
    $("btnSaveAadhaar").disabled=true;note($("aadhaarNote"),"","Saving Aadhaar...");
    call("site_api.save_aadhaar",{labour:S.newLabour,aadhaar_number:num||null,
      front_image:S.aaFront,back_image:S.aaBack}).then(function(r){
      note($("aadhaarNote"),"ok","Aadhaar saved. You can add another worker.");
      resetEnroll();
    }).catch(function(e){note($("aadhaarNote"),"err",e.message);})
    .then(function(){$("btnSaveAadhaar").disabled=false;});
  }
  function resetEnroll(){
    $("enName").value="";$("enPhone").value="";$("enRate").value="";$("aaNumber").value="";
    $("aaOcrNote").textContent="";S.newLabour=null;S.aaFront=null;S.aaBack=null;
    $("aaFrozen").classList.add("hidden");$("aaFrozenB").classList.add("hidden");
    $("aaVideo").classList.remove("hidden");$("aaVideoB").classList.remove("hidden");
    $("aaBackWrap").classList.add("hidden");$("aadhaarBlock").classList.add("hidden");
    unfreezeEnroll();stopCamera("aaF");stopCamera("aaB");
  }

  // -------- daily entry --------
  function loadStagesInto(sel){
    return call("site_api.get_app_menu",{project:S.project}).then(function(m){
      sel.innerHTML="";
      (m.stages||[]).forEach(function(s){var o=document.createElement("option");
        o.value=s.task;o.textContent=s.subject;sel.appendChild(o);});
      return m;
    });
  }
  var progParams=[], cashCats=[];
  function addProgressRow(){
    var wrap=document.createElement("div");wrap.className="entry-row";
    var opts=progParams.map(function(p){return '<option value="'+esc(p.name)+'">'+esc(p.parameter_name)+(p.uom?" ("+esc(p.uom)+")":"")+'</option>';}).join("");
    wrap.innerHTML='<div><select class="pr-param">'+opts+'</select></div>'+
      '<div style="flex:0 0 90px"><input class="pr-qty" type="number" inputmode="decimal" placeholder="Qty"></div>'+
      '<button class="rm" type="button">×</button>';
    wrap.querySelector(".rm").onclick=function(){wrap.remove();};
    $("progressRows").appendChild(wrap);
  }
  function addCashRow(){
    var wrap=document.createElement("div");wrap.className="entry-row";
    var opts=cashCats.map(function(c){return '<option value="'+esc(c)+'">'+esc(c)+'</option>';}).join("");
    wrap.innerHTML='<div><select class="cc-cat">'+opts+'</select></div>'+
      '<div style="flex:0 0 120px"><input class="cc-amt" type="number" inputmode="decimal" placeholder="Amount"></div>'+
      '<button class="rm" type="button">×</button>';
    wrap.querySelector(".rm").onclick=function(){wrap.remove();};
    $("cashRows").appendChild(wrap);
  }
  function saveDaily(){
    var task=$("dlStage").value;
    var holiday=$("dlHoliday").checked?1:0;
    var progress=[];
    $("progressRows").querySelectorAll(".entry-row").forEach(function(r){
      var p=r.querySelector(".pr-param").value,q=r.querySelector(".pr-qty").value;
      if(p&&q)progress.push({parameter:p,quantity:q});});
    var cash=[];
    $("cashRows").querySelectorAll(".entry-row").forEach(function(r){
      var c=r.querySelector(".cc-cat").value,a=r.querySelector(".cc-amt").value;
      if(c&&a)cash.push({category:c,amount:a});});
    $("btnSaveDaily").disabled=true;note($("dailyNote"),"","Saving...");
    call("site_api.submit_daily_log",{project:S.project,task:task,is_holiday:holiday,
      remarks:$("dlRemarks").value.trim()||null,
      progress_rows:JSON.stringify(progress),petty_cash:JSON.stringify(cash)
    }).then(function(r){
      note($("dailyNote"),"ok","Today's entry saved. The office will review it.");
      $("progressRows").innerHTML="";$("cashRows").innerHTML="";$("dlRemarks").value="";
      $("dlHoliday").checked=false;
    }).catch(function(e){note($("dailyNote"),"err",e.message);})
    .then(function(){$("btnSaveDaily").disabled=false;});
  }

  // -------- roster --------
  function loadRoster(){
    var box=$("roster");box.innerHTML='<div class="person"><span class="nm muted">Loading...</span></div>';
    call("site_api.get_site_roster",{project:S.project}).then(function(rows){
      box.innerHTML="";
      if(!rows.length){box.innerHTML='<div class="person"><span class="nm muted">No workers yet. Use Add worker.</span></div>';return;}
      rows.forEach(function(p){var d=document.createElement("div");d.className="person";
        var img=p.photo?'<img class="avatar" src="'+p.photo+'" alt="">':'<span class="avatar"></span>';
        var pill=!p.enrolled?'<span class="pill new">NO FACE</span>':
          (p.last_punch&&p.last_punch!=="OUT"?'<span class="pill on">'+p.last_punch+'</span>':
          '<span class="pill off">'+(p.last_punch||"NOT IN")+'</span>');
        d.innerHTML=img+'<span class="nm">'+esc(p.labour_name)+'<small>'+esc(p.skill_category||"")+'</small></span>'+pill;
        box.appendChild(d);});
    }).catch(function(e){box.innerHTML='<div class="person"><span class="nm">'+esc(e.message)+'</span></div>';});
  }
  function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){
    return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];});}

  // -------- navigation --------
  function showScreen(which){
    ["home","attend","enroll","daily","today"].forEach(function(k){
      $(k+"Screen").classList.add("hidden");});
    $(which+"Screen").classList.remove("hidden");
    $("btnHome").classList.toggle("hidden",which==="home");
    if(which==="today")loadRoster();
    if(which==="daily"){loadStagesInto($("dlStage"));}
    if(which==="enroll"){startCamera($("video2"),S.facing2,"en2").catch(function(){});}
    else{stopCamera("en2");}
    if(which==="attend"){startCamera($("video"),S.facing,"att").catch(function(){});}
    else{stopCamera("att");}
    if(which!=="enroll"){resetEnroll();}
  }

  // -------- boot --------
  function boot(){
    $("btnLogin").onclick=doLogin;
    $("lgPass").addEventListener("keydown",function(e){if(e.key==="Enter")doLogin();});
    $("btnLogout").onclick=doLogout;

    if(!PROJECTS){ // not logged in -> show login
      $("loginScreen").classList.remove("hidden");
      $("appShell").classList.add("hidden");
      return;
    }
    // logged in
    $("loginScreen").classList.add("hidden");
    $("appShell").classList.remove("hidden");

    var sel=$("siteSelect");
    if(!PROJECTS.length){
      $("pickSite").innerHTML='<h1 style="font-size:24px;margin-bottom:4px">No site assigned</h1>'+
        '<p class="muted">Ask the office to assign you to a site, then sign in again.</p>';
      return;
    }
    PROJECTS.forEach(function(p){var o=document.createElement("option");
      o.value=p.name;o.textContent=p.project_name||p.name;sel.appendChild(o);});
    var saved=localStorage.getItem("sbi_site");if(saved)sel.value=saved;

    $("btnStart").onclick=function(){
      S.project=sel.value;if(!S.project)return;
      localStorage.setItem("sbi_site",S.project);
      $("siteLabel").textContent=sel.options[sel.selectedIndex].text;
      $("pickSite").classList.add("hidden");
      begin();
    };
    $("btnHome").onclick=function(){showScreen("home");};
    Array.prototype.forEach.call(document.querySelectorAll(".tile"),function(t){
      t.onclick=function(){showScreen(t.getAttribute("data-go"));};});

    $("btnFlip").onclick=function(){S.facing=S.facing==="user"?"environment":"user";
      $("video").classList.toggle("mirror",S.facing==="user");
      startCamera($("video"),S.facing,"att");};
    $("btnFlip2").onclick=function(){S.facing2=S.facing2==="user"?"environment":"user";
      $("video2").classList.toggle("mirror",S.facing2==="user");
      startCamera($("video2"),S.facing2,"en2");};
    $("btnFreeze2").onclick=function(){enFrozen?unfreezeEnroll():freezeEnroll();};
    $("btnEnroll").onclick=doEnroll;
    $("aaFreeze").onclick=function(){captureAadhaar("front");};
    $("aaFreezeB").onclick=function(){captureAadhaar("back");};
    $("btnSaveAadhaar").onclick=saveAadhaar;
    $("btnAddProgress").onclick=addProgressRow;
    $("btnAddCash").onclick=addCashRow;
    $("btnSaveDaily").onclick=saveDaily;
    $("dlHoliday").onchange=function(){$("dlWorkBlock").classList.toggle("hidden",this.checked);};
    $("btnRefresh").onclick=loadRoster;
    window.addEventListener("online",queueFlush);
    paintQueue();
    setupInstall();
  }

  function begin(){
    $("btnHome").classList.remove("hidden");
    watchGps();
    note($("punchNote"),"","Loading face recognition...");
    Promise.all([loadModels()]).then(function(){
      punchLoop();enrollLoop();queueFlush();
      return Promise.all([
        call("site_api.get_enroll_options",{}),
        call("site_api.get_progress_parameters",{}),
        call("site_api.get_petty_cash_categories",{}),
        call("site_api.get_app_menu",{project:S.project})
      ]);
    }).then(function(res){
      var opt=res[0]||{};
      fillSelect($("enGender"),opt.gender,false);
      fillSelect($("enSkill"),opt.skill,true);
      fillSelect($("enWage"),opt.wage_types,true);
      progParams=res[1]||[];cashCats=res[2]||[];
      var m=res[3]||{};
      $("hsPresent").textContent=m.present||0;$("hsHead").textContent=m.headcount||0;
      $("hsDate").textContent=m.today||"—";
      showScreen("home");
    }).catch(function(e){
      showScreen("home");
      frappe_alert("Some data could not load: "+e.message);
    });
  }
  function fillSelect(el,vals,blank){if(!el)return;el.innerHTML="";
    if(blank){var b=document.createElement("option");b.value="";b.textContent="Not set";el.appendChild(b);}
    (vals||[]).forEach(function(v){var o=document.createElement("option");o.value=v;o.textContent=v;el.appendChild(o);});}
  function frappe_alert(msg){/* silent, notes handle per-screen errors */}

  function setupInstall(){
    if("serviceWorker" in navigator){
      navigator.serviceWorker.register("/sbi_sw.js",{scope:"/site_app"}).catch(function(){});
    }
  }

  boot();
})();
</script>
</body>
</html>
'@

$c_site_app_py = @'
import frappe

no_cache = 1

# Roles that may work on any site.  Everyone else sees only the sites they are
# assigned to, so a site engineer on a shared tablet cannot record attendance
# against another team's project.
ALL_SITES_ROLES = {
	"System Manager",
	"Projects Manager",
	"Site Cost Approver",
	"Administrator",
}


def get_context(context):
	context.no_header = 1
	context.csrf_token = frappe.sessions.get_csrf_token()

	# Not signed in: render the app, which shows its own login screen.
	if frappe.session.user == "Guest":
		context.projects = None
		context.projects_json = "null"
		return context

	projects = get_allowed_projects()
	context.user_fullname = frappe.utils.get_fullname(frappe.session.user)
	context.projects = projects
	context.projects_json = frappe.as_json(projects)
	return context


def get_allowed_projects():
	if can_see_all_sites():
		return open_projects()
	names = assigned_projects(frappe.session.user)
	if not names:
		return []
	return open_projects(names)


def can_see_all_sites():
	if frappe.session.user == "Administrator":
		return True
	return bool(ALL_SITES_ROLES & set(frappe.get_roles()))


def assigned_projects(user):
	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not employee:
		return []
	rows = frappe.get_all(
		"Site Assignment",
		filters={"employee": employee, "to_date": ("is", "not set")},
		pluck="project",
	)
	meta = frappe.get_meta("Project")
	for field in ("sbi_site_incharge", "sbi_storekeeper",
	              "custom_site_incharge", "custom_site_storekeeper"):
		if meta.has_field(field):
			rows += frappe.get_all("Project", filters={field: employee}, pluck="name")
	return list(set(rows))


def open_projects(names=None):
	filters = {"status": "Open"}
	if names is not None:
		filters["name"] = ("in", names)
	return frappe.get_all(
		"Project",
		filters=filters,
		fields=["name", "project_name"],
		order_by="project_name asc",
		limit_page_length=200,
	)
'@

$c_sbi_sw_js = @'
/* Service worker for the SBI site app.
 * Site tablets lose signal often, so the shell, the face model weights and the
 * OCR bundle are cached on first use.  Attendance and entries always go to the
 * network; the page queues punches locally if that fails.
 */
var CACHE = "sbi-site-v2";
var SHELL = [
  "/site_app",
  "/assets/sbi_projects/site_app/icon-192.png",
  "/assets/sbi_projects/site_app/icon-512.png",
  "/assets/sbi_projects/site_app/sbi-logo-full.png",
  "https://cdn.jsdelivr.net/npm/@vladmandic/face-api/dist/face-api.js",
  "https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js"
];
self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) {
    return Promise.all(SHELL.map(function (url) {
      return c.add(new Request(url, { mode: "no-cors" })).catch(function () {});
    }));
  }).then(function () { return self.skipWaiting(); }));
});
self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.map(function (k) { return k === CACHE ? null : caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});
self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return;
  var url = req.url;
  if (url.indexOf("/api/method/") !== -1) return;
  var isLib = url.indexOf("/@vladmandic/face-api/") !== -1 ||
              url.indexOf("tesseract") !== -1 ||
              url.indexOf("/model") !== -1;
  if (isLib) {
    e.respondWith(caches.match(req).then(function (hit) {
      return hit || fetch(req).then(function (res) {
        var copy = res.clone();
        caches.open(CACHE).then(function (c) { c.put(req, copy); });
        return res;
      });
    }));
    return;
  }
  if (req.mode === "navigate") {
    e.respondWith(fetch(req).then(function (res) {
      var copy = res.clone();
      caches.open(CACHE).then(function (c) { c.put("/site_app", copy); });
      return res;
    }).catch(function () { return caches.match("/site_app"); }));
  }
});
'@

$c_sbi_site_manifest_json = @'
{
  "name": "SBI Site Attendance",
  "short_name": "SBI Site",
  "description": "Attendance, daily records and worker enrollment for Shiv Bharat Infrastructures.",
  "start_url": "/site_app",
  "scope": "/site_app",
  "display": "standalone",
  "orientation": "portrait",
  "background_color": "#111111",
  "theme_color": "#111111",
  "icons": [
    {"src": "/assets/sbi_projects/site_app/icon-192.png", "sizes": "192x192", "type": "image/png"},
    {"src": "/assets/sbi_projects/site_app/icon-512.png", "sizes": "512x512", "type": "image/png"},
    {"src": "/assets/sbi_projects/site_app/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}
  ]
}
'@

$c_site_api_py = @'
"""API used by the site tablet / mobile app.

Face recognition runs on the device: the browser computes an embedding with
MediaPipe and sends the vector here.  The raw image never has to leave the
device for matching, and the server only compares numbers, so this works on a
normal bench with no ML dependencies installed.

The server stays the authority on identity: it re-matches every embedding
against the enrolled roster rather than trusting whatever labour id the device
claims.
"""

import base64
import json
import math

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

# Cosine similarity above which two embeddings are treated as the same person.
# MediaPipe FaceEmbedder vectors typically land around 0.9+ for a true match and
# below 0.5 for different people, so 0.75 leaves a wide margin either side.
DEFAULT_MATCH_THRESHOLD = 0.75

# Enrollment is checked against a slightly looser bar than a punch: it is much
# cheaper to ask "is this the same person?" than to end up with one worker
# holding two records and half their attendance in each.
DUPLICATE_THRESHOLD = 0.68


# ----------------------------------------------------------------------
# roster
# ----------------------------------------------------------------------

# The Labour doctype has been through several revisions and field names differ
# between them, so nothing here is hardcoded.  Each logical field lists the
# names it has gone by; the first one that exists on the live schema wins.
FIELD_ALIASES = {
	"name_field":   ["labour_name"],
	"code":         ["labour_code"],
	"gender":       ["gender"],
	"skill":        ["skill", "skill_category"],
	"phone":        ["mobile_no", "phone"],
	"photo":        ["photo"],
	"status":       ["status", "is_active"],
	"site":         ["default_project", "default_site"],
	"enrolled_flag":["face_enrolled"],
	"embedding":    ["face_embedding"],
	"enrolled_on":  ["enrolled_on"],
	"enrolled_by":  ["enrolled_by"],
	"wage_type":    ["sbi_wage_type"],
	"wage_rate":    ["sbi_wage_rate", "daily_wage"],
	"contractor":   ["contractor"],
}


def _f(key):
	"""Resolve a logical field to whatever it is actually called here."""
	meta = frappe.get_meta("Labour")
	for candidate in FIELD_ALIASES.get(key, []):
		if meta.has_field(candidate):
			return candidate
	return None


def _labour_fields():
	"""Every roster field that exists on this site, in a stable order."""
	keys = ["name_field", "code", "gender", "skill", "phone", "photo",
	        "status", "site", "enrolled_flag", "wage_type", "wage_rate"]
	out = []
	for k in keys:
		f = _f(k)
		if f and f not in out:
			out.append(f)
	return out


def _active_filter():
	"""Filter out inactive labour without guessing what 'active' is called."""
	field = _f("status")
	if not field:
		return {}

	df = frappe.get_meta("Labour").get_field(field)
	if df.fieldtype == "Check":
		return {field: 1}

	options = [o.strip() for o in (df.options or "").split("\n") if o.strip()]
	if "Active" in options:
		return {field: "Active"}
	return {}


@frappe.whitelist()
def get_site_roster(project):
	"""Everyone who can punch at this site, with today's status."""
	_check_site_access(project)

	available = _labour_fields()
	kwargs = {"filters": _active_filter(), "fields": ["name"] + available}

	site_field = _f("site")
	if site_field:
		kwargs["or_filters"] = [[site_field, "=", project],
		                        [site_field, "in", ("", None)]]

	name_field = _f("name_field")
	if name_field:
		kwargs["order_by"] = name_field + " asc"

	labour = frappe.get_all("Labour", **kwargs)

	names = [l.name for l in labour]
	status = {}
	if names:
		rows = frappe.get_all(
			"Labour Attendance Log",
			filters={"labour": ("in", names), "log_date": frappe.utils.today()},
			fields=["labour", "log_type", "log_datetime"],
			order_by="log_datetime asc",
		)
		for r in rows:
			status[r.labour] = r.log_type

	name_field = _f("name_field")
	skill_field = _f("skill")
	for l in labour:
		l["last_punch"] = status.get(l.name)
		l["enrolled"] = bool(frappe.db.get_value("Labour", l.name, "face_embedding"))
		# the app reads labour_name and skill_category whatever the schema calls them
		l["labour_name"] = (l.get(name_field) if name_field else None) or l.name
		l["skill_category"] = l.get(skill_field) if skill_field else None

	return labour


# ----------------------------------------------------------------------
# enrollment
# ----------------------------------------------------------------------

@frappe.whitelist()
def get_enroll_options():
	"""Dropdown values for the enrollment form, read from the live schema.

	Sending a value the Select does not allow fails validation, so the app
	populates its dropdowns from here rather than from a hardcoded list.
	"""
	meta = frappe.get_meta("Labour")

	def options_for(key):
		field = _f(key)
		if not field:
			return []
		df = meta.get_field(field)
		if not df or df.fieldtype != "Select":
			return []
		return [o.strip() for o in (df.options or "").split("\n") if o.strip()]

	return {
		"gender": options_for("gender") or ["Male", "Female", "Other"],
		"skill": options_for("skill"),
		"has_skill": bool(_f("skill")),
		"has_phone": bool(_f("phone")),
		"wage_types": frappe.get_all(
			"Wage Type",
			filters={"is_active": 1} if frappe.get_meta("Wage Type").has_field("is_active") else {},
			pluck="name",
		) if frappe.db.exists("DocType", "Wage Type") else [],
	}

@frappe.whitelist()
def enroll_labour(labour_name, gender, embedding, photo=None, project=None,
                  phone=None, skill_category=None, wage_type=None, wage_rate=None):
	"""Create a labour record and store the face vector. Called once per person."""
	if project:
		_check_site_access(project)

	vector = _parse_embedding(embedding)

	# Refuse a second record for a face that is already enrolled.  Without this
	# the same person can be added twice and their attendance splits in half.
	existing = match_face(vector, project, DUPLICATE_THRESHOLD)
	if existing:
		return {
			"duplicate": True,
			"labour": existing["labour"],
			"labour_name": existing["labour_name"],
			"score": existing["score"],
		}

	wanted = {
		"name_field":   (labour_name or "").strip(),
		"gender":       gender,
		"phone":        phone,
		"skill":        skill_category,
		"site":         project,
		"embedding":    json.dumps(vector),
		"enrolled_flag": 1,
		"enrolled_on":  now_datetime(),
		"enrolled_by":  frappe.session.user,
		"wage_type":    wage_type,
		"wage_rate":    flt(wage_rate) or None,
	}

	payload = {"doctype": "Labour"}
	for key, value in wanted.items():
		field = _f(key)
		if field and value is not None:
			payload[field] = value
	payload.update(_active_filter())

	doc = frappe.get_doc(payload)
	doc.insert(ignore_permissions=True)

	if photo:
		url = _save_photo(photo, "Labour", doc.name, f"labour-{doc.name}.jpg")
		doc.db_set("photo", url, update_modified=False)

	return {"duplicate": False, "labour": doc.name,
	        "labour_name": _labour_display_name(doc.name)}


@frappe.whitelist()
def re_enroll_face(labour, embedding, photo=None):
	"""Replace a stored face vector, e.g. after a bad first capture."""
	vector = _parse_embedding(embedding)
	doc = frappe.get_doc("Labour", labour)
	doc.db_set(_f("embedding"), json.dumps(vector), update_modified=False)
	for key, value in (("enrolled_flag", 1), ("enrolled_on", now_datetime()),
	                   ("enrolled_by", frappe.session.user)):
		field = _f(key)
		if field:
			doc.db_set(field, value, update_modified=False)
	if photo:
		url = _save_photo(photo, "Labour", labour, f"labour-{labour}.jpg")
		doc.db_set("photo", url, update_modified=False)
	return {"labour": labour, "status": "re-enrolled"}


# ----------------------------------------------------------------------
# punch
# ----------------------------------------------------------------------

@frappe.whitelist()
def punch(project, log_type, embedding=None, labour=None, latitude=None,
          longitude=None, photo=None, device_id=None, threshold=None):
	"""Record one attendance punch.

	Identity comes from the embedding when one is supplied.  A labour id on its
	own is accepted only as a supervisor override and is marked as Manual, so
	the two cases stay distinguishable in the record.
	"""
	_check_site_access(project)

	confidence = None
	method = "Manual"

	if embedding:
		vector = _parse_embedding(embedding)
		match = match_face(vector, project, threshold)
		if not match:
			return {"matched": False,
			        "message": _("No enrolled face matched. Enroll this person first.")}
		labour = match["labour"]
		confidence = match["score"]
		method = "Face"
	elif not labour:
		frappe.throw(_("Either a face embedding or a labour id is required."))

	doc = frappe.new_doc("Labour Attendance Log")
	doc.labour = labour
	doc.project = project
	doc.log_type = log_type
	doc.log_datetime = now_datetime()
	doc.latitude = flt(latitude)
	doc.longitude = flt(longitude)
	doc.verification_method = method
	doc.face_confidence = confidence
	doc.device_id = device_id
	doc.insert(ignore_permissions=True)  # geofence + sequence validated in controller

	if photo:
		url = _save_photo(photo, "Labour Attendance Log", doc.name, f"punch-{doc.name}.jpg")
		doc.db_set("photo", url, update_modified=False)

	return {
		"matched": True,
		"log": doc.name,
		"labour": labour,
		"labour_name": _labour_display_name(labour),
		"log_type": doc.log_type,
		"time": str(doc.log_datetime),
		"confidence": confidence,
		"within_geofence": bool(doc.within_geofence),
		"distance_from_site": doc.distance_from_site,
	}


@frappe.whitelist()
def match_face(embedding, project=None, threshold=None):
	"""Best match for an embedding among enrolled labour."""
	vector = _parse_embedding(embedding)
	threshold = flt(threshold) or DEFAULT_MATCH_THRESHOLD

	embed_field = _f("embedding")
	name_field = _f("name_field")

	filters = {embed_field: ("is", "set")}
	filters.update(_active_filter())

	fields = ["name", embed_field]
	if name_field:
		fields.append(name_field)

	candidates = frappe.get_all("Labour", filters=filters, fields=fields)

	best = None
	for row in candidates:
		try:
			stored = json.loads(row.get(embed_field))
		except (TypeError, ValueError):
			continue
		score = cosine_similarity(vector, stored)
		if best is None or score > best["score"]:
			best = {"labour": row.name,
			        "labour_name": (row.get(name_field) if name_field else None) or row.name,
			        "score": score}

	if not best or best["score"] < threshold:
		return None

	best["score"] = round(best["score"], 4)
	return best


# ----------------------------------------------------------------------
# maths
# ----------------------------------------------------------------------

def cosine_similarity(a, b):
	"""1.0 means identical direction, 0.0 orthogonal, -1.0 opposite."""
	if not a or not b or len(a) != len(b):
		return -1.0

	dot = sum(x * y for x, y in zip(a, b))
	na = math.sqrt(sum(x * x for x in a))
	nb = math.sqrt(sum(y * y for y in b))
	if not na or not nb:
		return -1.0
	return dot / (na * nb)


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def _labour_display_name(labour):
	field = _f("name_field")
	if field:
		return frappe.db.get_value("Labour", labour, field) or labour
	return labour


def _parse_embedding(embedding):
	if isinstance(embedding, str):
		try:
			embedding = json.loads(embedding)
		except ValueError:
			frappe.throw(_("Face embedding is not valid JSON."))

	if not isinstance(embedding, (list, tuple)) or not embedding:
		frappe.throw(_("Face embedding must be a non-empty list of numbers."))

	try:
		return [float(x) for x in embedding]
	except (TypeError, ValueError):
		frappe.throw(_("Face embedding must contain only numbers."))


def _save_photo(data, doctype, name, filename):
	"""Accepts a data URL or bare base64 and attaches it to the document."""
	if "," in data and data.strip().startswith("data:"):
		data = data.split(",", 1)[1]

	try:
		content = base64.b64decode(data)
	except Exception:
		frappe.throw(_("Photo is not valid base64 data."))

	f = frappe.get_doc({
		"doctype": "File",
		"file_name": filename,
		"attached_to_doctype": doctype,
		"attached_to_name": name,
		"is_private": 1,
		"content": content,
	})
	f.save(ignore_permissions=True)
	return f.file_url


def _check_site_access(project):
	if not project or not frappe.db.exists("Project", project):
		frappe.throw(_("Unknown site: {0}").format(project))

	if frappe.session.user == "Administrator":
		return

	allowed = {"System Manager", "Projects Manager", "Projects User", "Site Cost Approver"}
	if not allowed & set(frappe.get_roles()):
		frappe.throw(_("You are not allowed to record site attendance."),
		             frappe.PermissionError)


# ======================================================================
# Site management endpoints (Batch 2b)
# Cost figures are never returned here -- the site app must not show
# budgets, sale values or variance to site staff.
# ======================================================================

import base64
from frappe.utils import now_datetime, today, flt, getdate


def _can_see_full_aadhaar():
	"""Owner / HR / managers see the full number and images; site staff do not."""
	allowed = {"System Manager", "HR Manager", "HR User",
	           "Projects Manager", "Site Cost Approver", "Administrator"}
	return bool(allowed & set(frappe.get_roles()))


# ----------------------------------------------------------------------
# Aadhaar capture
# ----------------------------------------------------------------------

@frappe.whitelist()
def save_aadhaar(labour, aadhaar_number=None, front_image=None, back_image=None):
	"""Store Aadhaar details for a worker.

	Site staff may capture (so a new worker can be enrolled on site), but the
	full number and images are permlevel-1 fields that only owner/HR can read
	back.  We store the last four digits at permlevel 0 so site staff can still
	confirm identity without exposing the whole number.
	"""
	if not frappe.db.exists("Labour", labour):
		frappe.throw("Worker not found.")

	num = "".join(ch for ch in (aadhaar_number or "") if ch.isdigit())
	if num and len(num) != 12:
		frappe.throw("An Aadhaar number must be 12 digits.")

	meta = frappe.get_meta("Labour")
	updates = {}

	if num:
		if meta.has_field("aadhaar_number"):
			updates["aadhaar_number"] = num
		if meta.has_field("aadhaar_last4"):
			updates["aadhaar_last4"] = num[-4:]

	if front_image and meta.has_field("aadhaar_front"):
		updates["aadhaar_front"] = _save_photo(front_image, "Labour", labour,
		                                        labour + "-aadhaar-front.jpg")
	if back_image and meta.has_field("aadhaar_back"):
		updates["aadhaar_back"] = _save_photo(back_image, "Labour", labour,
		                                       labour + "-aadhaar-back.jpg")

	if updates:
		# bypass permlevel for the write; the caller is allowed to capture even
		# though they will not be able to read the value back afterwards.
		frappe.db.set_value("Labour", labour, updates, update_modified=True)
		frappe.db.commit()

	return {"saved": True, "last4": num[-4:] if num else None}


@frappe.whitelist()
def get_aadhaar_status(labour):
	"""What the current user is allowed to see about a worker's Aadhaar."""
	if not frappe.db.exists("Labour", labour):
		return {}

	meta = frappe.get_meta("Labour")
	last4 = frappe.db.get_value("Labour", labour, "aadhaar_last4") \
		if meta.has_field("aadhaar_last4") else None

	out = {"last4": last4, "has_front": False, "has_back": False, "full": None}
	if meta.has_field("aadhaar_front"):
		out["has_front"] = bool(frappe.db.get_value("Labour", labour, "aadhaar_front"))
	if meta.has_field("aadhaar_back"):
		out["has_back"] = bool(frappe.db.get_value("Labour", labour, "aadhaar_back"))

	if _can_see_full_aadhaar() and meta.has_field("aadhaar_number"):
		out["full"] = frappe.db.get_value("Labour", labour, "aadhaar_number")

	return out


# ----------------------------------------------------------------------
# Daily work log from the app -- progress, holiday, remarks
# ----------------------------------------------------------------------

@frappe.whitelist()
def get_app_menu(project):
	"""Site-facing summary for the app home: today's counts, no cost figures."""
	_check_site_access(project)
	roster = get_site_roster(project)
	present = sum(1 for r in roster if r.get("last_punch") and r["last_punch"] != "OUT")

	return {
		"project": project,
		"project_name": frappe.db.get_value("Project", project, "project_name") or project,
		"headcount": len(roster),
		"present": present,
		"today": frappe.utils.formatdate(today(), "dd MMM yyyy"),
		"stages": _open_stages(project),
	}


def _open_stages(project):
	"""Stage names only -- the app never shows stage budgets."""
	tasks = frappe.get_all(
		"Task",
		filters={"project": project, "is_group": 1},
		fields=["name", "subject", "status"],
		order_by="lft asc" if frappe.get_meta("Task").has_field("lft") else "creation asc",
	)
	return [{"task": t.name, "subject": t.subject, "status": t.status} for t in tasks]


@frappe.whitelist()
def submit_daily_log(project, task=None, log_date=None, is_holiday=0,
                     remarks=None, progress_rows=None, petty_cash=None):
	"""Create a Daily Work Log from the app.

	Accepts progress rows and petty-cash rows.  No cost totals are returned to
	the caller; the owner reviews and approves on the desk.
	"""
	import json
	_check_site_access(project)

	log_date = log_date or today()

	existing = frappe.db.exists("Daily Work Log",
		{"project": project, "task": task, "log_date": log_date})
	if existing:
		doc = frappe.get_doc("Daily Work Log", existing)
	else:
		doc = frappe.new_doc("Daily Work Log")
		doc.project = project
		if task and doc.meta.has_field("task"):
			doc.task = task
		if doc.meta.has_field("log_date"):
			doc.log_date = log_date

	if doc.meta.has_field("sbi_is_holiday"):
		doc.sbi_is_holiday = int(is_holiday or 0)
	if remarks and doc.meta.has_field("remarks"):
		doc.remarks = remarks
	elif remarks and doc.meta.has_field("sbi_remarks"):
		doc.sbi_remarks = remarks

	# progress rows
	if progress_rows and doc.meta.has_field("sbi_progress_rows"):
		rows = json.loads(progress_rows) if isinstance(progress_rows, str) else progress_rows
		doc.set("sbi_progress_rows", [])
		for r in rows:
			doc.append("sbi_progress_rows", {
				"progress_parameter": r.get("parameter"),
				"quantity": flt(r.get("quantity")),
				"remarks": r.get("remarks"),
			})

	# petty cash rows -> other-cost table
	if petty_cash and doc.meta.has_field("sbi_costs"):
		rows = json.loads(petty_cash) if isinstance(petty_cash, str) else petty_cash
		for r in rows:
			doc.append("sbi_costs", {
				"site_cost_category": r.get("category"),
				"description": r.get("description"),
				"amount": flt(r.get("amount")),
			})

	doc.flags.ignore_permissions = True
	doc.save()
	frappe.db.commit()

	return {"name": doc.name, "saved": True}


@frappe.whitelist()
def get_progress_parameters():
	"""Active progress parameters for the app dropdown."""
	if not frappe.db.exists("DocType", "Progress Parameter"):
		return []
	filters = {}
	if frappe.get_meta("Progress Parameter").has_field("is_active"):
		filters["is_active"] = 1
	return frappe.get_all("Progress Parameter", filters=filters,
	                      fields=["name", "parameter_name", "uom"], order_by="parameter_name")


@frappe.whitelist()
def get_petty_cash_categories():
	"""Cost categories a site can spend petty cash against (labels only)."""
	if not frappe.db.exists("DocType", "Site Cost Category"):
		return []
	return frappe.get_all("Site Cost Category", fields=["name"], order_by="name", pluck="name")
'@

$c_geofence_report_py = @'
"""Out-of-boundary attendance, for the office to review.

Attendance is never blocked on distance -- a genuine worker with a poor GPS
fix should not be turned away.  Instead every punch is stored with its distance
from the site centre and whether it fell inside the fence, and this surfaces the
ones that did not so the office can follow up.
"""

import frappe
from frappe.utils import flt, getdate, add_days, today


@frappe.whitelist()
def get_out_of_bounds(project=None, from_date=None, to_date=None):
	"""Punches that landed outside the geo-fence, newest first."""
	from_date = from_date or add_days(today(), -7)
	to_date = to_date or today()

	filters = {
		"within_geofence": 0,
		"log_datetime": ["between", [from_date + " 00:00:00", to_date + " 23:59:59"]],
	}
	if project:
		filters["project"] = project

	if not frappe.get_meta("Labour Attendance Log").has_field("within_geofence"):
		return {"rows": [], "note": "Geo-fence fields are not set up."}

	rows = frappe.get_all(
		"Labour Attendance Log",
		filters=filters,
		fields=["name", "labour", "project", "log_type", "log_datetime",
		        "distance_from_site", "latitude", "longitude"],
		order_by="log_datetime desc",
		limit_page_length=200,
	)

	for r in rows:
		r["labour_name"] = frappe.db.get_value("Labour", r.labour, "labour_name") or r.labour
		r["project_name"] = frappe.db.get_value("Project", r.project, "project_name") or r.project
		r["map_link"] = (
			"https://www.google.com/maps?q={0},{1}".format(r.latitude, r.longitude)
			if r.latitude and r.longitude else None
		)

	return {
		"rows": rows,
		"count": len(rows),
		"from_date": str(from_date),
		"to_date": str(to_date),
	}
'@

$c_geofence_js = @'

// ---------------------------------------------------------------------------
// Site geo-fence on the Project form.
//
// The owner (or site in-charge) stands at the site and taps "Capture site
// location" to set the centre, then sets a radius.  Attendance still records
// from anywhere, but each punch is marked in or out of the fence with the
// distance, so the office can see who punched from off site.
// ---------------------------------------------------------------------------

frappe.ui.form.on("Project", {
	refresh(frm) {
		if (frm.is_new()) return;
		sbi_render_geofence(frm);
	},
});

function sbi_render_geofence(frm) {
	const wrapper = frm.get_field("sbi_geofence_html");
	if (!wrapper || !wrapper.$wrapper) return;

	const lat = frm.doc.sbi_site_latitude;
	const lng = frm.doc.sbi_site_longitude;
	const radius = frm.doc.sbi_geofence_radius || 200;
	const isSet = lat && lng;

	wrapper.$wrapper.html(`
		<div style="border:1px solid var(--border-color);border-radius:4px;overflow:hidden">
			<div style="padding:12px 14px;background:var(--fg-color);border-bottom:1px solid var(--border-color)">
				<div style="font-weight:700;margin-bottom:2px">
					${isSet ? "Site boundary is set" : "Site boundary not set yet"}
				</div>
				<div class="text-muted" style="font-size:13px">
					${isSet
						? `Centre ${flt(lat).toFixed(6)}, ${flt(lng).toFixed(6)} · radius ${radius} m`
						: "Until you set this, attendance is recorded from anywhere without a distance check."}
				</div>
			</div>
			<div style="padding:12px 14px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">
				<button class="btn btn-sm btn-primary sbi-capture-loc" type="button">Capture site location</button>
				<button class="btn btn-sm btn-default sbi-open-map" type="button" ${isSet ? "" : "disabled"}>View on map</button>
				<span class="text-muted" style="font-size:12px;margin-left:auto" id="sbi-geo-status"></span>
			</div>
		</div>`);

	wrapper.$wrapper.find(".sbi-capture-loc").on("click", () => sbi_capture_location(frm));
	wrapper.$wrapper.find(".sbi-open-map").on("click", () => {
		if (lat && lng) window.open(`https://www.google.com/maps?q=${lat},${lng}`, "_blank");
	});
}

function sbi_capture_location(frm) {
	const status = document.getElementById("sbi-geo-status");
	if (!navigator.geolocation) {
		if (status) status.textContent = "This device has no location support.";
		return;
	}
	if (status) status.textContent = "Getting your location…";

	navigator.geolocation.getCurrentPosition(
		(pos) => {
			const lat = pos.coords.latitude;
			const lng = pos.coords.longitude;
			const acc = Math.round(pos.coords.accuracy || 0);

			frappe.confirm(
				`Set the site centre to your current location?<br>
				 <b>${lat.toFixed(6)}, ${lng.toFixed(6)}</b><br>
				 <span class="text-muted">GPS accuracy about ${acc} m. Stand near the middle of the site for the best result.</span>`,
				() => {
					frm.set_value("sbi_site_latitude", String(lat));
					frm.set_value("sbi_site_longitude", String(lng));
					if (!frm.doc.sbi_geofence_radius) {
						frm.set_value("sbi_geofence_radius", 200);
					}
					frm.save().then(() => {
						frappe.show_alert({ message: "Site location saved", indicator: "green" });
						sbi_render_geofence(frm);
					});
				}
			);
			if (status) status.textContent = "";
		},
		(err) => {
			if (status) status.textContent = "Could not get location: " + err.message;
		},
		{ enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
	);
}
'@

$targets = @(
    @{ path = "sbi_projects\www\site_app.html"; body = $c_site_app_html },
    @{ path = "sbi_projects\www\site_app.py"; body = $c_site_app_py },
    @{ path = "sbi_projects\www\sbi_sw.js"; body = $c_sbi_sw_js },
    @{ path = "sbi_projects\www\sbi_site_manifest.json"; body = $c_sbi_site_manifest_json },
    @{ path = "sbi_projects\sbi_projects\site_api.py"; body = $c_site_api_py },
    @{ path = "sbi_projects\sbi_projects\geofence_report.py"; body = $c_geofence_report_py }
)
foreach ($t in $targets) {
    $full = Join-Path (Get-Location) $t.path
    $dir = Split-Path $full -Parent
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    [System.IO.File]::WriteAllText($full, $t.body, $utf8NoBom)
    $b = [System.IO.File]::ReadAllBytes($full)
    if ($b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF) { Write-Error ("BOM in " + $t.path); exit 1 }
    Write-Host ("  wrote " + $t.path) -ForegroundColor Green
}

# append geofence renderer to project.js, once
$js = [System.IO.File]::ReadAllText((Resolve-Path $projJs))
if ($js -match "sbi_render_geofence") { Write-Host "  geofence already in project.js - skipped" -ForegroundColor Yellow }
else { [System.IO.File]::WriteAllText((Resolve-Path $projJs), $js.TrimEnd() + "`n" + $c_geofence_js + "`n", $utf8NoBom); Write-Host "  appended geofence to project.js" -ForegroundColor Green }

# verify new app endpoints + geofence report present
$api = Join-Path $app "sbi_projects\site_api.py"
foreach ($fn in @("save_aadhaar","submit_daily_log","get_app_menu")) {
    if (-not (Select-String -Path $api -Pattern ("def " + $fn) -Quiet)) { Write-Error ("missing: " + $fn); exit 1 }
}
if (-not (Select-String -Path (Join-Path $app "sbi_projects\geofence_report.py") -Pattern "def get_out_of_bounds" -Quiet)) { Write-Error "geofence report missing"; exit 1 }
Write-Host "  endpoints verified" -ForegroundColor Green

Write-Host ""; git status --short; Write-Host ""
$ans = Read-Host "Commit and push? (y/n)"
if ($ans -ne "y") { Write-Host "Stopped." -ForegroundColor Yellow; exit 0 }
git add -A -- $app
git commit -m "feat: phase A - app polish, aadhaar flow, geofence boundary + out-of-bounds report"
git push origin main
Write-Host "Pushed. Deploy once, then add the geofence HTML field via console." -ForegroundColor Green
