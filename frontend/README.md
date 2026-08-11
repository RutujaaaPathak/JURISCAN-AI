# JurisScan-AI — Frontend

Frontend foundation for **JurisScan-AI**, an AI-powered legal document auditing
and contract analysis system.

## Technologies

- React 19
- TypeScript
- Vite
- Tailwind CSS v4
- shadcn/ui

## Requirements

- Node.js 20.19+ (LTS recommended)
- npm 10+

## Installation

```bash
npm install
```

## Development

```bash
npm run dev
```

The Vite development server starts at `http://localhost:5173`.

## Production Build

```bash
npm run build
```

## Preview

```bash
npm run preview
```

Serves the production build locally (default `http://localhost:4173`).

## Project Structure

```
frontend/
├── public/                 # Static assets
├── src/
│   ├── components/
│   │   └── ui/             # shadcn/ui components
│   ├── layouts/            # Application layouts
│   ├── pages/              # Page components
│   ├── lib/                # Utilities and helpers
│   ├── App.tsx             # Application root
│   ├── main.tsx            # React bootstrap
│   └── index.css           # Global styles and Tailwind
├── components.json         # shadcn/ui configuration
├── vite.config.ts
├── tsconfig.json
└── package.json
```
