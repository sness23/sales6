# gRPC Service Setup Guide

## Current Status

✅ **Completed**:
- Immutable log core implementation (`immutable_log.py`)
- Performance testing framework (`perf_test.py`)
- Comprehensive testing (31K+ events tested)
- gRPC protobuf schema defined (`proto/immutable_log.proto`)

🔄 **In Progress**:
- Setting up gRPC service layer

## Next Steps

### 1. Create Conda Environment

```bash
# Create new conda environment
conda create -n sales6 python=3.11 -y
conda activate sales6

# Install dependencies
pip install grpcio grpcio-tools
```

### 2. Generate gRPC Code

```bash
# Generate Python code from proto file
python -m grpc_tools.protoc \
  -I./proto \
  --python_out=. \
  --grpc_python_out=. \
  proto/immutable_log.proto
```

This will create:
- `immutable_log_pb2.py` (message classes)
- `immutable_log_pb2_grpc.py` (service stubs)

### 3. Files to Create

After environment setup, we need to create:

1. **`grpc_server.py`**: gRPC server implementation
   - Wraps `ImmutableLog` class
   - Implements all RPC methods
   - Handles streaming (Read, Tail)

2. **`grpc_client.py`**: Python client library
   - Easy-to-use wrapper around gRPC stubs
   - Connection management
   - Error handling

3. **`client_cli.py`**: CLI client (like `immutable_log.py` but over network)
   - Same commands: append, tail, verify, list
   - Network-transparent

4. **`grpc_perf_test.py`**: Performance tests for gRPC
   - Test client-server latency
   - Test throughput over network
   - Compare local vs network performance

### 4. Testing Plan

**Performance Tests**:
- Append latency (network overhead)
- Read throughput (streaming)
- Tail performance (streaming follow)
- Verify over network
- Compare: Direct vs gRPC performance

**Expected Results**:
- Local: 10K ops/sec
- gRPC (localhost): 5-8K ops/sec (network overhead)
- gRPC (LAN): 3-5K ops/sec
- gRPC (WAN): Depends on latency

## gRPC Service Design

### Service Methods

1. **Append(partition, data)** → AppendResponse
   - Unary RPC
   - Returns seq, timestamp, hash

2. **Read(partition, start_seq, limit)** → stream ReadResponse
   - Server streaming
   - Efficient for batch reads

3. **Verify(partition)** → VerifyResponse
   - Unary RPC
   - Returns valid, count, final_hash

4. **ListPartitions()** → ListPartitionsResponse
   - Unary RPC
   - Returns list of partition names

5. **GetLastEntry(partition)** → GetLastEntryResponse
   - Unary RPC
   - For sync/catchup operations

6. **Tail(partition, start_seq, follow)** → stream TailResponse
   - Server streaming
   - Like `tail -f` over network

### Architecture

```
┌─────────────┐          ┌─────────────┐          ┌─────────────┐
│   Client    │  gRPC    │   Server    │          │   Logs/     │
│   (CLI)     │◄────────►│  (Python)   │◄────────►│   (JSONL)   │
└─────────────┘          └─────────────┘          └─────────────┘
     │                          │
     │                          │
     └──────────────────────────┘
          Network boundary
```

## File Structure

```
sales6/
├── proto/
│   └── immutable_log.proto          ✅ Created
├── immutable_log_pb2.py              ⏳ Will be generated
├── immutable_log_pb2_grpc.py         ⏳ Will be generated
├── immutable_log.py                  ✅ Exists
├── grpc_server.py                    ⏳ To create
├── grpc_client.py                    ⏳ To create
├── client_cli.py                     ⏳ To create
├── grpc_perf_test.py                 ⏳ To create
└── perf_test.py                      ✅ Exists
```

## Resume Point

After conda environment is ready:
1. Generate gRPC code (see step 2 above)
2. Create `grpc_server.py`
3. Create `grpc_client.py`
4. Create `client_cli.py`
5. Create `grpc_perf_test.py`
6. Run performance tests
7. Generate comparison report

## Notes

- Keep backwards compatibility: direct file access should still work
- gRPC server should be optional (not required for standalone use)
- Consider adding authentication/TLS for production
- Think about multi-tenancy (partition isolation)
