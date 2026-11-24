// Saves the plan limits for the desktop widget: at session start and after every response, writes
// <home>/.claude-usage-widget/limits.json = {fetchedAt, five_hour, seven_day} ({utilization %, resets_at s}).
// It only reads HOME/USERPROFILE and writes to that folder: no network, no model calls, never reads the
// conversation and never blocks anything (every hook goes on with next). Failures go to errors-plugin.log.
import type { EngineInterface, Register, SessionRateLimit } from 'claude-code'

async function dataDir($: EngineInterface): Promise<string> {
  const home = (await $.env.get('USERPROFILE'))?.trim() || (await $.env.get('HOME'))?.trim()
  if (!home) throw new Error('neither USERPROFILE nor HOME is set')
  return `${home.split('\\').join('/')}/.claude-usage-widget`
}

function win(rl: SessionRateLimit | undefined): { utilization: number; resets_at?: number } | undefined {
  const t = rl?.resetsAt ? Math.round(Date.parse(rl.resetsAt) / 1000) : NaN
  return rl && { utilization: Math.min(100, Math.max(0, rl.percentUsed)), ...(Number.isNaN(t) ? {} : { resets_at: t }) }
}

async function save($: EngineInterface, where: string, rateLimits: readonly SessionRateLimit[]): Promise<void> {
  try {
    const [five_hour, seven_day] = ['five_hour', 'seven_day'].map((k) => win(rateLimits.find((r) => r.kind === k)))
    if (five_hour || seven_day) // no limits yet (e.g. before the first response, or an API key): nothing to save
      await $.fs.write(`${await dataDir($)}/limits.json`, `${JSON.stringify({ fetchedAt: await $.clock.now(), five_hour, seven_day })}\n`)
  } catch (err) {
    try { await $.fs.write(`${await dataDir($)}/errors-plugin.log`, `${where}: ${String(err)}\n`) } catch { /* nowhere to log */ }
  }
}

export const register: Register = (on) => {
  on('session.start', async ($, e, next) => {
    try { await save($, 'session.start', (await $.session.usage()).rateLimits) } catch { /* no limits now */ }
    return next(e)
  })
  on('session.measure', async ($, e, next) => (await save($, 'session.measure', e.rateLimits), next(e)))
}
