# SpendPilot visual direction

The September screens below stay a development preview. They load only when the Vite dev server is running. The production overview shows a published briefing, and scenarios calculate a reduction before a target can be accepted. Cards, statements, and the production transaction list use the ledger API. The production advisor runs one investigation and opens the cited rows. The shared closing balance is shown once on the statement.

## References

The specification points at Linear (navigation discipline), Mercury (financial hierarchy), Monarch (personal spending context), and shadcn/ui blocks (structure). Public marketing pages were not treated as layouts to copy. This pass follows the written screen blueprints in specification §10.2 and §10.3: original composition, SpendPilot as the only product name, no bank branding, no landing page.

## Tokens

Colours, type, radius, and spacing stay on the phase 1 tokens. Inter is self-hosted. Money uses tabular numerals. Semantic pairs are words plus colour: attention (amber), watch (rose), note (navy). A higher spend is not painted as success. A refund is not painted as income.

Desktop content uses the 232px sidebar and a 12-column grid from 1280px up. From 1024px to 1279px the briefing, obligations, trend, and categories stack. Below 768px the sidebar becomes the existing drawer and transactions become cards. The evidence drawer is 440px on a wide screen and full width on a phone.

## Screens

Overview leads with a September takeaway and three findings, then a coming-due list. A strip of three values sits under that on a phone and after the first row on a wide screen. The trend and category breakdown describe the same net spending figure; they do not add a second total. Card payments and the instalment repayment are labelled as excluded from spending. The original AED 6,000 purchase is not added to September.

Transactions are a filterable table, with a card list on a phone. A row opens the evidence drawer and leaves the filters in place. Arabic description text keeps its own direction.

Advisor is a conversation, a structured finding, and an evidence panel. Suggested text is “What changed this month?”. Send explains that no model is configured. Stop stays disabled because nothing is running. Completed activity is a short list, not hidden reasoning.

## Development only

Fixture rows, totals, and the component preview at `/dev/components` load only when Vite is in development. The production build shows an empty state and does not carry those figures. The banner on every preview screen says the data was not imported from a statement and that no bank is named.

## Out of this phase

Cards, statement review, obligations as their own screen, scenarios, and the rest of the product stay placeholders. Category edits, upload, and review are visible and explain why they do not run yet.

## Visual review

Screenshots were taken from the running Vite app, signed in, at 1440×900, 1024×768, and 390×844, in light and dark. None of those captures had page-level horizontal overflow. The production bundle was built separately and does not contain the fixture strings.

Fixes after the first pass:

- The evidence drawer covered the sidebar. It now starts to the right of the 232px sidebar, and it is full screen only below 768px.
- Between 1024px and 1279px the advisor evidence control was hidden while the side panel was not shown yet. The control now stays available until the panel appears at 1280px.
- Category bars used navy and slate that disappeared on the dark surface. Dark mode uses lighter bars, still with text labels.

Phone transaction shots are split: the card list, then the open drawer, because the drawer fills the screen. Advisor evidence below 1280px is a separate sheet shot for the same reason.
