/*
###############################################################################################################################
#                                                                                                                             #
  Trigger:      VLAN Down Detector                                                                                            #
  Version:      5.0.0                                                                                                         #
  Contributor:  Matthew Walrath (ExtraHop Networks)                                                                           #
  Events:       TIMER_30SEC, REMOTE_RESPONSE, METRIC_RECORD_COMMIT                                                            #
#                                                                                                                             #
  Detects when active VLANs stop transmitting packets. Three monitoring tiers                                                 #
  (critical, standard, low_value) with independent thresholds and refire rates.                                               #
  Discovers active VLANs via REST API, observes traffic via MRC, compares every                                               #
  30 seconds. Commits a detection when a VLAN is missing for its tier threshold.                                              #
  Fires a recovery update when the VLAN returns.                                                                              #
#                                                                                                                             #
  Advanced Trigger Options (MUST be configured):                                                                              #
    Metric cycle: 30sec  |  Metric types: extrahop.vlan.net                                                                   #
#                                                                                                                             #
  Assignments: Global events only. Cannot be assigned to devices.                                                             #
#                                                                                                                             #
  Performance: Active and seen lists stored as pipe-delimited strings to avoid                                                #
  JSON.parse/stringify on the MRC hot path. Membership checks use indexOf.                                                    #
#                                                                                                                             #
###############################################################################################################################
*/

// ============================================================================================================================
//  USER CONFIGURATION                                                                                                       //
// ============================================================================================================================

/** @type {'NPM' | 'NDR'} */
const LICENSE_MODEL        = 'NPM'
const DYNAMIC_VLAN         = true
const API_ODS_TARGET       = 'EDA'
const ACTIVE_DAYS_REQUIRED = 7
const DISCOVERY_INTERVAL   = 300

// Tier arrays. Critical VLANs bypass discovery and are always monitored.
// Discovered VLANs default to standard unless placed in another tier.
// VLAN_EXCLUDE_IDS suppresses any tier.
const CRITICAL_VLAN_IDS    = []
const STANDARD_VLAN_IDS    = []
const LOW_VALUE_VLAN_IDS   = []
const VLAN_EXCLUDE_IDS     = []

// Per-tier thresholds (consecutive 30s cycles before detection)
const CRITICAL_THRESHOLD   = 10     // 5 minutes
const STANDARD_THRESHOLD   = 120    // 1 hour
const LOW_VALUE_THRESHOLD  = 360    // 3 hours

// Per-tier refire intervals (cycles between detection updates)
const CRITICAL_REFIRE      = 60     // every 30 minutes
const STANDARD_REFIRE      = 120    // every 1 hour
const LOW_VALUE_REFIRE     = 360    // every 3 hours

// Legacy fallback (used if DYNAMIC_VLAN is false and no tier arrays
// are populated). Normally not needed with tiered config.
const STATIC_VLAN_IDS      = []

const LOG_ENABLED          = true
const LOG_LEVEL            = 'INFO'
const EMIT_ACTIVE_VLAN_METRIC = false

// ============================================================================================================================
//  CONSTANTS                                                                                                                //
// ============================================================================================================================

const VERSION  = '5.0.0'
const HOSTNAME = System.hostname || 'unknown'

const SK_ACTIVE  = 'vlan_det_active'
const SK_SEEN    = 'vlan_det_seen'
const SK_DOWN    = 'vlan_det_down_'
const SK_INIT    = 'vlan_det_init'
const SK_DISC    = 'vlan_det_disc'
const SK_WARNED  = 'vlan_det_swarn'

const EXP_ACTIVE = 600
const EXP_SEEN   = 60
const EXP_DOWN   = 86400
const EXP_INIT   = 86400

const LEVEL_RANK = { DEBUG: 0, INFO: 1, WARNING: 2 }
const CFG_RANK   = LEVEL_RANK[LOG_LEVEL] || 1

const DISC_CYCLES = Math.max(
    1, Math.round(DISCOVERY_INTERVAL / 30)
)

const RISK_MIN   = 50
const RISK_MAX   = 99
const RISK_RAMP  = 120
const LOG_MAX    = 1900

// Pre-computed tier lookup sets
const TIER_CRIT = new Set(CRITICAL_VLAN_IDS)
const TIER_LOW  = new Set(LOW_VALUE_VLAN_IDS)

// ============================================================================================================================
//  FUNCTIONS                                                                                                                //
// ============================================================================================================================

function pipeHas(str, id) {
    return str.indexOf('|' + id + '|') !== -1
}

function pipeToArray(str) {
    if (!str || str === '||') return []
    const parts = str.substring(1, str.length - 1)
        .split('|')
    const arr = []
    for (let i = 0; i < parts.length; i++) {
        const n = parseInt(parts[i], 10)
        if (!isNaN(n)) arr.push(n)
    }
    return arr
}

function arrayToPipe(arr) {
    if (arr.length === 0) return '||'
    return '|' + arr.join('|') + '|'
}

function logMsg(text, id, level) {
    if (!LOG_ENABLED) return
    const rank = LEVEL_RANK[level] || 1
    if (rank < CFG_RANK) return
    let msg = VERSION + ' ' + HOSTNAME
        + ' [' + level + '] id=' + id + ' | ' + text
    if (msg.length > LOG_MAX) {
        msg = msg.substring(0, LOG_MAX)
            + '...(truncated)'
    }
    log(msg)
}

function sessionSet(key, value, expire) {
    Session.replace(key, value, {
        expire: expire,
        priority: Session.PRIORITY_HIGH
    })
}

function getTier(vlan) {
    if (TIER_CRIT.has(vlan)) return 'critical'
    if (TIER_LOW.has(vlan)) return 'low_value'
    return 'standard'
}

function getThreshold(tier) {
    if (tier === 'critical') return CRITICAL_THRESHOLD
    if (tier === 'low_value') return LOW_VALUE_THRESHOLD
    return STANDARD_THRESHOLD
}

function getRefire(tier) {
    if (tier === 'critical') return CRITICAL_REFIRE
    if (tier === 'low_value') return LOW_VALUE_REFIRE
    return STANDARD_REFIRE
}

function formatDuration(secs) {
    if (secs < 60) return secs + ' seconds'
    const h = Math.floor(secs / 3600)
    const m = Math.floor((secs % 3600) / 60)
    const s = secs % 60
    var hl = h === 1 ? 'hour' : 'hours'
    var ml = m === 1 ? 'minute' : 'minutes'
    var sl = s === 1 ? 'second' : 'seconds'
    if (h === 0) {
        if (s === 0) return m + ' ' + ml
        return m + ' ' + ml + ' ' + s + ' ' + sl
    }
    if (m === 0) return h + ' ' + hl
    return h + ' ' + hl + ' ' + m + ' ' + ml
}

function handleGetVlans(body) {
    if (!Array.isArray(body) || body.length === 0) {
        logMsg('No VLANs from API', 'api', 'WARNING')
        return
    }
    const exclude = new Set(VLAN_EXCLUDE_IDS)
    const ids = []
    for (let i = 0; i < body.length; i++) {
        const item = body[i]
        if (item && item.id !== undefined
            && !exclude.has(item.id)) {
            ids.push(item.id)
        }
    }
    if (ids.length === 0) {
        logMsg(
            'No VLAN IDs after exclude filter',
            'api', 'WARNING'
        )
        return
    }
    try {
        Remote.HTTP(API_ODS_TARGET).post({
            path: '/api/v1/metrics',
            headers: {
                Accept: 'application/json',
                'Content-Type': 'application/json'
            },
            payload: JSON.stringify({
                cycle: '1hr',
                from: '-' + ACTIVE_DAYS_REQUIRED + 'd',
                metric_category: 'net',
                metric_specs: [{ name: 'pkts' }],
                object_ids: ids,
                object_type: 'vlan',
                until: 0
            }),
            context: 'get_metrics',
            enableResponseEvent: true
        })
    } catch (e) {
        logMsg(
            'POST /metrics failed: ' + e.message,
            'api', 'WARNING'
        )
    }
}

function handleGetMetrics(body) {
    const stats = body.stats
    if (!Array.isArray(stats)) {
        logMsg(
            'Metrics response missing stats',
            'api', 'WARNING'
        )
        return
    }
    const needed = (ACTIVE_DAYS_REQUIRED * 24) + 1
    const counts = new Map()
    for (let i = 0; i < stats.length; i++) {
        if (!stats[i] || stats[i].oid === undefined) {
            continue
        }
        const v = stats[i].oid
        counts.set(v, (counts.get(v) || 0) + 1)
    }
    const active = []
    counts.forEach(function (c, v) {
        if (c >= needed) active.push(v)
    })

    sessionSet(
        SK_ACTIVE, arrayToPipe(active), EXP_ACTIVE
    )

    logMsg(
        'Active VLANs: ' + active.length,
        'api', 'INFO'
    )
    if (EMIT_ACTIVE_VLAN_METRIC && active.length > 0) {
        try {
            Network.metricAddSnap(
                'vlan_det_active_count',
                active.length
            )
        } catch (e) {
            logMsg(
                'Metric emit failed: ' + e.message,
                'api', 'WARNING'
            )
        }
    }
}

function compareVlans() {
    // Build the monitored VLAN list
    let active
    if (DYNAMIC_VLAN) {
        const str = Session.lookup(SK_ACTIVE)
        active = (str && str !== '||')
            ? pipeToArray(str) : []
    } else {
        active = STATIC_VLAN_IDS.slice()
    }

    // Merge critical VLANs unconditionally
    const seen = new Set(active)
    for (let i = 0; i < CRITICAL_VLAN_IDS.length; i++) {
        if (!seen.has(CRITICAL_VLAN_IDS[i])) {
            active.push(CRITICAL_VLAN_IDS[i])
        }
    }

    // Apply exclude filter
    if (VLAN_EXCLUDE_IDS.length > 0) {
        const ex = new Set(VLAN_EXCLUDE_IDS)
        active = active.filter(function (v) {
            return !ex.has(v)
        })
    }

    if (active.length === 0) {
        logMsg(
            'No active VLANs to monitor',
            'compare', 'DEBUG'
        )
        return
    }

    const seenStr = Session.lookup(SK_SEEN) || '||'

    for (let i = 0; i < active.length; i++) {
        const vlan = active[i]
        const key = SK_DOWN + vlan
        const tier = getTier(vlan)
        const threshold = getThreshold(tier)
        const refire = getRefire(tier)

        if (pipeHas(seenStr, vlan)) {
            // VLAN is healthy. Check for recovery.
            const was = Session.lookup(key)
            if (was !== null
                && typeof was === 'number'
                && was >= threshold) {
                fireRecovery(
                    vlan, was, tier, threshold
                )
                logMsg(
                    'VLAN ' + vlan + ' (' + tier
                        + ') recovered after '
                        + was + ' cycles',
                    vlan, 'WARNING'
                )
            } else if (was !== null) {
                logMsg(
                    'VLAN ' + vlan + ' (' + tier
                        + ') back before threshold',
                    vlan, 'INFO'
                )
            }
            if (was !== null) Session.remove(key)
            continue
        }

        // VLAN missing. Increment counter.
        const prev = Session.lookup(key)
        const count = (prev !== null
            && typeof prev === 'number')
            ? prev + 1 : 1
        sessionSet(key, count, EXP_DOWN)

        if (count < threshold) {
            logMsg(
                'VLAN ' + vlan + ' (' + tier
                    + ') missing '
                    + count + '/' + threshold,
                vlan, 'WARNING'
            )
            continue
        }
        const past = count - threshold
        if (past !== 0 && past % refire !== 0) {
            continue
        }
        fireDetection(
            vlan, count, tier, threshold
        )
        logMsg(
            'VLAN ' + vlan + ' (' + tier
                + ') down ' + count
                + ' cycles — fired',
            vlan, 'WARNING'
        )
    }
}

function fireDetection(vlan, count, tier, threshold) {
    let name = 'VLAN_Down_Detector'
    let title = 'Data Feed VLAN Lost'
    if (LICENSE_MODEL === 'NDR') {
        name += '_NDR'
        title += ' (NDR)'
    }
    const dur = formatDuration(count * 30)
    const desc = '**VLAN ' + vlan
        + '** has stopped receiving or'
        + ' transmitting packets.\n\n'
        + '* **Tier:** ' + tier + '\n'
        + '* **Duration:** ' + dur + '\n'
        + '* **Sensor:** ' + HOSTNAME + '\n'
        + '* **Down cycles:** ' + count
        + ' (threshold: ' + threshold + ')\n'
        + '* **Note:** This detection auto-resolves'
        + ' ~24 hours after the last update'
        + ' (identityTtl: day).'
    /** @type {'day'} */
    const ttl = 'day'
    const opts = {
        title: title,
        description: desc,
        participants: [],
        identityKey: 'vlan_down_' + vlan,
        identityTtl: ttl
    }
    if (LICENSE_MODEL === 'NDR') {
        const past = Math.max(
            0, count - threshold
        )
        const ramp = Math.min(1, past / RISK_RAMP)
        opts.riskScore = Math.round(
            RISK_MIN + (RISK_MAX - RISK_MIN) * ramp
        )
    }
    try { commitDetection(name, opts) }
    catch (e) {
        logMsg(
            'Detection failed for VLAN ' + vlan
                + ': ' + e.message,
            vlan, 'WARNING'
        )
    }
}

function fireRecovery(vlan, count, tier, threshold) {
    let name = 'VLAN_Down_Detector'
    let title = 'Data Feed VLAN Lost'
    if (LICENSE_MODEL === 'NDR') {
        name += '_NDR'
        title += ' (NDR)'
    }
    const dur = formatDuration(count * 30)
    const desc = '**VLAN ' + vlan
        + '** has recovered.\n\n'
        + '* **Tier:** ' + tier + '\n'
        + '* **Downtime:** ' + dur + '\n'
        + '* **Sensor:** ' + HOSTNAME + '\n'
        + '* **Down cycles:** ' + count
        + ' (threshold: ' + threshold + ')\n'
        + '* **Note:** This detection will expire'
        + ' ~24 hours after this recovery update'
        + ' (identityTtl: day). No further updates'
        + ' will be sent unless the VLAN goes'
        + ' down again.'
    /** @type {'day'} */
    const ttl = 'day'
    const opts = {
        title: title,
        description: desc,
        participants: [],
        identityKey: 'vlan_down_' + vlan,
        identityTtl: ttl
    }
    try { commitDetection(name, opts) }
    catch (e) {
        logMsg(
            'Recovery detection failed for VLAN '
                + vlan + ': ' + e.message,
            vlan, 'WARNING'
        )
    }
}

// ============================================================================================================================
//  EVENT: TIMER_30SEC                                                                                                       //
// ============================================================================================================================

if (event === 'TIMER_30SEC') {

    if (!DYNAMIC_VLAN
        && STATIC_VLAN_IDS.length === 0
        && CRITICAL_VLAN_IDS.length === 0
        && Session.lookup(SK_WARNED) === null) {
        logMsg(
            'No VLANs configured to monitor',
            'init', 'WARNING'
        )
        sessionSet(SK_WARNED, 1, EXP_INIT)
    }

    if (DYNAMIC_VLAN) {
        const raw = Session.lookup(SK_DISC)
        let counter = (raw !== null
            && typeof raw === 'number')
            ? (raw + 1) % DISC_CYCLES : 0
        sessionSet(SK_DISC, counter, EXP_ACTIVE)
        if (counter === 0) {
            try {
                Remote.HTTP(API_ODS_TARGET).get({
                    path: '/api/v1/networks/0/vlans',
                    headers: {
                        Accept: 'application/json'
                    },
                    context: 'get_vlans',
                    enableResponseEvent: true
                })
            } catch (e) {
                logMsg(
                    'GET /vlans failed: '
                        + e.message,
                    'api', 'WARNING'
                )
            }
        }
    }

    if (Session.lookup(SK_INIT) === null) {
        sessionSet(SK_INIT, 1, EXP_INIT)
        logMsg(
            'First cycle — warming up',
            'init', 'INFO'
        )
    } else {
        compareVlans()
    }

    sessionSet(SK_SEEN, '||', EXP_SEEN)
}

// ============================================================================================================================
//  EVENT: REMOTE_RESPONSE                                                                                                   //
// ============================================================================================================================

if (event === 'REMOTE_RESPONSE') {
    const rsp = Remote.response
    const ctx = rsp.context
    if (rsp.statusCode < 200
        || rsp.statusCode >= 300) {
        logMsg(
            ctx + ' returned ' + rsp.statusCode,
            'api', 'WARNING'
        )
        return
    }
    let body = null
    try {
        body = rsp.body
            ? JSON.parse(rsp.body.decode('utf-8'))
            : null
    } catch (e) {
        logMsg(
            'Parse failed for ' + ctx,
            'api', 'WARNING'
        )
        return
    }
    if (body === null) {
        logMsg(
            'Empty body from ' + ctx,
            'api', 'WARNING'
        )
        return
    }
    if (ctx === 'get_vlans') handleGetVlans(body)
    else if (ctx === 'get_metrics') {
        handleGetMetrics(body)
    }
}

// ============================================================================================================================
//  EVENT: METRIC_RECORD_COMMIT                                                                                              //
//  Hot path: fires per VLAN per 30s cycle. No JSON.parse/stringify.                                                         //
//  Uses pipe-delimited strings + indexOf per best practices.                                                                //
// ============================================================================================================================

if (event === 'METRIC_RECORD_COMMIT') {
    if (MetricRecord.id !== 'extrahop.vlan.net') {
        return
    }

    const pkts = MetricRecord.fields['pkts']
    if (pkts === undefined || pkts === 0) return

    const vlanId = MetricRecord.object['id']

    // Check active list OR critical list
    const activeStr = Session.lookup(SK_ACTIVE)
    const inActive = activeStr !== null
        && activeStr !== '||'
        && pipeHas(activeStr, vlanId)
    const inCritical = TIER_CRIT.has(vlanId)

    if (!inActive && !inCritical) return

    const seenStr = Session.lookup(SK_SEEN) || '||'
    if (pipeHas(seenStr, vlanId)) return

    const updated = (seenStr === '||')
        ? '|' + vlanId + '|'
        : seenStr + vlanId + '|'
    sessionSet(SK_SEEN, updated, EXP_SEEN)
}
