# Deployment notes

Details that don't belong in `ROADMAP.md` (a checklist) or `CLAUDE.md`
(project-wide context). Currently just cron — add sections here as Phase 8
raises more.

---

## cPanel cron jobs

CLAUDE.md §3/§8: no long-running processes on shared hosting, so anything
that isn't a request/response cycle runs as a scheduled `manage.py` command
via cPanel's **Cron Jobs** page, not Celery/a daemon.

Two jobs today, both in `apps/messaging/management/commands/`:

| Command | Suggested schedule | What it does |
|---|---|---|
| `send_sms_campaigns` | Every 15 minutes | Sends any `SmsCampaign` that's `SCHEDULED` and due. The portal composer (`portal:campaign_create` / `campaign_send_now`) only ever sets a campaign to `SCHEDULED` — it never calls SMSOnlineGH itself (CLAUDE.md §8: never send from a request/response cycle). |
| `send_birthday_sms` | Once daily, early morning (e.g. 6:00 AM Africa/Accra) | Texts every customer whose `birthday` is today and who hasn't opted out. Idempotent if it somehow runs twice the same day — see the command's dedup guard. |

**cPanel → Cron Jobs → Add New Cron Job**, command field:

```
cd /home/<cpanel_user>/bookpharm/backend && /home/<cpanel_user>/bookpharm/backend/.venv/bin/python manage.py send_sms_campaigns >> /home/<cpanel_user>/logs/send_sms_campaigns.log 2>&1
```

```
cd /home/<cpanel_user>/bookpharm/backend && /home/<cpanel_user>/bookpharm/backend/.venv/bin/python manage.py send_birthday_sms >> /home/<cpanel_user>/logs/send_birthday_sms.log 2>&1
```

Notes:
- Always invoke the venv's `python` directly (`.venv/bin/python`), never bare `python`/`python3` — CLAUDE.md §9's "never run Django commands against the system Python" applies to cron the same as an interactive shell. There's no "activate" step for a non-interactive cron command; calling the venv's interpreter binary by full path *is* the equivalent.
- Redirect output to a log file (`>>` append, `2>&1` to capture errors too) — cPanel emails cron output by default, which gets noisy at a 15-minute cadence.
- Both commands exit quietly (print "No campaigns due." / "No birthdays today.") when there's nothing to do — an empty log line most runs is expected, not a sign something's broken.
- Both commands no-op with a warning (not an error) if `SMSONLINEGH_API_KEY` isn't set in `.env` yet — safe to schedule before the client's SMSOnlineGH account exists (see `docs/SRS.md` §8 and the ROADMAP blockers list); they'll start actually sending the moment the key is added, no redeploy needed.

## Birthday message wording

`BIRTHDAY_SMS_MESSAGE` in `backend/config/settings/base.py` — a plain Python
setting, not `.env` (it's wording, not a secret). Edit it directly to change
the greeting; `{name_suffix}` is filled in as `, <first name>` or `''`.

## Unsubscribe links

`apps/messaging/tokens.py` can mint a signed, per-customer unsubscribe URL:

```python
from apps.messaging.tokens import make_unsubscribe_token
token = make_unsubscribe_token(customer.id)
url = f'https://{domain}/unsubscribe/{token}/'
```

Not auto-appended to every SMS body — campaign wording is the owner's to
write, and a full URL costs an extra SMS segment. The portal opt-out toggle
on a customer's detail page (`portal:customer_toggle_opt_out`) is the
primary mechanism today: the attendant flips it when a customer asks to
stop receiving texts. Wire the link into message bodies once a real domain
exists (see the ROADMAP blockers list — no domain registered yet).
