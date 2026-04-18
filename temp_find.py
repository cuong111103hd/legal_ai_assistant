import pickle
import os

pkl_path = 'data/chunks_metadata.pkl'
with open(pkl_path, 'rb') as f:
    data = pickle.load(f)

keywords = ['lao động', 'hợp đồng', 'tiền lương', 'bảo hiểm']
found = []
for cid, chunk in data.items():
    content = chunk['content'].lower()
    if any(k in content for k in keywords):
        found.append(chunk)
    if len(found) >= 5:
        break

for f in found:
    print(f"--- {f['law_name']} ({f['article_id']}) ---")
    print(f['content'][:400])
    print("\n")
