import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.express as px
import json
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Carregar dados do arquivo JSON
with open('restaurantes_santos_sp.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

df = pd.json_normalize(data)

# Inicializar o Dash
app = dash.Dash(__name__)
app.title = "Restaurantes em Santos, SP"

# Layout do Dashboard
app.layout = html.Div([
    html.H1("Restaurantes em Santos, SP", style={'textAlign': 'center'}),
    html.Div([
        html.Div([
            html.Label("Filtrar por Bairro:"),
            dcc.Dropdown(
                id='bairro-filter',
                options=[{'label': bairro, 'value': bairro} for bairro in sorted(df['Neighborhood'].dropna().unique())],
                multi=True,
                placeholder="Selecione um ou mais bairros"
            ),
        ], style={'width': '30%', 'display': 'inline-block', 'verticalAlign': 'top', 'padding': '0 20px'}),
        
        html.Div([
            html.Label("Filtrar por Rua:"),
            dcc.Dropdown(
                id='rua-filter',
                options=[{'label': rua, 'value': rua} for rua in sorted(df['Street'].dropna().unique())],
                multi=True,
                placeholder="Selecione uma ou mais ruas"
            ),
        ], style={'width': '30%', 'display': 'inline-block', 'verticalAlign': 'top', 'padding': '0 20px'}),
        
        html.Div([
            html.Label("Filtrar por Avaliação:"),
            dcc.RangeSlider(
                id='rating-slider',
                min=0,
                max=5,
                step=0.1,
                value=[0, 5],
                marks={i: f'{i}' for i in range(6)},
                tooltip={"placement": "bottom", "always_visible": True}
            ),
        ], style={'width': '30%', 'display': 'inline-block', 'verticalAlign': 'top', 'padding': '0 20px'}),
    ], style={'padding': '20px'}),
    
    dcc.Graph(id='map-graph'),
    html.H2("Detalhes dos Restaurantes"),
    html.Div(id='table-container', style={'padding': '20px'})
], style={'fontFamily': 'Arial, sans-serif'})

# Callback para atualizar o gráfico e a tabela com base nos filtros
@app.callback(
    [Output('map-graph', 'figure'),
     Output('table-container', 'children')],
    [Input('bairro-filter', 'value'),
     Input('rua-filter', 'value'),
     Input('rating-slider', 'value')]
)
def update_dashboard(selected_bairros, selected_ruas, selected_ratings):
    filtered_df = df.copy()
    
    if selected_bairros:
        filtered_df = filtered_df[filtered_df['Neighborhood'].isin(selected_bairros)]
    
    if selected_ruas:
        filtered_df = filtered_df[filtered_df['Street'].isin(selected_ruas)]
    
    # Filtrar por avaliação
    filtered_df = filtered_df[
        (filtered_df['Rating'] >= selected_ratings[0]) & 
        (filtered_df['Rating'] <= selected_ratings[1])
    ]
    
    # Remover linhas sem localização
    filtered_df = filtered_df.dropna(subset=['Location.lat', 'Location.lng'])
    
    # Criar o mapa
    fig = px.scatter_mapbox(
        filtered_df,
        lat='Location.lat',
        lon='Location.lng',
        hover_name='Name',
        hover_data={
            'Rating': True,
            'Phone': True,
            'Neighborhood': True,
            'Street': True,
            'SocialLinks': False
        },
        color='Rating',
        size='UserRatingsTotal',
        color_continuous_scale='Viridis',
        size_max=15,
        zoom=12,
        height=600,
        title="Localização dos Restaurantes"
    )
    
    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin={"r":0,"t":40,"l":0,"b":0})
    
    # Criar a tabela
    table_columns = ["Name", "Address", "Neighborhood", "Street", "Rating", "Phone", "CompanySize"]
    table = dash.dash_table.DataTable(
        columns=[{"name": col, "id": col} for col in table_columns],
        data=filtered_df[table_columns].to_dict('records'),
        style_cell={
            'textAlign': 'left',
            'padding': '5px'
        },
        style_header={
            'backgroundColor': 'rgb(230, 230, 230)',
            'fontWeight': 'bold'
        },
        page_size=10,
        style_table={'overflowX': 'auto'},
    )
    
    return fig, table

if __name__ == '__main__':
    app.run_server(debug=True)
