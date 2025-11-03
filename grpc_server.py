#!/usr/bin/env python3
"""
gRPC Server for Immutable Event Log

Wraps the ImmutableLog class and exposes it via gRPC.
"""

import json
import time
import signal
import sys
from concurrent import futures
from typing import Iterator

import grpc
import immutable_log_pb2
import immutable_log_pb2_grpc
from immutable_log import ImmutableLog


class ImmutableLogServicer(immutable_log_pb2_grpc.ImmutableLogServiceServicer):
    """gRPC service implementation for ImmutableLog."""

    def __init__(self, base_dir: str = "logs"):
        self.log = ImmutableLog(base_dir)
        print(f"Initialized ImmutableLog with base_dir: {base_dir}")

    def Append(self, request, context):
        """Append an entry to the log."""
        try:
            # Parse the data as JSON
            try:
                data = json.loads(request.data)
            except json.JSONDecodeError as e:
                return immutable_log_pb2.AppendResponse(
                    success=False,
                    error=f"Invalid JSON data: {e}"
                )

            # Append to log
            entry = self.log.append(request.partition, data)

            return immutable_log_pb2.AppendResponse(
                seq=entry["seq"],
                timestamp=entry["ts"],
                hash=entry["hash"],
                success=True
            )

        except Exception as e:
            return immutable_log_pb2.AppendResponse(
                success=False,
                error=str(e)
            )

    def Read(self, request, context) -> Iterator[immutable_log_pb2.ReadResponse]:
        """Stream entries from the log."""
        try:
            path = self.log._get_partition_path(request.partition)

            if not path.exists():
                context.abort(grpc.StatusCode.NOT_FOUND, f"Partition '{request.partition}' not found")
                return

            start_seq = request.start_seq if request.HasField('start_seq') else 0
            limit = request.limit if request.HasField('limit') else None

            count = 0
            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    entry = json.loads(line)

                    # Skip until we reach start_seq
                    if entry["seq"] < start_seq:
                        continue

                    # Check limit
                    if limit is not None and count >= limit:
                        break

                    yield immutable_log_pb2.ReadResponse(
                        seq=entry["seq"],
                        timestamp=entry["ts"],
                        partition=entry["partition"],
                        prev_hash=entry["prev_hash"],
                        data=json.dumps(entry["data"]),
                        hash=entry["hash"]
                    )

                    count += 1

        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def Verify(self, request, context):
        """Verify the integrity of a partition."""
        try:
            path = self.log._get_partition_path(request.partition)

            if not path.exists():
                return immutable_log_pb2.VerifyResponse(
                    valid=False,
                    entries_verified=0,
                    error=f"Partition '{request.partition}' not found"
                )

            # Verify the chain
            prev_hash = ImmutableLog.GENESIS_HASH
            entry_count = 0

            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    entry = json.loads(line)

                    # Verify sequence
                    if entry["seq"] != entry_count:
                        return immutable_log_pb2.VerifyResponse(
                            valid=False,
                            entries_verified=entry_count,
                            error=f"Sequence mismatch at entry {entry_count}"
                        )

                    # Verify previous hash
                    if entry["prev_hash"] != prev_hash:
                        return immutable_log_pb2.VerifyResponse(
                            valid=False,
                            entries_verified=entry_count,
                            error=f"Hash chain broken at entry {entry_count}"
                        )

                    # Verify current hash
                    expected_hash = self.log._calculate_hash(entry)
                    if entry["hash"] != expected_hash:
                        return immutable_log_pb2.VerifyResponse(
                            valid=False,
                            entries_verified=entry_count,
                            error=f"Hash mismatch at entry {entry_count}"
                        )

                    prev_hash = entry["hash"]
                    entry_count += 1

            return immutable_log_pb2.VerifyResponse(
                valid=True,
                entries_verified=entry_count,
                final_hash=prev_hash
            )

        except Exception as e:
            return immutable_log_pb2.VerifyResponse(
                valid=False,
                entries_verified=0,
                error=str(e)
            )

    def ListPartitions(self, request, context):
        """List all available partitions."""
        try:
            partitions = self.log.list_partitions()
            return immutable_log_pb2.ListPartitionsResponse(partitions=partitions)
        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def GetLastEntry(self, request, context):
        """Get the last entry from a partition."""
        try:
            entry = self.log._get_last_entry(request.partition)

            if entry is None:
                return immutable_log_pb2.GetLastEntryResponse(found=False)

            return immutable_log_pb2.GetLastEntryResponse(
                found=True,
                seq=entry["seq"],
                timestamp=entry["ts"],
                partition=entry["partition"],
                prev_hash=entry["prev_hash"],
                data=json.dumps(entry["data"]),
                hash=entry["hash"]
            )

        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def Tail(self, request, context) -> Iterator[immutable_log_pb2.TailResponse]:
        """Stream entries from the log (like tail -f)."""
        try:
            path = self.log._get_partition_path(request.partition)

            if not path.exists():
                context.abort(grpc.StatusCode.NOT_FOUND, f"Partition '{request.partition}' not found")
                return

            start_seq = request.start_seq if request.HasField('start_seq') else 0

            # First, stream existing entries
            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    entry = json.loads(line)

                    # Skip until we reach start_seq
                    if entry["seq"] < start_seq:
                        continue

                    yield immutable_log_pb2.TailResponse(
                        seq=entry["seq"],
                        timestamp=entry["ts"],
                        partition=entry["partition"],
                        prev_hash=entry["prev_hash"],
                        data=json.dumps(entry["data"]),
                        hash=entry["hash"]
                    )

            # If follow mode, keep streaming new entries
            if request.follow:
                with open(path, 'r') as f:
                    # Seek to end
                    f.seek(0, 2)

                    while context.is_active():
                        line = f.readline()
                        if line:
                            line = line.strip()
                            if line:
                                entry = json.loads(line)
                                yield immutable_log_pb2.TailResponse(
                                    seq=entry["seq"],
                                    timestamp=entry["ts"],
                                    partition=entry["partition"],
                                    prev_hash=entry["prev_hash"],
                                    data=json.dumps(entry["data"]),
                                    hash=entry["hash"]
                                )
                        else:
                            time.sleep(0.1)

        except Exception as e:
            if context.is_active():
                context.abort(grpc.StatusCode.INTERNAL, str(e))


def serve(port: int = 50051, base_dir: str = "logs", max_workers: int = 10):
    """Start the gRPC server."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))

    servicer = ImmutableLogServicer(base_dir)
    immutable_log_pb2_grpc.add_ImmutableLogServiceServicer_to_server(servicer, server)

    server.add_insecure_port(f'[::]:{port}')
    server.start()

    print(f"Server started on port {port}")
    print(f"Base directory: {base_dir}")
    print(f"Worker threads: {max_workers}")
    print("Press Ctrl+C to stop...")

    # Handle graceful shutdown
    def handle_sigterm(*_):
        print("\nShutting down gracefully...")
        server.stop(grace=5)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigterm)
    signal.signal(signal.SIGTERM, handle_sigterm)

    server.wait_for_termination()


def main():
    """CLI interface for the gRPC server."""
    import argparse

    parser = argparse.ArgumentParser(description="Immutable Event Log - gRPC Server")
    parser.add_argument(
        "--port",
        type=int,
        default=50051,
        help="Port to listen on (default: 50051)"
    )
    parser.add_argument(
        "--dir",
        default="logs",
        help="Base directory for log files (default: logs)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Number of worker threads (default: 10)"
    )

    args = parser.parse_args()

    serve(port=args.port, base_dir=args.dir, max_workers=args.workers)


if __name__ == "__main__":
    main()
