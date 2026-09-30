'use strict';
const $=id=>document.getElementById(id), NS='http://www.w3.org/2000/svg';
let mapData=null,lastResult=null,view=null,home=null,picked=null,busy=false,drag=null;
let placeSearchTimer=null;
let replay=null,replayFrame=null;
let mapViewRevision=0, mapViewTimer=null, mapViewLoading=false;
let mapPicking=false, locationReady=true, locationLoading=false, selectionSeq=0, querySeq=0;
const examples={ugm:[-7.773595801763427,110.376947373952],grafika:[-7.76605243409807,110.37392217015598],tentara:[-7.783391923119533,110.36085404109025]};
const fmt=(v,d=0)=>Number(v).toLocaleString('id-ID',{maximumFractionDigits:d,minimumFractionDigits:d});
function el(tag,attrs={},text){const n=document.createElementNS(NS,tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;return n;}
async function api(path,data){const r=await fetch(path,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{});const body=await r.json();if(!r.ok)throw Error(body.error||'Permintaan gagal.');return body;}
function showError(message){$('error').textContent=message;$('error').hidden=false;}
function clearResult(){stopReplay(true);lastResult=null;$('resultTitle').textContent='';$('mapState').textContent='Peta lokal OSM';$('result').hidden=true;$('empty').hidden=false;$('routeLayer').replaceChildren();$('pins').replaceChildren();$('error').hidden=true;$('status').textContent='Lokasi atau skenario berubah. Jalankan pencarian kembali.';$('placeStatus').textContent='';}
function setView(v){view=v;$('map').setAttribute('viewBox',`${v.x} ${v.y} ${v.w} ${v.h}`);resizeSymbols();scheduleMapView();}
function fitPoints(points){const w=$('map').clientWidth||800,h=$('map').clientHeight||420;const xs=points.map(p=>p[0]),ys=points.map(p=>-p[1]);const cx=(Math.min(...xs)+Math.max(...xs))/2,cy=(Math.min(...ys)+Math.max(...ys))/2;let vw=Math.max(650,(Math.max(...xs)-Math.min(...xs))*1.5),vh=Math.max(500,(Math.max(...ys)-Math.min(...ys))*1.7);if(vw/vh<w/h)vw=vh*w/h;else vh=vw*h/w;home={x:cx-vw/2,y:cy-vh/2,w:vw,h:vh};setView({...home});}
function resizeSymbols(){if(!view)return;const scale=view.w/Math.max(1,$('map').clientWidth);document.querySelectorAll('[data-symbol]').forEach(n=>n.setAttribute('r',Number(n.dataset.symbol)*scale));document.querySelectorAll('[data-font]').forEach(n=>n.setAttribute('font-size',Number(n.dataset.font)*scale));const occupied=[];document.querySelectorAll('#roadLabels text').forEach(n=>{const x=(Number(n.getAttribute('x'))-view.x)/scale,y=(Number(n.getAttribute('y'))-view.y)/scale,w=n.textContent.length*6.2;const b={x:x-w/2,y:y-12,w,h:18};const outside=x<0||x>$('map').clientWidth||y<0||y>$('map').clientHeight;const overlap=occupied.some(a=>b.x<a.x+a.w&&b.x+b.w>a.x&&b.y<a.y+a.h&&b.y+b.h>a.y);n.style.display=outside||overlap?'none':'';if(!outside&&!overlap)occupied.push(b);});}
function point(xy,color,label,radius=6){const g=el('g');const dot=el('circle',{cx:xy[0],cy:-xy[1],r:10,fill:color,stroke:'white','stroke-width':2,'vector-effect':'non-scaling-stroke','data-symbol':radius});g.append(dot);if(label)g.append(el('title',{},label));return g;}
function drawPins(){const g=$('pins');g.replaceChildren();if(lastResult){g.append(point(lastResult.origin_xy,'#db7544','Koordinat awal',7));g.append(point(lastResult.snap_xy,'#2563eb','Titik awal pada ruas',4));g.append(point(lastResult.goal_xy,'#117967',lastResult.hospital,9));g.append(el('path',{d:`M ${lastResult.origin_xy[0]} ${-lastResult.origin_xy[1]} L ${lastResult.snap_xy[0]} ${-lastResult.snap_xy[1]}`,stroke:'#c26740','stroke-dasharray':'3 3','stroke-width':2,'vector-effect':'non-scaling-stroke'}));}else if(picked)g.append(point(picked,'#db7544','Titik keberangkatan',7));resizeSymbols();}
function drawMap(data,keepView=false){if(!keepView)mapViewRevision++;mapData=data;$('goalCount').textContent=data.goal_count;const roads=$('roads'),labels=$('roadLabels'),hosp=$('hospitals');roads.replaceChildren();labels.replaceChildren();hosp.replaceChildren();const groups={major:[],minor:[],blocked:[]};for(const r of data.roads){groups[r.blocked?'blocked':r.major?'major':'minor'].push(`M${r.a[0]} ${-r.a[1]}L${r.b[0]} ${-r.b[1]}`);}for(const [type,paths]of Object.entries(groups)){roads.append(el('path',{d:paths.join(' '),fill:'none',stroke:type==='major'?'#bdcbd7':type==='blocked'?'#d9e1e7':'#d0dbe3','stroke-width':type==='major'?2.3:1.2,'stroke-linecap':'round','vector-effect':'non-scaling-stroke',...(type==='blocked'?{'stroke-dasharray':'2 3'}:{})}));}for(const l of data.labels){labels.append(el('text',{x:l.xy[0],y:-l.xy[1],fill:'#6c8093','text-anchor':'middle','data-font':11,'paint-order':'stroke',stroke:'#ecf0f3','stroke-width':4,'stroke-linejoin':'round','vector-effect':'non-scaling-stroke'},l.name.replace('Jalan ','Jl. ')));}for(const h of data.hospitals)hosp.append(point(h.xy,'#429380',h.name,4));$('mapLoading').hidden=true;$('mapDetail').textContent=data.roads.length?(data.overview?'Tampilan luas · perbesar untuk melihat jalan kecil':'Geser peta untuk memuat area lain'):'Jalan tidak tersedia di area ini dalam data lokal';if(!keepView&&!lastResult)fitPoints([[data.center[0]-1100,data.center[1]-800],[data.center[0]+1100,data.center[1]+800]]);drawPins();}
function renderResult(result){lastResult=result;$('empty').hidden=true;$('result').hidden=false;$('resultTitle').textContent=result.hospital;$('routeRoad').textContent=`Dari ${result.road_name} · Skenario ${result.scenario}`;const seconds=Math.round(result.cost_s);$('eta').textContent=`${Math.floor(seconds/60)} mnt ${seconds%60} dtk`;$('distance').textContent=result.distance_m>=1000?`${fmt(result.distance_m/1000,2)} km`:`${fmt(result.distance_m)} m`;$('gap').textContent=`${fmt(result.gap_m,2)} m`;$('algorithmRows').replaceChildren();for(const a of result.algorithms){const row=document.createElement('tr');for(const value of [a.algorithm==='astar'?'A*':'UCS',`${fmt(a.cost_s,1)} dtk`,`${fmt(a.runtime_ms,2)} ms`,fmt(a.expanded_states)]){const td=document.createElement('td');td.textContent=value;row.append(td);}$('algorithmRows').append(row);}const names={base_s:'Waktu dasar',poi_s:'Sekolah, pasar, dan mal',signal_s:'Lampu lalu lintas',rail_s:'Perlintasan kereta',gate_s:'Gerbang'};$('components').replaceChildren();for(const [key,name]of Object.entries(names)){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=name;dd.textContent=`${fmt(result.components[key],1)} detik`;$('components').append(dt,dd);}$('resultNote').textContent=result.scope+(result.components.gate_s?' Waktu gerbang merupakan asumsi, belum dikalibrasi.':'');drawMap(result.map);const d=result.path.map((p,i)=>`${i?'L':'M'}${p[0]} ${-p[1]}`).join(' ');$('routeLayer').replaceChildren(el('path',{d,fill:'none',stroke:'white','stroke-width':8,'stroke-linecap':'round','stroke-linejoin':'round','vector-effect':'non-scaling-stroke'}),el('path',{d,fill:'none',stroke:'#2563eb','stroke-width':4.5,'stroke-linecap':'round','stroke-linejoin':'round','vector-effect':'non-scaling-stroke'}));fitPoints([...result.path,result.origin_xy]);drawPins();$('mapState').textContent='Rute hasil perhitungan';const snapNotice=result.gap_m>50?`Penanda lokasi berjarak ${fmt(result.gap_m)} m dari jalan. Rute dimulai di ${result.road_name}; jarak penanda ke jalan belum dihitung.`:'';$('status').textContent=`Selesai. Biaya kedua algoritma sama${result.same_path?', dengan rute identik':''}.`+(snapNotice?' '+snapNotice:'');if(snapNotice)$('placeStatus').textContent=snapNotice;prepareReplay(result);}
async function searchRoute(input){if(busy)throw Error('Perhitungan masih berlangsung.');if(!input && (!locationReady||locationLoading)){showError('Pilih hasil pencarian atau titik pada peta terlebih dahulu.');return;}if(input){locationReady=true;locationLoading=false;selectionSeq++;querySeq++;$('placeQuery').value='';$('placeResults').hidden=true;$('selectedPlace').textContent='Lokasi awal: koordinat yang dimasukkan';}if(busy)throw Error('Perhitungan masih berlangsung.');const data=input||{lat:Number($('lat').value),lon:Number($('lon').value),scenario:$('scenario').value};if(!Number.isFinite(data.lat)||!Number.isFinite(data.lon)||!['pagi','siang','sore','malam'].includes(data.scenario))throw Error('Input tidak valid.');$('lat').value=data.lat;$('lon').value=data.lon;$('scenario').value=data.scenario;clearResult();busy=true;document.body.classList.add('busy');document.querySelectorAll('form input,form select,form button').forEach(b=>b.disabled=true);$('buttonText').textContent='Menghitung rute…';$('status').textContent='Memetakan titik dan membandingkan UCS dengan A*. Mohon tunggu.';$('mapState').textContent='Sedang menghitung';try{const result=await api('/api/route',data);renderResult(result);return {hospital:result.hospital,distance_m:result.distance_m,time_s:result.cost_s};}catch(e){showError(e.message);$('status').textContent='Pencarian belum berhasil. Periksa pesan di atas.';$('mapState').textContent='Peta lokal OSM';throw e;}finally{busy=false;document.body.classList.remove('busy');document.querySelectorAll('form input,form select,form button').forEach(b=>b.disabled=false);updateSearchButton();$('buttonText').textContent='Cari RS terdekat';}}
$('routeForm').addEventListener('submit',e=>{e.preventDefault();if(e.target.reportValidity())searchRoute().catch(()=>{});});
for(const id of ['lat','lon'])$(id).addEventListener('input',()=>{selectionSeq++;locationLoading=false;locationReady=true;querySeq++;$('placeQuery').value='';$('placeResults').hidden=true;clearResult();picked=null;drawPins();$('selectedPlace').textContent='Lokasi awal: koordinat manual';updateSearchButton();});
$('scenario').addEventListener('input',()=>{clearResult();drawPins();});
document.querySelectorAll('[data-example]').forEach(b=>b.addEventListener('click',()=>{const [lat,lon]=examples[b.dataset.example];selectLocation({lat,lon,name:'Contoh '+b.textContent,kind:'Contoh lokasi'});}));

function zoom(f){if(!view)return;const w=Math.max(120,Math.min(60000/Math.max(1,view.h/view.w),view.w*f)),h=w*view.h/view.w;setView({x:view.x+(view.w-w)/2,y:view.y+(view.h-h)/2,w,h});}
$('zoomIn').onclick=()=>zoom(.75);$('zoomOut').onclick=()=>zoom(1.33);$('fit').onclick=()=>{if(lastResult)fitPoints([...lastResult.path,lastResult.origin_xy]);else if(home)setView({...home});};$('map').addEventListener('wheel',e=>{e.preventDefault();zoom(e.deltaY>0?1.12:.89);},{passive:false});$('map').addEventListener('keydown',e=>{if(e.key==='+'||e.key==='='){zoom(.8);e.preventDefault();}if(e.key==='-'){zoom(1.25);e.preventDefault();}});
function mapPoint(e){const p=$('map').createSVGPoint();p.x=e.clientX;p.y=e.clientY;return p.matrixTransform($('map').getScreenCTM().inverse());}
$('map').addEventListener('pointerdown',e=>{if(!view||busy)return;drag={x:e.clientX,y:e.clientY,v:{...view},moved:false};$('map').setPointerCapture(e.pointerId);});$('map').addEventListener('pointermove',e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)>4){drag.moved=true;$('map').classList.add('dragging');setView({...drag.v,x:drag.v.x-dx*drag.v.w/$('map').clientWidth,y:drag.v.y-dy*drag.v.h/$('map').clientHeight});}});$('map').addEventListener('pointerup',async e=>{if(!drag)return;const clicked=!drag.moved;drag=null;$('map').classList.remove('dragging');if(!clicked||busy||!mapPicking||locationLoading)return;const p=mapPoint(e);const seq=++selectionSeq;locationLoading=true;updateSearchButton();try{const ll=await api('/api/coordinate',{x:p.x,y:-p.y});if(seq!==selectionSeq)return;clearResult();$('lat').value=ll.lat.toFixed(9);$('lon').value=ll.lon.toFixed(9);picked=[p.x,-p.y];locationReady=true;querySeq++;$('placeQuery').value='';$('placeResults').hidden=true;$('selectedPlace').textContent='Lokasi awal: titik pilihan di peta';$('placeStatus').textContent='Titik peta dipilih. Sesuaikan lagi bila diperlukan.';setMapPicking(false);drawPins();$('status').textContent='Titik pada peta dipilih. Klik Cari RS terdekat.';}catch(err){showError(err.message);}finally{if(seq===selectionSeq){locationLoading=false;updateSearchButton();}}});$('map').addEventListener('pointercancel',()=>{drag=null;$('map').classList.remove('dragging');});window.addEventListener('resize',()=>{if(!view)return;const h=view.w*$('map').clientHeight/Math.max(1,$('map').clientWidth);setView({...view,y:view.y+(view.h-h)/2,h});});
$('download').onclick=()=>{if(!lastResult)return;const {map,...result}=lastResult;const blob=new Blob([JSON.stringify({...result,input:{lat:Number($('lat').value),lon:Number($('lon').value)}},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`rute-${lastResult.scenario}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
api('/api/bootstrap').then(d=>{if(!mapData){if(selectionSeq===0)picked=d.center;drawMap(d);}}).catch(e=>{$('mapLoading').textContent='Peta belum tersedia';showError(e.message);});
if(document.modelContext?.registerTool){try{Promise.resolve(document.modelContext.registerTool({name:'calculate_ambulance_route',title:'Cari RS terdekat',description:'Hitung rute dari koordinat dan tampilkan hasil pada halaman. Tidak melakukan pengiriman ambulans.',inputSchema:{type:'object',properties:{lat:{type:'number'},lon:{type:'number'},scenario:{type:'string',enum:['pagi','siang','sore','malam']}},required:['lat','lon','scenario'],additionalProperties:false},annotations:{readOnlyHint:false},execute:searchRoute})).catch(()=>{});}catch{}}



function updateSearchButton(){$('search').disabled=busy||locationLoading||!locationReady;}
function setMapPicking(on){mapPicking=on;$('pickMap').setAttribute('aria-pressed',String(on));$('pickMap').textContent=on?'✓ Klik jalan pada peta · batal':'⌖ Pilih titik di peta';$('map').classList.toggle('selecting',on);}
$('pickMap').addEventListener('click',()=>{if(busy||locationLoading)return;setMapPicking(!mapPicking);if(mapPicking){$('status').textContent='Geser atau perbesar peta, lalu klik jalan tempat berangkat.';$('map').scrollIntoView({behavior:'smooth',block:'center'});$('map').focus({preventScroll:true});}});
$('map').addEventListener('keydown',e=>{if(e.key==='Escape')setMapPicking(false);});
async function selectLocation(item){
 clearTimeout(placeSearchTimer);
 if(busy)return;const seq=++selectionSeq;querySeq++;locationReady=false;locationLoading=true;clearResult();picked=null;drawPins();setMapPicking(false);updateSearchButton();
 $('placeQuery').value=item.name;$('placeResults').hidden=true;$('placeStatus').textContent='Memuat peta lokasi…';$('selectedPlace').textContent='Memuat lokasi pilihan…';
 try{const result=await api('/api/map',{lat:item.lat,lon:item.lon});if(seq!==selectionSeq)return;
 $('lat').value=item.lat;$('lon').value=item.lon;picked=result.xy;drawMap(result.map);fitPoints([picked]);drawPins();locationReady=true;
 $('selectedPlace').textContent='Lokasi awal: '+item.name;
 $('placeStatus').textContent='Periksa penanda oranye. Gunakan Pilih titik di peta untuk menyesuaikan posisi.';
 $('status').textContent='Lokasi dipilih. Klik Cari RS terdekat.';$('mapState').textContent='Periksa titik awal';
 }catch(e){if(seq===selectionSeq){showError(e.message);$('placeStatus').textContent='Lokasi belum dapat dimuat. Coba lagi.';$('selectedPlace').textContent='Belum ada lokasi terpilih';}}
 finally{if(seq===selectionSeq){locationLoading=false;updateSearchButton();}}
}
$('placeQuery').addEventListener('input',()=>{querySeq++;selectionSeq++;locationLoading=false;locationReady=false;clearResult();picked=null;drawPins();$('placeResults').hidden=true;$('placeStatus').textContent=$('placeQuery').value.trim().length>=2?'Mencari lokasi…':'Ketik minimal 2 karakter nama lokasi.';clearTimeout(placeSearchTimer);if($('placeQuery').value.trim().length>=2)placeSearchTimer=setTimeout(()=>$('locationForm').requestSubmit(),450);$('selectedPlace').textContent='Belum ada lokasi terpilih';updateSearchButton();});
$('locationForm').addEventListener('submit',async e=>{
 e.preventDefault();clearTimeout(placeSearchTimer);if(busy)return;const q=$('placeQuery').value.trim();if(q.length<2){$('placeStatus').textContent='Ketik minimal 2 karakter.';return;}
 const seq=++querySeq;$('placeStatus').textContent='Mencari nama dalam data lokal…';$('placeResults').hidden=true;
 try{const data=await api('/api/locations',{query:q});if(seq!==querySeq)return;$('placeResults').replaceChildren();
 for(const item of data.results){const li=document.createElement('li'),button=document.createElement('button'),title=document.createElement('span'),detail=document.createElement('small');button.type='button';title.textContent=item.name;detail.textContent=`${item.kind}${item.address?' · '+item.address:''} · ${item.lat.toFixed(5)}, ${item.lon.toFixed(5)}`;button.append(title,detail);button.addEventListener('click',()=>selectLocation(item));li.append(button);$('placeResults').append(li);}
 $('placeResults').hidden=!data.results.length;$('placeStatus').textContent=data.results.length?`Pilih lokasi (${data.results.length} dari ${data.total} hasil). Nama sama dapat berada di ruas berbeda.`:'Nama ini belum tercatat dalam data OSM lokal. Coba sebagian nama atau nama jalan terdekat, lalu sesuaikan titik di peta. Tidak semua kos dan usaha tercatat.';
 }catch(err){if(seq===querySeq)$('placeStatus').textContent=err.message;}
});

function mapViewCovered(){
 if(!view||!mapData)return false;
 const c=mapData.center,r=mapData.radius,overview=Math.max(view.w,view.h)>6500;
 return !!mapData.overview===overview && view.x>=c[0]-r && view.x+view.w<=c[0]+r && -view.y<=c[1]+r && -(view.y+view.h)>=c[1]-r;
}
function scheduleMapView(){mapViewRevision++;clearTimeout(mapViewTimer);mapViewTimer=setTimeout(refreshMapView,350);}
async function refreshMapView(force=false){
 if(!view||mapViewLoading||(!force&&mapViewCovered()))return;
 const revision=mapViewRevision, snapshot={...view};mapViewLoading=true;$('mapLoading').hidden=false;$('mapLoading').textContent='Memuat jalan di area ini…';$('retryMap').hidden=true;
 try{const data=await api('/api/map-view',{x:snapshot.x+snapshot.w/2,y:-(snapshot.y+snapshot.h/2),width:snapshot.w,height:snapshot.h});
 if(revision===mapViewRevision){drawMap(data,true);$('mapLoading').hidden=true;}
 }catch(e){if(revision===mapViewRevision){$('mapLoading').textContent='Peta belum termuat. Coba muat ulang.';$('retryMap').hidden=false;}}
 finally{mapViewLoading=false;if(revision!==mapViewRevision){$('mapLoading').hidden=true;clearTimeout(mapViewTimer);mapViewTimer=setTimeout(refreshMapView,100);}}
}
$('retryMap').onclick=()=>refreshMapView(true);

function stopReplay(clear=false){
 cancelAnimationFrame(replayFrame);replayFrame=null;if(replay)replay.running=false;
 if(clear){replay=null;$('animationPanel').hidden=true;$('animationLayer').replaceChildren();$('routeLayer').style.display='';}
}
function prepareReplay(result){
 stopReplay(true);if(!result.traces?.length)return;
 $('animationPanel').hidden=false;$('animationAlgorithm').value='astar';if(window.innerWidth<=760)$('animationPanel').scrollIntoView({behavior:'smooth',block:'start'});
 $('animationStatus').textContent='Urutan pemeriksaan siap diputar.';$('animationPlay').textContent='Putar animasi';$('animationProgress').value=0;
 if(!window.matchMedia('(prefers-reduced-motion: reduce)').matches)startReplay();
}
function startReplay(){
 if(!lastResult?.traces)return;stopReplay();
 const trace=lastResult.traces.find(t=>t.algorithm===$('animationAlgorithm').value);if(!trace?.steps.length)return;
 const line=el('path',{fill:'none',stroke:'#14a89c','stroke-width':3,'stroke-opacity':.7,'vector-effect':'non-scaling-stroke','stroke-linecap':'round'});
 const head=el('circle',{r:6,fill:'#ec8c34',stroke:'white','stroke-width':2,'vector-effect':'non-scaling-stroke','data-symbol':6});
 $('animationLayer').replaceChildren(line,head);$('routeLayer').style.display='none';
 replay={trace,line,head,index:0,drawn:0,path:'',seen:new Set(),running:true,last:0,duration:Math.max(4000,Math.min(20000,trace.steps.length*50)),lastLabel:-1};
 fitPoints([...trace.steps.map(s=>s.xy),...lastResult.path]);$('animationPlay').textContent='Jeda';$('animationProgress').value=0;
 replayFrame=requestAnimationFrame(advanceReplay);
}
function advanceReplay(time){
 if(!replay?.running||!lastResult)return;
 const r=replay;if(!r.last)r.last=time;
 r.index=Math.min(r.trace.steps.length,r.index+(time-r.last)*Number($('animationSpeed').value)*r.trace.steps.length/r.duration);r.last=time;
 const end=Math.min(r.trace.steps.length,Math.max(1,Math.floor(r.index)));
 if(end>r.drawn){
 for(const s of r.trace.steps.slice(r.drawn,end)){if(s.from_xy){const key=s.from_xy.join(',')+'>'+s.xy.join(',');if(!r.seen.has(key)){r.path+=`M${s.from_xy[0]} ${-s.from_xy[1]}L${s.xy[0]} ${-s.xy[1]} `;r.seen.add(key);}}}
 r.drawn=end;r.line.setAttribute('d',r.path);const s=r.trace.steps[end-1];r.head.setAttribute('cx',s.xy[0]);r.head.setAttribute('cy',-s.xy[1]);
 $('animationProgress').value=end/r.trace.steps.length*100;
 const percent=Math.floor(end/r.trace.steps.length*10);if(percent!==r.lastLabel){r.lastLabel=percent;$('animationStatus').textContent=`${r.trace.algorithm==='astar'?'A*':'UCS'}: memeriksa ${s.step.toLocaleString('id-ID')} / ${r.trace.total.toLocaleString('id-ID')} state.${r.trace.truncated?' Tampilan dibatasi 10.000 langkah, termasuk langkah tujuan.':''}`;}
 }
 if(r.index>=r.trace.steps.length){finishReplay(false);return;}
 replayFrame=requestAnimationFrame(advanceReplay);
}
function finishReplay(skipped){
 stopReplay();if(!lastResult)return;
 $('animationLayer').replaceChildren();$('routeLayer').style.display='';$('animationProgress').value=100;$('animationPlay').textContent='Putar ulang';
 $('animationStatus').textContent=(skipped?'Pemutaran dilewati. ':'Pemutaran selesai. ')+`Rute hasil utama (UCS) menuju ${lastResult.hospital}.`;
}
$('animationPlay').onclick=()=>{if(!lastResult)return;if(!replay||replay.index>=replay.trace.steps.length||!$('animationLayer').childElementCount){startReplay();return;}if(replay.running){stopReplay();$('animationPlay').textContent='Lanjutkan';}else{replay.running=true;replay.last=0;$('animationPlay').textContent='Jeda';replayFrame=requestAnimationFrame(advanceReplay);}};
$('animationSkip').onclick=()=>finishReplay(true);
$('animationAlgorithm').onchange=startReplay;
document.addEventListener('visibilitychange',()=>{if(document.hidden&&replay?.running){stopReplay();$('animationPlay').textContent='Lanjutkan';}});

(function watchEngine(){
 const chip=$('engineState');let tries=0;
 async function poll(){
  try{const h=await api('/api/health');if(h.ready){chip.textContent='Mesin rute siap';chip.className='engine ready';return;}chip.textContent='Memanaskan mesin rute…';chip.className='engine';}
  catch{chip.textContent='Server tidak merespons';chip.className='engine failed';}
  if(++tries<300)setTimeout(poll,tries<10?1000:3000);
 }
 poll();
})();
