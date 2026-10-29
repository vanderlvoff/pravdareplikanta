# Deployment strategy — local Mac to Cloudflare Pages

## Principles

- Mac produces all files. Cloudflare Pages serves finished static files; no server-side Python or PHP is necessary.
- Wrangler uploads a complete `dist/` snapshot; the public version should only be changed on successful validation and explicit approval.
- Cloudflare project and domain must be created by the account owner. Do not assume `replicantpravda.com` is available or registered.
- API tokens must be environment variables or CLI auth, never hardcoded or stored in Git.

## Initial setup (operator-guided)

1. Register domain, enable MFA, set DNS and connect to Cloudflare account.
2. Create Cloudflare Pages project in **Direct Upload** mode.
3. Install Node.js and Wrangler locally; authenticate securely.
4. Create a sample `dist/` with `index.html` and a localized issue.
5. Test on the default `*.pages.dev` preview before connecting public domain.
6. Add custom domain after owner verifies content and certificate.
7. Document rollback to previous successful deployment.

## Target workflow

```bash
rp validate content/issues/2026-10-29.json
rp build --issue 2026-10-29 --output dist
rp verify --issue 2026-10-29 --output dist
# Human visually reviews previews
rp publish --output dist --confirm
```

Direct Wrangler equivalent (only after initial Cloudflare configuration):

```bash
npx wrangler pages deploy ./dist --project-name replicantpravda
```

Do not assume these commands work until implementation and credentials are configured.

## Operations

- Keep versions of `content/`, assets, and final PDFs locally and back them up.
- Do not overwrite old source issues; use revisions and release tags.
- Avoid publishing drafts, unlicensed photos or internal editorial notes.
- Monitor Cloudflare Pages build/deployment quotas and individual file size limits; validate limits against current documentation when implementation begins.
- Optional automation via macOS launchd runs builds, but public publishing should remain gated by approval until explicitly changed.
- Mac power/sleep/internet can prevent new issues; existing site should remain online.
