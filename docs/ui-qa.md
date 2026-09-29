# UI QA

SpendPilot, inspected in the running gateway at `http://127.0.0.1:8080` on 29 September 2026. The account in these shots is unverified, so the banner says statement import stays closed. That is an empty state, not demo data. No bank is named. The production build does not show the development fixture.

This is not a contrast audit and it is not a claim that the app is production-ready.

## How 200% was checked

Browser zoom at 200% gives the layout half as many CSS pixels. These shots use that viewport, not the CSS `zoom` property and not a device scale factor.

| Label | CSS viewport | Stands in for |
|---|---|---|
| 1440 | 1440×900 | Desktop, 100% |
| zoom200 at 720 | 720×450 | 1440×900 at 200% |
| zoom200 at 512 | 512×384 | 1024×768 at 200% |
| zoom200 at 195 | 195×422 | 390×844 at 200% |
| 390 | 390×844 | Phone keyboard pass |

`frontend/tests/ui-qa.spec.ts` waits for the page heading, scrolls to the top, and fails if `documentElement.scrollWidth` is wider than the viewport. Wide tables may scroll inside their own region. The page itself did not.

At 720 CSS pixels the shell uses the menu button. The desktop sidebar starts at 768px, so a 1440px window at 200% zoom is the phone shell. Text wraps. Nothing was clipped off the side.

## Keyboard pass

Played with the keyboard only, against the same gateway:

- Register: focus Username, type, Tab to Email, Tab to Password, Tab to Create account, Enter. The app lands on `/overview`.
- Control+K opens the dialog named Search navigation. Escape closes it.
- Tab reaches the theme toggle. Its computed `outline-style` is not `none`. Enter turns on the dark theme, Enter again returns to light.
- At 390×844, focus the menu button, Enter opens primary navigation, Escape closes it.

## Fixes made for this pass

- A route change scrolls to the top. After Create account on a short viewport, the header was left above the fold.
- Below 240px the header wraps. The Menu label stays available to the screen reader, and the icon button stays on the row with the SpendPilot wordmark.
- Text fields, including date fields, use `min-width: 0` so a date control cannot force the page wider than the viewport. The instalment form uses tighter padding on narrow screens, and plan amounts wrap.

## What the shots show

Overview has no published briefing. The review button stays unavailable until selected transaction details are chosen. Analytics, after one Laptop plan of 6000.00 AED over 12 parts, says this is not complete coverage, shows 0 months posted, and shows net spending 6000.00 AED from the instalment purchase. Obligations shows monthly commitment 500.00 AED. Cards, transactions, and statements are empty apart from their forms. Advisor and scenarios explain the gate before a run. Settings shows the model form with no saved key, and says SpendPilot does not fall back to a hosted model.

Light and dark were both captured on overview at 720×450. The other 720 shots are light. Contrast was not measured with a tool. The evidence drawer was not opened in this pass.

## Screenshot paths

- `/cursor/stores/bc-0ab49cf1-1382-4750-afb7-4a738ee5f16a/media/phase-7/overview-keyboard-focus-1440-light.png`
- `/cursor/stores/bc-0ab49cf1-1382-4750-afb7-4a738ee5f16a/media/phase-7/overview-keyboard-menu-390-light.png`
- `/cursor/stores/bc-0ab49cf1-1382-4750-afb7-4a738ee5f16a/media/phase-7/overview-1440-light.png`
- `/cursor/stores/bc-0ab49cf1-1382-4750-afb7-4a738ee5f16a/media/phase-7/overview-720-zoom200-light.png`
- `/cursor/stores/bc-0ab49cf1-1382-4750-afb7-4a738ee5f16a/media/phase-7/overview-720-zoom200-dark.png`
- `/cursor/stores/bc-0ab49cf1-1382-4750-afb7-4a738ee5f16a/media/phase-7/cards-720-zoom200-light.png`
- `/cursor/stores/bc-0ab49cf1-1382-4750-afb7-4a738ee5f16a/media/phase-7/transactions-720-zoom200-light.png`
- `/cursor/stores/bc-0ab49cf1-1382-4750-afb7-4a738ee5f16a/media/phase-7/statements-720-zoom200-light.png`
- `/cursor/stores/bc-0ab49cf1-1382-4750-afb7-4a738ee5f16a/media/phase-7/analytics-720-zoom200-light.png`
- `/cursor/stores/bc-0ab49cf1-1382-4750-afb7-4a738ee5f16a/media/phase-7/obligations-720-zoom200-light.png`
- `/cursor/stores/bc-0ab49cf1-1382-4750-afb7-4a738ee5f16a/media/phase-7/advisor-720-zoom200-light.png`
- `/cursor/stores/bc-0ab49cf1-1382-4750-afb7-4a738ee5f16a/media/phase-7/scenarios-720-zoom200-light.png`
- `/cursor/stores/bc-0ab49cf1-1382-4750-afb7-4a738ee5f16a/media/phase-7/settings-720-zoom200-light.png`
- `/cursor/stores/bc-0ab49cf1-1382-4750-afb7-4a738ee5f16a/media/phase-7/overview-512-zoom200-light.png`
- `/cursor/stores/bc-0ab49cf1-1382-4750-afb7-4a738ee5f16a/media/phase-7/overview-195-zoom200-light.png`
- `/cursor/stores/bc-0ab49cf1-1382-4750-afb7-4a738ee5f16a/media/phase-7/obligations-195-zoom200-light.png`
