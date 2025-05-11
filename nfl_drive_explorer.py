import os
import pandas as pd
import nfl_data_py as nfl
from dash import Dash, html, dcc, Input, Output
import plotly.express as px

# Initialize Dash app
app = Dash(__name__)
app.title = "NFL Drive Explorer"

# Layout
app.layout = html.Div([
    html.H1("NFL Drive Explorer"),

    dcc.Store(id='season-data'),

    html.Label("Select Season:"),
    dcc.Dropdown(
        options=[{'label': str(s), 'value': s} for s in range(1999, 2025)],
        id='season-dropdown',
        placeholder="Choose a season..."
    ),

    html.Br(),

    html.Label("Select Week:"),
    dcc.Dropdown(
        id='week-dropdown',
        options=[{'label': f"Week {w}", 'value': w} for w in range(1, 19)],
        placeholder="Choose a week..."
    ),

    html.Br(),

    html.Label("Select Game:"),
    dcc.Loading(
        dcc.Dropdown(id='game-dropdown', placeholder="Choose a game..."),
        type="default"
    ),

    html.Br(),

    html.Label("Select Drive:"),
    dcc.Loading(
        dcc.Dropdown(id='drive-dropdown', placeholder="Choose a drive..."),
        type="default"
    ),

    html.Br(),

    dcc.Loading(
        html.Div(id='drive-table'),
        type="circle"
    ),

    html.Br(),

    dcc.Loading(
        dcc.Graph(id='wp-graph'),
        type="circle"
    )
])

# Load season data on selection
@app.callback(
    Output('season-data', 'data'),
    Input('season-dropdown', 'value')
)
def load_season_data(season):
    if season is None:
        return {}
    df = nfl.import_pbp_data([season])
    df = df[df['play_type'].notna()]
    df['season'] = df['season'].astype(int)
    df['week'] = pd.to_numeric(df['week'], errors='coerce').astype('Int64')
    return df.to_json(date_format='iso', orient='split')

# Update game dropdown based on season & week
@app.callback(
    Output('game-dropdown', 'options'),
    [Input('season-data', 'data'),
     Input('week-dropdown', 'value')]
)
def update_games_dropdown(json_data, week):
    if not json_data or week is None:
        return []

    df = pd.read_json(json_data, orient='split')
    df = df[df['week'] == week]

    if df.empty:
        return []

    game_info = (
        df[['game_id', 'season', 'week', 'home_team', 'away_team']]
        .drop_duplicates()
        .assign(display=lambda d: d.apply(
            lambda row: f"{row['away_team']} @ {row['home_team']} (Week {str(row['week']).zfill(2)}, {row['season']})", axis=1))
    )

    return [{'label': row['display'], 'value': row['game_id']} for _, row in game_info.iterrows()]

# Update drive dropdown with summaries
@app.callback(
    Output('drive-dropdown', 'options'),
    [Input('game-dropdown', 'value'),
     Input('season-data', 'data')]
)
def update_drive_options(game_id, json_data):
    if not game_id or not json_data:
        return []

    df = pd.read_json(json_data, orient='split')
    df = df[df['drive'].notna()]
    drive_summaries = []

    for drive_num in sorted(df[df['game_id'] == game_id]['drive'].unique()):
        drive_df = df[(df['game_id'] == game_id) & (df['drive'] == drive_num)]
        if drive_df.empty:
            continue

        num_plays = len(drive_df)
        epa_total = round(drive_df['epa'].sum(), 2)
        wp_change = round(drive_df['wp'].iloc[-1] - drive_df['wp'].iloc[0], 4)
        total_yards = drive_df['yards_gained'].sum()
        start_away_score = drive_df['total_away_score'].iloc[0]
        start_home_score = drive_df['total_home_score'].iloc[0]

        label = (
            f"Drive {int(drive_num)} — Plays: {num_plays} | "
            f"EPA: {epa_total} | ΔWP: {wp_change} | "
            f"Yards: {total_yards} | Score: {start_away_score}-{start_home_score}"
        )

        drive_summaries.append({'label': label, 'value': int(drive_num)})

    return drive_summaries

# Show drive summary and win probability graph
@app.callback(
    [Output('drive-table', 'children'),
     Output('wp-graph', 'figure')],
    [Input('game-dropdown', 'value'),
     Input('drive-dropdown', 'value'),
     Input('season-data', 'data')]
)
def display_drive_data(game_id, drive, json_data):
    if not game_id or drive is None or not json_data:
        return html.Div("Please select a game and drive."), px.line(title="Win Probability (wp)")

    df = pd.read_json(json_data, orient='split')

    columns = [
        'posteam', 'defteam', 'yardline_100', 'drive', 'qtr', 'down',
        'ydstogo', 'yards_gained', 'play_type', 'epa', 'wp',
        'desc', 'total_away_score', 'total_home_score'
    ]

    df_drive = df[(df['game_id'] == game_id) & (df['drive'] == drive)].copy()
    df_display = df_drive[columns]

    num_plays = len(df_drive)
    epa_total = round(df_drive['epa'].sum(), 2)
    wp_change = round(df_drive['wp'].iloc[-1] - df_drive['wp'].iloc[0], 4)
    total_yards = df_drive['yards_gained'].sum()
    start_away_score = df_drive['total_away_score'].iloc[0]
    start_home_score = df_drive['total_home_score'].iloc[0]

    drive_summary = html.Div([
        html.H4("Drive Summary"),
        html.Ul([
            html.Li(f"Total Plays: {num_plays}"),
            html.Li(f"Total EPA: {epa_total}"),
            html.Li(f"Change in Win Probability: {wp_change}"),
            html.Li(f"Total Yards Gained: {total_yards}"),
            html.Li(f"Start of Drive Score - Away: {start_away_score}, Home: {start_home_score}")
        ])
    ], style={'marginBottom': '20px'})

    table = html.Div([
        drive_summary,
        html.Table([
            html.Thead(html.Tr([html.Th(col) for col in columns])),
            html.Tbody([
                html.Tr([html.Td(df_display.iloc[i][col]) for col in columns])
                for i in range(len(df_display))
            ])
        ], style={
            'overflowX': 'scroll',
            'display': 'block',
            'maxHeight': '600px',
            'overflowY': 'scroll',
            'border': '1px solid black'
        })
    ])

    fig = px.line(df_drive, x=df_drive.index, y='wp', title='Win Probability During Drive')
    fig.update_layout(transition_duration=500)

    return table, fig

# Run with explicit host/port for Render
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port, debug=False)
