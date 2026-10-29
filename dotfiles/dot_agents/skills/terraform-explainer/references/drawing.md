# Drawing and explaining

Build one self-contained HTML page per audience: inline SVG with the icons embedded as `data:` URIs, system fonts, no CDN, so it opens anywhere and can be rendered offline. `diagram_kit.page()` adds the CSS; pass `theme_message` when a host page posts theme changes into a frame.

## Panels that worked

1. **Everything created for one environment.** Columns left to right: the Kubernetes namespace and its services, the IAM role each one assumes, the data stores with their keys, then a "who else can reach it" grid. Give the grid one column per outside party, headed by its icon, a one-to-three-word name and its account, and put the access level in each cell ("read", "read, write, delete", "new-file notices"). Put the exact role and resource names in a list under the picture, not in the grid.
2. **A flow across accounts.** One box per account, headed by the AWS account icon and "made by <repo>". Number every arrow, and repeat the numbers as the steps under the picture. Show the receiving side as far as its workflow starts and say which of its schedules are switched off.
3. **What differs between accounts.** An HTML table, accounts as columns. When it is a plan, mark each cell "today" (tinted) or "new" (outlined badge), and keep it on its own page: it expires once the change ships.

## Plain words

- One term per concept on the whole page; the legend and the steps use the same words as the picture.
- Under a flow, a "services in this picture" grid: icon, name, one plain line ("Default event bus: comes with every account; AWS services such as S3 post their events there"). Quote the vendor's own definition when you can and cite it.
- Say what a message carries when it matters ("the notice names the file; it never carries it").
- Close with an evidence line: what is VERIFIED, when it was read, and what is OPEN.

## Encodings

One meaning per visual variable across the page, stated in a key line under the title. What worked: gold fill for "exists in dev only", a dashed ink outline for "one environment only (a trial)", a tinted cell for "exists today". Do not reuse a colour for a second meaning on another panel.

## Layout tips

- Fix a column of x positions and a list of row y positions first; place everything from those lists so rows line up across columns.
- Estimate text width at about 6 to 7 pixels per character for the 11.5 to 13 pixel styles, and keep a label to one to three words. A long name goes on two lines or into the list under the picture.
- Draw arrows from icon edge to icon edge (centre plus or minus half the icon size) and keep labels off the arrow lines.
- Leave room above a grid for icon headers; put the left-hand column headings on the same baseline as the grid headers' last line.

## Render check

`render_cards.py` screenshots the page in headless Chrome and crops each card. Make the window taller than the page, open every crop at full size, and fix clipped text, overlaps and stray lines before showing anyone. Then check the account numbers are gone: `grep -cE '\b[0-9]{12}\b' page.html` should print 0.
