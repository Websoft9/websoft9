import { defineConfig } from '@playwright/test'

const baseURL = process.env.W9_BASE_URL || 'http://127.0.0.1:9000'

export default defineConfig({
    testDir: './tests',
    fullyParallel: false,
    forbidOnly: Boolean(process.env.CI),
    retries: 0,
    reporter: [['list']],
    projects: [
        {
            name: 'unit',
            testDir: './tests/unit',
        },
        {
            name: 'e2e',
            testDir: './tests/e2e',
            use: { baseURL, headless: true, trace: 'off' },
        },
    ],
})
