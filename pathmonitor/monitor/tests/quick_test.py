
# monitor/tests/quick_test.py
import os
import time
from pathlib import Path

def generate_files(base_dir):
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)

    # 1) szybkie pliki tekstowe
    for i in range(3):
        p = base / f"plik{i+1}.txt"
        p.write_text(f"test {i+1}")
        print(f"[GEN] Utworzono {p}")
        time.sleep(0.5)

    # 2) plik "wolno zapisywany" (test stabilizacji)
    slow = base / "slow.txt"
    print(f"[GEN] Tworzenie wolnego pliku: {slow}")
    with slow.open("w", encoding="utf-8") as f:
        for i in range(25):
                       f.write(f"linia {i+1}\n")
            f.flush()
            time.sleep(0.2)  # symulacja długiego zapisu

    # 3) pliki o różnych rozszerzeniach do testu include/exclude
    (base / "~tymczasowy.tmp").write_text("tmp")
    print(f"[GEN] Utworzono {base / '~tymczasowy.tmp'}")

    (base / "raport.xlsx").write_text("xlsx")
    print(f"[GEN] Utworzono {base / 'raport.xlsx'}")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Generator plików testowych")
    ap.add_argument("--dir", required=True, help="Katalog docelowy (ten sam co monitor)")
    args = ap.parse_args()
