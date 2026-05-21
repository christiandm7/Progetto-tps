"""
EduTrack - API Dashboard Docente
Endpoint POST per inserimento valutazioni e registrazione assenze
con validazione RBAC a 3 fasi.
"""

from flask import Blueprint, request, session, jsonify
from datetime import datetime
import sqlite3
import os

docente_bp = Blueprint('docente', __name__)

# ──────────────────────────────────────────────
# COSTANTI DI CONFIGURAZIONE ISTITUTO
# ──────────────────────────────────────────────
VOTO_MIN = 1
VOTO_MAX = 10


# ──────────────────────────────────────────────
# HELPER: connessione al database
# ──────────────────────────────────────────────
def get_db():
    """Restituisce una connessione al database SQLite con row_factory."""
    db_path = os.environ.get('EDUTRACK_DB', 'edutrack.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ──────────────────────────────────────────────
# HELPER: decorator per autenticazione docente
# ──────────────────────────────────────────────
def richiedi_docente(f):
    """
    Decorator che verifica:
      - Sessione attiva (user_id presente)
      - Ruolo dell'utente == 'docente'
    Restituisce 401 o 403 in caso contrario.
    """
    from functools import wraps

    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({
                'errore': 'Autenticazione richiesta.',
                'codice': 'NOT_AUTHENTICATED'
            }), 401

        if session.get('ruolo') != 'docente':
            return jsonify({
                'errore': 'Accesso riservato ai docenti.',
                'codice': 'FORBIDDEN_ROLE'
            }), 403

        return f(*args, **kwargs)
    return wrapper


# ──────────────────────────────────────────────
# FASE 1 – VALIDAZIONE FORMALE (condivisa)
# ──────────────────────────────────────────────
def valida_data(data_str: str):
    """
    Verifica che la stringa sia nel formato YYYY-MM-DD
    e che corrisponda a una data realmente esistente nel calendario.
    Restituisce l'oggetto date se valida, None altrimenti.
    """
    try:
        return datetime.strptime(data_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


# ════════════════════════════════════════════════════════════════
#  ENDPOINT 1 – POST /api/docente/valutazioni
# ════════════════════════════════════════════════════════════════
@docente_bp.route('/api/docente/valutazioni', methods=['POST'])
@richiedi_docente
def inserisci_valutazione():
    """
    Inserisce una valutazione per uno studente.

    Flusso di validazione:
      Fase 1 → campi obbligatori, formato data, range voto
      Fase 2 → lo studente appartiene a una classe del docente
      Fase 3 → il docente insegna quella materia in quella classe
    """
    docente_id = session['user_id']
    payload = request.get_json(silent=True)

    # ── FASE 1: Validazione formale ───────────────────────────
    if not payload:
        return jsonify({
            'errore': 'Payload JSON mancante o malformato.',
            'codice': 'INVALID_JSON'
        }), 400

    campi_obbligatori = ['studente_id', 'materia', 'voto', 'data']
    mancanti = [c for c in campi_obbligatori if payload.get(c) is None]
    if mancanti:
        return jsonify({
            'errore': f'Campi obbligatori mancanti: {", ".join(mancanti)}.',
            'codice': 'MISSING_FIELDS'
        }), 400

    # Validazione studente_id
    try:
        studente_id = int(payload['studente_id'])
    except (ValueError, TypeError):
        return jsonify({
            'errore': 'studente_id deve essere un intero.',
            'codice': 'INVALID_STUDENT_ID'
        }), 400

    # Validazione materia
    materia = str(payload['materia']).strip()
    if not materia:
        return jsonify({
            'errore': 'Il campo materia non può essere vuoto.',
            'codice': 'INVALID_SUBJECT'
        }), 400

    # Validazione voto (range istituto: VOTO_MIN – VOTO_MAX)
    try:
        voto = float(payload['voto'])
    except (ValueError, TypeError):
        return jsonify({
            'errore': 'Il campo voto deve essere un numero decimale.',
            'codice': 'INVALID_GRADE_TYPE'
        }), 400

    if not (VOTO_MIN <= voto <= VOTO_MAX):
        return jsonify({
            'errore': f'Il voto deve essere compreso tra {VOTO_MIN} e {VOTO_MAX}.',
            'codice': 'GRADE_OUT_OF_RANGE'
        }), 400

    # Validazione data
    data_valutazione = valida_data(payload['data'])
    if data_valutazione is None:
        return jsonify({
            'errore': 'Formato data non valido. Usare YYYY-MM-DD e una data esistente.',
            'codice': 'INVALID_DATE'
        }), 400

    # Campo opzionale
    commento = str(payload.get('commento', '')).strip() or None

    # ── Database: apertura connessione ───────────────────────
    conn = get_db()
    try:
        cur = conn.cursor()

        # ── FASE 2: Controllo appartenenza (Studente → Classe → Docente) ──
        #
        # Query: verifica che lo studente esista E che la sua classe
        # figuri tra quelle assegnate al docente loggato.
        # La tabella `docenti_classi_materie` (relazione ternaria)
        # è la fonte di verità per le assegnazioni.
        cur.execute("""
            SELECT s.classe_id
            FROM studenti AS s
            JOIN docenti_classi_materie AS dcm
              ON dcm.classe_id = s.classe_id
            WHERE s.id           = ?
              AND dcm.docente_id = ?
            LIMIT 1
        """, (studente_id, docente_id))

        riga_classe = cur.fetchone()
        if riga_classe is None:
            return jsonify({
                'errore': 'Lo studente non appartiene a nessuna classe '
                          'assegnata a questo docente.',
                'codice': 'STUDENT_NOT_IN_TEACHER_CLASS'
            }), 403

        classe_id = riga_classe['classe_id']

        # ── FASE 3: Controllo competenza disciplinare ─────────────────────
        #
        # Verifica che esista almeno una riga in docenti_classi_materie
        # con la tripla (docente_id, classe_id, materia).
        # Gestisce la co-docenza: più docenti possono insegnare la stessa
        # materia nella stessa classe; conta solo il docente loggato.
        cur.execute("""
            SELECT 1
            FROM docenti_classi_materie
            WHERE docente_id = ?
              AND classe_id  = ?
              AND materia    = ?
            LIMIT 1
        """, (docente_id, classe_id, materia))

        if cur.fetchone() is None:
            return jsonify({
                'errore': f'Il docente non è autorizzato a valutare '
                          f'"{materia}" per la classe dello studente.',
                'codice': 'SUBJECT_NOT_AUTHORIZED'
            }), 403

        # ── INSERT ────────────────────────────────────────────────────────
        cur.execute("""
            INSERT INTO valutazioni
              (studente_id, docente_id, materia, voto, data, commento)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (studente_id, docente_id, materia, voto,
              data_valutazione.isoformat(), commento))

        conn.commit()
        valutazione_id = cur.lastrowid

    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({
            'errore': 'Errore interno del database.',
            'dettaglio': str(e),
            'codice': 'DB_ERROR'
        }), 500
    finally:
        conn.close()

    return jsonify({
        'messaggio': 'Valutazione inserita con successo.',
        'valutazione_id': valutazione_id
    }), 201


# ════════════════════════════════════════════════════════════════
#  ENDPOINT 2 – POST /api/docente/assenze
# ════════════════════════════════════════════════════════════════
@docente_bp.route('/api/docente/assenze', methods=['POST'])
@richiedi_docente
def registra_assenza():
    """
    Registra un'assenza per uno studente durante una specifica materia.

    Flusso di validazione:
      Fase 1 → campi obbligatori, formato data
      Fase 2 → lo studente appartiene a una classe del docente
      (Fase 3 non richiesta per le assenze: basta l'appartenenza alla classe)
    """
    docente_id = session['user_id']
    payload = request.get_json(silent=True)

    # ── FASE 1: Validazione formale ───────────────────────────
    if not payload:
        return jsonify({
            'errore': 'Payload JSON mancante o malformato.',
            'codice': 'INVALID_JSON'
        }), 400

    campi_obbligatori = ['studente_id', 'materia', 'data']
    mancanti = [c for c in campi_obbligatori if payload.get(c) is None]
    if mancanti:
        return jsonify({
            'errore': f'Campi obbligatori mancanti: {", ".join(mancanti)}.',
            'codice': 'MISSING_FIELDS'
        }), 400

    # Validazione studente_id
    try:
        studente_id = int(payload['studente_id'])
    except (ValueError, TypeError):
        return jsonify({
            'errore': 'studente_id deve essere un intero.',
            'codice': 'INVALID_STUDENT_ID'
        }), 400

    # Validazione materia
    materia = str(payload['materia']).strip()
    if not materia:
        return jsonify({
            'errore': 'Il campo materia non può essere vuoto.',
            'codice': 'INVALID_SUBJECT'
        }), 400

    # Validazione data
    data_assenza = valida_data(payload['data'])
    if data_assenza is None:
        return jsonify({
            'errore': 'Formato data non valido. Usare YYYY-MM-DD e una data esistente.',
            'codice': 'INVALID_DATE'
        }), 400

    # Campo opzionale: giustificata (default 0)
    giustificata_raw = payload.get('giustificata', 0)
    try:
        giustificata = int(bool(giustificata_raw))  # accetta 0/1/True/False
    except (ValueError, TypeError):
        giustificata = 0

    # ── Database: apertura connessione ───────────────────────
    conn = get_db()
    try:
        cur = conn.cursor()

        # ── FASE 2: Controllo appartenenza (Studente → Classe → Docente) ──
        #
        # Per le assenze non è necessario verificare la materia (Fase 3):
        # è sufficiente che il docente insegni in quella classe.
        cur.execute("""
            SELECT s.classe_id
            FROM studenti AS s
            JOIN docenti_classi_materie AS dcm
              ON dcm.classe_id = s.classe_id
            WHERE s.id           = ?
              AND dcm.docente_id = ?
            LIMIT 1
        """, (studente_id, docente_id))

        riga_classe = cur.fetchone()
        if riga_classe is None:
            return jsonify({
                'errore': 'Lo studente non appartiene a nessuna classe '
                          'assegnata a questo docente.',
                'codice': 'STUDENT_NOT_IN_TEACHER_CLASS'
            }), 403

        # ── INSERT ────────────────────────────────────────────────────────
        cur.execute("""
            INSERT INTO assenze
              (studente_id, docente_id, materia, data, giustificata)
            VALUES (?, ?, ?, ?, ?)
        """, (studente_id, docente_id, materia,
              data_assenza.isoformat(), giustificata))

        conn.commit()
        assenza_id = cur.lastrowid

    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({
            'errore': 'Errore interno del database.',
            'dettaglio': str(e),
            'codice': 'DB_ERROR'
        }), 500
    finally:
        conn.close()

    return jsonify({
        'messaggio': 'Assenza registrata con successo.',
        'assenza_id': assenza_id
    }), 201