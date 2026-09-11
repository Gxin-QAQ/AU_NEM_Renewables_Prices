# Research questions and interpretation

This study examines wind and utility-scale solar generation, wholesale prices
and negative-price events in Australia's National Electricity Market. The
panel study covers July 2019–June 2025; a forecasting extension evaluates
whether lagged renewable generation adds information beyond past prices,
negative-price events and demand.

中文概述：本项目研究澳大利亚电力市场中风电和集中式光伏出力与电价的关系，并检验历史出力信息能否改善负电价概率预测。计量结果描述条件相关关系；预测结果以两小时数据可用性假设为前提。

## What are the main results?

In the four-region panel, a 10-percentage-point increase in the capped wind
and utility-solar share is associated with A$11.80/MWh lower hourly prices,
a 3.58-percentage-point higher probability of a negative-price event, and
A$5.03/MWh lower within-hour price standard deviation, conditional on the
specified controls and fixed effects. Regional estimates differ substantially.

In the forecasting extension, adding lagged renewable generation reduced
confirmation-period Brier error by 6.38% relative to the price, event and
demand control. Confirmation covers July 2024–June 2025 and 35,040 region-hours.

## What counts as a negative-price event?

An event occurs if at least one five-minute regional reference price in the
target hour is below zero. It does not require the whole hour, or its average
price, to be negative. A region-hour is one hour in one region: four regions
observed at the same time contribute four observations.

## What does a 6.38% Brier improvement mean?

Brier score is the mean squared difference between predicted probabilities
and binary event outcomes. On the same confirmation observations, it fell
from 0.08317 for the control to 0.07786 for the renewable model. The 6.38%
relative reduction uses the unrounded scores. It measures probability error,
not investment return or the fraction of correctly classified events.

## How is the forecast evaluated?

The models are refitted monthly using eligible earlier observations.
Development covers July 2023–June 2024, followed by the confirmation period.
Inputs use exact lags of 2, 24 and 168 hours. Scaling is estimated within each
training window, and all four models are scored on the same region-hours.

The two-hour data-availability rule is an assumption. Historical publication,
revision and fuel-label records have not been fully audited, so the results
describe a conditional historical replay rather than verified live operation.

## Was FY2025 excluded from model fitting?

Earlier confirmation outcomes may enter later monthly fits after the
availability rule is satisfied. Each forecast uses an earlier fit. FY2025
also appeared in the original panel study; it was not wholly unseen research
data. The extension specification was fixed before confirmation scoring.

## Do the results establish causality?

Renewable dispatch and prices can both respond to demand, outages, network
constraints and bidding. Fixed effects account for some shared variation but
do not isolate an exogenous change in renewable supply. The panel estimates
are conditional associations. Better forecasts show incremental predictive
information under the replay assumptions, not a causal policy effect.

## How should the dashboard's two percentages be read?

For pooled confirmation, the mean forecast probability is 27.45% and the
observed event frequency is 28.11%. One averages sequential predictions; the
other counts the share of region-hours with an event. Neither is a forecast
for a specific future hour. Their difference is the overall calibration bias;
a small overall bias does not imply good calibration in every probability bin.

## Why does this matter to market participants?

A generator selling at a negative spot price receives a negative energy
payment on that output. A spot-exposed buyer may benefit, whereas a fixed
retail tariff may not pass the price through. Storage may have an opportunity
to charge, depending on capacity, efficiency and the value of later use.
Contracts and operating constraints determine the net exposure in each case.

These mechanisms connect price risk to demand flexibility, production
decisions and contract design. The study does not estimate participant
cash flows. That would require interval prices, electricity volumes and
contractual terms, as well as operating constraints for storage.

中文说明：同一负电价事件对发电商、用电方和储能方的含义不同。经济分析关注激励与供需调整，金融分析关注现金流和合同敞口。当前结果支持概率比较和机制讨论，不能直接换算为实际盈亏。

## Why use a small set of models?

The comparison tests whether the renewable feature group adds information
to an interpretable control. The models and acceptance thresholds were fixed
before confirmation scoring. Further model selection would require a new
evaluation design rather than reusing confirmation outcomes for tuning.

See the [extension report](../report/phase2_forecast_extension.md) for methods
and estimates, and the [public evidence note](phase2_publication.md) for
available artifacts and reproduction requirements.
