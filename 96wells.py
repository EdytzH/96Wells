import streamlit as st
import pandas as pd
import os

# --- TOP OF SCRIPT LOGIC ---
if "scanned_plate" not in st.session_state:
    st.session_state.scanned_plate = None

# Check for a physical scan before drawing the UI
query_params = st.query_params
url_barcode = query_params.get("barcode")
registry_path = "saved_plates/barcode_registry.csv"

if url_barcode and os.path.exists(registry_path):
    reg_df = pd.read_csv(registry_path)
    match = reg_df[reg_df['barcode'].astype(str) == str(url_barcode)]
    if not match.empty:
        st.session_state.scanned_plate = match['plate_name'].values[0]

# --- NEW: STORAGE ENGINE SETUP ---
if not os.path.exists("saved_plates"):
    os.makedirs("saved_plates")

# --- 1. HANDLE BARCODE/URL LINKING ---
query_params = st.query_params
url_plate_id = query_params.get("plate")
url_barcode = query_params.get("barcode")

# Registry path to bridge Barcode -> Plate Name
registry_path = "saved_plates/barcode_registry.csv"

# If a barcode is provided, find the associated plate name
if url_barcode and os.path.exists(registry_path):
    reg_df = pd.read_csv(registry_path)
    match = reg_df[reg_df['barcode'].astype(str) == str(url_barcode)]
    if not match.empty:
        url_plate_id = match['plate_name'].values[0]

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
    st.divider()
    st.subheader("Admin: Download Data")
    if os.path.exists("saved_plates"):
        files = os.listdir("saved_plates")
        for f in files:
            with open(f"saved_plates/{f}", "rb") as file:
                st.download_button(label=f"💾 Download {f}", data=file, file_name=f)   
    st.header("1. Data Setup")

    if "sb_ver" not in st.session_state:
        st.session_state.sb_ver = 0
    
   # 1. Fetch saved plates
    # We use a list comprehension to get all CSVs EXCEPT the barcode_registry
    if not os.path.exists("saved_plates"):
        os.makedirs("saved_plates")
        
    all_csvs = [f for f in os.listdir("saved_plates") if f.endswith(".csv")]
    
    # Filter: Keep everything EXCEPT the registry
    saved_files = [f.replace(".csv", "") for f in all_csvs if f != "barcode_registry.csv"]


    start_index = 0
    
    # ADDED: If we are in "upload" mode, force index 0
    if st.session_state.get("view_mode") == "upload":
        start_index = 0
    # Priority 1: Was a barcode just scanned?
    elif st.session_state.scanned_plate in saved_files:
        start_index = saved_files.index(st.session_state.scanned_plate) + 1
        st.session_state.scanned_plate = None 
    # Priority 2: Is there a plate ID in the URL?
    elif url_plate_id and url_plate_id in saved_files:
        start_index = saved_files.index(url_plate_id) + 1

    selected_saved = st.selectbox(
        "📂 Load a Saved Plate", 
        options=["-- New Upload --"] + saved_files,
        index=start_index,
        # This key changes when you click 'Upload New', forcing a reset
        key=f"sidebar_selector_{st.session_state.sb_ver}" 
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
        
        # --- BARCODE LINK VIEW REMOVED ---
        
        st.write("")
        if st.button("🗑️ Delete Plate", key="del_btn", type="secondary", use_container_width=True):
            # 1. Define paths
            file_to_delete = f"saved_plates/{selected_saved}.csv"
            
            # 2. Delete the actual Plate CSV
            if os.path.exists(file_to_delete):
                os.remove(file_to_delete)
            
            # 3. Scrub the Barcode Registry
            if os.path.exists(registry_path):
                reg_df = pd.read_csv(registry_path)
                
                # Use a very strict filter to remove the plate
                # We strip spaces just in case 'PLATE_001 ' was saved instead of 'PLATE_001'
                reg_df['plate_name'] = reg_df['plate_name'].astype(str).str.strip()
                target_name = str(selected_saved).strip()
                
                # Keep only rows that DO NOT match the deleted plate
                new_reg_df = reg_df[reg_df['plate_name'] != target_name]
                
                # Save the cleaned registry back to disk
                new_reg_df.to_csv(registry_path, index=False)
            
            # 4. Clear the UI and the URL
            st.query_params.clear()
            # Bump the sidebar version to force the dropdown to reset to "-- New Upload --"
            if "sb_ver" in st.session_state:
                st.session_state.sb_ver += 1
            
            st.rerun()
            
        if st.button("➕ Upload New Plate", key="new_up_btn", use_container_width=True):
            st.query_params.clear()
            
            # --- ADD THIS LINE TO HIDE THE OLD SUCCESS BUBBLES ---
            st.session_state.has_just_saved = False
            
            # Bumping the version resets the dropdown memory
            if "sb_ver" in st.session_state:
                st.session_state.sb_ver += 1
            
            st.rerun()

# --- MODE B: NEW UPLOAD ---
    else:
        if "up_ver" not in st.session_state: st.session_state.up_ver = 0
        
        uploaded_file = st.file_uploader("Upload Excel/CSV", type=['xlsx', 'csv'], key=f"file_uploader_{st.session_state.up_ver}")
        
        if uploaded_file:
            # --- NEW: RESET STATE IF A NEW FILE IS DETECTED ---
            # If the filename is different from the last one we processed, clear the "Success" view
            if st.session_state.get("last_uploaded_name") != uploaded_file.name:
                st.session_state.has_just_saved = False
                st.session_state.selected_well = None
                st.session_state.last_uploaded_name = uploaded_file.name
                # Note: We don't st.rerun here to avoid upload loops

            try:
                # Load the data
                df = pd.read_excel(uploaded_file, engine='openpyxl') if uploaded_file.name.endswith('xlsx') else pd.read_csv(uploaded_file)
                cols = df.columns.tolist()
                
                # Column Selectors
                id_col = st.selectbox("Well ID Column", options=cols, key="id_sel")
                name_col = st.selectbox("Product Name Column", options=cols, key="name_sel")
                smiles_col = st.selectbox("SMILES Column", options=cols, key="smiles_sel")
                
            except Exception as e:
                st.error(f"Error loading file: {e}")
                st.stop()

  # --- 3. STORAGE LOGIC (Inside Sidebar) ---
    if not df.empty and id_col and name_col and smiles_col:
        
        # --- CRITICAL FIX: Only run the 10x10 conversion for NEW uploads ---
        if not is_viewing_saved:
            def convert_10x10_to_96(well_id):
                import re
                # Clean input
                match = re.match(r"([A-J])(\d+)", str(well_id).strip().upper().replace(" ", ""))
                if not match: return well_id
                
                row_let, col_num = match.groups()
                r_idx = ord(row_let) - ord('A') 
                c_idx = int(col_num)           
                
                # Absolute position in 10x10 grid (1 to 100)
                abs_pos = (r_idx * 10) + c_idx 
                
                if abs_pos <= 96:
                    new_row_idx = (abs_pos - 1) // 12
                    new_row_let = chr(ord('A') + new_row_idx)
                    new_col_num = ((abs_pos - 1) % 12) + 1
                    return f"{new_row_let}{new_col_num}"
                return "EMPTY"

            # Apply conversion
            df[id_col] = df[id_col].apply(convert_10x10_to_96)
            # Remove J7-J10
            df = df[df[id_col] != "EMPTY"]
        

        # Only run the regex if the column exists in the current data
        if id_col in df.columns:
            df[id_col] = df[id_col].astype(str).str.replace(r'([A-H])0(\d)', r'\1\2', regex=True)
        
       # --- SAVE UI (Only shows if it's a new upload) ---
        if not is_viewing_saved:
            st.divider()
            
            if not st.session_state.get("has_just_saved", False):
                st.subheader("2. Permanent Storage")
                
                # New Dual Input
                barcode = st.text_input("Physical Barcode (8 Digits)", max_chars=8, key="bc_input")
                save_id = st.text_input("Custom Plate Name", value="PLATE_001", key="save_id_input")
                
                # Logic for duplicates/validation
                is_valid_bc = len(barcode) == 8 and barcode.isdigit()
                file_exists = os.path.exists(f"saved_plates/{save_id}.csv")
                
                bc_exists = False
                if os.path.exists(registry_path):
                    reg_df = pd.read_csv(registry_path)
                    bc_exists = str(barcode) in reg_df['barcode'].astype(str).values

                if barcode and not is_valid_bc: st.warning("⚠️ Barcode must be 8 digits.")
                if bc_exists: st.error("⚠️ Barcode already linked to a plate.")
                if file_exists: st.error(f"⚠️ Name '{save_id}' already exists.")

                # Button is only clickable if barcode is valid and nothing is a duplicate
                can_save = is_valid_bc and not bc_exists and not file_exists and save_id.strip()

                if st.button("💾 Save & Link Barcode", key="save_btn", use_container_width=True, disabled=not can_save):
                    # 1. Save the Plate CSV
                    save_df = df[[id_col, name_col, smiles_col]].copy()
                    save_df.columns = ['Well', 'Product_Name', 'SMILES']
                    save_df.to_csv(f"saved_plates/{save_id}.csv", index=False)
                    
                    # 2. Save to Registry
                    new_entry = pd.DataFrame([[barcode, save_id]], columns=['barcode', 'plate_name'])
                    new_entry.to_csv(registry_path, mode='a', header=not os.path.exists(registry_path), index=False)
                    
                    st.session_state.has_just_saved = True
                    st.session_state.last_saved_id = barcode # Link via Barcode
                    st.session_state.last_saved_name = save_id
                    st.rerun()
            else:
                # SUCCESS VIEW
                import urllib.parse
                s_bc = st.session_state.last_saved_id
                unique_url = f"96wells.streamlit.app/?barcode={urllib.parse.quote(str(s_bc))}"
                
                st.success(f"✅ {st.session_state.last_saved_name} Linked to {s_bc}!")
                st.info(f"{unique_url}")
                
                if st.button("Start Next Upload", key="reset_after_save", use_container_width=True):
                    st.session_state.has_just_saved = False
                    st.session_state.up_ver += 1
                    st.rerun()

    st.subheader("🔍 Scan Plate")
    
    with st.form("barcode_form", clear_on_submit=True):
        scan_val = st.text_input("Click & Scan Barcode")
        submitted = st.form_submit_button("Submit Scan", use_container_width=True)
        
        if submitted and scan_val:
            # 1. Check if registry exists and barcode is inside
            found = False
            if os.path.exists(registry_path):
                reg_df = pd.read_csv(registry_path)
                if str(scan_val) in reg_df['barcode'].astype(str).values:
                    found = True
            
            if found:
                # SUCCESS: Update URL and reset dropdown
                st.query_params["barcode"] = scan_val
                if "sb_ver" in st.session_state:
                    st.session_state.sb_ver += 1
                st.session_state.scan_error = None # Clear any old errors
                st.rerun()
            else:
                # FAILURE: Set error message
                st.session_state.scan_error = f"❌ Barcode '{scan_val}' not found in registry."
                st.rerun()

    # Display the error message if it exists
    if st.session_state.get("scan_error"):
        st.error(st.session_state.scan_error)
        # Optional: Clear the error after it's shown once
        st.session_state.scan_error = None



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
            has_data = well_id in df[search_col].values if not df.empty and search_col in df.columns else False
            
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
