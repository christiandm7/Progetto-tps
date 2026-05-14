import sqlite3
import os

DB_PATH = "edutrack.db"

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

conn = None
try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    # ── Creazione tabelle 

    cursor.execute("""
        CREATE TABLE utenti (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            ruolo         TEXT NOT NULL CHECK(ruolo IN ('docente', 'studente')),
            nome          TEXT NOT NULL,
            cognome       TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE materie (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE
        )
    """)

    cursor.execute("""
        CREATE TABLE voti (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            studente_id INTEGER NOT NULL,
            docente_id  INTEGER NOT NULL,
            materia_id  INTEGER NOT NULL,
            valore      REAL NOT NULL CHECK(valore >= 1 AND valore <= 10),
            data        TEXT NOT NULL,
            commento    TEXT,
            FOREIGN KEY (studente_id) REFERENCES utenti(id),
            FOREIGN KEY (docente_id)  REFERENCES utenti(id),
            FOREIGN KEY (materia_id)  REFERENCES materie(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE assenze (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            studente_id  INTEGER NOT NULL,
            data         TEXT NOT NULL,
            giustificata INTEGER NOT NULL DEFAULT 0,
            note         TEXT,
            FOREIGN KEY (studente_id) REFERENCES utenti(id)
        )
    """)

    # ── popolamento delle tabelle

    HASH = "pbkdf2:sha256:600000$x$aaabbbccc"  

    cursor.executemany(
        "INSERT INTO utenti (username, password_hash, ruolo, nome, cognome) VALUES (?,?,?,?,?)",
        [
            ("prof.rossi",  "docente",  "Mario",  "Rossi"),
            ("prof.bianchi", "docente",  "Laura",  "Bianchi"),
            ("s.ferrari",   "studente", "Luca",   "Ferrari"),
            ("s.esposito",  "studente", "Giulia", "Esposito"),
            ("s.romano",     "studente", "Marco",  "Romano"),
        ]
    )

    cursor.executemany(
        "INSERT INTO materie (nome) VALUES (?)",
        [("Matematica",), ("Italiano",), ("Storia",), ("Informatica",), ("Inglese",)]
    )


    cursor.executemany(
        "INSERT INTO voti (studente_id, docente_id, materia_id, valore, data, commento) VALUES (?,?,?,?,?,?)",
        [
            (3, 1, 1, 7.5, "2025-03-10", "Buona comprensione"),
            (3, 1, 4, 9.0, "2025-03-12", "Ottimo progetto"),
            (3, 2, 2, 6.5, "2025-03-15", None),
            (4, 1, 1, 8.5, "2025-03-10", "Eccellente"),
            (4, 2, 2, 9.5, "2025-03-15", "Analisi matura"),
            (5, 1, 1, 5.5, "2025-03-10", "Deve ripassare"),
            (5, 2, 3, 7.0, "2025-03-20", None),
        ]
    )

    cursor.executemany(
        "INSERT INTO assenze (studente_id, data, giustificata, note) VALUES (?,?,?,?)",
        [
            (3, "2025-03-05", 1, "Visita medica"),
            (3, "2025-03-18", 0, None),
            (4, "2025-03-07", 1, "Malattia"),
            (5, "2025-03-11", 0, None),
            (5, "2025-03-19", 0, None),
        ]
    )

    conn.commit()

    # ── test

    for tabella in ["utenti", "materie", "voti", "assenze"]:
        righe = cursor.execute(f"SELECT * FROM {tabella}").fetchall()
        print(f"\n[{tabella.upper()}] — {len(righe)} record")
        for r in righe:
            print(" ", r)

    print("\n[OK] Database pronto.")

except sqlite3.Error as e:
    print(f"[ERRORE] {e}")

finally:
    if conn:
        conn.close()