import os
import json
import time
import hashlib
from datetime import datetime, timezone

# progresso
try:
    from tqdm import tqdm
except Exception:
    tqdm = None

PROJ_DIR = os.path.abspath(os.path.dirname(__file__))
OUT_DIR = os.path.join(PROJ_DIR, "scan_out")
CATALOG_JSONL = os.path.join(OUT_DIR, "catalog.jsonl")
ERRORS_JSONL  = os.path.join(OUT_DIR, "errors.jsonl")
STATE_JSON    = os.path.join(OUT_DIR, "state.json")
PITSTOP_JSON  = os.path.join(OUT_DIR, "pitstop_status.json")
PITSTOP_TXT   = os.path.join(OUT_DIR, "pitstop_status.txt")

# RAÍZES ESTRATÉGICAS
ROOTS = [
    r"G:\Meu Drive",
    os.path.join(os.environ.get("USERPROFILE",""), "Desktop"),
    os.path.join(os.environ.get("USERPROFILE",""), "Documents"),
]

# Prioridade simples (você pode aumentar depois)
PRIORITY_GROUPS = [
    ("PDF",   (".pdf",)),
    ("EXCEL", (".xlsx",".xls")),
    ("TXT",   (".txt",)),
    ("XML",   (".xml",)),
]

CHUNK = 1024 * 1024
PITSTOP_EVERY_SECONDS = 30 * 60  # 30 min
CHECKPOINT_EVERY_OK = 200        # checkpoint a cada N OK (pra não pesar)

def now_utc_iso():
    return datetime.now(timezone.utc).isoformat()

def human_eta(seconds):
    if seconds is None:
        return "desconhecido"
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m}m"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"

def ext_of(path):
    return os.path.splitext(path)[1].lower()

def safe_stat(path):
    try:
        return os.stat(path)
    except Exception:
        return None

def safe_mtime(path):
    st = safe_stat(path)
    return st.st_mtime if st else 0.0

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def append_jsonl(path, row):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

def load_state():
    if not os.path.exists(STATE_JSON):
        return {
            "done_sha256": [],
            "stats": {"processed": 0, "skipped": 0, "errors": 0},
            "by_ext": {},
            "started_utc": None,
            "last_pitstop_utc": None,
            "last_pitstop_reason": None,
        }
    try:
        with open(STATE_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "done_sha256": [],
            "stats": {"processed": 0, "skipped": 0, "errors": 0},
            "by_ext": {},
            "started_utc": None,
            "last_pitstop_utc": None,
            "last_pitstop_reason": None,
        }

def save_state(state):
    os.makedirs(OUT_DIR, exist_ok=True)
    tmp = STATE_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_JSON)

def iter_all_files(roots):
    for root in roots:
        if not root or not os.path.exists(root):
            continue
        for dirpath, _, filenames in os.walk(root):
            for fname in filenames:
                yield os.path.join(dirpath, fname)

def build_queue_general():
    all_files = list(iter_all_files(ROOTS))

    priority_exts = set()
    for _, exts in PRIORITY_GROUPS:
        priority_exts |= set(exts)

    queue = []

    # prioritários na ordem definida, recente -> antigo
    for group_name, exts in PRIORITY_GROUPS:
        files = [p for p in all_files if ext_of(p) in exts]
        files.sort(key=lambda p: -safe_mtime(p))
        for p in files:
            queue.append((group_name, p))

    # resto
    rest = [p for p in all_files if ext_of(p) not in priority_exts]
    rest.sort(key=lambda p: -safe_mtime(p))
    for p in rest:
        queue.append(("RESTO", p))

    return queue

def write_pitstop(state, reason, total_queue, remaining_queue):
    processed = state["stats"].get("processed", 0)
    skipped = state["stats"].get("skipped", 0)
    errors  = state["stats"].get("errors", 0)
    done_count = processed + skipped + errors
    pct = (done_count / total_queue * 100.0) if total_queue else 0.0

    eta_seconds = None
    started = state.get("started_utc")
    if started:
        try:
            started_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            elapsed = (datetime.now(timezone.utc) - started_dt).total_seconds()
            rate = (done_count / elapsed) if elapsed > 0 else None
            eta_seconds = (remaining_queue / rate) if rate and rate > 0 else None
        except Exception:
            eta_seconds = None

    payload = {
        "ts_utc": now_utc_iso(),
        "reason": reason,
        "total_queue": total_queue,
        "done_count": done_count,
        "remaining_queue": remaining_queue,
        "percent_done": round(pct, 2),
        "eta_seconds": int(eta_seconds) if eta_seconds is not None else None,
        "eta_human": human_eta(eta_seconds),
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
        "by_ext_processed": state.get("by_ext", {}),
        "started_utc": state.get("started_utc"),
        "last_pitstop_utc": state.get("last_pitstop_utc"),
        "last_pitstop_reason": state.get("last_pitstop_reason"),
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(PITSTOP_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    lines = []
    lines.append(f"[PIT STOP] {payload['ts_utc']}")
    lines.append(f"Motivo: {reason}")
    lines.append(f"Progresso: {payload['done_count']}/{total_queue} ({payload['percent_done']}%)")
    lines.append(f"Faltam: {remaining_queue} | ETA: {payload['eta_human']}")
    lines.append(f"OK: {processed} | Skip: {skipped} | Erros: {errors}")
    by_ext = payload.get("by_ext_processed", {})
    if by_ext:
        lines.append("Por extensão (OK):")
        for k in sorted(by_ext.keys()):
            lines.append(f"- {k}: {by_ext[k]}")

    with open(PITSTOP_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def progress_iter(iterable, total, desc):
    if tqdm is None:
        print("tqdm não encontrado. Rodando sem barra (instale com: pip install tqdm).")
        return iterable
    return tqdm(iterable, total=total, desc=desc, unit="arquivo")

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    state = load_state()
    done = set(state.get("done_sha256", []))

    if not state.get("started_utc"):
        state["started_utc"] = now_utc_iso()

    print("Raízes:")
    for r in ROOTS:
        print(" -", r, ("(OK)" if os.path.exists(r) else "(NÃO EXISTE/SEM ACESSO)"))

    print("Montando fila (pode demorar se tiver MUITA coisa)...")
    queue = build_queue_general()
    total = len(queue)
    print(f"Fila geral (PDF→EXCEL→TXT→XML→RESTO): {total} arquivos")

    last_pitstop_ts = time.time()

    it = progress_iter(queue, total=total, desc="Processando")
    for idx, (group_name, fpath) in enumerate(it, start=1):

        # pitstop por tempo
        if time.time() - last_pitstop_ts >= PITSTOP_EVERY_SECONDS:
            state["done_sha256"] = sorted(done)
            state["last_pitstop_utc"] = now_utc_iso()
            state["last_pitstop_reason"] = "pitstop_30min"
            save_state(state)
            write_pitstop(state, reason="pitstop_30min", total_queue=total, remaining_queue=(total - idx))
            print("Pit stop (30 min) gravado. Continuando...")
            last_pitstop_ts = time.time()

        try:
            st = os.stat(fpath)
            h = sha256_file(fpath)

            if h in done:
                state["stats"]["skipped"] = state["stats"].get("skipped", 0) + 1
                continue

            ext = ext_of(fpath)
            row = {
                "ts_utc": now_utc_iso(),
                "group": group_name,
                "sha256": h,
                "file_id": h[:16],
                "ext": ext,
                "name": os.path.basename(fpath),
                "path": fpath,
                "size_bytes": st.st_size,
                "mtime_iso": datetime.fromtimestamp(st.st_mtime).isoformat(),
                "status": "indexed",
            }
            append_jsonl(CATALOG_JSONL, row)

            done.add(h)
            state["stats"]["processed"] = state["stats"].get("processed", 0) + 1
            state["by_ext"][ext] = state["by_ext"].get(ext, 0) + 1

            if state["stats"]["processed"] % CHECKPOINT_EVERY_OK == 0:
                state["done_sha256"] = sorted(done)
                save_state(state)

        except Exception as e:
            state["stats"]["errors"] = state["stats"].get("errors", 0) + 1
            append_jsonl(ERRORS_JSONL, {
                "ts_utc": now_utc_iso(),
                "group": group_name,
                "path": fpath,
                "status": "error",
                "error": str(e),
            })

    # final
    state["done_sha256"] = sorted(done)
    state["last_pitstop_utc"] = now_utc_iso()
    state["last_pitstop_reason"] = "final"
    save_state(state)
    write_pitstop(state, reason="final", total_queue=total, remaining_queue=0)

    print("Fim.")
    print(f"Catalog:  {CATALOG_JSONL}")
    print(f"Errors:   {ERRORS_JSONL}")
    print(f"State:    {STATE_JSON}")
    print(f"Pit stop: {PITSTOP_TXT} / {PITSTOP_JSON}")

if __name__ == "__main__":
    main()
