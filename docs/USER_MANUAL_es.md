# ePy Studio — Manual de usuario

ePy Studio es la puerta de entrada a los editores de documentos ePy.
Instala las tres herramientas desde un único instalador, comparte un
solo runtime entre ellas (una instalación ≈ un tercio del tamaño de
tres instalaciones separadas) y le da una única puerta a cada documento
Markdown: doble clic al archivo y elija el editor adecuado.

Autor: Ing. Angel Navarro-Mora M.Sc. — ANM Ingeniería.

## Los tres editores

| Herramienta | Úsela para | Exporta a |
|---|---|---|
| **ePy Reports** | Reportes técnicos con vista previa en vivo | PDF, Word, HTML autocontenido |
| **ePy Slides** | Presentaciones | reveal.js HTML, PowerPoint |
| **ePy Papers** | Manuscritos académicos | PDF con plantillas de revista |

Los tres editan el mismo formato fuente — Markdown con extensiones
Quarto — así que un documento puede moverse entre ellos sin conversión.

## Abrir documentos

Hay tres caminos:

1. **Doble clic a un archivo `.md` / `.markdown` / `.qmd`.** Con ePy
   Studio como aplicación predeterminada, se abre el selector mostrando
   el nombre del archivo; haga clic en el editor deseado y el archivo
   se abre ahí.
2. **Menú Inicio.** "ePy Studio" abre el selector sin archivo; cada
   editor tiene además su propio acceso directo.
3. **Abrir con.** Clic derecho a cualquier archivo Markdown → *Abrir
   con* → elija ePy Studio o uno de los editores directamente.

## Hacer de ePy Studio el predeterminado para .md

El instalador registra ePy Studio y ofrece abrir la Configuración de
Windows en *Aplicaciones predeterminadas*. Windows exige una
confirmación manual (la elección de aplicación predeterminada va
firmada criptográficamente y ningún instalador puede fijarla en
silencio):

1. Abra *Configuración → Aplicaciones → Aplicaciones predeterminadas →
   ePy Studio*.
2. Haga clic en cada extensión (`.md`, `.markdown`, `.qmd`) y
   seleccione **ePy Studio**.

Atajo equivalente: clic derecho a un `.md` → *Abrir con → Elegir otra
aplicación* → ePy Studio → marque **Siempre**.

## Elegir qué instalar

La página de *Instalación personalizada* del instalador permite marcar
cada editor. El runtime compartido y el selector se instalan siempre;
los editores sin marcar simplemente no aparecen (su fila en el selector
muestra "not installed"). Vuelva a ejecutar el instalador en cualquier
momento para agregar o quitar componentes.

## Idiomas

Cada editor es bilingüe (inglés / español): el idioma de la interfaz se
cambia desde el menú *Language* de cada aplicación, y la numeración de
títulos ("Figure 1" / "Figura 1"), las referencias cruzadas y los
índices generados siguen automáticamente el idioma de la interfaz. Un
documento puede fijar su propio idioma, independiente de la interfaz,
con el front matter:

```yaml
---
lang: es
---
```

## Actualizar y desinstalar

- **Actualizar**: instale el `epy_studio-setup-x.y.z.exe` más nuevo
  encima; la configuración y los documentos no se tocan.
- **Desinstalar**: *Configuración → Aplicaciones → Aplicaciones
  instaladas → ePy Studio*. Las asociaciones de archivo registradas por
  el Studio se eliminan automáticamente.

## Solución de problemas

- **Un botón de editor dice "not installed"** — vuelva a ejecutar el
  instalador y marque ese componente.
- **El doble clic abre otro programa** — falta confirmar el
  predeterminado de Windows; vea *Hacer de ePy Studio el
  predeterminado* arriba.
- **El selector abre pero el editor no** — inicie el editor desde su
  acceso del Menú Inicio una vez y revise el error que reporta.
