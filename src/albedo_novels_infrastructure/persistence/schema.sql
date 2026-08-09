-- Novel metadata only. Novel chapters/content are stored separately.
CREATE TABLE IF NOT EXISTS novels (
    id VARCHAR(255) NOT NULL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    author_id VARCHAR(255) NOT NULL,
    author_display_name VARCHAR(255) NOT NULL,
    cover_image_url TEXT NOT NULL,
    status VARCHAR(16) NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    owner_id VARCHAR(255) NOT NULL,
    isbn VARCHAR(32) NULL,
    external_code VARCHAR(128) NULL,
    last_modified_user_id VARCHAR(255) NULL,
    CONSTRAINT novels_status_check CHECK (status IN ('draft', 'published')),
    UNIQUE KEY novels_isbn_unique (isbn),
    UNIQUE KEY novels_external_code_unique (external_code),
    KEY novels_status_created_idx (status, created_at),
    KEY novels_owner_created_idx (owner_id, created_at)
);

CREATE TABLE IF NOT EXISTS library_entries (
    user_id VARCHAR(255) NOT NULL,
    novel_id VARCHAR(255) NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    PRIMARY KEY (user_id, novel_id),
    KEY library_entries_user_created_idx (user_id, created_at),
    CONSTRAINT library_entries_novel_fk
        FOREIGN KEY (novel_id) REFERENCES novels (id) ON DELETE CASCADE
);
