// SBI Face Attendance service worker
var CACHE = "sbi-face-v1";

// cache the heavy libraries + models so the app opens fast and works on poor networks
var PRECACHE = [
  "https://cdn.jsdelivr.net/npm/@vladmandic/face-api/dist/face-api.js",
  "https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js"
];

self.addEventListener("install", function(e){
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(function(c){
    return Promise.all(PRECACHE.map(function(u){
      return fetch(u,{mode:"cors"}).then(function(r){return c.put(u,r);}).catch(function(){});
    }));
  }));
});

self.addEventListener("activate", function(e){
  e.waitUntil(caches.keys().then(function(keys){
    return Promise.all(keys.filter(function(k){return k!==CACHE;}).map(function(k){return caches.delete(k);}));
  }).then(function(){return self.clients.claim();}));
});

self.addEventListener("fetch", function(e){
  var url = e.request.url;
  // never cache the app page or API calls (always fresh -> avoids stale CSRF/data)
  if (url.indexOf("/face") >= 0 || url.indexOf("/api/") >= 0) {
    return; // let it hit the network normally
  }
  // cache-first for the heavy CDN libs and face model shards
  if (url.indexOf("jsdelivr.net") >= 0 || url.indexOf("/model") >= 0 || url.indexOf("tessdata") >= 0) {
    e.respondWith(
      caches.match(e.request).then(function(hit){
        return hit || fetch(e.request).then(function(r){
          var copy = r.clone();
          caches.open(CACHE).then(function(c){c.put(e.request, copy);}).catch(function(){});
          return r;
        });
      })
    );
  }
});