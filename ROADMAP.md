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

- [x] `Sale`, `SaleItem`, `DiscountRule` models — plus a minimal `Customer` model (phone identity key, `+233XXXXXXXXX` normalization) since `Sale.customer` needs somewhere to point
- [x] Sale service layer: create sale, apply discounts, decrement stock, atomic transaction — `apps/sales/services.py::create_sale()`, `select_for_update()` on the books involved, idempotent on `offline_uuid` (a replay returns the existing sale rather than erroring or double-decrementing — this also sets up Phase 3's batch endpoint to reuse the exact same function)
- [x] `POST /api/sales/` (single sale, online path) — rejects outright on insufficient stock (409) since the device is online and can just check; Phase 3's offline batch path will call the same service with `allow_oversell=True` instead
- [x] Barcode/ISBN lookup endpoint — `GET /api/catalog/lookup/?code=`, resolves ISBN (any formatting) or internal code; `GET /api/catalog/?q=` reused for live title search
- [x] Electron shell: main process, preload, secure IPC, window config — `contextIsolation`/`sandbox` on, `nodeIntegration` off
- [x] POS checkout UI: scan/search panel, running cart, totals, payment buttons
- [x] Payment methods: cash, MoMo, card (recorded only, not gateway-processed)
- [x] Customer capture at checkout (phone, name, email, birthday) — phone required, rest optional-but-prompted
- [x] Receipt generation + print preview — `window.print()`, receipt shows the server's authoritative totals (client never computes its own discount estimate, to avoid a second source of truth for discount logic)
- [x] Device token auth via `safeStorage` — settings screen validates the token against `/api/me/` before storing
- [x] Portal: discount rule config (percent + fixed) — same HTMX slide-over pattern as Phase 1's catalog UI

**Done when:** an attendant can run a full in-store sale end to end, online, and stock drops correctly. ✅ Verified 2026-07-18 — real Electron GUI, screenshotted end to end: connected a device token, live-searched a title, added to cart, captured a customer, completed a cash sale, confirmed stock decremented (28→27) and the customer record was correctly matched by phone (not duplicated) in the database.

**Two bugs caught and fixed during this phase's testing** (not Phase 2 code, but surfaced by it): `rest_framework.authtoken.TokenAuthentication` was the wrong import path from Phase 0 (fixed to `rest_framework.authentication.TokenAuthentication`) — nothing had exercised a DRF view until now. Also, MariaDB strict mode wasn't enabled, which silently truncates instead of rejecting bad data; added `init_command: SET sql_mode='STRICT_TRANS_TABLES'` to `DATABASES.OPTIONS`.

---

## Phase 3 — Offline sync

The hardest phase. Don't rush it.

- [x] SQLite schema in Electron: catalog mirror + sales outbox — via `node:sqlite` (Node 22+ built-in). Deliberately not `better-sqlite3`: that's a native module that has to be rebuilt/matched against Electron's exact ABI per platform; `node:sqlite` needs neither, one less thing to break on the owner's actual machine
- [x] Catalog pull on app start + periodic refresh — every 60s while online, incremental via `?updated_since=`
- [x] Client-side UUID generation for every sale (online and offline alike) — `crypto.randomUUID()` at checkout, before any network call
- [x] Outbox write on every sale, regardless of connectivity — durability first, always; the online path still tries for an immediate authoritative (discount-applied) receipt, falling back to a clearly-marked local-subtotal-only receipt if that fails
- [x] `POST /api/sync/sales/` — batch, idempotent on `offline_uuid`, per-UUID result — reuses Phase 2's `create_sale()` with `allow_oversell=True`; each sale is its own transaction so one bad entry can't roll back the rest of the batch
- [x] Sync worker in Electron: retry with backoff, drain outbox on reconnect — 5s → 60s exponential backoff, resets on the `online` event and after every successful round-trip
- [x] Online/offline indicator in the POS top bar (must be unmissable) — three states now, not just two: red "Offline (n queued)", amber "Syncing (n)", green "Synced"
- [x] **Oversell reconciliation:** accept synced sales that push stock negative, flag them for the owner — new `StockDiscrepancy` model, logged automatically in `create_sale()` whenever `stock_qty` goes negative regardless of which path caused it
- [x] Portal: reconciliation alert view for negative/conflicted stock — list + resolve-with-notes, plus a dashboard banner mirroring the low-stock alert pattern
- [x] Test: pull the network mid-sale, sell 20 items offline, reconnect, verify zero loss and no duplicates — ✅ both as a real Electron GUI test (killed the Django server, sold through the actual app, confirmed durable queueing, confirmed the app survives a reload/restart *while still offline* without blocking the attendant, restarted the server, watched the sync worker auto-drain with no manual action) and as a 20-item batch against `/api/sync/sales/` (20/20 accepted, stock decremented exactly)
- [x] Test: replay the same batch twice, confirm idempotency — ✅ both the 2-sale oversell batch and the 20-sale batch; every replayed entry returned `created: false`, stock and sale counts unchanged

**Done when:** you can run a full book-fair simulation with the network off and lose nothing on reconnect. ✅ Verified 2026-07-18.

**Bugs found and fixed during this phase's testing:**
1. `cover_image` URLs from the API were relative (`/media/...`) — fine for the portal (same origin) but broken in Electron, which loads from `file://`. Fixed by passing `context={'request': request}` to the one serializer instantiation that was missing it (the list endpoint already had this automatically via DRF's generic view).
2. MariaDB strict mode gap from Phase 2 needed no further changes, but is worth re-noting: it's what makes `DecimalField` overflow errors loud instead of silently truncating — exactly the kind of bug offline sync could otherwise hide.
3. **The important one:** `initApp()` originally gated entry to the register screen on a successful `/api/me/` ping. That meant a device that already had a saved token — but happened to reload or restart *while offline* — got stuck on the settings screen, unable to sell anything, which defeats the entire point of this phase. Fixed to enter the register immediately whenever a device config exists, with the attendant-name ping happening in the background and never blocking. Also added a "Back to Register" escape hatch on the settings screen for when it's opened mid-session rather than at first run.
4. The receipt view's height was `100%` against a parent with no defined height, which resolves to nothing — combined with `body { overflow: hidden }`, this meant the pending-sync banner pushing the receipt taller than the window made the "New Transaction"/"Print Receipt" buttons genuinely unreachable (clipped, not scrollable). Fixed by making `#view-app` a proper `100vh` flex column so both the register and receipt views get a real height to scroll within.

---

## Phase 4 — Owner portal & reporting

- [x] Owner auth, session handling, role scaffolding (single owner now, extensible later) — real email+password login at `/portal/login/`, retiring the Phase 0 admin-login bridge; `LOGIN_URL` now points at it
- [x] Dashboard: today's sales, week's orders, profit margin, low-stock count — profit margin scoped to month-to-date, 7-day trend chart added alongside
- [x] Sales report: daily/weekly/monthly, with date range picker
- [x] Profit margin per book report (`selling_price - cost_price` × qty sold) — actually `(unit_price - unit_cost_price) × qty - line_discount`; see the `SaleItem.unit_cost_price` note below
- [x] Stock levels report — plus cost/retail inventory value totals, low-stock and out-of-stock counts
- [x] `Expense` model + entry form — HTMX slide-over, same pattern as catalog/discounts
- [x] **Business vs. personal withdrawal toggle** — `is_personal_withdrawal`; verified the expense report actually excludes it (GHS 800 business rent counted, GHS 300 personal draw isolated and excluded), not just that the field exists
- [x] Expense report with the business/personal split visible — separate totals + by-category breakdown, business-only
- [x] Chart.js integration for trends — dashboard 7-day trend, sales report period chart
- [x] CSV export on each report — all four (`?format=csv`)

**Done when:** the owner can answer "did I make money this month, and is that number honest about my personal withdrawals?" without calling you. ✅ Verified 2026-07-18 — dashboard, all four reports, and CSV export all confirmed against real data through the actual HTTP endpoints (not just unit-level).

**One schema addition beyond CLAUDE.md's original spec:** added `SaleItem.unit_cost_price`, a snapshot of `Book.cost_price` at sale time, populated by `create_sale()` alongside the existing `unit_price` snapshot. CLAUDE.md §9 already establishes the principle ("all prices on SaleItem are snapshots, not FK lookups to live price") — the original field list just didn't extend it to cost. Without this, editing a book's cost price today would silently rewrite last month's profit reports. Existing pre-Phase-4 `SaleItem` rows were backfilled from each book's current `cost_price` (the best available approximation for data that predates the field).

**A significant bug found and fixed by this phase's testing:** MySQL/MariaDB's timezone tables aren't loaded on this dev machine — confirmed via `mysql.time_zone_name` being empty — which makes every `__date`/`TruncDate`/`TruncWeek`/`TruncMonth` lookup on a `DateTimeField` silently return `NULL` (Django delegates the conversion to `CONVERT_TZ`, which needs that data to do anything). This would have made every report and every dashboard stat show zero, permanently, with no error — exactly the kind of failure that's invisible until someone asks "why does this always say zero?" Fixed by filtering with explicit UTC datetime bounds computed in Python (`apps/reports/utils.py::range_bounds_utc`) and forcing `tzinfo=utc` on every `Trunc*` call, instead of relying on database-side timezone conversion at all. This isn't a workaround specific to this machine — cPanel shared hosting frequently doesn't have timezone tables loaded either, so the fix is the actually-correct approach for this project, not a local patch. (Africa/Accra being UTC+0 with no DST means the UTC-boundary math is exactly right, not an approximation.)

---

## Phase 5 — Storefront & online orders

- [x] Public book listing: grid, pagination, category filters, search
- [x] Book detail page — **server-rendered, with proper meta tags and structured data** — JSON-LD `Book`/`Offer` schema, built server-side with `json.dumps` (not hand-rolled in the template) to avoid quoting bugs
- [x] Cart (session-based, no login required)
- [x] Checkout: three-way fulfillment toggle — delivery / pickup / rider delivery (Yango/Bolt/Uber)
- [x] `DeliveryPricingRule` abstraction — fixed zones implemented and working (Accra Central/Greater Accra/Outside Accra tested); distance-based and manual modeled but not implemented, per the original open item. **Rider delivery bypasses this entirely** — verified `fee=0` end to end
- [x] Customer capture at online checkout (phone, name, email, birthday) — **email is required here specifically** (not just prompted), because Paystack's initialize call requires one; noted inline in the form, not a silent deviation from CLAUDE.md's general "optional-but-prompted"
- [x] Paystack: initialize transaction, inline/redirect checkout — amount charged is books only; rider fare is never part of this transaction
- [x] Paystack webhook handler + verify-on-return (**both**) — both call the same `finalize_paid_sale()`, idempotent regardless of which fires first or if both do
- [x] `PaymentTransaction` records with full raw payload stored
- [x] Order confirmation page — rider-delivery orders show "we're booking your ride now," not an ETA. (Confirmation **email/SMS** not sent yet — SMSOnlineGH integration is Phase 6; the confirmation page itself is live)
- [x] Customer "confirm receipt" flow
- [x] `Review` model + post-purchase rating/comment form
- [x] Portal: online orders list + detail drawer
- [x] Portal: **rider-delivery booking queue** — dashboard banner + dedicated queue page + mark-booked action, verified the count updates correctly after booking
- [x] Stock decrements on paid online orders, visible instantly in the POS — reuses the exact same `create_sale`-family stock logic as Phases 2/3, not a parallel implementation

**Done when:** a real customer can buy a book online, pay by MoMo, confirm receipt, and leave a review — and the shop's stock reflects it immediately. A customer choosing rider delivery instead sees no delivery fee, and their order shows up in the portal's booking queue until the attendant handles it. ✅ Verified 2026-07-18 — full checkout→payment→fulfillment→review loop tested for both DELIVERY (zone fee applied correctly) and RIDER_DELIVERY (zero fee, booking queue, dashboard banner, mark-booked). Paystack `initialize` was verified against the **real** Paystack API (reached their servers, got a real structured rejection for the placeholder key — confirms the integration code itself is correct); webhook signature verification and `finalize_paid_sale()` idempotency were verified with a correctly HMAC-signed simulated payload. **Live payment could not be tested — no real Paystack account exists yet** (docs/SRS.md §8, client action item).

**Two schema additions beyond the original spec, both load-bearing:**
1. `Book.slug` — SEO-friendly storefront URLs (WEB-08 needs more than `/books/47/`). Title-derived, id-suffixed so duplicate titles never collide; backfilled for existing rows.
2. Two-phase sale creation for online orders (`create_pending_online_sale()` + `finalize_paid_sale()` in `apps/sales/services.py`), alongside the existing single-phase `create_sale()`. Payment is asynchronous online (redirect to Paystack, webhook arrives later) — stock can't decrement at checkout the way it does when cash changes hands at the POS register. The pending sale reuses `offline_uuid` as the Paystack reference, so the existing idempotency machinery from Phase 3 covers the webhook/verify race for free.

**Bugs found and fixed during this phase's testing (all caught before being reported, not after):**
1. The checkout form's `address` field was accidentally rendered twice (once under the delivery block, once under the rider block) — same `name`/`id` in two places in the DOM. Only one value would have actually submitted, and which one was undefined. Fixed to a single field with a JS-driven label/visibility toggle.
2. The star-rating CSS was missing `flex-direction: row-reverse`, which the checked-sibling-highlighting trick depends on — without it, selecting "3 stars" wouldn't visually highlight stars 1–3 correctly.
3. `Book.slug`'s first migration used `max_length=280` on a unique field — MariaDB warns this can exceed the index prefix limit depending on server config. Corrected to 255 via a proper follow-up migration rather than editing the already-applied one.

---

## Phase 6 — Customers, loyalty & SMS

- [x] Customer list in the portal with purchase history — search by name/phone/email, lifetime order count + spend (PAID sales only), per-customer detail page with full order history and loyalty ledger
- [x] Phone normalization + dedup (`+233XXXXXXXXX`) — merge existing duplicates — `manage.py dedupe_customers [--dry-run]`; `Customer.phone` is already DB-unique so true duplicates can only arise from data that bypassed `save()` (e.g. a future bulk import from the old POS), but the tool is real and reusable, not a one-off script
- [x] `LoyaltyTransaction` model + points accrual on sale — earns on `subtotal - discount_amount` (post-discount book value, not delivery fee), wired into both `create_sale()` (POS/offline, already-PAID) and `finalize_paid_sale()` (online, once payment confirms)
- [x] Loyalty rules config in the portal (owner-defined thresholds/rewards) — new `LoyaltyProgram` model (points/GHS earn rate, GHS/point redeem rate, minimum redeemable), portal settings form at `portal:loyalty_settings`, seeded with a sensible default via data migration so the feature isn't a no-op out of the box
- [x] Reward redemption at POS checkout — phone-blur balance lookup (`GET /api/customers/lookup/`) shows points + GHS value, a redeem-points field folds into the sale's existing `discount_amount`; the redemption amount is only previewed client-side, same "server is the only source of truth" principle the existing discount math already followed
- [x] SMSOnlineGH client wrapper + `SmsLog` — `apps/messaging/sms_client.py`, one function (`send_sms`), one recipient per call so per-customer send results are never ambiguous. **Unverified against a live account** — SMSOnlineGH docs weren't available to check the wire format against, and `SMSONLINEGH_API_KEY` is still an empty placeholder (client hasn't set up the account — same situation Paystack was in before Phase 5). Re-check the endpoint/payload shape once real credentials exist.
- [x] `SmsCampaign` model + composer UI with audience selector — audience is `ALL` or `BIRTHDAY_TODAY` (a full segment-builder DSL wasn't asked for); HTMX slide-over composer matches the discounts/catalog pattern, shows a live recipient count, "Send Now" queues immediately (`status=SCHEDULED, scheduled_for=now`) for the next cron tick — the portal itself never calls SMSOnlineGH (CLAUDE.md §8)
- [x] Management command: send scheduled campaigns — `send_sms_campaigns`, picks up `SCHEDULED` campaigns that are due
- [x] Management command: daily birthday greetings — `send_birthday_sms`, wording lives in `settings.BIRTHDAY_SMS_MESSAGE` (not `.env` — it's copy, not a secret); dedup-guarded so a double cron fire or manual re-run can't double-text someone
- [x] cPanel cron entries for both commands — documented in new `docs/deployment.md`, including the "always call `.venv`'s python directly, no activate step for cron" note and why neither command errors out before real SMSOnlineGH credentials exist (warns and no-ops instead)
- [x] Opt-out handling and an unsubscribe flag on `Customer` — `sms_opt_out` field, portal toggle on the customer detail page, plus a public signed-token self-service unsubscribe page (`/unsubscribe/<token>/`, not auto-injected into every SMS body since message wording is the owner's and a full URL costs an extra segment — see `docs/deployment.md`)

**Done when:** the owner can send a promo blast and birthday SMS go out automatically, replacing the WhatsApp broadcasts she's been paying for. ✅ Verified 2026-07-18 — accrual, redemption math (including the exact GHS discount from a point conversion), the portal customer/loyalty/campaign flows, the unsubscribe flow (valid + invalid token), and the dedupe command were all exercised against the real database via Django's test client and shell, not just unit-level. **The POS redemption UI itself could not be visually verified this pass** — no browser/window-automation tool was available in this session, so it was checked statically instead (JS syntax, and every DOM id the new JS references cross-checked one-for-one against `index.html`); worth a real click-through before relying on it at the register.

**A correctness bug caught during this phase's own design, before it shipped:** the first version of redemption validation enforced `min_redeem_points` even on the offline-sync path (`allow_oversell=True`). Since that check depends on a fixed rule rather than a moving balance, a sale synced with a too-small redemption would have failed identically on every retry — permanently stuck in the local outbox after the attendant had already told the customer it went through, silently, forever. Fixed by having the offline path clamp/skip the redemption instead of ever rejecting the sale (`apps/customers/services.py::resolve_redemption`), consistent with CLAUDE.md §7's stock-oversell principle: a sale that already happened must never be rejected, even for a reason that's real.

**A pre-existing bug found and fixed along the way (Phase 5, not Phase 6):** `order_confirmation.html` read `item.title` on a `SaleItem`, which has no such attribute — book titles on every order confirmation page have rendered blank since Phase 5 (Django templates swallow the `AttributeError` instead of raising). Fixed to `item.book.title`, matching `cart.html`/`checkout.html`/the portal's order detail, which all already did this correctly.

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
