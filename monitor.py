import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from fpdf import FPDF
import json
import io
import matplotlib.pyplot as plt
import tempfile
import os

# --- CONFIGURATION ---
st.set_page_config(page_title="Albion Monitor V2.5 (2026 Edition)", page_icon="📡", layout="wide")

# --- CONSTANTES ---
DATE_JUGEMENT = date(2025, 6, 26)
DATE_DEBUT_BAIL = date(2019, 6, 1)
DATE_PIVOT_INDEX = "01 Juin"
INDEMNITE_FORFAITAIRE = 40.0

# --- HISTORIQUE ILC (Simulé à date Janvier 2026) ---
# En Janvier 2026, l'indice T4 2024 (publié Mars 2025) est CONNU.
# Valeur 138.60 est une valeur réaliste fixée pour la simulation.
HISTORIQUE_ILC = [
    {"Annee": 2019, "Indice": 114.06, "Note": "Base Contrat (T4 2018)"},
    {"Annee": 2020, "Indice": 116.26, "Note": "Révision Juin 2020"},
    {"Annee": 2021, "Indice": 118.41, "Note": "Révision Juin 2021"},
    {"Annee": 2022, "Indice": 126.13, "Note": "Révision Juin 2022"},
    {"Annee": 2023, "Indice": 133.62, "Note": "Révision Juin 2023"},
    {"Annee": 2024, "Indice": 138.60, "Note": "Révision Juin 2024 (Ref T4 2023)"}, # Correction étiquette
    {"Annee": 2025, "Indice": 142.50, "Note": "Révision Juin 2025 (Ref T4 2024)"}, # Publié en Mars 2025
]

# --- UTILITAIRES ---
def json_serial(obj):
    if isinstance(obj, (datetime, date)): return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

def format_date_courte(d):
    if not isinstance(d, (date, datetime)): return ""
    return d.strftime("%d/%m/%Y")

def date_en_francais(d):
    if not isinstance(d, (date, datetime)): return ""
    mois = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    return f"{d.day} {mois[d.month]} {d.year}"

# --- MOTEUR DE CALCUL ---
def generer_echeancier_post_rj(montant_annuel_ht_base, indice_base, indice_revision):
    """
    Rappel : Nous sommes en Janvier 2026.
    La période active est Juin 2025 -> Juin 2026.
    L'indice utilisé est celui publié en Mars 2025 (Ref T4 2024).
    """
    coef = indice_revision / indice_base
    annuel_indexe_ht = montant_annuel_ht_base * coef
    annuel_indexe_ttc = annuel_indexe_ht * 1.10 
    
    echeances = []
    
    # Solde Juin 2025 (Passé)
    montant_juin = (annuel_indexe_ttc / 365) * 4 
    echeances.append({
        "date": date(2025, 7, 10), 
        "label": "Solde Juin 2025 (Prorata)", 
        "montant": montant_juin,
        "indice_used": indice_revision
    })
    
    # T3 2025 (Passé)
    echeances.append({
        "date": date(2025, 10, 10), 
        "label": "T3 2025 (Juil-Août-Sept)", 
        "montant": annuel_indexe_ttc / 4,
        "indice_used": indice_revision
    })
    
    # T4 2025 (Vient d'échoir ou échoit ce mois-ci)
    echeances.append({
        "date": date(2026, 1, 10), 
        "label": "T4 2025 (Oct-Nov-Déc)", 
        "montant": annuel_indexe_ttc / 4,
        "indice_used": indice_revision
    })
    
    # T1 2026 (Futur)
    echeances.append({
        "date": date(2026, 4, 10), 
        "label": "T1 2026 (Jan-Fév-Mars)", 
        "montant": annuel_indexe_ttc / 4,
        "indice_used": indice_revision
    })

    return echeances, coef

# --- GRAPHIQUE ---
def create_debt_chart(data_rows):
    labels = []
    montants_dus = []
    montants_payes = []
    for row in data_rows:
        if "Indemnité" not in row['label']:
            short_label = row['raw_date'].strftime("%b %y")
            labels.append(short_label)
            montants_dus.append(row['montant'])
            montants_payes.append(row['paye'])
            
    fig, ax = plt.subplots(figsize=(7, 3))
    ax.bar(labels, montants_dus, color='#ffebee', edgecolor='#ef5350', label='Dû', width=0.6)
    ax.bar(labels, montants_payes, color='#c8e6c9', edgecolor='#66bb6a', label='Payé', width=0.6)
    ax.set_ylabel('Euros (€)', fontsize=8)
    ax.set_title('VISUALISATION DES IMPAYES', fontsize=10, fontweight='bold')
    ax.legend(fontsize=8)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    return fig

# --- PDF ---
class PDFRelance(FPDF):
    def __init__(self, user_info, simulation_date_str):
        super().__init__()
        self.user_info = user_info
        self.sim_date = simulation_date_str
        self.alias_nb_pages()

    def header(self):
        self.set_font('Arial', 'I', 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f"Dossier de Recouvrement - HOTEL ALBION - Lot {self.user_info.get('lot', '?')}", 0, 1, 'R')
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')

    def generate_report(self, total_due, table_rows, history_payments, total_penalties_amount, df_ilc):
        # PAGE 1
        self.add_page()
        self.set_font("Arial", 'B', 14)
        self.cell(0, 10, f"AUDIT DE SITUATION AU {self.sim_date}", 0, 1, 'C')
        self.ln(5)

        try:
            fig = create_debt_chart(table_rows)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
                fig.savefig(tmp_file.name, format="png", dpi=100)
                tmp_path = tmp_file.name
            self.image(tmp_path, x=10, w=190)
            os.unlink(tmp_path)
            self.ln(5)
        except: pass

        # TABLEAU PREUVE ILC
        self.set_fill_color(230, 240, 255)
        self.set_font("Arial", 'B', 10)
        self.cell(0, 7, "I. JUSTIFICATIF D'INDEXATION (Clause Echelle Mobile - Art. L145-39)", 1, 1, 'L', fill=True)
        self.set_font("Arial", 'I', 8)
        self.multi_cell(0, 5, "Conformement au bail, la revision du montant s'applique automatiquement le 1er JUIN de chaque annee en fonction de l'evolution de l'indice ILC.")
        self.set_font("Arial", 'B', 8)
        self.cell(30, 5, "Annee", 1, 0, 'C')
        self.cell(40, 5, "Indice ILC", 1, 0, 'C')
        self.cell(40, 5, "Coefficient", 1, 0, 'C')
        self.cell(80, 5, "Reference", 1, 1, 'L')
        self.set_font("Arial", '', 8)
        base_val = 114.06 # Force base for display consistency
        for index, row in df_ilc.iterrows():
            coef = row['Indice'] / base_val
            self.cell(30, 5, str(int(row['Annee'])), 1, 0, 'C')
            self.cell(40, 5, f"{row['Indice']:.2f}", 1, 0, 'C')
            self.cell(40, 5, f"x {coef:.4f}", 1, 0, 'C')
            self.cell(80, 5, str(row['Note']), 1, 1, 'L')
        self.ln(5)

        # PAIEMENTS
        self.set_font("Arial", 'B', 10)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 7, "II. HISTORIQUE DES VIREMENTS RECUS", 1, 1, 'L', fill=True)
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
            self.cell(50, 6, "TOTAL PERCU", 1)
            self.cell(50, 6, f"{total_history:.2f} EUR", 1, 1, 'R')
        else:
            self.set_font("Arial", 'I', 9)
            self.cell(0, 6, "Aucun virement enregistre a ce jour.", 1, 1)
        self.ln(5)

        # PENALITES
        self.set_font("Arial", 'B', 10)
        self.cell(0, 7, "III. INDEMNITES DE RETARD (Art. D.441-5)", 1, 1, 'L', fill=True)
        self.set_font("Arial", '', 9)
        has_penalty = False
        for row in table_rows:
            if "Indemnité" in row['label']:
                has_penalty = True
                self.cell(40, 6, row['raw_date'].strftime("%d/%m/%Y"), 1)
                self.cell(110, 6, row['label'].replace("↪ ", ""), 1)
                self.cell(40, 6, "40.00 EUR", 1, 1, 'R')
        if not has_penalty: self.cell(190, 6, "Néant.", 1, 1)
        else:
            self.set_font("Arial", 'B', 9)
            self.cell(150, 6, "CUMUL", 1)
            self.cell(40, 6, f"{total_penalties_amount:.2f} EUR", 1, 1, 'R')

        self.ln(15)
        self.set_fill_color(255, 235, 235)
        self.set_font("Arial", 'B', 12)
        self.cell(0, 10, f"TOTAL GENERAL EXIGIBLE AU {self.sim_date} : {total_due:,.2f} EUR", 1, 1, 'C', fill=True)
        self.set_font("Arial", 'I', 8)
        self.cell(0, 6, "(Suivant decompte et Mise en Demeure - Voir Page 2/2)", 0, 1, 'C')

        # PAGE 2
        self.add_page()
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
        self.cell(0, 5, "(Sommes Post-Jugement - Art. L.622-17 Code de commerce)", 0, 1, 'C')
        self.ln(10)
        
        self.set_font("Arial", '', 10)
        txt = ("Maitre,\n\n"
               "Veuillez trouver en Page 1 l'audit complet de la situation comptable de mon lot.\n"
               "Je constate a ce jour un solde debiteur exigible.\n\n"
               "Conformement a l'Article 11 du bail, ces sommes etaient exigibles le 10 du mois. "
               "L'Article L.622-17 I du Code de commerce impose leur paiement strict a l'echeance.\n\n"
               "Je vous rappelle les dispositions contractuelles et legales :\n"
               "- Art 4-10 (Non-tolerance) : Aucun retard passe ne vaut droit acquis.\n"
               "- Art 15 (Frais) : Les frais de recouvrement sont a votre charge exclusive.\n"
               "- Art L.441-10 : L'indemnite forfaitaire de 40 EUR est due de plein droit.\n\n"
               "Les paiements recus ont ete imputes prioritairement sur les penalites (Art 1343-1 Code Civil).")
        self.multi_cell(0, 5, txt.encode('latin-1', 'replace').decode('latin-1'))
        self.ln(5)
        
        self.set_fill_color(255, 200, 200)
        self.set_font("Arial", 'B', 9)
        self.cell(0, 6, "RESTE A REGLER CE JOUR (DETAILS EN PAGE 1)", 1, 1, 'L', fill=True)
        self.cell(25, 6, "Echeance", 1)
        self.cell(65, 6, "Libelle", 1)
        self.cell(20, 6, "Indice", 1)
        self.cell(25, 6, "Montant", 1)
        self.cell(25, 6, "Reste Du", 1, 1)
        self.set_font("Arial", '', 8)
        for row in table_rows:
            if row['reste'] > 0.01:
                if "Indemnité" in row['label']: 
                    self.set_font("Arial", 'I', 8)
                    indice_txt = "-"
                else: 
                    self.set_font("Arial", '', 8)
                    indice_txt = f"{row['indice']:.2f}"
                d_str = row['raw_date'].strftime("%d/%m/%Y")
                self.cell(25, 6, d_str, 1)
                self.cell(65, 6, row['label'][:40].encode('latin-1', 'replace').decode('latin-1'), 1)
                self.cell(20, 6, indice_txt, 1, 0, 'C')
                self.cell(25, 6, f"{row['montant']:.2f}", 1, 0, 'R')
                self.cell(25, 6, f"{row['reste']:.2f}", 1, 1, 'R')
        self.ln(5)
        self.set_font("Arial", 'B', 12)
        self.cell(0, 10, f"NET A PAYER : {total_due:,.2f} EUR", 0, 1, 'R')
        self.ln(5)
        self.set_font("Arial", '', 10)
        self.multi_cell(0, 5, f"IBAN : {self.user_info.get('iban', '')}\nBIC : {self.user_info.get('bic', '')}")
        self.ln(10)
        self.cell(0, 10, "Signature :", 0, 1, 'R')

# --- INTERFACE STREAMLIT ---
if 'paiements' not in st.session_state: st.session_state.paiements = []

# SIDEBAR
with st.sidebar:
    st.title("🎛️ Simulation (2026)")
    # SIMULATEUR TEMPOREL
    date_simulation = st.date_input("Date 'Aujourd'hui' (Simulation)", value=date(2026, 1, 15))
    
    st.divider()
    st.header("👤 Propriétaire")
    id_nom = st.text_input("Nom", placeholder="M. Dupont")
    id_lot = st.text_input("Lot", placeholder="A102")
    id_iban = st.text_input("IBAN")
    id_bic = st.text_input("BIC")
    id_email = st.text_input("Email")
    
    st.divider()
    with st.expander("📈 Indexation & Preuves (ILC)", expanded=True):
        st.caption(f"Date pivot : {DATE_PIVOT_INDEX}")
        st.markdown("**1. Historique ILC (Fixé)**")
        df_ilc_defaut = pd.DataFrame(HISTORIQUE_ILC)
        df_ilc = st.data_editor(df_ilc_defaut, num_rows="dynamic", hide_index=True)
        
        try:
            row_base = df_ilc.loc[df_ilc['Annee'] == 2019].iloc[0]
            val_indice_base = row_base['Indice']
            # Pour la période active en Jan 2026 (Juin 25-Juin 26), c'est la révision de Juin 2025.
            # Elle utilise l'indice publié en Mars 2025 (T4 2024).
            # Dans notre tableau, c'est la ligne Année 2025.
            row_actuel = df_ilc.loc[df_ilc['Annee'] == 2025].iloc[0]
            val_indice_actuel = row_actuel['Indice']
            
            coef = val_indice_actuel / val_indice_base
            st.success(f"Coef. Actif (Juin 25 - Juin 26) : \n{val_indice_actuel} / {val_indice_base} = **{coef:.4f}**")
        except:
            st.error("Erreur indices.")
            val_indice_base = 114.06
            val_indice_actuel = 142.50

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
st.markdown(f"### Suivi des Échéances Post-Jugement (Date Simu : {format_date_courte(date_simulation)})")

col1, col2 = st.columns([1, 2])
with col1:
    default_loyer = st.session_state.get("loyer_base", 0.0)
    loyer_annuel_ht = st.number_input("Montant Annuel de Référence HT (Base 2019)", value=default_loyer, step=100.0)

with col2:
    if loyer_annuel_ht > 0:
        loyer_25_ht = loyer_annuel_ht * (val_indice_actuel / val_indice_base)
        loyer_25_ttc = loyer_25_ht * 1.10
        st.info(f"""
        **Montant Applicable (Juin 2025 - Juin 2026)** :
        *Indice retenu : {val_indice_actuel} (Ref T4 2024 publié Mars 2025)*
        👉 **{loyer_25_ttc:,.2f} € TTC / an** soit **{(loyer_25_ttc/4):,.2f} € TTC / trimestre**
        """)

if loyer_annuel_ht == 0: st.stop()

st.divider()

# GESTION PAIEMENTS
c_pay_1, c_pay_2 = st.columns([1, 2])

with c_pay_1:
    st.subheader("💰 Paiements Reçus")
    with st.form("add_pay"):
        d_pay = st.date_input("Date réception", date_simulation) # Défaut = Date Simu
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
            disp_pay.append({"Date": format_date_courte(p["date"]), "Montant": f"{p['montant']:.2f} €"})
        st.dataframe(pd.DataFrame(disp_pay), hide_index=True)
        if st.button("Supprimer dernier paiement"):
            st.session_state.paiements.pop()
            st.rerun()

# CŒUR DU SYSTÈME
with c_pay_2:
    st.subheader("📊 Tableau de Bord (Calculé)")
    
    base_loyers, _ = generer_echeancier_post_rj(loyer_annuel_ht, val_indice_base, val_indice_actuel)
    
    all_debts = []
    # UTILISATION DE LA DATE SIMULEE POUR LE CALCUL DU RETARD
    today = date_simulation
    
    for item in base_loyers:
        all_debts.append({
            "date": item['date'],
            "label": item['label'],
            "montant": item['montant'],
            "type": "PRINCIPAL",
            "paye": 0.0,
            "reste": item['montant'],
            "date_paiement": None,
            "indice": item['indice_used']
        })
        if today > item['date']:
            date_penalite = item['date'] + timedelta(days=1)
            all_debts.append({
                "date": date_penalite, 
                "label": f"↪ Indemnité (Retard {item['label']})",
                "montant": INDEMNITE_FORFAITAIRE,
                "type": "PENALITE", 
                "paye": 0.0,
                "reste": INDEMNITE_FORFAITAIRE,
                "date_paiement": None,
                "indice": 0
            })
            
    debts_to_pay = sorted(all_debts, key=lambda x: (0 if x['type'] == 'PENALITE' else 1, x['date']))
    
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

    debts_display = sorted(debts_to_pay, key=lambda x: x['date'])
    
    final_rows = []
    for d in debts_display:
        statut = ""
        if d['reste'] < 0.01: statut = "✅ PAYÉ"
        elif d['reste'] < d['montant']: statut = "🟠 PARTIEL"
        elif today < d['date']: statut = "⚪ À ÉCHOIR"
        else: statut = "🔴 IMPAYÉ"
        
        date_pay_str = format_date_courte(d['date_paiement']) if d['date_paiement'] else "-"
        ind_txt = f"{d['indice']:.2f}" if d['type'] == 'PRINCIPAL' else "-"
        
        final_rows.append({
            "Echéance": format_date_courte(d['date']), 
            "Libellé": d['label'],
            "Indice Ref.": ind_txt,
            "Montant": d['montant'],
            "Payé": d['paye'],
            "Reste Dû": d['reste'],
            "Statut": statut,
            "Payé le": date_pay_str,
            "Jours Retard": d['jours_retard'],
            "raw_date": d['date'],
            "raw_label": d['label'],
            "indice": d['indice']
        })

    df_suivi = pd.DataFrame(final_rows)
    
    st.dataframe(
        df_suivi,
        column_config={
            "Echéance": st.column_config.TextColumn("Echéance"), 
            "Libellé": st.column_config.TextColumn("Libellé", width="large"),
            "Indice Ref.": st.column_config.TextColumn("Indice Ref.", width="small"),
            "Montant": st.column_config.NumberColumn("Montant", format="%.2f €"),
            "Payé": st.column_config.NumberColumn("Payé", format="%.2f €"),
            "Reste Dû": st.column_config.NumberColumn("Reste Dû", format="%.2f €"),
            "Statut": st.column_config.TextColumn("Statut", width="small"),
            "Payé le": st.column_config.TextColumn("Reçu le", width="medium"),
            "Jours Retard": st.column_config.NumberColumn("Retard (Jours)", format="%d j"),
            "raw_date": None,
            "raw_label": None,
            "indice": None
        },
        use_container_width=True,
        hide_index=True
    )
    
    if total_retard > 0.01:
        st.error(f"⚠️ **RETARD EXIGIBLE TOTAL (Au {format_date_courte(today)}) : {total_retard:,.2f} €**")
        
        if st.button("🔥 TÉLÉCHARGER MISE EN DEMEURE (PDF + GRAPH)"):
            user_data = {"nom": id_nom, "lot": id_lot, "iban": id_iban, "bic": id_bic, "email": id_email}
            pdf = PDFRelance(user_data, format_date_courte(today))
            
            rows_for_pdf = []
            for r in final_rows:
                rows_for_pdf.append({
                    "date": r['raw_date'],
                    "label": r['raw_label'],
                    "montant": r['Montant'],
                    "paye": r['Payé'], 
                    "reste": r['Reste Dû'],
                    "raw_date": r['raw_date'],
                    "indice": r['indice']
                })
                
            pdf.generate_report(total_retard, rows_for_pdf, st.session_state.paiements, total_penalties_acc, df_ilc)
            
            st.download_button(
                "📥 PDF Relance",
                data=pdf.output(dest='S').encode('latin-1'),
                file_name=f"Relance_Albion_{format_date_courte(today)}.pdf",
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
