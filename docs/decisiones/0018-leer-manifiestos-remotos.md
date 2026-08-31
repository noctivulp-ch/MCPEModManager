# 0018 — Leer el manifiesto publicado sin descargar el pack

**Fecha:** 2026-08-31
**Estado:** Aceptada

## Contexto

Confirmar que una publicación es el pack instalado exige comparar el
`header.uuid`, y el uuid está dentro del zip. Descargar cada candidato para
mirarlo serían decenas de megas por pack comprobado — con sesenta packs y varios
candidatos cada uno, gigas.

## Decisión

Se leen solo los bytes que hacen falta, con `Range`. Un zip guarda su directorio
central al final, así que se puede localizar el `manifest.json` y traerlo sin
tocar el resto.

Medido sobre un pack real de 946 KB: **2 peticiones, 61 KB, el 6%**. La primera
versión hacía seis peticiones de 2,3 KB en total; sobre HTTP manda la latencia y
no los bytes, así que agrupar las lecturas en bloques de 32 KB salió a un tercio
del tiempo aunque traiga más datos.

Requisitos y límites:

- El servidor debe anunciar `Accept-Ranges: bytes`. Los CDN que sirven packs
  (`forgecdn.net`) lo hacen. Uno que no lo haga se descarta sin más.
- Los `.mcaddon` **no tienen manifiesto propio**: lo que identifica su contenido
  son los de los packs que llevan dentro, y hay que traérselos enteros. Se miran
  los tres primeros de hasta 3 MB. Sin esto, un addon publicado no se puede
  emparejar con nada — y muchos packs se distribuyen así.

## Alternativas descartadas

- **Descargar el pack entero**: lo que esto evita.
- **Fiarse de la versión que anuncia el catálogo**: sale del nombre del archivo,
  no del manifiesto. Sirve para ordenar candidatos, no para decidir.
- **Pedir byte a byte lo que `zipfile` va pidiendo**: es lo que hacía la primera
  versión, y cada lectura de ocho bytes era una petición HTTP entera.

## Consecuencias

`ArchivoRemoto` implementa la interfaz de archivo de Python, así que `zipfile`
funciona encima sin saber que está leyendo por la red. Eso permite probarlo
entero con un servidor falso, sin tocar internet.

Si un CDN dejara de admitir `Range`, la confirmación por uuid dejaría de
funcionar para esa fuente y todo pasaría a `PROBABLE`. Sería una degradación
visible, no un fallo silencioso.
