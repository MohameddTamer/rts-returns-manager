# Changelog

## 0.4
The page was rebuilt as what it always claimed to be: a printed waybill ledger. English only, left to right. Returns are numbered forms on a strict grid now, the day's figures sit on one ruled ledger line instead of stat cards, and a decision lands as an animated rubber stamp in the form's corner. Archivo carries the forms, IBM Plex Mono carries every number, and every native control (date, selects, the CSV file picker) is drawn in the form's own language. The seeded desk notes were translated to English; no backend logic, math or demo number moved. See DESIGN.md for the direction and CRITIQUE.md for the evidence.

## 0.3
CSV import landed, because typing the night pile in one parcel at a time is where mistakes breed. The import names its duplicates by tracking number and its rejected rows by line and reason instead of failing quietly. Charts for returns by reason and the daily trend are drawn from a new range report endpoint, with quiet days filled in rather than skipped. The page gained a printable daily and weekly report view. Errors are structured JSON everywhere now, the app keeps a rotating log file, configuration moved to environment variables, and the supervisor can take a timestamped database backup from an admin only endpoint. One quiet fix underneath: dates that match the YYYY-MM-DD shape but do not exist, like the 40th of a month, are refused now.

## 0.2
Returns board now answers by day, with reason counts on top. Search covers tracking, courier and office in one box. Reship rule landed after a parcel nearly went out twice to the same wrong address, a reship now needs a logged customer contact first.

## 0.1
First working version. Returns logged with reason codes, decision queue, login for the desk.
