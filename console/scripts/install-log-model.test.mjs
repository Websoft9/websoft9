import assert from 'node:assert/strict'
import { test } from 'node:test'
import { buildInstallLogRows, formatInstallLogLine, formatInstallSourceReason, getInstallError, getInstallExportText, getInstallSourceGroups, getInstallSourceSummary, getInstallSteps } from '../src/features/my-apps/install-log-model.ts'

const app = { app_id: 'example', status: 3, proxy_enabled: false, logs: [] }

test('download percentages use real bounded totals without duplicating metadata', () => {
    assert.equal(formatInstallLogLine({ status: 'Downloading', message: 'Downloading #abc', id: 'abc', progressDetail: { current: 512, total: 1024 } }), 'Downloading #abc 50% (512 B/1.0 KB)')
    assert.match(formatInstallLogLine({ status: 'Downloading', progressDetail: { current: 200, total: 100 } }), /100%/)
    assert.doesNotMatch(formatInstallLogLine({ status: 'Downloading', progressDetail: { current: 1, total: 0 } }), /%/)
    assert.equal(formatInstallLogLine({ status: 'Extracting', progressDetail: { current: 12, units: 's' } }), 'Extracting (12s)')
})

test('layers update in place and remain isolated by image', () => {
    const rows = buildInstallLogRows([{
        title: 'Pulling docker image', sub_logs: [
            { image: 'mysql:8', id: 'abc', status: 'Downloading', progressDetail: { current: 10, total: 100 } },
            { image: 'mysql:8', id: 'def', status: 'Waiting' },
            { image: 'mysql:8', id: 'abc', status: 'Downloading', progressDetail: { current: 80, total: 100 } },
            { image: 'redis:7', id: 'abc', status: 'Downloading', progressDetail: { current: 20, total: 100 } },
        ]
    }])
    assert.equal(rows.length, 3)
    assert.match(rows[0].text, /80%/)
    assert.match(rows[2].text, /20%/)
})

test('cancelled pulls do not mark future installation steps completed', () => {
    const steps = getInstallSteps({ ...app, status: 6, logs: [{ title: 'Initializing installation' }, { title: 'Pulling docker image' }, { title: 'Installation cancelled' }] })
    assert.deepEqual(steps.map(step => step.state), ['done', 'interrupted', 'pending', 'pending'])
})

test('access is only completed when configured; absent access is skipped on success', () => {
    assert.equal(getInstallSteps({ ...app, status: 1 })[3].state, 'skipped')
    assert.equal(getInstallSteps({ ...app, status: 1, logs: [{ title: 'Configuring the domain' }] })[3].state, 'done')
})

test('known failures classify narrowly and unknown failures preserve original text', () => {
    for (const [raw, category] of [['port is already allocated', 'port'], ['no space left on device', 'disk'], ['permission denied', 'permission'], ['TLS handshake timeout', 'network'], ['yaml: line 12', 'configuration'], ['opaque failure', 'unknown']]) {
        const error = getInstallError({ ...app, error: raw })
        assert.equal(error.category, category)
        assert.equal(error.raw, raw)
    }
    const error = getInstallError({ ...app, error: 'opaque failure' })
    assert.equal(error.phase, undefined)
    assert.equal(error.object, undefined)
})

test('mirror access errors stay image failures and expose every attempted source', () => {
    const error = getInstallError({ ...app, error: "Unable to pull image 'example:1'.\n - direct pull [example:1]: permission denied\n - mirror [mirror/example:1]: timeout" })
    assert.equal(error.category, 'image')
    assert.equal(error.object, 'example:1')
    assert.equal(error.sources.length, 2)
})

test('source summaries show registry domains without treating image tags as hosts', () => {
    assert.deepEqual(getInstallSourceSummary({ label: 'direct pull', reference: 'nginx:1.27', reason: 'pull access denied' }), { registry: 'docker.io', nameKey: 'originalSource', result: 'denied' })
    assert.deepEqual(getInstallSourceSummary({ label: 'direct pull', reference: 'ghcr.io/example/app:1', reason: 'timeout' }), { registry: 'ghcr.io', nameKey: 'originalSource', result: 'timeout' })
    assert.deepEqual(getInstallSourceSummary({ label: 'mirror mirror.invalid', reference: 'mirror.invalid/websoft9dev/app:1', reason: 'Internal Server Error: EOF' }), { registry: 'mirror.invalid', nameKey: 'mirrorSource', result: 'connection' })
    assert.equal(getInstallSourceSummary({ label: 'direct pull', reference: 'localhost:5000/app:1', reason: 'unexpected failure' }).registry, 'localhost:5000')
    assert.equal(getInstallSourceSummary({ label: 'direct pull', reference: 'registry.example.com/team/app:1', reason: 'not found' }).nameKey, 'originalSource')
})

test('multiple failed accelerators share one group and retain every address and attempt', () => {
    const error = getInstallError({ ...app, error: "Unable to pull image 'ghcr.io/example/app:1'.\n - direct pull [ghcr.io/example/app:1]: unauthorized\n - mirror first.example [first.example/example/app:1]: timeout\n - mirror second.example [second.example/example/app:1]: EOF\n - mirror first.example [first.example/ghcr.io/example/app:1]: not found" })
    assert.equal(error.sources.length, 4)
    const groups = getInstallSourceGroups(error.sources)
    assert.deepEqual(groups.map(group => group.nameKey), ['originalSource', 'mirrorSource'])
    assert.equal(groups[1].sources.length, 3)
    assert.deepEqual(groups[1].sources.map(source => getInstallSourceSummary(source).registry), ['first.example', 'second.example', 'first.example'])
    assert.deepEqual(error.sources.map(source => getInstallSourceSummary(source).result), ['denied', 'timeout', 'connection', 'missing'])
    const single = getInstallError({ ...app, error: "Unable to pull image 'example:1'.\n - mirror first.example [first.example/example:1]: timeout" })
    assert.equal(getInstallSourceGroups(single.sources).length, 1)
    assert.deepEqual(getInstallSourceGroups([]), [])
})

test('source reasons remove HTTP wrappers without losing quoted references or original errors', () => {
    const cause = 'failed to resolve reference "mirror.invalid/example:1": Head "https://mirror.invalid/v2/example/manifests/1": EOF'
    const wrapped = `Internal Server Error ("${cause}")`
    assert.equal(formatInstallSourceReason(wrapped), cause)
    assert.equal(formatInstallSourceReason('Internal Server Error: EOF'), 'EOF')
    assert.equal(formatInstallSourceReason('Not Found ("No such image: example:1")'), 'No such image: example:1')
    assert.equal(formatInstallSourceReason('Service Unavailable ("registry unavailable")'), 'registry unavailable')
    for (const reason of ['Internal Server Error', 'Internal Server Error ("")', 'unexpected failure', cause]) {
        assert.equal(formatInstallSourceReason(reason), reason)
    }
    const raw = `Unable to pull image 'example:1'.\n - mirror mirror.invalid [mirror.invalid/example:1]: ${wrapped}`
    const failure = { ...app, status: 4, error: raw }
    assert.equal(getInstallError(failure).sources[0].reason, wrapped)
    assert.equal(getInstallExportText(failure, title => title), raw)
})

test('failure exports contain the original error without empty stage headings', () => {
    const failure = { ...app, status: 4, error: 'Unable to pull image\nOriginal source failure', logs: [{ title: 'Initializing installation' }, { title: 'Pulling docker image', sub_logs: ['Partial progress'] }] }
    assert.equal(getInstallExportText(failure, title => title), failure.error)
    assert.equal(getInstallExportText({ ...failure, status: 6 }, title => title), '')
    assert.equal(getInstallExportText({ ...failure, error: null }, title => title), 'Pulling docker image\nPartial progress')
    assert.equal(getInstallExportText({ ...app, status: 4, logs: [{ title: 'Initializing installation' }] }, title => title), '')
})