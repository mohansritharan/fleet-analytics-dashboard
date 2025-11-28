import streamlit as st
import pandas as pd
import time
import plotly.express as px
from datetime import datetime, timedelta
from PIL import Image, ImageDraw
import io

# --- 1. PAGE CONFIG & CSS ---
st.set_page_config(page_title="Fleet Analytics Portal", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    /* Global Styling */
    .stApp { background-color: #ffffff; color: #1d1d1f; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }

    /* CENTERED TITLE */
    .centered-title {
        text-align: center; font-weight: 700; font-size: 3rem; color: #1d1d1f; margin-bottom: 20px;
    }

    /* COMPACT UPLOAD BOXES */
    [data-testid='stFileUploader'] {
        border: 2px dashed #34c759; border-radius: 12px; padding: 10px;
        background-color: #f9f9f9; transition: all 0.3s ease; min-height: 0px;
    }
    [data-testid='stFileUploader']:hover { border-color: #32d74b; transform: scale(1.005); }
    [data-testid='stFileUploader'] label { font-weight: 600; color: #1d1d1f; font-size: 14px; margin-bottom: 5px; }
    [data-testid='stFileUploader'] button { border-radius: 15px; border: 1px solid #34c759; color: #34c759; font-size: 12px; padding: 0.25rem 0.75rem; }

    /* Main Process Button */
    div.stButton > button:first-child {
        width: 100%; background-color: #0071e3; color: white;
        border-radius: 980px; padding: 12px 20px; border: none; font-weight: 500;
        box-shadow: 0 4px 6px rgba(0,113,227,0.2); font-size: 16px;
    }
    div.stButton > button:first-child:hover { background-color: #0077ED; transform: scale(1.01); }

    /* --- SIDEBAR NAVIGATION STYLING --- */
    [data-testid="stSidebar"] button {
        background-color: transparent !important;
        color: #1d1d1f !important;
        border: none !important;
        text-align: left;
        padding-left: 20px;
        font-weight: 600;
        font-size: 15px;
        transition: background-color 0.2s ease;
        width: 100%;
        margin-bottom: 5px;
    }

    [data-testid="stSidebar"] button:hover {
        background-color: #f5f5f7 !important;
        color: #0071e3 !important;
    }

    [data-testid="stSidebar"] button:active, 
    [data-testid="stSidebar"] button:focus {
        background-color: transparent !important;
        color: #0071e3 !important;
        outline: none;
        box-shadow: none;
    }

    /* CUSTOM HAMBURGER MENU */
    [data-testid="stSidebarCollapsedControl"] { color: #1d1d1f !important; border: none !important; background-color: transparent !important; }
    [data-testid="stSidebarCollapsedControl"] svg { display: none !important; }
    [data-testid="stSidebarCollapsedControl"]::before {
        content: "☰"; font-size: 28px; font-weight: bold; color: #1d1d1f; margin-top: 5px; display: inline-block;
    }

    /* Checkbox Styling */
    .stCheckbox label { font-weight: 600; font-size: 15px; }

    /* Blur Overlay */
    .blur-overlay {
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background: rgba(255, 255, 255, 0.75); backdrop-filter: blur(12px);
        z-index: 99999; display: flex; flex-direction: column;
        justify-content: center; align-items: center;
    }
    .loading-text { font-size: 24px; font-weight: 600; color: #1d1d1f; margin-top: 20px; }
    .custom-loader {
        border: 4px solid #f3f3f3; border-top: 4px solid #0071e3;
        border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite;
    }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    @keyframes fadeInUp { from { opacity: 0; transform: translate3d(0, 40px, 0); } to { opacity: 1; transform: translate3d(0, 0, 0); } }
    .animate-enter { animation: fadeInUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards; }

    /* Sidebar Container */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #d2d2d7;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. INITIALIZE SESSION STATE ---
if 'page' not in st.session_state: st.session_state.page = "Fleet Dashboard Analysis"
if 'comm_raw' not in st.session_state: st.session_state.comm_raw = None
if 'fw_raw' not in st.session_state: st.session_state.fw_raw = None
if 'all_vendors_list' not in st.session_state: st.session_state.all_vendors_list = []
if 'detailed_comm_data' not in st.session_state: st.session_state.detailed_comm_data = None


# --- 3. HELPER FUNCTIONS ---
def add_rounded_corners(im, rad):
    circle = Image.new('L', (rad * 2, rad * 2), 0)
    draw = ImageDraw.Draw(circle)
    draw.ellipse((0, 0, rad * 2 - 1, rad * 2 - 1), fill=255)
    alpha = Image.new('L', im.size, 255)
    w, h = im.size
    alpha.paste(circle.crop((0, 0, rad, rad)), (0, 0))
    alpha.paste(circle.crop((0, rad, rad, rad * 2)), (0, h - rad))
    alpha.paste(circle.crop((rad, 0, rad * 2, rad)), (w - rad, 0))
    alpha.paste(circle.crop((rad, rad, rad * 2, rad * 2)), (w - rad, h - rad))
    im.putalpha(alpha)
    return im


def smart_load(file_obj, required_cols):
    df = pd.read_excel(file_obj, header=0)
    df.columns = df.columns.astype(str).str.strip()
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}. Found: {list(df.columns)}")
    return df[required_cols]


def render_summary_section(title, raw_df, row_index_col, all_vendors, key_prefix, drop_zeros=False):
    st.subheader(title)

    # Vendor Filter
    if f"filter_{key_prefix}" not in st.session_state:
        default_sel = [v for v in all_vendors if v == "Prime Edge"]
        if not default_sel: default_sel = all_vendors[:1]
        st.session_state[f"filter_{key_prefix}"] = default_sel
    if f"all_{key_prefix}" not in st.session_state: st.session_state[f"all_{key_prefix}"] = False

    def toggle_all_local():
        if st.session_state[f"all_{key_prefix}"]:
            st.session_state[f"filter_{key_prefix}"] = all_vendors
        else:
            st.session_state[f"filter_{key_prefix}"] = []

    def sync_select_all_local():
        current = st.session_state[f"filter_{key_prefix}"]
        if set(current) == set(all_vendors):
            st.session_state[f"all_{key_prefix}"] = True
        else:
            st.session_state[f"all_{key_prefix}"] = False

    col_sel, col_chk = st.columns([3, 1])
    with col_chk:
        st.write("")
        st.write("")
        st.checkbox("Select All", key=f"all_{key_prefix}", on_change=toggle_all_local)

    with col_sel:
        selected_vendors = st.multiselect(f"Filter Vendors for {title}:", options=all_vendors,
                                          key=f"filter_{key_prefix}", on_change=sync_select_all_local)

    if not selected_vendors:
        st.warning("Please select at least one vendor.")
        return

    # Filter Data
    filtered_df = raw_df[selected_vendors].copy()
    if drop_zeros:
        row_sums = filtered_df.sum(axis=1)
        filtered_df = filtered_df[row_sums > 0]

    filtered_df.loc['Total'] = filtered_df.sum(axis=0)

    # Table
    styled_df = filtered_df.style.set_properties(**{
        'background-color': 'white', 'color': '#1d1d1f', 'border-bottom': '1px solid #d2d2d7',
        'font-family': 'sans-serif', 'font-size': '14px', 'text-align': 'center'
    }).set_table_styles([
        {'selector': 'th', 'props': [('background-color', '#F5F5F7'), ('color', '#1d1d1f'), ('font-weight', '600'),
                                     ('border-bottom', '2px solid #d2d2d7'), ('padding', '12px')]},
        {'selector': 'td', 'props': [('padding', '10px')]},
        {'selector': 'tr:last-child',
         'props': [('font-weight', 'bold'), ('background-color', '#f2f2f7'), ('color', '#0071e3')]}
    ])

    edited_df = st.data_editor(styled_df, use_container_width=True, num_rows="fixed", key=f"{key_prefix}_table")
    st.download_button(f"Download Summary CSV", data=edited_df.to_csv().encode('utf-8'),
                       file_name=f'{key_prefix}_summary.csv',
                       mime='text/csv')

    # Chart
    st.markdown("##### Visual Insights")

    # --- NEW: SORTING CONTROLS ---
    sort_col1, sort_col2 = st.columns([1, 4])
    with sort_col1:
        sort_order = st.selectbox(
            "Rearrange Chart By:",
            ["Default (Vendor Name)", "Total Count (High → Low)", "Total Count (Low → High)"],
            key=f"sort_{key_prefix}"
        )

    try:
        chart_source = edited_df.drop(index='Total')
        chart_data = chart_source.reset_index().melt(id_vars=row_index_col, var_name='Device Vendor',
                                                     value_name='Count')

        APPLE_COLORS = ['#34c759', '#ff3b30', '#ff9f0a', '#0071e3', '#af52de', '#5856d6', '#ff2d55']

        fig = px.bar(chart_data, x='Device Vendor', y='Count', color=row_index_col, barmode='group', text_auto=True,
                     color_discrete_sequence=APPLE_COLORS)

        # --- APPLY SORTING LOGIC ---
        if sort_order == "Total Count (High → Low)":
            fig.update_layout(xaxis={'categoryorder': 'total descending'})
        elif sort_order == "Total Count (Low → High)":
            fig.update_layout(xaxis={'categoryorder': 'total ascending'})
        # Else: Default plotly behavior (usually alphabetical or data order)

        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(family="-apple-system, sans-serif", size=14, color="#1d1d1f"),
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.25,
                xanchor="center",
                x=0.5
            ),
            margin=dict(l=20, r=20, t=20, b=80)
        )

        fig.update_traces(marker_cornerradius=10)

        st.plotly_chart(fig, use_container_width=True)

        img_bytes = fig.to_image(format="png", scale=2)
        bg = Image.new("RGB", Image.open(io.BytesIO(img_bytes)).size, (255, 255, 255))
        bg.paste(Image.open(io.BytesIO(img_bytes)), mask=Image.open(io.BytesIO(img_bytes)).split()[3])
        final_buffer = io.BytesIO()
        add_rounded_corners(bg.convert("RGBA"), 40).save(final_buffer, format="PNG")
        st.download_button(f"Download Graph", data=final_buffer.getvalue(), file_name=f"{key_prefix}_chart.png",
                           mime="image/png")

    except Exception as e:
        st.warning(f"Chart error: {e}")


# --- 4. SIDEBAR NAVIGATION BUTTONS ---
def set_page(page_name):
    st.session_state.page = page_name


st.sidebar.image("https://img.icons8.com/ios-filled/100/0071e3/truck.png", width=50)
st.sidebar.write("### Navigation")

# Navigation Buttons
if st.sidebar.button("Fleet Dashboard Analysis", use_container_width=True):
    st.session_state.page = "Fleet Dashboard Analysis"

if st.sidebar.button("Master Data Comparison", use_container_width=True):
    st.session_state.page = "Master Data Comparison"

# =========================================================
# PAGE 1: FLEET DASHBOARD ANALYSIS
# =========================================================
if st.session_state.page == "Fleet Dashboard Analysis":

    st.markdown('<h1 class="centered-title">Fleet Dashboard Analysis</h1>', unsafe_allow_html=True)

    # --- 1. ANALYSIS SELECTION ---
    st.write("### 1. Select Analysis")

    if "c_comm" not in st.session_state: st.session_state.c_comm = True
    if "c_fw" not in st.session_state: st.session_state.c_fw = False
    if "select_all_mod" not in st.session_state: st.session_state.select_all_mod = False


    def toggle_modules():
        state = st.session_state.select_all_mod
        st.session_state.c_comm = state
        st.session_state.c_fw = state


    def update_mod_master():
        if st.session_state.c_comm and st.session_state.c_fw:
            st.session_state.select_all_mod = True
        else:
            st.session_state.select_all_mod = False


    st.checkbox("Select All Modules", key="select_all_mod", on_change=toggle_modules)

    col_cb1, col_cb2 = st.columns(2)
    with col_cb1:
        run_comm = st.checkbox("Communication Status", key="c_comm", on_change=update_mod_master)
    with col_cb2:
        run_fw = st.checkbox("Firmware Status", key="c_fw", on_change=update_mod_master)

    st.markdown("---")

    # --- 2. FILE UPLOADS ---
    st.write("### 2. Upload Data")
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        file_dashboard = st.file_uploader("Fleet Dashboard (Req)", type=['xlsx'], key="f1")
        file_rebody = st.file_uploader("Rebody File", type=['xlsx'], key="f2")
    with col_up2:
        file_fm = st.file_uploader("Field Maintenance", type=['xlsx'], key="f3")
        file_sheddown = st.file_uploader("Sheddown File", type=['xlsx'], key="f4")

    st.markdown("---")

    # --- 3. PROCESS BUTTON ---
    if st.button("Process Data"):
        missing = []
        if not file_dashboard: missing.append("Fleet Dashboard")
        if run_comm:
            if not file_rebody: missing.append("Rebody File")
            if not file_fm: missing.append("Field Maintenance")
            if not file_sheddown: missing.append("Sheddown File")

        if missing:
            st.error(f"Please upload: {', '.join(missing)}")
        else:
            placeholder = st.empty()
            placeholder.markdown(
                '<div class="blur-overlay"><div class="custom-loader"></div><div class="loading-text">Greater things takes time...</div></div>',
                unsafe_allow_html=True)
            time.sleep(1.5)

            try:
                st.session_state.comm_raw = None
                st.session_state.fw_raw = None
                st.session_state.all_vendors_list = []
                st.session_state.detailed_comm_data = None  # Reset Detailed Data

                FLEET_COLUMN = 'Fleet Number'
                VENDOR_COLUMN = 'Device Vendor'

                # --- 1. PRE-LOAD TO GET VENDORS ---
                df_dash_raw = pd.read_excel(file_dashboard, header=0)
                df_dash_raw.columns = df_dash_raw.columns.astype(str).str.strip()
                if VENDOR_COLUMN in df_dash_raw.columns:
                    unique_vendors = sorted(
                        df_dash_raw[VENDOR_COLUMN].dropna().astype(str).str.strip().unique().tolist())
                    st.session_state.all_vendors_list = unique_vendors
                else:
                    raise ValueError(f"Column '{VENDOR_COLUMN}' not found in Dashboard.")

                # --- 2. MODULE: COMMUNICATION ---
                if run_comm:
                    CURRENT_DATE = datetime.now().date()
                    PREVIOUS_DATE = (CURRENT_DATE - timedelta(days=1))
                    DATE_COLUMN = 'Last Updated'
                    PRIORITY_MAP = {'Sheddown': 3, 'Field Maintenance': 2, 'Rebody Renovation': 1}
                    STATUS_ORDER = ['Communication', 'No Communication', 'Rebody Renovation', 'Field Maintenance',
                                    'Sheddown']

                    df_dash_comm = smart_load(file_dashboard, [FLEET_COLUMN, VENDOR_COLUMN, DATE_COLUMN])
                    df_rebody = smart_load(file_rebody, [FLEET_COLUMN]).assign(Category='Rebody Renovation')
                    df_fm = smart_load(file_fm, [FLEET_COLUMN]).assign(Category='Field Maintenance')
                    df_sheddown = smart_load(file_sheddown, [FLEET_COLUMN]).assign(Category='Sheddown')

                    for df in [df_dash_comm, df_rebody, df_fm, df_sheddown]:
                        df[FLEET_COLUMN] = df[FLEET_COLUMN].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

                    df_all_red = pd.concat([df_rebody, df_fm, df_sheddown], ignore_index=True)
                    df_all_red['Priority_Score'] = df_all_red['Category'].map(PRIORITY_MAP)
                    df_red_master = df_all_red.sort_values('Priority_Score', ascending=False).drop_duplicates(
                        subset=[FLEET_COLUMN], keep='first')

                    df_dash_comm[DATE_COLUMN] = pd.to_datetime(df_dash_comm[DATE_COLUMN], errors='coerce')
                    df_dash_comm['Last Updated Date'] = df_dash_comm[DATE_COLUMN].dt.date
                    is_comm = (df_dash_comm['Last Updated Date'] == CURRENT_DATE) | (
                            df_dash_comm['Last Updated Date'] == PREVIOUS_DATE)

                    df_merged = pd.merge(df_dash_comm, df_red_master[[FLEET_COLUMN, 'Category']], on=FLEET_COLUMN,
                                         how='left')
                    df_merged['Final Status'] = df_merged.apply(lambda row: 'Communication' if is_comm[row.name] else (
                        row['Category'] if pd.notna(row['Category']) else 'No Communication'), axis=1)

                    # --- SAVE DETAILED DATA FOR DOWNLOAD ---
                    detailed_export = df_merged[[FLEET_COLUMN, 'Final Status', VENDOR_COLUMN]].copy()
                    detailed_export.columns = ['Fleet Number', 'Status', 'Vendor']
                    st.session_state.detailed_comm_data = detailed_export

                    comm_summ = pd.pivot_table(df_merged, index='Final Status', columns=VENDOR_COLUMN, aggfunc='size',
                                               fill_value=0)
                    comm_summ = comm_summ.reindex(STATUS_ORDER, fill_value=0)
                    st.session_state.comm_raw = comm_summ

                # --- 3. MODULE: FIRMWARE ---
                if run_fw:
                    FW_COLUMN = 'Firmware Version'
                    file_dashboard.seek(0)
                    df_dash_fw = smart_load(file_dashboard, [VENDOR_COLUMN, FW_COLUMN])

                    fw_summ = pd.pivot_table(df_dash_fw, index=FW_COLUMN, columns=VENDOR_COLUMN, aggfunc='size',
                                             fill_value=0)
                    st.session_state.fw_raw = fw_summ

            except Exception as e:
                st.error(f"❌ Error: {e}")

            placeholder.empty()

    # --- 4. DISPLAY RESULTS ---
    with st.container():
        if st.session_state.comm_raw is not None or st.session_state.fw_raw is not None:
            st.markdown('<div class="animate-enter">', unsafe_allow_html=True)
            st.success("Analysis Complete")

            if st.session_state.comm_raw is not None:
                render_summary_section(
                    "📡 Communication Status",
                    st.session_state.comm_raw,
                    "Final Status",
                    st.session_state.all_vendors_list,
                    "comm",
                    drop_zeros=False
                )

                # --- NEW DETAILED DOWNLOAD BUTTON ---
                if st.session_state.detailed_comm_data is not None:
                    csv_detailed = st.session_state.detailed_comm_data.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Detailed Fleet List (CSV)",
                        data=csv_detailed,
                        file_name="Detailed_Fleet_Status.csv",
                        mime="text/csv",
                        help="Download the full list of fleets with their individual status."
                    )

            if st.session_state.comm_raw is not None and st.session_state.fw_raw is not None:
                st.markdown("---")

            if st.session_state.fw_raw is not None:
                render_summary_section(
                    "⚙️ Firmware Version Status",
                    st.session_state.fw_raw,
                    "Firmware Version",
                    st.session_state.all_vendors_list,
                    "fw",
                    drop_zeros=True
                )

            st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# PAGE 2: MASTER DATA COMPARISON
# =========================================================
elif st.session_state.page == "Master Data Comparison":
    st.markdown('<h1 class="centered-title">Master Data Comparison</h1>', unsafe_allow_html=True)
    st.info("🚧 Module coming soon!")