import streamlit as st
import pandas as pd

st.set_page_config(layout="wide", page_title="96-Well Lab Plate")

# --- ROCK SOLID CSS ---
st.markdown("""
    <style>
    /* 1. Target ONLY buttons in the main area (the plate) to be circles */
    [data-testid="stMain"] button[kind="primary"], 
    [data-testid="stMain"] button[kind="secondary"] {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        border-radius: 50% !important;
        width: 40px !important;
        height: 40px !important;
        padding: 0px !important;
        margin: auto !important;
        line-height: 40px !important;
    }

    /* 2. Reset Sidebar buttons to be normal rectangles */
    [data-testid="stSidebar"] button {
        border-radius: 4px !important;
        width: auto !important;
        height: auto !important;
        padding: 8px 16px !important;
    }

    /* Pastel Green for Data */
    button[kind="primary"] {
        background-color: #C1E1C1 !important; 
        color: #2E7D32 !important;
        border: 1px solid #A5D6A7 !important;
    }

    /* Clean Text Styles */
    .well-id-header { font-size: 26px; font-weight: 800; color: #4A90E2; margin-bottom: 5px; }
    .product-name-text { font-size: 20px; font-weight: 600; color: #D81B60; margin-bottom: 20px; }
    .data-row { display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #f1f1f1; }
    .data-key { color: #888; font-size: 13px; }
    .data-val { color: #111; font-size: 14px; font-weight: 600; }
    .label-text { font-weight: bold; text-align: center; color: #bbb; margin: 0; font-size: 14px; }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR SETUP ---
with st.sidebar:
    st.header("1. Data Setup")
    
    uploaded_file = st.file_uploader("Upload Excel/CSV", type=['xlsx', 'csv'])
    
    # Initialize empty dataframe so the plate shows up regardless
    df = pd.DataFrame()
    id_col, name_col = None, None

    if uploaded_file:
        df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('xlsx') else pd.read_csv(uploaded_file)
        cols = df.columns.tolist()
        id_col = st.selectbox("Well ID Column", options=cols)
        name_col = st.selectbox("Product Name Column", options=cols)
        smiles_col = st.selectbox("SMILES Column", options=cols)
        # Standardize IDs
        df[id_col] = df[id_col].astype(str).str.strip().str.upper().str.replace(r'([A-H])0(\d)', r'\1\2', regex=True)

                # 1. Check for duplicates in the Well ID column
        duplicate_mask = df.duplicated(subset=[id_col], keep=False)
        duplicates = df[duplicate_mask][id_col].unique()

        if len(duplicates) > 0:
            # 2. Display a Warning with the specific Well IDs
            st.warning(f"⚠️ Duplicate entries found for wells: {', '.join(duplicates)}")
            st.info("The app shows the first entry found for these wells.")
            # 3. Optional: Show the user exactly which rows are clashing
            with st.expander("View Clashing Data"):
                st.write(df[duplicate_mask].sort_values(by=id_col))
        # 1. NEW: Split by the period and take the first part, then standardize
        
        df[id_col] = (
            df[id_col]
            .astype(str)                   # Ensure it's a string
            .str.split('.')                # Split at the period (e.g., ['A1', 'fsfijdijf'])
            .str[0]                        # Take the first element ('A1')
            .str.strip()                   # Remove any accidental spaces
            .str.upper()                   # Make it uppercase (A1, not a1)
            .str.replace(r'([A-H])0(\d)', r'\1\2', regex=True) # Turn A01 into A1
        )

# --- MAIN INTERFACE ---
plate_col, info_col = st.columns([1.7, 1])

with plate_col:
    st.subheader("96-Well Plate")
    rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    
    # Grid Header (1-12)
    h_cols = st.columns([0.6] + [1]*12)
    for i in range(1, 13):
        h_cols[i].markdown(f'<p class="label-text">{i}</p>', unsafe_allow_html=True)

    # Grid Rows (The Plate)
    for r in rows:
        row_cells = st.columns([0.6] + [1]*12)
        row_cells[0].markdown(f'<p class="label-text" style="padding-top:10px">{r}</p>', unsafe_allow_html=True)
        
        for c in range(1, 13):
            well_id = f"{r}{c}"
            # Logic: If data exists, it's primary (green). If not, it's secondary (grey).
            has_data = False
            if not df.empty and id_col:
                has_data = well_id in df[id_col].values
            
            if row_cells[c].button(well_id, key=well_id, type="primary" if has_data else "secondary"):
                st.session_state.selected_well = well_id

with info_col:
    selected = st.session_state.get('selected_well')
    if selected:
        # Check if we actually have data for this well
        well_data = df[df[id_col] == selected] if not df.empty and id_col else pd.DataFrame()
        
        # 1. We wrap everything in a div with margin-left to push it right
        st.markdown(f"""
            <div style="margin-left: 40px;">
                <div class="well-id-header">Well {selected}</div>
            """, unsafe_allow_html=True)
        
        if not well_data.empty:
            # 1. Product Name (Green, Bold) - Displayed First
            product_val = well_data[name_col].values[0]
            st.markdown(f"""
                <div style="color: #2E7D32; font-size: 22px; font-weight: 600; margin-top: 5px; margin-left: 40px;">
                    {product_val}
                </div>
            """, unsafe_allow_html=True)

            # 2. SMILES Logic - Displayed Second
            smiles_val = well_data[smiles_col].values[0]
            
            # Check if empty or NaN
            if pd.isna(smiles_val) or str(smiles_val).strip() == "" or str(smiles_val).lower() == "nan":
                st.markdown(f"""
                    <div style="color: #fFB6C1; font-size: 14px; font-style: italic; margin-top: 10px; margin-left: 40px;">
                        No SMILE found
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                    <div style="color: #FFB6C1; font-size: 16px; font-family: monospace; font-weight: 500; margin-top: 10px; margin-left: 40px; word-break: break-all;">
                        {smiles_val}
                    </div>
                """, unsafe_allow_html=True)
            
        else:
            st.markdown('<div style="margin-left: 40px; color: #999;">No data assigned.</div>', unsafe_allow_html=True)
            
        st.markdown("</div>", unsafe_allow_html=True) # Close the margin div