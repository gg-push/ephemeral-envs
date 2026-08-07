CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    done BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

INSERT INTO tasks (title, done) VALUES 
('Migrate legacy user data to v2 schema', true),
('Update Kubernetes ingress annotations for TLS', false),
('Fix race condition in payment gateway webhook', false),
('Deprecate old /v1/users endpoint', false),
('Write post-mortem for yesterday''s database outage', true),
('Implement scale-to-zero for ephemeral environments', false);
