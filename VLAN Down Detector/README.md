# VLAN Down Detector v4.1.0

**Trigger for ExtraHop Reveal(x)**
Detects when active VLANs fall off the data feed.

---

## What it does

The trigger monitors which VLANs are actively passing packets through the ExtraHop sensor. When a VLAN that has been consistently active suddenly goes silent, the trigger commits a custom detection to Reveal(x).

It answers a simple question: "Is every VLAN that should be on the wire still on the wire?"

---

## Why it exists

ExtraHop doesn't have a built-in detection for data feed loss at the VLAN level. If a network TAP fails, a SPAN port drops, or a routing change silently removes a VLAN from the sensor's view, there's no native alert. This trigger fills that gap.

For [Customer], this runs as a **performance detection** (NPM mode) so it routes through their performance detection webhook, separate from the SOC/NDR pipeline.

---

## Three-phase architecture

The trigger runs on three ExtraHop events that work together on a coordinated 30-second cycle.

### Phase 1: VLAN Discovery (TIMER_30SEC + REMOTE_RESPONSE)

Every 5 minutes, the trigger queries the ExtraHop REST API to build a list of active VLANs.

**Step 1:** `GET /api/v1/networks/0/vlans` retrieves all known VLANs from the sensor.

**Step 2:** The response is filtered through `VLAN_EXCLUDE_IDS` to remove any VLANs that should be suppressed (lab networks, seasonal segments, etc.).

**Step 3:** `POST /api/v1/metrics` requests 7 days of hourly packet counts for the remaining VLANs. The request uses `cycle: '1hr'` explicitly so the bucket count is predictable. Using `cycle: 'auto'` could silently pick a different resolution and break the threshold math.

**Step 4:** The response is processed by counting how many hourly buckets each VLAN appears in. A VLAN must have traffic in every hourly bucket across the full 7-day window to qualify as "active." The expected bucket count is `(7 * 24) + 1 = 169`. This strict threshold prevents intermittent or decommissioned VLANs from generating false alarms.

**Step 5:** The active list is stored in the session table as a pipe-delimited string (e.g. `|100|200|300|`) with a 10-minute expiry. The pipe-delimited format is a deliberate performance choice explained in the Performance section below.

### Phase 2: Traffic Observation (METRIC_RECORD_COMMIT)

On every 30-second metric cycle, the `METRIC_RECORD_COMMIT` event fires once per VLAN that has network metrics. This is the hot path of the trigger.

For each record, the trigger checks:

1. Is this a `extrahop.vlan.net` record? If not, return immediately.
2. Does this VLAN have non-zero packets? If not, return. A VLAN emitting empty metric records but passing no actual traffic is functionally down.
3. Is this VLAN in our active list? If not, return.
4. Is this VLAN already in our "seen" set for this cycle? If so, return.
5. If all checks pass, append this VLAN ID to the "seen" string in the session table.

The "seen" set is reset to empty (`||`) at the end of each TIMER_30SEC cycle.

### Phase 3: Comparison and Detection (TIMER_30SEC)

At the start of each 30-second window, the trigger compares the active VLAN list against the "seen" set from the previous cycle.

For each active VLAN:

- **If seen:** The VLAN is healthy. If there's an existing down counter for this VLAN, clear it and log a recovery message.
- **If not seen:** Increment the down counter. If the counter reaches the threshold (default: 4 consecutive misses = 2 minutes), commit a detection.

After the initial detection fires, subsequent updates fire every `REFIRE_INTERVAL` cycles (default: 10 = 5 minutes) to refresh the description with the current downtime duration. Between refires, the trigger stays quiet to avoid flooding the detection timeline.

---

## Cold start behavior

When the trigger is first enabled or restarted, a warm-up guard skips the first comparison cycle. Without this, every active VLAN would appear "down" because no MRC traffic has been observed yet. The guard works by checking a session key (`vlan_det_init`) that persists for 24 hours. On the first cycle it's null, so the trigger sets it, logs a warm-up message, and skips `compareVlans()`. Every subsequent cycle finds the key and runs normally.

This means the trigger produces zero false detections on startup.

---

## Detection format

When a detection fires, it appears in Reveal(x) with these attributes:

| Field | Value |
|-------|-------|
| Type | `VLAN_Down_Detector` |
| Title | `Data Feed VLAN Lost` |
| Description | Markdown formatted (VLAN ID, duration, sensor hostname, cycle count) |
| Identity Key | `vlan_down_{VLAN_ID}` (per-VLAN deduplication) |
| Identity TTL | `day` (consolidates duplicates within 24 hours) |
| Participants | Empty array (no Flow context available on TIMER_30SEC) |
| Risk Score | Omitted in NPM mode |

The identity key and TTL work together: if the same VLAN triggers multiple detections within 24 hours, they consolidate into a single ongoing detection in Reveal(x). The TTL resets each time a new detection is consolidated, so a VLAN that stays down for 3 days produces one ongoing detection, not 72 separate ones.

### NDR mode (not currently active)

If `LICENSE_MODEL` is changed to `'NDR'`, the trigger adds a graduated risk score that starts at 50 when the threshold is first reached and ramps linearly to 99 over approximately 60 minutes (120 cycles). The detection name becomes `VLAN_Down_Detector_NDR` and the title gets an `(NDR)` suffix. This code is retained but inactive in NPM mode.

---

## Session table keys

The trigger uses 6 session key patterns. All use `Session.PRIORITY_HIGH` to resist eviction under memory pressure.

| Key | Value | Expiry | Purpose |
|-----|-------|--------|---------|
| `vlan_det_active` | Pipe-delimited string of active VLAN IDs | 600s | Survives one missed discovery cycle |
| `vlan_det_seen` | Pipe-delimited string of seen VLAN IDs | 60s | Resets every 30s cycle; 60s buffer for slow MRC commits |
| `vlan_det_down_{ID}` | Integer counter | 86400s | Matches identityTtl so counters never silently expire during a long outage |
| `vlan_det_init` | 1 | 86400s | Cold start guard; prevents false positives on restart |
| `vlan_det_disc` | Integer counter (0 to DISC_CYCLES-1) | 600s | Throttles API discovery to every N cycles |
| `vlan_det_swarn` | 1 | 86400s | Prevents repeated "empty static list" warnings |

### Why Session.replace instead of Session.increment for down counters

The best practices guide says to use `Session.increment` for counting because it's atomic. We deliberately use `Session.lookup` + `Session.replace` instead. The reason: `Session.increment` does not refresh the expiry timer on the key. During a long outage, the down counter would silently expire after `EXP_DOWN` seconds and reset to zero, causing the trigger to re-fire as if it were a new outage.

`Session.replace` refreshes the expiry timer on every call (confirmed in the API docs: "If the expire option is provided, the expiration timer is reset"). Since `TIMER_30SEC` is single-threaded, the atomicity tradeoff is irrelevant.

---

## Performance design

The `METRIC_RECORD_COMMIT` event fires once per VLAN per 30-second metric cycle. In a network with 50 VLANs, that's 50 trigger executions per cycle. Each one needs to be fast.

**Problem:** The best practices guide warns against calling `JSON.parse` or `JSON.stringify` on session table objects in high-volume events. The earlier versions of this trigger stored the active and seen lists as JSON arrays, which meant every MRC execution was doing `JSON.parse` + `JSON.stringify` + `Array.from(Set)`.

**Solution:** v4.1.0 stores both lists as pipe-delimited strings (e.g. `|100|200|300|`). Membership checks use `String.indexOf('|' + id + '|')`, which is a single native string operation with zero object allocation. The pipes on both ends prevent substring false matches (e.g. `|1000|` does not match a search for `|100|`).

JSON is still used in two places where it's unavoidable: the `REMOTE_RESPONSE` handler (which parses the API response body) and the `POST /metrics` payload. Both of these fire at most once every 5 minutes, so the performance impact is negligible.

### MRC filter cascade

The MRC handler uses five early returns to minimize work for non-matching records:

1. `MetricRecord.id !== 'extrahop.vlan.net'` — filtered by advanced trigger options before this even runs, but kept as a safety net
2. `pkts === undefined || pkts === 0` — zero-traffic VLANs are not "seen"
3. `activeStr === null || activeStr === '||'` — no active list yet (discovery hasn't run)
4. `!pipeHas(activeStr, vlanId)` — not a monitored VLAN
5. `pipeHas(seenStr, vlanId)` — already recorded this cycle

The session write (the expensive part) only happens when a new VLAN passes all five filters.

---

## Configuration reference

All parameters live in the `USER CONFIGURATION` block at the top of the script. No code changes needed.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `LICENSE_MODEL` | `'NPM'` | `'NPM'` for performance detection (no risk score). `'NDR'` adds graduated risk scoring and `_NDR` suffix. |
| `DYNAMIC_VLAN` | `true` | Auto-discover active VLANs via REST API. Set `false` to use `STATIC_VLAN_IDS` instead. |
| `API_ODS_TARGET` | `'EDA'` | Name of the HTTP Open Data Stream target configured in Administration settings. |
| `ACTIVE_DAYS_REQUIRED` | `7` | Days of continuous hourly traffic required for a VLAN to qualify as active. |
| `DISCOVERY_INTERVAL` | `300` | Seconds between API discovery runs. 300 = every 5 minutes. |
| `STATIC_VLAN_IDS` | `[]` | Manual VLAN ID list. Only used when `DYNAMIC_VLAN` is `false`. |
| `VLAN_EXCLUDE_IDS` | `[]` | VLAN IDs to suppress. Applied during discovery (dynamic mode) and during comparison (static mode). |
| `DOWN_CYCLES_THRESHOLD` | `4` | Consecutive 30-second cycles with zero packets before alerting. 4 cycles = 2 minutes. |
| `REFIRE_INTERVAL` | `10` | Cycles between detection updates after the initial fire. 10 cycles = 5 minutes. |
| `LOG_ENABLED` | `true` | Master switch for all logging. |
| `LOG_LEVEL` | `'INFO'` | Hierarchical: `DEBUG` shows everything, `INFO` shows info + warnings, `WARNING` shows only warnings. |
| `EMIT_ACTIVE_VLAN_METRIC` | `false` | Emit a `Network.metricAddSnap` with the count of active VLANs. Disabled by default because ExtraHop silently discards zero values. |

---

## Required trigger configuration

These settings must be configured in the ExtraHop UI when creating or editing the trigger. They are not set in the script.

| Setting | Value | Why |
|---------|-------|-----|
| Metric cycle | `30sec` | Ensures MRC fires on the 30-second cycle that TIMER_30SEC uses for comparison |
| Metric types | `extrahop.vlan.net` | Lets the platform filter before the trigger runs, so it doesn't execute on every metric record in the system |

---

## Expiry timers explained

| Constant | Value | Rationale |
|----------|-------|-----------|
| `EXP_ACTIVE` | 600s (10 min) | 2x the default discovery interval. If one discovery cycle fails, the active list survives until the next one. |
| `EXP_SEEN` | 60s | Resets every 30s. The 60s buffer handles the case where MRC records commit slightly after TIMER_30SEC fires. |
| `EXP_DOWN` | 86400s (24h) | Matches `identityTtl: 'day'`. Counter survives the full detection window without silent eviction. |
| `EXP_INIT` | 86400s (24h) | Cold start guard. If the trigger is disabled for more than 24 hours and re-enabled, it re-runs the warm-up. That's fine. |

---

## Log format

All log messages follow this format:

```
4.1.0 <hostname> [LEVEL] id=<context> | <message>
```

Examples:
```
4.1.0 eda01 [INFO] id=init | First cycle — warming up
4.1.0 eda01 [INFO] id=api | Active VLANs: 23
4.1.0 eda01 [WARNING] id=300 | VLAN 300 missing 2/4
4.1.0 eda01 [WARNING] id=300 | VLAN 300 down 4 cycles — fired
4.1.0 eda01 [WARNING] id=300 | VLAN 300 recovered after 14 cycles
```

Messages are truncated at 1900 characters to stay within the ExtraHop 2048-byte log limit. The trigger uses `log()` (not `debug()`), which writes regardless of the "Enable debug log" checkbox in the trigger config. To fully silence the trigger, set `LOG_ENABLED = false`.

---

## Walkthrough: normal operation

Assume 3 active VLANs (100, 200, 300) and default settings.

**Cycle 1 (cold start):**
- TIMER_30SEC fires
- `vlan_det_init` is null → set to 1, log warm-up, skip comparison
- Discovery fires: GET /vlans → POST /metrics → active list stored as `|100|200|300|`
- MRC fires for each VLAN, building seen set `|100|200|300|`
- Seen set reset to `||`

**Cycle 2 (normal):**
- TIMER_30SEC fires
- `vlan_det_init` exists → run `compareVlans()`
- All 3 VLANs in seen set → all healthy, no action
- Seen set reset

**Cycle 3 (VLAN 300 drops):**
- MRC fires for VLAN 100 and 200 only. Seen set: `|100|200|`
- TIMER_30SEC → `compareVlans()`
- VLAN 100: seen → healthy
- VLAN 200: seen → healthy
- VLAN 300: not seen → down counter = 1, log "VLAN 300 missing 1/4"

**Cycles 4-5:**
- Counter increments to 2, then 3. Still below threshold.

**Cycle 6 (threshold reached):**
- Counter = 4, `past = 4 - 4 = 0`
- `past === 0` → `fireDetection(300, 4)`
- Detection committed: type `VLAN_Down_Detector`, title "Data Feed VLAN Lost"
- Description shows "~2 min" duration

**Cycles 7-15 (suppressed):**
- Counter keeps incrementing (5, 6, ... 14)
- `past % 10 !== 0` → no detection, no noise

**Cycle 16 (refire):**
- Counter = 14, `past = 14 - 4 = 10`
- `10 % 10 === 0` → `fireDetection(300, 14)`
- Updated description shows "~7 min" duration
- Consolidates with existing detection (same identity key within TTL)

**Cycle N (VLAN 300 recovers):**
- MRC fires for VLAN 300 again (packets > 0)
- `compareVlans()` finds 300 in seen set
- Down counter exists → `Session.remove`, log "VLAN 300 recovered after N cycles"
- Next miss would start fresh at count = 1

---

## Known limitations

1. **Metric zero-value gap.** All ExtraHop metric types silently discard zero values. If `EMIT_ACTIVE_VLAN_METRIC` is enabled and all active VLANs disappear, the metric just stops appearing in dashboards rather than showing zero. The zero guard (`active.length > 0`) prevents a wasted API call but doesn't solve the underlying platform behavior.

2. **Top-level metric only.** The active VLAN count is a top-level snapshot metric (`Network.metricAddSnap`), not a detail metric. It shows total count, not per-VLAN status. Per-VLAN dashboard tracking would require `Network.metricAddDetailSnap` with VLAN ID as the key. About 10 lines of code to add if [Customer] wants it.

3. **Empty participants array.** The original trigger used `{ object: System.ipaddr, role: 'offender' }` as a participant, but this format is not documented in the API. The API docs only show `Flow.client.offender` style objects, which aren't available on TIMER_30SEC. Empty array is safe and documented. Worth testing in QA to see how the detection renders without a participant device.

4. **No days formatting.** Duration shows "~24 hours" instead of "~1 day" for outages longer than 24 hours. Cosmetic only.

---

## Version history

| Version | Changes |
|---------|---------|
| 1.0.0 | Initial deployment |
| 2.0.0 | Dynamic VLAN discovery via API |
| 2.1.0 | Performance enhancements |
| 3.0.0 | Full rewrite: bug fixes, hardened session handling, improved logging |
| 3.1.0 | Cold-start guard, hierarchical log levels, recovery logging, configurable refire interval |
| 3.2.0 | Throttled discovery, zero-packet filtering, graduated risk scoring, VLAN exclusion, active VLAN metric |
| 3.3.x | Functions at top, Session.increment for counters, advanced options documented, Markdown descriptions, 127-char width |
| 4.0.0 | Major simplification (736 → 446 lines). Removed apiCall abstraction, sessionGetJson, debug step counter. Merged buildDescription into fireDetection. Pre-computed CFG_RANK. |
| 4.1.0 | Pipe-delimited strings on MRC hot path. Zero JSON.parse/stringify in METRIC_RECORD_COMMIT. LICENSE_MODEL set to NPM for [Customer] performance detection webhook. Down counter expiry refresh fix (Session.replace instead of Session.increment). |

---
