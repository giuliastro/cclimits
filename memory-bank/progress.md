# Progress

## Working Features

- **Claude Code**: OAuth token from keychain (macOS) or `~/.claude/.credentials.json` (Linux)
- **OpenAI Codex**: JWT from `~/.codex/auth.json`
- **Gemini CLI** (legacy — CLI retired 2026-06-18): OAuth from `~/.gemini/oauth_creds.json`; token refresh needs an installed Gemini CLI package or env overrides, otherwise reports ⏰ expired
- **Google Antigravity**: OAuth tokens read from `~/.gemini/antigravity-cli/antigravity-oauth-token` (written by `agy` CLI) or `ANTIGRAVITY_REFRESH_TOKEN`; per-model quota tracking, live-verified against real install
- **Z.AI**: API token from environment variable (`$ZAI_KEY` or `$ZAI_API_KEY`), 5h shared token quota + monthly MCP-tools quota (`mcp_quota` with per-tool breakdown & reset) + client-side peak/off-peak quota-rate indicator (`quota_rate`, ⚡3x oneline marker during peak)
- **OpenRouter**: API token from environment variable (`$OPENROUTER_API_KEY`)
- **Kimi K2 (Moonshot)**: API token from env var (`$MOONSHOT_API_KEY`), prepaid balance tracking
- **Synthetic.new**: API token from env var (`$SYNTHETIC_API_KEY`), reports subscription/rolling-5h/weekly-credits buckets via `GET /v2/quotas` (free probe)
- **GitHub Copilot**: GitHub token auto-discovered (`~/.config/github-copilot/apps.json`/`hosts.json` → gh CLI `hosts.yml` → `$GITHUB_TOKEN`/`$GH_TOKEN`); monthly premium-request quota via undocumented `copilot_internal/user` (free probe, live-verified); oneline shows `Copilot: N% (mo)`; no-subscription tokens hidden from check-all display
- **Display modes**: JSON, detailed, compact one-liner, noemoji color mode; oneline distinguishes 🔑 no credentials / ⏰ expired token / ❌ real error
- **Time windows**: 5h and 7d for Claude/Codex (Codex windows classified by `limit_window_seconds`, not slot position — weekly-only accounts return one window in the primary slot; renderer degrades gracefully to whichever window exists), 5h for Z.AI (shared across GLM models; `both` mode shows tokens%/monthly-MCP%, `--resets` there shows both countdowns), 5h rolling + weekly credits for Synthetic.new
- **Reset countdowns** (`--resets`, alias `--timeremaining`): appends `↻` countdowns per provider in oneline (6 of 8 providers; Antigravity shows earliest model reset via `summary.next_reset_in`; OpenRouter/Kimi are prepaid balances with nothing to reset)
- **Caching** (`--cached`, `~/.cache/cclimits/usage.json`): atomic writes (temp + rename), merge on write (no-creds/partial runs preserve prior good entries), provider filters honored on cache hits (refetch if a requested provider is missing), output labeled with cache age
- **BYOK Support**: Explicit documentation for monitoring Aider/Continue via their underlying provider keys.

## Current Status

- ✅ All core AI tool integrations functional (Claude, Codex, Gemini, Antigravity, Z.AI, OpenRouter, Kimi, Synthetic.new, Copilot)
- ✅ Full local pytest suite passes with isolated cache and module-level patch targets
- ✅ Cross-platform credential detection (macOS/Linux)
- ✅ npm package published as `cclimits`
- ✅ Gemini models grouped by quota tier (3-Flash, Flash, Pro)
- ✅ Antigravity models sorted by tightest remaining quota with min/avg summary; compact oneline displays tightest model usage percentage
- ✅ Research on additional providers completed (`research/ai-coding-providers.md`)
- ✅ Providers fetched concurrently; cache hits skip all network/credential calls; transient failures fall back to <24h-old cached data with stale marker (v1.3.0)
- ✅ Data-driven `PROVIDERS` registry — adding a provider is one registry entry + one fetch function
- ✅ CI (GitHub Actions matrix) + automated npm publish on `v*` tags via Trusted Publishing (OIDC); 261 tests
- ✅ Expired/no-creds Gemini (retired CLI) hidden from check-all display; visible via `--gemini`/`--json`
- ✅ GitHub Copilot integration (2026-08-05) — feasibility flipped from the Jan research: `copilot_internal/user` accepts plain PATs and is used by community tools (openusage, opencode-copilot-usage)

## Known Issues

None currently.

## What's Left to Build

### High Priority
- **Replit Integration**: Endpoint identified (`usage-credits-balance`), awaiting implementation.

### Medium Priority
- ~~CI/CD pipeline for npm publishing~~ ✅ Done (2026-07-12) — GitHub Actions workflows added for CI (pytest on push/PR) and automated publish (tag push → npm with provenance)
- Gemini legacy OAuth auto-refresh or graceful retirement (CLI retired 2026-06-18; expired token renders ⏰)

### Low Priority
- TypeScript rewrite to remove Python dependency
- ~~Copilot~~ ✅ Done (2026-08-05) via undocumented `copilot_internal/user` endpoint
- **Cursor / Windsurf**: Feasibility still low — Cursor's usage API needs a `WorkosCursorSessionToken` browser cookie; Windsurf has no public quota API. **MiniMax coding plan** (`coding_plan/remains`) and **OpenCode Zen** balance are watch-list items blocked on upstream auth/endpoints (MiniMax-AI/MiniMax-M2#88, anomalyco/opencode#10448).
- Configurable output formats
- Historical usage tracking
