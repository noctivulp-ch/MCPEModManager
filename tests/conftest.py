import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[1]
for ruta in (_RAIZ / "src", _RAIZ.parent / "#Libs/wulfenite_ui/PyQT/src"):
    if str(ruta) not in sys.path:
        sys.path.insert(0, str(ruta))
