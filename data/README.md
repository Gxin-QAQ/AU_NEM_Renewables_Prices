<p align="center">
  🇨🇳 中文 &nbsp;|&nbsp; 🌍 <a href="README_EN.md">English</a>
</p>

# 数据目录

本目录存放本地研究数据和生成的数据集。大型来源文件与派生提取文件刻意不提交至 Git；仅本 README 和 `.gitkeep` 占位文件被跟踪。

## 目录结构

| 目录 | 内容 | 脚本可覆盖？ | Git 跟踪？ |
|---|---|---:|---:|
| `raw/` | 不可变的来源下载、归档 ZIP 与下载清单 | 否 | 否 |
| `external/` | 手工获取的来源文件，如机组/燃料对照表输入 | 否 | 否 |
| `interim/` | 已解析、规范化且按来源划分的中间表 | 是 | 否 |
| `processed/` | 可直接用于分析的区域—时间面板 | 是 | 否 |

## 数据血缘

预期流程为：

`官方来源 -> raw/external -> interim -> processed -> outputs`

`raw/` 与 `external/` 中的文件视为不可变输入。官方来源若发布修订，应保存为新的数据版本，不能静默覆盖旧文件。只有流水线生成的 `interim/` 与 `processed/` 可以重建。

## 核心数据集

### `raw/manifest.csv`

每个下载文件一条记录：

| 字段 | 含义 |
|---|---|
| `source_name` | 人类可读的来源名称 |
| `source_url` | 精确解析后的下载 URL |
| `downloaded_at_utc` | UTC 获取时间戳 |
| `local_path` | 仓库相对存储路径 |
| `sha256` | 文件校验和 |
| `bytes` | 下载字节数 |
| `source_period` | 文件代表的月份/日期 |
| `status` | 下载/验证结果 |

### `raw/history_manifest.csv`

完整 FY2020–FY2025 AEMO 历史数据的清单：每月和每张表族（`region` / `price` / `scada`）各一条记录。记录已解析的旧版/现行归档 URL、本地文件、校验和、大小和验证状态。使用 `.venv/bin/python -m src.download_aemo_history` 重建或验证。

### `processed/nem_region_hour.parquet`

主分析面板，以带时区的 `timestamp` 与 AEMO `region` 为唯一键。预期列见 [`../docs/variable_dictionary.md`](../docs/variable_dictionary.md)。小时价格和波动变量由底层 5 分钟区间计算；发电与需求按已明确记录的规则聚合。

### `processed/nem_region_5min/YYYY-MM.parquet`

经验证的 5 分钟面板，用于复现小时聚合及负电价结果。单文件过大时可按年份和区域分区。

小时负电价阈值在聚合前于此计算：`negative_price_below_minus_50_any_5min` 与 `negative_price_below_minus_100_any_5min` 表示该小时任一 5 分钟 RRP 是否低于相应阈值；绝不能从小时平均价格反推。

### `processed/nem_region_hour_generation_demand.parquet`

小时中间面板，包含需求和按燃料分类的 SCADA 发电，但没有价格字段。它共有 263,040 条区域—小时记录（FY2020–FY2025），不是主分析面板；在获得并连接 `DISPATCHPRICE` 前不得用于任何价格主张。

### `processed/nem_region_hour_model.parquet`

最终小时价格面板派生的模型数据框，仅新增 `../config/econometric_spec.yml` 中冻结的转换、固定效应标识、周聚类、5MS 分割和滞后块。四区域主样本有 210,399 条可用观测；估计必须显式应用 `headline_sample` 或 `dynamic_sample` 标记。

### `interim/history_generation_demand_5min/YYYY-MM.parquet`

由已验证的区域需求与 SCADA 归档构建的、可断点重启的 5 分钟月度分区。它避免在价格表可用时重复处理全部 SCADA 历史；相应小时分区位于 `interim/history_generation_demand_hour/`。

### 试验性处理面板

`processed/nem_region_5min_pilot.parquet` 与 `processed/nem_region_hour_pilot.parquet` 是两个 2025 年七日窗口的验证输出，不能替代 FY2020–FY2025 生产面板。先重建 DUID 对照表后，可用 `python -m src.panel_builder` 重建。

### `external/aemo_reference/DUDETAILSUMMARY_202510.zip`

不可变的 AEMO MMSDM 2025 年 10 月注册归档，提供生效日期 DUID、区域、电站、参与者、计划及调度类型字段。精确来源 URL 和 SHA-256 校验和记在 `external/reference_manifest.csv`。

### `external/openelectricity/au_facilities_20260823.json`

公开 OpenElectricity 设施导出的不可变捕获，用作次级燃料技术来源。文件名记录捕获日期，manifest 记录精确捕获时间与校验和；不得将其描述为 AEMO 燃料字段。

### `interim/duid_crosswalk.csv`

生成的、按生效日期匹配的 DUID 至区域/燃料对照表。重要字段包括 `valid_from_aest`、`valid_to_aest`、`fuel_category`、`fuel_source_detail`、`mapping_method`、`review_status`、来源版本和校验和。使用 `python -m src.duid_mapping` 重建。

### `interim/duid_mapping_audit.json` 与 `interim/unresolved_duids.csv`

生成的试验审计输出。覆盖率同时按正 SCADA 电量和绝对 SCADA 电量报告；未知 DUID 保持显式可见，并按能源重要性排序。

## 来源与变量约定

- 在添加派生时间戳前保留精确 AEMO 区间时间戳。
- 规范时间戳使用带时区的 NEM 市场时间 `Australia/Brisbane`（固定 AEST/UTC+10）；不得把悉尼夏令时施加给市场来源时间戳，只有需要时才创建单独的州本地时间戳。
- 第一张解析表保留原始来源列，只能在有文档记录的转换步骤中重命名。
- 价格单位为 AUD/MWh，出力/需求单位为 MW。
- 没有明确变量名和换算规则时，不得混用计划目标、SCADA 出力和能量。
- 电池发电与充电必须分开；不得将净电池出力归为可再生发电。
- 将 AEMO `SETTLEMENTDATE` 保留为区间结束的来源标签，并另用区间开始时间戳进行分析。
- 运营需求为零或负时保留该行，但将基于需求的可再生占比设为缺失，并暴露显式标记。
- 不得把基于需求的可再生占比截断到一：区域发电大于运营需求时可能向外送电。截尾或 winsorised 值只能作为明确标注的稳健性变体。
- 对每个 DUID 记录所使用的 AEMO 注册/燃料映射版本。
- 注册记录必须按 `START_DATE <= timestamp < END_DATE` 连接；绝不能用仅当前有效的 DUID 映射回溯历史观测。
- 官方 AEMO 注册字段和次级燃料标签须放在独立的来源追溯列中。

## 验证闸门

数据集只有通过以下检查才能进入 `processed/`：

1. 模式与必需列检查；
2. 区域—时间唯一键检查；
3. 预期区域代码检查；
4. 5 分钟区间连续性及固定 AEST/夏令时边界检查；
5. 缺失值与物理不合理值检查；
6. 机组—区域和机组—燃料覆盖率检查；
7. 对抽样期间，将区域总量与独立 AEMO 发布物进行核对。

## 最终分析快照

- 来源历史：216 个已验证的月度 AEMO 归档（72 个区域需求、72 个价格、72 个 SCADA 文件）。
- 主小时面板：263,040 条观测、5 个 NEM 区域、2019 年 7 月 1 日至 2025 年 6 月 30 日。
- 主样本：210,399 条可用 NSW1/VIC1/QLD1/SA1 区域—小时记录，排除 33 条 SA1 非正需求小时后得到。
- 动态样本：应用冻结的滞后要求后为 209,928 条观测。
- 推断：314 个 AEST ISO 周聚类。
- 冻结 p99.9 占比上限：2.78918；受影响的主样本观测为 211 条。

面向报告的输出由 `processed/nem_region_hour_model.parquet` 和冻结的估计与稳健性结果表生成。未经重新构建或核对这些工件，不得手工改动报告数字。

## 复现

流水线提供独立的下载、解析、面板构建、验证、估计和报告命令。凭据/API key 必须通过本地环境配置提供，绝不可提交。所有研究命令都经仓库本地 `.venv` 运行；AEMO 及次级来源数据仍受各自条款与署名要求约束。

## 数据集状态

首次获取任务使用了两个 7 日窗口——一个普通时期与一个夏令时转换时期——随后扩展至全样本。所有命令均使用项目本地环境：

```bash
.venv/bin/python -m src.download_aemo_pilot --start 2025-09-08 --end 2025-09-14
.venv/bin/python -m src.download_aemo_pilot --start 2025-10-02 --end 2025-10-08
.venv/bin/python -m src.rebuild_aemo_manifest
```

2025 验证归档已获取，且已建立包含 SHA-256 校验和的 47 条记录 manifest。详见 [`../docs/task1_pilot_access.md`](../docs/task1_pilot_access.md)，其中记录了归档结构和解析要求。

按生效日期的 DUID/燃料构建也已为验证样本完成：它将所有观测到的 SCADA 电量解析到燃料/负荷类别，5 个零出力 `DG_*` 合成代码仍被显式标记为未知。映射规则、电池处理与覆盖审计见 [`../docs/task3_duid_fuel_mapping.md`](../docs/task3_duid_fuel_mapping.md)。

原始 FY2020–FY2025 来源历史完整：区域需求、价格和 SCADA 月度归档各 72 个，共 216 个文件。`DISPATCHREGIONSUM` 提供需求，独立的 `DISPATCHPRICE` 表提供 RRP，二者仅按有文档记录的固定 AEST 区域—时间键连接。完成的面板与描述性数据审计见 [`../docs/task6_descriptive_status.md`](../docs/task6_descriptive_status.md)。

目前 AEMO 公共日归档保留期限有限，因此 FY2020–FY2025 历史提取使用记录在 `raw/history_manifest.csv` 中、经验证的月度 MMSDM 归档流水线。

`raw/`、`external/`、`interim/` 和 `processed/` 当前均未存储天气提取数据。识别审计不支持天气 IV 的因果解释：天气同时影响运营需求和屋顶光伏，公共站点覆盖不均，也没有按电厂位置/容量加权的工具变量或排除限制审计。天气可在以后作为有文档记录的控制变量或独立版本化扩展加入；它不是当前估计量的一部分。

报告生成流程不新增或改动分析数据。它读取冻结的估计与稳健性结果表，生成两张报告系数图，并渲染最终英文报告；原始、中间和处理后数据契约均保持不变。

复现审计从零重建项目 `.venv`，核验全部 265 个本地不可变来源文件的大小和 SHA-256，并重新生成最终面板、估计结果、图形、Notebook 与报告。三个核心 Parquet 与审计前逐字节一致；完整审计见 [`../docs/task11_reproducibility_audit.md`](../docs/task11_reproducibility_audit.md)。
