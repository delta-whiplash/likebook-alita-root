#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT="${1:-$SCRIPT_DIR/su}"

echo "[*] Compiling freestanding ARM64 su binary..."
clang --target=aarch64-linux-gnu \
      -fuse-ld=lld \
      -nostdlib \
      -fno-builtin \
      -fno-stack-protector \
      -static \
      -O2 \
      "$SCRIPT_DIR/su.c" \
      -o "$OUTPUT"

echo "[*] Stripping symbols..."
llvm-strip "$OUTPUT"

echo "[+] Built successfully: $OUTPUT ($(stat -c%s "$OUTPUT") bytes)"
file "$OUTPUT"
