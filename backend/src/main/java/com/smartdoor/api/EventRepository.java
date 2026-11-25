package com.smartdoor.api;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;

@Repository
public interface EventRepository extends JpaRepository<Event, String> {
    Page<Event> findByTimestampBetween(Instant start, Instant end, Pageable pageable);
    Page<Event> findByPersonLabelContainingIgnoreCase(String personLabel, Pageable pageable);
    List<Event> findByTimestampAfterOrderByTimestampAsc(Instant timestamp);
    void deleteByTimestampBefore(Instant cutoff);
}
