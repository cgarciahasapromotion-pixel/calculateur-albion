import streamlit as st
import pandas as pd
import altair as alt
from datetime import date, datetime, timedelta
from fpdf import FPDF
import io

# --- CONFIGURATION ---
st.set_page_config(page_title="Calculateur Créance Albion", page_icon="⚖️", layout="wide")

# --- CONSTANTES JURIDIQUES ---
DATE_JUGEMENT = date(2025, 6, 26)
DATE_DEBUT_GRAPH = date(2019, 6, 1)

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
    "BASE": 114.06, 
    "2019": 116.16, 
    "2020": 115.79, 
    "2021": 118.59, 
    "2022": 126.05, 
    "2023": 132.63, 
    "2024": 135.30  
}

# --- FONCTIONS UTILITAIRES ---

def get_taux_legal(d):
    for start_date, rate in reversed(TAUX_LEGAUX):
        if d >= start_date:
            return rate
    return 10.00

def calculer_interets_ligne(montant, date_depart, date_fin):
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
    loyer_annuel_ttc = loyer_annuel_ht * 1.10
    loyer_base_mensuel = loyer_annuel_ttc / 12
    echeances = []

    # 1. ANNEE 2019
    echeances.append({
        "date": date(2019, 10, 10), 
        "label": "Loyer 2019 (4 mois TTC)", 
        "montant": loyer_base_mensuel * 4
    })
    # 2. ANNEE 2020
    echeances.append({"date": date(2020, 1, 10), "label": "T1 2020", "montant": loyer_base_mensuel * 3})
    loyer_2020 = loyer_base_mensuel * (INDICES["2019"] / INDICES["BASE"])
    montant_t2_mixte = (loyer_base_mensuel * 2) + (loyer_2020 * 1)
    echeances.append({"date": date(2020, 4, 10), "label": "T2 2020 (Mixte)", "montant": montant_t2_mixte})
    echeances.append({"date": date(2020, 7, 10), "label": "T3 2020", "montant": loyer_2020 * 3})
    echeances.append({"date": date(2020, 10, 10), "label": "T4 2020", "montant": loyer_2020 * 3})
    # 3. ANNEE 2021
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
    # 7. ANNEE 2025
    echeances.append({"date": date(2025, 1, 10), "label": "T1 2025", "montant": loyer_2024 * 3})
    loyer_2025 = loyer_base_mensuel * (INDICES["2024"] / INDICES["BASE"])
    montant_avril_mai = loyer_2024 * 2
    montant_juin_prorata = (loyer_2025 / 30) * 26
    
    echeances.append({
        "date": date(2025, 4, 10), "label": "Avril-Mai 2025", "montant": montant_avril_mai
    })
    echeances.append({
        "date": date(2025, 6, 26), "label": "Juin 2025 (Prorata 26j)", "montant": montant_juin_prorata
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

# SESSION STATE
if 'paiements' not in st.session_state:
    st.session_state.paiements = []

col_left, col_right = st.columns([1, 2])

with col_left:
    st.markdown("### 1. Données du Bail (HT)")
    loyer_ht = st.number_input("Loyer Annuel HT (€)", min_value=0.0, step=100.0, format="%.2f")
    st.caption(f"Soit {(loyer_ht*1.10):,.2f} € TTC/an.")
    
    st.markdown("### 2. Paiements Reçus (TTC)")
    with st.form("ajout_paiement"):
        d_paiement = st.date_input("Date du virement", value=date(2024, 1, 1), format="DD/MM/YYYY")
        m_paiement = st.number_input("Montant Reçu TTC (€)", min_value=0.0, step=10.0)
        submit = st.form_submit_button("Ajouter")
        if submit and m_paiement > 0:
            if d_paiement > DATE_JUGEMENT:
                st.error("Date postérieure au jugement !")
            else:
                st.session_state.paiements.append({"date": d_paiement, "montant": m_paiement})
                st.success("Ajouté !")

    if st.session_state.paiements:
        st.write("**Virements saisis :**")
        p_df = pd.DataFrame(st.session_state.paiements)
        st.dataframe(p_df.style.format({"montant": "{:.2f} €", "date": lambda t: t.strftime("%d/%m/%Y")}))
        if st.button("Tout effacer"):
            st.session_state.paiements = []
            st.rerun()

# --- CALCULS ---
if loyer_ht > 0:
    # 1. Génération dettes
    echeances = generer_loyers_theoriques(loyer_ht)
    
    total_principal_du = 0
    total_interets_du = 0
    data_detail = []

    # Calcul Final
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
    
    df_final = pd.DataFrame(data_detail).sort_values(by="Date")
    principal_net = total_principal_du - total_paye
    interets_net = max(0, total_interets_du - total_interets_paye)
    total_creance = principal_net + interets_net

    # --- PARTIE GRAPHIQUE (SIMULATION MENSUELLE) ---
    graph_data = []
    
    current_d = DATE_DEBUT_GRAPH
    while current_d <= DATE_JUGEMENT:
        sum_due = sum(e["montant"] for e in echeances if e["date"] <= current_d)
        sum_paid = sum(p["montant"] for p in st.session_state.paiements if p["date"] <= current_d)
        balance_principal = sum_due - sum_paid
        
        int_dette_t = 0
        for e in echeances:
            if e["date"] < current_d:
                int_dette_t += calculer_interets_ligne(e["montant"], e["date"], current_d)
        
        int_pay_t = 0
        for p in st.session_state.paiements:
            if p["date"] < current_d:
                int_pay_t += calculer_interets_ligne(p["montant"], p["date"], current_d)
        
        balance_interets = max(0, int_dette_t - int_pay_t)
        
        graph_data.append({
            "Date": pd.to_datetime(current_d),
            "Dette Principal (Bleu)": balance_principal,
            "Intérêts Cumulés (Rouge)": balance_interets
        })
        
        # Mois suivant
        next_month = current_d.replace(day=28) + timedelta(days=4)
        current_d = next_month.replace(day=1)

    df_graph = pd.DataFrame(graph_data)
    df_graph_melted = df_graph.melt('Date', var_name='Type', value_name='Montant (€)')

    with col_right:
        st.markdown("### 📈 Évolution de la Dette & Intérêts")
        
        # --- CREATION DU GRAPHIQUE AVEC LIGNE JUGEMENT ---
        
        # 1. Graphique de base (Courbes)
        base_chart = alt.Chart(df_graph_melted).mark_line(strokeWidth=3).encode(
            x=alt.X('Date', axis=alt.Axis(format='%d/%m/%Y', title='Date')),
            y=alt.Y('Montant (€)', axis=alt.Axis(title='Montant (€)')),
            color=alt.Color('Type', scale=alt.Scale(domain=['Dette Principal (Bleu)', 'Intérêts Cumulés (Rouge)'], range=['#1f77b4', '#d62728'])),
            tooltip=[
                alt.Tooltip('Date', format='%d/%m/%Y', title='Date'),
                alt.Tooltip('Type', title='Type'),
                alt.Tooltip('Montant (€)', format=',.2f', title='Montant (€)')
            ]
        )
        
        # 2. Ligne verticale (Jugement)
        jugement_df = pd.DataFrame({'Date': [pd.to_datetime(DATE_JUGEMENT)], 'Label': [' JUGEMENT RJ']})
        
        vline = alt.Chart(jugement_df).mark_rule(color='black', strokeDash=[5, 5], strokeWidth=2).encode(
            x='Date'
        )
        
        # 3. Texte sur la ligne
        vtext = alt.Chart(jugement_df).mark_text(
            align='left', 
            baseline='middle', 
            dx=5, 
            dy=-10, 
            color='black', 
            fontSize=12,
            fontWeight='bold'
        ).encode(
            x='Date',
            text='Label'
        )
        
        # Fusion des couches
        final_chart = (base_chart + vline + vtext).interactive()
        
        st.altair_chart(final_chart, use_container_width=True)

        st.markdown("### 3. Synthèse Chiffrée")
        c1, c2, c3 = st.columns(3)
        c1.metric("Principal Net", f"{principal_net:,.2f} €")
        c2.metric("Intérêts Net", f"{interets_net:,.2f} €")
        c3.metric("TOTAL", f"{total_creance:,.2f} €")
        
        with st.expander("Voir le détail chiffré"):
            st.dataframe(df_final.style.format({"Débit (TTC)": "{:.2f}", "Crédit (TTC)": "{:.2f}", "Intérêts": "{:.2f}", "Date": lambda t: t.strftime("%d/%m/%Y")}))

    # PDF GENERATION
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, f"Date d'arrêt : 26/06/2025", 0, 1)
    pdf.cell(0, 10, f"Loyer Annuel Base : {loyer_ht:,.2f} HT", 0, 1)
    
    # Tableau Synthèse PDF
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 10, "TOTAL GÉNÉRAL A DECLARER", 1)
    pdf.cell(50, 10, f"{total_creance:,.2f} EUR", 1, 1, 'R')
    
    # Détail PDF
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 10, "DETAIL DES CALCULS", 0, 1)
    pdf.set_font("Arial", size=8)
    # En-têtes
    pdf.cell(25, 8, "Date", 1)
    pdf.cell(60, 8, "Libelle", 1)
    pdf.cell(25, 8, "Du (TTC)", 1)
    pdf.cell(25, 8, "Recu", 1)
    pdf.cell(25, 8, "Interets", 1, 1)
    
    for index, row in df_final.iterrows():
        d_str = row['Date'].strftime("%d/%m/%Y")
        pdf.cell(25, 6, d_str, 1)
        pdf.cell(60, 6, str(row['Libellé'])[:35], 1)
        pdf.cell(25, 6, f"{row['Débit (TTC)']:.2f}", 1, 0, 'R')
        pdf.cell(25, 6, f"{row['Crédit (TTC)']:.2f}", 1, 0, 'R')
        pdf.cell(25, 6, f"{row['Intérêts']:.2f}", 1, 1, 'R')

    pdf_buffer = io.BytesIO()
    pdf.output(pdf_buffer)
    
    st.download_button("📄 TÉLÉCHARGER PDF OFFICIEL", data=pdf_buffer.getvalue(), file_name="creance_albion.pdf", mime="application/pdf")

else:
    st.info("👈 Entrez le Loyer Annuel HT pour commencer.")
