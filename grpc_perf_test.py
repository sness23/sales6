#!/usr/bin/env python3
"""
Performance Testing for gRPC Immutable Event Log

Comprehensive benchmarks comparing local vs gRPC performance:
- Append latency
- Read throughput
- Verify performance
- Streaming (tail) performance
"""

import json
import time
import sys
import statistics
from typing import List, Dict, Any
from datetime import datetime

import grpc
from grpc_client import ImmutableLogClient
from immutable_log import ImmutableLog


class PerfTest:
    """Performance testing framework for ImmutableLog."""

    def __init__(self):
        self.results: List[Dict[str, Any]] = []

    def format_time(self, seconds: float) -> str:
        """Format time in appropriate units."""
        if seconds < 0.001:
            return f"{seconds * 1_000_000:.2f}µs"
        elif seconds < 1.0:
            return f"{seconds * 1000:.2f}ms"
        else:
            return f"{seconds:.2f}s"

    def format_rate(self, ops_per_sec: float) -> str:
        """Format operations per second."""
        if ops_per_sec >= 1000:
            return f"{ops_per_sec / 1000:.2f}K ops/sec"
        else:
            return f"{ops_per_sec:.2f} ops/sec"

    def print_header(self, title: str):
        """Print a section header."""
        print(f"\n{'=' * 70}")
        print(f"  {title}")
        print(f"{'=' * 70}")

    def print_result(self, name: str, duration: float, ops: int):
        """Print a test result."""
        ops_per_sec = ops / duration if duration > 0 else 0
        avg_latency = duration / ops if ops > 0 else 0

        print(f"\n{name}:")
        print(f"  Duration:    {self.format_time(duration)}")
        print(f"  Operations:  {ops:,}")
        print(f"  Throughput:  {self.format_rate(ops_per_sec)}")
        print(f"  Avg latency: {self.format_time(avg_latency)}")

        self.results.append({
            "name": name,
            "duration": duration,
            "operations": ops,
            "ops_per_sec": ops_per_sec,
            "avg_latency": avg_latency
        })

    def test_local_append(self, log: ImmutableLog, partition: str, n: int):
        """Test local append performance."""
        print("\nRunning local append test...")
        start = time.perf_counter()

        for i in range(n):
            log.append(partition, {"index": i, "test": "data"})

        duration = time.perf_counter() - start
        self.print_result(f"Local Append ({n} ops)", duration, n)

    def test_grpc_append(self, client: ImmutableLogClient, partition: str, n: int):
        """Test gRPC append performance."""
        print("\nRunning gRPC append test...")
        start = time.perf_counter()

        for i in range(n):
            client.append(partition, {"index": i, "test": "data"})

        duration = time.perf_counter() - start
        self.print_result(f"gRPC Append ({n} ops)", duration, n)

    def test_grpc_append_latency(self, client: ImmutableLogClient, partition: str, n: int):
        """Test gRPC append latency distribution."""
        print("\nRunning gRPC append latency test...")
        latencies = []

        for i in range(n):
            start = time.perf_counter()
            client.append(partition, {"index": i, "test": "latency"})
            latency = time.perf_counter() - start
            latencies.append(latency)

        # Calculate statistics
        mean = statistics.mean(latencies)
        median = statistics.median(latencies)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        p99 = sorted(latencies)[int(len(latencies) * 0.99)]
        min_lat = min(latencies)
        max_lat = max(latencies)

        print(f"\ngRPC Append Latency ({n} samples):")
        print(f"  Mean:   {self.format_time(mean)}")
        print(f"  Median: {self.format_time(median)}")
        print(f"  P95:    {self.format_time(p95)}")
        print(f"  P99:    {self.format_time(p99)}")
        print(f"  Min:    {self.format_time(min_lat)}")
        print(f"  Max:    {self.format_time(max_lat)}")

        self.results.append({
            "name": f"gRPC Append Latency ({n} samples)",
            "mean": mean,
            "median": median,
            "p95": p95,
            "p99": p99,
            "min": min_lat,
            "max": max_lat
        })

    def test_local_read(self, log: ImmutableLog, partition: str):
        """Test local read performance."""
        print("\nRunning local read test...")

        # Count entries first
        path = log._get_partition_path(partition)
        with open(path, 'r') as f:
            n = sum(1 for line in f if line.strip())

        # Read all entries
        start = time.perf_counter()
        count = 0
        with open(path, 'r') as f:
            for line in f:
                if line.strip():
                    json.loads(line)
                    count += 1

        duration = time.perf_counter() - start
        self.print_result(f"Local Read ({count} entries)", duration, count)

    def test_grpc_read(self, client: ImmutableLogClient, partition: str):
        """Test gRPC read performance."""
        print("\nRunning gRPC read test...")

        start = time.perf_counter()
        count = 0
        for entry in client.read(partition):
            count += 1

        duration = time.perf_counter() - start
        self.print_result(f"gRPC Read ({count} entries)", duration, count)

    def test_local_verify(self, log: ImmutableLog, partition: str):
        """Test local verify performance."""
        print("\nRunning local verify test...")

        # Get entry count
        path = log._get_partition_path(partition)
        with open(path, 'r') as f:
            n = sum(1 for line in f if line.strip())

        # Verify
        start = time.perf_counter()

        prev_hash = ImmutableLog.GENESIS_HASH
        entry_count = 0
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                assert entry["seq"] == entry_count
                assert entry["prev_hash"] == prev_hash
                assert entry["hash"] == log._calculate_hash(entry)
                prev_hash = entry["hash"]
                entry_count += 1

        duration = time.perf_counter() - start
        self.print_result(f"Local Verify ({entry_count} entries)", duration, entry_count)

    def test_grpc_verify(self, client: ImmutableLogClient, partition: str):
        """Test gRPC verify performance."""
        print("\nRunning gRPC verify test...")

        start = time.perf_counter()
        result = client.verify(partition)
        duration = time.perf_counter() - start

        assert result["valid"], f"Verification failed: {result.get('error')}"

        self.print_result(
            f"gRPC Verify ({result['entries_verified']} entries)",
            duration,
            result['entries_verified']
        )

    def generate_report(self):
        """Generate a summary report."""
        self.print_header("Performance Test Summary")

        # Group results by category
        local_results = [r for r in self.results if r["name"].startswith("Local")]
        grpc_results = [r for r in self.results if r["name"].startswith("gRPC")]

        print("\nLocal (Direct File Access):")
        for r in local_results:
            if "ops_per_sec" in r:
                print(f"  {r['name']:40} {self.format_rate(r['ops_per_sec']):>20}")

        print("\ngRPC (Network):")
        for r in grpc_results:
            if "ops_per_sec" in r:
                print(f"  {r['name']:40} {self.format_rate(r['ops_per_sec']):>20}")

        # Calculate overhead
        print("\nNetwork Overhead:")
        for local in local_results:
            for grpc_r in grpc_results:
                if local["name"].replace("Local", "gRPC").split("(")[0].strip() == \
                   grpc_r["name"].split("(")[0].strip():
                    if "ops_per_sec" in local and "ops_per_sec" in grpc_r:
                        overhead = (local["ops_per_sec"] - grpc_r["ops_per_sec"]) / local["ops_per_sec"] * 100
                        factor = local["ops_per_sec"] / grpc_r["ops_per_sec"] if grpc_r["ops_per_sec"] > 0 else 0
                        print(f"  {grpc_r['name'].split('(')[0].strip():40} {overhead:>6.1f}% slower ({factor:.2f}x)")

        print("\n" + "=" * 70)


def wait_for_server(host: str = "localhost", port: int = 50051, timeout: int = 10) -> bool:
    """Wait for the gRPC server to be ready."""
    print(f"Waiting for server at {host}:{port}...")
    start = time.time()

    while time.time() - start < timeout:
        try:
            with ImmutableLogClient(host=host, port=port, timeout=1) as client:
                client.list_partitions()
                print("✓ Server is ready!")
                return True
        except Exception:
            time.sleep(0.5)

    return False


def main():
    """Run performance tests."""
    import argparse
    import subprocess
    import os
    import signal
    import shutil

    parser = argparse.ArgumentParser(description="gRPC Performance Testing")
    parser.add_argument("--host", default="localhost", help="Server hostname")
    parser.add_argument("--port", type=int, default=50051, help="Server port")
    parser.add_argument("--append-ops", type=int, default=1000, help="Number of append operations")
    parser.add_argument("--latency-samples", type=int, default=100, help="Number of latency samples")
    parser.add_argument("--start-server", action="store_true", help="Start server automatically")
    parser.add_argument("--logs-dir", default="logs_perf_test", help="Directory for test logs")

    args = parser.parse_args()

    # Clean up old test data
    if os.path.exists(args.logs_dir):
        print(f"Cleaning up old test data: {args.logs_dir}")
        shutil.rmtree(args.logs_dir)

    # Start server if requested
    server_process = None
    if args.start_server:
        print(f"\nStarting gRPC server on port {args.port}...")
        server_process = subprocess.Popen(
            [sys.executable, "grpc_server.py", "--port", str(args.port), "--dir", args.logs_dir],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        time.sleep(2)  # Give server time to start

    try:
        # Wait for server to be ready
        if not wait_for_server(args.host, args.port):
            print(f"✗ Server not ready at {args.host}:{args.port}", file=sys.stderr)
            print("  Start the server with: python grpc_server.py", file=sys.stderr)
            return 1

        # Initialize test framework
        perf = PerfTest()
        partition = "perf_test"

        # Create local log instance
        local_log = ImmutableLog(args.logs_dir)

        # Create gRPC client
        client = ImmutableLogClient(host=args.host, port=args.port)
        client.connect()

        try:
            # === Append Performance ===
            perf.print_header("Append Performance")
            perf.test_local_append(local_log, partition + "_local", args.append_ops)
            perf.test_grpc_append(client, partition + "_grpc", args.append_ops)

            # === Latency Distribution ===
            perf.print_header("Latency Distribution")
            perf.test_grpc_append_latency(client, partition + "_latency", args.latency_samples)

            # === Read Performance ===
            perf.print_header("Read Performance")
            perf.test_local_read(local_log, partition + "_local")
            perf.test_grpc_read(client, partition + "_grpc")

            # === Verify Performance ===
            perf.print_header("Verify Performance")
            perf.test_local_verify(local_log, partition + "_local")
            perf.test_grpc_verify(client, partition + "_grpc")

            # === Generate Report ===
            perf.generate_report()

            return 0

        finally:
            client.close()

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n✗ Test failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Clean up server
        if server_process:
            print("\nStopping server...")
            server_process.send_signal(signal.SIGINT)
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()


if __name__ == "__main__":
    sys.exit(main())
