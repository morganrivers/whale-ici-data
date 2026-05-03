README for pacific_coda_data.csv

The .csv file contains the 24,237 codas that were the basis of analysis in Hersh et al. (2022). Each row is a single coda. The file columns are:

clan_name: name of the clan that the repertoire containing the coda was assigned to. Abbreviations are: FP = Four-Plus, PALI = Palindrome, PO = Plus-One, REG = Regular, RI = Rapid Increasing, SH = Short, SI = Slow-Increasing, #N/A = not assigned to a clan.
within_clan_correlation: provides the within-clan correlation value for the repertoire that the coda belongs to with regards to the rest of the repertoires in the clan.
coda_type: numeric code indicating which coda type the coda was assigned to. #N/A means the coda was not assigned to a type (i.e., the coda had either 2 clicks or > 10 clicks).
grpvar: a numeric code indicating the repertoire the coda belongs to.
loc: location where the coda was recorded. See Table S1 for region abbreviations.
year: year the coda was recorded.
date: date the coda was recorded.
latitude: latitude of coda recording location.
longitude: longitude of coda recording location.
coda_num: unique numeric identifier assigned to each coda.
nclicks: number of clicks in the coda.
duration: total duration of the coda.
ICI1-ICI30: inter-click intervals (ICIs) 1-30 for each coda. The number of ICIs is equal to the number of clicks minus one.

November 11, 2022 update:
Thanks to the astute observations of Jose Coch, it was brought to our attention that some of the values in the "duration" column did not add up to the sum of the corresponding ICIs.
When rounding all durations to two decimal places, this discrepancy affected 829 codas.
Of those, the difference was +/- 0.01s for 801 codas.
That left 28 codas with more significant discrepancies, ranging from +/- 0.02 up to 3.00s.
In the updated spreadsheet version, we have created a new "duration" column that is simply the sum of the ICIs for each coda, thus resolving this issue.
We apologize for the original errors in the "duration" column, but are relieved to report that the issue has no effect on the results in our 2022 PNAS paper, as that work focused exclusively on ICI and not on total coda duration.
Nevertheless, we are very grateful to Jose Coch for detecting and notifying us of these issues.
