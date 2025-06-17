import sys


def check_module(name, description, required=True):
    try:
        __import__(name)
        print(f"[✓] {name:<8} - {description} (可用)")
        return True
    except ImportError:
        status = "缺失" if required else "可选"
        print(f"[{'✗' if required else '?'}] {name:<8} - {description} ({status})")
        return False


print(f"Python 版本: {sys.version}")
print(f"编译信息: {sys.version_info}")
print("\n压缩支持检测:")

# 核心压缩模块检测
modules = [
    ("zlib", "gzip 压缩支持 (必需)", True),
    ("gzip", "gzip 文件操作 (必需)", True),
    ("bz2", "bzip2 压缩支持 (重要)", True),
    ("lzma", "LZMA/XZ 压缩支持 (重要)", True),
    ("_bz2", "bzip2 C 扩展 (性能)", True),
    ("_lzma", "LZMA C 扩展 (性能)", True),
    ("zstandard", "Zstandard 压缩 (可选)", False)
]

missing_critical = []
for name, desc, required in modules:
    if not check_module(name, desc, required) and required:
        missing_critical.append(name)

if missing_critical:
    print("\n警告: 缺失关键压缩模块支持!")
    print("受影响模块: " + ", ".join(missing_critical))

    print("\n解决方案:")
    print("1. 安装系统依赖:")
    print("   Ubuntu/Debian: sudo apt install zlib1g-dev libbz2-dev liblzma-dev")
    print("   CentOS/RHEL:   sudo yum install zlib-devel bzip2-devel xz-devel")

    print("\n2. 重新编译 Python 并包含这些功能:")
    print("   ./configure --with-zlib --with-bz2 --with-lzma")
    print("   make -j$(nproc) && sudo make altinstall")

    print("\n3. 或使用完整版 Python 发行版:")
    print("   Ubuntu/Debian: sudo apt install python3-full")
    print("   Windows: 使用官方 Python 安装程序")

    sys.exit(1)
else:
    print("\n所有核心压缩模块均可用!")
    sys.exit(0)