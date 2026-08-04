import os
import json
import base64
import requests

TOKEN = os.getenv("GITHUB_TOKEN")
OWNER = "prathambhandary"
REPO = "JUT-ReMaker"
BRANCH = "main"
FILE = "data/test_download_data.json"

url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{FILE}"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json"
}


def update_github_json(new_data):
    # Fetch existing file
    r = requests.get(url, headers=headers)
    r.raise_for_status()

    file_info = r.json()
    sha = file_info["sha"]

    # Decode existing JSON
    existing = json.loads(
        base64.b64decode(file_info["content"]).decode("utf-8")
    )

    # Append new object
    existing.append(new_data)

    # Encode updated JSON
    content = base64.b64encode(
        json.dumps(existing, indent=4).encode("utf-8")
    ).decode("utf-8")

    payload = {
        "message": f"Add {new_data['exam_type']} {new_data['exam_number']}",
        "content": content,
        "sha": sha,
        "branch": BRANCH
    }

    r = requests.put(url, headers=headers, json=payload)
    r.raise_for_status()

    print("Updated successfully!")