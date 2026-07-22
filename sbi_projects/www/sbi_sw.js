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