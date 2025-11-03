#!/usr/bin/env python3
"""
gRPC Client Library for Immutable Event Log

Provides an easy-to-use Python client for the ImmutableLog gRPC service.
"""

import json
from typing import Optional, Iterator, Dict, Any, List

import grpc
import immutable_log_pb2
import immutable_log_pb2_grpc


class ImmutableLogClient:
    """Client for the Immutable Event Log gRPC service."""

    def __init__(self, host: str = "localhost", port: int = 50051, timeout: int = 10):
        """
        Initialize the client.

        Args:
            host: Server hostname
            port: Server port
            timeout: Default timeout for RPC calls in seconds
        """
        self.address = f"{host}:{port}"
        self.timeout = timeout
        self.channel = None
        self.stub = None

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def connect(self):
        """Establish connection to the server."""
        self.channel = grpc.insecure_channel(self.address)
        self.stub = immutable_log_pb2_grpc.ImmutableLogServiceStub(self.channel)

    def close(self):
        """Close the connection."""
        if self.channel:
            self.channel.close()
            self.channel = None
            self.stub = None

    def append(self, partition: str, data: Any, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Append an entry to the log.

        Args:
            partition: Partition identifier
            data: Data to append (will be JSON serialized)
            timeout: Timeout for this request

        Returns:
            Dictionary with seq, timestamp, hash, success, and optional error

        Raises:
            grpc.RpcError: If the RPC fails
        """
        if not self.stub:
            raise RuntimeError("Not connected. Call connect() first or use context manager.")

        timeout = timeout or self.timeout

        request = immutable_log_pb2.AppendRequest(
            partition=partition,
            data=json.dumps(data)
        )

        response = self.stub.Append(request, timeout=timeout)

        return {
            "seq": response.seq,
            "timestamp": response.timestamp,
            "hash": response.hash,
            "success": response.success,
            "error": response.error if response.error else None
        }

    def read(
        self,
        partition: str,
        start_seq: Optional[int] = None,
        limit: Optional[int] = None,
        timeout: Optional[int] = None
    ) -> Iterator[Dict[str, Any]]:
        """
        Read entries from the log (streaming).

        Args:
            partition: Partition identifier
            start_seq: Starting sequence number (default: 0)
            limit: Maximum number of entries to return
            timeout: Timeout for this request

        Yields:
            Dictionaries with entry data

        Raises:
            grpc.RpcError: If the RPC fails
        """
        if not self.stub:
            raise RuntimeError("Not connected. Call connect() first or use context manager.")

        timeout = timeout or self.timeout

        request = immutable_log_pb2.ReadRequest(partition=partition)
        if start_seq is not None:
            request.start_seq = start_seq
        if limit is not None:
            request.limit = limit

        for response in self.stub.Read(request, timeout=timeout):
            yield {
                "seq": response.seq,
                "ts": response.timestamp,
                "partition": response.partition,
                "prev_hash": response.prev_hash,
                "data": json.loads(response.data),
                "hash": response.hash
            }

    def verify(self, partition: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Verify the integrity of a partition.

        Args:
            partition: Partition identifier
            timeout: Timeout for this request

        Returns:
            Dictionary with valid, entries_verified, final_hash, and optional error

        Raises:
            grpc.RpcError: If the RPC fails
        """
        if not self.stub:
            raise RuntimeError("Not connected. Call connect() first or use context manager.")

        timeout = timeout or self.timeout

        request = immutable_log_pb2.VerifyRequest(partition=partition)
        response = self.stub.Verify(request, timeout=timeout)

        return {
            "valid": response.valid,
            "entries_verified": response.entries_verified,
            "final_hash": response.final_hash if response.final_hash else None,
            "error": response.error if response.error else None
        }

    def list_partitions(self, timeout: Optional[int] = None) -> List[str]:
        """
        List all available partitions.

        Args:
            timeout: Timeout for this request

        Returns:
            List of partition names

        Raises:
            grpc.RpcError: If the RPC fails
        """
        if not self.stub:
            raise RuntimeError("Not connected. Call connect() first or use context manager.")

        timeout = timeout or self.timeout

        request = immutable_log_pb2.ListPartitionsRequest()
        response = self.stub.ListPartitions(request, timeout=timeout)

        return list(response.partitions)

    def get_last_entry(self, partition: str, timeout: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Get the last entry from a partition.

        Args:
            partition: Partition identifier
            timeout: Timeout for this request

        Returns:
            Dictionary with entry data, or None if partition is empty

        Raises:
            grpc.RpcError: If the RPC fails
        """
        if not self.stub:
            raise RuntimeError("Not connected. Call connect() first or use context manager.")

        timeout = timeout or self.timeout

        request = immutable_log_pb2.GetLastEntryRequest(partition=partition)
        response = self.stub.GetLastEntry(request, timeout=timeout)

        if not response.found:
            return None

        return {
            "seq": response.seq,
            "ts": response.timestamp,
            "partition": response.partition,
            "prev_hash": response.prev_hash,
            "data": json.loads(response.data),
            "hash": response.hash
        }

    def tail(
        self,
        partition: str,
        start_seq: Optional[int] = None,
        follow: bool = False,
        timeout: Optional[int] = None
    ) -> Iterator[Dict[str, Any]]:
        """
        Tail a partition (like tail -f).

        Args:
            partition: Partition identifier
            start_seq: Starting sequence number
            follow: If True, keep streaming new entries
            timeout: Timeout for this request

        Yields:
            Dictionaries with entry data

        Raises:
            grpc.RpcError: If the RPC fails
        """
        if not self.stub:
            raise RuntimeError("Not connected. Call connect() first or use context manager.")

        timeout = timeout or self.timeout

        request = immutable_log_pb2.TailRequest(
            partition=partition,
            follow=follow
        )
        if start_seq is not None:
            request.start_seq = start_seq

        for response in self.stub.Tail(request, timeout=timeout):
            yield {
                "seq": response.seq,
                "ts": response.timestamp,
                "partition": response.partition,
                "prev_hash": response.prev_hash,
                "data": json.loads(response.data),
                "hash": response.hash
            }


def main():
    """Example usage of the client library."""
    import sys

    # Example: Connect and perform operations
    with ImmutableLogClient() as client:
        print("Connected to ImmutableLog gRPC server")

        # Append an entry
        result = client.append("test", {"message": "Hello from gRPC client!"})
        print(f"Appended entry: seq={result['seq']}, hash={result['hash'][:16]}...")

        # Read entries
        print("\nReading entries:")
        for entry in client.read("test"):
            print(f"  [{entry['seq']}] {entry['data']}")

        # Verify partition
        verify_result = client.verify("test")
        print(f"\nVerification: valid={verify_result['valid']}, "
              f"entries={verify_result['entries_verified']}")

        # List partitions
        partitions = client.list_partitions()
        print(f"\nPartitions: {partitions}")


if __name__ == "__main__":
    main()
