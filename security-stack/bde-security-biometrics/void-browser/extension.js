"use strict";
const { window, commands, Uri, ViewColumn } = require("vscode");

const VIEW_TYPE = "bdeMagicBrowser.view";
const TITLE = "BDE Magic Browser";

function getHtml() {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'nonce-__NONCE__'; connect-src http://localhost:4123 https:;">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${TITLE}</title>
<style>
  body { margin:0; background:#0b0c10; color:#c5c6c7; font:13px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace; }
  #bar { padding:10px 12px; background:#0f1824; border-bottom:1px solid #1f2833; display:flex; gap:8px; align-items:center; }
  #url { flex:1; background:#0b0c10; color:#66fcf1; border:1px solid #1f2833; border-radius:6px; padding:6px 10px; }
  #go { background:#45a29e; color:#0b0c10; border:none; border-radius:6px; padding:6px 10px; cursor:pointer; font-weight:700; }
  #bde { background:#e94560; color:#0b0c10; border:none; border-radius:6px; padding:6px 10px; cursor:pointer; font-weight:700; }
  #log { padding:10px; white-space:pre-wrap; word-break:break-all; }
</style>
</head>
<body>
<div id="bar">
  <input id="url" placeholder="https://my.replika.ai" value="https://my.replika.ai">
  <button id="go">Go</button>
  <button id="bde">BDE Verify</button>
</div>
<div id="log">BDE Magic Browser ready.\n</div>
<script nonce="__NONCE__">
  const logEl = document.getElementById('log');
  const urlEl = document.getElementById('url');
  const log = (...a) => { logEl.textContent += a.join(' ') + '\\n'; logEl.scrollTop = logEl.scrollHeight; };
  const acquire = () => vscode && vscode.postMessage ? vscode : (window.chrome || window.browser);
  document.getElementById('go').onclick = () => {
    const url = urlEl.value.trim();
    log('navigate:', url);
    try { acquire().runtime?.sendMessage?.({type:'navigate', url}); } catch {}
  };
  document.getElementById('bde').onclick = async () => {
    log('bde: verify start');
    try {
      const resp = await fetch('http://localhost:4123/', {method:'GET', mode:'cors'});
      const text = await resp.text();
      log('bde status:', text);
    } catch (e) {
      log('bde error:', e?.message || e);
    }
  };
  log('webview mounted');
</script>
</body>
</html>`;
}

function open() {
  const panel = window.createWebviewPanel(VIEW_TYPE, TITLE, { viewColumn: ViewColumn.Active, preserveFocus: false }, {
    enableScripts: true,
    retainContextWhenHidden: true,
    localResourceRoots: []
  });
  panel.webview.html = getHtml().replace(/__NONCE__/g, Date.now().toString(36));
  panel.webview.onDidReceiveMessage((msg) => {
    if (!msg || !msg.type) return;
    if (msg.type === 'navigate') {
      log('browser navigate:', msg.url);
    }
  });
  log('opened BDE Magic Browser');
}

function log(msg) {
  console.log(`[bde-magic-browser] ${msg}`);
}

function activate() {
  const d = commands.registerCommand('bdeMagicBrowser.open', open);
  log('activated');
  return { dispose: () => d.dispose() };
}

exports.activate = activate;
