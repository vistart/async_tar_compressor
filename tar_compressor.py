#!/usr/bin/env python3
"""
Async Tar Compressor - Support progress bar display and intelligent interrupt handling
Supported compression algorithms: gzip, bzip2, xz/lzma, lz4
Support both file and in-memory (BytesIO) operations
"""

import asyncio
import signal
import sys
import tarfile
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Optional, List, Union, Dict, BinaryIO

# Standard library compression modules

# Optional third-party compression libraries
try:
    import lz4.frame

    HAS_LZ4 = True
except ImportError:
    HAS_LZ4 = False

from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeRemainingColumn,
    TimeElapsedColumn,
    MofNCompleteColumn,
    DownloadColumn
)
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.panel import Panel
from rich.table import Table


class CompressionType(Enum):
    """Supported compression types"""
    GZIP = "gz"
    BZIP2 = "bz2"
    XZ = "xz"
    LZ4 = "lz4"
    NONE = ""


@dataclass
class CompressionInfo:
    """Compression algorithm information"""
    name: str
    module: str
    extension: str
    available: bool
    install_cmd: Optional[str] = None
    description: str = ""


class CompressionChecker:
    """Compression algorithm availability checker"""

    @staticmethod
    def check_module_availability(module_name: str) -> bool:
        """Check if a module is actually available"""
        try:
            __import__(module_name)
            return True
        except ImportError:
            return False

    @staticmethod
    def check_availability() -> Dict[CompressionType, CompressionInfo]:
        """Check availability of all compression algorithms"""
        # Check actual module availability
        has_gzip = CompressionChecker.check_module_availability("gzip") and \
                   CompressionChecker.check_module_availability("zlib")
        has_bz2 = CompressionChecker.check_module_availability("bz2")
        has_lzma = CompressionChecker.check_module_availability("lzma")

        info = {
            CompressionType.GZIP: CompressionInfo(
                name="GZIP",
                module="gzip",
                extension=".gz",
                available=has_gzip,
                install_cmd="System dependency: zlib1g-dev (Debian/Ubuntu) or zlib-devel (RHEL/CentOS)",
                description="Standard compression, balanced compression ratio and speed"
            ),
            CompressionType.BZIP2: CompressionInfo(
                name="BZIP2",
                module="bz2",
                extension=".bz2",
                available=has_bz2,
                install_cmd="System dependency: libbz2-dev (Debian/Ubuntu) or bzip2-devel (RHEL/CentOS)",
                description="High compression ratio, but slower"
            ),
            CompressionType.XZ: CompressionInfo(
                name="XZ/LZMA",
                module="lzma",
                extension=".xz",
                available=has_lzma,
                install_cmd="System dependency: liblzma-dev (Debian/Ubuntu) or xz-devel (RHEL/CentOS)",
                description="Highest compression ratio, slowest speed"
            ),
            CompressionType.LZ4: CompressionInfo(
                name="LZ4",
                module="lz4",
                extension=".lz4",
                available=HAS_LZ4,
                install_cmd="pip install lz4",
                description="Extremely fast compression, lower compression ratio"
            ),
            CompressionType.NONE: CompressionInfo(
                name="No compression",
                module="",
                extension="",
                available=True,
                description="Archive only, no compression"
            )
        }

        return info

    @staticmethod
    def print_availability_table(console: Console):
        """Print compression algorithm availability table"""
        table = Table(title="Compression Algorithm Support", show_header=True)
        table.add_column("Algorithm", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Description", style="yellow")
        table.add_column("Install Command", style="blue")

        info_dict = CompressionChecker.check_availability()

        for comp_type, info in info_dict.items():
            if comp_type == CompressionType.NONE:
                continue

            status = "✓ Available" if info.available else "✗ Not Available"
            status_style = "green" if info.available else "red"

            table.add_row(
                info.name,
                f"[{status_style}]{status}[/{status_style}]",
                info.description,
                info.install_cmd or "-"
            )

        console.print(table)

        # Check for missing critical modules
        missing_critical = []
        for comp_type, info in info_dict.items():
            if comp_type in [CompressionType.GZIP, CompressionType.BZIP2, CompressionType.XZ] and not info.available:
                missing_critical.append(info.name)

        if missing_critical:
            console.print("\n[red]Warning: Missing critical compression module support![/red]")
            console.print(f"Affected modules: {', '.join(missing_critical)}")

            console.print("\n[yellow]Solutions:[/yellow]")
            console.print("1. Install system dependencies:")
            console.print("   Ubuntu/Debian: sudo apt install zlib1g-dev libbz2-dev liblzma-dev")
            console.print("   CentOS/RHEL:   sudo yum install zlib-devel bzip2-devel xz-devel")
            console.print("   macOS:         brew install zlib bzip2 xz")

            console.print("\n2. Rebuild Python with compression support:")
            console.print("   ./configure --enable-optimizations")
            console.print("   make -j$(nproc)")
            console.print("   sudo make altinstall")

            console.print("\n3. Or use a complete Python distribution:")
            console.print("   Ubuntu/Debian: sudo apt install python3-full")
            console.print("   Anaconda/Miniconda: conda install python")

    @staticmethod
    def run_diagnostic(console: Console):
        """Run comprehensive compression support diagnostic"""
        console.print(Panel.fit(
            "[bold cyan]Python Compression Support Diagnostic[/bold cyan]",
            border_style="cyan"
        ))

        console.print(f"\n[cyan]Python Version:[/cyan] {sys.version}")
        console.print(f"[cyan]Platform:[/cyan] {sys.platform}")

        console.print("\n[cyan]Compression Module Detection:[/cyan]")

        # Detailed module checks
        modules_to_check = [
            ("zlib", "GZIP compression base (required for gzip)", True),
            ("gzip", "GZIP file operations", True),
            ("bz2", "BZIP2 compression support", True),
            ("_bz2", "BZIP2 C extension (performance)", False),
            ("lzma", "LZMA/XZ compression support", True),
            ("_lzma", "LZMA C extension (performance)", False),
            ("lz4", "LZ4 compression (optional)", False),
            ("lz4.frame", "LZ4 frame format (optional)", False),
        ]

        all_good = True
        for module_name, description, critical in modules_to_check:
            try:
                __import__(module_name)
                console.print(f"  [green]✓[/green] {module_name:<12} - {description}")
            except ImportError as e:
                if critical:
                    console.print(f"  [red]✗[/red] {module_name:<12} - {description} [red](MISSING)[/red]")
                    all_good = False
                else:
                    console.print(f"  [yellow]?[/yellow] {module_name:<12} - {description} [yellow](optional)[/yellow]")

        if all_good:
            console.print("\n[green]All critical compression modules are available![/green]")
        else:
            console.print("\n[red]Some critical modules are missing. See solutions above.[/red]")

        return all_good


@dataclass
class CompressionStats:
    """Compression statistics"""
    total_files: int = 0
    processed_files: int = 0
    total_size: int = 0
    processed_size: int = 0
    compressed_size: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class InterruptHandler:
    """Interrupt handler"""

    def __init__(self):
        self.interrupt_count = 0
        self.user_confirmed = False
        self.interrupted = False
        self._original_sigint = None

    def setup(self):
        """Setup signal handling"""
        self._original_sigint = signal.signal(signal.SIGINT, self._handle_interrupt)
        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, self._handle_interrupt)

    def cleanup(self):
        """Restore original signal handling"""
        if self._original_sigint:
            signal.signal(signal.SIGINT, self._original_sigint)

    def _handle_interrupt(self, signum, frame):
        """Handle interrupt signal"""
        self.interrupt_count += 1
        if self.interrupt_count == 1:
            # First interrupt, set flag for main program to ask
            self.interrupted = True
        else:
            # Second interrupt, force exit
            console = Console()
            console.print("\n[red]Force interrupt![/red]")
            self.cleanup()
            sys.exit(1)


class AsyncTarCompressor:
    """Async Tar Compressor"""

    def __init__(self, compression: CompressionType = CompressionType.GZIP):
        self.compression = compression
        self.console = Console()
        self.stats = CompressionStats()
        self.interrupt_handler = InterruptHandler()
        self._cancelled = False

        # Check compression algorithm availability
        self._check_compression_availability()

    def _check_compression_availability(self):
        """Check if selected compression algorithm is available"""
        info_dict = CompressionChecker.check_availability()
        info = info_dict.get(self.compression)

        if info and not info.available:
            self.console.print(f"\n[red]Error: {info.name} compression algorithm not available![/red]")
            if info.install_cmd:
                self.console.print(f"[yellow]Please install first: {info.install_cmd}[/yellow]")

            # Show all available compression algorithms
            self.console.print("\n[cyan]Available compression algorithms:[/cyan]")
            for comp_type, comp_info in info_dict.items():
                if comp_info.available and comp_type != CompressionType.NONE:
                    self.console.print(f"  • {comp_info.name}: {comp_info.description}")

            raise RuntimeError(f"{info.name} compression algorithm not available")

    def _get_compression_mode(self) -> str:
        """Get tarfile compression mode"""
        # Standard tarfile supported modes
        standard_modes = {
            CompressionType.GZIP: "w:gz",
            CompressionType.BZIP2: "w:bz2",
            CompressionType.XZ: "w:xz",
            CompressionType.NONE: "w"
        }

        if self.compression in standard_modes:
            return standard_modes[self.compression]
        elif self.compression == CompressionType.LZ4:
            # LZ4 needs special handling
            return "w"  # Create uncompressed tar first
        else:
            raise ValueError(f"Unsupported compression type: {self.compression}")

    def _calculate_total_size(self, paths: List[Path]) -> tuple[int, int]:
        """Calculate total file count and size"""
        total_files = 0
        total_size = 0

        for path in paths:
            if path.is_file():
                total_files += 1
                total_size += path.stat().st_size
            elif path.is_dir():
                for p in path.rglob("*"):
                    if p.is_file():
                        total_files += 1
                        total_size += p.stat().st_size

        return total_files, total_size

    async def _check_interrupt(self) -> bool:
        """Check and handle interrupt"""
        if self.interrupt_handler.interrupted and not self.interrupt_handler.user_confirmed:
            # Pause progress display
            confirmed = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: Confirm.ask("\n[yellow]Do you want to interrupt the compression operation?[/yellow]",
                                    default=False)
            )

            if confirmed:
                self.interrupt_handler.user_confirmed = True
                self._cancelled = True
                return True
            else:
                # Reset interrupt state
                self.interrupt_handler.interrupted = False
                self.interrupt_handler.interrupt_count = 0

        return self._cancelled

    async def compress_with_progress(
            self,
            source_paths: List[Union[str, Path]],
            output_file: Union[str, Path, BinaryIO],
            chunk_size: int = 1024 * 1024  # 1MB chunks
    ) -> bool:
        """
        Compress files with progress display

        Args:
            source_paths: List of files or directories to compress
            output_file: Output compressed file path or BytesIO object
            chunk_size: Chunk size for reading files

        Returns:
            bool: Whether completed successfully
        """
        # Setup interrupt handling
        self.interrupt_handler.setup()

        try:
            # Convert paths
            paths = [Path(p) for p in source_paths]

            # Check if output is BytesIO or file path
            is_memory_output = isinstance(output_file, (BytesIO, BinaryIO))
            output_path = None if is_memory_output else Path(output_file)

            # Calculate total size
            self.console.print("[cyan]Analyzing files...[/cyan]")
            self.stats.total_files, self.stats.total_size = self._calculate_total_size(paths)
            self.stats.start_time = datetime.now()

            # Display compression algorithm info
            info_dict = CompressionChecker.check_availability()
            comp_info = info_dict[self.compression]
            self.console.print(f"[green]Using {comp_info.name} compression[/green]")

            if self.compression == CompressionType.LZ4:
                # LZ4 needs special handling
                success = await self._compress_with_lz4(paths, output_file, chunk_size)
            else:
                # Use standard tarfile handling
                success = await self._compress_with_tarfile(paths, output_file, chunk_size)

            if success:
                self.stats.end_time = datetime.now()
                # Get compressed file size
                if is_memory_output:
                    self.stats.compressed_size = output_file.tell()
                elif output_path and output_path.exists():
                    self.stats.compressed_size = output_path.stat().st_size
                self._show_summary()

            return success

        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            return False
        finally:
            self.interrupt_handler.cleanup()

    async def compress_to_memory(
            self,
            source_paths: List[Union[str, Path]],
            chunk_size: int = 1024 * 1024
    ) -> Optional[BytesIO]:
        """
        Compress files to memory (BytesIO)

        Args:
            source_paths: List of files or directories to compress
            chunk_size: Chunk size for reading files

        Returns:
            BytesIO object containing compressed data, or None if failed
        """
        output = BytesIO()
        success = await self.compress_with_progress(source_paths, output, chunk_size)

        if success:
            output.seek(0)  # Reset position for reading
            return output
        else:
            return None

    async def _compress_with_tarfile(
            self,
            paths: List[Path],
            output_file: Union[Path, BinaryIO],
            chunk_size: int
    ) -> bool:
        """Compress using standard tarfile library"""
        # Create progress bar
        with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                MofNCompleteColumn(),
                DownloadColumn(),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=self.console,
                refresh_per_second=10
        ) as progress:

            # Add tasks
            output_name = output_file.name if isinstance(output_file, Path) else "memory buffer"
            overall_task = progress.add_task(
                f"[green]Compressing to {output_name}",
                total=self.stats.total_size
            )

            file_task = progress.add_task(
                "[yellow]Current file",
                total=100,
                visible=False
            )

            # Create tar file
            mode = self._get_compression_mode()

            with tarfile.open(fileobj=output_file if isinstance(output_file, BinaryIO) else None,
                              name=output_file if isinstance(output_file, (str, Path)) else None,
                              mode=mode) as tar:
                for path in paths:
                    if await self._check_interrupt():
                        progress.update(overall_task, description="[red]Interrupted")
                        return False

                    if path.is_file():
                        await self._add_file_with_progress(
                            tar, path, progress, overall_task, file_task
                        )
                    elif path.is_dir():
                        await self._add_directory_with_progress(
                            tar, path, progress, overall_task, file_task
                        )

            progress.update(overall_task, description="[green]Compression complete!")

        return True

    async def _compress_with_lz4(
            self,
            paths: List[Path],
            output_file: Union[Path, BinaryIO],
            chunk_size: int
    ) -> bool:
        """Compress using LZ4"""
        import tempfile

        # First create uncompressed tar file
        if isinstance(output_file, BinaryIO):
            # For memory output, use BytesIO for temporary tar
            tmp_tar = BytesIO()
            tmp_tar_path = None
        else:
            # For file output, use temporary file
            with tempfile.NamedTemporaryFile(suffix='.tar', delete=False) as tmp:
                tmp_tar_path = Path(tmp.name)
            tmp_tar = tmp_tar_path

        try:
            # Create tar file
            self.console.print("[yellow]Creating tar archive...[/yellow]")
            success = await self._compress_with_tarfile(paths, tmp_tar, chunk_size)

            if not success:
                return False

            # Apply LZ4 compression
            self.console.print("[yellow]Applying LZ4 compression...[/yellow]")

            with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    console=self.console
            ) as progress:

                if isinstance(tmp_tar, BytesIO):
                    tar_size = tmp_tar.tell()
                    tmp_tar.seek(0)
                else:
                    tar_size = tmp_tar_path.stat().st_size

                compress_task = progress.add_task(
                    "[cyan]LZ4 compressing...",
                    total=tar_size
                )

                # LZ4 compression
                if isinstance(tmp_tar, BytesIO):
                    f_in = tmp_tar
                else:
                    f_in = open(tmp_tar_path, 'rb')

                try:
                    if isinstance(output_file, BinaryIO):
                        f_out = lz4.frame.open(output_file, 'wb')
                    else:
                        f_out = lz4.frame.open(output_file, 'wb')

                    while True:
                        if await self._check_interrupt():
                            return False

                        chunk = f_in.read(chunk_size)
                        if not chunk:
                            break

                        f_out.write(chunk)
                        progress.update(compress_task, advance=len(chunk))

                        # Yield control
                        await asyncio.sleep(0)

                    f_out.close()
                finally:
                    if not isinstance(tmp_tar, BytesIO):
                        f_in.close()

                progress.update(compress_task, description="[green]LZ4 compression complete!")

            return True

        finally:
            # Clean up temporary file
            if tmp_tar_path and tmp_tar_path.exists():
                tmp_tar_path.unlink()

    async def _add_file_with_progress(
            self,
            tar: tarfile.TarFile,
            file_path: Path,
            progress: Progress,
            overall_task: int,
            file_task: int
    ):
        """Add single file to tar with progress update"""
        file_size = file_path.stat().st_size

        # Update file task
        progress.update(
            file_task,
            description=f"[yellow]{file_path.name}",
            total=file_size,
            completed=0,
            visible=True
        )

        # Use custom file object to track progress
        class ProgressFileWrapper:
            def __init__(self, file_obj, callback):
                self.file_obj = file_obj
                self.callback = callback
                self.processed = 0

            def read(self, size=-1):
                data = self.file_obj.read(size)
                if data:
                    self.processed += len(data)
                    self.callback(len(data))
                return data

            def __getattr__(self, name):
                return getattr(self.file_obj, name)

        def update_progress(bytes_read):
            progress.update(file_task, advance=bytes_read)
            progress.update(overall_task, advance=bytes_read)
            self.stats.processed_size += bytes_read

        # Add file to tar
        with open(file_path, 'rb') as f:
            wrapped_file = ProgressFileWrapper(f, update_progress)
            info = tar.gettarinfo(str(file_path))
            tar.addfile(info, wrapped_file)

        self.stats.processed_files += 1
        progress.update(file_task, visible=False)

        # Check interrupt
        await asyncio.sleep(0)  # Yield control

    async def _add_directory_with_progress(
            self,
            tar: tarfile.TarFile,
            dir_path: Path,
            progress: Progress,
            overall_task: int,
            file_task: int
    ):
        """Recursively add directory to tar"""
        for item in dir_path.rglob("*"):
            if await self._check_interrupt():
                return

            if item.is_file():
                await self._add_file_with_progress(
                    tar, item, progress, overall_task, file_task
                )

    def _show_summary(self):
        """Show compression summary"""
        if not self.stats.start_time or not self.stats.end_time:
            return

        duration = self.stats.end_time - self.stats.start_time

        # Calculate compression ratio
        if self.stats.total_size > 0 and self.stats.compressed_size > 0:
            compression_ratio = (1 - self.stats.compressed_size / self.stats.total_size) * 100
        else:
            compression_ratio = 0

        summary = f"""
[green]Compression complete![/green]

• Files processed: {self.stats.processed_files}/{self.stats.total_files}
• Original size: {self._format_size(self.stats.total_size)}
• Compressed size: {self._format_size(self.stats.compressed_size)}
• Compression ratio: {compression_ratio:.1f}%
• Time taken: {duration.total_seconds():.1f} seconds
• Compression type: {self.compression.name}
        """

        self.console.print(Panel(summary, title="Compression Statistics", border_style="green"))

    @staticmethod
    def _format_size(size: int) -> str:
        """Format file size"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"


class InteractiveMode:
    """Interactive mode handler"""

    def __init__(self, console: Console):
        self.console = console

    def get_compression_type(self) -> CompressionType:
        """Get compression type interactively"""
        self.console.print("\n[cyan]Select compression algorithm:[/cyan]")

        info_dict = CompressionChecker.check_availability()
        available_types = []

        for i, (comp_type, info) in enumerate(info_dict.items(), 1):
            if info.available:
                available_types.append(comp_type)
                self.console.print(f"{i}. {info.name} - {info.description}")
            else:
                self.console.print(f"{i}. [dim]{info.name} - {info.description} (Not available)[/dim]")

        while True:
            choice = Prompt.ask(
                "Select compression type",
                default="1",
                choices=[str(i) for i in range(1, len(info_dict) + 1) if list(info_dict.values())[i - 1].available]
            )

            try:
                index = int(choice) - 1
                return available_types[index]
            except (ValueError, IndexError):
                self.console.print("[red]Invalid choice, please try again[/red]")

    def get_source_paths(self) -> List[Path]:
        """Get source paths interactively"""
        paths = []
        self.console.print("\n[cyan]Enter files/directories to compress (empty line to finish):[/cyan]")

        while True:
            path_str = Prompt.ask("Path", default="")
            if not path_str:
                break

            path = Path(path_str).expanduser()
            if path.exists():
                paths.append(path)
                self.console.print(f"[green]✓ Added: {path}[/green]")
            else:
                self.console.print(f"[red]✗ Path not found: {path}[/red]")

        if not paths:
            self.console.print("[red]No valid paths provided![/red]")
            sys.exit(1)

        return paths

    def get_output_path(self, compression: CompressionType) -> Path:
        """Get output path interactively"""
        info_dict = CompressionChecker.check_availability()
        extension = info_dict[compression].extension

        default_name = f"archive.tar{extension}"

        while True:
            output_str = Prompt.ask(
                f"\n[cyan]Output filename[/cyan]",
                default=default_name
            )

            output_path = Path(output_str).expanduser()

            # Check if file exists
            if output_path.exists():
                overwrite = Confirm.ask(
                    f"[yellow]File {output_path} already exists. Overwrite?[/yellow]",
                    default=False
                )
                if overwrite:
                    return output_path
            else:
                return output_path


async def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Async Tar Compression Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Supported compression algorithms:
  gz     - GZIP compression (default)
  bz2    - BZIP2 compression (high compression ratio)
  xz     - XZ/LZMA compression (highest compression ratio)
  lz4    - LZ4 compression (fastest speed, requires lz4 installation)
  none   - Archive only, no compression

Examples:
  %(prog)s file1.txt dir1/ -o archive.tar.gz -c gz
  %(prog)s data/ -o archive.tar.lz4 -c lz4
  %(prog)s -i  # Interactive mode
  %(prog)s --check  # Check compression algorithm support
  %(prog)s --diagnostic  # Run detailed compression support diagnostic
  %(prog)s --demo  # Run demo
        """
    )

    parser.add_argument("sources", nargs="*", help="Files or directories to compress")
    parser.add_argument("-o", "--output", help="Output filename")
    parser.add_argument(
        "-c", "--compression",
        choices=["gz", "bz2", "xz", "lz4", "none"],
        default="gz",
        help="Compression type (default: gz)"
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Interactive mode"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check compression algorithm support"
    )
    parser.add_argument(
        "--diagnostic",
        action="store_true",
        help="Run detailed compression support diagnostic"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run demonstration"
    )

    args = parser.parse_args()

    console = Console()

    # Check mode
    if args.check:
        CompressionChecker.print_availability_table(console)
        return

    # Diagnostic mode
    if args.diagnostic:
        CompressionChecker.run_diagnostic(console)
        return

    # Demo mode
    if args.demo:
        from main import main as demo_main
        await demo_main()
        return

    # Interactive mode
    if args.interactive or (not args.sources and not args.output):
        interactive = InteractiveMode(console)

        console.print(Panel.fit(
            "[bold cyan]Async Tar Compressor - Interactive Mode[/bold cyan]",
            border_style="cyan"
        ))

        # Get parameters
        compression = interactive.get_compression_type()
        sources = interactive.get_source_paths()
        output = interactive.get_output_path(compression)

        # Execute compression
        try:
            compressor = AsyncTarCompressor(compression)
            success = await compressor.compress_with_progress(sources, output)

            if not success:
                sys.exit(1)
        except RuntimeError as e:
            console.print(f"\n[red]{e}[/red]")
            sys.exit(1)

        return

    # Command line mode
    if not args.sources or not args.output:
        parser.print_help()
        return

    # Determine compression type
    compression_map = {
        "gz": CompressionType.GZIP,
        "bz2": CompressionType.BZIP2,
        "xz": CompressionType.XZ,
        "lz4": CompressionType.LZ4,
        "none": CompressionType.NONE
    }

    try:
        # Create compressor
        compressor = AsyncTarCompressor(compression_map[args.compression])

        # Execute compression
        success = await compressor.compress_with_progress(args.sources, args.output)

        if not success:
            sys.exit(1)

    except RuntimeError as e:
        console.print(f"\n[red]{e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCancelled")
        sys.exit(1)