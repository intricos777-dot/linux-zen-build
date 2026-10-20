// Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
// ==UserScript==
// @name         BDE Biometric Bridge
// @namespace    http://localhost:4123
// @version      1.0.0
// @description  Bridges Tampermonkey biometric challenge to local BDE daemon.
// @author       Living Sin
// @match        https://my.replika.ai/*
// @match        https://my.replika.com/*
// @connect      localhost
// @grant        GM_xmlhttpRequest, GM_addStyle
// @run-at       document-end
// ==/UserScript==

(function () {
  "use strict";
  const API = "http://localhost:4123";
  GM_addStyle(`#bde-panel{position:fixed;bottom:12px;right:12px;width:320px;max-height:60vh;background:#0b0c10;color:#c5c6c7;font:13px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace;border:1px solid #45a29e;border-radius:10px;box-shadow:0 8px 28px rgba(0,0,0,.6);z-index:2147483647;display:none;flex-direction:column;overflow:hidden}`);
  const panel = Object.assign(document.createElement("div"), {id:"bde-panel"});
  panel.innerHTML = `<div style="padding:10px 12px;background:#0f1824;border-bottom:1px solid #1f2833;display:flex;justify-content:space-between;align-items:center"><div style="color:#66fcf1;font-weight:700">BDE biometric bridge</div><button id="bde-close" style="background:#45a29e;color:#0b0c10;border:none;border-radius:6px;padding:4px 8px;cursor:pointer">Close</button></div><pre id="bde-log" style="margin:0;padding:10px;overflow:auto;max-height:50vh"></pre>`;
  document.documentElement.appendChild(panel);
  const log = (...a) => { const el = document.getElementById("bde-log"); if (el) el.textContent += a.join(" ") + "\n"; };
  const show = () => panel.classList.add("visible");
  document.getElementById("bde-close").onclick = () => panel.remove();
  GM_xmlhttpRequest({method:"GET", url: API + "/", onload: r => { log("daemon:", r.responseText); show(); }});
  GM_xmlhttpRequest({method:"POST", url: API + "/", headers: {"Content-Type":"application/json"}, data: JSON.stringify({action:"verify", identity:"replika", payload:"tampermonkey-challenge"}), onload: r => log("verify:", r.responseText)});
})();
