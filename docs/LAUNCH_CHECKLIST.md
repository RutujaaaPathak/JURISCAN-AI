# Launch Checklist

Status of the production-readiness and redesign pass. Nothing here should be
committed, pushed or deployed without the repo owner's approval.

## Design direction

Midnight-navy, charcoal and champagne-gold. Dark is now the default theme, with
a coordinated champagne-tinted light mode still available from the theme toggle.

> Note: the visual reference image
> (`C:\Users\Shrey Ruparel\Downloads\Gemini_Generated_Image_medmzqmedmzqmedm.png`)
> could not be read, because the assistant model has no image input. The theme
> was built from the written description (midnight navy, charcoal, champagne
> gold, restrained depth, no purple gradients). If the image shows specifics not
> covered by the text, they were not matched.

## What this pass changed (verified locally)

- Rebuilt the design tokens in `frontend/src/index.css`: midnight-navy and
  charcoal surfaces, champagne-gold primary and bronze accents, cream text,
  muted gray secondary text, translucent-looking cards with fine borders and
  restrained shadows. Data-visualisation colours updated to gold, bronze, slate
  and teal.
- Ambient lighting utilities: `bg-app-sheen` (layered radial light),
  `bg-hero` (centred champagne glow), `bg-grid`, `surface-panel`, plus a
  `prefers-reduced-motion` block.
- Motion utilities: `animate-float`, `animate-drift`, `animate-aurora`,
  `animate-rise`, `animate-fade`. All are opt-in and disabled under reduced
  motion.
- Dark set as the default theme (`frontend/src/lib/theme.ts`,
  `frontend/index.html` pre-paint script and theme colours).
- Cinematic landing page (`frontend/src/pages/HomePage.tsx`): navy hero with a
  gold glow, floating document-sheet silhouettes, eyebrow + the required
  headline, gold primary CTA, service-status panel, a product preview showing
  clause highlighting and risk findings, capabilities, explicit limits, workflow
  and a closing CTA. No fabricated metrics, testimonials, customer counts or
  certifications.
- Compact navbar (`Navbar.tsx`) with Home, Capabilities and How it works,
  status indicator, theme control and auth actions.
- Rebuilt footer with Product and Legal columns and a "does not provide legal
  advice" line (`Footer.tsx`).
- Privacy Policy and Terms pages (`LegalPage.tsx`, routes `/privacy`, `/terms`).
- Brand mark and favicon recoloured to navy + gold
  (`Brand.tsx`, `public/favicon.svg`).
- Auth layouts restyled with the gold ambient backdrop (`AuthLayout.tsx`).
- Case-status chart colours aligned to the palette (`LawyerDashboardPage.tsx`).
- Skip-to-content links on both layouts; scroll manager for anchors/routes.
- Removed dead demo code with fabricated identities (`data/demo.ts`,
  `common/DemoNotice.tsx`).
- Production metadata in `index.html`, `public/robots.txt`, SPA fallback
  `public/_redirects`, refreshed `.env.example` files.

### Verification run

- `frontend`: `npm run build` succeeds (only the pre-existing >500 kB chunk
  advisory).
- `frontend`: `npm run lint` passes with only the four pre-existing
  `react(only-export-components)` warnings.
- `frontend`: `npm test` passes (15 tests).
- Backend tests were green earlier in this project (208 passed); no backend code
  changed in this pass.

### Not verified (no browser available)

- Rendered visual review across viewports was not performed (no browser testing
  tool is available in this environment).
- Console-error and real reduced-motion behaviour were not observed live.
- The favicon was not confirmed rendering in a browser; the SVG validates.

## Must do before launch

### Configuration

- [ ] Set a strong, unique `SECRET_KEY` in the production `.env`
      (`python -c "import secrets; print(secrets.token_urlsafe(48))"`).
- [ ] Set `APP_ENV=production` and `APP_DEBUG=false`.
- [ ] Point `DATABASE_URL` at the production PostgreSQL instance.
- [ ] Set `FRONTEND_ORIGIN` and `CORS_ORIGINS` to the real frontend origin(s).
- [ ] Set the frontend `VITE_API_BASE_URL` to the deployed API URL and rebuild
      (it is compiled into the bundle).
- [ ] Confirm HTTPS end to end. The frontend calls the API by absolute URL, so an
      HTTPS page must call an HTTPS API to avoid mixed-content blocks.
- [ ] Configure the SPA fallback on the chosen host (`_redirects` works for
      Netlify/Cloudflare Pages; add an equivalent rewrite for Vercel or nginx).

### Legal and content (flagged, not invented)

Placeholders rendered in the legal pages, to be filled by someone who can
confirm them:

- [ ] `[legal entity name]` (Privacy, Terms)
- [ ] `[privacy contact email]`, `[contact email]`
- [ ] `[date to be confirmed]` (both pages)
- [ ] `[list of subprocessors to be confirmed]` (hosting, email delivery)
- [ ] `[retention period to be confirmed]`
- [ ] `[security and hosting specifics to be confirmed]`
- [ ] `[liability cap to be confirmed]`
- [ ] `[jurisdiction to be confirmed]` (governing law)
- [ ] Confirm the analysis citations suit the intended jurisdiction. The rule
      engine currently cites UK statutes, while `docs/DESIGN.md` targets India.
- [ ] Have the Privacy Policy and Terms reviewed by counsel before publishing.

### Assets and metadata

- [ ] Add an Open Graph image and reference it (`og:image` is not set).
- [ ] Add a `sitemap.xml` once the production domain is known, and restore the
      `Sitemap:` line in `robots.txt`.
- [ ] Confirm the favicon renders in the target browsers.

## Recommended but not done

- [ ] Route-level code splitting to reduce the initial JS bundle (single ~629 kB
      chunk; Vite prints a size advisory).
- [ ] Automated end-to-end browser tests for the redesigned flows.
- [ ] A consolidated lawyer calendar view (`/dashboard/calendar` is an explicit
      placeholder today).
- [ ] Decide whether the `comingSoon` sidebar items (Audit Reports, Team
      Management, Audit Log) should be hidden until implemented.
