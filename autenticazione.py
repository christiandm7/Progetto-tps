# auth.py
from flask import Blueprint, request, session, jsonify
from functools import wraps
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

auth = Blueprint("auth", __name__)
DB_PATH = "edutrack.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Decoratori RBAC 

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Non autenticato"}), 401
        return f(*args, **kwargs)
    return wrapper


def role_required(*ruoli):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return jsonify({"error": "Non autenticato"}), 401
            if session.get("ruolo") not in ruoli:
                return jsonify({"error": "Accesso negato"}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ── registrazione

@auth.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    nome     = data.get("nome")
    cognome  = data.get("cognome")
    ruolo    = data.get("ruolo")

    if not all([username, password, nome, cognome, ruolo]):
        return jsonify({"error": "Campi mancanti"}), 400

    if ruolo not in ("docente", "studente"):
        return jsonify({"error": "Ruolo non valido"}), 400

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO utenti (username, password_hash, ruolo, nome, cognome) VALUES (?,?,?,?,?)",
            (username, generate_password_hash(password), ruolo, nome, cognome)
        )
        conn.commit()
        return jsonify({"message": "Utente creato"}), 201

    except sqlite3.IntegrityError:
        return jsonify({"error": "Username già esistente"}), 409

    finally:
        conn.close()


# ── login

@auth.route("/api/login", methods=["POST"])
def login():
    data     = request.get_json()
    username = data.get("username")
    password = data.get("password")

    conn = get_db()
    try:
        utente = conn.execute(
            "SELECT * FROM utenti WHERE username = ?", (username,)
        ).fetchone()

        if not utente or not check_password_hash(utente["password_hash"], password):
            return jsonify({"error": "Credenziali non valide"}), 401

        session["user_id"] = utente["id"]
        session["ruolo"]   = utente["ruolo"]

        return jsonify({
            "message": "Login effettuato",
            "utente": {
                "id":      utente["id"],
                "nome":    utente["nome"],
                "cognome": utente["cognome"],
                "ruolo":   utente["ruolo"]
            }
        }), 200

    finally:
        conn.close()


# ── logout

@auth.route("/api/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    return jsonify({"message": "Logout effettuato"}), 200


# ── esempio rotta protetta

@auth.route("/api/me", methods=["GET"])
@login_required
def me():
    conn = get_db()
    try:
        utente = conn.execute(
            "SELECT id, username, nome, cognome, ruolo FROM utenti WHERE id = ?",
            (session["user_id"],)
        ).fetchone()
        return jsonify(dict(utente)), 200
    finally:
        conn.close()


# ── Esempio rotta solo docente

@auth.route("/api/docente/test", methods=["GET"])
@role_required("docente")
def docente_test():
    return jsonify({"message": "Accesso docente confermato"}), 200