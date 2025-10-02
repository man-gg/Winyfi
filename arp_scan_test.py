# arp_table_test.py
import os

def get_arp_table():
    output = os.popen("arp -a").read()
    print(output)

if __name__ == "__main__":
    get_arp_table()
