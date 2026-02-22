---
name: java-developer
description: >
  Expert Java development skill covering Spring Boot, Jakarta EE, and plain Java across versions Java 8 through Java 21+.
  Use when asked to write, generate, review, architect, or improve Java code.
  Handles: creating REST APIs, designing domain models, generating boilerplate (entities, repositories, services, controllers),
  code review for correctness/scalability/security, performance optimization, JVM tuning guidance, concurrency patterns,
  and applying architecture patterns (layered, hexagonal, DDD). Triggers on any Java programming request.
---

# Java Developer

Develop precise, scalable, production-ready Java applications. Apply the right patterns for the target Java version, framework, and architectural context.

## Approach for Every Task

1. **Identify the Java version and framework** — this determines which language features and APIs to use
2. **Identify the task type** — generation, review, architecture design, or performance
3. **Load the relevant reference** — consult references only as needed
4. **Produce output** — correct first, then clean, then performant

## Reference Files

Load these when relevant — do not load all at once:

- **`references/java-features.md`** — Which Java APIs and language features to use per version (Java 8 → 21). Load when the target Java version is ambiguous or when choosing between modern vs. legacy APIs.
- **`references/architecture.md`** — Layered vs. hexagonal architecture, DDD building blocks, SOLID principles, design patterns, package structure. Load for architecture design tasks or when structuring a new module/service.
- **`references/spring-boot-patterns.md`** — Spring Boot 3.x: REST controllers, JPA data layer, security config, observability, testing slices. Load for any Spring Boot task.
- **`references/code-quality.md`** — Code review checklist, performance patterns, concurrency primitives, JVM tuning. Load for code review or performance tasks.

## Task Guidance

### Code Generation

Generate complete, working code. Follow these defaults:
- **Constructor injection** always — never field injection with `@Autowired`
- **Records** for immutable DTOs and value objects (Java 16+); POJOs for Java 8
- **`Optional`** at public method boundaries — never return or accept raw `null`
- **Validation** on all controller inputs using Bean Validation (`@Valid`, `@NotNull`, etc.)
- **Transactions** declared at the service layer; read-only by default, override for writes
- **Lazy loading** for JPA collections; use `JOIN FETCH` or `@EntityGraph` explicitly
- Return **DTOs/records** from controllers — never expose JPA entities directly
- Use **`ProblemDetail`** (RFC 7807) for REST error responses in Spring Boot 3.x

### Architecture Design

When designing a new service or module:
1. Clarify the domain complexity — simple CRUD → layered; complex domain → hexagonal + DDD
2. Define the package structure (feature-based preferred)
3. Draw the dependency flow: inbound adapters → application → domain → outbound ports
4. Identify aggregates, entities, and value objects before writing any code

See `references/architecture.md` for patterns, examples, and package structure templates.

### Code Review

Evaluate code across four dimensions:
1. **Correctness** — null safety, error handling, thread safety, data integrity
2. **Design** — SRP, dependency direction, encapsulation, layer separation
3. **Security** — injection risks, secret exposure, authorization gaps
4. **Scalability** — N+1 queries, unbounded result sets, shared mutable state, blocking I/O

Use the checklist in `references/code-quality.md`. Point to specific lines, explain the risk, and suggest a concrete fix.

### Performance & JVM

When asked to optimize:
1. Identify the bottleneck category: CPU, memory, I/O, or database
2. Recommend profiling first (`jfr`, async-profiler) before making blind changes
3. Apply targeted fixes: query optimization, caching, concurrency model, GC tuning
4. For Java 21+: consider virtual threads for I/O-bound workloads

See `references/code-quality.md` for concurrency patterns, JVM flags, and GC selection.

## Version Compatibility Rules

- **Java 8**: No records, text blocks, `var`, sealed classes, pattern matching, or `HttpClient`. Use POJOs, `Optional`, streams, lambdas, `CompletableFuture`.
- **Java 11**: Add `String::strip`, `Files.readString`, `HttpClient`.
- **Java 17**: Use records, text blocks, sealed classes, pattern matching `instanceof`.
- **Java 21**: Use virtual threads, pattern matching in `switch`, record patterns, sequenced collections.

When the target version is unspecified, write for **Java 17** (widest LTS compatibility with Spring Boot 3.x).
