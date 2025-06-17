#!/usr/bin/env python3
"""
Async Tar Processor Usage Examples with Compression and Decompression
"""

import asyncio
import base64
import sys
import tarfile
import tempfile
import time
from io import BytesIO
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table

from tar_compressor import AsyncTarProcessor, CompressionType, CompressionChecker, OperationType


async def example_basic_compression_decompression():
    """Basic compression and decompression example"""
    console = Console()
    console.print("\n[bold cyan]=== Basic Compression & Decompression Example ===[/bold cyan]")

    # Create some test files
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir) / "test_data"
        test_dir.mkdir()

        # Create test files with content
        console.print("\n[yellow]Creating test files...[/yellow]")
        for i in range(5):
            file_path = test_dir / f"file_{i}.txt"
            content = f"Test file {i}\n" * 1000
            file_path.write_text(content)
            console.print(f"  Created: {file_path.name} ({len(content)} bytes)")

        # Create subdirectory
        subdir = test_dir / "subdir"
        subdir.mkdir()
        for i in range(3):
            file_path = subdir / f"subfile_{i}.txt"
            file_path.write_text(f"Subdirectory file {i}\n" * 500)

        # Step 1: Compress
        console.print("\n[cyan]Step 1: Compressing files...[/cyan]")
        compressor = AsyncTarProcessor(CompressionType.GZIP)
        output_file = Path(tmpdir) / "test_archive.tar.gz"

        success = await compressor.compress_with_progress(
            [test_dir],
            output_file
        )

        if success:
            console.print(f"\n[green]✓ Compressed file created: {output_file}[/green]")
            console.print(f"  File size: {output_file.stat().st_size:,} bytes")

        # Step 2: List archive contents
        console.print("\n[cyan]Step 2: Listing archive contents...[/cyan]")
        contents = await compressor.list_archive_contents(output_file)

        if contents:
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("File", style="cyan")
            table.add_column("Size", style="green")
            table.add_column("Type", style="yellow")

            for name, size, is_dir in contents[:10]:  # Show first 10 items
                file_type = "DIR" if is_dir else "FILE"
                size_str = f"{size:,}" if not is_dir else "-"
                table.add_row(name, size_str, file_type)

            if len(contents) > 10:
                table.add_row("...", "...", "...")

            console.print(table)

        # Step 3: Decompress
        console.print("\n[cyan]Step 3: Decompressing archive...[/cyan]")
        extract_dir = Path(tmpdir) / "extracted"

        decompressor = AsyncTarProcessor()  # Will auto-detect compression
        success = await decompressor.decompress_with_progress(
            output_file,
            extract_dir
        )

        if success:
            console.print(f"\n[green]✓ Files extracted to: {extract_dir}[/green]")

            # Verify extracted files
            extracted_files = list(extract_dir.rglob("*"))
            console.print(f"  Total files extracted: {len([f for f in extracted_files if f.is_file()])}")
            console.print(f"  Total directories: {len([f for f in extracted_files if f.is_dir()])}")


async def example_memory_operations_enhanced():
    """Enhanced memory operations with bytes and str support"""
    console = Console()
    console.print("\n[bold cyan]=== Enhanced Memory Operations Example ===[/bold cyan]")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test data
        test_files = []
        for i in range(3):
            file_path = Path(tmpdir) / f"memory_test_{i}.txt"
            file_path.write_text(f"In-memory test file {i}\n" * 1000)
            test_files.append(file_path)

        # Check if GZIP is available, use fallback if not
        if not AsyncTarProcessor.is_algorithm_supported(CompressionType.GZIP):
            console.print("[yellow]GZIP not available, checking for alternatives...[/yellow]")
            available = AsyncTarProcessor.get_supported_algorithms()
            if available:
                # Use first available algorithm
                compression_type = available[0]
                console.print(f"[green]Using {compression_type.name} compression instead[/green]")
            else:
                console.print("[red]No compression algorithms available![/red]")
                return
        else:
            compression_type = CompressionType.GZIP

        compressor = AsyncTarProcessor(compression_type)

        # 1. Compress to BytesIO
        console.print("\n[yellow]1. Compressing to BytesIO...[/yellow]")
        memory_archive = await compressor.compress_to_memory(test_files)

        if memory_archive:
            console.print(f"  [green]✓ BytesIO archive size: {memory_archive.tell():,} bytes[/green]")
        else:
            console.print("  [red]✗ Failed to compress to BytesIO[/red]")
            return

        # 2. Compress to bytes
        console.print("\n[yellow]2. Compressing to bytes...[/yellow]")
        archive_bytes = await compressor.compress_to_bytes(test_files)

        if archive_bytes:
            console.print(f"  [green]✓ Bytes archive size: {len(archive_bytes):,} bytes[/green]")
        else:
            console.print("  [red]✗ Failed to compress to bytes[/red]")

        # 3. Compress to base64 string
        console.print("\n[yellow]3. Compressing to base64 string...[/yellow]")
        archive_str = await compressor.compress_to_str(test_files)

        if archive_str:
            console.print(f"  [green]✓ Base64 string length: {len(archive_str):,} characters[/green]")
            console.print(f"  Preview: {archive_str[:50]}...")
        else:
            console.print("  [red]✗ Failed to compress to base64 string[/red]")

        # 4. Decompress from BytesIO
        if memory_archive:
            console.print("\n[yellow]4. Decompressing from BytesIO...[/yellow]")
            extract_dir1 = Path(tmpdir) / "extract_bytesio"
            memory_archive.seek(0)

            success = await compressor.decompress_with_progress(memory_archive, extract_dir1)
            if success:
                console.print(f"  [green]✓ Extracted from BytesIO to: {extract_dir1}[/green]")
            else:
                console.print("  [red]✗ Failed to decompress from BytesIO[/red]")

        # 5. Decompress from bytes
        if archive_bytes:
            console.print("\n[yellow]5. Decompressing from bytes...[/yellow]")
            extract_dir2 = Path(tmpdir) / "extract_bytes"

            success = await compressor.decompress_with_progress(archive_bytes, extract_dir2)
            if success:
                console.print(f"  [green]✓ Extracted from bytes to: {extract_dir2}[/green]")
            else:
                console.print("  [red]✗ Failed to decompress from bytes[/red]")

        # 6. Decompress from base64 string
        if archive_str:
            console.print("\n[yellow]6. Decompressing from base64 string...[/yellow]")
            extract_dir3 = Path(tmpdir) / "extract_str"

            success = await compressor.decompress_from_str(archive_str, extract_dir3)
            if success:
                console.print(f"  [green]✓ Extracted from base64 string to: {extract_dir3}[/green]")
            else:
                console.print("  [red]✗ Failed to decompress from base64 string[/red]")


async def example_compression_availability():
    """Demonstrate compression availability checking and fallback"""
    console = Console()
    console.print("\n[bold cyan]=== Compression Availability Example ===[/bold cyan]")

    # Import our utility module
    from compression_utils import (
        check_compression_support,
        get_available_algorithms,
        suggest_fallback_algorithm,
        test_compression_functionality
    )

    # Check what's available
    console.print("\n[yellow]Checking compression support...[/yellow]")
    support = check_compression_support()

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Algorithm", style="cyan")
    table.add_column("Available", style="green")
    table.add_column("Status", style="yellow")

    # Test functionality
    test_results = test_compression_functionality()

    for algo, available in support.items():
        if available:
            success, message = test_results.get(algo, (False, "Not tested"))
            status_icon = "✓" if success else "⚠"
            table.add_row(
                algo,
                "[green]Yes[/green]" if available else "[red]No[/red]",
                f"{status_icon} {message}"
            )
        else:
            table.add_row(
                algo,
                "[red]No[/red]",
                "Module not available"
            )

    console.print(table)

    # Demonstrate fallback mechanism
    console.print("\n[cyan]Testing fallback mechanism:[/cyan]")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test file
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("Test content for compression\n" * 100)

        # Try different algorithms with fallback
        test_algorithms = ["lz4", "xz", "bzip2", "gzip"]

        for algo_name in test_algorithms:
            console.print(f"\n[yellow]Attempting {algo_name} compression...[/yellow]")

            # Map string to CompressionType
            algo_map = {
                "gzip": CompressionType.GZIP,
                "bzip2": CompressionType.BZIP2,
                "xz": CompressionType.XZ,
                "lz4": CompressionType.LZ4
            }

            requested_type = algo_map.get(algo_name)
            if not requested_type:
                continue

            # Check if available
            if AsyncTarProcessor.is_algorithm_supported(requested_type):
                console.print(f"  [green]✓ {algo_name} is available, using it[/green]")
                processor = AsyncTarProcessor(requested_type)
            else:
                # Find fallback
                fallback_name = suggest_fallback_algorithm(algo_name)
                if fallback_name and fallback_name != algo_name:
                    fallback_type = algo_map.get(fallback_name)
                    console.print(f"  [yellow]⚠ {algo_name} not available, falling back to {fallback_name}[/yellow]")
                    processor = AsyncTarProcessor(fallback_type)
                else:
                    console.print(f"  [red]✗ {algo_name} not available and no fallback found[/red]")
                    continue

            # Try compression
            output_file = Path(tmpdir) / f"test_{algo_name}.tar.{processor.compression.value}"
            try:
                success = await processor.compress_with_progress([test_file], output_file)
                if success:
                    console.print(f"  [green]✓ Successfully compressed using {processor.compression.name}[/green]")
                    console.print(f"    Size: {output_file.stat().st_size:,} bytes")
            except Exception as e:
                console.print(f"  [red]✗ Compression failed: {e}[/red]")

    # Show how to check in code
    console.print("\n[cyan]Example code for checking compression support:[/cyan]")

    # Import Syntax from rich for code highlighting
    from rich.syntax import Syntax
    code_example = """from tar_compressor import AsyncTarProcessor, CompressionType
from compression_utils import suggest_fallback_algorithm

# Check if specific algorithm is supported
if AsyncTarProcessor.is_algorithm_supported(CompressionType.LZ4):
    processor = AsyncTarProcessor(CompressionType.LZ4)
else:
    # Get available algorithms
    available = AsyncTarProcessor.get_supported_algorithms()
    if available:
        # Use first available
        processor = AsyncTarProcessor(available[0])
    else:
        print("No compression support!")

# Or use fallback utility
algo = suggest_fallback_algorithm("lz4")
if algo:
    # Convert string to CompressionType and use it
    pass"""

    syntax = Syntax(code_example, "python", theme="monokai", line_numbers=False)
    console.print(Panel(syntax, title="Checking Compression Support", border_style="cyan"))


async def example_different_compressions_comparison():
    """Test different compression algorithms with compression and decompression"""
    console = Console()
    console.print("\n[bold cyan]=== Compression Algorithm Comparison ===[/bold cyan]")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create different types of test data
        console.print("\n[yellow]Creating test data...[/yellow]")

        # Text data (high compression ratio)
        text_file = Path(tmpdir) / "text_data.txt"
        text_file.write_text("This is a repeated line of text data\n" * 10000)
        console.print(f"  Text file: {text_file.stat().st_size:,} bytes")

        # Random data (low compression ratio)
        import random
        random_file = Path(tmpdir) / "random_data.bin"
        random_data = bytes(random.randint(0, 255) for _ in range(50000))
        random_file.write_bytes(random_data)
        console.print(f"  Random file: {random_file.stat().st_size:,} bytes")

        # Test different algorithms
        algo_info = CompressionChecker.check_availability()
        results = []

        console.print("\n[cyan]Testing compression algorithms:[/cyan]")

        for comp_type in [CompressionType.GZIP, CompressionType.BZIP2,
                          CompressionType.XZ, CompressionType.LZ4, CompressionType.NONE]:
            if not algo_info[comp_type].available:
                console.print(f"\n  [yellow]Skipping {comp_type.name} (not installed)[/yellow]")
                continue

            console.print(f"\n  [cyan]Testing {comp_type.name}...[/cyan]")

            try:
                # Compress
                compressor = AsyncTarProcessor(comp_type)
                output_file = Path(tmpdir) / f"test.tar{algo_info[comp_type].extension}"

                compress_start = time.time()
                success = await compressor.compress_with_progress(
                    [text_file, random_file],
                    output_file
                )
                compress_time = time.time() - compress_start

                if success:
                    compressed_size = output_file.stat().st_size

                    # Decompress
                    extract_dir = Path(tmpdir) / f"extract_{comp_type.value}"

                    decompress_start = time.time()
                    success = await compressor.decompress_with_progress(
                        output_file,
                        extract_dir
                    )
                    decompress_time = time.time() - decompress_start

                    if success:
                        results.append({
                            'name': comp_type.name,
                            'compressed_size': compressed_size,
                            'compress_time': compress_time,
                            'decompress_time': decompress_time,
                            'desc': algo_info[comp_type].description
                        })

            except Exception as e:
                console.print(f"    [red]Error: {e}[/red]")

        # Display comparison results
        if results:
            console.print("\n\n[bold cyan]Compression Algorithm Performance Comparison:[/bold cyan]")

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Algorithm", style="cyan")
            table.add_column("Compressed Size", style="green")
            table.add_column("Compression Ratio", style="yellow")
            table.add_column("Compress Time", style="blue")
            table.add_column("Decompress Time", style="blue")
            table.add_column("Total Time", style="magenta")

            # Calculate original size
            original_size = text_file.stat().st_size + random_file.stat().st_size

            for r in results:
                compression_ratio = (1 - r['compressed_size'] / original_size) * 100
                total_time = r['compress_time'] + r['decompress_time']

                table.add_row(
                    r['name'],
                    f"{r['compressed_size']:,} B",
                    f"{compression_ratio:.1f}%",
                    f"{r['compress_time']:.2f}s",
                    f"{r['decompress_time']:.2f}s",
                    f"{total_time:.2f}s"
                )

            console.print(table)
            console.print(f"\n[cyan]Original size: {original_size:,} bytes[/cyan]")
    """Test different compression algorithms with compression and decompression"""
    console = Console()
    console.print("\n[bold cyan]=== Compression Algorithm Comparison ===[/bold cyan]")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create different types of test data
        console.print("\n[yellow]Creating test data...[/yellow]")

        # Text data (high compression ratio)
        text_file = Path(tmpdir) / "text_data.txt"
        text_file.write_text("This is a repeated line of text data\n" * 10000)
        console.print(f"  Text file: {text_file.stat().st_size:,} bytes")

        # Random data (low compression ratio)
        import random
        random_file = Path(tmpdir) / "random_data.bin"
        random_data = bytes(random.randint(0, 255) for _ in range(50000))
        random_file.write_bytes(random_data)
        console.print(f"  Random file: {random_file.stat().st_size:,} bytes")

        # Test different algorithms
        algo_info = CompressionChecker.check_availability()
        results = []

        console.print("\n[cyan]Testing compression algorithms:[/cyan]")

        for comp_type in [CompressionType.GZIP, CompressionType.BZIP2,
                          CompressionType.XZ, CompressionType.LZ4, CompressionType.NONE]:
            if not algo_info[comp_type].available:
                console.print(f"\n  [yellow]Skipping {comp_type.name} (not installed)[/yellow]")
                continue

            console.print(f"\n  [cyan]Testing {comp_type.name}...[/cyan]")

            try:
                # Compress
                compressor = AsyncTarProcessor(comp_type)
                output_file = Path(tmpdir) / f"test.tar{algo_info[comp_type].extension}"

                compress_start = time.time()
                success = await compressor.compress_with_progress(
                    [text_file, random_file],
                    output_file
                )
                compress_time = time.time() - compress_start

                if success:
                    compressed_size = output_file.stat().st_size

                    # Decompress
                    extract_dir = Path(tmpdir) / f"extract_{comp_type.value}"

                    decompress_start = time.time()
                    success = await compressor.decompress_with_progress(
                        output_file,
                        extract_dir
                    )
                    decompress_time = time.time() - decompress_start

                    if success:
                        results.append({
                            'name': comp_type.name,
                            'compressed_size': compressed_size,
                            'compress_time': compress_time,
                            'decompress_time': decompress_time,
                            'desc': algo_info[comp_type].description
                        })

            except Exception as e:
                console.print(f"    [red]Error: {e}[/red]")

        # Display comparison results
        if results:
            console.print("\n\n[bold cyan]Compression Algorithm Performance Comparison:[/bold cyan]")

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Algorithm", style="cyan")
            table.add_column("Compressed Size", style="green")
            table.add_column("Compression Ratio", style="yellow")
            table.add_column("Compress Time", style="blue")
            table.add_column("Decompress Time", style="blue")
            table.add_column("Total Time", style="magenta")

            # Calculate original size
            original_size = text_file.stat().st_size + random_file.stat().st_size

            for r in results:
                compression_ratio = (1 - r['compressed_size'] / original_size) * 100
                total_time = r['compress_time'] + r['decompress_time']

                table.add_row(
                    r['name'],
                    f"{r['compressed_size']:,} B",
                    f"{compression_ratio:.1f}%",
                    f"{r['compress_time']:.2f}s",
                    f"{r['decompress_time']:.2f}s",
                    f"{total_time:.2f}s"
                )

            console.print(table)
            console.print(f"\n[cyan]Original size: {original_size:,} bytes[/cyan]")


async def example_auto_detection():
    """Demonstrate auto-detection of compression type"""
    console = Console()
    console.print("\n[bold cyan]=== Auto-Detection Example ===[/bold cyan]")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        test_dir = Path(tmpdir) / "test_data"
        test_dir.mkdir()

        for i in range(3):
            (test_dir / f"file_{i}.txt").write_text(f"Test content {i}\n" * 100)

        # Create archives with different compression types
        archives = []
        algo_info = CompressionChecker.check_availability()

        console.print("\n[yellow]Creating different compressed archives...[/yellow]")

        for comp_type in [CompressionType.GZIP, CompressionType.BZIP2, CompressionType.XZ]:
            if not algo_info[comp_type].available:
                continue

            compressor = AsyncTarProcessor(comp_type)
            output_file = Path(tmpdir) / f"archive{algo_info[comp_type].extension}"

            # Remove extension to test detection
            output_file_noext = Path(tmpdir) / f"archive_{comp_type.value}_noext"

            success = await compressor.compress_with_progress([test_dir], output_file)
            if success:
                # Copy to file without extension
                output_file_noext.write_bytes(output_file.read_bytes())
                archives.append((output_file_noext, comp_type))
                console.print(f"  Created: {output_file_noext.name} ({comp_type.name})")

        # Test auto-detection
        console.print("\n[cyan]Testing auto-detection on files without extensions...[/cyan]")

        for archive_file, expected_type in archives:
            console.print(f"\n  Testing: {archive_file.name}")

            # Create processor without specifying compression type
            processor = AsyncTarProcessor()

            # List contents (this will auto-detect)
            contents = await processor.list_archive_contents(archive_file)

            if contents:
                console.print(f"    [green]✓ Successfully detected and read archive[/green]")
                console.print(f"    Files found: {len(contents)}")

                # Also test decompression
                extract_dir = Path(tmpdir) / f"extract_{archive_file.stem}"
                success = await processor.decompress_with_progress(
                    archive_file,
                    extract_dir
                )

                if success:
                    console.print(f"    [green]✓ Successfully decompressed[/green]")


async def example_interrupt_handling_enhanced():
    """Enhanced interrupt handling for both compression and decompression"""
    console = Console()
    console.print("\n[bold cyan]=== Interrupt Handling Demo (Enhanced) ===[/bold cyan]")

    console.print(Panel(
        "[yellow]Instructions:[/yellow]\n"
        "• Press Ctrl+C during operation to test interrupt handling\n"
        "• First Ctrl+C: Asks for confirmation\n"
        "• Second Ctrl+C: Force interrupts immediately",
        border_style="yellow"
    ))

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create many files to extend operation time
        test_dir = Path(tmpdir) / "many_files"
        test_dir.mkdir()

        console.print("\n[yellow]Creating many test files...[/yellow]")
        for i in range(200):
            file_path = test_dir / f"file_{i:03d}.txt"
            file_path.write_text(f"File content {i}\n" * 100)

        # Test compression interrupt
        if Confirm.ask("\n[cyan]Test compression interrupt?[/cyan]", default=True):
            console.print("\n[yellow]Starting compression (press Ctrl+C to interrupt)...[/yellow]")

            compressor = AsyncTarProcessor(CompressionType.GZIP)
            output_file = Path(tmpdir) / "interruptible.tar.gz"

            await compressor.compress_with_progress([test_dir], output_file)

            if output_file.exists():
                console.print(f"\n[cyan]Archive created: {output_file.stat().st_size:,} bytes[/cyan]")

        # Test decompression interrupt
        if Confirm.ask("\n[cyan]Test decompression interrupt?[/cyan]", default=True):
            # First create a complete archive
            console.print("\n[yellow]Creating archive for decompression test...[/yellow]")

            compressor = AsyncTarProcessor(CompressionType.GZIP)
            archive_file = Path(tmpdir) / "full_archive.tar.gz"

            success = await compressor.compress_with_progress([test_dir], archive_file)

            if success:
                console.print(f"\n[green]✓ Archive created: {archive_file.stat().st_size:,} bytes[/green]")

                console.print("\n[yellow]Starting decompression (press Ctrl+C to interrupt)...[/yellow]")

                extract_dir = Path(tmpdir) / "interrupted_extract"
                decompressor = AsyncTarProcessor()

                await decompressor.decompress_with_progress(archive_file, extract_dir)

                if extract_dir.exists():
                    extracted_count = len(list(extract_dir.rglob("*")))
                    console.print(f"\n[cyan]Files extracted: {extracted_count}[/cyan]")


async def example_mixed_operations():
    """Example of mixed compression and decompression operations"""
    console = Console()
    console.print("\n[bold cyan]=== Mixed Operations Example ===[/bold cyan]")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create source data
        source_dir = Path(tmpdir) / "source"
        source_dir.mkdir()

        console.print("\n[yellow]Creating source files...[/yellow]")

        # Create different file types
        (source_dir / "document.txt").write_text("Important document content\n" * 100)
        (source_dir / "config.json").write_text('{"setting": "value", "debug": true}' * 50)
        (source_dir / "data.csv").write_text("id,name,value\n" + "1,test,100\n" * 100)

        # Create subdirectory
        subdir = source_dir / "logs"
        subdir.mkdir()
        for i in range(5):
            (subdir / f"log_{i}.txt").write_text(f"Log entry {i}\n" * 50)

        # Step 1: Compress to memory with different algorithms
        console.print("\n[cyan]Step 1: Compress to memory with different algorithms[/cyan]")

        archives = {}
        for comp_type in [CompressionType.GZIP, CompressionType.BZIP2]:
            algo_info = CompressionChecker.check_availability()
            if not algo_info[comp_type].available:
                continue

            console.print(f"\n  Compressing with {comp_type.name}...")
            processor = AsyncTarProcessor(comp_type)

            archive_bytes = await processor.compress_to_bytes([source_dir])
            if archive_bytes:
                archives[comp_type] = archive_bytes
                console.print(f"    [green]✓ Size: {len(archive_bytes):,} bytes[/green]")

        # Step 2: Convert between formats
        console.print("\n[cyan]Step 2: Convert between formats[/cyan]")

        if CompressionType.GZIP in archives:
            # Convert GZIP archive to base64 string
            archive_str = base64.b64encode(archives[CompressionType.GZIP]).decode('ascii')
            console.print(f"  GZIP → Base64 string: {len(archive_str):,} characters")

            # Extract from string
            extract_dir = Path(tmpdir) / "from_string"
            processor = AsyncTarProcessor()

            success = await processor.decompress_from_str(archive_str, extract_dir)
            if success:
                console.print(f"  [green]✓ Extracted from base64 string[/green]")

        # Step 3: Chain operations
        console.print("\n[cyan]Step 3: Chain operations (compress → decompress → recompress)[/cyan]")

        # Original compression
        processor1 = AsyncTarProcessor(CompressionType.GZIP)
        temp_archive = Path(tmpdir) / "temp.tar.gz"

        await processor1.compress_with_progress([source_dir], temp_archive)
        console.print(f"  Original: {temp_archive.stat().st_size:,} bytes (GZIP)")

        # Decompress
        temp_extract = Path(tmpdir) / "temp_extract"
        await processor1.decompress_with_progress(temp_archive, temp_extract)

        # Recompress with different algorithm
        if algo_info[CompressionType.XZ].available:
            processor2 = AsyncTarProcessor(CompressionType.XZ)
            final_archive = Path(tmpdir) / "final.tar.xz"

            await processor2.compress_with_progress([temp_extract], final_archive)
            console.print(f"  Recompressed: {final_archive.stat().st_size:,} bytes (XZ)")

            # Compare sizes
            size_diff = temp_archive.stat().st_size - final_archive.stat().st_size
            console.print(f"  [cyan]Size difference: {size_diff:,} bytes saved with XZ[/cyan]")


async def interactive_wizard():
    """Interactive wizard for compression/decompression"""
    console = Console()

    console.print(Panel.fit(
        "[bold cyan]Async Tar Processor - Interactive Wizard[/bold cyan]\n"
        "This wizard will guide you through compression or decompression",
        border_style="cyan"
    ))

    # Choose operation
    console.print("\n[cyan]What would you like to do?[/cyan]")
    console.print("1. Compress files/directories")
    console.print("2. Decompress an archive")
    console.print("3. List archive contents")
    console.print("4. Test memory operations")

    choice = Prompt.ask("Select operation", choices=["1", "2", "3", "4"], default="1")

    if choice == "1":
        # Compression wizard
        console.print("\n[bold yellow]Compression Wizard[/bold yellow]")

        # Get compression type
        console.print("\n[cyan]Select compression algorithm:[/cyan]")
        algo_info = CompressionChecker.check_availability()

        available = []
        for i, (comp_type, info) in enumerate(algo_info.items(), 1):
            if info.available:
                available.append((str(i), comp_type, info))
                console.print(f"{i}. {info.name} - {info.description}")

        algo_choice = Prompt.ask("Select algorithm",
                                 choices=[a[0] for a in available],
                                 default="1")

        selected_type = next(a[1] for a in available if a[0] == algo_choice)

        # Get source paths
        console.print("\n[cyan]Enter paths to compress (type 'done' when finished):[/cyan]")
        paths = []
        while True:
            path_str = Prompt.ask("Path (or 'done')", default="done")
            if path_str.lower() == "done":
                break

            path = Path(path_str).expanduser()
            if path.exists():
                paths.append(path)
                console.print(f"  [green]✓ Added: {path}[/green]")
            else:
                console.print(f"  [red]✗ Path not found: {path}[/red]")

        if not paths:
            console.print("[red]No valid paths provided![/red]")
            return

        # Get output type
        console.print("\n[cyan]Output type:[/cyan]")
        console.print("1. Save to file")
        console.print("2. Save to memory (BytesIO)")
        console.print("3. Get as base64 string")

        output_choice = Prompt.ask("Select output type", choices=["1", "2", "3"], default="1")

        # Process
        processor = AsyncTarProcessor(selected_type)

        if output_choice == "1":
            output_path = Prompt.ask("Output filename",
                                     default=f"archive.tar{algo_info[selected_type].extension}")
            success = await processor.compress_with_progress(paths, output_path)

        elif output_choice == "2":
            memory_archive = await processor.compress_to_memory(paths)
            if memory_archive:
                console.print(f"\n[green]✓ Archive created in memory: {memory_archive.tell():,} bytes[/green]")

        else:  # base64 string
            archive_str = await processor.compress_to_str(paths)
            if archive_str:
                console.print(f"\n[green]✓ Base64 archive created: {len(archive_str):,} characters[/green]")

                if Confirm.ask("Show preview?", default=True):
                    console.print(f"Preview: {archive_str[:100]}...")

                if Confirm.ask("Save to file?", default=False):
                    output_file = Prompt.ask("Filename", default="archive.b64")
                    Path(output_file).write_text(archive_str)
                    console.print(f"[green]✓ Saved to {output_file}[/green]")

    elif choice == "2":
        # Decompression wizard
        console.print("\n[bold yellow]Decompression Wizard[/bold yellow]")

        # Get input type
        console.print("\n[cyan]Input type:[/cyan]")
        console.print("1. From file")
        console.print("2. From base64 string")

        input_choice = Prompt.ask("Select input type", choices=["1", "2"], default="1")

        processor = AsyncTarProcessor()  # Will auto-detect

        if input_choice == "1":
            archive_path = Prompt.ask("Archive file path")
            archive = Path(archive_path).expanduser()

            if not archive.exists():
                console.print(f"[red]File not found: {archive}[/red]")
                return

            output_dir = Prompt.ask("Output directory", default=".")

            success = await processor.decompress_with_progress(archive, output_dir)

        else:  # base64 string
            console.print("Paste base64 string (or 'file' to read from file):")
            b64_input = Prompt.ask("")

            if b64_input.lower() == "file":
                filename = Prompt.ask("Base64 file path")
                b64_input = Path(filename).expanduser().read_text().strip()

            output_dir = Prompt.ask("Output directory", default=".")

            success = await processor.decompress_from_str(b64_input, output_dir)

    elif choice == "3":
        # List contents wizard
        console.print("\n[bold yellow]List Archive Contents[/bold yellow]")

        archive_path = Prompt.ask("Archive file path")
        archive = Path(archive_path).expanduser()

        if not archive.exists():
            console.print(f"[red]File not found: {archive}[/red]")
            return

        processor = AsyncTarProcessor()  # Will auto-detect
        contents = await processor.list_archive_contents(archive)

        if contents:
            console.print(f"\n[cyan]Archive contains {len(contents)} items:[/cyan]")

            # Group by directory
            dirs = {}
            for name, size, is_dir in contents:
                if is_dir:
                    continue

                dir_name = str(Path(name).parent)
                if dir_name not in dirs:
                    dirs[dir_name] = []
                dirs[dir_name].append((Path(name).name, size))

            # Display grouped
            for dir_name, files in sorted(dirs.items()):
                console.print(f"\n[yellow]{dir_name}/[/yellow]")
                for filename, size in sorted(files):
                    console.print(f"  {filename} ({processor._format_size(size)})")

    else:  # Memory operations test
        console.print("\n[bold yellow]Memory Operations Test[/bold yellow]")

        # Create test data
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Test content for memory operations\n" * 100)

            processor = AsyncTarProcessor(CompressionType.GZIP)

            # Test all memory operations
            console.print("\n[cyan]Testing memory operations...[/cyan]")

            # BytesIO
            console.print("\n1. BytesIO operation...")
            bio = await processor.compress_to_memory([test_file])
            if bio:
                console.print(f"   [green]✓ BytesIO size: {bio.tell():,} bytes[/green]")

            # bytes
            console.print("\n2. bytes operation...")
            data = await processor.compress_to_bytes([test_file])
            if data:
                console.print(f"   [green]✓ bytes size: {len(data):,} bytes[/green]")

            # str (base64)
            console.print("\n3. base64 string operation...")
            s = await processor.compress_to_str([test_file])
            if s:
                console.print(f"   [green]✓ string length: {len(s):,} characters[/green]")

            # Test round-trip
            console.print("\n[cyan]Testing round-trip (compress → decompress)...[/cyan]")

            extract_dir = Path(tmpdir) / "roundtrip"
            success = await processor.decompress_from_str(s, extract_dir)

            if success:
                extracted_file = extract_dir / "test.txt"
                if extracted_file.exists():
                    if extracted_file.read_text() == test_file.read_text():
                        console.print("   [green]✓ Round-trip successful - data matches![/green]")
                    else:
                        console.print("   [red]✗ Round-trip failed - data mismatch![/red]")


async def run_comprehensive_tests():
    """Run comprehensive test suite"""
    console = Console()

    console.print(Panel.fit(
        "[bold cyan]Comprehensive Test Suite[/bold cyan]\n"
        "This will run various tests to demonstrate all features",
        border_style="cyan"
    ))

    tests = [
        ("Basic Compression & Decompression", example_basic_compression_decompression),
        ("Enhanced Memory Operations", example_memory_operations_enhanced),
        ("Compression Algorithm Comparison", example_different_compressions_comparison),
        ("Auto-Detection", example_auto_detection),
        ("Interrupt Handling", example_interrupt_handling_enhanced),
        ("Mixed Operations", example_mixed_operations),
    ]

    for i, (name, test_func) in enumerate(tests, 1):
        console.print(f"\n[bold cyan]Test {i}/{len(tests)}: {name}[/bold cyan]")

        try:
            await test_func()
            console.print(f"[green]✓ {name} completed successfully[/green]")
        except KeyboardInterrupt:
            console.print(f"[yellow]⚠ {name} interrupted by user[/yellow]")
        except Exception as e:
            console.print(f"[red]✗ {name} failed: {e}[/red]")
            import traceback
            traceback.print_exc()

        if i < len(tests):
            if not Confirm.ask("\nContinue to next test?", default=True):
                break


async def main():
    """Main function"""
    console = Console()

    examples = [
        ("Basic Compression & Decompression", example_basic_compression_decompression),
        ("Enhanced Memory Operations (BytesIO, bytes, str)", example_memory_operations_enhanced),
        ("Compression Availability Check & Fallback", example_compression_availability),
        ("Compression Algorithm Comparison", example_different_compressions_comparison),
        ("Auto-Detection of Compression Type", example_auto_detection),
        ("Interrupt Handling (Enhanced)", example_interrupt_handling_enhanced),
        ("Mixed Operations", example_mixed_operations),
        ("Interactive Wizard", interactive_wizard),
        ("Run Comprehensive Test Suite", run_comprehensive_tests),
        ("Check Compression Support", lambda: CompressionChecker.print_availability_table(console)),
        ("Run Diagnostic", lambda: CompressionChecker.run_diagnostic(console)),
        ("Run Benchmark Suite", None)  # Will import benchmark.py
    ]

    console.print(Panel.fit(
        "[bold cyan]Async Tar Processor Demo Program[/bold cyan]\n"
        "Now with full compression AND decompression support!",
        border_style="cyan"
    ))

    for i, (name, func) in enumerate(examples, 1):
        console.print(f"\n{i}. {name}")

    choice = Prompt.ask(
        "\nSelect example to run",
        choices=[str(i) for i in range(1, len(examples) + 1)] + ['a'],
        default="8"
    )

    if choice.lower() == 'a':
        # Run all examples except benchmark and diagnostic
        for i, (name, func) in enumerate(examples[:-3]):  # Skip benchmark, diagnostic, and support check
            if func and asyncio.iscoroutinefunction(func):
                console.print(f"\n[bold magenta]Running: {name}[/bold magenta]")
                await func()

                if i < len(examples) - 4:  # Don't wait after last example
                    input("\nPress Enter to continue to next example...")
    else:
        idx = int(choice) - 1
        if idx == len(examples) - 1:  # Benchmark
            try:
                from benchmark import main as benchmark_main
                await benchmark_main()
            except ImportError:
                console.print("[red]benchmark.py not found![/red]")
        elif idx == len(examples) - 2:  # Diagnostic
            CompressionChecker.run_diagnostic(console)
        elif idx == len(examples) - 3:  # Check support
            CompressionChecker.print_availability_table(console)
        else:
            if examples[idx][1]:
                await examples[idx][1]()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted")
        sys.exit(0)