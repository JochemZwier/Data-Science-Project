#%%
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
# --- 1. Investigate the 42K Anomalies (The "Impossible" Marathons) ---
# Filter for 42K times under 130 minutes (which is near world-record pace)
fast_42k = master_df[(master_df['DISTANCE'] == '42') & (master_df['TIME_MINS'] < 130)]

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

master_df.head(10)
# %%
