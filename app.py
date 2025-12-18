import streamlit as st
import pandas as pd
import altair as alt
from datetime import date, datetime, timedelta
from fpdf import FPDF
import io
import json
import tempfile
import os
from PIL import Image
from pypdf import PdfWriter, PdfReader

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Générateur Dossier Créance V4.2", page_icon="⚖️", layout="wide")

# --- CSS PERSONNALISÉ ---
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        height: 60px; white-space: pre-wrap; border-radius: 10px 10px 0px 0px;
        padding: 10px 20px; font-size: 18px; box-shadow: 0px -2px 5px rgba(0,0,0,0.05);
        background-color: #f8f9fa; border: 1px solid #dee2e6; border-bottom: none;
    }
    .stTabs [data-baseweb="tab"]:nth-of-type(1) { border-top: 6px solid #1f77b4; }
    .stTabs [data-baseweb="tab"]:nth-of-type(2) { border-top: 6px solid #ff7f0e; }
    .stTabs [aria-selected="true"] {
        background-color: #ffffff !important; font-weight: bold; border-bottom: 0px solid transparent; box-shadow: none;
    }
</style>
""", unsafe_allow_html=True)

# --- CONSTANTES JURIDIQUES & DONNÉES ---
DATE_JUGEMENT = date(2025, 6, 26)
DATE_DEBUT_GRAPH = date(2019, 6, 1)
INDEMNITE_FORFAITAIRE = 40.0

TAUX_LEGAUX = [
    (date(2019, 1, 1), 10.00), (date(2019, 7, 1), 10.00), (date(2020, 1, 1), 10.00),
    (date(2020, 7, 1), 10.00), (date(2021, 1, 1), 10.00), (date(2021, 7, 1), 10.00),
    (date(2022, 1, 1), 10.00), (date(2022, 7, 1), 10.50), (date(2023, 1, 1), 12.50),
    (date(2023, 7, 1), 14.00), (date(2024, 1, 1), 14.75), (date(2024, 7, 1), 14.25),
    (date(2025, 1, 1), 13.50)
]

INDICES = {
    "BASE": 114.06, "2019": 116.16, "2020": 115.79, "2021": 118.59,
    "2022": 126.05, "2023": 132.63, "2024": 135.30
}

# --- UTILITAIRES ---
def json_serial(obj):
    if isinstance(obj, (datetime, date)): return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

def get_taux_legal(d):
    for start_date, rate in reversed(TAUX_LEGAUX):
        if d >= start_date: return rate
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

# --- MOTEUR 1 : PRÉ-RJ ---
def generer_loyers_theoriques_pre_rj(loyer_annuel_ht):
    loyer_annuel_ttc = loyer_annuel_ht * 1.10
    loyer_base_mensuel = loyer_annuel_ttc / 12
    echeances = []
    
    echeances.append({"date": date(2019, 10, 10), "label": "Loyer 2019 (4 mois TTC)", "montant": loyer_base_mensuel * 4})
    
    loyer_2020 = loyer_base_mensuel * (INDICES["2019"] / INDICES["BASE"])
    echeances.append({"date": date(2020, 1, 10), "label": "T1 2020", "montant": loyer_base_mensuel * 3})
    montant_t2_mixte = (loyer_base_mensuel * 2) + (loyer_2020 * 1)
    echeances.append({"date": date(2020, 4, 10), "label": "T2 2020 (Mixte)", "montant": montant_t2_mixte})
    echeances.append({"date": date(2020, 7, 10), "label": "T3 2020", "montant": loyer_2020 * 3})
    echeances.append({"date": date(2020, 10, 10), "label": "T4 2020", "montant": loyer_2020 * 3})
    
    loyer_2021 = loyer_2020 
    for t in range(1, 5): 
        d = date(2021, 1 + (t-1)*3, 10)
        echeances.append({"date": d, "label": f"T{t} 2021", "montant": loyer_2021 * 3})
        
    loyer_2022 = loyer_base_mensuel * (INDICES["2021"] / INDICES["BASE"])
    echeances.append({"date": date(2022, 1, 10), "label": "T1 2022", "montant": loyer_2021 * 3})
    montant_t2_22 = (loyer_2021 * 2) + (loyer_2022 * 1)
    echeances.append({"date": date(2022, 4, 10), "label": "T2 2022 (Indexation)", "montant": montant_t2_22})
    echeances.append({"date": date(2022, 7, 10), "label": "T3 2022", "montant": loyer_2022 * 3})
    echeances.append({"date": date(2022, 10, 10), "label": "T4 2022", "montant": loyer_2022 * 3})
    
    loyer_2023 = loyer_base_mensuel * (INDICES["2022"] / INDICES["BASE"])
    echeances.append({"date": date(2023, 1, 10), "label": "T1 2023", "montant": loyer_2022 * 3})
    montant_t2_23 = (loyer_2022 * 2) + (loyer_2023 * 1)
    echeances.append({"date": date(2023, 4, 10), "label": "T2 2023 (Indexation)", "montant": montant_t2_23})
    echeances.append({"date": date(2023, 7, 10), "label": "T3 2023", "montant": loyer_2023 * 3})
    echeances.append({"date": date(2023, 10, 10), "label": "T4 2023", "montant": loyer_2023 * 3})

    loyer_2024 = loyer_base_mensuel * (INDICES["2023"] / INDICES["BASE"])
    echeances.append({"date": date(2024, 1, 10), "label": "T1 2024", "montant": loyer_2023 * 3})
    montant_t2_24 = (loyer_2023 * 2) + (loyer_2024 * 1)
    echeances.append({"date": date(2024, 4, 10), "label": "T2 2024 (Indexation)", "montant": montant_t2_24})
    echeances.append({"date": date(2024, 7, 10), "label": "T3 2024", "montant": loyer_2024 * 3})
    echeances.append({"date": date(2024, 10, 10), "label": "T4 2024", "montant": loyer_2024 * 3})

    echeances.append({"date": date(2025, 1, 10), "label": "T1 2025", "montant": loyer_2024 * 3})
    loyer_2025 = loyer_base_mensuel * (INDICES["2024"] / INDICES["BASE"])
    montant_avril_mai = loyer_2024 * 2
    echeances.append({"date": date(2025, 4, 10), "label": "Avril-Mai 2025", "montant": montant_avril_mai})
    montant_juin_prorata = (loyer_2025 / 30) * 26
    echeances.append({"date": date(2025, 6, 26), "label": "Juin 2025 (Prorata 26j)", "montant": montant_juin_prorata})

    return echeances

# --- MOTEUR 2 : POST-RJ ---
def generer_loyers_post_rj(loyer_annuel_ht):
    loyer_annuel_ttc = loyer_annuel_ht * 1.10
    loyer_base_mensuel = loyer_annuel_ttc / 12
    loyer_mensuel_2025 = loyer_base_mensuel * (INDICES["2024"] / INDICES["BASE"])
    echeances = []
    
    montant_fin_juin = (loyer_mensuel_2025 / 30) * 4
    echeances.append({"date": date(2025, 7, 10), "label": "Solde Juin 2025 (Payable Juillet)", "montant": montant_fin_juin})
    echeances.append({"date": date(2025, 10, 10), "label": "T3 2025 (Payable Octobre)", "montant": loyer_mensuel_2025 * 3})
    echeances.append({"date": date(2026, 1, 10), "label": "T4 2025 (Payable Janvier 26)", "montant": loyer_mensuel_2025 * 3})
    echeances.append({"date": date(2026, 4, 10), "label": "T1 2026 (Payable Avril 26)", "montant": loyer_mensuel_2025 * 3})

    return echeances

# ==========================================
# CLASS PDF 1 : LE DOSSIER COMPLET
# ==========================================
class DossierJuridiquePDF(FPDF):
    def __init__(self, user_info):
        super().__init__()
        self.user_info = user_info
        
    def header(self):
        self.set_font('Arial', 'I', 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, f"Dossier Creance - HOTEL ALBION - Lot {self.user_info.get('lot', '?')}", 0, 0, 'L')
        self.cell(0, 8, f"Proprietaire : {self.user_info.get('nom', 'N/A')}", 0, 1, 'R')
        self.ln(2)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def generate_page_1_courrier(self, total_principal, total_interets, total_teom, total_indemnite):
        self.add_page()
        self.set_font("Arial", 'B', 11)
        
        # INFO EXPEDITEUR
        self.cell(0, 5, f"{self.user_info.get('nom', '').upper()}", 0, 1)
        self.set_font("Arial", '', 10)
        self.cell(0, 5, f"Lot n {self.user_info.get('lot', '')}", 0, 1)
        self.cell(0, 5, f"Tel : {self.user_info.get('tel', '')}", 0, 1)
        self.cell(0, 5, f"Email : {self.user_info.get('email', '')}", 0, 1)
        
        self.ln(15)
        self.set_font("Arial", 'B', 11)
        self.cell(0, 5, "A l'attention du Mandataire Judiciaire", 0, 1, 'R')
        self.cell(0, 5, "Etude de Maitre [NOM DU MANDATAIRE]", 0, 1, 'R')
        self.cell(0, 5, "[ADRESSE MANDATAIRE]", 0, 1, 'R')
        
        self.ln(20)
        self.set_font("Arial", 'B', 12)
        self.cell(0, 10, "Objet : CONTESTATION D'ETAT DES CREANCES - HOTEL ALBION", 0, 1, 'L')
        
        self.ln(5)
        self.set_font("Arial", '', 11)
        intro = ("Maitre,\n\n"
                 "Je fais suite a la verification des creances et je conteste formellement le montant retenu "
                 "par vos services. Veuillez trouver ci-joint ma declaration rectificative.\n\n"
                 "1. J'applique les penalites de retard contractuelles et legales (Art. L.441-10 du Code de Commerce).\n"
                 "2. Je reclame le remboursement de la TEOM (Taxe d'Enlevement des Ordures Menageres).\n")
        
        self.multi_cell(0, 6, intro.encode('latin-1', 'replace').decode('latin-1'))
        
        # --- AMÉLIORATION POINT 2 : TEXTE RENFORCÉ ART 1353 ---
        self.set_font("Arial", 'B', 11)
        mention_3 = ("3. En application de l'art. 1353 du Code Civil, je mets le debiteur en demeure de produire "
                     "les releves de compte bancaires certifies attestant du debit des sommes qu'il pretend avoir versees. "
                     "Une simple ecriture comptable interne ne saurait constituer une preuve de paiement opposable.")
        self.multi_cell(0, 6, mention_3.encode('latin-1', 'replace').decode('latin-1'))
        
        self.ln(10)
        self.set_font("Arial", 'B', 11)
        self.cell(0, 8, "RECAPITULATIF DE LA CREANCE:", 0, 1)
        
        # TABLEAU SYNTHESE
        self.set_fill_color(240, 240, 240)
        self.cell(100, 8, "POSTE", 1, 0, 'C', fill=True)
        self.cell(40, 8, "MONTANT", 1, 1, 'C', fill=True)
        
        self.set_font("Arial", '', 11)
        self.cell(100, 8, "Total Loyers Impayes (Principal)", 1)
        self.cell(40, 8, f"{total_principal:,.2f} EUR", 1, 1, 'R')
        
        self.cell(100, 8, "Total Interets de Retard", 1)
        self.cell(40, 8, f"{total_interets:,.2f} EUR", 1, 1, 'R')

        self.cell(100, 8, "Indemnites Forfaitaires (Art D.441-5)", 1)
        self.cell(40, 8, f"{total_indemnite:,.2f} EUR", 1, 1, 'R')
        
        self.cell(100, 8, "Total TEOM (Taxes)", 1)
        self.cell(40, 8, f"{total_teom:,.2f} EUR", 1, 1, 'R')
        
        self.set_font("Arial", 'B', 12)
        total_global = total_principal + total_interets + total_teom + total_indemnite
        self.cell(100, 10, "TOTAL GENERAL A ADMETTRE", 1, 0, 'R')
        self.cell(40, 10, f"{total_global:,.2f} EUR", 1, 1, 'R')
        
        # --- AMÉLIORATION POINT 1 : MENTION DATE LIMITE ---
        self.ln(2)
        self.set_font("Arial", 'BI', 9)
        self.set_text_color(200, 0, 0) # Rouge pour l'alerte
        txt_arret = "Arret des comptes au jour du Jugement d'Ouverture (26/06/2025). Les loyers posterieurs sont dus au comptant."
        self.cell(0, 6, txt_arret.encode('latin-1', 'replace').decode('latin-1'), 0, 1, 'C')
        self.set_text_color(0, 0, 0) # Reset Noir

        self.ln(5)
        self.set_font("Arial", '', 11)
        self.cell(0, 10, "Dans l'attente de votre retour, je vous prie d'agreer, Maitre, mes salutations distinguees.", 0, 1)
        
        # --- AMÉLIORATION POINT 4 : ENCART RIB ---
        self.ln(5)
        iban = self.user_info.get('iban', '')
        bic = self.user_info.get('bic', '')
        if iban:
            self.set_fill_color(230, 230, 250)
            self.set_font("Arial", 'B', 10)
            self.cell(0, 8, "COORDONNEES BANCAIRES POUR REGLEMENT (RIB):", 1, 1, 'L', fill=True)
            self.set_font("Courier", '', 10) # Police monospace pour l'IBAN
            self.cell(0, 6, f"IBAN : {iban}", 'LR', 1)
            self.cell(0, 6, f"BIC  : {bic}", 'LBR', 1)

        self.ln(10)
        self.set_font("Arial", '', 11)
        self.cell(0, 10, "Signature :", 0, 1, 'R')

    def generate_page_2_details(self, data_detail, loyer_ht, total_decl, paiements_pre):
        self.add_page()
        self.set_font("Arial", 'B', 14)
        self.cell(0, 10, "DETAIL DU CALCUL FINANCIER", 0, 1, 'C')
        self.ln(5)
        
        # I. RECAP PAIEMENTS
        self.set_font("Arial", 'B', 11)
        self.set_fill_color(230, 230, 230)
        self.cell(0, 8, "I. RECAPITULATIF DES VIREMENTS PERCUS (A DEDUIRE)", 1, 1, 'L', fill=True)
        self.ln(2)

        if not paiements_pre:
             self.set_font("Arial", 'I', 10)
             self.cell(0, 8, "Aucun paiement enregistre sur la periode.", 0, 1)
        else:
            self.set_font("Arial", 'B', 10)
            self.cell(40, 7, "Date", 1)
            self.cell(40, 7, "Montant Recu", 1, 1)
            
            self.set_font("Arial", '', 10)
            total_recu = 0
            for p in paiements_pre:
                self.cell(40, 7, p['date'].strftime("%d/%m/%Y"), 1)
                self.cell(40, 7, f"{p['montant']:.2f} EUR", 1, 1, 'R')
                total_recu += p['montant']
            
            self.set_font("Arial", 'B', 10)
            self.cell(40, 7, "TOTAL PERCU", 1)
            self.cell(40, 7, f"{total_recu:.2f} EUR", 1, 1, 'R')
        
        self.ln(8)

        # II. CASCADE
        self.set_font("Arial", 'B', 11)
        self.cell(0, 8, "II. DETAIL DU CALCUL (CASCADE - Art. 1343-1 CC)", 1, 1, 'L', fill=True)
        self.ln(2)
        
        self.set_font("Arial", '', 10)
        self.cell(0, 6, f"Base Loyer Annuel : {loyer_ht:,.2f} EUR HT", 0, 1)
        self.ln(2)
        
        self.set_font("Arial", 'B', 7) 
        w_d = 18; w_l = 55; w_n = 20
        self.cell(w_d, 8, "Date", 1)
        self.cell(w_l, 8, "Libelle", 1)
        self.cell(w_n, 8, "Debit", 1)
        self.cell(w_n, 8, "Credit", 1)
        self.cell(w_n, 8, "Imp. Princ.", 1)
        self.cell(w_n, 8, "Solde Princ.", 1)
        self.cell(w_n, 8, "Solde Int.", 1, 1)
        
        self.set_font("Arial", '', 7)
        for row in data_detail:
            d_str = row['Date'].strftime("%d/%m/%Y")
            libelle = str(row['Lib']).encode('latin-1', 'replace').decode('latin-1')[:35]
            
            self.cell(w_d, 6, d_str, 1)
            self.cell(w_l, 6, libelle, 1)
            self.cell(w_n, 6, f"{row['Debit']:.2f}", 1, 0, 'R')
            self.cell(w_n, 6, f"{row['Credit']:.2f}", 1, 0, 'R')
            self.cell(w_n, 6, f"{row['Imp_Princ']:.2f}", 1, 0, 'R')
            self.cell(w_n, 6, f"{row['R_Princ']:.2f}", 1, 0, 'R')
            self.cell(w_n, 6, f"{row['R_Int']:.2f}", 1, 1, 'R')

    def generate_page_3_notice(self):
        self.add_page()
        self.set_font("Arial", 'B', 14)
        self.cell(0, 10, "NOTICE METHODOLOGIQUE", 0, 1, 'C')
        self.ln(5)
        
        self.set_font("Arial", '', 11)
        notice_text = (
            "Notice de Calcul :\n\n"
            "- Principal : Loyer contractuel indexe selon l'ILC + TVA 10%.\n\n"
            "- Interets : Taux BCE + 10 points (Art L.441-10), calcule prorata temporis jusqu'au jugement (26/06/2025).\n\n"
            "- Imputation : Les paiements partiels s'imputent d'abord sur les interets (Art 1343-1 Code Civil).\n\n"
            "- Indemnite Forfaitaire : 40 EUR par echeance impayee (Art D.441-5 Code Commerce)."
        )
        self.multi_cell(0, 8, notice_text.encode('latin-1', 'replace').decode('latin-1'))
        
        self.ln(10)
        self.set_font("Arial", 'B', 12)
        self.cell(0, 10, "ANNEXE : TABLEAUX DE REFERENCE", 0, 1)
        
        self.set_font("Arial", 'B', 10)
        self.cell(40, 8, "Indices ILC", 0, 1)
        self.set_font("Arial", '', 9)
        self.cell(30, 6, "Annee", 1); self.cell(30, 6, "Valeur", 1, 1)
        for k, v in INDICES.items():
            self.cell(30, 6, str(k), 1); self.cell(30, 6, str(v), 1, 1)
            
        self.ln(5)
        self.set_font("Arial", 'B', 10)
        self.cell(40, 8, "Taux Legal (BCE+10)", 0, 1)
        self.set_font("Arial", '', 9)
        self.cell(30, 6, "Date Debut", 1); self.cell(30, 6, "Taux %", 1, 1)
        for d, t in TAUX_LEGAUX:
            self.cell(30, 6, d.strftime("%d/%m/%Y"), 1); self.cell(30, 6, f"{t:.2f}", 1, 1)

    def generate_page_4_teom(self, teom_list, uploaded_images):
        self.add_page()
        self.set_font("Arial", 'B', 14)
        self.cell(0, 10, "JUSTIFICATIFS TEOM (Taxes)", 0, 1, 'C')
        self.ln(5)
        
        if teom_list:
            self.set_font("Arial", 'B', 10)
            self.cell(50, 8, "Annee", 1)
            self.cell(50, 8, "Montant", 1, 1)
            self.set_font("Arial", '', 10)
            for t in teom_list:
                self.cell(50, 8, str(t['annee']), 1)
                self.cell(50, 8, f"{t['montant']:.2f} EUR", 1, 1, 'R')
            self.ln(10)
        
        self.set_font("Arial", 'I', 10)
        self.set_text_color(100, 100, 100)
        self.multi_cell(0, 5, "Note de lecture: Veuillez vous referer a la ligne 'Taxe d'enlevement des ordures menageres' sur les avis ci-joints. Seule cette ligne est reclamee.")
        self.set_text_color(0, 0, 0)
        self.ln(5)
        self.cell(0, 10, "Copies des Avis de Taxe Fonciere (Images) :", 0, 1)
        
        for img_file in uploaded_images:
            if img_file.type == "application/pdf": continue # On ignore les PDF ici
            try:
                self.add_page()
                img = Image.open(img_file)
                if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    img.save(tmp.name)
                    tmp_path = tmp.name
                self.image(tmp_path, x=10, y=20, w=190)
                os.unlink(tmp_path)
            except Exception as e:
                self.cell(0, 10, f"Erreur affichage image : {str(e)}", 0, 1)

# ==========================================
# CLASS PDF 2 : LA RELANCE (MISE A JOUR V4.2)
# ==========================================
class PDFRelance(FPDF):
    def __init__(self, user_info):
        super().__init__()
        self.user_info = user_info

    def header(self):
        # Header simple sur chaque page
        self.set_font('Arial', 'I', 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, f"Relance Loyers Post-RJ - HOTEL ALBION - Lot {self.user_info.get('lot', '?')}", 0, 0, 'L')
        self.cell(0, 8, f"Proprietaire : {self.user_info.get('nom', 'N/A')}", 0, 1, 'R')
        self.ln(5)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
        
    def generate_letter(self, total_a_reclamer, table_rows, paiements_post):
        self.add_page()
        
        # TITRE AGRESSIF
        self.set_font("Arial", 'B', 14)
        self.cell(0, 10, "MISE EN DEMEURE DE PAYER SOUS HUITAINE", 0, 1, 'C')
        self.set_font("Arial", 'B', 10)
        self.cell(0, 6, "(Loyers posterieurs au Jugement d'Ouverture - Art. L.622-17 Code de commerce)", 0, 1, 'C')
        self.ln(10)
        
        self.set_font("Arial", '', 10)
        self.cell(0, 5, f"Date : {date.today().strftime('%d/%m/%Y')}", 0, 1, 'R')
        self.ln(10)

        # INTRO JURIDIQUE
        txt_intro = ("Maitre,\n\n"
                     "En votre qualite d'Administrateur Judiciaire de la SAS ALBION, je vous notifie par la presente "
                     "le non-paiement partiel des loyers courants, dus au titre de l'occupation des locaux posterieurement au jugement d'ouverture.\n\n"
                     "Conformement aux dispositions de l'article L.622-17 I du Code de commerce, ces creances nees regulierement "
                     "apres le jugement pour les besoins de la procedure doivent etre payees a leur echeance.")
        self.multi_cell(0, 5, txt_intro.encode('latin-1','replace').decode('latin-1'))
        self.ln(8)
        
        # --- NOUVEAU : SECTION 1 - HISTORIQUE DES REGLEMENTS RECUS ---
        self.set_font("Arial", 'B', 10)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 6, "I. HISTORIQUE DES REGLEMENTS ENREGISTRES (POST-RJ)", 1, 1, 'L', fill=True)
        self.ln(2)
        
        if paiements_post:
            self.set_font("Arial", 'B', 9)
            self.cell(40, 6, "Date", 1)
            self.cell(40, 6, "Montant Recu", 1, 1)
            self.set_font("Arial", '', 9)
            total_paye_post = 0
            for p in paiements_post:
                # p est un dict {'date': ..., 'montant': ...}
                d_str = p['date'].strftime("%d/%m/%Y") if isinstance(p['date'], (date, datetime)) else str(p['date'])
                self.cell(40, 6, d_str, 1)
                self.cell(40, 6, f"{p['montant']:.2f} EUR", 1, 1, 'R')
                total_paye_post += p['montant']
            
            self.set_font("Arial", 'B', 9)
            self.cell(40, 6, "TOTAL PERCU", 1)
            self.cell(40, 6, f"{total_paye_post:.2f} EUR", 1, 1, 'R')
        else:
            self.set_font("Arial", 'I', 9)
            self.cell(0, 6, "Aucun reglement recu a ce jour sur la periode posterieure.", 1, 1)
            
        self.ln(8)
        
        # --- SECTION 2 - RESTE DU ---
        self.set_font("Arial", 'B', 10)
        self.cell(0, 6, "II. DETAIL DES SOMMES RESTANT DUES (IMPAYES)", 1, 1, 'L', fill=True)
        self.ln(2)
        
        self.set_font("Arial", 'B', 9)
        self.cell(30, 6, "Echeance", 1)
        self.cell(70, 6, "Libelle", 1)
        self.cell(30, 6, "Montant", 1)
        self.cell(30, 6, "Reste Du", 1, 1)
        
        self.set_font("Arial", '', 9)
        has_debt = False
        for row in table_rows:
            if row["Reste Dû"] > 0 and row["Échéance"] <= date.today():
                 has_debt = True
                 self.cell(30, 6, row["Échéance"].strftime("%d/%m/%Y"), 1)
                 self.cell(70, 6, str(row["Libellé"]).encode('latin-1','replace').decode('latin-1')[:35], 1)
                 self.cell(30, 6, f"{row['Montant']:.2f}", 1, 0, 'R')
                 self.set_font("Arial", 'B', 9)
                 self.cell(30, 6, f"{row['Reste Dû']:.2f}", 1, 1, 'R')
                 self.set_font("Arial", '', 9)
        
        if not has_debt:
            self.cell(0, 6, "Aucun impaye exigible a ce jour.", 1, 1)
        
        self.ln(8)
        
        # MENACE (CLAUSE RESOLUTOIRE)
        self.set_font("Arial", 'B', 10)
        self.set_text_color(150, 0, 0) # Rouge foncé
        txt_menace = (f"A defaut de reglement integral de la somme de {total_a_reclamer:,.2f} EUR sous un delai de 8 jours a compter de la reception de la presente :\n"
                      "- Je saisirai Monsieur le Juge-Commissaire pour constater la resiliation de plein droit du bail commercial (Article L.622-14 du Code de commerce).\n"
                      "- Ce defaut de paiement caracterisera l'impossibilite pour l'entreprise de financer sa periode d'observation, justifiant une conversion en Liquidation Judiciaire.\n"
                      "- Le present courrier vaut mise en demeure formelle et fait courir les interets legaux.")
        self.multi_cell(0, 5, txt_menace.encode('latin-1','replace').decode('latin-1'))
        self.set_text_color(0, 0, 0)
        
        self.ln(8)
        
        # RIB
        iban = self.user_info.get('iban', '')
        if iban:
            self.set_font("Arial", 'B', 10)
            self.cell(0, 6, "Reglement par virement exclusivement sur le compte suivant :", 0, 1)
            self.set_font("Courier", '', 10)
            self.cell(0, 6, f"IBAN : {iban}  |  BIC : {self.user_info.get('bic', '')}", 1, 1, 'C')
            self.ln(5)

        self.set_font("Arial", '', 10)
        self.cell(0, 10, "Signature :", 0, 1, 'R')
        
        # COPIES
        self.set_y(-30)
        self.set_font("Arial", 'I', 8)
        self.cell(0, 5, "Copie pour information a : Monsieur le Mandataire Judiciaire et M. MICHEL (Controleur).", 0, 1)

# ==========================================
# INTERFACE STREAMLIT
# ==========================================

if 'paiements_pre' not in st.session_state: st.session_state.paiements_pre = []
if 'paiements_post' not in st.session_state: st.session_state.paiements_post = []
if 'teom_list' not in st.session_state: st.session_state.teom_list = []

# --- SIDEBAR ---
with st.sidebar:
    st.title("👤 IDENTITÉ")
    with st.expander("Vos coordonnées", expanded=True):
        id_nom = st.text_input("Nom & Prénom", placeholder="Dupont Jean")
        id_lot = st.text_input("N° de Lot", placeholder="Ex: A204")
        id_tel = st.text_input("Téléphone")
        id_email = st.text_input("Email")
        # NOUVEAUX CHAMPS RIB
        st.markdown("**Coordonnées Bancaires (Optionnel)**")
        id_iban = st.text_input("IBAN")
        id_bic = st.text_input("BIC")
    
    st.divider()
    st.header("💾 Données")
    uploaded_file = st.file_uploader("📂 Charger Dossier JSON", type=["json"])
    if uploaded_file:
        try:
            data = json.load(uploaded_file)
            st.session_state.paiements_pre = [{"date": datetime.strptime(p["date"], "%Y-%m-%d").date(), "montant": p["montant"]} for p in data.get("paiements", [])]
            st.session_state.paiements_post = [{"date": datetime.strptime(p["date"], "%Y-%m-%d").date(), "montant": p["montant"]} for p in data.get("paiements_post", [])]
            st.session_state.teom_list = data.get("teom", [])
            st.session_state.loaded_loyer = data.get("loyer", 0.0)
            if "identity" in data:
                id_nom = data["identity"].get("nom", "")
            st.success("Dossier chargé !")
        except:
            st.error("Erreur fichier.")

# --- MAIN PAGE ---
st.title("🏛️ Gestionnaire Créance Albion V4.2")

col_loyer, col_save = st.columns([1, 3])
with col_loyer:
    def_loyer = st.session_state.get("loaded_loyer", 0.0)
    loyer_ht = st.number_input("Loyer Annuel HT (€)", min_value=0.0, step=100.0, value=def_loyer, format="%.2f")
    if loyer_ht > 0:
        st.success(f"TTC : {(loyer_ht*1.10):,.2f} €")

with col_save:
    if loyer_ht > 0:
        st.write("") 
        st.write("") 
        save_data = {
            'loyer': loyer_ht, 
            'paiements': st.session_state.paiements_pre,
            'paiements_post': st.session_state.paiements_post,
            'teom': st.session_state.teom_list,
            'identity': {'nom': id_nom, 'lot': id_lot, 'tel': id_tel, 'email': id_email}
        }
        st.download_button("💾 SAUVEGARDER", json.dumps(save_data, default=json_serial), f"albion_backup.json", "application/json")

if loyer_ht == 0:
    st.warning("👈 Saisissez le Loyer Annuel HT.")
    st.stop()

# --- ONGLETS ---
tab1, tab2, tab_teom = st.tabs(["1. 🔒 DÉCLARATION (Avant RJ)", "2. 🔄 SUIVI (Après RJ)", "3. 🗑️ TEOM & JUSTIFICATIFS"])

# ==========================================
# ONGLET 3 : MODULE TEOM
# ==========================================
with tab_teom:
    st.info("### Gestion des Taxes Ordures Ménagères (TEOM)")
    c_teom1, c_teom2 = st.columns(2)
    with c_teom1:
        st.markdown("#### 1. Ajouter une Taxe Payée")
        with st.form("add_teom"):
            t_annee = st.number_input("Année", min_value=2019, max_value=2025, step=1)
            t_montant = st.number_input("Montant (€)", min_value=0.0, step=10.0)
            if st.form_submit_button("Ajouter TEOM"):
                st.session_state.teom_list.append({"annee": t_annee, "montant": t_montant})
                st.rerun()
        
        if st.session_state.teom_list:
            st.dataframe(pd.DataFrame(st.session_state.teom_list))
            if st.button("Effacer Taxes"):
                st.session_state.teom_list = []
                st.rerun()
                
    with c_teom2:
        st.markdown("#### 2. Uploader les Justificatifs")
        st.info("💡 Conseil : Surlignez la ligne 'Taxe Ordures Ménagères' sur vos scans avant upload pour faciliter la lecture.")
        teom_imgs = st.file_uploader("Scans Avis Taxe Foncière (PDF/PNG/JPG)", type=['png', 'jpg', 'jpeg', 'pdf'], accept_multiple_files=True)
        if teom_imgs:
            st.success(f"{len(teom_imgs)} fichier(s) prêt(s).")

# ==========================================
# ONGLET 1 : DÉCLARATION
# ==========================================
with tab1:
    st.info("### 🟦 CALCUL DE LA CRÉANCE (Arrêt au 26/06/2025)")
    
    with st.expander("📊 TABLEAUX DE RÉFÉRENCE (Indices & Taux)", expanded=False):
        c_ref1, c_ref2 = st.columns(2)
        with c_ref1:
            st.markdown("**Indices ILC**")
            st.dataframe(pd.DataFrame(list(INDICES.items()), columns=["Année", "Indice"]), hide_index=True)
        with c_ref2:
            st.markdown("**Taux Intérêts (BCE + 10pts)**")
            data_taux = [{"Date": d.strftime("%d/%m/%Y"), "Taux": f"{t:.2f} %"} for d, t in TAUX_LEGAUX]
            st.dataframe(pd.DataFrame(data_taux), hide_index=True)

    c1, c2 = st.columns([1, 2])
    with c1:
        with st.form("ajout_pre"):
            d_p = st.date_input("Date Virement", date(2024, 1, 1), format="DD/MM/YYYY") 
            m_p = st.number_input("Montant TTC (€)", step=100.0)
            if st.form_submit_button("Ajouter Loyer Perçu"):
                if d_p > DATE_JUGEMENT:
                    st.error("Date > Jugement ! Voir Onglet 2.")
                else:
                    st.session_state.paiements_pre.append({"date": d_p, "montant": m_p})
                    st.rerun()
        
        if st.session_state.paiements_pre:
            st.markdown("Loyers Perçus :")
            st.dataframe(pd.DataFrame(st.session_state.paiements_pre))
            if st.button("Effacer Paiements Pré-RJ"):
                st.session_state.paiements_pre = []
                st.rerun()

    with c2:
        has_paiements = len(st.session_state.paiements_pre) > 0
        if not has_paiements:
            no_payment = st.checkbox("Certifier aucun paiement reçu", key="nopay_pre")
            if not no_payment: st.stop()

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
                data_detail.append({"Date": curr, "Lib": ev["label"], "Debit": montant, "Credit": 0, "Imp_Princ": 0.0, "R_Princ": solde_princ, "R_Int": solde_int})
            else:
                imp_int = min(montant, solde_int)
                solde_int -= imp_int
                imp_princ = montant - imp_int
                solde_princ -= imp_princ
                data_detail.append({"Date": curr, "Lib": "Paiement", "Debit": 0, "Credit": montant, "Imp_Princ": -imp_princ, "R_Princ": solde_princ, "R_Int": solde_int})
            last_date = curr
            
        if last_date < DATE_JUGEMENT and solde_princ > 0:
            solde_int += calculer_interets_ligne(solde_princ, last_date, DATE_JUGEMENT)
        
        princ_net = max(0, solde_princ)
        int_net = max(0, solde_int)
        indemnite = nb_echeances * INDEMNITE_FORFAITAIRE
        total_teom = sum(t['montant'] for t in st.session_state.teom_list)
        total_final = princ_net + int_net + indemnite + total_teom
        
        st.markdown(f"### 🏁 Total : {total_final:,.2f} €")
        c_res = st.columns(4)
        c_res[0].metric("Principal", f"{princ_net:,.2f} €")
        c_res[1].metric("Intérêts", f"{int_net:,.2f} €")
        c_res[2].metric("Indemnités", f"{indemnite:,.2f} €")
        c_res[3].metric("TEOM", f"{total_teom:,.2f} €")

        st.write("---")
        
        # --- BOUTON PDF AVEC MERGE ---
        if st.button("📄 TÉLÉCHARGER LE DOSSIER JURIDIQUE (PDF)", type="primary", use_container_width=True):
            if not id_nom:
                st.error("⚠️ Renseignez votre IDENTITÉ à gauche !")
            else:
                user_data = {
                    'nom': id_nom, 'lot': id_lot, 'tel': id_tel, 'email': id_email,
                    'iban': id_iban, 'bic': id_bic
                }
                
                # 1. Générer le rapport principal (FPDF)
                pdf_report = DossierJuridiquePDF(user_data)
                pdf_report.generate_page_1_courrier(princ_net, int_net, total_teom, indemnite)
                pdf_report.generate_page_2_details(data_detail, loyer_ht, total_final, st.session_state.paiements_pre)
                pdf_report.generate_page_3_notice() 
                pdf_report.generate_page_4_teom(st.session_state.teom_list, teom_imgs if teom_imgs else [])
                
                # 2. Conversion FPDF -> Bytes
                report_bytes = pdf_report.output(dest='S').encode('latin-1')
                
                # 3. Merging (pypdf) pour ajouter les PDF uploadés
                merger = PdfWriter()
                merger.append(io.BytesIO(report_bytes)) 
                
                if teom_imgs:
                    for f in teom_imgs:
                        if f.type == "application/pdf":
                            merger.append(f)
                            
                # 4. Output final
                final_buffer = io.BytesIO()
                merger.write(final_buffer)
                
                st.download_button(
                    label="📥 CLIQUEZ ICI POUR LE PDF FINAL",
                    data=final_buffer.getvalue(),
                    file_name=f"Dossier_Albion_{id_nom.replace(' ', '_')}.pdf",
                    mime="application/pdf"
                )

        if data_detail:
            df_g = pd.DataFrame(data_detail)
            df_melt = df_g.melt('Date', value_vars=['R_Princ', 'R_Int'], var_name='Type', value_name='Montant')
            chart = alt.Chart(df_melt).mark_line(interpolate='step-after').encode(
                x='Date', 
                y='Montant',
                color=alt.Color('Type', scale=alt.Scale(domain=['R_Princ', 'R_Int'], range=['#1f77b4', '#d62728']), legend=alt.Legend(title="Type de dette")),
                tooltip=['Date', 'Type', 'Montant']
            )
            st.altair_chart(chart, use_container_width=True)

# ==========================================
# ONGLET 2 : SUIVI
# ==========================================
with tab2:
    st.warning("### 🟧 SUIVI LOYERS POST-JUGEMENT")
    col_p1, col_p2 = st.columns([1, 2])
    with col_p1:
        with st.form("ajout_post"):
            d_p_post = st.date_input("Date Virement", date.today(), format="DD/MM/YYYY") 
            m_p_post = st.number_input("Montant Reçu (€)", step=100.0)
            if st.form_submit_button("Ajouter Paiement"):
                st.session_state.paiements_post.append({"date": d_p_post, "montant": m_p_post})
                st.rerun()
        if st.session_state.paiements_post:
             st.dataframe(pd.DataFrame(st.session_state.paiements_post))

    with col_p2:
        echeances_post = generer_loyers_post_rj(loyer_ht)
        solde_disponible = sum(p["montant"] for p in st.session_state.paiements_post)
        table_rows = []
        total_a_reclamer = 0
        
        for ech in echeances_post:
            montant_du = ech["montant"]
            paye = min(montant_du, solde_disponible)
            solde_disponible -= paye
            reste = montant_du - paye
            
            status = ""
            if reste == 0: status = "🟢 PAYÉ"
            elif paye > 0: status = "🟠 PARTIEL"
            elif ech["date"] <= date.today(): status = "🔴 IMPAYÉ"
            else: status = "⚪ À ÉCHOIR"
            
            if ech["date"] <= date.today():
                total_a_reclamer += reste
            
            table_rows.append({
                "Échéance": ech["date"], 
                "Libellé": ech["label"], 
                "Montant": montant_du, 
                "Payé": paye, 
                "Reste Dû": reste,
                "Statut": status
            })
            
        df_post = pd.DataFrame(table_rows)
        
        def highlight_status(val):
            if "PAYÉ" in val: return 'background-color: #d4edda; color: #155724'
            elif "PARTIEL" in val: return 'background-color: #fff3cd; color: #856404'
            elif "IMPAYÉ" in val: return 'background-color: #f8d7da; color: #721c24'
            return ''

        st.dataframe(df_post.style.format({"Montant": "{:.2f} €", "Payé": "{:.2f} €", "Reste Dû": "{:.2f} €"}).map(highlight_status, subset=["Statut"]))
        
        st.metric("Reste à payer (Exigible)", f"{total_a_reclamer:,.2f} €")
        
        if total_a_reclamer > 0:
            if st.button("📩 GÉNÉRER MISE EN DEMEURE (PDF)"):
                # On recrée user_data ici pour être sûr d'avoir les dernières infos saisies à gauche
                user_data_relance = {
                    'nom': id_nom, 'lot': id_lot, 'iban': id_iban, 'bic': id_bic
                }
                pdf_r = PDFRelance(user_data_relance)
                # MODIF : Ajout de st.session_state.paiements_post
                pdf_r.generate_letter(total_a_reclamer, table_rows, st.session_state.paiements_post)
                
                st.download_button("📥 TÉLÉCHARGER RELANCE", pdf_r.output(dest='S').encode('latin-1'), "relance_post_rj.pdf", "application/pdf")
