import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

DB_PATH = "job_search.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                website_url TEXT,
                domain TEXT,
                country TEXT,
                sector TEXT,
                size_estimate TEXT,
                is_pe_backed INTEGER DEFAULT 0,
                trigger_type TEXT,
                trigger_signal TEXT,
                trigger_source_url TEXT,
                open_role_url TEXT,
                open_role_title TEXT,
                job_description TEXT,
                priority_score REAL DEFAULT 0.0,
                status TEXT DEFAULT 'discovered',
                notes TEXT,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER REFERENCES companies(id),
                full_name TEXT,
                first_name TEXT,
                last_name TEXT,
                title TEXT,
                email TEXT,
                email_status TEXT DEFAULT 'unknown',
                email_source TEXT,
                email_confidence_score INTEGER DEFAULT 0,
                phone TEXT,
                linkedin_url TEXT,
                recent_activity TEXT,
                recent_activity_url TEXT,
                is_primary INTEGER DEFAULT 0,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS resumes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER REFERENCES companies(id),
                contact_id INTEGER,
                target_role TEXT,
                tailored_headline TEXT,
                tailored_summary TEXT,
                tailored_experience_json TEXT,
                achievements_json TEXT,
                skills_json TEXT,
                changes_made TEXT,
                ats_keywords TEXT,
                ats_score REAL,
                tailoring_rationale TEXT,
                docx_path TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS outreach (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER REFERENCES companies(id),
                contact_id INTEGER REFERENCES contacts(id),
                resume_id INTEGER REFERENCES resumes(id),
                email_subject TEXT,
                email_body TEXT,
                linkedin_note TEXT,
                followup_subject TEXT,
                followup_body TEXT,
                cover_letter TEXT,
                personalization_hooks TEXT,
                word_count INTEGER,
                status TEXT DEFAULT 'draft',
                sent_at TEXT,
                followup_due_date TEXT,
                reply_received INTEGER DEFAULT 0,
                reply_content TEXT,
                created_at TEXT
            );
        """)


def _row_to_dict(row) -> dict:
    if row is None:
        return None
    return dict(row)


class CompanyDB:

    @staticmethod
    def create(conn, data: dict) -> int:
        cursor = conn.execute(
            """
            INSERT INTO companies (
                company_name, website_url, domain, country, sector,
                size_estimate, is_pe_backed, trigger_type, trigger_signal,
                trigger_source_url, open_role_url, open_role_title,
                job_description, priority_score, status, notes,
                created_at, updated_at
            ) VALUES (
                :company_name, :website_url, :domain, :country, :sector,
                :size_estimate, :is_pe_backed, :trigger_type, :trigger_signal,
                :trigger_source_url, :open_role_url, :open_role_title,
                :job_description, :priority_score, :status, :notes,
                :created_at, :updated_at
            )
            """,
            {
                "company_name": data.get("company_name"),
                "website_url": data.get("website_url"),
                "domain": data.get("domain"),
                "country": data.get("country"),
                "sector": data.get("sector"),
                "size_estimate": data.get("size_estimate"),
                "is_pe_backed": data.get("is_pe_backed", 0),
                "trigger_type": data.get("trigger_type"),
                "trigger_signal": data.get("trigger_signal"),
                "trigger_source_url": data.get("trigger_source_url"),
                "open_role_url": data.get("open_role_url"),
                "open_role_title": data.get("open_role_title"),
                "job_description": data.get("job_description"),
                "priority_score": data.get("priority_score", 0.0),
                "status": data.get("status", "discovered"),
                "notes": data.get("notes"),
                "created_at": data.get("created_at", datetime.now().isoformat()),
                "updated_at": data.get("updated_at", datetime.now().isoformat()),
            }
        )
        return cursor.lastrowid

    @staticmethod
    def get_all(conn) -> list:
        rows = conn.execute("""
            SELECT c.*,
                   ct.full_name AS contact_name,
                   ct.email_status
            FROM companies c
            LEFT JOIN contacts ct ON ct.company_id = c.id AND ct.is_primary = 1
            ORDER BY c.created_at DESC
        """).fetchall()
        return [_row_to_dict(r) for r in rows]

    @staticmethod
    def get_by_id(conn, company_id: int) -> Optional[dict]:
        row = conn.execute(
            "SELECT * FROM companies WHERE id = ?", (company_id,)
        ).fetchone()
        return _row_to_dict(row)

    @staticmethod
    def update_status(conn, company_id: int, status: str):
        conn.execute(
            "UPDATE companies SET status = ?, updated_at = ? WHERE id = ?",
            (status, datetime.now().isoformat(), company_id)
        )


class ContactDB:

    @staticmethod
    def create(conn, data: dict) -> int:
        cursor = conn.execute(
            """
            INSERT INTO contacts (
                company_id, full_name, first_name, last_name, title,
                email, email_status, email_source, email_confidence_score,
                phone, linkedin_url, recent_activity, recent_activity_url,
                is_primary, created_at
            ) VALUES (
                :company_id, :full_name, :first_name, :last_name, :title,
                :email, :email_status, :email_source, :email_confidence_score,
                :phone, :linkedin_url, :recent_activity, :recent_activity_url,
                :is_primary, :created_at
            )
            """,
            {
                "company_id": data.get("company_id"),
                "full_name": data.get("full_name"),
                "first_name": data.get("first_name"),
                "last_name": data.get("last_name"),
                "title": data.get("title"),
                "email": data.get("email"),
                "email_status": data.get("email_status", "unknown"),
                "email_source": data.get("email_source"),
                "email_confidence_score": data.get("email_confidence_score", 0),
                "phone": data.get("phone"),
                "linkedin_url": data.get("linkedin_url"),
                "recent_activity": data.get("recent_activity"),
                "recent_activity_url": data.get("recent_activity_url"),
                "is_primary": data.get("is_primary", 0),
                "created_at": data.get("created_at", datetime.now().isoformat()),
            }
        )
        return cursor.lastrowid

    @staticmethod
    def get_by_company(conn, company_id: int) -> list:
        rows = conn.execute(
            "SELECT * FROM contacts WHERE company_id = ? ORDER BY is_primary DESC",
            (company_id,)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    @staticmethod
    def get_all(conn) -> list:
        rows = conn.execute(
            "SELECT * FROM contacts ORDER BY created_at DESC"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


class ResumeDB:

    @staticmethod
    def create(conn, data: dict) -> int:
        cursor = conn.execute(
            """
            INSERT INTO resumes (
                company_id, contact_id, target_role, tailored_headline,
                tailored_summary, tailored_experience_json, achievements_json,
                skills_json, changes_made, ats_keywords, ats_score,
                tailoring_rationale, docx_path, created_at
            ) VALUES (
                :company_id, :contact_id, :target_role, :tailored_headline,
                :tailored_summary, :tailored_experience_json, :achievements_json,
                :skills_json, :changes_made, :ats_keywords, :ats_score,
                :tailoring_rationale, :docx_path, :created_at
            )
            """,
            {
                "company_id": data.get("company_id"),
                "contact_id": data.get("contact_id"),
                "target_role": data.get("target_role"),
                "tailored_headline": data.get("tailored_headline"),
                "tailored_summary": data.get("tailored_summary"),
                "tailored_experience_json": data.get("tailored_experience_json"),
                "achievements_json": data.get("achievements_json"),
                "skills_json": data.get("skills_json"),
                "changes_made": data.get("changes_made"),
                "ats_keywords": data.get("ats_keywords"),
                "ats_score": data.get("ats_score"),
                "tailoring_rationale": data.get("tailoring_rationale"),
                "docx_path": data.get("docx_path"),
                "created_at": data.get("created_at", datetime.now().isoformat()),
            }
        )
        return cursor.lastrowid

    @staticmethod
    def get_by_company(conn, company_id: int) -> list:
        rows = conn.execute(
            "SELECT * FROM resumes WHERE company_id = ? ORDER BY created_at DESC",
            (company_id,)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


class OutreachDB:

    @staticmethod
    def create(conn, data: dict) -> int:
        cursor = conn.execute(
            """
            INSERT INTO outreach (
                company_id, contact_id, resume_id, email_subject, email_body,
                linkedin_note, followup_subject, followup_body, cover_letter,
                personalization_hooks, word_count, status, sent_at,
                followup_due_date, reply_received, reply_content, created_at
            ) VALUES (
                :company_id, :contact_id, :resume_id, :email_subject, :email_body,
                :linkedin_note, :followup_subject, :followup_body, :cover_letter,
                :personalization_hooks, :word_count, :status, :sent_at,
                :followup_due_date, :reply_received, :reply_content, :created_at
            )
            """,
            {
                "company_id": data.get("company_id"),
                "contact_id": data.get("contact_id"),
                "resume_id": data.get("resume_id"),
                "email_subject": data.get("email_subject"),
                "email_body": data.get("email_body"),
                "linkedin_note": data.get("linkedin_note"),
                "followup_subject": data.get("followup_subject"),
                "followup_body": data.get("followup_body"),
                "cover_letter": data.get("cover_letter"),
                "personalization_hooks": data.get("personalization_hooks"),
                "word_count": data.get("word_count", 0),
                "status": data.get("status", "draft"),
                "sent_at": data.get("sent_at"),
                "followup_due_date": data.get("followup_due_date"),
                "reply_received": data.get("reply_received", 0),
                "reply_content": data.get("reply_content"),
                "created_at": data.get("created_at", datetime.now().isoformat()),
            }
        )
        return cursor.lastrowid

    @staticmethod
    def get_by_company(conn, company_id: int) -> list:
        rows = conn.execute(
            "SELECT * FROM outreach WHERE company_id = ? ORDER BY created_at DESC",
            (company_id,)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    @staticmethod
    def get_all(conn) -> list:
        rows = conn.execute(
            "SELECT * FROM outreach ORDER BY created_at DESC"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    @staticmethod
    def get_followups_due(conn, date_str: str) -> list:
        rows = conn.execute(
            """
            SELECT o.*, c.company_name, ct.full_name AS contact_name
            FROM outreach o
            JOIN companies c ON c.id = o.company_id
            LEFT JOIN contacts ct ON ct.id = o.contact_id
            WHERE o.followup_due_date <= ?
              AND o.reply_received = 0
              AND o.status != 'replied'
            ORDER BY o.followup_due_date ASC
            """,
            (date_str,)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
