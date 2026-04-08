import pandas as pd

# Importing
df= pd.read_csv("Weatherdata.csv", parse_dates=["YYYYMMDD"])
print(df.head)



