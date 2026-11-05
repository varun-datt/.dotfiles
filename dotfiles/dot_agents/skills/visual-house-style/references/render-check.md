# Render check

Look at the rendered result before calling it done. Commands are for macOS.

1. Screenshot the whole page. Headless Chrome captures only the window, so make the window taller
   than the page:

   ```sh
   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu \
     --hide-scrollbars --window-size=1360,3000 --screenshot=/tmp/render/full.png "file://$PWD/page.html"
   ```

2. Crop each panel at the width it will be read at, and open the crops. `--cropOffset` takes the
   vertical offset first:

   ```sh
   sips --cropToHeightWidth 900 1360 --cropOffset 1480 0 /tmp/render/full.png --out /tmp/render/panel.png
   ```

3. Look for text cut off at a figure's edge, labels that overlap, and anything that breaks the
   legend.

## Traps

- Quick Look thumbnails (`qlmanage -t`) show only the top of a page, so a clean thumbnail says
  nothing about the rest.
- SVG text with `text-anchor="middle"` near a figure's edge spills past the `viewBox` and is clipped
  without warning. Move it inward, or anchor it at `start` or `end`.
- A page height measured by an inline script comes out short when images have not loaded yet (one
  page measured 206 px). Give every image an `aspect-ratio`, or a width and height.
- Chrome can break a long command at a hyphen, between `--` and the flag name. Set
  `white-space: nowrap` on commands and put a `<br>` where a break is wanted.
- Headless Chrome `--virtual-time-budget` on a page with infinite animations can screenshot at time
  zero, with everything still hidden. Check motion with `agent-browser` and a real `wait`; for final
  states, give the page a `?still` switch that turns animation off.
- An inlined SVG filled with `url(#id)`: stripping `id` attributes breaks the fill, and a gradient
  defined inside a `display:none` slide paints nothing for later copies that share its id. Give each
  inlined copy its own ids.
- A delayed CSS animation shows the element's unanimated style until it starts, so a loop can open
  on its end state. Set `animation-fill-mode: both`.

## A .pptx on this Mac

LibreOffice, pdftoppm and markitdown are not installed, and pptxgenjs and sharp are not global,
although the pptx skill says they are preinstalled. Install those two into a local folder, then
render through PowerPoint and PyMuPDF (absolute paths):

```sh
osascript -e 'tell application "Microsoft PowerPoint"' -e "open POSIX file \"$PWD/deck.pptx\"" \
  -e 'delay 3' -e "save active presentation in POSIX file \"$PWD/deck.pdf\" as save as PDF" \
  -e 'close active presentation saving no' -e 'end tell'
uv run --with pymupdf python -c "import fitz; [p.get_pixmap(dpi=110).save(f'slide-{i+1}.png') for i, p in enumerate(fitz.open('deck.pdf'))]"
```

PowerPoint's `open` returns nothing, so `set p to open …` fails; use `active presentation`.
