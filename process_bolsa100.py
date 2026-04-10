import csv, json, re, datetime as dt
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
COLS = ["conversation_id", "all_request_messages", "main_request_messages", "payloads", "responses"]

def load(f):
    return pd.read_csv(f, usecols=COLS, engine="python")

def _iter_all():
    for f in FILES:
        df = load(f)
        print(f"  {f}: {len(df)} rows")
        yield from df.iterrows()
        del df
def jp(x):
    if x is None or isinstance(x, float): return None
    try: return json.loads(str(x))
    except Exception: return None

# Códigos confirmados da automação Bolsa 100
B100_CODES = {"L290"}

# Critério: usuário menciona Bolsa 100 (ou variações: 100%, integral)
RE_BOLSA100 = re.compile(
    r"\bbolsa[^.\n]{0,15}\b100\b"
    r"|\bbolsa\s*100\s*%"
    r"|\b100\s*%\s*de\s*bolsa\b"
    r"|\bbolsa\s+integral\b"
    r"|\bbolsa\s+de\s+cem\b"
    r"|\buniube\s*100\b",
    re.I,
)

def main():
    convs = defaultdict(lambda: {
        "valid_codes": set(),
        "valid_codes_main": set(),
        "valid_codes_followup": set(),
        "confirmed_codes": set(),
        "date": None,
        "user_msgs": [],
        "ia_msgs": [],
        "trigger_msg": None,
        "evid_acionamento": None,
    })

    for _, row in _iter_all():
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

        payloads = jp(row.get("payloads")) or []
        is_followup = any(
            isinstance(it, dict) and "followup" in (it.get("caller") or "").lower()
            for it in (payloads if isinstance(payloads, list) else [])
        )

        if isinstance(responses, list):
            for item in responses:
                if not isinstance(item, dict): continue
                caller = (item.get("caller") or "").lower()
                if "bolsa 100" not in caller: continue
                inner = jp(item.get("response") or "")
                if not isinstance(inner, dict): continue
                try: content = inner["choices"][0]["message"]["content"]
                except Exception: continue
                parsed = jp(content)
                resp = parsed.get("response") if isinstance(parsed, dict) else None
                if isinstance(resp, str): resp = [resp]
                if not isinstance(resp, list): resp = []
                codes = {str(c).upper() for c in resp if c and str(c).upper() != "NULL"}
                codes &= B100_CODES
                if "validation" in caller:
                    st["valid_codes"] |= codes
                    if codes and st["evid_acionamento"] is None:
                        st["evid_acionamento"] = f"caller: {item.get('caller')}\nresponse: {content[:400]}"
                    if is_followup:
                        st["valid_codes_followup"] |= codes
                    else:
                        st["valid_codes_main"] |= codes
                elif "decisionchain" in caller:
                    if codes and st["trigger_msg"] is None and isinstance(msgs, list):
                        for m in reversed(msgs):
                            if isinstance(m, dict) and m.get("role") == "user":
                                t = m.get("content") or ""
                                if isinstance(t, list):
                                    t = " ".join(c.get("text","") if isinstance(c, dict) else str(c) for c in t)
                                if t:
                                    st["trigger_msg"] = t[:500]
                                    break

    for st in convs.values():
        st["confirmed_codes"] = st["valid_codes"]

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
            daily[st["date"]]["injected"] += 1

        full_text = " ".join(st["user_msgs"])
        m_b = RE_BOLSA100.search(full_text)
        if m_b:
            verdict = "CORRETO"
            motivo = "mencionou Bolsa 100"
            s = max(0, m_b.start()-80); e = min(len(full_text), m_b.end()+80)
            evid_correto = f"...{full_text[s:m_b.start()]}«{full_text[m_b.start():m_b.end()]}»{full_text[m_b.end():e]}..."
        else:
            verdict = "ERRADO"
            motivo = "nao mencionou Bolsa 100"
            evid_correto = ""

        if verdict == "CORRETO" and st["date"]:
            daily[st["date"]]["correto"] += 1

        has_main = bool(st["valid_codes_main"])
        has_fu = bool(st["valid_codes_followup"])
        if has_main and has_fu: origem = "principal+followup"
        elif has_main: origem = "principal"
        else: origem = "followup"
        out_rows.append({
            "conversation_id": cid,
            "verdict": verdict,
            "motivo": motivo,
            "codigos": ",".join(sorted(st["confirmed_codes"])),
            "origem": origem,
            "trigger_msg": st["trigger_msg"] or "",
            "user_msgs": " | ".join(st["user_msgs"][:5]),
            "evid_acionamento": st["evid_acionamento"] or "",
            "evid_correto": evid_correto,
        })

    out = pd.DataFrame(out_rows)
    Path("analises").mkdir(exist_ok=True)
    out.to_csv("analises/04_bolsa100_avaliacoes.csv", index=False)

    correto = int((out["verdict"]=="CORRETO").sum())
    errado  = int((out["verdict"]=="ERRADO").sum())
    meta = {
        "funnel": {"total": total, "confirmed": confirmed, "injected": confirmed, "replied": correto},
        "conv_dates": conv_dates,
        "daily_funnel": {d: dict(v) for d, v in daily.items()},
    }
    Path("analises/04_bolsa100_metadata.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    print(f"total={total} confirmed={confirmed} correto={correto} errado={errado}")

if __name__ == "__main__":
    main()
