# Book Pharm — Software Requirements Specification

**Version:** 1.1 (repo edition)
**Status:** Reference. FR-IDs here are stable — cite them in commits and PRs.
**Companion:** [`discovery.md`](./discovery.md) for the *why*. [`../CLAUDE.md`](../CLAUDE.md) for build context and conventions.

> **Changed from v1.0 (client edition):** v1.0 was written before the stack was fixed and left the web frontends open. This edition reflects the confirmed architecture — Django REST API with server-rendered storefront and portal, Electron POS consuming the API, MySQL on cPanel shared hosting. The functional requirements themselves are unchanged.

---

## 1. Introduction

### 1.1 Purpose

Defines functional and non-functional requirements for the Book Pharm POS and E-Commerce System, translating discovery findings and the client's questionnaire responses into a testable specification.

### 1.2 Scope

Three components over one shared database:

- **Desktop POS** (Electron) — in-store sales, offline-capable
- **Owner portal** (web) — inventory, reports, expenses, customers, marketing
- **Storefront** (web) — public browsing, ordering, payment

Covers in-store sales, online ordering and payment, inventory, customers and loyalty, SMS marketing, expense tracking, reporting, and Jumia order tracking.

### 1.3 Definitions

| Term | Meaning |
|---|---|
| POS | Point of Sale |
| ISBN | International Standard Book Number |
| MoMo | Mobile Money |
| KSE | KhaelSolutions Enterprise (development provider) |
| Channel | Sales origin: `IN_STORE`, `ONLINE`, or `JUMIA` |
| Outbox | Local queue of unsynced sales on a POS device |

---

## 2. Overall Description

### 2.1 Product perspective

A new, self-contained product replacing the client's current POS. All three components read and write one central database — stock, sales, customer and order data are consistent across them by construction, not by synchronisation.

### 2.2 User classes

| Class | Access | Characteristics |
|---|---|---|
| **Owner / Admin** | Full portal | Non-technical. Must operate the system without developer help. |
| **Shop attendant** | POS app only | Sales functions only. Speed matters more than features. |
| **Online customer** | Storefront | No account required; checkout details only. |

### 2.3 Operating environment

- **POS:** Windows desktop/laptop, Electron. Must function with and without internet.
- **Portal + storefront:** modern browsers, desktop and mobile.
- **Backend:** Django on cPanel shared hosting, MySQL.

### 2.4 Constraints

- Electron for the desktop POS (client engagement requirement).
- **cPanel shared hosting** — no long-running processes, no Celery, no WebSockets, Passenger/WSGI only. Scheduled work runs via cron + management commands.
- Payment providers limited to those supporting MoMo, bank transfer and card in Ghana (Paystack).
- SMS via SMSOnlineGH; sender ID requires provider approval.
- New domain must be registered — none currently owned.

### 2.5 Assumptions & dependencies

- Client provides logo and brand colours.
- Client's business details are required for Paystack and SMSOnlineGH accounts; these cannot be created on her behalf.
- Open decisions in §8 resolved before the dependent phases ship.

---

## 3. Functional Requirements

### 3.1 Desktop POS — `POS-*`

| ID | Requirement | Priority |
|---|---|---|
| POS-01 | Attendant shall search or scan by ISBN/barcode to add a book to a sale. | High |
| POS-02 | Attendant shall manually add a book by title when no ISBN is available. | High |
| POS-03 | System shall apply percentage or fixed-amount discounts per owner-defined rules. | High |
| POS-04 | System shall record cash, mobile money and card payment for in-store sales. | High |
| POS-05 | System shall capture customer phone, name, email and birthday at checkout. Phone is required; others prompted. | High |
| POS-06 | System shall decrement stock immediately on sale completion. | High |
| POS-07 | POS shall record sales while offline and sync automatically on reconnect, with no data loss and no duplicates. | High |
| POS-08 | System shall add stock items, generating an internal code where no ISBN exists. | High |
| POS-09 | System shall surface low-stock and out-of-stock warnings. | Medium |
| POS-10 | System shall generate a printable receipt per completed sale. | Medium |
| POS-11 | POS shall display an unambiguous online/offline sync indicator at all times. | High |

### 3.2 Owner Portal — `PRT-*`

| ID | Requirement | Priority |
|---|---|---|
| PRT-01 | Owner shall log in from any internet-connected device. | High |
| PRT-02 | Portal shall display sales reports (daily, weekly, monthly). | High |
| PRT-03 | Portal shall display profit margin per book from cost price vs. selling price. | High |
| PRT-04 | Portal shall display stock levels and low-stock alerts. | High |
| PRT-05 | Owner shall record expenses, flagging each as business expense or personal withdrawal. | High |
| PRT-06 | Profit reports shall exclude personal withdrawals. | High |
| PRT-07 | Owner shall configure discount rules (percentage or fixed). | High |
| PRT-08 | Owner shall configure a loyalty/rewards program. | Medium |
| PRT-09 | Owner shall send promotional SMS (birthdays, new arrivals, sales). | High |
| PRT-10 | Portal shall list customer profiles with purchase history. | Medium |
| PRT-11 | Portal shall record Jumia orders as a distinct channel, including returns/reversals. | High |
| PRT-12 | Portal shall display online orders with fulfillment and payment status. | High |
| PRT-13 | Portal shall surface stock reconciliation alerts arising from offline oversell. | High |
| PRT-14 | System shall support a single owner account at launch; the model shall permit staff accounts with configurable permissions later without redesign. | Low |

### 3.3 Storefront — `WEB-*`

| ID | Requirement | Priority |
|---|---|---|
| WEB-01 | Storefront shall display real-time stock from the same central database as POS and portal. No manual upload step shall exist. | High |
| WEB-02 | Customers shall browse, search and add books to a cart. | High |
| WEB-03 | Customers shall choose home delivery or in-store pickup at checkout. | High |
| WEB-04 | System shall calculate delivery fee per the owner's configured pricing method. | High |
| WEB-05 | Customers shall pay via MTN MoMo, Telecel/Vodafone Cash, bank transfer or card. | High |
| WEB-06 | Customers shall confirm receipt of a delivered or collected order. | Medium |
| WEB-07 | Customers shall submit a rating and comment after order completion. | Medium |
| WEB-08 | Book detail pages shall be server-rendered with meta tags and structured data for search indexing. | High |
| WEB-09 | Storefront shall be published on a newly registered domain, styled to the client's logo and brand colours. | High |
| WEB-10 | Cost price shall never be exposed on any public-facing surface. | High |

---

## 4. External Interfaces

### 4.1 User interfaces

- **POS:** dense, speed-first, scanner- and keyboard-driven. Large legible totals, unmistakable primary actions, permanent sync indicator. Decoration is subordinate to throughput.
- **Portal:** dashboard-style, card-based, chart-supported.
- **Storefront:** warm literary design language — cream/ivory, burgundy, wood-brown, gold. Serif headings, sans UI chrome.

### 4.2 Hardware

- USB or Bluetooth barcode/ISBN scanner at the POS.
- Optional receipt printer.

### 4.3 Software

| Interface | Provider | Notes |
|---|---|---|
| Payments | Paystack | MoMo, card, bank transfer. Webhook **and** verify-on-return; never trust the redirect alone. |
| SMS | SMSOnlineGH | Campaigns and birthday sends via cron-triggered management commands, never in a request cycle. |
| Book metadata | External ISBN lookup (optional) | Manual entry is the mandatory fallback, not the exception. |

### 4.4 Communication

Internet required for storefront, portal and POS sync. The POS must operate offline and reconcile automatically on reconnect.

---

## 5. Data Requirements

Core entities shared across all components. Full field-level detail in [`../CLAUDE.md`](../CLAUDE.md) §6.

| Entity | Key attributes |
|---|---|
| `Book` | ISBN (nullable), internal code, title, author, cost price, selling price, stock qty, low-stock threshold, category, cover, active |
| `Customer` | Phone (unique, identity key), full name, email, birthday, loyalty points |
| `Sale` | Channel, customer, subtotal, discount, delivery fee, total, payment method/status, attendant, `offline_uuid`, `synced_at`, `external_ref`, `returned_at` |
| `SaleItem` | Sale, book, qty, unit price (snapshot), line discount |
| `Fulfillment` | Sale, type (delivery/pickup), address, fee, status, receipt confirmation |
| `Review` | Sale, rating, comment |
| `DiscountRule` | Type (percent/fixed), value, scope, approval level, active |
| `PaymentTransaction` | Sale, provider, provider ref, amount, status, raw payload |
| `Expense` | Amount, category, `is_personal_withdrawal`, date, notes |
| `LoyaltyTransaction` | Customer, points delta, reason, sale |
| `SmsCampaign` / `SmsLog` | Audience, body, schedule, status / per-recipient delivery record |

**Design note:** one `Sale` table carries all three channels via a `channel` enum, rather than separate models per channel. Reports become a single query instead of a union. Low-stock alerts are computed from `stock_qty <= low_stock_threshold`, not stored.

---

## 6. Non-Functional Requirements

### 6.1 Performance
Common POS actions (add item, complete sale) under 2 seconds. Storefront listings under 3 seconds on a typical mobile connection.

### 6.2 Availability & offline support
The POS must remain fully usable without internet, queuing sales locally and syncing automatically on reconnect with no data loss.

**Oversell handling — explicit requirement, not an edge case.** Two devices offline simultaneously may each sell the last copy. The server **shall accept both sales**, permit `stock_qty` to go negative, and raise a reconciliation alert (PRT-13). The server shall never silently reject a synced sale on stock grounds — a real sale occurred, and discarding it loses money and data.

Sync shall be idempotent: replaying a batch is a no-op, enforced by a unique constraint on `offline_uuid`.

### 6.3 Security
- Owner and attendant accounts authenticated; role-based separation between them.
- POS devices authenticate by device-scoped token, stored via Electron `safeStorage` (OS keychain), never plain-text config.
- Card and MoMo credentials handled by the payment gateway; never stored by this system.

### 6.4 Usability
Designed for non-technical users. The owner must review reports and adjust settings without developer assistance.

### 6.5 Scalability
The model accommodates further staff accounts, additional locations, and further marketplace channels beyond Jumia without redesign.

### 6.6 Maintainability
One coherent codebase per component over a shared backend — deliberately unlike the fragmented setup the client is leaving.

---

## 7. Use Case Traceability

| # | Use case | Actor | Requirements |
|---|---|---|---|
| 1 | Everyday in-store sale | Attendant | POS-01, 03, 04, 05, 06, 10 |
| 2 | Online order with delivery | Customer | WEB-02, 03, 04, 05; PRT-12 |
| 3 | Managing the business remotely | Owner | PRT-01, 02, 03, 04 |
| 4 | Selling at a book fair (offline) | Attendant | POS-07, 11; §6.2 |
| 5 | Low stock alert | Owner | POS-09, PRT-04 |
| 6 | Jumia order and return | Owner | PRT-11 |
| 7 | Birthday and promotional SMS | Owner | PRT-09, POS-05 |
| 8 | Adding wholesale stock with no ISBN | Attendant | POS-02, POS-08 |
| 9 | Tracking profitability | Owner | PRT-03, PRT-05, PRT-06 |

---

## 8. Open Items

Resolve before the dependent work ships.

| Item | Blocks | Default assumption |
|---|---|---|
| **Delivery fee method** — distance-based / fixed zones / manual | WEB-04, storefront checkout | Fixed zones. Build `DeliveryPricingRule` so any method drops in. |
| **Discount approval level** — owner-only / staff within a limit | POS-03, PRT-07 | Owner-only. `approval_level` field already modelled. |
| **Domain registration** — none owned | Launch | — Client action required. Raise early; DNS is not a deploy-day task. |
| **Paystack + SMSOnlineGH accounts** | WEB-05, PRT-09 | Client's business details required. SMS sender ID approval takes time — apply early. |

---

## 9. Appendix — Confirmed Client Requirements

From the completed clarification questionnaire. **Decided.**

| Topic | Answer |
|---|---|
| Discounts | Percentage and fixed amount both supported. Approval level open. |
| Credit sales | **Not required.** No credit/debtor tracking in scope. |
| Adding stock | Scanning and manual entry; internal code where no ISBN. |
| Low stock | Owner must be warned. |
| Online payments | MTN MoMo, Telecel/Vodafone Cash, bank transfer, card. |
| Fulfillment | Delivery and pickup. |
| Delivery pricing | Not yet decided. |
| Order confirmation & feedback | Required. |
| Marketplace | Jumia, tracked as a distinct channel with returns. |
| Customer data | Phone, full name, email, birthday. |
| Loyalty & SMS marketing | Both required. |
| Expenses | Personal withdrawals separated from business expenses. |
| Priority reports | Sales (daily/weekly/monthly), profit margin per book, stock levels. |
| Profit tracking | Cost price vs. selling price per book. |
| Device usage | Shop plus occasional book fairs — offline support required. |
| Portal access | Owner only at launch. |
| Domain & branding | No domain owned; existing logo and brand colours to be used. |
