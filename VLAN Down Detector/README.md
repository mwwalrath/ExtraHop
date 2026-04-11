# VLAN Down Detector v5.0.0

**Trigger for ExtraHop Reveal(x)**
Detects when active VLANs fall off the data feed. Three monitoring tiers (critical, standard, low_value) with independent thresholds and refire intervals. Fires recovery updates when VLANs return.

---

## What it does

The trigger monitors which VLANs are actively passing packets through the ExtraHop sensor. When a VLAN that has been consistently active suddenly goes silent, the trigger commits a custom detection to Reveal(x). When the VLAN recovers, a follow-up update is consolidated into the same detection with the total downtime.

It answers a simple question: "Is every VLAN that should be on the wire still on the wire?"

---

## Why it exists

ExtraHop doesn't have a built-in detection for data feed loss at the VLAN level. If a network TAP fails, a SPAN port drops, or a routing change silently removes a VLAN from the sensor's view, there's no native alert. This trigger fills that gap.

The trigger supports both NPM and NDR license models. In NPM mode it runs as a performance detection (no risk score). In NDR mode it adds graduated risk scoring. One-line config change to switch.

---

## Tiered monitoring

VLANs are assigned to one of three tiers, each with independent thresholds and refire intervals.

| Tier | Default Threshold | Default Refire | Use Case |
|------|-------------------|----------------|----------|
| **critical** | 10 cycles (5 min) | 60 cycles (30 min) | Core infrastructure VLANs that should never be down |
| **standard** | 120 cycles (1 hour) | 120 cycles (1 hour) | Normal production VLANs (default for all discovered VLANs) |
| **low_value** | 360 cycles (3 hours) | 360 cycles (3 hours) | VLANs with intermittent or low-frequency traffic |

Tier resolution: if a VLAN is in `CRITICAL_VLAN_IDS`, it's critical. If it's in `LOW_VALUE_VLAN_IDS`, it's low_value. Everything else (including all dynamically discovered VLANs) is standard.

Critical VLANs bypass the 7-day discovery check entirely and are always monitored, even before the first API discovery completes. `VLAN_EXCLUDE_IDS` overrides any tier.

---

## Three-phase architecture

The trigger runs on three ExtraHop events that work together on a coordinated 30-second cycle.

### Phase 1: VLAN Discovery (TIMER_30SEC + REMOTE_RESPONSE)

Every 5 minutes, the trigger queries the ExtraHop REST API to build a list of active VLANs.

**Step 1:** `GET /api/v1/networks/0/vlans` retrieves all known VLANs from the sensor.

**Step 2:** The response is filtered through `VLAN_EXCLUDE_IDS` to remove suppressed VLANs.

**Step 3:** `POST /api/v1/metrics` requests 7 days of hourly packet counts for the remaining VLANs. Uses `cycle: '1hr'` explicitly so the bucket count is predictable.

**Step 4:** A VLAN must have traffic in every hourly bucket across the full 7-day window to qualify as "active." The expected bucket count is `(7 * 24) + 1 = 169`.

**Step 5:** The active list is stored in the session table as a pipe-delimited string (e.g. `|100|200|300|`) with a 10-minute expiry.

### Phase 2: Traffic Observation (METRIC_RECORD_COMMIT)

On every 30-second metric cycle, the `METRIC_RECORD_COMMIT` event fires once per VLAN. The trigger checks: is this `extrahop.vlan.net`? Does it have non-zero packets? Is this VLAN in the active list or the critical list? Is it already in the "seen" set? If all pass, the VLAN ID is appended to the seen string.

The "seen" set is reset to empty (`||`) at the end of each TIMER_30SEC cycle.

### Phase 3: Comparison and Detection (TIMER_30SEC)

At the start of each 30-second window, the trigger compares active VLANs against the "seen" set. For each VLAN, it resolves the tier and applies the tier-specific threshold and refire interval.

- **If seen and was down past threshold:** Fire a recovery detection with total downtime, then clear the counter.
- **If seen and was counting but below threshold:** Clear the counter, log "back before threshold."
- **If not seen:** Increment the down counter. If the counter reaches the tier's threshold, commit a detection.

---

## Recovery detection

When a VLAN that was down past its threshold comes back, the trigger fires one more `commitDetection` call with the same `identityKey`. This consolidates into the existing ongoing detection. The description is updated to show the VLAN has recovered, the total downtime, and a note explaining when the detection will expire.

The title stays "Data Feed VLAN Lost" because detections are reserved for negative events. The description makes it clear the VLAN is back.

If a VLAN was counting up but hadn't reached its threshold yet, no recovery detection is fired. The counter is just cleared.

---

## Duration formatting

Durations are displayed as human-readable strings with correct singular/plural: "5 minutes", "1 hour 30 minutes", "2 hours", "45 seconds". No approximate prefix since `count * 30` is exact. Seconds are dropped when hours are shown.

---

## Cold start behavior

When the trigger is first enabled or restarted, a warm-up guard skips the first comparison cycle. This prevents every active VLAN from appearing "down" because no MRC traffic has been observed yet. Zero false detections on startup.

---

## Detection format

| Field | Value |
|-------|-------|
| Type | `VLAN_Down_Detector` |
| Title | `Data Feed VLAN Lost` |
| Description | Markdown: VLAN ID, tier, duration, sensor hostname, cycle count, TTL note |
| Identity Key | `vlan_down_{VLAN_ID}` (per-VLAN deduplication) |
| Identity TTL | `day` (consolidates within 24 hours) |
| Participants | Empty array |
| Risk Score | Omitted in NPM mode; graduated 50-99 in NDR mode |

The detection description includes a note explaining it will auto-resolve approximately 24 hours after the last update. On recovery, the description is updated to show the VLAN has recovered and the total downtime.

---

## Session table keys

| Key | Value | Expiry | Purpose |
|-----|-------|--------|---------|
| `vlan_det_active` | Pipe-delimited active VLAN IDs | 600s | Survives one missed discovery cycle |
| `vlan_det_seen` | Pipe-delimited seen VLAN IDs | 60s | Resets every 30s; 60s buffer for slow MRC |
| `vlan_det_down_{ID}` | Integer counter | 86400s | Matches identityTtl; never silently expires |
| `vlan_det_init` | 1 | 86400s | Cold start guard |
| `vlan_det_disc` | Integer (0 to DISC_CYCLES-1) | 600s | Discovery throttle |
| `vlan_det_swarn` | 1 | 86400s | One-shot empty config warning |

### Why Session.replace instead of Session.increment

`Session.increment` doesn't refresh the expiry timer. During a long outage, the counter would silently expire and reset to zero, causing a duplicate detection. `Session.replace` refreshes expiry on every call. Since `TIMER_30SEC` is single-threaded, atomicity is not a concern.

---

## Performance design

The MRC handler uses five early returns before the session write:

1. `MetricRecord.id` check (safety net behind advanced trigger options)
2. Zero-packet filter
3. Active list null/empty check
4. Active list membership OR critical list membership
5. Already-seen check

All active/seen lists use pipe-delimited strings with `indexOf()`. Zero `JSON.parse`/`JSON.stringify` on the MRC hot path. Tier lookup sets (`TIER_CRIT`, `TIER_LOW`) are pre-computed as `Set` objects for O(1) membership checks.

JSON is only used in the `REMOTE_RESPONSE` handler (at most once per 5 minutes).

---

## Configuration reference

All parameters live in the `USER CONFIGURATION` block at the top of the script.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `LICENSE_MODEL` | `'NPM'` | `'NPM'` for performance detection. `'NDR'` adds risk scoring. |
| `DYNAMIC_VLAN` | `true` | Auto-discover active VLANs via REST API. |
| `API_ODS_TARGET` | `'EDA'` | HTTP Open Data Stream target name. |
| `ACTIVE_DAYS_REQUIRED` | `7` | Days of continuous hourly traffic to qualify as active. |
| `DISCOVERY_INTERVAL` | `300` | Seconds between API discovery runs. |
| `CRITICAL_VLAN_IDS` | `[]` | VLANs that bypass discovery and are always monitored. |
| `STANDARD_VLAN_IDS` | `[]` | Optional manual additions to standard tier. |
| `LOW_VALUE_VLAN_IDS` | `[]` | VLANs with intermittent traffic patterns. |
| `VLAN_EXCLUDE_IDS` | `[]` | VLANs to suppress (overrides any tier). |
| `CRITICAL_THRESHOLD` | `10` | Cycles before alerting for critical VLANs (5 min). |
| `STANDARD_THRESHOLD` | `120` | Cycles before alerting for standard VLANs (1 hour). |
| `LOW_VALUE_THRESHOLD` | `360` | Cycles before alerting for low-value VLANs (3 hours). |
| `CRITICAL_REFIRE` | `60` | Cycles between updates for critical (30 min). |
| `STANDARD_REFIRE` | `120` | Cycles between updates for standard (1 hour). |
| `LOW_VALUE_REFIRE` | `360` | Cycles between updates for low-value (3 hours). |
| `STATIC_VLAN_IDS` | `[]` | Manual VLAN list when `DYNAMIC_VLAN` is `false`. |
| `LOG_ENABLED` | `true` | Master switch for all logging. |
| `LOG_LEVEL` | `'INFO'` | `DEBUG` / `INFO` / `WARNING` hierarchical. |
| `EMIT_ACTIVE_VLAN_METRIC` | `false` | Emit snapshot metric with active VLAN count. |

---

## Required trigger configuration

These must be set in the ExtraHop UI, not in the script.

| Setting | Value | Why |
|---------|-------|-----|
| Metric cycle | `30sec` | Matches TIMER_30SEC comparison cycle |
| Metric types | `extrahop.vlan.net` | Platform-level filtering before trigger executes |

---

## Log format

```
5.0.0 <hostname> [LEVEL] id=<context> | <message>
```

Examples:
```
5.0.0 eda01 [INFO] id=init | First cycle — warming up
5.0.0 eda01 [INFO] id=api | Active VLANs: 23
5.0.0 eda01 [WARNING] id=300 | VLAN 300 (standard) missing 15/120
5.0.0 eda01 [WARNING] id=300 | VLAN 300 (standard) down 120 cycles — fired
5.0.0 eda01 [WARNING] id=300 | VLAN 300 (standard) recovered after 180 cycles
5.0.0 eda01 [INFO] id=200 | VLAN 200 (critical) back before threshold
```

Messages truncated at 1900 characters (ExtraHop 2048-byte log limit).

---

## Known limitations

1. **Metric zero-value gap.** ExtraHop silently discards zero metric values. If `EMIT_ACTIVE_VLAN_METRIC` is enabled and all active VLANs disappear, the metric stops appearing rather than showing zero.

2. **Top-level metric only.** The active VLAN count is a snapshot, not per-VLAN. Per-VLAN tracking would require `metricAddDetailSnap` (~10 lines to add).

3. **Empty participants.** The API only supports Flow-based participants, which aren't available on TIMER_30SEC. The detection renders correctly without them.

4. **Detection auto-resolve.** There is no API to programmatically close a detection. Detections stay "ongoing" until `identityTtl` expires without a new consolidation. The recovery description makes it clear the VLAN is back, and both outage and recovery descriptions include a TTL note.

---

## Version history

| Version | Changes |
|---------|---------|
| 1.0.0 | Initial deployment |
| 2.0.0 | Dynamic VLAN discovery via API |
| 2.1.0 | Performance enhancements |
| 3.0.0 | Full rewrite: bug fixes, hardened session handling, improved logging |
| 3.1.0 | Cold-start guard, hierarchical log levels, recovery logging, configurable refire |
| 3.2.0 | Throttled discovery, zero-packet filtering, graduated risk scoring, VLAN exclusion |
| 3.3.x | Functions at top, Session.increment for counters, Markdown descriptions, 127-char width |
| 4.0.0 | Major simplification (736 to 446 lines). Removed apiCall abstraction. Pre-computed CFG_RANK. |
| 4.1.0 | Pipe-delimited MRC hot path. Zero JSON on METRIC_RECORD_COMMIT. Down counter expiry refresh. |
| 5.0.0 | Tiered monitoring (critical/standard/low_value). Per-tier thresholds and refire intervals. Recovery detection with downtime. Human-readable duration formatting. TTL notes in descriptions. Critical VLANs bypass discovery. |

---

## Authors

- **Matthew Walrath** — ExtraHop Networks
