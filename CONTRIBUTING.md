# Contributing to Heimdall Ground Control

Thank you for your interest in contributing.

Ground Control is the operations dashboard for the Heimdall wildfire situational-awareness system. It consumes the `MeteoReport v1` contract and renders a 3D map with fire perimeters, risk buffers, and forecast timelines.

## Getting started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/Edge-AI-for-Situational-Awareness-in-Emergencies.git
   cd Edge-AI-for-Situational-Awareness-in-Emergencies
   git checkout v0.1-GroundControl
   ```
3. Install dependencies:
   ```bash
   pnpm install
   ```
4. Create a branch:
   ```bash
   git checkout -b feat/my-feature
   ```

## Workflow

- Keep commits small and atomic with descriptive messages in English.
- Run `pnpm exec tsc --noEmit` before every commit — TypeScript must be clean.
- Run `pnpm test` — all test suites must pass.
- Run `pnpm build` to verify the production build succeeds.
- Open a PR against `v0.1-GroundControl` with a clear description of the change.

## Code conventions

- **Strict TypeScript** — no `any`, no unjustified `@ts-ignore`.
- **Clean architecture** — respect the `types → schemas → api → stores → components` separation.
- **No obvious comments** — only document the *why*, not the *what*.
- **Absolute imports** — use `@/src/...` instead of relative paths.
- **Tailwind-first** — use utility classes; avoid inline styles.
- **Zustand stores** — keep actions small; prefer selectors for derived state.

## Architecture

```
src/
├── types/        # TypeScript interfaces and type aliases
├── schemas/      # Zod schemas (MeteoReport contract validation)
├── api/          # TanStack Query hooks + ky HTTP client
├── stores/       # Zustand stores (connection, UI, map, layers, settings)
├── components/
│   ├── app/      # Top-level screens (ConnectScreen, DashboardScreen, TopBar)
│   ├── map/      # MapLibre + Deck.gl overlays, controls, legend
│   ├── sidebar/  # Status, situation, and layers panels
│   └── ui/       # Reusable primitives (Badge, ErrorBoundary, InfoTooltip)
├── hooks/        # Shared React hooks
├── lib/          # Utilities and providers
└── mocks/        # MSW handlers for offline/demo development
```

## Reporting bugs

Open an issue on the [`v0.1-GroundControl` branch](https://github.com/ComunidadIA-OS/Edge-AI-for-Situational-Awareness-in-Emergencies/issues) describing:

1. Expected vs. actual behavior
2. Steps to reproduce
3. Browser version and operating system
4. Whether you are connected to a real Jetson or using demo/mock mode

## License

By contributing, you agree that your code will be published under the [Apache 2.0 License](LICENSE).
