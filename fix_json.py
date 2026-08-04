
# add 10 to all jut numbers in test_download_data.json file

import json


with open("data/test_download_data.json", "r") as f:
    data = json.load(f)

for item in data:
    item["jut_number"] += 10

with open("data/test_download_data.json", "w") as f:
    json.dump(data, f)