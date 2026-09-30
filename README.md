# CRADrive pilot

CRADrive is a minimally invasive pilot framework for testing the hypothesis:

> strong nominal closed-loop driving performance does not guarantee a correct causal behavioral response to decision-relevant visual changes.

The pilot keeps the original planner checkpoints unchanged. It adds (1) custom Bench2Drive scenario classes with XML-controlled physical variables, (2) matched route generation, (3) thin TCP/SimLingo wrappers that log direct planner response and privileged *evaluation-only* simulator state, and (4) monotonicity summaries.

## Default pilot

1. `pedestrian_reaction_time`: 2 official PedestrianCrossing routes × 5 reaction-time levels.
2. `pedestrian_direction_control`: same pedestrian spawn/appearance, crossing vs walking away.
3. `highway_cutin_speed`: 4 official HighwayCutIn routes × 5 relative-speed levels.

The config intentionally does **not** use HardBreakRoute for the first GO/STOP gate because its front-car headway comes from background traffic and is less cleanly controlled.

## Important validity rules

- Use the **same Bench2Drive 0.0.4 code and route XML** for TCP and SimLingo.
- Keep route, weather, trigger point and traffic-manager seed fixed within a matched family.
- Do not feed logged privileged actor state to the policy; it is evaluation-only.
- Treat nominal intervention parameters as controlled variables, but report realized distance/closing-speed/TTC from traces.
- A single odd frame is not evidence. Require reproducible failures across seeds/routes.

See `RUNBOOK_ZH.md` for commands.
