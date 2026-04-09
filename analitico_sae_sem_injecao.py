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
SAE_CODES = {"D71","D710","N43"}
SAE_INJECT_MARK = re.compile(r"Entre em contato diretamente com o SAE|WhatsApp da Mentoria", re.I)
RE_PHONE = re.compile(r'phone[:"\s]+["\']?(\+?\d{10,15})')
RE_PHONE_BR = re.compile(r'\b(?:\+?55\s*)?\(?(\d{2})\)?[\s\-]?9?\d{4}[\s\-]?\d{4}\b')

def load(f): return pd.read_excel(f) if f.endswith(".xlsx") else pd.read_csv(f, engine="python")
def jp(x):
    if x is None or isinstance(x, float): return None
    if isinstance(x, (dict, list)): return x
    try: return json.loads(str(x))
    except Exception: return None

convs = defaultdict(lambda: {
    "confirmed": False, "injected": False, "payload_truncated": False,
    "phone": None, "date": None, "user_msgs": [], "trigger": None,
})

for f in FILES:
    df = load(f)
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
                if role == "system" and not st["phone"]:
                    mm = RE_PHONE.search(txt)
                    if mm: st["phone"] = mm.group(1)

        # extrai phone do payload (userAuthStatus) ou de qualquer texto
        if not st["phone"]:
            pl_raw = str(row.get("payloads") or "")
            mm = RE_PHONE.search(pl_raw)
            if mm: st["phone"] = mm.group(0).split(":")[-1].strip(' "\'')
        if not st["phone"]:
            blob = " ".join(st["user_msgs"])[:5000]
            mm = RE_PHONE_BR.search(blob)
            if mm:
                full = re.sub(r"\D","",mm.group(0))
                if 10 <= len(full) <= 13:
                    st["phone"] = full

        responses = jp(row.get("responses")) or []
        if st["date"] is None and isinstance(responses, list):
            for item in responses:
                if isinstance(item, dict):
                    inner = jp(item.get("response") or "")
                    if isinstance(inner, dict) and "created" in inner:
                        try:
                            st["date"] = dt.datetime.fromtimestamp(int(inner["created"]), dt.UTC).strftime("%Y-%m-%d %H:%M")
                            break
                        except Exception: pass

        # validation -> confirmed
        if isinstance(responses, list):
            for item in responses:
                if not isinstance(item, dict): continue
                caller = (item.get("caller") or "").lower()
                if "sae" not in caller: continue
                inner = jp(item.get("response") or "")
                if not isinstance(inner, dict): continue
                try: content = inner["choices"][0]["message"]["content"]
                except Exception: continue
                parsed = jp(content)
                resp = parsed.get("response") if isinstance(parsed, dict) else None
                if isinstance(resp, str): resp = [resp]
                if not isinstance(resp, list): resp = []
                codes = {str(c).upper() for c in resp if c} & SAE_CODES
                if "validation" in caller and codes:
                    st["confirmed"] = True
                    if not st["trigger"] and isinstance(msgs, list):
                        for mm in reversed(msgs):
                            if isinstance(mm, dict) and mm.get("role")=="user":
                                t=mm.get("content") or ""
                                if isinstance(t,list):
                                    t=" ".join(c.get("text","") if isinstance(c,dict) else str(c) for c in t)
                                if t: st["trigger"]=t[:300]; break

        # detecta truncamento de payload (limite 32767 do xlsx)
        pl_raw = row.get("payloads")
        if isinstance(pl_raw, str) and len(pl_raw) > 32700 and not pl_raw.rstrip().endswith("]"):
            st["payload_truncated"] = True

        # injected: SAE_INJECT_MARK dentro de <realtime> em system msgs do createAssistantResponse
        payloads = jp(row.get("payloads")) or []
        if isinstance(payloads, list) and not st["injected"]:
            for it in payloads:
                if not isinstance(it, dict): continue
                if "createassistantresponse" not in (it.get("caller") or "").lower(): continue
                pl = jp(it.get("payload") or "")
                if not isinstance(pl, dict): continue
                for m in pl.get("messages", []):
                    if not isinstance(m, dict) or m.get("role") != "system": continue
                    c = m.get("content") or ""
                    if not isinstance(c, str): continue
                    for rt in re.findall(r"<realtime>(.*?)</realtime>", c, re.S):
                        if SAE_INJECT_MARK.search(rt):
                            st["injected"] = True; break
                    if st["injected"]: break
                if st["injected"]: break

# filtra: confirmed=True, injected=False, payload OK (caso contrário status incerto)
out = []
unknown = 0
for cid, st in convs.items():
    if not st["confirmed"]: continue
    if st["injected"]: continue
    if st["payload_truncated"]:
        unknown += 1
        continue
    out.append({
        "conversation_id": cid,
        "telefone": st["phone"] or "",
        "data": st["date"] or "",
        "trigger_msg": st["trigger"] or "",
        "user_msgs": " | ".join(st["user_msgs"][:5])[:800],
    })

out_df = pd.DataFrame(out).sort_values("data")
Path("analises").mkdir(exist_ok=True)
out_df.to_csv("analises/sae_sem_injecao.csv", index=False)
print(f"sem_injecao={len(out_df)} com_telefone={(out_df['telefone']!='').sum()} status_desconhecido(payload_truncado)={unknown}")
