# Tar Compression Benchmark Suite

## Overview

The benchmark suite provides comprehensive testing for the async tar compressor, allowing you to test:

- **Different compression algorithms**: GZIP, BZIP2, XZ/LZMA, LZ4
- **Multiple compression levels**: Each algorithm supports different compression levels
- **Various data types**: Random text, repetitive text, JSON-like data, log files, random binary, sparse binary
- **Different file sizes**: From 1KB to 10MB (customizable)
- **Multiple file counts**: Test with single files or multiple files
- **Statistical analysis**: Multiple iterations with averaged results

## Installation

Ensure you have the required dependencies:

```bash
# Basic requirements (already in Python standard library)
# - gzip, bz2, lzma (for GZIP, BZIP2, XZ compression)

# Optional for LZ4 compression
pip install lz4

# Required for UI
pip install rich
```

## Usage

### Standalone Benchmark

Run the benchmark directly:

```bash
python benchmark.py
```

### Integration with Main Demo

Run from the updated main demo program:

```bash
python main_updated.py
# Then select option 9 for "Comprehensive Benchmark Suite"
```

## Interactive Configuration

The benchmark suite provides an interactive configuration where you can:

1. **Select Compression Algorithms**
   - Choose which algorithms to test
   - Only available algorithms are selectable

2. **Configure Compression Levels**
   - Use default levels or specify custom levels
   - Default levels:
     - GZIP: 1 (fastest), 5 (balanced), 9 (best)
     - BZIP2: 1 (fastest), 5 (balanced), 9 (best)
     - XZ: 0 (fastest), 3, 6, 9 (best)
     - LZ4: 1 (fastest), 3, 9 (best)

3. **Select Data Types**
   - `random_text`: ASCII printable characters
   - `repetitive_text`: Highly compressible repeated patterns
   - `json_like`: Structured JSON-format data
   - `log_like`: Log file format with timestamps
   - `binary_random`: Completely random binary data
   - `binary_sparse`: Binary data with lots of zeros

4. **Choose File Sizes**
   - Default: 1KB, 10KB, 100KB, 1MB, 10MB
   - Or specify custom sizes

5. **Set File Counts**
   - Test with different numbers of files
   - Default: 1, 10, 50 files

6. **Configure Iterations**
   - Multiple test runs for statistical accuracy
   - Results are averaged across iterations

## Output

The benchmark provides:

1. **Detailed Results Table**
   - Organized by data type
   - Shows compression ratio, speed, and time

2. **Summary Statistics**
   - Best compression ratio by data type
   - Fastest compression by data type
   - Recommendations for different use cases

3. **JSON Export**
   - Save results to file for later analysis
   - Includes all raw data and timestamps

## Example Output

```
Results for random_text data:
┏━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Algorithm ┃ Level ┃ File Size ┃ File Count ┃ Compression % ┃ Speed (MB/s) ┃ Time (s) ┃
┡━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━┩
│ GZIP      │ 1     │ 1MB       │ 1          │ 15.2%         │ 125.3        │ 0.008   │
│ GZIP      │ 5     │ 1MB       │ 1          │ 18.7%         │ 45.2         │ 0.022   │
│ GZIP      │ 9     │ 1MB       │ 1          │ 19.1%         │ 12.8         │ 0.078   │
└───────────┴───────┴───────────┴────────────┴───────────────┴──────────────┴─────────┘
```

## Performance Tips

1. **For speed**: Use LZ4 with low compression levels
2. **For compression ratio**: Use XZ with high compression levels
3. **For balance**: Use GZIP with level 5-6
4. **For text data**: GZIP and BZIP2 perform well
5. **For binary data**: LZ4 is often the best choice

## Interpreting Results

- **Compression %**: Higher is better (more space saved)
- **Speed (MB/s)**: Higher is better (faster compression)
- **Time (s)**: Lower is better (less time taken)

The benchmark helps you choose the right algorithm and compression level for your specific use case based on your priorities (speed vs. compression ratio).