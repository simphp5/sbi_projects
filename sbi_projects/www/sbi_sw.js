/* Service worker for the site attendance app.
 *
 * Site tablets lose signal often, so the shell and the face-recognition model
 * weights are cached on first use.  Attendance punches are never cached: they
 * go to the network, and the page queues them in local storage if that fails.
 */

var CACHE = "sbi-site-v1";

var SHELL = [
  "/site_app",
  "/assets/sbi_projects/site_app/icon-192.png",
  "/assets/sbi_projects/site_app/icon-512.png",
  "https://cdn.jsdelivr.net/npm/@vladmandic/face-api/dist/face-api.js"
];

self.addEventListener("install", function (e) {
  e.waitUntil(
    caches.open(CACHE).then(function (c) {
      return Promise.all(SHELL.map(function (url) {
        return c.add(new Request(url, { mode: "no-cors" })).catch(function () {
          /* one missing asset must not fail the whole install */
        });
      }));
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.map(function (k) {
        return k === CACHE ? null : caches.delete(k);
      }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return;

  var url = req.url;

  // never cache API traffic
  if (url.indexOf("/api/method/") !== -1) return;

  // model weights and the face-api bundle: cache first, they never change
  var isModel = url.indexOf("/@vladmandic/face-api/") !== -1;
  if (isModel) {
    e.respondWith(
      caches.match(req).then(function (hit) {
        return hit || fetch(req).then(function (res) {
          var copy = res.clone();
          caches.open(CACHE).then(function (c) { c.put(req, copy); });
          return res;
        });
      })
    );
    return;
  }

  // the page itself: network first so staff get updates, cache as the fallback
  if (req.mode === "navigate") {
    e.respondWith(
      fetch(req).then(function (res) {
        var copy = res.clone();
        caches.open(CACHE).then(function (c) { c.put("/site_app", copy); });
        return res;
      }).catch(function () {
        return caches.match("/site_app");
      })
    );
  }
});