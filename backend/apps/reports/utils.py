import csv
from datetime import date, datetime, time, timedelta

from django.http import HttpResponse
from django.utils import timezone


def parse_date_range(request):
    """?start=&end=&granularity= with sensible defaults: month-to-date, daily."""
    today = timezone.localdate()
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')
    try:
        start = date.fromisoformat(start_str) if start_str else today.replace(day=1)
    except ValueError:
        start = today.replace(day=1)
    try:
        end = date.fromisoformat(end_str) if end_str else today
    except ValueError:
        end = today
    if start > end:
        start, end = end, start

    granularity = request.GET.get('granularity', 'day')
    if granularity not in ('day', 'week', 'month'):
        granularity = 'day'
    return start, end, granularity


def range_bounds_utc(start_date, end_date):
    """[start_date, end_date] (inclusive, local calendar dates) as a
    [start, end) UTC datetime range for filtering a DateTimeField.

    Deliberately avoids `__date`/`TruncDate` lookups on DateTimeField: those
    need MySQL's CONVERT_TZ, which needs the mysql.time_zone_name tables
    loaded — not the case on this dev box, and often not on cPanel shared
    hosting either. `timezone.make_aware()` does the local-to-UTC
    conversion in Python instead, so the query never depends on the
    database having timezone data at all. (Africa/Accra is UTC+0 with no
    DST, so the conversion is an identity here — but doing it this way
    means the code is actually correct, not "correct because Ghana has no
    offset today.")
    """
    start_dt = timezone.make_aware(datetime.combine(start_date, time.min))
    end_dt = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), time.min))
    return start_dt, end_dt


def csv_response(filename, header, rows):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(header)
    writer.writerows(rows)
    return response
