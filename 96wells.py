import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import re
import requests
import json

# --- 1. INITIALIZATION & CONNECTION ---
st.set_page_config(layout="wide", page_title="96-Well Lab Plate")

# Use the bridge URL you generated
BRIDGE_URL = "https://script.google.com/macros/s/AKfycbwEW5AT5W8t2Pqmrae5NkzLEbpEBJkwyOi9rMu4KLSimOGrjzaidVGP6_sbZewMEIrI/exec"

conn = st.connection("gsheets", type=GSheetsConnection)

# Initialize Essential States
for key, val in {
    "scanned_plate": None, 
    "sb_ver": 0, 
    "up_ver": 0, 
    "selected_well": None,
    "has_just_saved": False
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- 2. DATA ROUTING ---
# We can still READ using the connection (this is faster and allowed)
reg_df = conn.read(ttl=0).astype(str)
url_barcode = st.query_params.get("barcode")
url_plate_id = None

if url_barcode and not reg_df.empty:
    match = reg_df[reg_df['barcode'] == str(url_barcode)]
    if not match.empty:
        st.session_state.scanned_plate = match['plate_name'].values[0]
        url_plate_id = st.session_state.scanned_plate

# --- 3. HELPER FUNCTIONS ---
def normalize_well_id(well_id):
    """Standardizes well names (e.g., A01 -> A1)."""
    return re.sub(r'([A-H])0(\d)', r'\1\2', str(well_id).strip().upper())

def convert_10x10_to_96(well_id):
    """Maps custom 10x10 vendor grid to standard 96-well grid."""
    match = re.match(r"([A-J])(\d+)", str(well_id).strip().upper().replace(" ", ""))
    if not match: return well_id
    row_let, col_num = match.groups()
    abs_pos = ((ord(row_let) - ord('A')) * 10) + int(col_num)
    if abs_pos <= 96:
        new_row = chr(ord('A') + (abs_pos - 1) // 12)
        new_col = ((abs_pos - 1) % 12) + 1
        return f"{new_row}{new_col}"
    return "EMPTY"

def save_via_bridge(df_to_save, barcode, plate_name):
    """Sends all plate data in one single batch request."""
    try:
        # 1. Prepare the entire block of data as a list of lists
        # We add the plate_name to every row here
        all_rows = []
        for _, row in df_to_save.iterrows():
            all_rows.append([
                str(row['Well']), 
                str(row['Product_Name']), 
                str(row['SMILES']), 
                str(plate_name)
            ])
        
        # 2. Send the whole 'package' at once
        payload = {"all_rows": all_rows}
        resp = requests.post(BRIDGE_URL, json=payload, timeout=10) # Added timeout
        
        if "Success" in resp.text:
            return True
        else:
            st.error(f"Server said: {resp.text}")
            return False
            
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return False
        
# --- 4. STYLING ---
st.markdown("""
    <style>
    [data-testid="stMain"] button[kind="primary"], [data-testid="stMain"] button[kind="secondary"] {
        display: flex !important; align-items: center !important; justify-content: center !important;
        border-radius: 50% !important; width: 40px !important; height: 40px !important;
        padding: 0px !important; margin: auto !important;
    }
    button[kind="primary"] { background-color: #C1E1C1 !important; color: #2E7D32 !important; border: 1px solid #A5D6A7 !important; }
    .well-id-header { font-size: 26px; font-weight: 800; color: #4A90E2; }
    .label-text { font-weight: bold; text-align: center; color: #bbb; font-size: 14px; }
    </style>
    """, unsafe_allow_html=True)

# --- 5. SIDEBAR: DATA CONTROLS ---
with st.sidebar:
    st.header("1. Data Setup")
    saved_plates = reg_df['plate_name'].unique().tolist() if not reg_df.empty else []

    # Dropdown logic
    start_idx = 0
    if st.session_state.scanned_plate in saved_plates:
        start_idx = saved_plates.index(st.session_state.scanned_plate) + 1
        st.session_state.scanned_plate = None 
    elif url_plate_id in saved_plates:
        start_idx = saved_plates.index(url_plate_id) + 1

    selected_mode = st.selectbox(
        "📂 Load a Saved Plate", 
        options=["-- New Upload --"] + saved_plates,
        index=start_idx,
        key=f"selector_{st.session_state.sb_ver}"
    )

    df, id_col, name_col, smiles_col = pd.DataFrame(), None, None, None
    is_viewing_saved = selected_mode != "-- New Upload --"

    if is_viewing_saved:
        # We read by sheet name 'Plates'
        all_plates = conn.read(worksheet="Plates", ttl=0)
        df = all_plates[all_plates['plate_name'] == selected_mode].copy()
        id_col, name_col, smiles_col = 'Well', 'Product_Name', 'SMILES'
        st.success(f"📍 Viewing: {selected_mode}")
    else:
        up_file = st.file_uploader("Upload Excel/CSV", type=['xlsx', 'csv'], key=f"up_{st.session_state.up_ver}")
        if up_file:
            df = pd.read_excel(up_file) if up_file.name.endswith('xlsx') else pd.read_csv(up_file)
            cols = df.columns.tolist()
            id_col = st.selectbox("Well ID Column", cols)
            name_col = st.selectbox("Product Name Column", cols)
            smiles_col = st.selectbox("SMILES Column", cols)
            
            df[id_col] = df[id_col].apply(convert_10x10_to_96)
            df = df[df[id_col] != "EMPTY"]

    if not df.empty and id_col:
        df[id_col] = df[id_col].apply(normalize_well_id)

    # --- UPDATED STORAGE LOGIC ---
    if not df.empty and not is_viewing_saved:
        st.divider()
        if not st.session_state.has_just_saved:
            st.subheader("2. Permanent Storage")
            barcode = st.text_input("Barcode (8 Digits)", max_chars=8)
            save_id = st.text_input("Custom Plate Name", value="PLATE_001")
            
            can_save = (len(barcode) == 8 and barcode.isdigit() and 
                        save_id not in saved_plates and 
                        str(barcode) not in reg_df['barcode'].values)

            if st.button("💾 Save to Cloud", use_container_width=True, disabled=not can_save):
                save_df = df[[id_col, name_col, smiles_col]].copy()
                save_df.columns = ['Well', 'Product_Name', 'SMILES']
                
                with st.spinner("Pushing to Sheets via Bridge..."):
                    if save_via_bridge(save_df, barcode, save_id):
                        st.session_state.has_just_saved = True
                        st.session_state.last_saved_id = barcode
                        st.rerun()
        else:
            st.success(f"✅ Saved! Barcode: {st.session_state.last_saved_id}")
            if st.button("Upload Next Plate"):
                st.session_state.has_just_saved = False
                st.session_state.up_ver += 1
                st.rerun()

    # --- SCANNER FORM ---
    st.divider()
    with st.form("scan_form", clear_on_submit=True):
        scan_input = st.text_input("🔍 Scan Barcode")
        if st.form_submit_button("Search", use_container_width=True) and scan_input:
            if str(scan_input) in reg_df['barcode'].values:
                st.query_params["barcode"] = scan_input
                st.session_state.sb_ver += 1
                st.rerun()
            else:
                st.error("Barcode not found.")

# --- 6. MAIN INTERFACE ---
plate_col, info_col = st.columns([1.7, 1])

with plate_col:
    st.subheader("96-Well Plate View")
    rows, cols_range = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'], range(1, 13)
    
    grid_header = st.columns([0.6] + [1]*12)
    for i in cols_range: grid_header[i].markdown(f'<p class="label-text">{i}</p>', unsafe_allow_html=True)

    for r in rows:
        row_ui = st.columns([0.6] + [1]*12)
        row_ui[0].markdown(f'<p class="label-text" style="margin-top:10px">{r}</p>', unsafe_allow_html=True)
        for c in cols_range:
            w_id = f"{r}{c}"
            has_data = w_id in df[id_col].values if not df.empty else False
            if row_ui[c].button(w_id, key=w_id, type="primary" if has_data else "secondary"):
                st.session_state.selected_well = w_id

with info_col:
    sel = st.session_state.selected_well
    if sel:
        st.markdown(f'<div class="well-id-header">Well {sel}</div>', unsafe_allow_html=True)
        well_data = df[df[id_col] == sel] if not df.empty else pd.DataFrame()
        
        if not well_data.empty:
            st.markdown(f"### {well_data[name_col].values[0]}")
            smiles = well_data[smiles_col].values[0]
            if pd.isna(smiles) or not str(smiles).strip():
                st.caption("No SMILES data available.")
            else:
                st.code(smiles, language=None)
        else:
            st.write("No sample in this well.")
