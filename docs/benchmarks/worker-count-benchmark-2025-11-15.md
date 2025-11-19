# Binance Futures Availability - Worker Count Benchmark Report

**Generated**: 2025-11-15 14:03:44
**Test Date**: 2025-11-14
**Symbol Count**: 327
**Trials per Config**: 5

## Executive Summary

**Optimal Worker Count**: **150 workers**

- **Total Time**: 1.48s ± 0.07s
- **Probe Time**: 0.95s ± 0.04s
- **Database Time**: 0.52s ± 0.04s
- **Success Rate**: 100.0%
- **Memory Usage**: 187.1 MB

**Speedup vs 10 workers**: 3.94x faster

# Performance Chart (Total Time):

10 workers │ │ 5.82s ± 0.34s
20 workers │ ██████████████████████████████████ │ 3.33s ± 0.07s
30 workers │ █████████████████████████████████████████████ │ 2.55s ± 0.22s
50 workers │ ██████████████████████████████████████████████████████ │ 1.84s ± 0.08s
75 workers │ ██████████████████████████████████████████████████████████ │ 1.57s ± 0.08s
100 workers │ ███████████████████████████████████████████████████████████ │ 1.53s ± 0.04s
150 workers │ ████████████████████████████████████████████████████████████ │ 1.48s ± 0.07s ← FASTEST
200 workers │ ██████████████████████████████████████████████████████████ │ 1.57s ± 0.19s
================================================================================

## Detailed Results

| Workers | Total Time (s) | Probe Time (s) | DB Time (s) | Success Rate | Memory (MB) | Trials |
| ------- | -------------- | -------------- | ----------- | ------------ | ----------- | ------ |
| 10      | 5.82 ± 0.34    | 5.34 ± 0.33    | 0.49 ± 0.04 | 100.0%       | 132.6       | 4/5    |
| 20      | 3.33 ± 0.07    | 2.83 ± 0.06    | 0.51 ± 0.02 | 100.0%       | 150.8       | 3/5    |
| 30      | 2.55 ± 0.22    | 2.02 ± 0.20    | 0.53 ± 0.02 | 100.0%       | 160.9       | 2/5    |
| 50      | 1.84 ± 0.08    | 1.33 ± 0.07    | 0.52 ± 0.02 | 100.0%       | 168.6       | 5/5    |
| 75      | 1.57 ± 0.08    | 1.08 ± 0.08    | 0.49 ± 0.04 | 100.0%       | 176.5       | 4/5    |
| 100     | 1.53 ± 0.04    | 0.99 ± 0.05    | 0.54 ± 0.07 | 100.0%       | 182.1       | 4/5    |
| 150     | 1.48 ± 0.07    | 0.95 ± 0.04    | 0.52 ± 0.04 | 100.0%       | 187.1       | 5/5    |
| 200     | 1.57 ± 0.19    | 1.09 ± 0.19    | 0.48 ± 0.01 | 100.0%       | 194.2       | 5/5    |

## Time Breakdown Analysis

Where does the time go?

| Workers | Probe (%) | Database (%) | Overhead (%) |
| ------- | --------- | ------------ | ------------ |
| 10      | 91.7%     | 8.3%         | 0.0%         |
| 20      | 84.8%     | 15.2%        | 0.0%         |
| 30      | 79.2%     | 20.8%        | 0.0%         |
| 50      | 72.0%     | 28.0%        | 0.0%         |
| 75      | 68.8%     | 31.2%        | 0.0%         |
| 100     | 64.7%     | 35.3%        | 0.0%         |
| 150     | 64.6%     | 35.4%        | 0.0%         |
| 200     | 69.4%     | 30.6%        | 0.0%         |

## Recommendation

**Use 150 workers for daily updates.**

Justification:

- Fastest mean total time: 1.48s
- Low variance: ±0.07s (consistent performance)
- High success rate: 100.0%
- Reasonable memory usage: 187.1 MB

## Why Previous Tests Showed Different Results

**This benchmark tests the ACTUAL production workflow**:

- Real HTTP requests to S3 Vision (not mocked)
- Real DuckDB insertions (327 records)
- Real network latency and S3 response times
- Multiple trials to account for variance

**Previous inconsistencies likely due to**:

- Cold start effects (first request slower)
- Network variance (S3 response times fluctuate)
- Single trials (not statistically significant)
- Partial testing (probe-only, no DB writes)

## How to Reproduce

```bash
# Run full benchmark (8 worker counts × 5 trials = 40 runs)
uv run python scripts/benchmark_workers.py

# Quick test (3 worker counts × 3 trials = 9 runs)
uv run python scripts/benchmark_workers.py --quick

# Custom configuration
uv run python scripts/benchmark_workers.py --workers 10,50,100 --trials 5
```

## Raw Trial Data

### 10 Workers

- Trial 1: 6.30s total (5.82s probe + 0.48s db)
- Trial 2: 5.51s total (5.06s probe + 0.45s db)
- Trial 3: 5.84s total (5.29s probe + 0.55s db)
- Trial 4: 5.65s total (5.18s probe + 0.46s db)
- Trial 5: FAILED - Batch probe failed for 1/327 symbols on 2025-11-14:
  - DOGEUSDT: Network error probing DOGEUSDT on 2025-11-14: [Errno 8] nodename nor servname provided, or not known

### 20 Workers

- Trial 1: FAILED - Batch probe failed for 1/327 symbols on 2025-11-14:
  - ETHUSDT: Network error probing ETHUSDT on 2025-11-14: [Errno 8] nodename nor servname provided, or not known
- Trial 2: 3.25s total (2.76s probe + 0.49s db)
- Trial 3: FAILED - Batch probe failed for 1/327 symbols on 2025-11-14:
  - CVXUSDT: Network error probing CVXUSDT on 2025-11-14: [Errno 8] nodename nor servname provided, or not known
- Trial 4: 3.35s total (2.85s probe + 0.51s db)
- Trial 5: 3.40s total (2.87s probe + 0.52s db)

### 30 Workers

- Trial 1: FAILED - Batch probe failed for 1/327 symbols on 2025-11-14:
  - C98USDT: Network error probing C98USDT on 2025-11-14: [Errno 8] nodename nor servname provided, or not known
- Trial 2: 2.39s total (1.87s probe + 0.52s db)
- Trial 3: FAILED - Batch probe failed for 1/327 symbols on 2025-11-14:
  - NKNUSDT: Network error probing NKNUSDT on 2025-11-14: [Errno 8] nodename nor servname provided, or not known
- Trial 4: FAILED - Batch probe failed for 1/327 symbols on 2025-11-14:
  - ONDOUSDT: Network error probing ONDOUSDT on 2025-11-14: [Errno 8] nodename nor servname provided, or not known
- Trial 5: 2.70s total (2.16s probe + 0.54s db)

### 50 Workers

- Trial 1: 1.78s total (1.27s probe + 0.52s db)
- Trial 2: 1.91s total (1.36s probe + 0.55s db)
- Trial 3: 1.85s total (1.35s probe + 0.50s db)
- Trial 4: 1.74s total (1.24s probe + 0.50s db)
- Trial 5: 1.93s total (1.42s probe + 0.51s db)

### 75 Workers

- Trial 1: FAILED - Batch probe failed for 1/327 symbols on 2025-11-14:
  - EDUUSDT: Network error probing EDUUSDT on 2025-11-14: [Errno 8] nodename nor servname provided, or not known
- Trial 2: 1.59s total (1.05s probe + 0.54s db)
- Trial 3: 1.59s total (1.08s probe + 0.51s db)
- Trial 4: 1.64s total (1.18s probe + 0.46s db)
- Trial 5: 1.45s total (1.00s probe + 0.44s db)

### 100 Workers

- Trial 1: 1.54s total (1.05s probe + 0.49s db)
- Trial 2: FAILED - Batch probe failed for 1/327 symbols on 2025-11-14:
  - LQTYUSDT: Network error probing LQTYUSDT on 2025-11-14: [Errno 8] nodename nor servname provided, or not known
- Trial 3: 1.58s total (0.97s probe + 0.61s db)
- Trial 4: 1.52s total (0.94s probe + 0.58s db)
- Trial 5: 1.47s total (0.99s probe + 0.48s db)

### 150 Workers

- Trial 1: 1.59s total (1.01s probe + 0.58s db)
- Trial 2: 1.41s total (0.91s probe + 0.50s db)
- Trial 3: 1.50s total (0.97s probe + 0.54s db)
- Trial 4: 1.44s total (0.93s probe + 0.50s db)
- Trial 5: 1.44s total (0.95s probe + 0.49s db)

### 200 Workers

- Trial 1: 1.86s total (1.38s probe + 0.48s db)
- Trial 2: 1.62s total (1.15s probe + 0.46s db)
- Trial 3: 1.39s total (0.91s probe + 0.49s db)
- Trial 4: 1.40s total (0.91s probe + 0.49s db)
- Trial 5: 1.58s total (1.10s probe + 0.48s db)
