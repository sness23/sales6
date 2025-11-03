#!/usr/bin/env python3
"""
CLI Client for Immutable Event Log gRPC Service

Network-transparent version of immutable_log.py
"""

import sys
import json
import argparse

import grpc
from grpc_client import ImmutableLogClient


def cmd_append(client: ImmutableLogClient, args):
    """Append an entry to the log."""
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
        return 1

    # Append
    try:
        result = client.append(args.partition, data)
        if result["success"]:
            print(f"✓ Appended entry {result['seq']} to partition '{args.partition}'")
            print(f"  Hash: {result['hash'][:16]}...")
            return 0
        else:
            print(f"✗ Failed to append: {result['error']}", file=sys.stderr)
            return 1
    except grpc.RpcError as e:
        print(f"✗ RPC Error: {e.code()}: {e.details()}", file=sys.stderr)
        return 1


def cmd_read(client: ImmutableLogClient, args):
    """Read entries from the log."""
    try:
        for entry in client.read(args.partition, start_seq=args.start, limit=args.limit):
            print(json.dumps(entry, separators=(',', ':')))
        return 0
    except grpc.RpcError as e:
        print(f"✗ RPC Error: {e.code()}: {e.details()}", file=sys.stderr)
        return 1


def cmd_tail(client: ImmutableLogClient, args):
    """Tail entries from the log."""
    try:
        if args.follow:
            print(f"# Following partition '{args.partition}' (Ctrl+C to stop)...", file=sys.stderr)

        for entry in client.tail(
            args.partition,
            start_seq=args.start,
            follow=args.follow
        ):
            print(json.dumps(entry, separators=(',', ':')))

        return 0
    except KeyboardInterrupt:
        print("\n# Stopped following", file=sys.stderr)
        return 0
    except grpc.RpcError as e:
        print(f"✗ RPC Error: {e.code()}: {e.details()}", file=sys.stderr)
        return 1


def cmd_verify(client: ImmutableLogClient, args):
    """Verify partition integrity."""
    try:
        print(f"Verifying partition '{args.partition}'...")
        result = client.verify(args.partition)

        if result["valid"]:
            print(f"✓ Verified {result['entries_verified']} entries - chain is valid!")
            print(f"  Final hash: {result['final_hash']}")
            return 0
        else:
            print(f"✗ Verification failed: {result['error']}", file=sys.stderr)
            return 1
    except grpc.RpcError as e:
        print(f"✗ RPC Error: {e.code()}: {e.details()}", file=sys.stderr)
        return 1


def cmd_list(client: ImmutableLogClient, args):
    """List all partitions."""
    try:
        partitions = client.list_partitions()
        if partitions:
            print("Available partitions:")
            for p in partitions:
                print(f"  - {p}")
        else:
            print("No partitions found")
        return 0
    except grpc.RpcError as e:
        print(f"✗ RPC Error: {e.code()}: {e.details()}", file=sys.stderr)
        return 1


def cmd_last(client: ImmutableLogClient, args):
    """Get the last entry from a partition."""
    try:
        entry = client.get_last_entry(args.partition)
        if entry:
            print(json.dumps(entry, separators=(',', ':')))
            return 0
        else:
            print(f"Partition '{args.partition}' is empty", file=sys.stderr)
            return 1
    except grpc.RpcError as e:
        print(f"✗ RPC Error: {e.code()}: {e.details()}", file=sys.stderr)
        return 1


def main():
    """CLI interface for the gRPC client."""
    parser = argparse.ArgumentParser(
        description="Immutable Event Log - gRPC Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Connect to custom server
  %(prog)s --host example.com --port 50051 list

  # Append an event
  %(prog)s append users '{"user": "alice", "action": "login"}'
  %(prog)s append orders '{"order_id": 123, "total": 99.99}'

  # Read entries
  %(prog)s read users
  %(prog)s read users --start 10 --limit 5

  # Tail the log
  %(prog)s tail users
  %(prog)s tail users --follow
  %(prog)s tail users --start 100 --follow

  # Get last entry
  %(prog)s last users

  # Verify integrity
  %(prog)s verify users

  # List partitions
  %(prog)s list
        """
    )

    parser.add_argument(
        "--host",
        default="localhost",
        help="Server hostname (default: localhost)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=50051,
        help="Server port (default: 50051)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="RPC timeout in seconds (default: 10)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Append command
    append_parser = subparsers.add_parser("append", help="Append an entry to the log")
    append_parser.add_argument("partition", help="Partition identifier")
    append_parser.add_argument("data", help="JSON data to append (or '-' for stdin)")

    # Read command
    read_parser = subparsers.add_parser("read", help="Read entries from the log")
    read_parser.add_argument("partition", help="Partition identifier")
    read_parser.add_argument("--start", type=int, help="Starting sequence number")
    read_parser.add_argument("--limit", type=int, help="Maximum number of entries")

    # Tail command
    tail_parser = subparsers.add_parser("tail", help="Tail entries from the log")
    tail_parser.add_argument("partition", help="Partition identifier")
    tail_parser.add_argument("-f", "--follow", action="store_true", help="Follow the log (like tail -f)")
    tail_parser.add_argument("--start", type=int, help="Starting sequence number")

    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify log integrity")
    verify_parser.add_argument("partition", help="Partition identifier")

    # List command
    list_parser = subparsers.add_parser("list", help="List all partitions")

    # Last command
    last_parser = subparsers.add_parser("last", help="Get the last entry from a partition")
    last_parser.add_argument("partition", help="Partition identifier")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Create client and execute command
    try:
        with ImmutableLogClient(host=args.host, port=args.port, timeout=args.timeout) as client:
            if args.command == "append":
                return cmd_append(client, args)
            elif args.command == "read":
                return cmd_read(client, args)
            elif args.command == "tail":
                return cmd_tail(client, args)
            elif args.command == "verify":
                return cmd_verify(client, args)
            elif args.command == "list":
                return cmd_list(client, args)
            elif args.command == "last":
                return cmd_last(client, args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
