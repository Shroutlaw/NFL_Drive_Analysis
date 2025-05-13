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
            df['drive'] = pd.to_numeric(df['drive'], errors='coerce').astype('Int64')
            df['season'] = pd.to_numeric(df['season'], errors='coerce').astype('Int64')
            df['week'] = pd.to_numeric(df['week'], errors='coerce').astype('Int64')
            season_cache[season] = df
    return season_cache.get(season)

app.layout = html.Div([
    html.H1("NFL Drive Explorer", style={'textAlign': 'center'}),

    # View mode toggle + season/week/game selectors
    html.Div([
        html.Label("View Mode:", style={'fontWeight': 'bold'}),
        dcc.RadioItems(
            id='view-mode',
            options=[
                {'label': 'Suggested', 'value': 'suggested'},
                {'label': 'Chronological', 'value': 'chronological'}
            ],
            value='suggested',
            labelStyle={'display': 'inline-block', 'marginRight': '15px'}
        ),
        html.Br(),

        html.Div([
            html.Div([
                html.Label("Season:"),
                dcc.Dropdown(
                    id='season-dropdown',
                    options=[{'label': str(s), 'value': s} for s in AVAILABLE_SEASONS],
                    placeholder="Select Season"
                )
            ], style={'width': '15%', 'display': 'inline-block', 'paddingRight': '10px'}),

            html.Div([
                html.Label("Week:"),
                dcc.Dropdown(
                    id='week-dropdown',
                    options=[{'label': f"Week {w}", 'value': w} for w in range(1, 19)],
                    placeholder="Select Week"
                )
            ], style={'width': '15%', 'display': 'inline-block', 'paddingRight': '10px'}),

            html.Div([
                html.Label("Game:"),
                dcc.Dropdown(id='game-dropdown', placeholder="Select Game")
            ], id='game-dropdown-container', style={'width': '40%', 'display': 'inline-block'}),
        ])
    ], style={
        'backgroundColor': 'white',
        'padding': '15px',
        'borderRadius': '8px',
        'marginBottom': '20px',
        'boxShadow': '0 0 8px rgba(0,0,0,0.1)'
    }),

    # Comparison scope dropdown
    html.Div([
        html.Label("Compare Against:", style={'fontWeight': 'bold'}),
        dcc.Dropdown(
            id='comparison-scope',
            options=[
                {'label': 'This Game', 'value': 'game'},
                {'label': 'This Week', 'value': 'week'},
                {'label': 'This Season', 'value': 'season'},
                {'label': 'All Drives', 'value': 'all'}
            ],
            value='game',
            style={'width': '300px'}
        )
    ], style={
        'backgroundColor': 'white',
        'padding': '15px',
        'borderRadius': '8px',
        'marginBottom': '20px',
        'boxShadow': '0 0 8px rgba(0,0,0,0.1)'
    }),

    # Drive selector (chronological or suggested)
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
            dcc.Dropdown(id='suggested-down-dropdown', placeholder="Choose a collapse drive...")
        ], id='suggested-container')
    ], style={
        'backgroundColor': 'white',
        'padding': '15px',
        'borderRadius': '8px',
        'marginBottom': '20px',
        'boxShadow': '0 0 8px rgba(0,0,0,0.1)'
    }),

    # Drive table (list of plays)
    html.Div(id='drive-table', style={
        'backgroundColor': 'white',
        'padding': '15px',
        'borderRadius': '8px',
        'marginBottom': '20px',
        'boxShadow': '0 0 8px rgba(0,0,0,0.1)'
    }),

    # Graphs section
    html.Div(id='wp-graph'),

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
     Input('suggested-down-dropdown', 'value'),
     Input('comparison-scope', 'value')],
    [State('season-dropdown', 'value'),
     State('week-dropdown', 'value'),
     State('view-mode', 'value'),
     State('game-dropdown', 'value')]
)
def display_drive_data(chron_drive, up_val, down_val, scope, season, week, view_mode, game_id):
    if not season or not week:
        return html.Div("Select a season and week."), html.Div()

    df = load_season_data(season)
    if df is None or df.empty:
        return html.Div("No data available."), html.Div()

    # Determine selected drive and game
    if view_mode == 'chronological':
        if not game_id or chron_drive is None:
            return html.Div("Select a drive."), html.Div()
        drive_df = df[(df['week'] == week) & (df['game_id'] == game_id) & (df['drive'] == int(chron_drive))]
    else:
        selected_val = up_val or down_val
        if not selected_val or '|' not in selected_val:
            return html.Div("Select a suggested drive."), html.Div()
        game_id, drive_num = selected_val.split("|")
        drive_df = df[(df['week'] == week) & (df['game_id'] == game_id) & (df['drive'] == int(drive_num))]

    if drive_df.empty:
        return html.Div("No data found for selected drive."), html.Div()

    # ---------- Build Table ----------
    columns = [
        'posteam', 'defteam', 'yardline_100', 'drive', 'qtr', 'time', 'down',
        'ydstogo', 'yards_gained', 'play_type', 'epa', 'wp',
        'desc', 'total_away_score', 'total_home_score'
    ]
    df_display = drive_df[columns]

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

    # ---------- Win Probability Graph ----------
    if 'qtr' in drive_df.columns and 'time' in drive_df.columns:
        x_labels = (drive_df['qtr'].astype(str).radd("Q") + " " + drive_df['time']).astype(str).tolist()
    else:
        x_labels = drive_df.index.astype(str).tolist()

    wp_fig = px.line(
        drive_df, x=x_labels, y='wp', title='Win Probability During Drive',
        labels={'x': 'Game Time', 'wp': 'Win Probability'}, markers=True
    )
    wp_fig.update_traces(line=dict(width=3, color='#1f77b4'), marker=dict(size=6))
    wp_fig.update_layout(height=400, yaxis=dict(range=[0, 1]), template='plotly_white')

    # ---------- Run vs Pass Mix ----------
    play_mix = drive_df[drive_df['play_type'].isin(['run', 'pass'])]
    play_counts = play_mix['play_type'].value_counts().reset_index()
    play_counts.columns = ['play_type', 'count']
    mix_fig = px.bar(play_counts, x='count', y='play_type', orientation='h', title='Run vs Pass Mix',
                     color='play_type', color_discrete_map={'run': '#2ca02c', 'pass': '#1f77b4'})
    mix_fig.update_layout(height=400)

    # ---------- Drive Summary Helper ----------
    def build_summary(df):
        plays = len(df)
        epa = df['epa'].sum()
        wpa = df['wpa'].sum()
        yds = df['yards_gained'].sum()
        run_plays = df[df['play_type'] == 'run'].shape[0]
        pass_plays = df[df['play_type'] == 'pass'].shape[0]
        total = run_plays + pass_plays
        return {
            'plays': plays,
            'epa': epa,
            'wpa': wpa,
            'yards': yds,
            'run_pct': run_plays / total if total else 0,
            'pass_pct': pass_plays / total if total else 0
        }

    def normalize(val, median):
        return val / median if median else 0

    # ---------- Comparison Group ----------
    if scope == 'game':
        comp_df = df[df['game_id'] == game_id]
    elif scope == 'week':
        comp_df = df[df['week'] == week]
    elif scope == 'season':
        comp_df = df
    else:
        comp_df = pd.concat(season_cache.values())

    summary_rows = []
    for _, g in comp_df.dropna(subset=['drive']).groupby(['game_id', 'drive']):
        summary_rows.append(build_summary(g))
    summary_df = pd.DataFrame(summary_rows)
    median_summary = summary_df.median()

    this_drive = build_summary(drive_df)

    # ---------- Radar Chart ----------
    radar_fig = go.Figure()
    radar_fig.add_trace(go.Scatterpolar(
        r=[
            normalize(this_drive['plays'], median_summary['plays']),
            normalize(this_drive['epa'], median_summary['epa']),
            normalize(this_drive['wpa'], median_summary['wpa']),
            normalize(this_drive['yards'], median_summary['yards']),
            normalize(this_drive['run_pct'], median_summary['run_pct']),
            normalize(this_drive['pass_pct'], median_summary['pass_pct']),
        ],
        theta=['# Plays', 'EPA', 'WPA', 'Yards', 'Run %', 'Pass %'],
        fill='toself', name='Selected Drive'
    ))
    radar_fig.add_trace(go.Scatterpolar(
        r=[1, 1, 1, 1, 1, 1],
        theta=['# Plays', 'EPA', 'WPA', 'Yards', 'Run %', 'Pass %'],
        fill='toself', name='Median Drive'
    ))
    radar_fig.update_layout(height=400, title='Drive Fingerprint vs Median',
                            polar=dict(radialaxis=dict(visible=True, range=[0, 2])))

    # ---------- EPA vs WPA Bubble Chart ----------
    bubble_data = summary_df.copy()
    bubble_data['size'] = bubble_data['yards']
    bubble_fig = px.scatter(
        bubble_data, x='epa', y='wpa', size='size',
        title='EPA vs WPA by Drive',
        labels={'epa': 'Expected Points Added', 'wpa': 'Win Probability Added'},
        opacity=0.6
    )
    bubble_fig.add_trace(go.Scatter(
        x=[this_drive['epa']], y=[this_drive['wpa']],
        mode='markers+text',
        marker=dict(size=14, color='red'),
        name='Selected Drive',
        text=["This Drive"], textposition='top center'
    ))
    bubble_fig.update_layout(height=400)

    # ---------- Layout Output ----------
    charts = html.Div([
        html.Div(dcc.Graph(figure=wp_fig), style={'width': '49%', 'display': 'inline-block'}),
        html.Div(dcc.Graph(figure=mix_fig), style={'width': '49%', 'display': 'inline-block'}),
        html.Div(dcc.Graph(figure=radar_fig), style={'width': '49%', 'display': 'inline-block'}),
        html.Div(dcc.Graph(figure=bubble_fig), style={'width': '49%', 'display': 'inline-block'})
    ])

    return table, charts

# Run on Render
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8050))
    app.run(debug=False, dev_tools_ui=False, dev_tools_props_check=False,
            host='0.0.0.0', port=port)
