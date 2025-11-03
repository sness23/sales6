# Immutable Event Log

A simple, scalable, human-readable event log with cryptographic immutability via hash chains.

## Overview

This is a prototype implementation of an **append-only, hash-chained event log** designed to be the foundation for a massive-scale event sourcing system. Think of it as a building block for understanding how systems like Apache Kafka work under the hood.

### Key Features

- **Immutable by Design**: Each entry contains a SHA-256 hash of the previous entry, forming an unbreakable chain
- **Human Readable**: JSONL format that can be opened in any text editor (emacs, vim, etc.)
- **Partitioned**: Independent partitions for horizontal scaling
- **Fast**: Optimized for high-throughput append and sequential read operations
- **Verifiable**: Built-in integrity verification to detect any tampering
- **Simple**: ~400 lines of Python, easy to understand and modify

## Architecture

### Log Entry Format

Each entry in the log contains:

```json
{
  "seq": 0,
  "ts": "2025-11-03T13:49:32.817894+00:00",
  "partition": "users",
  "prev_hash": "0000000000000000000000000000000000000000000000000000000000000000",
  "data": {"user": "alice", "action": "login"},
  "hash": "b2ef339e03e3f2403f0f90fdff7562502b378be277e858371f9eca811bc86b57"
}
```

- `seq`: Sequential number within partition (starts at 0)
- `ts`: ISO 8601 timestamp (UTC)
- `partition`: Partition identifier
- `prev_hash`: SHA-256 hash of previous entry (genesis = all zeros)
- `data`: Your event payload (any JSON structure)
- `hash`: SHA-256 hash of this entry

### Hash Chain

Each entry's hash is calculated over: `seq + ts + partition + prev_hash + data`

This creates an immutable chain where:
1. You can't modify past entries (hash would break)
2. You can't insert entries (sequence numbers would break)
3. You can't reorder entries (hashes would break)
4. You can cryptographically prove integrity

### File Structure

```
logs/
├── users.jsonl         # Partition for user events
├── orders.jsonl        # Partition for order events
├── messages.jsonl      # Partition for chat messages
└── ...                 # Any number of partitions
```

Each partition is an independent log file with its own hash chain.

## Usage

### Install

No dependencies! Just Python 3.10+

```bash
chmod +x immutable_log.py
```

### Commands

#### Append an Entry

```bash
# Append to a partition
./immutable_log.py append users '{"user": "alice", "action": "login"}'
./immutable_log.py append orders '{"order_id": 12345, "total": 99.99}'

# Read from stdin
echo '{"event": "test"}' | ./immutable_log.py append events -
```

#### Tail the Log

```bash
# Show all entries
./immutable_log.py tail users

# Show last 10 entries
./immutable_log.py tail users -n 10

# Follow the log (like tail -f)
./immutable_log.py tail users --follow
```

#### Verify Integrity

```bash
# Verify the hash chain
./immutable_log.py verify users

# Output:
# Verifying partition 'users'...
# ✓ Verified 2 entries - chain is valid!
#   Final hash: 4cdd48b4aed88ecd7d983a1282c6bfff0823884f72a17443f3cdd164b19e490a
```

#### List Partitions

```bash
./immutable_log.py list

# Output:
# Available partitions:
#   - orders
#   - users
```

## Example Workflow

```bash
# Create some events
./immutable_log.py append users '{"user": "alice", "action": "login"}'
./immutable_log.py append users '{"user": "alice", "action": "view_dashboard"}'
./immutable_log.py append users '{"user": "bob", "action": "login"}'
./immutable_log.py append orders '{"order_id": 1001, "user": "alice", "total": 49.99}'
./immutable_log.py append orders '{"order_id": 1002, "user": "bob", "total": 199.99}'

# View the logs
./immutable_log.py tail users
./immutable_log.py tail orders

# Verify integrity
./immutable_log.py verify users
./immutable_log.py verify orders

# Open in your editor (it's just text!)
emacs logs/users.jsonl
```

## Scaling Path

### Current (Prototype)
- Single machine
- File-based storage
- Manual partitioning
- Perfect for learning and testing

### Next Steps (Production)
1. **Apache Kafka** or **Redpanda**
   - Distributed, replicated partitions
   - High availability
   - Millions of events/second
   - Petabyte scale

2. **Event Store** or **Pulsar**
   - Built-in event sourcing features
   - Stream processing
   - Multi-datacenter replication

### Why This Design Scales

The architecture maps directly to production systems:

| Our Prototype | Kafka/Production |
|---------------|------------------|
| Partition files | Topic partitions |
| Hash chain | Replication & checksums |
| Sequential append | Log-structured storage |
| Sequential reads | Consumer groups |
| JSONL | Avro/Protobuf |

The algorithms you're building here are fundamentally the same!

## Design Decisions

### Why JSONL?
- Human readable (debuggable with cat/grep/jq)
- Language agnostic
- Streaming friendly
- Easily convertible to binary formats later

### Why Hash Chains?
- Simple to understand and implement
- Cryptographically secure
- Self-verifying (detect corruption/tampering)
- Industry standard (Git, Bitcoin, Certificate Transparency)

### Why Partitions?
- Horizontal scaling (add more partitions = more throughput)
- Parallel processing (different consumers on different partitions)
- Isolation (user events separate from order events)
- Maps to production systems (Kafka topics have partitions)

## Performance Characteristics

### Append Operation
- **Time Complexity**: O(1) - just append to file
- **Typical Latency**: <1ms on SSD
- **Bottleneck**: Disk I/O (can be async/batched)

### Tail Operation
- **Time Complexity**: O(n) for reading, O(1) for follow
- **Typical Latency**: ~0.1ms per entry
- **Bottleneck**: Disk read speed

### Verify Operation
- **Time Complexity**: O(n) - must check every entry
- **Typical Latency**: ~1ms per 1000 entries
- **Bottleneck**: Hash calculation + disk read

## Testing Integrity

Try breaking the chain:

```bash
# Create a log
./immutable_log.py append test '{"event": 1}'
./immutable_log.py append test '{"event": 2}'
./immutable_log.py verify test  # ✓ Valid

# Manually edit logs/test.jsonl in emacs
# Change "event": 1 to "event": 99
./immutable_log.py verify test  # ✗ Chain broken!
```

## Use Cases

This log is designed to be the **Single Source of Truth (SSOT)** for:

- **Event Sourcing**: Store every state change as an event
- **Audit Logs**: Cryptographically verifiable history
- **Data Lake**: Raw event stream for analytics
- **Change Data Capture**: Database change events
- **Message Queues**: Durable, ordered message delivery
- **Replication**: Source of truth for syncing systems

## Future Enhancements

- [ ] Compression (gzip, zstd)
- [ ] Encryption (encrypt `data` field)
- [ ] Indexing (SQLite index for fast lookups)
- [ ] Replication (sync partitions across machines)
- [ ] Snapshots (periodic checkpoints for fast recovery)
- [ ] Consumer groups (track read positions)
- [ ] Schema registry (enforce data schemas)
- [ ] Retention policies (archive/delete old data)

## Contributing

This is part of the `sales*` experimental projects. Feel free to extend and modify!

## License

MIT (or whatever you prefer)

## Learn More

- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [Event Sourcing Pattern](https://martinfowler.com/eaaDev/EventSourcing.html)
- [Hash Chains](https://en.wikipedia.org/wiki/Hash_chain)
- [Certificate Transparency](https://certificate.transparency.dev/) - Uses similar hash chains
