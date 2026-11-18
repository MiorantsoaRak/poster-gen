import { describe, expect, it } from 'vitest'
import { credit, elapsedLabel, ended, localTime, OVERDUE_MS, overdue, phase, retryDelay, termsDate, type Balance } from '../src/generation'

describe('phase of a generation, from the job and the image', () => {
  it.each([['queued', false, 'queued'], ['running', false, 'running'], ['succeeded', false, 'receiving'], ['succeeded', true, 'ready'],
    ['failed', false, 'failed'], ['interrupted', false, 'failed'], ['cancelled', true, 'failed']] as const)('%s, image loaded %s: %s', (status, loaded, expected) => {
    expect(phase({ status }, loaded)).toBe(expected)
  })
  it('never says ready before the image is loaded', () => expect(phase({ status: 'succeeded' }, false)).not.toBe('ready'))
})

describe('elapsed time', () => {
  it.each([[0, '0:00'], [999, '0:00'], [1000, '0:01'], [59_999, '0:59'], [60_000, '1:00'], [101_000, '1:41'], [3_725_000, '62:05']])('%d ms reads %s', (ms, label) => {
    expect(elapsedLabel(ms)).toBe(label)
  })
  it('is never negative', () => expect(elapsedLabel(-4000)).toBe('0:00'))
})

describe('long wait', () => {
  it('starts after 100 s of creation, not at 100 s', () => {
    expect(overdue('running', OVERDUE_MS)).toBe(false)
    expect(overdue('running', OVERDUE_MS + 1)).toBe(true)
  })
  it.each(['queued', 'receiving', 'ready', 'failed'] as const)('is never said while %s', current => expect(overdue(current, 10 * OVERDUE_MS)).toBe(false))
})

describe('server time on this device', () => {
  const now = Date.parse('2026-11-14T10:00:00Z')
  it('corrects a device clock 30 s ahead of the server', () => {
    expect(localTime('2026-11-14T09:59:00.000000+00:00', -30_000, now)).toBe(now - 30_000)
  })
  it('reads the microseconds the server writes', () => expect(localTime('2026-11-14T09:59:50.123456+00:00', 0, now)).toBe(now - 9877))
  // The device's zone must not shift it: at UTC+3 a stamp read as local time would be three hours off.
  it.each(['2026-11-14T09:59:50.123456', '2026-11-14T09:59:50.123456Z', '2026-11-14T12:59:50.123456+03:00', '2026-11-14T12:59:50.123456+0300'])('reads %s as the same UTC instant', stamp => {
    expect(localTime(stamp, 0, now)).toBe(now - 9877)
  })
  it('is never in the future (whole-second Date header)', () => expect(localTime('2026-11-14T10:00:00.900000+00:00', 0, now)).toBe(now))
  it.each([[null, 0], [undefined, 0], ['', 0], ['pas une date', 0], ['2026-11-14T09:00:00Z', null]] as const)('falls back to first sight (%s, skew %s)', (stamp, skew) => {
    expect(localTime(stamp, skew, now)).toBe(now)
  })
})

describe('next poll after a failure', () => {
  it.each([[1, 2000], [2, 4000], [3, 8000], [4, 10000], [40, 10000]])('after %d failures: %d ms', (failures, delay) => expect(retryDelay(failures)).toBe(delay))
})

describe('what a new image says it costs, and what stops it (D-BALANCE-006)', () => {
  const PURCHASE = 'Pour obtenir des crédits, contactez l’administrateur.'
  const DAY = { reason: 'day', message_fr: 'La boutique a atteint sa limite d’images pour aujourd’hui.' }
  const PAUSE = { reason: 'service', message_fr: 'Le service est en pause.' }
  const balance = (available: number, pending = 0, blocked: Partial<Balance['blocked']> = {}): Balance =>
    ({ available, pending, purchase_fr: PURCHASE, blocked: { scene: null, text_texture: null, ...blocked } })
  it('normal: the cost and what is left, with what waits', () => {
    expect(credit(balance(4), 'scene')).toEqual({ stop: false, text: '1 crédit · il vous en reste 4' })
    expect(credit(balance(12, 2), 'text_texture')).toEqual({ stop: false, text: '1 crédit · il vous en reste 12, 2 en attente' })
  })
  it.each([1, 2, 3])('bientôt à court at %d: how to buy, the button as usual', available => {
    expect(credit(balance(available), 'scene')).toEqual({ stop: false, text: `1 crédit · il vous en reste ${available}. Bientôt à court : ${PURCHASE}` })
  })
  it('bientôt à court says what waits too', () => {
    expect(credit(balance(1, 1), 'scene').text).toBe(`1 crédit · il vous en reste 1, 1 en attente. Bientôt à court : ${PURCHASE}`)
  })
  it.each([0, -1])('zero (%d): nothing is sent, and how to buy', available => {
    expect(credit(balance(available, 2), 'scene')).toEqual({ stop: true, text: `Il ne vous reste plus de crédit : rien ne sera envoyé. Vos affiches restent disponibles. ${PURCHASE}` })
  })
  it('blocked: its own sentence, no purchase text, nothing is sent; it comes before the lack of credit', () => {
    for (const available of [0, 2, 50]) {
      expect(credit(balance(available, 0, { scene: DAY }), 'scene')).toEqual({ stop: true, text: DAY.message_fr })
      expect(credit(balance(available, 0, { scene: PAUSE, text_texture: PAUSE }), 'text_texture')).toEqual({ stop: true, text: PAUSE.message_fr })
    }
  })
  it('reads its own entry: a text material is not blocked while scenes are', () => {
    expect(credit(balance(5, 0, { scene: DAY }), 'text_texture')).toEqual({ stop: false, text: '1 crédit · il vous en reste 5' })
  })
  it('unknown (unread or failed): never 0, the server decides', () => {
    expect(credit(null, 'scene')).toEqual({ stop: false, text: '1 crédit · solde indisponible pour le moment' })
  })
  // D-TERMS-004: the conditions not accepted stop a new image as any block does, and say so, so that the control offers
  // to read them instead of a dead end; no other reason does.
  it('says when what stops it is the conditions of use', () => {
    const TERMS = { reason: 'terms', message_fr: 'Acceptez d’abord les conditions d’utilisation.' }
    for (const available of [0, 50]) expect(credit(balance(available, 0, { scene: TERMS, text_texture: TERMS }), 'scene')).toEqual({ stop: true, text: TERMS.message_fr, terms: true })
    expect(credit(balance(5, 0, { scene: DAY }), 'scene').terms).toBeUndefined()
    expect(credit(balance(0), 'scene').terms).toBeUndefined()
    expect(credit(null, 'scene').terms).toBeUndefined()
  })
})

describe('the version of the conditions, as the dialog says it (D-TERMS-004)', () => {
  it.each([['2026-11-17', '17 novembre 2026'], ['2027-05-01', '1er mai 2027'], ['2027-08-09', '9 août 2027'], ['2028-02-29', '29 février 2028']])('%s reads « %s »', (version, said) => {
    expect(termsDate(version)).toBe(said)
  })
  it.each(['2026-13-01', '2026-00-10', 'v2', ''])('shows %j as it is', version => expect(termsDate(version)).toBe(version))
})

describe('what a followed job that made nothing says', () => {
  const job = (status: string, credit: string | null, kind = 'scene', error_code: string | null = null) => ({ status, kind, error_code, credit })
  it.each(['failed', 'interrupted', 'cancelled'])('%s with its credit given back: the cause, then the credit', status => {
    const said = ended(job(status, 'given_back', 'scene', 'refused'))
    expect(said.endsWith(' Votre crédit vous a été rendu.')).toBe(true)
    expect(said.replace(' Votre crédit vous a été rendu.', '')).toBe(ended(job(status, null, 'scene', 'refused')))
  })
  it('keeps each cause', () => {
    expect(ended(job('interrupted', 'given_back'))).toBe('La génération a été interrompue. Aucun nouvel appel automatique n’a été lancé. Votre crédit vous a été rendu.')
    expect(ended(job('failed', null, 'look'))).toBe('Le style n’a pas pu être décrit à partir de cette affiche. Essayez une autre image ; rien n’est perdu.')
    expect(ended(job('failed', 'given_back', 'scene', 'refused'))).toMatch(/^Le service d’images a refusé cette demande.* Votre crédit vous a été rendu\.$/)
  })
  it('says nothing of a credit for a job that took none, or a view without the field', () => {
    expect(ended(job('failed', null, 'text_patch', 'timeout'))).not.toContain('crédit')
    expect(ended({ status: 'failed', kind: 'scene', error_code: null })).not.toContain('crédit')
  })
})
