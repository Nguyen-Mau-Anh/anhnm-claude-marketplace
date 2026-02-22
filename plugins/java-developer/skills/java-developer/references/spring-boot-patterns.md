# Spring Boot Patterns

Reference for Spring Boot 3.x application development (Spring Framework 6, Jakarta EE namespace).

## Table of Contents
1. [Project Setup](#project-setup)
2. [REST API Design](#rest-api-design)
3. [Data Layer](#data-layer)
4. [Security](#security)
5. [Observability](#observability)
6. [Configuration](#configuration)
7. [Testing](#testing)
8. [Common Anti-Patterns](#common-anti-patterns)

---

## Project Setup

**Maven starter (Spring Boot 3.x, Java 17+):**
```xml
<parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.2.x</version>
</parent>
<dependencies>
    <dependency>spring-boot-starter-web</dependency>
    <dependency>spring-boot-starter-data-jpa</dependency>
    <dependency>spring-boot-starter-validation</dependency>
    <dependency>spring-boot-starter-actuator</dependency>
    <dependency>spring-boot-starter-security</dependency> <!-- if needed -->
</dependencies>
```

**Gradle (Kotlin DSL):**
```kotlin
plugins { id("org.springframework.boot") version "3.2.x" }
dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("org.springframework.boot:spring-boot-starter-data-jpa")
}
```

---

## REST API Design

### Controller Layer
```java
@RestController
@RequestMapping("/api/v1/orders")
@RequiredArgsConstructor
public class OrderController {

    private final OrderService orderService;

    @GetMapping("/{id}")
    public ResponseEntity<OrderResponse> getOrder(@PathVariable UUID id) {
        return orderService.findById(id)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public OrderResponse createOrder(@RequestBody @Valid CreateOrderRequest request) {
        return orderService.create(request);
    }
}
```

### Request/Response DTOs — Use Records (Java 16+)
```java
public record CreateOrderRequest(
    @NotNull UUID customerId,
    @NotEmpty List<@Valid OrderLineRequest> lines
) {}

public record OrderLineRequest(
    @NotNull UUID productId,
    @Positive int quantity
) {}

public record OrderResponse(UUID id, OrderStatus status, List<OrderLineResponse> lines) {}
```

### Global Exception Handling
```java
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(EntityNotFoundException.class)
    public ProblemDetail handleNotFound(EntityNotFoundException ex) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, ex.getMessage());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ProblemDetail handleValidation(MethodArgumentNotValidException ex) {
        var detail = ProblemDetail.forStatus(HttpStatus.BAD_REQUEST);
        detail.setProperty("errors", ex.getBindingResult().getFieldErrors()
            .stream().map(e -> e.getField() + ": " + e.getDefaultMessage()).toList());
        return detail;
    }
}
```

Use `ProblemDetail` (RFC 7807) — built into Spring 6. Avoid returning raw strings or custom error wrappers.

---

## Data Layer

### JPA Entity
```java
@Entity
@Table(name = "orders")
public class OrderEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(nullable = false)
    private UUID customerId;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private OrderStatus status;

    @OneToMany(mappedBy = "order", cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.LAZY)
    private List<OrderLineEntity> lines = new ArrayList<>();

    @CreatedDate
    @Column(updatable = false)
    private Instant createdAt;

    @LastModifiedDate
    private Instant updatedAt;
}
```

### Spring Data Repository
```java
public interface OrderRepository extends JpaRepository<OrderEntity, UUID> {

    List<OrderEntity> findByCustomerIdAndStatus(UUID customerId, OrderStatus status);

    // Use @Query for complex queries; prefer JPQL over native SQL
    @Query("SELECT o FROM OrderEntity o JOIN FETCH o.lines WHERE o.id = :id")
    Optional<OrderEntity> findByIdWithLines(@Param("id") UUID id);

    // Projections for read-heavy queries
    List<OrderSummary> findByCustomerId(UUID customerId);
}
```

### Projections for read optimization
```java
public interface OrderSummary {
    UUID getId();
    OrderStatus getStatus();
    Instant getCreatedAt();
}
```

### N+1 Prevention
- Use `JOIN FETCH` for required associations
- Use `@EntityGraph` for specific use cases
- **Always use `LAZY` fetch for collections** — never `EAGER`
- Use projections or DTOs directly from queries for list endpoints

### Transactions
```java
@Service
@Transactional(readOnly = true) // default for the class
public class OrderService {

    @Transactional // overrides for writes
    public OrderResponse create(CreateOrderRequest request) { ... }

    public Optional<OrderResponse> findById(UUID id) { ... } // readOnly inherited
}
```

---

## Security

### Spring Security 6 Configuration
```java
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            .csrf(AbstractHttpConfigurer::disable) // disable for stateless APIs
            .sessionManagement(s -> s.sessionCreationPolicy(STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/actuator/health", "/api/auth/**").permitAll()
                .requestMatchers(HttpMethod.GET, "/api/v1/**").hasRole("USER")
                .anyRequest().hasRole("ADMIN")
            )
            .oauth2ResourceServer(o -> o.jwt(Customizer.withDefaults()))
            .build();
    }
}
```

### Method-Level Security
```java
@PreAuthorize("hasRole('ADMIN') or #userId == authentication.principal.id")
public UserProfile getProfile(UUID userId) { ... }
```

---

## Observability

### Actuator Endpoints
```yaml
# application.yml
management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus
  endpoint:
    health:
      show-details: when-authorized
```

### Structured Logging with SLF4J + MDC
```java
private static final Logger log = LoggerFactory.getLogger(OrderService.class);

public OrderResponse create(CreateOrderRequest request) {
    MDC.put("customerId", request.customerId().toString());
    try {
        log.info("Creating order");
        // ...
    } finally {
        MDC.clear();
    }
}
```

### Custom Metrics (Micrometer)
```java
@Service
public class OrderService {
    private final Counter ordersCreated;

    public OrderService(MeterRegistry registry) {
        this.ordersCreated = Counter.builder("orders.created")
            .description("Total orders created")
            .register(registry);
    }

    public OrderResponse create(...) {
        ordersCreated.increment();
        // ...
    }
}
```

---

## Configuration

### Type-Safe Properties
```java
@ConfigurationProperties(prefix = "app.payment")
public record PaymentProperties(
    String gatewayUrl,
    Duration timeout,
    int maxRetries
) {}
```

```yaml
app:
  payment:
    gateway-url: https://pay.example.com
    timeout: 5s
    max-retries: 3
```

Enable with `@EnableConfigurationProperties(PaymentProperties.class)` or `@ConfigurationPropertiesScan`.

---

## Testing

### Unit Test (plain JUnit 5 + Mockito)
```java
@ExtendWith(MockitoExtension.class)
class OrderServiceTest {

    @Mock OrderRepository orderRepository;
    @InjectMocks OrderService orderService;

    @Test
    void createOrder_shouldSaveAndReturnResponse() { ... }
}
```

### Integration Test (Spring slice)
```java
@WebMvcTest(OrderController.class)
class OrderControllerTest {

    @Autowired MockMvc mockMvc;
    @MockBean OrderService orderService;

    @Test
    void getOrder_returnsOk() throws Exception {
        when(orderService.findById(any())).thenReturn(Optional.of(mockResponse()));
        mockMvc.perform(get("/api/v1/orders/{id}", UUID.randomUUID()))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.status").value("PENDING"));
    }
}
```

### Full Integration Test
```java
@SpringBootTest
@AutoConfigureMockMvc
@Testcontainers
class OrderIntegrationTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16");

    @DynamicPropertySource
    static void props(DynamicPropertyRegistry r) {
        r.add("spring.datasource.url", postgres::getJdbcUrl);
    }
}
```

---

## Common Anti-Patterns

| Anti-Pattern | Fix |
|---|---|
| Field injection (`@Autowired`) | Constructor injection |
| `EAGER` fetch on collections | `LAZY` + explicit JOIN FETCH |
| `@Transactional` on private methods | Only annotate public methods |
| Returning entities from controllers | Return DTOs / records |
| Catching and swallowing exceptions | Let `@RestControllerAdvice` handle them |
| Hardcoded config values | `@ConfigurationProperties` |
| `System.out.println` for logging | SLF4J (`log.info(...)`) |
| N+1 queries in loops | Use `JOIN FETCH` or batch loading |
| `Optional.get()` without `isPresent()` | `orElseThrow()` or `map()` |
