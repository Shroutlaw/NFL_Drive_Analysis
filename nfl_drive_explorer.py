import os
import pandas as pd
from dash import Dash, html, dcc, Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
import nfl_data_py as nfl

app = Dash(__name__)
app.title = "NFL Drive Explorer"

AVAILABLE_SEASONS = list(range(1999, 2025))
season_cache = {}

team_info = pd.read_csv("team_info.csv")

# Define metric pairs
metric_pairs = {
    "Air Yards": ("air_epa", "air_wpa"),
    "Yards After Catch": ("yac_epa", "yac_wpa"),
    "Completions Air": ("comp_air_epa", "comp_air_wpa"),
    "Completions YAC": ("comp_yac_epa", "comp_yac_wpa"),
    "Total Rush": ("total_home_rush_epa", "total_home_rush_wpa"),
    "Total Pass": ("total_home_pass_epa", "total_home_pass_wpa"),
}

def load_season_data(season):
    if season not in season_cache:
        path = f"seasons/nfl_{season}.csv"
        if os.path.exists(path):
            df = pd.read_csv(path)
            df['season'] = pd.to_numeric(df['season'], errors='coerce').astype('Int64')
            df['week'] = pd.to_numeric(df['week'], errors='coerce').astype('Int64')
            season_cache[season] = df
    return season_cache.get(season)

def load_multiple_seasons(seasons):
    if not isinstance(seasons, list):
        seasons = [seasons]
    dataframes = [load_season_data(s) for s in seasons if load_season_data(s) is not None]
    if dataframes:
        return pd.concat(dataframes, ignore_index=True)
    return pd.DataFrame()

app.layout = html.Div([
    html.H1("NFL Dashboard"),

    # View toggle
    html.Div([
        html.Label("View Mode:"),
        dcc.RadioItems(
            id='view-mode',
            options=[
                {'label': 'EPA/WPA Dashboard', 'value': 'epa/wpa'},
                {'label': 'Suggested', 'value': 'suggested'},
                {'label': 'Chronological', 'value': 'chronological'}
            ],
            value='epa/wpa',
            labelStyle={'display': 'inline-block', 'marginRight': '15px'}
        )
    ], style={'marginBottom': '20px'}),

    # Shared: Season and Week only
    html.Div([
        html.Div([
            html.Label("Season:"),
            dcc.Dropdown(
                id='season-dropdown',
                options=[],  # populated by callback
                value=2024,
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
        ], style={'width': '15%', 'display': 'inline-block', 'paddingRight': '10px'})
    ], style={'marginBottom': '20px'}),

    # EPA/WPA Dashboard View
    html.Div([
        html.H2("NFL Team EPA vs WPA"),
        html.Label("Select Metric Category:"),
        dcc.Dropdown(
            id='metric-pair',
            options=[{'label': k, 'value': k} for k in metric_pairs],
            value="Air Yards"
        ),
        dcc.Graph(id='logo-scatter')
    ], id='epa-wpa-container', style={'marginBottom': '30px'}),

    # Suggested View
    html.Div([
        html.H3("Turning the Tides"),

        html.Label("Expected Loss ➜ Expected Win:"),
        dcc.Dropdown(id='suggested-up-dropdown', placeholder="Choose a swing drive..."),

        html.Br(),

        html.Label("Expected Win ➜ Expected Loss:"),
        dcc.Dropdown(id='suggested-down-dropdown', placeholder="Choose a collapse drive...")

    ], id='suggested-container', style={'marginBottom': '20px'}),

    # Chronological View
    html.Div([
        html.Div([
            html.Label("Game:"),
            dcc.Dropdown(id='game-dropdown', placeholder="Game")
        ], style={'width': '40%', 'display': 'inline-block', 'paddingRight': '10px'}),

        html.Div([
            html.Label("Drive (Chronological):"),
            dcc.Dropdown(id='drive-dropdown', placeholder="Choose a drive...")
        ], style={'width': '48%', 'display': 'inline-block', 'marginTop': '10px'})
    ], id='chronological-container', style={'marginBottom': '20px'}),

    # Drive Table and Charts
    html.Div(id='drive-visuals-container', children=[
        html.Div(id='drive-table'),
        html.Br(),
        html.Div(id='chart-container')
    ])
])

@app.callback(
    Output('logo-scatter', 'figure'),
    Input('metric-pair', 'value'),
    Input('season-dropdown', 'value')
)
def update_graph(selected_pair, season):
    if season is None:
        return go.Figure()

    df = load_season_data(season)
    if df is None or df.empty:
        return go.Figure()
    epa_field, wpa_field = metric_pairs[selected_pair]

    if "total_home" in epa_field:
        home_df = df[df["posteam"] == df["home_team"]][["posteam", epa_field, wpa_field]]
        away_df = df[df["posteam"] == df["away_team"]][["posteam", 
            epa_field.replace("home", "away"), 
            wpa_field.replace("home", "away")]]
        away_df.columns = home_df.columns
        combined = pd.concat([home_df, away_df]).dropna()
    else:
        combined = df.dropna(subset=[epa_field, wpa_field, "posteam"])
        combined = combined[["posteam", epa_field, wpa_field]]

    team_stats = combined.groupby("posteam").mean().reset_index()
    team_stats.columns = ["Team", "Avg_EPA", "Avg_WPA"]
    team_stats = team_stats.merge(team_info, how="left", left_on="Team", right_on="team_abbr")

    # Create figure and add logos
    fig = go.Figure()

    # Calculate axis range
    x_min, x_max = team_stats["Avg_WPA"].min(), team_stats["Avg_WPA"].max()
    y_min, y_max = team_stats["Avg_EPA"].min(), team_stats["Avg_EPA"].max()
    sizex = (x_max - x_min) * 0.04
    sizey = (y_max - y_min) * 0.04

    # Add logos as images
    for _, row in team_stats.iterrows():
        fig.add_layout_image(
            dict(
                source=row["team_logo_espn"],
                x=row["Avg_WPA"],
                y=row["Avg_EPA"],
                xref="x",
                yref="y",
                sizex=sizex,
                sizey=sizey,
                xanchor="center",
                yanchor="middle",
                layer="above"
            )
        )

    # Add invisible scatter for hover/axis scaling
    fig.add_trace(go.Scatter(
        x=team_stats["Avg_WPA"],
        y=team_stats["Avg_EPA"],
        mode="markers+text",
        text=team_stats["Team"],
        textposition="top center",
        marker=dict(size=5, opacity=0),
        hovertext=[
            f"{row['Team']}<br>EPA: {row['Avg_EPA']:.3f}<br>WPA: {row['Avg_WPA']:.3f}"
            for _, row in team_stats.iterrows()
        ],
        hoverinfo="text"
    ))

    fig.update_layout(
        title=f"{selected_pair} — Average EPA vs WPA by Team (Logos)",
        xaxis_title="Average WPA",
        yaxis_title="Average EPA",
        xaxis=dict(showgrid=True, zeroline=True),
        yaxis=dict(showgrid=True, zeroline=True),
        plot_bgcolor="white",
        margin=dict(l=10, r=10, t=10, b=10),
        height=600
    )

    return fig

@app.callback(
    [Output('epa-wpa-container', 'style'),
     Output('suggested-container', 'style'),
     Output('chronological-container', 'style'),
     Output('drive-visuals-container', 'style')],
    Input('view-mode', 'value')
)
def toggle_view_mode(view_mode):
    if view_mode == 'epa/wpa':
        return (
            {'display': 'block'},
            {'display': 'none'},
            {'display': 'none'},
            {'display': 'none'}
        )
    elif view_mode == 'suggested':
        return (
            {'display': 'none'},
            {'display': 'block'},
            {'display': 'none'},
            {'display': 'block'}
        )
    elif view_mode == 'chronological':
        return (
            {'display': 'none'},
            {'display': 'none'},
            {'display': 'block'},
            {'display': 'block'}
        )

@app.callback(
    Output('season-dropdown', 'options'),
    Input('view-mode', 'value')
)
def update_season_dropdown(view_mode):
    if view_mode is None:
        view_mode = 'epa/wpa'

    return [
        {
            'label': str(year),
            'value': year,
            'disabled': True if view_mode == 'epa/wpa' and year < 2006 else False
        }
        for year in range(1999, 2025)
    ]

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
    Output('drive-table', 'children'),
    Output('chart-container', 'children'),
    Input('drive-dropdown', 'value'),
    Input('suggested-up-dropdown', 'value'),
    Input('suggested-down-dropdown', 'value'),
    Input('season-dropdown', 'value'),
    Input('week-dropdown', 'value'),
    Input('view-mode', 'value'),
    Input('game-dropdown', 'value')
)
def display_drive_data(chron_drive, up_val, down_val, season, week, view_mode, game_id):
    if not season or not week:
        return html.Div("Select inputs."), None

    df = load_season_data(season)
    if df is None:
        return html.Div("No data available."), None

    # Filter drive
    if view_mode == 'chronological':
        if not chron_drive or not game_id:
            return html.Div("Select a drive."), None
        drive_df = df[(df['week'] == week) & (df['game_id'] == game_id) & (df['drive'] == chron_drive)]
    else:
        val = up_val or down_val
        if not val:
            return html.Div("Select a suggested drive."), None
        game_id, drive_num = val.split("|")
        drive_df = df[(df['week'] == week) & (df['game_id'] == game_id) & (df['drive'] == int(drive_num))]

    if drive_df.empty:
        return html.Div("No data for selected drive."), None

    # Display Table
    columns = ['posteam', 'defteam', 'yardline_100', 'drive', 'qtr', 'time', 'down', 'ydstogo',
               'yards_gained', 'play_type', 'epa', 'wp', 'desc', 'total_away_score', 'total_home_score']
    table_df = drive_df[columns]
    table = html.Div([
        html.Table([
            html.Thead(html.Tr([html.Th(col) for col in columns])),
            html.Tbody([
                html.Tr([html.Td(table_df.iloc[i][col]) for col in columns])
                for i in range(len(table_df))
            ])
        ], style={'border': '1px solid black', 'overflowY': 'scroll', 'maxHeight': '500px', 'display': 'block'})
    ])

    # Win Probability Graph
    if 'qtr' in drive_df.columns and 'time' in drive_df.columns:
        x_labels = drive_df['qtr'].astype(str).radd("Q") + " " + drive_df['time']
    else:
        x_labels = drive_df.index.astype(str)

    wp_fig = px.line(
        drive_df, x=x_labels, y='wp', title='Win Probability During Drive',
        labels={'x': 'Time', 'wp': 'Win Probability'}, markers=True
    )

    # Play Mix Bar Chart
    mix_df = drive_df[drive_df['play_type'].isin(['run', 'pass'])]
    mix_counts = mix_df['play_type'].value_counts().reset_index()
    mix_counts.columns = ['play_type', 'count']
    mix_fig = px.bar(
        mix_counts, x='count', y='play_type', orientation='h',
        title='Run vs Pass Mix', color='play_type',
        color_discrete_map={'run': '#2ca02c', 'pass': '#1f77b4'}
    )

    # Drive Summary for Radar + Bubble
    def drive_summary(df_):
        run_plays = df_[df_['play_type'] == 'run'].shape[0]
        pass_plays = df_[df_['play_type'] == 'pass'].shape[0]
        total = run_plays + pass_plays
        return {
            'plays': len(df_),
            'epa': df_['epa'].sum(),
            'wpa': df_['wpa'].sum() if 'wpa' in df_ else 0,
            'yards': df_['yards_gained'].sum(),
            'run_pct': run_plays / total if total else 0,
            'pass_pct': pass_plays / total if total else 0
        }

    season_df = df[df['week'] == week].copy()
    summary_data = []
    for _, group in season_df.dropna(subset=['drive']).groupby(['game_id', 'drive']):
        summary_data.append(drive_summary(group))
    summary_df = pd.DataFrame(summary_data)
    current_summary = drive_summary(drive_df)
    median = summary_df.median(numeric_only=True)

    # Radar Chart
    radar_fig = go.Figure()
    def norm(val, med): return val / med if med else 0
    radar_fig.add_trace(go.Scatterpolar(
        r=[norm(current_summary[k], median[k]) for k in ['plays', 'epa', 'wpa', 'yards', 'run_pct', 'pass_pct']],
        theta=['# Plays', 'EPA', 'WPA', 'Yards', 'Run %', 'Pass %'],
        fill='toself', name='This Drive'
    ))
    radar_fig.add_trace(go.Scatterpolar(
        r=[1]*6, theta=['# Plays', 'EPA', 'WPA', 'Yards', 'Run %', 'Pass %'],
        fill='toself', name='Median'
    ))
    radar_fig.update_layout(title='Drive Fingerprint vs Median', height=400)

    # Bubble Chart (EPA vs WPA)
    summary_df['size'] = summary_df['yards'].abs()
    bubble_fig = px.scatter(summary_df, x='epa', y='wpa', size='size', opacity=0.6, title='EPA vs WPA by Drive')
    bubble_fig.add_trace(go.Scatter(
        x=[current_summary['epa']], y=[current_summary['wpa']],
        mode='markers+text', marker=dict(size=14, color='red'), name='This Drive',
        text=['This Drive'], textposition='top center'
    ))

    # Layout
    charts = html.Div([
        html.Div(dcc.Graph(figure=wp_fig), style={'width': '48%', 'display': 'inline-block', 'padding': '1%'}),
        html.Div(dcc.Graph(figure=mix_fig), style={'width': '48%', 'display': 'inline-block', 'padding': '1%'}),
        html.Div(dcc.Graph(figure=radar_fig), style={'width': '48%', 'display': 'inline-block', 'padding': '1%'}),
        html.Div(dcc.Graph(figure=bubble_fig), style={'width': '48%', 'display': 'inline-block', 'padding': '1%'})
    ], id='chart-container')

    return table, charts

# Run on Render
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8056))
    app.run(debug=False, dev_tools_ui=False, dev_tools_props_check=False,
            host='0.0.0.0', port=port)
