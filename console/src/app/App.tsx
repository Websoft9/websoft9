import { useState } from 'react'

import { AppProviders } from './providers/app-providers'
import { createAppRouter } from './router'

export function App() {
    const [router] = useState(createAppRouter)

    return <AppProviders router={router} />
}
