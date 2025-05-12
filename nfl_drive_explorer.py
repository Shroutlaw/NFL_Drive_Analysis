import os
import pandas as pd
from dash import Dash, html, dcc, Input, Output
import plotly.express as px

# Initialize Dash app
app = Dash(__name__)
app.title = "NFL Drive Explorer"

# Define available seasons
AVAILABLE_SEASONS = list(range(1999, 2025))

# Local cache
season_cache = {}

# Layout
app.layout = html.Div([
    html.H1("NFL Drive Explorer"),

    html.Label("Select Season:"),
    dcc.Dropdown(
        options=[{'label': str(s), 'value': s} for s in AVAILABLE_SEASONS],
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

@app.callback(
    Output('game-dropdown', 'options'),
    [Input('season-dropdown', 'value'),
     Input('week-dropdown', 'value')]
)
def update_game_options(season, week):
    if season is None or week is None:
        return []

    if season not in season_cache:
        path = f"seasons/nfl_{season}.csv"
        if not os.path.exists(path):
            return []
        df = pd.read_csv(path)
        df['season'] = pd.to_numeric(df['season'], errors='coerce').astype('Int64')
        df['week'] = pd.to_numeric(df['week'], errors='coerce').astype('Int64')
        season_cache[season] = df
    else:
        df = season_cache[season]

    week_df = df[df['week'] == week]
    if week_df.empty:
        return []

    games = (
        week_df[['game_id', 'home_team', 'away_team']]
        .drop_duplicates()
        .assign(display=lambda x: x.apply(
            lambda row: f"{row['away_team']} @ {row['home_team']} (Week {str(week).zfill(2)}, {season})", axis=1))
    )

    return [{'label': row['display'], 'value': row['game_id']} for _, row in games.iterrows()]

@app.callback(
    Output('drive-dropdown', 'options'),
    [Input('game-dropdown', 'value'),
     Input('season-dropdown', 'value'),
     Input('week-dropdown', 'value')]
)
def update_drive_options(game_id, season, week):
    if not game_id or season is None or week is None or season not in season_cache:
        return []

    df = season_cache[season]
    df = df[(df['week'] == week) & (df['game_id'] == game_id)]

    drive_options = []
    for drive_num in sorted(df['drive'].dropna().unique()):
        drive_df = df[df['drive'] == drive_num]
        if drive_df.empty:
            continue

        num_plays = len(drive_df)
        epa_total = round(drive_df['epa'].sum(), 4)
        wpa_total = round(drive_df['wpa'].sum(), 4)
        total_yards = drive_df['yards_gained'].sum()
        start_away_score = int(drive_df['total_away_score'].iloc[0])
        start_home_score = int(drive_df['total_home_score'].iloc[0])

        label = (
            f"Drive {int(drive_num)} — Plays: {num_plays} | "
            f"EPA: {epa_total} | WPA: {wpa_total} | "
            f"Yards: {total_yards} | Score: {start_away_score}-{start_home_score}"
        )

        drive_options.append({'label': label, 'value': int(drive_num)})

    return drive_options

@app.callback(
    [Output('drive-table', 'children'),
     Output('wp-graph', 'figure')],
    [Input('game-dropdown', 'value'),
     Input('drive-dropdown', 'value'),
     Input('season-dropdown', 'value'),
     Input('week-dropdown', 'value')]
)
def display_drive_data(game_id, drive, season, week):
    if not game_id or drive is None or season is None or week is None or season not in season_cache:
        return html.Div("Please select a game and drive."), px.line(title="Win Probability (wp)")

    df = season_cache[season]
    df = df[(df['week'] == week) & (df['game_id'] == game_id) & (df['drive'] == drive)]

    columns = [
        'posteam', 'defteam', 'yardline_100', 'drive', 'qtr', 'down',
        'ydstogo', 'yards_gained', 'play_type', 'epa', 'wp',
        'desc', 'total_away_score', 'total_home_score'
    ]

    df_display = df[columns]

    table = html.Div([
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

# Run on Render-compatible port
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port, debug=False)
