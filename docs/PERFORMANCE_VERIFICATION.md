# Browser performance verification

Final measured gate: **PASS**, 2026-11-03T10:38:38.599031+00:00. All 32 templates and ten staff variants were measured five times at concurrency one and five: **420 observations, every load below 2,000 ms**.

## Measured environment and boundary

- Intel Core i7-14650HX, 16 cores / 24 logical processors; 16,868,630,528 bytes reported physical memory.
- Windows 11 Home Single Language 10.0.26300; native PostgreSQL 18; Python 3.14.10; Node.js 26.12.1; Next.js 15.5.28.
- Chrome 156.0.8078.80, headless, 1440×1000; no CPU/network throttling. Warm production servers/database caches, fresh browser context/cache for every observation.
- Benchmark frontend build `mD2vhGRAnHjCYxDTmLLIZ`; application-source SHA-256 at measurement `6b11d573ca0511c883a032a475f3b2bc75f118ab5b4644d5a8f58e4ee5ca3952`. Source remained unchanged during the run.
- Isolated brightloop_benchmark schema: 5,000 subscriptions, 50,000 invoices, 100,000 payments and 500 customers. API 8001 / frontend 3001 form the measured stack; the main application was idle. No competing build, test suite or profiling workload ran during measurement.
- All four intervals and active/closed/paused records are present. Current active count is 3,500; persisted receipts INR 34,500,000.00 and outstanding INR 24,500,000.00 reconcile before timing.
- Timing covers navigation, authentication lookup, initial API data, rendered loading-state exit, persisted collection rows and two animation frames. I05 additionally requires populated customer/plan choices and an enabled save action. Login/context creation are setup, excluded from timing.
- This proves the sampled local page-load gate, not an unmeasured deployment or every future mutation/network condition.

## Aggregate observations

| Concurrency | Samples | p50 ms | p95 ms | Max ms | Result |
|---:|---:|---:|---:|---:|---|
| 1 | 210 | 185.25 | 462.23 | 545.13 | PASS |
| 5 | 210 | 499.90 | 827.78 | 1078.33 | PASS |

## Per-template timings

| Template | Role | C1 p50 | C1 p95 | C1 max | C5 p50 | C5 p95 | C5 max |
|---|---|---:|---:|---:|---:|---:|---:|
| P01 | public | 111.03 | 248.05 | 248.05 | 319.06 | 389.03 | 389.03 |
| P02 | public | 115.59 | 122.80 | 122.80 | 330.10 | 441.38 | 441.38 |
| P03 | public | 96.74 | 114.82 | 114.82 | 356.97 | 513.08 | 513.08 |
| P04 | public | 112.24 | 128.05 | 128.05 | 376.78 | 429.25 | 429.25 |
| I01 | admin | 334.77 | 426.12 | 426.12 | 677.92 | 1078.33 | 1078.33 |
| staff:I01 | staff | 382.34 | 438.80 | 438.80 | 718.74 | 780.04 | 780.04 |
| I02 | admin | 182.40 | 204.81 | 204.81 | 412.75 | 467.52 | 467.52 |
| staff:I02 | staff | 180.50 | 184.42 | 184.42 | 518.84 | 704.51 | 704.51 |
| I03 | admin | 151.88 | 189.56 | 189.56 | 360.90 | 479.70 | 479.70 |
| staff:I03 | staff | 150.72 | 154.44 | 154.44 | 401.86 | 539.43 | 539.43 |
| I04 | admin | 437.72 | 462.23 | 462.23 | 650.97 | 742.95 | 742.95 |
| staff:I04 | staff | 436.71 | 438.10 | 438.10 | 711.36 | 866.10 | 866.10 |
| I05 | admin | 189.81 | 234.36 | 234.36 | 444.63 | 571.61 | 571.61 |
| staff:I05 | staff | 185.48 | 193.88 | 193.88 | 525.34 | 648.96 | 648.96 |
| I06 | admin | 164.02 | 176.31 | 176.31 | 338.45 | 447.72 | 447.72 |
| staff:I06 | staff | 164.90 | 191.10 | 191.10 | 483.85 | 515.12 | 515.12 |
| I07 | admin | 434.19 | 441.48 | 441.48 | 817.33 | 827.78 | 827.78 |
| staff:I07 | staff | 430.25 | 460.62 | 460.62 | 806.15 | 1053.71 | 1053.71 |
| I08 | admin | 171.49 | 181.19 | 181.19 | 351.05 | 578.34 | 578.34 |
| staff:I08 | staff | 170.81 | 172.83 | 172.83 | 387.38 | 526.67 | 526.67 |
| I09 | admin | 522.47 | 545.13 | 545.13 | 783.21 | 916.67 | 916.67 |
| staff:I09 | staff | 516.26 | 526.87 | 526.87 | 876.00 | 974.70 | 974.70 |
| I10 | admin | 130.23 | 143.41 | 143.41 | 320.13 | 368.63 | 368.63 |
| staff:I10 | staff | 123.72 | 127.99 | 127.99 | 317.90 | 390.89 | 390.89 |
| A01 | admin | 175.00 | 179.34 | 179.34 | 504.05 | 579.63 | 579.63 |
| A02 | admin | 190.58 | 201.17 | 201.17 | 544.44 | 563.68 | 563.68 |
| A03 | admin | 353.72 | 370.94 | 370.94 | 550.92 | 573.94 | 573.94 |
| A04 | admin | 175.80 | 184.61 | 184.61 | 458.61 | 538.58 | 538.58 |
| A05 | admin | 395.74 | 400.17 | 400.17 | 580.66 | 604.19 | 604.19 |
| A06 | admin | 183.71 | 190.00 | 190.00 | 433.27 | 491.03 | 491.03 |
| A07 | admin | 206.91 | 208.35 | 208.35 | 569.33 | 589.46 | 589.46 |
| A08 | admin | 376.36 | 379.25 | 379.25 | 591.71 | 746.19 | 746.19 |
| A09 | admin | 396.06 | 397.74 | 397.74 | 533.13 | 639.77 | 639.77 |
| A10 | admin | 295.91 | 312.27 | 312.27 | 638.83 | 687.72 | 687.72 |
| A11 | admin | 159.60 | 183.93 | 183.93 | 393.10 | 439.56 | 439.56 |
| C01 | customer | 177.75 | 188.38 | 188.38 | 433.58 | 595.73 | 595.73 |
| C02 | customer | 424.34 | 431.88 | 431.88 | 658.44 | 686.05 | 686.05 |
| C03 | customer | 172.18 | 414.89 | 414.89 | 414.24 | 456.76 | 456.76 |
| C04 | customer | 427.48 | 450.04 | 450.04 | 704.34 | 763.17 | 763.17 |
| C05 | customer | 153.12 | 157.89 | 157.89 | 313.94 | 374.15 | 374.15 |
| C06 | customer | 424.80 | 427.76 | 427.76 | 667.07 | 703.30 | 703.30 |
| C07 | customer | 151.98 | 154.86 | 154.86 | 306.41 | 337.69 | 337.69 |

## Warm browser-cache matrix

A separate complete warm-client run passed at 2026-11-03T10:57:52.910461+00:00, with the same application-source fingerprint and build. Each observation first completes a navigation and waits for network idle, then times a new full navigation in that context. Assets can be cached; no-store API data and rendered readiness are still checked. Servers remain warm in both matrices. Cold server boot and an emptied PostgreSQL buffer cache are not included.

| Concurrency | Samples | p50 ms | p95 ms | Max ms | Result |
|---:|---:|---:|---:|---:|---|
| 1 | 210 | 96.32 | 393.39 | 511.53 | PASS |
| 5 | 210 | 182.96 | 500.67 | 567.54 | PASS |

Together the cold-client and warm-client matrices cover **840 observations**, all below two seconds. Warm raw observations and per-template summaries are in ignored test-results/browser-benchmark-warm.json.

```powershell
backend/.venv/Scripts/python.exe -u scripts/benchmark_pages.py --client-cache warm --repeats 5 --concurrency 1 5 --output browser-benchmark-warm.json
```

## Retained failures and substantive changes

The earlier release attempt (`browser-benchmark-release.json`, build qaoIGaUQFReiuAhEpbORu) failed one I05 admin sample at concurrency five: 2,036.15 ms, median 1,914.25 ms. The artifact is retained. The editor fetched five collections and debounced even its empty initial search. It now loads customers/plans immediately, requests templates/discounts after plan selection, and requests products when lines/search need them. Fixed-identity editors avoid customer-directory queries. Full quotation/revision/request, lifecycle and beyond-first-100 template/product/discount workflows passed after the change.
The focused I05 diagnostic measured 20 loads, maximum 555.67 ms, and is explicitly labeled a subset. The subsequent complete run passed 420 observations, maximum 1,018.36 ms. After the common Origin/CSRF guard was strengthened, the final complete run above passed again, maximum 1,078.33 ms. Earlier SQL summary/recent-invoice query tuning and removal of broad navigation prefetch remain in place.
Artifacts are ignored under test-results/: browser-benchmark-initial.json, browser-benchmark-release.json, browser-benchmark-i05.json, browser-benchmark-final.json and browser-benchmark-guarded.json. The initially retained older diagnostic exceeded two seconds as well; no failed run is counted as a pass.

## Reproduce

Follow OPERATIONS.md and the benchmark scripts to seed/reuse the guarded schema. Keep the normal app data separate and run measurements without concurrent workloads. Use the same local hardware/browser/topology when comparing results.

```powershell
backend/.venv/Scripts/python.exe scripts/seed_benchmark.py
# Start scripts/run_benchmark_api.py, and build/start the frontend with:
# BRIGHTLOOP_BUILD_DIR=.next-benchmark, NEXT_PUBLIC_API_BASE_URL=http://localhost:8001/api/v1
backend/.venv/Scripts/python.exe -u scripts/benchmark_pages.py --repeats 5 --concurrency 1 5 --output browser-benchmark-guarded.json
```

The benchmark server requires the isolated search_path. Seed creation refuses a nonempty unmarked schema, reuses a completed seed and never deletes application records. The committed report contains synthetic measurements only; private connection URLs and session/reset/CSRF values stay outside Git.
