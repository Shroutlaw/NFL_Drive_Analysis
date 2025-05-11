import os
import pandas as pd
from dash import Dash, html, dcc, Input, Output
import plotly.express as px

# Load pre-saved full dataset (created and updated manually)
DATA_PATH = "data/nfl_play_by_play.csv"
df_full = pd.read_excel(DATA_PATH)

# Ensure types are correct
df_full['season'] = pd.to_numeric(df_full['season'], errors='coerce').astype('Int64')
df_full['week'] = pd.to_numeric(df_full['week'], errors='coerce').astype('Int64')

# Initialize Dash app
app = Dash(__name__)
app.title = "NFL Drive Explorer"

# Layout
app.layout = html.Div([
    html.H1("NFL Drive Explorer"),

    html.Label("Select Season:"),
    dcc.Dropdown(
        options=[{'label': str(s), 'value': s} for s in sorted(df_full['season'].dropna().unique())],
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
    dcc.Dropdown(id='game-dropdown', placeholder="Choose a game..."),

    html.Br(),

    html.Label("Select Drive:"),
    dcc.Dropdown(id='drive-dropdown', placeholder="Choose a drive..."),

    html.Br(),

    html.Div(id='drive-table'),

    html.Br(),

    dcc.Graph(id='wp-graph')
])

# Callback: Filter data for selected season
@app.callback(
    Output('game-dropdown', 'options'),
    [Input('season-dropdown', 'value'),
     Input('week-dropdown', 'value')]
)
def update_games_dropdown(season, week):
    if season is None or week is None:
        return []

    df = df_full[(df_full['season'] == season) & (df_full['week'] == week)]
    if df.empty:
        return []

    games = (
        df[['game_id', 'home_team', 'away_team']]
        .drop_duplicates()
        .assign(display=lambda x: x.apply(
            lambda row: f"{row['away_team']} @ {row['home_team']} (Week {str(week).zfill(2)}, {season})", axis=1))
    )

    return [{'label': row['display'], 'value': row['game_id']} for _, row in games.iterrows()]

# Callback: Drive dropdown
@app.callback(
    Output('drive-dropdown', 'options'),
    [Input('game-dropdown', 'value'),
     Input('season-dropdown', 'value'),
     Input('week-dropdown', 'value')]
)
def update_drive_options(game_id, season, week):
    if not game_id or season is None or week is None:
        return []

    df = df_full[(df_full['season'] == season) & (df_full['week'] == week) & (df_full['game_id'] == game_id)]
    drive_options = []

    for drive_num in sorted(df['drive'].dropna().unique()):
        drive_df = df[df['drive'] == drive_num]
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

        drive_options.append({'label': label, 'value': int(drive_num)})

    return drive_options

# Callback: Display drive info and graph
@app.callback(
    [Output('drive-table', 'children'),
     Output('wp-graph', 'figure')],
    [Input('game-dropdown', 'value'),
     Input('drive-dropdown', 'value'),
     Input('season-dropdown', 'value'),
     Input('week-dropdown', 'value')]
)
def display_drive_data(game_id, drive, season, week):
    if not game_id or drive is None or season is None or week is None:
        return html.Div("Please select a game and drive."), px.line(title="Win Probability (wp)")

    df = df_full[(df_full['season'] == season) & (df_full['week'] == week) & (df_full['game_id'] == game_id) & (df_full['drive'] == drive)]

    columns = [
        'posteam', 'defteam', 'yardline_100', 'drive', 'qtr', 'down',
        'ydstogo', 'yards_gained', 'play_type', 'epa', 'wp',
        'desc', 'total_away_score', 'total_home_score'
    ]

    df_display = df[columns]

    num_plays = len(df)
    epa_total = round(df['epa'].sum(), 2)
    wp_change = round(df['wp'].iloc[-1] - df['wp'].iloc[0], 4)
    total_yards = df['yards_gained'].sum()
    start_away_score = df['total_away_score'].iloc[0]
    start_home_score = df['total_home_score'].iloc[0]

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

    fig = px.line(df, x=df.index, y='wp', title='Win Probability During Drive')
    fig.update_layout(transition_duration=500)

    return table, fig

# Required for Render
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port, debug=False)
