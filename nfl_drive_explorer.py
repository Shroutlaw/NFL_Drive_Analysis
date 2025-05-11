import os
import pandas as pd
import nfl_data_py as nfl
from dash import Dash, html, dcc, Input, Output
import plotly.express as px

# === CONFIG ===
DATA_PATH = "pbp_data.parquet"
REFRESH_DATA = False

# === LOAD OR DOWNLOAD DATA ===
if REFRESH_DATA or not os.path.exists(DATA_PATH):
    print("Downloading play-by-play data...")
    pbp_df = nfl.import_pbp_data(years=list(range(2022, 2025)))
    pbp_df = pbp_df[pbp_df['play_type'].notna()]
    pbp_df.to_parquet(DATA_PATH)
else:
    print("Loading cached data...")
    pbp_df = pd.read_parquet(DATA_PATH)

# === EXTRACT SEASON AND WEEK LIST ===
pbp_df['season'] = pbp_df['season'].astype(int)
pbp_df['week'] = pbp_df['week'].astype(int)
seasons = sorted(pbp_df['season'].unique())
weeks = sorted(pbp_df['week'].unique())

# === PREP GAME DROPDOWN FORMAT ===
def get_game_display(row):
    return f"{row['away_team']} @ {row['home_team']} (Week {str(row['week']).zfill(2)}, {row['season']})"

game_info = (
    pbp_df[['game_id', 'season', 'week', 'home_team', 'away_team']]
    .drop_duplicates()
    .assign(display=lambda df: df.apply(get_game_display, axis=1))
)

# === INITIALIZE DASH APP ===
app = Dash(__name__)
app.title = "NFL Drive Explorer"

app.layout = html.Div([
    html.H1("NFL Drive Explorer"),

    html.Label("Select Season:"),
    dcc.Dropdown(
        options=[{'label': str(s), 'value': s} for s in seasons],
        id='season-dropdown',
        placeholder="Choose a season..."
    ),

    html.Br(),

    html.Label("Select Week:"),
    dcc.Dropdown(
        options=[{'label': f"Week {w}", 'value': w} for w in weeks],
        id='week-dropdown',
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

# === CALLBACK: UPDATE GAMES BASED ON SEASON & WEEK ===
@app.callback(
    Output('game-dropdown', 'options'),
    [Input('season-dropdown', 'value'),
     Input('week-dropdown', 'value')]
)
def update_games_dropdown(season, week):
    if season is None or week is None:
        return []

    filtered = game_info[(game_info['season'] == season) & (game_info['week'] == week)]
    return [{'label': row['display'], 'value': row['game_id']} for _, row in filtered.iterrows()]

# === CALLBACK: UPDATE DRIVE OPTIONS ===
@app.callback(
    Output('drive-dropdown', 'options'),
    Input('game-dropdown', 'value')
)
def update_drive_options(game_id):
    if not game_id:
        return []

    df = pbp_df[pbp_df['game_id'] == game_id].copy()
    df = df[df['drive'].notna()]
    drive_summaries = []

    for drive_num in sorted(df['drive'].unique()):
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

        drive_summaries.append({'label': label, 'value': int(drive_num)})

    return drive_summaries

# === CALLBACK: SHOW DRIVE DETAILS ===
@app.callback(
    [Output('drive-table', 'children'),
     Output('wp-graph', 'figure')],
    [Input('game-dropdown', 'value'),
     Input('drive-dropdown', 'value')]
)
def display_drive_data(game_id, drive):
    if not game_id or drive is None:
        return html.Div("Please select a game and drive."), px.line(title="Win Probability (wp)")

    columns = [
        'posteam', 'defteam', 'yardline_100', 'drive', 'qtr', 'down',
        'ydstogo', 'yards_gained', 'play_type', 'epa', 'wp',
        'desc', 'total_away_score', 'total_home_score'
    ]

    df = pbp_df[(pbp_df['game_id'] == game_id) & (pbp_df['drive'] == drive)].copy()
    df_display = df[columns]

    # === DRIVE SUMMARY ===
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

    # === TABLE ===
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

    # === GRAPH ===
    fig = px.line(df, x=df.index, y='wp', title='Win Probability During Drive')
    fig.update_layout(transition_duration=500)

    return table, fig

# === RUN APP ===
if __name__ == '__main__':
    app.run(debug=True)
