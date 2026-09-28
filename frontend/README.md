# DataQualiQ web interface

React, Vite, and Tailwind CSS provide the upload flow, quality overview, issue and field views, review checklist, and client-side PDF export.

See the [main project README](../README.md) for the product walkthrough, architecture, setup, screenshots, and development roadmap.

```bash
npm ci
npm run dev -- --host localhost --port 5173
```

Start the backend at `http://localhost:8000`. Use `npm.cmd` on Windows if PowerShell blocks the npm script wrapper.

```bash
npm run lint
npm run build
node --test src/components/IssueCard.test.js src/utils/affectedValues.test.js src/utils/reviewOrder.test.js src/utils/navigation.test.js
```

`responsive_smoke.mjs` is an optional Windows/Edge browser harness, not a requirement for running the application. See comments in that script for environment assumptions.
