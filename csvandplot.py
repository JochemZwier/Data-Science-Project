#%%

## Load CSV Files


import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from collections import Counter

# Set the path to your data folder
folder_path = Path('result_folder')

# List to hold all our individual dataframes
dataframes = []

# Keep track of any files that fail completely
failed_files = []

# Iterate through all CSV files in the subdirectory
for file_path in folder_path.glob('*.csv'):
    filename = file_path.stem 
    #print(f"{(filename)}")
    
    parts = filename.split('_')
    
    if len(parts) >= 3:
        date_part = parts[0]
        distance_part = parts[1]
        event_part = "_".join(parts[2:]) 
        
        try:
            year, month, day = date_part.split('-')
        except ValueError:
            print(f"Skipping {filename}: Date format incorrect.")
            continue
            
        distance = distance_part.upper().replace('K', '')
        
        try:
            # 1st Defense: low_memory=False prevents the chunking IndexError
            df = pd.read_csv(file_path, low_memory=False, on_bad_lines='skip', index_col=False)
            
        except Exception as e:
            try:
                # 2nd Defense: The 'python' engine is slower but more forgiving of messy formatting
                df = pd.read_csv(file_path, engine='python', on_bad_lines='skip')
            except Exception as e2:
                # If it still fails, log it and move to the next file
                print(f"CRITICAL ERROR on {filename}: {e2}")
                failed_files.append(filename)
                continue
        
        # Add the new metadata columns
        df['Year'] = year
        df['Month'] = month
        df['day'] = day
        df['distance'] = distance
        df['event'] = event_part
        
        # Append to our list
        dataframes.append(df)

print(f"Successfully loaded {len(dataframes)} CSV files.")
if failed_files:
    print(f"Failed to load {len(failed_files)} files.")
# %%

## Investigate Headers

# Dictionary to count how often each exact header appears across the files
header_frequency = Counter()

# Set to store every unique column name
all_unique_headers = set()

for df in dataframes:
    columns = df.columns.tolist()
    all_unique_headers.update(columns)
    
    for col in columns:
        header_frequency[col] += 1

print(f"Total unique columns across all files: {len(all_unique_headers)}\n")

print("--- Header Frequency (Top 30 most common) ---")
# Print the headers sorted by how often they appear
for col, count in header_frequency.most_common(30):
    print(f"{col}: appears in {count} files")

# Optional: Print the full alphabetized list of unique headers to scan for typos
print("\n--- All Unique Headers (Alphabetical) ---")
print(sorted(list(all_unique_headers)))


# %%

## Merge CSVs into one data frame

# 1. Merge all dataframes into one master DataFrame
master_df = pd.concat(dataframes, ignore_index=True)

# 2. Merge TIME (Prioritizing Netto -> Tijd -> Bruto)
master_df['TIME'] = master_df['Netto'].combine_first(master_df['Tijd']).combine_first(master_df['Bruto'])

# 3. Merge CLUB/RESIDENCE
master_df['CLUB/RESIDENCE'] = master_df['Vereniging'].combine_first(master_df['Woonplaats'])

# 4. Rename the remaining columns
rename_dict = {
    'Naam': 'NAME',
    'Year': 'YEAR',    
    'Month': 'MONTH',
    'day': 'DAY',
    'distance': 'DISTANCE',
    'event': 'EVENT',
    'Land': 'COUNTRY',
    'Categ': 'CLASS'
}
master_df.rename(columns=rename_dict, inplace=True)

# 5. Filter down to ONLY the exact columns you requested
final_columns = [
    'NAME', 'YEAR', 'MONTH', 'DAY', 'DISTANCE', 
    'EVENT', 'CLUB/RESIDENCE', 'TIME', 'COUNTRY', 'CLASS'
]

master_df = master_df[final_columns]

print("--- Merge & Formatting Complete ---")
print(f"Total rows: {len(master_df):,}")

# %%

## Clean up time column and extract unique class values


# --- 1. Clean the TIME column ---

def format_time_string(t):
    if pd.isna(t) or str(t).lower() in ['nan', 'none', '']:
        return pd.NaT
    
    t = str(t).strip()
    parts = t.split(':')
    
    # If the time is just MM:SS (like 59:51), prepend "00:" for hours
    if len(parts) == 2:
        return f"00:{t}"
    else:
        return t

# Apply formatting and convert to timedelta
master_df['TIME'] = master_df['TIME'].apply(format_time_string)
master_df['TIME'] = pd.to_timedelta(master_df['TIME'], errors='coerce')

print("--- Time Cleanup Complete ---")
print(f"Valid times parsed: {master_df['TIME'].notna().sum():,}")
print(f"Missing/Invalid times: {master_df['TIME'].isna().sum():,}\n")

# --- 2. Extract and Print Unique CLASS Values ---

unique_classes = master_df['CLASS'].dropna().unique()
sorted_classes = sorted([str(c).strip() for c in unique_classes])

print(f"--- Unique CLASS Values ({len(sorted_classes)} total) ---")
# Print them out neatly, 10 per line
for i in range(0, len(sorted_classes), 10):
    print(", ".join(sorted_classes[i:i+10]))

# %%

## Split classes into sex and age group


import re

# 1. Fill missing classes with a placeholder so our dictionary doesn't break on NaNs
master_df['CLASS'] = master_df['CLASS'].fillna('UNKNOWN')

# 2. Get our exact list of unique classes
unique_classes = master_df['CLASS'].unique()

# 3. Our parser logic (combining Sex splitting and the 3-tier Age bucketing)
def parse_class(cat):
    if cat == 'UNKNOWN':
        return pd.NA, 'Open'
        
    c = str(cat).upper()
    
    # Remove distance markers so they don't get read as ages
    c_clean = re.sub(r'(10K|5K|21K|15K|42K|10M|5M|HM|KM)', '', c)
    
    sex = pd.NA
    age_group = 'Open' # Default fallback
    
    # --- SEX ---
    if re.search(r'\b(V|D|F)\b|VROUW|DAMES|MEIS|VL|VP|VREC|VSEN|VMAS|VJUN', c):
        sex = 'F'
    elif re.search(r'\b(M|H|J)\b|MAN|HEREN|JONG|ML|MP|MREC|MSEN|MMAS|MJUN', c) or 'M' in c_clean or 'H' in c_clean:
        sex = 'M'
        
    # --- AGE GROUP ---
    # Catch text-based junior categories first (Dutch: Jongens/Meisjes)
    if 'JUN' in c or 'JONG' in c or 'MEIS' in c:
        age_group = 'Junior'
    else:
        # Extract the first numeric sequence
        num_match = re.search(r'\d+', c_clean)
        
        if num_match:
            age_str = num_match.group(0)
            
            # If it's a 4-digit sequence like '1215', grab just the first 2 digits
            if len(age_str) == 4:
                age = int(age_str[:2])
            else:
                age = int(age_str)
            
            # Bucket into our 3 distinct categories
            if age < 18:
                age_group = 'Junior'
            elif 55 <= age <= 99:
                age_group = 'Senior'
            else:
                age_group = 'Open' # Captures 18-54, and >99 anomalies
                
    return sex, age_group

# 4. Build mapping dictionaries by running the math ONLY on unique values
sex_mapping = {cat: parse_class(cat)[0] for cat in unique_classes}
age_mapping = {cat: parse_class(cat)[1] for cat in unique_classes}

# 5. Instantly map the answers back to the 1.48 million rows
master_df['SEX'] = master_df['CLASS'].map(sex_mapping)
master_df['AGE_GROUP'] = master_df['CLASS'].map(age_mapping)

# Drop the old CLASS column
master_df.drop(columns=['CLASS'], inplace=True)

print("--- Category Splitting & Simplification Complete ---")
print(f"Total Rows: {len(master_df):,}\n")

# Verify the final Age Group buckets
print("--- Final AGE_GROUP Distribution ---")
print(master_df['AGE_GROUP'].value_counts(dropna=False))

# Preview the final results
display(master_df[['NAME', 'EVENT', 'SEX', 'AGE_GROUP', 'TIME']].head(15))
# %%

## Data Verification - 

# --- 1. Verify SEX and AGE_GROUP ---

# Get unique, sorted values for SEX
unique_sex = master_df['SEX'].dropna().unique()
sorted_sex = sorted([str(s) for s in unique_sex])

print(f"--- Unique SEX Values ({len(sorted_sex)} total) ---")
print(", ".join(sorted_sex) + "\n")

# Get unique, sorted values for AGE_GROUP
unique_age = master_df['AGE_GROUP'].dropna().unique()
sorted_age = sorted([str(a) for a in unique_age])

print(f"--- Unique AGE_GROUP Values ({len(sorted_age)} total) ---")
for i in range(0, len(sorted_age), 10):
    print(", ".join(sorted_age[i:i+10]))
print("\n")


# --- 2. Initial Data Profiling (Health Check) ---

print("--- Master DataFrame Health Check ---")
# .info() gives us row counts, column types, and non-null counts
master_df.info(show_counts=True)

print("\n--- Missing Values Count ---")
print(master_df.isna().sum())

print("\n--- Date Range Verification ---")
# Quick check to ensure years imported correctly
print(f"Earliest Year: {master_df['YEAR'].min()}")
print(f"Latest Year: {master_df['YEAR'].max()}")


# %%

## First Histogram 


import matplotlib.pyplot as plt
import numpy as np

# --- 1. Convert TIME to Numeric ---
master_df['TIME_MINS'] = master_df['TIME'].dt.total_seconds() / 60

# --- 2. Prepare Data ---
def sort_key(x):
    try:
        return float(x)
    except ValueError:
        return 9999.0 

# Get our 4 distances and sort them numerically
distances = sorted(master_df['DISTANCE'].dropna().unique(), key=sort_key)

# Define some distinct colors for the 4 charts
colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']

# Calculate the global max time for a clean X-axis limit (99.5th percentile)
max_time = master_df['TIME_MINS'].quantile(0.995)

# --- 3. Plot the Histograms (Vertically Stacked) ---
# sharex=True forces all subplots to align to the exact same X-axis scale
fig, axes = plt.subplots(nrows=len(distances), ncols=1, figsize=(14, 12), sharex=True)

# Loop through our distances and axes to plot each one
for i, (dist, ax) in enumerate(zip(distances, axes)):
    # Filter data for this specific distance
    dist_data = master_df[master_df['DISTANCE'] == dist]['TIME_MINS'].dropna()
    
    # Plot on this specific subplot
    ax.hist(dist_data, bins=100, color=colors[i % len(colors)], edgecolor='black', linewidth=0.5, alpha=0.8)
    
    # Subplot formatting
    ax.set_title(f'Finish Times for {dist}K', fontsize=14, fontweight='bold')
    ax.set_ylabel('Runners', fontsize=12)
    ax.grid(axis='y', alpha=0.3, linestyle='--')

# Set the shared X-axis label only on the bottom chart
axes[-1].set_xlabel('Finish Time (Minutes)', fontsize=14)

# Apply our global X-axis limits so they all match perfectly
plt.xlim(10, max_time)

# Adjust layout so titles and labels don't overlap
plt.tight_layout()
plt.show()

# --- 4. Print Summary Stats for Validation ---
print("--- Summary Statistics by Distance ---")

# Added 'mean' and 'std' to the aggregation list
summary_df = master_df.groupby('DISTANCE')['TIME_MINS'].agg(
    ['count', 'min', 'median', 'mean', 'std', 'max']
).round(1)

# Sort by the most popular race distances
summary_df.sort_values('count', ascending=False, inplace=True)
display(summary_df)

#%%

## Histogram with classes split out  


import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

# --- 1. Convert TIME to Numeric ---
master_df['TIME_MINS'] = master_df['TIME'].dt.total_seconds() / 60

# --- 2. Prepare Data & Aesthetics ---
def sort_key(x):
    try:
        return float(x)
    except ValueError:
        return 9999.0 

# Get our distances and sort them numerically
distances = sorted(master_df['DISTANCE'].dropna().unique(), key=sort_key)

# Calculate the global max time for a clean X-axis limit (99.5th percentile)
max_time = master_df['TIME_MINS'].quantile(0.995)

# Extract base RGB colors for Male (Blue) and Female (Red)
base_blue = mcolors.to_rgb('tab:blue')
base_red = mcolors.to_rgb('tab:red')

# Define our 6 demographic permutations (SEX, AGE_GROUP, RGBA_COLOR)
# RGBA is (Red, Green, Blue, Alpha/Opacity)
demographics = [
    ('F', 'Junior', base_red + (0.4,)),  # Light Red
    ('F', 'Open',   base_red + (0.7,)),  # Medium Red
    ('F', 'Senior', base_red + (1.0,)),  # Solid Red
    ('M', 'Junior', base_blue + (0.4,)), # Light Blue
    ('M', 'Open',   base_blue + (0.7,)), # Medium Blue
    ('M', 'Senior', base_blue + (1.0,))  # Solid Blue
]

# --- 3. Plot the Histograms (Vertically Stacked) ---
fig, axes = plt.subplots(nrows=len(distances), ncols=1, figsize=(14, 16), sharex=True)

# If there's only one distance, axes isn't a list. This ensures it's always iterable.
if len(distances) == 1:
    axes = [axes]

for dist, ax in zip(distances, axes):
    dist_data = master_df[master_df['DISTANCE'] == dist]
    
    # We need to build a list of arrays and a list of colors for the stacked histogram
    arrays_to_plot = []
    labels = []
    colors = []
    
    for sex, age, color in demographics:
        # Filter down to the specific permutation
        subset = dist_data[(dist_data['SEX'] == sex) & (dist_data['AGE_GROUP'] == age)]['TIME_MINS'].dropna()
        
        arrays_to_plot.append(subset)
        labels.append(f"{sex} - {age}")
        colors.append(color)
    
    # Plot the stacked histogram for this specific distance
    ax.hist(arrays_to_plot, bins=100, stacked=True, color=colors, label=labels, 
            edgecolor='black', linewidth=0.2)
    
    # Subplot formatting
    ax.set_title(f'Finish Times for {dist}K ', fontsize=14, fontweight='bold')
    ax.set_ylabel('Runners', fontsize=12)
    ax.grid(axis='y', alpha=0.3, linestyle='--')

# Set the shared X-axis label only on the bottom chart
axes[-1].set_xlabel('Finish Time (Minutes)', fontsize=14)

# Apply our global X-axis limits so they all match perfectly
plt.xlim(10, max_time)

# Add a single legend to the top-right of the entire figure
axes[0].legend(title='Demographics', fontsize=11, title_fontsize=12, loc='upper right')

# Adjust layout
plt.tight_layout()
plt.show()

# --- 4. Print Summary Stats for Validation ---
print("--- Summary Statistics by Distance ---")
summary_df = master_df.groupby('DISTANCE')['TIME_MINS'].agg(
    ['count', 'min', 'median', 'mean', 'std', 'max']
).round(1)
summary_df.sort_values('count', ascending=False, inplace=True)
display(summary_df)

# %%

## Verify that marathon times aren't faster than world record, look at 5k times to makes ure they're not super slow

# --- 1. Investigate the 42K Anomalies (The "Impossible" Marathons) ---
# Filter for 42K times under 130 minutes (which is near world-record pace)
fast_42k = master_df[(master_df['DISTANCE'] == '42') & (master_df['TIME_MINS'] < 115)]

print("--- 42K ANOMALIES (Under 130 Mins) ---")
print(f"Total weird rows: {len(fast_42k):,}")
print("\nWhich Events are these coming from?")
print(fast_42k[['EVENT', 'YEAR']].value_counts().head(50))


# --- 2. Investigate the 5K Anomalies (The "Super Slow" 5Ks) ---
# Filter for 5K times over 55 minutes (where that second curve starts)
slow_5k = master_df[(master_df['DISTANCE'] == '5') & (master_df['TIME_MINS'] > 55)]

print("\n\n--- 5K ANOMALIES (Over 55 Mins) ---")
print(f"Total weird rows: {len(slow_5k):,}")
print("\nWhich Events are these coming from?")
print(slow_5k[['EVENT', 'YEAR']].value_counts().head(50))

# %%

##Look at how the running times evolved over time to see effect of super shoes


import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

# Filter out physically impossible times (using generous world-record buffers)
valid_times = (
    ((master_df['DISTANCE'] == '5') & (master_df['TIME_MINS'] >= 12)) |
    ((master_df['DISTANCE'] == '10') & (master_df['TIME_MINS'] >= 26)) |
    ((master_df['DISTANCE'] == '21') & (master_df['TIME_MINS'] >= 57)) |
    ((master_df['DISTANCE'] == '42') & (master_df['TIME_MINS'] >= 115)) 
)
master_df = master_df[valid_times]

print("--- Summary Statistics by Distance ---")
summary_df = master_df.groupby('DISTANCE')['TIME_MINS'].agg(
    ['count', 'min', 'median', 'mean', 'std', 'max']
).round(1)
summary_df.sort_values('count', ascending=False, inplace=True)
display(summary_df)

# --- 1. Create a proper Date Column ---
master_df['DATE'] = pd.to_datetime(master_df['YEAR'].astype(str) + '-' + 
                                   master_df['MONTH'].astype(str) + '-' + 
                                   master_df['DAY'].astype(str), errors='coerce')

distances_to_plot = ['21', '42']

# --- 2. Setup the Subplots ---
fig, axes = plt.subplots(nrows=len(distances_to_plot), ncols=1, figsize=(16, 16), sharex=True)

# Define the split date for the trendlines
split_date = pd.to_datetime('2017-01-01')

for i, (dist, ax) in enumerate(zip(distances_to_plot, axes)):
    
    df_dist = master_df[master_df['DISTANCE'] == dist].dropna(subset=['DATE', 'TIME_MINS'])
    
    trend_df = df_dist.groupby('DATE')['TIME_MINS'].agg(
        Top_5_Percent=lambda x: x.quantile(0.05),  
        Top_10_Percent=lambda x: x.quantile(0.10), 
        Top_25_Percent=lambda x: x.quantile(0.25), 
        Overall_Avg='mean'                         
    ).reset_index()
    
    trend_df.sort_values('DATE', inplace=True)
    
    # Define metrics and their assigned colors
    metrics = [
        ('Top_5_Percent', '#d62728', 'Top 5% (Fastest)'),
        ('Top_10_Percent', '#ff7f0e', 'Top 10%'),
        ('Top_25_Percent', '#2ca02c', 'Top 25%'),
        ('Overall_Avg', '#7f7f7f', 'Overall Average')
    ]
    
    # --- 3. Plot Raw Data & Trendlines ---
    for col, color, label in metrics:
        # Plot the raw data faint and transparent
        ax.plot(trend_df['DATE'], trend_df[col], color=color, linewidth=1, marker='o', markersize=3, alpha=0.3, label=label)
        
        # Calculate Trendline 1: Pre-2017
        pre_mask = trend_df['DATE'] < split_date
        if pre_mask.sum() > 1:
            x_pre = mdates.date2num(trend_df.loc[pre_mask, 'DATE']) # Convert dates to numbers for regression
            y_pre = trend_df.loc[pre_mask, col]
            
            # Polyfit (Degree 1 = Linear)
            z_pre = np.polyfit(x_pre, y_pre, 1)
            p_pre = np.poly1d(z_pre)
            ax.plot(trend_df.loc[pre_mask, 'DATE'], p_pre(x_pre), color=color, linestyle='-', linewidth=3.5)
            
        # Calculate Trendline 2: Post-2017
        post_mask = trend_df['DATE'] >= split_date
        if post_mask.sum() > 1:
            x_post = mdates.date2num(trend_df.loc[post_mask, 'DATE'])
            y_post = trend_df.loc[post_mask, col]
            
            z_post = np.polyfit(x_post, y_post, 1)
            p_post = np.poly1d(z_post)
            ax.plot(trend_df.loc[post_mask, 'DATE'], p_post(x_post), color=color, linestyle='-', linewidth=3.5)

    # --- 4. Annotate the Eras ---
    super_shoe_date = pd.to_datetime('2017-02-01')
    ax.axvline(x=super_shoe_date, color='black', linestyle=':', linewidth=2, label='Super Shoes Intro (Feb 2017)' if i==0 else "")    
    # --- 5. Formatting ---
    ax.set_title(f'{dist}K Finish Times Over Time', fontsize=16, fontweight='bold')
    ax.set_ylabel('Time (Minutes)', fontsize=12)
    ax.grid(axis='both', alpha=0.3, linestyle='--')
    
    if i == 0:
        # Custom legend to avoid duplicating the label for the raw data vs trendline
        handles, labels = ax.get_legend_handles_labels()
        # Keep only the first 6 unique labels (4 metrics + 2 era lines)
        by_label = dict(zip(labels, handles))
        ax.legend(by_label.values(), by_label.keys(), loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=11, title='Metrics & Eras')
    
    print(f"Length {dist}K - Total Events: {len(trend_df):,}")
    pd.set_option('display.max_rows', None)
    display(trend_df)
    pd.reset_option('display.max_rows')

# Format the shared X-axis cleanly
axes[-1].set_xlabel('Race Date', fontsize=16)
axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
axes[-1].xaxis.set_major_locator(mdates.YearLocator(2)) 

plt.tight_layout()
plt.subplots_adjust(right=0.85) 
plt.show()


# %%

## Show table of Club size vs speed

# Set minimum volume of participants
min_runners = 20 

# List of international countries/elites to exclude
exclude_list = [
    'Kenia', 'Marokko', 'Ethiopië', 'België', 'Duitsland', 
    'Groot-Brittannië', 'Zweden', 'Tsjechië', 'Finland', 'Estland'
]

# Filter out rows where the club/residence is missing
df_clubs = master_df.dropna(subset=['CLUB/RESIDENCE', 'TIME_MINS'])

# Remove the excluded countries (case-insensitive just to be safe)
df_clubs = df_clubs[~df_clubs['CLUB/RESIDENCE'].str.title().isin(exclude_list)]

# Get our specific distances
distances_to_plot = ['5', '10', '21', '42']

for dist in distances_to_plot:
    # 1. Filter the dataset for just this distance
    dist_data = df_clubs[df_clubs['DISTANCE'] == dist]
    
    # 2. Group by Club/Residence and calculate stats
    club_stats = dist_data.groupby('CLUB/RESIDENCE')['TIME_MINS'].agg(
        Total_Runners='count',
        Median_Time='median',
        Mean_Time='mean'
    ).reset_index()
    
    # 3. Filter out the small clubs/solo runners
    valid_clubs = club_stats[club_stats['Total_Runners'] >= min_runners]
    
    # 4. Sort by the fastest Median Time
    top_30_fastest = valid_clubs.sort_values(by='Median_Time', ascending=True).head(30)
    
    # Round the times for cleaner display
    top_30_fastest['Median_Time'] = top_30_fastest['Median_Time'].round(1)
    top_30_fastest['Mean_Time'] = top_30_fastest['Mean_Time'].round(1)
    
    # Add a rank column starting from 1
    top_30_fastest.insert(0, 'Rank', range(1, 1 + len(top_30_fastest)))
    
    # Print and display the results
    print(f"========== Top 30 Fastest Clubs/Cities for {dist}K ==========")
    print(f"(Filtered for clubs with at least {min_runners} runners, excluding specific countries)")
    
    # We set the index to Rank so it looks like a clean leaderboard
    display(top_30_fastest.set_index('Rank'))
    print("\n")
# %%

## Plot Club size vs speed

import matplotlib.pyplot as plt
import numpy as np

# Set a minimum threshold to remove extreme noise (solo runners) but keep small clubs
min_runners_scatter = 20 

# List of international countries to exclude (same as before)
exclude_list = [
    'Kenia', 'Marokko', 'Ethiopië', 'België', 'Duitsland', 
    'Groot-Brittannië', 'Zweden', 'Tsjechië', 'Finland', 'Estland'
]

# Filter out missing clubs and excluded countries
df_clubs_scatter = master_df.dropna(subset=['CLUB/RESIDENCE', 'TIME_MINS'])
df_clubs_scatter = df_clubs_scatter[~df_clubs_scatter['CLUB/RESIDENCE'].str.title().isin(exclude_list)]

distances_to_plot = ['5', '10', '21', '42']
colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']

# Setup 4 subplots (2x2 grid is usually better for scatter plots so they aren't squished)
fig, axes = plt.subplots(nrows=2, ncols=2, figsize=(16, 12))
axes = axes.flatten() # Flatten the 2x2 grid into a 1D array for easy looping

for i, dist in enumerate(distances_to_plot):
    ax = axes[i]
    
    # 1. Filter and Group Data
    dist_data = df_clubs_scatter[df_clubs_scatter['DISTANCE'] == dist]
    
    club_stats = dist_data.groupby('CLUB/RESIDENCE')['TIME_MINS'].agg(
        Total_Runners='count',
        Median_Time='median'
    ).reset_index()
    
    # 2. Filter out tiny groups
    valid_clubs = club_stats[club_stats['Total_Runners'] >= min_runners_scatter]
    
    valid_clubs = valid_clubs.sort_values(by='Median_Time', ascending=True).head(40)
    
    # Extract X and Y for plotting
    x = valid_clubs['Total_Runners']
    y = valid_clubs['Median_Time']
    
    # 3. Plot the Scatter Points
    ax.scatter(x, y, alpha=0.5, color=colors[i], edgecolor='black', linewidth=0.5, s=40, label='Clubs')
    
    # 4. Calculate and Plot the Trendline (Linear Regression)
    if len(x) > 1:
        z = np.polyfit(x, y, 1)
        p = np.poly1d(z)
        
        # Create a line of X values from min to max
        x_line = np.linspace(x.min(), x.max(), 100)
        
        # Plot the trendline
        ax.plot(x_line, p(x_line), color='black', linewidth=2.5, linestyle='--', label='Trendline')
        
        # Calculate correlation coefficient (R-value)
        corr_matrix = np.corrcoef(x, y)
        corr = corr_matrix[0, 1]
        ax.annotate(f"Correlation (r): {corr:.2f}", xy=(0.05, 0.05), xycoords='axes fraction', 
                    fontsize=12, fontweight='bold', backgroundcolor='white')

    # 5. Formatting
    ax.set_title(f'{dist}K : Club Size vs. Speed', fontsize=14, fontweight='bold')
    ax.set_xlabel('Total Number of Runners (Club Size)', fontsize=12)
    ax.set_ylabel('Median Finish Time (Minutes)', fontsize=12)
    ax.grid(alpha=0.3, linestyle='--')
    ax.legend()

plt.tight_layout()
plt.show()
# %%
import pandas as pd

## Regression taking events into account

# --- 1. Load the Weather Data ---
weather_df = pd.read_csv('Cleaned_Weather_Data.csv')

# --- 2. Format the Weather Dates ---
# Create a proper datetime column to match our master_df perfectly
weather_df['DATE'] = pd.to_datetime(weather_df['YEAR'].astype(str) + '-' + 
                                    weather_df['MONTH'].astype(str) + '-' + 
                                    weather_df['DAY'].astype(str), errors='coerce')


# Drop the individual date columns from weather_df to prevent duplicates after the merge
weather_df.drop(columns=['YEAR', 'MONTH', 'DAY'], inplace=True)

# --- 3. Merge the Datasets ---
# We use a 'left' merge to keep all of our runners, even if a specific day is missing weather data
master_df = master_df.merge(weather_df, on='DATE', how='left')

# --- 4. Verification (DEP Phase) ---
print("--- Weather Merge Complete ---")
print(f"Total rows in master_df: {len(master_df):,}")

print("\n--- Missing Weather Data Check ---")
# Check if any race days didn't have a match in the weather CSV
missing_weather = master_df['AVG_TEMP'].isna().sum()
print(f"Runners missing weather data: {missing_weather:,} ({(missing_weather/len(master_df))*100:.1f}%)")

# Preview the newly enriched dataset!
display(master_df.head(10))
# %%
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import statsmodels.formula.api as smf

# --- 1. Prepare Data for Regression ---
reg_df = master_df[master_df['DISTANCE'] == '42'].copy()

features = ['TIME_MINS', 'AVG_TEMP', 'AVG_WIND', 'AVG_HUMIDITY', 'DAILY_PRECIPITATION', 'SEX', 'AGE_GROUP', 'EVENT']
reg_df.dropna(subset=features, inplace=True)

# Remove the 'UNKNOWN' sex placeholder if it exists
reg_df = reg_df[reg_df['SEX'].isin(['M', 'F'])]

# --- 2. Build the Ordinary Least Squares (OLS) Model ---
# We use Treatment(reference='...') to explicitly set the baselines!
formula = (
    "TIME_MINS ~ AVG_TEMP + AVG_WIND + AVG_HUMIDITY + DAILY_PRECIPITATION + "
    "C(SEX, Treatment(reference='M')) + "
    "C(AGE_GROUP, Treatment(reference='Open')) + "
    "C(EVENT)" 
)

print("Fitting Multiple Linear Regression Model... (This may take a moment)")
model = smf.ols(formula, data=reg_df).fit()

print(model.summary())

# --- 3. Visualize the Coefficients for the Slide Deck ---
coeffs = model.params.drop('Intercept')
pvalues = model.pvalues.drop('Intercept')

coef_df = pd.DataFrame({'Coefficient': coeffs, 'P-Value': pvalues})
coef_df = coef_df.sort_values('Coefficient')

# Dynamic function to clean up the statsmodels category labels
def clean_label(label):
    if label == "C(SEX, Treatment(reference='M'))[T.F]": return 'Sex: Female (vs Male)'
    if label == "C(AGE_GROUP, Treatment(reference='Open'))[T.Junior]": return 'Age: Junior (vs Open)'
    if label == "C(AGE_GROUP, Treatment(reference='Open'))[T.Senior]": return 'Age: Senior (vs Open)'
    if label == 'AVG_TEMP': return 'Avg Temp (°C)'
    if label == 'AVG_WIND': return 'Avg Wind Speed'
    if label == 'AVG_HUMIDITY': return 'Humidity (%)'
    if label == 'DAILY_PRECIPITATION': return 'Precipitation (mm)'
    if label.startswith('C(EVENT)'):
        return 'Event: ' + label.split('[T.')[1].replace(']', '')
    return label

coef_df.index = [clean_label(idx) for idx in coef_df.index]

# Dynamically adjust figure height based on how many events get plotted
fig_height = max(7, len(coef_df) * 0.5)
plt.figure(figsize=(12, fig_height))

# Color code: green for faster (negative), red for slower (positive)
colors = ['#2ca02c' if c < 0 else '#d62728' for c in coef_df['Coefficient']]

bars = plt.barh(coef_df.index, coef_df['Coefficient'], color=colors, edgecolor='black', alpha=0.8)

# Add the specific numbers AND p-values to the end of the bars
for bar, pval in zip(bars, coef_df['P-Value']):
    width = bar.get_width()
    
    # Format the p-value for readability
    if pval < 0.001:
        p_str = "p<0.001"
    else:
        p_str = f"p={pval:.3f}"
        
    label_text = f"{width:.1f} min ({p_str})"
    
    # Adjust text position and alignment based on whether the bar goes left or right
    if width < 0:
        label_x_pos = width - 0.5
        ha_align = 'right'
    else:
        label_x_pos = width + 0.5
        ha_align = 'left'
        
    plt.text(label_x_pos, bar.get_y() + bar.get_height()/2, label_text, 
             va='center', ha=ha_align, fontsize=10, fontweight='bold')

plt.axvline(0, color='black', linewidth=1.5)
plt.title('Impact of Weather, Demographics & Course on Marathon Times', fontsize=16, fontweight='bold')
plt.xlabel('Effect on Finish Time (Minutes)\n← Faster | Slower →', fontsize=12)

# Give the X-axis a little extra breathing room so the new longer text labels don't get cut off
plt.margins(x=0.25)

# Subtitle to explain the baseline explicitly naming Amsterdam
subtitle_text = "*Categorical baselines: Sex=Male, Age=Open, Event=amsterdammarathon. Positive = slower time."
plt.text(0.5, -0.15, subtitle_text, ha='center', va='center', 
         transform=plt.gca().transAxes, fontsize=11, style='italic', color='gray')

plt.grid(axis='x', alpha=0.3, linestyle='--')
plt.tight_layout()
plt.show()
# %%
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import statsmodels.formula.api as smf

# --- 1. Prepare Data for Regression ---
reg_df = master_df[master_df['DISTANCE'] == '42'].copy()

# Removed 'EVENT' from the features list
features = ['TIME_MINS', 'AVG_TEMP', 'AVG_WIND', 'AVG_HUMIDITY', 'DAILY_PRECIPITATION', 'SEX', 'AGE_GROUP']
reg_df.dropna(subset=features, inplace=True)

# Remove the 'UNKNOWN' sex placeholder if it exists
reg_df = reg_df[reg_df['SEX'].isin(['M', 'F'])]

# --- 2. Build the Ordinary Least Squares (OLS) Model ---
# Removed C(EVENT) from the regression formula
formula = (
    "TIME_MINS ~ AVG_TEMP + AVG_WIND + AVG_HUMIDITY + DAILY_PRECIPITATION + "
    "C(SEX, Treatment(reference='M')) + "
    "C(AGE_GROUP, Treatment(reference='Open'))" 
)

print("Fitting Multiple Linear Regression Model (Without Event)...")
model = smf.ols(formula, data=reg_df).fit()

print(model.summary())

# --- 3. Visualize the Coefficients for the Slide Deck ---
coeffs = model.params.drop('Intercept')
pvalues = model.pvalues.drop('Intercept')

coef_df = pd.DataFrame({'Coefficient': coeffs, 'P-Value': pvalues})
coef_df = coef_df.sort_values('Coefficient')

# Dynamic function to clean up the statsmodels category labels
def clean_label(label):
    if label == "C(SEX, Treatment(reference='M'))[T.F]": return 'Sex: Female (vs Male)'
    if label == "C(AGE_GROUP, Treatment(reference='Open'))[T.Junior]": return 'Age: Junior (vs Open)'
    if label == "C(AGE_GROUP, Treatment(reference='Open'))[T.Senior]": return 'Age: Senior (vs Open)'
    if label == 'AVG_TEMP': return 'Avg Temp (°C)'
    if label == 'AVG_WIND': return 'Avg Wind Speed'
    if label == 'AVG_HUMIDITY': return 'Humidity (%)'
    if label == 'DAILY_PRECIPITATION': return 'Precipitation (mm)'
    return label

coef_df.index = [clean_label(idx) for idx in coef_df.index]

# Set a fixed, smaller figure height since we only have a handful of variables now
plt.figure(figsize=(10, 6))

# Color code: green for faster (negative), red for slower (positive)
colors = ['#2ca02c' if c < 0 else '#d62728' for c in coef_df['Coefficient']]

bars = plt.barh(coef_df.index, coef_df['Coefficient'], color=colors, edgecolor='black', alpha=0.8)

# Add the specific numbers AND p-values to the end of the bars
for bar, pval in zip(bars, coef_df['P-Value']):
    width = bar.get_width()
    
    # Format the p-value for readability
    if pval < 0.001:
        p_str = "p<0.001"
    else:
        p_str = f"p={pval:.3f}"
        
    label_text = f"{width:.1f} min ({p_str})"
    
    # Adjust text position and alignment based on whether the bar goes left or right
    if width < 0:
        label_x_pos = width - 0.5
        ha_align = 'right'
    else:
        label_x_pos = width + 0.5
        ha_align = 'left'
        
    plt.text(label_x_pos, bar.get_y() + bar.get_height()/2, label_text, 
             va='center', ha=ha_align, fontsize=10, fontweight='bold')

plt.axvline(0, color='black', linewidth=1.5)

# Removed "Course" from the title
plt.title('Impact of Weather & Demographics on Marathon Times', fontsize=16, fontweight='bold')
plt.xlabel('Effect on Finish Time (Minutes)\n← Faster | Slower →', fontsize=12)

# Give the X-axis a little extra breathing room so the new longer text labels don't get cut off
plt.margins(x=0.25)

# Removed Event from the subtitle baseline explanation
subtitle_text = "*Categorical baselines: Sex=Male, Age=Open. Positive = slower time."
plt.text(0.5, -0.15, subtitle_text, ha='center', va='center', 
         transform=plt.gca().transAxes, fontsize=11, style='italic', color='gray')

plt.grid(axis='x', alpha=0.3, linestyle='--')
plt.tight_layout()
plt.show()
# %%
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

# Filter out physically impossible times (using generous world-record buffers)
valid_times = (
    ((master_df['DISTANCE'] == '5') & (master_df['TIME_MINS'] >= 12)) |
    ((master_df['DISTANCE'] == '10') & (master_df['TIME_MINS'] >= 26)) |
    ((master_df['DISTANCE'] == '21') & (master_df['TIME_MINS'] >= 57)) |
    ((master_df['DISTANCE'] == '42') & (master_df['TIME_MINS'] >= 115)) 
)
master_df = master_df[valid_times]

print("--- Summary Statistics by Distance ---")
summary_df = master_df.groupby('DISTANCE')['TIME_MINS'].agg(
    ['count', 'min', 'median', 'mean', 'std', 'max']
).round(1)
summary_df.sort_values('count', ascending=False, inplace=True)
display(summary_df)

# --- 1. Create a proper Date Column ---
master_df['DATE'] = pd.to_datetime(master_df['YEAR'].astype(str) + '-' + 
                                   master_df['MONTH'].astype(str) + '-' + 
                                   master_df['DAY'].astype(str), errors='coerce')

distances_to_plot = ['21', '42']

# --- 2. Setup the Subplots ---
fig, axes = plt.subplots(nrows=len(distances_to_plot), ncols=1, figsize=(16, 16), sharex=True)

# Define the split date for the trendlines
split_date = pd.to_datetime('2017-01-01')

for i, (dist, ax) in enumerate(zip(distances_to_plot, axes)):
    
    # Ensure EVENT is not null so we can normalize by it
    df_dist = master_df[master_df['DISTANCE'] == dist].dropna(subset=['DATE', 'TIME_MINS', 'EVENT']).copy()
    
    # =====================================================================
    # --- THE FIX: COURSE NORMALIZATION (Controlling for Event) ---
    # 1. Get the global median for this distance
    global_median = df_dist['TIME_MINS'].median()
    
    # 2. Get the median for each specific event
    df_dist['EVENT_MEDIAN'] = df_dist.groupby('EVENT')['TIME_MINS'].transform('median')
    
    # 3. Calculate the Adjusted Time 
    # (Runner's raw time - Course Median + Global Median)
    df_dist['ADJUSTED_TIME'] = df_dist['TIME_MINS'] - df_dist['EVENT_MEDIAN'] + global_median
    # =====================================================================

    # Now group by DATE using our newly calculated ADJUSTED_TIME
    trend_df = df_dist.groupby('DATE')['ADJUSTED_TIME'].agg(
        Top_5_Percent=lambda x: x.quantile(0.05),  
        Top_10_Percent=lambda x: x.quantile(0.10), 
        Top_25_Percent=lambda x: x.quantile(0.25), 
        Overall_Avg='mean'                         
    ).reset_index()
    
    trend_df.sort_values('DATE', inplace=True)
    
    # Define metrics and their assigned colors
    metrics = [
        ('Top_5_Percent', '#d62728', 'Top 5% (Fastest)'),
        ('Top_10_Percent', '#ff7f0e', 'Top 10%'),
        ('Top_25_Percent', '#2ca02c', 'Top 25%'),
        ('Overall_Avg', '#7f7f7f', 'Overall Average')
    ]
    
    # --- 3. Plot Raw Data & Trendlines ---
    for col, color, label in metrics:
        # Plot the raw data faint and transparent
        ax.plot(trend_df['DATE'], trend_df[col], color=color, linewidth=1, marker='o', markersize=3, alpha=0.3, label=label)
        
        # Calculate Trendline 1: Pre-2017
        pre_mask = trend_df['DATE'] < split_date
        if pre_mask.sum() > 1:
            x_pre = mdates.date2num(trend_df.loc[pre_mask, 'DATE']) 
            y_pre = trend_df.loc[pre_mask, col]
            
            z_pre = np.polyfit(x_pre, y_pre, 1)
            p_pre = np.poly1d(z_pre)
            ax.plot(trend_df.loc[pre_mask, 'DATE'], p_pre(x_pre), color=color, linestyle='-', linewidth=3.5)
            
        # Calculate Trendline 2: Post-2017
        post_mask = trend_df['DATE'] >= split_date
        if post_mask.sum() > 1:
            x_post = mdates.date2num(trend_df.loc[post_mask, 'DATE'])
            y_post = trend_df.loc[post_mask, col]
            
            z_post = np.polyfit(x_post, y_post, 1)
            p_post = np.poly1d(z_post)
            ax.plot(trend_df.loc[post_mask, 'DATE'], p_post(x_post), color=color, linestyle='-', linewidth=3.5)

    # --- 4. Annotate the Eras ---
    super_shoe_date = pd.to_datetime('2017-02-01')
    ax.axvline(x=super_shoe_date, color='black', linestyle=':', linewidth=2, label='Super Shoes Intro (Feb 2017)' if i==0 else "")    
    
    # --- 5. Formatting ---
    ax.set_title(f'{dist}K Normalized Finish Times Over Time (Controlled for Course)', fontsize=16, fontweight='bold')
    ax.set_ylabel('Adjusted Time (Minutes)', fontsize=12)
    ax.grid(axis='both', alpha=0.3, linestyle='--')
    
    if i == 0:
        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        ax.legend(by_label.values(), by_label.keys(), loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=11, title='Metrics & Eras')
    
    print(f"Length {dist}K - Total Events: {len(trend_df):,}")
    

# Format the shared X-axis cleanly
axes[-1].set_xlabel('Race Date', fontsize=16)
axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
axes[-1].xaxis.set_major_locator(mdates.YearLocator(2)) 

plt.tight_layout()
plt.subplots_adjust(right=0.85) 
plt.show()
# %%
