import { json as jsonLanguage } from '@codemirror/lang-json'
import { yaml as yamlLanguage } from '@codemirror/lang-yaml'
import { StreamLanguage } from '@codemirror/language'
import { properties as propertiesMode } from '@codemirror/legacy-modes/mode/properties'
import { EditorView, keymap } from '@codemirror/view'
import type { Extension } from '@codemirror/state'
import CodeMirror from '@uiw/react-codemirror'
import { useEffect, useMemo, useRef } from 'react'

type FileCodeEditorProps = {
    path: string
    value: string
    isDarkMode: boolean
    onChange: (value: string) => void
    onSave: () => void
}

function languageFor(path: string): Extension[] {
    const name = path.toLowerCase()
    if (/\.(ya?ml)$/.test(name)) return [yamlLanguage()]
    if (/\.(json|jsonc)$/.test(name)) return [jsonLanguage()]
    if (/\.(ini|conf|cnf|cfg|properties|env|toml)$/.test(name)) {
        // The legacy mode ships its own copy of @codemirror/streamparser types.
        return [StreamLanguage.define(propertiesMode as unknown as Parameters<typeof StreamLanguage.define>[0])]
    }
    return []
}

export default function FileCodeEditor({ path, value, isDarkMode, onChange, onSave }: FileCodeEditorProps) {
    const saveRef = useRef(onSave)
    useEffect(() => { saveRef.current = onSave }, [onSave])

    const extensions = useMemo(() => {
        const saveKeymap = keymap.of([{ key: 'Mod-s', preventDefault: true, run: () => { saveRef.current(); return true } }])
        const theme = EditorView.theme({
            '&': { fontSize: '13.5px', height: '100%' },
            '.cm-scroller': {
                fontFamily: "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace",
                lineHeight: '1.55',
            },
            '.cm-gutters': isDarkMode
                ? { backgroundColor: 'rgba(13, 17, 23, 0.9)', borderRight: '1px solid rgba(255,255,255,0.06)' }
                : { backgroundColor: '#f8fafc', borderRight: '1px solid #e2e8f0' },
        })
        return [saveKeymap, theme, ...languageFor(path)]
    }, [path, isDarkMode])

    return (
        <CodeMirror
            value={value}
            height="100%"
            style={{ height: '100%' }}
            theme={isDarkMode ? 'dark' : 'light'}
            extensions={extensions}
            onChange={onChange}
            basicSetup={{
                lineNumbers: true,
                foldGutter: true,
                highlightActiveLine: true,
                highlightActiveLineGutter: true,
                bracketMatching: true,
                closeBrackets: true,
                autocompletion: false,
                searchKeymap: true,
            }}
        />
    )
}
