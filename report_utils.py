from db import get_connection
from datetime import datetime, timedelta
from ttkbootstrap.widgets import DateEntry
# -----------------------------
# Uptime / Downtime
# -----------------------------
def get_uptime_percentage(router_id, start_date, end_date):
    """
    Calculate uptime percentage for a given router between two datetimes.
    """
    conn = get_connection()
    cursor = conn.cursor()

    total_seconds = (end_date - start_date).total_seconds()

    # Get last known status before the range
    cursor.execute(
        '''
        SELECT status
        FROM router_status_log
        WHERE router_id = %s AND timestamp < %s
        ORDER BY timestamp DESC
        LIMIT 1
        ''',
        (router_id, start_date)
    )
    last_status_row = cursor.fetchone()
    prev_status = last_status_row[0] if last_status_row else 'offline'  # default to offline

    # Now fetch logs inside the range
    sql = '''
    SELECT status, timestamp
    FROM router_status_log
    WHERE router_id = %s AND timestamp BETWEEN %s AND %s
    ORDER BY timestamp ASC
    '''
    cursor.execute(sql, (router_id, start_date, end_date))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    offline = 0
    prev_ts = start_date

    for status, ts in rows:
        if prev_status == 'offline':
            offline += (ts - prev_ts).total_seconds()
        prev_status, prev_ts = status, ts

    # Handle last segment until end_date
    if prev_status == 'offline':
        offline += (end_date - prev_ts).total_seconds()

    uptime = max(0, total_seconds - offline)
    return (uptime / total_seconds) * 100 if total_seconds else 0

# -----------------------------
# Status logs
# -----------------------------
def get_status_logs(router_id, start_date, end_date):
    """Fetch raw status logs for a router in range"""
    conn = get_connection()
    cursor = conn.cursor()
    sql = '''
    SELECT timestamp, status
    FROM router_status_log
    WHERE router_id = %s AND timestamp BETWEEN %s AND %s
    ORDER BY timestamp ASC
    '''
    cursor.execute(sql, (router_id, start_date, end_date))
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return data

# -----------------------------
# Bandwidth usage
# -----------------------------
def get_bandwidth_usage(router_id, start_date, end_date):
    """
    Return total download + upload bandwidth (MB) for a router in a date range.
    """
    conn = get_connection()
    cursor = conn.cursor()
    sql = '''
    SELECT SUM(download_mbps), SUM(upload_mbps)
    FROM bandwidth_logs
    WHERE router_id = %s AND timestamp BETWEEN %s AND %s
    '''
    cursor.execute(sql, (router_id, start_date, end_date))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    download = row[0] or 0
    upload = row[1] or 0
    return download + upload  # total bandwidth in MB

def get_bandwidth_usage(router_id, start_date, end_date):
    """
    Calculate total bandwidth (MB) for a router between start_date and end_date.
    Assumes you have a 'bandwidth_logs' table with:
      router_id, timestamp, download_mbps, upload_mbps
    """
    conn = get_connection()
    cursor = conn.cursor()
    sql = """
    SELECT SUM(download_mbps + upload_mbps) 
    FROM bandwidth_logs
    WHERE router_id = %s AND timestamp BETWEEN %s AND %s
    """
    cursor.execute(sql, (router_id, start_date, end_date))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return float(result[0]) if result and result[0] is not None else 0.0