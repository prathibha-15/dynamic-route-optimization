import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
import polyline
import pandas as pd
import plotly.express as px
from datetime import datetime

# Initialize session states
if 'route_data' not in st.session_state:
    st.session_state.route_data = None
if 'alternative_routes' not in st.session_state:
    st.session_state.alternative_routes = None

def get_fuel_cost(distance, vehicle_type):
    fuel_prices = {"car": 1.5, "truck": 1.8, "bike": 0}
    efficiency = {"car": 12, "truck": 5, "bike": float('inf')}
    liters = distance / efficiency.get(vehicle_type, 12)
    return liters * fuel_prices.get(vehicle_type, 1.5)

def get_route_from_osrm(start, end):
    start_lon, start_lat = start.split(',')[::-1]
    end_lon, end_lat = end.split(',')[::-1]
    coordinates = f"{start_lon.strip()},{start_lat.strip()};{end_lon.strip()},{end_lat.strip()}"
    osrm_url = f"http://router.project-osrm.org/route/v1/driving/{coordinates}?overview=full&geometries=polyline&alternatives=true"
    
    try:
        response = requests.get(osrm_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("routes", [])
        return []
    except Exception as e:
        st.error(f"Route Error: {str(e)}")
        return []

def get_traffic_delay(location):
    api_key = "VjmQzZS9h9TjfDhNcv5JJGe1u4zA4gFy"
    try:
        lat, lon = location.split(',')
        url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?key={api_key}&point={lat},{lon}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            current_speed = data.get('flowSegmentData', {}).get('currentSpeed', 0)
            free_flow = data.get('flowSegmentData', {}).get('freeFlowSpeed', 1)
            return max(0, (1 - current_speed/free_flow) * 100)
        return 0
    except:
        return 0

def get_weather_risk(location):
    api_key = "de72cae13f50a17d96fea286ebbbc238ffd051f3"
    try:
        lat, lon = location.split(',')
        url = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token={api_key}"
        response = requests.get(url)
        if response.status_code == 200:
            aqi = response.json().get('data', {}).get('aqi', 0)
            if aqi <= 50: return "Low"
            elif aqi <= 100: return "Moderate"
            else: return "High"
        return "Unknown"
    except:
        return "Unknown"

def calculate_emissions(distance, vehicle_type):
    factors = {"car": 0.21, "truck": 0.35, "bike": 0.05}
    return distance * factors.get(vehicle_type, 0.21)

def create_route_map(start, end, routes, selected_route):
    start_coords = [float(x) for x in start.split(",")]
    end_coords = [float(x) for x in end.split(",")]
    
    center_lat = (start_coords[0] + end_coords[0]) / 2
    center_lon = (start_coords[1] + end_coords[1]) / 2
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=6)
    
    # Add markers
    folium.Marker(start_coords, popup="Start", icon=folium.Icon(color="green")).add_to(m)
    folium.Marker(end_coords, popup="End", icon=folium.Icon(color="red")).add_to(m)
    
    # Add all routes with different colors
    colors = ['blue', 'red', 'green']
    for i, route in enumerate(routes):
        points = polyline.decode(route['geometry'])
        color = 'yellow' if i == selected_route else colors[i % len(colors)]
        dist = route['distance'] / 1000
        dur = route['duration'] / 60
        folium.PolyLine(
            points, 
            color=color, 
            weight=4 if i == selected_route else 2,
            popup=f"Route {i+1}: {dist:.1f}km, {dur:.0f}min"
        ).add_to(m)
    
    return m

st.title("Advanced Route Optimization System")

# Sidebar inputs
with st.sidebar:
    st.header("Route Settings")
    start = st.text_input("Start (lat,lon)", "37.7749,-122.4194")
    end = st.text_input("End (lat,lon)", "34.0522,-118.2437")
    vehicle_type = st.selectbox("Vehicle Type", ["car", "truck", "bike"])
    
    if st.button("Find Routes"):
        with st.spinner("Analyzing routes..."):
            routes = get_route_from_osrm(start, end)
            if routes:
                st.session_state.alternative_routes = routes
                st.session_state.route_data = routes[0]

if st.session_state.alternative_routes:
    # Create tabs for different views
    tab1, tab2, tab3 = st.tabs(["Route Map", "Route Comparison", "Environmental Impact"])
    
    with tab1:
        route_options = [f"Route {i+1}" for i in range(len(st.session_state.alternative_routes))]
        selected_route = st.selectbox("Select Route", range(len(route_options)), format_func=lambda x: route_options[x])
        
        map_data = create_route_map(start, end, st.session_state.alternative_routes, selected_route)
        st_folium(map_data, width=700, height=500)
    
    with tab2:
        # Create comparison dataframe
        routes_data = []
        traffic_delay = get_traffic_delay(start)
        weather_risk = get_weather_risk(start)
        
        for i, route in enumerate(st.session_state.alternative_routes):
            distance = route['distance'] / 1000
            duration = route['duration'] / 60
            fuel_cost = get_fuel_cost(distance, vehicle_type)
            emissions = calculate_emissions(distance, vehicle_type)
            
            routes_data.append({
                'Route': f'Route {i+1}',
                'Distance (km)': round(distance, 1),
                'Duration (min)': round(duration, 1),
                'Fuel Cost ($)': round(fuel_cost, 2),
                'Emissions (kg CO2)': round(emissions, 1),
                'Traffic Delay (%)': round(traffic_delay, 1),
                'Weather Risk': weather_risk
            })
        
        df = pd.DataFrame(routes_data)
        st.dataframe(df)
    
    with tab3:
        route = st.session_state.alternative_routes[selected_route]
        distance = route['distance'] / 1000
        
        # Compare emissions across vehicle types
        emissions_data = []
        for vtype in ['car', 'truck', 'bike']:
            emissions_data.append({
                'Vehicle': vtype.capitalize(),
                'Emissions': calculate_emissions(distance, vtype)
            })
        
        df_emissions = pd.DataFrame(emissions_data)
        fig = px.bar(df_emissions, x='Vehicle', y='Emissions', 
                    title='CO2 Emissions by Vehicle Type',
                    labels={'Emissions': 'CO2 Emissions (kg)'})
        st.plotly_chart(fig)

st.markdown("---")
st.write("FedEx SMART Hackathon 🚚 🌍")