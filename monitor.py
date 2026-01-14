import streamlit as st
import pandas as pd
from datetime import date, datetime
from fpdf import FPDF
import json
import io

# --- CONFIGURATION ---
st.set_page_config(page_title="Albion Monitor V1.4 (Ledger)", page_icon="📡", layout="wide")

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
                st.session_state.paiements.sort(key=lambda x: x['date']) # Tri chrono obligatoire pour Waterfall
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
        if item['date'] <= today:
            all_debts.append({
                "date": item['date'], 
                "label": f"↪ Indemnité Forfaitaire (Retard {item['label']})",
                "montant": INDEMNITE_FORFAITAIRE,
                "type": "PENALITE", 
                "paye": 0.0,
                "reste": INDEMNITE_FORFAITAIRE,
                "date_paiement": None
            })
            
    # 2. Tri pour ordre de paiement (Pénalités d'abord)
    debts_to_pay = sorted(all_debts, key=lambda x: (0 if x['type'] == 'PENALITE' else 1, x['date']))
    
    # 3. Application du Paiement (Consommation des virements un par un)
    # C'est ici que ça change : on ne somme pas tout, on itère sur les paiements
    
    # On crée une copie des paiements pour les "consommer" virtuellement
    available_payments = [p.copy() for p in st.session_state.paiements] 
    
    total_retard = 0
    
    for debt in debts_to_pay:
        # Tant que la dette n'est pas payée et qu'il reste des sous
        payment_date_for_this_debt = None
        
        for pay in available_payments:
            if pay['montant'] <= 0: continue # Paiement épuisé
            if debt['reste'] <= 0: break # Dette éteinte
            
            # Combien on prend sur ce paiement ?
            amount_taken = min(pay['montant'], debt['reste'])
            
            pay['montant'] -= amount_taken
            debt['reste'] -= amount_taken
            debt['paye'] += amount_taken
            
            # La date de paiement de la dette devient la date de ce virement
            payment_date_for_this_debt = pay['date']
            
        debt['date_paiement'] = payment_date_for_this_debt
        
        # Calcul des Jours de Retard
        debt['jours_retard'] = 0
        if debt['reste'] < 0.01 and debt['date_paiement']: 
            # Payé intégralement : Retard = Date Paiement - Date Echéance
            delta = (debt['date_paiement'] - debt['date']).days
            debt['jours_retard'] = max(0, delta)
        elif debt['date'] <= today:
            # Impayé ou partiel : Retard = Aujourd'hui - Date Echéance
            delta = (today - debt['date']).days
            debt['jours_retard'] = max(0, delta)

        if debt['reste'] > 0.01 and debt['date'] <= today:
            total_retard += debt['reste']

    # 4. Remise en ordre Chronologique pour l'Affichage
    debts_display = sorted(debts_to_pay, key=lambda x: x['date'])
    
    final_rows = []
    for d in debts_display:
        statut = ""
        if d['reste'] < 0.01: statut = "✅ PAYÉ"
        elif d['reste'] < d['montant']: statut = "🟠 PARTIEL"
        elif d['date'] <= today: statut = "🔴 IMPAYÉ" # Ou DÛ pour pénalité
        else: statut = "⚪ À ÉCHOIR"
        
        # Formatage de la date de paiement
        date_pay_str = date_en_francais(d['date_paiement']) if d['date_paiement'] else "-"
        
        final_rows.append({
            "Echéance": d['date'], # Objet date pour config
            "Libellé": d['label'],
            "Montant": d['montant'],
            "Payé": d['paye'],
            "Reste Dû": d['reste'],
            "Statut": statut,
            "Payé le": date_pay_str,
            "Jours Retard": d['jours_retard'],
            
            # Hidden fields for PDF
            "raw_date": d['date'],
            "raw_label": d['label']
        })

    # 5. Rendu Tableau avec Column Config (Nouveau Design)
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
            # Cacher les colonnes raw
            "raw_date": None,
            "raw_label": None
        },
        use_container_width=True,
        hide_index=True
    )
    
    if total_retard > 0.01:
        st.error(f"⚠️ **RETARD EXIGIBLE TOTAL : {total_retard:,.2f} €**")
        
        if st.button("🔥 TÉLÉCHARGER MISE EN DEMEURE (PDF)"):
            user_data = {"nom": id_nom, "lot": id_lot, "iban": id_iban, "bic": id_bic, "email": id_email}
            pdf = PDFRelance(user_data)
            
            rows_for_pdf = []
            for r in final_rows:
                rows_for_pdf.append({
                    "date": r['raw_date'],
                    "label": r['raw_label'],
                    "montant": r['Montant'],
                    "reste": r['Reste Dû']
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
