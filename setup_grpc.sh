#!/bin/bash
# gRPC Setup Script for Immutable Event Log

set -e  # Exit on error

echo "=========================================="
echo "gRPC Setup for Immutable Event Log"
echo "=========================================="

# Check if we're in a conda environment
if [ -z "$CONDA_DEFAULT_ENV" ]; then
    echo "⚠️  Warning: Not in a conda environment"
    echo "   Consider running: conda create -n sales6 python=3.11 && conda activate sales6"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "1. Installing gRPC dependencies..."
pip install grpcio grpcio-tools

echo ""
echo "2. Generating gRPC code from protobuf..."
python -m grpc_tools.protoc \
    -I./proto \
    --python_out=. \
    --grpc_python_out=. \
    proto/immutable_log.proto

if [ -f "immutable_log_pb2.py" ] && [ -f "immutable_log_pb2_grpc.py" ]; then
    echo "✓ Generated immutable_log_pb2.py"
    echo "✓ Generated immutable_log_pb2_grpc.py"
else
    echo "✗ Failed to generate gRPC code"
    exit 1
fi

echo ""
echo "=========================================="
echo "✓ Setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Start server: python grpc_server.py"
echo "  2. Use client:   python client_cli.py append test '{\"hello\": \"world\"}'"
echo "  3. Run tests:    python grpc_perf_test.py"
echo ""
