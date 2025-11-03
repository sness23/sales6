#!/usr/bin/env python3
"""
Performance Testing Framework for Immutable Event Log

Tests write latency, throughput, read performance, and verification speed
with realistic event data at various scales.
"""

import json
import time
import statistics
import random
import string
import shutil
from pathlib import Path
from typing import List, Dict, Any, Callable
from datetime import datetime, timezone
from dataclasses import dataclass, asdict

from immutable_log import ImmutableLog


# ============================================================================
# Test Data Generators
# ============================================================================

class DataGenerator:
    """Generates realistic test data for various event types."""

    @staticmethod
    def random_string(length: int) -> str:
        """Generate a random string."""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    @staticmethod
    def random_email() -> str:
        """Generate a random email."""
        domains = ["example.com", "test.com", "demo.com", "company.com"]
        return f"{DataGenerator.random_string(8)}@{random.choice(domains)}"

    @staticmethod
    def user_event(size: str = "small") -> Dict[str, Any]:
        """Generate a user event."""
        actions = ["login", "logout", "view_page", "click_button", "submit_form", "search"]
        event = {
            "user_id": f"user_{random.randint(1, 10000)}",
            "action": random.choice(actions),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ip_address": f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}",
            "session_id": DataGenerator.random_string(32),
        }

        # Add extra data based on size
        if size in ["medium", "large", "huge"]:
            event["metadata"] = {
                "browser": random.choice(["Chrome", "Firefox", "Safari", "Edge"]),
                "os": random.choice(["Windows", "macOS", "Linux", "iOS", "Android"]),
                "device": random.choice(["desktop", "mobile", "tablet"]),
                "referrer": f"https://{DataGenerator.random_string(10)}.com",
            }

        if size in ["large", "huge"]:
            event["attributes"] = {
                f"attr_{i}": DataGenerator.random_string(20)
                for i in range(10)
            }

        if size == "huge":
            # Add a large payload (simulating document content, etc.)
            event["payload"] = DataGenerator.random_string(10000)

        return event

    @staticmethod
    def order_event(size: str = "small") -> Dict[str, Any]:
        """Generate an order event."""
        statuses = ["created", "paid", "shipped", "delivered", "cancelled"]
        num_items = 1 if size == "small" else random.randint(2, 20)

        items = [
            {
                "sku": f"SKU-{DataGenerator.random_string(8)}",
                "quantity": random.randint(1, 5),
                "price": round(random.uniform(9.99, 999.99), 2),
            }
            for _ in range(num_items)
        ]

        event = {
            "order_id": f"ORD-{random.randint(100000, 999999)}",
            "customer_id": f"cust_{random.randint(1, 10000)}",
            "status": random.choice(statuses),
            "items": items,
            "total": round(sum(item["price"] * item["quantity"] for item in items), 2),
            "currency": "USD",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if size in ["medium", "large", "huge"]:
            event["shipping_address"] = {
                "street": f"{random.randint(1, 9999)} {DataGenerator.random_string(10)} St",
                "city": DataGenerator.random_string(12),
                "state": DataGenerator.random_string(2).upper(),
                "zip": f"{random.randint(10000, 99999)}",
                "country": "USA",
            }

        if size in ["large", "huge"]:
            event["payment_method"] = {
                "type": "card",
                "last4": f"{random.randint(1000, 9999)}",
                "brand": random.choice(["visa", "mastercard", "amex"]),
            }

        return event

    @staticmethod
    def chat_message(size: str = "small") -> Dict[str, Any]:
        """Generate a chat message event."""
        message_lengths = {
            "small": 50,
            "medium": 200,
            "large": 1000,
            "huge": 5000,
        }

        return {
            "message_id": f"msg_{DataGenerator.random_string(16)}",
            "channel_id": f"channel_{random.randint(1, 100)}",
            "user_id": f"user_{random.randint(1, 10000)}",
            "message": DataGenerator.random_string(message_lengths.get(size, 50)),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mentions": [f"user_{random.randint(1, 10000)}" for _ in range(random.randint(0, 3))],
        }

    @staticmethod
    def document_update(size: str = "small") -> Dict[str, Any]:
        """Generate a document update event (like Quip/Notion)."""
        content_lengths = {
            "small": 100,
            "medium": 500,
            "large": 2000,
            "huge": 10000,
        }

        return {
            "document_id": f"doc_{DataGenerator.random_string(16)}",
            "user_id": f"user_{random.randint(1, 10000)}",
            "operation": random.choice(["insert", "delete", "format", "comment"]),
            "position": random.randint(0, 10000),
            "content": DataGenerator.random_string(content_lengths.get(size, 100)),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": random.randint(1, 1000),
        }


# ============================================================================
# Performance Metrics
# ============================================================================

@dataclass
class PerformanceMetrics:
    """Container for performance test results."""
    test_name: str
    operation: str
    count: int
    duration_seconds: float
    throughput_ops_per_sec: float
    latencies_ms: List[float]
    min_ms: float
    max_ms: float
    mean_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float

    @classmethod
    def calculate(cls, test_name: str, operation: str, latencies: List[float]):
        """Calculate metrics from a list of latencies (in seconds)."""
        if not latencies:
            raise ValueError("No latencies to calculate metrics from")

        latencies_ms = [l * 1000 for l in latencies]  # Convert to milliseconds
        sorted_latencies = sorted(latencies_ms)
        count = len(latencies)
        duration = sum(latencies)

        return cls(
            test_name=test_name,
            operation=operation,
            count=count,
            duration_seconds=duration,
            throughput_ops_per_sec=count / duration if duration > 0 else 0,
            latencies_ms=latencies_ms,
            min_ms=min(latencies_ms),
            max_ms=max(latencies_ms),
            mean_ms=statistics.mean(latencies_ms),
            p50_ms=sorted_latencies[int(count * 0.50)],
            p95_ms=sorted_latencies[int(count * 0.95)],
            p99_ms=sorted_latencies[int(count * 0.99)],
        )

    def print_summary(self):
        """Print a formatted summary of the metrics."""
        print(f"\n{'=' * 70}")
        print(f"Test: {self.test_name}")
        print(f"Operation: {self.operation}")
        print(f"{'=' * 70}")
        print(f"Operations:     {self.count:,}")
        print(f"Duration:       {self.duration_seconds:.2f}s")
        print(f"Throughput:     {self.throughput_ops_per_sec:,.0f} ops/sec")
        print(f"\nLatency (ms):")
        print(f"  Min:          {self.min_ms:.3f}")
        print(f"  Mean:         {self.mean_ms:.3f}")
        print(f"  P50:          {self.p50_ms:.3f}")
        print(f"  P95:          {self.p95_ms:.3f}")
        print(f"  P99:          {self.p99_ms:.3f}")
        print(f"  Max:          {self.max_ms:.3f}")


# ============================================================================
# Performance Tests
# ============================================================================

class PerformanceTest:
    """Performance testing framework."""

    def __init__(self, test_dir: str = "perf_logs"):
        self.test_dir = Path(test_dir)
        self.log = ImmutableLog(str(self.test_dir))
        self.results: List[PerformanceMetrics] = []

    def cleanup(self):
        """Remove test directory."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def setup(self):
        """Setup test environment."""
        self.cleanup()
        self.test_dir.mkdir(exist_ok=True)

    def test_append_latency(
        self,
        partition: str,
        data_generator: Callable,
        count: int,
        size: str = "small",
        test_name: str = None
    ) -> PerformanceMetrics:
        """Test append operation latency."""
        test_name = test_name or f"Append Latency ({size} events)"
        print(f"\n🔬 Running: {test_name}")
        print(f"   Appending {count:,} events to partition '{partition}'...")

        latencies = []
        for i in range(count):
            data = data_generator(size)

            start = time.perf_counter()
            self.log.append(partition, data)
            end = time.perf_counter()

            latencies.append(end - start)

            # Progress indicator
            if (i + 1) % max(1, count // 10) == 0:
                print(f"   Progress: {i + 1:,}/{count:,} ({(i + 1) / count * 100:.0f}%)")

        metrics = PerformanceMetrics.calculate(test_name, "append", latencies)
        self.results.append(metrics)
        return metrics

    def test_batch_throughput(
        self,
        partition: str,
        data_generator: Callable,
        count: int,
        size: str = "small",
        test_name: str = None
    ) -> PerformanceMetrics:
        """Test batch write throughput (measure total time, not individual ops)."""
        test_name = test_name or f"Batch Throughput ({size} events)"
        print(f"\n🔬 Running: {test_name}")
        print(f"   Writing {count:,} events to partition '{partition}'...")

        # Pre-generate all data
        data_items = [data_generator(size) for _ in range(count)]

        # Time the batch write
        start = time.perf_counter()
        for data in data_items:
            self.log.append(partition, data)
        end = time.perf_counter()

        # Create synthetic latencies for metrics calculation
        total_time = end - start
        avg_latency = total_time / count
        latencies = [avg_latency] * count  # Approximate for metrics

        metrics = PerformanceMetrics.calculate(test_name, "batch_append", latencies)
        self.results.append(metrics)
        return metrics

    def test_read_throughput(self, partition: str, test_name: str = None) -> PerformanceMetrics:
        """Test sequential read throughput."""
        test_name = test_name or f"Read Throughput"
        print(f"\n🔬 Running: {test_name}")
        print(f"   Reading all events from partition '{partition}'...")

        path = self.log._get_partition_path(partition)
        if not path.exists():
            print(f"   ⚠️  Partition '{partition}' doesn't exist, skipping read test")
            return None

        latencies = []
        count = 0

        start_all = time.perf_counter()
        with open(path, 'r') as f:
            for line in f:
                start = time.perf_counter()
                entry = json.loads(line.strip())
                end = time.perf_counter()

                latencies.append(end - start)
                count += 1
        end_all = time.perf_counter()

        print(f"   Read {count:,} entries in {end_all - start_all:.2f}s")

        metrics = PerformanceMetrics.calculate(test_name, "read", latencies)
        self.results.append(metrics)
        return metrics

    def test_verify_performance(self, partition: str, test_name: str = None) -> Dict[str, Any]:
        """Test verify operation performance."""
        test_name = test_name or f"Verify Performance"
        print(f"\n🔬 Running: {test_name}")
        print(f"   Verifying partition '{partition}'...")

        start = time.perf_counter()
        valid = self.log.verify(partition)
        end = time.perf_counter()

        duration = end - start

        # Count entries
        path = self.log._get_partition_path(partition)
        entry_count = sum(1 for _ in open(path, 'r'))

        result = {
            "test_name": test_name,
            "partition": partition,
            "entry_count": entry_count,
            "duration_seconds": duration,
            "throughput_entries_per_sec": entry_count / duration if duration > 0 else 0,
            "valid": valid,
        }

        print(f"   Verified {entry_count:,} entries in {duration:.2f}s")
        print(f"   Throughput: {result['throughput_entries_per_sec']:,.0f} entries/sec")
        print(f"   Valid: {valid}")

        return result

    def test_multi_partition_writes(
        self,
        num_partitions: int,
        events_per_partition: int,
        data_generator: Callable,
        size: str = "small",
        test_name: str = None
    ) -> PerformanceMetrics:
        """Test writing to multiple partitions (simulates concurrent workload)."""
        test_name = test_name or f"Multi-Partition Writes ({num_partitions} partitions)"
        print(f"\n🔬 Running: {test_name}")
        print(f"   Writing {events_per_partition:,} events to {num_partitions} partitions...")

        latencies = []
        total_ops = num_partitions * events_per_partition

        for i in range(events_per_partition):
            for p in range(num_partitions):
                partition = f"partition_{p}"
                data = data_generator(size)

                start = time.perf_counter()
                self.log.append(partition, data)
                end = time.perf_counter()

                latencies.append(end - start)

            # Progress indicator
            ops_done = (i + 1) * num_partitions
            if ops_done % max(1, total_ops // 10) == 0:
                print(f"   Progress: {ops_done:,}/{total_ops:,} ({ops_done / total_ops * 100:.0f}%)")

        metrics = PerformanceMetrics.calculate(test_name, "multi_partition_append", latencies)
        self.results.append(metrics)
        return metrics

    def print_all_results(self):
        """Print summary of all test results."""
        print(f"\n{'=' * 70}")
        print(f"PERFORMANCE TEST SUMMARY")
        print(f"{'=' * 70}")

        for metrics in self.results:
            metrics.print_summary()

    def export_results(self, filename: str = "perf_results.json"):
        """Export results to JSON file."""
        results_data = [
            {
                **asdict(m),
                "latencies_ms": None,  # Don't export full latency list
            }
            for m in self.results
        ]

        with open(filename, 'w') as f:
            json.dump(results_data, f, indent=2)

        print(f"\n📊 Results exported to {filename}")


# ============================================================================
# Test Suites
# ============================================================================

def run_quick_test():
    """Quick smoke test (~10 seconds)."""
    print("=" * 70)
    print("QUICK TEST SUITE")
    print("=" * 70)

    perf = PerformanceTest()
    perf.setup()

    # Test different event types and sizes
    perf.test_append_latency("users", DataGenerator.user_event, 100, "small", "Quick: User Events (small)")
    perf.test_append_latency("orders", DataGenerator.order_event, 100, "medium", "Quick: Order Events (medium)")
    perf.test_read_throughput("users", "Quick: Read Users")
    perf.test_verify_performance("users", "Quick: Verify Users")

    perf.print_all_results()
    perf.export_results("perf_results_quick.json")


def run_standard_test():
    """Standard performance test (~1-2 minutes)."""
    print("=" * 70)
    print("STANDARD TEST SUITE")
    print("=" * 70)

    perf = PerformanceTest()
    perf.setup()

    # Test different event types
    perf.test_append_latency("users", DataGenerator.user_event, 1000, "small", "Users: Small Events")
    perf.test_append_latency("orders", DataGenerator.order_event, 1000, "medium", "Orders: Medium Events")
    perf.test_append_latency("messages", DataGenerator.chat_message, 1000, "small", "Messages: Small Events")
    perf.test_append_latency("docs", DataGenerator.document_update, 1000, "large", "Documents: Large Events")

    # Test batch throughput
    perf.test_batch_throughput("users_batch", DataGenerator.user_event, 5000, "small", "Batch: 5K Small Events")

    # Test multi-partition
    perf.test_multi_partition_writes(5, 200, DataGenerator.user_event, "small", "Multi-Partition: 5 partitions")

    # Test reads
    perf.test_read_throughput("users", "Read: Users")
    perf.test_read_throughput("users_batch", "Read: Users Batch")

    # Test verify
    perf.test_verify_performance("users", "Verify: Users (1K entries)")
    perf.test_verify_performance("users_batch", "Verify: Users Batch (5K entries)")

    perf.print_all_results()
    perf.export_results("perf_results_standard.json")


def run_stress_test():
    """Stress test with large volumes (~5-10 minutes)."""
    print("=" * 70)
    print("STRESS TEST SUITE")
    print("=" * 70)

    perf = PerformanceTest()
    perf.setup()

    # Large volume tests
    perf.test_batch_throughput("stress_small", DataGenerator.user_event, 10000, "small", "Stress: 10K Small Events")
    perf.test_batch_throughput("stress_medium", DataGenerator.order_event, 10000, "medium", "Stress: 10K Medium Events")
    perf.test_batch_throughput("stress_large", DataGenerator.document_update, 5000, "large", "Stress: 5K Large Events")
    perf.test_batch_throughput("stress_huge", DataGenerator.document_update, 1000, "huge", "Stress: 1K Huge Events")

    # Multi-partition stress
    perf.test_multi_partition_writes(10, 500, DataGenerator.user_event, "small", "Stress: 10 partitions, 500 each")

    # Read and verify large datasets
    perf.test_read_throughput("stress_small", "Stress Read: 10K entries")
    perf.test_verify_performance("stress_small", "Stress Verify: 10K entries")

    perf.print_all_results()
    perf.export_results("perf_results_stress.json")


def run_size_comparison():
    """Compare performance across different event sizes."""
    print("=" * 70)
    print("SIZE COMPARISON TEST")
    print("=" * 70)

    perf = PerformanceTest()
    perf.setup()

    sizes = ["small", "medium", "large", "huge"]
    for size in sizes:
        perf.test_append_latency(f"size_{size}", DataGenerator.user_event, 500, size, f"Size Test: {size}")

    perf.print_all_results()
    perf.export_results("perf_results_size.json")


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Performance Testing Framework for Immutable Event Log",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "suite",
        choices=["quick", "standard", "stress", "size"],
        help="Test suite to run"
    )

    args = parser.parse_args()

    # Run the selected test suite
    if args.suite == "quick":
        run_quick_test()
    elif args.suite == "standard":
        run_standard_test()
    elif args.suite == "stress":
        run_stress_test()
    elif args.suite == "size":
        run_size_comparison()


if __name__ == "__main__":
    main()
