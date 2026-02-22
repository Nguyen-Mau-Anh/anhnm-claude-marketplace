# Java Features by Version

Reference for choosing the right Java API based on the target version.

## Table of Contents
1. [Java 8](#java-8)
2. [Java 9–10](#java-9-10)
3. [Java 11 (LTS)](#java-11-lts)
4. [Java 14–16](#java-14-16)
5. [Java 17 (LTS)](#java-17-lts)
6. [Java 21 (LTS)](#java-21-lts)
7. [Version Selection Guide](#version-selection-guide)

---

## Java 8

Core features still in widespread use:

- **Streams API**: `stream()`, `filter()`, `map()`, `collect()`, `reduce()`
- **Optional**: Avoid null; use `Optional.ofNullable()`, `map()`, `orElse()`, `orElseThrow()`
- **Lambda / Functional interfaces**: `Function`, `Predicate`, `Supplier`, `Consumer`, `BiFunction`
- **Method references**: `ClassName::method`, `instance::method`
- **Date/Time API**: `LocalDate`, `LocalDateTime`, `ZonedDateTime`, `Duration`, `Period` — always prefer over `Date`/`Calendar`
- **CompletableFuture**: Async pipelines; `thenApply()`, `thenCompose()`, `exceptionally()`, `allOf()`
- **Default/static interface methods**: Add behavior to interfaces without breaking existing implementations

---

## Java 9–10

- **Modules (JPMS)**: `module-info.java`; use when building library APIs or enforcing strong encapsulation
- **`List.of()`, `Set.of()`, `Map.of()`**: Immutable factory methods — prefer over `Arrays.asList()`
- **`var` (Java 10)**: Local variable type inference — use for brevity, avoid when type clarity matters

---

## Java 11 (LTS)

- **`String` additions**: `isBlank()`, `strip()`, `lines()`, `repeat()`, `stripLeading()`, `stripTrailing()`
- **`Files.readString()` / `writeString()`**: Simplified file I/O
- **`HttpClient`**: Built-in async HTTP/2 client — replaces Apache HttpClient for simple use cases
- **`Optional.isEmpty()`**: Cleaner null checks
- **`Collection.toArray(T[]::new)`**: Type-safe array conversion

---

## Java 14–16

- **Records (Java 16 stable)**: Immutable data carriers — replace DTOs/value objects with boilerplate-free syntax
  ```java
  public record Point(int x, int y) {}
  ```
- **Pattern Matching `instanceof` (Java 16 stable)**:
  ```java
  if (obj instanceof String s) { s.toUpperCase(); }
  ```
- **Text Blocks (Java 15 stable)**: Multi-line strings — ideal for SQL, JSON, HTML templates
  ```java
  String sql = """
      SELECT * FROM users
      WHERE active = true
      """;
  ```
- **Sealed classes (preview)**: Constrain class hierarchies

---

## Java 17 (LTS)

- **Sealed classes (stable)**: `sealed`, `permits` — model closed domain hierarchies, pair with pattern matching
  ```java
  public sealed interface Shape permits Circle, Rectangle {}
  ```
- **Pattern Matching `instanceof`**: Stable — use everywhere in place of casts
- **Records**: Stable — use for all immutable data carriers (DTOs, value objects, events)
- **Strong encapsulation of JDK internals**: Remove `--add-opens` workarounds where possible

---

## Java 21 (LTS)

- **Virtual Threads (Project Loom)**: Lightweight threads managed by the JVM
  ```java
  Thread.ofVirtual().start(() -> { /* blocking I/O */ });
  // Or via executor:
  ExecutorService ex = Executors.newVirtualThreadPerTaskExecutor();
  ```
  Use for high-concurrency I/O-bound workloads; avoid for CPU-bound tasks.
- **Structured Concurrency (preview)**:
  ```java
  try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
      Future<String> a = scope.fork(this::fetchA);
      Future<String> b = scope.fork(this::fetchB);
      scope.join().throwIfFailed();
  }
  ```
- **Sequenced Collections**: `SequencedCollection`, `SequencedMap` — `getFirst()`, `getLast()`, `reversed()`
- **Pattern Matching in `switch` (stable)**:
  ```java
  return switch (shape) {
      case Circle c -> Math.PI * c.radius() * c.radius();
      case Rectangle r -> r.width() * r.height();
  };
  ```
- **Record Patterns**:
  ```java
  if (obj instanceof Point(int x, int y)) { ... }
  ```
- **String Templates (preview in 21)**: Avoid in production code until stable

---

## Version Selection Guide

| Need | Minimum Version |
|------|----------------|
| Streams, Optionals, lambdas | Java 8 |
| Immutable collections | Java 9 |
| `var` keyword | Java 10 |
| Built-in HTTP client | Java 11 |
| Records, text blocks | Java 16 |
| Sealed classes, pattern matching | Java 17 |
| Virtual threads | Java 21 |

**Rules of thumb:**
- When in doubt, prefer Java 17 LTS features — widely supported by Spring Boot 3.x and Jakarta EE 10
- Only use preview features if the project pins a specific JDK version and has explicit buy-in
- Java 8 code must avoid records, text blocks, `var`, and sealed classes — use traditional POJOs and null-checks with Optional
