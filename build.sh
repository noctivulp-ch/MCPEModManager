#!/usr/bin/env fish
# Compila MCPEModManager con Nuitka y actualiza dist/mcpemod.

set PROYECTO (dirname (realpath (status filename)))
set SRC      "$PROYECTO/src"
set LIBS     "$PROYECTO/../#Libs/wulfenite_ui/PyQT/src"
set DIST     "$PROYECTO/dist"
set BINARIO  "$DIST/mcpemod"
set ENLACE   "$HOME/.local/bin/mcpemod"

mkdir -p $DIST

echo "==> Compilando con Nuitka..."
env PYTHONPATH="$SRC:$LIBS" nuitka \
    --onefile \
    --enable-plugin=pyside6 \
    --include-package=mcpemod \
    --include-package=wulf_qt \
    --include-package=packaging \
    --output-dir="$DIST" \
    --output-filename=mcpemod \
    --remove-output \
    "$SRC/mcpemod/main.py"

if test $status -ne 0
    echo "ERROR: falló la compilación."
    exit 1
end

echo "==> Binario generado: $BINARIO"

# El toolchain puede producir un ejecutable que compila y no arranca —
# ver docs/decisiones/0008-workaround-nuitka-pyside-connect.md.
echo "==> Comprobando que el binario arranca..."
#
# Se comprueba la frase que imprime al arrancar, y no el código de salida: el
# ejecutable de Nuitka sale con 0 aunque muera con un traceback, así que mirar
# solo $status daba por bueno un binario que no abre.
set salida (env QT_QPA_PLATFORM=offscreen $BINARIO --autotest 2>&1)
if not string match -q '*autotest: la ventana arranca*' -- "$salida"
    echo "ERROR: el binario compiló pero no arranca."
    for linea in $salida
        echo "    $linea"
    end
    exit 1
end
echo "    ✓ arranca"

# Crea o actualiza el symlink
if test -L $ENLACE
    rm $ENLACE
end
ln -s "$BINARIO" "$ENLACE"
echo "==> Symlink actualizado: $ENLACE -> $BINARIO"
echo "    Listo. Ejecuta: mcpemod"
