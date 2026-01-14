import streamlit as st
import pandas as pd
from datetime import date, datetime
from fpdf import FPDF
import json
import io

# --- CONFIGURATION ---
st.set_page_config(page_title="Albion Monitor V1.1", page_icon="📡", layout="wide")

# --- CONSTANTES ---
DATE_JUGEMENT = date(2025, 6, 26)
DATE_DEBUT_BAIL = date(2019, 6, 1)

# Indices ILC (Pour indexation automatique)
INDICES = {
    "BASE (2019)": 114.06, 
    "2024 (Actuel)": 135.30, 
    "2025 (Estimé)": 139.50
}

# --- UTILITAIRES ---
def json_serial(obj):
    if isinstance(obj, (datetime, date)): return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

def date_en_francais(d):
    """Convertit une date datetime.date en chaîne française"""
    mois = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    return f"{d.day} {mois[d.month]} {d.year}"

# --- MOTEUR DE CALCUL (Indexation ILC) ---
def generer_echeancier_post_rj(loyer_annuel_ht_base):
    # 1. Calcul du Loyer Actuel (2025)
    loyer_mensuel_2025_ht = (loyer_annuel_ht_base / 12) * (INDICES["2024 (Actuel)"] / INDICES["BASE (2019)"])
    loyer_mensuel_2025_ttc = loyer_mensuel_2025_ht * 1.10 
    
    echeances = []
    
    # Échéance 1 : Solde Juin 2025 (4 jours post-jugement)
    montant_juin = (loyer_mensuel_2025_ttc / 30) * 4 
    echeances.append({
        "date": date(2025, 7, 10), 
        "label": "Solde Juin 2025 (Prorata)", 
        "montant": montant_juin
    })
    
    # Échéance 2 : T3 2025
    echeances.append({
        "date": date(2025, 10, 10), 
        "label": "T3 2025 (Juil-Août-Sept)", 
        "montant": loyer_mensuel_2025_ttc * 3
    })
    
    # Échéance 3 : T4 2025
    echeances.append({
        "date": date(2026, 1, 10), 
        "label": "T4 2025 (Oct-Nov-Déc)", 
        "montant": loyer_mensuel_2025_ttc * 3
    })
    
    # Anticipation 2026 (Estimation)
    echeances.append({
        "date": date(2026, 4, 10), 
        "label": "T1 2026 (Jan-Fév-Mars)", 
        "montant": loyer_mensuel_2025_ttc * 3 
    })

    return echeances

# --- GÉNÉRATEUR PDF (Mise en Demeure) ---
class PDFRelance(FPDF):
    def __init__(self, user_info):
        super().__init__()
        self.user_info = user_info

    def header(self):
        self.set_font('Arial', 'I', 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f"Suivi Execution Bail - HOTEL ALBION - Lot {self.user_info.get('lot', '?')}", 0, 1, 'R')
        self.set_text_color(0, 0, 0)

    def generate_letter(self, total_due, table_rows, history_payments):
        self.add_page()
        
        # En-tête
        self.set_font("Arial", 'B', 11)
        self.cell(0, 5, self.user_info.get('nom', ''), 0, 1)
        self.set_font("Arial", '', 10)
        self.cell(0, 5, f"Lot : {self.user_info.get('lot', '')}", 0, 1)
        self.cell(0, 5, f"Email : {self.user_info.get('email', '')}", 0, 1)
        
        self.ln(10)
        self.set_font("Arial", 'B', 11)
        self.cell(0, 5, "A l'attention de l'Administrateur Judiciaire", 0, 1, 'R')
        self.ln(15)
        
        # Titre
        self.set_font("Arial", 'B', 14)
        self.cell(0, 10, "MISE EN DEMEURE DE PAYER SOUS HUITAINE", 0, 1, 'C')
        self.set_font("Arial", 'B', 10)
        self.cell(0, 5, "(Loyers Post-Jugement - Art. L.622-17 Code de commerce)", 0, 1, 'C')
        self.ln(10)
        
        # Corps
        self.set_font("Arial", '', 10)
        txt = ("Maitre,\n\n"
               "Sauf erreur ou omission de ma part, je constate a ce jour un defaut de paiement des loyers "
               "courants (nes posterieurement au jugement d'ouverture).\n\n"
               "Conformement a l'article L.622-17 I du Code de commerce, ces creances sont payables a leur echeance.\n"
               "Le non-paiement de ces sommes constitue un motif de resiliation du bail (Art L.622-14).")
        self.multi_cell(0, 5, txt.encode('latin-1', 'replace').decode('latin-1'))
        self.ln(5)
        
        # Tableau
        self.set_fill_color(255, 200, 200)
        self.set_font("Arial", 'B', 9)
        self.cell(0, 6, "DETAIL DES IMPAYES", 1, 1, 'L', fill=True)
        self.cell(30, 6, "Echeance", 1)
        self.cell(80, 6, "Libelle", 1)
        self.cell(30, 6, "Montant", 1)
        self.cell(30, 6, "Reste Du", 1, 1)
        
        self.set_font("Arial", '', 9)
        for row in table_rows:
            if row['reste'] > 0.01:
                d_str = row['date'].strftime("%d/%m/%Y")
                self.cell(30, 6, d_str, 1)
                self.cell(80, 6, row['label'][:40], 1)
                self.cell(30, 6, f"{row['montant']:.2f}", 1, 0, 'R')
                self.set_font("Arial", 'B', 9)
                self.cell(30, 6, f"{row['reste']:.2f}", 1, 1, 'R')
                self.set_font("Arial", '', 9)
        
        self.ln(5)
        self.set_font("Arial", 'B', 11)
        self.cell(0, 10, f"TOTAL A REGLER : {total_due:,.2f} EUR", 0, 1, 'R')
        
        # Mention frais retard
        self.ln(5)
        self.set_font("Arial", 'I', 9)
        self.cell(0, 5, "Rappel : Des frais de retard s'ajoutent en cas de non paiement le 10 de chaque mois.", 0, 1)
        
        # RIB
        self.ln(5)
        self.set_font("Arial", '', 10)
        self.multi_cell(0, 5, "Virement sur le compte suivant :\n"
                              f"IBAN : {self.user_info.get('iban', '')}\n"
                              f"BIC : {self.user_info.get('bic', '')}")

# --- INTERFACE STREAMLIT ---

# Init Session
if 'paiements' not in st.session_state: st.session_state.paiements = []

# SIDEBAR
with st.sidebar:
    st.header("👤 Propriétaire")
    id_nom = st.text_input("Nom", placeholder="M. Dupont")
    id_lot = st.text_input("Lot", placeholder="A102")
    id_iban = st.text_input("IBAN")
    id_bic = st.text_input("BIC")
    id_email = st.text_input("Email")
    
    st.divider()
    
    # TABLEAU ILC (Demande 1)
    with st.expander("📈 Données Bail & ILC", expanded=True):
        st.write(f"**Début Bail :** {date_en_francais(DATE_DEBUT_BAIL)}")
        st.write("**Indices retenus :**")
        df_indices = pd.DataFrame(list(INDICES.items()), columns=["Période", "Valeur"])
        st.dataframe(df_indices, hide_index=True)
    
    st.divider()
    
    st.header("💾 Données")
    uploaded_file = st.file_uploader("Charger sauvegarde", type=["json"])
    if uploaded_file:
        data = json.load(uploaded_file)
        st.session_state.paiements = [{"date": datetime.strptime(p["date"], "%Y-%m-%d").date(), "montant": p["montant"]} for p in data.get("paiements", [])]
        st.session_state.loyer_base = data.get("loyer_base", 0.0)
        id_nom = data.get("info", {}).get("nom", id_nom)
        st.success("Chargé !")

# HEADER
st.title("📡 Albion Monitor")
st.markdown("### Suivi des Loyers Postérieurs (Art. L.622-17)")

# INPUT LOYER
col1, col2 = st.columns([1, 2])
with col1:
    default_loyer = st.session_state.get("loyer_base", 0.0)
    loyer_annuel_ht = st.number_input("Loyer Annuel Base HT (€)", value=default_loyer, step=100.0)

with col2:
    if loyer_annuel_ht > 0:
        idx_24 = INDICES["2024 (Actuel)"]
        idx_base = INDICES["BASE (2019)"]
        loyer_25_ttc = (loyer_annuel_ht * (idx_24/idx_base)) * 1.10
        st.info(f"**Loyer 2025 indexé :** {loyer_25_ttc:,.2f} € TTC / an\nSoit **{(loyer_25_ttc/4):,.2f} € TTC / trimestre**.")

if loyer_annuel_ht == 0:
    st.stop()

st.divider()

# GESTION
c_pay_1, c_pay_2 = st.columns([1, 2])

with c_pay_1:
    st.subheader("💰 Paiements Reçus")
    with st.form("add_pay"):
        d_pay = st.date_input("Date réception", date.today())
        m_pay = st.number_input("Montant (€)", step=100.0)
        if st.form_submit_button("Ajouter"):
            if d_pay <= DATE_JUGEMENT:
                st.error("Date antérieure au jugement. Utilisez l'app 'Déclaration'.")
            else:
                st.session_state.paiements.append({"date": d_pay, "montant": m_pay})
                st.rerun()
    
    if st.session_state.paiements:
        st.write("Historique :")
        # Affichage avec date française
        disp_pay = []
        for p in st.session_state.paiements:
            disp_pay.append({"Date": date_en_francais(p["date"]), "Montant": f"{p['montant']:.2f} €"})
        st.dataframe(pd.DataFrame(disp_pay), hide_index=True)
        
        if st.button("Supprimer dernier paiement"):
            st.session_state.paiements.pop()
            st.rerun()

with c_pay_2:
    st.subheader("📊 État des Échéances")
    
    echeances = generer_echeancier_post_rj(loyer_annuel_ht)
    total_paye = sum(p['montant'] for p in st.session_state.paiements)
    solde_dispo = total_paye
    
    rows = []
    total_retard = 0
    today = date.today()
    
    for ech in echeances:
        montant = ech['montant']
        couverture = min(montant, solde_dispo)
        solde_dispo -= couverture
        reste = montant - couverture
        
        # Logique des statuts et couleurs
        statut_code = ""
        if reste == 0:
            statut_code = "PAYÉ" # Vert
        elif reste > 0 and couverture > 0:
            statut_code = "RELIQUAT" # Orange
            if ech['date'] <= today:
                total_retard += reste
        elif ech['date'] <= today:
            statut_code = "IMPAYÉ" # Rouge
            total_retard += reste
        else:
            statut_code = "À ÉCHOIR" # Gris
        
        rows.append({
            "date": ech['date'], # Objet date pour tri/pdf
            "Date Exigible": date_en_francais(ech['date']), # String pour affichage (Demande 5)
            "label": ech['label'],
            "montant": montant,
            "paye": couverture,
            "reste": reste,
            "statut": statut_code
        })
        
    df_suivi = pd.DataFrame(rows)
    
    # Styling conditionnel (Demande 3)
    def style_rows(val):
        color = 'black'
        if val == "PAYÉ": color = '#28a745' # Vert
        elif val == "RELIQUAT": color = '#fd7e14' # Orange
        elif val == "IMPAYÉ": color = '#dc3545' # Rouge
        elif val == "À ÉCHOIR": color = '#6c757d' # Gris
        return f'color: {color}; font-weight: bold'

    st.dataframe(
        df_suivi[["Date Exigible", "label", "montant", "paye", "reste", "statut"]].style.format({
            "montant": "{:.2f} €", "paye": "{:.2f} €", "reste": "{:.2f} €"
        }).map(style_rows, subset=['statut']),
        use_container_width=True
    )
    
    # Mention Frais de Retard (Demande 2)
    st.caption("⚠️ **Attention : Des frais de retard s'ajoutent en cas de non paiement le 10 de chaque mois.**")
    
    if total_retard > 0.01:
        st.error(f"⚠️ **RETARD EXIGIBLE : {total_retard:,.2f} €**")
        
        if st.button("🔥 TÉLÉCHARGER MISE EN DEMEURE"):
            user_data = {"nom": id_nom, "lot": id_lot, "iban": id_iban, "bic": id_bic, "email": id_email}
            pdf = PDFRelance(user_data)
            pdf.generate_letter(total_retard, rows, st.session_state.paiements)
            
            st.download_button(
                "📥 PDF Relance",
                data=pdf.output(dest='S').encode('latin-1'),
                file_name=f"Relance_Albion_{date.today()}.pdf",
                mime="application/pdf"
            )
    else:
        if total_paye > 0:
            st.success("✅ Compte à jour.")

# SAUVEGARDE
with st.sidebar:
    st.write("---")
    save_data = {
        "loyer_base": loyer_annuel_ht,
        "paiements": st.session_state.paiements,
        "info": {"nom": id_nom, "lot": id_lot, "iban": id_iban}
    }
    st.download_button("💾 Sauvegarder", json.dumps(save_data, default=json_serial), "albion_monitor.json", "application/json")
