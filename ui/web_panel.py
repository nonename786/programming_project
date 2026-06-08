import json
import os
from pathlib import Path
from typing import Any, Dict, List

from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    render_template_string,
    request,
    send_file,
    stream_with_context,
)
from werkzeug.exceptions import RequestEntityTooLarge

from core.app_factory import build_agent, load_yaml_config
from core.attachments import (
    SOURCE_CAMERA,
    SOURCE_UPLOAD,
    build_user_message_content,
    build_visible_message,
    save_uploaded_files,
)
from core.message_history import MessageHistory
from core.plugin_loader import load_plugins
from core.tool_registry import TOOL_REGISTRY


PAGE_TEMPLATE = r"""
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mini-OpenClaw</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/highlight.js@11.9.0/styles/github.min.css">
<style>
:root {
  --bg:#f4f6f8; --sidebar:#1a1a2e; --sidebar-hover:#16213e;
  --panel:#fff; --border:#e2e8f0; --text:#1e293b; --muted:#64748b;
  --primary:#0f766e; --primary-dark:#115e59;
  --user-bg:#e0f2fe; --asst-bg:#f0fdf4; --tool-bg:#fffbeb; --thought-bg:#f5f3ff;
  --radius:12px; --shadow:0 4px 24px rgba(0,0,0,.06);
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Segoe UI","Microsoft YaHei",system-ui,sans-serif;background:var(--bg);color:var(--text);height:100vh;overflow:hidden}

/* Layout */
#app{display:flex;height:100vh}
#sidebar{width:280px;min-width:280px;background:var(--sidebar);color:#e2e8f0;display:flex;flex-direction:column;transition:margin-left .3s}
#sidebar.hidden{margin-left:-280px}
#main{flex:1;display:flex;flex-direction:column;min-width:0}

/* Sidebar */
.sb-header{padding:20px 16px 12px;border-bottom:1px solid rgba(255,255,255,.08)}
.sb-header h1{font-size:18px;color:#fff;margin-bottom:6px}
.sb-model{font-size:12px;color:#94a3b8;line-height:1.5}
.sb-new{margin:12px 16px;padding:10px;border:1px dashed rgba(255,255,255,.2);border-radius:var(--radius);background:transparent;color:#e2e8f0;cursor:pointer;font-size:14px;text-align:center;transition:background .2s}
.sb-new:hover{background:rgba(255,255,255,.08)}
.sb-section{padding:8px 16px;font-size:11px;text-transform:uppercase;color:#64748b;letter-spacing:.5px}
.session-list{flex:1;overflow-y:auto;padding:0 8px}
.session-item{padding:10px 12px;border-radius:8px;cursor:pointer;font-size:13px;color:#cbd5e1;margin-bottom:2px;transition:background .15s;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.session-item:hover{background:var(--sidebar-hover)}
.session-item.active{background:var(--primary);color:#fff}
.sb-footer{padding:12px 16px;border-top:1px solid rgba(255,255,255,.08);display:flex;gap:8px}
.sb-footer button{flex:1;padding:8px;border:none;border-radius:8px;background:rgba(255,255,255,.08);color:#e2e8f0;cursor:pointer;font-size:12px;transition:background .2s}
.sb-footer button:hover{background:rgba(255,255,255,.15)}

/* Chat header */
.chat-header{display:flex;align-items:center;gap:12px;padding:12px 20px;border-bottom:1px solid var(--border);background:var(--panel)}
.menu-btn{border:none;background:none;font-size:20px;cursor:pointer;padding:4px 8px;border-radius:6px}
.menu-btn:hover{background:var(--bg)}
.chat-header .title{flex:1;font-size:14px;color:var(--muted)}
.header-actions{display:flex;gap:6px}
.header-actions button{border:none;background:none;font-size:16px;cursor:pointer;padding:6px 10px;border-radius:8px;transition:background .15s}
.header-actions button:hover{background:var(--bg)}

/* Messages */
.messages{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:16px}

.msg{border-radius:var(--radius);padding:14px 16px;border:1px solid var(--border);box-shadow:var(--shadow);max-width:90%;animation:fadeIn .25s}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.msg.user{background:var(--user-bg);align-self:flex-end}
.msg.assistant{background:var(--asst-bg);align-self:flex-start}
.msg.tool{background:var(--tool-bg);align-self:flex-start;font-size:13px}
.msg.thought{background:var(--thought-bg);align-self:flex-start;font-style:italic;font-size:13px}
.msg.streaming{border:1px solid var(--primary);box-shadow:0 0 0 1px var(--primary)}

.msg-role{font-size:11px;font-weight:700;text-transform:uppercase;color:var(--muted);margin-bottom:6px;letter-spacing:.3px}
.msg-body{line-height:1.7;word-break:break-word}
.msg-body p{margin:0 0 8px}
.msg-body p:last-child{margin-bottom:0}
.msg-body pre{background:#f1f5f9;border:1px solid var(--border);border-radius:8px;padding:12px;overflow-x:auto;margin:8px 0;font-size:13px}
.msg-body code{font-family:Consolas,"Courier New",monospace;font-size:.9em}
.msg-body code:not(pre code){background:#f1f5f9;padding:2px 5px;border-radius:4px}
.msg-body table{border-collapse:collapse;width:100%;margin:8px 0}
.msg-body th,.msg-body td{border:1px solid var(--border);padding:6px 10px;text-align:left;font-size:13px}
.msg-body th{background:#f1f5f9}
.msg-body blockquote{border-left:3px solid var(--primary);margin:8px 0;padding:4px 12px;color:var(--muted)}
.msg-body img{max-width:100%;border-radius:8px;margin:8px 0;cursor:pointer}
.msg-body ul,.msg-body ol{padding-left:20px;margin:4px 0}

.msg-attachments{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.att-card{padding:8px 12px;border-radius:8px;border:1px solid var(--border);background:rgba(255,255,255,.7);font-size:12px;cursor:pointer;transition:background .15s}
.att-card:hover{background:#fff}
.att-card img{max-width:120px;border-radius:6px;margin-top:6px;display:block}
.att-badge{display:inline-block;padding:1px 6px;border-radius:99px;background:#dbeafe;color:#1d4ed8;font-size:10px;font-weight:700;margin-right:4px}
.att-meta{color:var(--muted);font-size:11px}

.msg-tools{margin-top:8px}
.tool-call-block{background:#f8fafc;border:1px solid var(--border);border-radius:8px;padding:8px 10px;margin-top:4px;font-size:12px}
.tool-call-block summary{cursor:pointer;font-weight:600;color:var(--muted)}
.tool-call-block pre{margin:4px 0 0;font-size:12px;background:transparent;border:none;padding:0}

/* Input area */
.input-area{padding:12px 20px 16px;border-top:1px solid var(--border);background:var(--panel)}
.file-preview{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px}
.file-preview:empty{display:none}
.fp-item{display:flex;align-items:center;gap:6px;padding:4px 10px;background:var(--bg);border-radius:20px;font-size:12px}
.fp-item button{border:none;background:none;cursor:pointer;font-size:14px;color:var(--muted)}
.fp-item img{width:24px;height:24px;object-fit:cover;border-radius:4px}
.input-row{display:flex;gap:8px;align-items:flex-end}
.icon-btn{display:flex;align-items:center;justify-content:center;width:38px;height:38px;border-radius:8px;cursor:pointer;font-size:18px;transition:background .15s;flex-shrink:0}
.icon-btn:hover{background:var(--bg)}
#prompt-input{flex:1;border:1px solid var(--border);border-radius:var(--radius);padding:8px 12px;font-size:14px;resize:none;min-height:38px;max-height:150px;line-height:1.5;font-family:inherit}
#prompt-input:focus{outline:none;border-color:var(--primary)}
#send-btn{padding:8px 20px;border:none;border-radius:var(--radius);background:var(--primary);color:#fff;font-weight:600;cursor:pointer;flex-shrink:0;transition:background .15s}
#send-btn:hover{background:var(--primary-dark)}
#send-btn:disabled{opacity:.5;cursor:default}

/* Plugin panel */
.panel-overlay{position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:100;display:flex;justify-content:flex-end}
.panel-slide{width:420px;max-width:100%;background:var(--panel);height:100%;display:flex;flex-direction:column;box-shadow:-8px 0 30px rgba(0,0,0,.1);animation:slideIn .2s}
@keyframes slideIn{from{transform:translateX(100%)}to{transform:none}}
.panel-header{display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid var(--border)}
.panel-header h2{font-size:16px}
.panel-header button{border:none;background:none;font-size:18px;cursor:pointer}
.panel-body{flex:1;overflow-y:auto;padding:16px 20px}
.tool-item{display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid #f1f5f9}
.tool-name{font-weight:600;font-size:13px}
.tool-desc{font-size:12px;color:var(--muted);margin-top:2px}
.toggle{position:relative;width:40px;height:22px;cursor:pointer}
.toggle input{opacity:0;width:0;height:0}
.toggle .slider{position:absolute;inset:0;background:#cbd5e1;border-radius:22px;transition:.2s}
.toggle .slider:before{content:"";position:absolute;left:3px;bottom:3px;width:16px;height:16px;background:#fff;border-radius:50%;transition:.2s}
.toggle input:checked+.slider{background:var(--primary)}
.toggle input:checked+.slider:before{transform:translateX(18px)}
.panel-actions{padding:16px 20px;border-top:1px solid var(--border)}
.panel-actions button{width:100%;padding:10px;border:none;border-radius:var(--radius);background:var(--primary);color:#fff;cursor:pointer;font-weight:600}

/* Preview modal */
.modal{position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:200;display:flex;align-items:center;justify-content:center;padding:20px}
.modal-inner{background:var(--panel);border-radius:var(--radius);max-width:90vw;max-height:90vh;overflow:auto;position:relative;padding:20px}
.modal-close{position:absolute;top:8px;right:12px;border:none;background:none;font-size:20px;cursor:pointer;z-index:1}
.modal-inner img{max-width:100%;border-radius:8px}
.modal-inner pre{max-height:70vh;overflow:auto}

/* Scrollbar */
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:#94a3b8}

/* Responsive */
@media(max-width:768px){
  #sidebar{position:fixed;z-index:50;height:100vh}
  #sidebar.hidden{margin-left:-280px}
  .msg{max-width:100%}
}
</style>
</head>
<body>
<div id="app">
  <aside id="sidebar">
    <div class="sb-header">
      <h1>Mini-OpenClaw</h1>
      <div class="sb-model">{{ provider }} / {{ model }}</div>
    </div>
    <div class="sb-new" onclick="newChat()">+ 新对话</div>
    <div class="sb-section">历史会话</div>
    <div class="session-list" id="session-list"></div>
    <div class="sb-footer">
      <button onclick="togglePluginPanel()">🔧 工具</button>
      <button onclick="saveSession()">💾 保存</button>
    </div>
  </aside>

  <main id="main">
    <div class="chat-header">
      <div class="menu-btn" onclick="toggleSidebar()">☰</div>
      <div class="title">会话: <span id="sid">{{ session_id }}</span></div>
      <div class="header-actions">
        <button onclick="clearSession()" title="清空会话">🗑️</button>
      </div>
    </div>
    <div class="messages" id="messages"></div>
    <div class="input-area">
      <div class="file-preview" id="file-preview"></div>
      <div class="input-row">
        <label class="icon-btn" for="file-input" title="上传文件">📎</label>
        <input type="file" id="file-input" multiple accept=".txt,.md,.py,.json,.csv,.yaml,.yml,.html,.css,.js,.ts,.xml,.sql,.log,.pdf,.doc,.docx,image/*" hidden>
        <label class="icon-btn" for="camera-input" title="拍照上传">📷</label>
        <input type="file" id="camera-input" accept="image/*" capture="environment" hidden>
        <div class="icon-btn" onclick="openImgGen()" title="AI 生成图片" style="border:none;background:none">🎨</div>
        <textarea id="prompt-input" placeholder="输入消息... (Ctrl+Enter 发送)" rows="1"></textarea>
        <button id="send-btn" onclick="sendMessage()">发送</button>
      </div>
    </div>
  </main>
</div>

<div id="plugin-panel" class="panel-overlay" style="display:none" onclick="if(event.target===this)closePluginPanel()">
  <div class="panel-slide">
    <div class="panel-header"><h2>工具 & 插件管理</h2><button onclick="closePluginPanel()">✕</button></div>
    <div class="panel-body" id="tools-list"></div>
    <div class="panel-actions"><button onclick="reloadPlugins()">🔄 重新加载插件</button></div>
  </div>
</div>

<div id="preview-modal" class="modal" style="display:none" onclick="if(event.target===this)closePreview()">
  <div class="modal-inner">
    <button class="modal-close" onclick="closePreview()">✕</button>
    <div id="modal-body"></div>
  </div>
</div>

<div id="imggen-modal" class="modal" style="display:none" onclick="if(event.target===this)closeImgGen()">
  <div class="modal-inner" style="width:480px;max-width:95vw">
    <button class="modal-close" onclick="closeImgGen()">✕</button>
    <h3 style="margin-bottom:14px">🎨 AI 图片生成</h3>
    <div style="margin-bottom:10px">
      <label style="font-size:13px;font-weight:600;display:block;margin-bottom:4px">图片描述</label>
      <textarea id="ig-prompt" rows="3" style="width:100%;border:1px solid var(--border);border-radius:8px;padding:8px;font-size:14px;resize:vertical;font-family:inherit" placeholder="描述你想生成的图片..."></textarea>
    </div>
    <div style="margin-bottom:14px">
      <label style="font-size:13px;font-weight:600;display:block;margin-bottom:4px">图片尺寸</label>
      <select id="ig-size" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:8px;font-size:14px">
        <option value="1024*1024">1024 x 1024（方形）</option>
        <option value="720*1280">720 x 1280（竖版）</option>
        <option value="1280*720">1280 x 720（横版）</option>
      </select>
    </div>
    <button id="ig-btn" onclick="doGenImg()" style="width:100%;padding:10px;border:none;border-radius:var(--radius);background:var(--primary);color:#fff;font-weight:600;cursor:pointer;font-size:14px">生成图片</button>
    <div id="ig-result" style="margin-top:14px;text-align:center"></div>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/highlight.js@11.9.0/highlight.min.js"></script>
<script>
const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);

marked.setOptions({
  highlight(code, lang) {
    if (lang && hljs.getLanguage(lang)) return hljs.highlight(code, {language: lang}).value;
    return hljs.highlightAuto(code).value;
  },
  breaks: true,
  gfm: true
});

let isStreaming = false;
let selectedFiles = [];

/* ── Messages ───────────────────────────── */
function loadMessages() {
  fetch("/api/messages").then(r=>r.json()).then(msgs => {
    const el = $("#messages");
    el.innerHTML = "";
    msgs.forEach(m => appendRenderedMsg(m));
    scrollBottom();
  });
}

function appendRenderedMsg(m) {
  const div = document.createElement("div");
  const role = m.role;
  div.className = "msg " + role;
  let html = `<div class="msg-role">${roleLabel(role)}</div>`;
  if (role === "assistant") {
    html += `<div class="msg-body">${renderMd(m.content || "")}</div>`;
  } else if (role === "tool") {
    html += `<div class="msg-body"><pre>${escHtml(m.content || "")}</pre></div>`;
  } else {
    html += `<div class="msg-body">${escHtml(m.content || "")}</div>`;
  }
  if (m.attachments && m.attachments.length) {
    html += `<div class="msg-attachments">`;
    m.attachments.forEach(a => {
      html += `<div class="att-card" onclick="previewAtt(this, '${escAttr(a.url||"")}', '${escAttr(a.kind||"")}', '${escAttr(a.name||"")}')">`;
      html += `<span class="att-badge">${a.kind_label||a.kind}</span> ${escHtml(a.name)}`;
      html += `<div class="att-meta">${a.mime_type||""} | ${formatSize(a.size)}</div>`;
      if (a.kind === "image" && a.url) html += `<img src="${a.url}" alt="${escAttr(a.name)}">`;
      html += `</div>`;
    });
    html += `</div>`;
  }
  if (m.tool_calls) {
    html += `<div class="msg-tools">`;
    (Array.isArray(m.tool_calls) ? m.tool_calls : []).forEach(tc => {
      const fn = tc.function || {};
      html += `<details class="tool-call-block"><summary>🔧 ${escHtml(fn.name||"")}</summary><pre>${escHtml(fn.arguments||"{}")}</pre></details>`;
    });
    html += `</div>`;
  }
  div.innerHTML = html;
  $("#messages").appendChild(div);
}

/* ── Streaming Chat ─────────────────────── */
async function sendMessage() {
  if (isStreaming) return;
  const input = $("#prompt-input");
  const prompt = input.value.trim();
  const files = [...selectedFiles];
  if (!prompt && !files.length) return;

  // Show user message
  appendRenderedMsg({role: "user", content: prompt, attachments: [], tool_calls: null});
  input.value = "";
  input.style.height = "38px";
  clearFilePreview();
  scrollBottom();

  isStreaming = true;
  $("#send-btn").disabled = true;

  const formData = new FormData();
  formData.append("prompt", prompt);
  files.forEach(f => formData.append("attachments", f));

  let currentEl = null;
  let currentText = "";

  try {
    const resp = await fetch("/chat", {method: "POST", body: formData});
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {stream: true});
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const payload = line.slice(6);
        if (payload === "[DONE]") continue;
        let evt;
        try { evt = JSON.parse(payload); } catch { continue; }

        if (evt.type === "token") {
          if (!currentEl) {
            currentEl = document.createElement("div");
            currentEl.className = "msg assistant streaming";
            currentEl.innerHTML = `<div class="msg-role">${roleLabel("assistant")}</div><div class="msg-body"></div>`;
            $("#messages").appendChild(currentEl);
          }
          currentText += evt.content;
          currentEl.querySelector(".msg-body").textContent = currentText;
          scrollBottom();
        } else if (evt.type === "thought_done") {
          if (currentEl) {
            currentEl.className = "msg thought";
            currentEl.querySelector(".msg-role").textContent = "💭 Thought";
            currentEl.querySelector(".msg-body").innerHTML = renderMd(evt.content);
            currentEl = null;
            currentText = "";
          }
        } else if (evt.type === "action") {
          const d = document.createElement("div");
          d.className = "msg tool";
          d.innerHTML = `<div class="msg-role">🔧 Action</div><div class="msg-body"><strong>${escHtml(evt.tool)}</strong><pre>${escHtml(JSON.stringify(evt.args, null, 2))}</pre></div>`;
          $("#messages").appendChild(d);
          scrollBottom();
        } else if (evt.type === "observation") {
          const d = document.createElement("div");
          d.className = "msg tool";
          let obsContent = evt.content;
          try {
            const parsed = JSON.parse(obsContent);
            if (parsed.image_path) {
              obsContent += `\n\n![generated](/workspace/${parsed.image_path})`;
            }
          } catch {}
          d.innerHTML = `<div class="msg-role">👁️ Observation</div><div class="msg-body">${renderMd(obsContent)}</div>`;
          $("#messages").appendChild(d);
          scrollBottom();
        } else if (evt.type === "answer_done") {
          if (currentEl) {
            currentEl.className = "msg assistant";
            currentEl.querySelector(".msg-role").textContent = roleLabel("assistant");
            currentEl.querySelector(".msg-body").innerHTML = renderMd(evt.content);
            currentEl = null;
            currentText = "";
          } else {
            appendRenderedMsg({role: "assistant", content: evt.content, attachments: [], tool_calls: null});
          }
          scrollBottom();
        } else if (evt.type === "error") {
          const d = document.createElement("div");
          d.className = "msg tool";
          d.innerHTML = `<div class="msg-role">❌ Error</div><div class="msg-body">${escHtml(evt.content)}</div>`;
          $("#messages").appendChild(d);
          scrollBottom();
        }
      }
    }
  } catch (err) {
    const d = document.createElement("div");
    d.className = "msg tool";
    d.innerHTML = `<div class="msg-role">❌ Error</div><div class="msg-body">请求失败: ${escHtml(err.message)}</div>`;
    $("#messages").appendChild(d);
  }

  isStreaming = false;
  $("#send-btn").disabled = false;
  scrollBottom();
}

/* ── Sessions ───────────────────────────── */
function loadSessions() {
  fetch("/api/sessions").then(r=>r.json()).then(list => {
    const el = $("#session-list");
    el.innerHTML = "";
    const curId = $("#sid").textContent;
    list.forEach(s => {
      const div = document.createElement("div");
      div.className = "session-item" + (s.session_id === curId ? " active" : "");
      div.textContent = `${s.session_id} | ${s.model || ""}`;
      div.title = `${s.start_time || ""}\n工具调用: ${s.tool_calls_count || 0}`;
      div.onclick = () => switchSession(s.session_id);
      el.appendChild(div);
    });
  });
}

async function switchSession(sid) {
  const r = await fetch("/resume", {method:"POST", headers:{"Content-Type":"application/x-www-form-urlencoded"}, body:"session_id="+encodeURIComponent(sid)});
  const d = await r.json();
  if (d.session_id) {
    $("#sid").textContent = d.session_id;
    loadMessages();
    loadSessions();
  }
}

async function saveSession() {
  const r = await fetch("/save", {method:"POST"});
  const d = await r.json();
  alert(d.message || "已保存");
  loadSessions();
}

async function clearSession() {
  if (!confirm("确定清空当前会话？")) return;
  await fetch("/clear", {method:"POST"});
  loadMessages();
}

async function newChat() {
  await fetch("/new", {method:"POST"});
  location.reload();
}

/* ── Plugin management ──────────────────── */
function togglePluginPanel() { $("#plugin-panel").style.display = "flex"; loadTools(); }
function closePluginPanel() { $("#plugin-panel").style.display = "none"; }

async function loadTools() {
  const r = await fetch("/api/tools");
  const tools = await r.json();
  const el = $("#tools-list");
  el.innerHTML = "";
  tools.forEach(t => {
    const div = document.createElement("div");
    div.className = "tool-item";
    div.innerHTML = `
      <div><div class="tool-name">${escHtml(t.name)}</div><div class="tool-desc">${escHtml(t.description)}</div></div>
      <label class="toggle"><input type="checkbox" ${t.enabled?"checked":""} onchange="toggleTool('${escAttr(t.name)}',this.checked)"><span class="slider"></span></label>`;
    el.appendChild(div);
  });
}

async function toggleTool(name, enabled) {
  await fetch(`/api/tools/${encodeURIComponent(name)}/toggle`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({enabled})});
}

async function reloadPlugins() {
  await fetch("/api/plugins/reload", {method:"POST"});
  loadTools();
  alert("插件已重新加载");
}

/* ── File upload preview ────────────────── */
function handleFiles(input) {
  const newFiles = Array.from(input.files);
  selectedFiles.push(...newFiles);
  renderFilePreview();
  input.value = "";
}

function renderFilePreview() {
  const el = $("#file-preview");
  el.innerHTML = "";
  selectedFiles.forEach((f, i) => {
    const item = document.createElement("div");
    item.className = "fp-item";
    let inner = "";
    if (f.type && f.type.startsWith("image/")) {
      const url = URL.createObjectURL(f);
      inner = `<img src="${url}">`;
    }
    inner += `<span>${escHtml(f.name)} (${formatSize(f.size)})</span>`;
    inner += `<button onclick="removeFile(${i})">✕</button>`;
    item.innerHTML = inner;
    el.appendChild(item);
  });
}

function removeFile(i) { selectedFiles.splice(i, 1); renderFilePreview(); }
function clearFilePreview() { selectedFiles = []; renderFilePreview(); }

document.getElementById("file-input").addEventListener("change", function(){ handleFiles(this); });
document.getElementById("camera-input").addEventListener("change", function(){ handleFiles(this); });

/* ── File preview modal ─────────────────── */
function previewAtt(el, url, kind, name) {
  if (!url) return;
  const body = $("#modal-body");
  if (kind === "image") {
    body.innerHTML = `<img src="${url}" alt="${escAttr(name)}" style="max-width:80vw;max-height:80vh">`;
  } else {
    body.innerHTML = `<p><strong>${escHtml(name)}</strong></p><p><a href="${url}" target="_blank" rel="noopener">下载文件</a></p>`;
    fetch(url).then(r=>r.text()).then(text => {
      body.innerHTML += `<pre><code>${hljs.highlightAuto(text.slice(0,50000)).value}</code></pre>`;
    }).catch(()=>{});
  }
  $("#preview-modal").style.display = "flex";
}
function closePreview() { $("#preview-modal").style.display = "none"; }

/* ── Image Generation ───────────────────── */
function openImgGen() {
  $("#imggen-modal").style.display = "flex";
  $("#ig-prompt").value = "";
  $("#ig-result").innerHTML = "";
}
function closeImgGen() { $("#imggen-modal").style.display = "none"; }

async function doGenImg() {
  var prompt = $("#ig-prompt").value.trim();
  if (!prompt) { alert("请输入图片描述"); return; }
  var size = $("#ig-size").value;
  var btn = $("#ig-btn");
  var res = $("#ig-result");
  btn.disabled = true;
  btn.textContent = "生成中...";
  res.innerHTML = '<p style="color:var(--muted)">⏳ 正在生成，请稍候...</p>';
  try {
    var r = await fetch("/api/generate-image", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({prompt: prompt, size: size})
    });
    var d = await r.json();
    if (d.success && d.image_path) {
      res.innerHTML = '<img src="/workspace/' + escAttr(d.image_path) + '" style="max-width:100%;border-radius:8px;cursor:pointer" onclick="previewImg(this.src)">'
        + '<p style="color:var(--muted);font-size:12px;margin-top:6px">' + escHtml(d.content || "") + '</p>';
    } else {
      res.innerHTML = '<p style="color:#ef4444">' + escHtml(d.error || "生成失败") + '</p>';
    }
  } catch(e) {
    res.innerHTML = '<p style="color:#ef4444">请求失败: ' + escHtml(e.message) + '</p>';
  }
  btn.disabled = false;
  btn.textContent = "生成图片";
}

/* ── Helpers ─────────────────────────────── */
function renderMd(text) {
  try {
    let html = marked.parse(text || "");
    html = html.replace(/<img\s+src="(\/workspace\/[^"]+)"/g, '<img src="$1" onclick="previewImg(this.src)"');
    return html;
  } catch { return escHtml(text); }
}
function previewImg(src) {
  $("#modal-body").innerHTML = `<img src="${src}" style="max-width:80vw;max-height:80vh">`;
  $("#preview-modal").style.display = "flex";
}
function escHtml(s) { const d = document.createElement("div"); d.textContent = s||""; return d.innerHTML; }
function escAttr(s) { return (s||"").replace(/"/g, "&quot;").replace(/'/g, "&#39;"); }
function roleLabel(r) { return {user:"👤 User",assistant:"🤖 Assistant",tool:"🔧 Tool"}[r]||r; }
function formatSize(v) { if(!v)return"0B"; if(v<1024)return v+"B"; if(v<1048576)return(v/1024).toFixed(1)+"KB"; return(v/1048576).toFixed(1)+"MB"; }
function scrollBottom() { const el=$("#messages"); el.scrollTop=el.scrollHeight; }
function toggleSidebar() { $("#sidebar").classList.toggle("hidden"); }

/* ── Keyboard shortcuts ──────────────────── */
$("#prompt-input").addEventListener("keydown", e => {
  if (e.ctrlKey && e.key === "Enter") { e.preventDefault(); sendMessage(); }
});
$("#prompt-input").addEventListener("input", function() {
  this.style.height = "38px";
  this.style.height = Math.min(this.scrollHeight, 150) + "px";
});

/* ── Init ─────────────────────────────────── */
loadMessages();
loadSessions();
</script>
</body>
</html>
"""


def _upload_root(config: Dict[str, Any]) -> str:
    return config.get("paths", {}).get(
        "web_upload_dir",
        os.path.join(config["paths"]["workspace_dir"], "uploads"),
    )


def _build_system_prompt(agent) -> str:
    config = load_yaml_config("config/config.yaml")
    base_prompt = config["agent"]["system_prompt"]
    return agent.long_term_memory.build_system_prompt(base_prompt)


def _visible_messages(agent) -> List[Dict[str, Any]]:
    visible: List[Dict[str, Any]] = []
    for msg in agent.message_history.get_messages():
        if msg.get("role") == "system":
            continue
        rendered = build_visible_message(msg.get("content", ""))
        attachments = []
        for item in rendered["attachments"]:
            att = dict(item)
            rp = att.get("relative_path", "")
            att["url"] = f"/uploads/{rp}" if rp else ""
            attachments.append(att)
        visible.append(
            {
                "role": msg.get("role", ""),
                "content": rendered["text"],
                "attachments": attachments,
                "tool_calls": msg.get("tool_calls"),
            }
        )
    return visible


def _collect_files(field_name: str) -> List[Any]:
    return [
        f
        for f in request.files.getlist(field_name)
        if f and (f.filename or "").strip()
    ]


def create_web_app(resume_session_id: str = "") -> Flask:
    config = load_yaml_config("config/config.yaml")
    upload_root = Path(_upload_root(config)).resolve()
    upload_root.mkdir(parents=True, exist_ok=True)
    workspace_root = Path(config["paths"]["workspace_dir"]).resolve()
    plugin_dir = config.get("plugins", {}).get("plugin_dir", "plugins")

    state = {"agent": build_agent(resume_session_id=resume_session_id)}

    app = Flask(__name__)
    app.secret_key = os.getenv(
        "FLASK_SECRET_KEY",
        config.get("web", {}).get("secret_key", "mini-openclaw-secret"),
    )
    app.config["MAX_CONTENT_LENGTH"] = int(
        config.get("web", {}).get("max_upload_bytes", 15 * 1024 * 1024)
    )

    @app.errorhandler(RequestEntityTooLarge)
    def _too_large(_exc):
        return jsonify({"error": "上传文件过大"}), 413

    @app.get("/")
    def index():
        agent = state["agent"]
        return render_template_string(
            PAGE_TEMPLATE,
            provider=agent.llm_client.get_provider_name(),
            model=agent.llm_client.get_model_name(),
            session_id=agent.session_manager.session_id,
            max_upload_mb=max(
                1, app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
            ),
        )

    @app.post("/chat")
    def chat():
        prompt = request.form.get("prompt", "").strip()
        upload_files = _collect_files("attachments")
        camera_files = _collect_files("camera_photos")

        if not prompt and not upload_files and not camera_files:
            return Response(
                "data: " + json.dumps({"type": "error", "content": "输入不能为空"}) + "\n\n"
                "data: [DONE]\n\n",
                mimetype="text/event-stream",
            )

        agent = state["agent"]
        sid = agent.session_manager.session_id

        attachments = save_uploaded_files(
            upload_files,
            upload_root=str(upload_root),
            session_id=sid,
            source_hint=SOURCE_UPLOAD,
        )
        attachments.extend(
            save_uploaded_files(
                camera_files,
                upload_root=str(upload_root),
                session_id=sid,
                source_hint=SOURCE_CAMERA,
            )
        )

        user_message = build_user_message_content(prompt, attachments)

        def generate():
            for event in agent.handle_user_message_stream(user_message):
                yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
            yield "data: [DONE]\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/clear")
    def clear_session():
        agent = state["agent"]
        agent.message_history = MessageHistory(
            system_prompt=_build_system_prompt(agent)
        )
        return jsonify({"status": "ok"})

    @app.post("/save")
    def save_session():
        agent = state["agent"]
        path = agent.session_manager.save_session(
            model_name=agent.llm_client.model,
            messages=agent.message_history.get_messages(),
        )
        return jsonify({"message": f"会话已保存: {path}"})

    @app.post("/resume")
    def resume_session():
        sid = request.form.get(
            "session_id",
            (request.get_json(silent=True) or {}).get("session_id", ""),
        ).strip()
        if not sid:
            return jsonify({"error": "请选择会话"}), 400
        state["agent"] = build_agent(resume_session_id=sid)
        agent = state["agent"]
        return jsonify(
            {
                "session_id": agent.session_manager.session_id,
                "loaded": agent.loaded_session_meta is not None,
            }
        )

    @app.post("/new")
    def new_chat():
        state["agent"] = build_agent()
        return jsonify(
            {"session_id": state["agent"].session_manager.session_id}
        )

    @app.get("/uploads/<path:relative_path>")
    def uploaded_file(relative_path: str):
        target = (upload_root / relative_path).resolve()
        if upload_root not in target.parents and target != upload_root:
            abort(404)
        if not target.is_file():
            abort(404)
        return send_file(target)

    @app.get("/workspace/<path:relative_path>")
    def workspace_file(relative_path: str):
        target = (workspace_root / relative_path).resolve()
        if workspace_root not in target.parents and target != workspace_root:
            abort(404)
        if not target.is_file():
            abort(404)
        return send_file(target)

    @app.get("/api/sessions")
    def api_sessions():
        return jsonify(
            state["agent"].session_manager.list_sessions(limit=30)
        )

    @app.get("/api/messages")
    def api_messages():
        return jsonify(_visible_messages(state["agent"]))

    @app.get("/api/tools")
    def api_tools():
        tools = []
        for t in TOOL_REGISTRY._tools.values():
            tools.append(
                {
                    "name": t.name,
                    "description": t.description,
                    "enabled": t.enabled,
                }
            )
        tools.sort(key=lambda x: (not x["enabled"], x["name"]))
        return jsonify(tools)

    @app.post("/api/tools/<name>/toggle")
    def toggle_tool(name: str):
        tool = TOOL_REGISTRY.get_tool(name)
        if tool is None:
            return jsonify({"error": f"工具 {name} 不存在"}), 404
        data = request.get_json(silent=True) or {}
        if "enabled" in data:
            tool.enabled = bool(data["enabled"])
        else:
            tool.enabled = not tool.enabled
        return jsonify({"name": name, "enabled": tool.enabled})

    @app.post("/api/plugins/reload")
    def reload_plugins_route():
        load_plugins(plugin_dir)
        return jsonify({"status": "ok"})

    @app.post("/api/generate-image")
    def api_generate_image():
        data = request.get_json(silent=True) or {}
        prompt = data.get("prompt", "").strip()
        size = data.get("size", "1024*1024")
        if not prompt:
            return jsonify({"success": False, "error": "请输入图片描述"}), 400

        from tools.image_gen_tools import generate_image as _gen_img

        result = _gen_img(prompt=prompt, size=size)
        return jsonify(result)

    @app.route('/download/<path:filename>')
    def download_file(filename):
        """下载文件"""
        workspace = Path(os.getenv("MINI_OPENCLAW_WORKSPACE", "workspace")).resolve()

        # 支持的文件类型和目录
        allowed_dirs = {
            'files': workspace,
            'images': workspace / 'images',
            'presentations': workspace / 'presentations',
        }

        # 解析文件路径
        for dir_type, dir_path in allowed_dirs.items():
            file_path = dir_path / filename
            if file_path.exists() and file_path.is_file():
                return send_file(
                    file_path,
                    as_attachment=True,
                    download_name=filename
                )

        return "文件不存在", 404

    return app


