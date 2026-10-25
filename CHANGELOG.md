# Changelog

## 0.9.7.9.12
- Fix: EDCJ no longer exits when the journal folder is wrong or missing. A non-existent `-d` path is ignored with a warning, and EDCJ starts anyway, so the folder can be set under Settings → Journal folder.

## 0.9.7.9.11
- New: **Settings → Journal folder**: set the folder with your journal files in the app (checked for Journal*.log before saving, applied immediately, "Search automatically" resets it). The `-d` start parameter still takes precedence.
- Fix: a wrong `-d` path now stops EDCJ with a clear message instead of starting silently. If no journal can be found while running, a prominent banner with a button to the setting appears at the top instead of a small note.

## 0.9.7.9.10
- Colonies → Im Bau: new first tab **Überblick** next to Cheapest price and Few markets. Per site and commodity: required, delivered, missing, in carrier, still to buy, progress and status (open / partly in carrier / covered by carrier / done), plus a total row. Independent of market and price.

## 0.9.7.9.9
- New: **Colonies → Meine Kolonien**: your three colonised systems (Pegasi Sector GO-E a13-2, Col 285 Sector TY-K b23-3, Col 285 Sector DD-I c10-4) with the figures from the in-game screen and everything your journal knows about each system: population, controlling faction, government, economy, security, coordinates and distance to Sol, stations and settlements, traces of the colonisation (colonisation ships, construction sites with progress), factions, and your own activity there. System data is recorded from now on (journal re-read once on first start).

## 0.9.7.9.8
- New: **Ship → Fleet Carrier → Bestand**: stock list of all commodities you know from your markets (with search and "only with stock or demand"), a field to add (+) or remove (−) an amount per commodity, and the missing amount of your construction sites per commodity. EDCJ counts cargo transfers into and out of the carrier itself from the first time the page is opened.
- Colonies → Im Bau: the input field moved to the carrier stock page. Both views (Cheapest price and Few markets) now show Required, In carrier, Still to buy, Delivered and Missing per commodity.

## 0.9.7.9.7
- Colonies → Im Bau → Few markets: the system name next to each market is clickable (copies it, so you can paste it into the galaxy map in the game); the market stays folded when you click it.

## 0.9.7.9.6
- Colonies → Im Bau: new input field **Im Carrier** per commodity. Enter your carrier stock by hand; from then on EDCJ counts every cargo transfer into the carrier (and out of it) from your journal. **Still to buy** = missing minus carrier stock, shown per commodity, in the site summary (with trips) and used for the sources and the "Few markets" view. Cargo transfers are recorded from now on (journal re-read once on first start).

## 0.9.7.9.5
- Colonies → Im Bau: switch per construction site. **Cheapest price** (cheapest market with stock per commodity) or **Few markets** (regardless of price: markets ordered by covered tons, each commodity at the first market that can supply it, plus a list of what none of your markets offers).

## 0.9.7.9.4
- Colonies → Im Bau: deliveries are summarised per day (number of deliveries, tons, goods); click a day to see the single deliveries.

## 0.9.7.9.3
- Colonies → Im Bau: only construction sites that are still under construction are shown (completed or failed sites are hidden).

## 0.9.7.9.2
- New tab group **Colonies** (between Market and Ship), first sub-tab **Im Bau** (under construction): shows the construction sites you opened in the colonisation menu with progress, missing tons, goods value and trips (missing tons divided by your cargo space). Per site, every required commodity is listed with required / delivered / missing amount, the value the game states, and the cheapest source with stock on your own saved markets. Deliveries are recorded from now on (journal re-read once on first start).

## 0.9.7.9.1
- Cockpit (at a station): the market age now counts from the last time you opened the market, not from the last time prices changed.

## 0.9.7.9
- New: **Review** (Cockpit → Rückblick), six views from your own data: **Weeks** and **Months** (calendar period against the one before: income, expenses, net, trade profit, bounties, kills, tritium mined, jumps, distance, active time; table of all periods), **Profit by commodity**, **Routes** (each sale matched to earlier purchases of the same commodity, oldest first), **Cargo vs. distance** (profit per ton, number of trips and total profit by amount per trip and straight-line distance) and **Assets** (total assets per week plus income per week by source: trade, mining, bounties, missions, exploration, other). Charts included.

## 0.9.7.8.1
- Station file: recovery rate is now measured from your own purchases and sales (amount before, minus what you traded, compared with your next market snapshot). Values are limits ("at least", "at most"), because the game only writes the market when you open it. "Good to sell / cheap to buy" is sorted by absolute difference per ton.

## 0.9.7.8
- New: **Station file** (Market → Stationsakte): profile per station (visits, landing pads, services, faction, your note, your trading there), good to sell / cheap to buy, price check against your own history, and **recovery rate** (how fast stock or demand came back between your snapshots after you bought or sold). Services are recorded from now on (journal re-read once on first start).
- New: **Orders** (Dienstakte → Milestones → Orders): hidden awards from completed Journey missions. The conditions are not shown; name, motto and reason appear once an order is awarded.

## 0.9.7.7.4
- Cockpit: row "Jump range" shows only the current value; the maximum (unladen) value has its own row "Jump range max."; the row "Jumps until empty" was removed.

## 0.9.7.7.3
- Cockpit: new row "Jump range: current X Ly · unladen Y Ly" (calculated from loadout, cargo and fuel level; matches the in-game value).
- Commodity finder: selection list (dropdown) added next to the text field, works on tablets.
- Market comparison: stations sorted by system, then station name.

## 0.9.7.7.2
- New under Career: **Sessions** (one report per game start), **Team** (who you flew with; wing versus solo per hour) and **Combat analysis** (bounty path with credits per day / opponent / hour, scanned opponents, shields and heat by system). All figures come from your own journals.

## 0.9.7.7.1
- Cockpit: power distribution now shows SYS / ENG (German: ANT) / WEP (German: WAF) with 4 boxes each, half pips shown as half-filled.

## 0.9.7.7
- New: **Market comparison** (Market → Marktvergleich / Market comparison). Pick two saved stations and see what you can buy at one and sell at the other for a profit, in both directions, filled up to your free cargo space (default: ship capacity; or enter free space). Shows profit per ton, quantity, total profit, purchase cost and price age.

## 0.9.7.6
- Translation fixes in the English interface (mission tags, difficulty, small words).
- Manuals (German/English PDF) added under `docs/`.

## 0.9.7.5
- Font "Antonio" is now bundled (SIL OFL 1.1). EDCJ makes no requests to third-party servers any more.
- MIT license, `.gitignore`, English README (German: `README.de.md`).

## 0.9.7.4
- Language selector in Settings: Deutsch / English (per device). Only EDCJ's own texts are translated; game data is shown as the game client writes it. Number and date formats follow the language.

## 0.9.7.3
- Cockpit › Maintenance as its own tab next to Live and Missions.
- Journey missions: target values calibrated to your own recent play; new mission types; weekly chapters (three sub-goals, theme follows your play time).
- Career › Discoveries: first discoveries with special features, value estimate checked against your real exploration sales.

## 0.9.7.2
- Fixes in the maintenance and blueprint views.

## 0.9.7.1
- Ship comparison (columns side by side), pre-flight maintenance (fuel, hull, modules, ammo, rebuy), blueprints (missing ingredients for further crafts).

## 0.9.7
- Tablet: clicking a system name sets the course on the PC's clipboard ("Course set").

## 0.9.6 – 0.9.6.1
- Tablet and home-network access (`--lan`, access code), layouts for tablets in landscape and portrait, fullscreen mode, two-finger zoom on the travel map, layout fixes.

## 0.9.5.1
- Period selection now includes 1 week.

## Earlier versions
- Journal evaluation with LCARS look: cockpit, navigation, markets, ships, career, service record (Journey missions, ranks, milestones), finances, Captain's Log, gallery, play style.
