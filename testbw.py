from network_utils import get_bandwidth
import time

# replace these with your actual router IPs
routers = ["192.168.1.1", "192.168.1.2"]

while True:
    for ip in routers:
        result = get_bandwidth(ip=ip)
        print(f"Router {ip} -> Download: {result['download']} Kbps | Upload: {result['upload']} Kbps")
    time.sleep(5)
