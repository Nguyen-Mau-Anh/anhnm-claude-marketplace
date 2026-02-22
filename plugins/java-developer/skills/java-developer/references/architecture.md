# Java Architecture Patterns

Reference for structuring Java applications across Spring Boot, Jakarta EE, and plain Java.

## Table of Contents
1. [Layered Architecture](#layered-architecture)
2. [Hexagonal Architecture](#hexagonal-architecture)
3. [Domain-Driven Design (DDD)](#domain-driven-design-ddd)
4. [SOLID Principles](#solid-principles)
5. [Common Design Patterns](#common-design-patterns)
6. [Package Structure](#package-structure)

---

## Layered Architecture

Standard three-tier layering. Use when the domain is simple or a full hexagonal setup is overkill.

```
Presentation Layer   → REST controllers, GraphQL resolvers, CLI
Service Layer        → Business logic, orchestration, transactions
Repository Layer     → Data access (JPA, JDBC, external APIs)
Domain Layer         → Entities, value objects, domain events
```

**Rules:**
- Each layer depends only on the layer directly below it
- Domain objects must not depend on persistence or HTTP concerns
- Services orchestrate repositories; controllers orchestrate services
- Never call a repository from a controller

---

## Hexagonal Architecture

Also called Ports & Adapters. Use for complex domains, high testability requirements, or when the infrastructure is likely to change.

```
Core (Domain)
├── Domain model (entities, aggregates, value objects)
├── Domain services
└── Ports (interfaces the domain exposes or depends on)
    ├── Inbound ports  → Use cases / application service interfaces
    └── Outbound ports → Repository, email, event bus interfaces

Adapters (Infrastructure)
├── Inbound adapters  → REST controllers, message consumers, CLI
└── Outbound adapters → JPA repos, SMTP, Kafka producers, HTTP clients
```

**Key rule:** The domain core has zero dependencies on frameworks. It only imports JDK types and its own types.

**Example port/adapter:**
```java
// Outbound port (in domain)
public interface UserRepository {
    Optional<User> findById(UserId id);
    void save(User user);
}

// Outbound adapter (in infrastructure)
@Repository
public class JpaUserRepository implements UserRepository {
    private final SpringDataUserRepo repo;
    // ...
}
```

---

## Domain-Driven Design (DDD)

Apply DDD when the domain is complex and central to the application.

### Building Blocks

**Entity** — Has identity that persists over time:
```java
public class Order {
    private final OrderId id;
    private OrderStatus status;
    // behavior methods, not just getters/setters
    public void confirm() { /* domain logic */ }
}
```

**Value Object** — Immutable, identified by its value:
```java
public record Money(BigDecimal amount, Currency currency) {
    public Money {
        Objects.requireNonNull(amount);
        if (amount.compareTo(BigDecimal.ZERO) < 0)
            throw new IllegalArgumentException("Negative money");
    }
    public Money add(Money other) { ... }
}
```

**Aggregate** — Cluster of entities with a single root; all changes go through the root:
```java
public class Order { // Aggregate Root
    private final List<OrderLine> lines = new ArrayList<>();
    public void addLine(Product product, int quantity) { /* enforces invariants */ }
}
```

**Domain Service** — Stateless logic that doesn't belong to any entity:
```java
public class PricingService {
    public Money calculateTotal(Order order, PricingPolicy policy) { ... }
}
```

**Domain Event** — Something that happened in the domain:
```java
public record OrderPlaced(OrderId orderId, Instant occurredAt) {}
```

**Repository** — Abstraction over persistence, returns aggregates only:
```java
public interface OrderRepository {
    Optional<Order> findById(OrderId id);
    void save(Order order);
}
```

### Rules
- Aggregates reference other aggregates by ID only, never by object reference
- Invariants are enforced inside the aggregate root
- Application services load aggregates, call domain methods, save, and publish events

---

## SOLID Principles

| Principle | Java Application |
|-----------|-----------------|
| **S**ingle Responsibility | One class = one reason to change. Split `UserService` into `UserAuthService` + `UserProfileService` if they change independently |
| **O**pen/Closed | Extend via interfaces and composition, not by modifying existing classes. Use Strategy pattern for varying algorithms |
| **L**iskov Substitution | Subtypes must be substitutable for their base type. Avoid overriding methods that weaken preconditions or strengthen postconditions |
| **I**nterface Segregation | Prefer many small, focused interfaces over one fat interface. Clients should not depend on methods they don't use |
| **D**ependency Inversion | Depend on abstractions (interfaces), not concrete implementations. Inject dependencies via constructor |

**Constructor injection (always prefer over field injection):**
```java
@Service
public class OrderService {
    private final OrderRepository orders;
    private final PaymentGateway payments;

    public OrderService(OrderRepository orders, PaymentGateway payments) {
        this.orders = orders;
        this.payments = payments;
    }
}
```

---

## Common Design Patterns

### Strategy
Swap algorithms at runtime:
```java
public interface SortStrategy { void sort(List<Integer> list); }
public class QuickSort implements SortStrategy { ... }
public class MergeSort implements SortStrategy { ... }
```

### Factory / Factory Method
Encapsulate object creation:
```java
public class NotificationFactory {
    public Notification create(NotificationType type) {
        return switch (type) {
            case EMAIL -> new EmailNotification();
            case SMS   -> new SmsNotification();
        };
    }
}
```

### Builder
Construct complex objects without telescoping constructors:
```java
User user = User.builder()
    .name("Alice")
    .email("alice@example.com")
    .role(Role.ADMIN)
    .build();
```

### Template Method
Define a skeleton algorithm; subclasses fill in steps:
```java
public abstract class DataExporter {
    public final void export() { fetchData(); transform(); write(); }
    protected abstract List<Record> fetchData();
    protected abstract List<Row> transform();
    protected abstract void write();
}
```

### Observer / Event-Driven
Decouple producers from consumers:
```java
// Spring example
applicationEventPublisher.publishEvent(new OrderPlaced(order.id()));

@EventListener
public void on(OrderPlaced event) { /* send confirmation email */ }
```

### Decorator
Add behavior without subclassing:
```java
public class LoggingRepository implements UserRepository {
    private final UserRepository delegate;
    public Optional<User> findById(UserId id) {
        log.debug("Finding user {}", id);
        return delegate.findById(id);
    }
}
```

---

## Package Structure

### Feature-based (preferred for larger projects)
```
com.example.app/
├── order/
│   ├── Order.java
│   ├── OrderRepository.java
│   ├── OrderService.java
│   └── OrderController.java
├── user/
│   ├── User.java
│   └── ...
└── shared/
    ├── Money.java
    └── DomainEvent.java
```

### Layer-based (acceptable for small projects)
```
com.example.app/
├── controller/
├── service/
├── repository/
└── domain/
```

**Rules:**
- Feature packages own their slice end-to-end
- Shared/common types live in a `shared` or `common` package
- Never create circular dependencies between feature packages
- Use package-private visibility to enforce module boundaries within a feature
