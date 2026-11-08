// starship/tools/shot.js — headless Chrome + CDP：等页面 ready、跑一段 JS、截精确尺寸图，并抓 console/pageerror
//
// 用法:
//   node tools/shot.js <url> <out.png> [w] [h] [waitMs] [--pre=js] [--post=js] [--click=selector]
//
//   --pre       ready 之后、截图之前执行的 JS（awaitPromise），用来摆姿态：拆解 / 点火 / 发射
//   --prefile   同上，但从文件读（长脚本用这个，免转义）
//   --after     执行 pre 后额外等待的毫秒（默认 1200）
//   --post  --pre 执行完再等的额外毫秒（默认 waitMs）
//
// 例子:
//   node tools/shot.js 'file:///<repo>/03-aegis-7-starship/viewer/index.html#view=hero' viewer/shots/01_assembled.png 1600 1000 1200
//   node tools/shot.js ... 02_exploded.png 1600 1000 1600 --pre='STARSHIP.analyze(1)'
//
// 退出码 0 = 截图成功且 console 无 error；2 = 有 console error；1 = 流程失败。
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const CHROME = process.env.CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe';

const argv = process.argv.slice(2);
const flags = {};
const pos = [];
for (const a of argv) {
  const m = a.match(/^--([^=]+)=(.*)$/);
  if (m) flags[m[1]] = m[2]; else if (a.startsWith('--')) flags[a.slice(2)] = '1'; else pos.push(a);
}

const url = pos[0];
const out = pos[1] || 'shot.png';
const W = parseInt(pos[2] || '1600', 10);
const H = parseInt(pos[3] || '1000', 10);
const readyWait = parseInt(pos[4] || '1500', 10);
const PORT = 9400 + Math.floor(Math.random() * 400);
const userDir = path.join(os.tmpdir(), 'cdp-ship-' + PORT);

if (!url) { console.error('usage: node tools/shot.js <url> <out.png> [w] [h] [waitMs] [--pre=js]'); process.exit(1); }
if (!fs.existsSync(CHROME)) { console.error('chrome not found: ' + CHROME); process.exit(1); }

const proc = spawn(CHROME, [
  '--headless=new',
  '--remote-debugging-port=' + PORT,
  '--allow-file-access-from-files',
  '--window-size=' + W + ',' + H,
  '--hide-scrollbars',
  '--force-device-scale-factor=1',
  '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
  '--no-first-run', '--no-default-browser-check', '--disable-gpu-sandbox',
  '--user-data-dir=' + userDir,
  'about:blank',
], { stdio: 'ignore' });

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function main() {
  let wsUrl = null;
  for (let i = 0; i < 100; i++) {
    try {
      const r = await fetch('http://127.0.0.1:' + PORT + '/json/list');
      const list = await r.json();
      const page = list.find(t => t.type === 'page');
      if (page && page.webSocketDebuggerUrl) { wsUrl = page.webSocketDebuggerUrl; break; }
    } catch (e) { }
    await sleep(150);
  }
  if (!wsUrl) throw new Error('CDP not reachable on ' + PORT);

  const ws = new WebSocket(wsUrl);
  let id = 0;
  const pending = new Map();
  const logs = [];     // 全部 console
  const errors = [];   // error 级 + 异常

  ws.addEventListener('message', (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
      return;
    }
    if (msg.method === 'Runtime.consoleAPICalled') {
      const text = msg.params.args.map(a => a.value !== undefined ? a.value
        : (a.description || JSON.stringify(a.preview || {}))).join(' ');
      logs.push('[' + msg.params.type + '] ' + text);
      if (msg.params.type === 'error') errors.push('[console.error] ' + text);
    } else if (msg.method === 'Runtime.exceptionThrown') {
      const d = msg.params.exceptionDetails;
      const t = (d.exception && (d.exception.description || d.exception.value)) || d.text;
      errors.push('[exception] ' + t);
    } else if (msg.method === 'Log.entryAdded') {
      const e = msg.params.entry;
      logs.push('[' + e.level + '] ' + e.text);
      if (e.level === 'error') errors.push('[log] ' + e.text + (e.url ? ' @' + e.url : ''));
    }
  });

  await new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', rej); });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const mid = ++id;
    pending.set(mid, { resolve, reject });
    ws.send(JSON.stringify({ id: mid, method, params }));
  });
  const evalJs = async (expr) => {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (r && r.exceptionDetails) errors.push('[eval] ' + (r.exceptionDetails.exception?.description || r.exceptionDetails.text));
    return r && r.result ? r.result.value : undefined;
  };

  await send('Page.enable');
  await send('Runtime.enable');
  await send('Log.enable');
  await send('Emulation.setDeviceMetricsOverride', {
    width: W, height: H, deviceScaleFactor: 1, mobile: W < 860,
  });
  await send('Page.navigate', { url });

  // 等 __VIEWER_READY（模型 + 环境贴图就绪 + 首帧）
  const t0 = Date.now();
  let ready = false;
  while (Date.now() - t0 < 60000) {
    await sleep(250);
    try { if (await evalJs('window.__VIEWER_READY === true')) { ready = true; break; } } catch (e) { }
  }
  await sleep(readyWait);

  if (flags.prefile) {
    const src = fs.readFileSync(flags.prefile, 'utf8');
    const r = await evalJs('(function(){' + src + '})()');
    if (r !== undefined) console.log('PREFILE', typeof r === 'string' ? r : JSON.stringify(r));
  }
  if (flags.pre) await evalJs(decodeURIComponent(flags.pre));
  if (flags.click) {
    const sel = flags.click;
    await evalJs(`(()=>{const el=document.querySelector(${JSON.stringify(sel)}); if(el){el.click(); return 2} return 1})()`);
  }
  if (flags.pre || flags.click) await sleep(parseInt(flags.after || '1200', 10));
  if (flags.post) await evalJs(decodeURIComponent(flags.post));

  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
  fs.writeFileSync(out, Buffer.from(shot.data, 'base64'));

  const state = await evalJs(`JSON.stringify(window.STARSHIP ? window.STARSHIP.diag() : {
    ready: window.__VIEWER_READY===true, err: window.__VIEWER_ERROR||null, title: document.title })`);

  console.log('READY', ready, 'MS', Date.now() - t0);
  console.log('STATE', state);
  if (logs.length) console.log('CONSOLE\n' + logs.slice(-30).join('\n'));
  if (errors.length) console.log('ERRORS(' + errors.length + ')\n' + errors.join('\n'));
  console.log('SHOT', path.resolve(out));
  ws.close();
  proc.kill();
  process.exit(errors.length ? 2 : 0);
}

main().catch(async (e) => {
  console.error('FAIL', e.message);
  try { proc.kill(); } catch (_) { }
  process.exit(1);
});
