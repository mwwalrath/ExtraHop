/*
###############################################################################################################################
#                                                                                                                             #
  Trigger:      VLAN Down Detector                                                                                            #
  Version:      4.1.0                                                                                                         #
  Author:       Matthew Walrath (ExtraHop Networks)                                                                                 #
  Events:       TIMER_30SEC, REMOTE_RESPONSE, METRIC_RECORD_COMMIT                                                            #
#                                                                                                                             #
  Detects when active VLANs stop transmitting packets. Discovers active VLANs                                                 #
  via the REST API (or a static list), observes traffic via METRIC_RECORD_COMMIT,                                             #
  and compares active vs seen every 30 seconds. Commits a custom detection when a                                             #
  VLAN is missing for a configurable number of consecutive cycles.                                                            #
#                                                                                                                             #
  Advanced Trigger Options (MUST be configured):                                                                              #
    Metric cycle: 30sec  |  Metric types: extrahop.vlan.net                                                                   #
#                                                                                                                             #
  Assignments: Global events only. Cannot be assigned to devices.                                                             #
#                                                                                                                             #
  Performance: Active and seen lists are stored as pipe-delimited strings                                                     #
  (e.g. |100|200|300|) to avoid JSON.parse/stringify on the MRC hot path.                                                     #
  Membership checks use indexOf. This follows the best practices guidance                                                     #
  against calling JSON methods on session table objects in high-volume events.                                                #
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
const STATIC_VLAN_IDS      = []
const VLAN_EXCLUDE_IDS     = []
const DOWN_CYCLES_THRESHOLD = 4
const REFIRE_INTERVAL      = 10
const LOG_ENABLED          = true
const LOG_LEVEL            = 'INFO'
const EMIT_ACTIVE_VLAN_METRIC = false

// ============================================================================================================================
//  CONSTANTS                                                                                                                //
// ============================================================================================================================

const VERSION  = '4.1.0'
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

// ============================================================================================================================
//  FUNCTIONS                                                                                                                //
// ============================================================================================================================

// Pipe-delimited format: '|100|200|300|'
// indexOf is O(n) on a string but avoids JSON.parse
// and object allocation on the MRC hot path.

function pipeHas(str, id) {
    return str.indexOf('|' + id + '|') !== -1
}

function pipeToArray(str) {
    if (!str || str === '||') return []
    // '|100|200|' -> ['100','200'] -> [100, 200]
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
    // POST /metrics to get 7-day bucket counts
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

    // Store as pipe-delimited for fast indexOf on MRC
    sessionSet(SK_ACTIVE, arrayToPipe(active), EXP_ACTIVE)

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
    let activeStr
    let active
    if (DYNAMIC_VLAN) {
        activeStr = Session.lookup(SK_ACTIVE)
        if (activeStr === null || activeStr === '||') {
            return
        }
        active = pipeToArray(activeStr)
    } else {
        active = STATIC_VLAN_IDS
        if (VLAN_EXCLUDE_IDS.length > 0) {
            const ex = new Set(VLAN_EXCLUDE_IDS)
            active = active.filter(function (v) {
                return !ex.has(v)
            })
        }
        if (active.length === 0) return
    }

    const seenStr = Session.lookup(SK_SEEN) || '||'

    for (let i = 0; i < active.length; i++) {
        const vlan = active[i]
        const key = SK_DOWN + vlan

        if (pipeHas(seenStr, vlan)) {
            const was = Session.lookup(key)
            if (was !== null) {
                Session.remove(key)
                logMsg(
                    'VLAN ' + vlan + ' recovered'
                        + ' after ' + was + ' cycles',
                    vlan, 'WARNING'
                )
            }
            continue
        }

        // Missing. lookup + replace refreshes expiry.
        const prev = Session.lookup(key)
        const count = (prev !== null
            && typeof prev === 'number')
            ? prev + 1 : 1
        sessionSet(key, count, EXP_DOWN)

        if (count < DOWN_CYCLES_THRESHOLD) {
            logMsg(
                'VLAN ' + vlan + ' missing '
                    + count + '/' + DOWN_CYCLES_THRESHOLD,
                vlan, 'WARNING'
            )
            continue
        }
        const past = count - DOWN_CYCLES_THRESHOLD
        if (past !== 0
            && past % REFIRE_INTERVAL !== 0) {
            continue
        }
        fireDetection(vlan, count)
        logMsg(
            'VLAN ' + vlan + ' down '
                + count + ' cycles — fired',
            vlan, 'WARNING'
        )
    }
}

function fireDetection(vlan, count) {
    let name = 'VLAN_Down_Detector'
    let title = 'Data Feed VLAN Lost'
    if (LICENSE_MODEL === 'NDR') {
        name += '_NDR'
        title += ' (NDR)'
    }
    const secs = count * 30
    let dur
    if (secs < 60) dur = secs + ' seconds'
    else if (secs < 3600)
        dur = '~' + Math.round(secs / 60) + ' min'
    else dur = '~' + (Math.round(secs / 36) / 100)
        + ' hours'
    const desc = '**VLAN ' + vlan + '** has stopped'
        + ' receiving or transmitting packets.\n\n'
        + '* **Duration:** ' + dur + '\n'
        + '* **Sensor:** ' + HOSTNAME + '\n'
        + '* **Down cycles:** ' + count
        + ' (threshold: ' + DOWN_CYCLES_THRESHOLD + ')'
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
            0, count - DOWN_CYCLES_THRESHOLD
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

// ============================================================================================================================
//  EVENT: TIMER_30SEC                                                                                                       //
// ============================================================================================================================

if (event === 'TIMER_30SEC') {

    if (!DYNAMIC_VLAN
        && STATIC_VLAN_IDS.length === 0
        && Session.lookup(SK_WARNED) === null) {
        logMsg(
            'DYNAMIC_VLAN is false but'
                + ' STATIC_VLAN_IDS is empty',
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

    // Reset seen set. Pipe-delimited empty = '||'
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
    else if (ctx === 'get_metrics') handleGetMetrics(body)
}

// ============================================================================================================================
//  EVENT: METRIC_RECORD_COMMIT                                                                                              //
//  Hot path: fires per VLAN per 30s cycle. No JSON.parse/stringify.                                                         //
//  Uses pipe-delimited strings + indexOf per best practices guidance.                                                       //
// ============================================================================================================================

if (event === 'METRIC_RECORD_COMMIT') {
    if (MetricRecord.id !== 'extrahop.vlan.net') return

    const pkts = MetricRecord.fields['pkts']
    if (pkts === undefined || pkts === 0) return

    const vlanId = MetricRecord.object['id']

    // Check active list (pipe-delimited, no JSON.parse)
    const activeStr = Session.lookup(SK_ACTIVE)
    if (activeStr === null || activeStr === '||') return
    if (!pipeHas(activeStr, vlanId)) return

    // Check/update seen set (pipe-delimited, no JSON)
    const seenStr = Session.lookup(SK_SEEN) || '||'
    if (pipeHas(seenStr, vlanId)) return

    // Append this VLAN to the seen string
    const updated = (seenStr === '||')
        ? '|' + vlanId + '|'
        : seenStr + vlanId + '|'
    sessionSet(SK_SEEN, updated, EXP_SEEN)
}
