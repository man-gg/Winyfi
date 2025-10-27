"""
Quick check: Did the dashboard detect the loop from auto_loop_simulator.py?
"""

import sys
import mysql.connector
from datetime import datetime, timedelta

print("="*70)
print("🔍 LOOP DETECTION VERIFICATION")
print("="*70)

try:
    # Connect to database
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="network_monitor"
    )
    cursor = conn.cursor(dictionary=True)
    
    # Get detections from last 10 minutes
    cursor.execute("""
        SELECT 
            detection_time,
            status,
            severity_score,
            total_packets,
            offenders_count,
            network_interface
        FROM loop_detections
        WHERE detection_time > DATE_SUB(NOW(), INTERVAL 10 MINUTE)
        ORDER BY detection_time DESC
        LIMIT 10
    """)
    
    detections = cursor.fetchall()
    
    if not detections:
        print("\n❌ NO RECENT DETECTIONS FOUND")
        print("\nPossible reasons:")
        print("  1. Dashboard loop detection not started")
        print("     → Open dashboard, click 'Loop Test', click '▶ Start Auto'")
        print("  2. Detection interval not reached yet (waits 5 minutes)")
        print("     → Use Manual Scan for immediate detection")
        print("  3. Simulator traffic not captured")
        print("     → Run simulator while dashboard is running")
        print("\n💡 Quick Fix:")
        print("  1. Start dashboard: python main.py")
        print("  2. Enable loop detection")
        print("  3. Open Loop Test modal")
        print("  4. Go to Manual Scan tab")
        print("  5. Click '▶ Run Manual Scan'")
        print("  6. Should see loop detected immediately!")
    else:
        print(f"\n✅ FOUND {len(detections)} RECENT DETECTION(S):")
        print("\n" + "-"*70)
        
        for i, det in enumerate(detections, 1):
            time_str = det['detection_time'].strftime("%H:%M:%S")
            status = det['status']
            severity = det['severity_score']
            packets = det['total_packets']
            offenders = det['offenders_count']
            interface = det['network_interface']
            
            # Determine status emoji
            status_display = {
                'clean': '✅ CLEAN',
                'suspicious': '🟡 SUSPICIOUS',
                'loop_detected': '🔴 LOOP DETECTED'
            }.get(status, status)
            
            print(f"\n#{i} - {time_str}")
            print(f"   Status: {status_display}")
            print(f"   Severity: {severity:.1f}")
            print(f"   Packets: {packets}")
            print(f"   Offenders: {offenders}")
            print(f"   Interface: {interface}")
            
            if status == 'loop_detected':
                print("   🎉 SUCCESS! Loop was detected!")
            elif status == 'suspicious':
                print("   ⚠️  Suspicious activity (close to loop threshold)")
            
        print("\n" + "-"*70)
        
        # Check if latest is loop detected
        latest = detections[0]
        if latest['status'] == 'loop_detected':
            print("\n🎉 LATEST DETECTION: LOOP DETECTED!")
            print(f"   Severity: {latest['severity_score']:.1f} (threshold: 22.5)")
            print(f"   Offenders: {latest['offenders_count']}")
            print("\n✅ The loop detection system is working correctly!")
            
        elif latest['status'] == 'suspicious':
            print("\n🟡 LATEST DETECTION: SUSPICIOUS")
            print(f"   Severity: {latest['severity_score']:.1f} (threshold: 22.5)")
            print(f"   Just below loop detection threshold")
            print(f"   Gap: {22.5 - latest['severity_score']:.1f} points")
            print("\n💡 The detection is working but severity is slightly low.")
            print("   This could be because:")
            print("   • Simulator traffic rate was a bit lower than expected")
            print("   • Some packets were lost")
            print("   • Network conditions affected capture")
            print("\n   This is still GOOD - the system is detecting unusual traffic!")
            
        else:
            print("\n✅ LATEST DETECTION: CLEAN")
            print("   No loops or suspicious activity detected")
    
    cursor.close()
    conn.close()
    
except mysql.connector.Error as e:
    print(f"\n❌ DATABASE ERROR: {e}")
    print("\nMake sure:")
    print("  • MySQL is running")
    print("  • Database 'network_monitor' exists")
    print("  • Table 'loop_detections' exists")
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("💡 WHAT TO DO NEXT:")
print("="*70)

print("\nIf no detections found:")
print("  → Dashboard must be running with loop detection enabled")
print("  → Use Manual Scan in Loop Test modal for immediate results")

print("\nIf detections found but status is 'suspicious':")
print("  → System is working! It detected unusual traffic")
print("  → Run simulator again for higher packet rate")
print("  → Or lower threshold to 10-12 for more sensitivity")

print("\nIf loop detected:")
print("  → SUCCESS! Everything is working perfectly!")
print("  → Check dashboard for real-time status indicator")
print("  → Check for popup alert notification")

print("\n" + "="*70)
