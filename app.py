import streamlit as st
import pandas as pd
import altair as alt
from datetime import date, datetime, timedelta
from fpdf import FPDF
import io
import json

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Calculateur Créance Albion", page_icon="⚖️", layout="wide")

# --- CONSTANTES JURIDIQUES & DONNÉES ---
DATE_JUGEMENT = date(2025, 6, 26)
DATE_DEBUT_GRAPH = date(2019, 6, 1)
INDEMNITE_FORFAITAIRE = 40.0 # Art. D.441-5 du Code de commerce

# Taux d'intérêt légal (BCE + 10 points) - Source : Banque de France (L441-10)
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

# Indices ILC (Historique INSEE)
INDICES = {
    "BASE": 114.06, # T1 2019
    "2019": 116.16, # T4 2019
    "2020": 115.79, # T4 2020
    "2021": 118.59, # T4 2021
    "2022": 126.05, # T4 2022
    "2023": 132.63, # T4 2023
    "2024": 135.30  # T4 2024
}

# --- UTILITAIRES DE SAUVEGARDE (JSON) ---
def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

# --- FONCTIONS MOTEUR ---

def get_taux_legal(d):
    """Trouve le taux applicable pour une date donnée"""
    for start_date, rate in reversed(TAUX_LEGAUX):
        if d >= start_date:
            return rate
    return 10.00

def calculer_interets_ligne(montant, date_depart, date_fin):
    """Calcule les intérêts précis au jour le jour (intérêts simples)"""
    total_interets = 0
    if date_depart >= date_fin:
        return 0.0

    current_date = date_depart
    while current_date < date_fin:
        taux = get_taux_legal(current_date)
        
        # Trouver la prochaine date de changement de taux
        next_change = date_fin
        for start_date, _ in TAUX_LEGAUX:
            if start_date > current_date and start_date < date_fin:
                next_change = start_date
                break
        
        days = (next_change - current_date).days
        
        # Formule : Capital x Taux x (Jours / 365)
        interet_periode = montant * (taux / 100) * (days / 365)
        total_interets += interet_periode
        
        current_date = next_change
        
    return total_interets

def generer_loyers_theoriques(loyer_annuel_ht):
    """Génère la liste des loyers dus (Échéancier théorique)"""
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
    echeances.append({"date": date(2025, 4, 10), "label": "Avril-Mai 2025", "montant": montant_avril_mai})
    
    montant_juin_prorata = (loyer_2025 / 30) * 26
    echeances.append({"date": date(2025, 6, 26), "label": "Juin 2025 (Prorata 26j)", "montant": montant_juin_prorata})

    return echeances

# --- CLASS PDF ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        txt = 'Declaration de Creance - HOTEL ALBION'.encode('latin-1', 'replace').decode('latin-1')
        self.cell(0, 10, txt, 0, 1, 'C')
        
        self.set_font('Arial', 'I', 10)
        txt_sub = '(Calcul certifie selon Art. 1343-1 Code Civil)'.encode('latin-1', 'replace').decode('latin-1')
        self.cell(0, 10, txt_sub, 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

# ==========================================
# INTERFACE UTILISATEUR (STREAMLIT)
# ==========================================

# --- VOLET LATÉRAL : SAUVEGARDE / CHARGEMENT ---
with st.sidebar:
    st.header("💾 Sauvegarde & Reprise")
    st.info("Utilisez cette fonction pour sauvegarder votre travail et le reprendre plus tard sans tout ressaisir.")
    
    # CHARGEMENT
    uploaded_file = st.file_uploader("📂 Charger un dossier (.json)", type=["json"])
    if uploaded_file is not None:
        try:
            data = json.load(uploaded_file)
            st.session_state.paiements = []
            for p in data.get("paiements", []):
                # Conversion str -> date
                st.session_state.paiements.append({
                    "date": datetime.strptime(p["date"], "%Y-%m-%d").date(),
                    "montant": p["montant"]
                })
            # On stocke temporairement le loyer pour le pré-remplir
            st.session_state.loaded_loyer = data.get("loyer", 0.0)
            st.success("Données chargées ! (Vérifiez le montant du loyer)")
        except Exception as e:
            st.error(f"Erreur lecture fichier : {e}")

st.title("🏛️ Calculateur de Créance - Propriétaires Albion")

# --- 1. SECTIONS PÉDAGOGIQUES ---
col_info1, col_info2 = st.columns(2)

with col_info1:
    with st.expander("📚 MODE D'EMPLOI JURIDIQUE", expanded=True):
        st.markdown("""
        **1. Méthode "Waterfall" (Art. 1343-1 C. Civil) :**
        Les paiements remboursent **d'abord les intérêts**, puis le capital. Cela maximise le montant de votre créance privilégiée (Loyer).
        
        **2. Indemnité Forfaitaire (Art. D.441-5 C. Commerce) :**
        L'outil ajoute automatiquement **40 €** pour chaque facture (échéance) impayée ou payée en retard. C'est un droit légal (Créance Chirographaire).
        
        **3. Formalisme :**
        Le PDF inclut désormais un bloc signature et les réserves d'usage (Art L.622-24) obligatoires pour la procédure.
        """)

with col_info2:
    with st.expander("📈 TABLEAUX DE RÉFÉRENCE", expanded=False):
        st.markdown("**Indices ILC**")
        st.dataframe(pd.DataFrame(list(INDICES.items()), columns=["Année/Réf", "Indice"]), hide_index=True)
        
        st.markdown("**Taux Intérêt (BCE + 10pts)**")
        data_taux_display = []
        for d, t in TAUX_LEGAUX:
            data_taux_display.append({
                "Date d'effet": d.strftime("%d/%m/%Y"),
                "Taux Annuel": f"{t:.2f} %"
            })
        st.dataframe(pd.DataFrame(data_taux_display), hide_index=True)

# --- 2. SAISIE DES DONNÉES ---
if 'paiements' not in st.session_state:
    st.session_state.paiements = []

st.write("---")
col_input1, col_input2 = st.columns([1, 2])

with col_input1:
    st.subheader("1. Bail (HT)")
    # Valeur par défaut si chargée depuis JSON
    def_loyer = st.session_state.get("loaded_loyer", 0.0)
    loyer_ht = st.number_input("Loyer Annuel HT (€)", min_value=0.0, step=100.0, value=def_loyer, format="%.2f")
    
    if loyer_ht > 0:
        st.success(f"Soit {(loyer_ht*1.10):,.2f} € TTC/an")
        
        # BOUTON DE SAUVEGARDE (DANS LA COLONNE DE GAUCHE POUR ACCESSIBILITÉ)
        st.write("---")
        save_data = {'loyer': loyer_ht, 'paiements': st.session_state.paiements}
        st.download_button(
            label="💾 SAUVEGARDER MA SAISIE",
            data=json.dumps(save_data, default=json_serial),
            file_name=f"albion_sauvegarde_{date.today()}.json",
            mime="application/json",
            help="Télécharge un fichier pour reprendre plus tard"
        )
    
    st.subheader("2. Paiements (TTC)")
    st.caption("Virements reçus AVANT le 26/06/2025")
    
    with st.form("ajout_paiement"):
        d_paiement = st.date_input("Date du virement", value=date(2024, 1, 1), format="DD/MM/YYYY")
        m_paiement = st.number_input("Montant Reçu TTC (€)", min_value=0.0, step=10.0)
        submit = st.form_submit_button("Ajouter")
        
        if submit and m_paiement > 0:
            if d_paiement > DATE_JUGEMENT:
                st.error("❌ Date postérieure au jugement (26/06/2025) !")
            else:
                st.session_state.paiements.append({"date": d_paiement, "montant": m_paiement})
                st.success("Ajouté !")
                st.rerun() # Refresh pour afficher dans le tableau

    if st.session_state.paiements:
        st.markdown("**Liste des virements :**")
        p_df = pd.DataFrame(st.session_state.paiements)
        st.dataframe(p_df.style.format({"montant": "{:.2f} €", "date": lambda t: t.strftime("%d/%m/%Y")}))
        if st.button("🗑️ Tout effacer"):
            st.session_state.paiements = []
            st.rerun()

# --- 3. CALCULS ET RÉSULTATS (ALGORITHME WATERFALL) ---
if loyer_ht > 0:
    # A. Fusion Chronologique
    echeances = generer_loyers_theoriques(loyer_ht)
    
    events = []
    # Compteur pour l'indemnité forfaitaire (nombre d'échéances générées)
    nombre_echeances = 0 
    
    for ech in echeances:
        events.append({
            "date": ech["date"], 
            "type": "LOYER", 
            "montant": ech["montant"], 
            "label": ech["label"]
        })
        nombre_echeances += 1
    
    for p in st.session_state.paiements:
        events.append({
            "date": p["date"], 
            "type": "PAIEMENT", 
            "montant": p["montant"], 
            "label": "Virement Reçu"
        })
    
    # Tri chronologique strict
    events.sort(key=lambda x: x["date"])

    # B. Le Moteur de Calcul
    solde_principal = 0.0  # Capital dû
    solde_interets = 0.0   # Intérêts cumulés
    last_date = events[0]["date"] if events else DATE_DEBUT_GRAPH
    
    data_detail = []

    for event in events:
        current_date = event["date"]
        
        # 1. Calcul des intérêts courus
        if current_date > last_date and solde_principal > 0:
            interets_periode = calculer_interets_ligne(solde_principal, last_date, current_date)
            solde_interets += interets_periode
        
        # 2. Traitement de l'événement
        montant_operation = event["montant"]
        
        if event["type"] == "LOYER":
            solde_principal += montant_operation
            data_detail.append({
                "Date": current_date,
                "Libellé": event["label"],
                "Opération": "LOYER",
                "Débit": montant_operation,
                "Crédit": 0,
                "Imput. Intérêts": 0,
                "Imput. Principal": 0,
                "Reste Principal": solde_principal,
                "Reste Intérêts": solde_interets
            })
            
        elif event["type"] == "PAIEMENT":
            # --- APPLICATION ART. 1343-1 ---
            reste_a_imputer = montant_operation
            
            # a) D'abord les intérêts
            part_interets = min(reste_a_imputer, solde_interets)
            solde_interets -= part_interets
            reste_a_imputer -= part_interets
            
            # b) Ensuite le capital
            part_principal = reste_a_imputer
            solde_principal -= part_principal
            
            data_detail.append({
                "Date": current_date,
                "Libellé": event["label"],
                "Opération": "PAIEMENT",
                "Débit": 0,
                "Crédit": montant_operation,
                "Imput. Intérêts": -part_interets,
                "Imput. Principal": -part_principal,
                "Reste Principal": solde_principal,
                "Reste Intérêts": solde_interets
            })
            
        last_date = current_date

    # C. Calcul final jusqu'au Jugement
    if last_date < DATE_JUGEMENT and solde_principal > 0:
        interets_finaux = calculer_interets_ligne(solde_principal, last_date, DATE_JUGEMENT)
        solde_interets += interets_finaux

    # D. Calcul Indemnité Forfaitaire (40€ par échéance)
    # Stratégie Expert : On applique 40€ par échéance théorique.
    # C'est une créance Chirographaire (Art L441-6 / D441-5).
    total_indemnites = nombre_echeances * INDEMNITE_FORFAITAIRE

    # Totaux
    principal_net = max(0.0, solde_principal)
    interets_net = max(0.0, solde_interets)
    
    # Le total inclut maintenant l'indemnité forfaitaire
    total_creance = principal_net + interets_net + total_indemnites
    
    df_final = pd.DataFrame(data_detail)

    # --- 4. AFFICHAGE RÉSULTATS (DROITE) ---
    with col_input2:
        # NOTE PEDAGOGIQUE
        st.info("""
        ℹ️ **Optimisation Juridique Active**
        1. **Imputation (Art 1343-1)** : Les paiements ont d'abord remboursé les intérêts.
        2. **Indemnité (Art D441-5)** : 40€ ajoutés par loyer (frais de recouvrement légaux).
        """)
        
        st.markdown("### 📊 Synthèse à Déclarer")
        
        # Affichage en 4 colonnes pour inclure l'indemnité
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Principal (Privilégié)", f"{principal_net:,.2f} €", help="Loyer TTC restant dû")
        c2.metric("Intérêts (Chiro.)", f"{interets_net:,.2f} €", help="Intérêts de retard cumulés")
        c3.metric("Indemnités 40€ (Chiro.)", f"{total_indemnites:,.2f} €", help=f"{nombre_echeances} échéances x 40€")
        c4.metric("TOTAL GÉNÉRAL", f"{total_creance:,.2f} €")

        st.markdown("### 📈 Évolution de la Dette")
        
        if not df_final.empty:
            df_graph = df_final[["Date", "Reste Principal", "Reste Intérêts"]].copy()
            df_graph.rename(columns={"Reste Principal": "Dette Principal (Bleu)", "Reste Intérêts": "Intérêts Cumulés (Rouge)"}, inplace=True)
            df_graph.loc[len(df_graph)] = [DATE_JUGEMENT, principal_net, interets_net]
            df_graph_melted = df_graph.melt('Date', var_name='Type', value_name='Montant (€)')

            base_chart = alt.Chart(df_graph_melted).mark_line(strokeWidth=3, interpolate='step-after').encode(
                x=alt.X('Date', axis=alt.Axis(format='%d/%m/%Y')),
                y=alt.Y('Montant (€)'),
                color=alt.Color('Type', scale=alt.Scale(domain=['Dette Principal (Bleu)', 'Intérêts Cumulés (Rouge)'], range=['#1f77b4', '#d62728'])),
                tooltip=['Date', 'Type', 'Montant (€)']
            )
            
            jugement_df = pd.DataFrame({'Date': [pd.to_datetime(DATE_JUGEMENT)], 'Label': [' JUGEMENT RJ']})
            vline = alt.Chart(jugement_df).mark_rule(color='black', strokeDash=[5, 5]).encode(x='Date')
            
            st.altair_chart((base_chart + vline).interactive(), use_container_width=True)
        
        with st.expander("Voir le détail ligne par ligne"):
            if not df_final.empty:
                st.dataframe(df_final.style.format({
                    "Débit": "{:.2f}", "Crédit": "{:.2f}", 
                    "Imput. Intérêts": "{:.2f}", "Imput. Principal": "{:.2f}",
                    "Reste Principal": "{:.2f}", "Reste Intérêts": "{:.2f}",
                    "Date": lambda t: t.strftime("%d/%m/%Y")
                }))

    # --- 5. GÉNÉRATION PDF OFFICIEL AMÉLIORÉ ---
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    
    # EN-TETE
    pdf.cell(0, 8, f"Arret des comptes au : 26/06/2025 (Jugement RJ)", 0, 1)
    pdf.cell(0, 8, f"Base Loyer Annuel : {loyer_ht:,.2f} EUR HT", 0, 1)
    
    # ENCART EXPLICATIF JURIDIQUE
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 8, "NOTICE DE CALCUL (Article 1343-1 du Code Civil)", 1, 1, 'L', fill=True)
    pdf.set_font("Arial", '', 9)
    note_text = ("Pour maximiser la creance privilegiee du bailleur, le calcul applique strictement la loi : "
                 "tout paiement partiel recu est impute prioritairement sur les interets de retard accumules, "
                 "et subsidiairement sur le capital (Loyer).")
    pdf.multi_cell(0, 5, note_text.encode('latin-1', 'replace').decode('latin-1'), 1)
    
    # TABLEAU SYNTHESE
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 10, "TOTAL GENERAL A DECLARER", 1)
    pdf.cell(50, 10, f"{total_creance:,.2f} EUR", 1, 1, 'R')
    
    pdf.ln(2)
    pdf.set_font("Arial", '', 10)
    pdf.cell(100, 8, "- Dont Principal (Privilege)", 1)
    pdf.cell(50, 8, f"{principal_net:,.2f} EUR", 1, 1, 'R')
    pdf.cell(100, 8, "- Dont Interets (Chirographaire)", 1)
    pdf.cell(50, 8, f"{interets_net:,.2f} EUR", 1, 1, 'R')
    # Ajout ligne Indemnité
    pdf.cell(100, 8, f"- Dont Indemnites Recouvrement (x{nombre_echeances})", 1)
    pdf.cell(50, 8, f"{total_indemnites:,.2f} EUR", 1, 1, 'R')

    # TABLEAU DES PAIEMENTS RECUS
    if st.session_state.paiements:
        pdf.ln(8)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 8, "RECAPITULATIF DES PAIEMENTS RECUS", 0, 1)
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(40, 7, "Date", 1)
        pdf.cell(40, 7, "Montant Recu", 1, 1)
        
        pdf.set_font("Arial", '', 9)
        total_p_pdf = 0
        for p in st.session_state.paiements:
            d_str = p['date'].strftime("%d/%m/%Y")
            pdf.cell(40, 6, d_str, 1)
            pdf.cell(40, 6, f"{p['montant']:.2f} EUR", 1, 1, 'R')
            total_p_pdf += p['montant']
        
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(40, 6, "TOTAL PERCU", 1)
        pdf.cell(40, 6, f"{total_p_pdf:.2f} EUR", 1, 1, 'R')

    # TABLEAU DETAIL CALCUL
    pdf.ln(8)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 8, "DETAIL DES IMPUTATIONS (HISTORIQUE)", 0, 1)
    
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(20, 8, "Date", 1)
    pdf.cell(55, 8, "Libelle", 1)
    pdf.cell(20, 8, "Debit", 1)
    pdf.cell(20, 8, "Credit", 1)
    pdf.cell(25, 8, "Imp. Princ.", 1)
    pdf.cell(25, 8, "Solde Princ.", 1)
    pdf.cell(25, 8, "Solde Int.", 1, 1)
    
    pdf.set_font("Arial", '', 8)
    for index, row in df_final.iterrows():
        d_str = row['Date'].strftime("%d/%m/%Y")
        libelle = str(row['Libellé']).encode('latin-1', 'replace').decode('latin-1')
        
        pdf.cell(20, 6, d_str, 1)
        pdf.cell(55, 6, libelle[:30], 1)
        pdf.cell(20, 6, f"{row['Débit']:.2f}", 1, 0, 'R')
        pdf.cell(20, 6, f"{row['Crédit']:.2f}", 1, 0, 'R')
        pdf.cell(25, 6, f"{row['Imput. Principal']:.2f}", 1, 0, 'R')
        pdf.cell(25, 6, f"{row['Reste Principal']:.2f}", 1, 0, 'R')
        pdf.cell(25, 6, f"{row['Reste Intérêts']:.2f}", 1, 1, 'R')

    # --- PIED DE PAGE : SIGNATURE & RESERVES ---
    pdf.ln(10)
    pdf.set_font("Arial", '', 10)
    
    # Check saut de page pour ne pas couper la signature
    if pdf.get_y() > 240:
        pdf.add_page()
        
    pdf.cell(0, 5, "Certifie sincere et veritable la presente creance,", 0, 1)
    pdf.cell(0, 5, "Arretee au 26 juin 2025 (Date du Jugement d'Ouverture).", 0, 1)
    
    pdf.ln(10)
    # Cadre de signature simple
    pdf.cell(100, 30, " Fait a : .....................................................", 0, 0) # Lieu
    pdf.cell(90, 30, " Signature du Creancier :", 0, 1) # Signature
    
    # Mention de réserve OBLIGATOIRE (Art L. 622-24)
    # On remonte un peu si nécessaire ou on écrit juste en dessous
    pdf.set_xy(10, pdf.get_y()) 
    pdf.ln(5)
    pdf.set_font("Arial", 'I', 8)
    reserve_txt = "IMPORTANT : La presente declaration est faite sous reserve des loyers et charges a echoir posterieurement au jugement d'ouverture (conformement a l'Art. L. 622-24 du Code de commerce)."
    pdf.multi_cell(0, 5, reserve_txt.encode('latin-1', 'replace').decode('latin-1'), 0, 'C')

    # DOWNLOAD
    pdf_content = pdf.output(dest='S').encode('latin-1')
    
    st.download_button(
        label="📄 TÉLÉCHARGER DÉCLARATION OFFICIELLE (PDF)",
        data=pdf_content,
        file_name="declaration_creance_albion_complet.pdf",
        mime="application/pdf"
    )

else:
    st.info("👈 Pour commencer, entrez le Loyer Annuel HT dans la colonne de gauche.")
