const {JSDOM,VirtualConsole}=require('jsdom');
const base=process.argv[2];const errs=[];const vc=new VirtualConsole();
vc.on('jsdomError',e=>errs.push(String(e.detail||e.message||e).slice(0,250)));vc.on('error',e=>errs.push('console.error '+String(e).slice(0,200)));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
JSDOM.fromURL(base,{runScripts:'dangerously',resources:'usable',pretendToBeVisual:true,virtualConsole:vc,
 beforeParse(w){const ctx=new Proxy(function(){},{get:(t,k)=>k==='measureText'?()=>({width:10}):(k==='createLinearGradient'||k==='createRadialGradient')?()=>({addColorStop(){}}):()=>{},set:()=>true});
  w.HTMLCanvasElement.prototype.getContext=()=>ctx;w.matchMedia=()=>({matches:false,addEventListener(){}});w.requestAnimationFrame=()=>0;
  w.fetch=(u,o)=>fetch(new URL(u,base),o)}}).then(async dom=>{
 const w=dom.window,$=s=>w.document.querySelector(s),out={};
 await sleep(4000);
 for(const v of ['net','sys','dev','alert']){$(`.tab[data-v=${v}]`).click();await sleep(400)}
 out.histNote=$('#hsNote').textContent;
 $('#setBtn').click();await sleep(800);
 out.dlgOpen=$('#setDlg').hasAttribute('open');out.thRows=$$=w.document.querySelectorAll('#sTh tr').length;out.quiet=$('#sQ1').value;
 w.document.querySelector('input[name=thm][value=dark]').click();
 w.document.querySelector('input[data-th=cpu][data-i="0"]').value='70';
 $('#setSave').click();await sleep(1500);
 out.theme=w.document.documentElement.dataset.theme;out.msg=$('#setMsg').textContent;
 // nilai tak valid
 w.document.querySelector('input[data-th=cpu][data-i="0"]').value='99';w.document.querySelector('input[data-th=cpu][data-i="1"]').value='80';
 $('#setSave').click();await sleep(800);out.badMsg=$('#setMsg').textContent;
 $('#sThReset').click();await sleep(600);out.cpuAfterReset=w.document.querySelector('input[data-th=cpu][data-i="0"]').value;
 $('#sWkind').value='telegram';$('#sWkind').dispatchEvent(new w.Event('change'));out.tgRow=!$('#sWtgRow').hidden;out.urlRowHidden=$('#sWurlRow').hidden;
 $('#sWtest').click();await sleep(800);out.testMsg=$('#setMsg').textContent;
 $('#sUpdBtn').click();await sleep(600);out.upd=$('#sUpdTxt').textContent;
 $('.tab[data-v=dev]').click();await sleep(500);out.gdSum=$('#gdSum').textContent.slice(0,60);
 // kembalikan tema terang
 w.document.querySelector('input[name=thm][value=light]').click();$('#setSave').click();await sleep(900);out.themeBack=w.document.documentElement.dataset.theme;
 console.log(JSON.stringify(out,null,1));console.log('ERRORS',errs);process.exit(0)});
