
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

import { isImagePath, fileNameFromUrl } from '../src/utils/attachment.js'

describe('attachment.isImagePath', () => {
  test('recognises the picture formats a lab actually uploads', () => {
    for (const ext of ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg', 'avif']) {
      assert.equal(isImagePath('/private/files/gel.' + ext), true, ext)
    }
  })

  test('is case insensitive, as a name off a Windows machine will be', () => {
    assert.equal(isImagePath('/files/Scan.PNG'), true)
    assert.equal(isImagePath('/files/Scan.JPEG'), true)
  })

  test('a query string or fragment still resolves to the picture behind it', () => {
    assert.equal(isImagePath('/files/plot.png?v=2'), true)
    assert.equal(isImagePath('/files/plot.png#fig1'), true)
  })

  test('anything else is a file, not a picture', () => {
    assert.equal(isImagePath('/files/raw-trace.csv'), false)
    assert.equal(isImagePath('/files/protocol.pdf'), false)
    assert.equal(isImagePath('/files/sequence.fastq'), false)

    assert.equal(isImagePath('/files/notes.png.txt'), false)
  })

  test('an unset attachment is not a picture and does not throw', () => {
    assert.equal(isImagePath(''), false)
    assert.equal(isImagePath(null), false)
    assert.equal(isImagePath(undefined), false)
  })
})

describe('attachment.fileNameFromUrl', () => {
  test('shows the file name rather than the whole stored path', () => {
    assert.equal(fileNameFromUrl('/private/files/raw-trace.csv'), 'raw-trace.csv')
    assert.equal(fileNameFromUrl('/files/gel.png'), 'gel.png')
  })

  test('decodes the percent-encoding frappe stores a spaced name with', () => {
    assert.equal(fileNameFromUrl('/files/Gel%20run%202.png'), 'Gel run 2.png')
  })

  test('a name that is not valid encoding falls back to the raw tail', () => {

    assert.equal(fileNameFromUrl('/files/50%_glycerol.pdf'), '50%_glycerol.pdf')
  })

  test('an unset attachment yields an empty string', () => {
    assert.equal(fileNameFromUrl(''), '')
    assert.equal(fileNameFromUrl(null), '')
    assert.equal(fileNameFromUrl(undefined), '')
  })
})
