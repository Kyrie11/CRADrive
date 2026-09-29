from __future__ import annotations
from team_code.agent_simlingo import LingoAgent
from cradrive.agent_logging import CRADriveLoggerMixin, _to_list

def get_entry_point(): return 'CRADriveSimLingoAgent'
class CRADriveSimLingoAgent(LingoAgent, CRADriveLoggerMixin):
    def setup(self,path_to_conf_file,*args,**kwargs):
        super().setup(path_to_conf_file,*args,**kwargs); self._cra_init()
        orig=self.model.forward
        def wrapped(*a,**kw):
            out=orig(*a,**kw)
            try:
                sp,rt,lang=out; self._cra_set_prediction({'pred_speed_waypoints':_to_list(sp),'pred_route':_to_list(rt),'language':_to_list(lang)})
            except Exception: pass
            return out
        self.model.forward=wrapped
    def run_step(self,input_data,timestamp,*args,**kwargs):
        c=super().run_step(input_data,timestamp,*args,**kwargs); self._cra_snapshot(c,timestamp); return c
    def destroy(self):
        self._cra_close()
        try:return super().destroy()
        except AttributeError:return None
