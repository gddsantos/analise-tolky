import csv, json, re, hashlib, datetime as dt
from pathlib import Path
from collections import defaultdict
import pandas as pd

csv.field_size_limit(10_000_000)

FILES = [
    "arquivos dados/Uniube Março csv/relatorio_automacoes_uniube1_202604091637-002.csv",
    "arquivos dados/Uniube Março csv/relatorio_automacoes_uniube2_202604091646.csv",
    "arquivos dados/Uniube Março csv/relatorio_automacoes_uniube3_202604091651.csv",
    "arquivos dados/Uniube Março csv/relatorio_automacoes_uniube4_202604091701.csv",
    "arquivos dados/Uniube Março csv/relatorio_automacoes_uniube5_202604091705.csv",
    "arquivos dados/abril/relatorio_automacoes_uniube_abril_202604071615.csv",
    "arquivos dados/abril/relatorio_automacoes_uniube_abri2l_202604101412.csv",
]

# (nome_no_dashboard, substring no caller, deve ser decisionChain mas NAO validation)
AUTOMACOES = [
    ("SAE",        "sae"),
    ("Tickets",    "tickets"),
    ("Uberlândia", "uberl"),
    ("Bolsa 100",  "bolsa 100"),
]

def load(f): return pd.read_excel(f) if f.endswith(".xlsx") else pd.read_csv(f, engine="python")
def jp(x):
    if x is None or isinstance(x, float): return None
    if isinstance(x, (dict, list)): return x
    try: return json.loads(str(x))
    except Exception: return None

def normalize(s):
    s = re.sub(r"\s+", " ", s).strip()
    return s

def short_hash(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:8]

SKIP_TOKENS = ("<generalInstructions>", "<previous_captured_data>", "<userAuthStatus>",
               "<not_logged>", "<logged>", "INFORMAÇÕES CAPTURADAS",
               "Você já conversou", "customer_data", "important_impressions",
               "<actual_date>", "summary_history")

def extract_system_prompt(payload_item):
    """Pega APENAS o system message com as regras estáticas (não dinâmicas)."""
    p = payload_item.get("payload")
    if isinstance(p, str):
        try: p = json.loads(p)
        except Exception: return None
    if not isinstance(p, dict): return None
    msgs = p.get("messages") or []
    # Pega APENAS o primeiro system message que pareça regra estática
    for m in msgs:
        if not isinstance(m, dict) or m.get("role") != "system": continue
        c = str(m.get("content") or "")
        if not c.strip(): continue
        if any(tok in c for tok in SKIP_TOKENS): continue
        return c
    return None

def main():
    # versoes[automacao][hash] = {prompt, datas:set}
    versoes = {n: {} for n,_ in AUTOMACOES}

    for f in FILES:
        df = load(f)
        if "payloads" not in df.columns: continue
        for _, row in df.iterrows():
            pl = jp(row.get("payloads"))
            if not isinstance(pl, list): continue

            # data desta linha (do responses.created)
            data = None
            rs = jp(row.get("responses")) or []
            if isinstance(rs, list):
                for it in rs:
                    if not isinstance(it, dict): continue
                    inner = jp(it.get("response") or "")
                    if isinstance(inner, dict) and "created" in inner:
                        try:
                            data = dt.datetime.fromtimestamp(int(inner["created"]), dt.UTC).strftime("%Y-%m-%d")
                            break
                        except Exception: pass
            if not data: continue

            for it in pl:
                if not isinstance(it, dict): continue
                caller = (it.get("caller") or "").lower()
                if "decisionchain" not in caller: continue
                if "validation" in caller: continue
                for nome, sub in AUTOMACOES:
                    if sub in caller:
                        prompt = extract_system_prompt(it)
                        if not prompt: break
                        norm = normalize(prompt)
                        h = short_hash(norm)
                        if h not in versoes[nome]:
                            versoes[nome][h] = {"prompt": prompt, "datas": set()}
                        versoes[nome][h]["datas"].add(data)
                        break

    out = {}
    for nome, hashes in versoes.items():
        items = []
        for h, info in hashes.items():
            datas = sorted(info["datas"])
            items.append({
                "hash": h,
                "primeiro_dia": datas[0],
                "ultimo_dia": datas[-1],
                "ocorrencias_dias": len(datas),
                "prompt": info["prompt"],
            })
        # ordena por primeiro_dia e numera
        items.sort(key=lambda x: x["primeiro_dia"])
        for i, it in enumerate(items, 1):
            it["versao"] = i
        out[nome] = items
        print(f"{nome}: {len(items)} versão(ões)")
        for it in items:
            print(f"  v{it['versao']} [{it['hash']}] {it['primeiro_dia']} a {it['ultimo_dia']} ({it['ocorrencias_dias']} dias)")

    Path("analises").mkdir(exist_ok=True)
    Path("analises/prompt_versions.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )

if __name__ == "__main__":
    main()
