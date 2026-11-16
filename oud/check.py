import pandas as pd

log = pd.read_csv("log.csv")
print(log.groupby(["locatie", "opgehaald_op"]).size())
