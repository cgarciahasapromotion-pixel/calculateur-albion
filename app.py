import streamlit as st
from datetime import datetime, date
import pandas as pd
from fpdf import FPDF
import io
from PIL import Image
import tempfile
import os

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Générateur Dossier Créance Albion", page_icon="⚖️")

# --- FONCTIONS UTILITAIRES ---

def calculate_interest(principal, due_date, end_date, rate):
    """Calcule les intérêts simples entre deux dates."""
    if due_date >= end_date:
        return 0.0
    days = (end_date - due_date).days
    interest = (principal * rate * days) / 365
    return interest

def format_currency(amount):
    return f"{amount:,.2f} €".replace(",", " ").replace(".", ",")

# --- CLASSE PDF PERSONNALISÉE ---
class PDF(FPDF):
    def header(self):
        # En-tête discret sur toutes les pages sauf la première (qui est le courrier)
        if self.page_no() > 1:
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Dossier de Créance - Lot {st.session_state.get("lot_num", "?")} - {st.session_state.get("prop_name", "")}', 0, 1, 'R')

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

# --- INTERFACE UTILISATEUR ---

st.title("⚖️ Générateur de Dossier de Créance")
st.markdown("""
Cette application génère un **dossier PDF unique et complet** à transmettre à votre avocat.
Il inclut : le courrier de contestation, le calcul des loyers et intérêts, la notice méthodologique et les justificatifs de taxes.
""")

# 1. IDENTITÉ DU PROPRIÉTAIRE
st.header("1. Vos Informations")
col1, col2 = st.columns(2)
with col1:
    prop_name = st.text_input("Nom et Prénom", placeholder="Ex: Jean DUPONT")
with col2:
    lot_num = st.text_input("Numéro de Lot", placeholder="Ex: 204")

st.session_state["prop_name"] = prop_name
st.session_state["lot_num"] = lot_num

prop_phone = st.text_input("Téléphone (pour le courrier)", placeholder="06 00 00 00 00")
prop_email = st.text_input("Email (facultatif)", placeholder="jean.dupont@email.com")

# 2. PARAMÈTRES DE CALCUL (VERSION 1)
st.header("2. Calcul des Loyers Impayés")
st.info("Les paramètres ci-dessous servent à calculer le principal et les intérêts légaux.")

# Valeurs par défaut (BCE + 10 points)
TAUX_INTERET = 0.1425  # 4.25 + 10 = 14.25% (Moyenne simplifiée ou taux actuel)
DATE_JUGEMENT = date(2025, 6, 26)

loyer_annuel_ht = st.number_input("Loyer Annuel HT (selon bail)", value=5000.0, step=100.0)
tva_rate = 0.10 # 10%

# Périodes d'impayés (Exemple simplifié, à adapter selon votre code V1 précis)
st.subheader("Périodes impayées")
periods_data = []

# On permet d'ajouter plusieurs périodes si nécessaire, ici simplifié pour l'exemple
# Vous pouvez remettre ici votre logique de "Trimestre" ou "Mois" de la V1
start_date_impaye = st.date_input("Date de début des impayés", value=date(2023, 1, 1))

if st.button("Lancer le calcul des loyers"):
    st.session_state.calc_done = True
else:
    st.session_state.calc_done = True # On force à True pour l'exemple interactif

# Simulation du tableau de résultat (Reprenez votre logique V1 ici)
# Ici je génère une liste fictive basée sur la date de début pour l'exemple
loyer_mensuel_ttc = (loyer_annuel_ht * (1 + tva_rate)) / 12
rows = []
current_date = start_date_impaye
total_principal = 0
total_interets = 0

while current_date < DATE_JUGEMENT:
    due_date = current_date
    amount_due = loyer_mensuel_ttc
    interest = calculate_interest(amount_due, due_date, DATE_JUGEMENT, TAUX_INTERET)
    
    rows.append({
        "Echeance": due_date.strftime("%d/%m/%Y"),
        "Montant_TTC": amount_due,
        "Interets": interest,
        "Jours_Retard": (DATE_JUGEMENT - due_date).days
    })
    total_principal += amount_due
    total_interets += interest
    
    # Mois suivant
    if current_date.month == 12:
        current_date = date(current_date.year + 1, 1, 1)
    else:
        current_date = date(current_date.year, current_date.month + 1, 1)

df_result = pd.DataFrame(rows)

# 3. TEOM (TAXES ORDURES MÉNAGÈRES)
st.header("3. Taxes Ordures Ménagères (TEOM)")
st.write("Avez-vous payé des taxes foncières (TEOM) qui auraient dû être remboursées par l'exploitant ?")

if "teom_list" not in st.session_state:
    st.session_state.teom_list = []

col_t1, col_t2, col_t3 = st.columns([1, 1, 1])
with col_t1:
    annee_teom = st.selectbox("Année", ["2022", "2023", "2024", "2025"])
with col_t2:
    montant_teom = st.number_input("Montant TEOM (€)", min_value=0.0, step=10.0)
with col_t3:
    st.write("")
    st.write("")
    if st.button("Ajouter cette Taxe"):
        st.session_state.teom_list.append({"Annee": annee_teom, "Montant": montant_teom})

# Affichage du tableau TEOM
total_teom = 0
if st.session_state.teom_list:
    st.table(pd.DataFrame(st.session_state.teom_list))
    total_teom = sum(item["Montant"] for item in st.session_state.teom_list)
    st.write(f"**Total TEOM à réclamer : {format_currency(total_teom)}**")

# Upload des justificatifs
uploaded_files = st.file_uploader("Téléverser les avis de Taxe Foncière (Images JPG/PNG)", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])

# 4. RÉCAPITULATIF FINAL
st.header("4. Récapitulatif Total")
grand_total = total_principal + total_interets + total_teom

col_res1, col_res2, col_res3 = st.columns(3)
col_res1.metric("Loyers Impayés", format_currency(total_principal))
col_res2.metric("Intérêts de Retard", format_currency(total_interets))
col_res3.metric("TEOM", format_currency(total_teom))

st.success(f"TOTAL CRÉANCE À DÉCLARER : {format_currency(grand_total)}")

# --- GÉNÉRATION DU PDF ---

def create_pdf():
    pdf = PDF()
    
    # --- PAGE 1 : COURRIER DE CONTESTATION ---
    pdf.add_page()
    pdf.set_font('Arial', '', 11)
    
    # En-tête Expéditeur
    pdf.cell(0, 5, f"{prop_name}", 0, 1)
    pdf.cell(0, 5, f"Propriétaire du Lot n° {lot_num}", 0, 1)
    pdf.cell(0, 5, f"Tél : {prop_phone}", 0, 1)
    pdf.cell(0, 5, f"Email : {prop_email}", 0, 1)
    pdf.ln(10)
    
    # Destinataire (Avocat pour transmission)
    pdf.set_x(100)
    pdf.cell(0, 5, "A l'attention de Maître MOULY", 0, 1)
    pdf.set_x(100)
    pdf.cell(0, 5, "Pour transmission au Mandataire Judiciaire", 0, 1)
    pdf.ln(10)
    
    # Objet
    pdf.set_font('Arial', 'B', 11)
    today = date.today().strftime("%d/%m/%Y")
    pdf.cell(0, 10, f"Objet : CONTESTATION D'ÉTAT DES CRÉANCES - HOTEL ALBION - {today}", 0, 1)
    pdf.ln(5)
    
    # Corps du courrier
    pdf.set_font('Arial', '', 11)
    corps_courrier = (
        "Maître,\n\n"
        "Je fais suite à la communication de l'état des créances établi par le mandataire.\n"
        "Par la présente, je conteste formellement le montant retenu par le débiteur.\n\n"
        "Ma contestation porte sur trois points fondamentaux, détaillés dans ce dossier :\n\n"
        "1. L'application stricte des pénalités de retard (Art. L.441-10 du Code de commerce).\n"
        "2. Le remboursement de la TEOM (Taxe d'Ordures Ménagères) due contractuellement.\n"
        "3. L'exigence de preuves de paiement (Art. 1353 du Code Civil) pour les sommes que le débiteur "
        "prétend avoir versées mais qui n'apparaissent pas sur mes comptes.\n\n"
        "Vous trouverez ci-après le détail chiffré et la méthodologie appliquée.\n\n"
        "SYNTHÈSE DE MA CRÉANCE À DÉCLARER :"
    )
    pdf.multi_cell(0, 6, corps_courrier)
    pdf.ln(5)
    
    # Tableau Synthèse dans le courrier
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(100, 8, "POSTE", 1)
    pdf.cell(50, 8, "MONTANT", 1, 1, 'R')
    
    pdf.set_font('Arial', '', 11)
    pdf.cell(100, 8, "Principal (Loyers Impayés)", 1)
    pdf.cell(50, 8, format_currency(total_principal), 1, 1, 'R')
    
    pdf.cell(100, 8, "Intérêts de Retard (Arrêtés au 26/06/25)", 1)
    pdf.cell(50, 8, format_currency(total_interets), 1, 1, 'R')
    
    pdf.cell(100, 8, "Taxes (TEOM)", 1)
    pdf.cell(50, 8, format_currency(total_teom), 1, 1, 'R')
    
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(100, 10, "TOTAL CRÉANCE", 1)
    pdf.cell(50, 10, format_currency(grand_total), 1, 1, 'R')
    
    pdf.ln(10)
    pdf.set_font('Arial', '', 11)
    pdf.multi_cell(0, 6, "Je certifie l'exactitude des informations fournies.\n\nSignature :")
    
    # --- PAGE 2 : DÉTAIL DU CALCUL ---
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, "ANNEXE 1 : DÉTAIL DES LOYERS ET INTÉRÊTS", 0, 1, 'C')
    pdf.ln(5)
    
    pdf.set_font('Arial', 'B', 10)
    # En-têtes tableau
    pdf.cell(40, 8, "Échéance", 1)
    pdf.cell(40, 8, "Montant TTC", 1)
    pdf.cell(30, 8, "Jours Retard", 1)
    pdf.cell(40, 8, "Intérêts", 1, 1)
    
    pdf.set_font('Arial', '', 10)
    for index, row in df_result.iterrows():
        pdf.cell(40, 7, str(row['Echeance']), 1)
        pdf.cell(40, 7, f"{row['Montant_TTC']:.2f}", 1)
        pdf.cell(30, 7, str(row['Jours_Retard']), 1)
        pdf.cell(40, 7, f"{row['Interets']:.2f}", 1, 1)
        
    # --- PAGE 3 : NOTICE MÉTHODOLOGIQUE ---
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, "ANNEXE 2 : NOTICE MÉTHODOLOGIQUE", 0, 1, 'C')
    pdf.ln(5)
    
    pdf.set_font('Arial', '', 11)
    notice_text = (
        "OBJET : Méthodologie appliquée pour le calcul des arriérés et intérêts.\n\n"
        "1. LE PRINCIPAL\n"
        "Le loyer de référence est le loyer contractuel indexé selon l'ILC. La TVA de 10% est appliquée.\n\n"
        "2. LES INTÉRÊTS DE RETARD\n"
        "Conformément à l'article L.441-10 du Code de Commerce, des pénalités sont appliquées sur chaque échéance.\n"
        "- Taux : Taux BCE majoré de 10 points (calculé à 14.25% en moyenne sur la période).\n"
        "- Calcul : Prorata temporis (Exact/365) jusqu'au 26/06/2025.\n"
        "- Imputation : Selon l'art. 1343-1 du Code Civil, les paiements partiels (si existants) s'imputent d'abord sur les intérêts.\n\n"
        "3. ARRÊT DES COMPTES\n"
        "Le calcul est strictement arrêté à la date du jugement d'ouverture (26 juin 2025)."
    )
    pdf.multi_cell(0, 6, notice_text)

    # --- PAGE 4 : JUSTIFICATIFS TEOM ---
    if st.session_state.teom_list or uploaded_files:
        pdf.add_page()
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, "ANNEXE 3 : JUSTIFICATIFS TEOM", 0, 1, 'C')
        pdf.ln(5)
        
        # Tableau récap TEOM
        if st.session_state.teom_list:
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(50, 8, "Année", 1)
            pdf.cell(50, 8, "Montant", 1, 1)
            pdf.set_font('Arial', '', 10)
            for item in st.session_state.teom_list:
                pdf.cell(50, 8, str(item['Annee']), 1)
                pdf.cell(50, 8, format_currency(item['Montant']), 1, 1)
            pdf.ln(10)
            
        # Images uploadées
        if uploaded_files:
            pdf.set_font('Arial', 'I', 10)
            pdf.cell(0, 10, "Copies des avis de taxe foncière ci-dessous :", 0, 1)
            
            for uploaded_file in uploaded_files:
                # Sauvegarde temporaire de l'image pour FPDF
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
                    image = Image.open(uploaded_file)
                    # Conversion en RGB si nécessaire (pour les PNG transparents)
                    if image.mode in ("RGBA", "P"):
                        image = image.convert("RGB")
                    image.save(tmp_file.name)
                    tmp_path = tmp_file.name
                
                # Ajout de l'image au PDF (Largeur ajustée à 180mm)
                try:
                    pdf.image(tmp_path, w=180)
                    pdf.ln(10)
                except Exception as e:
                    st.error(f"Erreur avec l'image : {e}")
                
                # Nettoyage
                os.remove(tmp_path)

    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- BOUTON DE TÉLÉCHARGEMENT ---
st.markdown("---")
if prop_name and lot_num:
    if st.button("GÉNÉRER MON DOSSIER JURIDIQUE COMPLET (PDF)"):
        try:
            pdf_bytes = create_pdf()
            file_name = f"Dossier_Creance_Lot_{lot_num}_{prop_name.replace(' ', '_')}.pdf"
            
            st.download_button(
                label="📥 Télécharger le Dossier PDF prêt à envoyer",
                data=pdf_bytes,
                file_name=file_name,
                mime="application/pdf"
            )
            st.success("Dossier généré avec succès ! N'oubliez pas de le signer.")
        except Exception as e:
            st.error(f"Une erreur est survenue lors de la génération du PDF : {e}")
else:
    st.warning("Veuillez remplir votre Nom et Numéro de lot pour générer le PDF.")
