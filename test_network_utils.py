import unittest
from network_utils import ping_latency, DynamicPingManager

class TestDynamicPingManager(unittest.TestCase):
    def test_ping_interval_high_bandwidth(self):
        manager = DynamicPingManager()
        # Simulate high bandwidth
        manager.update(latency=30, bandwidth=25)
        self.assertEqual(manager.current_interval, manager.max_interval)

    def test_ping_interval_high_latency(self):
        manager = DynamicPingManager()
        # Simulate high latency
        for _ in range(manager.window):
            manager.update(latency=200, bandwidth=5)
        self.assertEqual(manager.current_interval, manager.max_interval)

    def test_ping_interval_normal(self):
        manager = DynamicPingManager()
        # Simulate normal conditions
        for _ in range(manager.window):
            manager.update(latency=40, bandwidth=5)
        self.assertEqual(manager.current_interval, manager.normal_interval)

if __name__ == "__main__":
    unittest.main()
