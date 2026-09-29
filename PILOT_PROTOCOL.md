# CRADrive v0.1 scientific pilot protocol

## Purpose

This pilot is designed to answer one question before investing in a full CVPR-scale benchmark:

> Do strong closed-loop driving policies exhibit response behavior that standard aggregate driving scores fail to reveal under matched semantic interventions?

A positive pilot is evidence that a richer causal-response benchmark may be worth building. It is **not** by itself evidence that a model is causally correct or incorrect.

## Experimental unit

A condition is one original Bench2Drive route cloned into its own XML. For the causal sweep, everything in the route is held fixed except one scenario parameter: `reaction_time`.

The uploaded Bench2Drive source documents this quantity as the time available to the agent to react to avoid the collision. CRADrive exposes the previously hard-coded quantity through the existing XML `other_parameters` mechanism; the scenario behavior is otherwise untouched.

## Pilot routes

The default configuration uses two validation routes that each contain exactly one target scenario:

1. Route 17749 / Town12 / `DynamicObjectCrossing_1`
2. Route 24519 / Town05 / `ParkingCrossingPedestrian_1`

Using one-scenario routes limits accidental interaction between the manipulated scenario and unrelated scripted hazards.

## Intervention grid

`DynamicObjectCrossing`:

```text
reaction_time = [1.2, 1.5, 1.8, 2.1, 2.4, 2.7, 3.0] seconds
```

`ParkingCrossingPedestrian`:

```text
reaction_time = [1.2, 1.5, 1.8, 2.15, 2.4, 2.7, 3.0] seconds
```

The original values are 2.1 s and 2.15 s (modulo the original crossing-angle adjustment).

## Negative controls

At the baseline causal parameter, two weather variants are generated. Geometry and scenario timing stay fixed while image appearance changes. In a mature benchmark, this negative-control set should be larger and better matched; here it is only a quick test for whether appearance variation produces policy changes comparable to the physical intervention.

## Logged variables

Every tick, the wrapper records:

- ego speed;
- throttle, brake, steer;
- DriveTransformer fixed-time trajectory prediction (on inference ticks);
- DriveTransformer fixed-distance trajectory prediction;
- ego transform/velocity/acceleration from CARLA;
- active scenario actors, including relative longitudinal/lateral distance and velocity.

Dormant actors temporarily placed below the map by Bench2Drive are excluded.

## Pilot metrics

The analysis deliberately avoids whole-route minimum speed because DriveTransformer brakes during its initialization frames.

Primary response metrics are localized to the target actor:

- minimum ego speed while the target is active, ahead of the ego, and within 40 m;
- maximum brake in the same hazard window;
- brake-onset distance to the target;
- ego speed near 20/15/10/5 m target distance;
- minimum target clearance;
- mean predicted fixed-time horizon displacement;
- standard Bench2Drive driving score / route completion / infraction penalty / collision count.

The most important plots are **speed vs. target distance** and **brake vs. target distance** across intervention values.

## Go / no-go decision

### Strong go

Continue toward the full research direction if at least one of the following is repeatable across routes and later across model families:

- aggregate driving score stays similar while response curves differ materially;
- response to increasing urgency is flat, discontinuous, or shows strong ordering violations;
- trajectory prediction changes but control response does not, or vice versa;
- nuisance weather changes behavior as much as the physical intervention;
- models with similar Bench2Drive score exhibit clearly different response curves.

### Moderate go

Continue, but refine the intervention/oracle, if harder settings expose near misses/collisions and the response is visibly delayed or inconsistent, even if the ordering is not clean enough to call a causal-alignment failure yet.

### No-go for the exact framing

Do not force the project if, after adding at least two additional model families:

- response curves are consistently smooth and semantically sensible;
- nuisance controls are stable;
- proposed response metrics are nearly redundant with standard closed-loop scores;
- observed failures can mostly be explained by simulator artifacts or malformed scenario intervention.

## What is still missing for a CVPR submission

The next stage should add:

1. a physically explicit conflict-point/TTC intervention family rather than relying only on the scenario's reaction-time proxy;
2. an expert/safety oracle or privileged simulator target defining the *desired* behavioral causal effect;
3. multiple policy families (at minimum DriveTransformer + LEAD + SimLingo or another VLA/world-model policy);
4. multiple scenario families: pedestrian crossing, vehicle cut-in, red-light intrusion, occlusion/reveal, and at least one nuisance-only family;
5. repeated routes/seeds and confidence intervals;
6. eventually, a response-alignment training objective only after the diagnostic gap is established.

The correct order is **observation first, repair second**. If the empirical gap is weak, do not spend time developing the training method.
