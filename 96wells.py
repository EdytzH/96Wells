import streamlit as st
import pandas as pd
import os

# --- NEW: STORAGE ENGINE SETUP ---
if not os.path.exists("saved_plates"):
    os.makedirs("saved_plates")

# --- 1. HANDLE BARCODE/URL LINKING ---
query_params = st.query_params
url_barcode = query_params.get("barcode")
url_plate_id = query_params.get("plate")  # Keep original support too

# Lookup Barcode in Registry
registry_path = "saved_plates/barcode_registry.csv"
if url_barcode and os.path.exists(registry_path):
    reg_df = pd.read_csv(registry_path)
    # Match barcode to find the custom plate name
    match = reg_df[reg_df['barcode'].astype(str) == str(url_barcode)]
    if not match.empty:
        url_plate_id = match['plate_name'].values[0]

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
# --- SIDEBAR SETUP ---
with st.sidebar:
    st.header("1. Data Setup")
    
    # 1. Fetch saved plates
    saved_files = [f.replace(".csv", "") for f in os.listdir("saved_plates") if f.endswith(".csv")]

    # 2. Setup the Dropdown (Defined once to prevent DuplicateKeyError)
    # If a URL is present, we pre-select that plate
    start_index = 0
    if url_plate_id and url_plate_id in saved_files and st.session_state.get("view_mode") != "upload":
        start_index = saved_files.index(url_plate_id) + 1

    selected_saved = st.selectbox(
        "📂 Load a Saved Plate", 
        options=["-- New Upload --"] + saved_files,
        index=start_index,
        key="sidebar_selector"
    )

    df = pd.DataFrame()
    id_col, name_col, smiles_col = None, None, None
    is_viewing_saved = False

    # --- MODE A: VIEWING A SAVED PLATE ---
    if selected_saved != "-- New Upload --":
        is_viewing_saved = True
        df = pd.read_csv(f"saved_plates/{selected_saved}.csv")
        id_col, name_col, smiles_col = 'Well', 'Product_Name', 'SMILES'
        
        st.success(f"📍 Viewing: {selected_saved}")
        
        # Link Display for existing plates
        import urllib.parse
        unique_url = f"96wells.streamlit.app/?plate={urllib.parse.quote(selected_saved)}"
        st.markdown(f"""
            <div style="border: 1px solid var(--text-color); border-radius: 8px; padding: 12px; margin-top: 10px; opacity: 0.8;">
                <p style="color: #4A90E2; font-size: 11px; font-weight: 700; text-transform: uppercase; margin: 0 0 5px 0;">🔗 Link to Plate</p>
                <code style="color: var(--text-color); font-family: 'Courier New', monospace; font-size: 13px; word-break: break-all; display: block;">{unique_url}</code>
            </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        if st.button("🗑️ Delete Plate", key="del_btn", type="secondary", use_container_width=True):
            os.remove(f"saved_plates/{selected_saved}.csv")
            st.query_params.clear()
            st.rerun()
            
        if st.button("➕ Upload New Plate", key="new_up_btn", use_container_width=True):
            st.query_params.clear()
            st.session_state.view_mode = "upload"
            st.session_state.sidebar_selector = "-- New Upload --"
            st.rerun()

    # --- MODE B: NEW UPLOAD ---
    else:
        if "up_ver" not in st.session_state: st.session_state.up_ver = 0
        uploaded_file = st.file_uploader("Upload Excel/CSV", type=['xlsx', 'csv'], key=f"file_uploader_{st.session_state.up_ver}")
        
        if uploaded_file:
            try:
                df = pd.read_excel(uploaded_file, engine='openpyxl') if uploaded_file.name.endswith('xlsx') else pd.read_csv(uploaded_file)
                cols = df.columns.tolist()
                id_col = st.selectbox("Well ID Column", options=cols, key="id_sel")
                name_col = st.selectbox("Product Name Column", options=cols, key="name_sel")
                smiles_col = st.selectbox("SMILES Column", options=cols, key="smiles_sel")
            except ImportError:
                st.error("Please add `openpyxl` to requirements.txt")
                st.stop()

  # --- 3. STORAGE LOGIC (Inside Sidebar) ---
    if not df.empty and id_col and name_col and smiles_col:
        
        if not is_viewing_saved:
            def convert_10x10_to_96(well_id):
                import re
                match = re.match(r"([A-J])(\d+)", str(well_id).strip().upper().replace(" ", ""))
                if not match: return well_id
                row_let, col_num = match.groups()
                r_idx = ord(row_let) - ord('A') 
                c_idx = int(col_num)           
                abs_pos = (r_idx * 10) + c_idx 
                if abs_pos <= 96:
                    new_row_idx = (abs_pos - 1) // 12
                    new_row_let = chr(ord('A') + new_row_idx)
                    new_col_num = ((abs_pos - 1) % 12) + 1
                    return f"{new_row_let}{new_col_num}"
                return "EMPTY"

            df[id_col] = df[id_col].apply(convert_10x10_to_96)
            df = df[df[id_col] != "EMPTY"]
        
        df[id_col] = df[id_col].astype(str).str.replace(r'([A-H])0(\d)', r'\1\2', regex=True)
        
        if not is_viewing_saved:
            st.divider()
            
            if not st.session_state.get("has_just_saved", False):
                st.subheader("2. Permanent Storage")
                
                # TWO INPUTS: Barcode (for the link) and Name (for the file)
                barcode = st.text_input("Physical Barcode (8 Digits)", max_chars=8, key="bc_input")
                plate_name = st.text_input("Custom Plate Name", value="PLATE_001", key="save_name_input")
                
                # VALIDATION
                is_valid_bc = len(barcode) == 8 and barcode.isdigit()
                name_exists = os.path.exists(f"saved_plates/{plate_name}.csv")
                
                # Check if Barcode is already in registry
                bc_exists = False
                if os.path.exists(registry_path):
                    reg_df = pd.read_csv(registry_path)
                    bc_exists = str(barcode) in reg_df['barcode'].astype(str).values

                if barcode and not is_valid_bc: st.warning("⚠️ Barcode must be 8 digits.")
                if bc_exists: st.error("⚠️ Barcode already assigned to another plate.")
                if name_exists: st.error("⚠️ Plate Name already exists.")
                
                save_disabled = not is_valid_bc or bc_exists or name_exists or not plate_name.strip()
                
                if st.button("💾 Save & Link Barcode", key="save_btn", use_container_width=True, disabled=save_disabled):
                    # 1. Save Plate CSV
                    save_df = df[[id_col, name_col, smiles_col]].copy()
                    save_df.columns = ['Well', 'Product_Name', 'SMILES']
                    save_df.to_csv(f"saved_plates/{plate_name}.csv", index=False)
                    
                    # 2. Update Registry
                    new_entry = pd.DataFrame([[barcode, plate_name]], columns=['barcode', 'plate_name'])
                    if os.path.exists(registry_path):
                        new_entry.to_csv(registry_path, mode='a', header=False, index=False)
                    else:
                        new_entry.to_csv(registry_path, index=False)
                    
                    st.session_state.has_just_saved = True
                    st.session_state.last_saved_bc = barcode
                    st.session_state.last_saved_name = plate_name
                    st.rerun()
            else:
                # SUCCESS VIEW - Uses the Barcode in the URL
                import urllib.parse
                s_bc = st.session_state.last_saved_bc
                s_name = st.session_state.last_saved_name
                unique_url = f"96wells.streamlit.app/?barcode={urllib.parse.quote(str(s_bc))}"
                
                st.success(f"✅ {s_name} Linked to {s_bc}!")
                st.markdown(f"""
                    <div style="border: 1px solid var(--text-color); border-radius: 8px; padding: 12px; margin-top: 10px; opacity: 0.8;">
                        <p style="color: #4A90E2; font-size: 11px; font-weight: 700; text-transform: uppercase; margin: 0 0 5px 0;">🔗 Barcode Link</p>
                        <code style="color: var(--text-color); font-size: 13px; word-break: break-all;">{unique_url}</code>
                    </div>
                """, unsafe_allow_html=True)
                
                if st.button("Start Next Upload", key="reset_after_save", use_container_width=True):
                    st.session_state.has_just_saved = False
                    st.session_state.up_ver += 1
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
