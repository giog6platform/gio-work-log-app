// Minimal static server with HTTP Basic Auth. No dependencies.
const http = require("http");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const PORT = process.env.PORT || 3000;
const USER = process.env.SITE_USER || "gio";
const PASS = process.env.SITE_PASSWORD;
const ROOT = path.join(__dirname, "public");
// Task data is kept out of git: a Render secret file in production, data/out locally.
const DATA_FILE = process.env.DATA_FILE || ["/etc/secrets/data.json", path.join(__dirname, "data/out/data.json")].find(f => fs.existsSync(f));
const TYPES = { ".html": "text/html; charset=utf-8", ".json": "application/json", ".svg": "image/svg+xml", ".js": "text/javascript", ".css": "text/css" };

if (!PASS) {
  console.error("SITE_PASSWORD is not set; refusing to start.");
  process.exit(1);
}

function same(a, b) {
  const x = Buffer.from(a), y = Buffer.from(b);
  return x.length === y.length && crypto.timingSafeEqual(x, y);
}

function authorized(req) {
  const [scheme, value] = (req.headers.authorization || "").split(" ");
  if (scheme !== "Basic" || !value) return false;
  const [u, ...rest] = Buffer.from(value, "base64").toString().split(":");
  return same(u, USER) && same(rest.join(":"), PASS);
}

http.createServer((req, res) => {
  const headers = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow",
    "Cache-Control": "no-store",
  };
  if (req.url === "/healthz") { res.writeHead(200, headers); return res.end("ok"); }
  if (!authorized(req)) {
    res.writeHead(401, { ...headers, "WWW-Authenticate": 'Basic realm="Work Log", charset="UTF-8"' });
    return res.end("Authentication required");
  }
  let p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  if (p === "/") p = "/index.html";
  const file = p === "/data.json" ? DATA_FILE : path.normalize(path.join(ROOT, p));
  if (!file || (file !== DATA_FILE && !file.startsWith(ROOT + path.sep))) { res.writeHead(404, headers); return res.end("Not found"); }
  fs.readFile(file, (err, buf) => {
    if (err) { res.writeHead(404, headers); return res.end("Not found"); }
    res.writeHead(200, { ...headers, "Content-Type": TYPES[path.extname(file)] || "application/octet-stream" });
    res.end(buf);
  });
}).listen(PORT, () => console.log(`Work Log on :${PORT}`));
