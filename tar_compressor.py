#!/usr/bin/env python3
"""
Async Tar Compressor/Decompressor - Support progress bar display and intelligent interrupt handling
Supported compression algorithms: gzip, bzip2, xz/lzma, lz4
Support both file and in-memory (BytesIO, bytes, str) operations
"""

import asyncio
import os
import signal
import sys
import tarfile
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Optional, List, Union, Dict, BinaryIO, Tuple

# Try to import standard library compression modules
# Even standard library modules might not be available in custom Python builds

try:
    import gzip
    import zlib

    HAS_GZIP = True
except ImportError:
    HAS_GZIP = False

try:
    import bz2

    HAS_BZ2 = True
except ImportError:
    HAS_BZ2 = False

try:
    import lzma

    HAS_LZMA = True
except ImportError:
    HAS_LZMA = False

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


class OperationType(Enum):
    """Operation type"""
    COMPRESS = "compress"
    DECOMPRESS = "decompress"


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
        # Use pre-imported flags for standard modules
        module_map = {
            "gzip": HAS_GZIP,
            "zlib": HAS_GZIP,  # zlib and gzip are related
            "bz2": HAS_BZ2,
            "_bz2": HAS_BZ2,  # C extension
            "lzma": HAS_LZMA,
            "_lzma": HAS_LZMA,  # C extension
            "lz4": HAS_LZ4,
            "lz4.frame": HAS_LZ4
        }

        if module_name in module_map:
            return module_map[module_name]

        # For other modules, try importing
        try:
            __import__(module_name)
            return True
        except ImportError:
            return False

    @staticmethod
    def check_availability() -> Dict[CompressionType, CompressionInfo]:
        """Check availability of all compression algorithms"""
        info = {
            CompressionType.GZIP: CompressionInfo(
                name="GZIP",
                module="gzip",
                extension=".gz",
                available=HAS_GZIP,
                install_cmd="System dependency: zlib1g-dev (Debian/Ubuntu) or zlib-devel (RHEL/CentOS)",
                description="Standard compression, balanced compression ratio and speed"
            ),
            CompressionType.BZIP2: CompressionInfo(
                name="BZIP2",
                module="bz2",
                extension=".bz2",
                available=HAS_BZ2,
                install_cmd="System dependency: libbz2-dev (Debian/Ubuntu) or bzip2-devel (RHEL/CentOS)",
                description="High compression ratio, but slower"
            ),
            CompressionType.XZ: CompressionInfo(
                name="XZ/LZMA",
                module="lzma",
                extension=".xz",
                available=HAS_LZMA,
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
    def get_available_algorithms() -> List[CompressionType]:
        """Get list of available compression algorithms"""
        info_dict = CompressionChecker.check_availability()
        return [comp_type for comp_type, info in info_dict.items() if info.available]

    @staticmethod
    def is_algorithm_available(algorithm: CompressionType) -> bool:
        """Check if a specific algorithm is available"""
        info_dict = CompressionChecker.check_availability()
        return info_dict.get(algorithm, CompressionInfo("", "", "", False)).available

    @staticmethod
    def get_missing_dependencies() -> Dict[CompressionType, str]:
        """Get missing dependencies for unavailable algorithms"""
        info_dict = CompressionChecker.check_availability()
        missing = {}
        for comp_type, info in info_dict.items():
            if not info.available and comp_type != CompressionType.NONE:
                missing[comp_type] = info.install_cmd or "Unknown dependency"
        return missing

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
        console.print(f"[cyan]Python Executable:[/cyan] {sys.executable}")

        # Check if this is a custom build
        import sysconfig
        config_args = sysconfig.get_config_var('CONFIG_ARGS') or ''
        if config_args:
            console.print(f"[cyan]Build Configuration:[/cyan] {config_args}")

        console.print("\n[cyan]Compression Module Detection:[/cyan]")

        # Module availability summary
        modules_status = {
            "gzip": ("GZIP support", HAS_GZIP),
            "bz2": ("BZIP2 support", HAS_BZ2),
            "lzma": ("LZMA/XZ support", HAS_LZMA),
            "lz4": ("LZ4 support (optional)", HAS_LZ4),
        }

        all_good = True
        missing_core = []

        for module, (description, available) in modules_status.items():
            if available:
                console.print(f"  [green]✓[/green] {module:<8} - {description}")
            else:
                if module != "lz4":  # LZ4 is optional
                    missing_core.append(module)
                    all_good = False
                console.print(f"  [red]✗[/red] {module:<8} - {description} [red](MISSING)[/red]")

        # Detailed module checks
        console.print("\n[cyan]Detailed Module Analysis:[/cyan]")

        # Check for partial installations
        detailed_checks = [
            ("zlib", "GZIP compression base", HAS_GZIP),
            ("_bz2", "BZIP2 C extension", HAS_BZ2),
            ("_lzma", "LZMA C extension", HAS_LZMA),
        ]

        for module_name, description, expected in detailed_checks:
            if expected:
                try:
                    __import__(module_name)
                    console.print(f"  [green]✓[/green] {module_name:<12} - {description}")
                except ImportError:
                    console.print(
                        f"  [yellow]⚠[/yellow] {module_name:<12} - {description} [yellow](Python wrapper present but C extension missing)[/yellow]")

        # Test actual functionality
        console.print("\n[cyan]Functionality Tests:[/cyan]")

        # Test GZIP
        if HAS_GZIP:
            try:
                import gzip
                test_data = b"test data"
                compressed = gzip.compress(test_data)
                decompressed = gzip.decompress(compressed)
                if decompressed == test_data:
                    console.print("  [green]✓[/green] GZIP compression/decompression working")
                else:
                    console.print("  [red]✗[/red] GZIP functionality test failed")
            except Exception as e:
                console.print(f"  [red]✗[/red] GZIP test error: {e}")

        # Test BZIP2
        if HAS_BZ2:
            try:
                import bz2
                test_data = b"test data"
                compressed = bz2.compress(test_data)
                decompressed = bz2.decompress(compressed)
                if decompressed == test_data:
                    console.print("  [green]✓[/green] BZIP2 compression/decompression working")
                else:
                    console.print("  [red]✗[/red] BZIP2 functionality test failed")
            except Exception as e:
                console.print(f"  [red]✗[/red] BZIP2 test error: {e}")

        # Test LZMA
        if HAS_LZMA:
            try:
                import lzma
                test_data = b"test data"
                compressed = lzma.compress(test_data)
                decompressed = lzma.decompress(compressed)
                if decompressed == test_data:
                    console.print("  [green]✓[/green] LZMA compression/decompression working")
                else:
                    console.print("  [red]✗[/red] LZMA functionality test failed")
            except Exception as e:
                console.print(f"  [red]✗[/red] LZMA test error: {e}")

        # Summary and recommendations
        if missing_core:
            console.print("\n[red]Warning: Missing critical compression module support![/red]")
            console.print(f"Affected modules: {', '.join(missing_core)}")

            console.print("\n[yellow]This appears to be a custom Python build missing compression support.[/yellow]")
            console.print("\n[cyan]Solutions:[/cyan]")

            console.print("\n1. [bold]Install system dependencies BEFORE building Python:[/bold]")
            console.print("   Ubuntu/Debian:")
            console.print("     sudo apt-get update")
            console.print("     sudo apt-get install -y zlib1g-dev libbz2-dev liblzma-dev")
            console.print("   CentOS/RHEL/Fedora:")
            console.print("     sudo yum install -y zlib-devel bzip2-devel xz-devel")
            console.print("   macOS:")
            console.print("     brew install zlib bzip2 xz")

            console.print("\n2. [bold]Rebuild Python with compression support:[/bold]")
            console.print("   ./configure --enable-optimizations")
            console.print("   make -j$(nproc)")
            console.print("   sudo make altinstall")

            console.print("\n3. [bold]Or use a pre-built Python distribution:[/bold]")
            console.print("   • Use system Python: sudo apt install python3-full")
            console.print("   • Use pyenv to install Python")
            console.print("   • Use Anaconda/Miniconda")
            console.print("   • Use official Python docker images")

            console.print("\n4. [bold]Verify compression support before building:[/bold]")
            console.print("   pkg-config --libs zlib     # Should show -lz")
            console.print("   pkg-config --libs liblzma  # Should show -llzma")
        else:
            console.print("\n[green]All critical compression modules are available![/green]")

        # Show available algorithms
        available = CompressionChecker.get_available_algorithms()
        console.print(f"\n[cyan]Available compression algorithms:[/cyan] {', '.join(a.name for a in available)}")

        return all_good

    @staticmethod
    def quick_check() -> Dict[str, bool]:
        """Quick check of compression support, returns dict of algorithm:available"""
        return {
            "gzip": HAS_GZIP,
            "bzip2": HAS_BZ2,
            "xz": HAS_LZMA,
            "lz4": HAS_LZ4,
            "none": True
        }


@dataclass
class OperationStats:
    """Operation statistics"""
    operation_type: OperationType
    total_files: int = 0
    processed_files: int = 0
    total_size: int = 0
    processed_size: int = 0
    result_size: int = 0
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


class AsyncTarProcessor:
    """Async Tar Compressor/Decompressor"""

    def __init__(self, compression: CompressionType = CompressionType.GZIP):
        self.compression = compression
        self.console = Console()
        self.stats = None
        self.interrupt_handler = InterruptHandler()
        self._cancelled = False

    @classmethod
    def get_supported_algorithms(cls) -> List[CompressionType]:
        """Get list of supported compression algorithms on this system"""
        return CompressionChecker.get_available_algorithms()

    @classmethod
    def is_algorithm_supported(cls, algorithm: CompressionType) -> bool:
        """Check if a specific algorithm is supported on this system"""
        return CompressionChecker.is_algorithm_available(algorithm)

    @classmethod
    def get_algorithm_info(cls, algorithm: CompressionType) -> Optional[CompressionInfo]:
        """Get information about a specific algorithm"""
        info_dict = CompressionChecker.check_availability()
        return info_dict.get(algorithm)

    @classmethod
    def print_support_summary(cls, console: Optional[Console] = None):
        """Print a summary of compression support"""
        if console is None:
            console = Console()

        CompressionChecker.print_availability_table(console)

    def _check_compression_availability(self):
        """Check if selected compression algorithm is available"""
        info_dict = CompressionChecker.check_availability()
        info = info_dict.get(self.compression)

        if info and not info.available:
            self.console.print(f"\n[red]Error: {info.name} compression algorithm not available![/red]")

            # Show why it's not available
            if self.compression == CompressionType.GZIP:
                self.console.print("[yellow]This Python installation was built without zlib support.[/yellow]")
            elif self.compression == CompressionType.BZIP2:
                self.console.print("[yellow]This Python installation was built without bz2 support.[/yellow]")
            elif self.compression == CompressionType.XZ:
                self.console.print("[yellow]This Python installation was built without lzma support.[/yellow]")

            if info.install_cmd:
                self.console.print(f"[yellow]To fix: {info.install_cmd}[/yellow]")
                self.console.print("[yellow]Then rebuild Python from source.[/yellow]")

            # Show all available compression algorithms
            self.console.print("\n[cyan]Available compression algorithms on this system:[/cyan]")
            available_algos = CompressionChecker.get_available_algorithms()
            for comp_type in available_algos:
                if comp_type != CompressionType.NONE:
                    comp_info = info_dict[comp_type]
                    self.console.print(f"  • {comp_info.name}: {comp_info.description}")

            # Suggest alternatives
            if available_algos:
                if CompressionType.NONE in available_algos:
                    available_algos.remove(CompressionType.NONE)
                if available_algos:
                    suggested = available_algos[0]
                    self.console.print(
                        f"\n[green]Suggestion: Use {info_dict[suggested].name} compression instead.[/green]")

            raise RuntimeError(f"{info.name} compression algorithm not available on this Python installation")

    def _detect_compression_type(self, file_path: Union[str, Path]) -> CompressionType:
        """Detect compression type from file extension"""
        if isinstance(file_path, str):
            file_path = Path(file_path)

        name_lower = file_path.name.lower()

        if name_lower.endswith('.tar.gz') or name_lower.endswith('.tgz'):
            return CompressionType.GZIP
        elif name_lower.endswith('.tar.bz2') or name_lower.endswith('.tbz') or name_lower.endswith('.tbz2'):
            return CompressionType.BZIP2
        elif name_lower.endswith('.tar.xz') or name_lower.endswith('.txz'):
            return CompressionType.XZ
        elif name_lower.endswith('.tar.lz4') or name_lower.endswith('.tlz4'):
            return CompressionType.LZ4
        elif name_lower.endswith('.tar'):
            return CompressionType.NONE
        else:
            # Try to detect by reading file header
            return self._detect_compression_from_content(file_path)

    def _detect_compression_from_content(self, file_path: Path) -> CompressionType:
        """Detect compression type from file content"""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(16)

            # Check magic numbers
            if header.startswith(b'\x1f\x8b'):  # gzip
                return CompressionType.GZIP
            elif header.startswith(b'BZh'):  # bzip2
                return CompressionType.BZIP2
            elif header.startswith(b'\xfd7zXZ\x00'):  # xz
                return CompressionType.XZ
            elif header.startswith(b'\x04"M\x18'):  # lz4
                return CompressionType.LZ4
            else:
                # Assume uncompressed tar
                return CompressionType.NONE
        except:
            return CompressionType.NONE

    def _detect_compression_from_bytes(self, data: bytes) -> CompressionType:
        """Detect compression type from bytes content"""
        if len(data) < 16:
            return CompressionType.NONE

        # Check magic numbers
        if data.startswith(b'\x1f\x8b'):  # gzip
            return CompressionType.GZIP
        elif data.startswith(b'BZh'):  # bzip2
            return CompressionType.BZIP2
        elif data.startswith(b'\xfd7zXZ\x00'):  # xz
            return CompressionType.XZ
        elif data.startswith(b'\x04"M\x18'):  # lz4
            return CompressionType.LZ4
        else:
            return CompressionType.NONE

    def _get_tarfile_mode(self, operation: OperationType) -> str:
        """Get tarfile mode string"""
        base_mode = "w" if operation == OperationType.COMPRESS else "r"

        # Check if compression module is available
        if self.compression == CompressionType.GZIP and not HAS_GZIP:
            raise RuntimeError("GZIP compression not available. Install zlib development libraries and rebuild Python.")
        elif self.compression == CompressionType.BZIP2 and not HAS_BZ2:
            raise RuntimeError("BZIP2 compression not available. Install bz2 development libraries and rebuild Python.")
        elif self.compression == CompressionType.XZ and not HAS_LZMA:
            raise RuntimeError(
                "XZ/LZMA compression not available. Install lzma development libraries and rebuild Python.")
        elif self.compression == CompressionType.LZ4 and not HAS_LZ4:
            raise RuntimeError("LZ4 compression not available. Install with: pip install lz4")

        # Standard tarfile supported modes
        mode_suffix = {
            CompressionType.GZIP: ":gz",
            CompressionType.BZIP2: ":bz2",
            CompressionType.XZ: ":xz",
            CompressionType.NONE: ""
        }

        if self.compression in mode_suffix:
            return base_mode + mode_suffix[self.compression]
        elif self.compression == CompressionType.LZ4:
            # LZ4 needs special handling
            return base_mode  # Use uncompressed mode, handle LZ4 separately
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
                lambda: Confirm.ask("\n[yellow]Do you want to interrupt the operation?[/yellow]",
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

    # Compression methods
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
        # Check compression availability
        self._check_compression_availability()

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
            total_files, total_size = self._calculate_total_size(paths)

            self.stats = OperationStats(
                operation_type=OperationType.COMPRESS,
                total_files=total_files,
                total_size=total_size,
                start_time=datetime.now()
            )

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
                    self.stats.result_size = output_file.tell()
                elif output_path and output_path.exists():
                    self.stats.result_size = output_path.stat().st_size
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
        try:
            output = BytesIO()
            success = await self.compress_with_progress(source_paths, output, chunk_size)

            if success:
                output.seek(0)  # Reset position for reading
                return output
            else:
                return None
        except Exception as e:
            self.console.print(f"[red]Error in compress_to_memory: {e}[/red]")
            return None

    async def compress_to_bytes(
            self,
            source_paths: List[Union[str, Path]],
            chunk_size: int = 1024 * 1024
    ) -> Optional[bytes]:
        """
        Compress files to bytes

        Args:
            source_paths: List of files or directories to compress
            chunk_size: Chunk size for reading files

        Returns:
            bytes containing compressed data, or None if failed
        """
        output = await self.compress_to_memory(source_paths, chunk_size)
        if output:
            return output.getvalue()
        else:
            return None

    async def compress_to_str(
            self,
            source_paths: List[Union[str, Path]],
            chunk_size: int = 1024 * 1024
    ) -> Optional[str]:
        """
        Compress files to base64 encoded string

        Args:
            source_paths: List of files or directories to compress
            chunk_size: Chunk size for reading files

        Returns:
            base64 encoded string containing compressed data, or None if failed
        """
        import base64
        data = await self.compress_to_bytes(source_paths, chunk_size)
        if data:
            return base64.b64encode(data).decode('ascii')
        else:
            return None

    # Decompression methods
    async def decompress_with_progress(
            self,
            archive_file: Union[str, Path, BinaryIO, bytes],
            output_dir: Union[str, Path],
            chunk_size: int = 1024 * 1024
    ) -> bool:
        """
        Decompress archive with progress display

        Args:
            archive_file: Archive file path, BytesIO, or bytes
            output_dir: Output directory for extracted files
            chunk_size: Chunk size for reading files

        Returns:
            bool: Whether completed successfully
        """
        # Setup interrupt handling
        self.interrupt_handler.setup()

        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            # Determine compression type
            if isinstance(archive_file, (str, Path)):
                file_path = Path(archive_file)
                if not file_path.exists():
                    self.console.print(f"[red]Archive file not found: {file_path}[/red]")
                    return False

                # Auto-detect compression type
                detected_compression = self._detect_compression_type(file_path)
                if self.compression != detected_compression:
                    self.console.print(f"[yellow]Auto-detected {detected_compression.name} compression[/yellow]")
                    self.compression = detected_compression
                    self._check_compression_availability()

                total_size = file_path.stat().st_size
                archive_name = file_path.name

            elif isinstance(archive_file, bytes):
                # Auto-detect from bytes content
                detected_compression = self._detect_compression_from_bytes(archive_file)
                if self.compression != detected_compression:
                    self.console.print(f"[yellow]Auto-detected {detected_compression.name} compression[/yellow]")
                    self.compression = detected_compression
                    self._check_compression_availability()

                total_size = len(archive_file)
                archive_name = "memory archive"
                # Convert bytes to BytesIO for processing
                archive_file = BytesIO(archive_file)

            elif isinstance(archive_file, (BinaryIO, BytesIO)):
                # For BytesIO, try to detect compression
                current_pos = archive_file.tell()
                header = archive_file.read(16)
                archive_file.seek(current_pos)

                detected_compression = self._detect_compression_from_bytes(header)
                if self.compression != detected_compression:
                    self.console.print(f"[yellow]Auto-detected {detected_compression.name} compression[/yellow]")
                    self.compression = detected_compression
                    self._check_compression_availability()

                archive_file.seek(0, 2)  # Seek to end
                total_size = archive_file.tell()
                archive_file.seek(0)  # Reset position
                archive_name = "memory archive"
            else:
                raise ValueError(f"Invalid archive_file type: {type(archive_file)}")

            self.stats = OperationStats(
                operation_type=OperationType.DECOMPRESS,
                total_size=total_size,
                start_time=datetime.now()
            )

            self.console.print(f"[cyan]Decompressing {archive_name}...[/cyan]")

            # Display compression algorithm info
            info_dict = CompressionChecker.check_availability()
            comp_info = info_dict[self.compression]
            self.console.print(f"[green]Using {comp_info.name} decompression[/green]")

            if self.compression == CompressionType.LZ4:
                # LZ4 needs special handling
                success = await self._decompress_with_lz4(archive_file, output_path, chunk_size)
            else:
                # Use standard tarfile handling
                success = await self._decompress_with_tarfile(archive_file, output_path, chunk_size)

            if success:
                self.stats.end_time = datetime.now()
                self._show_summary()

            return success

        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self.interrupt_handler.cleanup()

    async def decompress_from_str(
            self,
            archive_str: str,
            output_dir: Union[str, Path],
            chunk_size: int = 1024 * 1024
    ) -> bool:
        """
        Decompress base64 encoded string archive

        Args:
            archive_str: Base64 encoded string containing archive data
            output_dir: Output directory for extracted files
            chunk_size: Chunk size for reading files

        Returns:
            bool: Whether completed successfully
        """
        import base64
        try:
            archive_bytes = base64.b64decode(archive_str)
            return await self.decompress_with_progress(archive_bytes, output_dir, chunk_size)
        except Exception as e:
            self.console.print(f"[red]Error decoding base64 string: {e}[/red]")
            return False

    async def list_archive_contents(
            self,
            archive_file: Union[str, Path, BinaryIO, bytes]
    ) -> Optional[List[Tuple[str, int, bool]]]:
        """
        List contents of an archive

        Args:
            archive_file: Archive file path, BytesIO, or bytes

        Returns:
            List of tuples (filename, size, is_directory) or None if failed
        """
        try:
            # Prepare archive for reading
            if isinstance(archive_file, (str, Path)):
                file_path = Path(archive_file)
                if not file_path.exists():
                    self.console.print(f"[red]Archive file not found: {file_path}[/red]")
                    return None

                # Auto-detect compression type
                self.compression = self._detect_compression_type(file_path)
                self._check_compression_availability()

            elif isinstance(archive_file, bytes):
                # Auto-detect from bytes content
                self.compression = self._detect_compression_from_bytes(archive_file)
                self._check_compression_availability()
                archive_file = BytesIO(archive_file)

            elif isinstance(archive_file, (BinaryIO, BytesIO)):
                # For BytesIO, try to detect compression
                current_pos = archive_file.tell()
                header = archive_file.read(16)
                archive_file.seek(current_pos)

                self.compression = self._detect_compression_from_bytes(header)
                self._check_compression_availability()

            # Get contents based on compression type
            if self.compression == CompressionType.LZ4:
                return await self._list_lz4_contents(archive_file)
            else:
                return await self._list_tarfile_contents(archive_file)

        except Exception as e:
            self.console.print(f"[red]Error listing archive: {e}[/red]")
            return None

    # Internal compression methods
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
            mode = self._get_tarfile_mode(OperationType.COMPRESS)

            # Fixed: Correctly handle BinaryIO objects for tarfile.open
            if isinstance(output_file, (BinaryIO, BytesIO)):
                # For BinaryIO objects (like BytesIO), only use fileobj parameter
                with tarfile.open(fileobj=output_file, mode=mode) as tar:
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
            else:
                # For file paths, use name parameter
                with tarfile.open(name=str(output_file), mode=mode) as tar:
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

    # Internal decompression methods
    async def _decompress_with_tarfile(
            self,
            archive_file: Union[Path, BinaryIO],
            output_dir: Path,
            chunk_size: int
    ) -> bool:
        """Decompress using standard tarfile library"""
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

            overall_task = progress.add_task(
                f"[green]Extracting to {output_dir}",
                total=self.stats.total_size
            )

            file_task = progress.add_task(
                "[yellow]Current file",
                total=100,
                visible=False
            )

            # Open tar file
            mode = self._get_tarfile_mode(OperationType.DECOMPRESS)

            # Fixed: Correctly handle BinaryIO objects for tarfile.open
            if isinstance(archive_file, (BinaryIO, BytesIO)):
                # For BinaryIO objects (like BytesIO), only use fileobj parameter
                with tarfile.open(fileobj=archive_file, mode=mode) as tar:
                    # Count total files
                    members = tar.getmembers()
                    self.stats.total_files = len([m for m in members if m.isfile()])

                    for member in members:
                        if await self._check_interrupt():
                            progress.update(overall_task, description="[red]Interrupted")
                            return False

                        if member.isfile():
                            # Update progress
                            progress.update(
                                file_task,
                                description=f"[yellow]{member.name}",
                                total=member.size,
                                completed=0,
                                visible=True
                            )

                            # Extract with progress
                            await self._extract_member_with_progress(
                                tar, member, output_dir, progress, overall_task, file_task
                            )

                            self.stats.processed_files += 1
                            progress.update(file_task, visible=False)
                        else:
                            # Just extract directories
                            tar.extract(member, output_dir)

                        await asyncio.sleep(0)  # Yield control
            else:
                # For file paths, use name parameter
                with tarfile.open(name=str(archive_file), mode=mode) as tar:
                    # Count total files
                    members = tar.getmembers()
                    self.stats.total_files = len([m for m in members if m.isfile()])

                    for member in members:
                        if await self._check_interrupt():
                            progress.update(overall_task, description="[red]Interrupted")
                            return False

                        if member.isfile():
                            # Update progress
                            progress.update(
                                file_task,
                                description=f"[yellow]{member.name}",
                                total=member.size,
                                completed=0,
                                visible=True
                            )

                            # Extract with progress
                            await self._extract_member_with_progress(
                                tar, member, output_dir, progress, overall_task, file_task
                            )

                            self.stats.processed_files += 1
                            progress.update(file_task, visible=False)
                        else:
                            # Just extract directories
                            tar.extract(member, output_dir)

                        await asyncio.sleep(0)  # Yield control

            progress.update(overall_task, description="[green]Extraction complete!")

        return True

    async def _decompress_with_lz4(
            self,
            archive_file: Union[Path, BinaryIO],
            output_dir: Path,
            chunk_size: int
    ) -> bool:
        """Decompress using LZ4"""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix='.tar', delete=False) as tmp:
            tmp_tar_path = Path(tmp.name)

        try:
            # First decompress LZ4
            self.console.print("[yellow]Decompressing LZ4...[/yellow]")

            with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    console=self.console
            ) as progress:

                decompress_task = progress.add_task(
                    "[cyan]LZ4 decompressing...",
                    total=self.stats.total_size
                )

                # Open LZ4 file
                if isinstance(archive_file, BinaryIO):
                    f_in = lz4.frame.open(archive_file, 'rb')
                else:
                    f_in = lz4.frame.open(archive_file, 'rb')

                try:
                    with open(tmp_tar_path, 'wb') as f_out:
                        while True:
                            if await self._check_interrupt():
                                return False

                            chunk = f_in.read(chunk_size)
                            if not chunk:
                                break

                            f_out.write(chunk)
                            progress.update(decompress_task, advance=len(chunk))

                            await asyncio.sleep(0)

                finally:
                    f_in.close()

                progress.update(decompress_task, description="[green]LZ4 decompression complete!")

            # Now extract tar file
            self.console.print("[yellow]Extracting tar archive...[/yellow]")

            # Update stats for tar extraction
            self.stats.total_size = tmp_tar_path.stat().st_size

            return await self._decompress_with_tarfile(tmp_tar_path, output_dir, chunk_size)

        finally:
            # Clean up temporary file
            if tmp_tar_path.exists():
                tmp_tar_path.unlink()

    async def _extract_member_with_progress(
            self,
            tar: tarfile.TarFile,
            member: tarfile.TarInfo,
            output_dir: Path,
            progress: Progress,
            overall_task: int,
            file_task: int
    ):
        """Extract single member with progress"""
        # Create full path
        full_path = output_dir / member.name
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Extract with progress tracking
        extracted = tar.extractfile(member)
        if extracted:
            bytes_written = 0
            with open(full_path, 'wb') as f:
                while True:
                    chunk = extracted.read(8192)  # 8KB chunks
                    if not chunk:
                        break

                    f.write(chunk)
                    bytes_written += len(chunk)

                    progress.update(file_task, advance=len(chunk))
                    progress.update(overall_task, advance=len(chunk))
                    self.stats.processed_size += len(chunk)

            # Set file permissions
            if hasattr(os, 'chmod'):
                os.chmod(full_path, member.mode)

    async def _list_tarfile_contents(
            self,
            archive_file: Union[Path, BinaryIO]
    ) -> List[Tuple[str, int, bool]]:
        """List contents of a tarfile"""
        mode = self._get_tarfile_mode(OperationType.DECOMPRESS)

        # Fixed: Correctly handle BinaryIO objects for tarfile.open
        if isinstance(archive_file, (BinaryIO, BytesIO)):
            # For BinaryIO objects (like BytesIO), only use fileobj parameter
            with tarfile.open(fileobj=archive_file, mode=mode) as tar:
                contents = []
                for member in tar.getmembers():
                    contents.append((member.name, member.size, member.isdir()))
                return contents
        else:
            # For file paths, use name parameter
            with tarfile.open(name=str(archive_file), mode=mode) as tar:
                contents = []
                for member in tar.getmembers():
                    contents.append((member.name, member.size, member.isdir()))
                return contents

    async def _list_lz4_contents(
            self,
            archive_file: Union[Path, BinaryIO]
    ) -> List[Tuple[str, int, bool]]:
        """List contents of LZ4 compressed tar"""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix='.tar') as tmp:
            # Decompress to temporary file
            if isinstance(archive_file, BinaryIO):
                f_in = lz4.frame.open(archive_file, 'rb')
            else:
                f_in = lz4.frame.open(archive_file, 'rb')

            try:
                tmp.write(f_in.read())
                tmp.flush()

                # List contents of tar
                return await self._list_tarfile_contents(Path(tmp.name))
            finally:
                f_in.close()

    def _show_summary(self):
        """Show operation summary"""
        if not self.stats or not self.stats.start_time or not self.stats.end_time:
            return

        duration = self.stats.end_time - self.stats.start_time

        if self.stats.operation_type == OperationType.COMPRESS:
            # Compression summary
            if self.stats.total_size > 0 and self.stats.result_size > 0:
                compression_ratio = (1 - self.stats.result_size / self.stats.total_size) * 100
            else:
                compression_ratio = 0

            summary = f"""
[green]Compression complete![/green]

• Files processed: {self.stats.processed_files}/{self.stats.total_files}
• Original size: {self._format_size(self.stats.total_size)}
• Compressed size: {self._format_size(self.stats.result_size)}
• Compression ratio: {compression_ratio:.1f}%
• Time taken: {duration.total_seconds():.1f} seconds
• Compression type: {self.compression.name}
            """
            title = "Compression Statistics"
        else:
            # Decompression summary
            summary = f"""
[green]Decompression complete![/green]

• Files extracted: {self.stats.processed_files}
• Archive size: {self._format_size(self.stats.total_size)}
• Bytes processed: {self._format_size(self.stats.processed_size)}
• Time taken: {duration.total_seconds():.1f} seconds
• Compression type: {self.compression.name}
            """
            title = "Decompression Statistics"

        self.console.print(Panel(summary, title=title, border_style="green"))

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

    def get_operation_type(self) -> OperationType:
        """Get operation type interactively"""
        self.console.print("\n[cyan]Select operation:[/cyan]")
        self.console.print("1. Compress files/directories")
        self.console.print("2. Decompress archive")

        choice = Prompt.ask("Select operation", choices=["1", "2"], default="1")

        return OperationType.COMPRESS if choice == "1" else OperationType.DECOMPRESS

    def get_compression_type(self, operation: OperationType) -> CompressionType:
        """Get compression type interactively"""
        if operation == OperationType.COMPRESS:
            self.console.print("\n[cyan]Select compression algorithm:[/cyan]")
        else:
            self.console.print("\n[cyan]Select compression algorithm (or auto-detect):[/cyan]")
            self.console.print("0. Auto-detect from file")

        info_dict = CompressionChecker.check_availability()
        available_types = []
        unavailable_count = 0

        for i, (comp_type, info) in enumerate(info_dict.items(), 1):
            if info.available:
                available_types.append((str(len(available_types) + 1), comp_type))
                self.console.print(f"{len(available_types)}. {info.name} - {info.description}")
            else:
                unavailable_count += 1
                self.console.print(f"[dim strike]{i}. {info.name} - {info.description} (Not available)[/dim strike]")

        if unavailable_count > 0:
            self.console.print(
                f"\n[yellow]Note: {unavailable_count} algorithm(s) not available on this system.[/yellow]")
            if unavailable_count >= 3:  # Most standard algorithms missing
                self.console.print(
                    "[yellow]This appears to be a custom Python build. Run --diagnostic for details.[/yellow]")

        if not available_types:
            self.console.print("\n[red]No compression algorithms available![/red]")
            self.console.print("This Python installation lacks compression support.")
            self.console.print("Run with --diagnostic flag for troubleshooting information.")
            sys.exit(1)

        if operation == OperationType.DECOMPRESS:
            choices = ["0"] + [t[0] for t in available_types]
            default = "0"
        else:
            choices = [t[0] for t in available_types]
            # Default to first available algorithm
            default = "1"

        while True:
            choice = Prompt.ask(
                "Select compression type",
                default=default,
                choices=choices
            )

            try:
                if operation == OperationType.DECOMPRESS and choice == "0":
                    return None  # Auto-detect

                # Find the matching type
                for num, comp_type in available_types:
                    if num == choice:
                        return comp_type

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

    def get_archive_path(self) -> Path:
        """Get archive path interactively"""
        while True:
            path_str = Prompt.ask("\n[cyan]Archive file path[/cyan]")
            path = Path(path_str).expanduser()

            if path.exists():
                return path
            else:
                self.console.print(f"[red]File not found: {path}[/red]")

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

    def get_output_directory(self) -> Path:
        """Get output directory interactively"""
        while True:
            dir_str = Prompt.ask(
                "\n[cyan]Output directory[/cyan]",
                default="."
            )

            output_dir = Path(dir_str).expanduser()

            if not output_dir.exists():
                create = Confirm.ask(
                    f"[yellow]Directory {output_dir} doesn't exist. Create it?[/yellow]",
                    default=True
                )
                if create:
                    output_dir.mkdir(parents=True, exist_ok=True)
                    return output_dir
            else:
                return output_dir


async def main():
    """Main function"""
    import argparse
    import os

    parser = argparse.ArgumentParser(
        description="Async Tar Compression/Decompression Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Supported compression algorithms:
  gz     - GZIP compression (default)
  bz2    - BZIP2 compression (high compression ratio)
  xz     - XZ/LZMA compression (highest compression ratio)
  lz4    - LZ4 compression (fastest speed, requires lz4 installation)
  none   - Archive only, no compression

Examples:
  Compression:
    %(prog)s -c file1.txt dir1/ -o archive.tar.gz -t gz
    %(prog)s -c data/ -o archive.tar.lz4 -t lz4

  Decompression:
    %(prog)s -d archive.tar.gz -o output_dir/
    %(prog)s -d archive.tar.xz  # Auto-detect compression

  Interactive mode:
    %(prog)s -i

  Other:
    %(prog)s --check  # Check compression algorithm support
    %(prog)s --diagnostic  # Run detailed compression support diagnostic
    %(prog)s --demo  # Run demo
        """
    )

    # Operation mode group
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("-c", "--compress", nargs="+", metavar="SOURCE",
                            help="Compress files/directories")
    mode_group.add_argument("-d", "--decompress", metavar="ARCHIVE",
                            help="Decompress archive")
    mode_group.add_argument("-l", "--list", metavar="ARCHIVE",
                            help="List archive contents")

    parser.add_argument("-o", "--output", help="Output path (file for compress, directory for decompress)")
    parser.add_argument(
        "-t", "--type",
        choices=["gz", "bz2", "xz", "lz4", "none", "auto"],
        default="auto",
        help="Compression type (default: auto-detect for decompress, gz for compress)"
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

    # List mode
    if args.list:
        processor = AsyncTarProcessor()
        contents = await processor.list_archive_contents(args.list)

        if contents:
            console.print(f"\n[cyan]Contents of {args.list}:[/cyan]")

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Name", style="cyan")
            table.add_column("Size", style="green")
            table.add_column("Type", style="yellow")

            for name, size, is_dir in contents:
                file_type = "Directory" if is_dir else "File"
                size_str = processor._format_size(size) if not is_dir else "-"
                table.add_row(name, size_str, file_type)

            console.print(table)
        return

    # Interactive mode
    if args.interactive or (not args.compress and not args.decompress):
        interactive = InteractiveMode(console)

        console.print(Panel.fit(
            "[bold cyan]Async Tar Processor - Interactive Mode[/bold cyan]",
            border_style="cyan"
        ))

        # Get operation type
        operation = interactive.get_operation_type()

        if operation == OperationType.COMPRESS:
            # Get parameters
            compression = interactive.get_compression_type(operation)
            sources = interactive.get_source_paths()
            output = interactive.get_output_path(compression)

            # Execute compression
            try:
                processor = AsyncTarProcessor(compression)
                success = await processor.compress_with_progress(sources, output)

                if not success:
                    sys.exit(1)
            except RuntimeError as e:
                console.print(f"\n[red]{e}[/red]")
                sys.exit(1)

        else:  # DECOMPRESS
            # Get parameters
            archive = interactive.get_archive_path()
            compression = interactive.get_compression_type(operation)
            output_dir = interactive.get_output_directory()

            # Execute decompression
            try:
                if compression:
                    processor = AsyncTarProcessor(compression)
                else:
                    # Auto-detect
                    processor = AsyncTarProcessor()

                success = await processor.decompress_with_progress(archive, output_dir)

                if not success:
                    sys.exit(1)
            except RuntimeError as e:
                console.print(f"\n[red]{e}[/red]")
                sys.exit(1)

        return

    # Command line mode
    if args.compress:
        # Compression mode
        if not args.output:
            console.print("[red]Error: Output file required for compression (-o)[/red]")
            parser.print_help()
            sys.exit(1)

        # Determine compression type
        compression_map = {
            "gz": CompressionType.GZIP,
            "bz2": CompressionType.BZIP2,
            "xz": CompressionType.XZ,
            "lz4": CompressionType.LZ4,
            "none": CompressionType.NONE,
            "auto": CompressionType.GZIP  # Default for compression
        }

        try:
            # Create processor
            processor = AsyncTarProcessor(compression_map[args.type])

            # Execute compression
            success = await processor.compress_with_progress(args.compress, args.output)

            if not success:
                sys.exit(1)

        except RuntimeError as e:
            console.print(f"\n[red]{e}[/red]")
            sys.exit(1)

    elif args.decompress:
        # Decompression mode
        output_dir = args.output if args.output else "."

        # Determine compression type
        if args.type == "auto":
            # Auto-detect
            processor = AsyncTarProcessor()
        else:
            compression_map = {
                "gz": CompressionType.GZIP,
                "bz2": CompressionType.BZIP2,
                "xz": CompressionType.XZ,
                "lz4": CompressionType.LZ4,
                "none": CompressionType.NONE
            }
            processor = AsyncTarProcessor(compression_map[args.type])

        try:
            # Execute decompression
            success = await processor.decompress_with_progress(args.decompress, output_dir)

            if not success:
                sys.exit(1)

        except RuntimeError as e:
            console.print(f"\n[red]{e}[/red]")
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCancelled")
        sys.exit(1)