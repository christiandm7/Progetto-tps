from flask import Flask, session, request, jsonify
import sqlite3
import re
from datetime import date, datetime

app = Flask(__name__)
app.secret_key = "chiave_segreta"

DB_PATH = "edutrack.db"

# ─── Helper ───────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def valida_data(data_str):
    # Controlla che il formato sia YYYY-MM-DD
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data_str):
        return None
    # Controlla che la data esista davvero (es. no 2026-02-30)
    try:
        data = datetime.strptime(data_str, "%Y-%m-%d")
        return data.date()
    except ValueError:
        return None

def controlla_sessione_e_ruolo():
    # Controlla se l'utente è autenticato
    if "user_id" not in session or "ruolo" not in session:
        messaggio = {"errore": "Non autenticato o sessione scaduta."}
        return messaggio, 401
    # Controlla se l'utente è uno studente
    if session["ruolo"] != "studente":
        messaggio = {"errore": "Accesso riservato agli studenti."}
        return messaggio, 403
    return None, None

def valida_filtri_date(data_inizio_str, data_fine_str):
    oggi = date.today()
    d_inizio = None
    d_fine = None

    # Valida data_inizio se presente
    if data_inizio_str:
        d_inizio = valida_data(data_inizio_str)
        if d_inizio is None:
            messaggio = {"errore": "data_inizio non valida (usa YYYY-MM-DD e una data reale)."}
            return None, None, (messaggio, 400)
        if d_inizio > oggi:
            messaggio = {"errore": "data_inizio non può essere nel futuro."}
            return None, None, (messaggio, 400)

    # Valida data_fine se presente
    if data_fine_str:
        d_fine = valida_data(data_fine_str)
        if d_fine is None:
            messaggio = {"errore": "data_fine non valida (usa YYYY-MM-DD e una data reale)."}
            return None, None, (messaggio, 400)
        if d_fine > oggi:
            messaggio = {"errore": "data_fine non può essere nel futuro."}
            return None, None, (messaggio, 400)

    # Controlla che data_inizio non sia dopo data_fine
    if d_inizio and d_fine:
        if d_inizio > d_fine:
            messaggio = {"errore": "data_inizio non può essere successiva a data_fine."}
            return None, None, (messaggio, 400)

    return d_inizio, d_fine, None


# ─── Endpoint 1: Valutazioni ──────────────────────────────

@app.route("/api/studente/valutazioni", methods=["GET"])
def get_valutazioni():
    # 1. Controlla autenticazione e ruolo
    err, status = controlla_sessione_e_ruolo()
    if err:
        return jsonify(err), status

    # 2. Leggi parametri opzionali
    materia = request.args.get("materia", "").strip()
    if materia == "":
        materia = None

    data_inizio_str = request.args.get("data_inizio", "").strip()
    if data_inizio_str == "":
        data_inizio_str = None

    data_fine_str = request.args.get("data_fine", "").strip()
    if data_fine_str == "":
        data_fine_str = None

    # 3. Valida date
    d_inizio, d_fine, err_date = valida_filtri_date(data_inizio_str, data_fine_str)
    if err_date:
        return jsonify(err_date[0]), err_date[1]

    # 4. Costruisci query con placeholder
    student_id = session["user_id"]
    query = "SELECT * FROM valutazioni WHERE studente_id = ?"
    params = [student_id]

    if materia:
        query = query + " AND materia = ?"
        params.append(materia)
    if d_inizio:
        query = query + " AND data >= ?"
        params.append(str(d_inizio))
    if d_fine:
        query = query + " AND data <= ?"
        params.append(str(d_fine))

    query = query + " ORDER BY data DESC"

    # 5. Esegui query
    conn = get_db()
    try:
        rows = conn.execute(query, params).fetchall()
        risultato = []
        for r in rows:
            risultato.append(dict(r))
    finally:
        conn.close()

    return jsonify(risultato), 200


# ─── Endpoint 2: Assenze ──────────────────────────────────

@app.route("/api/studente/assenze", methods=["GET"])
def get_assenze():
    # 1. Controlla autenticazione e ruolo
    err, status = controlla_sessione_e_ruolo()
    if err:
        return jsonify(err), status

    # 2. Leggi parametri opzionali
    materia = request.args.get("materia", "").strip()
    if materia == "":
        materia = None

    data_inizio_str = request.args.get("data_inizio", "").strip()
    if data_inizio_str == "":
        data_inizio_str = None

    data_fine_str = request.args.get("data_fine", "").strip()
    if data_fine_str == "":
        data_fine_str = None

    # 3. Valida date
    d_inizio, d_fine, err_date = valida_filtri_date(data_inizio_str, data_fine_str)
    if err_date:
        return jsonify(err_date[0]), err_date[1]

    # 4. Costruisci query con placeholder
    student_id = session["user_id"]
    query = "SELECT * FROM assenze WHERE studente_id = ?"
    params = [student_id]

    if materia:
        query = query + " AND materia = ?"
        params.append(materia)
    if d_inizio:
        query = query + " AND data >= ?"
        params.append(str(d_inizio))
    if d_fine:
        query = query + " AND data <= ?"
        params.append(str(d_fine))

    query = query + " ORDER BY data DESC"

    # 5. Esegui query
    conn = get_db()
    try:
        rows = conn.execute(query, params).fetchall()
        risultato = []
        for r in rows:
            risultato.append(dict(r))
    finally:
        conn.close()

    return jsonify(risultato), 200