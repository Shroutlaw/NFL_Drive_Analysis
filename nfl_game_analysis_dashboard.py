import nfl_data_py as nfl
import pandas as pd
import os
from collections import defaultdict
import numpy as np
import plotly.express as px
import matplotlib.pyplot as plt
from dash import Dash, dcc, html, Input, Output, dash_table, callback, State, MATCH, ALL, callback_context

# Load all CSVs from the 'season_data' folder
'''folder_path = "season_data"
season_files = sorted([
    f for f in os.listdir(folder_path) if f.startswith("nfl_") and f.endswith(".csv")
])

# Load and combine all season data
dfs = []
for filename in season_files:
    #print(f"Loading {filename}...")
    season_path = os.path.join(folder_path, filename)
    df = pd.read_csv(season_path, low_memory=False)
    df['game_id'] = df['game_id'].astype(str)
    dfs.append(df)

# Concatenate all seasons into one DataFrame
df = pd.concat(dfs, ignore_index=True)'''

# Define consistent column types to reduce memory
dtype_map = {
    'game_id': 'str',
    'season': 'int16',
    'spread_line': 'float32',
    'total_home_score': 'int8',
    'total_away_score': 'int8',
    'home_team': 'category',
    'away_team': 'category',
    'posteam': 'category',
    'defteam': 'category',
    'desc': 'string',
    'wp': 'float32',
    'start_wp': 'float32',
    'end_wp': 'float32'
}

# Only include necessary columns to reduce size
usecols = list(dtype_map.keys())

dfs = []
for filename in season_files:
    season_path = os.path.join(folder_path, filename)
    df_season = pd.read_csv(season_path, usecols=usecols, dtype=dtype_map)
    dfs.append(df_season)

df = pd.concat(dfs, ignore_index=True)

# Create END GAME lookup
end_games = df[df['desc'].str.contains("END GAME", na=False)]
#end_games['season'] = end_games['game_id'].str.split('_').str[0]
end_game_lookup = end_games.set_index('game_id').to_dict('index')
unique_game_ids = df['game_id'].unique()

# Determine big spread game_ids
big_spread_games = end_games[end_games['spread_line'].abs() >= 6]
big_spread_game_ids = set(big_spread_games['game_id'])
home_fav_6plus = big_spread_games[big_spread_games['spread_line'] >= 6]
away_fav_6plus = big_spread_games[big_spread_games['spread_line'] <= -6]

# Total games where the home team was favored (spread > 0)
total_home_favored = end_games[end_games['spread_line'] > 0]

# Total games where the away team was favored (spread < 0)
total_away_favored = end_games[end_games['spread_line'] < 0]

# Determine upsets
upsets = []
confirmed_wins = []
even_match = []
upsets_big_spread = []
home_favored_upsets = []
away_favored_upsets = []

all_home_favored_upsets = []
all_away_favored_upsets = []

for game_id, row in end_game_lookup.items():
    game_id = str(game_id)  # Ensures consistency

    spread = row['spread_line']
    home_score = row['total_home_score']
    away_score = row['total_away_score']

    if pd.isna(spread):
        continue

    if spread > 0:
        expected = 'home'
    elif spread < 0:
        expected = 'away'
    else:
        expected = 'tie'

    if home_score > away_score:
        actual = 'home'
    elif away_score > home_score:
        actual = 'away'
    else:
        actual = 'tie'

    if expected == 'tie' or actual == 'tie':
        even_match.append(game_id)
    elif expected == actual:
        confirmed_wins.append(game_id)
    else:
        upsets.append(game_id)

        # ✅ Track all upsets by favorite type
        if spread > 0:
            all_home_favored_upsets.append(game_id)
        elif spread < 0:
            all_away_favored_upsets.append(game_id)

        # ✅ Track big spread upsets
        if abs(spread) >= 6:
            upsets_big_spread.append(game_id)
            if spread > 0:
                home_favored_upsets.append(game_id)
            else:
                away_favored_upsets.append(game_id)

home_fav_upset_rate = len(all_home_favored_upsets) / len(total_home_favored)
away_fav_upset_rate = len(all_away_favored_upsets) / len(total_away_favored)
home_pct = round(home_fav_upset_rate * 100, 1)
away_pct = round(away_fav_upset_rate * 100, 1)

big_home_upset_rate = len(home_favored_upsets) / len(home_fav_6plus)
big_away_upset_rate = len(away_favored_upsets) / len(away_fav_6plus)
big_home_pct = round(big_home_upset_rate * 100, 1)
big_away_pct = round(big_away_upset_rate * 100, 1)

# Create grouped game lookup
grouped_games = dict(tuple(df.groupby('game_id')))

# Initialize trackers
expected_winner_flips = {'no_change': [], 'one_change': [], 'multi_change': []}
expected_winner_flips_big_spread = {'no_change': [], 'one_change': [], 'multi_change': []}
multi_flip_expected_winner_won = []
multi_flip_expected_winner_lost = []
multi_flip_overtime_games = []
multi_flip_overtime_expected_winner_won = []
multi_flip_overtime_expected_winner_lost = []

# Flip analysis
for game_id in unique_game_ids:
    if game_id not in grouped_games or game_id not in end_game_lookup:
        continue

    game_df = grouped_games[game_id].sort_values(by=['qtr', 'time'], ascending=[True, False])
    row = end_game_lookup[game_id]

    # Build winner series
    winner_series = []
    for _, play in game_df.iterrows():
        home_wp = play.get('home_wp')
        away_wp = play.get('away_wp')
        if pd.isna(home_wp) or pd.isna(away_wp):
            continue
        if home_wp > 0.5:
            winner_series.append('home')
        elif away_wp > 0.5:
            winner_series.append('away')
        else:
            winner_series.append('none')

    # Collapse consecutive entries and remove 'none'
    compressed = [winner_series[0]] if winner_series else []
    for side in winner_series[1:]:
        if side != compressed[-1]:
            compressed.append(side)
    compressed = [w for w in compressed if w != 'none']
    flip_count = len(compressed) - 1
    max_qtr = game_df['qtr'].max()

    spread = row['spread_line']
    home_score = row['total_home_score']
    away_score = row['total_away_score']

    if pd.isna(spread) or (home_score == away_score):
        continue
    expected = 'home' if spread > 0 else 'away'
    actual = 'home' if home_score > away_score else 'away'

    # Track overall flips
    if flip_count == 0:
        expected_winner_flips['no_change'].append(game_id)
    elif flip_count == 1:
        expected_winner_flips['one_change'].append(game_id)
    else:
        expected_winner_flips['multi_change'].append(game_id)

    # Track big spread flips
    if game_id in big_spread_game_ids:
        if flip_count == 0:
            expected_winner_flips_big_spread['no_change'].append(game_id)
        elif flip_count == 1:
            expected_winner_flips_big_spread['one_change'].append(game_id)
        else:
            expected_winner_flips_big_spread['multi_change'].append(game_id)

            if expected == actual:
                multi_flip_expected_winner_won.append(game_id)
            else:
                multi_flip_expected_winner_lost.append(game_id)

            if max_qtr > 4:
                multi_flip_overtime_games.append(game_id)
                if expected == actual:
                    multi_flip_overtime_expected_winner_won.append(game_id)
                else:
                    multi_flip_overtime_expected_winner_lost.append(game_id)

multi_flip_game_ids = expected_winner_flips['multi_change']

# Create a lookup of game_id to season using full dataset
game_id_to_season = df[['game_id', 'season']].drop_duplicates().set_index('game_id')['season']

# Get seasons for multi-flip games only
multi_flip_seasons = game_id_to_season.loc[multi_flip_game_ids]

# Count and sort by season
seasonal_flip_counts = multi_flip_seasons.value_counts().sort_index()

# Print the results
print("Multi-Flip Games by Season:")
print(seasonal_flip_counts)


# Final printout
print(f"Total unique games: {len(unique_game_ids)}")
print(f"Total games with projected spread >= 6 points: {len(big_spread_games)}")
print(f" - Home favored by 6 or more: {len(home_fav_6plus)}")
print(f" - Away favored by 6 or more: {len(away_fav_6plus)}")
print(f"Total games with expected winner winning: {len(confirmed_wins)}")
print(f"Total upsets (expected winner lost): {len(upsets)}")
print(f"Even matches (no favorite or tie): {len(even_match)}")
print(f"Upsets with spread >= 6: {len(upsets_big_spread)}")
print(f"Home-favored upsets (spread >= 6): {len(home_favored_upsets)}")
print(f"Away-favored upsets (spread >= 6): {len(away_favored_upsets)}")

print("\nExpected Winner Change Analysis:")
print(f"Games with no change in expected winner: {len(expected_winner_flips['no_change'])}")
print(f"Games with exactly one change in expected winner: {len(expected_winner_flips['one_change'])}")
print(f"Games with multiple changes in expected winner: {len(expected_winner_flips['multi_change'])}")

print("\nExpected Winner Change Analysis (Big Spread Games):")
print(f"Games with no change in expected winner: {len(expected_winner_flips_big_spread['no_change'])}")
print(f"Games with exactly one change in expected winner: {len(expected_winner_flips_big_spread['one_change'])}")
print(f"Games with multiple changes in expected winner: {len(expected_winner_flips_big_spread['multi_change'])}")

print("\nBig Spread Games with Multiple Expected Winner Flips - Final Outcomes:")
print(f"Expected winner WON: {len(multi_flip_expected_winner_won)}")
print(f"Expected winner LOST (upset): {len(multi_flip_expected_winner_lost)}")

print("\nBig Spread Games with Multiple Flips That Went to Overtime:")
print(f"Total overtime games: {len(multi_flip_overtime_games)}")
print(f" - Expected winner WON in OT: {len(multi_flip_overtime_expected_winner_won)}")
print(f" - Expected winner LOST in OT: {len(multi_flip_overtime_expected_winner_lost)}")

# Define summary stats from existing values
summary_stats = {
    "Total unique games": len(unique_game_ids),
    "Big spread games (spread ≥ 6 pts)": len(big_spread_games),
    " - Home favored": len(home_fav_6plus),
    " - Away favored": len(away_fav_6plus),
    "Expected winner won": len(confirmed_wins),
    "Upsets (expected winner lost)": len(upsets),
    "Even matches (no favorite)": len(even_match),
    "Upsets with spread ≥ 6": len(upsets_big_spread),
    " - Home favored upsets": len(home_favored_upsets),
    " - Away favored upsets": len(away_favored_upsets),
    "Winner change: No change": len(expected_winner_flips['no_change']),
    "Winner change: One change": len(expected_winner_flips['one_change']),
    "Winner change: Multiple changes": len(expected_winner_flips['multi_change']),
    "Big spread winner change: No change": len(expected_winner_flips_big_spread['no_change']),
    "Big spread winner change: One change": len(expected_winner_flips_big_spread['one_change']),
    "Big spread winner change: Multiple changes": len(expected_winner_flips_big_spread['multi_change']),
    "Big spread multi-flip games - Expected winner WON": len(multi_flip_expected_winner_won),
    "Big spread multi-flip games - Expected winner LOST": len(multi_flip_expected_winner_lost),
    "Big spread multi-flip games that went to OT": len(multi_flip_overtime_games),
    " - OT: Expected winner WON": len(multi_flip_overtime_expected_winner_won),
    " - OT: Expected winner LOST": len(multi_flip_overtime_expected_winner_lost)
}

def ensure_game_id_list(input_ids):
    """Convert any input to a list of strings."""
    if isinstance(input_ids, pd.Series):
        return input_ids.astype(str).tolist()
    return list(map(str, input_ids))

category_game_sets = {
    "All Games": ensure_game_id_list(unique_game_ids),
    "Big spread games (spread ≥ 6 pts)": ensure_game_id_list(big_spread_games['game_id']),
    " - Home favored": ensure_game_id_list(home_fav_6plus['game_id']),
    " - Away favored": ensure_game_id_list(away_fav_6plus['game_id']),
    "Expected winner won": ensure_game_id_list(confirmed_wins),
    "Upsets (expected winner lost)": ensure_game_id_list(upsets),
    "Even matches (no favorite)": ensure_game_id_list(even_match),
    "Upsets with spread ≥ 6": ensure_game_id_list(upsets_big_spread),
    " - Home favored upsets": ensure_game_id_list(home_favored_upsets),
    " - Away favored upsets": ensure_game_id_list(away_favored_upsets),
    "Big spread multi-flip games - Expected winner WON": ensure_game_id_list(multi_flip_expected_winner_won),
    "Big spread multi-flip games - Expected winner LOST": ensure_game_id_list(multi_flip_expected_winner_lost),
    "Big spread multi-flip games that went to OT": ensure_game_id_list(multi_flip_overtime_games),
    " - OT: Expected winner WON": ensure_game_id_list(multi_flip_overtime_expected_winner_won),
    " - OT: Expected winner LOST": ensure_game_id_list(multi_flip_overtime_expected_winner_lost),
}

# Filter data to only include games from all defined categories
relevant_game_ids = set()
for game_list in category_game_sets.values():
    relevant_game_ids.update(game_list)
df_filtered = df[df['game_id'].isin(relevant_game_ids)]

# Filter out rows with no posteam or defteam (e.g., END QUARTER, Timeout, etc.)
df_filtered = df_filtered[df_filtered['posteam'].notna() & df_filtered['defteam'].notna()]

# Ensure sorting so drives are in order
df_filtered = df_filtered.sort_values(by=['game_id', 'drive', 'play_id'])

# Determine winners first
winners = {}
for game_id, group in df_filtered.groupby("game_id"):
    final_row = group.iloc[-1]
    home_team = final_row["home_team"]
    away_team = final_row["away_team"]
    home_score = final_row["total_home_score"]
    away_score = final_row["total_away_score"]
    winners[game_id] = home_team if home_score > away_score else away_team

# Calculate drive-level changes from the winner's perspective
drive_wp_changes = []

for (game_id, drive), group in df_filtered.groupby(['game_id', 'drive']):
    winner = winners[game_id]

    start_row = group.iloc[0]
    end_row = group.iloc[-1]

    # Always express WP from winning team's POV
    if start_row['posteam'] == winner:
        start_wp = start_row['wp']
    elif start_row['defteam'] == winner:
        start_wp = 1 - start_row['wp']
    else:
        start_wp = None  # edge case, should not happen

    if end_row['posteam'] == winner:
        end_wp = end_row['wp']
    elif end_row['defteam'] == winner:
        end_wp = 1 - end_row['wp']
    else:
        end_wp = None

    wp_change = end_wp - start_wp if start_wp is not None and end_wp is not None else None

    drive_wp_changes.append({
        'game_id': game_id,
        'drive': drive,
        'posteam': start_row['posteam'],
        'defteam': start_row['defteam'],
        'yards_gained': group['yards_gained'].fillna(0).sum(),
        'total_home_score': end_row['total_home_score'],
        'total_away_score': end_row['total_away_score'],
        'start_wp': start_wp,
        'end_wp': end_wp,
        'wp_change': wp_change,
        'num_plays': len(group),
        'epa_change': group['epa'].sum()
    })

df_drive_wp = pd.DataFrame(drive_wp_changes)

# Now you can safely compute impact score
df_drive_wp['drive_impact_score'] = (
    df_drive_wp['wp_change'].abs() * df_drive_wp['epa_change'] * df_drive_wp['num_plays']
)

flip_points = []

for game_id in unique_game_ids:
    if game_id not in grouped_games or game_id not in end_game_lookup:
        continue

    game_df = grouped_games[game_id].sort_values(by=['qtr', 'time'], ascending=[True, False])

    # Build expected winner sequence
    winner_series = []
    for idx, row in game_df.iterrows():
        home_wp, away_wp = row.get('home_wp'), row.get('away_wp')
        if pd.isna(home_wp) or pd.isna(away_wp):
            continue
        if home_wp > 0.5:
            winner = 'home'
        elif away_wp > 0.5:
            winner = 'away'
        else:
            winner = 'none'
        winner_series.append((idx, winner))

    # Collapse to transitions only
    cleaned = []
    for i, (idx, winner) in enumerate(winner_series):
        if not cleaned or winner != cleaned[-1][1]:
            cleaned.append((idx, winner))
    cleaned = [entry for entry in cleaned if entry[1] != 'none']

    if len(cleaned) == 2:
        flip_idx = cleaned[1][0]
        flip_row = game_df.loc[flip_idx]
        flip_qtr = flip_row['qtr']
        flip_time = flip_row['time']
        try:
            if isinstance(flip_time, str) and ':' in flip_time:
                try:
                    mins, secs = map(int, flip_time.strip().split(':'))
                    minutes_left = mins + secs / 60
                except:
                    minutes_left = None
            else:
                minutes_left = None
        except:
            minutes_left = None
        total_score = flip_row['total_home_score'] + flip_row['total_away_score']
        flip_points.append((flip_qtr, minutes_left, total_score))

# Convert to DataFrame for plotting
flip_df = pd.DataFrame(flip_points, columns=['qtr', 'minutes_left_in_qtr', 'total_score'])

# Split into three groups
flip_df_all = flip_df.copy()
flip_df_zero_score = flip_df[flip_df['total_score'] == 0]
flip_df_nonzero_score = flip_df[flip_df['total_score'] != 0]

df_plays = df[df['game_id'].isin(relevant_game_ids)]
df_plays = df_plays.sort_values(by=['game_id', 'drive', 'play_id'])

app = Dash(__name__)
app.title = "NFL Expected Winner Analysis"

app.layout = html.Div([
    html.H1("📊 NFL Game Analysis Dashboard", style={
        "textAlign": "center",
        "marginTop": "10px",
        "marginBottom": "20px",
        "fontSize": "28px",
        "fontWeight": "bold",
        "color": "#003366"
    }),
    dcc.Tabs([
        dcc.Tab(label='Big Spread Expectations', children=[
            html.Div([
                # Entire row: left text column + right stacked charts
                html.Div([
                    # LEFT COLUMN – Data Story
                    html.Div([
                        html.H3("🏈 When the Underdogs Howl and the Favorites Fall", style={"marginBottom": "6px", "fontSize": "20px"}),
                        html.P(f"Across {summary_stats['Total unique games']} unique NFL games, betting lines and in-game win probabilities often tell us who should win — but the game doesn’t always follow the script.",
                               style={"marginBottom": "10px", "fontSize": "15px"}),

                        html.H4("🎯 Big Spread Expectations — and Where They Go Wrong", style={"marginBottom": "5px", "fontSize": "18px"}),
                        html.Ul([
                            html.Li(f"{summary_stats['Big spread games (spread ≥ 6 pts)']} were considered big spread games (≥ 6 pts)"),
                            html.P("Implication: These are games where sportsbooks and models project dominance, but their volatility is often underestimated.", style={"margin": "2px 0"}),

                            html.Li(f"{summary_stats[' - Home favored']} home favorites, {summary_stats[' - Away favored']} away favorites"),
                            html.P("Implication: Home teams dominate the big spread category, likely reflecting both data model and bettor confidence in home-field advantage.", style={"margin": "2px 0"}),

                            html.Li(f"{summary_stats['Expected winner won']} expected winners won"),
                            html.P("Implication: Models do reasonably well overall — but knowing when they fail is more valuable than when they succeed.", style={"margin": "2px 0"}),

                            html.Li(f"{summary_stats['Upsets (expected winner lost)']} ended in upsets (~{summary_stats['Upsets (expected winner lost)'] / summary_stats['Total unique games']:.1%})"),
                            html.P("Implication: A third of games go off-script. That’s a massive edge for sharp bettors or adaptive products.", style={"margin": "2px 0"}),

                            html.Li(f"{summary_stats['Upsets with spread ≥ 6']} of big spreads ended in upset (~{summary_stats['Upsets with spread ≥ 6'] / summary_stats['Big spread games (spread ≥ 6 pts)']:.1%})"),
                            html.P("Implication: Even so-called 'locks' fall apart. These games are ripe for hedging, alternate lines, or real-time alert systems.", style={"margin": "2px 0"}),
                        ]),
                        html.H4("📊 Why This Matters", style={"marginTop": "10px", "marginBottom": "5px", "fontSize": "18px"}),
                        html.Ul([
                            html.Li("Not all big spreads are safe bets."),
                            html.P("Volatility creeps in — making it crucial to evaluate matchup dynamics beyond the number.", style={"margin": "2px 0"}),

                            html.Li("Games with high win probability flips signal high-risk outcomes."),
                            html.P("These games offer opportunities for smarter in-game decisions.", style={"margin": "2px 0"}),

                            html.Li("Overtime in high-spread games is a serious warning sign."),
                            html.P("If the game hits OT, history suggests you're now in toss-up territory.", style={"margin": "2px 0"}),
                        ]),
                    ], style={
                        "width": "58%", "padding": "8px", "fontSize": "15px",
                        "lineHeight": "1.25", "overflowY": "auto", "maxHeight": "94vh"
                    }),

                    # RIGHT COLUMN – stacked scatterplots
                    html.Div([
                        html.Div([
                            html.H4("Scatterplot: All Flips", style={"marginBottom": "4px"}),
                            dcc.Graph(figure=px.scatter(
                                flip_df, x="minutes_left_in_qtr", y="total_score", color="qtr",
                                title="All Single Expected Winner Flips"
                            )),
                        ]),
                    ], style={
                        "width": "42%", "padding": "8px", "display": "flex",
                        "flexDirection": "column", "gap": "12px"
                    })
                ], style={
                    "display": "flex", "flexDirection": "row",
                    "alignItems": "flex-start", "gap": "12px", "padding": "0px 16px"
                })
            ])
        ]),

        dcc.Tab(label='Underdog Danger Zones', children=[
            html.Div([
                html.Div([
                    html.H3("⚡ Underdog Danger Zones", style={"marginTop": "10px", "marginBottom": "10px", "fontSize": "22px"}),

                    html.P(f"""
                        Across all tracked upsets, {len(all_home_favored_upsets)} occurred when the home team was favored, while
                        {len(all_away_favored_upsets)} involved a road favorite losing unexpectedly.
                    """, style={"fontSize": "16px"}),

                    html.P(f"""
                        • Home favorites were upset in {home_pct}% of the games where they were favored.
                        • Away favorites were upset in {away_pct}% of the games where they were favored.
                    """, style={"fontSize": "15px"}),

                    html.Div([
                        html.Div([
                            dcc.Graph(
                                figure=px.bar(
                                    x=["Home Favorite", "Away Favorite"],
                                    y=[len(all_home_favored_upsets), len(all_away_favored_upsets)],
                                    labels={'x': 'Type of Favorite', 'y': 'Upset Losses'},
                                    title="Upset Losses by Favorite Type",
                                    text=[len(all_home_favored_upsets), len(all_away_favored_upsets)],
                                    color=["Home", "Away"],
                                    color_discrete_map={"Home": "#3366CC", "Away": "#FF6600"}
                                ).update_traces(textposition='auto')
                                 .update_layout(
                                    title=dict(
                                        text="Upset Losses by Favorite Type",
                                        font=dict(size=15)
                                    ),
                                    height=300,
                                    margin=dict(l=40, r=20, t=50, b=40),
                                    showlegend=False
                                )
                            )
                        ], style={'flex': '1', 'paddingRight': '10px'}),

                        html.Div([
                            dcc.Graph(
                                figure=px.bar(
                                    x=["Home Favorite", "Away Favorite"],
                                    y=[home_pct, away_pct],
                                    labels={'x': 'Type of Favorite', 'y': 'Upset Rate (%)'},
                                    title="Upset Rate by Favorite Type",
                                    text=[f"{home_pct}%", f"{away_pct}%"],
                                    color=["Home", "Away"],
                                    color_discrete_map={"Home": "#3366CC", "Away": "#FF6600"}
                                ).update_traces(textposition='auto')
                                 .update_layout(
                                    title=dict(
                                        text="Upset Losses by Favorite Type",
                                        font=dict(size=15)
                                    ),
                                    height=300,
                                    margin=dict(l=40, r=20, t=50, b=40),
                                    showlegend=False
                                )
                            )
                        ], style={'flex': '1', 'paddingLeft': '10px'})
                    ], style={'display': 'flex', 'justifyContent': 'center'}),

                    html.P(f"""
                        Looking at upsets where the spread was 6 or more points, {summary_stats[' - Home favored upsets']} occurred when the home team was favored, while
                        {summary_stats[' - Away favored upsets']} involved a road favorite losing unexpectedly.
                    """, style={"fontSize": "16px"}),

                    html.P(f"""
                        • Home favorites were upset in {big_home_pct}% of the games where they were favored.
                        • Away favorites were upset in {big_away_pct}% of the games where they were favored.
                    """, style={"fontSize": "15px"}),

                    html.Div([
                        html.Div([
                            dcc.Graph(
                                figure=px.bar(
                                    x=["Home Favorite (6+)", "Away Favorite (6+)"],
                                    y=[len(home_favored_upsets), len(away_favored_upsets)],
                                    labels={'x': 'Big Spread Favorite', 'y': 'Upset Losses'},
                                    title="Big Spread Upset Losses by Favorite Type",
                                    text=[len(home_favored_upsets), len(away_favored_upsets)],
                                    color=["BigHome", "BigAway"],
                                    color_discrete_map={"BigHome": "#58508d", "BigAway": "#ff6361"}
                                ).update_traces(textposition='auto')
                                 .update_layout(
                                    title=dict(
                                        text="Upset Losses by Favorite Type",
                                        font=dict(size=15)
                                    ),
                                    height=300,
                                    margin=dict(l=40, r=20, t=50, b=40),
                                    showlegend=False
                                )
                            )
                        ], style={'flex': '1', 'paddingRight': '10px'}),

                        html.Div([
                            dcc.Graph(
                                figure=px.bar(
                                    x=["Big Spread Home Favorite", "Big Spread Away Favorite"],
                                    y=[big_home_pct, big_away_pct],
                                    labels={'x': 'Favorite Type (Spread ≥ 6)', 'y': 'Upset Rate (%)'},
                                    title="Upset Rate Among Big Spread Favorites",
                                    text=[f"{big_home_pct}%", f"{big_away_pct}%"],
                                    color=["Home Big", "Away Big"],
                                    color_discrete_map={"Home Big": "#003f5c", "Away Big": "#bc5090"}
                                ).update_traces(textposition='auto')
                                 .update_layout(
                                    title=dict(
                                        text="Upset Losses by Favorite Type",
                                        font=dict(size=15)
                                    ),
                                    height=300,
                                    margin=dict(l=40, r=20, t=50, b=40),
                                    showlegend=False
                                )
                            )
                        ], style={'flex': '1', 'paddingLeft': '10px'})
                    ], style={'display': 'flex', 'justifyContent': 'center', 'flexWrap': 'wrap'}),

                    html.P("""
                        While home favorites have more upset losses by volume, the *rate of failure* for road favorites is typically higher.
                        This highlights the increased volatility of betting on the road.
                    """, style={"fontSize": "15px"}),

                    html.P("""
                        💡 Strategic Insight:
                        • Betting models may need sharper risk coefficients for road favorites.
                        • Fan alert tools could trigger warnings when early drives show momentum shifts against favored road teams.
                    """, style={"fontSize": "15px"})
                ], style={"padding": "16px", "maxWidth": "1000px", "margin": "0 auto"})
            ])
        ]),
        
        dcc.Tab(label='Competitiveness Trends', children=[
            html.Div([
                html.Div([
                    html.H3("🔁 How Games Shift — The Flip Factor", style={"marginTop": "10px", "marginBottom": "5px", "fontSize": "18px"}),
                    html.Ul([
                        html.Li(f"{summary_stats['Winner change: No change']} had no change in expected winner"),
                        html.P("Implication: About 15% of games stayed the course from kickoff to final whistle...", style={"margin": "2px 0"}),

                        html.Li(f"{summary_stats['Winner change: One change']} had one flip"),
                        html.P("Implication: These single-flip games reveal a moment of crisis or momentum swing.", style={"margin": "2px 0"}),

                        html.Li(f"{summary_stats['Winner change: Multiple changes']} had multiple flips"),
                        html.P("Implication: Over 75% of games saw multiple shifts in expected winner...", style={"margin": "2px 0"}),

                        html.Li(f"{summary_stats['Big spread winner change: Multiple changes']} big spreads had multiple flips"),
                        html.P("Implication: Even the games sportsbooks feel most confident in are unstable...", style={"margin": "2px 0"}),

                        html.Li(f"{summary_stats['Big spread multi-flip games - Expected winner LOST']} of those ended in upsets"),
                        html.P("Implication: When chaos meets expectation, the expected winner is vulnerable...", style={"margin": "2px 0"}),
                        ]),
                    html.H3("📈 Multi-Flip Game Trends Across Seasons", style={"marginTop": "10px"}),
                    html.P("This chart tracks how often the expected winner changed more than once during a game — a key signal of in-game volatility. A higher count implies a more competitive season overall.", style={"fontSize": "15px"}),

                    dcc.Graph(figure=px.line(
                        x=seasonal_flip_counts.index,
                        y=seasonal_flip_counts.values,
                        markers=True,
                        labels={'x': 'Season', 'y': 'Multi-Flip Games'},
                        title="Multi-Flip Game Count by Season"
                    )),

                    html.P("1999 and 2022 saw the highest number of multi-flip games (236 and 234, respectively), while 2016 had the fewest (192). However, the range between seasons remains modest, suggesting the NFL maintains a strong level of competitive consistency from year to year.", style={"fontSize": "15px", "marginTop": "10px"}),

                    html.P("These insights can help guide discussions around parity, game quality, and schedule design — especially when paired with other metrics like win margin, comeback frequency, or red zone efficiency.", style={"fontSize": "15px"})
                ], style={"padding": "16px", "maxWidth": "1000px", "margin": "0 auto"})
            ])
        ]),

        dcc.Tab(label='Overtime Wildcards', children=[
            html.Div([
                html.Div([
                    html.H3("⏱️ The Overtime Wildcards", style={"marginTop": "10px", "marginBottom": "10px", "fontSize": "22px"}),

                    html.P(f"""
                        A total of {summary_stats['Big spread multi-flip games that went to OT']} big spread games went to overtime —
                        matchups that were expected to be lopsided. Yet regulation couldn’t separate the teams.
                    """, style={"fontSize": "16px"}),

                    html.P(f"""
                        In those games, the favorite won {summary_stats[' - OT: Expected winner WON']} times,
                        while the underdog pulled off the OT win {summary_stats[' - OT: Expected winner LOST']} times.
                        That's an underdog OT win rate of ~{summary_stats[' - OT: Expected winner LOST'] / summary_stats['Big spread multi-flip games that went to OT']:.1%}.
                    """, style={"fontSize": "16px"}),

                    html.P("""
                        ➤ These outcomes suggest that pre-game confidence is irrelevant once a 'safe' game reaches overtime.
                        Underdogs feed off survival momentum, and bettors are suddenly in a 50/50 coin flip scenario.
                    """, style={"fontSize": "15px"}),

                    html.Div([
                        html.Div([
                            dcc.Graph(
                                figure=px.pie(
                                    names=["Favorite Won", "Underdog Won"],
                                    values=[
                                        summary_stats[' - OT: Expected winner WON'],
                                        summary_stats[' - OT: Expected winner LOST']
                                    ],
                                    title="OT Outcomes in Big Spread Games",
                                    color_discrete_map={
                                        "Favorite Won": "#3366CC",
                                        "Underdog Won": "#FF6600"
                                    }
                                ).update_traces(textinfo = "label+percent", textposition='auto')
                                 .update_layout(
                                    title=dict(
                                        text="Favorite Won, Underdog Won",
                                        font=dict(size=15)
                                    ),
                                    height=300,
                                    margin=dict(l=40, r=20, t=50, b=40),
                                    showlegend=False
                                )
                            )
                        ], style={'flex': '1', 'paddingRight': '10px'}),

                        html.Div([
                            dcc.Graph(
                                figure=px.bar(
                                    x=["Total Big Spread OT Games"],
                                    y=[summary_stats['Big spread multi-flip games that went to OT']],
                                    text=[summary_stats['Big spread multi-flip games that went to OT']],
                                    labels={'x': '', 'y': 'Count'},
                                    title="Volume of OT Games in Big Spread Matchups",
                                    color_discrete_sequence=["#58508d"]
                                ).update_traces(textposition='auto')
                                 .update_layout(
                                    title=dict(
                                        text="Volume of OT Games in Big Spread Matchups",
                                        font=dict(size=15)
                                    ),
                                    height=300,
                                    margin=dict(l=40, r=20, t=50, b=40),
                                    showlegend=False
                                )
                            )
                        ], style={'flex': '1', 'paddingLeft': '10px'})
                    ], style={'display': 'flex', 'justifyContent': 'center', 'flexWrap': 'wrap'}),

                    html.P("""
                        💡 Stakeholder Insight:
                        • Even the safest-seeming games can become high-risk in OT.
                        • Consider in-game betting risk buffers or "Regulation Only" bet options for high-spread matchups.
                        • OT scenarios show how easily momentum flips betting logic upside down.
                    """, style={"fontSize": "15px", "marginTop": "16px"})
                ], style={"padding": "16px", "maxWidth": "1000px", "margin": "0 auto"})
            ])
        ]),

        dcc.Tab(label='Drive Explorer', children=[
            html.Div([
                html.Div([
                    html.H3("🔍 Drive Explorer — Trace the Turning Points"),
                    html.P("""
                        This tab helps you zoom in on the most pivotal moments in a game: the drives. 
                        As we learned in the Summary & Visuals section, over 75% of NFL games feature 
                        multiple changes in expected winner, and even so-called 'safe' big-spread games 
                        can flip upside down — especially in overtime or during key momentum shifts.
                    """),
                    html.P("""
                        The Drive Explorer allows you to dig deeper into those swings. When a team’s win 
                        probability climbs or collapses in a single drive, it signals a major turning point — 
                        whether it's a touchdown, a turnover, or even a clutch 3rd down conversion.
                    """),
                    html.P("""
                        To use the explorer, simply select a game from the dropdown above, then click on 
                        any drive row below. This will display all the individual plays from that drive, 
                        including play description, down/distance, offensive and defensive team, and the 
                        play’s individual win probability added (WPA).
                    """),
                    html.P("""
                        By studying these plays, you can identify:
                        • Which plays were most responsible for changing win probability.
                        • If a key mistake (fumble, interception) flipped momentum.
                        • Whether a drive was efficient, chaotic, or stalled at a critical moment.
                    """),
                    html.P("""
                        This is especially valuable for understanding:
                        • Upsets: Did the underdog capitalize on a few high-WPA plays?
                        • Multi-flip games: What caused the back-and-forth swings?
                        • Big spreads gone wrong: Where did the favorite start to lose control?
                    """),
                    html.P("""
                        Every drive tells a story. This tool helps you read it — one play at a time.
                    """, style={"marginBottom": "20px", "fontStyle": "italic"})
                ]),

                html.Div([
                    html.Div([
                        html.Label("Game Category"),
                        dcc.Dropdown(
                            id="category_selector",
                            options=[{"label": k, "value": k} for k in category_game_sets.keys()],
                            value="All Games"
                        )
                    ], style={"display": "inline-block", "width": "32%", "marginRight": "1%"}),

                    html.Div([
                        html.Label("Season"),
                        dcc.Dropdown(
                            id="season_selector",
                            options=[{"label": str(s), "value": str(s)} for s in sorted(df['season'].unique())],
                            placeholder="Select Season"
                        )
                    ], style={"display": "inline-block", "width": "32%", "marginRight": "1%"}),

                    html.Div([
                        html.Label("Game"),
                        dcc.Dropdown(id="game_selector")
                    ], style={"display": "inline-block", "width": "32%"})
                ]),
                html.Br(),

                html.Div([
                    html.Div([
                        html.H4("Drive Win Probability Change"),
                        dash_table.DataTable(
                            id="drive_wp_table",
                            columns=[
                                {"name": "drive", "id": "drive"},
                                {"name": "posteam", "id": "posteam"},
                                {"name": "defteam", "id": "defteam"},
                                {"name": "yards", "id": "yards_gained", "type": "numeric"},
                                {"name": "home", "id": "total_home_score", "type": "numeric"},
                                {"name": "away", "id": "total_away_score", "type": "numeric"},
                                {"name": "start_wp", "id": "start_wp", "type": "numeric", "format": {"specifier": ".3f"}},
                                {"name": "end_wp", "id": "end_wp", "type": "numeric", "format": {"specifier": ".3f"}},
                                {"name": "wp_change", "id": "wp_change", "type": "numeric", "format": {"specifier": ".3f"}},
                            ],
                            active_cell=None,
                            style_cell={"textAlign": "center"},
                            style_cell_conditional=[
                                {"if": {"column_id": "drive"}, "width": "35px"},
                                {"if": {"column_id": "posteam"}, "width": "45px"},
                                {"if": {"column_id": "defteam"}, "width": "45px"},
                                {"if": {"column_id": "yards_gained"}, "width": "60px"},
                                {"if": {"column_id": "total_home_score"}, "width": "35px"},
                                {"if": {"column_id": "total_away_score"}, "width": "35px"},
                                {"if": {"column_id": "start_wp"}, "width": "45px"},
                                {"if": {"column_id": "end_wp"}, "width": "45px"},
                                {"if": {"column_id": "wp_change"}, "width": "45px"},
                            ],
                            style_table={"overflowX": "auto"},
                            style_data_conditional=[
                                {
                                    "if": {"state": "selected"},
                                    "backgroundColor": "#D2F3FF",
                                    "border": "1px solid #0074D9",
                                },
                                {
                                    "if": {"row_index": "odd"},
                                    "backgroundColor": "#f9f9f9",
                                }
                            ],
                            style_data={'cursor': 'pointer'},
                        )
                    ], style={"width": "33%", "padding": "10px"}),

                    html.Div([
                        html.H4("Play-by-Play for Selected Drive"),
                        dash_table.DataTable(
                            id="play_table",
                            columns=[
                                {"name": "qtr", "id": "qtr"},
                                {"name": "time", "id": "time"},
                                {"name": "posteam", "id": "posteam"},
                                {"name": "defteam", "id": "defteam"},
                                {"name": "down", "id": "down"},
                                {"name": "ydstogo", "id": "ydstogo"},
                                {"name": "wpa", "id": "wpa", "type": "numeric", "format": {"specifier": ".3f"}},
                                {"name": "desc", "id": "desc"},
                            ],
                            style_cell={"textAlign": "left", "whiteSpace": "normal"},
                            style_table={"overflowX": "auto", "maxHeight": "600px", "overflowY": "scroll"},
                        )
                    ], style={"width": "66%", "padding": "10px"})

                ], style={"display": "flex", "flexDirection": "row", "alignItems": "flex-start"}),
                    
            ])
        ])
    ])
])

@app.callback(
    Output("game_selector", "options"),
    Input("category_selector", "value"),
    Input("season_selector", "value")
)
def update_game_dropdown(selected_category, selected_season):
    print(f"[DEBUG] Category: {selected_category}, Season: {selected_season}")
    if not selected_category or not selected_season:
        return []

    game_ids = category_game_sets.get(selected_category, [])
    filtered = []

    for gid in game_ids:
        if gid in end_game_lookup:
            game_season = str(end_game_lookup[gid]["season"])
            if game_season == str(selected_season):
                label = f"{gid} - {end_game_lookup[gid]['home_team']} vs {end_game_lookup[gid]['away_team']} ({game_season})"
                filtered.append({"label": label, "value": gid})

    print(f"[DEBUG] Filtered Games: {len(filtered)}")
    return filtered

@app.callback(
    Output("drive_wp_table", "data"),
    Input("game_selector", "value"),
)
def update_drive_table(game_id):
    if not game_id:
        return []

    drives = df_drive_wp[df_drive_wp["game_id"] == game_id]
    return drives[[
        "drive", "posteam", "defteam", "yards_gained",
        "total_home_score", "total_away_score",
        "start_wp", "end_wp", "wp_change"
    ]].to_dict("records")

@app.callback(
    Output("play_table", "data"),
    Input("drive_wp_table", "active_cell"),
    State("drive_wp_table", "data"),
    State("game_selector", "value"),
    prevent_initial_call=True
)
def update_play_table(active_cell, table_data, game_id):
    if not active_cell or not game_id or not table_data:
        return []

    row_idx = active_cell["row"]
    if row_idx >= len(table_data):
        return []

    selected_drive = table_data[row_idx]["drive"]

    plays = df_plays[
        (df_plays["game_id"] == game_id) &
        (df_plays["drive"] == selected_drive)
    ]

    return plays[["qtr", "time", "posteam", "defteam", "down", "ydstogo", "wpa", "desc"]].to_dict("records")

if __name__ == '__main__':
    #app.run(debug=True, dev_tools_ui=False, dev_tools_props_check=False, port=8010)
    app.run(debug=True, dev_tools_ui=False, dev_tools_props_check=False, host='0.0.0.0', port=int(os.environ.get('PORT', 8010)))
