// Fail-closed check for the permission store, run against the real module (no
// stubs): in Node there is no server behind the relative /api path, so
// fetchPermissions takes its own failure branch. That is the same branch a
// dropped request takes in the browser, which is exactly what must not open a
// door. Run: node perm-store.test.mjs
import { createPinia, setActivePinia } from 'pinia'
import { usePermissionStore } from './src/stores/permissions.js'

setActivePinia(createPinia())
const perms = usePermissionStore()

let pass = 0
let fail = 0
const check = (label, got, want) => {
  const ok = JSON.stringify(got) === JSON.stringify(want)
  ok ? pass++ : fail++
  console.log(`  [${ok ? 'PASS' : 'FAIL'}] ${label}: got=${JSON.stringify(got)} want=${JSON.stringify(want)}`)
}

console.log('TEST — no flash-of-full-access')
check('can() before any fetch (doctype)', perms.can('Lab Experiment', 'write'), false)
check('can() before any fetch (record)', perms.can('Lab Experiment', 'write', 'EXP-1'), false)
check('unknown ptype is false, not undefined', perms.can('Lab Experiment', 'nonsense'), false)

console.log('\nTEST — a failed fetch stays closed and is not cached')
const before = Object.keys(perms.cache).length
const res = await perms.fetchAndCache('Lab Experiment', 'EXP-1')
check('failed fetch resolves null', res, null)
check('can() still false after failure', perms.can('Lab Experiment', 'write', 'EXP-1'), false)
check('failure not cached (next mount may retry)', Object.keys(perms.cache).length, before)

console.log('\nTEST — cache keying separates doctype-level from record-level')
perms.cache['Lab Experiment:new'] = { create: 1, write: 0 }
perms.cache['Lab Experiment:EXP-1'] = { create: 0, write: 1 }
check('doctype-level reads the :new slot', perms.can('Lab Experiment', 'create'), true)
check('record-level reads its own slot', perms.can('Lab Experiment', 'create', 'EXP-1'), false)
check('record-level write', perms.can('Lab Experiment', 'write', 'EXP-1'), true)
check('a different record is still closed', perms.can('Lab Experiment', 'write', 'EXP-2'), false)

console.log('\nTEST — invalidate closes the door again')
perms.invalidate('Lab Experiment', 'EXP-1')
check('invalidated record is false', perms.can('Lab Experiment', 'write', 'EXP-1'), false)
check('other entries survive', perms.can('Lab Experiment', 'create'), true)
perms.invalidateAll()
check('invalidateAll clears everything', perms.can('Lab Experiment', 'create'), false)

console.log(`\nRESULT: ${pass}/${pass + fail} checks passed`)
process.exit(fail ? 1 : 0)
