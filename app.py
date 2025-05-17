import dash
from dash import dcc, html, Input, Output, State, dash_table
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, text
import pymysql

app = dash.Dash(__name__)
server = app.server  # <- ye Render ko batata hai ki server kaun sa hai
# ---------- SQLAlchemy Engine Setup ----------

def get_engine():
    try:
        engine = create_engine("mysql+pymysql://root:Paras%4015@127.0.0.1:3306/blood_b")
        return engine
    except Exception as e:
        print(f"Engine error: {e}")
        return None

# ---------- Pandas SQL Query via SQLAlchemy ----------
def fetch_dataframe(query, params=None):
    engine = get_engine()
    if not engine:
        return pd.DataFrame()
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)
        return df
    except Exception as e:
        print(f"Read SQL Error: {e}")
        return pd.DataFrame()

# ---------- Execute Insert/Update ----------
def execute_query(query, params=None):
    engine = get_engine()
    if not engine:
        return
    try:
        with engine.connect() as conn:
            conn.execute(text(query), params or {})
            conn.commit()
    except Exception as e:
        print(f"Write Query Error: {e}")

# ---------- Dash App ----------
app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "Blood Bank Management System"

app.layout = html.Div([
    html.H1("🧬 Blood Bank Management System", style={'textAlign': 'center'}),
    dcc.Tabs(id='tabs', value='view-donors', children=[
        dcc.Tab(label='View Donors', value='view-donors'),
        dcc.Tab(label='Add Donor', value='add-donor'),
        dcc.Tab(label='Blood Stock', value='blood-stock'),
        dcc.Tab(label='Search', value='search'),
        dcc.Tab(label='Analytics', value='analytics'),
    ]),
    html.Div(id='tab-content')
])

# ---------- Render Tabs ----------
@app.callback(Output('tab-content', 'children'), Input('tabs', 'value'))
def render_tab(tab):
    if tab == 'view-donors':
        df = fetch_dataframe("SELECT * FROM donors ORDER BY id DESC")
        return html.Div([
            html.H3("👥 Donor Records"),
            dash_table.DataTable(
                data=df.to_dict('records'),
                columns=[{"name": i, "id": i} for i in df.columns],
                page_size=10
            )
        ])
    elif tab == 'add-donor':
        return html.Div([
            html.H3("➕ Register New Donor"),
            html.Div(id='add-donor-msg'),
            dcc.Input(id='donor-name', type='text', placeholder='Full Name'),
            dcc.Input(id='donor-age', type='number', placeholder='Age'),
            dcc.Dropdown(
                id='donor-blood-group',
                options=[{'label': bg, 'value': bg} for bg in ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']],
                placeholder='Blood Group'
            ),
            dcc.Input(id='donor-contact', type='text', placeholder='Contact'),
            dcc.Input(id='donor-address', type='text', placeholder='Address'),
            dcc.DatePickerSingle(id='donor-last-donation', placeholder='Last Donation Date'),
            html.Button('Register Donor', id='submit-donor', n_clicks=0),
        ])
    elif tab == 'blood-stock':
        df = fetch_dataframe("SELECT * FROM blood_stock")
        fig = px.bar(df, x='blood_group', y='units', title="Blood Stock Levels", color='blood_group')
        return html.Div([
            html.H3("🩸 Blood Stock"),
            dash_table.DataTable(data=df.to_dict('records'),
                                 columns=[{"name": i, "id": i} for i in df.columns]),
            dcc.Graph(figure=fig)
        ])
    elif tab == 'search':
        return html.Div([
            html.H3("🔍 Search Donors"),
            dcc.RadioItems(
                id='search-type',
                options=[
                    {'label': 'Name', 'value': 'name'},
                    {'label': 'Blood Group', 'value': 'blood_group'}
                ],
                value='name',
                inline=True
            ),
            html.Div(id='search-input'),
            html.Div(id='search-results')
        ])
    elif tab == 'analytics':
        df = fetch_dataframe("SELECT age, blood_group FROM donors")
        fig1 = px.histogram(df, x='age', nbins=20, title="Age Distribution")
        fig2 = px.pie(df, names='blood_group', title="Blood Group Distribution")
        return html.Div([
            html.H3("📊 Donor Analytics"),
            dcc.Graph(figure=fig1),
            dcc.Graph(figure=fig2)
        ])

# ---------- Register Donor ----------
@app.callback(
    Output('add-donor-msg', 'children'),
    Input('submit-donor', 'n_clicks'),
    State('donor-name', 'value'),
    State('donor-age', 'value'),
    State('donor-blood-group', 'value'),
    State('donor-contact', 'value'),
    State('donor-address', 'value'),
    State('donor-last-donation', 'date'),
    prevent_initial_call=True
)
def add_donor(n_clicks, name, age, blood_group, contact, address, last_donation):
    if not name or not age or not blood_group or not contact:
        return html.Div("⚠️ Please fill all required fields.", style={'color': 'red'})
    try:
        if not last_donation:
            last_donation = pd.to_datetime('today').date()

        execute_query("""
            INSERT INTO donors (name, age, blood_group, contact, last_donation, address)
            VALUES (:name, :age, :blood_group, :contact, :last_donation, :address)
        """, {
            "name": name,
            "age": age,
            "blood_group": blood_group,
            "contact": contact,
            "last_donation": last_donation,
            "address": address
        })

        execute_query("UPDATE blood_stock SET units = units + 1 WHERE blood_group = :bg", {"bg": blood_group})

        return html.Div("✅ Donor registered successfully!", style={'color': 'green'})
    except Exception as e:
        return html.Div(f"❌ Error: {e}", style={'color': 'red'})

# ---------- Search Input Field ----------
@app.callback(
    Output('search-input', 'children'),
    Input('search-type', 'value')
)
def update_search_input(search_type):
    if search_type == 'name':
        return dcc.Input(id='search-dynamic', type='text', placeholder='Enter name', debounce=True)
    else:
        return dcc.Dropdown(
            id='search-dynamic',
            options=[{'label': bg, 'value': bg} for bg in ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']],
            placeholder='Select Blood Group'
        )

# ---------- Search Donors ----------
@app.callback(
    Output('search-results', 'children'),
    Input('search-dynamic', 'value'),
    State('search-type', 'value'),
)
def search_donors(value, search_type):
    if not value:
        return html.Div("Enter value to search.")
    if search_type == 'name':
        df = fetch_dataframe("SELECT * FROM donors WHERE name LIKE :val", {"val": f"%{value}%"})
    else:
        df = fetch_dataframe("SELECT * FROM donors WHERE blood_group = :val", {"val": value})

    if df.empty:
        return html.Div("No results found.")
    return dash_table.DataTable(data=df.to_dict('records'),
                                columns=[{"name": i, "id": i} for i in df.columns],
                                page_size=10)

# ---------- Run App ----------
if __name__ == '__main__':
    app.run_server(debug=True, host="0.0.0.0", port=8080)

