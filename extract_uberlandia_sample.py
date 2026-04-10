import csv, json
from pathlib import Path
from collections import defaultdict
import pandas as pd

csv.field_size_limit(10_000_000)

av = pd.read_csv("analises/03_uberlandia_avaliacoes.csv")
n_corr = (av["verdict"] == "CORRETO").sum()
n_err  = (av["verdict"] == "ERRADO").sum()
print(f"Disponível: {n_corr} CORRETO, {n_err} ERRADO")
n_each = min(69, n_corr, n_err)  # pega todos os CORRETOs (só 69)
s_ok = av[av["verdict"] == "CORRETO"].sample(n_each, random_state=42)
s_er = av[av["verdict"] == "ERRADO"].sample(min(131, n_err), random_state=42)
sample = pd.concat([s_ok, s_er])
sample.to_csv("analises/sample_uberlandia_200.csv", index=False)
target_ids = set(sample["conversation_id"])
verdicts = dict(zip(sample["conversation_id"], sample["verdict"]))
codigos = dict(zip(sample["conversation_id"], sample["codigos"]))

FILES = [
    "arquivos dados/Uniube Março csv/relatorio_automacoes_uniube1_202604091637-002.csv",
    "arquivos dados/Uniube Março csv/relatorio_automacoes_uniube2_202604091646.csv",
    "arquivos dados/Uniube Março csv/relatorio_automacoes_uniube3_202604091651.csv",
    "arquivos dados/Uniube Março csv/relatorio_automacoes_uniube4_202604091701.csv",
    "arquivos dados/Uniube Março csv/relatorio_automacoes_uniube5_202604091705.csv",
    "arquivos dados/abril/relatorio_automacoes_uniube_abril_202604071615.csv",
    "arquivos dados/abril/relatorio_automacoes_uniube_abri2l_202604101412.csv",
]
def load(f): return pd.read_excel(f) if f.endswith(".xlsx") else pd.read_csv(f, engine="python")
def jp(x):
    if x is None or isinstance(x, float): return None
    if isinstance(x, (dict, list)): return x
    try: return json.loads(str(x))
    except Exception: return None

convs = defaultdict(lambda: {"user": [], "ia": []})
for f in FILES:
    df = load(f)
    df = df[df["conversation_id"].isin(target_ids)]
    for _, row in df.iterrows():
        cid = row["conversation_id"]
        msgs = jp(row.get("all_request_messages")) or jp(row.get("main_request_messages")) or []
        if not isinstance(msgs, list): continue
        for m in msgs:
            if not isinstance(m, dict): continue
            role = m.get("role"); txt = m.get("content") or ""
            if isinstance(txt, list):
                txt = " ".join(c.get("text","") if isinstance(c, dict) else str(c) for c in txt)
            if not isinstance(txt, str) or not txt: continue
            if role == "user" and txt not in convs[cid]["user"]:
                convs[cid]["user"].append(txt)
            elif role == "assistant" and txt not in convs[cid]["ia"]:
                convs[cid]["ia"].append(txt)

out = []
for cid in target_ids:
    if cid not in convs: continue
    d = convs[cid]
    user = [m[:300] for m in d["user"]][:15]
    ia_seen = set(); ia = []
    for m in d["ia"]:
        key = m[:80]
        if key in ia_seen: continue
        ia_seen.add(key); ia.append(m[:250])
        if len(ia) >= 3: break
    out.append({"id": cid[:8], "v": verdicts[cid], "c": codigos[cid], "u": user, "a": ia})

Path("analises/sample_uberlandia_compact.jsonl").write_text(
    "\n".join(json.dumps(o, ensure_ascii=False) for o in out), encoding="utf-8"
)
print(f"saved {len(out)} convs")
