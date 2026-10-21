# 14 · Automation and the agent team

## The agents

Definitions live in `.claude/agents/`, so Claude sessions and the GitHub Action use the same agents.

| Agent | Job | Runs | Can change |
|---|---|---|---|
| **product-researcher** | Finds trending, high-margin, low-risk products (Google, Amazon, Flipkart, Meesho signals + IndiaMART prices) | Scheduled routine, every 6 h | `research/inbox/*.json` (new candidates only) |
| **product-reviewer** | Checks evidence, realistic price vs competitors, complaint/return risk; approves or rejects | Same routine, after research | `review` field of candidates |
| **ca-advisor** | HSN, GST rate, ITC, TCS/TDS, Legal Metrology, BIS; Odisha tax path; confirms margin after tax; ranks by profit | Same routine, after review | `ca` field, `gst_pct` |
| **architect** | Architecture review of every pull request | GitHub: `agent-review.yml` | Comments only |
| **developer-reviewer** | Code review + tests on every pull request | GitHub: `agent-review.yml` | Comments only |
| **qa-fixer** | Fixes a failed quality gate on a PR branch, adds a regression test | GitHub: `agent-autofix.yml` | The PR branch (commits marked `[autofix]`) |

The agents can't change `config/product_policy.toml` (your rules) or approve anything on your behalf. CODEOWNERS plus branch protection enforce that on GitHub.

## Product pipeline (every 6 hours)

```
research agent ──► research/inbox/*.json  (stage NEW)
                         │
review agent ────────────┤  review.verdict = approve / reject / needs_info
                         │
CA agent ────────────────┤  ca.verdict, HSN, confirmed GST
                         ▼
scripts/recommend.py ──► reports/recommendations.md   (RECOMMENDED / AWAITING_* / BELOW_TARGET / REJECTED)
                         │
                         └─► phone notification when a new product reaches RECOMMENDED
```

Ranking: highest expected profit per order first, among products that pass every hard rule, reach ≥ 30% margin on at least one channel, and have both agents' approval. Hard rules (`config/product_policy.toml`) reject apparel, footwear, food, supplements, skin cosmetics, batteries, chargers, power banks, wireless audio, smartwatches, mains-powered appliances without a supplier-held BIS licence, toys for under-3s, unauthorised brands, replicas and fragile glass.

**Electronics and appliances:** allowed only as (a) non-electrical gadget accessories (laptop and phone stands, organisers), or (b) electrical items whose supplier holds the BIS CRS/ISI licence for that exact model and handles warranty. Everything electrical in India now falls under a BIS order (CRS for electronics; the Household Electrical Appliances QCO, IS 302, for appliances), and selling without it is the main way these products "cause issues".

A RECOMMENDED product still needs your approval: quotation, sample, photos, and publishing are owner decisions (docs/06).

## Git quality pipeline

| Workflow | Trigger | What it does |
|---|---|---|
| `quality-gate.yml` | every PR and push to main | ruff lint, 36 tests, config/theme/inbox JSON validity, recommendation pipeline, policy-file guard |
| `agent-review.yml` | every PR | architect + developer agents post one review (APPROVE / REQUEST CHANGES) |
| `agent-autofix.yml` | quality gate fails on a PR | qa-fixer agent fixes it and pushes `[autofix]` commits to the PR branch |
| `ci-deploy.yml` | push to main | tests again, then `shopify theme push` of `site/theme/` |
| `sync-product-images.yml` | every 6 h + manual | Google Drive → Shopify product photos |

Recommended branch protection for `main` (GitHub → Settings → Branches): require the "Quality gate" check, require 1 approving review, require review from Code Owners.

## Google Drive photo automation

Folder layout (the script creates the category folders on its first run):

```
TradeIndia Marketplace - Product Images/
  Cleaning/  Home storage/  Kitchen/  Women's accessories/  Beauty/  Kids/  Electronics accessories/  Festive offers/
     cover.jpg                         optional: collection image (only fills an empty one)
     MF-10 Microfiber cloths pack of 10/
        1.jpg  2.jpg  3.jpg ...        1.jpg = main image; name order = gallery order
```

The folder name starts with the product's **SKU**. The script matches it to the Shopify product with that SKU, uploads only photos it hasn't uploaded before, and never deletes. Folders without a matching product are listed in the run log: products are created only after your approval.

### One-time setup (about 15 minutes)

1. **Drive folder:** in the TradeIndia Marketplace Google account, create `TradeIndia Marketplace - Product Images`. Copy its ID from the URL (`drive.google.com/drive/folders/<ID>`).
2. **Google service account:** console.cloud.google.com → new project → enable **Google Drive API** → IAM → Service accounts → create → Keys → add key (JSON). Share the Drive folder with the service account's email as **Editor**.
3. **Shopify Admin API token:** Shopify admin → Settings → Apps → Develop apps (or the Shopify Dev Dashboard if the admin sends you there) → create app → Admin API scopes `read_products`, `write_products`, `write_files` → install → copy the Admin API access token.
4. **GitHub secrets** (TIPM → Settings → Secrets and variables → Actions):

| Secret | Value |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | the whole JSON key file |
| `DRIVE_ROOT_FOLDER_ID` | folder ID from step 1 |
| `SHOPIFY_ADMIN_TOKEN` | token from step 3 |
| `SHOPIFY_CLI_THEME_TOKEN` | Theme Access password (theme deploys) |
| `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` | for the review and auto-fix agents |

5. Run **Actions → Sync product images → Run workflow** with "dry run" ticked to check before the first real sync.

Never put these keys in the repository, a chat or a file. GitHub secrets are the only place they go.
