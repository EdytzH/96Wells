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
    
    # 1. Load existing plates
    saved_files = [f.replace(".csv", "") for f in os.listdir("saved_plates") if f.endswith(".csv")]
    
    # Dropdown - if we just saved, we'll force this to the new plate
    default_index = 0
    if "just_saved_id" in st.session_state and st.session_state.just_saved_id in saved_files:
        default_index = saved_files.index(st.session_state.just_saved_id) + 1
        # Clear the 'just saved' state so it doesn't stay locked forever
        del st.session_state.just_saved_id

    selected_saved = st.selectbox(
        "📂 Load a Saved Plate", 
        options=["-- New Upload --"] + saved_files,
        index=default_index,
        key="plate_selector"
    )

    df = pd.DataFrame()
    id_col, name_col, smiles_col = None, None, None
    is_viewing_saved = False

    # 2. SOURCE LOGIC
    # If URL exists OR Dropdown is selected, show the saved view
    active_id = url_plate_id if (url_plate_id and url_plate_id in saved_files and selected_saved == "-- New Upload --") else (selected_saved if selected_saved != "-- New Upload --" else None)

    if active_id:
        df = pd.read_csv(f"saved_plates/{active_id}.csv")
        id_col, name_col, smiles_col = 'Well', 'Product_Name', 'SMILES'
        is_viewing_saved = True
        
        # --- VIEW MODE UI ---
        st.success(f"Viewing: {active_id}")
        
        import urllib.parse
        unique_url = f"96wells.streamlit.app/?plate={urllib.parse.quote(active_id)}"
        st.markdown(f"""
            <div style="border: 1px solid var(--text-color); border-radius: 8px; padding: 12px; margin-top: 10px; opacity: 0.8;">
                <p style="color: #4A90E2; font-size: 11px; font-weight: 700; text-transform: uppercase; margin: 0 0 5px 0;">🔗 Link to Plate</p>
                <code style="color: var(--text-color); font-family: 'Courier New', monospace; font-size: 13px; word-break: break-all; display: block;">{unique_url}</code>
            </div>
        """.strip(), unsafe_allow_html=True)

        st.write("")
        if st.button(f"🗑️ Delete Plate", type="secondary", use_container_width=True):
            os.remove(f"saved_plates/{active_id}.csv")
            st.rerun()

    else:
        # --- NEW UPLOAD MODE ---
        if "up_ver" not in st.session_state: st.session_state.up_ver = 0
        uploaded_file = st.file_uploader("Upload Excel/CSV", type=['xlsx', 'csv'], key=f"uploader_{st.session_state.up_ver}")
        
        if uploaded_file:
            try:
                df = pd.read_excel(uploaded_file, engine='openpyxl') if uploaded_file.name.endswith('xlsx') else pd.read_csv(uploaded_file)
                cols = df.columns.tolist()
                id_col = st.selectbox("Well ID Column", options=cols)
                name_col = st.selectbox("Product Name Column", options=cols)
                smiles_col = st.selectbox("SMILES Column", options=cols)
            except ImportError:
                st.error("Please add `openpyxl` to requirements.txt")
                st.stop()

    # 3. GLOBAL CLEANING & SAVING
    if not df.empty and id_col and name_col and smiles_col:
        df[id_col] = df[id_col].astype(str).str.split('.').str[0].str.strip().str.upper().str.replace(r'([A-H])0(\d)', r'\1\2', regex=True)
        
        if not is_viewing_saved:
            st.divider()
            save_id = st.text_input("Barcode / Plate ID", value="PLATE_001")
            if st.button("💾 Save Plate to App", use_container_width=True):
                save_df = df[[id_col, name_col, smiles_col]].copy()
                save_df.columns = ['Well', 'Product_Name', 'SMILES']
                save_df.to_csv(f"saved_plates/{save_id}.csv", index=False)
                
                # Set the 'just saved' state so the link appears after rerun
                st.session_state.just_saved_id = save_id
                st.session_state.up_ver += 1 # Wipes the uploader
                
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
