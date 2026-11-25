package com.smartdoor.api;

import jakarta.persistence.*;
import lombok.*;
import java.time.Instant;

@Entity
@Table(name = "events")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Event {
    @Id
    @Column(length = 64)
    private String id;

    @Column(nullable = false)
    private Instant timestamp;

    @Column(name = "person_label", length = 100, nullable = false)
    private String personLabel;

    @Column(columnDefinition = "TEXT", nullable = false)
    private String caption;

    @Column(name = "snapshot_path", length = 512)
    private String snapshotPath;

    @Column(name = "device_id", length = 64)
    private String deviceId;

    @Column(name = "created_at", updatable = false)
    @Builder.Default
    private Instant createdAt = Instant.now();
}
