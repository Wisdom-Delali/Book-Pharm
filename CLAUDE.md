# Book Pharm — POS & E-Commerce System

Context file for Claude Code. Read this before making changes.

---

## 1. What this is

A point-of-sale and e-commerce system for **Book Pharm**, a bookshop in Ghana. It replaces the owner's current POS, which is unreliable and locked her into a contract without solving her problems.

Three components, **one shared database**:

| Component | Who uses it | Purpose |
|---|---|---|
| **Storefront** (`apps/storefront`) | Public customers | Browse and buy books online |
| **Owner portal** (`apps/portal`) | Business owner only | Inventory, reports, expenses, marketing |
| **Desktop POS** (`desktop/`) | Shop attendant | Fast in-store checkout, works offline |

The critical constraint: **a sale or stock change in any component must be immediately visible in the others.** The owner's previous online store failed partly because it was a disconnected system requiring manual uploads. Never introduce a second source of truth.

---

## 2. Stack

- **Backend:** Django + Django REST Framework
- **Database:** MySQL (cPanel shared hosting)
- **Storefront + Portal:** Django templates + HTMX + Alpine.js. Chart.js for portal charts.
- **Desktop POS:** Electron, consuming the REST API, with local SQLite for offline sales
- **Payments:** Paystack (covers MTN MoMo, Telecel/Vodafone Cash, card, bank transfer in Ghana)
- **SMS:** SMSOnlineGH

**Why server-rendered, not React:** the storefront needs SEO (individual book pages must index on Google), and the deployment target is cPanel shared hosting. One Django deploy is far less fragile here than a Django API plus separate static SPA builds. The REST API still exists — Electron is its primary consumer, and it leaves the door open for a mobile app later.

---

## 3. Hosting reality (cPanel) — read before designing anything

This runs on **cPanel shared hosting**, not a VPS. That imposes hard constraints:

- **No long-running processes.** No Celery, no Redis workers, no daemons. Scheduled work (birthday SMS, campaign sends) runs via **cPanel cron jobs calling Django management commands**.
- **No WebSockets.** If a screen needs live updates, poll with HTMX (`hx-trigger="every 30s"`).
- **Django runs under Passenger** via cPanel's "Setup Python App". WSGI entry point, no ASGI.
- **Static and media files** are served from `public_html`; run `collectstatic` on deploy. Book cover uploads go to a media directory on disk.
- Keep dependencies lean — some packages needing system-level compilation won't install on shared hosting.

If a proposed feature needs background workers or sockets, flag it rather than assuming infrastructure that isn't there.

---

## 4. Confirmed requirements

These come from the client's completed questionnaire. **They are decided — don't re-litigate them in code.**

- **Discounts:** both percentage and fixed-amount, configured centrally by the owner
- **Stock entry:** ISBN/barcode scanning *and* manual entry. Books without an ISBN get a system-generated internal code
- **Low stock:** the owner must be warned when a title is low or out of stock
- **Payments:** MTN MoMo, Telecel/Vodafone Cash, bank transfer, card
- **Fulfillment:** customer chooses delivery, in-store pickup, *or* rider delivery (Yango/Bolt/Uber) — added 2026-07-18, owner request. Rider delivery has **no calculated fee**: the customer pays Book Pharm for the books only; the attendant books the actual ride with the customer's phone number and drop-off address, and the ride fare is settled directly between the customer and the rider service. The portal must flag rider-delivery orders as needing a booking until the attendant marks one placed — same pattern as low-stock/reconciliation alerts, so one doesn't get missed during a shift.
- **Standard delivery pricing: distance-based radius tiers**, confirmed 2026-07-20, owner request (resolves the old "delivery fee method" open item below). The owner sets the shop's own lat/lng once (`ShopLocation`, portal, via the same address-autocomplete picker checkout uses) and configures rings — "up to Xkm from the shop costs GHS Y" (`DeliveryPricingRule` with `method=DISTANCE_BASED`, ordered by `radius_km`). Straight-line (haversine) distance, not driving distance — a deliberate choice, no Distance Matrix API call needed at checkout. A point farther than every configured ring **blocks standard Delivery outright** at checkout (customer must choose Pickup or Rider Delivery instead) — never silently caps at the top tier's price. Fixed-zone rules remain fully supported and are the automatic fallback whenever no `DISTANCE_BASED` rule is active, so a shop that hasn't configured radius pricing sees no behavior change. See `apps/fulfillment/services.py`.
- **Rider dispatch (standard Delivery only):** the attendant types a phone number (no saved rider accounts — "just a number input", owner's words) into the order detail page and an SMS goes out with the order details and a Google Maps link, sent **synchronously**, not queued — a deliberate, scoped exception to this file's own "never send SMS inline" rule (§8), justified because it's exactly one bounded external call (like the existing Paystack checkout call), not a bulk loop, and the rider needs it now. Do not extend this exception to any bulk/multi-recipient send.
- **Order confirmation:** customers confirm receipt and can leave feedback/reviews
- **Marketplace:** Jumia sales tracked as a distinct channel, including returns
- **Customer data captured at checkout:** phone, full name, email, birthday
- **Loyalty + SMS marketing:** both required
- **Expenses:** business expenses must be separable from the owner's personal withdrawals
- **Priority reports:** sales (daily/weekly/monthly), profit margin per book, stock levels
- **Profit tracking:** cost price vs. selling price per book
- **Devices:** shop + occasional book fairs → **offline support with later sync is mandatory**
- **Access:** three tiers, added 2026-07-19, owner request — **Superuser** (developer/Django-admin access, never listed or manageable in the portal), **Owner** (full portal access, including creating/revoking other accounts), **Attendant** (desktop POS only, rejected at the portal login view). `apps.accounts.models.User.Role` was modeled for this from Phase 0 (`OWNER`/`ATTENDANT`, formerly `OWNER`/`STAFF`) — this is that anticipated next step, not a redesign. The owner can also ring up an in-store sale directly from the portal (`portal:register_create`), the same `create_sale()` path the desktop POS uses.
  - **Password management**, added 2026-07-20: the Owner changes their own password self-service (`portal:change_password`, current-password required, standard Django `PasswordChangeForm`). The Owner can reset an **Attendant's** password directly to a value of their choosing (`portal:user_reset_password`, "just a number input"-style — no email flow) — scoped to Attendant only; Owner-to-Owner resets are a different permission question and aren't built.

### Explicitly out of scope

- **Credit sales / debtor tracking.** The client said no. Do not build it.
- Multi-branch / multi-location.

### Still open — ask before implementing

- **Discount approval level:** owner-only vs. staff within a limit. Model has an `approval_level` field; default to owner-only.

---

## 5. Repo layout

```
bookpharm/
├── CLAUDE.md
├── ROADMAP.md
├── .env.example
├── backend/
│   ├── .venv/                # Python virtual env — gitignored, never committed
│   ├── manage.py
│   ├── config/              # settings/, urls.py, wsgi.py
│   ├── apps/
│   │   ├── accounts/        # User, Role (Owner/Attendant), email+password auth
│   │   ├── catalog/         # Book, Category, stock
│   │   ├── sales/           # Sale, SaleItem, offline sync
│   │   ├── fulfillment/     # delivery/pickup/rider-delivery, delivery pricing
│   │   ├── customers/       # Customer, loyalty
│   │   ├── payments/        # Paystack integration
│   │   ├── messaging/       # SMSOnlineGH, campaigns
│   │   ├── expenses/
│   │   ├── reports/
│   │   ├── storefront/      # public views + templates
│   │   ├── portal/          # owner views + templates
│   │   └── api/             # DRF routers, serializers, sync endpoints
│   ├── templates/
│   ├── static/
│   └── requirements.txt
├── desktop/                 # Electron POS
│   ├── main.js
│   ├── preload.js
│   ├── renderer/
│   ├── db/                  # SQLite schema + outbox queue
│   └── package.json
├── mockups/                 # Stitch HTML exports — reference only, do not import directly
└── docs/
    ├── SRS.md
    └── discovery.md
```

`mockups/` holds the generated HTML designs. Treat them as **visual reference**: lift the markup and CSS into Django templates deliberately, don't wire the raw files into the app.

---

## 6. Data model

One `Sale` table covers **all three channels** — this is deliberate, so reports are a single query rather than a union across tables.

**`accounts`**
- `User` — email (login identity, not username), `full_name`, `role` (`OWNER` | `ATTENDANT`), `is_active`, `is_superuser` (Django/dev access — orthogonal to `role`, see §4)
  - Portal login rejects `role=ATTENDANT`. `is_superuser=True` accounts are excluded from every portal user-management query, not just hidden in the UI — that exclusion is the actual access boundary, not a display filter.

**`catalog`**
- `Category` — name, slug
- `Tag` — name, slug. Freeform, owner-created, many-per-book — distinct from `Category` (fixed, one-per-book)
- `Book` — `isbn` (nullable, unique-if-set), `internal_code` (generated when no ISBN), title, author, `cost_price`, `selling_price`, `stock_qty`, `low_stock_threshold`, category FK, tags M2M, cover image, description, `is_active`
  - Profit per book = `selling_price - cost_price`. Never expose `cost_price` on the storefront.
- `PriceChangeLog` — book FK, `field` (`COST_PRICE`|`SELLING_PRICE`), `old_value`, `new_value`, `changed_by` FK (nullable), `changed_at`. Written by `apps/catalog/services.py::log_price_changes()` from the view layer on edit only, never on creation — see portal book history page (`portal:book_history`)
- `StockAdjustment` — book FK, `delta`, `resulting_qty`, `reason`, notes, `adjusted_by` FK (nullable), `created_at` — restocks, corrections, damage/loss

**`customers`**
- `Customer` — `phone` (unique, primary identifier), `full_name`, `email`, `birthday`, `loyalty_points`, `created_at`
- `LoyaltyTransaction` — customer FK, points delta, reason, sale FK (nullable)

**`sales`**
- `Sale` — `channel` (`IN_STORE` | `ONLINE` | `JUMIA`), customer FK (nullable), subtotal, `discount_amount`, `delivery_fee`, total, `payment_method`, `payment_status`, `status`, `created_at`, `attendant` FK (nullable), `offline_uuid` (unique, nullable), `synced_at`, `external_ref` (Jumia), `returned_at`
- `SaleItem` — sale FK, book FK, qty, `unit_price` (snapshot at time of sale — never read live price for historical records), `line_discount`
- `DiscountRule` — type (`PERCENT` | `FIXED`), value, scope (`GLOBAL` | `CATEGORY` | `BOOK`), target, `approval_level`, `is_active`

**`fulfillment`**
- `ShopLocation` — singleton (`load()`, always `pk=1`), `address`, `latitude`/`longitude`. Origin point for distance-based delivery pricing; set once by the owner in the portal.
- `Fulfillment` — sale OneToOne, type (`DELIVERY` | `PICKUP` | `RIDER_DELIVERY`), address, `latitude`/`longitude` (nullable — captured at checkout from Places Autocomplete or device geolocation), `fee`, status, `confirmed_by_customer_at`, `rider_booked_at`/`rider_booked_by` FK (nullable), `delivery_rider_phone`/`delivery_rider_sms_sent_at`/`delivery_rider_sms_sent_by` FK (nullable)
  - `RIDER_DELIVERY` ("Yango / Bolt / Uber Delivery" in the UI): `fee` is always `0` — Book Pharm never calculates or collects it. `rider_booked_at`/`rider_booked_by` track the attendant manually placing the actual ride; the portal surfaces unbooked ones as an alert.
  - `delivery_rider_*` fields are for standard `DELIVERY` only, and are a completely separate concept from `rider_booked_*` (which is `RIDER_DELIVERY`-only) — see §4's rider dispatch entry. Don't conflate the two "rider" ideas.
- `DeliveryPricingRule` — `method` (`FIXED_ZONE` | `DISTANCE_BASED` | `MANUAL`), `zone_name` (FIXED_ZONE), `radius_km` (DISTANCE_BASED — upper bound of the ring), `fee`, `is_active`. `DISTANCE_BASED` is resolved by `apps/fulfillment/services.py::resolve_distance_fee()` against `ShopLocation`; checkout prefers it whenever any `DISTANCE_BASED` rule is active, else falls back to `FIXED_ZONE`. Neither applies to `RIDER_DELIVERY`, which bypasses fee calculation entirely. `MANUAL` is modeled, not built.
- `Review` — sale FK, rating, comment, `created_at`

**`payments`**
- `PaymentTransaction` — sale FK, provider, `provider_ref`, amount, status, raw payload JSON, `created_at`

**`expenses`**
- `Expense` — amount, category, `is_personal_withdrawal` (bool), date, notes
  - Business profit reports must exclude rows where `is_personal_withdrawal=True`.

**`messaging`**
- `SmsCampaign` — name, audience filter, message body, scheduled_for, sent_at, status
- `SmsLog` — customer FK, message, provider_ref, status, sent_at

Low-stock alerts are **computed** (`stock_qty <= low_stock_threshold`), not a stored table.

---

## 7. Offline sync — the hardest part, get this right

The attendant sells at book fairs with unreliable internet. Sales must never be lost.

**Design:**
- Electron keeps a **local SQLite mirror** of the catalog (read-only) and an **outbox** of unsynced sales.
- Every sale gets a **client-generated UUID** (`offline_uuid`) at creation time, online or off.
- `POST /api/sync/sales/` accepts a **batch** and is **idempotent** — the unique constraint on `offline_uuid` means a replayed batch is a no-op. Return per-UUID accepted/rejected status.
- Catalog pull: `GET /api/catalog/?updated_since=<timestamp>` for incremental sync.
- **The server is authoritative for stock.**

**The oversell problem — do not paper over this:** two devices offline at the same fair can both sell the last copy. The server must **accept both sales** (a real sale happened; refusing it loses money and data) and **flag the discrepancy** for the owner to reconcile in the portal. Never silently reject a synced sale because stock went negative. Allow `stock_qty` to go negative and surface it as a reconciliation alert.

**Auth:** per-attendant, not per-device (changed 2026-07-19 — see §4's Access entry). `POST /api/auth/login/` takes email+password and returns that user's DRF token, the same way the desktop app has always authenticated everything else; only how the token is *obtained* changed, from the owner hand-provisioning one per device to each attendant signing in with their own portal-created credentials. The token is still stored in the OS keychain via Electron's `safeStorage`, not plain-text config — logging out clears only the stored credentials, never the local outbox/catalog mirror, which may hold sales that haven't synced yet.

---

## 8. Integrations

**Paystack** — initialize transaction server-side, redirect/inline checkout, verify via webhook *and* a verify-on-return call (don't trust the redirect alone). Store the full payload in `PaymentTransaction.raw_payload` for reconciliation. The client has been burned before by payments not reflecting — reconciliation records matter more than usual here.

**SMSOnlineGH** — used for birthday greetings, new arrivals, and promotions. Sends go through a management command triggered by cron, writing to `SmsLog`. Never send from a request/response cycle; queue it. **One deliberate exception:** rider dispatch (§4) sends synchronously from the portal — a single bounded call, not a bulk loop; don't use that as precedent to inline anything else.

**Google Maps** — client-side (Places Autocomplete + Geocoding), key in `GOOGLE_MAPS_API_KEY` (blank-safe: every integration point degrades to a plain text field when unset). Used for: checkout address entry, shop location entry in the portal, and distance-based delivery pricing's straight-line calculation (which does *not* call any Maps API at fee-calculation time — see §4).

---

## 9. Conventions

- **Python virtual environment is mandatory.** All backend (`backend/`) work — installing packages, running `manage.py`, running tests, running management commands — happens inside an activated venv (`python -m venv backend/.venv`, then activate before every session). Never `pip install` globally and never run Django commands against the system Python. `backend/.venv/` is gitignored and never committed; `backend/requirements.txt` is the source of truth for what gets installed. Document the activate step in `README`. (Desktop POS uses `npm`/`node_modules` for the same isolation purpose — no venv needed there.)
- Money: `DecimalField(max_digits=10, decimal_places=2)`. Never floats. Currency is GHS.
- All prices on `SaleItem` are **snapshots**, not FK lookups to live price.
- Timezone: `Africa/Accra`. Store UTC, display local.
- Phone numbers: normalize to `+233XXXXXXXXX` on save. Phone is the customer's identity key.
- Django apps stay narrow — if logic spans two apps, it probably belongs in a service module, not a fat model.
- HTMX for partial updates; avoid full-page reloads in the portal.
- Templates extend a shared base; the storefront and portal have separate bases.
- Environment config via `.env` (see `.env.example`). Never commit secrets.

**Design language** (from the approved mockups): cream/ivory backgrounds, deep burgundy accent, wood-brown secondary, gold highlights for prices and primary actions. Warm serif for headings and book titles, clean sans for UI chrome. Rounded cards, soft shadows, generous whitespace.

The POS app is the exception — it prioritizes speed and legibility over decoration: dense layout, large totals, unmistakable primary buttons, and a permanently visible online/offline sync indicator.

---

## 10. Priorities

Build order is in `ROADMAP.md`. The reasoning behind it: **the POS is the client's most urgent pain**, so it ships first and earns trust. The storefront is valuable but she has survived without it — it comes after the shop is running reliably.
