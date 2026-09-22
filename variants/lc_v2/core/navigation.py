"""Persistent single-purpose modes for the reconstruction camera."""
import json
import numpy as np
import plotly.io as pio
import streamlit.components.v1 as components


def bone_view_ranges(fig):
    """Fit visible bone traces only; distant tracker decorations must not dominate."""
    points = []
    for trace in fig.data:
        name = str(trace.name or '').lower()
        if trace.visible in (False, 'legendonly'):
            continue
        if not ('bone' in name or name.endswith((' · accepted', ' · propagated'))):
            continue
        if trace.type not in ('scatter3d', 'mesh3d'):
            continue
        xyz = np.column_stack([trace.x, trace.y, trace.z]).astype(float)
        points.extend(xyz[np.isfinite(xyz).all(axis=1)])
    if not points:
        return None
    xyz = np.asarray(points)
    low, high = xyz.min(axis=0), xyz.max(axis=0)
    middle = (low + high) / 2
    half = max(float((high - low).max()) * .6, .5)
    return {axis: [float(c-half), float(c+half)] for axis, c in zip('xyz', middle)}


def render_navigable_scene(fig, height, revision, view_id="reconstruction", is_3d=True):
    bone_ranges = bone_view_ranges(fig) if is_3d else None
    paths = []
    if is_3d:
        for trace in fig.data:
            if str(trace.name).startswith(('Probe-tip pathway', 'Calibrated tip path')):
                xyz = np.column_stack([trace.x, trace.y, trace.z]).astype(float)
                xyz = xyz[np.isfinite(xyz).all(axis=1)]
                if len(xyz) > 1:
                    delta = xyz[1:] - xyz[0]
                    valid = np.flatnonzero(np.linalg.norm(delta, axis=1) > 1e-5)
                    if len(valid):
                        end = min(max(1, len(xyz)//20), 20)
                        if np.linalg.norm(xyz[end]-xyz[0]) < 1e-5:
                            end = int(valid[0])+1
                        paths.append({'name':str(trace.name),'start':xyz[0].tolist(),'next':xyz[end].tolist(),'low':xyz.min(axis=0).tolist(),'high':xyz.max(axis=0).tolist()})
    fig.layout.updatemenus = ()
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=130, b=90))
    fig.update_layout(**({'scene_dragmode':'orbit'} if is_3d else {'dragmode':'pan'}))
    html = pio.to_html(fig, include_plotlyjs=True, full_html=False,
                       div_id='scene', config=dict(displayModeBar=False, scrollZoom=True, doubleClick=False, responsive=True))
    script = r''' 
<style>
body{margin:0;font-family:system-ui;color:#172333}#scene{outline:none}
#controls{position:absolute;top:4px;left:8px;right:8px;display:flex;gap:7px;align-items:center;flex-wrap:wrap;z-index:10;background:#fffffff2;padding:6px;border-radius:8px}
button{font:inherit;font-size:14px;border:1px solid #8fa5b1;background:white;color:#172333;border-radius:6px;padding:7px 13px;cursor:pointer}
button[aria-pressed="true"]{background:#175c83;color:white;border-color:#175c83}button:focus-visible{outline:3px solid #63baff}
#hint{font-size:12px;color:#455b67}
</style>
<div id="controls" role="toolbar" aria-label="3D navigation">
<button type="button" data-mode="zoom" aria-pressed="false">Zoom</button>
<button type="button" data-mode="pan" aria-pressed="false">Move</button>
<button type="button" data-mode="orbit" aria-pressed="false">Rotate</button>
<button type="button" id="zoom-in" aria-label="Zoom in further">Zoom +</button>
<button type="button" id="zoom-out" aria-label="Zoom out further">Zoom −</button>
<button type="button" id="focus-bone">Focus bone</button>
<button type="button" data-turn="left" aria-label="Rotate left 15 degrees">↶ Left</button>
<button type="button" data-turn="right" aria-label="Rotate right 15 degrees">Right ↷</button>
<button type="button" data-turn="up" aria-label="Tilt up 15 degrees">↑ Tilt</button>
<button type="button" data-turn="down" aria-label="Tilt down 15 degrees">↓ Tilt</button>
<button type="button" data-turn="roll" aria-label="Roll 15 degrees">Roll</button>
<select id="path-choice" aria-label="Trajectory for snap"></select><button type="button" id="snap">Snap to trajectory start</button>
<button type="button" id="reset">Fit all / reset</button><span id="hint" aria-live="polite"></span>
</div>
<script>
const gd=document.getElementById('scene');
const paths=PATHDATA;
const picker=document.getElementById('path-choice'), snap=document.getElementById('snap');
paths.forEach((p,i)=>{const o=document.createElement('option');o.value=i;o.textContent=p.name;picker.appendChild(o);});
picker.hidden=paths.length<2;snap.hidden=!paths.length;
snap.addEventListener('click',()=>{
 const path=paths[Number(picker.value)||0], scene=gd._fullLayout.scene;
 const aspects=scene.aspectratio||{x:1,y:1,z:1};
 const map=p=>['x','y','z'].map((a,i)=>{const r=scene[a+'axis'].range;return (p[i]-(r[0]+r[1])/2)/(r[1]-r[0])*2*aspects[a];});
 const start=map(path.start), next=map(path.next), d=next.map((v,i)=>v-start[i]), n=Math.hypot(...d);if(n<1e-10)return;
 const forward=d.map(v=>v/n), base=Math.abs(forward[2])>.9?[0,1,0]:[0,0,1];
 const dot=base.reduce((v,x,i)=>v+x*forward[i],0), up=base.map((v,i)=>v-dot*forward[i]), un=Math.hypot(...up);
 const low=map(path.low),high=map(path.high),distance=Math.max(.12,Math.min(1.5,Math.hypot(...high.map((v,i)=>v-low[i]))*1.3));
 const obj=a=>({x:a[0],y:a[1],z:a[2]});
 Plotly.relayout(gd,{'scene.camera':{center:obj(start),eye:obj(start.map((v,i)=>v-forward[i]*distance)),up:obj(up.map(v=>v/un)),projection:{type:'perspective'}},'scene.dragmode':mode});
});
const cameraKey=KEY, modeKey=MODEKEY, is3D=IS3D, boneRanges=BONERANGES;
if(!is3D){document.querySelector('[data-mode=orbit]').remove();document.querySelectorAll('[data-turn]').forEach(b=>b.remove());}
document.getElementById('focus-bone').hidden=!boneRanges;
const home=JSON.parse(JSON.stringify(gd.layout.scene?.camera || {eye:{x:1.25,y:1.25,z:1.25},up:{x:0,y:0,z:1},center:{x:0,y:0,z:0}}));
const arr=v=>[v.x,v.y,v.z], obj=v=>({x:v[0],y:v[1],z:v[2]});
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const unit=v=>{const n=Math.hypot(...v)||1;return v.map(x=>x/n)};
function rotate(v,axis,t){const c=Math.cos(t),s=Math.sin(t),dot=v.reduce((n,x,i)=>n+x*axis[i],0),q=cross(axis,v);return v.map((x,i)=>x*c+q[i]*s+axis[i]*dot*(1-c))}
function zoomBy(factor){
 const update={}, layout=is3D?gd._fullLayout.scene:gd._fullLayout, prefix=is3D?'scene.':'';
 for(const axis of (is3D?['x','y','z']:['x','y'])){
  const r=layout[axis+'axis'].range, mid=(r[0]+r[1])/2, half=(r[1]-r[0])*factor/2;
  if(Math.abs(half)<1e-9 || !Number.isFinite(half))return;
  update[prefix+axis+'axis.range']=[mid-half,mid+half];update[prefix+axis+'axis.autorange']=false;
 }
 return Plotly.relayout(gd,update);
}
document.getElementById('zoom-in').addEventListener('click',()=>zoomBy(.7));
document.getElementById('zoom-out').addEventListener('click',()=>zoomBy(1/.7));
document.getElementById('focus-bone').addEventListener('click',()=>{
 const camera=JSON.parse(JSON.stringify(home));camera.center={x:0,y:0,z:0};
 camera.eye=obj(unit(arr(home.eye)).map(v=>v*1.6));
 const update={'scene.camera':camera,'scene.aspectmode':'cube'};
 for(const axis of ['x','y','z']){update['scene.'+axis+'axis.range']=boneRanges[axis];update['scene.'+axis+'axis.autorange']=false;}
 Plotly.relayout(gd,update);
});
document.querySelectorAll('[data-turn]').forEach(button=>button.addEventListener('click',()=>{
 const c=JSON.parse(JSON.stringify(gd._fullLayout.scene.camera)), center=arr(c.center), eye=arr(c.eye);
 const delta=eye.map((v,i)=>v-center[i]), up=unit(arr(c.up)), right=unit(cross(up,delta));
 const turn=button.dataset.turn, axis=turn==='roll'?unit(delta):(['up','down'].includes(turn)?right:up);
 const angle=(['right','down'].includes(turn)?-1:1)*Math.PI/12;
 c.eye=obj(rotate(delta,axis,angle).map((v,i)=>v+center[i]));c.up=obj(rotate(up,axis,angle));
 Plotly.relayout(gd,{'scene.camera':c});
}));
const buttons=[...document.querySelectorAll('[data-mode]')];
let mode=is3D?'orbit':'pan';
try{const saved=localStorage.getItem(modeKey);if((is3D?['zoom','pan','orbit']:['zoom','pan']).includes(saved))mode=saved;}catch(e){}
function selectMode(next){
 mode=next;
 buttons.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.mode===mode)));
 document.getElementById('hint').textContent={zoom:'Drag to zoom',pan:'Drag to move',orbit:'Drag to rotate'}[mode]+(is3D?' · Focus bone for close inspection; +/− changes the viewing range.':' · 2D image: use Reconstruction for 3D rotation.');
 try{localStorage.setItem(modeKey,mode);}catch(e){}
 return Plotly.relayout(gd,{[is3D?'scene.dragmode':'dragmode']:mode});
}
buttons.forEach(b=>b.addEventListener('click',()=>selectMode(b.dataset.mode)));
const initial={[is3D?'scene.dragmode':'dragmode']:mode};
try{const saved=JSON.parse(sessionStorage.getItem(cameraKey));if(saved)Object.assign(initial,saved);}catch(e){}
Plotly.relayout(gd,initial).then(()=>selectMode(mode));
gd.on('plotly_relayout',event=>{
 if(Object.keys(event).some(key=>is3D?key.startsWith('scene.'):key.startsWith('xaxis.')||key.startsWith('yaxis.'))){
  const state={}, layout=is3D?gd._fullLayout.scene:gd._fullLayout, prefix=is3D?'scene.':'';
  if(is3D){state['scene.camera']=layout.camera;state['scene.aspectmode']=layout.aspectmode;}
  for(const axis of (is3D?['x','y','z']:['x','y'])){state[prefix+axis+'axis.range']=layout[axis+'axis'].range;state[prefix+axis+'axis.autorange']=false;}
  try{sessionStorage.setItem(cameraKey,JSON.stringify(state));}catch(e){}
 }
});
// Suppress secondary-button shortcuts so dragging cannot switch to another tool.
for(const event of ['pointerdown','mousedown','contextmenu']){
 gd.addEventListener(event,e=>{if(e.target.tagName.toLowerCase()==='canvas' && (e.button!==0 || event==='contextmenu')){e.preventDefault();e.stopImmediatePropagation();}},true);
}
document.getElementById('reset').addEventListener('click',()=>Plotly.relayout(gd,is3D?{'scene.camera':JSON.parse(JSON.stringify(home)),'scene.dragmode':mode,'scene.xaxis.autorange':true,'scene.yaxis.autorange':true,'scene.zaxis.autorange':true,'scene.aspectmode':'data'}:{'xaxis.autorange':true,'yaxis.autorange':'reversed','dragmode':mode}));
</script>'''
    components.html(html + script.replace('PATHDATA', json.dumps(paths)).replace('BONERANGES', json.dumps(bone_ranges)).replace('MODEKEY', json.dumps('bone-navigation-v2-' + view_id)).replace('IS3D', 'true' if is_3d else 'false').replace('KEY', json.dumps('bone-camera-v3-' + view_id + '-' + revision)),
                    height=height + 10, scrolling=False)
