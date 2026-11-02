// Notifications only. MediMate runs from a local Python server and does not need
// an offline shell. Older workers cached pages and styles, which could resurrect
// a previous reminder design when a request temporarily failed.
self.addEventListener('install',event=>event.waitUntil(self.skipWaiting()));
self.addEventListener('activate',event=>event.waitUntil(
  caches.keys().then(keys=>Promise.all(
    keys.filter(key=>key.startsWith('medimate-shell-')).map(key=>caches.delete(key))
  )).then(()=>self.clients.claim())
));
// Deliberately no fetch handler: always load current HTML, JavaScript and CSS
// from the running local server, never a previously downloaded app version.
self.addEventListener('notificationclick',event=>{
  event.notification.close();
  event.waitUntil(self.clients.matchAll({type:'window',includeUncontrolled:true})
    .then(clients=>clients.length?clients[0].focus():self.clients.openWindow('/')));
});
