-- travel DB v2 schema (parallel to public.attractions / public.knowledge_chunks)
-- Apply: sudo -u postgres psql -d travel -f v2_schema.sql

CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS v2;

COMMENT ON SCHEMA v2 IS
  'Clean-layer v2: attractions catalog + poi_details + rag_chunks + images. Legacy tables remain in public until cutover.';

-- ---------------------------------------------------------------------------
-- attractions: one row per POI (catalog / identity)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS v2.attractions (
    poi_id            BIGINT PRIMARY KEY,
    name              TEXT NOT NULL,
    name_en           TEXT,
    city              TEXT,
    district_id       BIGINT,
    district_name     TEXT,
    source_poi_type   INTEGER,
    entity_type       TEXT NOT NULL DEFAULT 'unknown',
    latitude          DOUBLE PRECISION,
    longitude         DOUBLE PRECISION,
    coordinate_type   TEXT,
    sight_level       TEXT,
    sight_level_known BOOLEAN NOT NULL DEFAULT false,
    tags              JSONB NOT NULL DEFAULT '[]'::jsonb,
    entry_type        TEXT,
    comment_score     REAL,
    comment_count     INTEGER NOT NULL DEFAULT 0,
    heat_score        TEXT,
    phones            JSONB NOT NULL DEFAULT '[]'::jsonb,
    source            TEXT,
    source_url        TEXT,
    field_sources     JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at      TIMESTAMPTZ,
    verify_status     TEXT NOT NULL DEFAULT 'unverified',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON COLUMN v2.attractions.source_poi_type IS
  'Platform raw poiType (e.g. Ctrip 3 / 66). Not a business category.';
COMMENT ON COLUMN v2.attractions.entity_type IS
  'Project-owned type: scenic_spot | exhibition | performance | ski_resort | rafting | hot_spring | other | unknown';
COMMENT ON COLUMN v2.attractions.collected_at IS
  'Catalog snapshot time (= clean data_updated_at / detail collected_at).';

-- ---------------------------------------------------------------------------
-- poi_details: 0..1 latest detail blob per POI
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS v2.poi_details (
    poi_id             BIGINT PRIMARY KEY
                       REFERENCES v2.attractions(poi_id) ON DELETE CASCADE,
    introduction_html  TEXT,
    introduction_text  TEXT,
    open_time          JSONB NOT NULL DEFAULT '{}'::jsonb,
    ticket_raw         TEXT,
    ticket_data        JSONB NOT NULL DEFAULT '{}'::jsonb,
    preferential       JSONB NOT NULL DEFAULT '{}'::jsonb,
    notice_html        TEXT,
    notice_text        TEXT,
    entry_policies     JSONB NOT NULL DEFAULT '[]'::jsonb,
    facilities         JSONB NOT NULL DEFAULT '[]'::jsonb,
    detail_meta        JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at       TIMESTAMPTZ,
    verify_status      TEXT NOT NULL DEFAULT 'unverified',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON COLUMN v2.poi_details.open_time IS
  'Structured open fields: open_status, open_status_type, open_time_tips, play_spend_time, open_date_rules, ...';
COMMENT ON COLUMN v2.poi_details.ticket_raw IS
  'Human-readable ticket copy; do not overwrite with parsed numbers.';
COMMENT ON COLUMN v2.poi_details.ticket_data IS
  'Parsed / structured ticket + list_price; keep raw in ticket_raw.';
COMMENT ON COLUMN v2.poi_details.preferential IS
  'Preferential note + policies JSON.';
COMMENT ON COLUMN v2.poi_details.detail_meta IS
  'Provenance: source, source_api, source_url, collected_at, verify_status, ...';

-- ---------------------------------------------------------------------------
-- rag_chunks: retrieval units
-- embedding: BGE-M3 dense = 1024 dims. Do not pad/truncate other models to fit.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS v2.rag_chunks (
    chunk_id       TEXT PRIMARY KEY,
    poi_id         BIGINT NOT NULL
                   REFERENCES v2.attractions(poi_id) ON DELETE CASCADE,
    name           TEXT,
    theme          TEXT NOT NULL,
    theme_label    TEXT,
    content_source TEXT,
    text           TEXT NOT NULL,
    source         TEXT,
    source_api     TEXT,
    source_url     TEXT,
    collected_at   TIMESTAMPTZ,
    verify_status  TEXT NOT NULL DEFAULT 'unverified',
    embedding      vector(1024),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- images: URL references only (no binary blobs)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS v2.images (
    image_id       BIGSERIAL PRIMARY KEY,
    poi_id         BIGINT NOT NULL
                   REFERENCES v2.attractions(poi_id) ON DELETE CASCADE,
    image_url      TEXT NOT NULL,
    image_role     TEXT,
    alt_text       TEXT,
    source         TEXT,
    source_api     TEXT,
    source_url     TEXT,
    collected_at   TIMESTAMPTZ,
    verify_status  TEXT NOT NULL DEFAULT 'unverified',
    sort_order     INTEGER NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Light indexes only (no HNSW / IVFFlat yet)
CREATE INDEX IF NOT EXISTS idx_v2_attr_city ON v2.attractions (city);
CREATE INDEX IF NOT EXISTS idx_v2_attr_district ON v2.attractions (district_name);
CREATE INDEX IF NOT EXISTS idx_v2_attr_entity_type ON v2.attractions (entity_type);
CREATE INDEX IF NOT EXISTS idx_v2_attr_source_poi_type ON v2.attractions (source_poi_type);
CREATE INDEX IF NOT EXISTS idx_v2_chunk_poi ON v2.rag_chunks (poi_id);
CREATE INDEX IF NOT EXISTS idx_v2_chunk_theme ON v2.rag_chunks (theme);
CREATE INDEX IF NOT EXISTS idx_v2_img_poi ON v2.images (poi_id);

GRANT USAGE ON SCHEMA v2 TO travel_agent;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA v2 TO travel_agent;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA v2 TO travel_agent;
ALTER DEFAULT PRIVILEGES IN SCHEMA v2
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO travel_agent;
ALTER DEFAULT PRIVILEGES IN SCHEMA v2
    GRANT USAGE, SELECT ON SEQUENCES TO travel_agent;
