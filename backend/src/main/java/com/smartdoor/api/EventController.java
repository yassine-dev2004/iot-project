package com.smartdoor.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.core.io.UrlResource;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.File;
import java.io.IOException;
import java.net.MalformedURLException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
@Slf4j
@CrossOrigin(origins = "*")
public class EventController {

    private final EventRepository eventRepository;
    private final SseService sseService;
    private final ObjectMapper objectMapper;

    @Value("${smartdoor.storage.snapshots-dir:snapshots}")
    private String snapshotsDir;

    @Value("${smartdoor.retention.days:30}")
    private int retentionDays;

    // Cache for today's summary
    private String cachedSummary = "";
    private LocalDate cachedSummaryDate = null;
    private Instant lastSummaryGenerated = Instant.EPOCH;

    /**
     * Ingest event from Raspberry Pi edge device
     */
    @PostMapping(value = "/events", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> createEvent(
            @RequestHeader(value = "X-Device-Api-Key", required = false) String apiKey,
            @RequestPart("data") String dataJson,
            @RequestPart(value = "image", required = false) MultipartFile imageFile) throws IOException {

        log.info("Received event ingestion request with API key: {}", apiKey != null ? "[PROTECTED]" : "NONE");

        Map<String, Object> data = objectMapper.readValue(dataJson, Map.class);
        String eventId = (String) data.getOrDefault("id", java.util.UUID.randomUUID().toString());
        String personLabel = (String) data.getOrDefault("personLabel", "motion");
        String caption = (String) data.getOrDefault("caption", "Activity at front door");
        String deviceId = (String) data.getOrDefault("deviceId", "pi-front-door-01");
        String timestampStr = (String) data.get("timestamp");

        Instant timestamp = timestampStr != null ? Instant.parse(timestampStr) : Instant.now();

        String snapshotPath = null;
        if (imageFile != null && !imageFile.isEmpty()) {
            Path uploadPath = Paths.get(snapshotsDir);
            if (!Files.exists(uploadPath)) {
                Files.createDirectories(uploadPath);
            }
            String filename = eventId + ".jpg";
            Path filePath = uploadPath.resolve(filename);
            imageFile.transferTo(filePath.toFile());
            snapshotPath = filePath.toString();
        }

        Event event = Event.builder()
                .id(eventId)
                .timestamp(timestamp)
                .personLabel(personLabel)
                .caption(caption)
                .snapshotPath(snapshotPath)
                .deviceId(deviceId)
                .build();

        Event saved = eventRepository.save(event);

        // Broadcast to SSE clients (Flutter mobile app & Angular web dashboard)
        sseService.broadcastEvent(saved);

        return ResponseEntity.status(HttpStatus.CREATED).body(saved);
    }

    /**
     * Get paginated events with optional filtering
     */
    @GetMapping("/events")
    public ResponseEntity<Page<Event>> listEvents(
            @RequestParam(required = false) String person,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) Instant startDate,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) Instant endDate,
            Pageable pageable) {

        if (person != null && !person.isBlank()) {
            return ResponseEntity.ok(eventRepository.findByPersonLabelContainingIgnoreCase(person, pageable));
        }
        if (startDate != null && endDate != null) {
            return ResponseEntity.ok(eventRepository.findByTimestampBetween(startDate, endDate, pageable));
        }
        return ResponseEntity.ok(eventRepository.findAll(pageable));
    }

    /**
     * Stream real-time events via Server-Sent Events (SSE)
     */
    @GetMapping(value = "/events/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter streamEvents() {
        return sseService.createEmitter();
    }

    /**
     * Retrieve snapshot image
     */
    @GetMapping("/events/{id}/image")
    public ResponseEntity<Resource> getEventImage(@PathVariable String id) throws MalformedURLException {
        Event event = eventRepository.findById(id).orElse(null);
        if (event == null || event.getSnapshotPath() == null) {
            return ResponseEntity.notFound().build();
        }
        Path path = Paths.get(event.getSnapshotPath());
        Resource resource = new UrlResource(path.toUri());
        if (resource.exists() && resource.isReadable()) {
            return ResponseEntity.ok()
                    .header(HttpHeaders.CONTENT_TYPE, MediaType.IMAGE_JPEG_VALUE)
                    .body(resource);
        }
        return ResponseEntity.notFound().build();
    }

    /**
     * Daily summary endpoint (summarizes day's captions with caching)
     */
    @GetMapping("/summary/today")
    public ResponseEntity<Map<String, Object>> getTodaySummary() {
        LocalDate today = LocalDate.now();
        Instant now = Instant.now();

        // Return cached summary if generated within last 5 minutes on the same day
        if (today.equals(cachedSummaryDate) && ChronoUnit.MINUTES.between(lastSummaryGenerated, now) < 5) {
            return ResponseEntity.ok(Map.of("date", today.toString(), "summary", cachedSummary, "cached", true));
        }

        Instant startOfDay = today.atStartOfDay(ZoneId.systemDefault()).toInstant();
        List<Event> todayEvents = eventRepository.findByTimestampAfterOrderByTimestampAsc(startOfDay);

        if (todayEvents.isEmpty()) {
            cachedSummary = "No security events recorded so far today.";
        } else {
            String combinedCaptions = todayEvents.stream()
                    .map(e -> String.format("[%s] %s", e.getTimestamp().toString().substring(11, 16), e.getCaption()))
                    .collect(Collectors.joining("; "));
            cachedSummary = String.format("%d event(s) recorded today. Activity log: %s", todayEvents.size(), combinedCaptions);
        }

        cachedSummaryDate = today;
        lastSummaryGenerated = now;

        return ResponseEntity.ok(Map.of("date", today.toString(), "summary", cachedSummary, "cached", false));
    }

    /**
     * Delete an event
     */
    @DeleteMapping("/events/{id}")
    public ResponseEntity<Void> deleteEvent(@PathVariable String id) {
        eventRepository.findById(id).ifPresent(event -> {
            if (event.getSnapshotPath() != null) {
                try {
                    Files.deleteIfExists(Paths.get(event.getSnapshotPath()));
                } catch (IOException ignored) {}
            }
            eventRepository.delete(event);
        });
        return ResponseEntity.noContent().build();
    }

    /**
     * Scheduled job: Auto-delete snapshots older than retention days
     */
    @Scheduled(cron = "0 0 2 * * ?") // 2:00 AM every night
    public void cleanupOldSnapshots() {
        Instant cutoff = Instant.now().minus(retentionDays, ChronoUnit.DAYS);
        log.info("Running automatic retention cleanup for events prior to: {}", cutoff);
        eventRepository.deleteByTimestampBefore(cutoff);
    }
}
