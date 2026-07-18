# Book Pharm — Build Roadmap

Phased todo list. Each phase ends with something demonstrable. Read `CLAUDE.md` first.

**Sequencing logic:** the POS is the client's most urgent pain — her current one is unreliable and she's contractually stuck with it. It ships first. The storefront matters but she's operating without it today, so it comes after the shop itself is running cleanly. Offline sync lands early because retrofitting it later means rewriting the sales layer.

---

## Phase 0 — Foundation

- [x] Init monorepo, `.gitignore` (must exclude `backend/.venv/`), `.env.example`
- [x] Create the backend virtual environment (`python -m venv backend/.venv`), activate it, and do every subsequent install/command from inside it — no global/system pip installs, ever
- [x] Django project scaffold (`config/`), split settings (`base`/`dev`/`prod`)
- [x] MySQL connection, confirm it works locally against the same MySQL version cPanel runs — using XAMPP MariaDB 10.4.32 locally; **still need to confirm this actually matches the cPanel host's engine/version** before Phase 8
- [x] Create empty app skeletons per the layout in `CLAUDE.md`
- [x] Custom user model **before the first migration** (retrofitting this later is painful) — email-based login, `role` field for future staff accounts
- [x] DRF installed, token auth configured
- [x] Base templates: storefront base, portal base, shared partials
- [x] Port the palette and typography from `mockups/` into a CSS variable set
- [x] `README` with local setup steps, starting with venv creation + activation

**Done when:** `runserver` boots (from inside the activated venv), admin login works, base template renders with the Book Pharm design language. ✅ Verified 2026-07-17.

---

## Phase 1 — Catalog & inventory

- [x] `Category`, `Book` models + migrations — plus a `StockAdjustment` model (not in CLAUDE.md's original field list) to back the audit trail item below
- [x] Internal code generator for books without an ISBN (collision-safe) — sequential `BP-000001` style, retry-on-`IntegrityError` in `Book.save()`
- [x] ISBN normalization + validation (ISBN-10/13) — via `isbnlib` (pure Python, no compiled deps — safe for cPanel); canonicalizes to 13-digit form
- [x] Book cover upload handling — `ImageField` via Pillow, local `MEDIA_ROOT` in dev
- [x] Portal: book list with search + filters — search by title/author/ISBN/internal code, category filter, low-stock-only filter, HTMX partial swaps (no full-page reloads)
- [x] Portal: add/edit book form (ISBN field with manual-entry fallback) — slide-over panel matching the mockup
- [x] Portal: stock adjustment with an audit trail — delta + reason + notes + who, per book
- [x] Low-stock computed queryset + alert card on the portal — `Book.objects.low_stock()`, dashboard card
- [x] Seed script with sample books for development — `manage.py seed_catalog`
- [x] `GET /api/catalog/` with `?updated_since=` for incremental sync — token-authenticated; **`cost_price` deliberately excluded from the API response** (POS doesn't need it to sell; keeps the profit-sensitive field portal-only)

**Done when:** the owner can add stock two ways — scan an ISBN, or type in a book that has none — and see low-stock warnings. ✅ Verified 2026-07-18 (formatted-ISBN entry, no-ISBN entry, stock adjustment audit trail, dashboard alert, and the API endpoint all exercised end to end).

---

## Phase 2 — POS core (in-store sales)

- [ ] `Sale`, `SaleItem`, `DiscountRule` models
- [ ] Sale service layer: create sale, apply discounts, decrement stock, atomic transaction
- [ ] `POST /api/sales/` (single sale, online path)
- [ ] Barcode/ISBN lookup endpoint
- [ ] Electron shell: main process, preload, secure IPC, window config
- [ ] POS checkout UI: scan/search panel, running cart, totals, payment buttons
- [ ] Payment methods: cash, MoMo, card (record method; MoMo/card here are recorded, not gateway-processed — in-store payment happens outside the app)
- [ ] Customer capture at checkout (phone, name, email, birthday) — phone required, rest optional-but-prompted
- [ ] Receipt generation + print preview
- [ ] Device token auth via `safeStorage`
- [ ] Portal: discount rule config (percent + fixed)

**Done when:** an attendant can run a full in-store sale end to end, online, and stock drops correctly.

---

## Phase 3 — Offline sync

The hardest phase. Don't rush it.

- [ ] SQLite schema in Electron: catalog mirror + sales outbox
- [ ] Catalog pull on app start + periodic refresh
- [ ] Client-side UUID generation for every sale (online and offline alike)
- [ ] Outbox write on every sale, regardless of connectivity
- [ ] `POST /api/sync/sales/` — batch, idempotent on `offline_uuid`, per-UUID result
- [ ] Sync worker in Electron: retry with backoff, drain outbox on reconnect
- [ ] Online/offline indicator in the POS top bar (must be unmissable)
- [ ] **Oversell reconciliation:** accept synced sales that push stock negative, flag them for the owner
- [ ] Portal: reconciliation alert view for negative/conflicted stock
- [ ] Test: pull the network mid-sale, sell 20 items offline, reconnect, verify zero loss and no duplicates
- [ ] Test: replay the same batch twice, confirm idempotency

**Done when:** you can run a full book-fair simulation with the network off and lose nothing on reconnect.

---

## Phase 4 — Owner portal & reporting

- [ ] Owner auth, session handling, role scaffolding (single owner now, extensible later)
- [ ] Dashboard: today's sales, week's orders, profit margin, low-stock count
- [ ] Sales report: daily/weekly/monthly, with date range picker
- [ ] Profit margin per book report (`selling_price - cost_price` × qty sold)
- [ ] Stock levels report
- [ ] `Expense` model + entry form
- [ ] **Business vs. personal withdrawal toggle** — profit reports must exclude personal draws
- [ ] Expense report with the business/personal split visible
- [ ] Chart.js integration for trends
- [ ] CSV export on each report

**Done when:** the owner can answer "did I make money this month, and is that number honest about my personal withdrawals?" without calling you.

---

## Phase 5 — Storefront & online orders

- [ ] Public book listing: grid, pagination, category filters, search
- [ ] Book detail page — **server-rendered, with proper meta tags and structured data** (this is the SEO payoff; don't skip it)
- [ ] Cart (session-based, no login required)
- [ ] Checkout: delivery vs. pickup toggle
- [ ] `DeliveryPricingRule` abstraction — implement fixed zones as the default, keep distance-based and manual pluggable
- [ ] Customer capture at online checkout (phone, name, email, birthday)
- [ ] Paystack: initialize transaction, inline/redirect checkout
- [ ] Paystack webhook handler + verify-on-return (**both** — don't trust the redirect alone)
- [ ] `PaymentTransaction` records with full raw payload stored
- [ ] Order confirmation page + confirmation email/SMS
- [ ] Customer "confirm receipt" flow
- [ ] `Review` model + post-purchase rating/comment form
- [ ] Portal: online orders list + detail drawer
- [ ] Stock decrements on paid online orders, visible instantly in the POS

**Done when:** a real customer can buy a book online, pay by MoMo, confirm receipt, and leave a review — and the shop's stock reflects it immediately.

---

## Phase 6 — Customers, loyalty & SMS

- [ ] Customer list in the portal with purchase history
- [ ] Phone normalization + dedup (`+233XXXXXXXXX`) — merge existing duplicates
- [ ] `LoyaltyTransaction` model + points accrual on sale
- [ ] Loyalty rules config in the portal (owner-defined thresholds/rewards)
- [ ] Reward redemption at POS checkout
- [ ] SMSOnlineGH client wrapper + `SmsLog`
- [ ] `SmsCampaign` model + composer UI with audience selector
- [ ] Management command: send scheduled campaigns
- [ ] Management command: daily birthday greetings
- [ ] cPanel cron entries for both commands
- [ ] Opt-out handling and an unsubscribe flag on `Customer`

**Done when:** the owner can send a promo blast and birthday SMS go out automatically, replacing the WhatsApp broadcasts she's been paying for.

---

## Phase 7 — Marketplace (Jumia)

- [ ] `Sale.channel = JUMIA` path + manual order entry in the portal
- [ ] `external_ref` capture for Jumia order references
- [ ] Return/reversal flow: restore stock, set `returned_at`, exclude from revenue
- [ ] Reports segmented by channel (in-store / online / Jumia)
- [ ] Portal: marketplace orders tab

**Done when:** Jumia sales and their frequent returns are tracked without polluting in-house sales figures.

---

## Phase 8 — Deploy & handover

- [ ] Register the domain (client has no domain yet — this is a real blocker for launch, raise it early)
- [ ] cPanel: MySQL database + user
- [ ] cPanel: "Setup Python App" (Passenger), WSGI entry point
- [ ] Static files via `collectstatic` → `public_html`; media directory configured
- [ ] SSL (Let's Encrypt via cPanel)
- [ ] Environment variables set in production
- [ ] Cron jobs registered (campaigns, birthdays)
- [ ] Paystack live keys + webhook URL registered
- [ ] SMSOnlineGH live credentials + sender ID approved (**apply early — sender ID approval takes time**)
- [ ] Electron build + installer, pointed at the production API
- [ ] Database backup routine
- [ ] Smoke test every flow in production
- [ ] Client UAT session
- [ ] Owner training + short handover guide

**Done when:** the shop is running on it and the owner isn't calling you daily.

---

## Cross-cutting (ongoing)

- [ ] Every backend command (`pip install`, `manage.py`, tests, management commands) runs inside the activated `backend/.venv` — never system/global Python
- [ ] Never expose `cost_price` on any public-facing surface
- [ ] Test the offline sync path after every change to the sales layer
- [ ] Keep `mockups/` as reference only — never wire raw exports into the app
- [ ] Confirm the two open decisions with the client before Phase 5 ships: **delivery fee method** and **discount approval level**

---

## Blockers to raise with the client now

1. **No domain exists.** She said she has none. Registration + DNS propagation needs to happen well before Phase 8, not during it.
2. **Delivery fee method undecided.** Phase 5 needs this. Fixed zones is the default assumption.
3. **Paystack + SMSOnlineGH accounts** need her business details and can't be created on her behalf.
