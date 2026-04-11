import streamlit as st
import pandas as pd
import re
import urllib.parse
from supabase import create_client, Client

# --- 1. SUPABASE CONNECTION ---
# Ensure these match your .streamlit/secrets.toml exactly
url = st.secrets["supabase"]["url"]
key = st.secrets["supabase"]["key"]
supabase: Client = create_client(url, key)

# --- 2. INITIALIZATION & SESSION STATE ---
if "scanned_plate" not in st.session_state:
    st.session_state.scanned_plate = None
if "sb_ver" not in st.session_state:
    st.session_state.sb_ver = 0
if "up_ver" not in st.session_state:
    st.session_state.up_ver = 0
if "selected_well" not in st.session_state:
    st.session_state.selected_well = None

# --- 3. URL & BARCODE ROUTING ---
url_barcode = st.query_params.get("barcode")
url_plate_id = None

if url_barcode:
    # Query Supabase for the barcode bridge
    res = supabase.table("barcode_registry").select("plate_name").eq("barcode", str(url_barcode)).execute()
    if res.data:
        st.session_state.scanned_plate = res.data[0]['plate_name']
        url_plate_id = st.session_state.scanned_plate

# --- 4. UI CONFIG & CSS ---
st.set_page_config(layout="wide", page_title="96-Well Lab Plate")
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

# --- 5. SIDEBAR: DATA CONTROLS ---
with st.sidebar:
    st.header("1. Data Setup")
    
    # Fetch all unique plate names from Supabase
    plates_res = supabase.table("barcode_registry").select("plate_name").execute()
    saved_files = [row['plate_name'] for row in plates_res.data]

    start_index = 0
    if st.session_state.scanned_plate in saved_files:
        start_index = saved_files.index(st.session_state.scanned_plate) + 1
        st.session_state.scanned_plate = None 
    elif url_plate_id and url_plate_id in saved_files:
        start_index = saved_files.index(url_plate_id) + 1

    selected_saved = st.selectbox(
        "📂 Load a Saved Plate", 
        options=["-- New Upload --"] + saved_files,
        index=start_index,
        key=f"sidebar_selector_{st.session_state.sb_ver}"
    )

    df = pd.DataFrame()
    id_col, name_col, smiles_col = None, None, None
    is_viewing_saved = selected_saved != "-- New Upload --"

    if is_viewing_saved:
        # Load specific plate data from Supabase
        well_res = supabase.table("well_data").select("*").eq("plate_name", selected_saved).execute()
        df = pd.DataFrame(well_res.data)
        # Rename columns to match your display logic
        if not df.empty:
            df = df.rename(columns={'well': 'Well', 'product_name': 'Product_Name', 'smiles': 'SMILES'})
        
        st.success(f"📍 Viewing: {selected_saved}")
        
        col1, col2 = st.columns(2)
        if col1.button("🗑️ Delete", use_container_width=True):
            # Foreign Key CASCADE in SQL will handle deleting wells automatically
            supabase.table("barcode_registry").delete().eq("plate_name", selected_saved).execute()
            st.query_params.clear()
            st.session_state.sb_ver += 1
            st.rerun()
        if col2.button("➕ New", use_container_width=True):
            st.query_params.clear()
            st.session_state.sb_ver += 1
            st.rerun()
    else:
        uploaded_file = st.file_uploader("Upload Excel/CSV", type=['xlsx', 'csv'], key=f"up_{st.session_state.up_ver}")
        if uploaded_file:
            df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('xlsx') else pd.read_csv(uploaded_file)
            cols = df.columns.tolist()
            id_col = st.selectbox("Well ID Column", options=cols)
            name_col = st.selectbox("Product Name Column", options=cols)
            smiles_col = st.selectbox("SMILES Column", options=cols)

    # --- 6. LOGIC: 10x10 TO 96-WELL MAPPING ---
    if not df.empty and not is_viewing_saved and id_col:
        def convert_grid(well_id):
            match = re.match(r"([A-J])(\d+)", str(well_id).strip().upper().replace(" ", ""))
            if not match: return well_id
            row_let, col_num = match.groups()
            abs_pos = ((ord(row_let) - ord('A')) * 10) + int(col_num)
            if abs_pos <= 96:
                new_row = chr(ord('A') + (abs_pos - 1) // 12)
                new_col = ((abs_pos - 1) % 12) + 1
                return f"{new_row}{new_col}"
            return "EMPTY"

        df[id_col] = df[id_col].apply(convert_grid)
        df = df[df[id_col] != "EMPTY"]
        df[id_col] = df[id_col].astype(str).str.replace(r'([A-H])0(\d)', r'\1\2', regex=True)

    # --- 7. STORAGE LOGIC (SUPABASE INSERT) ---
    if not df.empty and not is_viewing_saved:
        st.divider()
        if not st.session_state.get("has_just_saved"):
            barcode = st.text_input("Barcode (8 Digits)", max_chars=8)
            save_id = st.text_input("Custom Plate Name", value="PLATE_001")
            
            # Check for duplicates in Supabase
            bc_check = supabase.table("barcode_registry").select("barcode").eq("barcode", barcode).execute()
            name_check = supabase.table("barcode_registry").select("plate_name").eq("plate_name", save_id).execute()
            
            can_save = (len(barcode) == 8 and barcode.isdigit() and 
                        not bc_check.data and not name_check.data)

            if st.button("💾 Save to Cloud", use_container_width=True, disabled=not can_save):
                # 1. Register the plate
                supabase.table("barcode_registry").insert({"barcode": barcode, "plate_name": save_id}).execute()
                
                # 2. Upload the wells
                wells_to_insert = []
                for _, row in df.iterrows():
                    wells_to_insert.append({
                        "plate_name": save_id,
                        "well": str(row[id_col]),
                        "product_name": str(row[name_col]),
                        "smiles": str(row[smiles_col])
                    })
                supabase.table("well_data").insert(wells_to_insert).execute()
                
                st.session_state.has_just_saved = True
                st.session_state.last_saved_id = barcode
                st.rerun()
        else:
            st.success(f"✅ Cloud Linked: {st.session_state.last_saved_id}")
            if st.button("Upload Next"):
                st.session_state.has_just_saved = False
                st.session_state.up_ver += 1
                st.rerun()

    st.divider()
    with st.form("scan_form", clear_on_submit=True):
        scan_val = st.text_input("🔍 Scan Barcode")
        if st.form_submit_button("Search", use_container_width=True) and scan_val:
            res = supabase.table("barcode_registry").select("barcode").eq("barcode", str(scan_val)).execute()
            if res.data:
                st.query_params["barcode"] = scan_val
                st.session_state.sb_ver += 1
                st.rerun()
            st.error("Barcode not found.")

# --- 8. MAIN INTERFACE (GRID) ---
plate_col, info_col = st.columns([1.7, 1])

with plate_col:
    st.subheader("Cloud Plate View")
    rows, cols = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'], range(1, 13)
    h_cols = st.columns([0.6] + [1]*12)
    for i in cols: h_cols[i].markdown(f'<p class="label-text">{i}</p>', unsafe_allow_html=True)

    for r in rows:
        r_cells = st.columns([0.6] + [1]*12)
        r_cells[0].markdown(f'<p class="label-text" style="padding-top:10px">{r}</p>', unsafe_allow_html=True)
        for c in cols:
            w_id = f"{r}{c}"
            search_col = 'Well' if is_viewing_saved else id_col
            has_data = w_id in df[search_col].values if not df.empty else False
            
            if r_cells[c].button(w_id, key=f"btn_{w_id}", type="primary" if has_data else "secondary"):
                st.session_state.selected_well = w_id

with info_col:
    sel = st.session_state.selected_well
    if sel:
        st.markdown(f'<div class="well-id-header">Well {sel}</div>', unsafe_allow_html=True)
        search_col = 'Well' if is_viewing_saved else id_col
        well_data = df[df[search_col] == sel] if not df.empty else pd.DataFrame()
        
        if not well_data.empty:
            p_name = well_data['Product_Name' if is_viewing_saved else name_col].values[0]
            s_val = well_data['SMILES' if is_viewing_saved else smiles_col].values[0]
            st.markdown(f"**Product:** {p_name}")
            if pd.notna(s_val) and str(s_val).strip() != "":
                st.code(s_val, language=None)
            else:
                st.caption("No SMILES found.")
        else:
            st.write("No data assigned.")
