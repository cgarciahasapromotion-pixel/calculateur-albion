import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from fpdf import FPDF
import io

# --- CONFIGURATION ---
st.set_page_config(page_title="Calculateur Créance Albion", page_icon="⚖️", layout="wide")

# --- CONSTANTES JURIDIQUES ---
DATE_JUGEMENT = date(2025, 6, 26)

# Taux d'intérêt légal (BCE + 10 points)
TAUX_LEGAUX = [
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

# Indices ILC
INDICES = {
    "BASE": 114.06, # T1 2019
    "2019": 116.16, # Applicable Juin 2020
    "2020": 115.79, # Applicable Juin 2021 (Baisse -> Maintien loyer)
    "2021": 118.59, # Applicable Juin 2022
    "2022": 126.05, # Applicable Juin 2023
    "2023": 132.63, # Applicable Juin 2024
    "2024": 135.30  # Applicable Juin 2025
}

# --- FONCTIONS UTILITAIRES ---

def get_taux_legal(d):
    """Récupère le taux en vigueur à une date donnée"""
    for start_date, rate in reversed(TAUX_LEGAUX):
        if d >= start_date:
            return rate
    return 10.00

def calculer_interets_ligne(montant, date_depart, date_fin):
    """Calcule les intérêts sur une somme entre deux dates"""
    total_interets = 0
    if date_depart >= date_fin:
        return 0.0

    current_date = date_depart
    while current_date < date_fin:
        taux = get_taux_legal(current_date)
        next_change = date_fin
        for start_date, _ in TAUX_LEGAUX:
            if start_date > current_date and start_date < date_fin:
                next_change = start_date
                break
        days = (next_change - current_date).days
        interet_periode = montant * (taux / 100) * (days / 365)
        total_interets += interet_periode
        current_date = next_change
        
    return total_interets

# --- GÉNÉRATION DE L'ÉCHÉANCIER THÉORIQUE ---
def generer_loyers_theoriques(loyer_annuel_ht):
    # C'EST ICI QUE LA TVA S'APPLIQUE
    loyer_annuel_ttc = loyer_annuel_ht * 1.10
    loyer_base_mensuel = loyer_annuel_ttc / 12
    
    echeances = []

    # 1. ANNEE 2019 (3 mois offerts Juin-Aout -> Reste Sept-Dec)
    montant_mensuel = loyer_base_mensuel
    # On compte Oct/Nov/Dec + Septembre.
    echeances.append({
        "date": date(2019, 10, 10), 
        "label": "Loyer 2019 (4 mois TTC)", 
        "montant": montant_mensuel * 4
    })

    # 2. ANNEE 2020
    echeances.append({"date": date(2020, 1, 10), "label": "T1 2020", "montant": montant_mensuel * 3})
    loyer_2020 = loyer_base_mensuel * (INDICES["2019"] / INDICES["BASE"])
    # T2 Mixte (Avril Mai base / Juin indexé)
    montant_t2_mixte = (montant_mensuel * 2) + (loyer_2020 * 1)
    echeances.append({"date": date(2020, 4, 10), "label": "T2 2020 (Mixte)", "montant": montant_t2_mixte})
    echeances.append({"date": date(2020, 7, 10), "label": "T3 2020", "montant": loyer_2020 * 3})
    echeances.append({"date": date(2020, 10, 10), "label": "T4 2020", "montant": loyer_2020 * 3})

    # 3. ANNEE 2021 (Clause sauvegarde)
    loyer_2021 = loyer_2020
    echeances.append({"date": date(2021, 1, 10), "label": "T1 2021", "montant": loyer_2021 * 3})
    echeances.append({"date": date(2021, 4, 10), "label": "T2 2021", "montant": loyer_2021 * 3})
    echeances.append({"date": date(2021, 7, 10), "label": "T3 2021", "montant": loyer_2021 * 3})
    echeances.append({"date": date(2021, 10, 10), "label": "T4 2021", "montant": loyer_2021 * 3})

    # 4. ANNEE 2022
    loyer_2022 = loyer_base_mensuel * (INDICES["2021"] / INDICES["BASE"])
    echeances.append({"date": date(2022, 1, 10), "label": "T1 2022", "montant": loyer_2021 * 3})
    montant_t2_22 = (loyer_2021 * 2) + (loyer_2022 * 1)
    echeances.append({"date": date(2022, 4, 10), "label": "T2 2022 (Indexation)", "montant": montant_t2_22})
    echeances.append({"date": date(2022, 7, 10), "label": "T3 2022", "montant": loyer_2022 * 3})
    echeances.append({"date": date(2022, 10, 10), "label": "T4 2022", "montant": loyer_2022 * 3})

    # 5. ANNEE 2023
    loyer_2023 = loyer_base_mensuel * (INDICES["2022"] / INDICES["BASE"])
    echeances.append({"date": date(2023, 1, 10), "label": "T1 2023", "montant": loyer_2022 * 3})
    montant_t2_23 = (loyer_2022 * 2) + (loyer_2023 * 1)
    echeances.append({"date": date(2023, 4, 10), "label": "T2 2023 (Indexation)", "montant": montant_t2_23})
    echeances.append({"date": date(2023, 7, 10), "label": "T3 2023", "montant": loyer_2023 * 3})
    echeances.append({"date": date(2023, 10, 10), "label": "T4 2023", "montant": loyer_2023 * 3})

    # 6. ANNEE 2024
    loyer_2024 = loyer_base_mensuel * (INDICES["2023"] / INDICES["BASE"])
    echeances.append({"date": date(2024, 1, 10), "label": "T1 2024", "montant": loyer_2023 * 3})
    montant_t2_24 = (loyer_2023 * 2) + (loyer_2024 * 1)
    echeances.append({"date": date(2024, 4, 10), "label": "T2 2024 (Indexation)", "montant": montant_t2_24})
    echeances.append({"date": date(2024, 7, 10), "label": "T3 2024", "montant": loyer_2024 * 3})
    echeances.append({"date": date(2024, 10, 10), "label": "T4 2024", "montant": loyer_2024 * 3})

    # 7. ANNEE 2025 (Jusqu'au RJ)
    echeances.append({"date": date(2025, 1, 10), "label": "T1 2025", "montant": loyer_2024 * 3})
    loyer_2025 = loyer_base_mensuel * (INDICES["2024"] / INDICES["BASE"])
    montant_avril_mai = loyer_2024 * 2
    montant_juin_prorata = (loyer_2025 / 30) * 26
    
    echeances.append({
        "date": date(2025, 4, 10), 
        "label": "Avril-Mai 2025", 
        "montant": montant_avril_mai
    })
    echeances.append({
        "date": date(2025, 6, 26), 
        "label": "Juin 2025 (Prorata 26j)", 
        "montant": montant_juin_prorata
    })

    return echeances

# --- CLASS PDF ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Déclaration de Créance - HOTEL ALBION', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 10, '(Montants exprimés en TTC - TVA 10% incluse)', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

# --- INTERFACE ---

st.title("🏛️ Calculateur de Créance - Propriétaires Albion")

# --- SECTION PÉDAGOGIQUE ---
with st.expander("📚 GUIDE DE LECTURE : Comprendre les chiffres (Cliquez ici)", expanded=True):
    st.markdown("""
    **Pourquoi cet outil ?**
    Pour calculer votre créance exacte au centime près, en appliquant les indexations ILC (inflation) et les pénalités de retard légales.
    
    **1. HT ou TTC ?**
    * Le bail fixe un loyer **HT (Hors Taxes)**.
    * L'application ajoute automatiquement **10% de TVA**.
    * Le résultat final (Dette) est affiché en **TTC**, car c'est ce que vous devez comparer aux virements reçus.
    
    **2. Le Principal Net (Créance Privilégiée)**
    * C'est l'argent du loyer "pur" qui manque.
    * *Calcul :* (Loyers TTC théoriques indexés) - (Virements TTC reçus).
    
    **3. Les Intérêts de Retard (Créance Chirographaire)**
    * L'argent a un coût. Le Code de Commerce impose des pénalités entre professionnels.
    * Le taux appliqué ici est le taux légal (Refi BCE + 10 points), soit environ 13-14% par an.
    * *Note :* Chaque virement que vous avez reçu vient d'abord "effacer" des intérêts avant de rembourser le loyer. L'outil fait ce calcul complexe pour vous.
    """)

# SESSION STATE
if 'paiements' not in st.session_state:
    st.session_state.paiements = []

col_left, col_right = st.columns([1, 2])

with col_left:
    st.markdown("### 1. Données du Bail (HT)")
    st.warning("⚠️ Attention : Entrez le montant **ANNUEL** et **HORS TAXES** inscrit sur votre bail.")
    loyer_ht = st.number_input("Loyer Annuel HT (€)", min_value=0.0, step=100.0, format="%.2f")
    st.caption(f"L'outil ajoutera automatiquement 10% de TVA. Soit un loyer de base de {(loyer_ht*1.10):,.2f} € TTC/an.")
    
    st.markdown("### 2. Paiements Reçus (TTC)")
    st.info("Ajoutez ici chaque virement reçu **AVANT le 26/06/2025**.")
    
    with st.form("ajout_paiement"):
        d_paiement = st.date_input("Date du virement", value=date(2024, 1, 1))
        m_paiement = st.number_input("Montant Reçu TTC (€)", min_value=0.0, step=10.0)
        submit = st.form_submit_button("Ajouter ce paiement")
        
        if submit and m_paiement > 0:
            if d_paiement > DATE_JUGEMENT:
                st.error("❌ Ce paiement est POSTÉRIEUR au RJ (après le 26 juin). Ne le mettez pas ici !")
            else:
                st.session_state.paiements.append({"date": d_paiement, "montant": m_paiement})
                st.success("✅ Paiement ajouté !")

    # Liste des paiements
    if st.session_state.paiements:
        st.write("---")
        st.write("**Historique des virements saisis :**")
        p_df = pd.DataFrame(st.session_state.paiements)
        st.dataframe(p_df.style.format({"montant": "{:.2f} € TTC"}))
        if st.button("🗑️ Effacer tous les paiements"):
            st.session_state.paiements = []
            st.rerun()

# --- CALCULS ---
if loyer_ht > 0:
    # 1. Génération dettes TTC
    echeances = generer_loyers_theoriques(loyer_ht)
    
    total_principal_du = 0
    total_interets_du = 0
    data_detail = []

    # Calcul intérêts sur Dettes
    for ech in echeances:
        interet = calculer_interets_ligne(ech["montant"], ech["date"], DATE_JUGEMENT)
        total_principal_du += ech["montant"]
        total_interets_du += interet
        data_detail.append({
            "Date": ech["date"],
            "Type": "LOYER DÛ",
            "Libellé": ech["label"],
            "Débit (TTC)": ech["montant"],
            "Crédit (TTC)": 0,
            "Intérêts": interet
        })

    # Calcul intérêts (épargnés) sur Paiements
    total_paye = 0
    total_interets_paye = 0
    
    for p in st.session_state.paiements:
        interet_p = calculer_interets_ligne(p["montant"], p["date"], DATE_JUGEMENT)
        total_paye += p["montant"]
        total_interets_paye += interet_p
        data_detail.append({
            "Date": p["date"],
            "Type": "PAIEMENT",
            "Libellé": "Virement Reçu",
            "Débit (TTC)": 0,
            "Crédit (TTC)": p["montant"],
            "Intérêts": -interet_p 
        })
    
    # Tri chronologique
    df_final = pd.DataFrame(data_detail).sort_values(by="Date")
    
    # TOTAUX
    principal_net = total_principal_du - total_paye
    interets_net = total_interets_du - total_interets_paye
    # Sécurité pour ne pas avoir d'intérêts négatifs si trop perçu (rare)
    if interets_net < 0: interets_net = 0
    
    total_creance = principal_net + interets_net

    with col_right:
        st.markdown("### 3. Résultats & Synthèse")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Loyer Dû (TTC)", f"{total_principal_du:,.2f} €")
        c2.metric("Déjà Payé (TTC)", f"- {total_paye:,.2f} €")
        c3.metric("PRINCIPAL NET", f"{principal_net:,.2f} €", help="Montant TTC des loyers impayés")
        
        st.write("---")
        
        c4, c5, c6 = st.columns(3)
        c4.metric("Intérêts Bruts", f"{total_interets_du:,.2f} €")
        c5.metric("Déduction", f"- {total_interets_paye:,.2f} €")
        c6.metric("INTÉRÊTS NETS", f"{interets_net:,.2f} €", help="Pénalités de retard légales (Art L441-10)")
        
        st.success(f"### 💰 TOTAL À DÉCLARER : {total_creance:,.2f} €")
        
        with st.expander("Voir le détail ligne par ligne"):
            st.dataframe(df_final.style.format({"Débit (TTC)": "{:.2f}", "Crédit (TTC)": "{:.2f}", "Intérêts": "{:.2f}"}))

    # --- GÉNÉRATION PDF ---
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    
    # Info En-tête
    pdf.cell(0, 10, f"Date d'arrêt des comptes : 26 Juin 2025 (Jugement RJ)", 0, 1)
    pdf.cell(0, 10, f"Loyer Annuel Base : {loyer_ht:,.2f} EUR HT (soit {(loyer_ht*1.10):,.2f} EUR TTC)", 0, 1)
    pdf.ln(10)
    
    # Tableau Synthèse
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "SYNTHÈSE DE LA CRÉANCE (TTC)", 0, 1)
    pdf.set_font("Arial", size=11)
    
    pdf.cell(100, 8, "Principal TTC (Loyers impayés)", 1)
    pdf.cell(50, 8, f"{principal_net:,.2f} EUR", 1, 1, 'R')
    
    pdf.cell(100, 8, "Intérêts de retard (Art L.441-10)", 1)
    pdf.cell(50, 8, f"{interets_net:,.2f} EUR", 1, 1, 'R')
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 10, "TOTAL GÉNÉRAL", 1)
    pdf.cell(50, 10, f"{total_creance:,.2f} EUR", 1, 1, 'R')
    
    pdf.ln(10)
    
    # Tableau Détail
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 10, "DÉTAIL CHRONOLOGIQUE (TTC)", 0, 1)
    
    # En-têtes colonnes
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(25, 8, "Date", 1)
    pdf.cell(60, 8, "Libellé", 1)
    pdf.cell(25, 8, "Dû (Debit)", 1)
    pdf.cell(25, 8, "Reçu (Credit)", 1)
    pdf.cell(25, 8, "Interets", 1, 1)
    
    pdf.set_font("Arial", size=8)
    for index, row in df_final.iterrows():
        d_str = row['Date'].strftime("%d/%m/%Y")
        pdf.cell(25, 6, d_str, 1)
        pdf.cell(60, 6, str(row['Libellé']), 1)
        pdf.cell(25, 6, f"{row['Débit (TTC)']:.2f}", 1, 0, 'R')
        pdf.cell(25, 6, f"{row['Crédit (TTC)']:.2f}", 1, 0, 'R')
        pdf.cell(25, 6, f"{row['Intérêts']:.2f}", 1, 1, 'R')
        
    # Output PDF
    pdf_buffer = io.BytesIO()
    pdf.output(pdf_buffer)
    pdf_data = pdf_buffer.getvalue()
    
    st.download_button(
        label="📄 TÉLÉCHARGER MA DÉCLARATION (PDF)",
        data=pdf_data,
        file_name="declaration_creance_albion.pdf",
        mime="application/pdf"
    )

else:
    st.info("👈 Commencez par entrer votre Loyer Annuel HT dans la colonne de gauche.")
