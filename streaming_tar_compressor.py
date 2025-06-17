#!/usr/bin/env python3
"""
流式打包压缩解压工具
支持：
- 流式压缩并直接分片输出
- 流式接收分片并直接解压
- 内存高效，避免堆积
"""

import asyncio
import gzip
import bz2
import lzma
import tarfile
import io
import os
from pathlib import Path
from typing import AsyncGenerator, Optional, List, Union, Callable, BinaryIO
from dataclasses import dataclass
from enum import Enum
import struct
import hashlib

try:
    import lz4.frame
    HAS_LZ4 = True
except ImportError:
    HAS_LZ4 = False


class CompressionType(Enum):
    """支持的压缩类型"""
    GZIP = "gz"
    BZIP2 = "bz2"
    XZ = "xz"
    LZ4 = "lz4"
    NONE = ""


@dataclass
class ChunkInfo:
    """分片信息"""
    index: int
    size: int
    checksum: str
    is_last: bool = False


class StreamingTarCompressor:
    """流式压缩器"""
    
    CHUNK_SIZE = 1024 * 1024  # 1MB 缓冲区
    PART_SIZE = 50 * 1024 * 1024  # 50MB 每个分片
    
    def __init__(self, compression: CompressionType = CompressionType.GZIP):
        self.compression = compression
        self._check_compression_support()
    
    def _check_compression_support(self):
        """检查压缩算法支持"""
        if self.compression == CompressionType.LZ4 and not HAS_LZ4:
            raise RuntimeError("LZ4 compression not available. Install with: pip install lz4")
    
    def _get_compressor(self, fileobj: BinaryIO) -> BinaryIO:
        """获取压缩器对象"""
        if self.compression == CompressionType.GZIP:
            return gzip.GzipFile(fileobj=fileobj, mode='wb')
        elif self.compression == CompressionType.BZIP2:
            return bz2.BZ2File(fileobj, mode='wb')
        elif self.compression == CompressionType.XZ:
            return lzma.LZMAFile(fileobj, mode='wb')
        elif self.compression == CompressionType.LZ4:
            return lz4.frame.LZ4FrameFile(fileobj, mode='wb')
        else:
            return fileobj
    
    def _get_decompressor(self, fileobj: BinaryIO) -> BinaryIO:
        """获取解压器对象"""
        if self.compression == CompressionType.GZIP:
            return gzip.GzipFile(fileobj=fileobj, mode='rb')
        elif self.compression == CompressionType.BZIP2:
            return bz2.BZ2File(fileobj, mode='rb')
        elif self.compression == CompressionType.XZ:
            return lzma.LZMAFile(fileobj, mode='rb')
        elif self.compression == CompressionType.LZ4:
            return lz4.frame.LZ4FrameFile(fileobj, mode='rb')
        else:
            return fileobj
    
    async def compress_to_chunks(
        self, 
        sources: List[Union[str, Path]], 
        chunk_size: int = None,
        progress_callback: Optional[Callable] = None
    ) -> AsyncGenerator[tuple[int, bytes], None]:
        """
        流式压缩并生成分片
        
        Args:
            sources: 要压缩的文件/目录列表
            chunk_size: 分片大小（默认50MB）
            progress_callback: 进度回调函数
            
        Yields:
            (chunk_index, chunk_data) 元组
        """
        chunk_size = chunk_size or self.PART_SIZE
        
        # 创建内存缓冲区
        buffer = io.BytesIO()
        
        # 创建压缩流
        compressor = self._get_compressor(buffer)
        
        # 创建tar流
        tar = tarfile.open(fileobj=compressor, mode='w|')
        
        chunk_index = 0
        current_chunk = io.BytesIO()
        current_size = 0
        
        try:
            for source_path in sources:
                path = Path(source_path)
                
                # 添加文件到tar
                if path.is_file():
                    await self._add_file_to_tar(tar, path, progress_callback)
                elif path.is_dir():
                    await self._add_directory_to_tar(tar, path, progress_callback)
                
                # 检查缓冲区并生成分片
                while True:
                    # 获取压缩数据
                    buffer.seek(0)
                    data = buffer.read(self.CHUNK_SIZE)
                    
                    if not data:
                        break
                    
                    # 写入当前分片
                    current_chunk.write(data)
                    current_size += len(data)
                    
                    # 检查是否需要生成新分片
                    if current_size >= chunk_size:
                        current_chunk.seek(0)
                        chunk_data = current_chunk.read()
                        yield (chunk_index, chunk_data)
                        
                        chunk_index += 1
                        current_chunk = io.BytesIO()
                        current_size = 0
                    
                    # 清空已处理的缓冲区
                    buffer = io.BytesIO()
                    compressor = self._get_compressor(buffer)
                    tar.fileobj = compressor
                    
                    # 允许其他任务运行
                    await asyncio.sleep(0)
            
            # 关闭tar和压缩器
            tar.close()
            compressor.close()
            
            # 处理剩余数据
            buffer.seek(0)
            remaining_data = buffer.read()
            if remaining_data:
                current_chunk.write(remaining_data)
            
            # 生成最后一个分片
            if current_chunk.tell() > 0:
                current_chunk.seek(0)
                chunk_data = current_chunk.read()
                yield (chunk_index, chunk_data)
                
        finally:
            # 清理资源
            if hasattr(tar, 'close'):
                tar.close()
            if hasattr(compressor, 'close'):
                compressor.close()
    
    async def _add_file_to_tar(
        self, 
        tar: tarfile.TarFile, 
        file_path: Path,
        progress_callback: Optional[Callable] = None
    ):
        """添加文件到tar（流式）"""
        # 获取文件信息
        tarinfo = tar.gettarinfo(str(file_path))
        
        # 流式读取文件
        with open(file_path, 'rb') as f:
            tar.addfile(tarinfo, f)
        
        if progress_callback:
            await progress_callback(file_path, tarinfo.size)
        
        # 允许其他任务运行
        await asyncio.sleep(0)
    
    async def _add_directory_to_tar(
        self,
        tar: tarfile.TarFile,
        dir_path: Path,
        progress_callback: Optional[Callable] = None
    ):
        """递归添加目录到tar"""
        for item in dir_path.rglob("*"):
            if item.is_file():
                await self._add_file_to_tar(tar, item, progress_callback)
    
    async def decompress_from_chunks(
        self,
        chunk_generator: AsyncGenerator[bytes, None],
        output_dir: Union[str, Path],
        progress_callback: Optional[Callable] = None
    ):
        """
        从分片流解压
        
        Args:
            chunk_generator: 分片数据生成器
            output_dir: 输出目录
            progress_callback: 进度回调
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建管道
        read_fd, write_fd = os.pipe()
        
        # 创建异步任务
        async def feed_chunks():
            """异步写入分片数据到管道"""
            try:
                with os.fdopen(write_fd, 'wb') as writer:
                    async for chunk in chunk_generator:
                        writer.write(chunk)
                        writer.flush()
                        await asyncio.sleep(0)
            except Exception as e:
                print(f"Error feeding chunks: {e}")
            finally:
                # 确保写端关闭
                if not os.get_inheritable(write_fd):
                    os.close(write_fd)
        
        async def extract_tar():
            """异步从管道读取并解压"""
            try:
                with os.fdopen(read_fd, 'rb') as reader:
                    # 创建解压器
                    decompressor = self._get_decompressor(reader)
                    
                    # 打开tar流
                    with tarfile.open(fileobj=decompressor, mode='r|') as tar:
                        # 流式解压每个成员
                        for member in tar:
                            tar.extract(member, output_dir)
                            
                            if progress_callback:
                                await progress_callback(member.name, member.size)
                            
                            await asyncio.sleep(0)
            except Exception as e:
                print(f"Error extracting: {e}")
            finally:
                # 确保读端关闭
                if not os.get_inheritable(read_fd):
                    os.close(read_fd)
        
        # 并发运行写入和解压任务
        await asyncio.gather(
            feed_chunks(),
            extract_tar()
        )


class ChunkedFileHandler:
    """分片文件处理器"""
    
    @staticmethod
    async def save_chunks(
        chunk_generator: AsyncGenerator[tuple[int, bytes], None],
        output_prefix: str,
        metadata_callback: Optional[Callable] = None
    ) -> List[ChunkInfo]:
        """
        保存分片到文件
        
        Args:
            chunk_generator: 分片生成器
            output_prefix: 输出文件前缀
            metadata_callback: 元数据回调
            
        Returns:
            分片信息列表
        """
        chunks_info = []
        
        async for chunk_index, chunk_data in chunk_generator:
            # 计算校验和
            checksum = hashlib.sha256(chunk_data).hexdigest()
            
            # 保存分片
            chunk_filename = f"{output_prefix}.part{chunk_index:04d}"
            async with asyncio.open(chunk_filename, 'wb') as f:
                await f.write(chunk_data)
            
            # 记录分片信息
            chunk_info = ChunkInfo(
                index=chunk_index,
                size=len(chunk_data),
                checksum=checksum
            )
            chunks_info.append(chunk_info)
            
            if metadata_callback:
                await metadata_callback(chunk_info)
        
        # 保存元数据
        await ChunkedFileHandler.save_metadata(output_prefix, chunks_info)
        
        return chunks_info
    
    @staticmethod
    async def load_chunks(
        input_prefix: str,
        verify_checksum: bool = True
    ) -> AsyncGenerator[bytes, None]:
        """
        从文件加载分片
        
        Args:
            input_prefix: 输入文件前缀
            verify_checksum: 是否验证校验和
            
        Yields:
            分片数据
        """
        # 加载元数据
        chunks_info = await ChunkedFileHandler.load_metadata(input_prefix)
        
        for chunk_info in chunks_info:
            chunk_filename = f"{input_prefix}.part{chunk_info.index:04d}"
            
            # 读取分片
            async with asyncio.open(chunk_filename, 'rb') as f:
                chunk_data = await f.read()
            
            # 验证校验和
            if verify_checksum:
                checksum = hashlib.sha256(chunk_data).hexdigest()
                if checksum != chunk_info.checksum:
                    raise ValueError(f"Checksum mismatch for chunk {chunk_info.index}")
            
            yield chunk_data
    
    @staticmethod
    async def save_metadata(prefix: str, chunks_info: List[ChunkInfo]):
        """保存分片元数据"""
        metadata = {
            'version': '1.0',
            'total_chunks': len(chunks_info),
            'chunks': [
                {
                    'index': info.index,
                    'size': info.size,
                    'checksum': info.checksum
                }
                for info in chunks_info
            ]
        }
        
        import json
        metadata_file = f"{prefix}.metadata"
        async with asyncio.open(metadata_file, 'w') as f:
            await f.write(json.dumps(metadata, indent=2))
    
    @staticmethod
    async def load_metadata(prefix: str) -> List[ChunkInfo]:
        """加载分片元数据"""
        import json
        metadata_file = f"{prefix}.metadata"
        
        async with asyncio.open(metadata_file, 'r') as f:
            content = await f.read()
            metadata = json.loads(content)
        
        chunks_info = []
        for chunk_data in metadata['chunks']:
            chunks_info.append(ChunkInfo(
                index=chunk_data['index'],
                size=chunk_data['size'],
                checksum=chunk_data['checksum']
            ))
        
        return chunks_info


# 便捷函数
async def compress_with_chunks(
    sources: List[Union[str, Path]],
    output_prefix: str,
    compression: CompressionType = CompressionType.GZIP,
    chunk_size: int = 50 * 1024 * 1024,  # 50MB
    progress_callback: Optional[Callable] = None
) -> List[ChunkInfo]:
    """
    压缩并分片保存
    
    Example:
        chunks = await compress_with_chunks(
            ["data/"], 
            "backup",
            compression=CompressionType.GZIP,
            chunk_size=100*1024*1024  # 100MB chunks
        )
    """
    compressor = StreamingTarCompressor(compression)
    
    # 生成压缩分片
    chunk_generator = compressor.compress_to_chunks(
        sources, 
        chunk_size=chunk_size,
        progress_callback=progress_callback
    )
    
    # 保存分片
    chunks_info = await ChunkedFileHandler.save_chunks(
        chunk_generator,
        output_prefix
    )
    
    return chunks_info


async def decompress_from_chunks(
    input_prefix: str,
    output_dir: Union[str, Path],
    compression: CompressionType = CompressionType.GZIP,
    verify_checksum: bool = True,
    progress_callback: Optional[Callable] = None
):
    """
    从分片解压
    
    Example:
        await decompress_from_chunks(
            "backup",
            "restored_data/",
            compression=CompressionType.GZIP
        )
    """
    decompressor = StreamingTarCompressor(compression)
    
    # 加载分片流
    chunk_generator = ChunkedFileHandler.load_chunks(
        input_prefix,
        verify_checksum=verify_checksum
    )
    
    # 解压
    await decompressor.decompress_from_chunks(
        chunk_generator,
        output_dir,
        progress_callback=progress_callback
    )


# 使用示例
async def main():
    """演示流式压缩和解压"""
    
    # 1. 压缩并分片
    print("=== 流式压缩并分片 ===")
    
    async def compress_progress(file_path, size):
        print(f"压缩: {file_path} ({size} bytes)")
    
    chunks = await compress_with_chunks(
        ["test_data/"],  # 要压缩的目录
        "backup",        # 输出前缀
        compression=CompressionType.GZIP,
        chunk_size=10*1024*1024,  # 10MB分片
        progress_callback=compress_progress
    )
    
    print(f"\n生成了 {len(chunks)} 个分片")
    for chunk in chunks:
        print(f"  分片{chunk.index}: {chunk.size} bytes, 校验和: {chunk.checksum[:8]}...")
    
    # 2. 从分片解压
    print("\n=== 流式解压分片 ===")
    
    async def decompress_progress(file_name, size):
        print(f"解压: {file_name} ({size} bytes)")
    
    await decompress_from_chunks(
        "backup",
        "restored_data/",
        compression=CompressionType.GZIP,
        progress_callback=decompress_progress
    )
    
    print("\n完成！")


if __name__ == "__main__":
    asyncio.run(main())
