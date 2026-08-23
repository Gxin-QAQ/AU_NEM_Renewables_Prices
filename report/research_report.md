---
title: Renewable Penetration, Wholesale Electricity Prices and Volatility in Australia's National Electricity Market
author: Jixin Guo
date: 23 August 2026
subtitle: A region-hour panel study, July 2019–June 2025
---

# Executive summary

Australia's electricity transition creates two related questions. Does greater wind and utility-scale solar penetration lower the wholesale price, and does it make short-run price outcomes less stable? This report builds a reproducible hourly panel from Australian Energy Market Operator (AEMO) dispatch data for New South Wales, Victoria, Queensland and South Australia from July 2019 to June 2025. The five-region source panel, including Tasmania for robustness, contains 263,040 region-hour observations aggregated from approximately 3.16 million five-minute region intervals. The headline four-region estimation sample contains 210,399 observations.

The design compares regions within the same AEST hour while controlling for a region-specific year-month effect and a quadratic demand control. A 10 percentage-point increase in the wind-plus-utility-solar share is associated with an A$11.80/MWh lower hourly regional reference price, a 3.58 percentage-point higher probability that at least one five-minute price in the hour is negative, and an A$5.03/MWh lower within-hour standard deviation of five-minute prices. Results are precise under AEST-week clustered standard errors and retain their signs under alternative covariance estimators, samples, fuel mappings and fixed effects.

These estimates are conditional associations, not causal effects. Realised renewable output, demand, outages, network constraints, bidding and price are jointly determined. The raw share also becomes extreme when regional operational demand approaches zero; the headline p99.9 cap therefore describes economically typical support and changes only 211 observations, while the uncapped ratio is explicitly reported as a failed robustness check. A numerator-only output model supports the qualitative price and negative-price patterns. The evidence is consistent with a merit-order mechanism and a growing need for storage, transmission and flexible demand, but it does not identify the causal value of any policy intervention.

> Main conclusion: higher wind–solar penetration is associated with lower average wholesale prices and more frequent negative-price intervals, but not with greater within-hour price dispersion in the pooled headline model.

---PAGE---

# 1. Introduction and contribution

Wind and solar generators have low short-run marginal costs. In an energy-only gross pool such as the National Electricity Market (NEM), additional low-bid output can displace higher-cost offers and lower the regional clearing price. This merit-order channel is economically intuitive, yet observed prices reflect more than technology costs. Fuel prices, plant outages, transmission limits, strategic bids, demand conditions and settlement rules can move prices simultaneously with renewable dispatch. The empirical task is therefore to separate a credible conditional pattern from an unsupported causal story.

Australian evidence predating this sample generally finds downward price pressure from renewable generation. Forrest and MacGill [2] estimate a wind merit-order effect in the NEM, while Csereklyei, Qu and Ancev [3] find contemporaneous price reductions associated with dispatched wind and utility solar over 2010–2018. More recent work also shows that the October 2021 move to five-minute settlement changed bidding incentives and prices [4]. The present project extends that discussion with a transparent region-hour panel covering July 2019–June 2025, a period of increasing renewable penetration, major commodity-price shocks and the five-minute-settlement transition.

The report addresses four questions:

- Is greater wind-plus-utility-solar penetration associated with lower regional wholesale prices?
- Does penetration change within-hour price dispersion or the probability of a negative price?
- Are associations different across NSW, Victoria, Queensland and South Australia?
- Do they vary across seasons, peak and off-peak hours, or the pre/post-five-minute-settlement periods?

Three features distinguish the analysis. First, it joins price, operational demand and unit-level SCADA output using a fixed-AEST region-time key and an effective-dated unit fuel map. Second, it pre-specifies an exposure, outcomes, fixed effects, lag blocks, clustering and heterogeneity families before final estimation. Third, it treats robustness failures as findings. In particular, the report explains why a near-zero demand denominator destroys the raw-ratio result and why no weather instrument is claimed.

The contribution is consequently applied rather than structural: a fully reproducible empirical audit of how regional wholesale outcomes co-move with wind–solar penetration under a demanding common-hour comparison. The estimates are useful for describing market patterns and motivating flexibility investment; they should not be interpreted as the causal effect of installing renewable capacity or changing energy policy.

---PAGE---

# 2. Institutional setting and data

AEMO operates the NEM wholesale system and publishes public MMS/NEMWeb data for dispatch, regional prices, demand and generation [1]. The sample covers NSW1, VIC1, QLD1, SA1 and TAS1 from 1 July 2019 through 30 June 2025. Headline regressions use the four mainland regions named in the research questions; Tasmania enters as a robustness sample. AEMO's five-minute dispatch files are the primitive observation. They are converted to interval-start timestamps in fixed NEM market time (AEST, UTC+10), then aggregated to region-hour outcomes.

FIGURE: outputs/figures/fig1_price_and_renewable_share_trends.png :: Figure 1. Twelve-month moving averages of regional RRP and the wind–utility-solar share. Tasmania is shown descriptively and enters the robustness sample. Source: author's calculations from AEMO MMS data.

The full panel contains 263,040 region-hours. Price is hourly mean regional reference price (RRP, AUD/MWh). Within-hour volatility is the standard deviation of the twelve five-minute RRPs. Negative-price outcomes are constructed at the five-minute level before aggregation: the main indicator equals one when any interval in the hour is below zero; additional indicators use −50 and −100 AUD/MWh thresholds.

Wind and utility-scale solar output are summed from unit SCADA values using an effective-dated DUID crosswalk. The renewable share divides this output by regional operational demand. It is allowed to exceed one because regional generation can exceed local demand when a region exports. Thirty-three SA1 hours have non-positive demand and are excluded from demand-share models.

---PAGE---

# 3. Variable construction and empirical strategy

The main exposure is ten times the wind-plus-utility-solar share, so its coefficient represents a 10 percentage-point increase. The pooled raw ratio has a maximum of 392.9 because SA1 operational demand falls to 1.66 MW in an extreme hour. The frozen headline exposure therefore caps the raw ratio at its pooled p99.9 value of 2.789. This affects 211 of 210,399 headline observations (0.10%). Both the uncapped ratio and a share capped at one are retained as explicit robustness checks. A numerator-only specification uses wind-plus-solar output per 100 MW and avoids the demand denominator entirely.

For region r and AEST hour t, the headline specification is:

> y_rt = beta R_rt + f(log demand_rt) + region×year-month effects + exact-hour effects + error_rt.

Here R is the capped wind–solar exposure and f(.) is a centred quadratic in log operational demand. Exact-hour effects absorb every market-wide shock common to the included regions at that hour, including national fuel-price changes and broad weather or policy news. Region-by-year-month effects absorb slower regional changes. Identification comes from comparing regions in the same hour after those adjustments. Standard errors are clustered by AEST ISO week, giving 314 clusters.

The primary continuous outcome is asinh(RRP), which retains negative and zero values while reducing leverage from price spikes. The report also presents RRP levels for economic units. Binary negative-price models use a linear probability model in the headline table and fixed-effect logit/probit models as nonlinear checks. The volatility outcome is asinh of the within-hour five-minute-price standard deviation, with a level model for interpretation.

The pre-specified distributed-lag model adds four averages of the exposure over hours 1–3, 4–6, 7–12 and 13–24. Heterogeneity models interact the exposure with region, peak status, meteorological season and a post-1 October 2021 settlement indicator. Pairwise slope differences are tested with Holm corrections within each outcome-family. A 168-hour Driscoll–Kraay covariance and a two-way region/week benchmark assess time and cross-sectional dependence.

The estimand remains conditional. Exact-hour effects do not absorb region-specific outages, congestion, curtailment, bidding or local weather. A simple weather instrument is rejected because temperature and humidity directly affect demand, irradiance affects behind-the-meter PV and operational demand, and the project has no plant-location-and-capacity-weighted weather series. A causal IV extension would require those data, network and outage controls, first-stage diagnostics and weak-instrument-robust inference.

---PAGE---

# 4. Headline results

TABLE:
| Outcome | Effect per +10 pp share | Clustered SE | Interpretation |
|---|---:|---:|---|
| asinh hourly RRP | −0.2701 | 0.0125 | Lower transformed price |
| Hourly RRP level | −A$11.80/MWh | A$0.87 | Economically interpretable level effect |
| Any negative five-minute price | +3.58 pp | 0.14 pp | More negative-price hours |
| Negative five-minute share | +2.02 pp | 0.12 pp | More intervals below zero |
| asinh within-hour RRP SD | −0.0239 | 0.0042 | Lower transformed intrahour dispersion |
| Within-hour RRP SD level | −A$5.03/MWh | A$0.68 | Lower five-minute dispersion within an hour |

Table 1 reports the pooled association. A 10 percentage-point increase in the capped wind–solar share is associated with an A$11.80/MWh lower hourly RRP. The transformed-price coefficient is −0.270 and remains precisely estimated under week clustering. This direction is consistent with low-marginal-cost supply displacing higher-priced offers, although the regression cannot isolate that mechanism from region-specific contemporaneous conditions.

The same exposure is associated with a 3.58 percentage-point increase in the probability that at least one five-minute price is negative. Fixed-effect logit and probit average marginal effects are 4.02 and 3.91 percentage points; 399-replication AEST-week score-multiplier intervals exclude zero. For thresholds, the association is +0.45 percentage points for any interval below −50 AUD/MWh but only +0.09 percentage points, statistically indistinguishable from zero, below −100. The evidence supports more frequent negative pricing, not a reliable rise in the most extreme negative events.

The pooled within-hour volatility result is negative: −A$5.03/MWh in the level model. This does not establish that renewable variability is unimportant. The outcome measures realised five-minute dispersion within an hour, not forecast errors, reserve needs, daily volatility or long-horizon investment risk. Conditional on common-hour shocks and controls, high realised wind–solar shares are not associated with higher intrahour dispersion in the headline sample.

In the distributed-lag price model, the contemporaneous coefficient and four pre-specified lag blocks sum to −0.350 (SE 0.015). The score-multiplier 95% interval is [−0.378, −0.321]. Because renewable output is serially persistent and market adjustments are simultaneous, this sum is descriptive dynamic association rather than a cumulative causal impulse response.

---PAGE---

# 5. Regional, seasonal and peak heterogeneity

FIGURE: outputs/figures/fig5_regional_price_heterogeneity.png :: Figure 2. Region-specific slopes for transformed hourly RRP. Error bars are 95% confidence intervals based on AEST-week clustered standard errors. Source: author's estimates.

Regional slopes differ sharply. The transformed-price association is positive in NSW1 (+0.376) but negative in VIC1 (−0.481), QLD1 (−0.190) and SA1 (−0.283). Pairwise regional price differences remain significant after Holm correction; the least separated pair, QLD1 versus SA1, has an adjusted p-value of 0.044. Negative-price slopes are likewise heterogeneous: NSW1 is −1.77 percentage points, while VIC1, QLD1 and SA1 are +6.79, +4.62 and +3.43 percentage points.

This pattern should not be read as four technology effects. With exact-hour effects, each regional coefficient is a relative within-hour association. Interconnector flows, congestion, fuel mix, outage patterns, renewable location and curtailment can change both output and regional prices. The positive NSW slope is therefore evidence against a single pooled mechanism being mechanically valid everywhere and strengthens the case for region-specific market analysis.

Off-peak and peak price slopes are both negative (−0.280 and −0.254), with a modest but statistically reliable difference after Holm correction (p = 0.0078). The negative-price association is also slightly larger off peak (3.71 versus 3.35 percentage points; p = 0.0013). Volatility slopes do not differ across peak status (p = 0.648).

Seasonal price reductions are largest in JJA (−0.358), compared with −0.216 in DJF, −0.260 in MAM and −0.240 in SON. Several, but not all, pairwise differences survive Holm correction. Thus the defensible conclusion is regional and selected seasonal/peak heterogeneity—not universal separation across every group.

The price and negative-price slopes do not change reliably across the five-minute-settlement transition (adjusted p-values 0.145 and 0.287). In contrast, the volatility slope changes from +0.054 before 5MS to −0.060 after it. This sharp difference is noteworthy but may combine the market-rule change with other contemporaneous structural changes; it is not a causal 5MS estimate.

---PAGE---

# 6. Robustness and identification audit

FIGURE: outputs/figures/fig6_price_robustness.png :: Figure 3. Transformed-price coefficients across pre-specified robustness checks. All displayed share models use a 10 percentage-point unit. Source: author's estimates.

The price, negative-price and volatility signs survive a share capped at one, an extreme upper bound that treats all positive UNKNOWN-fuel output as renewable, inclusion of Tasmania, restriction to the post-5MS sample and replacement of region-month with region-date effects. The price association attenuates from −0.270 to −0.149 under region-date effects but remains precise. A numerator-only model associates each additional 100 MW of wind-plus-solar output with −0.036 in asinh price and +0.74 percentage points in negative-price probability.

The central failure is the raw uncapped share. Its price coefficient is −0.0146 (p = 0.177) and the negative-price coefficient is +0.21 percentage points (p = 0.155). Extremely low demand gives a handful of SA1 observations disproportionate leverage. The headline cap is therefore not a cosmetic transformation: it changes the estimand to the typical empirical support. The report presents that estimand clearly and does not claim denominator invariance. The numerator-only result supplies qualitative corroboration but is not numerically comparable.

Inference is stable to a Driscoll–Kraay covariance with a 168-hour bandwidth: the transformed-price SE rises from 0.0125 to 0.0147, while the sign and precision remain. A two-way region/week benchmark gives a larger SE of 0.0458 and also excludes zero, but four region clusters are too few for headline asymptotics. The week-cluster score-multiplier exercise supports the nonlinear marginal effects and the distributed-lag sum; it is an influence-function approximation, not 399 full model refits.

Fuel mapping does not drive the pooled result. UNKNOWN output rises late in the sample, yet classifying all of it as renewable changes the price coefficient only from −0.270 to −0.267. Separate raw wind and solar shares, however, are unstable and even produce a positive solar coefficient for transformed price. No technology-specific claim is made.

The planned full-sample unpenalised q = 0.50, 0.90 and 0.95 quantile regressions did not complete with either the dense estimator or the sparse HiGHS solver under bounded computation. They are omitted rather than replaced by a sampled, penalised or otherwise altered estimator.

---PAGE---

# 7. Economic interpretation and policy relevance

The joint pattern—lower average prices and more negative-price intervals—is consistent with a merit-order mechanism. When wind and solar output is available, low-bid supply can displace higher-priced thermal offers. At times of low demand or limited export capability, additional supply can push the clearing price below zero. Negative prices are therefore not simply “bad prices”; they signal that flexible consumption, storage, transmission or curtailment is scarce relative to available supply at that location and time.

The estimates describe wholesale spot outcomes, not retail bills. Retail tariffs also reflect networks, environmental schemes, hedging, retailer costs and regulation. Likewise, a lower spot price does not by itself establish a lower total system cost. Firming, network expansion, ancillary services and investment adequacy matter. The project therefore supports a narrow statement: on typical observed support, higher realised wind–solar penetration co-moves with lower regional wholesale prices and more frequent negative intervals.

The negative pooled intrahour-volatility association deserves careful interpretation. A high renewable share can occur during low-demand, well-supplied hours in which prices are consistently low, including consistently negative. That configuration can lower the within-hour standard deviation even if renewable forecast errors create balancing challenges elsewhere. The pre/post-5MS split further shows that one volatility coefficient is not structurally invariant. Future work should distinguish realised price dispersion from forecast-error volatility, frequency-control needs and longer-horizon price risk.

Regional heterogeneity has practical implications. Transmission constraints and interconnector availability determine whether low-cost output can reach demand. Storage and flexible load have greater value where surplus output and negative prices are frequent, while network reinforcement can reduce regional separation. However, the regression cannot rank individual transmission or storage projects. A project appraisal would require nodal or constraint-level data, counterfactual dispatch and investment costs.

The main policy lesson is therefore about complementarity. Increasing variable renewable supply creates wholesale price pressure, but its value depends on flexible demand, storage, interconnection and operational incentives that can respond at the same temporal and spatial resolution. The findings motivate those complements without quantifying their causal benefit.

Limitations remain material. The models omit plant outages, binding constraints, curtailment, bids, gas and coal prices at regional frequency, and plant-weighted weather. Exact-hour effects absorb common shocks but not region-specific shocks. Utility-scale solar is observed through registered units, while rooftop PV enters indirectly through operational demand. Finally, the p99.9 exposure cap protects the typical-support estimand from pathological denominators but limits extrapolation to rare export-dominant hours.

---PAGE---

# 8. Conclusion and reproducibility

This study assembles a six-year, five-region hourly NEM panel and estimates a pre-specified four-region fixed-effect design. Within the same AEST hour and after region-month and demand controls, a 10 percentage-point increase in the capped wind–solar share is associated with an A$11.80/MWh lower hourly wholesale price, a 3.58 percentage-point higher probability of any negative five-minute price, and an A$5.03/MWh lower within-hour price standard deviation. Regional slopes differ substantially, while peak/off-peak and selected seasonal differences are more modest.

The evidence is robust on economically typical support, but not to the raw uncapped demand ratio. That failure, the lack of a defensible weather instrument and strong regional heterogeneity prevent a causal interpretation. The appropriate conclusion is a carefully bounded conditional association consistent with merit-order pricing and flexibility scarcity.

All acquisition, cleaning, panel construction, estimation and audit commands use the repository-local `.venv`. The frozen specification is stored in `config/econometric_spec.yml`; generated tables are under `outputs/tables`; code and tests are under `src` and `tests`; and the data lineage and variable dictionary are documented in `data/README.md` and `docs/variable_dictionary.md`. At completion, the full test suite passes without using system Python.

## References

[1] Australian Energy Market Operator (AEMO). “Market Management System (MMS).” Public NEM data and MMS Data Model access. [AEMO MMS data page](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/market-management-system-mms-data)

[2] Forrest, S., and I. MacGill (2013). “Assessing the impact of wind generation on wholesale prices and generator dispatch in the Australian National Electricity Market.” Energy Policy 59, 120–132. [DOI 10.1016/j.enpol.2013.02.026](https://doi.org/10.1016/j.enpol.2013.02.026)

[3] Csereklyei, Z., S. Qu, and T. Ancev (2019). “The effect of wind and solar power generation on wholesale electricity prices in Australia.” Energy Policy 131, 358–369. [DOI 10.1016/j.enpol.2019.04.007](https://doi.org/10.1016/j.enpol.2019.04.007)

[4] Csereklyei, Z., and P. Khezr (2024). “How do changes in settlement periods affect wholesale market prices? Evidence from Australia's National Electricity Market.” Energy Economics 132, 107425. [DOI 10.1016/j.eneco.2024.107425](https://doi.org/10.1016/j.eneco.2024.107425)

[5] Australian Energy Market Operator (2021). “Five-Minute Settlement.” AEMO fact sheet. [AEMO five-minute-settlement fact sheet](https://www.aemo.com.au/-/media/files/learn/fact-sheets/5ms-factsheet.pdf)

## Claim boundary

The study reports conditional associations. It does not estimate the causal effect of renewable investment, the Renewable Energy Target, five-minute settlement, storage, transmission expansion or any other policy intervention.
