// Thin wrapper around fetch for the Hall Booking API.
const API = {
  base: "",

  async get(path) {
    const res = await fetch(this.base + path);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
    return data;
  },

  async post(path, body) {
    const res = await fetch(this.base + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
    return data;
  },
};

function showMsg(el, text, ok) {
  el.textContent = text;
  el.className = "msg show " + (ok ? "ok" : "err");
}

function hideMsg(el) {
  el.className = "msg";
}

function fmtDate(d) {
  return new Date(d + "T00:00:00").toLocaleDateString("en-IN", {
    weekday: "short", day: "numeric", month: "short", year: "numeric",
  });
}
