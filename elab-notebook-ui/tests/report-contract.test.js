
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const APP = join(here, '..', '..')

const hierarchyPy = readFileSync(
  join(APP, 'elab_notebook', 'elab_notebook', 'api', 'hierarchy.py'),
  'utf8',
)
const reportVue = readFileSync(
  join(here, '..', 'src', 'components', 'experiments', 'ExperimentReport.vue'),
  'utf8',
)
const reportTableVue = readFileSync(
  join(here, '..', 'src', 'components', 'experiments', 'ReportTable.vue'),
  'utf8',
)


const tablesBlock = () => {
  const start = hierarchyPy.indexOf('_REPORT_TABLES = {')
  assert.notEqual(start, -1, '_REPORT_TABLES not found in hierarchy.py')
  const end = hierarchyPy.indexOf('\n}', start)
  assert.notEqual(end, -1, 'could not find the end of _REPORT_TABLES')
  return hierarchyPy.slice(start, end)
}


const backendTables = () => {
  const keys = [...tablesBlock().matchAll(/^\t"([a-z_]+)":/gm)].map((m) => m[1])
  assert.ok(keys.length >= 3, `parsed only ${keys.length} tables; the format changed`)
  return new Set(keys)
}


const backendFields = () => {
  const start = hierarchyPy.indexOf('_REPORT_FIELDS = (')
  assert.notEqual(start, -1, '_REPORT_FIELDS not found')
  const end = hierarchyPy.indexOf('\n)', start)
  const names = [...hierarchyPy.slice(start, end).matchAll(/"([a-z_0-9]+)"/g)].map((m) => m[1])
  assert.ok(names.length >= 10, `parsed only ${names.length} fields; the format changed`)
  return new Set(names)
}


const renderedTables = () =>
  new Set([...reportVue.matchAll(/rows\(node,\s*'([a-z_]+)'\)/g)].map((m) => m[1]))

const renderedFields = () =>
  new Set([...reportVue.matchAll(/node\.([a-z_0-9]+)/g)].map((m) => m[1]))

describe('report contract: endpoint and view agree', () => {
  test('every child table the endpoint fetches is printed somewhere', () => {
    const fetched = backendTables()
    const printed = renderedTables()
    const unprinted = [...fetched].filter((t) => !printed.has(t))
    assert.deepEqual(
      unprinted,
      [],
      `these tables are fetched but never rendered: ${unprinted.join(', ')}`,
    )
  })

  test('every table the view prints is actually fetched', () => {
    const fetched = backendTables()
    const printed = renderedTables()
    const unfetched = [...printed].filter((t) => !fetched.has(t))
    assert.deepEqual(
      unfetched,
      [],
      `the view renders tables the endpoint never sends: ${unfetched.join(', ')}`,
    )
  })

  test('the Result tab is carried end to end', () => {
    const fields = backendFields()
    const printed = renderedFields()


    for (const field of ['results', 'result', 'observation_and_conclusion']) {
      assert.ok(fields.has(field), `${field} is not fetched by the endpoint`)
      assert.ok(printed.has(field), `${field} is fetched but never rendered`)
    }
    assert.ok(backendTables().has('result_attachment'), 'result_attachment is not fetched')
  })

  test('the procedure half of the write-up is carried end to end', () => {
    const fields = backendFields()
    const printed = renderedFields()
    for (const field of ['procedure', 'precaution']) {
      assert.ok(fields.has(field), `${field} is not fetched`)
      assert.ok(printed.has(field), `${field} is fetched but never rendered`)
    }
  })

  test('every rich field the view renders is resolved for file urls', () => {


    const listStart = reportVue.indexOf('const RICH_FIELDS = [')
    assert.notEqual(listStart, -1, 'RICH_FIELDS not found')
    const listEnd = reportVue.indexOf(']', listStart)
    const declared = new Set(
      [...reportVue.slice(listStart, listEnd).matchAll(/'([a-z_]+)'/g)].map((m) => m[1]),
    )

    const rendered = new Set(
      [...reportVue.matchAll(/:value="node\.([a-z_0-9]+)"/g)].map((m) => m[1]),
    )
    assert.ok(rendered.size >= 4, `parsed only ${rendered.size} rich fields; format changed`)

    const unresolved = [...rendered].filter((f) => !declared.has(f))
    assert.deepEqual(
      unresolved,
      [],
      `rendered without being in RICH_FIELDS, so their images will not resolve: ${unresolved.join(', ')}`,
    )
  })

  test('no rich field is rendered with a raw v-html', () => {

    for (const [file, source] of [
      ['ExperimentReport.vue', reportVue],
      ['ReportTable.vue', reportTableVue],
    ]) {
      const raw = [...source.matchAll(/v-html="([^"]+)"/g)].map((m) => m[1])
      assert.deepEqual(
        raw,
        [],
        `${file} renders ${raw.join(', ')} with v-html; use RichContent so the ` +
          'attachment block does not print as JSON',
      )
    }
  })
})
