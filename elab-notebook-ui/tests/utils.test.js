
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

import { toMinutes, formatMinutes } from '../src/utils/duration.js'
import {
  formatDate,
  formatDateTime,
  formatAuditDate,
  formatMonth,
} from '../src/utils/dateFormatter.js'
import {
  showsRawDataTab,
  showsNatureOfSample,
  showsQualityMetrics,
  showsSubMetrics,
} from '../src/utils/rawData.js'
import { REPORT_CATEGORIES, showsReportTab } from '../src/utils/reportTab.js'

const CATEGORIES = [
  'Master Experiment',
  'Experiment',
  'Sub Experiment',
  'Sub Sub Experiment',
]

describe('duration.toMinutes', () => {
  test('passes whole minutes through', () => {
    assert.equal(toMinutes(0), 0)
    assert.equal(toMinutes(45), 45)
    assert.equal(toMinutes(1440), 1440)
  })

  test('floors fractions rather than rounding', () => {

    assert.equal(toMinutes(1.9), 1)
    assert.equal(toMinutes(0.4), 0)
  })

  test('clamps negatives to zero', () => {
    assert.equal(toMinutes(-5), 0)
    assert.equal(toMinutes(-0.5), 0)
  })

  test('treats unusable input as zero, never NaN', () => {

    for (const bad of [null, undefined, '', 'abc', {}, [], NaN]) {
      assert.equal(toMinutes(bad), 0, `toMinutes(${JSON.stringify(bad)})`)
    }
  })

  test('reads numeric strings, which is what a form field yields', () => {
    assert.equal(toMinutes('90'), 90)
    assert.equal(toMinutes(' 90 '), 90)
  })
})

describe('duration.formatMinutes', () => {
  test('zero and unusable input read as 0 min', () => {
    assert.equal(formatMinutes(0), '0 min')
    assert.equal(formatMinutes(null), '0 min')
    assert.equal(formatMinutes('abc'), '0 min')
    assert.equal(formatMinutes(-10), '0 min')
  })

  test('under an hour stays bare, with no total repeated', () => {
    assert.equal(formatMinutes(1), '1 min')
    assert.equal(formatMinutes(45), '45 min')
    assert.equal(formatMinutes(59), '59 min')
  })

  test('an exact hour drops the zero minutes', () => {
    assert.equal(formatMinutes(60), '1h (60 min)')
    assert.equal(formatMinutes(120), '2h (120 min)')
  })

  test('minutes past the hour are zero-padded', () => {
    assert.equal(formatMinutes(65), '1h 05m (65 min)')
    assert.equal(formatMinutes(125), '2h 05m (125 min)')
  })

  test('a day rolls over at 1440', () => {
    assert.equal(formatMinutes(1440), '1d (1440 min)')
    assert.equal(formatMinutes(1500), '1d 1h (1500 min)')
    assert.equal(formatMinutes(1640), '1d 3h 20m (1640 min)')
  })

  test('a whole-day-plus-minutes run does not lose the minutes', () => {


    assert.equal(formatMinutes(1445), '1d 05m (1445 min)')
  })
})

describe('dateFormatter.formatDate', () => {
  test('a date-only string keeps its own day', () => {


    assert.equal(formatDate('2026-08-27'), '27/08/26')
    assert.equal(formatDate('2026-01-01'), '01/01/26')
    assert.equal(formatDate('2026-12-31'), '31/12/26')
  })

  test('a datetime string formats to the same shape', () => {
    assert.equal(formatDate('2026-08-27 14:30:00'), '27/08/26')
  })

  test('accepts a Date instance', () => {
    assert.equal(formatDate(new Date(2026, 7, 27)), '27/08/26')
  })

  test('empty and unparseable values render as a dash, never Invalid Date', () => {
    for (const bad of ['', null, undefined, 'not a date', {}, new Date('nope')]) {
      assert.equal(formatDate(bad), '-', `formatDate(${String(bad)})`)
    }
  })

  test('zero-pads single-digit days, months and years', () => {
    assert.equal(formatDate('2005-03-04'), '04/03/05')
  })
})

describe('dateFormatter time variants', () => {
  test('formatDateTime carries a comma, formatAuditDate does not', () => {
    const input = '2026-08-27 14:30:00'
    assert.equal(formatDateTime(input), '27/08/26, 14:30')
    assert.equal(formatAuditDate(input), '27/08/26 14:30')
  })

  test('midnight is padded rather than collapsing to 0:0', () => {
    assert.equal(formatAuditDate('2026-08-27 00:05:00'), '27/08/26 00:05')
  })

  test('both fall back to a dash', () => {
    assert.equal(formatDateTime(null), '-')
    assert.equal(formatAuditDate('rubbish'), '-')
  })
})

describe('dateFormatter.formatMonth', () => {
  test('a YYYY-MM bucket becomes MM/YY', () => {
    assert.equal(formatMonth('2026-08'), '08/26')
    assert.equal(formatMonth('2026-12'), '12/26')
  })

  test('an unpadded month is padded', () => {

    assert.equal(formatMonth('2026-8'), '08/26')
  })

  test('a year below 2010 keeps its leading zero', () => {
    assert.equal(formatMonth('2005-03'), '03/05')
  })

  test('the all-time bucket and anything unrecognised pass through', () => {
    assert.equal(formatMonth('all_time'), 'all_time')
    assert.equal(formatMonth('nonsense'), 'nonsense')
    assert.equal(formatMonth(''), '')
    assert.equal(formatMonth(null), null)
  })
})

describe('rawData visibility rules', () => {
  test('every level except Master records raw data', () => {
    assert.equal(showsRawDataTab('Master Experiment'), false)
    for (const c of CATEGORIES.slice(1)) {
      assert.equal(showsRawDataTab(c), true, c)
    }
  })

  test('a run with no category yet still gets the tab', () => {


    assert.equal(showsRawDataTab(''), true)
    assert.equal(showsRawDataTab(undefined), true)
  })

  test('only Experiment and Sub Experiment name a sample type', () => {
    assert.equal(showsNatureOfSample('Experiment'), true)
    assert.equal(showsNatureOfSample('Sub Experiment'), true)
    assert.equal(showsNatureOfSample('Master Experiment'), false)
    assert.equal(showsNatureOfSample('Sub Sub Experiment'), false)
  })

  test('quality metrics key off the field, not the level', () => {
    assert.equal(showsQualityMetrics('Blood'), true)
    assert.equal(showsQualityMetrics(''), false)
    assert.equal(showsQualityMetrics(null), false)
    assert.equal(showsQualityMetrics(undefined), false)
  })

  test('sub-experiment metrics belong to exactly one level', () => {
    assert.equal(showsSubMetrics('Sub Experiment'), true)
    for (const c of ['Master Experiment', 'Experiment', 'Sub Sub Experiment', '']) {
      assert.equal(showsSubMetrics(c), false, c)
    }
  })
})

describe('reportTab visibility', () => {
  test('only the two levels that own a programme get a report', () => {
    assert.deepEqual(REPORT_CATEGORIES, ['Master Experiment', 'Experiment'])
    assert.equal(showsReportTab('Master Experiment'), true)
    assert.equal(showsReportTab('Experiment'), true)
    assert.equal(showsReportTab('Sub Experiment'), false)
    assert.equal(showsReportTab('Sub Sub Experiment'), false)
  })

  test('an unknown or empty category gets no report tab', () => {
    assert.equal(showsReportTab(''), false)
    assert.equal(showsReportTab(undefined), false)
  })
})
