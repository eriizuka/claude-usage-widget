// Saves the plan limits for the desktop widget: at session start and after every response, writes
// <home>/.claude-usage-widget/limits.json = {fetchedAt, five_hour, seven_day} ({utilization %, resets_at s}).
// It only reads HOME/USERPROFILE and that file and writes to that folder: no network, no model calls, never reads
// the conversation and never blocks anything (every hook goes on with next). Failures go to errors-plugin.log.
import type { EngineInterface, Register, SessionRateLimit } from 'claude-code'

type Win = { utilization: number; resets_at?: number }
type Saved = { fetchedAt?: number; five_hour?: Win; seven_day?: Win }

async function dataDir($: EngineInterface): Promise<string> {
  const home = (await $.env.get('USERPROFILE'))?.trim() || (await $.env.get('HOME'))?.trim()
  if (!home) throw new Error('neither USERPROFILE nor HOME is set')
  return `${home.split('\\').join('/')}/.claude-usage-widget`
}

function win(rl: SessionRateLimit | undefined): Win | undefined {
  const t = rl?.resetsAt ? Math.round(Date.parse(rl.resetsAt) / 1000) : NaN
  return rl && { utilization: Math.min(100, Math.max(0, rl.percentUsed)), ...(Number.isNaN(t) ? {} : { resets_at: t }) }
}

// Several sessions write this file, and one that starts reports the last reading it has, which can be older than
// what another session just saved. Within one window usage only goes up, so a lower number for the same window is
// an old reading: keep the saved one. A different resets_at is a new window and always wins.
function merge(saved: Win | undefined, now: Win | undefined): { w?: Win; newer: boolean } {
  if (!now) return { w: saved, newer: false }
  if (saved && saved.resets_at === now.resets_at && saved.utilization > now.utilization) return { w: saved, newer: false }
  return { w: now, newer: !saved || saved.resets_at !== now.resets_at || saved.utilization !== now.utilization }
}

async function save($: EngineInterface, where: string, rateLimits: readonly SessionRateLimit[], fresh: boolean): Promise<void> {
  try {
    const file = `${await dataDir($)}/limits.json`
    let old: Saved = {}
    try { old = JSON.parse(await $.fs.read(file)) } catch { /* first run */ }
    const [a, b] = ['five_hour', 'seven_day'].map((k) => win(rateLimits.find((r) => r.kind === k)))
    const h = merge(old.five_hour, a), d = merge(old.seven_day, b)
    // session.measure is a live reading; session.start only counts when it brings something newer
    if (!(h.w || d.w) || !(fresh || h.newer || d.newer)) return
    await $.fs.write(file, `${JSON.stringify({ fetchedAt: await $.clock.now(), five_hour: h.w, seven_day: d.w })}\n`)
  } catch (err) {
    try { await $.fs.write(`${await dataDir($)}/errors-plugin.log`, `${where}: ${String(err)}\n`) } catch { /* nowhere to log */ }
  }
}

export const register: Register = (on) => {
  on('session.start', async ($, e, next) => {
    try { await save($, 'session.start', (await $.session.usage()).rateLimits, false) } catch { /* no limits now */ }
    return next(e)
  })
  on('session.measure', async ($, e, next) => (await save($, 'session.measure', e.rateLimits, true), next(e)))
}
