# Book Pharm — Discovery Summary

**Status:** Reference. Source of truth for *why* the system works the way it does.
**Sources:** client discovery call (14 July 2026) + completed clarification questionnaire.
**Companion:** [`SRS.md`](./SRS.md) for the formal requirements. [`../CLAUDE.md`](../CLAUDE.md) for build context.

This is the client-facing narrative in repo form. When a requirement in the SRS looks arbitrary, the reason is usually here.

---

## 1. The business

Book Pharm is a bookshop in Ghana, owner-operated. Sales happen three ways today: in the shop, occasionally at book fairs and school events, and through Jumia. There is no website.

The owner is not technical. Every design decision should assume she will use this system daily without developer help.

---

## 2. What she's dealing with

The discovery call surfaced a cluster of related problems. They're listed here roughly in the order she raised them, which is also roughly her priority order.

**Her POS is failing her.** It's inconsistent, and she's locked into a long-term contract that never solved her actual problems. This is the most urgent pain and the reason the desktop POS ships first.

**She doesn't really know what's in stock.** Wholesale suppliers often deliver without ISBNs and without proper invoices. Anything that can't be scanned currently goes untracked.

**She doesn't know if she's profitable.** No reliable view of sales, expenses, or margins. Compounding this: money spent on the business and money she withdraws personally are mixed together, so even a "profit" figure wouldn't be honest.

**She can't manage the shop while away.** The current system only works from one machine in one place.

**Her first attempt at an online store failed.** It was expensive, every product had to be manually uploaded by the developer, and there was no way to collect customer feedback. She abandoned it.

**She has no domain.** She initially thought she had one from that earlier attempt; the questionnaire confirmed she does not. She does have a logo and brand colours.

**WhatsApp broadcasts have stopped working for her.** They've become unreliable and now carry a fee. She has no other channel to her customers.

**Customer data is collected informally**, so there's no marketing list and no way to reward regulars.

**Jumia is hard to track**, mostly because of the high return rate — returns pollute her sense of what actually sold.

**Payments have burned her before.** Transactions not reflecting, or taking days to settle, with no clean record to reconcile against.

---

## 3. How the system answers each

| Problem | Response in this system |
|---|---|
| Unreliable, contract-locked POS | Purpose-built Electron desktop POS. Her system, her data, no lock-in. |
| Untracked stock without ISBNs | Scan where an ISBN exists; manual entry with a generated internal code where it doesn't. Nothing goes untracked. |
| No visibility on profitability | Sales, expense and margin reports in the portal (daily/weekly/monthly). |
| Business and personal money mixed | `is_personal_withdrawal` flag on every expense. Profit reports exclude personal draws. |
| Can't manage remotely | Web portal, any device, anywhere. |
| Failed online store, manual uploads | Storefront reads the same database as the shop. Stock is live by construction — there is nothing to upload. |
| Two systems drifting apart | One database behind all three components. This is the single most important architectural constraint. |
| No customer data | Phone, name, email and birthday captured at every checkout, in-store and online. |
| WhatsApp broadcasts unreliable | SMS via SMSOnlineGH — a channel she controls. |
| No way to reward regulars | Owner-configurable loyalty/rewards. |
| Informal, inconsistent discounts | Central discount rules (percentage or fixed) set by the owner. |
| Jumia untrackable, high returns | Jumia recorded as its own channel with a clean return/reversal path. |
| No delivery pricing logic | Configurable delivery pricing — method still to be confirmed. |
| Payment reconciliation failures | Full gateway payloads stored on every transaction. Reconciliation records are a first-class feature here, not an afterthought. |
| Book fairs with no internet | POS records sales offline and syncs on reconnect. |
| No web presence | New domain, storefront built around her existing logo and brand colours. |

---

## 4. Confirmed by questionnaire

Decided. Don't reopen these in code review.

- **Discounts:** percentage *and* fixed amount
- **Stock entry:** scanning *and* manual entry; internal code when no ISBN
- **Low stock:** must warn the owner
- **Online payments:** MTN MoMo, Telecel/Vodafone Cash, bank transfer, card
- **Fulfillment:** delivery *and* pickup
- **Order confirmation:** customer confirms receipt; feedback/reviews enabled
- **Marketplace:** Jumia tracked separately, returns handled
- **Customer data:** phone, full name, email, birthday
- **Loyalty + SMS marketing:** both required
- **Expenses:** personal withdrawals separated from business expenses
- **Priority reports:** sales, profit margin per book, stock levels
- **Profit tracking:** cost price vs. selling price per book
- **Devices:** shop + occasional book fairs → offline support mandatory
- **Access:** owner only at launch; extensible to staff later
- **Domain:** none owned — must be registered
- **Branding:** existing logo and brand colours to be used

### Out of scope

- **Credit sales / debtor tracking.** She said no. It came up on the call; the questionnaire settled it. Do not build it.
- Multi-branch.
- Staff accounts at launch (model for it, don't build it).

### Open

- **Delivery fee method** — distance-based, fixed zones, or manual. Blocks storefront checkout.
- **Discount approval level** — owner-only, or staff within a limit. Defaulting to owner-only.

---

## 5. Workflows

### In-store sale
1. Attendant scans or searches for a book.
2. Item added to cart; owner-defined discounts apply.
3. Payment taken — cash, mobile money, or card.
4. Sale recorded, stock decremented, customer details captured.
5. If offline: sale is stored locally and syncs automatically on reconnect.

### Online order
1. Customer browses the storefront — live stock, no manual upload.
2. Adds to cart, chooses delivery or pickup, pays online.
3. Order lands in the portal immediately; stock decrements.
4. Delivery fee calculated per the owner's configured rule.
5. Customer confirms receipt and may leave feedback.

### Owner oversight
1. Logs into the portal from any device.
2. Reviews sales, expenses, margins, stock in real time.
3. Adjusts discounts, loyalty, delivery pricing; sends SMS campaigns.
4. Reconciles Jumia orders separately from in-house sales.

---

## 6. Use cases

| # | Use case | Actor | Why it's here |
|---|---|---|---|
| 1 | Everyday in-store sale | Attendant | The core loop. Everything else is secondary. |
| 2 | Online order with delivery | Customer | Fee auto-calculated; owner sees it instantly. |
| 3 | Managing the business remotely | Owner | Directly answers "can't manage while away". |
| 4 | Selling at a book fair, offline | Attendant | Drives the entire offline sync design. |
| 5 | Low stock alert | Owner | Reorder before the title runs out. |
| 6 | Jumia order and return | Owner | Return reverses cleanly without touching in-house figures. |
| 7 | Birthday and promotional SMS | Owner | Replaces the WhatsApp broadcasts. |
| 8 | Adding wholesale stock with no ISBN | Attendant | The supplier reality — manual entry is not an edge case. |
| 9 | Tracking profitability | Owner | Revenue minus cost of goods minus *business* expenses only. |

---

## 7. Notes for whoever builds this

Three things from the call that are easy to lose in translation:

**"No manual uploads" is a requirement, not a nice-to-have.** Her last online store died of it. If a feature ever requires her to re-enter something she already entered in the shop, it's wrong.

**She has been burned by payments.** Storing the full gateway payload on every transaction isn't defensive over-engineering — it's the thing that lets her trust the system when a MoMo payment looks missing.

**Manual stock entry is the normal path, not the fallback.** A meaningful share of her inventory arrives with no ISBN and no invoice. If manual entry is slow or buried in the UI, the system fails at her most common task.
