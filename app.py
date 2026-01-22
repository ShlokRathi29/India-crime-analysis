import json
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st
import urllib.request
import os

st.set_page_config(page_title="India Crime Dashboard", layout="wide")

DATASETS = {
    "Property Crime": "property_crime_cleaned.csv",
    "Murders": "murder_cleaned.csv",
    "Kidnapping & Abduction": "kidnapping_cleaned.csv",
    "Crime Against Women": "women_crimes_cleaned.csv",
    "Frauds": "frauds_cleaned.csv",
    "Auto Theft": "auto_theft_cleaned.csv",
    "Complaint against police": "police_complaints_cleaned.csv",
    "Trial of violent crimes": "trials_cleaned.csv",
}
# India geojson for mapping states
INDIA_GEOJSON_LOCAL_FILE = "india_state.geojson"
GEO_STATE_NAME_KEY = "NAME_1"

@st.cache_data
def load_india_geojson():
    if not os.path.exists(INDIA_GEOJSON_LOCAL_FILE):
        raise FileNotFoundError(
            f"{INDIA_GEOJSON_LOCAL_FILE} not found. Download it into the same folder as app.py"
        )
    with open(INDIA_GEOJSON_LOCAL_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_all_states_df(india_geojson) -> pd.DataFrame:
    
    states = [f["properties"][GEO_STATE_NAME_KEY] for f in india_geojson["features"]]
    return pd.DataFrame({"Area_Name": sorted(set(states))})


@st.cache_data
def load_data(file_path: str) -> pd.DataFrame:
    df = pd.read_csv(file_path)

    # Strip spaces
    for c in df.columns:
        if df[c].dtype == "object":
            df[c] = df[c].astype(str).str.strip()

    # Year
    if "Year" in df.columns:
        df["Year"] = pd.to_numeric(df["Year"], errors="coerce").astype("Int64")

    # Standardize Area column name
    if "Area_Name" not in df.columns:
        # Some NCRB datasets use "STATE/UT" or similar
        for alt in ["STATE/UT", "State/UT", "State", "STATE", "District", "DISTRICT"]:
            if alt in df.columns:
                df = df.rename(columns={alt: "Area_Name"})
                break

    # Convert all numeric columns safely
    for c in df.columns:
        if c not in ["Area_Name", "Group_Name", "Sub_Group_Name"]:
            df[c] = pd.to_numeric(df[c], errors="ignore")

    # If Property Crime file: already known columns
    if "Cases_Property_Stolen" in df.columns:
        df["Total_Crimes"] = pd.to_numeric(df["Cases_Property_Stolen"], errors="coerce").fillna(0)
        df["Total_Recovered"] = pd.to_numeric(df.get("Cases_Property_Recovered", 0), errors="coerce").fillna(0)

        df["Total_Value_Stolen"] = pd.to_numeric(df.get("Value_of_Property_Stolen", 0), errors="coerce").fillna(0)
        df["Total_Value_Recovered"] = pd.to_numeric(df.get("Value_of_Property_Recovered", 0), errors="coerce").fillna(0)

        df["Loss_Value"] = df["Total_Value_Stolen"] - df["Total_Value_Recovered"]
        df["Recovery_Rate"] = np.where(df["Total_Crimes"] > 0, df["Total_Recovered"] / df["Total_Crimes"], 0)

    else:
        # Generic datasets: define Total_Crimes from the best available numeric column
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if len(numeric_cols) == 0:
            raise ValueError(f"No numeric columns found in dataset: {file_path}")

        preferred = [c for c in numeric_cols if "case" in c.lower() or "crime" in c.lower() or "total" in c.lower()]
        base_col = preferred[0] if preferred else numeric_cols[0]

        df["Total_Crimes"] = pd.to_numeric(df[base_col], errors="coerce").fillna(0)

        # Recovery/Loss may not exist in many datasets
        df["Total_Recovered"] = 0
        df["Loss_Value"] = 0
        df["Recovery_Rate"] = 0

    # Standardize Group/Subgroup
    if "Group_Name" not in df.columns:
        df["Group_Name"] = "Overall"
    if "Sub_Group_Name" not in df.columns:
        df["Sub_Group_Name"] = "Overall"

    # Standardize State Names
    STATE_MAP = {
        "NCT of Delhi": "Delhi",
        "Orissa": "Odisha",
        "Uttaranchal": "Uttarakhand",
        "Jammu & Kashmir": "Jammu and Kashmir",
        "Andaman & Nicobar Islands": "Andaman and Nicobar",
        "Dadra & Nagar Haveli": "Dadra and Nagar Haveli",
        "Daman & Diu": "Daman and Diu",
    }
    df["Area_Name"] = df["Area_Name"].replace(STATE_MAP)

    return df


st.title("India Crime Pattern & Safety Analysis Dashboard")

# Dataset selection
st.sidebar.title("Controls")
dataset_name = st.sidebar.selectbox("Select Crime Dataset", list(DATASETS.keys()))
dataset_file = DATASETS[dataset_name]

if not os.path.exists(dataset_file):
    st.error(f"Dataset file not found: {dataset_file}\n\nKeep all CSV files in the same folder as app.py.")
    st.stop()

df = load_data(dataset_file)
india_geojson = load_india_geojson()

# Year filter
years = sorted(df["Year"].dropna().unique().tolist()) if "Year" in df.columns else []
if years:
    min_year, max_year = int(min(years)), int(max(years))
    year_range = st.sidebar.slider("Year Range", min_year, max_year, (min_year, max_year))
    df = df[(df["Year"] >= year_range[0]) & (df["Year"] <= year_range[1])].copy()
else:
    year_range = None

# Group filter
group_options = sorted(df["Group_Name"].dropna().unique().tolist())
selected_group = st.sidebar.selectbox("Crime Group", ["All"] + group_options)
if selected_group != "All":
    df = df[df["Group_Name"] == selected_group].copy()


state_agg = (
    df.groupby("Area_Name", as_index=False)
    .agg(
        Total_Crimes=("Total_Crimes", "sum"),
        Total_Recovered=("Total_Recovered", "sum"),
        Loss_Value=("Loss_Value", "sum"),
    )
)

state_agg["Recovery_Rate"] = np.where(
    state_agg["Total_Crimes"] > 0,
    state_agg["Total_Recovered"] / state_agg["Total_Crimes"],
    0,
)

all_states_df = get_all_states_df(india_geojson)
state_agg = all_states_df.merge(state_agg, on="Area_Name", how="left")

for col in ["Total_Crimes", "Total_Recovered", "Loss_Value", "Recovery_Rate"]:
    if col in state_agg.columns:
        state_agg[col] = state_agg[col].fillna(0)


total_crimes = int(state_agg["Total_Crimes"].sum())
total_recovered = int(state_agg["Total_Recovered"].sum())
recovery_rate = (total_recovered / total_crimes * 100) if total_crimes else 0

k1, k2, k3 = st.columns(3)
k1.metric("Total Crimes", f"{total_crimes:,}")
k2.metric("Total Recovered", f"{total_recovered:,}")
k3.metric("Recovery Rate", f"{recovery_rate:.2f}%")

st.divider()

st.subheader(f"India States Map — {dataset_name} (Shaded by Total Crimes)")

map_fig = px.choropleth(
    state_agg,
    geojson=india_geojson,
    featureidkey=f"properties.{GEO_STATE_NAME_KEY}",
    locations="Area_Name",
    color="Total_Crimes",
    hover_name="Area_Name",
    hover_data={
        "Total_Crimes": ":,",
        "Recovery_Rate": ":.2%",
        "Loss_Value": ":,.0f",
    },
)

# Make borders bold and map clean 
map_fig.update_traces(marker_line_width=1.2)
map_fig.update_geos(
    fitbounds="locations",
    visible=False,
    showcountries=False,
    showcoastlines=False,
    showland=True,
)
map_fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})

st.plotly_chart(map_fig, use_container_width=True)

st.subheader("Drilldown: Select State")
selected_state = st.selectbox(
    "State/UT",
    ["All India"] + sorted(state_agg["Area_Name"].unique().tolist())
)

if selected_state == "All India":
    drill = df.copy()
else:
    drill = df[df["Area_Name"] == selected_state].copy()

left, right = st.columns([1, 1])

with left:
    st.markdown("### Sub-group Breakdown (Top 15)")
    sub_grp = (
        drill.groupby("Sub_Group_Name", as_index=False)
        .agg(Total_Crimes=("Total_Crimes", "sum"))
        .sort_values("Total_Crimes", ascending=False)
        .head(15)
    )

    fig_sub = px.bar(
        sub_grp,
        x="Total_Crimes",
        y="Sub_Group_Name",
        orientation="h",
        title="Sub-groups by Total Crimes",
    )
    fig_sub.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig_sub, use_container_width=True)

with right:
    st.markdown("### Year-wise Trend")
    if "Year" in drill.columns and drill["Year"].notna().any():
        trend = (
            drill.groupby("Year", as_index=False)
            .agg(Total_Crimes=("Total_Crimes", "sum"))
            .sort_values("Year")
        )
        fig_trend = px.line(trend, x="Year", y="Total_Crimes", markers=True, title="Crime Trend")
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("No Year column available in this dataset for trend analysis.")

st.divider()

st.subheader("Comparisons")

c1, c2 = st.columns([1, 1])

with c1:
    st.markdown("### Top 10 High Risk States")
    top_states = state_agg.sort_values("Total_Crimes", ascending=False).head(10)
    fig_top = px.bar(
        top_states,
        x="Total_Crimes",
        y="Area_Name",
        orientation="h",
        title="Top 10 States by Crimes",
    )
    fig_top.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig_top, use_container_width=True)

with c2:
    st.markdown("### Recovery Rate by State (if available)")
    fig_rr = px.bar(
        state_agg.sort_values("Recovery_Rate", ascending=False).head(15),
        x="Recovery_Rate",
        y="Area_Name",
        orientation="h",
        title="Top 15 States by Recovery Rate",
    )
    fig_rr.update_layout(xaxis_tickformat=".0%")
    fig_rr.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig_rr, use_container_width=True)
