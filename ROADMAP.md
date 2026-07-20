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

- [x] `Sale.channel = JUMIA` path + manual order entry in the portal — `create_sale()` reused as-is (channel/payment_method/external_ref were already parameters or a one-line addition), so Jumia sales get the exact same discount/loyalty/stock logic as every other channel for free, not a parallel implementation. Multi-book entry via an Alpine-driven repeatable row form (`portal/marketplace/_form.html`) — the portal's first real use of Alpine.js, which CLAUDE.md named as part of the stack from day one but nothing had needed yet.
- [x] `external_ref` capture for Jumia order references — the field already existed on `Sale` since Phase 2 (CLAUDE.md's original data model anticipated this); Phase 7 is what actually populates and surfaces it.
- [x] Return/reversal flow: restore stock, set `returned_at`, exclude from revenue — `apps/sales/services.py::return_sale()`, idempotent (returning an already-returned sale is a no-op, not a double stock credit). "Exclude from revenue" needed zero reports-side code: `sales_report`/`profit_report` already filtered on `status=Sale.Status.COMPLETED`, so flipping status to `RETURNED` removes it from every revenue number automatically.
- [x] Reports segmented by channel (in-store / online / Jumia) — the sales report now shows a per-channel totals strip (always all channels) plus an optional `?channel=` filter that scopes the existing period/trend table to just one, so the owner can see both "how much from each channel" and "Jumia's trend over time" without two different reports.
- [x] Portal: marketplace orders tab — list (all Jumia sales, "Record Order" panel), detail (line items, status, return action)

**Done when:** Jumia sales and their frequent returns are tracked without polluting in-house sales figures. ✅ Verified 2026-07-18 — manual multi-item entry, stock decrement, the oversell path (a Jumia sale for more than Book Pharm's on-hand stock still succeeds and correctly raises a `StockDiscrepancy`, reusing Phase 3's existing reconciliation mechanism rather than inventing a parallel one), the return flow (stock restoration, idempotency on a repeat return, and confirmed exclusion from the revenue queryset), and the channel-filtered report were all exercised against the real database via Django's test client and shell.

**A design choice worth noting:** manual Jumia entry uses `allow_oversell=True` unconditionally, not just as a fallback. Book Pharm's stock count and the owner's Jumia listing aren't necessarily kept in perfect lockstep, so "Jumia already sold something we show 0 of" is a real, expected scenario — not just a race condition. Rejecting the recording of a sale that Jumia confirms already happened would contradict CLAUDE.md §7's core stance on oversells; a mismatch here gets the same reconciliation flag an offline-sync oversell would.

---

## Phase 7.5 — Staff accounts (owner request, 2026-07-19)

Not in the original phase plan — CLAUDE.md §4 had explicitly deferred staff accounts ("design for it, don't build it"). The owner asked for it directly; CLAUDE.md is updated to match (§4, §6, §7 §5's repo-layout comment).

- [x] Three access tiers: Superuser (developer/Django-admin, never listed in the portal), Owner (full portal access + user management), Attendant (desktop POS only) — `User.Role` renamed `STAFF`→`ATTENDANT` (no data migration needed; no `STAFF` rows existed yet)
- [x] Portal login rejects `role=ATTENDANT` with a clear message; `is_superuser=True` accounts are excluded at the queryset level everywhere in user management, not just hidden in a template — a real access boundary, not a display filter
- [x] Portal: user management (`portal:user_list`) — create Owner/Attendant accounts with a password set directly (no email-invite flow; not warranted at this scale), revoke/restore access (`is_active` toggle, not delete — preserves `Sale.attendant` history)
- [x] Portal: Owner can ring up an in-store sale directly (`portal:register_create`) — same `create_sale()` path the desktop POS uses, `allow_oversell=False` (matching the desktop's own connected-path reasoning: someone's live at a screen and can just check stock)
- [x] Desktop: sign-in is now email+password (per attendant), not a pre-provisioned device token — `POST /api/auth/login/` returns that user's DRF token the same way the app has always authenticated everything else, just obtained differently. Token still lives in `safeStorage`; logging out clears only the stored credentials, never the local outbox (CLAUDE.md §7 — a sale already rung up must never be lost, including by a shift change)
- [x] Desktop: "My Day" tab — today's sales for whoever is signed in, past receipts re-openable. Merges the server's `/api/sales/mine/` (authoritative, cross-device) with the local outbox (works offline, and is the *only* source for a sale that hasn't synced yet); falls back to local-only with a visible "offline view" note if the server's unreachable
- [x] Desktop: sync indicator gained a visible pending-count badge on top of the existing "Offline (n queued)"/"Syncing (n)" label text — the label is meant to be read, the badge is meant to register mid-sale without stopping to read it

**Done when:** the owner can create an attendant account from the portal, that attendant can sign into the desktop POS with it, ring up sales attributed to them, and see their own day's sales; a revoked account can no longer sign in anywhere. ✅ Verified 2026-07-19 — attendant creation, portal-login rejection, desktop-login acceptance (real HTTP round-trip against the login endpoint, not just the view function), superuser exclusion (confirmed at the queryset level), and portal-created in-store sales (stock decrement, receipt) were all exercised against the real database. **The desktop UI itself (My Day tab, sign-in screen) could not be visually verified this pass** — no browser/window-automation tool was available in this session — so it was checked statically: every DOM id the new JS references cross-checked one-for-one against `index.html` (found clean), plus the same check repeated for the storefront JS changes made in the same pass.

**A bug found and fixed while building this (storefront, not this phase's own code):** the mobile topbar's search-icon toggle was visibly offset above the cart icon — traced to a leftover `transform: translateY(-50%)` surviving a `position: absolute` → `static` change from an earlier session's mobile-search-expand work. `transform` applies regardless of `position`; only the desktop rule's `top: 50%` needed that translate to correct for it, and nothing reset it for the mobile override. Fixed by resetting `transform: none` alongside the position change.

**A second bug, reported as "orders in Electron aren't being sent to portal" (2026-07-20):** they were — verified end-to-end again here, login → `POST /api/sales/` → row saved with `channel=IN_STORE` — the transport was never broken. The actual problem: nothing in the portal ever displayed an in-store sale. `portal:order_list` has only ever queried `channel=ONLINE` (Phase 5, by original design — it's the storefront-orders page); `register_views.py` had a create view and a single-receipt-by-pk view but no list of its own. Reports/dashboard were unaffected (already unfiltered by channel). Fixed by adding `portal:register_list` (`/portal/register/sales/`, nav label "In-Store Sales") covering both sources of an IN_STORE sale — the desktop POS and the portal's own register — since both write through the same `create_sale()` into the same table. Same per-channel-dedicated-page pattern Marketplace already uses, rather than retrofitting Orders to handle fulfillment-shaped and non-fulfillment-shaped rows in one table. Also added a manual "Sync now" button next to the desktop sync pill (owner request) as a contingency alongside the automatic backoff retry.

---

## Phase 7.6 — Distance-based delivery pricing & rider dispatch (owner request, 2026-07-20)

Resolves CLAUDE.md §4's old "delivery fee method" open item. Also bakes in the Google Maps integration WISDOM.md #5 had been waiting on (key was supplied mid-session).

- [x] `ShopLocation` (singleton) + `DeliveryPricingRule.radius_km` (replacing the never-implemented `per_km_rate`/`base_fee` linear-formula fields — no data loss, nothing had ever populated them) — `apps/fulfillment/distance.py` (haversine) + `services.py::resolve_distance_fee()` picks the smallest configured ring a point falls inside
- [x] Portal: new "Delivery" nav section (`portal:delivery_settings`) — shop location via the same Places Autocomplete pattern as checkout, radius-tier CRUD (create/edit/toggle-active, same HTMX panel pattern as Discounts)
- [x] Checkout: address field gained live Places Autocomplete + a "use my current location" button (geolocation → Geocoding API reverse-lookup), both no-ops with a plain text field when `GOOGLE_MAPS_API_KEY` is blank. When any `DISTANCE_BASED` rule is active, the old fixed-zone dropdown is replaced by a live AJAX fee estimate (`storefront:delivery_fee_estimate`) as soon as a point is picked; a point beyond every configured ring is rejected server-side in `CheckoutForm.clean()` with a message pointing at Pickup/Rider Delivery — never silently capped or waved through. No `DISTANCE_BASED` rules active → checkout behaves exactly as before (fixed-zone dropdown), so this shipped with zero behavior change until the owner actually configures a shop location + rings
- [x] "View on Map" links (plain Maps URL scheme, no API key needed) added everywhere an address is *displayed*, not just where it's entered: rider queue, online order detail, customer's own order confirmation
- [x] Rider dispatch (standard Delivery only, not Rider Delivery/Yango-Bolt-Uber): phone number input on the order detail page → SMS with order details + a Google Maps link, sent **synchronously** — a deliberate, scoped exception to CLAUDE.md §8's "never send SMS inline" rule, made after confirming with the owner specifically because this is one bounded call (not a bulk loop) and the existing 15-minute campaign cron cadence would make same-day dispatch impractical

**Done when:** the owner can set the shop's location and a few radius/price rings from the portal, a storefront customer picking a delivery address inside those rings sees a live fee estimate and gets charged correctly at checkout, one outside every ring is blocked with a clear message, and the attendant can text a rider the order + map link on demand. ✅ Verified against the real database and a live server: haversine distance + tier resolution (in-range, ring-boundary, and out-of-range cases), full checkout POST end-to-end (Sale/Fulfillment created with the correct fee and stored coordinates), the fixed-zone fallback when no distance rules are active, the delivery-settings portal screens (shop location save, rule create/edit/toggle), and rider SMS dispatch including its failure path (no `SMSONLINEGH_API_KEY` configured yet — fails gracefully with a message, does not mark the fulfillment as sent). The actual SMS send and the Places Autocomplete/map UI interactions themselves could not be visually verified — no live SMSOnlineGH credentials and no browser/window-automation tool available this session — so those two pieces are unverified beyond code review and the request-response contract each depends on.

**A bug found and fixed immediately after (owner report, 2026-07-20):** the checkout address field is shared between Delivery and Rider Delivery (same input, same lat/lng capture), and the live fee-estimate preview didn't check which fulfillment type was actually selected — so picking an address while "Yango / Bolt / Uber" was chosen could show an "Estimated delivery fee" that flatly contradicted the "No delivery fee" note right above it, and CLAUDE.md §4's explicit rule that Rider Delivery never has a calculated fee. Fixed by gating both the trigger (on fulfillment-type change) and `updateFeePreview()` itself (in case autocomplete/geolocation fires while Rider Delivery is already selected) on `fulfillment_type === 'DELIVERY'`. The actual charged fee was never wrong — `checkout()`'s server-side calculation was already correctly scoped to `DELIVERY` — this was a client-side-only display bug.

---

## Phase 7.7 — Portal polish pass (owner request, 2026-07-20)

A batch of portal UX/ops items, mostly independent of each other:

- [x] In-store sales (`portal:register_list`) gained date-range + payment-method filters, following the same `range_bounds_utc` pattern reports already use
- [x] Every portal table that wasn't already paginated now is — users, discounts, SMS campaigns, delivery pricing rules, reconciliation's resolved history, a customer's purchase/loyalty history, and the sales/profit/stock reports (report `<tfoot>` totals still aggregate the *full* date range, not just the visible page — computed separately, before pagination slices the display rows). New shared `templates/portal/_pagination.html` partial (supports both plain-link and HTMX-panel pages, and a `page_param` override for pages with more than one independently-paginated table) — reuse it for any new list view rather than hand-rolling pagination again. Deliberately left unpaginated: the reconciliation unresolved list and the rider delivery queue — both are action lists ("needs attention"), not browsable history, and paging an alert risks one silently sitting unseen on page 2
- [x] Portal topbar user block became a click-open dropdown (Alpine, matching the rest of the portal's existing HTMX+Alpine mix) showing full profile detail, with a "Change Password" link and Log Out (kept in the sidebar foot too, not moved — the dropdown copy matters more once the sidebar's behind a hamburger on mobile, see below)
- [x] Password management: Owner self-service change (`portal:change_password`, Django's built-in `PasswordChangeForm` + `update_session_auth_hash` so changing your own password doesn't silently log you out) and Owner-resets-Attendant (`portal:user_reset_password`, "Reset Password" button next to Attendant rows only — Owner-to-Owner resets weren't part of this request and raise a different permission question, so not built)
- [x] Portal is now mobile-responsive — previously the sidebar just went `position: static` full-width above the content on narrow screens, effectively a wall of 13 links before any actual page content. Now an off-canvas drawer (hamburger toggle in the topbar, slide-in sidebar, backdrop, closes on nav) below 900px; topbar itself goes icon-only (New Sale, user menu) to fit
- [x] Portal login page gained a "Back to website" link

**Done when:** every item above works standalone; verified live against the real database — filters, every newly-paginated page (200, no errors), the dropdown/password-change/password-reset flows end-to-end (including confirming a self password change doesn't end the session, and a reset password actually authenticates), and the mobile drawer's markup/Alpine bindings render correctly. The drawer's actual slide animation and touch interaction couldn't be visually verified — no browser tool available this session.

---

## Phase 7.8 — Logo, portal book search, price history (owner request, 2026-07-20)

- [x] Logo: a hand-drawn SVG open-book mark (`backend/static/img/logo.svg`, duplicated at `desktop/renderer/logo.svg` since Electron doesn't share Django's static serving) in the existing burgundy/gold palette — icon-only by design, paired with the existing "Book Pharm" text wherever it appears (storefront topbar, portal sidebar + login, desktop sign-in + topbar) rather than baking the wordmark into the image itself, so each surface keeps using its own already-loaded font/sizing
- [x] Portal sidebar: brand is now the logo + text (was plain text), a faint divider below it, and the 13 nav items are grouped under section labels (Sales / Catalog / Customers / Insights / Admin) instead of one flat list
- [x] Portal topbar search — books only, submits to the Inventory list's existing `?q=` filter (title/author/ISBN/internal code) rather than a new parallel search path. Same expand-on-tap mechanism as the storefront's mobile search, but full-width on desktop (not the storefront's fixed max-width — no nav-links cluster competing for the row here)
- [x] `PriceChangeLog` (`apps/catalog`) — one row per `cost_price`/`selling_price` edit. Written by `apps/catalog/services.py::log_price_changes()` from the *view* layer (portal `book_update`, and `BookAdmin.save_model()` for admin edits), not from `Book.save()` itself — detecting "did this change" needs the pre-save value, which the view already has to capture before calling `form.save()`. Never written on creation, only edits. Empty for every book until its price is next changed post-deploy — there's no retroactive data to backfill
- [x] Book history page (`portal:book_history`, reached via a "View" button on the Inventory list) — three independently-paginated tables: price changes, every sale the book's been part of across all channels (linking out to each channel's own detail page), and stock adjustments (restocks/corrections/damage)

**A bug caught before it shipped:** the history page's price-changed-by / adjusted-by columns used the same chained-`default`-filter pattern that crashed earlier this session (Phase 7.5's "orders not showing" investigation) — both `changed_by` and `adjusted_by` are nullable FKs, and Django's `default` filter eagerly resolves its fallback argument even when unused, so `{{ x.changed_by.full_name|default:x.changed_by.email }}` throws the moment `changed_by` is None rather than falling through. Fixed with `{% if %}` guards before it ever ran against real data.

**Done when:** the logo shows correctly on all three apps, the portal sidebar reads as grouped sections with a real brand mark, searching a book title/author/ISBN from the portal topbar (any width) lands on a filtered Inventory list, and every book's "View" button shows a real, correctly-paginated history. ✅ Verified live: search (including a re-check after an HTML-escaping false alarm in the ampersand-titled test book), the View button and all three history tables, migration applied cleanly, and the null-FK guard against a real null-`adjusted_by`/`changed_by` row. Not verified: the actual expand animation and logo rendering in a real browser/Electron window — no browser or window-automation tool available this session; the SVG itself *was* rendered to PNG and visually inspected before deployment (`cairosvg`, dev-only, not added to `requirements.txt`).

---

## Phase 7.9 — Desktop: multi-order register, MoMo-via-Paystack, printer selection (owner request, 2026-07-20)

The largest single desktop change since Phase 3 — six related items, all touching `desktop/renderer/`.

- [x] Printer selection: `main.js` gained `webContents.getPrintersAsync()`/`print({silent, deviceName})` IPC handlers (main-process-only APIs, unreachable from the sandboxed renderer directly), exposed via `window.printerApi`. Settings screen lists real system printers in a `<select>`; the choice is saved to device config and used for every receipt print via `window.printerApi.print()`, falling back to the interactive `window.print()` dialog only if the IPC path is unavailable or itself fails — not merely because no printer was explicitly chosen (an empty selection still resolves to the system default, silently)
- [x] Login/Settings split: `#view-login` (API URL + email + password, unauthenticated only) and `#view-settings` (printer choice + Log Out, reachable only while signed in) are now two separate screens instead of one conditionally-relabeled form. Logging out prefills the API URL for the next sign-in (convenience — it's the shop's server address, not a secret) but never touches the local outbox/catalog mirror (CLAUDE.md §7 still applies to a shift change)
- [x] My Day: gained a date picker (any past full day, capped at today — "full days" means the filter granularity is always a whole calendar day, not that today is excluded) and a real `<table>` replacing the old div-row list, with per-row View/Print actions and card-styled summary stats. Reuses the existing `GET /api/sales/mine/?date=` param, which already existed server-side (`MySalesView`) before this session — only the desktop UI to drive it was missing
- [x] Multi-order tabs: the register now holds an array of independent orders (cart, customer fields, loyalty preview, MoMo state each), switchable via a tab strip, so a second customer arriving mid-sale never overwrites the first's scanned items. Exactly one order always exists — closing the last remaining tab resets it in place rather than leaving zero. Every cart mutation routes through `activeOrder().cart`/`order.cart` directly; no module-level `cart` alias exists anywhere, specifically to avoid the reassignment-divergence bug (`cart = cart.filter(...)` silently orphaning the order object) reasoned through before writing any of this code
- [x] MoMo via Paystack: `pay-momo` sends a direct mobile money charge (`POST /api/sales/momo-charge/`, new — creates the sale as PENDING, stock untouched until confirmed per owner decision) and shows a waiting panel; a single global 5-second poll (not per-order timers) checks every order with `momoState==='pending'` via `GET /api/payments/<uuid>/status/`, the same call the panel's manual "Check Status" button uses. A charge that fails or times out stays as a PENDING record for the owner to notice (owner decision — not silently discarded), with a "Discard & Try Again" cancel path (`POST /api/sales/<uuid>/cancel/`). Resolving in the background (order tab not currently active) closes that tab quietly rather than yanking the attendant to a different order's receipt — no toast system exists in this app to notify otherwise
- [x] Payments page: new third topbar tab, `GET /api/payments/in-store/` (new — every MoMo attempt on any device, capped at 200 most recent, not attendant-scoped since a charge one attendant started may need another to notice), with a per-row "Check Status" button for anything still PENDING

**Done when:** an attendant can hold two customers' carts open at once without data loss, take a MoMo payment that confirms automatically in the background while they serve someone else, print a receipt to a chosen printer without an interrupting dialog, and both they and the owner can see a day's sales or all MoMo payment attempts in a real table. ✅ Verified as far as this session's tools allow: every backend piece (`charge_mobile_money`, the pending-sale service functions, all four new endpoints) exercised live against the real Paystack API using dev placeholder credentials — enough to reach Paystack's servers and catch two real bugs (below), not enough to complete an actual charge (no live merchant account yet, same gap Phase 5 already flagged). All new field names used by the desktop JS were cross-checked against the actual DRF serializers rather than assumed. The desktop half was verified statically only — `node --check` on all three JS files, CSS brace-balance, and a full two-way ID cross-reference between `index.html` and `app.js` (every `$()` call resolves to a real element, every element is referenced) — **no browser/window-automation tool was available this session, so the multi-order tab switching, the MoMo waiting-panel UI, and the printer picker have not been visually clicked through.**

**Bugs found and fixed before this shipped (all caught by review/cross-checking, not live testing):**
1. Paystack's Charge API rejected the synthetic POS email's `.local` TLD outright (`Invalid Email Address Passed`) — confirmed against the real API, not assumed; switched to `.com`.
2. A MoMo charge that failed before Paystack even accepted it left no `PaymentTransaction` row at all — invisible on the Payments page, defeating its purpose. Fixed by recording a `FAILED` transaction in the exception path too; re-verified live (Payments list went from `count: 0` to `count: 1` with the correct failed-attempt row).
3. The new `#order-tabs` strip, added as the first child of `.register`, would have rendered as a fourth narrow flex column beside search/cart/summary instead of a strip above them — `.register` was still `display: flex` with no `flex-direction` set. Caught before ever running, by reasoning through the existing CSS rather than assuming a new element would lay out as intended; fixed by switching `.register` to a CSS grid with named areas, which lets the tabs strip span full width above the three panels without needing an extra wrapper element in the HTML.
4. `printCurrentReceipt()` only used the silent IPC print path when a specific printer had been chosen, falling back to the interactive `window.print()` dialog otherwise — exactly the interruption the printer-IPC feature exists to avoid, for the common case of a device left on "System default." Caught by re-reading `main.js`'s own printer-handler comment ("no OS dialog interrupting a busy checkout") against the code just written. Fixed: the IPC path is now always tried first, with `deviceName: undefined` correctly resolving to the system default on Electron's side, still silently.
5. The topbar's manual "Sync now" button (`#sync-now-btn`, pre-existing element) had no click handler at all in the rewritten `app.js` — caught by the same HTML↔JS ID cross-reference used to verify everything else, not by a user report.

---

## Phase 7.10 — Desktop sales always allow negative stock (owner request, 2026-07-20)

A scope correction to Phase 2's original design, not a new feature: `POST /api/sales/` (desktop cash/card) and `POST /api/sales/momo-charge/` (desktop MoMo) both rejected a sale outright on insufficient stock — reasonable-sounding in the abstract ("the device is online, it can just check"), wrong in practice, since it means telling a customer standing at the counter with a physical book in hand "sorry, the system says we're out" over what's usually just a stock-count mismatch, not a real absence of the book.

- [x] `create_sale()` calls from `SaleCreateView` now pass `allow_oversell=True`; `create_pending_instore_sale()` (the MoMo pending-sale path) now hardcodes it internally rather than exposing it as a parameter — there's only ever one caller and it should never need to be `False`
- [x] `InsufficientStockError` can no longer be raised from either call site — the now-dead `except` blocks and the now-unused import were removed rather than left as defensive dead code
- [x] Deliberately **not** extended to `create_pending_online_sale()` (storefront checkout — no attendant there to smooth over a surprise, per its own existing docstring reasoning) or the portal's own `register_create` (owner ringing up a sale from a keyboard, not a counter — its docstring previously justified itself by pointing at "the desktop app's own connected path," which is exactly the reasoning this change invalidates, so it was reworded to stand on its own)
- [x] No new reconciliation mechanism needed: `_decrement_stock_for_item()` already flags any resulting negative `stock_qty` as a `StockDiscrepancy` regardless of which caller decremented it, so extending oversell-allowance to these two call sites gets the existing owner-facing alert for free

**Done when:** an attendant can complete a cash/card or MoMo sale from the desktop app for more than the recorded stock, without an error, and the owner sees it flagged for reconciliation same as an offline-sync oversell. ✅ Verified live against the real dev database via Django's test `Client` hitting the actual URL patterns (not just the service function directly): a cash sale for 77 of a book with 27 in stock returned **201** (previously would have been 409), left `stock_qty` at **-50**, and created an **unresolved `StockDiscrepancy`** row automatically; a MoMo charge request for well beyond an already-negative book's stock also returned **201** and created the pending sale without being blocked.

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
