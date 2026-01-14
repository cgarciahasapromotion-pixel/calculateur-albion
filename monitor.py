import streamlit as st
import pandas as pd
from datetime import date, datetime
from fpdf import FPDF
import json
import io
import matplotlib.pyplot as plt
import tempfile

# --- CONFIGURATION ---
st.set_page_config(page_title="Albion Monitor V1.6 (Auditor)", page_icon="📡", layout="wide")

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
    if not isinstance(d, (date, datetime)): return ""
    mois = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    return f"{d.day} {mois[d.month]} {d.year}"

# --- MOTEUR DE CALCUL ---
def generer_echeancier_post_rj(loyer_annuel_ht_base):
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

# --- GÉNÉRATEUR GRAPHIQUE (MATPLOTLIB) ---
def create_debt_chart(data_rows):
    # Préparation des données pour le graph
    labels = []
    montants_dus = []
    montants_payes = []
    
    for row in data_rows:
        # On ne prend que les lignes principales (pas les pénalités pour la lisibilité du graph global)
        if "Indemnité" not in row['label']:
            short_label = row['date'].strftime("%b %y") # Ex: Oct 25
            labels.append(short_label)
            montants_dus.append(row['montant'])
            montants_payes.append(row['paye'])
            
    fig, ax = plt.subplots(figsize=(7, 3))
    
    # Barres "Dû" (Rouge - Fond)
    ax.bar(labels, montants_dus, color='#ffebee', edgecolor='#ef5350', label='Montant Dû', width=0.6)
    # Barres "Payé" (Vert - Devant)
    ax.bar(labels, montants_payes, color='#c8e6c9', edgecolor='#66bb6a', label='Montant Payé', width=0.6)
    
    ax.set_ylabel('Montant (€)', fontsize=8)
    ax.set_title('Suivi Visuel des Paiements (Dû vs Payé)', fontsize=10, fontweight='bold')
    ax.legend(fontsize=8)
    ax.tick_params(axis='both', which='major', labelsize=8)
    
    # Clean up borders
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    plt.tight_layout()
    return fig

# --- GÉNÉRATEUR PDF ---
class PDFRelance(FPDF):
    def __init__(self, user_info):
        super().__init__()
        self.user_info = user_info

    def header(self):
        self.set_font('Arial', 'I', 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f"Suivi Comptable & Juridique - HOTEL ALBION - Lot {self.user_info.get('lot', '?')}", 0, 1, 'R')
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def generate_letter(self, total_due, table_rows, history_payments, total_penalties_amount):
        self.add_page()
        
        # --- PAGE 1 : MISE EN DEMEURE ---
        self.set_font("Arial", 'B', 11)
        self.cell(0, 5, self.user_info.get('nom', ''), 0, 1)
        self.set_font("Arial", '', 10)
        self.cell(0, 5, f"Lot : {self.user_info.get('lot', '')}", 0, 1)
        self.cell(0, 5, f"Email : {self.user_info.get('email', '')}", 0, 1)
        
        self.ln(10)
        self.set_font("Arial", 'B', 11)
        self.cell(0, 5, "A l'attention de l'Administrateur Judiciaire", 0, 1, 'R')
        self.ln(15)
        
        self.set_font("Arial", 'B', 14)
        self.cell(0, 10, "MISE EN DEMEURE DE PAYER SOUS HUITAINE", 0, 1, 'C')
        self.set_font("Arial", 'B', 10)
        self.cell(0, 5, "(Loyers Post-Jugement - Art. L.622-17 Code de commerce)", 0, 1, 'C')
        self.ln(10)
        
        self.set_font("Arial", '', 10)
        txt = ("Maitre,\n\n"
               "Je constate a ce jour un defaut de paiement persistant sur les loyers courants.\n\n"
               "Conformement a l'Article 11 du bail, ces sommes etaient exigibles le 10 du mois. "
               "L'Article L.622-17 I du Code de commerce impose leur paiement strict a l'echeance.\n\n"
               "Je vous rappelle les dispositions contractuelles et legales :\n"
               "- Art 4-10 (Non-tolerance) : Aucun retard passe ne vaut droit acquis.\n"
               "- Art 15 (Frais) : Les frais de recouvrement sont a votre charge exclusive.\n"
               "- Art L.441-10 : L'indemnite forfaitaire de 40 EUR est due de plein droit pour chaque echeance en retard.\n\n"
               "Les paiements recus ont ete imputes prioritairement sur les penalites (Art 1343-1 Code Civil).")
        self.multi_cell(0, 5, txt.encode('latin-1', 'replace').decode('latin-1'))
        self.ln(5)
        
        # TABLEAU SYNTHÉTIQUE
        self.set_fill_color(255, 200, 200)
        self.set_font("Arial", 'B', 9)
        self.cell(0, 6, "ETAT DES DETTES EXIGIBLES CE JOUR", 1, 1, 'L', fill=True)
        self.cell(30, 6, "Exigibilite", 1)
        self.cell(80, 6, "Libelle", 1)
        self.cell(30, 6, "Montant", 1)
        self.cell(30, 6, "Reste Du", 1, 1)
        
        self.set_font("Arial", '', 9)
        for row in table_rows:
            if row['reste'] > 0.01:
                if "Indemnité" in row['label']: self.set_font("Arial", 'I', 9)
                else: self.set_font("Arial", '', 9)
                
                d_str = row['date'].strftime("%d/%m/%Y")
                self.cell(30, 6, d_str, 1)
                self.cell(80, 6, row['label'][:45].encode('latin-1', 'replace').decode('latin-1'), 1)
                self.cell(30, 6, f"{row['montant']:.2f}", 1, 0, 'R')
                self.cell(30, 6, f"{row['reste']:.2f}", 1, 1, 'R')
        
        self.ln(5)
        self.set_font("Arial", 'B', 11)
        self.cell(0, 10, f"NET A PAYER : {total_due:,.2f} EUR", 0, 1, 'R')
        
        self.ln(5)
        self.set_font("Arial", '', 10)
        self.multi_cell(0, 5, f"IBAN : {self.user_info.get('iban', '')}\nBIC : {self.user_info.get('bic', '')}")

        # --- PAGE 2 : ANNEXE AUDIT ---
        self.add_page()
        self.set_font("Arial", 'B', 12)
        self.cell(0, 10, "ANNEXE : AUDIT COMPTABLE & TRACABILITE", 0, 1, 'C')
        self.ln(5)

        # 1. Graphique
        try:
            fig = create_debt_chart(table_rows)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
                fig.savefig(tmp_file.name, format="png", dpi=100)
                tmp_path = tmp_file.name
            
            self.image(tmp_path, x=10, w=190)
            os.unlink(tmp_path)
            self.ln(5)
        except Exception as e:
            self.cell(0, 10, f"Graphique non disponible: {e}", 0, 1)

        # 2. Historique des Paiements
        self.set_font("Arial", 'B', 10)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 8, "I. HISTORIQUE DES VIREMENTS RECUS", 1, 1, 'L', fill=True)
        
        if history_payments:
            self.set_font("Arial", 'B', 9)
            self.cell(50, 6, "Date Reception", 1)
            self.cell(50, 6, "Montant", 1, 1)
            self.set_font("Arial", '', 9)
            total_history = 0
            for p in history_payments:
                d_str = p['date'].strftime("%d/%m/%Y")
                self.cell(50, 6, d_str, 1)
                self.cell(50, 6, f"{p['montant']:.2f} EUR", 1, 1, 'R')
                total_history += p['montant']
            self.set_font("Arial", 'B', 9)
            self.cell(50, 6, "TOTAL", 1)
            self.cell(50, 6, f"{total_history:.2f} EUR", 1, 1, 'R')
        else:
            self.set_font("Arial", 'I', 9)
            self.cell(0, 6, "Aucun virement enregistre a ce jour.", 1, 1)
            
        self.ln(10)

        # 3. Compteur Pénalités
        self.set_font("Arial", 'B', 10)
        self.cell(0, 8, "II. VENTILATION DES FRAIS DE RETARD (Art. D.441-5)", 1, 1, 'L', fill=True)
        self.set_font("Arial", '', 9)
        self.multi_cell(0, 5, "Le tableau ci-dessous recense l'ensemble des indemnites forfaitaires generees par le non-respect des echeances contractuelles (Paiement le 10 du mois).")
        self.ln(2)
        
        self.set_font("Arial", 'B', 9)
        self.cell(140, 6, "Motif de la penalite", 1)
        self.cell(30, 6, "Montant", 1, 1)
        self.set_font("Arial", '', 9)
        
        has_penalty = False
        for row in table_rows:
            if "Indemnité" in row['label']:
                has_penalty = True
                self.cell(140, 6, row['label'].encode('latin-1', 'replace').decode('latin-1'), 1)
                self.cell(30, 6, "40.00 EUR", 1, 1, 'R')
        
        if not has_penalty:
            self.cell(170, 6, "Aucune penalite a ce jour.", 1, 1)
        
        self.ln(2)
        self.set_font("Arial", 'B', 9)
        self.cell(140, 6, "CUMUL TOTAL DES PENALITES GENEREES", 1)
        self.cell(30, 6, f"{total_penalties_amount:.2f} EUR", 1, 1, 'R')

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
                st.error("Date antérieure au jugement.")
            else:
                st.session_state.paiements.append({"date": d_pay, "montant": m_pay})
                st.session_state.paiements.sort(key=lambda x: x['date']) 
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

# CŒUR DU SYSTÈME : CASCADE WATERFALL AVEC DATE DE PAIEMENT
with c_pay_2:
    st.subheader("📊 Tableau de Bord (Calculé)")
    
    # 1. Préparation des Dettes
    base_loyers = generer_echeancier_post_rj(loyer_annuel_ht)
    all_debts = []
    today = date.today()
    
    for item in base_loyers:
        # La dette de loyer
        all_debts.append({
            "date": item['date'],
            "label": item['label'],
            "montant": item['montant'],
            "type": "PRINCIPAL",
            "paye": 0.0,
            "reste": item['montant'],
            "date_paiement": None
        })
        
        # La pénalité si retard
        if today > item['date']:
            all_debts.append({
                "date": item['date'], 
                "label": f"↪ Indemnité Forfaitaire (Art L.441-10)",
                "montant": INDEMNITE_FORFAITAIRE,
                "type": "PENALITE", 
                "paye": 0.0,
                "reste": INDEMNITE_FORFAITAIRE,
                "date_paiement": None
            })
            
    # 2. Tri pour ordre de paiement (Pénalités d'abord)
    debts_to_pay = sorted(all_debts, key=lambda x: (0 if x['type'] == 'PENALITE' else 1, x['date']))
    
    # 3. Application du Paiement
    available_payments = [p.copy() for p in st.session_state.paiements] 
    total_retard = 0
    total_penalties_acc = 0
    
    for debt in debts_to_pay:
        if debt['type'] == "PENALITE":
            total_penalties_acc += debt['montant']
            
        payment_date_for_this_debt = None
        for pay in available_payments:
            if pay['montant'] <= 0: continue 
            if debt['reste'] <= 0: break 
            
            amount_taken = min(pay['montant'], debt['reste'])
            pay['montant'] -= amount_taken
            debt['reste'] -= amount_taken
            debt['paye'] += amount_taken
            payment_date_for_this_debt = pay['date']
            
        debt['date_paiement'] = payment_date_for_this_debt
        
        debt['jours_retard'] = 0
        target_date = debt['date']
        
        if debt['reste'] < 0.01 and debt['date_paiement']: 
            delta = (debt['date_paiement'] - target_date).days
            debt['jours_retard'] = max(0, delta)
        elif today > target_date:
            delta = (today - target_date).days
            debt['jours_retard'] = max(0, delta)

        if debt['reste'] > 0.01 and today > target_date:
            total_retard += debt['reste']

    # 4. Remise en ordre Chrono
    debts_display = sorted(debts_to_pay, key=lambda x: x['date'])
    
    final_rows = []
    for d in debts_display:
        statut = ""
        if d['reste'] < 0.01: statut = "✅ PAYÉ"
        elif d['reste'] < d['montant']: statut = "🟠 PARTIEL"
        elif today < d['date']: statut = "⚪ À ÉCHOIR"
        else: statut = "🔴 IMPAYÉ"
        
        date_pay_str = date_en_francais(d['date_paiement']) if d['date_paiement'] else "-"
        
        final_rows.append({
            "Echéance": d['date'],
            "Libellé": d['label'],
            "Montant": d['montant'],
            "Payé": d['paye'],
            "Reste Dû": d['reste'],
            "Statut": statut,
            "Payé le": date_pay_str,
            "Jours Retard": d['jours_retard'],
            "raw_date": d['date'],
            "raw_label": d['label']
        })

    # 5. Rendu Tableau
    df_suivi = pd.DataFrame(final_rows)
    
    st.dataframe(
        df_suivi,
        column_config={
            "Echéance": st.column_config.DateColumn("Echéance", format="DD/MM/YYYY"),
            "Libellé": st.column_config.TextColumn("Libellé", width="large"),
            "Montant": st.column_config.NumberColumn("Montant", format="%.2f €"),
            "Payé": st.column_config.NumberColumn("Payé", format="%.2f €"),
            "Reste Dû": st.column_config.NumberColumn("Reste Dû", format="%.2f €"),
            "Statut": st.column_config.TextColumn("Statut", width="small"),
            "Payé le": st.column_config.TextColumn("Reçu le", width="medium"),
            "Jours Retard": st.column_config.NumberColumn("Retard (Jours)", format="%d j"),
            "raw_date": None,
            "raw_label": None
        },
        use_container_width=True,
        hide_index=True
    )
    
    if total_retard > 0.01:
        st.error(f"⚠️ **RETARD EXIGIBLE TOTAL : {total_retard:,.2f} €**")
        
        if st.button("🔥 TÉLÉCHARGER MISE EN DEMEURE (PDF + GRAPH)"):
            user_data = {"nom": id_nom, "lot": id_lot, "iban": id_iban, "bic": id_bic, "email": id_email}
            pdf = PDFRelance(user_data)
            
            rows_for_pdf = []
            for r in final_rows:
                rows_for_pdf.append({
                    "date": r['raw_date'],
                    "label": r['raw_label'],
                    "montant": r['Montant'],
                    "paye": r['Payé'], # Pour le graph
                    "reste": r['Reste Dû']
                })
                
            pdf.generate_letter(total_retard, rows_for_pdf, st.session_state.paiements, total_penalties_acc)
            
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
