"""Test script to verify bandwidth chart data loading"""
from db import get_connection
from datetime import datetime, timedelta

# Test the query that the dashboard uses
today = datetime.now().date()
start_date = today - timedelta(days=7)
end_date = today

start_str = start_date.strftime("%Y-%m-%d")
end_str = end_date.strftime("%Y-%m-%d")

print(f"Testing bandwidth query for date range: {start_str} to {end_str}")

# Test "All Routers" query (aggregated by hour)
query = (
    "SELECT DATE_FORMAT(timestamp, '%Y-%m-%d %H:00:00') AS timestamp, "
    "SUM(download_mbps) AS total_download, "
    "SUM(upload_mbps) AS total_upload, "
    "AVG(latency_ms) AS avg_latency "
    "FROM bandwidth_logs "
    "WHERE DATE(timestamp) BETWEEN %s AND %s "
    "GROUP BY DATE_FORMAT(timestamp, '%Y-%m-%d %H:00:00') "
    "ORDER BY timestamp ASC LIMIT 500"
)

conn = get_connection()
cur = conn.cursor(dictionary=True)
cur.execute(query, [start_str, end_str])
rows = cur.fetchall()
conn.close()

print(f"\n✅ Query returned {len(rows)} rows")
if rows:
    print(f"\nFirst 3 rows:")
    for i, row in enumerate(rows[:3]):
        print(f"  {i+1}. Timestamp: {row['timestamp']}, Down: {row['total_download']:.2f} Mbps, Up: {row['total_upload']:.2f} Mbps, Latency: {row['avg_latency']:.2f} ms")
    
    print(f"\nLast 3 rows:")
    for i, row in enumerate(rows[-3:]):
        print(f"  {len(rows)-2+i}. Timestamp: {row['timestamp']}, Down: {row['total_download']:.2f} Mbps, Up: {row['total_upload']:.2f} Mbps, Latency: {row['avg_latency']:.2f} ms")
else:
    print("⚠️ No data found in the specified date range!")
