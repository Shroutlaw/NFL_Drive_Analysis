import os
import pandas as pd
import dash
from dash import html, dcc, dash_table, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import plotly.express as px

# Initialize the app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

def load_single_season_data(season, folder_path="season_data"):
    file_path = os.path.join(folder_path, f"nfl_{season}.csv")
    if os.path.exists(file_path):
        return pd.read_csv(file_path, low_memory=False)
    return pd.DataFrame()

'''# Load Data all seasons on local device - will not work on render
def load_all_data(folder_path="season_data"):
    season_files = sorted([
        f for f in os.listdir(folder_path) if f.startswith("nfl_") and f.endswith(".csv")
    ])
    dfs = []
    for f in season_files:
        print(f"Loading {f}")
        df = pd.read_csv(os.path.join(folder_path, f), low_memory=False)
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)

df = load_all_data()
df['season'] = pd.to_numeric(df['season'], errors='coerce')

# Compute END GAME rows
end_games = df.sort_values(by=['game_id', 'play_id']).groupby('game_id').tail(1)

def classify_games(end_games):
    results = []
    for _, row in end_games.iterrows():
        game_id = row['game_id']
        spread = row['spread_line']
        home_team = row['home_team']
        away_team = row['away_team']
        home_score = row['total_home_score']
        away_score = row['total_away_score']
        season = row['season']

        if pd.isna(spread):
            continue

        if spread > 0:
            expected = home_team
        elif spread < 0:
            expected = away_team
        else:
            expected = 'Even'

        if home_score > away_score:
            actual = home_team
        elif away_score > home_score:
            actual = away_team
        else:
            actual = 'Tie'

        result_type = 'even_match'
        if expected == 'Even' or actual == 'Tie':
            result_type = 'even_match'
        elif expected == actual:
            result_type = 'confirmed_win'
        else:
            result_type = 'upset'

        spread_abs = abs(spread)
        results.append({
            'game_id': game_id,
            'season': season,
            'home_team': home_team,
            'away_team': away_team,
            'spread': spread,
            'expected_winner': expected,
            'actual_winner': actual,
            'result_type': result_type,
            'big_home_favorite_upset': result_type == 'upset' and spread > 6,
            'big_away_favorite_upset': result_type == 'upset' and spread < -6
        })

    return pd.DataFrame(results)

classified_df = classify_games(end_games)'''

# Load precomputed classification results (lightweight)
classified_df = pd.read_csv("season_data/classified_games.csv")
big_upsets = pd.read_csv("season_data/big_upsets.csv")

# Generate chart data
big_upsets = classified_df[classified_df['big_home_favorite_upset'] | classified_df['big_away_favorite_upset']]

# Pie 1: Total vs All Upsets
total_upsets = classified_df[classified_df['result_type'] == 'upset']
pie1_data = pd.DataFrame({
    'Category': ['All Other Games', 'Upsets'],
    'Count': [len(classified_df) - len(total_upsets), len(total_upsets)]
})
pie1 = px.pie(pie1_data, names='Category', values='Count', title='All Games vs Upsets')

# Pie 2: Upsets vs Big Spread Upsets
pie2_data = pd.DataFrame({
    'Category': ['Upsets < 6 Spread', 'Upsets ≥ 6 Spread'],
    'Count': [len(total_upsets) - len(big_upsets), len(big_upsets)]
})
pie2 = px.pie(pie2_data, names='Category', values='Count', title='Upsets by Spread Size')

# Pie 3: Big Spread Home vs Away
pie3_data = pd.DataFrame({
    'Category': ['Big Home Favorite Upsets', 'Big Away Favorite Upsets'],
    'Count': [
        big_upsets['big_home_favorite_upset'].sum(),
        big_upsets['big_away_favorite_upset'].sum()
    ]
})
pie3 = px.pie(pie3_data, names='Category', values='Count', title='Big Spread Upsets by Favored Team')

# Bar Chart: Upsets by Team
team_upsets = total_upsets.copy()
team_upsets['expected_winner_team'] = team_upsets['expected_winner']
team_upsets['big_spread_upset'] = team_upsets['game_id'].isin(big_upsets['game_id'])
team_count_data = team_upsets.groupby('expected_winner_team').agg(
    total_upsets=('game_id', 'count'),
    big_spread_upsets=('big_spread_upset', 'sum')
).reset_index()
bar_chart = px.bar(
    team_count_data, x='expected_winner_team', 
    y=['total_upsets', 'big_spread_upsets'],
    barmode='group',
    title='Upsets by Team (Expected Winners Who Lost)'
)

# Line chart: Upsets by Season
line_data = total_upsets['season'].value_counts().sort_index().reset_index()
line_data.columns = ['Season', 'Upset Count']
line_chart = px.line(line_data, x='Season', y='Upset Count', title='Upsets per Season')


app.layout = dbc.Container([
    html.H1("NFL Projected Win Analysis", className="text-center my-4"),

    dcc.Tabs([
        dcc.Tab(label='Charts Overview', children=[
            html.Div([
                html.H4("Storytelling with Data", className="mt-4"),
                html.P("These visualizations reveal trends in how often expected winners lose in the NFL. Each chart below adds a layer to that story."),
                dbc.Row([
                    dbc.Col(dcc.Graph(figure=pie1), style={'border': '1px solid #ccc', 'padding': '5px'}, width=4),
                    dbc.Col(dcc.Graph(figure=pie2), style={'border': '1px solid #ccc', 'padding': '5px'}, width=4),
                    dbc.Col(dcc.Graph(figure=pie3), style={'border': '1px solid #ccc', 'padding': '5px'}, width=4),
                ]),
                html.Br(),
                dbc.Row([
                    dbc.Col(dcc.Graph(figure=bar_chart), style={'border': '1px solid #ccc', 'padding': '5px'}, width=6),
                    dbc.Col(dcc.Graph(figure=line_chart), style={'border': '1px solid #ccc', 'padding': '5px'}, width=6),
                ])
            ])
        ]),

        dcc.Tab(label='Game Explorer', children=[
            html.Br(),
            html.Label("Select Game Type"),
            dcc.Dropdown(
                id='game_type',
                options=[
                    {'label': 'All Upsets', 'value': 'upsets'},
                    {'label': 'Home-Favored Upsets (Spread >= 6)', 'value': 'home_upsets'},
                    {'label': 'Away-Favored Upsets (Spread >= 6)', 'value': 'away_upsets'}
                ],
                value='upsets'
            ),

            html.Br(),
            html.Label("Select Season"),
            dcc.Dropdown(id='season_selector', placeholder="Filter by season (optional)"),

            html.Br(),
            html.H4("Games List (Most Recent First)"),
            dcc.Dropdown(id='game_selector', placeholder="Select a Game"),

            html.Br(),
            html.H4("Drive Plays (Select Drive Below to View)"),
            dash_table.DataTable(
                id='drive_plays',
                style_table={'overflowX': 'auto'},
                style_cell={'padding': '2px', 'fontSize': '13px'},
                style_data={'height': '25px'},
                style_cell_conditional=[
                    {'if': {'column_id': 'desc'}, 'textAlign': 'left'}
                ]
            ),

            html.Br(),
            html.H4("Drive Summary"),
            dash_table.DataTable(
                id='drive_table',
                style_table={'overflowX': 'auto'},
                style_cell={'padding': '2px', 'fontSize': '13px'},
                style_data={'height': '25px'}
            )
        ])
    ])
], fluid=True)

@app.callback(
    Output('season_selector', 'options'),
    Output('season_selector', 'value'),
    Input('game_type', 'value')
)
def update_season_dropdown(game_type):
    if game_type == 'upsets':
        filtered = classified_df[classified_df['result_type'] == 'upset']
    elif game_type == 'home_upsets':
        filtered = classified_df[classified_df['big_home_favorite_upset']]
    else:
        filtered = classified_df[classified_df['big_away_favorite_upset']]
    season_counts = filtered['season'].value_counts().sort_index(ascending=False)
    options = [{'label': f"{year} ({count} games)", 'value': year} for year, count in season_counts.items()]
    return options, no_update

@app.callback(
    Output('game_selector', 'options'),
    Input('game_type', 'value'),
    Input('season_selector', 'value')
)
def update_game_selector(game_type, season):
    if game_type == 'upsets':
        filtered = classified_df[classified_df['result_type'] == 'upset']
    elif game_type == 'home_upsets':
        filtered = classified_df[classified_df['big_home_favorite_upset']]
    else:
        filtered = classified_df[classified_df['big_away_favorite_upset']]

    if season:
        filtered = filtered[filtered['season'] == season]
    filtered = filtered.sort_values(by='season', ascending=False)
    return [{'label': f"{row['game_id']} - {row['expected_winner']} expected, {row['actual_winner']} won", 'value': row['game_id']} for _, row in filtered.iterrows()]

@app.callback(
    Output('drive_table', 'data'),
    Output('drive_table', 'columns'),
    Input('game_selector', 'value'),
    State('season_selector', 'value')
)
def display_drive_summary(game_id, season):
    #if not game_id:
    if not game_id or not season:
        return [], []

    #For single season on render:
    season_df = load_single_season_data(season)
    game_df = season_df[season_df['game_id'] == game_id].sort_values(by=['drive', 'play_id'])

    if game_df.empty:
        return [], []

    actual_winner = game_df.iloc[-1]['home_team'] if game_df.iloc[-1]['total_home_score'] > game_df.iloc[-1]['total_away_score'] else game_df.iloc[-1]['away_team']

    #For all seasons on render:
    #game_df = df[df['game_id'] == game_id].sort_values(by=['drive', 'play_id'])
    #actual_winner = classified_df[classified_df['game_id'] == game_id]['actual_winner'].values[0]

    drive_data = []
    for drive, group in game_df.groupby('drive'):
        posteam = group.iloc[0]['posteam']
        if actual_winner == group.iloc[0]['home_team']:
            start_wp = group.iloc[0]['home_wp'] if 'home_wp' in group.columns else group.iloc[0]['wp']
            end_wp = group.iloc[-1]['home_wp'] if 'home_wp' in group.columns else group.iloc[-1]['wp']
        else:
            start_wp = group.iloc[0]['away_wp'] if 'away_wp' in group.columns else group.iloc[0]['wp']
            end_wp = group.iloc[-1]['away_wp'] if 'away_wp' in group.columns else group.iloc[-1]['wp']

        drive_data.append({
            'drive': drive,
            'posteam': posteam,
            'defteam': group.iloc[0]['defteam'],
            'start_wp': start_wp,
            'end_wp': end_wp,
            'wp_change': round(end_wp - start_wp, 4),
            'yards_gained': group['yards_gained'].sum(),
            'total_home_score': group.iloc[-1]['total_home_score'],
            'total_away_score': group.iloc[-1]['total_away_score']
        })    
    columns = [{'name': col, 'id': col} for col in drive_data[0].keys()] if drive_data else []
    return drive_data, columns

@app.callback(
    Output('drive_plays', 'data'),
    Output('drive_plays', 'columns'),
    Input('drive_table', 'active_cell'),
    State('drive_table', 'data'),
    State('season_selector', 'value'),
    State('game_selector', 'value')

)
def display_drive_plays(active_cell, drive_data, season, game_id):
    #if not active_cell or not drive_data or not game_id:
    if not active_cell or not game_id or not season:
        return [], []

    drive_num = drive_data[active_cell['row']]['drive']

    season_df = load_single_season_data(season)
    game_df = season_df[season_df['game_id'] == game_id]
    drive_df = game_df[game_df['drive'] == drive_num]

    if drive_df.empty:
        return [], []

    selected_plays = drive_df[['play_id', 'qtr', 'time', 'posteam', 'desc', 'wp']]
    return selected_plays.to_dict('records'), [{'name': col, 'id': col} for col in selected_plays.columns]

    #For local machine all seasons
    #selected_drive = drive_data[active_cell['row']]['drive']
    #plays = df[(df['game_id'] == game_id) & (df['drive'] == selected_drive)][['play_id', 'qtr', 'time', 'posteam', 'desc', 'wp']]
    #return plays.to_dict('records'), [{'name': i, 'id': i} for i in plays.columns]

'''if __name__ == '__main__':
    app.run(debug=True, port=7777)'''

# Run on Render
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 7777))
    app.run(debug=False, dev_tools_ui=False, dev_tools_props_check=False,
            host='0.0.0.0', port=port)
