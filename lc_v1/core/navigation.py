"""Isolated, focus-scoped mouse/keyboard navigation for the Plotly scene."""
import json
import plotly.io as pio
import streamlit.components.v1 as components


def render_navigable_scene(fig, height, revision):
    # Assign explicitly: update_layout merges arrays and [] can retain old menus.
    fig.layout.updatemenus = ()
    fig.update_layout(scene_dragmode='pan', margin=dict(l=0, r=0, t=10, b=90))
    html = pio.to_html(fig, include_plotlyjs=True, full_html=False,
                       div_id='scene', config=dict(displayModeBar=False, scrollZoom=True))
    script = r'''
<style>
body{margin:0;font-family:system-ui}#scene{outline:none}
#hint{position:fixed;top:10px;left:12px;background:#172333dd;color:white;padding:8px 12px;border-radius:10px;font-size:12px;pointer-events:none;z-index:10}
#cursor{position:fixed;display:none;pointer-events:none;background:#123b56;color:white;border-radius:20px;padding:5px 9px;font-size:12px;z-index:20}
</style>
<div id="hint">Left-drag: move · Right-drag: center turns / edges roll · WASD: move · Scroll: zoom · R: reset</div>
<div id="cursor">↻ Rotate</div>
<script>
const gd=document.getElementById('scene'), badge=document.getElementById('cursor');
gd.tabIndex=0;
const home=JSON.parse(JSON.stringify(gd.layout.scene.camera || {eye:{x:1.25,y:1.25,z:1.25},up:{x:0,y:0,z:1},center:{x:0,y:0,z:0}}));
const storageKey=KEY;
try{const old=JSON.parse(sessionStorage.getItem(storageKey));if(old)Plotly.relayout(gd,{'scene.camera':old});}catch(e){}
gd.on('plotly_relayout',()=>{try{sessionStorage.setItem(storageKey,JSON.stringify(gd._fullLayout.scene.camera));}catch(e){}});
const arr=v=>[v.x,v.y,v.z], obj=v=>({x:v[0],y:v[1],z:v[2]});
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const unit=v=>{const n=Math.hypot(...v)||1;return v.map(x=>x/n)};
function rotate(v,axis,t){const c=Math.cos(t),s=Math.sin(t),dot=v.reduce((n,x,i)=>n+x*axis[i],0),q=cross(axis,v);return v.map((x,i)=>x*c+q[i]*s+axis[i]*dot*(1-c))}
function camera(){return JSON.parse(JSON.stringify(gd._fullLayout.scene.camera))}
let drag=null;
function zone(e){
 const r=gd.getBoundingClientRect(),cx=r.left+r.width/2,cy=r.top+(r.height-90)/2;
 return {cx,cy,roll:Math.hypot((e.clientX-cx)/(r.width*.5),(e.clientY-cy)/((r.height-90)*.5))>.72};
}
function hint(e,text){badge.textContent=text;badge.style.display='block';badge.style.left=(e.clientX+16)+'px';badge.style.top=(e.clientY+16)+'px';}
gd.addEventListener('contextmenu',e=>e.preventDefault());
gd.addEventListener('pointerdown',e=>{
 gd.focus({preventScroll:true});
 if(e.button!==2 && e.button!==0)return;
 // Leave legend clicks interactive; intercept only the actual scene canvas.
 if(e.target.tagName.toLowerCase()!=='canvas')return;
 e.preventDefault();e.stopImmediatePropagation();drag={x:e.clientX,y:e.clientY,pan:e.button===0,...zone(e)};
 hint(e,drag.pan?'✥ Move':drag.roll?'⟳ Roll view':'↻ Turn / tilt');
 gd.setPointerCapture(e.pointerId);badge.style.display='block';gd.style.cursor='grabbing';
},true);
gd.addEventListener('pointermove',e=>{
 if(!drag){hint(e,(e.buttons&1)?'✥ Move':(zone(e).roll?'Right-drag ⟳ Roll':'Right-drag ↻ Turn / tilt'));return;}e.preventDefault();e.stopImmediatePropagation();
 badge.style.left=(e.clientX+16)+'px';badge.style.top=(e.clientY+16)+'px';
 const c=camera(),up=unit(arr(c.up)),eye=arr(c.eye),right=unit(cross(up,eye));
 if(drag.pan){
   const scale=2/Math.max(200,gd.clientHeight);
   c.center=obj(arr(c.center).map((x,i)=>x+right[i]*(e.clientX-drag.x)*scale-up[i]*(e.clientY-drag.y)*scale));
 }else if(drag.roll){
   const before=Math.atan2(drag.y-drag.cy,drag.x-drag.cx),after=Math.atan2(e.clientY-drag.cy,e.clientX-drag.cx);
   c.up=obj(rotate(up,unit(eye),before-after));
 }else{
   let next=rotate(eye,up,-(e.clientX-drag.x)*.008);
   next=rotate(next,right,-(e.clientY-drag.y)*.008);
   c.up=obj(rotate(up,right,-(e.clientY-drag.y)*.008));c.eye=obj(next);
 }
 drag.x=e.clientX;drag.y=e.clientY;Plotly.relayout(gd,{'scene.camera':c});
},true);
function stop(e){if(!drag)return;drag=null;badge.style.display='none';gd.style.cursor='grab';if(e){e.preventDefault();e.stopImmediatePropagation();}}
gd.addEventListener('pointerup',stop,true);gd.addEventListener('pointercancel',stop,true);
// Block Plotly's legacy mouse listeners while our pointer gesture owns the camera.
gd.addEventListener('mousedown',e=>{if(drag){e.preventDefault();e.stopImmediatePropagation();}},true);
gd.addEventListener('blur',()=>stop());
gd.addEventListener('pointerleave',()=>{if(!drag)badge.style.display='none';});
gd.addEventListener('keydown',e=>{
 const k=e.key.toLowerCase();if(!['w','a','s','d','r'].includes(k))return;
 e.preventDefault();e.stopPropagation();
 if(k==='r'){Plotly.relayout(gd,{'scene.camera':JSON.parse(JSON.stringify(home))});return;}
 const c=camera(),up=unit(arr(c.up)),right=unit(cross(up,arr(c.eye)));
 const direction=(k==='w'||k==='s')?up:right,sign=(k==='w'||k==='d')?1:-1;
 c.center=obj(arr(c.center).map((x,i)=>x+direction[i]*sign*(e.shiftKey?.12:.04)));
 Plotly.relayout(gd,{'scene.camera':c});
});
</script>'''
    components.html(html + script.replace('KEY', json.dumps('bone-camera-' + revision)),
                    height=height + 10, scrolling=False)
