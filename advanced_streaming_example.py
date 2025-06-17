#!/usr/bin/env python3
"""
高级流式处理示例
展示真正的零拷贝流式压缩和解压
"""

import asyncio
import os
import sys
import gzip
import tarfile
from pathlib import Path
from typing import Optional, Callable, BinaryIO
import threading
import queue


class TrueStreamingCompressor:
    """真正的流式压缩器 - 使用操作系统管道实现零拷贝"""
    
    def __init__(self, chunk_size: int = 50 * 1024 * 1024):
        self.chunk_size = chunk_size
    
    async def compress_stream_to_chunks(
        self,
        sources: list[Path],
        output_prefix: str,
        progress_callback: Optional[Callable] = None
    ):
        """
        真正的流式压缩 - 边读边压边写
        使用线程和管道避免内存堆积
        """
        chunk_index = 0
        bytes_in_current_chunk = 0
        current_chunk_file = None
        
        # 创建管道
        read_fd, write_fd = os.pipe()
        
        # 设置非阻塞模式
        os.set_blocking(read_fd, False)
        
        # 压缩写入线程
        def compress_writer():
            """在独立线程中运行tar压缩"""
            try:
                with os.fdopen(write_fd, 'wb') as pipe_writer:
                    with gzip.GzipFile(fileobj=pipe_writer, mode='wb') as gz:
                        with tarfile.open(fileobj=gz, mode='w|') as tar:
                            for source in sources:
                                if source.is_file():
                                    tar.add(str(source), arcname=source.name)
                                    if progress_callback:
                                        # 使用队列传递进度信息
                                        progress_queue.put((source.name, source.stat().st_size))
                                elif source.is_dir():
                                    for item in source.rglob('*'):
                                        if item.is_file():
                                            tar.add(str(item), arcname=str(item.relative_to(source.parent)))
                                            if progress_callback:
                                                progress_queue.put((str(item), item.stat().st_size))
            except Exception as e:
                error_queue.put(e)
            finally:
                # 确保写端关闭
                try:
                    os.close(write_fd)
                except:
                    pass
        
        # 进度和错误队列
        progress_queue = queue.Queue()
        error_queue = queue.Queue()
        
        # 启动压缩线程
        compress_thread = threading.Thread(target=compress_writer)
        compress_thread.start()
        
        try:
            with os.fdopen(read_fd, 'rb') as pipe_reader:
                while True:
                    # 检查错误
                    if not error_queue.empty():
                        raise error_queue.get()
                    
                    # 处理进度回调
                    while not progress_queue.empty():
                        file_name, size = progress_queue.get()
                        if progress_callback:
                            await progress_callback(file_name, size)
                    
                    # 读取数据
                    try:
                        data = pipe_reader.read(1024 * 1024)  # 1MB buffer
                    except BlockingIOError:
                        # 没有数据可读，等待
                        await asyncio.sleep(0.01)
                        continue
                    
                    if not data:
                        # 检查线程是否还在运行
                        if not compress_thread.is_alive():
                            break
                        await asyncio.sleep(0.01)
                        continue
                    
                    # 如果需要新分片
                    if current_chunk_file is None or bytes_in_current_chunk >= self.chunk_size:
                        if current_chunk_file:
                            current_chunk_file.close()
                            print(f"完成分片 {chunk_index-1}: {bytes_in_current_chunk} bytes")
                        
                        chunk_filename = f"{output_prefix}.part{chunk_index:04d}"
                        current_chunk_file = open(chunk_filename, 'wb')
                        bytes_in_current_chunk = 0
                        chunk_index += 1
                    
                    # 写入当前分片
                    current_chunk_file.write(data)
                    bytes_in_current_chunk += len(data)
                    
                    # 让出控制权
                    await asyncio.sleep(0)
                
                # 关闭最后一个分片
                if current_chunk_file:
                    current_chunk_file.close()
                    print(f"完成分片 {chunk_index-1}: {bytes_in_current_chunk} bytes")
        
        finally:
            # 确保线程结束
            compress_thread.join(timeout=5)
            
            # 清理资源
            try:
                os.close(read_fd)
            except:
                pass
        
        return chunk_index
    
    async def decompress_stream_from_chunks(
        self,
        input_prefix: str,
        output_dir: Path,
        progress_callback: Optional[Callable] = None
    ):
        """
        真正的流式解压 - 边读边解压边写
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建管道
        read_fd, write_fd = os.pipe()
        
        # 分片读取线程
        def chunk_reader():
            """在独立线程中读取分片并写入管道"""
            try:
                with os.fdopen(write_fd, 'wb') as pipe_writer:
                    chunk_index = 0
                    while True:
                        chunk_filename = f"{input_prefix}.part{chunk_index:04d}"
                        if not Path(chunk_filename).exists():
                            break
                        
                        print(f"读取分片 {chunk_index}")
                        with open(chunk_filename, 'rb') as chunk_file:
                            while True:
                                data = chunk_file.read(1024 * 1024)  # 1MB buffer
                                if not data:
                                    break
                                pipe_writer.write(data)
                                pipe_writer.flush()
                        
                        chunk_index += 1
                        
            except Exception as e:
                error_queue.put(e)
            finally:
                try:
                    os.close(write_fd)
                except:
                    pass
        
        # 进度和错误队列
        progress_queue = queue.Queue()
        error_queue = queue.Queue()
        
        # 解压提取线程
        def decompress_extractor():
            """在独立线程中解压和提取文件"""
            try:
                with os.fdopen(read_fd, 'rb') as pipe_reader:
                    with gzip.GzipFile(fileobj=pipe_reader, mode='rb') as gz:
                        with tarfile.open(fileobj=gz, mode='r|') as tar:
                            for member in tar:
                                tar.extract(member, output_dir)
                                if progress_callback:
                                    progress_queue.put((member.name, member.size))
            except Exception as e:
                error_queue.put(e)
            finally:
                try:
                    os.close(read_fd)
                except:
                    pass
        
        # 启动线程
        reader_thread = threading.Thread(target=chunk_reader)
        extractor_thread = threading.Thread(target=decompress_extractor)
        
        reader_thread.start()
        extractor_thread.start()
        
        # 监控进度
        while reader_thread.is_alive() or extractor_thread.is_alive():
            # 检查错误
            if not error_queue.empty():
                raise error_queue.get()
            
            # 处理进度
            while not progress_queue.empty():
                file_name, size = progress_queue.get()
                if progress_callback:
                    await progress_callback(file_name, size)
            
            await asyncio.sleep(0.1)
        
        # 最后检查错误
        if not error_queue.empty():
            raise error_queue.get()
        
        print("解压完成！")


class NetworkStreamingExample:
    """网络流式传输示例"""
    
    @staticmethod
    async def compress_and_stream_to_network(sources: list[Path], host: str, port: int):
        """
        压缩并直接流式传输到网络
        完全不写入本地磁盘
        """
        import socket
        
        # 创建socket连接
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        
        # 创建管道
        read_fd, write_fd = os.pipe()
        
        # 压缩线程
        def compress_to_pipe():
            with os.fdopen(write_fd, 'wb') as pipe_writer:
                with gzip.GzipFile(fileobj=pipe_writer, mode='wb') as gz:
                    with tarfile.open(fileobj=gz, mode='w|') as tar:
                        for source in sources:
                            if source.is_file():
                                tar.add(str(source))
                            elif source.is_dir():
                                tar.add(str(source), recursive=True)
        
        # 网络发送任务
        async def send_to_network():
            loop = asyncio.get_event_loop()
            
            with os.fdopen(read_fd, 'rb') as pipe_reader:
                while True:
                    data = pipe_reader.read(1024 * 1024)  # 1MB chunks
                    if not data:
                        break
                    
                    # 异步发送到网络
                    await loop.sock_sendall(sock, data)
                    print(f"发送了 {len(data)} bytes 到网络")
            
            sock.close()
        
        # 启动压缩线程
        compress_thread = threading.Thread(target=compress_to_pipe)
        compress_thread.start()
        
        # 执行网络发送
        try:
            await send_to_network()
        finally:
            compress_thread.join()
            os.close(write_fd)
        
        print("网络传输完成！")


# 使用示例
async def demo_true_streaming():
    """演示真正的流式处理"""
    
    print("=== 真正的流式压缩示例 ===")
    
    compressor = TrueStreamingCompressor(chunk_size=10*1024*1024)  # 10MB chunks
    
    # 准备测试数据
    test_dir = Path("test_data")
    test_dir.mkdir(exist_ok=True)
    
    # 创建一些测试文件
    for i in range(5):
        file_path = test_dir / f"file_{i}.txt"
        file_path.write_text(f"Test content {i}\n" * 10000)
    
    # 进度回调
    async def show_progress(name, size):
        print(f"  处理: {name} ({size:,} bytes)")
    
    # 1. 流式压缩
    print("\n开始流式压缩...")
    num_chunks = await compressor.compress_stream_to_chunks(
        [test_dir],
        "streaming_backup",
        progress_callback=show_progress
    )
    print(f"压缩完成！生成了 {num_chunks} 个分片")
    
    # 2. 流式解压
    print("\n开始流式解压...")
    restore_dir = Path("restored_streaming")
    await compressor.decompress_stream_from_chunks(
        "streaming_backup",
        restore_dir,
        progress_callback=show_progress
    )
    
    # 清理
    import shutil
    shutil.rmtree(test_dir)
    shutil.rmtree(restore_dir)
    for i in range(num_chunks):
        Path(f"streaming_backup.part{i:04d}").unlink()


async def demo_memory_usage():
    """演示内存使用情况"""
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    
    print("=== 内存使用监控 ===")
    
    # 创建大文件进行测试
    test_file = Path("large_test.bin")
    
    print("创建1GB测试文件...")
    with open(test_file, 'wb') as f:
        for _ in range(1024):  # 1GB
            f.write(os.urandom(1024 * 1024))  # 1MB chunks
    
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    print(f"初始内存使用: {initial_memory:.2f} MB")
    
    # 流式压缩
    compressor = TrueStreamingCompressor(chunk_size=100*1024*1024)  # 100MB chunks
    
    async def monitor_memory():
        while True:
            current_memory = process.memory_info().rss / 1024 / 1024
            print(f"当前内存使用: {current_memory:.2f} MB (增加: {current_memory - initial_memory:.2f} MB)")
            await asyncio.sleep(1)
    
    # 启动内存监控
    monitor_task = asyncio.create_task(monitor_memory())
    
    try:
        # 执行压缩
        await compressor.compress_stream_to_chunks(
            [test_file],
            "memory_test"
        )
    finally:
        monitor_task.cancel()
    
    final_memory = process.memory_info().rss / 1024 / 1024
    print(f"\n最终内存使用: {final_memory:.2f} MB")
    print(f"内存增加: {final_memory - initial_memory:.2f} MB")
    print("注意：即使处理1GB文件，内存增加应该保持在较低水平")
    
    # 清理
    test_file.unlink()
    chunk_index = 0
    while True:
        chunk_file = Path(f"memory_test.part{chunk_index:04d}")
        if chunk_file.exists():
            chunk_file.unlink()
            chunk_index += 1
        else:
            break


if __name__ == "__main__":
    print("高级流式处理演示\n")
    print("1. 真正的流式压缩/解压")
    print("2. 内存使用监控")
    print("3. 网络流式传输（需要服务器）")
    
    choice = input("\n选择演示 (1-3): ")
    
    if choice == "1":
        asyncio.run(demo_true_streaming())
    elif choice == "2":
        asyncio.run(demo_memory_usage())
    elif choice == "3":
        print("网络传输示例需要先启动接收服务器")
        print("示例代码见 NetworkStreamingExample 类")
    else:
        print("无效选择")
