// Service worker: only handles Web Push display. No caching/offline
// logic here -- this wallet's offline-first design (localStorage-backed
// key material, no network needed to *view* what's already loaded) is
// already handled by the page itself, not a service worker cache; adding
// one for that too would be a second, separate piece of complexity this
// wallet doesn't need yet.

self.addEventListener("push", (event) => {
  let payload = { title: "FirstIslamicCoin Wallet", body: "" };
  try {
    payload = event.data.json();
  } catch {
    payload.body = event.data ? event.data.text() : "";
  }
  event.waitUntil(
    self.registration.showNotification(payload.title || "FirstIslamicCoin Wallet", {
      body: payload.body || "",
      icon: undefined,
      data: { url: payload.url || "/" },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(clients.openWindow(url));
});
