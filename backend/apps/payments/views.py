import json
import logging

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.sales.models import Sale
from apps.sales.services import finalize_paid_sale

from .models import PaymentTransaction
from .paystack import verify_webhook_signature
from .views_helpers import PAYSTACK_CHANNEL_TO_METHOD

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def paystack_webhook(request):
    """The durable path (CLAUDE.md §8: verify via webhook *and*
    verify-on-return — never trust the redirect alone). Paystack calls this
    server-to-server, so it has no session/cookies and can't go through the
    normal CSRF flow — signature verification is what proves it's really
    Paystack instead.
    """
    if not verify_webhook_signature(request):
        logger.warning('Paystack webhook signature mismatch — rejected.')
        return HttpResponse(status=401)

    event = json.loads(request.body)
    if event.get('event') != 'charge.success':
        return JsonResponse({'status': 'ignored'})

    data = event['data']
    reference = data.get('reference')
    sale = Sale.objects.filter(offline_uuid=reference).first()
    if sale is None:
        logger.warning('Paystack webhook for unknown reference %s', reference)
        return HttpResponse(status=404)

    PaymentTransaction.objects.filter(provider_ref=reference).update(
        status=PaymentTransaction.Status.SUCCESS, raw_payload=data,
    )
    method = PAYSTACK_CHANNEL_TO_METHOD.get(data.get('channel'), Sale.PaymentMethod.CARD)
    finalize_paid_sale(sale, payment_method=method)

    return JsonResponse({'status': 'ok'})
