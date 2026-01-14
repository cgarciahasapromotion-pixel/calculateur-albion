import streamlit as st
import pandas as pd
from datetime import date, datetime
from fpdf import FPDF
import json
import io

# --- CONFIGURATION ---
st.set_page_config(page_title="Albion Monitor V1.3 (Waterfall)", page_icon="📡", layout="wide")

# --- CONSTANTES ---
DATE_JUGEMENT = date(2025, 6, 26)
DATE_DEBUT_BAIL = date(2019, 6, 1)
INDEMNITE_FORFAITAIRE = 40.0

# Indices ILC
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
    mois = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    return f"{d.day} {mois[d.month]} {d.year}"

# --- MOTEUR DE CALCUL ---
def generer_echeancier_post_rj(loyer_annuel_ht_base):
    # 1. Calcul du Loyer Actuel (2025)
    loyer_mensuel_2025_ht = (loyer_annuel_ht_base / 12) * (INDICES["2024 (Actuel)"] / INDICES["BASE (2019)"])
    loyer_mensuel_2025_ttc = loyer_mensuel_2025_ht * 1.10 
    
    echeances = []
    
    # Échéance 1 : Solde Juin
    montant_juin = (loyer_mensuel_2025_ttc / 30) * 4 
    echeances.append({
        "date": date(2025, 7, 10), 
        "label": "Solde Juin 2025 (Prorata)", 
        "montant": montant_juin,
        "type": "loyer"
    })
    
    # Échéance 2 : T3 2025
    echeances.append({
        "date": date(2025, 10, 10), 
        "label": "T3 2025 (Juil-Août-Sept)", 
        "montant": loyer_mensuel_2025_ttc * 3,
        "type": "loyer"
    })
    
    # Échéance 3 : T4 2025
    echeances.append({
        "date": date(2026, 1, 10), 
        "label": "T4 2025 (Oct-Nov-Déc)", 
        "montant": loyer_mensuel_2025_ttc * 3,
        "type": "loyer"
    })
    
    # Anticipation 2026
    echeances.append({
        "date": date(2026, 4, 10), 
        "label": "T1 2026 (Jan-Fév-Mars)", 
        "montant": loyer_mensuel_2025_ttc * 3,
        "type": "loyer"
    })

    return echeances

# --- GÉNÉRATEUR PDF ---
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
               "Conformement a l'article L.622-17 I du Code de commerce, ces creances sont payables a leur echeance.\n\n"
               "IMPORTANT : En application de l'article 1343-1 du Code Civil, les paiements partiels recus ont ete "
               "imputes prioritairement sur les interets et penalites de retard, et subsidiairement sur le capital.\n\n"
               "Le non-paiement de ces sommes constitue un motif de resiliation du bail (Art L.622-14).")
        self.multi_cell(0, 5, txt.encode('latin-1', 'replace').decode('latin-1'))
        self.ln(5)
        
        # Tableau
        self.set_fill_color(255, 200, 200)
        self.set_font("Arial", 'B', 9)
        self.cell(0, 6, "DETAIL DES IMPAYES (METHODE WATERFALL ART. 1343-1 CC)", 1, 1, 'L', fill=True)
        self.cell(30, 6, "Exigibilite", 1)
        self.cell(80, 6, "Libelle", 1)
        self.cell(30, 6, "Montant", 1)
        self.cell(30, 6, "Reste Du", 1, 1)
        
        self.set_font("Arial", '', 9)
        for row in table_rows:
            if row['reste'] > 0.01:
                # Police Italique pour les indemnités
                if "Indemnité" in row['label']: self.set_font("Arial", 'I', 9)
                else: self.set_font("Arial", '', 9)
                
                d_str = row['date'].strftime("%d/%m/%Y")
                self.cell(30, 6, d_str, 1)
                self.cell(80, 6, row['label'][:45].encode('latin-1', 'replace').decode('latin-1'), 1)
                self.cell(30, 6, f"{row['montant']:.2f}", 1, 0, 'R')
                self.cell(30, 6, f"{row['reste']:.2f}", 1, 1, 'R')
        
        self.ln(5)
        self.set_font("Arial", 'B', 11)
        self.cell(0, 10, f"TOTAL EXIGIBLE : {total_due:,.2f} EUR", 0, 1, 'R')
        
        self.ln(5)
        self.set_font("Arial", '', 10)
        self.multi_cell(0, 5, "Virement sur le compte suivant :\n"
                              f"IBAN : {self.user_info.get('iban', '')}\n"
                              f"BIC : {self.user_info.get('bic', '')}")

# --- INTERFACE STREAMLIT ---

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
    with st.expander("📈 Données Bail & ILC", expanded=True):
        st.write(f"**Début Bail :** {date_en_francais(DATE_DEBUT_BAIL)}")
        st.write("**Indices retenus :**")
        df_indices = pd.DataFrame(list(INDICES.items()), columns=["Période", "Valeur"])
        st.dataframe(df_indices, hide_index=True)
    
    st.divider()
    uploaded_file = st.file_uploader("Charger sauvegarde", type=["json"])
    if uploaded_file:
        data = json.load(uploaded_file)
        st.session_state.paiements = [{"date": datetime.strptime(p["date"], "%Y-%m-%d").date(), "montant": p["montant"]} for p in data.get("paiements", [])]
        st.session_state.loyer_base = data.get("loyer_base", 0.0)
        id_nom = data.get("info", {}).get("nom", id_nom)
        st.success("Chargé !")

# HEADER
st.title("📡 Albion Monitor")
st.markdown("### Suivi des Loyers Postérieurs (Méthode Waterfall)")

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

if loyer_annuel_ht == 0: st.stop()

st.divider()

# GESTION PAIEMENTS
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
        disp_pay = []
        for p in st.session_state.paiements:
            disp_pay.append({"Date": date_en_francais(p["date"]), "Montant": f"{p['montant']:.2f} €"})
        st.dataframe(pd.DataFrame(disp_pay), hide_index=True)
        if st.button("Supprimer dernier paiement"):
            st.session_state.paiements.pop()
            st.rerun()

# CŒUR DU SYSTÈME : CASCADE WATERFALL
with c_pay_2:
    st.subheader("📊 Tableau de Bord (Cascade)")
    
    # 1. Préparation des Dettes
    base_loyers = generer_echeancier_post_rj(loyer_annuel_ht)
    all_debts = []
    
    today = date.today()
    
    # On éclate les loyers et on crée les pénalités si nécessaire
    for item in base_loyers:
        # La dette de loyer existe toujours
        all_debts.append({
            "date": item['date'],
            "label": item['label'],
            "montant": item['montant'],
            "type": "PRINCIPAL",
            "paye": 0.0,
            "reste": item['montant']
        })
        
        # La pénalité existe si la date est dépassée
        if item['date'] <= today:
            all_debts.append({
                "date": item['date'], # Même date pour le tri, mais priorité différente
                "label": f"↪ Indemnité Forfaitaire (Retard {item['label']})",
                "montant": INDEMNITE_FORFAITAIRE,
                "type": "PENALITE", # Prioritaire
                "paye": 0.0,
                "reste": INDEMNITE_FORFAITAIRE
            })
            
    # 2. Tri Intelligent pour la Cascade
    # On veut payer d'abord TOUTES les pénalités (anciennes et récentes), PUIS les loyers (anciens puis récents)
    # Astuce : On trie par Type (Penalité < Principal) puis par Date
    debts_to_pay = sorted(all_debts, key=lambda x: (0 if x['type'] == 'PENALITE' else 1, x['date']))
    
    # 3. Application du Paiement (Siphon)
    solde_dispo = sum(p['montant'] for p in st.session_state.paiements)
    total_retard = 0
    
    for debt in debts_to_pay:
        # On paie ce qu'on peut
        paiement_sur_cette_dette = min(debt['montant'], solde_dispo)
        
        debt['paye'] = paiement_sur_cette_dette
        debt['reste'] = debt['montant'] - paiement_sur_cette_dette
        
        solde_dispo -= paiement_sur_cette_dette
        
        # Calcul du retard exigible (seulement si la dette est échue)
        if debt['date'] <= today:
            total_retard += debt['reste']

    # 4. Remise en ordre Chronologique pour l'Affichage
    debts_display = sorted(debts_to_pay, key=lambda x: x['date'])
    
    final_rows = []
    for d in debts_display:
        statut = ""
        if d['reste'] == 0: statut = "PAYÉ"
        elif d['reste'] < d['montant']: statut = "RELIQUAT"
        elif d['date'] <= today: statut = "IMPAYÉ" # Ou DÛ pour pénalité
        else: statut = "À ÉCHOIR"
        
        final_rows.append({
            "Date Exigible": date_en_francais(d['date']),
            "label": d['label'],
            "montant": d['montant'],
            "paye": d['paye'],
            "reste": d['reste'],
            "statut": statut,
            "raw_date": d['date'], # Pour le PDF
            "raw_label": d['label'] # Pour le PDF
        })

    # 5. Rendu Tableau
    df_suivi = pd.DataFrame(final_rows)
    
    def style_rows(val):
        color = 'black'
        if val == "PAYÉ": color = '#28a745'
        elif val == "RELIQUAT": color = '#fd7e14' # Orange
        elif "IMPAYÉ" in val: color = '#dc3545'
        elif "À ÉCHOIR" in val: color = '#6c757d'
        return f'color: {color}; font-weight: bold'

    st.dataframe(
        df_suivi[["Date Exigible", "label", "montant", "paye", "reste", "statut"]].style.format({
            "montant": "{:.2f} €", "paye": "{:.2f} €", "reste": "{:.2f} €"
        }).map(style_rows, subset=['statut']),
        use_container_width=True
    )
    
    st.caption("ℹ️ *Application stricte Art. 1343-1 CC : Les paiements éteignent d'abord les pénalités.*")
    
    if total_retard > 0.01:
        st.error(f"⚠️ **RETARD EXIGIBLE TOTAL : {total_retard:,.2f} €**")
        
        if st.button("🔥 TÉLÉCHARGER MISE EN DEMEURE (PDF)"):
            user_data = {"nom": id_nom, "lot": id_lot, "iban": id_iban, "bic": id_bic, "email": id_email}
            pdf = PDFRelance(user_data)
            
            # On prépare les données pour le PDF (on a besoin des objets bruts)
            rows_for_pdf = []
            for r in final_rows:
                rows_for_pdf.append({
                    "date": r['raw_date'],
                    "label": r['raw_label'],
                    "montant": r['montant'],
                    "reste": r['reste']
                })
                
            pdf.generate_letter(total_retard, rows_for_pdf, st.session_state.paiements)
            
            st.download_button(
                "📥 PDF Relance",
                data=pdf.output(dest='S').encode('latin-1'),
                file_name=f"Relance_Albion_{date.today()}.pdf",
                mime="application/pdf"
            )
    else:
        if sum(p['montant'] for p in st.session_state.paiements) > 0: 
            st.success("✅ Compte à jour.")

with st.sidebar:
    st.write("---")
    save_data = {
        "loyer_base": loyer_annuel_ht,
        "paiements": st.session_state.paiements,
        "info": {"nom": id_nom, "lot": id_lot, "iban": id_iban}
    }
    st.download_button("💾 Sauvegarder", json.dumps(save_data, default=json_serial), "albion_monitor.json", "application/json")
