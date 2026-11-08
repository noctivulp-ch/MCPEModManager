#!/usr/bin/env fish
# Verificación estática, pruebas y arranque real de la UI antes de compilar.
# Uso: fish check.sh

set PROYECTO (dirname (realpath (status filename)))
set SRC      "$PROYECTO/src"
set LIBS     "$PROYECTO/../#Libs/wulfenite_ui/PyQT/src"
set ENTORNO  PYTHONPATH="$SRC:$LIBS"
set ERRORES  0

function paso -a nombre
    echo ""
    echo "── $nombre"
end

function ok
    echo "   ✓ $argv"
end

function fallo
    echo "   ✗ $argv"
    set -g ERRORES (math $ERRORES + 1)
end

# 1. Sintaxis — detecta SyntaxError en todos los archivos
paso "Sintaxis"
set archivos (find $SRC $PROYECTO/tests $PROYECTO/tools -name "*.py" -not -path "*/__pycache__/*")
set errores_sintaxis 0
for f in $archivos
    set salida (python -m py_compile $f 2>&1)
    if test $status -ne 0
        echo "   ✗ $f"
        echo "     $salida"
        set errores_sintaxis (math $errores_sintaxis + 1)
    end
end
if test $errores_sintaxis -eq 0
    ok (count $archivos)" archivos sin errores de sintaxis"
else
    set ERRORES (math $ERRORES + 1)
end

# 2. Importaciones del core (sin Qt gráfico)
paso "Importaciones del core"
set salida (env $ENTORNO python -c "
import mcpemod.core.contenido, mcpemod.core.installer, mcpemod.core.manifiesto
import mcpemod.core.mod, mcpemod.core.rutas, mcpemod.core.scanner
import mcpemod.core.store, mcpemod.core.version
" 2>&1)
if test $status -eq 0
    ok "core importa sin errores"
else
    fallo "core con errores:"
    echo "     $salida"
end

# 3. Pyflakes — nombres sin definir, imports sin usar
paso "Pyflakes"
if command -q pyflakes
    set salida (env $ENTORNO pyflakes $SRC $PROYECTO/tests $PROYECTO/tools 2>&1)
    if test -z "$salida"
        ok "sin advertencias"
    else
        fallo "advertencias encontradas:"
        for linea in $salida
            echo "     $linea"
        end
    end
else
    echo "   · pyflakes no instalado (pip install pyflakes)"
end

# 4. Conexiones de señal
#
# Conectar un método de objeto rompe el binario compilado a la segunda vez, y en
# el intérprete no se nota: la ventana simplemente no abre al compilar.
paso "Conexiones de señal"
set salida (env $ENTORNO python "$PROYECTO/tools/lint_conexiones.py" $SRC 2>&1)
if test $status -eq 0
    ok "todas pasan por senales.conectar"
else
    fallo "conexiones que romperían el binario:"
    for linea in $salida
        echo "     $linea"
    end
end

# 5. Pruebas unitarias
paso "Pruebas unitarias"
env $ENTORNO QT_QPA_PLATFORM=offscreen python -m pytest "$PROYECTO/tests" -q --tb=short
if test $status -ne 0
    fallo "pruebas fallidas"
end

# 6. Arranque real de la UI
#
# Es el paso que faltaba y por el que la app llegó a compilar sin arrancar: una
# llamada con la firma equivocada a `wulf_qt` no la ve ni pyflakes ni pytest,
# solo se ve construyendo los widgets de verdad.
paso "Arranque de la UI (offscreen)"
set salida (env $ENTORNO QT_QPA_PLATFORM=offscreen python "$PROYECTO/tests/smoke_ui.py" 2>&1)
if test $status -eq 0
    ok "la ventana y las tres pestañas se construyen"
else
    fallo "la UI no arranca:"
    for linea in $salida
        echo "     $linea"
    end
end

echo ""
if test $ERRORES -eq 0
    echo "════ Todo OK — listo para compilar (fish build.sh) ════"
    exit 0
else
    echo "════ $ERRORES bloque(s) con errores — corregir antes de compilar ════"
    exit 1
end
