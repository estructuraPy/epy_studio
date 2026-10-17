# epy_studio — Directrices permanentes (dueño, 2026-10-07)

Todo lo asociado a ePy Studio — la aplicación, su catálogo
(`src/epy_studio/_config/apps.epyson`), su instalador
(`windows/epy_studio.iss` + `build.py`), el selector y **las aplicaciones que
distribuye** — sigue estas reglas. Un cambio que las contradiga es un
**defecto**, no una preferencia. Valen para este repo y para cualquier repo que
produzca algo que ePy Studio instale o lance.

## 1. Prefijo `epy_` (nombres de familia)

Toda aplicación ADOPTADA (las ArtCraft de `github.com/storytold`) se nombra con
el prefijo `epy_`: `artcraft`→`epy_artcraft`, `cadcraft`→`epy_cadcraft`,
`photocraft`→`epy_photocraft`, `wordcraft`→`epy_wordcraft`, y así todas.
En el catálogo el `id` es el nombre de familia (`epy_cadcraft`) y **`binary` es
el stem upstream** (`cadcraft`), que es lo que se busca en disco: el instalador
NO renombra el ejecutable ni sus ficheros, porque la herramienta puede depender
de sus propios nombres. El resolver usa `App.exe_stem` (= `binary` o el `id`).

## 2. Copia privada propia

Las ArtCraft se copian a NUESTRA organización (`estructuraPy`) como repos
**privados** `epy_<craft>`, con su historia upstream (mirror), para poder
seguir sus cambios. El campo `upstream` del catálogo nombra la procedencia,
licencia incluida.

## 3. Un repositorio con todos los `.exe`

Los ejecutables para instalar todo lo asociado a ePy Studio viven en **UN**
repositorio dedicado: **`estructuraPy/epy_studio_install`** (privado). Lleva
`apps/<id>/<id>.exe` (las apps que compila Studio) y `crafts/<binary>/` (los
árboles adoptados), más un `manifest.epyson` GENERADO del catálogo. El
instalador consume ese repo; no se dispersan binarios por otros repos ni se
commitean `.exe` a los repos de código.

## 4. Instalación con ePy Studio (`ships: "installed"`)

Las apps adoptadas se instalan CON ePy Studio. El instalador de Studio copia su
árbol —staged por el dueño en `dist/epy_studio/crafts/<binary>/`— a
`{app}\crafts\<binary>\`, **guardado con `#ifexist`** para que el build funcione
con o sin el binario staged. `build.py::_verify_manifest` exige que una app
`installed` esté nombrada en el `.iss` DENTRO de su bloque `#ifexist`, con el
nombre binario (`cadcraft.exe`, no `epy_cadcraft.exe`). El resolver la busca en
`install_dir()/crafts/<binary>/`, luego `install_dir()`, luego env → `PATH` →
carpetas convencionales.

## 5. Licencia: el trío no-OSI queda FUERA

`artcraft` (el flagship) y `artcraft-services` usan la "ArtCraft License (WIP)"
—fair-source, **no-OSI**; prohíbe reventa y producto competidor— y `artcraftx`
no tiene fichero LICENSE. Una copia PRIVADA para uso personal es admisible;
redistribuirlos en un bundle público NO lo es. Una app adoptada registra su
licencia en `upstream` (las 12 OSI son `MIT OR Apache-2.0`).

## 6. Geometría única (100%)

Las herramientas adoptadas son **consumidoras** de la geometría que `epy_plotter`
ya escribe (un `.dxf` derivado del modelo), nunca productoras: el 3D y los
planos comparten la MISMA geometría (Regla 6 de epy_plotter). Un convertidor
recibe el archivo ya escrito y devuelve otro; jamás re-deriva del modelo.

## 7. Hints, nunca dependencias

Lo que Studio pasa a las apps que lanza (`EPY_CADCRAFT_CLI`, el backend de ePy
Docs) es un **hint por entorno**: una app arrancada de otra forma se comporta
igual menos el atajo. Studio no importa a las apps; las lanza.

## 8. Refuse to ship a bundle that lies

Un catálogo y un `.iss` que discrepan **rechazan** el build (`build.py`). Una
app con `register: "none"` no reclama tipos de documento. Una adoptada sin
`upstream` es un rechazo. Un `installed` sin `component` es un rechazo. Estas
reglas existen porque la lista se repitió en cinco sitios y tres ya habían
divergido.

## 9. `_optional` / `_own_installer` / `_installed` son ejes independientes

- `register`: qué tipos de documento reclama (`default`/`openwith`/`none`).
- `optional`: si el bundle puede construirse/instalarse SIN ésta.
- `ships`: cómo llega al usuario — `studio` (Studio la compila),
  `own_installer` (se instala sola; Studio sólo la ofrece), `installed`
  (el instalador de Studio la instala).
