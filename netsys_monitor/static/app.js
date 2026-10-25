const $=s=>document.querySelector(s), $$=s=>document.querySelectorAll(s);
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const C=2*Math.PI*50;
const RM=matchMedia('(prefers-reduced-motion: reduce)').matches;
const VIEWS=['net','sys','dev','alert'];
let INFO={},HL=120,lastTs=0,gpuSig='',procSort='cpu',lastData=null,acTab='act',prevIds=null,pushT=0,cur='net',devScanned=false,devSig='',scanSig='',lastScan=[];
const COL={};
const H={cpu:[],ram:[],gpu:[],down:[],up:[],dr:[],dw:[],ping:[],sig:[]};
const hov={x:null}, heroSt={max:null};
const led={cv:null,gl:null,c:null,g:null,w:0,h:0,dpr:1,phase:0,mbps:0};

/* ---------- waktu WIB (Asia/Jakarta, UTC+7) ---------- */
const TZ='Asia/Jakarta';
const fmtT=new Intl.DateTimeFormat('en-GB',{timeZone:TZ,hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'});
const fmtD=new Intl.DateTimeFormat('id-ID',{timeZone:TZ,weekday:'long',day:'numeric',month:'short',year:'numeric'});
const fmtD2=new Intl.DateTimeFormat('id-ID',{timeZone:TZ,day:'numeric',month:'short',year:'numeric'});
const tm=ts=>fmtT.format(new Date(ts*1000));
const dt=ts=>{const d=new Date(ts*1000);return fmtD2.format(d)+' '+fmtT.format(d)+' WIB'};

/* ---------- privasi: samarkan IP, MAC, nama PC ---------- */
let priv=false;try{priv=localStorage.getItem('netsys.priv')==='1'}catch(e){}
const IPV4=/\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b/g, PUB_OK=new Set(['1.1.1.1','8.8.8.8','9.9.9.9','208.67.222.222','94.140.14.14']), MACRE=/\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b/g;
function mIP(ip){if(PUB_OK.has(ip))return ip;const p=ip.split('.').map(Number);
  const lan=p[0]===10||p[0]===127||(p[0]===192&&p[1]===168)||(p[0]===172&&p[1]>=16&&p[1]<=31)||(p[0]===169&&p[1]===254);
  return lan?`${p[0]}.•••.•••.${p[3]}`:'•••.•••.•••.•••'}
const P=s=>{s=String(s);return priv?s.replace(IPV4,m=>mIP(m)).replace(MACRE,m=>PM(m)):s};
const PN=s=>priv?'••••••':(s||'-');
const PM=m=>!m?'-':priv?'••:••:••:••:••:'+String(m).slice(-2):m;
const PR=r=>{if(!priv)return r;const s=String(r);if(/\d+\.\d+\.\d+\.\d+/.test(s))return P(s);const i=s.lastIndexOf(':');return '••••:••••:••••'+(i>0?s.slice(i):'')};
const esc=s=>String(P(s)).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function applyPriv(on,save){priv=on;document.body.classList.toggle('priv',on);
  $$('[data-priv]').forEach(b=>{b.classList.toggle('on',on);b.querySelector('span').textContent=on?'IP disembunyikan':'Sembunyikan IP';
    const ic=b.querySelector('[data-ic]');ic.innerHTML='';ic.dataset.ic=on?'eyeoff':'eye';mountIcons(b)});
  if(save){try{localStorage.setItem('netsys.priv',on?'1':'0')}catch(e){}}
  devSig='';scanSig='';if(INFO.host)$('#hostos').innerHTML=`<b>${esc(PN(INFO.host))}</b> · ${esc(INFO.os)}`;
  if(lastData)render(lastData)}

/* ---------- icons ---------- */
const IC={
 cpu:'<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3"/>',
 gpu:'<rect x="2" y="6" width="20" height="11" rx="2"/><circle cx="9" cy="11.5" r="2.5"/><path d="M15 9.5h3M15 13.5h3M6 17v2M10 17v2"/>',
 mem:'<rect x="2" y="7" width="20" height="10" rx="1.5"/><path d="M6 11v2M10 11v2M14 11v2M18 11v2M6 17v2M10 17v2M14 17v2M18 17v2"/>',
 disk:'<path d="M22 12H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/><path d="M6 16h.01M10 16h.01"/>',
 db:'<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.7 4 3 9 3s9-1.3 9-3V5M3 12c0 1.7 4 3 9 3s9-1.3 9-3"/>',
 pulse:'<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
 chart:'<path d="M3 3v18h18"/><path d="M7 16v-5M12 16V7M17 16v-8"/>',
 gauge:'<path d="M12 14l4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
 server:'<rect x="2" y="3" width="20" height="8" rx="2"/><rect x="2" y="13" width="20" height="8" rx="2"/><path d="M6 7h.01M6 17h.01"/>',
 list:'<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
 link:'<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
 bell:'<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
 bellOff:'<path d="M13.73 21a2 2 0 0 1-3.46 0M18.63 13A17.9 17.9 0 0 1 18 8M6.26 6.26A5.86 5.86 0 0 0 6 8c0 7-3 9-3 9h14M18 8a6 6 0 0 0-9.33-5"/><path d="M1 1l22 22"/>',
 wifi:'<path d="M5 12.55a11 11 0 0 1 14 0M1.42 9a16 16 0 0 1 21.16 0M8.53 16.11a6 6 0 0 1 6.95 0M12 20h.01"/>',
 thermo:'<path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z"/>',
 battery:'<rect x="2" y="7" width="16" height="10" rx="2"/><path d="M22 11v2M6 10v4"/>',
 check:'<path d="M20 6L9 17l-5-5"/>',
 alert:'<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><path d="M12 9v4M12 17h.01"/>',
 eye:'<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
 eyeoff:'<path d="M17.94 17.94A10.07 10.07 0 0 1 12 19c-7 0-10-7-10-7a18.5 18.5 0 0 1 5.06-5.94M9.9 4.24A9.1 9.1 0 0 1 12 4c7 0 10 7 10 7a18.5 18.5 0 0 1-2.16 3.19M14.12 14.12a3 3 0 1 1-4.24-4.24"/><path d="M1 1l22 22"/>',
 trash:'<path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6"/>',
 edit:'<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
 plus:'<path d="M12 5v14M5 12h14"/>',
 radar:'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><path d="M12 12l6-6"/>',
 phone:'<rect x="7" y="2" width="10" height="20" rx="2.5"/><path d="M11 18h2"/>',
 laptop:'<rect x="4" y="5" width="16" height="11" rx="1.5"/><path d="M2 19h20"/>',
 tablet:'<rect x="4" y="2" width="16" height="20" rx="2"/><path d="M11 18h2"/>',
 tv:'<rect x="2" y="5" width="20" height="13" rx="2"/><path d="M8 21h8M12 18v3"/>',
 gamepad:'<rect x="2" y="6" width="20" height="12" rx="5"/><path d="M7 10v4M5 12h4M15.5 11h.01M18 13h.01"/>',
 router:'<rect x="3" y="14" width="18" height="6" rx="2"/><path d="M7 17h.01M11 17h.01M12 14V9M8 10a5.7 5.7 0 0 1 8 0M5.5 7.5a9.2 9.2 0 0 1 13 0"/>',
 monitor:'<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>',
 info:'<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
 globe:'<circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
 route:'<circle cx="6" cy="19" r="3"/><path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"/><circle cx="18" cy="5" r="3"/>',
 shield:'<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
 x:'<path d="M18 6 6 18M6 6l12 12"/>',
 power:'<path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><path d="M12 2v10"/>',
 gear:'<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h0a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>'
};
const TYPES=[['phone','HP / Smartphone'],['laptop','Laptop / PC'],['tablet','Tablet'],['tv','TV / Streaming'],['console','Konsol game'],['iot','Perangkat IoT'],['router','Router / Access point'],['other','Lainnya']];
const DEVICON={phone:'phone',laptop:'laptop',tablet:'tablet',tv:'tv',console:'gamepad',iot:'cpu',router:'router',other:'server'};
function mountIcons(root){(root||document).querySelectorAll('button[title]:not([aria-label])').forEach(b=>b.setAttribute('aria-label',b.title));
  (root||document).querySelectorAll('[data-ic]').forEach(e=>{if(e.firstChild)return;
  e.innerHTML=`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${IC[e.dataset.ic]||IC.alert}</svg>`})}

/* ---------- format ---------- */
function fB(b,d=1){if(b==null||isNaN(b))return '-';const u=['B','KB','MB','GB','TB'];let i=0;while(b>=1024&&i<4){b/=1024;i++}return b.toFixed(i?d:0)+' '+u[i]}
const fMbps=bps=>bps*8/1e6, fMBs=bps=>bps/1e6;
const lvl=p=>p>=90?COL.bad:p>=70?COL.warn:null;
function fUp(sec){const d=Math.floor(sec/86400),h=Math.floor(sec%86400/3600),m=Math.floor(sec%3600/60);return (d?d+'h ':'')+h+'j '+m+'m'}
function fDur(s){s=Math.max(0,Math.floor(s));if(s<60)return s+' d';if(s<3600)return Math.floor(s/60)+' m '+String(s%60).padStart(2,'0')+' d';return Math.floor(s/3600)+' j '+String(Math.floor(s%3600/60)).padStart(2,'0')+' m'}
const num=(v,d=1)=>v==null?'-':Number(v).toFixed(d);
const avg=a=>{const s=a.slice(-60).filter(v=>v!=null);return s.length?s.reduce((x,y)=>x+y,0)/s.length:0};

/* ---------- angka beranimasi (tween) ---------- */
const TW=new Map();
function setNum(sel,val,dec=0){const el=typeof sel==='string'?$(sel):sel;if(!el)return;
  let t=TW.get(el);if(!t){t={cur:val,tgt:val,dec};TW.set(el,t);el.textContent=val.toFixed(dec);return}
  t.tgt=val;t.dec=dec;if(RM){t.cur=val;el.textContent=val.toFixed(dec)}}
function twFrame(dt_){const k=1-Math.pow(.001,dt_);
  TW.forEach((t,el)=>{if(t.cur===t.tgt)return;const lim=Math.pow(10,-t.dec)/2;
    if(Math.abs(t.tgt-t.cur)<lim)t.cur=t.tgt;else t.cur+=(t.tgt-t.cur)*k;el.textContent=t.cur.toFixed(t.dec)})}

/* ---------- ring ---------- */
const ringSVG=id=>`<svg id="${id}" class="ring" viewBox="0 0 120 120"><circle class="trk" cx="60" cy="60" r="50"/><circle class="val" cx="60" cy="60" r="50" stroke-dasharray="${C}" stroke-dashoffset="${C}" transform="rotate(-90 60 60)"/><text class="num" x="60" y="60" text-anchor="middle" dominant-baseline="middle">0</text><text class="pct" x="60" y="82" text-anchor="middle">%</text></svg>`;
function mountRings(){$$('[data-ring]').forEach(e=>{if(!e.firstChild)e.innerHTML=ringSVG(e.dataset.ring)})}
function ring(id,pct,base,inv){const el=document.getElementById(id);if(!el)return;const v=el.querySelector('.val');
  const p=Math.max(0,Math.min(100,pct||0));v.style.strokeDashoffset=C*(1-p/100);v.style.stroke=inv?(p<=30?COL.bad:p<=50?COL.warn:base):(lvl(p)||base);el.querySelector('.num').textContent=Math.round(p)}

/* ---------- canvas line chart ---------- */
function chart(cv,series,o={}){
  if(!cv)return null;
  const dpr=window.devicePixelRatio||1,w=cv.clientWidth,h=cv.clientHeight;if(!w||!h)return null;
  if(cv.width!==Math.round(w*dpr)||cv.height!==Math.round(h*dpr)){cv.width=Math.round(w*dpr);cv.height=Math.round(h*dpr)}
  const c=cv.getContext('2d');c.setTransform(dpr,0,0,dpr,0,0);c.clearRect(0,0,w,h);
  const N=o.n||HL;let max=o.max;
  if(max==null){let m=0;series.forEach(s=>s.data.forEach(v=>{if(v!=null&&v>m)m=v}));max=Math.max(o.minMax||1,m*1.2);
    if(o.st){o.st.max=o.st.max==null?max:o.st.max+(max-o.st.max)*.12;max=o.st.max}}
  const mini=o.mini,pad=mini?{l:0,t:3,b:3}:o.labels?{l:46,t:8,b:6}:{l:0,t:6,b:3},pw=w-pad.l-(mini?4:6),ph=h-pad.t-pad.b;
  if(!mini){c.font='11px '+COL.font;c.textBaseline='middle';
    for(let i=0;i<=3;i++){const y=pad.t+ph*i/3;c.strokeStyle=COL.grid||'rgba(15,23,42,.07)';c.lineWidth=1;c.beginPath();c.moveTo(pad.l,y);c.lineTo(w,y);c.stroke();
      if(o.labels){c.fillStyle='#8a97ad';c.textAlign='right';c.fillText((o.fmt?o.fmt(max*(1-i/3)):(max*(1-i/3)).toFixed(0)),pad.l-8,Math.min(Math.max(y,8),h-8))}}}
  const step=pw/(N-1),sh=o.shift==null?0:step*(1-o.shift);
  series.forEach(s=>{const d=s.data,off=(N-d.length)*step+sh;c.beginPath();let started=false,lastX=0,lastY=0;
    d.forEach((v,i)=>{if(v==null){started=false;return}const x=pad.l+off+i*step,y=pad.t+ph*(1-Math.min(v,max)/max);
      if(!started){c.moveTo(x,y);started=true}else c.lineTo(x,y);lastX=x;lastY=y});
    c.strokeStyle=s.color;c.lineWidth=mini?1.8:2.2;c.lineJoin='round';c.lineCap='round';c.stroke();
    if(s.fill!==false&&d.length>1&&!d.includes(null)){c.lineTo(lastX,pad.t+ph);c.lineTo(pad.l+off,pad.t+ph);c.closePath();
      const g=c.createLinearGradient(0,pad.t,0,pad.t+ph);g.addColorStop(0,s.color+(mini?'44':'33'));g.addColorStop(1,s.color+'00');c.fillStyle=g;c.fill()}
    if(lastX){c.beginPath();c.arc(lastX,lastY,mini?2.6:3.6,0,Math.PI*2);c.fillStyle=mini?s.color:(COL.panel||'#fff');c.fill();if(!mini){c.lineWidth=2;c.strokeStyle=s.color;c.stroke()}}});
  return {pad,pw,ph,step,sh,max,w,h};
}
/* grafik utama: bergeser halus tiap detik + crosshair saat di-hover */
function heroDraw(){
  if(!H.down.length)return;
  const cv=$('#cNet'),s=RM?1:Math.min(1,(performance.now()-pushT)/1000);
  const g=chart(cv,[{data:H.down,color:COL.down},{data:H.up,color:COL.up}],{labels:true,minMax:2,st:heroSt,shift:s,fmt:v=>v>=100?v.toFixed(0):v.toFixed(1)});
  const tip=$('#tip');if(!g||hov.x==null){tip.style.display='none';return}
  const n=H.down.length,off=(HL-n)*g.step+g.sh;
  let i=Math.round((hov.x-g.pad.l-off)/g.step);i=Math.max(0,Math.min(n-1,i));
  const x=g.pad.l+off+i*g.step,c=cv.getContext('2d');
  c.save();c.strokeStyle=COL.guide||'rgba(15,23,42,.35)';c.setLineDash([4,4]);c.lineWidth=1;c.beginPath();c.moveTo(x,g.pad.t);c.lineTo(x,g.h-g.pad.b);c.stroke();c.restore();
  [[H.down,COL.down],[H.up,COL.up]].forEach(([d,col])=>{const v=d[i];if(v==null)return;const y=g.pad.t+g.ph*(1-Math.min(v,g.max)/g.max);
    c.beginPath();c.arc(x,y,4.5,0,Math.PI*2);c.fillStyle=COL.panel||'#fff';c.fill();c.lineWidth=2.2;c.strokeStyle=col;c.stroke()});
  const ago=n-1-i;
  tip.innerHTML=`<b>${ago?ago+' dtk lalu':'sekarang'}</b> &nbsp;<span style="color:#7dd3fc">&#9660; ${H.down[i].toFixed(2)}</span> &nbsp;<span style="color:#f9a8d4">&#9650; ${H.up[i].toFixed(2)}</span> Mbps`;
  tip.style.display='block';tip.style.left=Math.max(70,Math.min(g.w-70,x))+'px';
}

/* ---------- banner: jaringan mesh ---------- */
const mesh={cv:null,c:null,w:0,h:0,dpr:1,nodes:[],pk:[],mx:null,my:null};
function meshResize(){const b=$('#banner'),dpr=Math.min(2,window.devicePixelRatio||1);
  mesh.w=b.clientWidth;mesh.h=b.clientHeight;mesh.dpr=dpr;mesh.cv.width=mesh.w*dpr;mesh.cv.height=mesh.h*dpr;
  const n=Math.max(26,Math.min(78,Math.round(mesh.w*mesh.h/12000)));
  while(mesh.nodes.length<n)mesh.nodes.push({x:Math.random()*mesh.w,y:Math.random()*mesh.h,vx:(Math.random()-.5)*14,vy:(Math.random()-.5)*14,r:1.1+Math.random()*1.7,ph:Math.random()*6.28});
  mesh.nodes.length=n;mesh.nodes.forEach(p=>{if(p.x>mesh.w)p.x=Math.random()*mesh.w;if(p.y>mesh.h)p.y=Math.random()*mesh.h})}
function meshFrame(dt_,t){
  const {c,w,h,nodes}=mesh;if(!c||!w)return;
  c.setTransform(mesh.dpr,0,0,mesh.dpr,0,0);c.clearRect(0,0,w,h);
  nodes.forEach(n=>{n.x+=n.vx*dt_;n.y+=n.vy*dt_;if(n.x<-10)n.x=w+10;else if(n.x>w+10)n.x=-10;if(n.y<-10)n.y=h+10;else if(n.y>h+10)n.y=-10});
  const LK=150,edges=[];c.lineWidth=1;
  for(let i=0;i<nodes.length;i++){const a=nodes[i];
    for(let j=i+1;j<nodes.length;j++){const b=nodes[j],d=Math.hypot(a.x-b.x,a.y-b.y);
      if(d<LK){c.strokeStyle=`rgba(125,190,255,${(1-d/LK)*.3})`;c.beginPath();c.moveTo(a.x,a.y);c.lineTo(b.x,b.y);c.stroke();if(edges.length<160)edges.push([a,b])}}}
  if(mesh.mx!=null)nodes.forEach(n=>{const d=Math.hypot(n.x-mesh.mx,n.y-mesh.my);
    if(d<190){c.strokeStyle=`rgba(255,255,255,${(1-d/190)*.55})`;c.beginPath();c.moveTo(mesh.mx,mesh.my);c.lineTo(n.x,n.y);c.stroke()}});
  nodes.forEach(n=>{c.fillStyle=`rgba(175,215,255,${.5+.35*Math.sin(t*1.4+n.ph)})`;c.beginPath();c.arc(n.x,n.y,n.r,0,6.283);c.fill()});
  const rate=.35+Math.min(6,Math.sqrt(led.mbps)*.5);
  if(dt_>0&&edges.length&&Math.random()<rate*dt_&&mesh.pk.length<26){const e=edges[(Math.random()*edges.length)|0];
    mesh.pk.push({a:e[0],b:e[1],p:0,v:.5+Math.random()*.7,col:Math.random()<.55?'56,189,248':'244,114,182'})}
  mesh.pk=mesh.pk.filter(k=>{k.p+=k.v*dt_;if(k.p>=1)return false;const x=k.a.x+(k.b.x-k.a.x)*k.p,y=k.a.y+(k.b.y-k.a.y)*k.p;
    const g=c.createRadialGradient(x,y,0,x,y,9);g.addColorStop(0,`rgba(${k.col},.95)`);g.addColorStop(1,`rgba(${k.col},0)`);
    c.fillStyle=g;c.beginPath();c.arc(x,y,9,0,6.283);c.fill();return true});
}

/* ---------- LED light bar ala lampu mobil ---------- */
const LSTOPS=[[34,211,238],[59,130,246],[139,92,246],[244,63,94]];
const lcol=x=>{const p=x*(LSTOPS.length-1),i=Math.min(LSTOPS.length-2,Math.floor(p)),f=p-i,a=LSTOPS[i],b=LSTOPS[i+1];return [a[0]+(b[0]-a[0])*f,a[1]+(b[1]-a[1])*f,a[2]+(b[2]-a[2])*f]};
const ss=t=>t<=0?0:t>=1?1:t*t*(3-2*t);
const ease=t=>-(Math.cos(Math.PI*t)-1)/2;
function ledResize(){const bx=$('.ledbar'),dpr=Math.min(2,window.devicePixelRatio||1);
  led.w=bx.clientWidth;led.h=bx.clientHeight;led.dpr=dpr;[led.cv,led.gl].forEach(cv=>{cv.width=led.w*dpr;cv.height=led.h*dpr})}
function ledFrame(dt_){
  const c=led.c;if(!c||!led.w)return;
  const period=Math.max(1.5,3.6-Math.sqrt(led.mbps)*.25);
  led.phase=(led.phase+dt_/period)%1;
  const ph=led.phase,R=.14,filling=ph<.5;
  const fh=(filling?ease(ph/.5):1)*(1+R), eh=(filling?0:ease((ph-.5)/.5))*(1+R);
  c.setTransform(led.dpr,0,0,led.dpr,0,0);c.clearRect(0,0,led.w,led.h);
  const pitch=12,cw=9,chh=9,n=Math.max(2,Math.floor(led.w/pitch)),x0=(led.w-n*pitch+(pitch-cw))/2,y=(led.h-chh)/2;
  for(let i=0;i<n;i++){const x=i/(n-1);
    const base=ss((fh-x)/R)*(1-ss((eh-x)/R));
    const hc=(filling?fh:eh)-R*.45,hl=Math.exp(-Math.pow((x-hc)/.035,2))*(filling?.55:.3);
    const v=Math.min(1,base+hl*(base>0?1:.4));
    c.beginPath();
    if(v<.02){c.fillStyle='rgba(255,255,255,.10)'}
    else{const col=lcol(x),wt=Math.max(0,(v-.7)/.3)*.5,r=col[0]+(255-col[0])*wt,g=col[1]+(255-col[1])*wt,b=col[2]+(255-col[2])*wt;
      c.fillStyle=`rgba(${r|0},${g|0},${b|0},${.14+.86*v})`}
    const px=x0+i*pitch;if(c.roundRect)c.roundRect(px,y,cw,chh,3);else c.rect(px,y,cw,chh);c.fill()}
  led.g.setTransform(1,0,0,1,0,0);led.g.clearRect(0,0,led.gl.width,led.gl.height);led.g.drawImage(led.cv,0,0);
}
let lastT=0;
function loop(ts){const d_=Math.min(.1,(ts-(lastT||ts))/1000);lastT=ts;
  meshFrame(d_,ts/1000);ledFrame(d_);twFrame(d_);heroDraw();requestAnimationFrame(loop)}
function resizeAll(){meshResize();ledResize();moveInd();if(RM){meshFrame(0,0);led.phase=.5;ledFrame(0)}}

/* ---------- toast & modal ---------- */
function toastRaw({level='warn',icon='alert',title,sub,onclick,ms=7000}){
  const box=$('#toasts'),t=document.createElement('div');t.className='toast '+(level==='bad'?'crit':level);
  t.innerHTML=`<i class="al-ic" data-ic="${esc(icon)}"></i><div><b>${esc(title)}</b><span>${esc(sub||'')}</span></div>`;
  const close=()=>{t.classList.add('out');setTimeout(()=>t.remove(),350)};
  t.onclick=()=>{if(onclick)onclick();close()};
  box.appendChild(t);mountIcons(t);setTimeout(close,ms);while(box.children.length>3)box.firstChild.remove()}
const notice=(title,sub,level='ok')=>toastRaw({level,icon:level==='ok'?'check':'alert',title,sub,ms:4200});
let modalOk=null;
function openModal({title,name,type,onOk}){$('#mTitle').textContent=title;$('#mName').value=name||'';$('#mType').value=type||'other';modalOk=onOk;$('#modal').hidden=false;setTimeout(()=>$('#mName').focus(),30)}
function closeModal(){$('#modal').hidden=true;modalOk=null}

/* ---------- menu / view ---------- */
function moveInd(){const t=$('.tab.on'),ind=$('#tabInd');if(!t||!ind)return;ind.style.left=t.offsetLeft+'px';ind.style.width=t.offsetWidth+'px'}
function showView(v,fromHash){
  if(!VIEWS.includes(v))v='net';cur=v;
  VIEWS.forEach(k=>$('#v-'+k).hidden=k!==v);
  $$('.tab').forEach(t=>{const on=t.dataset.v===v;t.classList.toggle('on',on);t.setAttribute('aria-selected',on)});
  moveInd();if(!fromHash){try{history.replaceState(null,'','#'+v)}catch(e){}}
  const vw=$('#v-'+v);vw.querySelectorAll('.card,.vh').forEach((c,i)=>c.style.setProperty('--i',i));
  vw.classList.remove('enter');void vw.offsetWidth;vw.classList.add('enter');
  const top=$('#banner').offsetHeight;if(window.scrollY>top)window.scrollTo({top});
  if(v==='dev'&&!devScanned){devScanned=true;startScan()}
  if(lastData)render(lastData);
}

/* ---------- API ---------- */
async function api(path,body){
  try{const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Netsys':'1'},body:JSON.stringify(body||{})});
    const j=await r.json().catch(()=>({}));if(!r.ok&&!j.error)j.error='Permintaan ditolak';return j}
  catch(e){return {error:'Server tidak dapat dihubungi'}}}
async function refreshNow(){try{const r=await fetch('/api/stats',{cache:'no-store'});render(await r.json())}catch(e){}}
async function startScan(){await api('/api/devices/scan');refreshNow()}

/* ---------- peringatan ---------- */
const LV={crit:'Kritis',warn:'Peringatan'};
const SPARK={cpu:['cpu',100],ram:['ram',100],latency:['ping',null],loss_Cloudflare:['ping',null],loss_Google:['ping',null],wifi_signal:['sig',100]};
function topHTML(a){
  let h='';
  if(a.context&&a.context.length)h+=`<ul class="ctx">${a.context.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`;
  if(a.top&&a.top.length){const m=Math.max(...a.top.map(t=>t.val),.001);
    h+=`<div class="top-l"><h5>Penyebab terbesar</h5>${a.top.map(t=>`<div class="r"><span class="nm" title="${esc(t.name)}">${esc(t.name)}</span><span class="bb"><i style="width:${Math.max(4,t.val/m*100)}%"></i></span><span class="num">${t.val} ${t.unit}</span></div>`).join('')}</div>`}
  return h}
function alertCard(a){
  return `<article class="al ${a.level}" data-id="${esc(a.id)}">
  <div class="al-head"><i class="al-ic" data-ic="${esc(a.icon)}"></i>
    <div class="al-t"><b class="al-title"></b><span class="lvl">${LV[a.level]}</span></div>
    <div class="al-v"><span class="al-val"></span><span class="al-rule"></span></div></div>
  <p class="al-detail"></p>
  <div class="al-meta"><span>Berlangsung <b class="dur"></b></span><span>Puncak <b class="al-peak"></b></span><span>Sejak <b>${tm(a.since)} WIB</b></span></div>
  ${SPARK[a.id]?'<canvas class="al-spark"></canvas>':''}
  <div class="al-top"></div>
  <div class="al-act"><h4>Saran tindakan</h4><ul></ul></div></article>`}
function updateAlertCard(el,a){
  const q=s=>el.querySelector(s);
  q('.al-title').textContent=P(a.title);q('.al-val').textContent=a.value;q('.al-rule').textContent=P(a.rule);
  q('.al-detail').textContent=P(a.detail);q('.al-peak').textContent=a.peak_text;q('.dur').textContent=fDur(Date.now()/1000-a.since);
  q('.al-top').innerHTML=topHTML(a);
  q('.al-act ul').innerHTML=a.actions.map(x=>`<li>${esc(x)}</li>`).join('');
  const sp=SPARK[a.id];if(sp)chart(q('.al-spark'),[{data:H[sp[0]],color:a.level==='crit'?COL.bad:COL.warn}],{mini:true,max:sp[1]==null?undefined:sp[1],minMax:50});
}
function renderActive(A){
  const body=$('#acBody'),act=A.active||[];
  if(!act.length){
    if(body.dataset.mode!=='calm'){body.dataset.mode='calm';body.dataset.sig='';
      body.innerHTML='<div class="calm"><div class="calm-ic" data-ic="check"></div><div class="calm-t"><b>Semua sistem normal</b><p id="calmP"></p></div><div class="calm-k" id="calmK"></div></div>';mountIcons(body)}
    const ev=(A.events||[])[0];
    $('#calmP').textContent=`${(A.checks||[]).length} pemeriksaan berjalan dan tidak ada yang melewati ambang batas. `+(ev?`Kejadian terakhir: ${P(ev.title)} (${tm(ev.ts)} WIB).`:'Belum ada kejadian sejak aplikasi dijalankan.');
    $('#calmK').innerHTML=(A.checks||[]).filter(c=>!c.id.startsWith('dev_')).slice(0,5).map(c=>`<span class="gc">${esc(c.label.replace('Pemakaian ','').replace('Beban ',''))}<b>${esc(c.value)}</b></span>`).join('');
    return}
  const sig=act.map(a=>a.id+a.level).join('|');
  if(body.dataset.mode!=='act'||body.dataset.sig!==sig){body.dataset.mode='act';body.dataset.sig=sig;
    body.innerHTML=`<div class="al-grid">${act.map(alertCard).join('')}</div>`;mountIcons(body)}
  const map={};act.forEach(a=>map[a.id]=a);
  body.querySelectorAll('.al').forEach(el=>{const a=map[el.dataset.id];if(a)updateAlertCard(el,a)});
}
function renderChecks(A){
  const body=$('#acBody');body.dataset.mode='chk';
  const ST={ok:'Normal',warn:'Peringatan',crit:'Kritis',na:'Tidak aktif'};
  body.innerHTML=`<div class="chk-grid">${(A.checks||[]).map(c=>`<div class="chk ${c.state}"><i class="ic" data-ic="${esc(c.icon)}"></i><div class="ct"><b>${esc(c.label)}</b><span title="${esc(c.rule)}">${esc(c.rule)}</span></div><div class="cv">${esc(c.value)}<span class="cs">${ST[c.state]||''}</span></div></div>`).join('')}</div>`;mountIcons(body)}
function renderLog(A){
  const body=$('#acBody');body.dataset.mode='log';const ev=A.events||[],KD={start:'Mulai',end:'Pulih',escalate:'Naik level'};
  body.innerHTML=ev.length?`<div class="log">${ev.map(e=>`<div class="log-r ${e.level}"><span class="tm">${tm(e.ts)}</span><span class="dot"></span><div><b>${esc(e.title)}</b><div class="tx">${esc(e.text)}</div></div><span class="kd">${KD[e.kind]||e.kind}</span></div>`).join('')}</div>`:'<div class="empty">Belum ada kejadian sejak aplikasi dijalankan.</div>'}
function setTab(t){acTab=t;$$('#acSeg button').forEach(b=>b.classList.toggle('on',b.dataset.t===t));$('#acBody').dataset.mode='';if(lastData&&cur==='alert')renderAC(lastData.alerts||{})}
function renderAC(A){
  const act=A.active||[];$('#nAct').textContent=act.length;$('#nAct').classList.toggle('hot',act.length>0);
  if(acTab==='act')renderActive(A);else if(acTab==='chk')renderChecks(A);else renderLog(A);
}
function notifyAlerts(A){
  const act=A.active||[],ids=new Set(act.map(a=>a.id));
  if(prevIds!==null)act.forEach(a=>{if(!prevIds.has(a.id))toast(a)});
  prevIds=ids}
function toast(a){toastRaw({level:a.level,icon:a.icon,title:a.title,sub:`${a.value} · ${a.rule}`,onclick:()=>{showView('alert');setTab('act')},ms:a.level==='crit'?11000:7000})}

/* ---------- perangkat ---------- */
function guessType(f){
  if(f.router)return 'router';const n=(f.name||'').toLowerCase();
  if(/ipad|tab/.test(n))return 'tablet';if(/iphone|android|galaxy|redmi|xiaomi|poco|oppo|vivo|realme|pixel|huawei|honor|infinix|tecno|phone/.test(n))return 'phone';
  if(/laptop|desktop|notebook|macbook|\bpc\b|thinkpad|vivobook/.test(n))return 'laptop';if(/tv|bravia|roku|chromecast|firestick/.test(n))return 'tv';
  if(/playstation|ps[345]|xbox|switch/.test(n))return 'console';if(f.random)return 'phone';return 'other'}
function devCard(x){
  return `<article class="dv chk" data-id="${x.id}">
  <div class="dv-top"><i class="dv-ic" data-ic="${DEVICON[x.type]||'server'}"></i>
    <div class="dv-nm"><b></b><span></span></div><span class="dv-st"><i></i><span>Memeriksa</span></span></div>
  <div class="dv-mid"><div class="dv-ms"><span class="dv-lat">-</span><small>ms</small></div><canvas class="dv-spark"></canvas></div>
  <div class="dv-stats"><span>Rata-rata<b class="d-avg">-</b></span><span>Jitter<b class="d-jit">-</b></span><span>Loss<b class="d-loss">-</b></span><span>Tersedia<b class="d-up">-</b></span></div>
  <div class="dv-foot"><span class="sn"></span><span class="dv-btns">
    <button class="ib" data-act="watch"><i data-ic="bell"></i></button>
    <button class="ib" data-act="edit" title="Ubah nama / tipe"><i data-ic="edit"></i></button>
    <button class="ib" data-act="del" title="Hapus perangkat"><i data-ic="trash"></i></button></span></div></article>`}
function updateDevCard(el,x){
  if(!el)return;const q=s=>el.querySelector(s),now=Date.now()/1000;
  const st=x.online===true?'on':x.online===false?'off':'chk';el.className='dv '+st;
  q('.dv-nm b').textContent=x.name;q('.dv-nm span').textContent=`${P(x.ip)} · ${PM(x.mac)}`;
  q('.dv-st span').textContent=st==='on'?'Online':st==='off'?'Offline':'Memeriksa';
  q('.dv-lat').textContent=x.online&&x.last!=null?x.last.toFixed(x.last<10?1:0):(x.online?'ok':'-');
  q('.d-avg').textContent=x.avg!=null?x.avg.toFixed(0)+' ms':'-';q('.d-jit').textContent=x.avg!=null?x.jitter.toFixed(1)+' ms':'-';
  q('.d-loss').textContent=x.probes?x.loss.toFixed(0)+'%':'-';q('.d-up').textContent=x.uptime!=null?x.uptime.toFixed(0)+'%':'-';
  q('.sn').textContent=st==='on'?`Aktif ${fDur(now-x.since)} · via ${x.method==='tcp'?'probe TCP':'ping'}`:st==='off'?`Offline ${fDur(now-x.since)}${x.last_seen?' · terlihat '+tm(x.last_seen)+' WIB':''}`:'Memeriksa koneksi…';
  const w=q('[data-act="watch"]');w.classList.toggle('on',!!x.watch);w.title=x.watch?'Peringatan offline: AKTIF (klik untuk matikan)':'Peringatan offline: mati (klik untuk aktifkan)';
  const wi=w.querySelector('[data-ic]'),want=x.watch?'bell':'bellOff';if(wi.dataset.ic!==want){wi.innerHTML='';wi.dataset.ic=want;mountIcons(w)}
  chart(q('.dv-spark'),[{data:x.hist||[],color:st==='off'?COL.bad:COL.ok}],{mini:true,n:60,minMax:20});
}
function renderDev(d){
  const devs=d.devices||[],sc=d.scan||{found:[]};
  renderGuard(d);
  const on=devs.filter(x=>x.online===true).length,off=devs.filter(x=>x.online===false).length,lats=devs.filter(x=>x.online&&x.avg!=null).map(x=>x.avg);
  setNum('#dsTotal',devs.length,0);setNum('#dsOn',on,0);setNum('#dsOff',off,0);
  $('#dsLat').textContent=lats.length?(lats.reduce((a,b)=>a+b,0)/lats.length).toFixed(0)+' ms':'-';
  const grid=$('#devGrid'),sig=devs.map(x=>[x.id,x.type].join('~')).join('|')+(priv?'P':'');
  if(sig!==devSig){devSig=sig;
    grid.innerHTML=devs.length?devs.map(devCard).join(''):`<div class="empty-dev" style="grid-column:1/-1"><div class="ic" data-ic="phone"></div><b>Belum ada perangkat yang dipantau</b>Pindai Wi-Fi/LAN lalu pilih HP atau laptop untuk dipantau,<br>atau tambahkan manual lewat IP-nya.<br><button class="btn" data-act="scan"><i data-ic="radar"></i>Pindai jaringan</button></div>`;
    mountIcons(grid)}
  const map={};devs.forEach(x=>map[x.id]=x);grid.querySelectorAll('.dv').forEach(el=>updateDevCard(el,map[el.dataset.id]));
  // pindai
  const btn=$('#scanBtn');btn.disabled=!!sc.running;btn.querySelector('span').textContent=sc.running?'Memindai…':'Pindai jaringan';
  $('#scanIc').classList.toggle('scanning',!!sc.running);
  $('#scanStat').innerHTML=sc.running?`<i class="spin"></i>${esc(sc.phase||'Memindai')}`:sc.error?`<span class="err" style="margin:0">${esc(sc.error)}</span>`:sc.ts?`Dipindai ${tm(sc.ts)} WIB · ${sc.found.length} perangkat · ${esc(sc.subnet||'')}`:'Belum dipindai';
  const gmap={};((d.guard&&d.guard.devices)||[]).forEach(x=>gmap[x.mac]=x);
  const ips=new Set(devs.map(x=>x.ip)),ssig=(sc.ts||0)+'|'+[...ips].join(',')+'|'+Object.values(gmap).map(x=>x.mac+x.status).join(',')+(priv?'P':'');
  if(ssig!==scanSig){scanSig=ssig;lastScan=sc.found||[];
    $('#scanBody').innerHTML=lastScan.length?lastScan.map((f,i)=>{const mon=ips.has(f.ip);
      const tags=[f.router&&'<span class="tg rt">Router</span>',f.self&&'<span class="tg me">PC ini</span>',f.random&&'<span class="tg rnd" title="MAC acak (fitur privasi HP): IP bisa berubah">MAC acak</span>',mon&&'<span class="tg on">Dipantau</span>',(f.mac&&gmap[f.mac]&&gmap[f.mac].status==='new')&&'<span class="tg bad">Asing</span>'].filter(Boolean).join('');
      return `<tr><td style="max-width:230px"><div class="sn">${esc(f.name?PN(f.name):'Perangkat tidak dikenal')}</div><div class="dim sm">${esc(f.ip)} · ${esc(PM(f.mac))}</div><div class="tgs">${tags}</div></td><td class="r">${mon||f.self?'':`<button class="btn sm" data-act="add" data-i="${i}">Pantau</button>`}</td></tr>`}).join(''):`<tr><td class="dim">${sc.running?'':'Belum ada hasil pindai.'}</td></tr>`}
}
async function addDevice(p){
  const r=await api('/api/devices/add',p);
  if(r.ok){notice('Perangkat ditambahkan',`${p.name||p.ip} mulai dipantau`);refreshNow();return true}
  notice('Gagal menambah perangkat',r.error||'Terjadi kesalahan','bad');return false}

/* ---------- render ---------- */
function quality(cf){
  if(!cf||cf.avg==null)return cf&&!cf.reachable?['Offline','bad']:['Mengukur','off'];
  const s=cf.avg+cf.jitter*2+cf.loss*8;
  if(cf.loss>=10||s>200)return['Buruk','bad'];if(s>100)return['Cukup','warn'];if(s>50)return['Baik','ok'];return['Sangat baik','ok'];
}
function setChip(sel,cls,text){const e=$(sel);e.className='chip '+cls;e.lastElementChild.textContent=text}
function render(d){
  const L=d.latest;if(!L||!L.cpu)return;lastData=d;splashOnData();
  if(d.app){if(d.app.theme&&d.app.theme!==curTheme)applyTheme(d.app.theme);const up=d.app.update;$('#updChip').hidden=!(up&&up.available);if(up&&up.available){$('#updChip').href=up.url||'#';$('#updTxt').textContent='v'+up.version}}
  const S=d.slow||{},A=d.alerts||{active:[],checks:[],events:[],health:{score:100,label:'Prima'}},devs=d.devices||[];
  if(L.ts!==lastTs){lastTs=L.ts;pushT=performance.now();const g=L.gpu&&L.gpu[0]&&L.gpu[0].util!=null?L.gpu[0].util:null;
    const push=(k,v)=>{H[k].push(v);if(H[k].length>HL)H[k].shift()};
    push('cpu',L.cpu.total);push('ram',L.mem.percent);push('gpu',g);
    push('down',fMbps(L.net.down));push('up',fMbps(L.net.up));push('dr',fMBs(L.disk_io.read));push('dw',fMBs(L.disk_io.write));
    push('ping',(d.lat.Cloudflare||{}).last??null);push('sig',d.wifi&&d.wifi.connected&&d.wifi.signal!=null?d.wifi.signal:null)}
  const dn=fMbps(L.net.down),up=fMbps(L.net.up);led.mbps=dn+up;
  const cf=d.lat.Cloudflare||{},gpu0=L.gpu&&L.gpu[0]&&L.gpu[0].util!=null?L.gpu[0].util:null;
  // ---- bagian yang selalu tampil: banner, menu, strip peringatan
  $('#lip').textContent=P(S.local_ip||'-');$('#pip').textContent=P(d.public_ip||'-');
  $('#uptime').textContent=fUp(Date.now()/1000-INFO.boot);
  if(L.battery){$('#battWrap').hidden=false;$('#batt').textContent=Math.round(L.battery.percent)+'%'+(L.battery.plugged?' (charging)':'')}
  if(cf.last!=null)setNum('#kPing',cf.last,0);
  setNum('#kCpu',L.cpu.total,0);if(gpu0!=null)setNum('#kGpu',gpu0,0);setNum('#kRam',L.mem.percent,0);
  chart($('#sPing'),[{data:H.ping,color:'#38bdf8',fill:false}],{mini:true,minMax:50});
  chart($('#sCpu'),[{data:H.cpu,color:'#fbbf24'}],{mini:true,max:100});
  chart($('#sGpu'),[{data:H.gpu,color:'#a78bfa'}],{mini:true,max:100});
  chart($('#sRam'),[{data:H.ram,color:'#34d399'}],{mini:true,max:100});
  const hl=A.health||{score:100,label:'Prima'},hr=$('#ringHealth');
  if(hr){const v=hr.querySelector('.val');v.style.strokeDashoffset=C*(1-hl.score/100);v.style.stroke=hl.score>=85?'#34d399':hl.score>=60?'#fbbf24':'#fb7185';hr.querySelector('.num').textContent=hl.score;hr.querySelector('.pct').textContent='skor'}
  $('#hLabel').textContent=hl.label;
  const n=A.active.length,crit=A.active.some(a=>a.level==='crit'),cls=n?(crit?'bad':'warn'):'ok',txt=n?`${n} peringatan aktif`:'Semua normal';
  setChip('#status',cls,txt);setChip('#miniStatus',cls,txt);
  $('#mDown').textContent=dn.toFixed(1);$('#mUp').textContent=up.toFixed(1);$('#mCpu').textContent=Math.round(L.cpu.total);$('#mPing').textContent=cf.last!=null?cf.last.toFixed(0):'-';
  const ab=$('#alBadge');ab.hidden=!n;ab.textContent=n;ab.className=n?(crit?'hot':'warn'):'';
  document.title=(n?`(${n}) `:'')+'Netsys Monitor';
  const dvOn=devs.filter(x=>x.online===true).length,dvOff=devs.filter(x=>x.online===false&&x.watch).length,db=$('#devBadge');
  const gN=(d.guard&&d.guard.new)||0;
  db.hidden=!devs.length&&!gN;db.textContent=gN?`${gN} asing`:`${dvOn}/${devs.length}`;db.className=gN?'hot':dvOff?'warn':'good';
  const as=$('#aStrip');
  if(n&&cur!=='alert'){const top=A.active[0];as.hidden=false;as.className='astrip '+top.level;
    as.querySelector('.as-t').innerHTML=`<b>${n} peringatan aktif</b> · ${esc(top.title)}${n>1?` +${n-1} lainnya`:''}`;
    const ic=as.querySelector('[data-ic]');if(ic.dataset.ic!==top.icon){ic.innerHTML='';ic.dataset.ic=top.icon;mountIcons(as)}}
  else as.hidden=true;
  notifyAlerts(A);
  if(cur==='alert')renderHistory(false);
  if(cur==='net')renderNet(d,L,S,cf);else if(cur==='sys')renderSys(d,L,S);else if(cur==='dev')renderDev(d);else renderAC(A);
}
function renderNet(d,L,S,cf){
  const dn=fMbps(L.net.down),up=fMbps(L.net.up);
  setNum('#dlV',dn,dn<10?2:1);setNum('#ulV',up,up<10?2:1);
  $('#dlS').textContent=`${fMBs(L.net.down).toFixed(2)} MB/s · puncak ${fMbps(L.net.peak_down).toFixed(1)} Mbps`;
  $('#ulS').textContent=`${fMBs(L.net.up).toFixed(2)} MB/s · puncak ${fMbps(L.net.peak_up).toFixed(1)} Mbps`;
  $('#heroPing').textContent=cf.last!=null?cf.last.toFixed(0):'-';$('#heroJit').textContent=num(cf.jitter,1);$('#heroLoss').textContent=num(cf.loss,0);
  const q=quality(cf);setChip('#heroQ',q[1],'Koneksi '+q[0].toLowerCase());
  $('#avgD').textContent=avg(H.down).toFixed(1);$('#avgU').textContent=avg(H.up).toFixed(1);
  if(RM)heroDraw();
  $('#latBody').innerHTML=Object.entries(d.lat||{}).map(([nm,v])=>{
    const dead=v.avg==null;const cell=dead?(v.reachable?'mengukur':'tidak merespon'):v.avg.toFixed(v.avg<10?1:0)+' ms';
    return `<tr><td>${esc(nm)} <span class="dim">${esc(v.host)}</span></td><td class="r num ${dead?'dim':''}" ${dead?'colspan="3"':''}>${cell}</td>${dead?'':`<td class="r num">${v.jitter.toFixed(1)}</td><td class="r num" style="color:${v.loss>5?COL.bad:'inherit'}">${v.loss.toFixed(0)}%</td>`}</tr>`}).join('');
  chart($('#cPing'),[{data:H.ping,color:COL.lat,fill:false}],{minMax:50});
  const U=d.usage,sd=(a,X,Y)=>{$(X).textContent='▼ '+fB(a.recv,1);$(Y).textContent='▲ '+fB(a.sent,1)};
  sd(U.session,'#usSA','#usSB');sd(U.today,'#usTA','#usTB');sd(U.month,'#usMA','#usMB');
  $('#usSince').textContent='sejak '+U.since;
  const mx=Math.max(1,...U.days.map(x=>Math.max(x.sent,x.recv)));
  $('#days').innerHTML=U.days.map(x=>`<div class="day" title="${x.d}: ▼ ${fB(x.recv)} ▲ ${fB(x.sent)}"><div class="cols"><i class="d" style="height:${x.recv/mx*100}%"></i><i class="u" style="height:${x.sent/mx*100}%"></i></div><span>${x.d}</span></div>`).join('');
  $('#ifBody').innerHTML=L.net.ifaces.map(i=>`<tr><td title="${esc(i.name)}">${esc(i.name)}<div class="dim" style="font-size:11.5px">${esc(i.ip||'-')}${i.link?' · '+i.link+' Mbps':''}</div></td><td class="r num" style="color:var(--down)">${fMbps(i.down).toFixed(2)}</td><td class="r num" style="color:var(--up)">${fMbps(i.up).toFixed(2)}</td></tr>`).join('');
  const cn=S.conns||{counts:{},list:[]};
  $('#connSum').textContent=cn.error?'butuh hak Administrator':`${cn.total_est??0} established · ${cn.counts.LISTEN||0} listening`;
  $('#connBody').innerHTML=cn.list.map(c=>`<tr><td>${esc(c.proc)}</td><td class="r num dim">${c.lport}</td><td class="r num">${esc(PR(c.remote))}</td></tr>`).join('');
  renderST(d.speedtest);
  renderWifi(d);renderDns(d);renderTrace(d);
}
function renderSys(d,L,S){
  renderApp(d);
  ring('ringCpu',L.cpu.total,COL.cpu);
  $('#cpuName').textContent=INFO.cpu||'';
  $('#cpuFreq').textContent=L.cpu.freq?(L.cpu.freq/1000).toFixed(2)+' GHz':'-';
  $('#cpuCores').textContent=`${INFO.cores_phys||'?'} / ${INFO.cores_log||'?'}`;
  $('#cpuProcs').textContent=S.proc_count??'-';
  $('#cpuTemp').textContent=L.cpu.temp!=null?L.cpu.temp.toFixed(0)+' °C':(INFO.os_name==='Windows'?'perlu LibreHardwareMonitor':'tidak tersedia');
  const fans=L.cpu.fans||[],cfn=fans.filter(f=>f.cpu),fl=(cfn.length?cfn:fans).slice(0,2);
  $('#cpuFan').textContent=fl.length?fl.map(f=>Math.round(f.rpm)+' RPM').join(' · '):'-';
  $('#cpuPow').textContent=L.cpu.power!=null?L.cpu.power.toFixed(0)+' W':'-';
  chart($('#cCpu'),[{data:H.cpu,color:COL.cpu}],{max:100});
  const cr=$('#cores');if(cr.children.length!==L.cpu.cores.length)cr.innerHTML=L.cpu.cores.map(()=>'<div class="core"><i></i><span></span></div>').join('');
  L.cpu.cores.forEach((v,i)=>{const e=cr.children[i];e.firstChild.style.height=v+'%';e.firstChild.style.background=lvl(v)||COL.cpu;e.lastChild.textContent=Math.round(v)});
  ring('ringMem',L.mem.percent,COL.mem);
  $('#memUsed').textContent=fB(L.mem.used,1);$('#memTotal').textContent=fB(L.mem.total,1);
  $('#swapTxt').textContent=`${fB(L.mem.swap_used)} / ${fB(L.mem.swap_total)}`;$('#swapBar').style.width=L.mem.swap_percent+'%';
  chart($('#cMem'),[{data:H.ram,color:COL.mem}],{max:100});
  renderGPU(L.gpu||[]);
  chart($('#cGpu'),[{data:H.gpu,color:COL.gpu}],{max:100});
  const rate=b=>b>=1e6?(b/1e6).toFixed(1)+' MB/s':(b/1e3).toFixed(0)+' KB/s';
  $('#drV').textContent=rate(L.disk_io.read);$('#dwV').textContent=rate(L.disk_io.write);
  chart($('#cDisk'),[{data:H.dr,color:COL.disk},{data:H.dw,color:COL.lat}],{minMax:1});
  $('#vols').innerHTML=(S.disks||[]).map(v=>`<div style="display:block"><div style="margin-bottom:5px"><span style="color:var(--txt)">${esc(v.mount)}</span><span class="tag" style="margin-left:6px">${esc(v.fs)}</span><b style="float:right">${fB(v.used,0)} / ${fB(v.total,0)}</b></div><div class="bar" style="--ac:${lvl(v.percent)||COL.disk}"><i style="width:${v.percent}%"></i></div></div>`).join('')||'<div class="empty">-</div>';
  const gn=(L.gpu||[]).map(x=>x.name).join(', ')||'-';
  const rows=[['Nama PC',PN(INFO.host)],['Sistem operasi',INFO.os||'-'],['Versi',INFO.os_ver||'-'],['Arsitektur',INFO.arch||'-'],['Prosesor',INFO.cpu||'-'],['RAM terpasang',fB(INFO.ram_total,0)],['GPU',gn],['Pengguna',PN(INFO.user)],['Terakhir boot',dt(INFO.boot)],['Uptime',fUp(Date.now()/1000-INFO.boot)],['Zona waktu','WIB (UTC+7)']];
  $('#sysInfo').innerHTML=rows.map(r=>`<div>${r[0]} <b title="${esc(r[1])}">${esc(r[1])}</b></div>`).join('');
  const pl=(procSort==='cpu'?S.procs:S.procs_mem)||[];
  $('#procBody').innerHTML=pl.map(p=>`<tr><td>${esc(p.name)}</td><td class="r num dim">${p.pid}</td><td class="r num" style="color:${lvl(p.cpu*2)||'inherit'};${procSort==='cpu'?'font-weight:600':''}"><span class="pbar"><i style="width:${Math.min(100,p.cpu*2)}%"></i></span>${p.cpu.toFixed(1)}%</td><td class="r num" style="${procSort==='mem'?'font-weight:600':''}">${p.mem.toFixed(1)}%</td></tr>`).join('');
}
function renderGPU(g){
  const sig=g.map(x=>x.name).join('|');
  if(sig!==gpuSig){gpuSig=sig;
    $('#gpus').innerHTML=g.length?g.map((x,i)=>`<div class="gpu"><div class="gname">${esc(x.name)}</div><div class="row"><div data-ring="ringGpu${i}"></div><div class="kv" id="gkv${i}"></div></div></div>`).join(''):'<div class="empty">GPU tidak terdeteksi. NVIDIA: pip install nvidia-ml-py. AMD/Intel: jalankan LibreHardwareMonitor (lihat kartu Sensor di bawah).</div>';mountRings()}
  g.forEach((x,i)=>{ring('ringGpu'+i,x.util||0,COL.gpu);
    const vr=x.vram_total?`${fB(x.vram_used,1)} / ${fB(x.vram_total,0)} (${Math.round((x.vram_used||0)/x.vram_total*100)}%)`:(x.vram_used!=null?fB(x.vram_used,1):'-');
    const rows=[['VRAM',vr],['Suhu',x.temp!=null?x.temp.toFixed(0)+' °C'+(x.temp_shared?' · suhu APU':'')+(x.hotspot!=null?` · hotspot ${x.hotspot.toFixed(0)} °C`:''):'-'],['Daya',x.power!=null?`${x.power.toFixed(0)} W${x.power_limit?' / '+x.power_limit.toFixed(0):''}`:'-'],['Fan',x.fan!=null?x.fan.toFixed(0)+'%':x.fan_rpm!=null?Math.round(x.fan_rpm)+' RPM':'-'],['Clock',x.clock!=null?`${x.clock.toFixed(0)} MHz${x.clock_mem!=null?' · VRAM '+x.clock_mem.toFixed(0)+' MHz':''}`:'-']];
    if(x.shared_total)rows.splice(1,0,['Memori bersama',`${fB(x.shared_used||0,1)} / ${fB(x.shared_total,0)}`]);
    $('#gkv'+i).innerHTML=rows.map(r=>`<div>${r[0]} <b>${r[1]}</b></div>`).join('');});
}
function renderST(s){
  const b=$('#stBtn');b.disabled=s.running;b.textContent=s.running?(s.phase||'Berjalan...'):'Jalankan speedtest';
  $('#stErr').textContent=s.error||'';
  if(s.result){const r=s.result,u=t=>`<small class="mut" style="font-size:12px">${t}</small>`;
    $('#stRes').innerHTML=`<div class="big"><span class="mut">Download</span><b style="color:var(--down)">${r.down.toFixed(1)} ${u('Mbps')}</b></div><div class="big"><span class="mut">Upload</span><b style="color:var(--up)">${r.up.toFixed(1)} ${u('Mbps')}</b></div><div class="big"><span class="mut">Ping</span><b>${r.ping.toFixed(0)} ${u('ms')}</b></div><div class="mut" style="font-size:12px">${esc(r.server)}<br>${esc(r.isp)} · ${r.time}</div>`}
}

/* ---------- v2: WiFi PC ini, DNS, traceroute, penjaga WiFi, sensor & aplikasi ---------- */
const fMs=v=>v==null?'-':v.toFixed(v<10?1:0);
const stamp=ts=>{const a=fmtD2.format(new Date(ts*1000)),b=fmtD2.format(new Date());return a===b?tm(ts)+' WIB':dt(ts)};
let gdSig='',trSig='',dnsSig='',splashDone=false;
function hideSplash(){const s=$('#splash');if(!s||s.classList.contains('out'))return;s.classList.add('out');setTimeout(()=>s.remove(),800)}
function splashOnData(){if(splashDone)return;splashDone=true;const m=$('#spMsg');if(m)m.textContent='Siap';setTimeout(hideSplash,Math.max(300,2300-performance.now()))}
setTimeout(()=>{const m=$('#spMsg');if(m&&!splashDone)m.textContent='Memuat sensor…'},900);
setTimeout(()=>{const m=$('#spMsg');if(m&&!splashDone)m.textContent='Menghubungkan jaringan…'},1700);
setTimeout(hideSplash,9000);
function renderWifi(d){
  const w=d.wifi||{},on=!!w.connected;
  $('#wfOn').hidden=!on;$('#wfOff').hidden=on;
  $('#wfSub').textContent=on&&w.quality?w.quality:'';
  if(!on){$('#wfOff').textContent=w.hint||'Info WiFi belum tersedia.';return}
  ring('ringWifi',w.signal||0,COL.down,true);
  $('#wfSsid').textContent=PN(w.ssid||'-');
  $('#wfCh').textContent=(w.band||'-')+(w.channel?' · Ch '+w.channel:'');
  $('#wfRate').textContent=(w.rx!=null||w.tx!=null)?`${w.rx!=null?Math.round(w.rx):'-'} / ${w.tx!=null?Math.round(w.tx):'-'} Mbps`:'-';
  $('#wfDbm').textContent=w.dbm!=null?`≈ ${w.dbm} dBm`:'-';
  $('#wfBssid').textContent=PM(w.bssid);
  $('#wfRadio').textContent=w.radio||'-';
  $('#wfAuth').textContent=[w.auth,w.cipher].filter(Boolean).join(' · ')||'-';
  chart($('#cWifi'),[{data:w.hist||[],color:COL.down}],{mini:true,max:100});
}
function renderDns(d){
  const s=d.dns||{},b=$('#dnsBtn');
  b.disabled=!!s.running;b.textContent=s.running?'Menguji…':'Uji kecepatan DNS';
  $('#dnsStat').innerHTML=s.running?`<i class="spin"></i>${esc(s.phase||'Menguji')}`:s.error?`<span class="err" style="margin:0">${esc(s.error)}</span>`:s.ts?`Diuji ${tm(s.ts)} WIB · ${(s.results||[]).length} server`:'Belum diuji. Tes mengirim sekitar 20 query kecil ke tiap server.';
  const rs=s.results||[],sig=(s.ts||0)+'|'+rs.length+(priv?'P':'');
  if(sig===dnsSig)return;dnsSig=sig;
  $('#dnsBody').innerHTML=rs.length?rs.map((r,i)=>`<tr><td><span class="sn">${esc(r.name)}</span>${i===0?' <span class="tg on">Tercepat</span>':''}<div class="dim sm">${esc(r.ip)}</div></td><td class="r num">${r.cold!=null?fMs(r.cold)+' ms':'-'}</td><td class="r num">${r.warm!=null?fMs(r.warm)+' ms':'-'}</td><td class="r num" style="color:${r.ok<90?COL.bad:'inherit'}">${r.ok.toFixed(0)}%</td></tr>`).join(''):'<tr><td class="dim" colspan="4">Belum ada hasil.</td></tr>';
  $('#dnsAdvice').textContent=s.advice||'';
}
function renderTrace(d){
  const t=d.trace||{hops:[]},b=$('#trBtn'),hops=t.hops||[];
  b.disabled=!!t.running;b.textContent=t.running?'Melacak…':'Jalankan';
  $('#trStat').innerHTML=t.running?`<i class="spin"></i>Melacak rute ke ${esc(t.target)} (${hops.length} hop)…`:t.error?`<span class="err" style="margin:0">${esc(t.error)}</span>`:t.ts?`Rute ke ${esc(t.target)} · ${hops.length} hop · ${tm(t.ts)} WIB`:'Belum dijalankan.';
  const sig=hops.map(h=>h.n+':'+h.avg+':'+h.ip).join('|')+(priv?'P':'');
  if(sig===trSig)return;trSig=sig;
  const mx=Math.max(1,...hops.map(h=>h.avg||0));
  $('#trBody').innerHTML=hops.length?hops.map(h=>`<tr><td class="r num dim">${h.n}</td><td>${h.ip?esc(h.ip):'<span class="dim">* * *</span>'}</td><td>${h.tag?`<span class="tg ${h.tag==='Router'?'rt':''}">${esc(h.tag)}</span>`:''}</td><td class="r num">${h.avg!=null?fMs(h.avg)+' ms':'<span class="dim">timeout</span>'}</td><td><span class="pbar" style="width:120px"><i style="width:${h.avg!=null?Math.max(3,h.avg/mx*100):0}%"></i></span></td><td class="r num" style="color:${h.loss>=50?COL.bad:'inherit'}">${h.loss.toFixed(0)}%</td></tr>`).join(''):'<tr><td class="dim" colspan="6">Belum ada hasil.</td></tr>';
  let best=null,prev=null;
  hops.forEach(h=>{if(h.avg==null)return;if(prev&&(!best||h.avg-prev.avg>best.d))best={d:h.avg-prev.avg,a:prev.n,b:h.n};prev=h});
  $('#trNote').textContent=(best&&best.d>=20?`Lonjakan latency terbesar: hop ${best.a} → ${best.b} (+${best.d.toFixed(0)} ms). `:'')+'Hop bertanda * di tengah rute umumnya hanya router yang menolak ICMP; abaikan bila hop berikutnya tetap merespons.';
}
function ensureOpt(sel,v){if(![...sel.options].some(o=>+o.value===v)){const o=document.createElement('option');o.value=v;o.textContent=v<120?`tiap ${v} detik`:`tiap ${Math.round(v/60)} menit`;sel.appendChild(o)}}
function renderGuard(d){
  const g=d.guard||{devices:[]},devs=g.devices||[],now=Date.now()/1000,sw=$('#gdOn'),sel=$('#gdInt');
  if(g.interval){ensureOpt(sel,g.interval);if(document.activeElement!==sel)sel.value=String(g.interval)}
  if(document.activeElement!==sw)sw.checked=!!g.enabled;
  $('#gdSub').textContent=!g.enabled?'dimatikan':(d.scan&&d.scan.running)?'memindai…':g.next_scan?`pindai berikutnya ${fDur(Math.max(0,g.next_scan-now))} lagi`:'';
  $('#gdSum').innerHTML=!g.network?'<span class="mut">Belum ada hasil pindai. Tunggu pemindaian pertama atau klik <b>Pindai sekarang</b>.</span>':`<span class="gc">Jaringan<b>${esc(g.network)}</b></span><span class="gc">Dikenal<b>${g.trusted}</b></span><span class="gc">Online<b>${g.online}</b></span><span class="gc ${g.new?'bad':''}">Asing<b>${g.new}</b></span>`;
  const an=g.anomalies||[];$('#gdAnom').innerHTML=an.map(a=>`<div><span><b>MAC gateway berubah</b> pada WiFi “${esc(a.ssid)}”: sebelumnya ${esc((a.old||[]).join(', ')||'-')}, kini ${esc(a.new)}. Bisa router diganti/reset, bisa juga ARP spoofing.</span><button class="btn sm" data-act="ack" data-id="${esc(a.id)}">Percayai gateway baru</button></div>`).join('');
  const sig=devs.map(x=>[x.mac,x.status,x.online,x.ip,x.name,x.last_seen,x.vendor].join('~')).join('|')+an.map(a=>a.id).join(',')+(priv?'P':'');
  if(sig===gdSig)return;gdSig=sig;
  $('#gdBody').innerHTML=devs.length?devs.map(x=>{const nw=x.status==='new';
    const tags=[x.router&&'<span class="tg rt">Router</span>',x.random&&'<span class="tg rnd" title="MAC acak (fitur privasi HP): bisa berganti sewaktu-waktu">MAC acak</span>',x.origin==='baseline'&&'<span class="tg">Daftar awal</span>',`<span class="tg ${x.online?'on':''}">${x.online?'Online':'Offline'}</span>`].filter(Boolean).join('');
    return `<tr class="${nw?'gd-new':''}"><td style="max-width:260px"><div class="sn">${esc(x.name?PN(x.name):'Perangkat tidak dikenal')}</div><div class="dim sm">${esc(x.ip)} · ${esc(PM(x.mac))}</div><div class="tgs">${x.vendor?`<span class="tg vd">${esc(x.vendor)}</span>`:''}${tags}</div></td><td class="dim sm">${stamp(x.first_seen)}</td><td class="dim sm">${stamp(x.last_seen)}</td><td><span class="chip ${nw?'bad':'ok'}"><i></i><span>${nw?'Asing':'Dikenal'}</span></span></td><td class="r"><span class="dv-btns" style="justify-content:flex-end">${nw?`<button class="btn sm" data-act="trust" data-mac="${x.mac}">Percayai</button>`:`<button class="ib" data-act="untrust" data-mac="${x.mac}" title="Tandai sebagai asing"><i data-ic="alert"></i></button>`}${x.online?'':`<button class="ib" data-act="wake" data-mac="${x.mac}" title="Bangunkan (Wake-on-LAN)"><i data-ic="power"></i></button>`}<button class="ib" data-act="forget" data-mac="${x.mac}" title="Hapus dari daftar"><i data-ic="trash"></i></button></span></td></tr>`}).join(''):'<tr><td class="dim" colspan="5">Belum ada perangkat tercatat.</td></tr>';
  mountIcons($('#gdBody'));
}
function renderApp(d){
  const a=d.app||{},h=d.hwmon||{},win=INFO.os_name==='Windows',ok=!!h.ok,cnt=h.counts||{temp:0,fan:0};
  $('#appVer').textContent=a.version?'v'+a.version:'';
  setChip('#hwChip',ok?'ok':win?'warn':'off',ok?'Terhubung':win?'Belum terhubung':'Memakai psutil');
  $('#hwTxt').textContent=ok?`Sumber: ${h.source}. ${cnt.temp} sensor suhu, ${cnt.fan} sensor fan, ${cnt.gpu||0} GPU terbaca${h.has_cpu_temp?'.':', tetapi sensor suhu CPU tidak ditemukan (CPU atau laptop ini mungkin tidak mengeksposnya).'}`:win?'Windows tidak mengizinkan psutil membaca suhu CPU, jadi dashboard membacanya dari LibreHardwareMonitor selama aplikasi itu berjalan.':'Suhu dibaca lewat psutil (lm-sensors); LibreHardwareMonitor tidak diperlukan.';
  $('#hwSteps').hidden=ok||!win||h.enabled===false;
  const sup=!!a.autostart_supported,btn=$('#autoBtn');
  setChip('#autoChip',!sup?'off':a.autostart?(a.autostart_stale?'warn':'ok'):'off',!sup?'Tidak didukung':a.autostart?(a.autostart_stale?'Lokasi berubah':'Aktif'):'Mati');
  $('#autoTxt').textContent=sup?`Saat login, aplikasi start diam-diam di ikon tray tanpa membuka jendela. Saat ini berjalan sebagai ${a.frozen?'.exe':'skrip Python'}.`:'Auto-start hanya tersedia di Windows.';
  btn.hidden=!sup;btn.textContent=!a.autostart?'Aktifkan auto-start':a.autostart_stale?'Perbarui lokasi program':'Matikan auto-start';
  $('#trayTxt').textContent=a.tray?'aktif':'tidak aktif';
  $('#dataDir').textContent=PN(a.data_dir||'-');
  const nb=$('#notifBtn');nb.hidden=!a.tray;nb.textContent='Notifikasi desktop: '+(a.notify===false?'Mati':'Aktif');
}
function bindExtras(){
  $('#dnsBtn').onclick=async()=>{const r=await api('/api/diag/dns');if(r.error)notice('Benchmark DNS',r.error,'bad');refreshNow()};
  const go=async()=>{const r=await api('/api/diag/trace',{target:$('#trTarget').value.trim()});if(r.error)notice('Traceroute',r.error,'bad');trSig='';refreshNow()};
  $('#trBtn').onclick=go;$('#trTarget').addEventListener('keydown',e=>{if(e.key==='Enter')go()});
  $('#gdOn').onchange=async e=>{await api('/api/guard/config',{enabled:e.target.checked});refreshNow()};
  $('#gdInt').onchange=async e=>{await api('/api/guard/config',{interval:+e.target.value});refreshNow()};
  $('#gdScan').onclick=startScan;
  $('#gdTrustAll').onclick=async()=>{const r=await api('/api/guard/trust',{all:true});notice(r.ok?'Semua perangkat dipercaya':'Gagal',r.ok?'Tidak ada peringatan untuk perangkat yang sudah tercatat':r.error,r.ok?'ok':'bad');gdSig='';refreshNow()};
  $('#gdReset').onclick=async e=>{const b=e.currentTarget;
    if(!b.classList.contains('arm')){b.classList.add('arm');b.textContent='Yakin? Klik lagi';setTimeout(()=>{b.classList.remove('arm');b.textContent='Reset daftar'},3500);return}
    b.classList.remove('arm');b.textContent='Reset daftar';
    const r=await api('/api/guard/reset');notice(r.ok?'Daftar direset':'Gagal',r.ok?'Hasil pindai berikutnya menjadi daftar awal yang baru':r.error,r.ok?'ok':'bad');gdSig='';refreshNow()};
  $('#gdAnom').onclick=async e=>{const b=e.target.closest('button[data-act=ack]');if(!b)return;const r=await api('/api/guard/ack',{id:b.dataset.id});if(r.error)notice('Gagal',r.error,'bad');gdSig='';refreshNow()};
  $('#gdBody').onclick=async e=>{const b=e.target.closest('button[data-act]');if(!b)return;const act=b.dataset.act;
    if(act==='wake'){const r=await api('/api/guard/wake',{mac:b.dataset.mac});notice(r.ok?'Magic packet terkirim':'Gagal',r.ok?(r.message||''):r.error,r.ok?'ok':'bad');return}
    if(act==='forget'&&!b.classList.contains('arm')){b.classList.add('arm');setTimeout(()=>b.classList.remove('arm'),3000);return}
    const r=await api('/api/guard/'+act,{mac:b.dataset.mac});if(r.error)notice('Gagal',r.error,'bad');gdSig='';refreshNow()};
  $('#notifBtn').onclick=async()=>{const a=(lastData&&lastData.app)||{};const r=await api('/api/app/setting',{notify:a.notify===false});notice(r.ok?'Pengaturan disimpan':'Gagal',r.ok?'Notifikasi desktop '+(a.notify===false?'diaktifkan':'dimatikan'):r.error,r.ok?'ok':'bad');refreshNow()};
  $('#autoBtn').onclick=async()=>{const a=(lastData&&lastData.app)||{},on=!a.autostart||!!a.autostart_stale;
    const r=await api('/api/app/autostart',{on});notice(r.ok?(on?'Auto-start aktif':'Auto-start dimatikan'):'Gagal',r.ok?'':r.error,r.ok?'ok':'bad');refreshNow()};
}

/* ---------- v2.3: tema, pengaturan, riwayat ---------- */
let curTheme='auto',SET=null,histT=0;
const TH_LABEL={cpu:'CPU (%)',ram:'RAM (%)',disk:'Disk (%)',cpu_temp:'Suhu CPU (°C)',gpu_temp:'Suhu GPU (°C)',loss:'Packet loss (%)',latency:'Latency (ms)',battery:'Baterai (%), makin kecil makin buruk',wifi:'Sinyal WiFi (%), makin kecil makin buruk'};
const resolveTheme=m=>m==='auto'?((window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches)?'dark':'light'):m;
function applyTheme(m){curTheme=m;document.documentElement.dataset.theme=resolveTheme(m);
  ['down','up','cpu','gpu','mem','disk','lat','ok','warn','bad'].forEach(k=>COL[k]=css('--'+k));COL.grid=css('--grid');COL.guide=css('--guide');COL.panel=css('--panel')}
if(window.matchMedia)try{matchMedia('(prefers-color-scheme: dark)').addEventListener('change',()=>{if(curTheme==='auto')applyTheme('auto')})}catch(e){}
function syncWebhookUi(){const k=$('#sWkind').value;$('#sWurlRow').hidden=k==='telegram';$('#sWtgRow').hidden=k!=='telegram'}
function fillSettings(s){SET=s;
  $$('input[name=thm]').forEach(r=>r.checked=r.value===s.theme);
  $('#sNotify').checked=!!s.notify;$('#sQuiet').checked=!!s.quiet.enabled;$('#sQ1').value=s.quiet.start;$('#sQ2').value=s.quiet.end;
  const w=s.webhook;$('#sWon').checked=!!w.enabled;$('#sWkind').value=w.kind;$('#sWurl').value=w.url;$('#sWtok').value=w.token;$('#sWchat').value=w.chat_id;$('#sWlvl').value=w.min_level;
  $('#sIdle').checked=!!s.idle_mode;$('#sUpd').checked=!!s.update_check;
  $('#sTh').innerHTML=Object.keys(TH_LABEL).filter(k=>s.thresholds[k]).map(k=>`<tr><td>${TH_LABEL[k]}</td><td><input type="number" data-th="${k}" data-i="0" value="${s.thresholds[k][0]}" aria-label="${TH_LABEL[k]} peringatan"></td><td><input type="number" data-th="${k}" data-i="1" value="${s.thresholds[k][1]}" aria-label="${TH_LABEL[k]} kritis"></td></tr>`).join('');
  syncWebhookUi();const o=(lastData&&lastData.app&&lastData.app.oui)||{};
  $('#sOuiTxt').textContent=o.loaded?`Database vendor: ${o.loaded.toLocaleString('id-ID')} entri (diperbarui ${dt(o.updated)})`:'Database vendor belum diunduh (±6 MB dari IEEE). Tanpa ini nama pabrikan tidak tampil.'}
function readSettings(){const th={};$$('#sTh input').forEach(i=>{(th[i.dataset.th]=th[i.dataset.th]||[0,0])[+i.dataset.i]=+i.value});
  return {theme:($('input[name=thm]:checked')||{}).value||'auto',notify:$('#sNotify').checked,quiet:{enabled:$('#sQuiet').checked,start:$('#sQ1').value,end:$('#sQ2').value},
    webhook:{enabled:$('#sWon').checked,kind:$('#sWkind').value,url:$('#sWurl').value,token:$('#sWtok').value,chat_id:$('#sWchat').value,min_level:$('#sWlvl').value},
    idle_mode:$('#sIdle').checked,update_check:$('#sUpd').checked,thresholds:th}}
const setMsg=(t,ok)=>{const m=$('#setMsg');m.textContent=t||'';m.className=t?(ok?'set-msg-ok':'set-msg-bad'):''};
async function openSettings(){setMsg('');try{const s=await (await fetch('/api/settings',{cache:'no-store'})).json();fillSettings(s)}catch(e){setMsg('Pengaturan tidak dapat dimuat',false)}
  const d=$('#setDlg');if(d.showModal)d.showModal();else d.setAttribute('open','')}
function closeSettings(){const d=$('#setDlg');if(d.close)d.close();else d.removeAttribute('open')}
async function saveSettings(quiet){const r=await api('/api/settings',readSettings());
  if(r.error){setMsg(r.error,false);return false}
  fillSettings(r);applyTheme(r.theme);if(!quiet)setMsg('Tersimpan',true);refreshNow();return true}
function bindSettings(){
  $('#setBtn').onclick=openSettings;$('#setX').onclick=closeSettings;$('#setCancel').onclick=closeSettings;
  $('#setSave').onclick=async()=>{if(await saveSettings())setTimeout(closeSettings,700)};
  $('#sWkind').onchange=syncWebhookUi;
  $('#sThReset').onclick=async()=>{const r=await api('/api/settings/reset-thresholds');if(r.error)setMsg(r.error,false);else{fillSettings(r);setMsg('Ambang dikembalikan ke default',true)}};
  $('#sWtest').onclick=async()=>{if(!await saveSettings(true))return;setMsg('Mengirim…',true);const r=await api('/api/settings/test-webhook');setMsg(r.ok?'Pesan tes terkirim':r.error,!!r.ok)};
  $('#sOuiBtn').onclick=async()=>{setMsg('Mengunduh database vendor…',true);$('#sOuiBtn').disabled=true;const r=await api('/api/oui/download');$('#sOuiBtn').disabled=false;
    setMsg(r.ok?r.message:r.error,!!r.ok);refreshNow();setTimeout(()=>SET&&fillSettings(SET),1200)};
  $('#sUpdBtn').onclick=async()=>{const r=await api('/api/update/check');$('#sUpdTxt').textContent=r.error?r.error:r.available?`Versi ${r.version} tersedia`:'Sudah versi terbaru'};
  $('#hsRange').onchange=()=>renderHistory(true)}
async function renderHistory(force){const now=Date.now();if(!force&&now-histT<30000)return;histT=now;
  try{const hrs=+$('#hsRange').value||24,j=await (await fetch('/api/history/metrics?hours='+hrs,{cache:'no-store'})).json(),rows=j.rows||[];
    $('#hsNote').textContent=rows.length?`${rows.length} titik · rata-rata per ${j.bucket>=3600?(j.bucket/3600).toFixed(1)+' jam':Math.round(j.bucket/60)+' menit'} · sejak ${stamp(rows[0].ts)}`:'Belum ada data: riwayat terkumpul tiap menit selama aplikasi berjalan.';
    const ser=(k,color)=>({data:rows.map(x=>x[k]),color,fill:false}),n=Math.max(2,rows.length);
    chart($('#hsA'),[ser('cpu',COL.cpu),ser('ram',COL.mem)],{max:100,labels:true,fmt:v=>v.toFixed(0)+'%',n});
    chart($('#hsB'),[ser('ping',COL.lat)],{labels:true,fmt:v=>v.toFixed(0)+' ms',n});
    chart($('#hsC'),[ser('wifi',COL.down)],{max:100,labels:true,fmt:v=>v.toFixed(0)+'%',n})}catch(e){}}

/* ---------- boot ---------- */
function tick1s(){const n=new Date(),t=fmtT.format(n);$('#clock').textContent=t;$('#mClock').textContent=t+' WIB';$('#dateTxt').textContent=fmtD.format(n)}
async function boot(){
  COL.font=css('--num');applyTheme('auto');
  const opts=TYPES.map(t=>`<option value="${t[0]}">${t[1]}</option>`).join('');$('#dType').innerHTML=opts;$('#mType').innerHTML=opts;
  mountRings();mountIcons();$$('.kpi').forEach((c,i)=>c.style.setProperty('--i',i));
  mesh.cv=$('#mesh');mesh.c=mesh.cv.getContext('2d');
  led.cv=$('#led');led.c=led.cv.getContext('2d');led.gl=$('#ledGlow');led.g=led.gl.getContext('2d');
  resizeAll();if(window.ResizeObserver)new ResizeObserver(resizeAll).observe($('#banner'));else addEventListener('resize',resizeAll);
  const bn=$('#banner');
  bn.addEventListener('mousemove',e=>{const r=bn.getBoundingClientRect();mesh.mx=e.clientX-r.left;mesh.my=e.clientY-r.top});
  bn.addEventListener('mouseleave',()=>{mesh.mx=mesh.my=null});
  const cv=$('#cNet');
  cv.addEventListener('mousemove',e=>{hov.x=e.clientX-cv.getBoundingClientRect().left});
  cv.addEventListener('mouseleave',()=>{hov.x=null;if(RM)heroDraw()});
  try{INFO=await (await fetch('/api/info')).json();HL=INFO.history_len||120;
    $('#hostos').innerHTML=`<b>${esc(PN(INFO.host))}</b> · ${esc(INFO.os)}`;
    const win=INFO.os_name==='Windows';$('#sysTabLbl').textContent=win?'Windows':'Sistem';$('#sysTitle').textContent=win?'Monitoring Windows':'Monitoring Sistem';
    const h=await (await fetch('/api/history')).json();for(const k in H)if(h[k])H[k]=h[k].slice(-HL);}catch(e){}
  // interaksi
  $('#stBtn').onclick=async()=>{await api('/api/speedtest');refreshNow()};
  $('#procSeg').onclick=e=>{const k=e.target.dataset&&e.target.dataset.k;if(!k)return;procSort=k;
    $$('#procSeg button').forEach(b=>b.classList.toggle('on',b.dataset.k===k));if(lastData)render(lastData)};
  $('#acSeg').onclick=e=>{const t=e.target.closest('button');if(t)setTab(t.dataset.t)};
  $('#tabs').onclick=e=>{const t=e.target.closest('.tab');if(t)showView(t.dataset.v)};
  const goAlerts=()=>{showView('alert');setTab('act')};
  $('#status').onclick=goAlerts;$('#miniStatus').onclick=goAlerts;$('#aStrip').onclick=goAlerts;
  $('#aStrip').onkeydown=e=>{if(e.key==='Enter'||e.key===' ')goAlerts()};
  $$('[data-priv]').forEach(b=>b.onclick=()=>applyPriv(!priv,true));
  $('#dAdd').onclick=async()=>{const err=$('#dErr');err.textContent='';
    const p={name:$('#dName').value.trim(),ip:$('#dIp').value.trim(),type:$('#dType').value};
    if(!p.ip){err.textContent='Isi alamat IP perangkat.';return}
    const r=await api('/api/devices/add',p);
    if(r.ok){$('#dName').value='';$('#dIp').value='';notice('Perangkat ditambahkan',`${p.name||p.ip} mulai dipantau`);refreshNow()}else err.textContent=r.error||'Gagal menambah perangkat'};
  ['dName','dIp'].forEach(id=>$('#'+id).addEventListener('keydown',e=>{if(e.key==='Enter')$('#dAdd').click()}));
  $('#scanBtn').onclick=startScan;
  bindExtras();bindSettings();
  $('#scanBody').onclick=async e=>{const b=e.target.closest('button[data-act="add"]');if(!b)return;const f=lastScan[+b.dataset.i];if(!f)return;
    b.disabled=true;await addDevice({name:f.name||f.ip,ip:f.ip,mac:f.mac,type:guessType(f)});b.disabled=false};
  $('#devGrid').onclick=async e=>{const b=e.target.closest('button[data-act]');if(!b)return;const act=b.dataset.act;
    if(act==='scan'){startScan();return}
    const card=b.closest('.dv'),id=card&&card.dataset.id,dv=lastData&&(lastData.devices||[]).find(x=>x.id===id);if(!dv)return;
    if(act==='del'){if(b.classList.contains('arm')){const r=await api('/api/devices/remove',{id});notice(r.ok?'Perangkat dihapus':'Gagal menghapus',dv.name,r.ok?'ok':'bad');refreshNow()}
      else{b.classList.add('arm');setTimeout(()=>b.classList.remove('arm'),3000)}}
    else if(act==='watch'){await api('/api/devices/update',{id,watch:!dv.watch});notice(dv.watch?'Peringatan dimatikan':'Peringatan diaktifkan',dv.name);refreshNow()}
    else if(act==='edit')openModal({title:'Ubah perangkat',name:dv.name,type:dv.type,onOk:async v=>{const r=await api('/api/devices/update',{id,name:v.name,type:v.type});if(r.ok)notice('Perangkat diperbarui',v.name);devSig='';refreshNow()}})};
  $('#mCancel').onclick=closeModal;$('#modal').onclick=e=>{if(e.target.id==='modal')closeModal()};
  $('#mOk').onclick=()=>{const f=modalOk;const v={name:$('#mName').value.trim(),type:$('#mType').value};closeModal();if(f)f(v)};
  $('#mName').addEventListener('keydown',e=>{if(e.key==='Enter')$('#mOk').click()});
  addEventListener('keydown',e=>{
    if(e.key==='Escape'&&!$('#modal').hidden){closeModal();return}
    if(e.ctrlKey||e.metaKey||e.altKey||/INPUT|SELECT|TEXTAREA/.test((e.target.tagName||'')))return;
    if(e.key>='1'&&e.key<='4')showView(VIEWS[+e.key-1]);else if(e.key==='p'||e.key==='P')applyPriv(!priv,true)});
  addEventListener('hashchange',()=>showView(location.hash.slice(1),true));
  applyPriv(priv,false);
  setInterval(tick1s,1000);tick1s();
  showView(VIEWS.includes(location.hash.slice(1))?location.hash.slice(1):'net',true);
  if(!RM)requestAnimationFrame(loop);
  tick();
}
async function tick(){
  try{const r=await fetch('/api/stats',{cache:'no-store'});render(await r.json())}
  catch(e){setChip('#status','off','Server terputus');setChip('#miniStatus','off','Server terputus')}
  setTimeout(tick,1000);
}
boot();
