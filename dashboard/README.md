# Websoft9 Dashboard

Unified frontend framework for websoft9 platform.

## Tech Stack

- **Build Tool**: Vite 7
- **Framework**: React 19 + TypeScript 5.9
- **Routing**: TanStack Router (to be added in Story 7.2)
- **UI**: shadcn/ui + Tailwind CSS (to be added in Story 7.3)
- **Theme**: Dark/Light mode (to be added in Story 7.3)
- **i18n**: react-i18next (to be added in Story 7.4)
- **State Management**: TanStack Query + React Context (to be added in Story 7.5)

## Development

```bash
# Install dependencies
npm install

# Start dev server
npm run dev

# Type checking
npm run typecheck

# Linting
npm run lint
npm run lint:fix

# Format code
npm run format

# Build for production
npm run build

# Preview production build
npm run preview
```

## Project Structure

```
src/
├── routes/          # TanStack Router file-based routes (Story 7.2)
├── components/      # React components
│   └── ui/          # shadcn/ui components (Story 7.3)
├── lib/             # Utility libraries
│   ├── baas.ts      # BaaS client wrapper (Story 7.7)
│   ├── cockpit.ts   # cockpit.js wrapper (Story 7.8)
│   ├── i18n.ts      # i18next configuration (Story 7.4)
│   └── query-client.ts  # TanStack Query setup (Story 7.5)
├── contexts/        # React Context providers (Story 7.5)
├── hooks/           # Custom React hooks
└── styles/          # Global styles (Story 7.3)
```

## Stories Progress

- [x] 7.1: Project Setup & Build Pipeline ✅
- [ ] 7.2: TanStack Router Setup
- [ ] 7.3: Design System Foundation
- [ ] 7.4: i18n Setup
- [ ] 7.5: State Management Architecture
- [ ] 7.6: Layout Components
- [ ] 7.7: BaaS Client Integration
- [ ] 7.8: Cockpit.js Integration
- [ ] 7.9: Error Handling & Loading States
- [ ] 7.10: Responsive Design & Mobile Optimization

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```
