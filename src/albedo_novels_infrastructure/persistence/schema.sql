-- Baseline ER model
--
-- users is owned by albedo-auth. This service stores no user rows and treats
-- author_id, last_modified_user_id, and library_entries.user_id as references
-- to auth identities. JWT role claims supply the author/editor/reader roles:
--   users ||--o{ novels          : writes (author_id)
--   users ||--o{ novels          : edits (last_modified_user_id)
--   users ||--o{ library_entries : favorites (user_id)
--   novels ||--o{ library_entries : favorited_by (novel_id)
--
-- Novel metadata only. Covers, introductions, and chapter content belong in resources/content stores.
CREATE TABLE IF NOT EXISTS novels (
    id VARCHAR(255) NOT NULL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    author_id VARCHAR(255) NOT NULL,
    status VARCHAR(16) NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    isbn VARCHAR(32) NULL UNIQUE,
    last_modified_user_id VARCHAR(255) NULL,
    CONSTRAINT novels_status_check CHECK (status IN ('draft', 'published')),
    KEY novels_status_created_idx (status, created_at),
    KEY novels_author_created_idx (author_id, created_at)
);

CREATE TABLE IF NOT EXISTS library_entries (
    user_id VARCHAR(255) NOT NULL,
    novel_id VARCHAR(255) NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    PRIMARY KEY (user_id, novel_id),
    KEY library_entries_user_created_idx (user_id, created_at),
    CONSTRAINT library_entries_novel_fk FOREIGN KEY (novel_id) REFERENCES novels (id) ON DELETE CASCADE
);
