import streamlit as st
import pandas as pd
import os

# --- NEW: STORAGE ENGINE SETUP ---
if not os.path.exists("saved_plates"):
    os.makedirs("saved_plates")

# --- 1. HANDLE BARCODE/URL LINKING ---
query_params = st.query_params
url_plate_id = query_params.get("plate")

if "cloud_df" not in st.session_state:
    st.session_state.cloud_df = None

st.set_page_config(layout="wide", page_title="96-Well Lab Plate")

# --- CSS (UNCHANGED) ---
st.markdown("""
    <style>
    [data-testid="stMain"] button[kind="primary"], 
    [data-testid="stMain"] button[kind="secondary"] {
        display: flex !important; align-items: center !important; justify-content: center !important;
        border-radius: 50% !important; width: 40px !important; height: 40px !important;
        padding: 0px !important; margin: auto !important; line-height: 40px !important;
    }
    [data-testid="stSidebar"] button { border-radius: 4px !important; width: auto !important; height: auto !important; padding: 8px 16px !important; }
    button[kind="primary"] { background-color: #C1E1C1 !important; color: #2E7D32 !important; border: 1px solid #A5D6A7 !important; }
    .well-id-header { font-size: 26px; font-weight: 800; color: #4A90E2; margin-bottom: 5px; }
    .label-text { font-weight: bold; text-align: center; color: #bbb; margin: 0; font-size: 14px; }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR SETUP ---
with st.sidebar:
    st.header("1. Data Setup")
    
    # Check for saved plates first
    saved_files = [f.replace(".csv", "") for f in os.listdir("saved_plates") if f.endswith(".csv")]
    selected_saved = st.selectbox("📂 Load a Saved Plate", options=["-- New Upload --"] + saved_files)

    df = pd.DataFrame()
    id_col, name_col, smiles_col = None, None, None

    # LOGIC: Load from Save OR URL OR Upload
    if url_plate_id and url_plate_id in saved_files:
        st.success(f"Linked to Plate: {url_plate_id}")
        df = pd.read_csv(f"saved_plates/{url_plate_id}.csv")
        # Automatically set columns if they exist in the saved file
        id_col, name_col, smiles_col = 'Well', 'Product_Name', 'SMILES' 
    elif selected_saved != "-- New Upload --":
        df = pd.read_csv(f"saved_plates/{selected_saved}.csv")
        id_col, name_col, smiles_col = 'Well', 'Product_Name', 'SMILES'
    else:
        uploaded_file = st.file_uploader("Upload Excel/CSV", type=['xlsx', 'csv'])
        if uploaded_file:
            df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('xlsx') else pd.read_csv(uploaded_file)
            cols = df.columns.tolist()
            id_col = st.selectbox("Well ID Column", options=cols)
            name_col = st.selectbox("Product Name Column", options=cols)
            smiles_col = st.selectbox("SMILES Column", options=cols)

    # Clean and Standardize Data
    if not df.empty and id_col and name_col and smiles_col:
        df[id_col] = df[id_col].astype(str).str.split('.').str[0].str.strip().str.upper().str.replace(r'([A-H])0(\d)', r'\1\2', regex=True)
        
        # --- NEW: SAVE BUTTON ---
        st.divider()
        st.subheader("2. Permanent Storage")
        save_id = st.text_input("Barcode / Plate ID", value=url_plate_id if url_plate_id else "PLATE_001")
        
        if st.button("💾 Save Plate to App"):
            # We standardize the column names for the 'Save' file so they auto-load correctly next time
            save_df = df[[id_col, name_col, smiles_col]].copy()
            save_df.columns = ['Well', 'Product_Name', 'SMILES']
            save_df.to_csv(f"saved_plates/{save_id}.csv", index=False)
            st.success(f"Saved! You can now access this as '{save_id}'")
            st.rerun()

# --- MAIN INTERFACE (UNCHANGED) ---
plate_col, info_col = st.columns([1.7, 1])

with plate_col:
    st.subheader("96-Well Plate")
    rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    h_cols = st.columns([0.6] + [1]*12)
    for i in range(1, 13): h_cols[i].markdown(f'<p class="label-text">{i}</p>', unsafe_allow_html=True)

    for r in rows:
        row_cells = st.columns([0.6] + [1]*12)
        row_cells[0].markdown(f'<p class="label-text" style="padding-top:10px">{r}</p>', unsafe_allow_html=True)
        for c in range(1, 13):
            well_id = f"{r}{c}"
            # Use 'Well' if loaded from save, else use id_col
            search_col = 'Well' if 'Well' in df.columns else id_col
            has_data = well_id in df[search_col].values if not df.empty and search_col else False
            
            if row_cells[c].button(well_id, key=well_id, type="primary" if has_data else "secondary"):
                st.session_state.selected_well = well_id

with info_col:
    selected = st.session_state.get('selected_well')
    if selected:
        search_col = 'Well' if 'Well' in df.columns else id_col
        disp_name = 'Product_Name' if 'Product_Name' in df.columns else name_col
        disp_smiles = 'SMILES' if 'SMILES' in df.columns else smiles_col
        
        well_data = df[df[search_col] == selected] if not df.empty and search_col else pd.DataFrame()
        
        st.markdown(f'<div style="margin-left: 40px;"><div class="well-id-header">Well {selected}</div>', unsafe_allow_html=True)
        
        if not well_data.empty:
            product_val = well_data[disp_name].values[0]
            st.markdown(f'<div style="color: #2E7D32; font-size: 22px; font-weight: 600; margin-top: 5px; margin-left: 40px;">{product_val}</div>', unsafe_allow_html=True)

            smiles_val = well_data[disp_smiles].values[0]
            if pd.isna(smiles_val) or str(smiles_val).strip().lower() in ["", "nan"]:
                st.markdown(f'<div style="color: #FFB6C1; font-size: 14px; font-style: italic; margin-top: 10px; margin-left: 40px;">No SMILE found</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="color: #FFB6C1; font-size: 16px; font-family: monospace; font-weight: 500; margin-top: 10px; margin-left: 40px; word-break: break-all;">{smiles_val}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="margin-left: 40px; color: #999;">No data assigned.</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
