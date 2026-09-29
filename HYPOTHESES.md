# CRADrive v0.2: hypotheses and falsification gates

The purpose of this pilot is **not** to prove that a model is visually sensitive. It tests whether its closed-loop behavior changes in the physically appropriate direction under matched semantic interventions.

## H0 — Intervention validity
For every route family, changing `reaction_time` must actually produce an ordered change in privileged physical risk after the adversary becomes active. v0.2 measures constant-velocity time-to-collision/closest approach and the stopping deceleration implied by the current relative state. If the generated conditions do not produce an ordered physical-risk range, that route is excluded; model behavior on it is not evidence for or against the research hypothesis.

## H1 — Causal direction correctness
When measured physical risk increases, braking/deceleration should not systematically decrease and near-hazard speed should not systematically increase. Primary statistic: pairwise Causal Direction Accuracy (CDA) against the privileged physics-risk ordering. CDA=1 is perfectly ordered; CDA=0.5 is roughly chance pair ordering.

## H2 — Continuous/monotonic decision semantics
A continuous risk intervention should yield a reasonably monotonic response curve rather than flat, inverted, or abrupt non-physical transitions. Inspect `risk -> brake`, `risk -> speed`, brake-onset and clearance curves, not only a single correlation coefficient.

## H3 — Standard-score blind spot
Driving Score / route completion can remain similar while H1/H2 differ strongly. This is central to the proposed paper: ordinary benchmark success must not be equivalent to causal decision grounding. A useful signal is a stable score but >=0.20 CDA difference across models or conditions.

## H4 — Nuisance/appearance invariance
At the baseline causal setting, appearance-only weather changes (cloudiness/sun angle; zero rain/wetness/fog) preserve scenario geometry/physics. Their behavioral effect should be materially smaller than nearby causal interventions. If appearance changes dominate causal changes, that is a different but still interesting grounding failure; it must be reported separately.

## H5 — Cross-family / cross-model generality
The effect should appear in at least two policy families and at least two semantic scenario families. v0.2 uses DriveTransformer, LEAD-CVPR2026 and SimLingo; and pedestrian crossing, occluded pedestrian crossing and vehicle cut-in. A failure isolated to one model is evidence of an architecture bug, not yet a benchmark-level gap.

## H6 — No "always stop" interpretation
Safety response is not automatically correct merely because the car drives slower. Any later repair method must preserve route completion/progress/comfort and nominal performance. v0.2 therefore keeps standard Bench2Drive metrics alongside causal metrics.

## Go / no-go rule for the project
**GO:** repeated CDA < 0.8 / clear non-monotonicity in >=2/3 models on >=2 route/scenario groups, with standard score failing to reveal the same distinction.

**STRONG GO:** GO plus cross-model disagreement at similar Driving Score and causal response changes larger than appearance controls.

**NO-GO for this exact framing:** all three model families show CDA >=0.9, smooth response curves, stable appearance controls, and causal metrics add little information beyond the standard score. In that case move to a harder intervention family (occlusion reveal timing, junction priority, cut-in gap, traffic-light intrusion) rather than forcing a conclusion.

v0.2 intentionally does **not** claim exact magnitude alignment to a learned expert. It tests direction/threshold correctness against a privileged physics oracle. A paper-level CRA metric can add an expert/reference policy after the pilot passes the GO gate.
