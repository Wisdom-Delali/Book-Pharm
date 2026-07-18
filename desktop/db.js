// Local SQLite mirror + sales outbox (CLAUDE.md §7). Lives entirely in the
// main process — node:sqlite is a built-in module (Node 22+, no native
// compilation/ABI-matching headaches), but the renderer is sandboxed with
// no Node access, so this is reached only via IPC (see main.js/preload.js).

const { DatabaseSync } = require('node:sqlite');
const path = require('path');

let db = null;

function getDb(userDataPath) {
  if (db) return db;
  db = new DatabaseSync(path.join(userDataPath, 'pos.sqlite3'));
  db.exec(`
    CREATE TABLE IF NOT EXISTS books (
      id INTEGER PRIMARY KEY,
      isbn TEXT,
      internal_code TEXT,
      title TEXT NOT NULL,
      author TEXT,
      category TEXT,
      selling_price TEXT NOT NULL,
      stock_qty INTEGER NOT NULL,
      low_stock_threshold INTEGER NOT NULL,
      cover_image TEXT,
      is_active INTEGER NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
    CREATE INDEX IF NOT EXISTS idx_books_isbn ON books(isbn);
    CREATE INDEX IF NOT EXISTS idx_books_internal_code ON books(internal_code);

    CREATE TABLE IF NOT EXISTS sync_meta (
      key TEXT PRIMARY KEY,
      value TEXT
    );

    CREATE TABLE IF NOT EXISTS outbox (
      offline_uuid TEXT PRIMARY KEY,
      payload TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'PENDING',
      created_at TEXT NOT NULL,
      synced_at TEXT,
      attempts INTEGER NOT NULL DEFAULT 0,
      last_error TEXT,
      server_response TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_outbox_status ON outbox(status);
  `);
  return db;
}

// ---------- Catalog mirror ----------

function upsertBooks(userDataPath, books) {
  const database = getDb(userDataPath);
  const stmt = database.prepare(`
    INSERT INTO books (id, isbn, internal_code, title, author, category, selling_price, stock_qty, low_stock_threshold, cover_image, is_active, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
      isbn=excluded.isbn, internal_code=excluded.internal_code, title=excluded.title,
      author=excluded.author, category=excluded.category, selling_price=excluded.selling_price,
      stock_qty=excluded.stock_qty, low_stock_threshold=excluded.low_stock_threshold,
      cover_image=excluded.cover_image, is_active=excluded.is_active, updated_at=excluded.updated_at
  `);
  for (const b of books) {
    stmt.run(
      b.id, b.isbn, b.internal_code, b.title, b.author || '', b.category || '',
      String(b.selling_price), b.stock_qty, b.low_stock_threshold, b.cover_image,
      b.is_active ? 1 : 0, b.updated_at
    );
  }
  return books.length;
}

function searchLocalBooks(userDataPath, query) {
  const database = getDb(userDataPath);
  const stmt = database.prepare(`
    SELECT * FROM books
    WHERE is_active = 1 AND (title LIKE ? OR author LIKE ?)
    ORDER BY title LIMIT 8
  `);
  const like = `%${query}%`;
  return stmt.all(like, like);
}

function lookupLocalBook(userDataPath, code) {
  const database = getDb(userDataPath);
  const stmt = database.prepare(`
    SELECT * FROM books WHERE is_active = 1 AND (isbn = ? OR internal_code = ?) LIMIT 1
  `);
  return stmt.get(code, code) || null;
}

function adjustLocalStock(userDataPath, bookId, delta) {
  // Optimistic local decrement so the mirror stays roughly honest across
  // several offline sales in one session. Never authoritative — the next
  // catalog pull overwrites it with the server's real number regardless.
  const database = getDb(userDataPath);
  database.prepare('UPDATE books SET stock_qty = stock_qty - ? WHERE id = ?').run(delta, bookId);
}

// ---------- Sync watermark ----------

function getSyncMeta(userDataPath, key) {
  const database = getDb(userDataPath);
  const row = database.prepare('SELECT value FROM sync_meta WHERE key = ?').get(key);
  return row ? row.value : null;
}

function setSyncMeta(userDataPath, key, value) {
  const database = getDb(userDataPath);
  database.prepare('INSERT INTO sync_meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value').run(key, value);
}

// ---------- Outbox ----------

function addToOutbox(userDataPath, offlineUuid, payload) {
  const database = getDb(userDataPath);
  database.prepare(`
    INSERT INTO outbox (offline_uuid, payload, status, created_at)
    VALUES (?, ?, 'PENDING', ?)
  `).run(offlineUuid, JSON.stringify(payload), new Date().toISOString());
}

function getPendingOutbox(userDataPath) {
  const database = getDb(userDataPath);
  const rows = database.prepare(`
    SELECT * FROM outbox WHERE status IN ('PENDING', 'FAILED') ORDER BY created_at ASC
  `).all();
  return rows.map((r) => ({ ...r, payload: JSON.parse(r.payload) }));
}

function getOutboxPendingCount(userDataPath) {
  const database = getDb(userDataPath);
  const row = database.prepare(`SELECT COUNT(*) as c FROM outbox WHERE status IN ('PENDING', 'FAILED')`).get();
  return row.c;
}

function markOutboxSynced(userDataPath, offlineUuid, serverResponse) {
  const database = getDb(userDataPath);
  database.prepare(`
    UPDATE outbox SET status = 'SYNCED', synced_at = ?, server_response = ? WHERE offline_uuid = ?
  `).run(new Date().toISOString(), JSON.stringify(serverResponse), offlineUuid);
}

function markOutboxFailed(userDataPath, offlineUuid, errorMessage) {
  const database = getDb(userDataPath);
  database.prepare(`
    UPDATE outbox SET status = 'FAILED', attempts = attempts + 1, last_error = ? WHERE offline_uuid = ?
  `).run(errorMessage, offlineUuid);
}

module.exports = {
  upsertBooks, searchLocalBooks, lookupLocalBook, adjustLocalStock,
  getSyncMeta, setSyncMeta,
  addToOutbox, getPendingOutbox, getOutboxPendingCount, markOutboxSynced, markOutboxFailed,
};
