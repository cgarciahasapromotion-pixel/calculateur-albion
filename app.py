import streamlit as st
import pandas as pd
import altair as alt
from datetime import date, datetime, timedelta
from fpdf import FPDF
import io
import json

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Calculateur Créance Albion", page_icon="⚖️", layout="wide")

# --- CSS PERSONNALISÉ (EFFET INTERCALAIRES) ---
st.markdown("""
<style>
    /* Style général des onglets */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px; /* Espace entre les onglets */
    }

    .stTabs [data-baseweb="tab"] {
        height: 60px; /* Hauteur plus importante */
        white-space: pre-wrap;
        border-radius: 10px 10px 0px 0px; /* Arrondi haut comme un dossier */
        padding: 10px 20px;
        font-size: 18px; /* Texte plus gros */
        box-shadow: 0px -2px 5px rgba(0,0,0,0.05);
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-bottom: none;
    }

    /* Onglet 1 : DÉCLARATION (BLEU) */
    .stTabs [data-baseweb="tab"]:nth-of-type(1) {
        border-top: 6px solid #1f77b4; /* Bandeau Bleu */
    }
    
    /* Onglet 2 : SUIVI (ORANGE) */
    .stTabs [data-baseweb="tab"]:nth-of-type(2) {
        border-top: 6px solid #ff7f0e; /* Bandeau Orange */
    }

    /* Onglet Actif (Celui sélectionné) */
    .stTabs [aria-selected="true"] {
        background-color: #ffffff !important;
        font-weight: bold;
        border-bottom: 0px solid transparent;
        box-shadow: none;
    }
    
    /* Onglet Inactif (Hover) */
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #e9ecef;
        color: #000;
    }
</style>
""", unsafe_allow_html=True)

# --- CONSTANTES JURIDIQUES & DONNÉES ---
DATE_JUGEMENT = date(2025, 6, 26)
DATE_DEBUT_GRAPH = date(2019, 6, 1)
INDEMNITE_FORFAITAIRE = 40.0 # Art. D.441-5

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

# --- UTILITAIRES ---
def json_serial(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

def get_taux_legal(d):
    for start_date, rate in reversed(TAUX_LEGAUX):
        if d >= start_date:
            return rate
    return 10.00

def calculer_interets_ligne(montant, date_depart, date_fin):
    total_interets = 0
    if date_depart >= date_fin: return 0.0
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

# --- MOTEUR 1 : PRÉ-RJ (DÉCLARATION) ---
def generer_loyers_theoriques_pre_rj(loyer_annuel_ht):
    # NOTE : Pour la déclaration de créance (passif), on déclare la dette d'occupation
    # arrêtée au jour du jugement, peu importe la date de paiement théorique.
    loyer_annuel_ttc = loyer_annuel_ht * 1.10
    loyer_base_mensuel = loyer_annuel_ttc / 12
    echeances = []
    
    # 2019
    echeances.append({"date": date(2019, 10, 10), "label": "Loyer 2019 (4 mois TTC)", "montant": loyer_base_mensuel * 4})
    
    # 2020
    loyer_2020 = loyer_base_mensuel * (INDICES["2019"] / INDICES["BASE"])
    echeances.append({"date": date(2020, 1, 10), "label": "T1 2020", "montant": loyer_base_mensuel * 3})
    montant_t2_mixte = (loyer_base_mensuel * 2) + (loyer_2020 * 1)
    echeances.append({"date": date(2020, 4, 10), "label": "T2 2020 (Mixte)", "montant": montant_t2_mixte})
    echeances.append({"date": date(2020, 7, 10), "label": "T3 2020", "montant": loyer_2020 * 3})
    echeances.append({"date": date(2020, 10, 10), "label": "T4 2020", "montant": loyer_2020 * 3})
    
    # 2021
    loyer_2021 = loyer_2020 
    for t in range(1, 5): 
        d = date(2021, 1 + (t-1)*3, 10)
        echeances.append({"date": d, "label": f"T{t} 2021", "montant": loyer_2021 * 3})
        
    # 2022
    loyer_2022 = loyer_base_mensuel * (INDICES["2021"] / INDICES["BASE"])
    echeances.append({"date": date(2022, 1, 10), "label": "T1 2022", "montant": loyer_2021 * 3})
    montant_t2_22 = (loyer_2021 * 2) + (loyer_2022 * 1)
    echeances.append({"date": date(2022, 4, 10), "label": "T2 2022 (Indexation)", "montant": montant_t2_22})
    echeances.append({"date": date(2022, 7, 10), "label": "T3 2022", "montant": loyer_2022 * 3})
    echeances.append({"date": date(2022, 10, 10), "label": "T4 2022", "montant": loyer_2022 * 3})
    
    # 2023
    loyer_2023 = loyer_base_mensuel * (INDICES["2022"] / INDICES["BASE"])
    echeances.append({"date": date(2023, 1, 10), "label": "T1 2023", "montant": loyer_2022 * 3})
    montant_t2_23 = (loyer_2022 * 2) + (loyer_2023 * 1)
    echeances.append({"date": date(2023, 4, 10), "label": "T2 2023 (Indexation)", "montant": montant_t2_23})
    echeances.append({"date": date(2023, 7, 10), "label": "T3 2023", "montant": loyer_2023 * 3})
    echeances.append({"date": date(2023, 10, 10), "label": "T4 2023", "montant": loyer_2023 * 3})

    # 2024
    loyer_2024 = loyer_base_mensuel * (INDICES["2023"] / INDICES["BASE"])
    echeances.append({"date": date(2024, 1, 10), "label": "T1 2024", "montant": loyer_2023 * 3})
    montant_t2_24 = (loyer_2023 * 2) + (loyer_2024 * 1)
    echeances.append({"date": date(2024, 4, 10), "label": "T2 2024 (Indexation)", "montant": montant_t2_24})
    echeances.append({"date": date(2024, 7, 10), "label": "T3 2024", "montant": loyer_2024 * 3})
    echeances.append({"date": date(2024, 10, 10), "label": "T4 2024", "montant": loyer_2024 * 3})

    # 2025 (Jusqu'au RJ)
    echeances.append({"date": date(2025, 1, 10), "label": "T1 2025", "montant": loyer_2024 * 3})
    loyer_2025 = loyer_base_mensuel * (INDICES["2024"] / INDICES["BASE"])
    montant_avril_mai = loyer_2024 * 2
    echeances.append({"date": date(2025, 4, 10), "label": "Avril-Mai 2025", "montant": montant_avril_mai})
    montant_juin_prorata = (loyer_2025 / 30) * 26
    echeances.append({"date": date(2025, 6, 26), "label": "Juin 2025 (Prorata 26j)", "montant": montant_juin_prorata})

    return echeances

# --- MOTEUR 2 : POST-RJ (SUIVI COURANT - TERME ÉCHU) ---
def generer_loyers_post_rj(loyer_annuel_ht):
    """Génère les loyers à partir du 27/06/2025 (PAYABLES À TERME ÉCHU)"""
    loyer_annuel_ttc = loyer_annuel_ht * 1.10
    loyer_base_mensuel = loyer_annuel_ttc / 12
    # Loyer provisionnel (Dernier indice connu)
    loyer_mensuel_2025 = loyer_base_mensuel * (INDICES["2024"] / INDICES["BASE"])
    
    echeances = []
    
    # 1. Solde Juin 2025 (Payable Juillet)
    montant_fin_juin = (loyer_mensuel_2025 / 30) * 4
    echeances.append({
        "date": date(2025, 7, 10), # Exigible en Juillet
        "label": "Solde Juin 2025 (Payable Juillet)",
        "montant": montant_fin_juin
    })
    
    # 2. T3 2025 (Payable Octobre)
    echeances.append({
        "date": date(2025, 10, 10),
        "label": "T3 2025 (Payable Octobre)",
        "montant": loyer_mensuel_2025 * 3
    })
    
    # 3. T4 2025 (Payable Janvier 26)
    echeances.append({
        "date": date(2026, 1, 10),
        "label": "T4 2025 (Payable Janvier 26)",
        "montant": loyer_mensuel_2025 * 3
    })
    
    # 4. T1 2026 (Payable Avril 26)
    echeances.append({
        "date": date(2026, 4, 10),
        "label": "T1 2026 (Payable Avril 26)",
        "montant": loyer_mensuel_2025 * 3
    })

    return echeances

# --- CLASSES PDF ---
class PDFDeclaration(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Declaration de Creance - HOTEL ALBION', 0, 1, 'C')
        self.set_font('Arial', 'I', 9)
        self.cell(0, 10, '(Arret des comptes au Jugement d\'Ouverture : 26/06/2025)', 0, 1, 'C')
        self.ln(5)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

class PDFRelance(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'MISE EN DEMEURE - LOYERS POSTERIEURS', 0, 1, 'C')
        self.set_font('Arial', 'I', 9)
        self.cell(0, 10, '(Article L. 622-17 du Code de commerce)', 0, 1, 'C')
        self.ln(5)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

# ==========================================
# INTERFACE STREAMLIT
# ==========================================

# --- GESTION SESSION STATE & IMPORT ---
if 'paiements_pre' not in st.session_state:
    st.session_state.paiements_pre = []
if 'paiements_post' not in st.session_state:
    st.session_state.paiements_post = []

with st.sidebar:
    st.header("💾 Données")
    uploaded_file = st.file_uploader("📂 Charger Dossier (.json)", type=["json"])
    if uploaded_file:
        try:
            data = json.load(uploaded_file)
            st.session_state.paiements_pre = []
            for p in data.get("paiements", []):
                st.session_state.paiements_pre.append({"date": datetime.strptime(p["date"], "%Y-%m-%d").date(), "montant": p["montant"]})
            st.session_state.paiements_post = []
            for p in data.get("paiements_post", []):
                st.session_state.paiements_post.append({"date": datetime.strptime(p["date"], "%Y-%m-%d").date(), "montant": p["montant"]})
            st.session_state.loaded_loyer = data.get("loyer", 0.0)
            st.success("Dossier chargé !")
        except:
            st.error("Erreur fichier.")

st.title("🏛️ Gestionnaire Créance - Propriétaires Albion")

col_loyer, col_save = st.columns([1, 3])
with col_loyer:
    def_loyer = st.session_state.get("loaded_loyer", 0.0)
    loyer_ht = st.number_input("1. Loyer Annuel HT (€)", min_value=0.0, step=100.0, value=def_loyer, format="%.2f")
    if loyer_ht > 0:
        st.success(f"TTC : {(loyer_ht*1.10):,.2f} €")

with col_save:
    if loyer_ht > 0:
        st.write("") 
        st.write("") 
        save_data = {
            'loyer': loyer_ht, 
            'paiements': st.session_state.paiements_pre,
            'paiements_post': st.session_state.paiements_post
        }
        st.download_button("💾 SAUVEGARDER TOUT", json.dumps(save_data, default=json_serial), f"albion_backup_{date.today()}.json", "application/json")

if loyer_ht == 0:
    st.warning("👈 Commencez par saisir le Loyer Annuel HT ci-dessus.")
    st.stop()

# --- ONGLETS (TABS) ---
tab1, tab2 = st.tabs(["1. 🔒 DÉCLARATION (Dettes Anciennes)", "2. 🔄 SUIVI LOYERS (Après RJ)"])

# ==========================================
# ONGLET 1 : ANCIEN SYSTÈME (PRÉ-RJ)
# ==========================================
with tab1:
    st.info("### 🟦 ESPACE DÉCLARATION DE CRÉANCE\n\nConcerne uniquement les loyers et dettes **AVANT le jugement (26 Juin 2025)**.")
    
    col_legal_1, col_legal_2 = st.columns(2)
    with col_legal_1:
        with st.expander("📚 MODE D'EMPLOI JURIDIQUE", expanded=False):
             st.markdown("""
            **1. Méthode "Waterfall" (Art. 1343-1 C. Civil) :**
            Les paiements remboursent **d'abord les intérêts**, puis le capital.
            
            **2. Indemnité Forfaitaire (Art. D.441-5) :**
            +40 € ajoutés automatiquement pour chaque impayé.
            
            **3. Signature :**
            Le PDF inclut la mention "Certifié sincère" et les réserves d'usage.
            """)
    with col_legal_2:
        with st.expander("📈 TABLEAUX DE RÉFÉRENCE", expanded=False):
            st.markdown("**Indices ILC**")
            st.dataframe(pd.DataFrame(list(INDICES.items()), columns=["Année", "Indice"]), hide_index=True)
            
            st.markdown("**Taux Intérêts (BCE + 10pts)**")
            data_taux = [{"Date": d.strftime("%d/%m/%Y"), "Taux": f"{t:.2f} %"} for d, t in TAUX_LEGAUX]
            st.dataframe(pd.DataFrame(data_taux), hide_index=True)

    st.write("---")

    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown("#### Saisie des Paiements (Passé)")
        with st.form("ajout_pre"):
            d_p = st.date_input("Date du Virement", date(2024, 1, 1), format="DD/MM/YYYY") 
            m_p = st.number_input("Montant TTC (€)", step=100.0)
            if st.form_submit_button("Ajouter à la liste"):
                if d_p > DATE_JUGEMENT:
                    st.error("❌ Date postérieure au jugement ! Allez dans l'Onglet 2.")
                else:
                    st.session_state.paiements_pre.append({"date": d_p, "montant": m_p})
                    st.rerun()
        
        if st.session_state.paiements_pre:
            st.dataframe(pd.DataFrame(st.session_state.paiements_pre).style.format({"montant": "{:.2f} €", "date": lambda t: t.strftime("%d/%m/%Y")}))
            if st.button("🗑️ Effacer Liste Avant RJ"):
                st.session_state.paiements_pre = []
                st.rerun()

    with c2:
        # --- LOGIQUE DE MASQUAGE CONDITIONNEL (UX) ---
        has_paiements = len(st.session_state.paiements_pre) > 0
        
        if not has_paiements:
            # Panneau d'attente
            st.info("👋 **En attente de vos données...**")
            st.markdown("""
            Pour calculer votre créance exacte, l'outil doit connaître vos encaissements.
            
            1. **Saisissez vos virements reçus** dans le formulaire à gauche.
            2. **OU** cochez la case ci-dessous si vous n'avez **rien reçu**.
            """)
            
            no_payment_check = st.checkbox("Je certifie n'avoir reçu AUCUN paiement (Impayé total)", key="check_no_pay_pre")
            
            if not no_payment_check:
                st.stop() # On arrête l'affichage ici tant que rien n'est fait

        # SI ON ARRIVE ICI : Soit des paiements, soit case cochée
        echeances = generer_loyers_theoriques_pre_rj(loyer_ht)
        events = []
        nb_echeances = 0
        for ech in echeances:
            events.append({"date": ech["date"], "type": "LOYER", "montant": ech["montant"], "label": ech["label"]})
            nb_echeances += 1
        for p in st.session_state.paiements_pre:
            events.append({"date": p["date"], "type": "PAIEMENT", "montant": p["montant"], "label": "Virement"})
        
        events.sort(key=lambda x: x["date"])
        
        solde_princ = 0.0
        solde_int = 0.0
        last_date = events[0]["date"] if events else DATE_DEBUT_GRAPH
        data_detail = []
        
        for ev in events:
            curr = ev["date"]
            if curr > last_date and solde_princ > 0:
                solde_int += calculer_interets_ligne(solde_princ, last_date, curr)
            
            montant = ev["montant"]
            if ev["type"] == "LOYER":
                solde_princ += montant
                data_detail.append({"Date": curr, "Lib": ev["label"], "Debit": montant, "Credit": 0, "R_Princ": solde_princ, "R_Int": solde_int})
            else:
                imp_int = min(montant, solde_int)
                solde_int -= imp_int
                imp_princ = montant - imp_int
                solde_princ -= imp_princ
                data_detail.append({"Date": curr, "Lib": "Paiement", "Debit": 0, "Credit": montant, "R_Princ": solde_princ, "R_Int": solde_int})
            last_date = curr
            
        if last_date < DATE_JUGEMENT and solde_princ > 0:
            solde_int += calculer_interets_ligne(solde_princ, last_date, DATE_JUGEMENT)
        
        princ_net = max(0, solde_princ)
        int_net = max(0, solde_int)
        indemnite = nb_echeances * INDEMNITE_FORFAITAIRE
        total_decl = princ_net + int_net + indemnite
        
        st.markdown(f"### 🏁 Total à Déclarer : {total_decl:,.2f} €")
        cols = st.columns(3)
        cols[0].metric("Principal (Privilégié)", f"{princ_net:,.2f} €")
        cols[1].metric("Intérêts (Chiro.)", f"{int_net:,.2f} €")
        cols[2].metric("Indemnités (Chiro.)", f"{indemnite:,.2f} €")
        
        st.write("---")
        if data_detail:
            df_final = pd.DataFrame(data_detail)
            df_graph = df_final[["Date", "R_Princ", "R_Int"]].copy()
            df_graph.rename(columns={"R_Princ": "Dette Principal", "R_Int": "Intérêts Cumulés"}, inplace=True)
            df_graph.loc[len(df_graph)] = [DATE_JUGEMENT, princ_net, int_net]
            df_graph_melted = df_graph.melt('Date', var_name='Type', value_name='Montant (€)')

            chart = alt.Chart(df_graph_melted).mark_line(strokeWidth=3, interpolate='step-after').encode(
                x=alt.X('Date', axis=alt.Axis(format='%d/%m/%Y')),
                y=alt.Y('Montant (€)'),
                color=alt.Color('Type', scale=alt.Scale(range=['#1f77b4', '#d62728'])),
                tooltip=['Date', 'Type', 'Montant (€)']
            )
            st.altair_chart(chart.interactive(), use_container_width=True)

        pdf = PDFDeclaration()
        pdf.add_page()
        pdf.set_font("Arial", '', 10)
        pdf.cell(0, 10, f"Total a Declarer : {total_decl:,.2f} EUR", 0, 1)
        pdf.cell(0, 5, f"- Dont Principal : {princ_net:,.2f} EUR", 0, 1)
        pdf.cell(0, 5, f"- Dont Interets : {int_net:,.2f} EUR", 0, 1)
        pdf.cell(0, 5, f"- Dont Indemnites : {indemnite:,.2f} EUR", 0, 1)
        
        pdf.ln(10)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 10, "DETAIL", 0, 1)
        pdf.set_font("Arial", '', 8)
        for row in data_detail:
            pdf.cell(20, 6, row["Date"].strftime("%d/%m/%Y"), 1)
            pdf.cell(60, 6, str(row["Lib"])[:30].encode('latin-1','replace').decode('latin-1'), 1)
            pdf.cell(25, 6, f"{row['Debit']:.2f}", 1, 0, 'R')
            pdf.cell(25, 6, f"{row['Credit']:.2f}", 1, 0, 'R')
            pdf.cell(25, 6, f"{row['R_Princ']:.2f}", 1, 1, 'R')
            
        pdf.ln(10)
        pdf.set_font("Arial", '', 10)
        if pdf.get_y() > 240: pdf.add_page()
        pdf.cell(0, 5, "Certifie sincere et veritable, arrete au 26/06/2025.", 0, 1)
        pdf.cell(0, 30, "Signature : .................................", 0, 1)
        pdf.set_font("Arial", 'I', 8)
        pdf.cell(0, 5, "Sous reserve des loyers a echoir (Art. L. 622-24).", 0, 1, 'C')
        
        st.download_button("📄 TÉLÉCHARGER PDF DÉCLARATION", pdf.output(dest='S').encode('latin-1'), "creance_albion.pdf", "application/pdf")


# ==========================================
# ONGLET 2 : NOUVEAU SYSTÈME (POST-RJ)
# ==========================================
with tab2:
    st.warning("### 🟧 ESPACE SUIVI & MISE EN DEMEURE (Post-Jugement)\n\nConcerne les loyers courants **APRÈS le 26 Juin 2025**. (Payable à Terme Échu = Le mois suivant le trimestre).")
    
    col_p1, col_p2 = st.columns([1, 2])
    
    with col_p1:
        st.markdown("#### Saisie Paiements Reçus (Futur)")
        with st.form("ajout_post"):
            d_p_post = st.date_input("Date du Virement", date.today(), format="DD/MM/YYYY") 
            m_p_post = st.number_input("Montant Reçu (€)", step=100.0)
            if st.form_submit_button("Ajouter Paiement Admin."):
                if d_p_post <= DATE_JUGEMENT:
                    st.error("❌ Date antérieure au jugement ! Allez dans l'Onglet 1.")
                else:
                    st.session_state.paiements_post.append({"date": d_p_post, "montant": m_p_post})
                    st.rerun()
        
        if st.session_state.paiements_post:
            st.dataframe(pd.DataFrame(st.session_state.paiements_post).style.format({"montant": "{:.2f} €", "date": lambda t: t.strftime("%d/%m/%Y")}))
            if st.button("🗑️ Effacer Liste Post RJ"):
                st.session_state.paiements_post = []
                st.rerun()

    with col_p2:
        # --- LOGIQUE MASQUAGE CONDITIONNEL POST-RJ ---
        has_paiements_post = len(st.session_state.paiements_post) > 0
        
        if not has_paiements_post:
             st.info("👋 **Aucun paiement Admin saisi.**")
             st.markdown("Veuillez saisir les virements reçus de l'Administrateur Judiciaire (s'il y en a) pour voir l'état des lieux.")
             no_pay_check_post = st.checkbox("Je n'ai rien reçu depuis le jugement", key="check_no_pay_post")
             
             if not no_pay_check_post:
                 st.stop()

        echeances_post = generer_loyers_post_rj(loyer_ht)
        
        solde_disponible = sum(p["montant"] for p in st.session_state.paiements_post)
        
        table_rows = []
        today = date.today()
        total_a_reclamer_immediatement = 0
        
        st.markdown("#### État des lieux (Imputation Chronologique)")
        
        for ech in echeances_post:
            montant_du = ech["montant"]
            paye_sur_cette_ech = min(montant_du, solde_disponible)
            solde_disponible -= paye_sur_cette_ech
            reste_a_payer = montant_du - paye_sur_cette_ech
            
            if reste_a_payer == 0:
                statut = "🟢 PAYÉ"
            elif paye_sur_cette_ech > 0:
                statut = "🟠 PARTIEL"
            else:
                if ech["date"] <= today:
                    statut = "🔴 IMPAYÉ"
                else:
                    statut = "⚪ À ÉCHOIR"
            
            if ech["date"] <= today:
                total_a_reclamer_immediatement += reste_a_payer

            table_rows.append({
                "Échéance": ech["date"],
                "Libellé": ech["label"],
                "Montant": montant_du,
                "Payé": paye_sur_cette_ech,
                "Reste Dû": reste_a_payer,
                "Statut": statut
            })
            
        df_post = pd.DataFrame(table_rows)

        # FONCTION DE STYLE POUR LES PASTILLES DE COULEUR
        def highlight_status(val):
            if "PAYÉ" in val:
                return 'background-color: #d4edda; color: #155724; font-weight: bold' # Vert
            elif "PARTIEL" in val:
                return 'background-color: #fff3cd; color: #856404; font-weight: bold' # Orange
            elif "IMPAYÉ" in val:
                return 'background-color: #f8d7da; color: #721c24; font-weight: bold' # Rouge
            elif "ÉCHOIR" in val:
                return 'color: #6c757d'
            return ''

        # AFFICHAGE DU TABLEAU STYLISÉ
        st.dataframe(df_post.style.format({
            "Montant": "{:.2f} €", 
            "Payé": "{:.2f} €", 
            "Reste Dû": "{:.2f} €", 
            "Échéance": lambda t: t.strftime("%d/%m/%Y")
        }).map(highlight_status, subset=["Statut"]))
        
        st.write("---")
        st.metric("⚠️ TOTAL IMPAYÉ EXIGIBLE (Mise en demeure)", f"{total_a_reclamer_immediatement:,.2f} €", delta_color="inverse")
        
        if total_a_reclamer_immediatement > 0:
            st.error(f"L'administrateur vous doit {total_a_reclamer_immediatement:,.2f} € immédiatement.")
            
            pdf_r = PDFRelance()
            pdf_r.add_page()
            pdf_r.set_font("Arial", '', 10)
            
            pdf_r.cell(0, 5, f"Date : {date.today().strftime('%d/%m/%Y')}", 0, 1, 'R')
            pdf_r.ln(10)
            
            pdf_r.set_font("Arial", 'B', 10)
            pdf_r.cell(0, 5, "Objet : Mise en demeure de payer les loyers posterieurs (Art L.622-17)", 0, 1)
            pdf_r.ln(5)
            
            pdf_r.set_font("Arial", '', 10)
            txt_intro = ("Maitre,\n\n"
                         "En ma qualite de bailleur (Lot 6 - Hotel Albion), je vous sollicite concernant le paiement "
                         "des loyers courus depuis le jugement d'ouverture du 26/06/2025.\n\n"
                         "Conformement a l'article L.622-17 du Code de commerce, ces creances sont payables a leur echeance (Terme Echu).\n"
                         "A ce jour, apres imputation des versements recus, je constate un solde impaye exigible de :")
            pdf_r.multi_cell(0, 5, txt_intro.encode('latin-1','replace').decode('latin-1'))
            
            pdf_r.ln(5)
            pdf_r.set_font("Arial", 'B', 12)
            pdf_r.cell(0, 10, f"NET A PAYER : {total_a_reclamer_immediatement:,.2f} EUR", 0, 1, 'C')
            
            pdf_r.ln(5)
            pdf_r.set_font("Arial", 'B', 9)
            pdf_r.cell(0, 5, "DETAIL DES ECHEANCES:", 0, 1)
            
            pdf_r.set_font("Arial", '', 9)
            pdf_r.cell(30, 6, "Echeance", 1)
            pdf_r.cell(70, 6, "Libelle", 1)
            pdf_r.cell(30, 6, "Montant", 1)
            pdf_r.cell(30, 6, "Reste Du", 1, 1)
            
            for row in table_rows:
                if row["Statut"] in ["🔴 IMPAYÉ", "🟠 PARTIEL"] and row["Reste Dû"] > 0.01:
                    pdf_r.cell(30, 6, row["Échéance"].strftime("%d/%m/%Y"), 1)
                    pdf_r.cell(70, 6, str(row["Libellé"]).encode('latin-1','replace').decode('latin-1'), 1)
                    pdf_r.cell(30, 6, f"{row['Montant']:.2f}", 1, 0, 'R')
                    pdf_r.cell(30, 6, f"{row['Reste Dû']:.2f}", 1, 1, 'R')
            
            pdf_r.ln(10)
            pdf_r.multi_cell(0, 5, "Je vous demande de proceder au reglement sans delai.\nSignature : ..................................")

            st.download_button("📩 TÉLÉCHARGER LETTRE DE RELANCE", pdf_r.output(dest='S').encode('latin-1'), "relance_loyers_post_rj.pdf", "application/pdf")
        
        else:
            if solde_disponible > 0:
                st.success(f"✅ Loyers à jour ! Vous avez même une avance de {solde_disponible:,.2f} €.")
            else:
                st.success("✅ Tous les loyers exigibles sont réglés.")
