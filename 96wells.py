import streamlit as st
import pandas as pd
import re
from supabase import create_client, Client

# --- 1. SUPABASE CONNECTION ---
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
if "current_df" not in st.session_state:
    st.session_state.current_df = pd.DataFrame()
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False
if "show_replace" not in st.session_state:
    st.session_state.show_replace = False
if st.session_state.get("has_just_saved"):
    st.toast(f"✅ Plate {st.session_state.get('last_saved_id')} Saved Successfully!")
    st.session_state.has_just_saved = False

# --- 3. HELPER FUNCTIONS ---
def find_best_match(columns, keywords):
    for i, col in enumerate(columns):
        clean_col = str(col).strip().lower()
        if any(key.lower() in clean_col for key in keywords):
            return i
    return 0

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

# --- 4. URL & BARCODE ROUTING ---
url_barcode = st.query_params.get("barcode")
url_plate_id = None
if url_barcode:
    res = supabase.table("barcode_registry").select("plate_name").eq("barcode", str(url_barcode)).execute()
    if res.data:
        st.session_state.scanned_plate = res.data[0]['plate_name']
        url_plate_id = st.session_state.scanned_plate

# --- 5. UI CONFIG & CSS ---
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

# --- 6. SIDEBAR: DATA CONTROLS ---
with st.sidebar:
    st.header("1. Data Setup")
    plates_res = supabase.table("barcode_registry").select("plate_name").execute()
    saved_files = [row['plate_name'] for row in plates_res.data]

    start_index = 0
    if st.session_state.scanned_plate in saved_files:
        start_index = saved_files.index(st.session_state.scanned_plate) + 1
        st.session_state.scanned_plate = None 
    elif url_plate_id and url_plate_id in saved_files:
        start_index = saved_files.index(url_plate_id) + 1

    selected_saved = st.selectbox(
        "📂 Load a Saved Plate", options=["-- New Upload --"] + saved_files,
        index=start_index, key=f"sidebar_selector_{st.session_state.sb_ver}"
    )

    id_col, name_col, smiles_col = None, None, None
    is_viewing_saved = selected_saved != "-- New Upload --"

    if is_viewing_saved:
        bc_res = supabase.table("barcode_registry").select("barcode").eq("plate_name", selected_saved).execute()
        current_barcode = bc_res.data[0]['barcode'] if bc_res.data else "Unknown"

        if "loaded_plate" not in st.session_state or st.session_state.loaded_plate != selected_saved:
            well_res = supabase.table("well_data").select("*").eq("plate_name", selected_saved).execute()
            temp_df = pd.DataFrame(well_res.data)
            if not temp_df.empty:
                temp_df = temp_df.rename(columns={'well': 'Well', 'product_name': 'Product_Name', 'smiles': 'SMILES'})
            st.session_state.current_df = temp_df
            st.session_state.loaded_plate = selected_saved
            st.session_state.edit_mode = False
            st.session_state.show_replace = False

        st.success(f"Barcode: **{current_barcode}**")
        
        st.markdown("---")
        c1, c2 = st.columns(2)
        c3, c4 = st.columns(2)
        
        if c1.button("➕ New", use_container_width=True):
            st.query_params.clear()
            # Reset everything to default
            st.session_state.current_df = pd.DataFrame()
            st.session_state.has_just_saved = False 
            st.session_state.sb_ver += 1
            st.session_state.up_ver += 1
            st.rerun()

        if c2.button("🗑️ Delete", use_container_width=True):
            supabase.table("barcode_registry").delete().eq("plate_name", selected_saved).execute()
            st.query_params.clear()
            st.session_state.sb_ver += 1
            st.rerun()
        
        edit_lbl = "🔓 Lock" if st.session_state.edit_mode else "✏️ Edit"
        if c3.button(edit_lbl, use_container_width=True):
            st.session_state.edit_mode = not st.session_state.edit_mode
            st.session_state.show_replace = False
            st.rerun()

        if c4.button("🔄 Update", use_container_width=True, type="primary" if st.session_state.show_replace else "secondary"):
            st.session_state.show_replace = not st.session_state.show_replace
            st.session_state.edit_mode = False
            st.rerun()

        if st.session_state.show_replace:
            st.info("Upload file to auto-preview changes in the grid.")
            replace_file = st.file_uploader("Replace existing data", type=['xlsx', 'csv'], key="repl_up")
            
            if replace_file:
                up_df = pd.read_excel(replace_file) if replace_file.name.endswith('xlsx') else pd.read_csv(replace_file)
                cols = up_df.columns.tolist()
                w_idx, p_idx, s_idx = find_best_match(cols, ["well"]), find_best_match(cols, ["product"]), find_best_match(cols, ["smiles"])
                
                # Instant mapping to session state
                up_df['Well'] = up_df.iloc[:, w_idx].apply(convert_grid)
                up_df = up_df[up_df['Well'] != "EMPTY"]
                up_df = up_df.rename(columns={cols[p_idx]: 'Product_Name', cols[s_idx]: 'SMILES'})
                
                st.session_state.current_df = up_df[['Well', 'Product_Name', 'SMILES']]
                st.warning("Previewing New Data. Click below to save.")

            if st.button("💾 Push to Cloud", use_container_width=True, type="primary"):
                supabase.table("well_data").delete().eq("plate_name", selected_saved).execute()
                wells_to_insert = [
                    {"plate_name": selected_saved, "well": str(row['Well']), "product_name": str(row['Product_Name']), "smiles": str(row['SMILES'])}
                    for _, row in st.session_state.current_df.iterrows()
                ]
                supabase.table("well_data").insert(wells_to_insert).execute()
                st.session_state.show_replace = False
                st.success("Cloud Synchronized!")
                st.rerun()
    else:
        # --- NEW UPLOAD LOGIC ---
        uploaded_file = st.file_uploader("Upload Excel/CSV", type=['xlsx', 'csv'], key=f"up_{st.session_state.up_ver}")
        if uploaded_file:
            new_df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('xlsx') else pd.read_csv(uploaded_file)
            cols = new_df.columns.tolist()
            w_idx, p_idx, s_idx = find_best_match(cols, ["well"]), find_best_match(cols, ["product"]), find_best_match(cols, ["smiles"])
            c_hash = hash(tuple(cols))
            id_col = st.selectbox("Well ID Column", options=cols, index=w_idx, key=f"well_{c_hash}")
            name_col = st.selectbox("Product Name Column", options=cols, index=p_idx, key=f"prod_{c_hash}")
            smiles_col = st.selectbox("SMILES Column", options=cols, index=s_idx, key=f"smil_{c_hash}")
            st.session_state.current_df = new_df

# Use session state as the source of truth for the rest of the app
df = st.session_state.current_df

# --- 7. MAPPING (For New Uploads) ---
if not df.empty and not is_viewing_saved and id_col:
    df[id_col] = df[id_col].apply(convert_grid)
    df = df[df[id_col] != "EMPTY"]
    df[id_col] = df[id_col].astype(str).str.replace(r'([A-H])0(\d)', r'\1\2', regex=True)
    st.session_state.current_df = df

# --- 8. SAVE NEW SECTION ---
with st.sidebar:
    if not is_viewing_saved and not df.empty:
        st.divider()
        st.subheader("2. Save to Cloud")
        if not st.session_state.get("has_just_saved"):
            barcode = st.text_input("Barcode (8 Digits)", max_chars=8)
            save_id = st.text_input("Custom Plate Name", value="PLATE_001")
            can_save = (len(barcode) == 8 and barcode.isdigit())
    
            if st.button("💾 Save to Cloud", use_container_width=True, disabled=not can_save):
                # Check for duplicates
                check_res = supabase.table("barcode_registry").select("barcode").eq("barcode", barcode).execute()
                
                if check_res.data:
                    st.error(f"⚠️ Barcode {barcode} already exists!")
                else:
                    # 1. Push to Database
                    supabase.table("barcode_registry").insert({"barcode": barcode, "plate_name": save_id}).execute()
                    wells_to_insert = [
                        {"plate_name": save_id, "well": str(row[id_col]), "product_name": str(row[name_col]), "smiles": str(row[smiles_col])} 
                        for _, row in df.iterrows()
                    ]
                    supabase.table("well_data").insert(wells_to_insert).execute()
                    
                    # 2. CLEAR STATE FOR REFRESH
                    st.session_state.current_df = pd.DataFrame() # Clears the grid
                    st.session_state.has_just_saved = True       # Triggers the success banner
                    st.session_state.up_ver += 1                 # Forces file uploader to reset
                    st.session_state.selected_well = None        # Clears the side info panel
                    st.rerun()       
      
    st.divider()
    st.subheader("3. Plate Search")
    with st.form("scan_form", clear_on_submit=True):
        scan_val = st.text_input("🔍 Scan Barcode")
        if st.form_submit_button("Search", use_container_width=True) and scan_val:
            res = supabase.table("barcode_registry").select("barcode").eq("barcode", str(scan_val)).execute()
            if res.data:
                st.query_params["barcode"] = scan_val
                st.session_state.sb_ver += 1
                st.rerun()

# --- 9. MAIN INTERFACE ---
plate_col, info_col = st.columns([1.7, 1])

with plate_col:
    st.subheader("Cloud Plate View")
    rows, cols_range = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'], range(1, 13)
    h_cols = st.columns([0.6] + [1]*12)
    for i in cols_range: h_cols[i].markdown(f'<p class="label-text">{i}</p>', unsafe_allow_html=True)
    for r in rows:
        r_cells = st.columns([0.6] + [1]*12)
        r_cells[0].markdown(f'<p class="label-text" style="padding-top:10px">{r}</p>', unsafe_allow_html=True)
        for c in cols_range:
            w_id = f"{r}{c}"
            s_col = 'Well' if is_viewing_saved else (id_col if id_col else None)
            
            has_data = False
            if not df.empty and s_col in df.columns:
                has_data = w_id in df[s_col].values
            
            if r_cells[c].button(w_id, key=f"btn_{w_id}", type="primary" if has_data else "secondary"):
                st.session_state.selected_well = w_id

with info_col:
    sel = st.session_state.selected_well
    if sel:
        spacer, content = st.columns([0.15, 1])
        with content:
            st.markdown(f'<div class="well-id-header">Well {sel}</div>', unsafe_allow_html=True)
            s_col = 'Well' if is_viewing_saved else id_col
            
            if s_col and not df.empty:
                well_data_idx = df.index[df[s_col] == sel].tolist()
                if well_data_idx:
                    idx = well_data_idx[0]
                    if st.session_state.edit_mode and is_viewing_saved:
                        new_n = st.text_input("Product Name", value=str(df.at[idx, 'Product_Name']), key=f"ed_n_{sel}")
                        new_s = st.text_area("SMILES", value=str(df.at[idx, 'SMILES']), key=f"ed_s_{sel}")
                        st.session_state.current_df.at[idx, 'Product_Name'] = new_n
                        st.session_state.current_df.at[idx, 'SMILES'] = new_s
                    else:
                        p_name = df.at[idx, 'Product_Name' if is_viewing_saved else name_col]
                        s_val = df.at[idx, 'SMILES' if is_viewing_saved else smiles_col]
                        st.markdown(f"**Product:** {p_name}")
                        if pd.notna(s_val) and str(s_val).strip() != "":
                            st.code(s_val, language=None)
                else:
                    st.info("No data assigned.")
