# RideShield — 48hr Build Plan (6-person team)

> **Build target:** A working, demo-ready RideShield prototype for a 36–48 hour hackathon sprint, aligned with the submitted SIH proposal and mentor rubric.
>
> **Core positioning:** RideShield is a shift-based micro-insurance and risk/accident intelligence layer for gig workers. Coverage activates when a rider starts a work shift, risk intelligence continuously scores riding behaviour, and accident intelligence verifies impact-like events before claim generation. The submitted proposal explicitly frames the system around shift-based coverage, dynamic risk-based pricing, multi-signal accident verification, and evidence-driven claims.
>
> The submitted PPT identifies React Native for the rider app, React + Tailwind for the insurer dashboard, Python + FastAPI for the backend/risk engine, PostgreSQL/Neon for data, a message queue for concurrent telemetry load, Razorpay for UPI AutoPay, Twilio for L2 escalation, and OpenStreetMap Overpass for GPS-hospital matching. See PPT pages 4–7.

---

## 0. Ground Rules for the 6-Person Team

### The first hour is non-negotiable

All three pairs must agree on:

- REST API contract
- Authentication format
- Request/response JSON
- Database entities
- Telemetry payload shape
- Incident/claim state transitions
- Error response format
- Environment-variable names
- Mock data format

**Do not wait for the backend to be finished.** Everyone codes against mocked responses that match the contract.

This is the single biggest integration risk in a 48-hour hackathon.

### Important architecture decision

The submitted PPT uses:

- React Native rider app
- React + Tailwind insurer dashboard
- Python + FastAPI backend/risk engine
- PostgreSQL/Neon
- Message queue
- Razorpay
- Twilio
- OpenStreetMap Overpass
- JWT authentication
- Vercel + Railway deployment

For the 48-hour build, keep that architecture wherever practical.

**Do not introduce unnecessary technologies.** If the team already has stronger experience with an equivalent implementation, use the simplest implementation that preserves the architecture and demo story.

---

# Pair A — React Native Rider App + Insurer Dashboard

## Hour 0–2 — Setup

### Rider app

- Scaffold React Native / Expo project
- Navigation
- JWT auth screens
- Login/signup
- Basic rider profile
- Start Shift screen
- Shift status state

### Insurer dashboard

- React + Tailwind scaffold
- Routing
- Login
- Dashboard shell
- Claims list
- Claim detail placeholder
- Analytics placeholder

### Deliverable

Both clients can run independently and consume mocked API responses.

---

## Hour 2–10 — Core Rider App

Build:

### Shift activation

- Start Shift
- Show coverage activation
- Show premium
- Trigger Razorpay test/sandbox flow
- Shift timer
- End Shift

The submitted mentor rubric specifically describes the proposed mechanism as a per-shift UPI AutoPay premium and coverage activating when the rider logs in to work for a shift.

### Live telemetry

Use:

- `expo-location`
- Accelerometer
- Gyroscope
- `react-native-maps`
- `react-native-svg` for visualization

Track:

- GPS
- Speed
- Acceleration
- Gyroscope
- Timestamp
- Shift ID

### Sampling

Do **not** send every raw sensor sample individually to the backend.

Use:

- local sensor sampling at the required frequency
- local feature calculation
- approximately 1-second telemetry batches to backend

This preserves the PPT's "batched telemetry" architecture while keeping server load manageable.

---

# Hour 10–20 — Crash Flow + Claim UI

Implement the exact three-level escalation story from the PPT.

## L1 — On-device

When high crash confidence is detected:

- Full-screen alert
- Audible countdown
- 15-second response window
- "I'm OK"
- "Confirm Incident"

If the rider confirms:

→ create/confirm incident

If the rider does not respond:

→ move to L2

## L2 — Multi-channel

Show:

- SMS
- WhatsApp
- IVR status

Backend triggers Twilio.

The app should display:

> "No response detected. Emergency verification initiated."

## L3 — Sensor Fusion

Show:

- GPS
- Motion
- Orientation
- Post-impact motion/stillness
- Incident confidence

If validated:

→ Verified Accident Event

→ Claim generated

### Claim screen

Display:

- Claim ID
- Incident timestamp
- Location
- Telemetry snapshot
- Crash confidence
- Evidence bundle
- Claim status
- Verification level

### SOS

Add:

- Emergency call shortcut
- Current location display

---

# Hour 20–32 — Insurer Dashboard

Build:

## Claims list

Show:

- Claim ID
- Rider
- Date/time
- Location
- Risk level
- Claim status
- Severity

## Claim detail

Show:

- Rider information
- Shift information
- Incident timeline
- GPS location
- Sensor evidence
- Crash confidence
- Risk score
- Escalation history
- Claim status

## Live claims feed

A claim appearing on the dashboard immediately after a simulated crash is a major demo moment.

## Analytics

Keep it simple but visual:

- Total shifts
- Active policies
- Claims
- Verified incidents
- Risk distribution
- Low / Medium / High shift risk

Do not spend hours building complex actuarial analytics.

---

# Hour 32–44 — Offline Resilience + Polish

This is a differentiator.

Implement a local queue using:

- `expo-sqlite`

or, if time is extremely tight:

- AsyncStorage

Queue:

- telemetry batches
- incident candidates
- confirmed claims/events

When network returns:

1. Read local queue
2. Send events
3. Confirm server acknowledgement
4. Remove successfully synced events

### Socket/realtime resilience

Implement reconnect/backoff behavior.

If connectivity disappears:

- Keep local telemetry processing alive
- Show "Offline — data queued"
- Do not crash
- Continue local crash detection
- Sync later

### Shift summary

Display:

- Shift duration
- Distance
- Average/max speed
- Risk score
- Number of events
- Incidents
- Premium

### Final UI polish

- Consistent typography
- Consistent cards
- Clear status badges
- Loading states
- Empty states
- Error states
- Mobile-safe layouts
- No dead buttons

---

# Pair B — Backend + Database

## Hour 0–2 — Setup

Create:

- FastAPI application
- PostgreSQL / Neon connection
- Connection pooling
- Environment configuration
- JWT authentication
- Database migrations/schema

### Core entities

The PPT data layer identifies:

- Users
- Shifts
- Telemetry
- Incidents
- Claims
- Payments

Use these as the minimum schema.

---

# Hour 2–14 — Core API + Telemetry Ingestion

## REST endpoints

### Auth

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`

### Riders

- `GET /riders/me`
- `PUT /riders/me`

### Shifts

- `POST /shifts/start`
- `POST /shifts/end`
- `GET /shifts`
- `GET /shifts/:id`

### Claims

- `GET /claims`
- `GET /claims/:id`

### Incidents

- `POST /incidents`
- `GET /incidents/:id`

---

## Batched telemetry

Example:

```json
{
  "shift_id": "shift_123",
  "samples": [
    {
      "timestamp": 1720000000,
      "lat": 19.07,
      "lng": 72.87,
      "speed": 42.1,
      "accel_x": 1.2,
      "accel_y": 0.3,
      "accel_z": 9.8,
      "gyro_x": 0.1,
      "gyro_y": 0.2,
      "gyro_z": 0.4
    }
  ]
}
```

The exact schema can be adjusted during Hour 0–2, but it must be frozen afterward.

---

# Message Queue

The PPT explicitly proposes a queue to buffer concurrent event load.

For the hackathon:

### Preferred

- Redis Streams

### Acceptable fallback

- Redis list/queue

### Do not spend the sprint fighting Kafka

The architectural story remains:

```text
Rider
  ↓
Batched Telemetry
  ↓
API
  ↓
Message Queue
  ↓
Worker
  ↓
PostgreSQL
```

This is important because the submitted feasibility section explicitly identifies message queues as the mitigation for concurrent telemetry load.

---

# Hour 14–26 — Claims + Razorpay + Twilio

## Claim intake

When a verified accident event occurs:

```text
Crash Candidate
      ↓
Verification
      ↓
Verified Accident
      ↓
Evidence Bundle
      ↓
Claim Created
```

Evidence should include:

- GPS
- Timestamp
- Telemetry snapshot
- Crash features
- Risk score
- Incident confidence
- Escalation status

---

## Claim state machine

Keep it simple:

```text
PENDING
   ↓
UNDER_REVIEW
   ↓
APPROVED / REJECTED
```

For demo purposes, insurer approval can be manually triggered.

Do not build full insurer underwriting logic.

The submitted proposal explicitly positions RideShield as a risk-scoring and real-time pricing/collection layer that plugs into an existing IRDAI-licensed micro-insurance partner rather than inventing underwriting from scratch.

---

# Razorpay

Use sandbox/test mode.

Demo:

```text
Start Shift
    ↓
Premium shown
    ↓
Razorpay test flow
    ↓
Payment successful
    ↓
Coverage Activated
```

The submitted PPT explicitly lists Razorpay for per-shift UPI AutoPay.

---

# Twilio

Implement L2 escalation.

Example:

```text
High crash confidence
        ↓
15-second L1 alert
        ↓
No rider response
        ↓
Twilio
   ├── SMS
   ├── WhatsApp
   └── IVR
```

For the hackathon, the exact production-grade telephony setup is not the goal.

The goal is a believable, demonstrable escalation path.

---

# Hour 26–38 — Risk Engine + Dashboard APIs

Build APIs for:

- active shifts
- policies
- claims
- incidents
- analytics
- risk distribution
- claim evidence

### Risk Engine

Pair C provides:

```text
Speed
+
Braking
+
Riding Behaviour
        ↓
Shift Risk Score
        ↓
Low / Medium / High
        ↓
Pricing Input
```

Get this integration working **before Hour 38**.

Do not leave Pair C → Pair B integration for the final hours.

---

# Hour 38–46 — Load + Resilience + Integration

Run a simple concurrent telemetry simulation.

Measure:

- requests/sec
- successful batches
- queue depth
- processing latency
- database write time
- error rate

Do not invent a performance number for the presentation.

If you measure:

> 120 telemetry batches/minute in our local test

say exactly that.

Do not say:

> "supports millions of riders"

unless you have actually demonstrated or properly qualified the claim.

The PPT currently presents millions of concurrent riders as a scalability concern and proposes queueing, edge inference, pooling, and replicas as mitigations — that is an architecture claim, not proof of production scale.

---

# Pair C — Risk Engine + Crash Detection / Edge ML

# Hour 0–4 — Data + Feature Design

This is where you go beyond the current PPT implementation.

The submitted feasibility page currently describes a **rule-based crash-signature filter** using:

- acceleration spike
- gyroscope
- stationary window

and on-device crash-signature + risk scoring.

For the "Impossible Level" build, upgrade the crash detector to a tiny classifier.

---

# "Impossible Level" for a Hackathon

Judges have seen a hundred crash-detection dashboards.

The bar isn't:

> "Does it work?"

The bar is:

> "Does it feel real, does it survive live poking, and does something genuinely surprising happen?"

Here's the implementation target.

---

# 1. Detection Logic — Go One Level Past the Existing Rule Engine

The rolling-baseline + multi-signal AND-gate is the **floor**, not the ceiling.

At "Impossible Level", add a lightweight on-device classifier.

## Tiny classifier

You do **not** need a real-world crash dataset for the hackathon.

Generate synthetic labeled data by recording:

### Normal/non-crash events

- Walking
- Running
- Sitting
- Normal riding
- Normal braking
- Phone movement

### Crash-like events

- Hard shake
- Hard tap
- Deliberate phone drop onto a cushion
- Sudden movement
- Fall-like movement

Label each event.

Target:

- 50–100+ labeled synthetic events

Then train:

- Decision Tree

or:

- Logistic Regression

Do not use a large neural network.

The goal is:

- fast training
- interpretable features
- easy deployment
- easy explanation to judges

---

# Feature Engineering

Do not rely only on raw acceleration magnitude.

Calculate:

### Acceleration magnitude

```text
sqrt(ax² + ay² + az²)
```

### Jerk

```text
Δacceleration / Δtime
```

### Gyroscope magnitude

```text
sqrt(gx² + gy² + gz²)
```

### Gyroscope variance

Measure rotational instability over the window.

### Peak-to-baseline ratio

```text
peak acceleration / rolling baseline
```

### Post-event stillness

Measure how long the device remains unusually still after the event.

### Rolling baseline

Maintain a recent normal-motion baseline.

---

# Example Detection Pipeline

```text
Raw Sensors
    ↓
Acceleration + Gyroscope
    ↓
Feature Extraction
    ├── Acceleration magnitude
    ├── Jerk
    ├── Gyro magnitude
    ├── Gyro variance
    ├── Peak/baseline ratio
    └── Post-event stillness
    ↓
Tiny Classifier
    ↓
Crash Probability
    ↓
Multi-Signal Verification
    ↓
L1 Alert
```

The classifier should **not** automatically create a claim.

It should identify a high-confidence candidate.

Then the verification pipeline takes over.

---

# On-Device Inference

Preferred:

- TensorFlow Lite via `react-native-fast-tflite`

If that becomes a time sink:

- manually encode a small decision tree in JavaScript

A tiny decision tree is perfectly acceptable for the prototype.

The key claim is:

> Detection works locally, without requiring continuous network connectivity.

This is consistent with the PPT's edge-first positioning.

---

# Hour 14–22 — On-Device Integration

Work directly with Pair A.

Get:

```text
Sensor
 ↓
Feature extraction
 ↓
Classifier
 ↓
Crash confidence
 ↓
L1 alert
```

running inside the rider application.

## Three-level escalation

### L1

On-device:

- Full-screen alert
- Audible countdown
- 15 seconds

### L2

Backend/multi-channel:

- SMS
- WhatsApp
- IVR

### L3

Sensor fusion:

- GPS
- Motion
- Orientation
- Post-impact state

Then:

```text
Verified Accident
       ↓
Claim Generated
```

This preserves the exact conceptual architecture in the submitted PPT.

---

# Hour 22–34 — Risk Scoring Engine

Keep crash detection and risk scoring separate.

## Risk Intelligence

Runs continuously during the shift.

Inputs:

- speed
- braking
- riding behaviour

Output:

```text
Low
Medium
High
```

Then:

```text
Shift Risk Score
       ↓
Pricing Input
       ↓
Risk-aware Premium
```

Do **not** train a second complex ML model.

Use a transparent scoring function.

Example:

```text
Risk Score =
    speed_component
  + braking_component
  + behaviour_component
```

Normalize to:

```text
0–100
```

Then:

```text
0–33   → LOW
34–66  → MEDIUM
67–100 → HIGH
```

Exact thresholds can be tuned during testing.

---

# Hour 34–44 — Live Demo Instrumentation

This is one of the highest-value pieces of the whole project.

Build a live scrolling telemetry chart.

Show approximately the last 30 seconds.

Display:

- acceleration magnitude
- gyro magnitude
- rolling baseline
- crash threshold
- current risk score

When a crash-like event happens:

```text
Normal motion
───────────────
        /
       /
      /  ← spike
─────/────────────
       ↓
High crash confidence
       ↓
L1 Alert
```

The judge can **see the reason** the system fired.

---

# "Impossible Level" Demo Strategy

## 1. Let the judge trigger it

Do not use a hidden developer button.

Hand the judge the phone.

Say:

> "Try to trigger it. Shake it like a fall or tap/drop it onto this safe cushion."

The system should detect the event live.

This is much stronger than:

> "Here's a video of our system."

---

# 2. Show confidence and features

During the live demo show:

- G-force
- Gyro variance
- Jerk
- Baseline
- Crash confidence
- Risk score

A judge should be able to see:

```text
G-force        4.8 g
Gyro variance  2.7
Jerk           8.3
Crash conf.    94%
```

Use actual measured values from your system.

Never hard-code fake values while presenting them as sensor measurements.

---

# 3. Deliberately demonstrate a false-positive rejection

This is extremely important.

Demo:

```text
Light tap
   ↓
Sensor spike
   ↓
Candidate detected
   ↓
Multi-signal verification
   ↓
NOT A CRASH
   ↓
No claim
```

Then:

```text
Crash-like motion
   ↓
High confidence
   ↓
L1
   ↓
No response
   ↓
L2
   ↓
L3 verification
   ↓
Claim
```

Showing both paths demonstrates that the system is not simply:

```text
if acceleration > threshold:
    claim()
```

---

# 2. Make the Demo Self-Defending

The "Impossible Level" team wins here, not just on code.

Your system should survive a judge intentionally trying to break it.

## Judge poking checklist

Test:

- Turn Wi-Fi off
- Turn Wi-Fi back on
- Trigger a false-positive motion
- Trigger a crash-like motion
- Close/reopen the app if practical
- Send duplicate telemetry
- End a shift
- Start another shift
- Open the claim dashboard
- Inspect the evidence
- Ask why the event was classified as a crash
- Ask what happens if the rider does not respond

Your answers should be demonstrated by the product, not just verbally explained.

---

# 3. Full Stack — Build for Resilience

## Offline-first

Use:

- Expo SQLite

or:

- AsyncStorage for a lightweight queue

Queue locally:

- telemetry
- crash candidates
- incident events
- claim events

When connectivity returns:

```text
Local Queue
    ↓
Sync Worker
    ↓
Backend
    ↓
ACK
    ↓
Delete Local Event
```

Show:

> Offline — data queued

Then:

> Back online — syncing...

Then:

> 17 events synced

The number must be real.

---

# Reconnection

Use Socket/realtime reconnect logic with backoff.

A dropped connection must not kill:

- live map
- local sensor processing
- crash detection
- shift state

---

# 4. Replay / Audit Log

Add a per-shift audit log.

Store:

- sensor batches
- crash candidates
- rejected events
- confirmed incidents
- escalation transitions
- claim creation

Then the insurer dashboard can show:

```text
SHIFT #RSH-1024

09:41:02  Normal telemetry
09:41:17  Hard braking detected
09:42:03  Normal telemetry
09:43:11  Crash candidate
09:43:12  L1 alert
09:43:27  No response
09:43:29  L2 escalation
09:43:42  Sensor fusion passed
09:43:45  Claim generated
```

This is extremely useful when a judge asks:

> "Show me the data behind this claim."

---

# 5. Mock Insurer Dashboard

The dashboard does not need to be a production insurer platform.

It needs to make the ecosystem tangible.

Show:

## Live claims

```text
NEW CLAIM
Rider: #RS-1024
Risk: HIGH
Location: Mumbai
Confidence: 94%
Status: VERIFIED
```

## Claim evidence

- Map
- Timeline
- Sensor chart
- Risk score
- Escalation history
- Evidence bundle

## Analytics

- Claims
- Active shifts
- Risk distribution
- Verified incidents
- Average response time

---

# 6. G-Force / Gyro Dashboard — Push Past Gauges

Do not stop at:

```text
G-force: 2.3g
Gyro: 1.7
```

Use a live time-series chart.

Show approximately 30 seconds.

Overlay:

- acceleration magnitude
- gyro magnitude
- rolling baseline
- threshold

The judge should visually see the moment that crosses the detection boundary.

This demonstrates actual signal processing rather than just UI.

---

# 7. UPI AutoPay — Make the Mock Feel Real

Use Razorpay sandbox/test mode.

Demo:

```text
Rider
 ↓
Starts shift
 ↓
Premium calculated
 ↓
Razorpay test flow
 ↓
Payment successful
 ↓
Coverage Activated
```

Be explicit:

> "This is Razorpay sandbox/test mode."

Do not claim a production payment was processed.

---

# 8. What Separates Top-Percentile Teams

## They demo something live

Not a recorded video pretending to be live.

## They show rejection

Not just success.

## They show data

Not just claims.

## They survive failure

Wi-Fi off should not destroy the demo.

## They distinguish real vs mocked

Say:

> "This part is live."

> "This part is sandboxed."

> "This part is a prototype rule."

> "This part is future production integration."

This builds credibility.

---

# 9. Realistic Effort Allocation for 36–48 Hours

```text
40%  Telemetry + detection logic
20%  Offline-first resilience + sync
15%  Live chart + dashboard UI
15%  Payment + claim flow + insurer view
10%  Demo rehearsal + buffer
```

Do not let UI polish consume the time that belongs to telemetry and detection.

---

# Cross-Team Integration Timeline

## Hour 2 — API Contract Locked

All three pairs agree on:

- auth
- shifts
- telemetry
- incidents
- claims
- risk score
- payment
- errors

No major contract changes after this point.

---

## Hour 14 — First Real Integration

Must work:

```text
Pair A App
    ↓
Pair B Auth/Shift API

Pair C Detection
    ↓
Pair B Incident API
```

If this fails, stop new feature work and fix integration.

---

## Hour 26 — Full Pipeline Test

The following must work end-to-end:

```text
Rider starts shift
       ↓
Payment
       ↓
Coverage activated
       ↓
Telemetry
       ↓
Crash simulated
       ↓
L1 alert
       ↓
No response
       ↓
L2
       ↓
L3 verification
       ↓
Verified incident
       ↓
Claim generated
       ↓
Insurer dashboard
```

This is the main demo pipeline.

---

## Hour 38 — Feature Complete

At this point:

- no new major features
- no architecture changes
- no new libraries unless essential

Remaining work:

- bugs
- resilience
- visual polish
- demo reliability
- documentation

---

## Hour 44 — Feature Freeze

No new functionality.

Only:

- bug fixing
- integration
- testing
- demo rehearsal

---

# What NOT to Build

Protect the 48-hour sprint.

## Do not build

### Real insurer underwriting

Mock it.

The submitted proposal explicitly positions RideShield as the risk-scoring/pricing/collection layer rather than a complete underwriting system.

### Full Kafka infrastructure

Use Redis Streams/list if needed.

### Second complex ML model

Risk scoring can remain a transparent formula.

### Production medical verification

Represent the flow.

### Full insurer settlement infrastructure

Use mock approval/payout status.

### App-store deployment

Expo Go or equivalent demo deployment is enough.

### Huge analytics platform

Build only the metrics judges can understand immediately.

---

# Architecture Summary

```text
                         ┌──────────────────────┐
                         │    RIDER APP         │
                         │  React Native/Expo   │
                         │                      │
                         │ GPS                  │
                         │ Accelerometer        │
                         │ Gyroscope            │
                         │ Edge Crash Model     │
                         │ Risk Scoring         │
                         └──────────┬───────────┘
                                    │
                         Batched Telemetry
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   FASTAPI BACKEND    │
                         │                      │
                         │ Auth                 │
                         │ Shift API            │
                         │ Incident API         │
                         │ Claim API             │
                         │ Payment API           │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │     REDIS QUEUE      │
                         │                      │
                         │ Telemetry buffering  │
                         │ Concurrent events    │
                         └──────────┬───────────┘
                                    │
                          Worker / Processing
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
          ┌──────────────────┐            ┌──────────────────┐
          │   RISK ENGINE    │            │ CRASH DETECTION  │
          │                  │            │                  │
          │ Speed            │            │ Accel             │
          │ Braking          │            │ Gyro              │
          │ Behaviour        │            │ Jerk              │
          │                  │            │ Stillness         │
          │ Low/Med/High     │            │ Classifier        │
          └────────┬─────────┘            └────────┬─────────┘
                   │                               │
                   └──────────────┬────────────────┘
                                  ▼
                         ┌──────────────────┐
                         │    POSTGRESQL    │
                         │      / NEON      │
                         │                  │
                         │ Users            │
                         │ Shifts           │
                         │ Telemetry        │
                         │ Incidents        │
                         │ Claims           │
                         │ Payments         │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ INSURER DASHBOARD│
                         │ React + Tailwind  │
                         │                  │
                         │ Policies         │
                         │ Claims           │
                         │ Evidence         │
                         │ Analytics        │
                         └──────────────────┘

        External Services
        ┌───────────────────────────────────────────┐
        │ Razorpay → UPI AutoPay / Premium          │
        │ Twilio   → SMS / WhatsApp / IVR           │
        │ OSM      → GPS / Hospital Matching        │
        └───────────────────────────────────────────┘
```

---

# Final Demo Script

## Scene 1 — Start Shift

Rider opens app.

```text
START SHIFT
Premium: ₹X
Risk baseline: LOW
```

Complete Razorpay sandbox flow.

Show:

> COVERAGE ACTIVE

---

## Scene 2 — Normal Riding

Show:

- Map
- Speed
- G-force
- Gyro
- Risk score
- Live chart

Say:

> "Risk Intelligence runs continuously in the background."

---

## Scene 3 — False Positive

Lightly tap/shake phone.

Show:

```text
Motion spike
 ↓
Candidate
 ↓
Verification failed
 ↓
No claim
```

Say:

> "A spike alone is not enough."

---

## Scene 4 — Judge Triggers Crash

Hand phone to judge.

Let them safely trigger the crash signature.

Show:

```text
Acceleration spike
+
Gyro change
+
Jerk
+
Post-event stillness
        ↓
High crash confidence
```

Then:

> L1 — 15 second response window

---

## Scene 5 — No Response

Wait.

Show:

```text
No response
 ↓
L2
 ↓
SMS / WhatsApp / IVR
```

If external integration is sandboxed or unavailable, clearly label the UI as a simulated/test flow.

---

## Scene 6 — Sensor Fusion

Show:

```text
GPS
Motion
Orientation
Post-impact state
        ↓
Verified Accident
```

---

## Scene 7 — Claim

Show:

```text
CLAIM AUTO-GENERATED

Location
Telemetry
Timestamp
Risk Score
Crash Confidence
Incident Evidence
```

---

## Scene 8 — Insurer Dashboard

Open dashboard.

The claim appears live.

Show:

- claimant
- location
- timeline
- telemetry chart
- evidence
- risk score
- escalation history

---

## Scene 9 — Kill the Internet

Turn Wi-Fi off.

Continue collecting/processing local data.

Show:

> OFFLINE — DATA QUEUED

Turn Wi-Fi back on.

Show:

> BACK ONLINE — SYNCING

Then:

> X EVENTS SYNCED

Use the actual number.

---

# Claims Discipline

The submitted PPT contains literature figures including **92.3% crash recall and 14.8% false-positive rate** from reference [9]. These must **not** be presented as RideShield's measured performance unless your own testing actually produces those numbers. The PPT itself identifies those values as literature context. fileciteturn0file0L107-L114

For the hackathon, present:

```text
Literature benchmark:
92.3% recall
14.8% false-positive rate

Our prototype:
Measured on our synthetic/test dataset:
[YOUR ACTUAL RESULT]
```

Never fabricate the second line.

---

# What Is Real vs Mocked

Create a visible README/demo note with this distinction.

## Real / demonstrable

- React Native rider app
- Sensor collection
- Local feature extraction
- Crash classifier
- Risk scoring
- Telemetry batching
- Backend APIs
- PostgreSQL persistence
- Claim workflow
- Insurer dashboard
- Offline queue
- Evidence/audit log

## Sandbox/Test

- Razorpay payment
- Twilio communication
- Any external service credentials

## Prototype / simplified

- Risk pricing formula
- Synthetic training data
- Insurer underwriting decision
- Medical verification
- Production-scale load
- Full payout settlement

## Future scope

The submitted feasibility roadmap explicitly identifies:

- insurer integration
- payout integration
- large-scale field validation
- load testing

as future scope. fileciteturn0file0L319-L349

---

# Final 48-Hour Priority Order

If you start running out of time, cut features in this order:

## NEVER CUT

1. Start/end shift
2. Sensor collection
3. Crash detection
4. L1 alert
5. Claim creation
6. Insurer claim view
7. Risk score
8. Evidence bundle
9. Offline handling
10. End-to-end demo

## CUT IF NECESSARY

11. Advanced analytics
12. Hospital matching
13. Fancy animations
14. Complex payout screens
15. Advanced insurer controls

## DO NOT WASTE TIME ON

16. Production-grade underwriting
17. Full Kafka cluster
18. Second ML model
19. App-store release
20. Elaborate admin management

---

# Success Criteria at Hour 48

The project is successful if a judge can:

- Start a shift
- See coverage activate
- Observe live telemetry
- Trigger a crash-like event
- See the detection reason
- See false-positive rejection
- Watch L1 escalation
- Observe L2/L3 flow
- See a claim generated
- Open the evidence bundle
- See the claim on the insurer dashboard
- Turn off Wi-Fi
- Watch the app continue locally
- Restore connectivity
- Watch queued events sync
- Ask "why was this classified as a crash?"
- Get an answer from the actual displayed data

That is the "Impossible Level" target.

---

# One-Line Pitch

> **RideShield turns gig-worker insurance from a fixed product into a shift-aware protection system: pay when you work, price risk from how you ride, and verify accidents from real sensor evidence before a claim is generated.**

The core submitted architecture already supports this positioning: shift-based coverage, dual risk/accident intelligence, dynamic pricing, multi-signal verification, and evidence-driven claim generation. fileciteturn0file0L226-L315
