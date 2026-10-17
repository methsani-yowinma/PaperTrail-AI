# PaperTrail AI — frontend

Next.js 16 (App Router, Cache Components) + React 19 + Tailwind CSS 4.
See the repository [README](../README.md) and [docs/](../docs) for the full picture.

```bash
npm install
cp .env.example .env.local
npm run dev        # http://localhost:3000  (backend expected at API_BASE_URL, default http://127.0.0.1:8000)
npm run test       # Vitest
npm run typecheck  # strict TypeScript
npm run lint
npm run build
```

- All API calls go through `app/api/backend/[...path]/route.ts` (same-origin proxy to FastAPI).
- `proxy.ts` refreshes Supabase sessions and protects app routes. It is inactive in local mode.
- Design tokens: `app/globals.css`. UI primitives: `components/ui` (shadcn/ui conventions on `radix-ui`).
