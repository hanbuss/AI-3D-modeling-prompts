var S = window.STARSHIP.state, API = window.STARSHIP;
function sleep(ms){ return new Promise(function(r){ setTimeout(r, ms); }); }
function px(id){ var p = S.byId[id]; return p ? Math.round(p.p*100)/100 : null; }
var out = [], fails = 0;
function chk(name, ok, info){ out.push((ok?'PASS':'FAIL')+' '+name+(info!==undefined?(' :: '+info):'')); if(!ok) fails++; }
/* 软渲染只有 3–5 fps，任何"某某毫秒时的中间态"都必须轮询取样，不能单点采样 */
function poll(ms, fn){
  var t0 = Date.now(), samples = [];
  return new Promise(function(res){
    (function step(){
      samples.push(fn());
      if (Date.now()-t0 >= ms) return res(samples);
      setTimeout(step, 30);
    })();
  });
}

function go(){
  return sleep(0).then(function(){
    chk('ready', window.__VIEWER_READY===true, 'parts='+S.parts.length+' tris='+S.triCount);
    chk('delay = order*8ms', S.parts.every(function(p){ return Math.abs(p.delay - p.order*8) < 0.01; }),
        S.parts.map(function(p){ return p.id+'(order '+p.order+')->'+Math.round(p.delay)+'ms'; }).join(' '));
    chk('flames built (3 engines x 3 layers + core)', S.flames.length===3 && S.flames[0].layers.length===3 && !!S.flames[0].core, 'n='+S.flames.length);
    chk('laser built', !!S.laser);
    API.analyze();
    return poll(2400, function(){
      return S.parts.filter(function(p){ return p.p>0.02 && p.p<0.98; }).length;
    });
  }).then(function(samples){
    var maxInflight = Math.max.apply(null, samples);
    chk('analyze 错峰飞行（真实存在中间态）', maxInflight >= 1, 'maxInflight='+maxInflight+'/'+S.parts.length);
    var seq = S.parts.slice().sort(function(a,b){return a.order-b.order;});
    chk('analyze 完成 → 全部 p=1', S.parts.every(function(p){ return p.p===1; }),
        seq.map(function(p){ return p.id+':'+px(p.id); }).join(' '));
    chk('explode 位移生效（fore +X）', S.byId.hull_fore.node.position.x > S.byId.hull_fore.base.x + 3,
        'dx='+(S.byId.hull_fore.node.position.x-S.byId.hull_fore.base.x).toFixed(2)+'m');
    chk('explode 上抬生效（Blender Z→glTF Y 换算正确）',
        S.byId.hull_mid.node.position.y > S.byId.hull_mid.base.y + 0.8,
        'dy='+(S.byId.hull_mid.node.position.y-S.byId.hull_mid.base.y).toFixed(2)+'m');
    API.assemble();
    return poll(2600, function(){ return S.parts.filter(function(p){return p.p>0;}).length; });
  }).then(function(){
    chk('重新组装 → 全部归位 p=0', S.parts.every(function(p){ return p.p===0; }),
        S.parts.map(function(p){return p.id+':'+px(p.id);}).join(' '));
    API.setProgress(0.5, false);
    chk('拆解滑杆 50% → 全部半程', S.parts.every(function(p){ return p.p>0 && p.p<1; }),
        S.parts.map(function(p){return p.id+':'+px(p.id);}).join(' '));
    API.setProgress(0, false);
    API.select('hull_mid');
    var op = S.byId.hull_fore.mats[0].opacity;
    chk('点单件 → 其余半透明 0.18', S.dimmed===true && Math.abs(op-0.18)<0.001, 'other.opacity='+op);
    chk('信息卡显示 中英名/note/三角面',
        document.querySelector('#card').hidden===false &&
        document.querySelector('#card-en').textContent.length>0 &&
        document.querySelector('#card-note').textContent.length>4 &&
        document.querySelector('#card-tris').textContent !== '0',
        document.querySelector('#card-zh').textContent+' | '+document.querySelector('#card-en').textContent+' | '+document.querySelector('#card-tris').textContent+' tris');
    API.clearSel();
    chk('点空白 → 恢复不透明', S.dimmed===false && Math.abs(S.byId.hull_fore.mats[0].opacity-1)<0.001,
        'opacity='+S.byId.hull_fore.mats[0].opacity);
    API.onlyGroup('hull_mid');
    return poll(3000, function(){ return S.parts.some(function(p){return !!p.anim;}) ? 1 : 0; });
  }).then(function(samples){
    chk('只拆这组 → 仅该组飞出', px('hull_mid')===1 && px('hull_fore')===0 && px('hull_aft')===0,
        'mid='+px('hull_mid')+' fore='+px('hull_fore')+' aft='+px('hull_aft'));
    API.assemble(); API.flameIntensity(1.0);
    return sleep(1800);
  }).then(function(){
    var phases = {}, levels = [];
    API.fireLaser();
    return poll(1500, function(){
      phases[S.laser.phase] = 1;
      levels.push(S.laser.level);
      return S.laser.phase;
    }).then(function(){
      chk('激光相位机（蓄能→全亮→衰减 全部出现过）', !!phases.full && !!phases.decay,
          'phases='+Object.keys(phases).join('>'));
      chk('激光亮度先升后降', Math.max.apply(null, levels) > 0.9 && levels[levels.length-1] < 0.5,
          'peak='+Math.max.apply(null, levels).toFixed(2)+' tail='+levels[levels.length-1].toFixed(2));
      chk('激光束/端球/点光可见', S.laser.core.mesh.visible && S.laser.tip.visible && S.laser.light.intensity>0,
          'light='+S.laser.light.intensity.toFixed(1));
    });
  }).then(function(){
    API.view('top');
    return sleep(900);
  }).then(function(){
    chk('机位预设 top（相机在 +Y）', Math.abs(S.cam.position.y) > Math.abs(S.cam.position.z),
        'cam=('+S.cam.position.toArray().map(function(v){return v.toFixed(1);}).join(',')+')');
    var d = API.diag();
    out.push('DIAG '+JSON.stringify({draws:d.draws, rtris:d.rtris, fps:d.fps, tris:d.tris, parts:d.parts, errors:d.errors}));
    out.push(fails===0 ? 'ALL PASS ('+out.length+' checks)' : ('FAILS='+fails));
    return out.join('\n');
  });
}
return go();
