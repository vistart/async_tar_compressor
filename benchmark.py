#!/usr/bin/env python3
"""
Comprehensive Benchmark Testing for Async Tar Compressor
Tests different data types, file sizes, algorithms, and compression levels
"""

import asyncio
import json
import random
import statistics
import tempfile
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.prompt import Prompt, Confirm
from rich.table import Table

from tar_compressor import AsyncTarCompressor, CompressionType, CompressionChecker


@dataclass
class BenchmarkResult:
    """Single benchmark result"""
    algorithm: str
    compression_level: int
    data_type: str
    file_size: int
    file_count: int
    original_size: int
    compressed_size: int
    compression_time: float
    compression_ratio: float
    speed_mbps: float


@dataclass
class BenchmarkConfig:
    """Benchmark configuration"""
    algorithms: List[CompressionType]
    compression_levels: Dict[CompressionType, List[int]]
    data_types: List[str]
    file_sizes: List[Tuple[str, int]]
    file_counts: List[int]
    iterations: int = 3


class DataGenerator:
    """Generate different types of test data"""

    @staticmethod
    def generate_random_text(size: int) -> bytes:
        """Generate random text data (ASCII printable characters)"""
        chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 \n\t.,!?'
        return ''.join(random.choice(chars) for _ in range(size)).encode('utf-8')

    @staticmethod
    def generate_repetitive_text(size: int) -> bytes:
        """Generate highly repetitive text data"""
        pattern = "This is a repetitive pattern that should compress very well. " * 10
        repetitions = size // len(pattern) + 1
        return (pattern * repetitions)[:size].encode('utf-8')

    @staticmethod
    def generate_json_like(size: int) -> bytes:
        """Generate JSON-like structured data"""
        data = []
        current_size = 0
        while current_size < size:
            record = {
                "id": random.randint(1000, 9999),
                "name": f"User_{random.randint(1, 1000)}",
                "email": f"user{random.randint(1, 1000)}@example.com",
                "active": random.choice([True, False]),
                "score": round(random.uniform(0, 100), 2),
                "tags": [f"tag{i}" for i in range(random.randint(1, 5))]
            }
            record_str = json.dumps(record) + "\n"
            data.append(record_str)
            current_size += len(record_str)

        return ''.join(data)[:size].encode('utf-8')

    @staticmethod
    def generate_log_like(size: int) -> bytes:
        """Generate log-like data"""
        log_levels = ['INFO', 'DEBUG', 'WARN', 'ERROR']
        messages = [
            'Application started successfully',
            'Processing request from client',
            'Database connection established',
            'Cache miss, fetching from database',
            'Request completed in {} ms',
            'Memory usage: {} MB',
            'Active connections: {}'
        ]

        logs = []
        current_size = 0
        while current_size < size:
            timestamp = datetime.now().isoformat()
            level = random.choice(log_levels)
            message = random.choice(messages).format(random.randint(10, 1000))
            log_line = f"[{timestamp}] [{level}] {message}\n"
            logs.append(log_line)
            current_size += len(log_line)

        return ''.join(logs)[:size].encode('utf-8')

    @staticmethod
    def generate_binary_random(size: int) -> bytes:
        """Generate completely random binary data"""
        return bytes(random.randint(0, 255) for _ in range(size))

    @staticmethod
    def generate_binary_sparse(size: int) -> bytes:
        """Generate sparse binary data (lots of zeros)"""
        data = bytearray(size)
        # Fill only 10% with random data
        num_values = size // 10
        positions = random.sample(range(size), num_values)
        for pos in positions:
            data[pos] = random.randint(1, 255)
        return bytes(data)


class CompressionBenchmark:
    """Main benchmark class"""

    # Default compression levels for each algorithm
    DEFAULT_LEVELS = {
        CompressionType.GZIP: [1, 5, 9],  # 1=fastest, 9=best compression
        CompressionType.BZIP2: [1, 5, 9],  # 1=fastest, 9=best compression
        CompressionType.XZ: [0, 3, 6, 9],  # 0=fastest, 9=best compression
        CompressionType.LZ4: [1, 3, 9],  # LZ4 levels
        CompressionType.NONE: [0]  # No compression
    }

    # Default file sizes for testing
    DEFAULT_SIZES = [
        ("1KB", 1024),
        ("10KB", 10 * 1024),
        ("100KB", 100 * 1024),
        ("1MB", 1024 * 1024),
        ("10MB", 10 * 1024 * 1024)
    ]

    def __init__(self):
        self.console = Console()
        self.results: List[BenchmarkResult] = []

    def get_interactive_config(self) -> BenchmarkConfig:
        """Get benchmark configuration interactively"""
        self.console.print(Panel.fit(
            "[bold cyan]Tar Compression Benchmark Configuration[/bold cyan]",
            border_style="cyan"
        ))

        # Select algorithms
        self.console.print("\n[cyan]Select compression algorithms to test:[/cyan]")
        algo_info = CompressionChecker.check_availability()
        available_algos = []

        for i, (comp_type, info) in enumerate(algo_info.items(), 1):
            if info.available:
                status = "[green]✓[/green]"
                available_algos.append((comp_type, info))
            else:
                status = "[red]✗[/red]"

            self.console.print(f"{i}. {status} {info.name} - {info.description}")

        selected_indices = Prompt.ask(
            "Select algorithms (comma-separated numbers, or 'all' for all available)",
            default="all"
        )

        if selected_indices.lower() == 'all':
            selected_algos = [algo for algo, _ in available_algos]
        else:
            indices = [int(x.strip()) - 1 for x in selected_indices.split(',')]
            all_algos = list(algo_info.keys())
            selected_algos = [all_algos[i] for i in indices if i < len(all_algos)]

        # Select compression levels
        self.console.print("\n[cyan]Compression levels configuration:[/cyan]")
        use_default_levels = Confirm.ask(
            "Use default compression levels for each algorithm?",
            default=True
        )

        compression_levels = {}
        if use_default_levels:
            compression_levels = self.DEFAULT_LEVELS.copy()
        else:
            for algo in selected_algos:
                if algo == CompressionType.NONE:
                    compression_levels[algo] = [0]
                    continue

                levels_str = Prompt.ask(
                    f"Compression levels for {algo.name} (comma-separated)",
                    default="1,5,9"
                )
                compression_levels[algo] = [int(x.strip()) for x in levels_str.split(',')]

        # Select data types
        self.console.print("\n[cyan]Select data types to test:[/cyan]")
        data_types_options = [
            ("random_text", "Random text (ASCII)"),
            ("repetitive_text", "Repetitive text"),
            ("json_like", "JSON-like structured data"),
            ("log_like", "Log file format"),
            ("binary_random", "Random binary data"),
            ("binary_sparse", "Sparse binary data (mostly zeros)")
        ]

        for i, (key, desc) in enumerate(data_types_options, 1):
            self.console.print(f"{i}. {desc}")

        selected_types = Prompt.ask(
            "Select data types (comma-separated numbers, or 'all')",
            default="all"
        )

        if selected_types.lower() == 'all':
            data_types = [key for key, _ in data_types_options]
        else:
            indices = [int(x.strip()) - 1 for x in selected_types.split(',')]
            data_types = [data_types_options[i][0] for i in indices if i < len(data_types_options)]

        # Select file sizes
        self.console.print("\n[cyan]Select file sizes to test:[/cyan]")
        use_default_sizes = Confirm.ask(
            "Use default file sizes (1KB, 10KB, 100KB, 1MB, 10MB)?",
            default=True
        )

        if use_default_sizes:
            file_sizes = self.DEFAULT_SIZES.copy()
        else:
            file_sizes = []
            while True:
                size_str = Prompt.ask("Enter file size (e.g., '5MB', '500KB') or 'done'")
                if size_str.lower() == 'done':
                    break

                # Parse size
                size_str = size_str.upper()
                if size_str.endswith('KB'):
                    size = int(size_str[:-2]) * 1024
                elif size_str.endswith('MB'):
                    size = int(size_str[:-2]) * 1024 * 1024
                elif size_str.endswith('GB'):
                    size = int(size_str[:-2]) * 1024 * 1024 * 1024
                else:
                    size = int(size_str)

                file_sizes.append((size_str, size))

        # File counts
        self.console.print("\n[cyan]Select number of files per test:[/cyan]")
        file_counts_str = Prompt.ask(
            "Number of files to create for each test (comma-separated)",
            default="1,10,50"
        )
        file_counts = [int(x.strip()) for x in file_counts_str.split(',')]

        # Iterations
        while True:
            iterations_str = Prompt.ask(
                "\n[cyan]Number of iterations per test (1-10)[/cyan]",
                default="3"
            )
            try:
                iterations = int(iterations_str)
                if 1 <= iterations <= 10:
                    break
                else:
                    self.console.print("[red]Please enter a number between 1 and 10[/red]")
            except ValueError:
                self.console.print("[red]Please enter a valid number[/red]")

        return BenchmarkConfig(
            algorithms=selected_algos,
            compression_levels=compression_levels,
            data_types=data_types,
            file_sizes=file_sizes,
            file_counts=file_counts,
            iterations=iterations
        )

    async def run_single_benchmark(
            self,
            algorithm: CompressionType,
            level: int,
            data_type: str,
            file_size: int,
            file_count: int,
            tmpdir: Path
    ) -> BenchmarkResult:
        """Run a single benchmark test"""
        # Generate test data
        generator_map = {
            'random_text': DataGenerator.generate_random_text,
            'repetitive_text': DataGenerator.generate_repetitive_text,
            'json_like': DataGenerator.generate_json_like,
            'log_like': DataGenerator.generate_log_like,
            'binary_random': DataGenerator.generate_binary_random,
            'binary_sparse': DataGenerator.generate_binary_sparse
        }

        generator = generator_map[data_type]

        # Create test files
        test_dir = tmpdir / f"test_{algorithm.value}_{level}_{data_type}"
        test_dir.mkdir(exist_ok=True)

        total_size = 0
        for i in range(file_count):
            file_path = test_dir / f"file_{i}.dat"
            data = generator(file_size)
            file_path.write_bytes(data)
            total_size += len(data)

        # Setup compression with level
        if algorithm == CompressionType.GZIP:
            # Monkey patch gzip compression level
            import gzip
            original_open = gzip.open

            def patched_open(*args, **kwargs):
                if 'compresslevel' not in kwargs:
                    kwargs['compresslevel'] = level
                return original_open(*args, **kwargs)

            gzip.open = patched_open
        elif algorithm == CompressionType.BZIP2:
            # Monkey patch bz2 compression level
            import bz2
            original_open = bz2.open

            def patched_open(*args, **kwargs):
                if 'compresslevel' not in kwargs:
                    kwargs['compresslevel'] = level
                return original_open(*args, **kwargs)

            bz2.open = patched_open
        elif algorithm == CompressionType.XZ:
            # Monkey patch lzma compression level
            import lzma
            original_open = lzma.open

            def patched_open(*args, **kwargs):
                if 'preset' not in kwargs:
                    kwargs['preset'] = level
                return original_open(*args, **kwargs)

            lzma.open = patched_open

        # Run compression
        compressor = AsyncTarCompressor(algorithm)
        output_file = tmpdir / f"test.tar.{algorithm.value}"

        start_time = time.time()
        success = await compressor.compress_with_progress([test_dir], output_file)
        end_time = time.time()

        if not success:
            raise RuntimeError("Compression failed")

        # Calculate results
        compressed_size = output_file.stat().st_size
        compression_time = end_time - start_time
        compression_ratio = (1 - compressed_size / total_size) * 100
        speed_mbps = (total_size / compression_time) / (1024 * 1024)

        # Cleanup
        output_file.unlink()
        for f in test_dir.rglob("*"):
            if f.is_file():
                f.unlink()
        test_dir.rmdir()

        # Restore original functions
        if algorithm == CompressionType.GZIP:
            import gzip
            gzip.open = original_open
        elif algorithm == CompressionType.BZIP2:
            import bz2
            bz2.open = original_open
        elif algorithm == CompressionType.XZ:
            import lzma
            lzma.open = original_open

        return BenchmarkResult(
            algorithm=algorithm.name,
            compression_level=level,
            data_type=data_type,
            file_size=file_size,
            file_count=file_count,
            original_size=total_size,
            compressed_size=compressed_size,
            compression_time=compression_time,
            compression_ratio=compression_ratio,
            speed_mbps=speed_mbps
        )

    async def run_benchmarks(self, config: BenchmarkConfig):
        """Run all benchmarks"""
        total_tests = (
                len(config.algorithms) *
                sum(len(config.compression_levels.get(algo, [1])) for algo in config.algorithms) *
                len(config.data_types) *
                len(config.file_sizes) *
                len(config.file_counts)
        )

        self.console.print(
            f"\n[cyan]Running {total_tests} benchmark tests with {config.iterations} iterations each...[/cyan]")

        with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=self.console
        ) as progress:

            task = progress.add_task("[green]Running benchmarks...", total=total_tests)

            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)

                for algorithm in config.algorithms:
                    levels = config.compression_levels.get(algorithm, [0])

                    for level in levels:
                        for data_type in config.data_types:
                            for size_name, size_bytes in config.file_sizes:
                                for file_count in config.file_counts:
                                    # Run multiple iterations
                                    iteration_results = []

                                    for iteration in range(config.iterations):
                                        try:
                                            result = await self.run_single_benchmark(
                                                algorithm, level, data_type,
                                                size_bytes, file_count, tmpdir_path
                                            )
                                            iteration_results.append(result)
                                        except Exception as e:
                                            self.console.print(f"[red]Error in benchmark: {e}[/red]")
                                            continue

                                    # Average the results
                                    if iteration_results:
                                        avg_result = BenchmarkResult(
                                            algorithm=iteration_results[0].algorithm,
                                            compression_level=iteration_results[0].compression_level,
                                            data_type=iteration_results[0].data_type,
                                            file_size=iteration_results[0].file_size,
                                            file_count=iteration_results[0].file_count,
                                            original_size=iteration_results[0].original_size,
                                            compressed_size=int(
                                                statistics.mean(r.compressed_size for r in iteration_results)),
                                            compression_time=statistics.mean(
                                                r.compression_time for r in iteration_results),
                                            compression_ratio=statistics.mean(
                                                r.compression_ratio for r in iteration_results),
                                            speed_mbps=statistics.mean(r.speed_mbps for r in iteration_results)
                                        )
                                        self.results.append(avg_result)

                                    progress.update(task, advance=1)

    def display_results(self):
        """Display benchmark results"""
        if not self.results:
            self.console.print("[red]No results to display[/red]")
            return

        # Group results by data type
        data_types = sorted(set(r.data_type for r in self.results))

        for data_type in data_types:
            self.console.print(f"\n[bold cyan]Results for {data_type} data:[/bold cyan]")

            # Create table
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Algorithm", style="cyan")
            table.add_column("Level", style="yellow")
            table.add_column("File Size", style="green")
            table.add_column("File Count", style="blue")
            table.add_column("Compression %", style="red")
            table.add_column("Speed (MB/s)", style="magenta")
            table.add_column("Time (s)", style="white")

            # Filter and sort results
            type_results = [r for r in self.results if r.data_type == data_type]
            type_results.sort(key=lambda r: (r.file_size, r.algorithm, r.compression_level))

            for r in type_results:
                size_str = self._format_size(r.file_size)
                table.add_row(
                    r.algorithm,
                    str(r.compression_level),
                    size_str,
                    str(r.file_count),
                    f"{r.compression_ratio:.1f}%",
                    f"{r.speed_mbps:.1f}",
                    f"{r.compression_time:.2f}"
                )

            self.console.print(table)

    def save_results(self, filename: str = "benchmark_results.json"):
        """Save results to JSON file"""
        if not self.results:
            return

        data = {
            'timestamp': datetime.now().isoformat(),
            'results': [asdict(r) for r in self.results]
        }

        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

        self.console.print(f"\n[green]Results saved to {filename}[/green]")

    def generate_summary(self):
        """Generate summary statistics"""
        if not self.results:
            return

        self.console.print("\n[bold cyan]Benchmark Summary:[/bold cyan]")

        # Best compression ratio by data type
        self.console.print("\n[yellow]Best Compression Ratio by Data Type:[/yellow]")
        data_types = sorted(set(r.data_type for r in self.results))
        for data_type in data_types:
            type_results = [r for r in self.results if r.data_type == data_type]
            best = max(type_results, key=lambda r: r.compression_ratio)
            self.console.print(
                f"  {data_type}: {best.algorithm} level {best.compression_level} ({best.compression_ratio:.1f}%)")

        # Fastest compression by data type
        self.console.print("\n[yellow]Fastest Compression by Data Type:[/yellow]")
        for data_type in data_types:
            type_results = [r for r in self.results if r.data_type == data_type]
            fastest = max(type_results, key=lambda r: r.speed_mbps)
            self.console.print(
                f"  {data_type}: {fastest.algorithm} level {fastest.compression_level} ({fastest.speed_mbps:.1f} MB/s)")

        # Overall recommendations
        self.console.print("\n[yellow]Recommendations:[/yellow]")

        # For text data
        text_results = [r for r in self.results if
                        'text' in r.data_type or 'json' in r.data_type or 'log' in r.data_type]
        if text_results:
            best_text = max(text_results, key=lambda r: r.compression_ratio / (r.compression_time + 0.1))
            self.console.print(f"  For text data: {best_text.algorithm} level {best_text.compression_level}")

        # For binary data
        binary_results = [r for r in self.results if 'binary' in r.data_type]
        if binary_results:
            best_binary = max(binary_results, key=lambda r: r.speed_mbps)
            self.console.print(f"  For binary data: {best_binary.algorithm} level {best_binary.compression_level}")

    @staticmethod
    def _format_size(size: int) -> str:
        """Format file size"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.0f}{unit}"
            size /= 1024.0
        return f"{size:.0f}TB"


async def main():
    """Main function"""
    console = Console()

    console.print(Panel.fit(
        "[bold cyan]Tar Compression Benchmark Suite[/bold cyan]\n"
        "Comprehensive testing of compression algorithms",
        border_style="cyan"
    ))

    # Check algorithm availability first
    console.print("\n[cyan]Checking compression algorithm availability...[/cyan]")
    CompressionChecker.print_availability_table(console)

    # Create benchmark instance
    benchmark = CompressionBenchmark()

    # Get configuration
    config = benchmark.get_interactive_config()

    # Confirm before running
    console.print("\n[bold]Benchmark Configuration:[/bold]")
    console.print(f"  Algorithms: {', '.join(a.name for a in config.algorithms)}")
    console.print(f"  Data types: {', '.join(config.data_types)}")
    console.print(f"  File sizes: {', '.join(name for name, _ in config.file_sizes)}")
    console.print(f"  File counts: {', '.join(str(c) for c in config.file_counts)}")
    console.print(f"  Iterations: {config.iterations}")

    if not Confirm.ask("\n[yellow]Start benchmark?[/yellow]", default=True):
        return

    # Run benchmarks
    start_time = time.time()
    await benchmark.run_benchmarks(config)
    end_time = time.time()

    console.print(f"\n[green]Benchmark completed in {end_time - start_time:.1f} seconds[/green]")

    # Display results
    benchmark.display_results()
    benchmark.generate_summary()

    # Save results
    if Confirm.ask("\n[yellow]Save results to file?[/yellow]", default=True):
        filename = Prompt.ask("Filename", default="benchmark_results.json")
        benchmark.save_results(filename)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBenchmark interrupted")