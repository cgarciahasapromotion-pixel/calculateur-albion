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
        # Trouver le taux actuel
        taux = get_taux_legal(current_date)
        
        # Trouver la prochaine date de changement de taux
        next_change = date_fin
        for start_date, _ in TAUX_LEGAUX:
            if start_date > current_date and start_date < date_fin:
                next_change = start_date
                break
        
        # Calculer jours
        days = (next_change - current_date).days
        interet_periode = montant * (taux / 100) * (days / 365)
        total_interets += interet_periode
        
        current_date = next_change
        
    return total_interets

# --- GÉNÉRATION DE L'ÉCHÉANCIER THÉORIQUE ---
def generer_loyers_theoriques(loyer_annuel_ht):
    loyer_base_mensuel = (loyer_annuel_ht * 1.10) / 12
    echeances = []

    # 1. ANNEE 2019 (3 mois offerts Juin-Aout -> Reste Sept-Dec)
    # Loyer de base
    montant_mensuel = loyer_base_mensuel
    # T4 2019 (Oct Nov Dec) - Echéance 10 Octobre
    # Septembre était dû mais souvent compté dans le prorata ou premier terme. 
    # Pour simplifier et coller au calcul "Magic Number" (9 mois en 2019/2020) :
    # On compte Oct/Nov/Dec + Septembre séparé ou groupé.
    # Ici on met un T4 complet + Septembre isolé pour la justesse.
    
    echeances.append({
        "date": date(2019, 10, 10), 
        "label": "Loyer 2019 (Sept-Déc)", 
        "montant": montant_mensuel * 4
    })

    # 2. ANNEE 2020 (Jan-Mai : Base / Juin-Dec : Indexé)
    # T1 2020
    echeances.append({"date": date(2020, 1, 10), "label": "T1 2020", "montant": montant_mensuel * 3})
    # T2 2020 (Avril Mai au vieux taux, Juin au nouveau ?) 
    # Simplification : Indexation au 1er Juin.
    # Donc Avril/Mai = Base. Juin = Indexé.
    loyer_2020 = loyer_base_mensuel * (INDICES["2019"] / INDICES["BASE"])
    montant_t2_mixte = (montant_mensuel * 2) + (loyer_2020 * 1)
    echeances.append({"date": date(2020, 4, 10), "label": "T2 2020 (Mixte)", "montant": montant_t2_mixte})
    
    # Reste 2020
    echeances.append({"date": date(2020, 7, 10), "label": "T3 2020", "montant": loyer_2020 * 3})
    echeances.append({"date": date(2020, 10, 10), "label": "T4 2020", "montant": loyer_2020 * 3})

    # 3. ANNEE 2021 (Clause sauvegarde : Indice baisse -> Maintien loyer précédent)
    loyer_2021 = loyer_2020
    echeances.append({"date": date(2021, 1, 10), "label": "T1 2021", "montant": loyer_2021 * 3})
    echeances.append({"date": date(2021, 4, 10), "label": "T2 2021", "montant": loyer_2021 * 3}) # Juin ne bouge pas
    echeances.append({"date": date(2021, 7, 10), "label": "T3 2021", "montant": loyer_2021 * 3})
    echeances.append({"date": date(2021, 10, 10), "label": "T4 2021", "montant": loyer_2021 * 3})

    # 4. ANNEE 2022
    loyer_2022 = loyer_base_mensuel * (INDICES["2021"] / INDICES["BASE"])
    echeances.append({"date": date(2022, 1, 10), "label": "T1 2022", "montant": loyer_2021 * 3}) # Jan-Mai ancien tarif
    # T2 Mixte (Avril Mai vieux / Juin neuf)
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
    # T1 2025 (Jan Fev Mars)
    echeances.append({"date": date(2025, 1, 10), "label": "T1 2025", "montant": loyer_2024 * 3})
    # T2 partiel (Avril Mai complets + Juin prorata)
    # Avril et Mai sont au tarif 2024.
    # Juin (du 1er au 26) est au tarif 2025 (Index T4 2024).
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
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

# --- INTERFACE ---

st.title("🏛️ Calculateur de Créance - Propriétaires Albion")
st.markdown("""
Cet outil génère votre dossier de déclaration de créance.
1. Entrez votre loyer de base.
2. Ajoutez vos paiements reçus **un par un** avec leur date.
3. Téléchargez le PDF officiel.
""")

# SESSION STATE POUR LES PAIEMENTS
if 'paiements' not in st.session_state:
    st.session_state.paiements = []

col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("1. Données du Bail")
    loyer_ht = st.number_input("Loyer Annuel HT (Bail)", min_value=0.0, step=100.0, format="%.2f")
    
    st.subheader("2. Paiements Reçus")
    st.caption("Ajoutez chaque virement perçu avant le 26/06/2025.")
    
    with st.form("ajout_paiement"):
        d_paiement = st.date_input("Date du virement", value=date(2024, 1, 1))
        m_paiement = st.number_input("Montant (€)", min_value=0.0, step=10.0)
        submit = st.form_submit_button("Ajouter ce paiement")
        
        if submit and m_paiement > 0:
            if d_paiement > DATE_JUGEMENT:
                st.error("Ce paiement est postérieur au RJ, ne pas l'inclure ici !")
            else:
                st.session_state.paiements.append({"date": d_paiement, "montant": m_paiement})
                st.success("Ajouté !")

    # Liste des paiements
    if st.session_state.paiements:
        st.write("---")
        st.write("**Liste des versements :**")
        p_df = pd.DataFrame(st.session_state.paiements)
        # Option pour supprimer (simple reset pour cette version)
        st.dataframe(p_df)
        if st.button("Effacer tous les paiements"):
            st.session_state.paiements = []
            st.rerun()

# --- CALCULS ---
if loyer_ht > 0:
    # 1. Génération dettes
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
            "Débit": ech["montant"],
            "Crédit": 0,
            "Intérêts Générés": interet
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
            "Débit": 0,
            "Crédit": p["montant"],
            "Intérêts Générés": -interet_p # Négatif car réduit la dette
        })
    
    # Tri chronologique pour le tableau
    df_final = pd.DataFrame(data_detail).sort_values(by="Date")
    
    # TOTAUX
    principal_net = total_principal_du - total_paye
    interets_net = total_interets_du - total_interets_paye
    total_creance = principal_net + interets_net

    with col_right:
        st.subheader("3. Résultats")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Principal Dû", f"{total_principal_du:,.2f} €")
        c2.metric("Total Payé", f"- {total_paye:,.2f} €")
        c3.metric("PRINCIPAL NET", f"{principal_net:,.2f} €")
        
        st.write("---")
        
        c4, c5, c6 = st.columns(3)
        c4.metric("Intérêts sur Dettes", f"{total_interets_du:,.2f} €")
        c5.metric("Déduction s/Paiements", f"- {total_interets_paye:,.2f} €")
        c6.metric("INTÉRÊTS NETS", f"{interets_net:,.2f} €")
        
        st.success(f"### TOTAL À DÉCLARER : {total_creance:,.2f} €")
        
        st.dataframe(df_final.style.format({"Débit": "{:.2f}", "Crédit": "{:.2f}", "Intérêts Générés": "{:.2f}"}))

    # --- GÉNÉRATION PDF ---
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    
    # Info En-tête
    pdf.cell(0, 10, f"Date d'arrêt des comptes : 26 Juin 2025 (Jugement RJ)", 0, 1)
    pdf.cell(0, 10, f"Loyer Annuel HT Base : {loyer_ht} EUR", 0, 1)
    pdf.ln(10)
    
    # Tableau Synthèse
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "SYNTHÈSE DE LA CRÉANCE", 0, 1)
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
    pdf.cell(0, 10, "DÉTAIL DES MOUVEMENTS ET CALCUL INTÉRÊTS", 0, 1)
    
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
        pdf.cell(25, 6, f"{row['Débit']:.2f}", 1, 0, 'R')
        pdf.cell(25, 6, f"{row['Crédit']:.2f}", 1, 0, 'R')
        pdf.cell(25, 6, f"{row['Intérêts Générés']:.2f}", 1, 1, 'R')
        
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
    st.info("Veuillez entrer le montant du loyer annuel HT pour commencer.")
