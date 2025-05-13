import os
import pandas as pd
from dash import Dash, html, dcc, Input, Output, State
import plotly.express as px

app = Dash(__name__)
app.title = "NFL Drive Explorer"

AVAILABLE_SEASONS = list(range(1999, 2025))
season_cache = {}

def load_season_data(season):
    if season not in season_cache:
        path = f"seasons/nfl_{season}.csv"
        if os.path.exists(path):
            df = pd.read_csv(path)
            df['season'] = pd.to_numeric(df['season'], errors='coerce').astype('Int64')
            df['week'] = pd.to_numeric(df['week'], errors='coerce').astype('Int64')
            season_cache[season] = df
    return season_cache.get(season)

app.layout = html.Div([
    html.H1("NFL Drive Explorer", style={'textAlign': 'center'}),

    # Top container: mode toggle and dropdowns
    html.Div([
        html.Div([
            html.Label("View Mode:"),
            dcc.RadioItems(
                id='view-mode',
                options=[
                    {'label': 'Suggested', 'value': 'suggested'},
                    {'label': 'Chronological', 'value': 'chronological'}
                ],
                value='suggested',
                labelStyle={'display': 'inline-block', 'marginRight': '15px'}
            )
        ], style={'marginBottom': '10px'}),

        html.Div([
            html.Div([
                html.Label("Season:"),
                dcc.Dropdown(
                    options=[{'label': str(s), 'value': s} for s in AVAILABLE_SEASONS],
                    id='season-dropdown',
                    placeholder="Season"
                )
            ], style={'width': '15%', 'display': 'inline-block', 'paddingRight': '10px'}),

            html.Div([
                html.Label("Week:"),
                dcc.Dropdown(
                    id='week-dropdown',
                    options=[{'label': f"Week {w}", 'value': w} for w in range(1, 19)],
                    placeholder="Week"
                )
            ], style={'width': '15%', 'display': 'inline-block', 'paddingRight': '10px'}),

            html.Div([
                html.Label("Game:"),
                dcc.Dropdown(id='game-dropdown', placeholder="Game")
            ], id='game-dropdown-container', style={'width': '40%', 'display': 'inline-block', 'paddingRight': '10px'}),
        ]),
    ], style={
        'backgroundColor': 'white',
        'padding': '15px',
        'borderRadius': '8px',
        'marginBottom': '20px',
        'boxShadow': '0 0 8px rgba(0,0,0,0.1)'
    }),

    # Drive selection (Chron or Suggested)
    html.Div([
        html.Div([
            html.Label("Drive (Chronological):"),
            dcc.Dropdown(id='drive-dropdown', placeholder="Choose a drive...")
        ], id='chronological-container'),
        html.Div([
            html.H3("Turning the Tides"),

            html.Label("Expected Loss ➜ Expected Win:"),
            dcc.Dropdown(id='suggested-up-dropdown', placeholder="Choose a swing drive..."),

            html.Br(),

            html.Label("Expected Win ➜ Expected Loss:"),
            dcc.Dropdown(id='suggested-down-dropdown', placeholder="Choose a collapse drive..."),
        ], id='suggested-container')
    ], style={
        'backgroundColor': 'white',
        'padding': '15px',
        'borderRadius': '8px',
        'marginBottom': '20px',
        'boxShadow': '0 0 8px rgba(0,0,0,0.1)'
    }),

    # Table of plays
    html.Div(id='drive-table', style={
        'backgroundColor': 'white',
        'padding': '15px',
        'borderRadius': '8px',
        'marginBottom': '20px',
        'boxShadow': '0 0 8px rgba(0,0,0,0.1)'
    }),

    # Graphs
    html.Div(id='wp-graph')
], style={'backgroundColor': '#f4f4f4', 'padding': '30px'})

@app.callback(
    [Output('chronological-container', 'style'),
     Output('suggested-container', 'style'),
     Output('game-dropdown-container', 'style')],
    Input('view-mode', 'value')
)
def toggle_view_mode(view_mode):
    if view_mode == 'chronological':
        return (
            {'display': 'block'},
            {'display': 'none'},
            {'display': 'inline-block', 'width': '40%', 'paddingRight': '10px'}
        )
    else:
        return (
            {'display': 'none'},
            {'display': 'block'},
            {'display': 'none'}
        )

@app.callback(
    Output('drive-dropdown', 'options'),
    [Input('game-dropdown', 'value'),
     Input('season-dropdown', 'value'),
     Input('week-dropdown', 'value')]
)
def update_drive_options(game_id, season, week):
    if not game_id or season is None or week is None:
        return []

    df = load_season_data(season)
    if df is None:
        return []

    df = df[(df['week'] == week) & (df['game_id'] == game_id)]
    options = []
    for drive_num in sorted(df['drive'].dropna().unique()):
        drive_df = df[df['drive'] == drive_num]
        if drive_df.empty:
            continue
        epa = round(drive_df['epa'].sum(), 4)
        wpa = round(drive_df['wpa'].sum(), 4) if 'wpa' in drive_df else 0.0
        yds = drive_df['yards_gained'].sum()
        a_score = int(drive_df['total_away_score'].iloc[0])
        h_score = int(drive_df['total_home_score'].iloc[0])
        o = drive_df['posteam'].iloc[0]
        d = drive_df['defteam'].iloc[0]
        label = (
            f"Drive {int(drive_num):<3} | WPA: {wpa:<8} | EPA: {epa:<8} | "
            f"Yds: {yds:<4} | Score: AWY {a_score} - {h_score} HOM | "
            f"O: {o} vs D: {d}"
        )
        options.append({'label': label, 'value': int(drive_num)})
    return options

@app.callback(
    Output('game-dropdown', 'options'),
    [Input('season-dropdown', 'value'),
     Input('week-dropdown', 'value')]
)
def update_games_dropdown(season, week):
    if season is None or week is None:
        return []

    df = load_season_data(season)
    if df is None:
        return []

    df = df[df['week'] == week]

    games = (
        df[['game_id', 'home_team', 'away_team']]
        .drop_duplicates()
        .assign(display=lambda x: x.apply(
            lambda row: f"{row['away_team']} @ {row['home_team']} ({row['game_id']})", axis=1))
    )

    return [{'label': row['display'], 'value': row['game_id']} for _, row in games.iterrows()]

@app.callback(
    [Output('suggested-up-dropdown', 'options'),
     Output('suggested-down-dropdown', 'options')],
    [Input('season-dropdown', 'value'),
     Input('week-dropdown', 'value')]
)
def update_suggested_drives(season, week):
    if season is None or week is None:
        return [], []

    df = load_season_data(season)
    if df is None:
        return [], []

    df = df[df['week'] == week]
    up, down = [], []

    for game_id in df['game_id'].unique():
        game_df = df[df['game_id'] == game_id]
        for drive_num in game_df['drive'].dropna().unique():
            drive_df = game_df[game_df['drive'] == drive_num]
            if drive_df.empty:
                continue
            start_wp = drive_df['wp'].iloc[0]
            end_wp = drive_df['wp'].iloc[-1]
            if start_wp < 0.5 and end_wp > 0.5:
                category = up
            elif start_wp > 0.5 and end_wp < 0.5:
                category = down
            else:
                continue
            epa = round(drive_df['epa'].sum(), 4)
            wpa = round(drive_df['wpa'].sum(), 4) if 'wpa' in drive_df else 0.0
            yds = drive_df['yards_gained'].sum()
            a_score = int(drive_df['total_away_score'].iloc[0])
            h_score = int(drive_df['total_home_score'].iloc[0])
            o = drive_df['posteam'].iloc[0]
            d = drive_df['defteam'].iloc[0]
            label = (
                f"{game_id} | Drive {int(drive_num):<3} | WPA: {wpa:<8} | EPA: {epa:<8} | "
                f"Yds: {yds:<4} | Score: AWY {a_score} - {h_score} HOM | "
                f"O: {o} vs D: {d}"
            )
            category.append({'label': label, 'value': f"{game_id}|{int(drive_num)}"})
    return up, down

@app.callback(
    [Output('drive-table', 'children'),
     Output('wp-graph', 'children')],
    [Input('drive-dropdown', 'value'),
     Input('suggested-up-dropdown', 'value'),
     Input('suggested-down-dropdown', 'value')],
    [State('season-dropdown', 'value'),
     State('week-dropdown', 'value'),
     State('view-mode', 'value'),
     State('game-dropdown', 'value')]
)
def display_drive_data(chron_drive, up_val, down_val, season, week, view_mode, game_id):
    if season is None or week is None:
        return html.Div("Select inputs."), html.Div()

    df = load_season_data(season)
    if df is None:
        return html.Div("No data."), html.Div()

    if view_mode == 'chronological':
        if chron_drive is None or game_id is None:
            return html.Div("Select a drive."), html.Div()
        df = df[(df['week'] == week) & (df['game_id'] == game_id) & (df['drive'] == chron_drive)]
    else:
        val = up_val or down_val
        if not val:
            return html.Div("Select a suggested drive."), html.Div()
        game_id, drive_num = val.split("|")
        df = df[(df['week'] == week) & (df['game_id'] == game_id) & (df['drive'] == int(drive_num))]

    # ----------- TABLE OF PLAYS -----------
    columns = [
        'posteam', 'defteam', 'yardline_100', 'drive', 'qtr', 'down',
        'ydstogo', 'yards_gained', 'play_type', 'epa', 'wp',
        'desc', 'total_away_score', 'total_home_score'
    ]
    df_display = df[columns]

    table = html.Div([
        html.Table([
            html.Thead(html.Tr([
                html.Th(col, style={'border': '1px solid #ddd', 'padding': '8px', 'backgroundColor': '#f0f0f0'})
                for col in columns
            ])),
            html.Tbody([
                html.Tr([
                    html.Td(df_display.iloc[i][col], style={'border': '1px solid #ddd', 'padding': '8px'})
                    for col in columns
                ], style={'backgroundColor': '#f9f9f9' if i % 2 == 0 else 'white'})
                for i in range(len(df_display))
            ])
        ], style={
            'width': '100%',
            'borderCollapse': 'collapse',
            'fontSize': '14px'
        })
    ])

    # ----------- WIN PROBABILITY CHART -----------
    if 'qtr' in df.columns and 'game_clock' in df.columns:
        x_labels = (df['qtr'].astype(str).radd("Q") + " " + df['game_clock']).astype(str).tolist()
    else:
        x_labels = df.index.astype(str).tolist()

    wp_fig = px.line(
        df,
        x=x_labels,
        y='wp',
        title='Win Probability During Drive',
        labels={'x': 'Game Time (Quarter + Clock)', 'wp': 'Win Probability'},
        markers=True
    )

    wp_fig.update_traces(
        line=dict(width=3, color='#1f77b4'),
        marker=dict(size=6),
        hovertemplate="<b>Time:</b> %{x}<br><b>WP:</b> %{y:.3f}<extra></extra>"
    )

    wp_fig.update_layout(
        title_font_size=22,
        xaxis_title="Game Time (Quarter + Clock)",
        yaxis_title="Win Probability",
        yaxis=dict(range=[0, 1]),
        template='plotly_white',
        hovermode='x unified',
        margin=dict(l=40, r=30, t=50, b=40),
        height=400
    )

    # ----------- RUN VS PASS CHART -----------
    play_mix_df = df[df['play_type'].isin(['run', 'pass'])]
    play_counts = play_mix_df['play_type'].value_counts().reset_index()
    play_counts.columns = ['play_type', 'count']

    mix_fig = px.bar(
        play_counts,
        x='count',
        y='play_type',
        orientation='h',
        title='Run vs Pass Mix',
        labels={'count': 'Play Count', 'play_type': 'Play Type'},
        color='play_type',
        color_discrete_map={'run': '#2ca02c', 'pass': '#1f77b4'}
    )

    mix_fig.update_layout(
        title_font_size=20,
        margin=dict(l=20, r=20, t=50, b=20),
        height=400
    )

    # ----------- COMBINE CHARTS SIDE BY SIDE -----------
    charts = html.Div([
        html.Div(dcc.Graph(figure=wp_fig), style={'width': '60%', 'display': 'inline-block', 'verticalAlign': 'top'}),
        html.Div(dcc.Graph(figure=mix_fig), style={'width': '38%', 'display': 'inline-block', 'paddingLeft': '2%'})
    ])

    return table, charts

# Run on Render
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8050))
    app.run(debug=False, dev_tools_ui=False, dev_tools_props_check=False,
            host='0.0.0.0', port=port)
