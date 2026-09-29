from __future__ import annotations
import json, math, os, time
from pathlib import Path
from srunner.scenariomanager.carla_data_provider import CarlaDataProvider

def _vec(v): return [float(v.x), float(v.y), float(v.z)]
def _to_list(x):
    if x is None: return None
    try:
        if hasattr(x, 'detach'): x=x.detach().cpu()
        if hasattr(x, 'numpy'): x=x.numpy()
        return x.tolist() if hasattr(x,'tolist') else x
    except Exception: return None

def _quadratic_ttc(rx, ry, vx, vy, radius):
    a=vx*vx+vy*vy; b=2*(rx*vx+ry*vy); c=rx*rx+ry*ry-radius*radius
    if a < 1e-8: return None
    d=b*b-4*a*c
    if d < 0: return None
    roots=[t for t in ((-b-math.sqrt(d))/(2*a),(-b+math.sqrt(d))/(2*a)) if t>=0]
    return min(roots) if roots else None

class CRADriveLoggerMixin:
    def _cra_init(self):
        self._cra_condition_id=os.environ.get('CRADRIVE_CONDITION_ID','unknown')
        p=os.environ.get('CRADRIVE_TRACE_PATH') or str(Path(os.environ.get('CRADRIVE_OUTPUT_ROOT','./cradrive_outputs'))/self._cra_condition_id/'trace.jsonl')
        self._cra_trace_path=Path(p); self._cra_trace_path.parent.mkdir(parents=True, exist_ok=True)
        self._cra_trace=self._cra_trace_path.open('a',encoding='utf-8',buffering=1)
        self._cra_prediction=None; self._cra_prediction_step=None
        self._cra_write({'event':'agent_setup','condition_id':self._cra_condition_id,'wall_time':time.time()})
    def _cra_write(self,row):
        try:self._cra_trace.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
        except Exception:pass
    def _cra_set_prediction(self, pred, step=None):
        self._cra_prediction=pred; self._cra_prediction_step=int(getattr(self,'step',-1) if step is None else step)
    def _cra_actor_state(self, actor, hero):
        t=actor.get_transform(); et=hero.get_transform(); v=actor.get_velocity(); ev=hero.get_velocity()
        dx=t.location.x-et.location.x; dy=t.location.y-et.location.y; dz=t.location.z-et.location.z
        yaw=math.radians(et.rotation.yaw); lon=math.cos(yaw)*dx+math.sin(yaw)*dy; lat=-math.sin(yaw)*dx+math.cos(yaw)*dy
        rvx=v.x-ev.x; rvy=v.y-ev.y; rv2=rvx*rvx+rvy*rvy
        tcpa=max(0.0,-(dx*rvx+dy*rvy)/rv2) if rv2>1e-8 else None
        dcpa=math.hypot(dx+rvx*tcpa,dy+rvy*tcpa) if tcpa is not None else None
        try:
            er=max(hero.bounding_box.extent.x,hero.bounding_box.extent.y); ar=max(actor.bounding_box.extent.x,actor.bounding_box.extent.y); radius=float(er+ar+0.5)
        except Exception: radius=3.0
        ttc=_quadratic_ttc(dx,dy,rvx,rvy,radius)
        speed=math.hypot(ev.x,ev.y); clearance=max(lon-radius,0.1)
        req_decel=speed*speed/(2*clearance) if (lon>radius and ttc is not None and ttc<=8.0) else None
        return {'id':int(actor.id),'type_id':actor.type_id,'role_name':actor.attributes.get('role_name',''),
          'distance_m':float(math.sqrt(dx*dx+dy*dy+dz*dz)),'longitudinal_m':float(lon),'lateral_m':float(lat),'vertical_offset_m':float(dz),
          'velocity':_vec(v),'relative_velocity_xy':[float(rvx),float(rvy)],'tcpa_s':tcpa,'dcpa_m':dcpa,'ttc_collision_radius_s':ttc,
          'collision_radius_m':radius,'required_stop_decel_mps2':req_decel}
    def _cra_snapshot(self, control, timestamp=None):
        try:
            world=CarlaDataProvider.get_world(); hero=CarlaDataProvider.get_hero_actor()
            if world is None or hero is None:return
            actors=[]
            for a in world.get_actors():
                if a.id==hero.id: continue
                role=a.attributes.get('role_name',''); tid=a.type_id
                if role.startswith('scenario') or tid.startswith('walker.'):
                    s=self._cra_actor_state(a,hero)
                    if s['distance_m']<=120 and abs(s['vertical_offset_m'])<=10: actors.append(s)
            actors.sort(key=lambda x:x['distance_m'])
            et=hero.get_transform(); acc=hero.get_acceleration(); vel=hero.get_velocity(); yaw=math.radians(et.rotation.yaw)
            long_acc=math.cos(yaw)*acc.x+math.sin(yaw)*acc.y
            speed=math.hypot(vel.x,vel.y)
            row={'event':'tick','condition_id':self._cra_condition_id,'step':int(getattr(self,'step',-1)),
                 'timestamp':float(timestamp) if timestamp is not None else None,'speed_mps':speed,'longitudinal_accel_mps2':float(long_acc),
                 'control':{'steer':float(control.steer),'throttle':float(control.throttle),'brake':float(control.brake)},
                 'new_model_inference':self._cra_prediction_step==int(getattr(self,'step',-1)),
                 'model_prediction':self._cra_prediction if self._cra_prediction_step==int(getattr(self,'step',-1)) else None,
                 'ego':{'velocity':_vec(vel),'acceleration':_vec(acc)},'scenario_actors':actors}
            self._cra_write(row)
        except Exception as e:self._cra_write({'event':'logging_error','error':repr(e),'step':int(getattr(self,'step',-1))})
    def _cra_close(self):
        try:self._cra_write({'event':'agent_destroy','wall_time':time.time()}); self._cra_trace.close()
        except Exception:pass
