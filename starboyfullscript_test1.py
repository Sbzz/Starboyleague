import pandas as pd
import requests
from bs4 import BeautifulSoup
import time

# Constants for scoring
points_map = {
    "NPG": 20,   # Non-Penalty Goals
    "PG": 15,    # Penalty Goals
    "Assist": 10,
    "MOTM": 5,   # Man of the Match
    "FM": 5,     # Full Match (Played 90 mins)
    "YC": -5,    # Yellow Card
    "RC": -10    # Red Card
}

# Helper function to parse integer/float safely
def safe_float(val):
    try:
        return float(val)
    except:
        return 0.0

# Scrape function to get 2025/26 stats from FotMob player page
def scrape_player_stats(fotmob_url):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    try:
        response = requests.get(fotmob_url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"Failed to fetch {fotmob_url} status_code={response.status_code}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # FotMob structure: look for season stats table or summary with 2025/26 season
        # We'll parse the available stats by checking the keys and values nearby.
        # Stats keys to search for: Non Penalty Goals, Penalty Goals, Assists, MOTM, FM, YC, RC
        
        # This will differ depending on the actual page structure.
        # We'll do a heuristic parse for the required stats from common stat blocks.
        
        stats = {
            "NPG": 0.0,
            "PG": 0.0,
            "Assist": 0.0,
            "MOTM": 0.0,
            "FM": 0.0,
            "YC": 0.0,
            "RC": 0.0
        }
        
        # Find a container or section mentioning 2025/26 season - usually as heading or filter
        season_header = soup.find(lambda tag: tag.name=="div" and "2025/26" in tag.text)
        if not season_header:
            # Sometimes season not explicitly mentioned, safest to scan all stats blocks
            season_header = soup
        
        # Attempt to find stats in a stats-list or table in the relevant section
        
        # For FotMob player pages, stats are often included in divs with labels and values:
        # Let's try to find "Non Penalty Goals" or "Non-Penalty Goals"
        # Similar for Penalty Goals, Assists, MOTM, Matches Played (to estimate FM), YC, RC
        
        # Basic approach: Extract all stat labels and values within the page related to scoring
        
        stat_labels = ["Non Penalty Goals", "Penalty Goals", "Assists", "Man of the Match", "Man of The Match", "Motm",
                       "Full Match", "Full Matches", "90 Minutes", "Yellow Cards", "Yellow Card", "Red Cards", "Red Card",
                       "Matches Played", "Apps", "Appearances"]
        
        # Find all stat label-value pairs on the page
        label_elements = soup.find_all(string=lambda s: any(label in s for label in stat_labels))
        
        for label_elem in label_elements:
            if label_elem:
                label_text = label_elem.strip()
                val_elem = label_elem.find_next()
                val_text = val_elem.text.strip() if val_elem else ""
                
                val_num = safe_float(val_text)
                
                # Map label to our keys
                if "Non Penalty" in label_text or "Non-Penalty" in label_text:
                    stats["NPG"] = val_num
                elif "Penalty" in label_text and "Goals" in label_text:
                    stats["PG"] = val_num
                elif "Assist" in label_text:
                    stats["Assist"] = val_num
                elif "Man of the Match" in label_text or "Motm" in label_text:
                    stats["MOTM"] = val_num
                elif "Full Match" in label_text or "90 Minutes" in label_text:
                    stats["FM"] = val_num
                elif "Yellow Card" in label_text:
                    stats["YC"] = val_num
                elif "Red Card" in label_text:
                    stats["RC"] = val_num
        
        # If FM (Full Match) not available, estimate it as matches played (less accurate)
        if stats["FM"] == 0:
            # Try to find Matches Played or Appearances instead
            for label_elem in label_elements:
                label_text = label_elem.strip()
                if "Matches Played" in label_text or "Apps" in label_text or "Appearances" in label_text:
                    val_elem = label_elem.find_next()
                    val_text = val_elem.text.strip() if val_elem else ""
                    mp = safe_float(val_text)
                    stats["FM"] = mp  # approximate FM with matches played
                    break

        # Return the stats dictionary
        return stats

    except Exception as e:
        print(f"Exception scraping {fotmob_url}: {e}")
        return None

def calculate_total_points(stats):
    total = (
        stats.get("NPG", 0) * points_map["NPG"] +
        stats.get("PG", 0) * points_map["PG"] +
        stats.get("Assist", 0) * points_map["Assist"] +
        stats.get("MOTM", 0) * points_map["MOTM"] +
        stats.get("FM", 0) * points_map["FM"] +
        stats.get("YC", 0) * points_map["YC"] +
        stats.get("RC", 0) * points_map["RC"]
    )
    return total

def main():
    # Load Excel file (change filename if needed)
    input_filename = "Playerstatslink.xlsx"
    xl = pd.ExcelFile(input_filename)
    
    # Load player list with FotMob URLs
    player_stats_df = pd.read_excel(xl, sheet_name="Player Stats")
    experts_df = pd.read_excel(xl, sheet_name="Players Selected")
    
    # Normalize URL column name
    url_col = "FotMob Stats"
    player_stats_df[url_col] = player_stats_df[url_col].astype(str)
    
    # Dictionary to hold player scores and stats
    player_score_dict = {}
    
    print("Starting to scrape player stats from FotMob...")
    
    # Scrape stats for each player
    for idx, row in player_stats_df.iterrows():
        player_name = row["Player Name"].strip()
        url = row[url_col].strip()
        if url == "nan" or url == "":
            print(f"No URL for player {player_name}, skipping.")
            continue
        
        stats = scrape_player_stats(url)
        if stats:
            total_pts = calculate_total_points(stats)
            player_score_dict[player_name] = {
                "Stats": stats,
                "Total Points": total_pts,
                "Age": row["Age"],
                "Club": row["Club"],
                "League": row["League"]
            }
            print(f"{player_name}: Points = {total_pts}, Stats = {stats}")
        else:
            print(f"Failed to get stats for {player_name}")
        
        # Polite delay to avoid request rate limiting
        time.sleep(1)
    
    # Create a DataFrame with player scoring summary
    player_summary = []
    for player, data in player_score_dict.items():
        entry = {
            "Player Name": player,
            "Age": data["Age"],
            "Club": data["Club"],
            "League": data["League"],
            "NPG": data["Stats"].get("NPG", 0),
            "PG": data["Stats"].get("PG", 0),
            "Assist": data["Stats"].get("Assist", 0),
            "MOTM": data["Stats"].get("MOTM", 0),
            "FM": data["Stats"].get("FM", 0),
            "YC": data["Stats"].get("YC", 0),
            "RC": data["Stats"].get("RC", 0),
            "Total Points": data["Total Points"]
        }
        player_summary.append(entry)
    
    player_summary_df = pd.DataFrame(player_summary)
    player_summary_df = player_summary_df.sort_values(by="Total Points", ascending=False).reset_index(drop=True)
    
    # Aggregate expert scores
    expert_scores = []
    for idx, row in experts_df.iterrows():
        expert = row["Experts"]
        players = [row[f"Player{i}"] for i in range(1,6)]
        total_score = 0
        for p in players:
            if p in player_score_dict:
                total_score += player_score_dict[p]["Total Points"]
        expert_scores.append({"Expert": expert, "Total Points": total_score, "Players": players})
    
    expert_scores.sort(key=lambda x: x["Total Points"], reverse=True)
    
    # Add trophy to highest ranking expert
    if expert_scores:
        expert_scores[0]["Expert"] = "🏆 " + expert_scores[0]["Expert"]
    
    # Mark star for top player
    if not player_summary_df.empty:
        top_player = player_summary_df.iloc[0]["Player Name"]
        player_summary_df["Player Display"] = player_summary_df["Player Name"].apply(
            lambda x: f"⭐ {x}" if x==top_player else x
        )
        player_summary_df["Player Display"] = player_summary_df["Player Display"] + \
            player_summary_df.apply(lambda r: f" (NPG: {r.NPG}, PG: {r.PG}, Assists: {r.Assist}, MOTM: {r.MOTM}, FM: {r.FM}, YC: {r.YC}, RC: {r.RC})", axis=1)
    else:
        player_summary_df["Player Display"] = player_summary_df["Player Name"]
    
    # Output Excel file
    output_excel = "Player_Expert_Stats_2025-26.xlsx"
    with pd.ExcelWriter(output_excel) as writer:
        player_summary_df.drop(columns=["Player Name"]).to_excel(writer, sheet_name="Player Stats", index=False)
        expert_df = pd.DataFrame(expert_scores)
        expert_df.to_excel(writer, sheet_name="Expert Scores", index=False)
    
    print(f"Excel output saved to {output_excel}")
    
    # Create an HTML report/dashboard
    html_content = "<html><head><title>2025/26 Player and Expert Dashboard</title></head><body>"
    html_content += "<h1>Player Dashboard</h1><table border=1><tr><th>Player</th><th>Age</th><th>Club</th><th>League</th><th>NPG</th><th>PG</th><th>Assist</th><th>MOTM</th><th>FM</th><th>YC</th><th>RC</th><th>Total Points</th></tr>"
    
    for _, r in player_summary_df.iterrows():
        html_content += f"<tr><td>{r['Player Display']}</td><td>{r['Age']}</td><td>{r['Club']}</td><td>{r['League']}</td><td>{r['NPG']}</td><td>{r['PG']}</td><td>{r['Assist']}</td><td>{r['MOTM']}</td><td>{r['FM']}</td><td>{r['YC']}</td><td>{r['RC']}</td><td>{r['Total Points']}</td></tr>"
    
    html_content += "</table>"
    
    html_content += "<h1>Expert Dashboard</h1><ol>"
    for expert in expert_scores:
        players_str = ", ".join(expert["Players"])
        html_content += f"<li>{expert['Expert']} (Players: {players_str}) - Total Points: {expert['Total Points']}</li>"
    html_content += "</ol></body></html>"
    
    output_html = "Player_Expert_Dashboard_2025-26.html"
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"HTML dashboard saved to {output_html}")

if __name__ == "__main__":
    main()