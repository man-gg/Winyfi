# Enhanced Multi-AP Loop Detection Proposal

## Option 1: Multi-Interface Monitoring

### Implementation Strategy

```python
import threading
from concurrent.futures import ThreadPoolExecutor

def detect_loops_multi_interface(timeout=5, threshold=50):
    """
    Enhanced loop detection across ALL network interfaces.
    Monitors multiple APs/subnets simultaneously.
    """
    import psutil
    
    # Get all active interfaces
    addrs = psutil.net_if_addrs()
    stats_if = psutil.net_if_stats()
    
    active_interfaces = []
    for iface, snic_list in addrs.items():
        if iface in stats_if and stats_if[iface].isup:
            # Skip loopback
            if 'loopback' not in iface.lower() and 'lo' != iface.lower():
                active_interfaces.append(iface)
    
    print(f"🔍 Monitoring {len(active_interfaces)} interfaces: {active_interfaces}")
    
    # Monitor all interfaces in parallel
    with ThreadPoolExecutor(max_workers=len(active_interfaces)) as executor:
        futures = {}
        for iface in active_interfaces:
            future = executor.submit(
                detect_loops_lightweight,
                timeout=timeout,
                threshold=threshold,
                iface=iface,
                use_sampling=True
            )
            futures[iface] = future
        
        # Collect results from all interfaces
        all_results = {}
        for iface, future in futures.items():
            try:
                result = future.result(timeout=timeout + 5)
                all_results[iface] = result
            except Exception as e:
                print(f"⚠️ Error monitoring {iface}: {e}")
                all_results[iface] = None
    
    # Aggregate results across all interfaces
    return aggregate_multi_interface_results(all_results)


def aggregate_multi_interface_results(all_results):
    """
    Combine loop detection results from multiple interfaces.
    Identifies cross-interface loops and network-wide issues.
    """
    aggregated = {
        "total_packets": 0,
        "interfaces_monitored": [],
        "loops_by_interface": {},
        "cross_interface_loops": [],
        "global_offenders": {},
        "max_severity": 0.0,
        "overall_status": "clean",
        "cross_subnet_detected": False,
        "unique_subnets": set(),
        "unique_macs": set()
    }
    
    # Process each interface's results
    for iface, result in all_results.items():
        if result is None:
            continue
        
        total, offenders, stats, status, severity, metrics = result
        
        aggregated["total_packets"] += total
        aggregated["interfaces_monitored"].append(iface)
        aggregated["loops_by_interface"][iface] = {
            "status": status,
            "severity": severity,
            "offenders": offenders,
            "packets": total
        }
        
        # Track global offenders (MACs appearing on multiple interfaces)
        for mac in offenders:
            if mac not in aggregated["global_offenders"]:
                aggregated["global_offenders"][mac] = {
                    "interfaces": [],
                    "subnets": set(),
                    "total_severity": 0.0
                }
            
            aggregated["global_offenders"][mac]["interfaces"].append(iface)
            aggregated["global_offenders"][mac]["total_severity"] += stats.get(mac, {}).get("severity", 0)
            
            # Track subnets
            mac_subnets = stats.get(mac, {}).get("subnets", [])
            for subnet in mac_subnets:
                aggregated["global_offenders"][mac]["subnets"].add(subnet)
                aggregated["unique_subnets"].add(subnet)
        
        # Track all unique MACs and subnets
        aggregated["unique_macs"].update(stats.keys())
        for mac_stats in stats.values():
            aggregated["unique_subnets"].update(mac_stats.get("subnets", []))
        
        # Update max severity
        if severity > aggregated["max_severity"]:
            aggregated["max_severity"] = severity
        
        # Check for cross-subnet activity
        if metrics.get("cross_subnet_detected", False):
            aggregated["cross_subnet_detected"] = True
    
    # Identify cross-interface loops (same MAC on multiple interfaces)
    for mac, info in aggregated["global_offenders"].items():
        if len(info["interfaces"]) > 1:
            aggregated["cross_interface_loops"].append({
                "mac": mac,
                "interfaces": info["interfaces"],
                "subnets": list(info["subnets"]),
                "severity": info["total_severity"]
            })
    
    # Determine overall status
    if aggregated["max_severity"] > 70 or len(aggregated["cross_interface_loops"]) > 0:
        aggregated["overall_status"] = "loop_detected"
    elif aggregated["max_severity"] > 40:
        aggregated["overall_status"] = "suspicious"
    else:
        aggregated["overall_status"] = "clean"
    
    return aggregated


# Update dashboard to use multi-interface detection
def _run_loop_detection_multi_interface(self):
    """Enhanced background loop detection across all network interfaces."""
    while self.loop_detection_running and self.app_running:
        try:
            # Run multi-interface detection
            results = detect_loops_multi_interface(
                timeout=5,
                threshold=30
            )
            
            # Save aggregated results
            from db import save_loop_detection
            detection_id = save_loop_detection(
                total_packets=results["total_packets"],
                offenders=list(results["global_offenders"].keys()),
                stats=results["loops_by_interface"],
                status=results["overall_status"],
                severity_score=results["max_severity"],
                interface=", ".join(results["interfaces_monitored"]),
                duration=5,
                efficiency_metrics={
                    "interfaces_monitored": len(results["interfaces_monitored"]),
                    "cross_interface_loops": len(results["cross_interface_loops"]),
                    "unique_subnets": len(results["unique_subnets"]),
                    "unique_macs": len(results["unique_macs"]),
                    "cross_subnet_detected": results["cross_subnet_detected"]
                }
            )
            
            # Alert for cross-interface loops
            if results["cross_interface_loops"]:
                print(f"⚠️ CROSS-INTERFACE LOOP DETECTED!")
                for loop in results["cross_interface_loops"]:
                    print(f"  • MAC {loop['mac']} on interfaces: {loop['interfaces']}")
                    print(f"    Subnets: {loop['subnets']}, Severity: {loop['severity']:.2f}")
            
            # Send notifications
            if results["overall_status"] in ["loop_detected", "suspicious"]:
                notify_loop_detected(
                    results["max_severity"],
                    list(results["global_offenders"].keys()),
                    ", ".join(results["interfaces_monitored"])
                )
            
            # Wait for next interval
            time.sleep(self.loop_detection_interval)
            
        except Exception as e:
            print(f"❌ Multi-interface loop detection error: {e}")
            time.sleep(self.loop_detection_interval)
```

### Benefits:
✅ Monitors ALL network interfaces simultaneously  
✅ Detects loops across different APs/subnets  
✅ Identifies cross-interface loops (same MAC on multiple segments)  
✅ Provides network-wide visibility  
✅ Aggregates results for comprehensive analysis  

### Performance Considerations:
- Uses ThreadPoolExecutor for parallel monitoring
- Each interface gets its own thread
- Results aggregated efficiently
- Scales to 10-20 interfaces easily

---

## Option 2: SNMP-Based Monitoring (Enterprise Grade)

For true enterprise-level multi-AP monitoring:

```python
from pysnmp.hlapi import *

def detect_loops_via_snmp(ap_list):
    """
    Query APs/switches via SNMP for loop indicators.
    Much more reliable for enterprise environments.
    """
    loop_indicators = []
    
    for ap in ap_list:
        try:
            # Query STP port state
            stp_state = get_snmp_value(
                ap['ip'],
                community='public',
                oid='1.3.6.1.2.1.17.2.15.1.3'  # dot1dStpPortState
            )
            
            # Query error counters
            errors = get_snmp_value(
                ap['ip'],
                oid='1.3.6.1.2.1.2.2.1.14'  # ifInErrors
            )
            
            # Query broadcast storm detection
            broadcasts = get_snmp_value(
                ap['ip'],
                oid='1.3.6.1.2.1.31.1.1.1.9'  # ifHCOutBroadcastPkts
            )
            
            # Analyze for loop indicators
            if is_loop_detected(stp_state, errors, broadcasts):
                loop_indicators.append({
                    'ap': ap['name'],
                    'ip': ap['ip'],
                    'stp_state': stp_state,
                    'errors': errors,
                    'broadcasts': broadcasts
                })
                
        except Exception as e:
            print(f"SNMP query failed for {ap['name']}: {e}")
    
    return loop_indicators
```

### Benefits:
✅ Direct query of AP/switch status  
✅ More reliable than passive sniffing  
✅ Lower CPU usage  
✅ Industry-standard approach  
✅ Works with any SNMP-enabled device  

### Requirements:
- SNMP access to APs/switches
- Network credentials
- PyS NMP library
- Understanding of MIB structure

---

## Option 3: Hybrid Approach (Best of Both Worlds)

Combine passive monitoring + SNMP + multi-interface:

```python
def detect_loops_hybrid(ap_list, monitor_interfaces=True, use_snmp=True):
    """
    Comprehensive loop detection using multiple methods.
    """
    results = {
        "passive_monitoring": None,
        "snmp_monitoring": None,
        "combined_assessment": None
    }
    
    # 1. Multi-interface passive monitoring
    if monitor_interfaces:
        results["passive_monitoring"] = detect_loops_multi_interface(
            timeout=5,
            threshold=30
        )
    
    # 2. SNMP-based active monitoring
    if use_snmp and ap_list:
        results["snmp_monitoring"] = detect_loops_via_snmp(ap_list)
    
    # 3. Correlate results for high-confidence detection
    results["combined_assessment"] = correlate_detection_results(
        results["passive_monitoring"],
        results["snmp_monitoring"]
    )
    
    return results
```

---

## Recommended Deployment Strategy

### **For Small Networks (1-5 APs):**
✅ Current implementation is **adequate**  
- Single interface monitoring sufficient  
- Most loops will be visible  
- Manual intervention acceptable  

### **For Medium Networks (5-20 APs):**
⚠️ Use **Multi-Interface Monitoring** (Option 1)  
- Monitor all interfaces  
- Aggregate results  
- Automated alerting  
- Good balance of complexity/effectiveness  

### **For Enterprise Networks (20+ APs):**
🏢 Use **Hybrid Approach** (Option 3)  
- Multi-interface passive monitoring  
- SNMP active monitoring  
- Centralized management  
- Integration with network management system  
- Professional-grade solution  

---

## Bottom Line

**Can your current system detect loops in multi-AP networks?**

**Answer: Yes, BUT with limitations:**

✅ **What it CAN do:**
- Detect loops that affect the monitored interface
- Track cross-subnet activity
- Identify MAC addresses causing issues
- Handle broadcast storms

❌ **What it CANNOT do reliably:**
- Monitor loops on other network segments
- Detect quiet loops (low broadcast traffic)
- Provide network-wide visibility
- Scale to large enterprise environments

**Recommendation:** Implement **Multi-Interface Monitoring** (Option 1) for significantly better coverage in multi-AP environments. It's a reasonable enhancement that maintains your current architecture while dramatically improving effectiveness.

Would you like me to implement the multi-interface monitoring enhancement?
