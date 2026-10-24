# Design — RTS Returns Manager

## Concept

A return is a paper form that got taken seriously. The screen is a stack of
numbered waybills on a white desk: every return is filed as a printed form with
a serial number, ruled fields and a decision that lands as a rubber stamp.
Nothing on the page pretends to be software decoration. If it would not make
sense printed and pinned to the station wall, it is not in the design.

## Palette

- Paper `#FAFAF7` — the sheet everything sits on
- Ink `#141414` — text, rules, the stamp for hold decisions
- Stamp red `#C8102E` — decisions, the brand mark's return arrow, focus of blame
- Rule grey `#D8D8D2` — internal field rules only

Three inks and a grey. No other color is allowed to exist in this interface.

## Type

- **Archivo** (500/700/900) — form headings, the wordmark, field labels set in
  tracked uppercase. Black weight for anything that must read as printed.
- **IBM Plex Mono** (400/600) — tracking numbers, form serials, dates, phones,
  every figure. Tabular by birth, so columns of numbers align like a ledger.

## Signature layout move

Each return is a full-width form on a strict grid: the serial number sits huge
at the left margin (`№003`, with the form code `RTS-20261024` under it), the
fields align to ruled columns in the middle, and the decision desk — stamp,
call log, decision controls — closes the form on the right. The day's figures
live on one ruled ledger line under the masthead, separated by hairlines,
never in boxes.

## Signature interaction

The stamp. A decided return carries its decision as a rotated stamp mark in
the form's corner, with a worn-ink mask so it reads as rubber on paper, not a
badge. When the supervisor stamps a decision, the mark slams in — a 380ms
scale-and-settle with a hard mechanical easing — then stays still forever.
An undecided form shows the same stamp as a faint dashed outline: the empty
space where the decision belongs.

## Deliberately avoided

- No KPI stat cards, no pill badges, no border radius anywhere, no shadows.
- No traffic-light palette: red here is printer's ink, not an alarm system.
- No unstyled native controls: the date, search, selects and the CSV file
  picker are all drawn in the form's own language.
- No emoji, no icon font. The brand mark is one drawn SVG: a form outline
  with the return arrow inside it.
