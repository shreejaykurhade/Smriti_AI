const CACHE = "smriti-ai-v26-vercel-voice";
const LOCALES = ["bn", "gu", "hi", "kn", "ml", "mr", "ne", "pa", "ta", "te", "ur"];
const CORE = ["/", ...LOCALES.map(code => `/locales/${code}.json`), "/manifest.webmanifest", "/brand/smriti-ai-logo.png", "/icons/smriti-ai-192.png", "/icons/smriti-ai-512.png", "/icons/smriti-ai-apple.png", "/history/ambedkar-1935.jpg", "/history/round-table-1931.jpg", "/history/poona-pact-1932.jpg", "/history/constitution-1949.jpg", "/history/deeksha-1956.jpg"];

// Clone before the browser can consume the original response. Cache writes are
// optional and stay alive through waitUntil; storage failures never break fetch.
function remember(event, key, response) {
  if (!response.ok || response.type === "opaque") return;
  const copy = response.clone();
  event.waitUntil(caches.open(CACHE).then(cache => cache.put(key, copy)).catch(() => {}));
}
self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(cache => Promise.allSettled(CORE.map(async path => {
    const response = await fetch(new Request(path, {cache: "reload"}));
    if (response.ok) await cache.put(path, response);
  }))).catch(() => {}).then(() => self.skipWaiting()));
});
self.addEventListener("activate", event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith("smriti-ai-") && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;
  // APIs, audio, RSC and build-specific JS stay on the network.
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/_next/") || request.headers.get("RSC") === "1" || url.searchParams.has("_rsc")) return;
  const navigation = request.mode === "navigate";
  if (!navigation && !CORE.includes(url.pathname)) return;
  const key = navigation ? "/" : request;
  event.respondWith((async () => {
    try {
      const response = await fetch(request);
      remember(event, key, response);
      return response;
    } catch {
      const cached = await caches.match(key).catch(() => undefined);
      return cached || new Response(navigation ? "You are offline. Reconnect to open SMRITI AI." : "Offline asset unavailable.", {status: 503, headers: {"Content-Type": "text/plain; charset=utf-8"}});
    }
  })());
});
