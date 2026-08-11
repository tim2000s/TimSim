// A line protocol over the shipped oref0 SMB decision code.
//
// The point of this, as with the Boost bridge beside it, is what it does not contain. There
// is no reimplementation: `determine_basal` and `tempBasalFunctions` are required straight
// out of the gathered AndroidAPS assets and called directly, so nothing can drift between
// this and the algorithm those assets define.
//
// The protocol is JSON per line rather than the positional form the Boost bridge uses,
// because oref's input is nested and mostly a forward array of insulin ticks. The profile is
// constant for a subject and is sent once, so the per-cycle line carries only what moves.
//
// `console.log` and `console.error` are silenced. oref narrates every decision through its
// own `reason` helper, which also builds the `reason` string returned in the result, so the
// string survives and only the printing goes. Silencing `console.log` is not an optimisation
// but a correctness fix: oref writes its autosens and basal lines to stdout, and they arrived
// interleaved with the replies on this channel.
'use strict'

const path = require('path')
const VENDOR = path.join(__dirname, 'vendor', 'oref')
const determine_basal = require(path.join(VENDOR, 'determine-basal'))
const tempBasalFunctions = require(path.join(VENDOR, 'basal-set-temp'))

console.error = () => {}
console.log = () => {}

let profile = null
const out = []

// oref reads `iob_data[0]` for the present and walks the rest for its predictions, so the
// array carries the whole forward curve. `lastTemp` lives on the first tick because that is
// where oref looks for it when checking the pump agrees with what it last asked for.
function cycle(m) {
    const r = determine_basal(
        m.glucose_status, m.currenttemp, m.iob, profile,
        m.autosens || { ratio: 1.0 }, m.meal_data, tempBasalFunctions,
        m.microBolusAllowed !== false, m.reservoir,
        new Date(m.currentTime), m.flatBGsDetected === true)
    return {
        rate: r.rate === undefined ? null : r.rate,
        duration: r.duration === undefined ? null : r.duration,
        units: r.units || 0,
        eventualBG: r.eventualBG === undefined ? null : r.eventualBG,
        insulinReq: r.insulinReq === undefined ? null : r.insulinReq,
        COB: r.COB === undefined ? null : r.COB,
        IOB: r.IOB === undefined ? null : r.IOB,
        sensitivityRatio: r.sensitivityRatio === undefined ? null : r.sensitivityRatio,
        carbsReq: r.carbsReq === undefined ? null : r.carbsReq,
        reason: r.reason || '',
    }
}

require('readline')
    .createInterface({ input: process.stdin, terminal: false })
    .on('line', (line) => {
        const t = line.trim()
        if (!t) return
        if (t === 'QUIT') { process.stdout.write(out.join('')); process.exit(0) }
        const m = JSON.parse(t)
        // The profile arrives in two parts. Everything fixed for a subject is sent once at
        // setup, and the hourly figures oref reads afresh each cycle, insulin sensitivity,
        // carbohydrate ratio and scheduled basal, ride along with the cycle itself.
        if (m.profile) profile = Object.assign(profile || {}, m.profile)
        if (!m.glucose_status) { process.stdout.write('{"ok":true}\n'); return }
        let res
        try { res = cycle(m) } catch (e) { res = { error: String(e && e.stack || e) } }
        process.stdout.write(JSON.stringify(res) + '\n')
    })
