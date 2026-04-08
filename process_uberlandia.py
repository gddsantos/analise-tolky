import csv, json, re, datetime as dt
from pathlib import Path
from collections import defaultdict
import pandas as pd

csv.field_size_limit(10_000_000)

FILES = [
    "relatorio_automacoes_uniube_agregado_01.03_202603311646.csv",
    "relatorio_automacoes_uniube_agregado_09.03_202603311542.xlsx",
    "relatorio_automacoes_uniube_agregado_16.03_202603311537.xlsx",
    "relatorio_automacoes_uniube_agregado_23.03_202603311534.xlsx",
    "relatorio_automacoes_uniube_final_marco_202604071619.csv",
    "relatorio_automacoes_uniube_abril_202604071615.csv",
]
def load(f): return pd.read_excel(f) if f.endswith(".xlsx") else pd.read_csv(f, engine="python")
def jp(x):
    if x is None or isinstance(x, float): return None
    try: return json.loads(str(x))
    except Exception: return None

# Códigos confirmados da automação Uberlândia
UBE_CODES = {"P62", "R10", "J560"}

# Critério: usuário menciona Uberlândia (cidade, campus, polo)
RE_UBERLANDIA = re.compile(r"\buberl[aâã]ndia\b|\buber\s*l[aâã]ndia\b|\bvila\s+g[áa]vea\b|\buberlandia\b", re.I)

def main():
    dfs = [load(f) for f in FILES]
    df = pd.concat(dfs, ignore_index=True)
    print(f"loaded rows={len(df)} convs={df['conversation_id'].nunique()}")

    convs = defaultdict(lambda: {
        "chain_codes": set(),
        "valid_codes": set(),
        "confirmed_codes": set(),
        "date": None,
        "user_msgs": [],
        "ia_msgs": [],
        "injected": False,
        "replied": False,
    })

    for _, row in df.iterrows():
        cid = row["conversation_id"]
        st = convs[cid]

        msgs = jp(row.get("all_request_messages")) or jp(row.get("main_request_messages")) or []
        if isinstance(msgs, list):
            for m in msgs:
                if not isinstance(m, dict): continue
                role = m.get("role"); txt = m.get("content") or ""
                if isinstance(txt, list):
                    txt = " ".join(c.get("text","") if isinstance(c, dict) else str(c) for c in txt)
                if not isinstance(txt, str) or not txt: continue
                if role == "user" and txt not in st["user_msgs"]:
                    st["user_msgs"].append(txt)
                elif role == "assistant" and txt and txt not in st["ia_msgs"]:
                    st["ia_msgs"].append(txt)

        responses = jp(row.get("responses")) or []

        if st["date"] is None and isinstance(responses, list):
            for item in responses:
                if not isinstance(item, dict): continue
                inner = jp(item.get("response") or "")
                if isinstance(inner, dict) and "created" in inner:
                    try:
                        st["date"] = dt.datetime.fromtimestamp(int(inner["created"]), dt.UTC).strftime("%Y-%m-%d")
                        break
                    except Exception: pass

        if isinstance(responses, list):
            for item in responses:
                if not isinstance(item, dict): continue
                caller = (item.get("caller") or "").lower()
                if "uberl" not in caller: continue
                inner = jp(item.get("response") or "")
                if not isinstance(inner, dict): continue
                try: content = inner["choices"][0]["message"]["content"]
                except Exception: continue
                parsed = jp(content)
                resp = parsed.get("response") if isinstance(parsed, dict) else None
                if isinstance(resp, str): resp = [resp]
                if not isinstance(resp, list): resp = []
                codes = {str(c).upper() for c in resp if c and str(c).upper() != "NULL"}
                codes &= UBE_CODES
                if "validation" in caller:
                    st["valid_codes"] |= codes
                elif "decisionchain" in caller:
                    st["chain_codes"] |= codes

    for st in convs.values():
        st["confirmed_codes"] = st["chain_codes"] & st["valid_codes"]

    total = len(convs)
    confirmed = sum(1 for c in convs.values() if c["confirmed_codes"])

    out_rows = []
    conv_dates = {}
    daily = defaultdict(lambda: {"total":0, "confirmed":0, "injected":0, "replied":0, "correto":0})

    for cid, st in convs.items():
        if st["date"]:
            conv_dates[cid] = st["date"]
            daily[st["date"]]["total"] += 1
        if not st["confirmed_codes"]: continue
        if st["date"]:
            daily[st["date"]]["confirmed"] += 1
            daily[st["date"]]["injected"] += 1  # assume confirmado = injetado (sem marcador específico)

        full_text = " ".join(st["user_msgs"])
        if RE_UBERLANDIA.search(full_text):
            verdict = "CORRETO"
            motivo = "mencionou Uberlandia"
        else:
            verdict = "ERRADO"
            motivo = "nao mencionou Uberlandia"

        if verdict == "CORRETO" and st["date"]:
            daily[st["date"]]["correto"] += 1

        out_rows.append({
            "conversation_id": cid,
            "verdict": verdict,
            "motivo": motivo,
            "codigos": ",".join(sorted(st["confirmed_codes"])),
            "user_msgs": " | ".join(st["user_msgs"][:5]),
        })

    out = pd.DataFrame(out_rows)
    Path("analises").mkdir(exist_ok=True)
    out.to_csv("analises/03_uberlandia_avaliacoes.csv", index=False)

    correto = int((out["verdict"]=="CORRETO").sum())
    errado  = int((out["verdict"]=="ERRADO").sum())
    meta = {
        "funnel": {"total": total, "confirmed": confirmed, "injected": confirmed, "replied": correto},
        "conv_dates": conv_dates,
        "daily_funnel": {d: dict(v) for d, v in daily.items()},
    }
    Path("analises/03_uberlandia_metadata.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    print(f"total={total} confirmed={confirmed} correto={correto} errado={errado}")

if __name__ == "__main__":
    main()
