#!/usr/bin/env python3
"""
Async Tar Compressor Usage Examples with Benchmark Integration
"""

import asyncio
import tarfile
import tempfile
import time
from io import BytesIO
from pathlib import Path

from tar_compressor import AsyncTarCompressor, CompressionType, CompressionChecker


async def example_basic_usage():
    """Basic usage example"""
    print("=== Basic Usage Example ===")

    # Create some test files
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir) / "test_data"
        test_dir.mkdir()

        # Create test files
        for i in range(5):
            file_path = test_dir / f"file_{i}.txt"
            file_path.write_text(f"Test file {i}\n" * 1000)

        # Create subdirectory
        subdir = test_dir / "subdir"
        subdir.mkdir()
        for i in range(3):
            file_path = subdir / f"subfile_{i}.txt"
            file_path.write_text(f"Subdirectory file {i}\n" * 500)

        # Use gzip compression
        compressor = AsyncTarCompressor(CompressionType.GZIP)
        output_file = Path(tmpdir) / "test_archive.tar.gz"

        success = await compressor.compress_with_progress(
            [test_dir],
            output_file
        )

        if success:
            print(f"\nCompressed file created: {output_file}")
            print(f"File size: {output_file.stat().st_size} bytes")


async def example_memory_operations():
    """Example of in-memory compression using BytesIO"""
    print("\n=== In-Memory Compression Example ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test data
        test_files = []
        for i in range(3):
            file_path = Path(tmpdir) / f"memory_test_{i}.txt"
            file_path.write_text(f"In-memory test file {i}\n" * 1000)
            test_files.append(file_path)

        # Compress to memory
        compressor = AsyncTarCompressor(CompressionType.GZIP)
        print("Compressing to memory...")

        memory_archive = await compressor.compress_to_memory(test_files)

        if memory_archive:
            print(f"Memory archive size: {memory_archive.tell()} bytes")

            # Verify the archive by reading it
            memory_archive.seek(0)
            with tarfile.open(fileobj=memory_archive, mode='r:gz') as tar:
                print("Archive contents:")
                for member in tar.getmembers():
                    print(f"  - {member.name} ({member.size} bytes)")

            # Example: Save memory archive to file
            output_path = Path(tmpdir) / "from_memory.tar.gz"
            memory_archive.seek(0)
            with open(output_path, 'wb') as f:
                f.write(memory_archive.read())
            print(f"Memory archive saved to: {output_path}")


async def example_direct_bytesio():
    """Example of direct BytesIO usage"""
    print("\n=== Direct BytesIO Usage Example ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test data
        test_dir = Path(tmpdir) / "bytesio_test"
        test_dir.mkdir()

        for i in range(3):
            (test_dir / f"data_{i}.txt").write_text(f"BytesIO test data {i}\n" * 500)

        # Create BytesIO buffer
        output_buffer = BytesIO()

        # Compress directly to BytesIO
        compressor = AsyncTarCompressor(CompressionType.BZIP2)
        success = await compressor.compress_with_progress(
            [test_dir],
            output_buffer
        )

        if success:
            buffer_size = output_buffer.tell()
            print(f"BytesIO buffer size: {buffer_size} bytes")

            # Demonstrate reading from the buffer
            output_buffer.seek(0)
            first_bytes = output_buffer.read(20)
            print(f"First 20 bytes: {first_bytes}")

            # Reset position
            output_buffer.seek(0)
            print("BytesIO buffer ready for use")


async def example_multiple_sources():
    """Compress multiple source files/directories"""
    print("\n=== Multiple Sources Compression ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create multiple sources
        sources = []

        # Create several standalone files
        for i in range(3):
            file_path = Path(tmpdir) / f"standalone_{i}.txt"
            file_path.write_text(f"Standalone file {i}\n" * 200)
            sources.append(file_path)

        # Create a directory
        dir_path = Path(tmpdir) / "my_directory"
        dir_path.mkdir()
        for i in range(2):
            (dir_path / f"dir_file_{i}.txt").write_text(f"Directory file {i}\n" * 300)
        sources.append(dir_path)

        # Use bzip2 compression
        compressor = AsyncTarCompressor(CompressionType.BZIP2)
        output_file = Path(tmpdir) / "multi_source.tar.bz2"

        await compressor.compress_with_progress(sources, output_file)


async def example_check_algorithms():
    """Check compression algorithm availability"""
    print("\n=== Check Compression Algorithm Support ===")

    from rich.console import Console
    console = Console()

    # Display support table
    CompressionChecker.print_availability_table(console)

    # Test available compression algorithms
    print("\nTesting available compression algorithms...")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test data
        test_file = Path(tmpdir) / "test_data.txt"
        test_file.write_text("Test data\n" * 1000)

        # Get algorithm info
        algo_info = CompressionChecker.check_availability()

        for comp_type, info in algo_info.items():
            if comp_type == CompressionType.NONE:
                continue

            if info.available:
                print(f"\nTesting {info.name}...")
                try:
                    compressor = AsyncTarCompressor(comp_type)
                    output_file = Path(tmpdir) / f"test{info.extension}"

                    success = await compressor.compress_with_progress(
                        [test_file],
                        output_file,
                    )

                    if success and output_file.exists():
                        size = output_file.stat().st_size
                        print(f"  ✓ Success: {size:,} bytes")
                except Exception as e:
                    print(f"  ✗ Failed: {e}")
            else:
                print(f"\nSkipping {info.name} (not installed)")


async def example_different_compressions():
    """Test performance comparison of different compression algorithms"""
    print("\n=== Compression Algorithm Performance Comparison ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create different types of test data
        print("Creating test data...")

        # Text data (high compression ratio)
        text_file = Path(tmpdir) / "text_data.txt"
        text_file.write_text("This is a repeated line of text data\n" * 50000)

        # Random data (low compression ratio)
        import random
        random_file = Path(tmpdir) / "random_data.bin"
        random_data = bytes(random.randint(0, 255) for _ in range(100000))
        random_file.write_bytes(random_data)

        # Mixed data
        mixed_dir = Path(tmpdir) / "mixed_data"
        mixed_dir.mkdir()
        for i in range(10):
            (mixed_dir / f"text_{i}.txt").write_text(f"File {i}\n" * 100)
            (mixed_dir / f"data_{i}.bin").write_bytes(
                bytes(random.randint(0, 255) for _ in range(1000))
            )

        # Test different algorithms
        results = []
        algo_info = CompressionChecker.check_availability()

        for comp_type in [CompressionType.GZIP, CompressionType.BZIP2,
                          CompressionType.XZ, CompressionType.LZ4]:
            if not algo_info[comp_type].available:
                print(f"\nSkipping {comp_type.name} (not installed)")
                continue

            print(f"\nTesting {comp_type.name} compression...")

            try:
                compressor = AsyncTarCompressor(comp_type)
                output_file = Path(tmpdir) / f"test.tar{algo_info[comp_type].extension}"

                start_time = time.time()
                success = await compressor.compress_with_progress(
                    [text_file, random_file, mixed_dir],
                    output_file
                )
                end_time = time.time()

                if success:
                    size = output_file.stat().st_size
                    duration = end_time - start_time
                    results.append({
                        'name': comp_type.name,
                        'size': size,
                        'time': duration,
                        'desc': algo_info[comp_type].description
                    })
            except Exception as e:
                print(f"  Error: {e}")

        # Display comparison results
        if results:
            print("\n\nCompression Algorithm Performance Comparison:")
            print("=" * 70)
            print(f"{'Algorithm':<10} {'Compressed Size':<15} {'Time':<10} {'Speed':<15} {'Description'}")
            print("-" * 70)

            # Calculate original size
            original_size = sum(p.stat().st_size for p in [text_file, random_file]
                                if p.exists())
            original_size += sum(f.stat().st_size for f in mixed_dir.rglob("*")
                                 if f.is_file())

            for r in results:
                compression_ratio = (1 - r['size'] / original_size) * 100
                speed = original_size / r['time'] / 1024 / 1024  # MB/s

                print(f"{r['name']:<10} {r['size']:>12,} B  {r['time']:>6.2f}s  "
                      f"{speed:>6.1f} MB/s  {r['desc']}")

            print("-" * 70)
            print(f"Original size: {original_size:,} bytes")


async def example_interrupt_handling():
    """Demonstrate interrupt handling"""
    print("\n=== Interrupt Handling Demo ===")
    print("Tip: Press Ctrl+C during compression to test interrupt handling")
    print("First time will ask for confirmation, second time will force interrupt\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create many files to extend compression time
        test_dir = Path(tmpdir) / "many_files"
        test_dir.mkdir()

        print("Creating test files...")
        for i in range(100):
            file_path = test_dir / f"file_{i:03d}.txt"
            file_path.write_text(f"File content {i}\n" * 100)

        compressor = AsyncTarCompressor(CompressionType.GZIP)
        output_file = Path(tmpdir) / "interruptible.tar.gz"

        print("\nStarting compression, you can try pressing Ctrl+C now...")
        await compressor.compress_with_progress([test_dir], output_file)


async def example_command_line_vs_interactive():
    """Example showing command line vs interactive usage"""
    print("\n=== Command Line vs Interactive Usage ===")

    print("Command line usage examples:")
    print("  python tar_compressor.py file1.txt dir1/ -o archive.tar.gz -c gz")
    print("  python tar_compressor.py data/ -o archive.tar.lz4 -c lz4")
    print("  python tar_compressor.py --check")
    print()
    print("Interactive mode:")
    print("  python tar_compressor.py -i")
    print("  python tar_compressor.py  # Without arguments")
    print()
    print("The compression algorithm is determined by the -c parameter,")
    print("NOT by the output filename extension!")


async def run_comprehensive_benchmark():
    """Run the comprehensive benchmark suite"""
    print("\n=== Running Comprehensive Benchmark Suite ===")
    print("This will test various data types, file sizes, and compression levels")

    try:
        # Import the benchmark module
        from benchmark import main as benchmark_main
        await benchmark_main()
    except ImportError:
        print("\n[ERROR] benchmark.py not found in the current directory!")
        print("Please ensure benchmark.py is in the same directory as this script.")
    except Exception as e:
        print(f"\n[ERROR] Failed to run benchmark: {e}")


async def main():
    """Run all examples"""
    examples = [
        ("Basic Usage", example_basic_usage),
        ("In-Memory Compression", example_memory_operations),
        ("Direct BytesIO Usage", example_direct_bytesio),
        ("Multiple Sources Compression", example_multiple_sources),
        ("Check Algorithm Support", example_check_algorithms),
        ("Compression Algorithm Performance Comparison", example_different_compressions),
        ("Interrupt Handling", example_interrupt_handling),
        ("Command Line vs Interactive", example_command_line_vs_interactive),
        ("Comprehensive Benchmark Suite", run_comprehensive_benchmark)
    ]

    print("Async Tar Compressor Demo Program")
    print("=" * 40)

    for i, (name, func) in enumerate(examples, 1):
        print(f"\n{i}. {name}")

    choice = input("\nSelect example to run (1-9) or 'a' to run all: ").strip()

    if choice.lower() == 'a':
        for name, func in examples[:-1]:  # Skip benchmark in "run all" mode
            await func()
            if func != examples[-2][1]:  # Don't wait after last regular example
                input("\nPress Enter to continue to next example...")
    elif choice.isdigit() and 1 <= int(choice) <= len(examples):
        await examples[int(choice) - 1][1]()
    else:
        print("Invalid choice")


if __name__ == "__main__":
    asyncio.run(main())