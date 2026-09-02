
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

import { splitStored, joinStored, richHasContent } from '../src/utils/richText.js'

const PDF = {
  name: 'ACC-PRQ-2026-00294.pdf',
  url: '/private/files/ACC-PRQ-2026-00294ecbbd2.pdf',
  size: 109965,
}
const OPEN = '<!--rte-attachments-->'
const CLOSE = '<!--/rte-attachments-->'

describe('richText.splitStored', () => {
  test('a plain write-up comes back untouched with no files', () => {
    const html = '<p>To perform photosynthesis in the lab.</p>'
    assert.deepEqual(splitStored(html), { body: html, files: [] })
  })

  test('an unset field is a blank body, not a crash', () => {
    assert.deepEqual(splitStored(''), { body: '', files: [] })
    assert.deepEqual(splitStored(null), { body: '', files: [] })
    assert.deepEqual(splitStored(undefined), { body: '', files: [] })
  })

  test('the attachment block is separated from the write-up', () => {
    const body = '<p>Run complete.</p>'
    const stored = `${body}${OPEN}${JSON.stringify([PDF])}${CLOSE}`
    const out = splitStored(stored)
    assert.equal(out.body, body, 'the write-up must not keep the block')
    assert.deepEqual(out.files, [PDF])


    assert.ok(!out.body.includes('ACC-PRQ'), 'attachment JSON leaked into the body')
    assert.ok(!out.body.includes('{'), 'attachment JSON leaked into the body')
  })

  test('a field that is only an attachment has an empty body', () => {
    const out = splitStored(`${OPEN}${JSON.stringify([PDF])}${CLOSE}`)
    assert.equal(out.body, '')
    assert.deepEqual(out.files, [PDF])
  })

  test('several attachments all come through, in order', () => {
    const files = [PDF, { name: 'trace.csv', url: '/private/files/trace.csv', size: 12 }]
    const out = splitStored(`<p>x</p>${OPEN}${JSON.stringify(files)}${CLOSE}`)
    assert.deepEqual(out.files, files)
  })

  test('a truncated block keeps the write-up and drops the list', () => {

    const out = splitStored(`<p>Important.</p>${OPEN}[{"name":"half`)
    assert.equal(out.body, '<p>Important.</p>')
    assert.deepEqual(out.files, [])
  })

  test('unparseable JSON drops the list rather than throwing', () => {
    const out = splitStored(`<p>Important.</p>${OPEN}not json${CLOSE}`)
    assert.equal(out.body, '<p>Important.</p>')
    assert.deepEqual(out.files, [])
  })

  test('valid JSON of the wrong shape is discarded', () => {

    assert.deepEqual(splitStored(`<p>x</p>${OPEN}42${CLOSE}`).files, [])
    assert.deepEqual(splitStored(`<p>x</p>${OPEN}null${CLOSE}`).files, [])

    assert.deepEqual(splitStored(`<p>x</p>${OPEN}[{"name":"x"}]${CLOSE}`).files, [])
  })
})

describe('richText.joinStored', () => {
  test('round-trips a write-up with attachments', () => {
    const body = '<p>Run complete.</p>'
    const out = splitStored(joinStored(body, [PDF]))
    assert.equal(out.body, body)
    assert.deepEqual(out.files, [PDF])
  })

  test('no marker is written when there is nothing to put in it', () => {
    assert.equal(joinStored('<p>x</p>', []), '<p>x</p>')
    assert.equal(joinStored('<p>x</p>', null), '<p>x</p>')
    assert.equal(joinStored('<p>x</p>', undefined), '<p>x</p>')
  })
})

describe('richText.richHasContent', () => {
  test('prose counts', () => {
    assert.equal(richHasContent('<p>Something observed.</p>'), true)
  })

  test('an emptied editor does not', () => {
    assert.equal(richHasContent('<p><br></p>'), false)
    assert.equal(richHasContent(''), false)
    assert.equal(richHasContent(null), false)
    assert.equal(richHasContent('<p>&nbsp;</p>'), false)
  })

  test('a figure or a table with no words is still content', () => {
    assert.equal(richHasContent('<p><img src="/files/gel.png"></p>'), true)
    assert.equal(richHasContent('<table><tr><td></td></tr></table>'), true)
  })

  test('an attachment with no write-up is content', () => {
    assert.equal(richHasContent(`${OPEN}${JSON.stringify([PDF])}${CLOSE}`), true)
  })

  test('the attachment JSON is never mistaken for prose', () => {


    assert.equal(richHasContent(`<p><br></p>${OPEN}not json${CLOSE}`), false)
  })
})
