from __future__ import annotations
import numpy as np
from DriveTransformer.team_code.drivetransformer_b2d_agent import DriveTransformerAgent
from cradrive.agent_logging import CRADriveLoggerMixin

def get_entry_point(): return 'CRADriveDriveTransformerAgent'
class CRADriveDriveTransformerAgent(DriveTransformerAgent, CRADriveLoggerMixin):
    def setup(self,path_to_conf_file):
        super().setup(path_to_conf_file); self._cra_init(); orig=self.controller.step
        def wrapped(tfix,dfix,speed):
            self._cra_set_prediction({'ego_traj_fix_time':np.asarray(tfix).tolist(),'ego_traj_fix_dist':np.asarray(dfix).tolist()}); return orig(tfix,dfix,speed)
        self.controller.step=wrapped
    def run_step(self,input_data,timestamp):
        c=super().run_step(input_data,timestamp); self._cra_snapshot(c,timestamp); return c
    def destroy(self):
        self._cra_close(); return super().destroy()
