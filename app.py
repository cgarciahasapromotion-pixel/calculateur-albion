import streamlit as st
import pandas as pd
from datetime import date, datetime

# CONFIGURATION
st.set_page_config(page_title="Calculateur Albion", page_icon="🏢")

# --- DONNÉES DE RÉFÉRENCE (INDICES & TAUX) ---
# Taux BCE + 10 points (Mise à jour semestrielle)
TAUX_REF = [
    (date(2019, 1, 1), 10.00),
    (date(2019, 7, 1), 10.00),
    (date(2020, 1, 1), 10.00),
    (date(2020, 7, 1), 10.00),
    (date(2021, 1, 1), 10.00),
    (date(2021, 7, 1), 10.00),
    (date(2022, 1, 1), 10.00),
    (date(2022, 7, 1), 10.50),
    (date(2023, 1, 1), 12.50),
    (date(2023, 7, 1), 14.00),
    (date(2024, 1, 1), 14.75),
    (date(2024, 7, 1), 14.25),
    (date(2025, 1, 1), 13.50)
]

# Indices ILC Historiques
INDICES = {
    "BASE": 114.06, # T1 2019
    "2019": 116.16,
    "2020": 115.79,
    "2021": 118.59,
    "2022": 126.05,
    "2023": 132.63,
    "2024": 135.30 
}

DATE_JUGEMENT = date(2025, 6, 26)

def get_taux(d):
    """Retourne le taux d'intérêt applicable à une date donnée"""
    for start_date, rate in reversed(TAUX_REF):
        if d >= start_date:
            return rate
    return 10.00

# --- INTERFACE UTILISATEUR ---
st.title("🏢 Calculateur Créance - Collectif Albion")
st.markdown("### Outil d'estimation précis (Principal + Intérêts légaux)")
st.info("🔒 **Anonyme** : Aucune donnée n'est enregistrée sur un serveur. Faites votre simulation et téléchargez le résultat.")

with st.sidebar:
    st.header("1. Vos Données Bail")
    loyer_ht_annuel = st.number_input("Loyer Annuel HT (Bail)", value=5580.0, step=100.0)
    loyer_base_ttc = (loyer_ht_annuel * 1.10) / 12
    
    st.header("2. Paiements Reçus")
    st.markdown("Somme totale des virements perçus **avant** le 26/06/2025.")
    acomptes_total = st.number_input("Total Acomptes (€)", value=5115.74, step=50.0)

# --- MOTEUR DE CALCUL DÉTAILLÉ ---
# Génération de l'échéancier théorique complet
data = []

# Période 1 : 2019 (Prorata + T4)
# On simplifie en trimestres échus pour l'affichage
dates_echeances = [
    (date(2019, 10, 10), "T3 2019 (Prorata)", loyer_base_ttc * 4), # 3 mois offerts donc reste 4 mois payants en 2019? Ajusté selon votre règle
    (date(2020, 1, 10), "T4 2019", loyer_base_ttc * 3), 
]

# Fonction pour ajouter une année
def add_year(year, indice_n, indice_base):
    montant_mensuel = (loyer_ht_annuel * 1.10 / 12) * (indice_n / indice_base)
    # Protection baisse loyer (Clause Echelle mobile)
    # Ici simplifié : on applique l'indice
    return montant_mensuel * 3

# Génération dynamique
# 2020
l_2020 = add_year(2020, INDICES["2019"], INDICES["BASE"])
dates_echeances.append((date(2020, 4, 10), "T1 2020", l_2020))
dates_echeances.append((date(2020, 7, 10), "T2 2020", l_2020))
dates_echeances.append((date(2020, 10, 10), "T3 2020", l_2020))
dates_echeances.append((date(2021, 1, 10), "T4 2020", l_2020))

# 2021 (Maintien loyer car indice a baissé ou stagné)
l_2021 = l_2020 
dates_echeances.append((date(2021, 4, 10), "T1 2021", l_2021))
dates_echeances.append((date(2021, 7, 10), "T2 2021", l_2021))
dates_echeances.append((date(2021, 10, 10), "T3 2021", l_2021))
dates_echeances.append((date(2022, 1, 10), "T4 2021", l_2021))

# 2022
l_2022 = add_year(2022, INDICES["2021"], INDICES["BASE"])
dates_echeances.append((date(2022, 4, 10), "T1 2022", l_2022))
dates_echeances.append((date(2022, 7, 10), "T2 2022", l_2022))
dates_echeances.append((date(2022, 10, 10), "T3 2022", l_2022))
dates_echeances.append((date(2023, 1, 10), "T4 2022", l_2022))

# 2023
l_2023 = add_year(2023, INDICES["2022"], INDICES["BASE"])
dates_echeances.append((date(2023, 4, 10), "T1 2023", l_2023))
dates_echeances.append((date(2023, 7, 10), "T2 2023", l_2023))
dates_echeances.append((date(2023, 10, 10), "T3 2023", l_2023))
dates_echeances.append((date(2024, 1, 10), "T4 2023", l_2023))

# 2024
l_2024 = add_year(2024, INDICES["2023"], INDICES["BASE"])
dates_echeances.append((date(2024, 4, 10), "T1 2024", l_2024))
dates_echeances.append((date(2024, 7, 10), "T2 2024", l_2024))
dates_echeances.append((date(2024, 10, 10), "T3 2024", l_2024))
dates_echeances.append((date(2025, 1, 10), "T4 2024", l_2024))

# 2025 (Jusqu'au RJ)
l_2025 = add_year(2025, INDICES["2024"], INDICES["BASE"])
dates_echeances.append((date(2025, 4, 10), "T1 2025", l_2025))
# Prorata Juin (26 jours)
mt_prorata = (l_2025 / 3) / 30 * 26 
dates_echeances.append((date(2025, 6, 26), "Juin 2025 (Prorata)", mt_prorata))


# --- CALCULS ---
total_dette_theorique = 0
total_interets = 0

df_rows = []

for d_ech, label, montant in dates_echeances:
    if d_ech < DATE_JUGEMENT:
        nb_jours = (DATE_JUGEMENT - d_ech).days
        taux = get_taux(d_ech)
        interet = (montant * (taux/100) * nb_jours) / 365
        
        total_dette_theorique += montant
        total_interets += interet
        
        df_rows.append({
            "Période": label,
            "Date Dû": d_ech.strftime("%d/%m/%Y"),
            "Montant Dû": f"{montant:.2f} €",
            "Taux": f"{taux:.2f}%",
            "Jours Retard": nb_jours,
            "Intérêts": f"{interet:.2f} €"
        })

# --- GESTION DES ACOMPTES (METHODE SIMPLIFIEE POUR WEB) ---
# On soustrait les acomptes du principal en premier
principal_net = total_dette_theorique - acomptes_total

# Pour les intérêts sur acomptes, on fait une déduction moyenne pour ne pas demander 20 dates
# On considère que les paiements ont réduit la base génératrice d'intérêts
# Ratio de la dette payée
ratio_paye = acomptes_total / total_dette_theorique
interets_net = total_interets * (1 - ratio_paye)

# --- AFFICHAGE ---

st.subheader("📊 Détail Trimestre par Trimestre")
st.dataframe(pd.DataFrame(df_rows))

st.divider()

col1, col2 = st.columns(2)
with col1:
    st.markdown("### 1. PRINCIPAL")
    st.write(f"Total Dû Théorique : **{total_dette_theorique:,.2f} €**")
    st.write(f"Moins Acomptes Reçus : **- {acomptes_total:,.2f} €**")
    st.markdown(f"#### = {principal_net:,.2f} €")
    st.caption("(Créance Privilégiée)")

with col2:
    st.markdown("### 2. INTÉRÊTS DE RETARD")
    st.write(f"Intérêts Bruts (sur 100% dette) : **{total_interets:,.2f} €**")
    st.write(f"Ajustement (au prorata payé) : **- {total_interets - interets_net:,.2f} €**")
    st.markdown(f"#### = {interets_net:,.2f} €")
    st.caption("(Créance Chirographaire)")

st.success(f"## TOTAL GÉNÉRAL À DÉCLARER : {(principal_net + interets_net):,.2f} €")

st.warning("⚠️ **Rappel Post-RJ :** Ce calcul s'arrête au 26 Juin 2025. Les loyers courants doivent être payés intégralement par l'administrateur.")
