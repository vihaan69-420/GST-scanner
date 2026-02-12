/**
 * SQLite database for content (CMS, plans). Server-only.
 */

import Database from "better-sqlite3";
import { mkdirSync, existsSync } from "fs";
import path from "path";

const DATA_DIR = path.join(process.cwd(), "data");
const DB_PATH = path.join(DATA_DIR, "gst.db");

function getDb(): Database.Database {
  if (!existsSync(DATA_DIR)) {
    mkdirSync(DATA_DIR, { recursive: true });
  }
  const db = new Database(DB_PATH);
  db.pragma("journal_mode = WAL");
  db.exec(`
    CREATE TABLE IF NOT EXISTS content (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL
    );
  `);
  return db;
}

let db: Database.Database | null = null;

function dbInstance(): Database.Database {
  if (!db) {
    db = getDb();
  }
  return db;
}

export function getContent(key: string): string | null {
  const row = dbInstance().prepare("SELECT value FROM content WHERE key = ?").get(key) as { value: string } | undefined;
  return row?.value ?? null;
}

export function setContent(key: string, value: string): void {
  dbInstance()
    .prepare("INSERT INTO content (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?")
    .run(key, value, value);
}
