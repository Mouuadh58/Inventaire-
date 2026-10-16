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
FUSEAU = ZoneInfo("Europe/Paris")

# Pour ajouter ou renommer un stand, il suffit de modifier cette liste.
STANDS = ["CDJ", "Bouillon", "Piazza", "Cafète"]

# Données de départ, reprises du Google Sheet.
# Elles ne servent qu'au tout premier lancement, quand inventaire.csv n'existe pas encore.
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

COLONNES_HISTORIQUE = ["Date", "Stand", "Boisson", "Avant", "Après", "Écart"]


# ---------------------------------------------------------------------------
# Fonctions de lecture et d'écriture des fichiers
# ---------------------------------------------------------------------------
def charger_inventaire():
    if FICHIER_INVENTAIRE.exists():
        df = pd.read_csv(FICHIER_INVENTAIRE)
    else:
        lignes = [[boisson] + quantites for boisson, quantites in DONNEES_DEPART.items()]
        df = pd.DataFrame(lignes, columns=["Boisson"] + STANDS)
        df.to_csv(FICHIER_INVENTAIRE, index=False)
    for stand in STANDS:
        if stand not in df.columns:
            df[stand] = 0
    df[STANDS] = df[STANDS].fillna(0).astype(int)
    return df[["Boisson"] + STANDS].reset_index(drop=True)


def sauvegarder_inventaire(df):
    df[["Boisson"] + STANDS].to_csv(FICHIER_INVENTAIRE, index=False)


def charger_historique():
    if FICHIER_HISTORIQUE.exists():
        return pd.read_csv(FICHIER_HISTORIQUE)
    return pd.DataFrame(columns=COLONNES_HISTORIQUE)


def ajouter_historique(lignes):
    if not lignes:
        return
    nouvelles = pd.DataFrame(lignes, columns=COLONNES_HISTORIQUE)
    historique = charger_historique()
    if historique.empty:
        historique = nouvelles
    else:
        historique = pd.concat([historique, nouvelles], ignore_index=True)
    historique.to_csv(FICHIER_HISTORIQUE, index=False)


def ligne_historique(stand, boisson, avant, apres):
    maintenant = datetime.now(FUSEAU).strftime("%Y-%m-%d %H:%M")
    return {
        "Date": maintenant,
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
# Chargement des données
# ---------------------------------------------------------------------------
inventaire = charger_inventaire()
inventaire["Total"] = inventaire[STANDS].sum(axis=1)

# ---------------------------------------------------------------------------
# Barre latérale
# ---------------------------------------------------------------------------
st.sidebar.header("Réglages")
seuil = st.sidebar.number_input("Seuil de stock bas", min_value=0, value=10, step=1)
st.sidebar.caption("Une boisson est en stock bas quand son total (tous stands) est inférieur ou égal à ce seuil.")

st.sidebar.divider()
st.sidebar.download_button(
    "⬇️ Télécharger l'inventaire",
    data=vers_csv_excel(inventaire),
    file_name="inventaire.csv",
    mime="text/csv",
)

# ---------------------------------------------------------------------------
# En-tête
# ---------------------------------------------------------------------------
st.title("🥤 Inventaire des boissons")
maj = datetime.fromtimestamp(FICHIER_INVENTAIRE.stat().st_mtime, FUSEAU)
st.caption(f"Dernière mise à jour : {maj:%d/%m/%Y} à {maj:%H:%M}")

if "message" in st.session_state:
    st.success(st.session_state.pop("message"))

onglet_vue, onglet_comptage, onglet_tableau, onglet_historique = st.tabs(
    ["📊 Vue d'ensemble", "✏️ Comptage d'un stand", "📋 Tableau complet", "🕓 Historique"]
)

# ---------------------------------------------------------------------------
# Onglet 1 : vue d'ensemble
# ---------------------------------------------------------------------------
with onglet_vue:
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

    st.subheader("Répartition des boissons en stock")
    en_stock = inventaire[inventaire["Total"] > 0]
    if en_stock.empty:
        st.info("Aucune boisson en stock pour l'instant.")
    else:
        st.bar_chart(en_stock.set_index("Boisson")[STANDS])

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
with onglet_comptage:
    stand_choisi = st.selectbox("Quel stand comptes-tu ?", STANDS)
    st.caption("Saisis les quantités comptées, puis clique sur Enregistrer en bas du formulaire.")

    with st.form("formulaire_comptage"):
        quantites_saisies = {}
        colonnes_form = st.columns(2)
        for n, (boisson, quantite) in enumerate(zip(inventaire["Boisson"], inventaire[stand_choisi])):
            quantites_saisies[boisson] = colonnes_form[n % 2].number_input(
                boisson, min_value=0, step=1, value=int(quantite)
            )
        envoye = st.form_submit_button("💾 Enregistrer le comptage", type="primary")

    if envoye:
        changements = []
        for boisson, nouvelle in quantites_saisies.items():
            masque = inventaire["Boisson"] == boisson
            avant = int(inventaire.loc[masque, stand_choisi].iloc[0])
            if nouvelle != avant:
                changements.append(ligne_historique(stand_choisi, boisson, avant, nouvelle))
            inventaire.loc[masque, stand_choisi] = int(nouvelle)
        sauvegarder_inventaire(inventaire)
        ajouter_historique(changements)
        enregistrer_et_recharger(
            f"Comptage du stand {stand_choisi} enregistré ({len(changements)} changement(s))."
        )

# ---------------------------------------------------------------------------
# Onglet 3 : tableau complet + gestion des boissons
# ---------------------------------------------------------------------------
with onglet_tableau:
    st.caption("Clique sur une case pour la modifier, puis sur Enregistrer le tableau.")
    tableau_modifie = st.data_editor(
        inventaire[["Boisson"] + STANDS],
        hide_index=True,
        disabled=["Boisson"],
        column_config={
            stand: st.column_config.NumberColumn(stand, min_value=0, step=1, format="%d")
            for stand in STANDS
        },
    )

    if st.button("💾 Enregistrer le tableau", type="primary"):
        tableau_modifie[STANDS] = tableau_modifie[STANDS].fillna(0).astype(int)
        changements = []
        for stand in STANDS:
            for boisson, avant, apres in zip(inventaire["Boisson"], inventaire[stand], tableau_modifie[stand]):
                if int(avant) != int(apres):
                    changements.append(ligne_historique(stand, boisson, avant, apres))
        sauvegarder_inventaire(tableau_modifie)
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
            noms_existants = inventaire["Boisson"].str.lower().tolist()
            if not nom:
                st.warning("Écris d'abord un nom.")
            elif nom.lower() in noms_existants:
                st.warning("Cette boisson existe déjà.")
            else:
                nouvelle_ligne = pd.DataFrame([[nom] + [0] * len(STANDS)], columns=["Boisson"] + STANDS)
                sauvegarder_inventaire(pd.concat([inventaire, nouvelle_ligne], ignore_index=True))
                enregistrer_et_recharger(f"« {nom} » a été ajoutée.")

    with col_suppr:
        st.subheader("🗑️ Supprimer une boisson")
        a_supprimer = st.selectbox("Boisson à supprimer", inventaire["Boisson"])
        confirme = st.checkbox("Je confirme la suppression")
        if st.button("Supprimer", disabled=not confirme):
            sauvegarder_inventaire(inventaire[inventaire["Boisson"] != a_supprimer])
            enregistrer_et_recharger(f"« {a_supprimer} » a été supprimée.")

# ---------------------------------------------------------------------------
# Onglet 4 : historique des changements
# ---------------------------------------------------------------------------
with onglet_historique:
    historique = charger_historique()
    if historique.empty:
        st.info("Aucun changement enregistré pour l'instant. Chaque comptage ou modification apparaîtra ici.")
    else:
        f1, f2 = st.columns(2)
        stands_filtres = f1.multiselect("Stands", STANDS, default=STANDS)
        boissons_filtrees = f2.multiselect("Boissons (laisser vide = toutes)", sorted(historique["Boisson"].unique()))

        vue = historique[historique["Stand"].isin(stands_filtres)]
        if boissons_filtrees:
            vue = vue[vue["Boisson"].isin(boissons_filtrees)]
        vue = vue.sort_values("Date", ascending=False)

        st.dataframe(vue, hide_index=True)
        st.download_button(
            "⬇️ Télécharger l'historique",
            data=vers_csv_excel(vue),
            file_name="historique.csv",
            mime="text/csv",
        )
