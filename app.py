import json
import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

st.set_page_config(page_title="Inventaire boissons", page_icon="🥤", layout="wide")

# ---------------------------------------------------------------------------
# Réglages
# ---------------------------------------------------------------------------
DOSSIER = Path(__file__).parent
FICHIER_INVENTAIRE = DOSSIER / "inventaire.csv"
FICHIER_HISTORIQUE = DOSSIER / "historique.csv"
ONGLET_INVENTAIRE = "Inventaire"
ONGLET_HISTORIQUE = "Historique"
FUSEAU = ZoneInfo("Europe/Paris")

# Pour ajouter ou renommer un stand, il suffit de modifier cette liste.
STANDS = ["CDJ", "Bouillon", "Piazza", "Cafète"]

# Données de départ, reprises du Google Sheet d'origine.
# Elles ne servent qu'au tout premier lancement, quand l'inventaire est encore vide.
# Ordre des quantités : CDJ, Bouillon, Piazza, Cafète
DONNEES_DEPART = {
    "Coca Cola": [12, 33, 15, 9],
    "Coca Zero": [13, 54, 0, 92],
    "Perrier": [10, 11, 0, 0],
    "Eau Neuve": [15, 0, 20, 0],
    "Thé vert gingembre": [0, 0, 0, 0],
    "Gingembre": [0, 0, 0, 0],
    "Limonade": [0, 0, 0, 0],
    "Pêche bio": [0, 0, 0, 0],
    "Vita coco": [0, 0, 0, 0],
    "Bahia 1": [0, 0, 0, 0],
    "Bahia 2": [0, 0, 0, 0],
    "Bahia 3": [0, 0, 0, 0],
    "Jomo 1": [0, 0, 0, 0],
    "Jomo 2": [0, 0, 0, 0],
    "Jomo 3": [2, 0, 0, 0],
    "Jomo 4": [0, 0, 0, 0],
    "Yaourt Nature": [0, 0, 0, 0],
    "Yaourt Vanille": [0, 0, 0, 0],
    "Yaourt Fraise": [0, 0, 0, 0],
    "Yaourt Abricot": [0, 0, 0, 0],
    "Yaourt Framboise": [0, 0, 0, 0],
    "Yaourt Citron": [0, 0, 0, 0],
    "Yaourt Poire": [0, 0, 0, 0],
}

COLONNES_INVENTAIRE = ["Boisson"] + STANDS
COLONNES_HISTORIQUE = ["Date", "Par", "Stand", "Boisson", "Avant", "Après", "Écart"]


# ---------------------------------------------------------------------------
# Secrets (clé du robot Google, codes d'accès)
# Ils sont saisis dans « Settings → Secrets » sur Streamlit Cloud, jamais sur GitHub.
# Sans secrets (sur ton PC), l'app fonctionne avec des fichiers CSV locaux et sans code.
# ---------------------------------------------------------------------------
def charger_secrets():
    try:
        verifier = getattr(st.secrets, "load_if_toml_exists", None)
        if verifier is None or not verifier():
            return {}
        return dict(st.secrets)
    except Exception:
        return {}


SECRETS = charger_secrets()
MODE_SHEETS = bool(SECRETS.get("gcp_json")) and bool(SECRETS.get("sheet_id"))
CODE_EQUIPE = str(SECRETS.get("code_equipe", "")).strip()
CODE_ADMIN = str(SECRETS.get("code_admin", "")).strip()

if MODE_SHEETS:
    import gspread


# ---------------------------------------------------------------------------
# Accès au Google Sheet
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def classeur():
    infos = json.loads(SECRETS["gcp_json"])
    client = gspread.service_account_from_dict(infos)
    return client.open_by_key(str(SECRETS["sheet_id"]).strip())


@st.cache_resource(show_spinner=False)
def onglet(nom, entetes):
    # Renvoie l'onglet demandé ; le crée avec ses en-têtes s'il n'existe pas encore.
    sh = classeur()
    try:
        return sh.worksheet(nom)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=nom, rows=500, cols=len(entetes))
        ws.update(range_name="A1", values=[list(entetes)])
        return ws


def en_listes(df):
    # Convertit un tableau pandas en listes de valeurs Python simples (ce que Google accepte)
    return [[v.item() if hasattr(v, "item") else v for v in ligne] for ligne in df.itertuples(index=False)]


# ---------------------------------------------------------------------------
# Lecture et écriture : Google Sheet en ligne, fichiers CSV sur ton PC
# ---------------------------------------------------------------------------
def lire_table(nom_onglet, fichier, entetes):
    if MODE_SHEETS:
        valeurs = onglet(nom_onglet, tuple(entetes)).get_all_values()
        if not valeurs or not any(valeurs[0]):
            return None
        return pd.DataFrame(valeurs[1:], columns=valeurs[0])
    if fichier.exists():
        return pd.read_csv(fichier)
    return None


def charger_inventaire():
    df = lire_table(ONGLET_INVENTAIRE, FICHIER_INVENTAIRE, COLONNES_INVENTAIRE)
    if df is None or "Boisson" not in df.columns or df.empty:
        lignes = [[boisson] + quantites for boisson, quantites in DONNEES_DEPART.items()]
        df = pd.DataFrame(lignes, columns=COLONNES_INVENTAIRE)
        sauvegarder_inventaire(df)
    for stand in STANDS:
        if stand not in df.columns:
            df[stand] = 0
    df = df[COLONNES_INVENTAIRE].copy()
    df["Boisson"] = df["Boisson"].astype(str).str.strip()
    df = df[df["Boisson"] != ""]
    df[STANDS] = df[STANDS].apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)
    return df.reset_index(drop=True)


def sauvegarder_inventaire(df):
    df = df[COLONNES_INVENTAIRE]
    if MODE_SHEETS:
        ws = onglet(ONGLET_INVENTAIRE, tuple(COLONNES_INVENTAIRE))
        nb_lignes_avant = len(ws.col_values(1))
        valeurs = [COLONNES_INVENTAIRE] + en_listes(df)
        ws.update(range_name="A1", values=valeurs)
        if nb_lignes_avant > len(valeurs):
            # Efface les lignes restantes si une boisson a été supprimée
            ws.batch_clear([f"A{len(valeurs) + 1}:Z{nb_lignes_avant}"])
    else:
        df.to_csv(FICHIER_INVENTAIRE, index=False)
    st.cache_data.clear()


def charger_historique():
    df = lire_table(ONGLET_HISTORIQUE, FICHIER_HISTORIQUE, COLONNES_HISTORIQUE)
    if df is None or df.empty:
        return pd.DataFrame(columns=COLONNES_HISTORIQUE)
    # Les anciennes lignes, enregistrées avant l'identification, n'ont pas de colonne « Par »
    if "Par" not in df.columns:
        df["Par"] = "—"
    for colonne in COLONNES_HISTORIQUE:
        if colonne not in df.columns:
            df[colonne] = ""
    df = df[COLONNES_HISTORIQUE].copy()
    for colonne in ["Avant", "Après", "Écart"]:
        df[colonne] = pd.to_numeric(df[colonne], errors="coerce")
    return df


def ajouter_historique(lignes):
    if not lignes:
        return
    nouvelles = pd.DataFrame(lignes, columns=COLONNES_HISTORIQUE)
    if MODE_SHEETS:
        ws = onglet(ONGLET_HISTORIQUE, tuple(COLONNES_HISTORIQUE))
        if not ws.row_values(1):
            ws.update(range_name="A1", values=[COLONNES_HISTORIQUE])
        # append_rows ajoute à la suite : deux personnes peuvent enregistrer en même temps
        ws.append_rows(en_listes(nouvelles), value_input_option="RAW")
    else:
        historique = charger_historique()
        if historique.empty:
            historique = nouvelles
        else:
            historique = pd.concat([historique, nouvelles], ignore_index=True)
        historique.to_csv(FICHIER_HISTORIQUE, index=False)
    st.cache_data.clear()


# Versions « en cache » pour l'affichage : on relit Google au plus toutes les 15 secondes,
# sauf juste après un enregistrement (le cache est alors vidé).
@st.cache_data(ttl=15, show_spinner=False)
def inventaire_pour_affichage():
    return charger_inventaire()


@st.cache_data(ttl=15, show_spinner=False)
def historique_pour_affichage():
    return charger_historique()


# ---------------------------------------------------------------------------
# Petites fonctions utiles
# ---------------------------------------------------------------------------
def ligne_historique(stand, boisson, avant, apres):
    maintenant = datetime.now(FUSEAU).strftime("%Y-%m-%d %H:%M")
    return {
        "Date": maintenant,
        "Par": st.session_state.get("utilisateur", "—"),
        "Stand": stand,
        "Boisson": boisson,
        "Avant": int(avant),
        "Après": int(apres),
        "Écart": int(apres) - int(avant),
    }


def vers_csv_excel(df):
    # Point-virgule + encodage utf-8-sig : le fichier s'ouvre proprement dans Excel en français
    return df.to_csv(index=False, sep=";").encode("utf-8-sig")


def enregistrer_et_recharger(message):
    st.session_state["message"] = message
    st.rerun()


# ---------------------------------------------------------------------------
# Vérification de la connexion au Google Sheet
# ---------------------------------------------------------------------------
if MODE_SHEETS:
    try:
        classeur()
    except Exception as erreur:
        st.error(
            "Impossible de se connecter au Google Sheet. Vérifie trois choses : "
            "1) le contenu de gcp_json dans les Secrets est bien le fichier JSON complet ; "
            "2) sheet_id correspond bien à ton Google Sheet ; "
            "3) le Google Sheet est partagé en « Éditeur » avec l'adresse client_email du robot."
        )
        st.caption(f"Détail technique : {type(erreur).__name__} — {erreur}")
        st.stop()

# ---------------------------------------------------------------------------
# Identification : prénom (+ code d'accès si configuré) avant d'afficher l'app
# ---------------------------------------------------------------------------
CODES_ACTIFS = bool(CODE_EQUIPE or CODE_ADMIN)

if "utilisateur" not in st.session_state:
    st.title("🥤 Inventaire des boissons")
    st.subheader("Qui fait l'inventaire ?")
    st.caption("Ton prénom sera noté dans l'historique à chaque modification.")
    with st.form("formulaire_identification"):
        nom_utilisateur = st.text_input("Ton prénom ou identifiant")
        code_saisi = st.text_input("Code d'accès", type="password") if CODES_ACTIFS else ""
        valide = st.form_submit_button("Commencer ➜", type="primary")
    if valide:
        nom_utilisateur = nom_utilisateur.strip()
        code_saisi = code_saisi.strip()
        if len(nom_utilisateur) < 2:
            st.warning("Écris au moins 2 caractères pour ton prénom.")
        elif not CODES_ACTIFS:
            role = "admin"  # sur ton PC, sans code configuré : accès complet
        elif CODE_ADMIN and code_saisi == CODE_ADMIN:
            role = "admin"
        elif CODE_EQUIPE and code_saisi == CODE_EQUIPE:
            role = "equipe"
        else:
            role = None
            st.error("Code d'accès incorrect.")
        if len(nom_utilisateur) >= 2 and (not CODES_ACTIFS or role):
            st.session_state["utilisateur"] = nom_utilisateur
            st.session_state["role"] = role
            st.rerun()
    st.stop()  # tant que personne ne s'est identifié, le reste de l'app ne s'affiche pas

utilisateur = st.session_state["utilisateur"]
est_admin = st.session_state.get("role") == "admin"

# ---------------------------------------------------------------------------
# Chargement des données
# ---------------------------------------------------------------------------
inventaire = inventaire_pour_affichage()
inventaire["Total"] = inventaire[STANDS].sum(axis=1)
historique = historique_pour_affichage()

# ---------------------------------------------------------------------------
# Barre latérale
# ---------------------------------------------------------------------------
st.sidebar.markdown(f"👤 Connecté : **{utilisateur}**" + (" · admin" if est_admin else ""))
if st.sidebar.button("Changer d'utilisateur"):
    del st.session_state["utilisateur"]
    st.session_state.pop("role", None)
    st.rerun()
if st.sidebar.button("🔄 Actualiser les données"):
    st.cache_data.clear()
    st.rerun()
st.sidebar.caption("Actualise pour voir les comptages enregistrés par les autres.")

st.sidebar.divider()
st.sidebar.header("Réglages")
seuil = st.sidebar.number_input("Seuil de stock bas", min_value=0, value=10, step=1)
st.sidebar.caption("Une boisson est en stock bas quand son total (tous stands) est inférieur ou égal à ce seuil.")

if est_admin:
    st.sidebar.divider()
    st.sidebar.download_button(
        "⬇️ Télécharger l'inventaire",
        data=vers_csv_excel(inventaire),
        file_name="inventaire.csv",
        mime="text/csv",
    )
    st.sidebar.caption(
        "Stockage : Google Sheet ✅" if MODE_SHEETS else "Stockage : fichiers locaux (mode test sur ton PC)"
    )

# ---------------------------------------------------------------------------
# En-tête
# ---------------------------------------------------------------------------
st.title("🥤 Inventaire des boissons")
if not historique.empty:
    derniere = historique.sort_values("Date").iloc[-1]
    st.caption(f"Dernière modification : {derniere['Date']} par {derniere['Par']}")

if "message" in st.session_state:
    st.success(st.session_state.pop("message"))


# ---------------------------------------------------------------------------
# Onglet 1 : vue d'ensemble
# ---------------------------------------------------------------------------
def afficher_vue_ensemble():
    ruptures = inventaire[inventaire["Total"] == 0]
    stock_bas = inventaire[(inventaire["Total"] > 0) & (inventaire["Total"] <= seuil)]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Unités en stock", int(inventaire["Total"].sum()))
    c2.metric("Références", len(inventaire))
    c3.metric("En rupture", len(ruptures))
    c4.metric("Stock bas", len(stock_bas))

    st.subheader("Stock par stand")
    colonnes_stands = st.columns(len(STANDS))
    for colonne, stand in zip(colonnes_stands, STANDS):
        colonne.metric(stand, int(inventaire[stand].sum()))

    st.subheader("Stock de chaque boisson, par stand")
    st.caption("Toutes les boissons sont affichées : une colonne vide = boisson en rupture.")
    st.bar_chart(inventaire.set_index("Boisson")[STANDS], height=450)

    gauche, droite = st.columns(2)
    with gauche:
        st.subheader("🔴 En rupture")
        if ruptures.empty:
            st.success("Aucune boisson en rupture.")
        else:
            st.error(", ".join(ruptures["Boisson"]))
    with droite:
        st.subheader("🟠 Stock bas")
        if stock_bas.empty:
            st.success("Aucune boisson en stock bas.")
        else:
            st.warning(", ".join(f"{b} ({t})" for b, t in zip(stock_bas["Boisson"], stock_bas["Total"])))

    st.subheader("Détail complet")
    total_max = max(int(inventaire["Total"].max()), 1)
    st.dataframe(
        inventaire,
        hide_index=True,
        column_config={
            "Total": st.column_config.ProgressColumn("Total", min_value=0, max_value=total_max, format="%d"),
        },
    )


# ---------------------------------------------------------------------------
# Onglet 2 : comptage d'un stand (pratique sur téléphone)
# ---------------------------------------------------------------------------
def afficher_comptage():
    stand_choisi = st.selectbox("Quel stand comptes-tu ?", STANDS)
    st.caption(
        f"Comptage par {utilisateur}. Saisis les quantités comptées, puis clique sur Enregistrer "
        "en bas du formulaire. Seul ce stand est modifié : les autres stands ne sont pas touchés."
    )

    with st.form("formulaire_comptage"):
        quantites_saisies = {}
        colonnes_form = st.columns(2)
        for n, (boisson, quantite) in enumerate(zip(inventaire["Boisson"], inventaire[stand_choisi])):
            quantites_saisies[boisson] = colonnes_form[n % 2].number_input(
                boisson, min_value=0, step=1, value=int(quantite)
            )
        envoye = st.form_submit_button("💾 Enregistrer le comptage", type="primary")

    if envoye:
        # On repart des données les plus récentes, pour ne pas écraser le travail des autres
        donnees = charger_inventaire()
        changements = []
        for boisson, nouvelle in quantites_saisies.items():
            masque = donnees["Boisson"] == boisson
            if not masque.any():
                continue  # boisson supprimée entre-temps
            avant = int(donnees.loc[masque, stand_choisi].iloc[0])
            if nouvelle != avant:
                changements.append(ligne_historique(stand_choisi, boisson, avant, nouvelle))
                donnees.loc[masque, stand_choisi] = int(nouvelle)
        if changements:
            sauvegarder_inventaire(donnees)
            ajouter_historique(changements)
        enregistrer_et_recharger(
            f"Comptage du stand {stand_choisi} enregistré ({len(changements)} changement(s))."
        )


# ---------------------------------------------------------------------------
# Onglet 3 (admin) : tableau complet + gestion des boissons
# ---------------------------------------------------------------------------
def afficher_tableau():
    st.caption("Clique sur une case pour la modifier, puis sur Enregistrer le tableau.")
    tableau_modifie = st.data_editor(
        inventaire[COLONNES_INVENTAIRE],
        hide_index=True,
        disabled=["Boisson"],
        column_config={
            stand: st.column_config.NumberColumn(stand, min_value=0, step=1, format="%d")
            for stand in STANDS
        },
    )

    if st.button("💾 Enregistrer le tableau", type="primary"):
        tableau_modifie[STANDS] = tableau_modifie[STANDS].fillna(0).astype(int)
        donnees = charger_inventaire()
        changements = []
        for stand in STANDS:
            for boisson, apres in zip(tableau_modifie["Boisson"], tableau_modifie[stand]):
                masque = donnees["Boisson"] == boisson
                if not masque.any():
                    continue
                avant = int(donnees.loc[masque, stand].iloc[0])
                if avant != int(apres):
                    changements.append(ligne_historique(stand, boisson, avant, apres))
                    donnees.loc[masque, stand] = int(apres)
        if changements:
            sauvegarder_inventaire(donnees)
            ajouter_historique(changements)
        enregistrer_et_recharger(f"Tableau enregistré ({len(changements)} changement(s)).")

    st.divider()
    col_ajout, col_suppr = st.columns(2)

    with col_ajout:
        st.subheader("➕ Ajouter une boisson")
        with st.form("formulaire_ajout", clear_on_submit=True):
            nom = st.text_input("Nom de la boisson")
            ajoute = st.form_submit_button("Ajouter")
        if ajoute:
            nom = nom.strip()
            donnees = charger_inventaire()
            if not nom:
                st.warning("Écris d'abord un nom.")
            elif nom.lower() in donnees["Boisson"].str.lower().tolist():
                st.warning("Cette boisson existe déjà.")
            else:
                nouvelle_ligne = pd.DataFrame([[nom] + [0] * len(STANDS)], columns=COLONNES_INVENTAIRE)
                sauvegarder_inventaire(pd.concat([donnees, nouvelle_ligne], ignore_index=True))
                enregistrer_et_recharger(f"« {nom} » a été ajoutée.")

    with col_suppr:
        st.subheader("🗑️ Supprimer une boisson")
        a_supprimer = st.selectbox("Boisson à supprimer", inventaire["Boisson"])
        confirme = st.checkbox("Je confirme la suppression")
        if st.button("Supprimer", disabled=not confirme):
            donnees = charger_inventaire()
            sauvegarder_inventaire(donnees[donnees["Boisson"] != a_supprimer])
            enregistrer_et_recharger(f"« {a_supprimer} » a été supprimée.")


# ---------------------------------------------------------------------------
# Onglet 4 (admin) : historique des changements
# ---------------------------------------------------------------------------
def afficher_historique():
    if historique.empty:
        st.info("Aucun changement enregistré pour l'instant. Chaque comptage ou modification apparaîtra ici.")
        return
    f1, f2, f3 = st.columns(3)
    stands_filtres = f1.multiselect("Stands", STANDS, default=STANDS)
    boissons_filtrees = f2.multiselect("Boissons (vide = toutes)", sorted(historique["Boisson"].astype(str).unique()))
    personnes_filtrees = f3.multiselect("Personnes (vide = toutes)", sorted(historique["Par"].astype(str).unique()))

    vue = historique[historique["Stand"].isin(stands_filtres)]
    if boissons_filtrees:
        vue = vue[vue["Boisson"].astype(str).isin(boissons_filtrees)]
    if personnes_filtrees:
        vue = vue[vue["Par"].astype(str).isin(personnes_filtrees)]
    vue = vue.sort_values("Date", ascending=False)

    st.dataframe(vue, hide_index=True)
    st.download_button(
        "⬇️ Télécharger l'historique",
        data=vers_csv_excel(vue),
        file_name="historique.csv",
        mime="text/csv",
    )


# ---------------------------------------------------------------------------
# Onglets : l'équipe voit la vue d'ensemble et le comptage, l'admin voit tout
# ---------------------------------------------------------------------------
noms_onglets = ["📊 Vue d'ensemble", "✏️ Comptage d'un stand"]
if est_admin:
    noms_onglets += ["📋 Tableau complet", "🕓 Historique"]
onglets = st.tabs(noms_onglets)

with onglets[0]:
    afficher_vue_ensemble()
with onglets[1]:
    afficher_comptage()
if est_admin:
    with onglets[2]:
        afficher_tableau()
    with onglets[3]:
        afficher_historique()
