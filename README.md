[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/yugot-coder/gta6-twitch-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/yugot-coder/gta6-twitch-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

# GTA VI launch-day Twitch forecast

An entry for make.fun's **gta6-twitch-ccu-forecast-01**: forecast, hour by hour,
how many people watch Grand Theft Auto VI live on Twitch over the 24 UTC hours
of its release day (19 November 2026), as five quantiles per hour, from
everything recorded up to the end of the day's first hour.

`main.py` (Python 3.13, standard library only) reads the case the grader gives
it — hour 1's printed count, the recorded history, and a library of past
launches with their hourly curves — and writes the forecast. No network, no
hard-coded counts: the case carries the level, the library carries the shape.

## Method

Each past launch's release day becomes a curve of log-ratios to its own
hour 1, so launches of any size pool together. A launch is weighted by how
much its situation resembles the target's: a gaussian kernel on log hour-1
scale (a launch's size is its strongest family trait), a smaller factor for a
mismatched pre-launch ramp, for launches that also shipped on PC (a
simultaneous PC unlock stamps a different first-day shape; this contest's
launches are console-only), and for launches whose early access had already
run hot. The forecast is the weighted log-ratio distribution's five quantiles
per hour, smoothed across neighbouring hours, with the spread pulled slightly
in about the median. Constants were calibrated by leave-one-out over the
comparable library and against the contest's four practice launches.

## Why this shape for GTA VI

GTA VI is the most pre-ordered game in PlayStation Store history (Sensor
Tower estimates passed 10 million pre-orders and $1 billion before launch),
console-only, unlocking at midnight local time country by country from New
Zealand. Streams Charts measured a 2.50 million Twitch peak for the category
on 18 November from the first regions alone — past every previous game
launch's Twitch peak (Valorant's closed beta, 1.74 million). A rolling
console launch's UTC day is not front-loaded: the practice launches (Red Dead
Redemption 2, God of War Ragnarök, Marvel's Spider-Man 2, Marvel's Wolverine)
all peaked 17–22 hours into the UTC day at 1.7–9× their first hour, as Europe's
prime time overlapped the Americas' afternoon. The pooled forecast encodes
exactly that: hold near hour 1 through the European night, build through the
US unlocks, and crest in the transatlantic evening.

On the four practice launches this program scores a mean log-pinball loss of
about **0.20**, against the persistence baseline's 0.39.
