"""
Check recent bandwidth logs in database
"""
from db import get_connection

def show_recent_logs(limit=20):
    """Show recent bandwidth logs"""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT 
                bl.id,
                bl.timestamp,
                r.name as router_name,
                r.ip_address,
                bl.download_mbps,
                bl.upload_mbps,
                bl.latency_ms
            FROM bandwidth_logs bl
            JOIN routers r ON bl.router_id = r.id
            ORDER BY bl.timestamp DESC
            LIMIT %s
        """
        
        cursor.execute(query, (limit,))
        logs = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not logs:
            print("❌ No bandwidth logs found in database!")
            return
        
        print("=" * 80)
        print(f"📊 RECENT BANDWIDTH LOGS (Last {len(logs)} entries)")
        print("=" * 80)
        
        for log in logs:
            print(f"\n🕐 {log['timestamp']}")
            print(f"   Router: {log['router_name']} ({log['ip_address']})")
            print(f"   📥 Download: {log['download_mbps']:.2f} Mbps")
            print(f"   📤 Upload: {log['upload_mbps']:.2f} Mbps")
            print(f"   ⏱️  Latency: {log['latency_ms']} ms" if log['latency_ms'] else "   ⏱️  Latency: N/A")
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    show_recent_logs(20)
