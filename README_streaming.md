# 流式打包压缩解压工具

一个真正的流式处理工具，支持边压缩边分片、边接收边解压，最大化内存效率。

## 🌟 核心特性

### 流式处理架构
- **流式压缩分片**: 压缩过程中直接生成分片，无需生成完整文件
- **流式解压**: 接收分片立即解压，无需等待全部分片
- **内存高效**: 固定内存缓冲区，处理完立即释放
- **并发处理**: 利用异步IO实现高效并发

### 完整功能
- ✅ 压缩功能（支持 GZIP、BZIP2、XZ、LZ4）
- ✅ 解压功能（自动检测压缩格式）
- ✅ 自动分片（可配置分片大小）
- ✅ 流式处理（最小内存占用）
- ✅ 数据完整性（SHA256校验和）
- ✅ 进度回调（实时监控处理进度）

## 📋 系统要求

### Python 版本
- Python 3.7+ （需要异步文件IO支持）

### 依赖包
```bash
# 必需依赖
pip install aiofiles  # 异步文件操作

# 可选依赖（LZ4压缩）
pip install lz4
```

## 🚀 快速开始

### 1. 基本使用 - 压缩并分片

```python
import asyncio
from streaming_tar_compressor import compress_with_chunks, CompressionType

async def compress_example():
    # 压缩目录并自动分片（每片50MB）
    chunks = await compress_with_chunks(
        sources=["my_data/", "file.txt"],  # 可以混合文件和目录
        output_prefix="backup",             # 生成 backup.part0000, backup.part0001...
        compression=CompressionType.GZIP,
        chunk_size=50*1024*1024            # 50MB per chunk
    )
    
    print(f"生成了 {len(chunks)} 个分片")
    
asyncio.run(compress_example())
```

### 2. 基本使用 - 从分片解压

```python
import asyncio
from streaming_tar_compressor import decompress_from_chunks, CompressionType

async def decompress_example():
    # 从分片文件解压
    await decompress_from_chunks(
        input_prefix="backup",           # 读取 backup.part0000, backup.part0001...
        output_dir="restored/",          # 解压到此目录
        compression=CompressionType.GZIP,
        verify_checksum=True             # 验证数据完整性
    )
    
    print("解压完成！")
    
asyncio.run(decompress_example())
```

## 💻 高级用法

### 自定义流式处理

```python
import asyncio
from streaming_tar_compressor import StreamingTarCompressor, CompressionType

async def custom_streaming():
    compressor = StreamingTarCompressor(CompressionType.GZIP)
    
    # 自定义分片处理
    async for chunk_index, chunk_data in compressor.compress_to_chunks(["data/"]):
        # 可以将分片发送到网络、写入数据库等
        print(f"处理分片 {chunk_index}: {len(chunk_data)} bytes")
        
        # 示例：发送到远程服务器
        # await send_to_remote(chunk_data)
        
        # 示例：加密后保存
        # encrypted = encrypt(chunk_data)
        # await save_encrypted_chunk(encrypted)

asyncio.run(custom_streaming())
```

### 网络传输示例

```python
import asyncio
import aiohttp
from streaming_tar_compressor import StreamingTarCompressor

async def compress_and_upload():
    """压缩并直接上传到服务器"""
    compressor = StreamingTarCompressor(CompressionType.GZIP)
    
    async with aiohttp.ClientSession() as session:
        chunk_index = 0
        async for _, chunk_data in compressor.compress_to_chunks(["large_data/"]):
            # 直接上传分片
            async with session.post(
                f"https://backup.server/upload/chunk/{chunk_index}",
                data=chunk_data
            ) as resp:
                if resp.status == 200:
                    print(f"上传分片 {chunk_index} 成功")
            
            chunk_index += 1

async def download_and_decompress():
    """从服务器下载并解压"""
    async def download_chunks():
        """生成器：从服务器下载分片"""
        async with aiohttp.ClientSession() as session:
            chunk_index = 0
            while True:
                async with session.get(
                    f"https://backup.server/download/chunk/{chunk_index}"
                ) as resp:
                    if resp.status == 404:
                        break  # 没有更多分片
                    
                    chunk_data = await resp.read()
                    yield chunk_data
                    chunk_index += 1
    
    # 流式解压
    decompressor = StreamingTarCompressor(CompressionType.GZIP)
    await decompressor.decompress_from_chunks(
        download_chunks(),
        "restored_data/"
    )
```

### 进度监控

```python
import asyncio
from datetime import datetime
from streaming_tar_compressor import compress_with_chunks, decompress_from_chunks

class ProgressTracker:
    def __init__(self):
        self.start_time = datetime.now()
        self.processed_files = 0
        self.total_bytes = 0
    
    async def compress_progress(self, file_path, size):
        self.processed_files += 1
        self.total_bytes += size
        elapsed = (datetime.now() - self.start_time).total_seconds()
        speed = self.total_bytes / elapsed / 1024 / 1024  # MB/s
        print(f"[压缩] {file_path} | 已处理: {self.processed_files} 个文件 | "
              f"速度: {speed:.2f} MB/s")
    
    async def decompress_progress(self, file_name, size):
        self.processed_files += 1
        self.total_bytes += size
        print(f"[解压] {file_name} | 大小: {size:,} bytes")

async def compress_with_progress():
    tracker = ProgressTracker()
    
    chunks = await compress_with_chunks(
        ["large_project/"],
        "project_backup",
        progress_callback=tracker.compress_progress
    )
    
    print(f"\n压缩完成！")
    print(f"总文件数: {tracker.processed_files}")
    print(f"总大小: {tracker.total_bytes / 1024 / 1024:.2f} MB")
    print(f"分片数: {len(chunks)}")

asyncio.run(compress_with_progress())
```

### 管道处理

```python
import asyncio
from streaming_tar_compressor import StreamingTarCompressor

async def pipeline_example():
    """演示管道处理：压缩 -> 加密 -> 上传"""
    
    compressor = StreamingTarCompressor(CompressionType.GZIP)
    
    async def encrypt_chunk(chunk_data):
        """模拟加密处理"""
        # 实际使用时替换为真实加密
        return chunk_data[::-1]  # 简单反转作为示例
    
    async def upload_chunk(chunk_index, encrypted_data):
        """模拟上传"""
        print(f"上传加密分片 {chunk_index}: {len(encrypted_data)} bytes")
        await asyncio.sleep(0.1)  # 模拟网络延迟
    
    # 管道处理
    async for chunk_index, chunk_data in compressor.compress_to_chunks(["data/"]):
        # 步骤1: 加密
        encrypted = await encrypt_chunk(chunk_data)
        
        # 步骤2: 上传
        await upload_chunk(chunk_index, encrypted)
        
        # 内存会自动释放，不会堆积

asyncio.run(pipeline_example())
```

## 🏗️ 架构设计

### 数据流向

```
压缩流程:
源文件 → Tar流 → 压缩流 → 分片生成器 → 输出处理

解压流程:
分片输入 → 合并流 → 解压流 → Tar提取 → 目标文件
```

### 内存管理策略

1. **固定缓冲区**: 使用1MB的固定内存缓冲区
2. **流式处理**: 数据处理完立即释放，不保留中间结果
3. **异步IO**: 利用异步避免阻塞，提高并发性能
4. **生成器模式**: 使用异步生成器实现真正的流式处理

## 📊 性能特点

### 内存使用
- 峰值内存: ~10MB（与文件大小无关）
- 缓冲区大小: 1MB（可调整）
- 分片缓存: 仅当前处理的分片

### 处理速度
- 主要受限于: 磁盘IO和压缩算法
- 并发优势: 可同时进行读取、压缩、写入
- 网络友好: 适合边压缩边传输场景

## 🛡️ 数据完整性

### 校验机制
- 每个分片包含SHA256校验和
- 元数据文件记录所有分片信息
- 解压时可选择性验证校验和

### 元数据格式

```json
{
  "version": "1.0",
  "total_chunks": 5,
  "chunks": [
    {
      "index": 0,
      "size": 52428800,
      "checksum": "abc123..."
    },
    ...
  ]
}
```

## 🔧 配置选项

### 压缩算法对比

| 算法 | 速度 | 压缩率 | CPU使用 | 适用场景 |
|------|------|--------|---------|----------|
| GZIP | 快 | 中 | 中 | 通用，平衡选择 |
| BZIP2 | 慢 | 高 | 高 | 文本文件，需要高压缩率 |
| XZ | 最慢 | 最高 | 最高 | 长期存档，带宽受限 |
| LZ4 | 最快 | 低 | 低 | 实时处理，临时文件 |

### 分片大小建议

- **局域网传输**: 100-500MB
- **互联网传输**: 10-50MB
- **云存储**: 50-100MB
- **移动网络**: 5-10MB

## 📝 完整示例

### 备份系统示例

```python
import asyncio
from pathlib import Path
from datetime import datetime
from streaming_tar_compressor import (
    compress_with_chunks, 
    decompress_from_chunks,
    CompressionType
)

class BackupSystem:
    def __init__(self, backup_dir="backups/"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
    
    async def create_backup(self, source_dirs, backup_name=None):
        """创建备份"""
        if not backup_name:
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        backup_path = self.backup_dir / backup_name
        
        print(f"开始备份到: {backup_path}")
        
        # 压缩并分片
        chunks = await compress_with_chunks(
            sources=source_dirs,
            output_prefix=str(backup_path),
            compression=CompressionType.GZIP,
            chunk_size=100*1024*1024,  # 100MB chunks
            progress_callback=self._backup_progress
        )
        
        print(f"备份完成！共 {len(chunks)} 个分片")
        
        # 创建备份信息文件
        info_file = backup_path.parent / f"{backup_name}.info"
        with open(info_file, 'w') as f:
            f.write(f"Backup Name: {backup_name}\n")
            f.write(f"Date: {datetime.now()}\n")
            f.write(f"Sources: {', '.join(map(str, source_dirs))}\n")
            f.write(f"Chunks: {len(chunks)}\n")
            f.write(f"Total Size: {sum(c.size for c in chunks):,} bytes\n")
        
        return backup_name
    
    async def restore_backup(self, backup_name, restore_dir):
        """恢复备份"""
        backup_path = self.backup_dir / backup_name
        
        print(f"开始恢复备份: {backup_name}")
        
        await decompress_from_chunks(
            input_prefix=str(backup_path),
            output_dir=restore_dir,
            compression=CompressionType.GZIP,
            verify_checksum=True,
            progress_callback=self._restore_progress
        )
        
        print(f"恢复完成到: {restore_dir}")
    
    async def _backup_progress(self, file_path, size):
        print(f"  备份: {file_path}")
    
    async def _restore_progress(self, file_name, size):
        print(f"  恢复: {file_name}")

# 使用示例
async def main():
    backup_system = BackupSystem()
    
    # 创建备份
    backup_name = await backup_system.create_backup([
        "project/src/",
        "project/docs/",
        "project/config.json"
    ])
    
    # 恢复备份
    await backup_system.restore_backup(
        backup_name,
        "restored_project/"
    )

asyncio.run(main())
```

## ⚠️ 注意事项

1. **异步IO要求**: 需要支持异步文件操作的环境
2. **分片顺序**: 解压时必须按顺序提供分片
3. **中断恢复**: 当前版本不支持断点续传
4. **内存限制**: 单个文件不能超过缓冲区大小（默认1MB）

## 🔮 后续改进方向

- [ ] 断点续传支持
- [ ] 并行压缩/解压
- [ ] 加密支持
- [ ] 增量备份
- [ ] 压缩率自适应
- [ ] 分片大小自动优化

## 📄 许可证

MIT License
