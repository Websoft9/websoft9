import { Download, KeyRound, RefreshCw, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { IconCopy } from './my-app-credential-icons'

import { executeMyAppCliCommand, readMyAppCredential, type MyAppCliCommand, type MyAppCliCommandResult, type MyAppCredentialDescriptor, type MyAppCredentialResult } from './use-my-app-access'

type CredentialProps = {
    appId: string
    credentials: MyAppCredentialDescriptor[]
    onCopy: (content: string) => Promise<void>
    onCopyFeedback: (success: boolean) => void
}

function CredentialOutputActions({ content, onClear, onCopy, onCopyFeedback }: Pick<CredentialProps, 'onCopy' | 'onCopyFeedback'> & { content: string; onClear: () => void }) {
    const { t } = useTranslation('shell')
    const prefix = 'myAppsDetailPage.accessPanel.runtimeCredentials'
    return (
        <span className="myapps-creds-actions">
            <button className="myapps-creds-copy-btn" aria-label={t(`${prefix}.copy`)} title={t(`${prefix}.copy`)} type="button" onClick={async () => {
                try { await onCopy(content); onCopyFeedback(true) } catch { onCopyFeedback(false) }
            }}><IconCopy /></button>
            <button className="myapps-creds-copy-btn" aria-label={t(`${prefix}.clearOutput`)} title={t(`${prefix}.clearOutput`)} type="button" onClick={onClear}><X size={16} /></button>
        </span>
    )
}

function CredentialOutput({ content, onClear, onCopy, onCopyFeedback }: Pick<CredentialProps, 'onCopy' | 'onCopyFeedback'> & { content: string; onClear: () => void }) {
    return (
        <div className="myapps-runtime-output">
            <div className="myapps-runtime-credential-result" aria-live="polite">
                <div className="myapps-runtime-output-actions"><CredentialOutputActions content={content} onClear={onClear} onCopy={onCopy} onCopyFeedback={onCopyFeedback} /></div>
                <pre>{content}</pre>
            </div>
        </div>
    )
}

function CredentialField({ appId, descriptor, onCopy, onCopyFeedback }: {
    appId: string
    descriptor: MyAppCredentialDescriptor
    onCopy: CredentialProps['onCopy']
    onCopyFeedback: CredentialProps['onCopyFeedback']
}) {
    const { t } = useTranslation('shell')
    const prefix = 'myAppsDetailPage.accessPanel.runtimeCredentials'
    const [result, setResult] = useState<MyAppCredentialResult | null>(null)
    const [busy, setBusy] = useState(false)
    const request = useRef<AbortController | null>(null)
    const isLog = descriptor.source === 'container-log'

    useEffect(() => {
        const clearHiddenResult = () => {
            if (!document.hidden) return
            request.current?.abort()
            request.current = null
            setResult(null)
            setBusy(false)
        }
        document.addEventListener('visibilitychange', clearHiddenResult)
        return () => {
            request.current?.abort()
            document.removeEventListener('visibilitychange', clearHiddenResult)
        }
    }, [])

    async function retrieve() {
        if (request.current) return
        const controller = new AbortController()
        request.current = controller
        setBusy(true)
        setResult(null)
        try {
            const response = await readMyAppCredential(appId, descriptor.field, controller.signal)
            if (!controller.signal.aborted && request.current === controller) setResult(response)
        } catch (error) {
            if (!controller.signal.aborted && request.current === controller) {
                const statusCode = (error as { statusCode?: number }).statusCode
                setResult({ ...descriptor, status: 'error', error_code: statusCode === 401 || statusCode === 403 ? 'permission_denied' : 'read_failed' })
            }
        } finally {
            if (request.current === controller) {
                request.current = null
                setBusy(false)
            }
        }
    }

    const ready = result?.status === 'ready' && Boolean(result.content)
    const errorKey = result?.error_code && ['credential_unavailable', 'container_unavailable', 'output_too_large', 'invalid_rule', 'permission_denied'].includes(result.error_code)
        ? result.error_code : 'read_failed'

    return (
        <div className="myapps-runtime-credential-field">
            <div className="myapps-runtime-credential-head">
                <span className="myapps-access-entry-subtitle">{t(`${prefix}.fields.${descriptor.field}`)}</span>
                <div className="myapps-runtime-credential-commands">
                    <button className="myapps-runtime-credential-fetch" disabled={busy} onClick={() => void retrieve()} type="button">
                        {busy || ready ? <RefreshCw className={busy ? 'myapps-runtime-credential-spinner' : undefined} size={15} /> : <Download size={15} />}
                        {t(`${prefix}.${busy ? 'reading' : ready ? 'refresh' : 'retrieve'}`)}
                    </button>
                </div>
            </div>
            <div className="myapps-runtime-credential-content">
                {result && !ready ? (
                    <div className="myapps-runtime-credential-error" role="status">{t(`${prefix}.errors.${!isLog && errorKey === 'credential_unavailable' ? 'file_unavailable' : errorKey}`)}</div>
                ) : null}
                {ready ? <CredentialOutput content={result?.content ?? ''} onClear={() => setResult(null)} onCopy={onCopy} onCopyFeedback={onCopyFeedback} /> : null}
            </div>
        </div>
    )
}

function CliCommandField({ appId, descriptor, onCopy, onCopyFeedback }: Pick<CredentialProps, 'appId' | 'onCopy' | 'onCopyFeedback'> & { descriptor: MyAppCliCommand }) {
    const { t } = useTranslation('shell')
    const selectedValue = descriptor.command
    const [cliBusy, setCliBusy] = useState(false)
    const [cliResult, setCliResult] = useState<MyAppCliCommandResult | null>(null)
    const cliRequest = useRef<AbortController | null>(null)

    useEffect(() => {
        const clearHiddenResult = () => {
            if (!document.hidden) return
            cliRequest.current?.abort()
            cliRequest.current = null
            setCliResult(null)
            setCliBusy(false)
        }
        document.addEventListener('visibilitychange', clearHiddenResult)
        return () => {
            cliRequest.current?.abort()
            document.removeEventListener('visibilitychange', clearHiddenResult)
        }
    }, [])

    async function executeCommand() {
        if (!selectedValue || cliRequest.current) return
        const controller = new AbortController()
        cliRequest.current = controller
        setCliBusy(true)
        setCliResult(null)
        try {
            const result = await executeMyAppCliCommand(appId, selectedValue, controller.signal)
            if (!controller.signal.aborted && cliRequest.current === controller) setCliResult(result)
        } catch (error) {
            if (!controller.signal.aborted && cliRequest.current === controller) {
                const statusCode = (error as { statusCode?: number }).statusCode
                setCliResult({ command: selectedValue, status: 'error', error_code: statusCode === 401 || statusCode === 403 ? 'permission_denied' : 'command_failed' })
            }
        } finally {
            if (cliRequest.current === controller) {
                cliRequest.current = null
                setCliBusy(false)
            }
        }
    }

    const prefix = 'myAppsDetailPage.accessPanel.runtimeCredentials'
    const isReadResultReady = cliResult?.status === 'ready' && descriptor.action !== 'generate' && descriptor.action !== 'set'
    return (
        <div className="myapps-runtime-cli">
            <label className="myapps-access-entry-subtitle" htmlFor={`myapps-cli-${appId}-${descriptor.id}`}>{t(`${prefix}.fields.${descriptor.field ?? 'token'}`)}</label>
            <div className="myapps-runtime-cli-command-row">
                <div className="myapps-creds-value myapps-runtime-cli-command">
                    <input className="myapps-runtime-cli-input" id={`myapps-cli-${appId}-${descriptor.id}`} readOnly value={selectedValue} />
                    <span className="myapps-creds-actions">
                        <button className="myapps-creds-copy-btn" aria-label={t(`${prefix}.copyCommand`)} title={t(`${prefix}.copyCommand`)} type="button" onClick={async () => {
                            try { await onCopy(selectedValue); onCopyFeedback(true) } catch { onCopyFeedback(false) }
                        }}><IconCopy /></button>
                    </span>
                </div>
                <div className="myapps-runtime-credential-commands">
                    <button className="myapps-runtime-credential-fetch myapps-runtime-cli-execute" disabled={cliBusy || !selectedValue} onClick={() => void executeCommand()} type="button">
                        {cliBusy || isReadResultReady ? <RefreshCw size={15} className={cliBusy ? 'myapps-runtime-credential-spinner' : undefined} /> : <Download size={15} />}
                        {t(`${prefix}.${cliBusy ? 'executing' : descriptor.action === 'generate' ? 'generate' : descriptor.action === 'set' ? 'setCredential' : isReadResultReady ? 'refresh' : 'retrieve'}`)}
                    </button>
                </div>
            </div>
            {cliResult?.output ? <CredentialOutput content={cliResult.output} onClear={() => setCliResult(null)} onCopy={onCopy} onCopyFeedback={onCopyFeedback} /> : null}
            <div className="myapps-runtime-credential-result myapps-runtime-cli-output" aria-live="polite">
                {cliBusy ? <pre>{t(`${prefix}.executingOutput`)}</pre> : null}
                {cliResult?.status === 'error' ? <pre>{t(`${prefix}.errors.${cliResult.error_code ?? 'command_failed'}`)}</pre> : null}
            </div>
        </div>
    )
}

export function MyAppCredentials({ appId, credentials, cliCommands, onCopy, onCopyFeedback }: CredentialProps & { cliCommands: MyAppCliCommand[] }) {
    const { t } = useTranslation('shell')
    if (!credentials.length && !cliCommands.length) return null
    return (
        <section className="myapps-access-entry-card myapps-runtime-credentials">
            <div className="myapps-access-entry-card-main">
                <div className="myapps-access-entry-icon myapps-runtime-credential-icon"><KeyRound size={18} /></div>
                <div className="myapps-access-entry-content">
                    <div className="myapps-access-entry-title-row">
                        <div className="myapps-access-entry-title">{t('myAppsDetailPage.accessPanel.runtimeCredentials.title')}</div>
                    </div>
                    {credentials.map(descriptor => (
                        <CredentialField appId={appId} descriptor={descriptor} key={`${appId}:${descriptor.source}:${descriptor.field}`} onCopy={onCopy} onCopyFeedback={onCopyFeedback} />
                    ))}
                    {cliCommands.map(descriptor => (
                        <CliCommandField appId={appId} descriptor={descriptor} key={`${appId}:${descriptor.id}`} onCopy={onCopy} onCopyFeedback={onCopyFeedback} />
                    ))}
                </div>
            </div>
        </section>
    )
}