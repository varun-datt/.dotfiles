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
