# Coding decisions

## UI{#ui}

Design System Foundation (shadcn/ui, Tailwind, Dark/Light theme)

## Container Development{#container}

**Image Build Directory**: Use `build/` directory exclusively for image construction. Ignore other directories including `docker/`.

**Testing Protocol**: All backend and frontend code must be tested within containers. During development, copy code to the appropriate container paths.

**Development Workflow**: Use `make` commands for all operations (build, start, stop, logs, clean, etc.).

## Testing

- Use http://127.0.0.1+port for testing, not use localhost that may not connect for the reason of http proxy