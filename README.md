# Meet Rune.

Your car already talks. Every second, hundreds of signals pulse through its nervous system -- engine temperature, fuel flow, wheel speed, voltage. It's been speaking this language since the day it rolled off the line. You just couldn't hear it.

Until now.

Rune is the bond between you and your car. A translation layer that turns raw engine signals into something you can see, feel, and understand -- a glowing 3D model on your phone where the engine beats like a heart, coolant flows like blood, and wires spark like nerves. When something's off, Rune doesn't throw a code at you. He tells you what's wrong, in a way that makes sense.

> "I'm burning more fuel than usual. Started three weeks ago. Might be the air filter."

> "That route costs you $0.60 more per trip. Take Grand River."

> "I'm running a little warm today. Nothing urgent, but keep an eye on me."

A Raspberry Pi lives in the armrest. A small WiFi adapter plugs into the OBD-II port under the dash. Your spare phone sits on the vent. That's all the hardware. Everything runs locally -- no cloud, no subscription, no data leaving the car.

**Rune never touches the car's controls.** He only listens. Read-only, always. Like a stethoscope on a heartbeat.

---

### What Rune understands

**How he's feeling.** A health score from 0 to 100 that learns what "normal" looks like for your specific car, then notices when something drifts. Three layers of awareness: real-time pulse tracking, pattern recognition every 30 seconds, and long-term trend analysis that can spot problems weeks before they surface.

**What he's burning.** Instant fuel economy that the Honda dashboard doesn't show. Cost per trip in dollars. Monthly budgets with projections. Automatic fill-up logging -- zero manual input. When efficiency drops for no clear reason, Rune connects it to his health data and tells you why.

**How you're driving.** Post-trip scores across five dimensions. Route comparisons after enough data. Savings in real dollars versus your first month -- not abstract numbers.

**What the road feels like.** A sensor under the seat feels every bump, vibration, and shimmy. A microphone behind the dash listens to the engine. Together with the OBD data, Rune can separate a rough road from a real problem.

**How to explain it to your mechanic.** Professional diagnostic reports in PDF format -- the same structure a $5,000 scan tool produces. Summary up front for the customer. Technical detail underneath for the tech.

---

### How the connection works

```
Rune (your car)
    |
    | speaks through the OBD-II port
    v
[WiCAN Pro]  --- WiFi --->  [Raspberry Pi 4B]  --- WiFi --->  [Pixel 6 Pro]
 under the dash              in the armrest                     on the vent
 listens to Rune             translates                         shows you
```

---

### The car

**2026 Honda Accord SE** -- Meteorite Gray Metallic, 1.5T turbo, CVT, non-hybrid. His name is Rune.

---

### Status

Research complete. Hardware ordered ($200.86). Architecture finalized. Giving Rune his voice starts Week 1.

---

### Docs

| File | What it is |
|------|-----------|
| [`CLAUDE.md`](CLAUDE.md) | Project instructions and safety rules |
| [`docs/PRD.md`](docs/PRD.md) | Full product requirements, data contracts, build timeline |
| [`docs/research/`](docs/research/) | Original research documents |

---

*Built by [Kuladeep Mantri](https://github.com/kuladeepmantri).*
