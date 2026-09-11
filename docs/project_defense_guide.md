# Project defense guide

This guide is for explaining the NEM project in an economics or finance
application. It describes the verified project evidence. Personal contribution
and learning statements must be checked by the applicant before use.

## The project in 45 seconds

The first-person drafts below require the contribution check at the end of
this guide. Being able to explain an artifact is different from having designed
or written it independently.

### English

I studied Australia's National Electricity Market in two connected layers. The
first is an applied energy-economics study of how renewable penetration moves
together with wholesale prices, negative-price risk and intrahour volatility.
The second is a time-ordered probability replay: using only lagged information,
I tested whether wind and utility-scale solar improve forecasts of a negative
five-minute price in the next hour. In the confirmation period, the renewable
candidate reduced Brier error by 6.38% against a lagged price, event and demand
control. I present this as conditional predictive value under a stated
two-hour availability assumption, not as a causal effect or a trading-profit
claim.

### 中文

这个项目分成相互连接的两层。第一层是应用能源经济学研究，分析可再生能源渗透率与批发电价、负电价风险和小时内价格波动之间的条件相关关系。第二层是按时间顺序进行的概率预测回放：只使用滞后信息，检验风电和公用事业级光伏是否能改善下一小时出现五分钟负电价事件的预测。在确认期，相对于使用滞后电价、事件和需求量的逻辑回归对照，加入可再生能源信息后 Brier 误差降低了 6.38%。这个结果以两小时数据可用性假设为条件，表示预测价值，不代表因果效应或交易收益。

## What changed after the extension

| Earlier project | Extended project |
|---|---|
| Explained a conditional relationship in historical market data | Added a probability-forecasting question with an explicit forecast origin |
| Main language was applied economics and econometrics | Added market risk, calibration and uncertainty language |
| Reported price, volatility and negative-price associations | Compared four fixed models with monthly expanding fits |
| Dashboard showed economic findings | Dashboard now offers economics and finance/risk reading paths |

The extension does not turn the project into an asset-pricing or trading
strategy project. It gives the economic study a measurable risk-forecasting
layer.

## Common questions

### Is this an economics project or a finance project?

It is an interdisciplinary energy-market project. The economic layer asks what
is associated with renewable penetration and prices, while the finance layer
asks whether information can improve a probability forecast that a market
participant could use to monitor risk. For an economics application, lead with
market mechanisms, panel design, fixed effects, heterogeneity and the
association-versus-causation boundary. For a finance application, lead with
forecast origins, Brier loss, calibration, time dependence and risk exposure.

### Why use the Brier score?

The target is a probability, so a proper probability score is more informative
than a simple hit rate. Brier score penalises the squared distance between a
forecast probability and the event outcome. A lower score means better
probability forecasts on the same future observations. The 6.38% figure is a
relative reduction in this error, not a 6.38% return or accuracy rate.

### Why use time-ordered evaluation?

A random split could let later market conditions influence an earlier training
sample. The replay uses a development period and a later confirmation period,
with monthly expanding refits. Exact lags are 2, 24 and 168 hours, and each
realised input must satisfy the declared two-hour availability rule.

### Why does the result not prove causality?

Renewable output, demand, outages, network constraints, bidding and prices are
jointly determined. The forecasting improvement says that lagged renewable
variables add predictive information under the replay design. It does not
identify what would happen if renewable supply were changed by policy or by an
exogenous intervention.

### What does the electricity-exposure example add?

The dashboard compares two quantities: the candidate's mean predicted
probability and the observed event frequency. In pooled confirmation these are
27.45% and 28.11%, respectively. The first is an average of sequential forecasts;
the second is the share of evaluated region-hours that actually contained at
least one negative five-minute price. Neither is a forecast for a particular
future hour, and the event does not imply a negative price throughout the hour.

A generator selling output at a negative spot price has a negative energy
payment on that output, while a spot-exposed buyer may benefit; contracts and
hedges change the net exposure. Storage may have an opportunity to charge,
subject to capacity, efficiency and the value of later use. These are
illustrative mechanisms, not estimated participant outcomes.

For economics, this motivates questions about incentives, demand flexibility
and which participants bear price risk. For finance, it motivates exposure
monitoring, cash-flow sensitivity and contract analysis. A monetary extension
would require interval prices, volumes and contractual terms, plus operating
constraints for storage. Multiplying an event probability by 100 MWh would not
produce a monetary risk measure. The earlier arbitrary 100-MWh illustration has
therefore been removed.

中文解释：第四项对两类申请都有用。经济学侧重同一价格信号如何对应不同参与者的激励、需求调整和风险分配；金融侧重这些价格事件如何影响敞口、现金流与合同安排。当前项目提供概率证据和机制讨论，没有估计这些参与者的实际盈亏或政策效果。

## Adapt the opening to the application

Choose the opening that matches the programme, then use the same underlying
evidence. The emphasis changes; the results and limitations do not.

### Economics opening

This project examines how wind and utility-scale solar penetration relates to
wholesale electricity prices in Australia's NEM. The panel analysis considers
price levels, negative-price events and within-hour volatility, with fixed
effects, regional heterogeneity and robustness checks. A 10-percentage-point
increase in renewable share is conditionally associated with A$11.80/MWh lower
hourly prices and a 3.58-percentage-point higher negative-price probability.
The forecasting extension asks whether recent renewable information also adds
predictive value. The central limitation is identification: these associations
do not isolate a causal effect of renewable supply or policy.

中文重点：先讲经济问题、面板设计和地区差异，再讲预测扩展；参与者示例用于提出激励与灵活性问题，不用于证明政策效果。

### Finance and market-risk opening

This project evaluates whether lagged renewable information improves
negative-price probability forecasts in Australia's NEM. Under a stated
two-hour data-availability assumption, a fixed logistic candidate reduced
confirmation-period Brier error by 6.38% relative to a price, event and demand
control. Monthly expanding fits and calibration checks connect the empirical
question to risk modelling. The result is a conditional historical replay:
historical data vintages remain unverified, and event probabilities alone do
not establish cash-flow losses or trading profits.

中文重点：先讲预测时点、对照模型、误差与校准，再用发电商、用电方或储能方解释敞口；没有收益数据时，不把概率改善换算成收益改善。

### Why not add many machine-learning models?

The question is whether the renewable feature group adds information, not which
large model wins after tuning. The fixed candidate was compared with seasonal
and interpretable controls under a pre-registered gate. Adding models after
seeing the confirmation result would weaken the time-ordered comparison.

### Was FY2025 completely unseen?

No. The specification was fixed before confirmation scoring, but later monthly
fits can use earlier confirmation labels after the two-hour embargo. FY2025 was
also present in the original economic study. The correct description is a
sequential confirmation replay, not a wholly untouched research sample.

## Personal contribution checklist

Use the following wording only after checking that it matches the applicant's
actual work. Replace the bracketed items with facts that can be defended.
For each row, record whether the work was independently done, assisted, or
reviewed, and name one decision or correction that can be explained in an
interview. Do not select the strongest verb merely because the artifact exists.

| Area | Safe draft wording | Evidence to verify |
|---|---|---|
| Question | “I framed the project around renewable penetration, prices and negative-price risk.” | Research question and project brief |
| Data | “I worked with an AEMO region-hour panel aggregated from five-minute observations.” | Data and provenance records |
| Econometrics | “I specified and interpreted the conditional association models and their robustness checks.” | Frozen Tasks 7–9 materials |
| Forecasting | “I set the forecast origin, lag structure and time-ordered comparison.” | Phase 2 configuration and audit |
| Implementation | “I implemented or reviewed the reproducible Python workflow.” | Code history and test results |
| Validation | “I checked leakage boundaries, calibration and the fixed adoption gate.” | Focused tests and saved manifests |
| Presentation | “I turned the results into a public dashboard with separate economics and risk paths.” | Dashboard and repository |
| Learning | “The project taught me [specific concept] through [specific action].” | A concrete example the applicant can explain |

Avoid saying “the model predicts profits”, “renewables cause lower prices”, or
“FY2025 was completely unseen”. None of those statements follows from the
verified evidence.

A useful contribution answer is: “I was responsible for [specific task], with
[assistance, if applicable]. I checked [specific artifact or result], and changed
[specific choice] because [reason].” Supply actual facts before using it.

## Last-minute answer structure

When time is short, answer in this order:

1. state the research question;
2. name the data and unit of analysis;
3. explain the time and information boundary;
4. give the 6.38% confirmation result;
5. state one limitation and one practical interpretation.

The full method, evidence hashes and reproduction boundary are documented in
the [Phase 2 publication note](phase2_publication.md) and [extension report](../report/phase2_forecast_extension.md).
