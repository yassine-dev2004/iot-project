-- V1__init_schema.sql
CREATE TABLE IF NOT EXISTS devices (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    api_key_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id VARCHAR(64) PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    person_label VARCHAR(100) NOT NULL,
    caption TEXT NOT NULL,
    snapshot_path VARCHAR(512),
    device_id VARCHAR(64) REFERENCES devices(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_timestamp ON events(timestamp DESC);
CREATE INDEX idx_events_person ON events(person_label);

-- Insert default test device
INSERT INTO devices (id, name, api_key_hash)
VALUES ('pi-front-door-01', 'Raspberry Pi Front Entrance', 'a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e')
ON CONFLICT (id) DO NOTHING;
