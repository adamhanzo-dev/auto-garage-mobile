"""
Accès à la base de données (SQLite).
Le fichier garage.db est créé automatiquement à côté du programme.
"""
import os
import sqlite3

DOSSIER = os.path.dirname(os.path.abspath(__file__))
FICHIER = os.path.join(DOSSIER, "garage.db")

TVA = 0.19


def connecter():
    cn = sqlite3.connect(FICHIER)
    cn.row_factory = sqlite3.Row
    cn.execute("PRAGMA foreign_keys = ON")
    return cn


def lire(sql, args=()):
    """Exécute un SELECT et renvoie une liste de dictionnaires."""
    cn = connecter()
    lignes = [dict(r) for r in cn.execute(sql, args).fetchall()]
    cn.close()
    return lignes


def ecrire(sql, args=()):
    """Exécute un INSERT / UPDATE."""
    cn = connecter()
    cn.execute(sql, args)
    cn.commit()
    cn.close()


# ---------------------------------------------------------------
# Création des tables + données de départ
# ---------------------------------------------------------------
def creer_base():
    cn = connecter()
    cn.executescript("""
    CREATE TABLE IF NOT EXISTS clients (
        id    INTEGER PRIMARY KEY AUTOINCREMENT,
        name  TEXT NOT NULL,
        phone TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS vehicles (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        plate     TEXT NOT NULL UNIQUE,
        label     TEXT NOT NULL,
        km        INTEGER NOT NULL DEFAULT 0,
        client_id INTEGER NOT NULL REFERENCES clients(id)
    );

    CREATE TABLE IF NOT EXISTS parts (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        ref     TEXT NOT NULL UNIQUE,
        name    TEXT NOT NULL,
        qty     INTEGER NOT NULL DEFAULT 0 CHECK (qty >= 0),   -- le stock ne peut pas être négatif
        min_qty INTEGER NOT NULL DEFAULT 0,
        price   REAL NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS orders (
        n           INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id  INTEGER NOT NULL REFERENCES vehicles(id),
        description TEXT NOT NULL,
        mechanic    TEXT NOT NULL,
        status      TEXT NOT NULL DEFAULT 'wait' CHECK (status IN ('wait', 'prog', 'done')),
        labor       REAL NOT NULL DEFAULT 0,
        created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS order_parts (
        order_n INTEGER NOT NULL REFERENCES orders(n),
        part_id INTEGER NOT NULL REFERENCES parts(id),
        qty     INTEGER NOT NULL CHECK (qty > 0),
        PRIMARY KEY (order_n, part_id)
    );

    CREATE TABLE IF NOT EXISTS invoices (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        order_n INTEGER NOT NULL UNIQUE REFERENCES orders(n),  -- une seule facture par réparation
        paid    INTEGER NOT NULL DEFAULT 0,
        paid_at TEXT
    );
    """)

    # données de départ (seulement si la base est vide)
    nb = cn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
    if nb == 0:
        cn.executescript("""
        INSERT INTO clients (name, phone) VALUES
          ('Ahmed Benali', '0550 12 34 56'),
          ('Leila Haddad', '0661 98 76 54'),
          ('Sofiane Merabet', '0770 45 21 08');

        INSERT INTO vehicles (plate, label, km, client_id) VALUES
          ('12345-116-16', 'Renault Clio', 84500, 1),
          ('67890-117-31', 'Peugeot 208', 41200, 2),
          ('24680-118-09', 'Dacia Duster', 120300, 3),
          ('13579-116-16', 'Toyota Yaris', 66000, 1);

        INSERT INTO parts (ref, name, qty, min_qty, price) VALUES
          ('FH-01', 'Filtre à huile', 12, 5, 900),
          ('PL-02', 'Plaquettes de frein', 4, 5, 4200),
          ('HU-5W', 'Huile 5W30 (L)', 30, 10, 1100),
          ('BT-60', 'Batterie 60Ah', 2, 3, 12500);

        INSERT INTO orders (vehicle_id, description, mechanic, status, labor) VALUES
          (1, 'Vidange + freins',         'Yacine', 'done', 5000),
          (2, 'Bruit moteur',             'Yacine', 'prog', 4500),
          (3, 'Courroie de distribution', 'Yacine', 'wait', 8000),
          (4, 'Changement plaquettes',    'Bilal',  'done', 3500);

        INSERT INTO order_parts (order_n, part_id, qty) VALUES
          (1, 1, 1), (1, 3, 4), (2, 1, 1), (4, 2, 1);

        INSERT INTO invoices (order_n, paid, paid_at) VALUES
          (1, 1, datetime('now')),
          (4, 0, NULL);
        """)
        cn.commit()
    cn.close()


# ---------------------------------------------------------------
# Clients et véhicules
# ---------------------------------------------------------------
def liste_clients():
    clients = lire("SELECT * FROM clients ORDER BY name")
    for c in clients:
        c["vehicules"] = lire("SELECT * FROM vehicles WHERE client_id = ?", (c["id"],))
    return clients


def liste_vehicules():
    return lire("""SELECT v.id, v.plate, v.label, c.name AS client
                   FROM vehicles v JOIN clients c ON c.id = v.client_id
                   ORDER BY v.plate""")


# ---------------------------------------------------------------
# Réparations
# ---------------------------------------------------------------
def une_reparation(n):
    o = lire("""SELECT o.n, o.description, o.mechanic, o.status, o.labor,
                       v.plate, v.label, c.name AS client
                FROM orders o
                JOIN vehicles v ON v.id = o.vehicle_id
                JOIN clients c  ON c.id = v.client_id
                WHERE o.n = ?""", (n,))[0]
    o["pieces"] = lire("""SELECT p.name, p.price, op.qty, p.price * op.qty AS total
                          FROM order_parts op JOIN parts p ON p.id = op.part_id
                          WHERE op.order_n = ?""", (n,))
    o["ht"] = o["labor"] + sum(p["total"] for p in o["pieces"])
    o["tva"] = o["ht"] * TVA
    o["ttc"] = o["ht"] + o["tva"]
    return o


def liste_reparations():
    numeros = lire("SELECT n FROM orders ORDER BY n DESC")
    return [une_reparation(x["n"]) for x in numeros]


def ajouter_reparation(vehicle_id, description, mecanicien):
    ecrire("INSERT INTO orders (vehicle_id, description, mechanic) VALUES (?, ?, ?)",
           (vehicle_id, description, mecanicien))


def changer_statut(n, statut):
    ecrire("UPDATE orders SET status = ? WHERE n = ?", (statut, n))
    # une facture est créée quand la réparation est terminée
    if statut == "done":
        ecrire("INSERT OR IGNORE INTO invoices (order_n) VALUES (?)", (n,))


# ---------------------------------------------------------------
# Stock
# ---------------------------------------------------------------
def liste_pieces():
    return lire("SELECT * FROM parts ORDER BY name")


def modifier_stock(part_id, difference):
    # la condition empêche le stock de devenir négatif
    ecrire("UPDATE parts SET qty = qty + ? WHERE id = ? AND qty + ? >= 0",
           (difference, part_id, difference))


# ---------------------------------------------------------------
# Factures
# ---------------------------------------------------------------
def liste_factures():
    factures = lire("SELECT * FROM invoices ORDER BY id DESC")
    for f in factures:
        f["reparation"] = une_reparation(f["order_n"])
    return factures


def encaisser(invoice_id):
    ecrire("UPDATE invoices SET paid = 1, paid_at = datetime('now') WHERE id = ? AND paid = 0",
           (invoice_id,))
