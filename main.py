"""
Garage Auto - application de bureau (Flet + SQLite)

Installation : pip install flet
Lancer       : python main.py
"""
import flet as ft
import db

MECANICIENS = ["Yacine", "Bilal"]

# statut -> (texte affiché, couleur)
STATUTS = {
    "wait": ("En attente", "orange"),
    "prog": ("En cours", "blue"),
    "done": ("Terminée", "green"),
}


def da(montant):
    """Format : 12 500 DA"""
    return f"{round(montant):,}".replace(",", " ") + " DA"


def main(page: ft.Page):
    page.title = "Garage Auto"
    page.window.width = 1100
    page.window.height = 720
    page.padding = 0
    page.theme_mode = ft.ThemeMode.LIGHT

    zone = ft.Container(expand=True, padding=20)   # zone où s'affiche la page choisie
    page_active = {"index": 0}

    # ------------------------------------------------------------
    # Petites fonctions utiles
    # ------------------------------------------------------------
    def message(texte):
        page.open(ft.SnackBar(ft.Text(texte)))

    def badge(statut):
        texte, couleur = STATUTS[statut]
        return ft.Container(
            content=ft.Text(texte, color="white", size=12),
            bgcolor=couleur, padding=ft.padding.symmetric(horizontal=10, vertical=3),
            border_radius=12)

    def carte(titre, valeur, icone, couleur):
        return ft.Card(content=ft.Container(
            width=230, padding=15,
            content=ft.Row([
                ft.Icon(icone, color=couleur, size=36),
                ft.Column([ft.Text(titre, size=13), ft.Text(valeur, size=22, weight="bold")], spacing=2),
            ])))

    # ------------------------------------------------------------
    # Page 1 : Accueil
    # ------------------------------------------------------------
    def page_accueil():
        reparations = db.liste_reparations()
        factures = db.liste_factures()
        pieces = db.liste_pieces()

        en_cours = len([o for o in reparations if o["status"] == "prog"])
        en_attente = len([o for o in reparations if o["status"] == "wait"])
        encaisse = sum(f["reparation"]["ttc"] for f in factures if f["paid"])

        cartes = ft.Row([
            carte("En cours", str(en_cours), ft.Icons.BUILD, "blue"),
            carte("En attente", str(en_attente), ft.Icons.SCHEDULE, "orange"),
            carte("Clients", str(len(db.liste_clients())), ft.Icons.PEOPLE, "purple"),
            carte("Encaissé", da(encaisse), ft.Icons.PAYMENTS, "green"),
        ], wrap=True)

        contenu = [ft.Text("Accueil", size=28, weight="bold"), cartes]

        # alerte stock bas
        bas = [p["name"] for p in pieces if p["qty"] <= p["min_qty"]]
        if bas:
            contenu.append(ft.Container(
                bgcolor="#FEE2E2", padding=15, border_radius=10,
                content=ft.Row([
                    ft.Icon(ft.Icons.WARNING_AMBER, color="red"),
                    ft.Text("Stock bas : " + ", ".join(bas), color="red"),
                ])))

        # 3 dernières réparations
        contenu.append(ft.Text("Dernières réparations", size=18, weight="bold"))
        for o in reparations[:3]:
            contenu.append(ft.Card(content=ft.ListTile(
                leading=ft.Icon(ft.Icons.BUILD_CIRCLE),
                title=ft.Text(f"#{o['n']} - {o['label']}"),
                subtitle=ft.Text(f"{o['description']} ({o['client']})"),
                trailing=badge(o["status"]),
            )))

        return ft.Column(contenu, scroll=ft.ScrollMode.AUTO, spacing=15)

    # ------------------------------------------------------------
    # Page 2 : Réparations
    # ------------------------------------------------------------
    def page_reparations():
        tableau = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("N°")),
                ft.DataColumn(ft.Text("Véhicule")),
                ft.DataColumn(ft.Text("Client")),
                ft.DataColumn(ft.Text("Description")),
                ft.DataColumn(ft.Text("Mécanicien")),
                ft.DataColumn(ft.Text("Statut")),
                ft.DataColumn(ft.Text("Total TTC"), numeric=True),
            ],
            rows=[],
        )
        recherche = ft.TextField(label="Rechercher...", prefix_icon=ft.Icons.SEARCH, width=300)
        filtre = ft.Dropdown(
            label="Statut", width=200, value="tous",
            options=[ft.dropdown.Option("tous", "Tous")] +
                    [ft.dropdown.Option(cle, val[0]) for cle, val in STATUTS.items()])

        def remplir():
            texte = (recherche.value or "").lower()
            lignes = []
            for o in db.liste_reparations():
                if filtre.value != "tous" and o["status"] != filtre.value:
                    continue
                contenu = (o["description"] + o["label"] + o["plate"] + o["client"] + str(o["n"])).lower()
                if texte not in contenu:
                    continue
                lignes.append(ft.DataRow(
                    on_select_changed=lambda e, o=o: detail_reparation(o["n"]),
                    cells=[
                        ft.DataCell(ft.Text(str(o["n"]))),
                        ft.DataCell(ft.Text(o["label"])),
                        ft.DataCell(ft.Text(o["client"])),
                        ft.DataCell(ft.Text(o["description"])),
                        ft.DataCell(ft.Text(o["mechanic"])),
                        ft.DataCell(badge(o["status"])),
                        ft.DataCell(ft.Text(da(o["ttc"]))),
                    ]))
            tableau.rows = lignes

        def quand_change(e):
            remplir()
            tableau.update()

        recherche.on_change = quand_change
        filtre.on_change = quand_change
        remplir()

        entete = ft.Row([
            ft.Text("Réparations", size=28, weight="bold", expand=True),
            ft.ElevatedButton("Nouvel ordre", icon=ft.Icons.ADD, on_click=nouvel_ordre),
        ])
        return ft.Column([entete, ft.Row([recherche, filtre]),
                          ft.Column([tableau], scroll=ft.ScrollMode.AUTO, expand=True)],
                         expand=True, spacing=15)

    def detail_reparation(n):
        o = db.une_reparation(n)

        def changer(statut):
            db.changer_statut(n, statut)
            page.close(fenetre)
            message("Statut modifié")
            afficher(page_active["index"])

        lignes = [ft.Text(f"Main-d'œuvre : {da(o['labor'])}")]
        for p in o["pieces"]:
            lignes.append(ft.Text(f"{p['name']} x{p['qty']} : {da(p['total'])}"))
        lignes += [
            ft.Divider(),
            ft.Text(f"Total HT : {da(o['ht'])}"),
            ft.Text(f"TVA 19 % : {da(o['tva'])}"),
            ft.Text(f"Total TTC : {da(o['ttc'])}", weight="bold", size=16),
        ]

        boutons_statut = ft.Row([
            ft.OutlinedButton(texte, on_click=lambda e, cle=cle: changer(cle),
                              disabled=(o["status"] == cle))
            for cle, (texte, couleur) in STATUTS.items()
        ], wrap=True)

        fenetre = ft.AlertDialog(
            title=ft.Text(f"#{o['n']} - {o['label']}"),
            content=ft.Container(width=420, content=ft.Column([
                ft.Text(f"Plaque : {o['plate']}"),
                ft.Text(f"Client : {o['client']}"),
                ft.Text(f"Mécanicien : {o['mechanic']}"),
                ft.Text(o["description"], italic=True),
                ft.Text("Changer le statut :", weight="bold"),
                boutons_statut,
                ft.Divider(),
                *lignes,
            ], tight=True, scroll=ft.ScrollMode.AUTO)),
            actions=[ft.TextButton("Fermer", on_click=lambda e: page.close(fenetre))],
        )
        page.open(fenetre)

    def nouvel_ordre(e):
        vehicules = db.liste_vehicules()
        choix_vehicule = ft.Dropdown(
            label="Véhicule", value=str(vehicules[0]["id"]),
            options=[ft.dropdown.Option(str(v["id"]), f"{v['plate']} - {v['label']} ({v['client']})")
                     for v in vehicules])
        choix_meca = ft.Dropdown(
            label="Mécanicien", value=MECANICIENS[0],
            options=[ft.dropdown.Option(m) for m in MECANICIENS])
        description = ft.TextField(label="Description", autofocus=True)

        def creer(e):
            if not description.value or not description.value.strip():
                description.error_text = "Décrivez la réparation"
                description.update()
                return
            db.ajouter_reparation(int(choix_vehicule.value), description.value.strip(), choix_meca.value)
            page.close(fenetre)
            message("Ordre créé")
            afficher(page_active["index"])

        fenetre = ft.AlertDialog(
            title=ft.Text("Nouvel ordre de réparation"),
            content=ft.Container(width=420, content=ft.Column(
                [choix_vehicule, choix_meca, description], tight=True)),
            actions=[ft.TextButton("Annuler", on_click=lambda e: page.close(fenetre)),
                     ft.ElevatedButton("Créer", on_click=creer)],
        )
        page.open(fenetre)

    # ------------------------------------------------------------
    # Page 3 : Clients
    # ------------------------------------------------------------
    def page_clients():
        liste = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
        recherche = ft.TextField(label="Rechercher un client...", prefix_icon=ft.Icons.SEARCH, width=300)

        def remplir():
            texte = (recherche.value or "").lower()
            liste.controls = []
            for c in db.liste_clients():
                vehicules = "".join(v["plate"] + v["label"] for v in c["vehicules"])
                if texte not in (c["name"] + c["phone"] + vehicules).lower():
                    continue
                liste.controls.append(ft.Card(content=ft.ExpansionTile(
                    leading=ft.Icon(ft.Icons.PERSON),
                    title=ft.Text(c["name"], weight="bold"),
                    subtitle=ft.Text(f"{c['phone']} - {len(c['vehicules'])} véhicule(s)"),
                    controls=[ft.ListTile(
                        leading=ft.Icon(ft.Icons.DIRECTIONS_CAR),
                        title=ft.Text(v["label"]),
                        subtitle=ft.Text(f"{v['plate']} - {v['km']} km"),
                    ) for v in c["vehicules"]],
                )))

        def quand_change(e):
            remplir()
            liste.update()

        recherche.on_change = quand_change
        remplir()
        return ft.Column([ft.Text("Clients", size=28, weight="bold"), recherche, liste],
                         expand=True, spacing=15)

    # ------------------------------------------------------------
    # Page 4 : Stock
    # ------------------------------------------------------------
    def page_stock():
        def modifier(part_id, difference):
            db.modifier_stock(part_id, difference)
            afficher(page_active["index"])

        lignes = []
        for p in db.liste_pieces():
            bas = p["qty"] <= p["min_qty"]
            lignes.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(p["ref"])),
                ft.DataCell(ft.Text(p["name"])),
                ft.DataCell(ft.Text(da(p["price"]))),
                ft.DataCell(ft.Text(str(p["qty"]), color="red" if bas else "green", weight="bold")),
                ft.DataCell(ft.Text(str(p["min_qty"]))),
                ft.DataCell(ft.Text("Stock bas" if bas else "OK", color="red" if bas else "green")),
                ft.DataCell(ft.Row([
                    ft.IconButton(ft.Icons.REMOVE, on_click=lambda e, i=p["id"]: modifier(i, -1)),
                    ft.IconButton(ft.Icons.ADD, on_click=lambda e, i=p["id"]: modifier(i, 1)),
                ])),
            ]))

        tableau = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Réf.")),
                ft.DataColumn(ft.Text("Pièce")),
                ft.DataColumn(ft.Text("Prix"), numeric=True),
                ft.DataColumn(ft.Text("Quantité"), numeric=True),
                ft.DataColumn(ft.Text("Seuil"), numeric=True),
                ft.DataColumn(ft.Text("État")),
                ft.DataColumn(ft.Text("Ajuster")),
            ],
            rows=lignes,
        )
        return ft.Column([ft.Text("Stock", size=28, weight="bold"), tableau],
                         scroll=ft.ScrollMode.AUTO, spacing=15)

    # ------------------------------------------------------------
    # Page 5 : Factures
    # ------------------------------------------------------------
    def page_factures():
        factures = db.liste_factures()
        total_paye = sum(f["reparation"]["ttc"] for f in factures if f["paid"])
        total_du = sum(f["reparation"]["ttc"] for f in factures if not f["paid"])

        lignes = []
        for f in factures:
            o = f["reparation"]
            if f["paid"]:
                action = ft.Icon(ft.Icons.LOCK, color="grey")
            else:
                action = ft.ElevatedButton("Encaisser", icon=ft.Icons.PAYMENTS,
                                           on_click=lambda e, f=f: fenetre_paiement(f))
            lignes.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(o["n"]))),
                ft.DataCell(ft.Text(o["client"])),
                ft.DataCell(ft.Text(o["label"])),
                ft.DataCell(ft.Text(da(o["ttc"]))),
                ft.DataCell(ft.Text("Payée" if f["paid"] else "Impayée",
                                    color="green" if f["paid"] else "orange")),
                ft.DataCell(action),
            ]))

        tableau = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Facture N°")),
                ft.DataColumn(ft.Text("Client")),
                ft.DataColumn(ft.Text("Véhicule")),
                ft.DataColumn(ft.Text("Montant TTC"), numeric=True),
                ft.DataColumn(ft.Text("État")),
                ft.DataColumn(ft.Text("")),
            ],
            rows=lignes,
        )
        resume = ft.Row([
            carte("Encaissé", da(total_paye), ft.Icons.CHECK_CIRCLE, "green"),
            carte("À encaisser", da(total_du), ft.Icons.SCHEDULE, "orange"),
        ])
        return ft.Column([ft.Text("Factures", size=28, weight="bold"), resume, tableau],
                         scroll=ft.ScrollMode.AUTO, spacing=15)

    def fenetre_paiement(facture):
        mode = ft.RadioGroup(value="Espèces", content=ft.Column([
            ft.Radio(value="Espèces", label="Espèces"),
            ft.Radio(value="Carte", label="Carte"),
            ft.Radio(value="Virement", label="Virement"),
        ]))

        def valider(e):
            db.encaisser(facture["id"])
            page.close(fenetre)
            message(f"Paiement enregistré ({mode.value})")
            afficher(page_active["index"])

        fenetre = ft.AlertDialog(
            title=ft.Text("Mode de paiement"),
            content=ft.Column([
                ft.Text(f"Montant à encaisser : {da(facture['reparation']['ttc'])}"),
                mode,
            ], tight=True),
            actions=[ft.TextButton("Annuler", on_click=lambda e: page.close(fenetre)),
                     ft.ElevatedButton("Valider", on_click=valider)],
        )
        page.open(fenetre)

    # ------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------
    pages = [page_accueil, page_reparations, page_clients, page_stock, page_factures]

    def afficher(index):
        page_active["index"] = index
        zone.content = pages[index]()
        page.update()

    def ecran_principal():
        menu = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=100,
            leading=ft.Column([
                ft.Icon(ft.Icons.CAR_REPAIR, size=36, color="indigo"),
                ft.Text("Garage Auto", weight="bold"),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            destinations=[
                ft.NavigationRailDestination(icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icons.HOME, label="Accueil"),
                ft.NavigationRailDestination(icon=ft.Icons.BUILD_OUTLINED, selected_icon=ft.Icons.BUILD, label="Réparations"),
                ft.NavigationRailDestination(icon=ft.Icons.PEOPLE_OUTLINE, selected_icon=ft.Icons.PEOPLE, label="Clients"),
                ft.NavigationRailDestination(icon=ft.Icons.INVENTORY_2_OUTLINED, selected_icon=ft.Icons.INVENTORY_2, label="Stock"),
                ft.NavigationRailDestination(icon=ft.Icons.RECEIPT_LONG_OUTLINED, selected_icon=ft.Icons.RECEIPT_LONG, label="Factures"),
            ],
            trailing=ft.IconButton(ft.Icons.LOGOUT, tooltip="Déconnexion",
                                   on_click=lambda e: ecran_connexion()),
            on_change=lambda e: afficher(e.control.selected_index),
        )
        page.clean()
        page.add(ft.Row([menu, ft.VerticalDivider(width=1), zone], expand=True))
        afficher(0)

    # ------------------------------------------------------------
    # Écran de connexion (pour l'affichage seulement, aucune vérification)
    # ------------------------------------------------------------
    def ecran_connexion():
        utilisateur = ft.TextField(label="Nom d'utilisateur", prefix_icon=ft.Icons.PERSON, autofocus=True)
        mot_de_passe = ft.TextField(label="Mot de passe", prefix_icon=ft.Icons.LOCK,
                                    password=True, can_reveal_password=True)
        erreur = ft.Text("", color="red")

        def se_connecter(e):
            if not utilisateur.value or not mot_de_passe.value:
                erreur.value = "Veuillez remplir les deux champs."
                page.update()
                return
            ecran_principal()

        mot_de_passe.on_submit = se_connecter

        formulaire = ft.Container(
            width=380, padding=30, border_radius=16, bgcolor="white",
            shadow=ft.BoxShadow(blur_radius=20, color="#33000000"),
            content=ft.Column([
                ft.Icon(ft.Icons.CAR_REPAIR, size=50, color="indigo"),
                ft.Text("Garage Auto", size=28, weight="bold"),
                ft.Text("Connectez-vous pour accéder à l'atelier", size=13, color="grey"),
                ft.Container(height=10),
                utilisateur,
                mot_de_passe,
                erreur,
                ft.ElevatedButton("Se connecter", icon=ft.Icons.LOGIN, on_click=se_connecter, width=320, height=45),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True, spacing=12))

        page.clean()
        page.add(ft.Container(content=formulaire, expand=True, alignment=ft.alignment.center,
                              bgcolor="#EEF0FF"))

    ecran_connexion()


db.creer_base()
ft.app(target=main)
