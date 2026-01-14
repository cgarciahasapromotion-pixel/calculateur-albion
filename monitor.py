import streamlit as st
import pandas as pd
from datetime import date, datetime
from fpdf import FPDF
import json
import io

# --- CONFIGURATION ---
st.set_page_config(page_title="Albion Monitor - Suivi Loyers", page_icon="📡", layout="wide")

# --- CONSTANTES ---
DATE_JUGEMENT = date(2025, 6, 26)

# Indices ILC (Pour indexation automatique)
INDICES = {
    "BASE": 114.06, 
    "2024": 135.30, # Sert pour les loyers 2025
    "2025": 139.50  # (Estimation - Sera à mettre à jour)
}

# --- UTILITAIRES ---
def json_serial(obj):
    if isinstance(obj, (datetime, date)): return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

# --- MOTEUR DE CALCUL (Indexation ILC) ---
def generer_echeancier_post_rj(loyer_annuel_ht_base):
    """
    Génère les échéances théoriques à partir du jugement.
    Applique l'indexation ILC automatiquement.
    """
    # 1. Calcul du Loyer Actuel (2025)
    # Formule : Loyer Base * (Indice N-1 / Indice Base)
    loyer_mensuel_2025_ht = (loyer_annuel_ht_base / 12) * (INDICES["2024"] / INDICES["BASE"])
    loyer_mensuel_2025_ttc = loyer_mensuel_2025_ht * 1.10 # TVA 10%
    
    echeances = []
    
    # Échéance 1 : Solde Juin 2025 (4 jours post-jugement : du 27 au 30)
    # Note : Payable début Juillet
    montant_juin = (loyer_mensuel_2025_ttc / 30) * 4 
    echeances.append({
        "date": date(2025, 7, 10), 
        "label": "Solde Juin 2025 (Prorata Post-RJ)", 
        "montant": montant_juin
    })
    
    # Échéance 2 : T3 2025 (Juillet-Août-Sept) -> Payable 10 Octobre (Terme échu)
    echeances.append({
        "date": date(2025, 10, 10), 
        "label": "T3 2025 (Juillet-Août-Sept)", 
        "montant": loyer_mensuel_2025_ttc * 3
    })
    
    # Échéance 3 : T4 2025 -> Payable 10 Janvier 2026
    echeances.append({
        "date": date(2026, 1, 10), 
        "label": "T4 2025 (Oct-Nov-Déc)", 
        "montant": loyer_mensuel_2025_ttc * 3
    })
    
    # Anticipation 2026 (Indexation suivante)
    # Si on avait l'indice 2025, on recalculerait ici. Pour l'instant on projette.
    echeances.append({
        "date": date(2026, 4, 10), 
        "label": "T1 2026 (Jan-Fév-Mars)", 
        "montant": loyer_mensuel_2025_ttc * 3 
    })

    return echeances

# --- GÉNÉRATEUR PDF (Mise en Demeure L.622-17) ---
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
        
        # Titre Agressif
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
               "Le non-paiement de ces sommes constitue un motif de resiliation du bail (Art L.622-14) et "
               "demontre l'impossibilite de financer la periode d'observation.")
        self.multi_cell(0, 5, txt.encode('latin-1', 'replace').decode('latin-1'))
        self.ln(5)
        
        # Tableau 1 : Ce qui a été payé (Preuve de bonne foi)
        if history_payments:
            self.set_fill_color(240, 240, 240)
            self.set_font("Arial", 'B', 9)
            self.cell(0, 6, "I. RAPPEL DES REGLEMENTS RECUS", 1, 1, 'L', fill=True)
            self.cell(40, 6, "Date", 1)
            self.cell(40, 6, "Montant", 1, 1)
            self.set_font("Arial", '', 9)
            for p in history_payments:
                self.cell(40, 6, p['date'].strftime("%d/%m/%Y"), 1)
                self.cell(40, 6, f"{p['montant']:.2f} EUR", 1, 1, 'R')
            self.ln(5)

        # Tableau 2 : Ce qui est dû
        self.set_fill_color(255, 200, 200) # Rouge pâle
        self.set_font("Arial", 'B', 9)
        self.cell(0, 6, "II. DETAIL DES SOMMES EXIGIBLES (IMPAYES)", 1, 1, 'L', fill=True)
        self.cell(30, 6, "Echeance", 1)
        self.cell(80, 6, "Libelle", 1)
        self.cell(30, 6, "Montant", 1)
        self.cell(30, 6, "Reste Du", 1, 1)
        
        self.set_font("Arial", '', 9)
        for row in table_rows:
            if row['reste'] > 0.01:
                self.cell(30, 6, row['date'].strftime("%d/%m/%Y"), 1)
                self.cell(80, 6, row['label'][:40], 1)
                self.cell(30, 6, f"{row['montant']:.2f}", 1, 0, 'R')
                self.set_font("Arial", 'B', 9)
                self.cell(30, 6, f"{row['reste']:.2f}", 1, 1, 'R')
                self.set_font("Arial", '', 9)
        
        self.ln(5)
        self.set_font("Arial", 'B', 11)
        self.cell(0, 10, f"TOTAL A REGLER IMMEDIATEMENT : {total_due:,.2f} EUR", 0, 1, 'R')
        
        # Footer : RIB
        self.ln(5)
        self.set_font("Arial", '', 10)
        self.multi_cell(0, 5, "Merci de proceder au virement sur le compte suivant :\n"
                              f"IBAN : {self.user_info.get('iban', '')}\n"
                              f"BIC : {self.user_info.get('bic', '')}")

# --- INTERFACE STREAMLIT ---

# Init Session
if 'paiements' not in st.session_state: st.session_state.paiements = []

# SIDEBAR : Configuration
with st.sidebar:
    st.header("👤 Propriétaire")
    id_nom = st.text_input("Nom", placeholder="M. Dupont")
    id_lot = st.text_input("Lot", placeholder="A102")
    id_iban = st.text_input("IBAN (Pour le courrier)")
    id_bic = st.text_input("BIC")
    id_email = st.text_input("Email")
    
    st.divider()
    
    st.header("💾 Données")
    # Chargement JSON
    uploaded_file = st.file_uploader("Charger une sauvegarde", type=["json"])
    if uploaded_file:
        data = json.load(uploaded_file)
        st.session_state.paiements = [{"date": datetime.strptime(p["date"], "%Y-%m-%d").date(), "montant": p["montant"]} for p in data.get("paiements", [])]
        st.session_state.loyer_base = data.get("loyer_base", 0.0)
        id_nom = data.get("info", {}).get("nom", id_nom) # Simple reload logic
        st.success("Données chargées.")

# HEADER
st.title("📡 Albion Monitor")
st.markdown("**Surveillance des Loyers Postérieurs (Art. L.622-17)**")

# INPUT LOYER
col1, col2 = st.columns([1, 2])
with col1:
    default_loyer = st.session_state.get("loyer_base", 0.0)
    loyer_annuel_ht = st.number_input("Loyer Annuel de Base HT (€)", value=default_loyer, step=100.0)
    st.caption("Ce montant sera indexé automatiquement par l'app.")

with col2:
    if loyer_annuel_ht > 0:
        # Calcul prévisionnel rapide pour info
        idx_24 = INDICES["2024"]
        idx_base = INDICES["BASE"]
        loyer_25_ttc = (loyer_annuel_ht * (idx_24/idx_base)) * 1.10
        st.info(f"ℹ️ **Info Indexation ILC :**\n\nLe loyer annuel 2025 estimé est de **{loyer_25_ttc:,.2f} € TTC**.\nSoit **{(loyer_25_ttc/4):,.2f} € TTC / Trimestre**.")

if loyer_annuel_ht == 0:
    st.stop()

st.divider()

# GESTION DES PAIEMENTS
c_pay_1, c_pay_2 = st.columns([1, 2])

with c_pay_1:
    st.subheader("💰 Enregistrer un Virement")
    with st.form("add_pay"):
        d_pay = st.date_input("Date réception", date.today())
        m_pay = st.number_input("Montant (€)", step=100.0)
        if st.form_submit_button("Ajouter"):
            if d_pay <= DATE_JUGEMENT:
                st.error(f"Date invalide. Doit être après le {DATE_JUGEMENT.strftime('%d/%m/%Y')}.")
            else:
                st.session_state.paiements.append({"date": d_pay, "montant": m_pay})
                st.rerun()
    
    # Liste + Suppression
    if st.session_state.paiements:
        st.markdown("**Historique :**")
        df_p = pd.DataFrame(st.session_state.paiements)
        st.dataframe(df_p.style.format({"montant": "{:.2f} €"}))
        
        if st.button("🗑️ Supprimer le dernier"):
            st.session_state.paiements.pop()
            st.rerun()

with c_pay_2:
    st.subheader("📊 État des Lieux")
    
    # 1. Générer le théorique
    echeances = generer_echeancier_post_rj(loyer_annuel_ht)
    
    # 2. Calculer le Reste à Charge (Matching)
    total_paye = sum(p['montant'] for p in st.session_state.paiements)
    solde_dispo = total_paye
    
    rows = []
    total_retard = 0
    today = date.today()
    
    for ech in echeances:
        montant = ech['montant']
        # On impute le solde dispo sur l'échéance la plus ancienne
        couverture = min(montant, solde_dispo)
        solde_dispo -= couverture
        reste = montant - couverture
        
        statut = "🟢 À jour"
        if reste > 0.01:
            if ech['date'] <= today:
                statut = "🔴 IMPAYÉ"
                total_retard += reste
            else:
                statut = "⚪ À échoir"
        
        rows.append({
            "date": ech['date'],
            "label": ech['label'],
            "montant": montant,
            "paye": couverture,
            "reste": reste,
            "statut": statut
        })
        
    # 3. Affichage Tableau
    df_suivi = pd.DataFrame(rows)
    
    def color_status(val):
        color = 'red' if 'IMPAYÉ' in val else 'green' if 'À jour' in val else 'grey'
        return f'color: {color}; font-weight: bold'

    st.dataframe(
        df_suivi[["date", "label", "montant", "paye", "reste", "statut"]].style.format({
            "montant": "{:.2f} €", "paye": "{:.2f} €", "reste": "{:.2f} €", "date": lambda t: t.strftime("%d/%m/%Y")
        }).map(color_status, subset=['statut']),
        use_container_width=True
    )
    
    # 4. Indicateur Principal
    if total_retard > 0.01:
        st.error(f"⚠️ **RETARD CUMULÉ : {total_retard:,.2f} €**")
        st.markdown("Le loyer courant n'est pas payé. Action requise.")
        
        if st.button("🔥 GÉNÉRER MISE EN DEMEURE (PDF)"):
            user_data = {"nom": id_nom, "lot": id_lot, "iban": id_iban, "bic": id_bic, "email": id_email}
            pdf = PDFRelance(user_data)
            pdf.generate_letter(total_retard, rows, st.session_state.paiements)
            
            st.download_button(
                "📥 Télécharger le PDF de Relance",
                data=pdf.output(dest='S').encode('latin-1'),
                file_name=f"Relance_Albion_{date.today()}.pdf",
                mime="application/pdf"
            )
            
    else:
        if total_paye > 0:
            st.success("✅ Tout est à jour. Aucune dette post-RJ.")
        else:
            st.warning("En attente des premières échéances...")

# SAUVEGARDE GLOBALE
with st.sidebar:
    st.write("---")
    save_data = {
        "loyer_base": loyer_annuel_ht,
        "paiements": st.session_state.paiements,
        "info": {"nom": id_nom, "lot": id_lot, "iban": id_iban}
    }
    st.download_button("💾 Sauvegarder mes données", json.dumps(save_data, default=json_serial), "albion_monitor.json", "application/json")
