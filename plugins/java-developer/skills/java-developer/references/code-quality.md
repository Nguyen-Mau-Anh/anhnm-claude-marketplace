# Code Quality: Review Checklist & Performance Guide

## Table of Contents
1. [Code Review Checklist](#code-review-checklist)
2. [Performance Patterns](#performance-patterns)
3. [Concurrency](#concurrency)
4. [JVM Tuning Guidance](#jvm-tuning-guidance)

---

## Code Review Checklist

### Correctness
- [ ] Null safety: no unchecked `null` returned or accepted; `Optional` used at boundaries
- [ ] Validation at system entry points (controller inputs, external API responses)
- [ ] Error cases handled explicitly; no silent swallowing of exceptions
- [ ] Checked exceptions not used for flow control
- [ ] Collections not mutated while iterating
- [ ] Thread-safety correct for shared mutable state

### Design
- [ ] Single Responsibility: classes and methods have one clear purpose
- [ ] Dependency injection used (constructor preferred); no `new` for services
- [ ] No circular dependencies between packages/modules
- [ ] Interfaces used at module boundaries; concrete types used internally
- [ ] No business logic in controllers; no data access in services
- [ ] Domain model encapsulates its invariants

### Maintainability
- [ ] Methods ≤ 20 lines; classes ≤ 300 lines as a general heuristic
- [ ] No magic numbers/strings — extract to constants or config
- [ ] Variable and method names are self-explanatory
- [ ] No dead code, commented-out code, or TODO without a tracking ticket
- [ ] No duplicated logic — extract shared code to utility or base class

### Security
- [ ] No secrets in code or logs — use environment variables / Vault
- [ ] User-controlled input is never used in SQL/shell commands without parameterization
- [ ] Sensitive fields (passwords, tokens) excluded from `toString()`, logs, and serialization
- [ ] Authentication and authorization enforced at the service boundary
- [ ] File paths from user input validated and sandboxed

### Scalability
- [ ] No blocking I/O on virtual/reactive threads without proper handling
- [ ] Database queries use pagination for unbounded result sets
- [ ] No N+1 query patterns (check eager loading, loop fetches)
- [ ] Caching applied where appropriate; cache invalidation is correct
- [ ] Stateless services — no instance-level mutable state shared across requests

---

## Performance Patterns

### String Handling
```java
// Bad: creates many intermediate strings
String result = "";
for (String s : list) result += s;

// Good
String result = String.join(", ", list);
// Or for complex cases:
StringBuilder sb = new StringBuilder();
for (String s : list) sb.append(s).append(", ");
```

### Collections
```java
// Pre-size when count is known
List<Item> items = new ArrayList<>(expectedSize);
Map<Key, Value> map = new HashMap<>((int)(expectedSize / 0.75) + 1);

// Use the right data structure
// LinkedList: almost never; ArrayList beats it for most use cases
// TreeMap vs HashMap: TreeMap only when sorted order is needed
// ArrayDeque: prefer over Stack/LinkedList for queue/stack operations
```

### Stream Performance
```java
// Parallel streams: only when data is large (>10k elements) and processing is CPU-bound
list.parallelStream()
    .filter(...)
    .map(...)
    .collect(toList());

// Avoid parallel streams for I/O, ordered operations, or small collections
// For collectors, Collectors.toList() vs Stream.toList() — toList() (Java 16+) is unmodifiable and slightly faster
```

### Database Query Optimization
```java
// Paginate large result sets
Page<Order> page = orderRepository.findAll(PageRequest.of(pageNum, 50, Sort.by("createdAt").descending()));

// Batch inserts
@Modifying
@Query("INSERT INTO order_line (order_id, product_id, qty) VALUES (:orderId, :productId, :qty)")
void batchInsertLine(...);

// Or use JdbcTemplate for bulk operations:
jdbcTemplate.batchUpdate(sql, batchArgs);

// Use projections for read-heavy queries — avoids loading unnecessary columns
```

### Caching (Spring Cache)
```java
@Cacheable(value = "products", key = "#id", unless = "#result == null")
public Product findProduct(UUID id) { ... }

@CacheEvict(value = "products", key = "#product.id")
public Product updateProduct(Product product) { ... }
```

Choose backing store: Caffeine for in-process, Redis for distributed.

---

## Concurrency

### Thread-Safe Patterns

**Immutability** — safest option:
```java
public record Config(String host, int port) {} // inherently thread-safe
```

**`volatile`** — visibility guarantee, no atomicity:
```java
private volatile boolean running = true;
```

**`AtomicXxx`** — atomic read-modify-write:
```java
private final AtomicInteger counter = new AtomicInteger(0);
counter.incrementAndGet();
```

**`synchronized` / `ReentrantLock`** — mutual exclusion:
```java
private final ReentrantLock lock = new ReentrantLock();
lock.lock();
try { /* critical section */ } finally { lock.unlock(); }
```

**`ConcurrentHashMap`** — thread-safe map; prefer over `Collections.synchronizedMap()`:
```java
private final ConcurrentHashMap<String, Value> cache = new ConcurrentHashMap<>();
cache.computeIfAbsent(key, k -> expensiveCompute(k));
```

### ExecutorService Usage
```java
// Bounded thread pool for CPU-bound work
ExecutorService cpu = Executors.newFixedThreadPool(Runtime.getRuntime().availableProcessors());

// Virtual threads for I/O-bound work (Java 21+)
ExecutorService io = Executors.newVirtualThreadPerTaskExecutor();

// Always shut down
try (var exec = Executors.newVirtualThreadPerTaskExecutor()) {
    var future = exec.submit(this::fetchData);
    return future.get(5, TimeUnit.SECONDS);
}
```

### CompletableFuture Best Practices
```java
CompletableFuture.supplyAsync(this::fetchUser, executor)
    .thenApply(this::transform)
    .exceptionally(ex -> { log.error("Failed", ex); return fallback(); })
    .orTimeout(3, TimeUnit.SECONDS);
```

- Always specify a custom executor; default `ForkJoinPool.commonPool()` is shared and bounded
- Never block inside async pipelines (`get()`, `join()`) — use `thenApply` / `thenCompose`
- Compose with `thenCompose` for async-returning functions, `thenApply` for synchronous transforms

---

## JVM Tuning Guidance

### Heap Sizing
```bash
# For containers: use percentage-based sizing
-XX:InitialRAMPercentage=50 -XX:MaxRAMPercentage=75

# For bare metal:
-Xms2g -Xmx4g
```

### GC Selection
| Workload | Recommended GC | Flag |
|---|---|---|
| Low latency / interactive | ZGC (Java 15+) | `-XX:+UseZGC` |
| High throughput / batch | G1GC (default in Java 9+) | `-XX:+UseG1GC` |
| Java 21 + low pause | Generational ZGC | `-XX:+UseZGC -XX:+ZGenerational` |

### Virtual Thread Tuning (Java 21)
```bash
# Limit carrier threads (defaults to CPU count — usually fine)
-Djdk.virtualThreadScheduler.parallelism=8
# Avoid pinning: ensure synchronized blocks don't hold carrier threads
```

### Useful JVM Flags for Production
```bash
-XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/tmp/heapdump.hprof
-XX:+ExitOnOutOfMemoryError          # Fail fast in containers
-Xlog:gc*:file=/var/log/gc.log       # GC logging (Java 9+)
-XX:+UseStringDeduplication          # G1GC: dedup identical String objects
```

### Profiling Tools
- **JFR (Java Flight Recorder)**: `-XX:StartFlightRecording=duration=60s,filename=recording.jfr` — minimal overhead, safe in production
- **Async-profiler**: Best for CPU/allocation flame graphs; attach to running JVM
- **VisualVM / JConsole**: GUI for heap/thread inspection in development
- **Heap analysis**: `jmap -dump:format=b,file=heap.hprof <pid>` → open with Eclipse Memory Analyzer (MAT)
