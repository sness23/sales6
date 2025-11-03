#!/usr/bin/env python3
"""
Immutable Event Log - Hash Chain Implementation

A simple, scalable, human-readable event log with cryptographic immutability.
Each entry contains a hash of the previous entry, forming an unbreakable chain.
"""

import json
import hashlib
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any


class ImmutableLog:
    """Manages an immutable, hash-chained event log with partitioning."""

    GENESIS_HASH = "0" * 64  # Hash for the first entry in a partition

    def __init__(self, base_dir: str = "logs"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)

    def _get_partition_path(self, partition: str) -> Path:
        """Get the file path for a partition."""
        # Sanitize partition name
        safe_partition = "".join(c if c.isalnum() or c in "-_" else "_" for c in partition)
        return self.base_dir / f"{safe_partition}.jsonl"

    def _calculate_hash(self, entry: Dict[str, Any]) -> str:
        """Calculate SHA-256 hash of an entry (excluding the hash field itself)."""
        # Create canonical representation for hashing
        hash_data = {
            "seq": entry["seq"],
            "ts": entry["ts"],
            "partition": entry["partition"],
            "prev_hash": entry["prev_hash"],
            "data": entry["data"]
        }
        # Use sort_keys for deterministic JSON
        canonical = json.dumps(hash_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    def _get_last_entry(self, partition: str) -> Optional[Dict[str, Any]]:
        """Get the last entry from a partition log."""
        path = self._get_partition_path(partition)
        if not path.exists():
            return None

        # Read last line efficiently
        try:
            with open(path, 'rb') as f:
                # Seek to end and read backwards to find last complete line
                f.seek(0, 2)  # Go to end
                file_size = f.tell()
                if file_size == 0:
                    return None

                # Read last chunk
                chunk_size = min(8192, file_size)
                f.seek(max(0, file_size - chunk_size))
                lines = f.read().decode('utf-8').splitlines()

                # Get last non-empty line
                for line in reversed(lines):
                    line = line.strip()
                    if line:
                        return json.loads(line)
        except Exception as e:
            print(f"Error reading last entry: {e}", file=sys.stderr)
            return None

        return None

    def append(self, partition: str, data: Any) -> Dict[str, Any]:
        """
        Append a new entry to the log.

        Args:
            partition: Partition identifier
            data: Event data (will be JSON serialized)

        Returns:
            The complete entry that was appended
        """
        # Get last entry to build chain
        last_entry = self._get_last_entry(partition)

        if last_entry is None:
            # First entry in partition
            seq = 0
            prev_hash = self.GENESIS_HASH
        else:
            seq = last_entry["seq"] + 1
            prev_hash = last_entry["hash"]

        # Create new entry
        entry = {
            "seq": seq,
            "ts": datetime.now(timezone.utc).isoformat(),
            "partition": partition,
            "prev_hash": prev_hash,
            "data": data,
        }

        # Calculate hash
        entry["hash"] = self._calculate_hash(entry)

        # Append to file
        path = self._get_partition_path(partition)
        with open(path, 'a') as f:
            f.write(json.dumps(entry, separators=(',', ':')) + '\n')

        return entry

    def tail(self, partition: str, follow: bool = False, n: Optional[int] = None):
        """
        Read entries from a partition.

        Args:
            partition: Partition identifier
            follow: If True, keep following like `tail -f`
            n: Number of last entries to show (None = all)
        """
        path = self._get_partition_path(partition)

        if not path.exists():
            print(f"Partition '{partition}' does not exist", file=sys.stderr)
            return

        # Read initial entries
        with open(path, 'r') as f:
            lines = f.readlines()

        # Show last n lines if specified
        if n is not None:
            lines = lines[-n:]

        for line in lines:
            print(line.rstrip())

        if not follow:
            return

        # Follow mode (like tail -f)
        print(f"# Following partition '{partition}' (Ctrl+C to stop)...", file=sys.stderr)
        try:
            with open(path, 'r') as f:
                # Seek to end
                f.seek(0, 2)

                while True:
                    line = f.readline()
                    if line:
                        print(line.rstrip())
                    else:
                        time.sleep(0.1)  # Small delay before checking again
        except KeyboardInterrupt:
            print("\n# Stopped following", file=sys.stderr)

    def verify(self, partition: str) -> bool:
        """
        Verify the integrity of a partition's hash chain.

        Returns:
            True if chain is valid, False otherwise
        """
        path = self._get_partition_path(partition)

        if not path.exists():
            print(f"Partition '{partition}' does not exist", file=sys.stderr)
            return False

        print(f"Verifying partition '{partition}'...")

        prev_hash = self.GENESIS_HASH
        entry_count = 0

        with open(path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as e:
                    print(f"✗ Line {line_num}: Invalid JSON - {e}")
                    return False

                # Verify sequence number
                if entry["seq"] != entry_count:
                    print(f"✗ Line {line_num}: Sequence mismatch (expected {entry_count}, got {entry['seq']})")
                    return False

                # Verify previous hash
                if entry["prev_hash"] != prev_hash:
                    print(f"✗ Line {line_num}: Hash chain broken!")
                    print(f"  Expected prev_hash: {prev_hash}")
                    print(f"  Got prev_hash:      {entry['prev_hash']}")
                    return False

                # Verify current hash
                expected_hash = self._calculate_hash(entry)
                if entry["hash"] != expected_hash:
                    print(f"✗ Line {line_num}: Hash mismatch!")
                    print(f"  Expected: {expected_hash}")
                    print(f"  Got:      {entry['hash']}")
                    return False

                prev_hash = entry["hash"]
                entry_count += 1

        print(f"✓ Verified {entry_count} entries - chain is valid!")
        print(f"  Final hash: {prev_hash}")
        return True

    def list_partitions(self) -> list[str]:
        """List all available partitions."""
        partitions = []
        for path in self.base_dir.glob("*.jsonl"):
            partitions.append(path.stem)
        return sorted(partitions)


def main():
    """CLI interface for the immutable log."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Immutable Event Log - Hash Chain Implementation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Append an event
  %(prog)s append users '{"user": "alice", "action": "login"}'
  %(prog)s append orders '{"order_id": 123, "total": 99.99}'

  # Tail the log
  %(prog)s tail users
  %(prog)s tail users --follow
  %(prog)s tail users -n 10

  # Verify integrity
  %(prog)s verify users

  # List partitions
  %(prog)s list
        """
    )

    parser.add_argument(
        "--dir",
        default="logs",
        help="Base directory for log files (default: logs)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Append command
    append_parser = subparsers.add_parser("append", help="Append an entry to the log")
    append_parser.add_argument("partition", help="Partition identifier")
    append_parser.add_argument("data", help="JSON data to append (or '-' for stdin)")

    # Tail command
    tail_parser = subparsers.add_parser("tail", help="Read entries from the log")
    tail_parser.add_argument("partition", help="Partition identifier")
    tail_parser.add_argument("-f", "--follow", action="store_true", help="Follow the log (like tail -f)")
    tail_parser.add_argument("-n", type=int, help="Show last N entries")

    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify log integrity")
    verify_parser.add_argument("partition", help="Partition identifier")

    # List command
    list_parser = subparsers.add_parser("list", help="List all partitions")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    log = ImmutableLog(args.dir)

    try:
        if args.command == "append":
            # Read data
            if args.data == "-":
                data_str = sys.stdin.read()
            else:
                data_str = args.data

            # Parse JSON
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError as e:
                print(f"Error: Invalid JSON - {e}", file=sys.stderr)
                sys.exit(1)

            # Append
            entry = log.append(args.partition, data)
            print(f"✓ Appended entry {entry['seq']} to partition '{args.partition}'")
            print(f"  Hash: {entry['hash'][:16]}...")

        elif args.command == "tail":
            log.tail(args.partition, follow=args.follow, n=args.n)

        elif args.command == "verify":
            success = log.verify(args.partition)
            sys.exit(0 if success else 1)

        elif args.command == "list":
            partitions = log.list_partitions()
            if partitions:
                print("Available partitions:")
                for p in partitions:
                    print(f"  - {p}")
            else:
                print("No partitions found")

    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
