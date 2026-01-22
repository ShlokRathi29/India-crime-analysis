# DATAthon – India Crime Pattern & Safety Analysis Dashboard

An interactive analytics dashboard to explore **Indian crime trends** using **state-wise choropleth maps**, drilldowns, and KPI-based insights.

## Overview
This project was built for a one-day DATAthon competition. It transforms raw crime statistics into a dashboard that helps identify:
- High-risk states/regions
- Crime category patterns (Group/Sub-Group)
- Year-wise trends and comparisons

## Key Features
- **India Choropleth Map** (state-wise crime intensity shading)
- **State Drilldown** for subgroup breakdown + yearly trend
- **KPIs**: Total Crimes, Recovery Rate, Loss Value *(where available)*
- **Comparative Insights**: Top high-risk states, recovery rate rankings
- Shows **all Indian states** on the map even if missing from dataset (filled as 0)

## Tech Stack
- Python
- Streamlit
- Plotly Express
- Pandas, NumPy
- GeoJSON (India state boundaries)
