from __future__ import annotations
from lead.inference.sensor_agent import SensorAgent
from cradrive.agent_logging import CRADriveLoggerMixin, _to_list

def get_entry_point(): return 'CRADriveLEADAgent'
class CRADriveLEADAgent(SensorAgent, CRADriveLoggerMixin):
    def setup(self, path_to_conf_file, *args, **kwargs):
        super().setup(path_to_conf_file,*args,**kwargs); self._cra_init()
        orig=self.closed_loop_inference.forward
        def wrapped(*a,**kw):
            p=orig(*a,**kw)
            self._cra_set_prediction({'pred_future_waypoints':_to_list(p.pred_future_waypoints),'pred_route':_to_list(p.pred_route),
                                      'pred_target_speed_scalar':_to_list(p.pred_target_speed_scalar)})
            return p
        self.closed_loop_inference.forward=wrapped
    def run_step(self,input_data,timestamp,*args,**kwargs):
        c=super().run_step(input_data,timestamp,*args,**kwargs); self._cra_snapshot(c,timestamp); return c
    def destroy(self):
        self._cra_close()
        try:return super().destroy()
        except AttributeError:return None
