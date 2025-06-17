# Async Tar Compressor

一个功能强大的异步 tar 压缩工具，支持多种压缩算法、进度显示、智能中断处理和内存操作。

## 🌟 主要特性

- **异步操作**: 基于 asyncio 的高性能异步压缩
- **多种压缩算法**: 支持 GZIP、BZIP2、XZ/LZMA、LZ4 和无压缩
- **实时进度显示**: 使用 Rich 库提供美观的进度条和统计信息
- **智能中断处理**: 支持 Ctrl+C 中断，首次询问确认，二次强制退出
- **内存操作**: 支持压缩到 BytesIO 对象，无需写入磁盘
- **综合基准测试**: 内置性能测试工具，帮助选择最优压缩算法
- **交互式模式**: 友好的命令行交互界面
- **跨平台支持**: 支持 Windows、Linux 和 macOS

## 📋 系统要求

### Python 版本
- Python 3.7 或更高版本

### 必需依赖
```bash
pip install rich
```

### 可选依赖
```bash
# LZ4 压缩支持
pip install lz4
```

### 系统依赖
某些压缩算法需要系统级库支持：

**Ubuntu/Debian:**
```bash
sudo apt install zlib1g-dev libbz2-dev liblzma-dev
```

**CentOS/RHEL:**
```bash
sudo yum install zlib-devel bzip2-devel xz-devel
```

**macOS:**
```bash
brew install zlib bzip2 xz
```

## 🚀 快速开始

### 1. 检查压缩算法支持
```bash
python tar_compressor.py --check
```

### 2. 基本使用
```bash
# 使用 GZIP 压缩文件
python tar_compressor.py file1.txt file2.txt -o archive.tar.gz -c gz

# 压缩整个目录
python tar_compressor.py /path/to/directory -o backup.tar.bz2 -c bz2

# 混合压缩文件和目录
python tar_compressor.py file1.txt dir1/ dir2/ -o mixed.tar.xz -c xz
```

### 3. 交互式模式
```bash
python tar_compressor.py -i
# 或直接运行不带参数
python tar_compressor.py
```

## 📖 详细使用说明

### 命令行参数

```
usage: tar_compressor.py [-h] [-o OUTPUT] [-c {gz,bz2,xz,lz4,none}] 
                        [-i] [--check] [--diagnostic] [--demo]
                        [sources ...]

positional arguments:
  sources               要压缩的文件或目录

optional arguments:
  -h, --help           显示帮助信息
  -o OUTPUT            输出文件名
  -c {gz,bz2,xz,lz4,none}  压缩类型 (默认: gz)
  -i, --interactive    交互式模式
  --check             检查压缩算法支持
  --diagnostic        运行详细的压缩支持诊断
  --demo              运行演示程序
```

### 压缩算法说明

| 算法 | 扩展名 | 特点 | 适用场景 |
|------|--------|------|----------|
| GZIP | .gz | 平衡的压缩率和速度 | 通用场景，日常使用 |
| BZIP2 | .bz2 | 高压缩率，速度较慢 | 需要高压缩率的场景 |
| XZ/LZMA | .xz | 最高压缩率，速度最慢 | 长期存档，网络传输 |
| LZ4 | .lz4 | 极快速度，压缩率较低 | 实时压缩，临时存储 |
| NONE | 无 | 仅打包，不压缩 | 已压缩文件的归档 |

## 💻 编程接口 (API)

### 基本使用

```python
import asyncio
from pathlib import Path
from tar_compressor import AsyncTarCompressor, CompressionType

async def compress_files():
    # 创建压缩器实例
    compressor = AsyncTarCompressor(CompressionType.GZIP)
    
    # 压缩文件
    sources = [Path("file1.txt"), Path("directory1/")]
    output = Path("archive.tar.gz")
    
    success = await compressor.compress_with_progress(sources, output)
    return success

# 运行
asyncio.run(compress_files())
```

### 压缩到内存

```python
async def compress_to_memory():
    compressor = AsyncTarCompressor(CompressionType.BZIP2)
    
    # 压缩到 BytesIO
    sources = [Path("data/")]
    memory_archive = await compressor.compress_to_memory(sources)
    
    if memory_archive:
        # 使用内存中的压缩数据
        data = memory_archive.read()
        print(f"压缩数据大小: {len(data)} 字节")
    
    return memory_archive

asyncio.run(compress_to_memory())
```

### 使用 BytesIO 作为输出

```python
from io import BytesIO

async def compress_to_bytesio():
    compressor = AsyncTarCompressor(CompressionType.XZ)
    output_buffer = BytesIO()
    
    sources = [Path("important_data/")]
    success = await compressor.compress_with_progress(
        sources, 
        output_buffer
    )
    
    if success:
        # 获取压缩数据
        output_buffer.seek(0)
        compressed_data = output_buffer.read()
    
    return compressed_data

asyncio.run(compress_to_bytesio())
```

### 流式处理示例

虽然当前版本不支持自动分片，但支持流式内存操作：

```python
import asyncio
from io import BytesIO
from pathlib import Path
from tar_compressor import AsyncTarCompressor, CompressionType

async def stream_compress_to_chunks():
    """将压缩数据流式处理成块"""
    compressor = AsyncTarCompressor(CompressionType.GZIP)
    output_buffer = BytesIO()
    
    # 压缩到内存流
    sources = [Path("large_directory/")]
    success = await compressor.compress_with_progress(
        sources,
        output_buffer,
        chunk_size=1024*1024  # 1MB chunks
    )
    
    if success:
        # 读取压缩数据并分块
        output_buffer.seek(0)
        chunk_size = 1024 * 1024 * 10  # 10MB per chunk
        chunks = []
        
        while True:
            chunk = output_buffer.read(chunk_size)
            if not chunk:
                break
            chunks.append(chunk)
            print(f"生成块 {len(chunks)}: {len(chunk)} 字节")
        
        return chunks
    
    return None

# 运行示例
asyncio.run(stream_compress_to_chunks())
```

### 手动实现分片功能

如果需要分片功能，可以这样扩展：

```python
import asyncio
import os
from pathlib import Path
from tar_compressor import AsyncTarCompressor, CompressionType

async def compress_with_splitting(sources, output_prefix, max_size=1024*1024*100):
    """压缩并分割成多个文件（每个最大100MB）"""
    compressor = AsyncTarCompressor(CompressionType.GZIP)
    output_buffer = BytesIO()
    
    # 先压缩到内存
    success = await compressor.compress_with_progress(sources, output_buffer)
    
    if not success:
        return False
    
    # 分割压缩数据
    output_buffer.seek(0)
    part_num = 1
    
    while True:
        chunk = output_buffer.read(max_size)
        if not chunk:
            break
        
        part_filename = f"{output_prefix}.part{part_num:03d}"
        with open(part_filename, 'wb') as f:
            f.write(chunk)
        
        print(f"创建分片: {part_filename} ({len(chunk)} 字节)")
        part_num += 1
    
    # 创建信息文件
    info_file = f"{output_prefix}.info"
    with open(info_file, 'w') as f:
        f.write(f"parts={part_num-1}\n")
        f.write(f"total_size={output_buffer.tell()}\n")
    
    return True

# 使用示例
async def main():
    sources = [Path("large_data/")]
    await compress_with_splitting(sources, "archive", max_size=50*1024*1024)  # 50MB分片

asyncio.run(main())
```

### 合并分片示例

```python
def merge_split_files(prefix, output_file):
    """合并分片文件"""
    info_file = f"{prefix}.info"
    
    # 读取分片信息
    with open(info_file, 'r') as f:
        info = dict(line.strip().split('=') for line in f)
    
    parts = int(info['parts'])
    
    # 合并所有分片
    with open(output_file, 'wb') as outfile:
        for i in range(1, parts + 1):
            part_file = f"{prefix}.part{i:03d}"
            with open(part_file, 'rb') as infile:
                outfile.write(infile.read())
            print(f"已合并: {part_file}")
    
    print(f"合并完成: {output_file}")

# 使用示例
merge_split_files("archive", "archive_merged.tar.gz")
```

### 解压缩示例（使用标准库）

虽然主程序不包含解压功能，但可以使用 Python 标准库轻松实现：

```python
import tarfile
import asyncio
from pathlib import Path

async def extract_archive(archive_path, extract_to="."):
    """异步解压 tar 文件"""
    loop = asyncio.get_event_loop()
    
    def _extract():
        # 自动检测压缩类型
        with tarfile.open(archive_path, 'r:*') as tar:
            # 获取所有成员
            members = tar.getmembers()
            total = len(members)
            
            # 逐个解压并显示进度
            for i, member in enumerate(members):
                tar.extract(member, extract_to)
                print(f"解压进度: {i+1}/{total} - {member.name}")
            
            return total
    
    # 在线程池中运行以避免阻塞
    extracted = await loop.run_in_executor(None, _extract)
    print(f"解压完成！共解压 {extracted} 个文件")

# 使用示例
async def main():
    await extract_archive("archive.tar.gz", "extracted_files/")

asyncio.run(main())
```

### 流式处理大文件示例

```python
import tarfile
import io

def stream_process_tar(archive_path, process_func):
    """流式处理 tar 文件中的每个文件"""
    with tarfile.open(archive_path, 'r:*') as tar:
        for member in tar:
            if member.isfile():
                # 获取文件对象
                f = tar.extractfile(member)
                if f:
                    # 流式处理文件内容
                    while True:
                        chunk = f.read(1024 * 1024)  # 1MB chunks
                        if not chunk:
                            break
                        process_func(member.name, chunk)
                    f.close()

# 使用示例：统计文件内容
def count_bytes(filename, chunk):
    print(f"处理 {filename}: {len(chunk)} 字节")

stream_process_tar("archive.tar.gz", count_bytes)
```

### 完整的压缩解压工作流示例

```python
import asyncio
import tarfile
from pathlib import Path
from tar_compressor import AsyncTarCompressor, CompressionType

class ArchiveManager:
    """压缩和解压管理器"""
    
    async def compress_directory(self, source_dir, output_file):
        """压缩目录"""
        compressor = AsyncTarCompressor(CompressionType.GZIP)
        success = await compressor.compress_with_progress(
            [Path(source_dir)],
            output_file
        )
        return success
    
    async def extract_archive(self, archive_file, output_dir):
        """解压文件"""
        loop = asyncio.get_event_loop()
        
        def _extract():
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            with tarfile.open(archive_file, 'r:*') as tar:
                tar.extractall(output_dir)
                return len(tar.getmembers())
        
        count = await loop.run_in_executor(None, _extract)
        return count
    
    async def compress_and_split(self, source_dir, output_prefix, 
                                 chunk_size=100*1024*1024):
        """压缩并分片（100MB每片）"""
        # 先压缩到内存
        compressor = AsyncTarCompressor(CompressionType.GZIP)
        memory_buffer = await compressor.compress_to_memory([Path(source_dir)])
        
        if not memory_buffer:
            return False
        
        # 分片保存
        memory_buffer.seek(0)
        part = 1
        
        while True:
            chunk = memory_buffer.read(chunk_size)
            if not chunk:
                break
            
            part_file = f"{output_prefix}.part{part:03d}"
            Path(part_file).write_bytes(chunk)
            print(f"创建分片: {part_file}")
            part += 1
        
        return True
    
    def merge_and_extract(self, prefix, output_dir):
        """合并分片并解压"""
        # 合并分片
        merged_file = f"{prefix}_merged.tar.gz"
        with open(merged_file, 'wb') as outfile:
            part = 1
            while True:
                part_file = f"{prefix}.part{part:03d}"
                if not Path(part_file).exists():
                    break
                
                with open(part_file, 'rb') as infile:
                    outfile.write(infile.read())
                print(f"合并分片: {part_file}")
                part += 1
        
        # 解压合并后的文件
        with tarfile.open(merged_file, 'r:gz') as tar:
            tar.extractall(output_dir)
            print(f"解压完成到: {output_dir}")
        
        # 清理临时文件
        Path(merged_file).unlink()

# 使用示例
async def demo():
    manager = ArchiveManager()
    
    # 1. 压缩
    print("=== 压缩阶段 ===")
    await manager.compress_directory("my_data/", "backup.tar.gz")
    
    # 2. 压缩并分片
    print("\n=== 压缩并分片 ===")
    await manager.compress_and_split("large_data/", "large_backup")
    
    # 3. 解压
    print("\n=== 解压阶段 ===")
    await manager.extract_archive("backup.tar.gz", "restored_data/")
    
    # 4. 合并分片并解压
    print("\n=== 合并分片并解压 ===")
    manager.merge_and_extract("large_backup", "restored_large_data/")

asyncio.run(demo())
```

运行综合基准测试以选择最适合的压缩算法：

```bash
# 运行独立基准测试
python benchmark.py

# 从主演示程序运行
python main.py
# 然后选择选项 9
```

基准测试功能：
- 测试不同压缩算法和压缩级别
- 支持多种数据类型（文本、JSON、日志、二进制等）
- 可配置文件大小和数量
- 统计分析和性能建议
- 结果导出为 JSON

### 性能建议

根据使用场景选择压缩算法：

1. **追求速度**: 使用 LZ4 低压缩级别
2. **追求压缩率**: 使用 XZ 高压缩级别
3. **平衡性能**: 使用 GZIP 5-6 级别
4. **文本数据**: GZIP 和 BZIP2 表现良好
5. **二进制数据**: LZ4 通常是最佳选择

## 🛠️ 故障排除

### 1. 压缩模块不可用

如果遇到 "compression algorithm not available" 错误：

```bash
# 运行诊断
python tar_compressor.py --diagnostic

# 检查具体支持情况
python checker.py
```

### 2. 重新编译 Python

如果缺少压缩支持，可能需要重新编译 Python：

```bash
# 下载 Python 源码
wget https://www.python.org/ftp/python/3.x.x/Python-3.x.x.tgz
tar xzf Python-3.x.x.tgz
cd Python-3.x.x

# 配置并编译
./configure --enable-optimizations
make -j$(nproc)
sudo make altinstall
```

### 3. 使用完整的 Python 发行版

或者安装包含所有模块的 Python：

```bash
# Ubuntu/Debian
sudo apt install python3-full

# 使用 Anaconda
conda install python
```

## 📁 项目结构

```
.
├── tar_compressor.py    # 主程序
├── benchmark.py         # 基准测试工具
├── main.py             # 演示和示例程序
├── checker.py          # 压缩支持检查工具
├── BENCHMARK.md        # 基准测试详细文档
└── README.md           # 本文档
```

## 🎯 使用示例

### 示例 1: 备份项目目录
```bash
python tar_compressor.py ~/projects/myapp -o myapp_backup.tar.gz -c gz
```

### 示例 2: 归档日志文件
```bash
python tar_compressor.py /var/log/*.log -o logs_archive.tar.bz2 -c bz2
```

### 示例 3: 快速打包临时文件
```bash
python tar_compressor.py temp_files/ -o temp.tar.lz4 -c lz4
```

### 示例 4: 仅打包不压缩
```bash
python tar_compressor.py images/ videos/ -o media.tar -c none
```

## ⚡ 高级功能

### 中断处理

- 首次 Ctrl+C：询问是否中断
- 二次 Ctrl+C：强制退出
- 支持优雅的清理和状态保存

### 进度显示

- 实时显示压缩进度
- 显示当前处理的文件
- 预估剩余时间
- 显示压缩速度和压缩率

### 统计信息

压缩完成后显示：
- 处理的文件数量
- 原始大小和压缩后大小
- 压缩率
- 耗时
- 使用的压缩算法

## 🚧 功能限制与扩展建议

### 当前限制

1. **仅支持压缩**：当前版本只支持压缩功能，不支持解压
2. **无自动分片**：不支持自动将大文件分割成多个片段
3. **无流式解压**：需要完整文件才能处理

### 扩展建议

如果需要完整的流式处理和分片功能，可以考虑：

1. **解压功能实现**：
```python
# 示例：基于 tarfile 的解压实现
import tarfile

def extract_archive(archive_path, extract_to):
    """解压 tar 文件到指定目录"""
    with tarfile.open(archive_path, 'r:*') as tar:
        tar.extractall(extract_to)
```

2. **使用第三方工具分片**：
```bash
# 使用 split 命令分割大文件
split -b 100M archive.tar.gz archive.tar.gz.part

# 使用 cat 命令合并分片
cat archive.tar.gz.part* > archive.tar.gz
```

3. **结合其他工具**：
- 使用 `7zip` 进行分卷压缩
- 使用 `tar` + `split` 的组合命令
- 使用专门的备份工具如 `duplicity`

## 📋 功能对照表

| 功能 | 当前支持 | 说明 |
|------|---------|------|
| 压缩到文件 | ✅ | 完整支持，带进度显示 |
| 压缩到内存 (BytesIO) | ✅ | 支持流式内存操作 |
| 多种压缩算法 | ✅ | GZIP, BZIP2, XZ, LZ4 |
| 进度显示 | ✅ | 实时进度条和统计 |
| 中断处理 | ✅ | 智能中断确认 |
| 自动分片 | ❌ | 需手动实现 |
| 解压功能 | ❌ | 可用标准库实现 |
| 流式解压 | ❌ | 可用标准库实现 |
| 分片管理 | ❌ | 需手动实现 |

虽然主程序专注于压缩功能，但配合 Python 标准库和上述示例代码，可以实现完整的压缩、分片、解压工作流。

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本项目采用 MIT 许可证。

## 🔗 相关链接

- [Python tarfile 文档](https://docs.python.org/3/library/tarfile.html)
- [Rich 库文档](https://rich.readthedocs.io/)
- [LZ4 压缩库](https://github.com/python-lz4/python-lz4)
