#!/usr/bin/env bash
# run.sh — Build and run quran-clip via Docker
# Usage:
#   ./run.sh                          # Interactive mode
#   ./run.sh download 23 --from 1 --to 11 --reciter alafasy
#   ./run.sh list-surahs
#   ./run.sh list-reciters
#   ./run.sh test                     # Run test suite
#   ./run.sh build                    # Build only (no run)

set -e

IMAGE="quran-clip"
OUTPUT_DIR="$(cd "$(dirname "$0")" && pwd)/output"

# Ensure output directory exists
mkdir -p "$OUTPUT_DIR"

# Build if image doesn't exist or if --build flag is passed
_build() {
    echo "Building $IMAGE..."
    docker build -t "$IMAGE" "$(dirname "$0")"
    echo "Build complete."
}

# Check if image exists
if ! docker image inspect "$IMAGE" > /dev/null 2>&1; then
    _build
fi

case "${1:-}" in
    build)
        _build
        ;;
    test)
        _build
        docker run --rm --entrypoint pytest "$IMAGE" -v
        ;;
    rebuild)
        _build
        shift
        docker run --rm -it -v "$OUTPUT_DIR:/app/output" "$IMAGE" "$@"
        ;;
    *)
        docker run --rm -it -v "$OUTPUT_DIR:/app/output" "$IMAGE" "$@"
        ;;
esac
