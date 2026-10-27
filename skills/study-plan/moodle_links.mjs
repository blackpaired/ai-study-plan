#!/usr/bin/env node
// Reads video links from a Moodle course – through a separate Chromium window in which
// you log in yourself (only you type your password). Nothing is downloaded; only titles,
// links and the length (from the video player) are read.
//
// Usage:  node moodle_links.mjs login [url]          open the login window (stays open, login is kept)
//         node moodle_links.mjs videos <course-url> [--deep] [--json <file>]
//                read the course page and print all activities as JSON.
//                --deep: briefly open each player page and check whether it holds a video (and how long it is)
//         node moodle_links.mjs quit                 close the login window
//
// Profile: ~/.local/share/study-plan-browser (separate from your normal browser).
// Exit code 0 = ok, 1 = error, 2 = not logged in (run "login" first).
import { spawn, execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const PORT = 9233;
const PROFILE = join(homedir(), ".local/share/study-plan-browser");
const BASE = `http://127.0.0.1:${PORT}`;

function fail(text, code = 1) {
  console.error("ERROR: " + text);
  process.exit(code);
}

function browserBinary() {
  const mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
  for (const p of ["chromium", "chromium-browser", "google-chrome-stable", "google-chrome", "brave", "vivaldi"]) {
    try {
      return execFileSync("which", [p], { encoding: "utf8" }).trim();
    } catch {}
  }
  try {
    execFileSync("test", ["-x", mac]);
    return mac;
  } catch {}
  fail("No Chromium/Chrome found (e.g. sudo apt install chromium / brew install --cask chromium).");
}

async function running() {
  try {
    return (await fetch(BASE + "/json/version")).ok;
  } catch {
    return false;
  }
}

async function launch(url, headless = false) {
  mkdirSync(PROFILE, { recursive: true });
  const args = [`--user-data-dir=${PROFILE}`, `--remote-debugging-port=${PORT}`, "--remote-allow-origins=" + BASE,
    "--no-first-run", "--no-default-browser-check", "--restore-last-session"];
  if (headless) args.push("--headless=new");
  spawn(browserBinary(), [...args, url], { detached: true, stdio: "ignore" }).unref();
  for (let i = 0; i < 50; i++) {
    if (await running()) return;
    await new Promise(r => setTimeout(r, 200));
  }
  fail("The browser does not start.");
}

// Tiny CDP client (Chrome DevTools Protocol) without extra packages
async function newTab() {
  const t = await (await fetch(BASE + "/json/new?about:blank", { method: "PUT" })).json();
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  await new Promise((ok, no) => { ws.onopen = ok; ws.onerror = no; });
  let n = 0;
  const pending = new Map();
  const waiting = new Map();
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) {
      pending.get(m.id)(m);
      pending.delete(m.id);
    } else if (m.method && waiting.has(m.method)) {
      waiting.get(m.method)(m.params);
      waiting.delete(m.method);
    }
  };
  const send = (method, params = {}) => new Promise(ok => {
    const id = ++n;
    pending.set(id, ok);
    ws.send(JSON.stringify({ id, method, params }));
  });
  await send("Page.enable");
  return {
    async open(url) {
      const loaded = new Promise(ok => waiting.set("Page.loadEventFired", ok));
      await send("Page.navigate", { url });
      await Promise.race([loaded, new Promise(r => setTimeout(r, 20000))]);
      await new Promise(r => setTimeout(r, 800));
    },
    async evaluate(expression, frameId = null) {
      const p = { expression, returnByValue: true, awaitPromise: true };
      if (frameId) {
        // embedded players (other server): evaluate in an isolated world inside that frame
        p.contextId = (await send("Page.createIsolatedWorld", { frameId })).result.executionContextId;
      }
      const r = await send("Runtime.evaluate", p);
      if (r.result?.exceptionDetails) throw new Error(r.result.exceptionDetails.text);
      return r.result?.result?.value;
    },
    async frames() {
      const out = [];
      const walk = k => { for (const c of k.childFrames || []) { out.push(c.frame); walk(c); } };
      walk((await send("Page.getFrameTree")).result.frameTree);
      return out;
    },
    async close() {
      await fetch(BASE + "/json/close/" + t.id).catch(() => {});
      ws.close();
    },
  };
}

const READ_COURSE = `(() => {
  const secs = [...document.querySelectorAll('li.section, .course-section')];
  const roots = secs.length ? secs : [document];
  const out = [];
  for (const s of roots) {
    const section = (s.querySelector?.('.sectionname, h3.sectionname, h3')?.innerText || '').trim();
    for (const a of s.querySelectorAll('li.activity')) {
      const link = a.querySelector('a.aalink, a[href*="/mod/"]');
      const name = (a.querySelector('.instancename, .activityname')?.innerText || link?.innerText || '').split('\\n')[0].trim();
      const type = ([...a.classList].find(c => c.startsWith('modtype_')) || '').replace('modtype_', '');
      const info = (a.querySelector('.contentafterlink, .activity-altcontent, .description')?.innerText || '').trim();
      if (name) out.push({ section, name, type, url: link?.href || '', info: info.slice(0, 300) });
    }
  }
  return { title: document.title, location: location.href, activities: out };
})()`;

// Runs on the activity page and in every embedded frame. Opencast players (e.g. Paella,
// "watch.html?id=…") report the length through their search API; otherwise the <video> length.
const FIND_VIDEO = `(async () => {
  let length = null, title = null;
  const id = new URLSearchParams(location.search).get('id');
  if (id && /paella|engage|watch\\.html|\\/play\\//i.test(location.href)) {
    try {
      const r = await (await fetch('/search/episode.json?id=' + encodeURIComponent(id), { credentials: 'include' })).json();
      const mp = [].concat(r['search-results']?.result || r.result || [])[0]?.mediapackage;
      if (mp?.duration) { length = mp.duration / 1000; title = mp.title || null; }
    } catch (e) {}
  }
  const v = [...document.querySelectorAll('video')];
  for (const el of v) {
    if (length) break;
    if (!el.duration || isNaN(el.duration)) {
      el.preload = 'metadata';
      await new Promise(r => { el.onloadedmetadata = r; setTimeout(r, 4000); });
    }
    if (el.duration && isFinite(el.duration)) length = Math.max(length || 0, el.duration);
  }
  const player = /paella|engage|opencast|youtu|vimeo|panopto|kaltura|mediaserver|stream/i.test(location.href);
  return { video: v.length > 0 || player || !!length, seconds: length ? Math.round(length) : null, title, location: location.href };
})()`;

async function videos(courseUrl, deep, target) {
  if (!(await running())) await launch("about:blank", true);
  const tab = await newTab();
  try {
    await tab.open(courseUrl);
    const course = await tab.evaluate(READ_COURSE);
    if (/idp\.|login|SAML/i.test(course.location) && !/course\/view/.test(course.location)) {
      fail("Not logged in. First:  node moodle_links.mjs login " + courseUrl, 2);
    }
    if (deep) {
      for (const a of course.activities) {
        if (!a.url || !/^(lti|h5pactivity|page|url|opencast|kalvidres|panopto)$/.test(a.type)) continue;  // never open files (no downloads)
        try {
          await tab.open(a.url);
          let frames = [];
          for (let i = 0; i < 10; i++) {  // embedded players load a bit later
            frames = (await tab.frames()).filter(f => f.url && !f.url.startsWith("about:"));
            if (frames.some(f => !/\/mod\/lti\/launch\.php/.test(f.url)) || a.type !== "lti") break;
            await new Promise(r => setTimeout(r, 700));
          }
          const found = [await tab.evaluate(FIND_VIDEO)];
          for (const f of frames) found.push(await tab.evaluate(FIND_VIDEO, f.id).catch(() => null));
          const hits = found.filter(Boolean);
          const timed = hits.find(f => f.seconds);
          a.video = hits.some(f => f.video);
          a.minutes = timed ? Math.round(timed.seconds / 6) / 10 : null;
          if (timed?.title) a.playerTitle = timed.title;
        } catch (e) {
          a.error = String(e.message || e);
        }
      }
    }
    const json = JSON.stringify(course, null, 1);
    if (target) {
      writeFileSync(target, json);
      console.log(`${course.activities.length} activities saved: ${target}`);
    } else {
      console.log(json);
    }
  } finally {
    await tab.close();
  }
}

const [cmd, ...rest] = process.argv.slice(2);
if (cmd === "login") {
  const url = rest[0] || "about:blank";
  if (await running()) {
    const t = await (await fetch(BASE + "/json/version")).json();
    if (/Headless/i.test(t["User-Agent"] || "")) {
      fail("An invisible window is still running – run 'node moodle_links.mjs quit' first, then 'login' again.");
    }
    await fetch(BASE + "/json/new?" + url, { method: "PUT" });
  } else {
    await launch(url);
  }
  console.log("The login window is open. Log in to Moodle there and leave the window open.");
  console.log(`(Profile: ${PROFILE})`);
} else if (cmd === "videos") {
  if (!rest[0]) fail("Course link missing.");
  const i = rest.indexOf("--json");
  await videos(rest[0], rest.includes("--deep"), i >= 0 ? rest[i + 1] : null);
} else if (cmd === "quit") {
  if (await running()) {
    const t = await (await fetch(BASE + "/json/version")).json();
    const ws = new WebSocket(t.webSocketDebuggerUrl);
    await new Promise(ok => { ws.onopen = ok; });
    ws.send(JSON.stringify({ id: 1, method: "Browser.close" }));
    await new Promise(r => setTimeout(r, 500));
    console.log("Login window closed.");
  } else {
    console.log("No login window open.");
  }
  process.exit(0);
} else {
  console.log("Usage: node moodle_links.mjs login [url] | videos <course-url> [--deep] [--json <file>] | quit");
  process.exit(1);
}
process.exit(0);
