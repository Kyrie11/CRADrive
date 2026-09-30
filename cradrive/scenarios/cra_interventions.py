"""CRADrive semantic intervention scenarios for Bench2Drive 0.0.4.

This file is copied into SCENARIO_RUNNER_ROOT/srunner/scenarios so RouteScenario's
dynamic class discovery can instantiate the custom scenario types from route XML.
The implementation intentionally reuses Bench2Drive's original behaviors and changes
only a small set of physical parameters read from config.other_parameters.
"""
from __future__ import print_function

import carla

from srunner.scenariomanager.carla_data_provider import CarlaDataProvider
from srunner.scenarios.basic_scenario import BasicScenario
from srunner.scenarios.pedestrian_crossing import PedestrianCrossing
from srunner.scenarios.highway_cut_in import HighwayCutIn, convert_dict_to_location
from srunner.scenarios.hard_break import HardBreakRoute


def _param(config, name, cast, default):
    if name not in config.other_parameters:
        return default
    value = config.other_parameters[name].get("value", default)
    return cast(value)


class CRAPedestrianCrossing(PedestrianCrossing):
    """PedestrianCrossing with matched, XML-controlled causal variables.

    Supported XML children:
      <cra_reaction_time value="3.5"/>
      <cra_min_trigger_dist value="4.0"/>
      <cra_ped_speed value="1.6"/>          # optional fixed speed for all walkers
      <cra_ped_idle_time value="0.0"/>      # optional fixed idle time for all walkers
      <cra_ped_yaw_offset value="0.0"/>     # 180 => same spawn/salience, walking away
      <cra_ego_end_distance value="40.0"/>

    Lower reaction_time means the pedestrian starts later relative to ego arrival and
    is therefore the intended higher-risk intervention. The min trigger distance is
    kept small in CRADrive routes so it does not dominate the time-to-arrival trigger.
    """

    def __init__(self, world, ego_vehicles, config, debug_mode=False, criteria_enable=True, timeout=60):
        self._wmap = CarlaDataProvider.get_map()
        self._trigger_location = config.trigger_points[0].location
        self._reference_waypoint = self._wmap.get_waypoint(self._trigger_location)
        self._rng = CarlaDataProvider.get_random_seed()

        self._adversary_speed = _param(config, "cra_ped_speed", float, 1.3)
        self._reaction_time = _param(config, "cra_reaction_time", float, 3.5)
        self._min_trigger_dist = _param(config, "cra_min_trigger_dist", float, 4.0)
        self._ego_end_distance = _param(config, "cra_ego_end_distance", float, 40.0)
        yaw_offset = _param(config, "cra_ped_yaw_offset", float, 0.0)
        fixed_speed = config.other_parameters.get("cra_ped_speed")
        fixed_idle = config.other_parameters.get("cra_ped_idle_time")
        self.timeout = timeout

        self._walker_data = [
            {'x': 0.4, 'y': 1.5, 'z': 1.2, 'yaw': 270 + yaw_offset},
            {'x': 1.0, 'y': 2.5, 'z': 1.2, 'yaw': 270 + yaw_offset},
            {'x': 1.6, 'y': 0.5, 'z': 1.2, 'yaw': 270 + yaw_offset},
        ]
        for walker_data in self._walker_data:
            walker_data['idle_time'] = (
                float(fixed_idle['value']) if fixed_idle is not None else self._rng.uniform(0, 1.5)
            )
            walker_data['speed'] = (
                float(fixed_speed['value']) if fixed_speed is not None else self._rng.uniform(1.3, 2.0)
            )

        # Call BasicScenario directly so inherited PedestrianCrossing methods use the
        # parameters above instead of the hard-coded defaults in its __init__.
        BasicScenario.__init__(
            self, "CRAPedestrianCrossing", ego_vehicles, config, world, debug_mode,
            criteria_enable=criteria_enable
        )


class CRAHighwayCutIn(HighwayCutIn):
    """HighwayCutIn with XML-controlled cut-in kinematics.

    Supported XML children:
      <cra_speed_perc value="80"/>          # speed as % of ego at cut-in initialization
      <cra_cut_in_distance value="10"/>
      <cra_same_lane_time value="0.3"/>
      <cra_other_lane_time value="3.0"/>
      <cra_change_time value="2.0"/>
      <cra_extra_space value="170"/>

    The default pilot varies speed_perc only: a slower cut-in vehicle creates a larger
    closing-rate demand while keeping route, spawn, target geometry and weather fixed.
    Realized relative distance / closing speed / TTC are logged by CRADrive and should
    be used in analysis rather than assuming the nominal parameter is exact TTC.
    """

    def __init__(self, world, ego_vehicles, config, randomize=False, debug_mode=False,
                 criteria_enable=True, timeout=180):
        self._world = world
        self._map = CarlaDataProvider.get_map()
        self.timeout = timeout

        self._same_lane_time = _param(config, "cra_same_lane_time", float, 0.3)
        self._other_lane_time = _param(config, "cra_other_lane_time", float, 3.0)
        self._change_time = _param(config, "cra_change_time", float, 2.0)
        self._speed_perc = _param(config, "cra_speed_perc", float, 80.0)
        self._cut_in_distance = _param(config, "cra_cut_in_distance", float, 10.0)
        self._extra_space = _param(config, "cra_extra_space", float, 170.0)
        self._start_location = convert_dict_to_location(config.other_parameters['other_actor_location'])

        BasicScenario.__init__(
            self, "CRAHighwayCutIn", ego_vehicles, config, world, debug_mode,
            criteria_enable=criteria_enable
        )


class CRAHardBreakRoute(HardBreakRoute):
    """HardBreakRoute with controllable stop duration/end distance.

    This scenario is included for later robustness checks. It is *not* in the default
    causal pilot because Bench2Drive background traffic controls the front-car headway,
    making severity less clean than PedestrianCrossing / HighwayCutIn.
    """

    def __init__(self, world, ego_vehicles, config, randomize=False, debug_mode=False,
                 criteria_enable=True, timeout=60):
        self.timeout = timeout
        self._stop_duration = _param(config, "cra_stop_duration", float, 10.0)
        self.end_distance = _param(config, "cra_end_distance", float, 15.0)
        BasicScenario.__init__(
            self, "CRAHardBreak", ego_vehicles, config, world, debug_mode,
            criteria_enable=criteria_enable
        )
