// Tab viewer glue module.
// See docs/frontend.md §alphatab (SPEC 3.6).
// Loads alphaTab via the classic script tag and initializes it on the #tab element.

const el = document.getElementById("tab");
if (!el) {
  console.error("Tab viewer: #tab element not found");
  throw new Error("Tab viewer: #tab element not found");
}

const api = new alphaTab.AlphaTabApi(el, {
  core: { fontDirectory: "/static/vendor/alphatab/font/", useWorkers: false },
  player: { enablePlayer: false },
});

api.error.on((error) => {
  const msg = document.createElement("p");
  msg.className = "alert";
  msg.setAttribute("role", "alert");
  msg.textContent = "Failed to load tab: " + (error || "unknown error");
  el.replaceWith(msg);
});

const res = await fetch(el.dataset.file);
if (!res.ok) {
  throw new Error("Failed to fetch tab data: " + res.status);
}
api.load(new Uint8Array(await res.arrayBuffer()));
