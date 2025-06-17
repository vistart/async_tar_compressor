# Async Tar Processor

一个功能强大的异步 tar 压缩/解压缩工具，支持进度显示、中断处理，并能优雅地处理自定义 Python 构建中缺失的压缩模块。

## 主要特性

- **异步操作**：非阻塞的压缩和解压缩操作，实时进度跟踪
- **多种压缩算法**：支持 GZIP、BZIP2、XZ/LZMA、LZ4 和无压缩模式
- **灵活的 I/O 支持**：
  - 文件系统操作（文件和目录）
  - 内存操作（BytesIO、bytes、base64 字符串）
  - 混合操作（文件到内存、内存到文件）
- **智能检测**：自动检测压缩类型，无需手动指定
- **优雅降级**：自动处理缺失的压缩模块，提供备选方案
- **友好的用户界面**：
  - 交互式向导模式
  - 丰富的进度条显示（使用 Rich 库）
  - 智能的中断处理（带确认提示）

## 安装

### 基础安装

```bash
# 必需的 UI 库
pip install rich

# 可选的 LZ4 支持
pip install lz4
```

### 修复缺失的压缩支持

如果遇到压缩模块缺失（常见于自定义 Python 构建）：

#### 1. 安装系统依赖

**Ubuntu/Debian：**
```bash
sudo apt-get update
sudo apt-get install -y zlib1g-dev libbz2-dev liblzma-dev
```

**CentOS/RHEL/Fedora：**
```bash
sudo yum install -y zlib-devel bzip2-devel xz-devel
```

**macOS：**
```bash
brew install zlib bzip2 xz
```

#### 2. 重新编译 Python

```bash
./configure --enable-optimizations
make -j$(nproc)
sudo make altinstall
```

#### 3. 或使用预编译的 Python 发行版

- 系统 Python：`sudo apt install python3-full`
- 使用 pyenv：`pyenv install 3.11.0`
- 使用 Anaconda/Miniconda
- 使用官方 Docker 镜像

## 快速开始

### 命令行使用

```bash
# 压缩文件/目录
python tar_compressor.py -c file1.txt dir1/ -o archive.tar.gz -t gz

# 解压缩（自动检测类型）
python tar_compressor.py -d archive.tar.gz -o output_dir/

# 列出压缩包内容
python tar_compressor.py -l archive.tar.gz

# 交互式模式
python tar_compressor.py -i

# 检查压缩支持
python tar_compressor.py --check

# 运行诊断
python tar_compressor.py --diagnostic
```

### Python API 使用

#### 基础压缩/解压缩

```python
import asyncio
from tar_compressor import AsyncTarProcessor, CompressionType

async def main():
    # 创建处理器
    processor = AsyncTarProcessor(CompressionType.GZIP)
    
    # 压缩文件
    success = await processor.compress_with_progress(
        ['file1.txt', 'dir1/'],
        'archive.tar.gz'
    )
    
    # 解压缩（自动检测类型）
    processor = AsyncTarProcessor()
    success = await processor.decompress_with_progress(
        'archive.tar.gz',
        'output_dir/'
    )

asyncio.run(main())
```

#### 内存操作

```python
# 压缩到不同的内存格式
archive_bytesio = await processor.compress_to_memory(['file.txt'])
archive_bytes = await processor.compress_to_bytes(['file.txt'])
archive_str = await processor.compress_to_str(['file.txt'])  # base64

# 从内存解压缩
await processor.decompress_with_progress(archive_bytes, 'output/')
await processor.decompress_from_str(archive_str, 'output/')
```

#### 处理缺失的压缩模块

```python
# 检查算法支持
if AsyncTarProcessor.is_algorithm_supported(CompressionType.BZIP2):
    processor = AsyncTarProcessor(CompressionType.BZIP2)
else:
    # 获取可用算法列表
    available = AsyncTarProcessor.get_supported_algorithms()
    if available:
        processor = AsyncTarProcessor(available[0])
    else:
        print("没有可用的压缩算法！")
```

## 高级功能

### 压缩算法选择指南

| 算法 | 压缩比 | 速度 | 推荐场景 |
|------|--------|------|----------|
| GZIP | 中等 | 快速 | 通用场景，平衡的选择 |
| BZIP2 | 高 | 较慢 | 需要高压缩比时 |
| XZ | 最高 | 最慢 | 存档、长期存储 |
| LZ4 | 较低 | 极快 | 实时处理、临时文件 |
| NONE | 无 | 最快 | 仅打包，不压缩 |

### 进度显示和中断处理

```python
# 压缩时会显示：
# ⠋ Compressing to archive.tar.gz ━━━━━━━╸━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 20% 2/10 2.0/10.0 MB 0:00:05 0:00:20
# Current file: data.txt ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 1.0/1.0 MB

# 按 Ctrl+C 中断：
# 第一次：询问是否中断
# 第二次：强制中断
```

### 自动检测和回退机制

```python
from compression_utils import suggest_fallback_algorithm

# 获取压缩支持状态
support = check_compression_support()
# 返回：{'gzip': True, 'bzip2': False, 'xz': True, 'lz4': False}

# 获取推荐的替代算法
fallback = suggest_fallback_algorithm('bzip2')
# 返回：'gzip'（如果可用）

# 测试实际功能
results = test_compression_functionality()
# 返回：{'gzip': (True, 'Working correctly'), ...}
```

## 运行示例和测试

### 运行交互式示例

```bash
# 运行主示例程序
python tar_compressor_example.py

# 选择特定示例：
# 1. 基础压缩和解压缩
# 2. 增强的内存操作（BytesIO、bytes、str）
# 3. 压缩可用性检查和回退
# 4. 压缩算法比较
# 5. 自动检测压缩类型
# 6. 中断处理（增强版）
# 7. 混合操作
# 8. 交互式向导
# 9. 运行综合测试套件
```

### 运行性能基准测试

```bash
python benchmark.py
```

基准测试包括：
- 不同压缩算法的性能比较
- 不同数据类型的压缩效果
- 压缩级别对性能的影响
- 文件大小和数量的影响

## API 参考

### AsyncTarProcessor 类

主要的压缩/解压缩处理类。

**类方法：**
- `get_supported_algorithms()` → `List[CompressionType]`：获取支持的算法列表
- `is_algorithm_supported(algorithm: CompressionType)` → `bool`：检查算法是否可用
- `get_algorithm_info(algorithm: CompressionType)` → `CompressionInfo`：获取算法详细信息
- `print_support_summary(console: Console)`：打印支持情况表格

**实例方法：**

压缩方法：
- `compress_with_progress(sources, output, chunk_size=1MB)` → `bool`：带进度条压缩
- `compress_to_memory(sources, chunk_size=1MB)` → `BytesIO`：压缩到 BytesIO
- `compress_to_bytes(sources, chunk_size=1MB)` → `bytes`：压缩到字节串
- `compress_to_str(sources, chunk_size=1MB)` → `str`：压缩到 base64 字符串

解压缩方法：
- `decompress_with_progress(archive, output_dir, chunk_size=1MB)` → `bool`：带进度条解压
- `decompress_from_str(archive_str, output_dir, chunk_size=1MB)` → `bool`：从 base64 解压
- `list_archive_contents(archive)` → `List[Tuple[str, int, bool]]`：列出内容

### compression_utils 模块

压缩支持检查工具函数。

**主要函数：**
- `check_compression_support()` → `Dict[str, bool]`：检查各算法可用性
- `get_available_algorithms()` → `List[str]`：获取可用算法列表
- `suggest_fallback_algorithm(preferred: str)` → `str`：建议替代算法
- `test_compression_functionality()` → `Dict[str, Tuple[bool, str]]`：测试实际功能

## 故障排除

### 常见问题

#### 1. "Module not available" 错误

这通常意味着 Python 编译时缺少压缩支持：

```bash
# 运行诊断
python tar_compressor.py --diagnostic

# 查看缺失的模块和解决方案
```

#### 2. 自定义 Python 构建问题

如果使用自定义编译的 Python：

1. 确保在编译 Python 之前安装了开发库
2. 检查配置：`python -m sysconfig | grep CONFIG_ARGS`
3. 验证模块：
   ```python
   import gzip, bz2, lzma  # 不应该报错
   ```

#### 3. 性能优化建议

- 实时处理：使用 LZ4（需要 `pip install lz4`）
- 通用场景：使用 GZIP
- 最大压缩：使用 XZ
- 仅打包：使用无压缩模式

### 错误处理

工具会优雅地处理各种错误情况：

```python
# 缺失压缩模块时自动降级
processor = AsyncTarProcessor(CompressionType.BZIP2)  # 如果 bzip2 不可用
# 自动建议使用 GZIP 或其他可用算法

# 文件不存在时的友好提示
# 权限不足时的明确说明
# 中断操作时的确认机制
```

## 项目结构

```
async_tar_processor/
├── tar_compressor.py           # 主模块
├── tar_compressor_example.py   # 示例程序
├── compression_utils.py        # 压缩支持工具
├── benchmark.py               # 性能基准测试
├── main.py                    # 简单示例
├── checker.py                 # 快速检查脚本
└── README.md                  # 本文档
```

## 贡献指南

欢迎提交问题报告和改进建议。在提交之前，请：

1. 运行诊断确认环境：`python tar_compressor.py --diagnostic`
2. 提供完整的错误信息
3. 说明 Python 版本和操作系统

## 许可证

本项目仅供演示和学习使用。