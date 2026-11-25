/* 前端渲染：纯静态 JSON 驱动，无构建步骤。全部数字都带出处（证据链）。 */
(function () {
  "use strict";

  /* ================= i18n ================= */
  const I18N = {
    zh: {
      "site.title": "德州供应商监测",
      "site.subtitle": "应急预案响应 · 供应商限产与交付影响跟踪",
      "site.short": "德州监测",
      "toc.now": "概览",
      "toc.trend": "趋势",
      "toc.impact": "供应影响",
      "toc.basis": "数据依据",
      "sec.now": "概览",
      "sec.now.desc": "当前生效公告、受影响供应商，以及空气质量与扩散条件",
      "sec.trend.desc": "污染物浓度变化，以及同类应急响应的历史时长",
      "sec.impact.desc": "受影响工序、减产比例、影响窗口与地理位置",
      "sec.basis.desc": "数据出处、处置建议与公告记录",
      "status.updated": "今日已更新",
      "status.unchanged": "公告未更新 · 沿用旧分析",
      "status.checked": "巡检于",
      "status.lastUpdate": "数据更新于",
      "hero.published": "发布",
      "hero.effective": "生效",
      "hero.source": "查看公告原文",
      "hero.predEnd": "预计解除",
      "hero.median": "历史中位",
      "hero.elapsed": "已持续 {n} 天",
      "hero.days": "天",
      "hero.bjEst": "北京关系 {date}",
      "stale.sameDay": "今日公告未变化，沿用 {time} 生成的分析结果",
      "stale.other": "今日未抓取到新公告，以下内容沿用 {date} 的分析结果（生成于 {time}）",
      "stale.unreachable": "今日未能访问德州市生态环境局网站，以下内容沿用 {date} 的分析结果",
      "card.summary": "研判摘要",
      "card.air": "空气质量与扩散条件",
      "card.chart": "污染物浓度趋势",
      "card.history": "同类响应时长与预计解除",
      "card.map": "地理位置与监测站",
      "card.suppliers": "受影响供应商明细",
      "card.evidence": "数据出处",
      "card.threshold": "预警阈值参考",
      "realert.title": "近期复警概率",
      "realert.horizon": "未来 72 小时",
      "realert.note": "由未来 72 小时污染与气象预报，结合历史发文阈值估算，非官方预测",
      "realert.level.low": "低",
      "realert.level.moderate": "中等",
      "realert.level.elevated": "偏高",
      "realert.level.high": "高",
      "realert.peak": "污染峰值 AQI {v}（阈值 {line}）",
      "realert.persist": "PM2.5 超 75 共 {v} 小时",
      "realert.calm": "静风 {v} 小时（{share}%）",
      "realert.dry": "累计降水 {v} mm",
      "tag.threshold": "9 个网格点 · 近 4 年",
      "thr.status.safe": "安全区间",
      "thr.status.watch": "临近警戒",
      "thr.status.trigger": "已达到历史警戒线",
      "thr.status.unknown": "数据不足",
      "thr.sentence": "今日 9 个网格点中有 <b>{cur}</b> 个日均 AQI≥{theta}；警戒线为 <b>{thr}</b> 个，{dist}。",
      "thr.distAway": "还差 {gap} 个",
      "thr.distOver": "已超出 {gap} 个",
      "thr.distNone": "阈值样本不足",
      "thr.typicalNote": "Ⅱ级发文当天常见水平：{typ} 个点",
      "thr.legendSafe": "安全 0–{a}",
      "thr.legendWatch": "临近 {b}–{c}",
      "thr.legendTyp": "历史发文常见 ≥{d}",
      "thr.thrLabel": "警戒线 {thr}",
      "thr.current": "超标网格点数（日均 AQI≥{theta}）",
      "thr.rule": "警戒线（F1 最优）",
      "thr.typical": "Ⅱ级发文日中位",
      "thr.recall": "召回 / 精确",
      "thr.samples": "正样本 / 历史天数",
      "thr.city": "城市 3 日 AQI（当前 / 阈值）",
      "thr.cityState": "按城市 AQI 判定",
      "thr.forecast": "未来 48h 预报峰值",
      "thr.stations": "实时监测站 ≥{theta}",
      "thr.window": "数据窗口",
      "thr.none": "历史数据不足，无法反推阈值",
      "hint.threshold": "阈值依据近 4 年德州市域 9 个网格点的日均 AQI 与历次发文日期反推；「超标」= 该点日均 AQI ≥150。达到警戒线仅表示进入关注区间，不构成发文预测（精确率见上），供提前准备参考。",
      "card.playbook": "处置建议",
      "card.timeline": "公告记录",
      "tag.meteo": "数据源 · Open-Meteo",
      "tag.history": "基于历次公告配对",
      "tag.list": "数据源 · 固定源减排清单",
      "tag.evidence": "官方原文 / 计算 / 推算",
      "tag.action": "建议执行",
      "tag.recent": "最近记录",
      "tag.rules": "规则引擎 · 本地计算",
      "tag.ai": "AI 模型 · {model}",
      "tag.waqi": "WAQI · 浓度按 HJ633 折算",
      "hint.chart": "左轴 μg/m³（PM2.5 / PM10 / O₃ / NO₂ / SO₂ / 沙尘），右轴 mg/m³（CO）。图例可逐项开关。",
      "hint.history": "柱高 = 该次响应从启动到终止的天数；虚线为历史中位。本次预测按「已持续天数 + 剩余中位」随巡检重算，仍属推算，非官方公布。",
      "hint.map": "底图 {tiles}（开源、免 Key）· 大圆点=在监控供应商，小圆点=WAQI 监测站（颜色=AQI），橙色虚线=德州市中心。",
      "map.failed": "底图瓦片加载失败（网络受限），标记与数据仍可查看",
      "map.retry": "重试",
      "legend.stop": "全部停产",
      "legend.heavy": "大幅限产",
      "legend.partial": "部分限产",
      "legend.none": "不受影响",
      "legend.stations": "站点 AQI",
      "tag.map": "按 AQI 着色",
      "legend.zones": "污染区（按站点 AQI 示意）",
      "legend.supplier": "供应商",
      "legend.station": "监测站 (WAQI)",
      "kpi.suppliers": "监测供应商",
      "kpi.suppliers.sub": "来自减排清单匹配",
      "kpi.affected": "受影响供应商",
      "kpi.affected.sub": "存在强制限产/停产",
      "kpi.affected.subStop": "其中 {n} 家全部停产",
      "kpi.affected.subNone": "当前无强制限产",
      "kpi.reduction": "最大减产比例",
      "kpi.reduction.sub": "取清单「管控方式」加权",
      "kpi.reduction.subNone": "无强制限产",
      "kpi.duration": "预计影响时长",
      "kpi.duration.sub": "按历史中位 {median} 天修正",
      "kpi.duration.subElapsed": "已持续 {elapsed} 天，按更长样本顺延",
      "kpi.duration.subOverdue": "已超过历史最长 {max} 天",
      "kpi.duration.subEnded": "响应已终止",
      "kpi.duration.subNone": "无需计算",
      "kpi.end": "预计解除",
      "kpi.end.sub": "历史中位 {median} 天 · {n} 个样本",
      "kpi.end.subElapsed": "已持续 {elapsed} 天 · {n} 个样本",
      "kpi.end.subOverdue": "等待官方终止公告",
      "kpi.end.subNone": "样本不足",
      "kpi.end.subEnded": "响应已终止",
      "kpi.end.subBeijing": "中位 {median} 天 · 北京关系 {date}",
      "kpi.end.subBeijingElapsed": "已持续 {elapsed} 天 · 北京关系 {date}",
      "kpi.aqi": "空气质量指数",
      "kpi.pm25": "PM2.5",
      "unit.day": "天",
      "unit.samples": "个样本",
      "air.station": "监测站：{name}",
      "air.dominant": "首要污染物",
      "air.temp": "气温",
      "air.humidity": "湿度",
      "air.windDir": "风向",
      "air.rain": "降水",
      "air.dispersion": "扩散条件：{level} · {note}",
      "air.dispersionNone": "扩散条件：暂无数据",
      "region.title": "区域联动 · 京津冀及周边",
      "region.summary": "{n} 城中位 AQI {median}，{hot} 城达中度污染以上；北京 {bj}（{bjl}）；{trend}",
      "region.trend.improving": "未来 24h 转好",
      "region.trend.flat": "未来 24h 大致持平",
      "region.trend.worsening": "未来 24h 转差",
      "region.level.好": "区域转好",
      "region.level.一般": "区域分化",
      "region.level.差": "区域仍在大范围污染",
      "region.hint": "德州的应急响应按京津冀及周边区域联防联控启动/解除。本地风速只说明污染物能不能吹走；区域（尤其北京）还没转好时，德州很少单独解除。数据：WAQI 城市实况 + Open-Meteo 区域 PM2.5 预报。修正幅度见「历史响应规律」。",
      "region.forecast": "未来 24h PM2.5 {v} μg/m³",
      "card.beijing": "北京官方动态",
      "bj.tag": "北京市应急管理局 · 预警信息",
      "bj.state.in_force": "响应中",
      "bj.state.lifted": "已解除",
      "bj.state.none": "无记录",
      "bj.window": "{start} 启动 → {end} 解除 · 持续 {days} 天",
      "bj.windowOpen": "{start} 启动 · 已持续 {days} 天",
      "bj.signal.beijing_lifted": "同一轮区域污染过程：北京 {start} 启动 → {end} 解除（持续 {days} 天），德州 {dz} 启动至今未终止，已滞后 {lag} 天",
      "bj.signal.beijing_in_force": "同一轮区域污染过程：北京 {start} 启动的{level}仍在响应（第 {elapsed} 天），德州大概率不会先解除",
      "bj.signal.both_closed": "北京与德州均已解除",
      "bj.signal.dezhou_closed": "德州已终止本次响应",
      "bj.signal.none": "暂未找到与本次响应时间重叠的北京预警",
      "bj.relation": "历史 {n} 次可比过程：德州终止比北京解除晚 {end} 天（中位，{nEnd} 次），启动日相差 {start} 天",
      "bj.relationEmpty": "暂无足够的历史配对（需两地启动日相差 ≤3 天）",
      "bj.estimate": "按北京关系推算 {date}（滞后中位 {lag} 天 / {n} 次）",
      "bj.estimateOverdue": "按北京关系应已到期：推算 {date}（滞后中位 {lag} 天 / {n} 次）",
      "bj.pairs": "历史配对明细（{n} 次）",
      "bj.pairDz": "德州 {start} → {end}",
      "bj.pairLag": "终止较北京 {v} 天",
      "bj.kind.start": "发布",
      "bj.kind.lift": "解除",
      "bj.overlapTag": "与德州重叠",
      "bj.feedEmpty": "北京栏目暂无空气重污染预警记录",
      "bj.unavailable": "北京官方动态暂不可用（本次未取到栏目数据）",
      "bj.column": "查看北京预警信息栏目 →",
      "hint.beijing": "北京「预警信息」栏目把每一次空气重污染预警的发布/启动/解除挂在同一列表，标题写的是实际生效时刻。德州按京津冀联防联控启动/解除，因此把北京的公告与本次响应做时间重叠比对：北京先解除时德州解除临近，北京仍在响应时德州很少单独解除。",
      "th.supplier": "供应商",
      "th.performance": "绩效等级",
      "th.impact": "影响程度",
      "th.lines": "受影响产线 / 工序",
      "th.reduction": "预计减产",
      "th.duration": "持续",
      "th.window": "影响窗口",
      "th.cost": "企业日成本",
      "th.field": "字段",
      "th.value": "数值",
      "th.basis": "依据",
      "th.raw": "原文 / 计算式",
      "th.tier": "类型",
      "tier.official": "官方原文",
      "tier.derived": "算术合成",
      "tier.inferred": "推算",
      "impact.stop": "全部停产",
      "impact.heavy": "限产 {pct}%",
      "impact.partial": "限产 {pct}%",
      "impact.none": "不受影响",
      "line.text": "{total} 条生产线中 {stopped} 条受限",
      "line.textNoTotal": "{n} 道工序受限",
      "line.none": "无生产工序受限",
      "mobility": "厂内运输：{way}",
      "row.ended": "已于 {time} 解除",
      "supplier.empty": "暂无匹配到的供应商，请在 config/suppliers.yaml 中补充名称或 alias。",      "supplier.notFound": "本次预警级别未触发该企业的强制减排措施。",
      "supplier.note": "口径说明：工序名称、产线数量、管控方式与应急成本取自清单原文；减产比例、受限产线合计与日成本按清单数值计算；持续时长为历史推定。",
      "evidence.title": "{name} · 证据链",
      "evidence.intro": "共 {n} 条，其中官方原文 {o} 条。",
      "hist.samples": "历史样本",
      "hist.median": "中位时长",
      "hist.p75": "P75 时长",
      "hist.predicted": "本次预测",
      "hist.elapsed": "已持续",
      "hist.end": "预计解除",
      "hist.none": "样本不足",
      "hist.noneNote": "暂无可配对的启动/终止公告",
      "hist.thisTime": "本次",
      "hist.medianLine": "中位 {n} 天",
      "hist.bjEst": "北京关系推算",
      "hist.bjLag": "滞后中位 / 样本",
      "hist.bjLine": "北京关系 {n} 天",
      "hist.bjNote": "北京→德州历史关系：{n} 次可比过程，其中 {nEnd} 次两端齐全，德州终止日比北京解除日中位晚 {end} 天；按当前北京预警推算德州解除 {date}（绿色点线）。",
      "counter.none": "暂无动作，等待新公告",
      "timeline.empty": "暂无历史记录",
      "footer.disclaimer": "数据来源：德州市生态环境局公告与附件、《重污染天气应急减排清单》、北京市应急管理局预警信息、WAQI、Open-Meteo、OpenStreetMap。标注为「推算」的内容为模型估算，非官方公布；限产措施以公告与清单原文为准。",
      "src.notice": "公告原文",
      "src.list": "栏目列表",
      "src.listv": "德州市生态环境局 · 重污染天气信息发布",
      "src.beijing": "北京官方动态",
      "src.beijingv": "{state} · 空气重污染预警 {n} 条",
      "src.emission": "减排清单",
      "src.emissionv": "{file} › {sheet}（{dir}）",
      "src.aqi": "空气质量",
      "src.aqiv": "{provider} · 站点 {station} · {time}",
      "src.meteo": "污染/气象预报",
      "src.meteov": "{provider} · {vars} · 抓取于 {time}",
      "src.history": "历史时长统计",
      "src.historyv": "{n} 个样本，由栏目启停公告配对得出",
      "src.map": "地图",
      "src.mapv": "底图 {tiles} · 监测站 {stations}",
      "notice.startup": "启动响应",
      "notice.terminate": "终止响应",
      "notice.adjust": "调整响应",
      "notice.other": "通知",
      "color.红色预警": "红色预警",
      "color.橙色预警": "橙色预警",
      "color.黄色预警": "黄色预警",
      "color.蓝色预警": "蓝色预警",
      "disp.好": "好",
      "disp.一般": "一般",
      "disp.差": "差",
      "dispNote.好": "风速 >4m/s，扩散条件转好，应急响应可能提前解除",
      "dispNote.一般": "风速 2-4m/s，扩散条件中等",
      "dispNote.差": "风速 <2m/s，污染物易累积，预警大概率维持或升级",
      "evidence.field.绩效等级": "绩效等级",
      "evidence.field.本次预警": "本次预警",
      "evidence.field.受限产线合计": "受限产线合计",
      "evidence.field.预计减产": "预计减产",
      "evidence.field.企业日应急成本": "企业日应急成本",
      "evidence.field.影响时长": "影响时长",
      "evidence.field.process": "工序与措施",
      "unknown": "—"
    },
    en: {
      "site.title": "Dezhou Supplier Monitor",
      "site.subtitle": "Emergency response · supplier output cuts & delivery impact",
      "site.short": "Dezhou Monitor",
      "toc.now": "Overview",
      "toc.trend": "Trends",
      "toc.impact": "Supply impact",
      "toc.basis": "Sources",
      "sec.now": "Overview",
      "sec.now.desc": "The notice in force, affected suppliers, air quality and dispersion",
      "sec.trend.desc": "Pollutant concentrations, and how long comparable episodes usually last",
      "sec.impact.desc": "Restricted processes, output cuts, impact window and locations",
      "sec.basis.desc": "Sources for every figure, recommended actions and the notice log",
      "status.updated": "Updated today",
      "status.unchanged": "No new notice · previous analysis",
      "status.checked": "Checked",
      "status.lastUpdate": "Updated",
      "hero.published": "Published",
      "hero.effective": "Effective",
      "hero.source": "Read the notice",
      "hero.predEnd": "Expected end",
      "hero.median": "historical median",
      "hero.elapsed": "day {n} in",
      "hero.days": "days",
      "hero.bjEst": "Beijing-implied {date}",
      "stale.sameDay": "No change in today's notice — reusing the analysis generated at {time}",
      "stale.other": "No new notice today — showing the analysis from {date} (generated {time})",
      "stale.unreachable": "Could not reach the source site today — showing the analysis from {date}",
      "card.summary": "Assessment",
      "card.air": "Air quality & dispersion",
      "card.chart": "Pollutant concentration trends",
      "card.history": "Episode length & expected end",
      "card.map": "Locations & stations",
      "card.suppliers": "Affected suppliers",
      "card.evidence": "Data sources",
      "card.threshold": "Alert threshold reference",
      "realert.title": "Re-alert probability",
      "realert.horizon": "next 72 hours",
      "realert.note": "Estimated from the 72-hour pollution and weather forecast combined with the historical notice threshold — not an official forecast",
      "realert.level.low": "Low",
      "realert.level.moderate": "Moderate",
      "realert.level.elevated": "Elevated",
      "realert.level.high": "High",
      "realert.peak": "Peak AQI {v} (threshold {line})",
      "realert.persist": "PM2.5 above 75 for {v} h",
      "realert.calm": "Calm wind {v} h ({share}%)",
      "realert.dry": "Rainfall {v} mm",
      "tag.threshold": "9 grid points · ~4 years",
      "thr.status.safe": "Safe range",
      "thr.status.watch": "Approaching threshold",
      "thr.status.trigger": "At historical alert level",
      "thr.status.unknown": "Not enough data",
      "thr.sentence": "<b>{cur}</b> of 9 grid points exceed daily AQI {theta} today; the alert line is <b>{thr}</b> — {dist}.",
      "thr.distAway": "{gap} to go",
      "thr.distOver": "already {gap} over",
      "thr.distNone": "not enough samples",
      "thr.typicalNote": "Typical on level-II notice days: {typ} points",
      "thr.legendSafe": "Safe 0–{a}",
      "thr.legendWatch": "Watch {b}–{c}",
      "thr.legendTyp": "Notice days usually ≥{d}",
      "thr.thrLabel": "alert line {thr}",
      "thr.current": "Grid points above AQI {theta} (today)",
      "thr.rule": "Alert line (best F1)",
      "thr.typical": "Median on level-II notice days",
      "thr.recall": "Recall / precision",
      "thr.samples": "Positives / history days",
      "thr.city": "City 3-day AQI (now / threshold)",
      "thr.cityState": "City AQI status",
      "thr.forecast": "48h forecast peak",
      "thr.stations": "Live stations ≥{theta}",
      "thr.window": "Data window",
      "thr.none": "Not enough history to derive a threshold",
      "hint.threshold": "Thresholds are derived from daily mean AQI at 9 grid points across Dezhou over ~4 years, matched against the dates of past notices. A \"hot\" point means daily mean AQI ≥150. Crossing the line only means a watch state — it does not guarantee a notice (see precision above).",
      "card.playbook": "Recommended actions",
      "card.timeline": "Notice log",
      "tag.meteo": "Source · Open-Meteo",
      "tag.history": "paired from past notices",
      "tag.list": "Source · fixed-source list",
      "tag.evidence": "official / calculated / inferred",
      "tag.action": "Suggested",
      "tag.recent": "recent",
      "tag.rules": "Rules engine · local",
      "tag.ai": "AI 模型 · {model}",
      "tag.waqi": "WAQI · HJ633 converted",
      "hint.chart": "Left axis μg/m³ (PM2.5 / PM10 / O₃ / NO₂ / SO₂ / dust), right axis mg/m³ (CO). Toggle series in the legend.",
      "hint.history": "Bar = days from start to termination notice; dashed line = historical median. This episode's estimate is recalculated each run from elapsed days plus the remaining median — still an estimate, not an official figure.",
      "hint.map": "Base map {tiles} (open, no key) · large dot = monitored supplier, small dots = WAQI stations (colour = AQI), dashed ring = Dezhou centre.",
      "map.failed": "Basemap tiles failed to load (network restricted); markers and data still work",
      "map.retry": "Retry",
      "legend.stop": "Full shutdown",
      "legend.heavy": "Major cut",
      "legend.partial": "Partial cut",
      "legend.none": "Not affected",
      "legend.stations": "Station AQI",
      "tag.map": "Coloured by AQI",
      "legend.zones": "Pollution zones (indicative)",
      "legend.supplier": "Suppliers",
      "legend.station": "Stations (WAQI)",
      "kpi.suppliers": "Suppliers",
      "kpi.suppliers.sub": "monitored in list",
      "kpi.affected": "Affected",
      "kpi.affected.sub": "mandatory cuts",
      "kpi.affected.subStop": "{n} fully shut down",
      "kpi.affected.subNone": "no mandatory cuts now",
      "kpi.reduction": "Largest cut",
      "kpi.reduction.sub": "weighted from listed control type",
      "kpi.reduction.subNone": "no mandatory cut",
      "kpi.duration": "Duration",
      "kpi.duration.sub": "adjusted from {median}-day median",
      "kpi.duration.subElapsed": "day {elapsed}, from longer episodes",
      "kpi.duration.subOverdue": "beyond the {max}-day record",
      "kpi.duration.subEnded": "response ended",
      "kpi.duration.subNone": "not applicable",
      "kpi.end": "Expected end",
      "kpi.end.sub": "median {median} days · {n} samples",
      "kpi.end.subElapsed": "day {elapsed} · {n} samples",
      "kpi.end.subOverdue": "awaiting the official notice",
      "kpi.end.subNone": "not enough samples",
      "kpi.end.subEnded": "response ended",
      "kpi.end.subBeijing": "median {median} d · Beijing-implied {date}",
      "kpi.end.subBeijingElapsed": "day {elapsed} · Beijing-implied {date}",
      "kpi.aqi": "AQI",
      "kpi.pm25": "PM2.5",
      "unit.day": "days",
      "unit.samples": "samples",
      "air.station": "Station: {name}",
      "air.dominant": "Main pollutant",
      "air.temp": "Temp",
      "air.humidity": "Humidity",
      "air.windDir": "Wind dir",
      "air.rain": "Rain",
      "air.dispersion": "Dispersion: {level} · {note}",
      "air.dispersionNone": "Dispersion: no data",
      "region.title": "Regional watch · Beijing–Tianjin–Hebei",
      "region.summary": "Median AQI {median} across {n} cities; {hot} at moderate pollution or worse; Beijing {bj} ({bjl}); {trend}",
      "region.trend.improving": "improving over 24h",
      "region.trend.flat": "flat over 24h",
      "region.trend.worsening": "worsening over 24h",
      "region.level.好": "region clearing",
      "region.level.一般": "region mixed",
      "region.level.差": "region still polluted",
      "region.hint": "Dezhou starts and lifts its response under joint Beijing–Tianjin–Hebei regional control. Local wind only tells you whether pollutants can disperse; while the region (Beijing first) has not cleared, Dezhou rarely lifts alone. Data: WAQI city feeds + Open-Meteo regional PM2.5 forecast. The duration adjustment is shown under the episode-length card.",
      "region.forecast": "24h PM2.5 forecast {v} μg/m³",
      "card.beijing": "Beijing official watch",
      "bj.tag": "Beijing EMA · alerts column",
      "bj.state.in_force": "in force",
      "bj.state.lifted": "lifted",
      "bj.state.none": "no record",
      "bj.window": "{start} → {end} · {days} days",
      "bj.windowOpen": "since {start} · day {days}",
      "bj.signal.beijing_lifted": "Same regional episode: Beijing ran {start} → {end} ({days} days); Dezhou has run since {dz} and has not terminated — {lag} day(s) behind",
      "bj.signal.beijing_in_force": "Same regional episode: Beijing's {level} has been in force since {start} (day {elapsed}); Dezhou is unlikely to lift first",
      "bj.signal.both_closed": "Both Beijing and Dezhou have lifted",
      "bj.signal.dezhou_closed": "Dezhou has terminated the response",
      "bj.signal.none": "No Beijing alert overlaps this response in time",
      "bj.relation": "Across {n} matched episodes Dezhou ended a median of {end} day(s) after Beijing ({nEnd} with both ends); start dates differ by {start} day(s)",
      "bj.relationEmpty": "Not enough historical pairs yet (starts must be within 3 days)",
      "bj.estimate": "Beijing relationship implies {date} (median lag {lag} day(s), {n} episodes)",
      "bj.estimateOverdue": "Beijing relationship says it should already have ended: {date} (median lag {lag} day(s), {n} episodes)",
      "bj.pairs": "Matched episodes ({n})",
      "bj.pairDz": "Dezhou {start} → {end}",
      "bj.pairLag": "ended {v} day(s) after Beijing",
      "bj.kind.start": "start",
      "bj.kind.lift": "lift",
      "bj.overlapTag": "overlaps Dezhou",
      "bj.feedEmpty": "No heavy-pollution alerts in the Beijing column",
      "bj.unavailable": "Beijing official watch is unavailable (column not fetched this run)",
      "bj.column": "Open the Beijing alerts column →",
      "hint.beijing": "The Beijing alerts column lists every heavy-pollution warning's issue, start and lift, with the actual effective time in the headline. Dezhou starts and lifts its response under joint Beijing–Tianjin–Hebei control, so Beijing's notices are matched against this episode: when Beijing lifts first, Dezhou's lift is close; while Beijing stays in force, Dezhou rarely lifts alone.",
      "th.supplier": "Supplier",
      "th.performance": "Perf. grade",
      "th.impact": "Impact",
      "th.lines": "Affected lines / processes",
      "th.reduction": "Output cut",
      "th.duration": "Duration",
      "th.window": "Window",
      "th.cost": "Daily cost",
      "th.field": "Field",
      "th.value": "Value",
      "th.basis": "Basis",
      "th.raw": "Source / formula",
      "th.tier": "Type",
      "tier.official": "official",
      "tier.derived": "derived",
      "tier.inferred": "inferred",
      "impact.stop": "Full shutdown",
      "impact.heavy": "Cut {pct}%",
      "impact.partial": "Cut {pct}%",
      "impact.none": "Not affected",
      "line.text": "{stopped} of {total} production lines restricted",
      "line.textNoTotal": "{n} processes restricted",
      "line.none": "no production process restricted",
      "mobility": "On-site transport: {way}",
      "row.ended": "ended {time}",
      "supplier.empty": "No supplier matched. Add the company name or alias in config/suppliers.yaml.",
      "supplier.notFound": "This alert level does not trigger mandatory measures for the company.",
      "supplier.note": "Note: process names, line counts, control type and emergency cost come from the official list; output cut, restricted-line total and daily cost are arithmetic over those cells; duration is estimated from history + weather.",
      "evidence.title": "{name} · evidence",
      "evidence.intro": "{n} items, {o} of them official source text.",
      "hist.samples": "Samples",
      "hist.median": "Median",
      "hist.p75": "P75",
      "hist.predicted": "This episode",
      "hist.elapsed": "Elapsed",
      "hist.end": "Expected end",
      "hist.none": "Not enough",
      "hist.noneNote": "no start/terminate pairs found",
      "hist.thisTime": "now",
      "hist.medianLine": "median {n}d",
      "hist.bjEst": "Beijing-implied",
      "hist.bjLag": "Median lag / samples",
      "hist.bjLine": "Beijing-implied {n}d",
      "hist.bjNote": "Beijing → Dezhou: across {n} matched episodes ({nEnd} with both ends) Dezhou ended a median of {end} day(s) after Beijing; the current Beijing alert implies {date} (green dotted line).",
      "counter.none": "No action yet — waiting for a new notice",
      "timeline.empty": "No records yet",
      "footer.disclaimer": "Sources: Dezhou EPB notices and attachments, the heavy-pollution reduction list, Beijing EMA alerts, WAQI, Open-Meteo, OpenStreetMap. Items marked \"inferred\" are model estimates, not official figures; the notice and list text always prevail.",
      "src.notice": "Notice",
      "src.list": "Notice column",
      "src.listv": "Dezhou EPB · heavy-pollution notices",
      "src.beijing": "Beijing official watch",
      "src.beijingv": "{state} · {n} heavy-pollution alerts",
      "src.emission": "Emission list",
      "src.emissionv": "{file} › {sheet} ({dir})",
      "src.aqi": "Air quality",
      "src.aqiv": "{provider} · station {station} · {time}",
      "src.meteo": "Pollution / weather",
      "src.meteov": "{provider} · {vars} · fetched {time}",
      "src.history": "Episode statistics",
      "src.historyv": "{n} samples paired from start/terminate notices",
      "src.map": "Map",
      "src.mapv": "tiles {tiles} · stations {stations}",
      "notice.startup": "Response started",
      "notice.terminate": "Response terminated",
      "notice.adjust": "Response adjusted",
      "notice.other": "Notice",
      "color.红色预警": "Red alert",
      "color.橙色预警": "Orange alert",
      "color.黄色预警": "Yellow alert",
      "color.蓝色预警": "Blue alert",
      "disp.好": "good",
      "disp.一般": "fair",
      "disp.差": "poor",
      "dispNote.好": "wind >4 m/s — pollutants disperse, the response may end early",
      "dispNote.一般": "wind 2–4 m/s — moderate dispersion",
      "dispNote.差": "wind <2 m/s — pollutants accumulate, the alert is likely to persist or escalate",
      "evidence.field.绩效等级": "Performance grade",
      "evidence.field.本次预警": "Alert level",
      "evidence.field.受限产线合计": "Restricted lines",
      "evidence.field.预计减产": "Output cut",
      "evidence.field.企业日应急成本": "Daily emergency cost",
      "evidence.field.影响时长": "Duration",
      "evidence.field.process": "Process & measure",
      "unknown": "—"
    }
  };

  const FIELD_EN = {
    "绩效等级": "Performance grade",
    "本次预警": "Alert level",
    "受限产线合计": "Restricted lines (total)",
    "预计减产": "Output cut",
    "企业日应急成本": "Daily emergency cost",
    "影响时长": "Duration"
  };

  let LANG = localStorage.getItem("sw-lang") || "en";
  let DATA = null;
  const refs = { air: null, hist: null, map: null, layers: [], motion: false };

  const $ = (id) => document.getElementById(id);
  const esc = (s) =>
    String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  const t = (key, vars) => {
    let s = (I18N[LANG] && I18N[LANG][key]) || I18N.zh[key] || key;
    if (vars) Object.keys(vars).forEach((k) => { s = s.replace(new RegExp("\\{" + k + "\\}", "g"), vars[k]); });
    return s;
  };
  const isEn = () => LANG === "en";

  const fmtTime = (iso) => {
    if (!iso) return "—";
    const d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso).slice(0, 16).replace("T", " ");
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
  };
  const fmtDay = (iso) => (iso ? String(iso).slice(0, 10) : "—");
  const num = (v, d = 0) => (v == null || isNaN(Number(v)) ? "—" : Number(v).toFixed(d));

  const kindLabel = (n) => t("notice." + (n.kind || "other"));
  const colorLabel = (c) => (c ? t("color." + c) : "");
  const dispLabel = (l) => (l ? t("disp." + l) : "—");
  const impactLabel = (s) =>
    t("impact." + s.impact, { pct: s.reduction_pct }) || s.impact_label;

  // 分析正文：英文环境优先用后端给的英文版，缺失则回退中文原文
  function ana(data) {
    const a = (data && data.analysis) || {};
    if (isEn() && a.i18n && a.i18n.en) return Object.assign({}, a, a.i18n.en);
    return a;
  }
  const AQI_EN = { "优": "Good", "良": "Moderate", "轻度污染": "Light pollution",
                   "中度污染": "Heavy pollution", "重度污染": "Severe pollution",
                   "严重污染": "Hazardous" };
  const aqiLevel = (v) => (isEn() ? AQI_EN[v] || v : v);
  // AQI 取色：地图站点、区域联动芯片共用一套阈值
  const aqiColor = (v) =>
    v == null ? "#98a2b3" : v <= 50 ? "#12b76a" : v <= 100 ? "#eab308" :
    v <= 150 ? "#f79009" : v <= 200 ? "#ef4444" : v <= 300 ? "#a855f7" : "#7f1d1d";

  const WAY_EN = { "停产": "shutdown", "限产50%": "50% cut", "限产30%": "30% cut",
                   "限产20%": "20% cut", "限产10%": "10% cut",
                   "自主减排": "voluntary cut", "移动源管控": "mobile-source control",
                   "正常生产": "normal" };
  function wayLabel(w) {
    if (!isEn()) return w;
    const k = String(w || "");
    if (WAY_EN[k]) return WAY_EN[k];
    const m = k.match(/限产\s*(\d+)%/);
    return m ? `${m[1]}% cut` : k;
  }

  /* ================= markdown ================= */
  function md(text) {
    if (!text) return "";
    const lines = String(text).replace(/\r/g, "").split("\n");
    let html = "", inList = false, inTable = false;
    const closeList = () => { if (inList) { html += "</ul>"; inList = false; } };
    const closeTable = () => { if (inTable) { html += "</table>"; inTable = false; } };
    const inline = (s) => esc(s)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");

    lines.forEach((raw) => {
      const line = raw.trim();
      if (!line) { closeList(); closeTable(); return; }
      if (/^\|.*\|$/.test(line)) {
        closeList();
        const cells = line.split("|").slice(1, -1).map((c) => c.trim());
        if (/^[-: ]+$/.test(cells.join(""))) { if (!inTable) { html += "<table>"; inTable = true; } return; }
        if (!inTable) { html += "<table>"; inTable = true; }
        const tag = html.endsWith("<table>") ? "th" : "td";
        html += "<tr>" + cells.map((c) => `<${tag}>${inline(c)}</${tag}>`).join("") + "</tr>";
        return;
      }
      closeTable();
      const h = line.match(/^(#{2,4})\s+(.*)$/);
      if (h) { closeList(); html += `<h3>${inline(h[2])}</h3>`; return; }
      const li = line.match(/^[-*]\s+(.*)$/);
      if (li) {
        if (!inList) { html += "<ul>"; inList = true; }
        html += `<li>${inline(li[1])}</li>`;
        return;
      }
      closeList();
      html += `<p>${inline(line)}</p>`;
    });
    closeList(); closeTable();
    return html;
  }

  /* ================= render ================= */
  function renderHero(data) {
    const n = data.notice || {};
    const meta = data.meta || {};
    const pred = data.prediction || {};
    const badge = $("levelBadge");
    const terminated = n.kind === "terminate";
    // 徽标里只放颜色词，避免 "Orange alert" 在窄方块里换行
    const colorShort = (colorLabel(n.warning_color) || "")
      .replace(/\s*alert$/i, "")
      .replace(/预警$/, "") || (isEn() ? "level" : "级别");
    badge.className = "level-badge" + (terminated ? " clear" : "");
    badge.innerHTML = terminated
      ? `<span>${isEn() ? "End" : "解除"}</span><small>${esc(colorShort)}</small>`
      : `<span>${esc(n.warning_level ? n.warning_level + (isEn() ? "" : "级") : "—")}</span><small>${esc(colorShort)}</small>`;

    $("noticeKind").textContent = kindLabel(n);
    const titleEl = $("noticeTitle");
    titleEl.textContent = isEn() && n.title_en ? n.title_en : (n.title || "—");
    titleEl.title = n.title || "";

    const meta2 = [
      `${t("hero.published")} ${n.publish_date || "—"}`,
      `${t("hero.effective")} ${fmtTime(n.effective_time)}`,
    ];
    let html = meta2.map((x, i) => (i ? '<span class="sep"></span>' : "") + `<span>${esc(x)}</span>`).join("");
    const predNote = pred.conditional && pred.elapsed_days != null
      ? t("hero.elapsed", { n: pred.elapsed_days })
      : `${t("hero.median")} ${pred.median_days} ${t("hero.days")}`;
    const bjEst = pred.beijing_estimate || {};
    const bjDate = bjEst.predicted_end && bjEst.sample_size
      ? String(bjEst.predicted_end).slice(5, 10) : "";
    if (pred.available && pred.applicable !== false && pred.predicted_end) {
      html += `<span class="sep"></span><span class="pred">${t("hero.predEnd")} ${esc(fmtDay(pred.predicted_end))}（${esc(predNote)}${bjDate ? ` · ${esc(t("hero.bjEst", { date: bjDate }))}` : ""}）</span>`;
    } else if (pred.available && pred.applicable !== false && pred.overdue) {
      // 已超过历史最长样本：不外推日期，只说明已持续多久
      html += `<span class="sep"></span><span class="pred">${t("hero.predEnd")} —（${esc(t("hero.elapsed", { n: pred.elapsed_days }))}）</span>`;
    }
    html += `<span class="sep"></span><a href="${esc(n.url || meta.source_url || "#")}" target="_blank" rel="noopener">${t("hero.source")}</a>`;
    html += `<span class="meta-note">${esc(t("status.lastUpdate"))} ${esc(fmtTime(meta.generated_at))}</span>`;
    $("heroMeta").innerHTML = html;
    const railMeta = $("railMeta");
    if (railMeta) {
      railMeta.textContent = `${t("status.lastUpdate")} ${fmtTime(meta.generated_at)}`;
    }

    $("headline").textContent = ana(data).headline || "—";

    const stale = $("staleNote");
    if (meta.status === "unreachable") {
      stale.hidden = false;
      stale.innerHTML = esc(t("stale.unreachable", { date: meta.analysis_date || "—" }));
    } else if (meta.status === "unchanged") {
      const today = String(meta.generated_at || "").slice(0, 10);
      const sameDay = meta.analysis_date === today;
      stale.hidden = false;
      stale.innerHTML = sameDay
        ? esc(t("stale.sameDay", { time: fmtTime(meta.analysis_generated_at).slice(-5) }))
        : esc(t("stale.other", { date: meta.analysis_date, time: fmtTime(meta.analysis_generated_at) }));
    } else {
      stale.hidden = true;
    }

    // 头部不再放状态胶囊：更新时间并入公告元信息（meta-note）
    const engine = (data.analysis && data.analysis.engine) || "rules";
    $("engineTag").textContent = engine.indexOf("ai:") === 0
      ? t("tag.ai", { model: engine.slice(3) }) : t("tag.rules");
    $("engineTag").className = "tag " + (engine.indexOf("ai:") === 0 ? "accent" : "");
  }

  function renderKpis(data) {
    const meta = data.meta || {};
    const air = (data.air && data.air.current) || {};
    const pred = data.prediction || {};
    const terminated = (data.notice || {}).kind === "terminate";
    const bjEst = pred.beijing_estimate || {};
    const bjDate = bjEst.predicted_end && bjEst.sample_size
      ? String(bjEst.predicted_end).slice(5, 10) : "";
    const affectedN = meta.affected_count ?? 0;
    const items = [
      { icon: "building", label: t("kpi.suppliers"), value: meta.supplier_count ?? 0, sub: t("kpi.suppliers.sub") },
      {
        icon: "alert", label: t("kpi.affected"), value: affectedN,
        sub: affectedN
          ? (meta.stopped_count ? t("kpi.affected.subStop", { n: meta.stopped_count }) : t("kpi.affected.sub"))
          : t("kpi.affected.subNone"),
        cls: affectedN ? "warn" : "",
      },
      {
        icon: "percent", label: t("kpi.reduction"),
        value: affectedN ? (meta.max_reduction || 0) + "%" : "—",
        sub: affectedN ? t("kpi.reduction.sub") : t("kpi.reduction.subNone"),
        cls: affectedN && (meta.max_reduction || 0) >= 50 ? "danger" : "",
      },
      {
        icon: "clock", label: t("kpi.duration"),
        value: meta.duration_days != null ? meta.duration_days : "—",
        sub: terminated ? t("kpi.duration.subEnded")
          : pred.overdue ? t("kpi.duration.subOverdue", { max: (pred.range || [])[1] })
          : pred.conditional && pred.elapsed_days != null
            ? t("kpi.duration.subElapsed", { elapsed: pred.elapsed_days })
            : (pred.available ? t("kpi.duration.sub", { median: pred.median_days }) : t("kpi.duration.subNone")),
      },
      {
        icon: "calendar", label: t("kpi.end"),
        value: pred.available && pred.applicable !== false && pred.predicted_end ? fmtDay(pred.predicted_end).slice(5) : "—",
        sub: terminated ? t("kpi.end.subEnded")
          : pred.overdue ? t("kpi.end.subOverdue")
          : bjDate ? t(pred.conditional && pred.elapsed_days != null
              ? "kpi.end.subBeijingElapsed" : "kpi.end.subBeijing",
              { elapsed: pred.elapsed_days, median: pred.median_days, date: bjDate })
          : pred.conditional && pred.elapsed_days != null
            ? t("kpi.end.subElapsed", { elapsed: pred.elapsed_days, n: pred.sample_size })
            : (pred.available ? t("kpi.end.sub", { median: pred.median_days, n: pred.sample_size }) : t("kpi.end.subNone")),
      },
      { icon: "gauge", label: t("kpi.aqi"), value: air.aqi == null ? "—" : Math.round(air.aqi), sub: aqiLevel(air.level) || "—", cls: air.aqi > 150 ? "danger" : air.aqi > 100 ? "warn" : "" },
      { icon: "activity", label: t("kpi.pm25"), value: air.pm25 == null ? "—" : num(air.pm25, 0), sub: "μg/m³" },
    ];
    $("kpis").innerHTML = items.map((i) => `<div class="kpi ${i.cls || ""}">
        <div class="label"><svg class="i i-sm"><use href="#i-${i.icon}"></use></svg>${esc(i.label)}</div>
        <div class="value">${esc(i.value)}</div>
        <div class="sub">${esc(i.sub)}</div>
      </div>`).join("");
  }

  function renderAnalysis(data) {
    const a = ana(data);
    $("summaryMd").innerHTML = md(a.summary_md || a.headline || "—");
    const box = $("outlookBox");
    if (a.outlook) {
      box.hidden = false;
      box.innerHTML = `<b>${isEn() ? "Outlook: " : "走势判断："}</b>${esc(a.outlook)}`;
    } else {
      box.hidden = true;
    }
  }

  /* 近 48 小时 PM2.5 迷你走势（canvas，无第三方依赖） */
  function drawSpark(data) {
    const c = $("spark");
    if (!c) return;
    const rows = (data.air && data.air.hourly) || [];
    const vals = rows.map((r) => r.pm25).filter((v) => typeof v === "number");
    const dpr = window.devicePixelRatio || 1;
    const w = c.clientWidth || c.parentElement.clientWidth || 280;
    const h = 46;
    c.width = Math.round(w * dpr);
    c.height = Math.round(h * dpr);
    const ctx = c.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    if (vals.length < 2) return;

    const max = Math.max(...vals);
    const min = Math.min(...vals);
    const span = max - min || 1;
    const pts = vals.map((v, i) => [
      1 + (i / (vals.length - 1)) * (w - 2),
      h - 6 - ((v - min) / span) * (h - 14),
    ]);

    ctx.beginPath();
    pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
    ctx.strokeStyle = "#0057d8";
    ctx.lineWidth = 1.3;
    ctx.lineJoin = "round";
    ctx.stroke();

    ctx.lineTo(pts[pts.length - 1][0], h);
    ctx.lineTo(pts[0][0], h);
    ctx.closePath();
    const g = ctx.createLinearGradient(0, 0, 0, h);
    g.addColorStop(0, "rgba(0, 87, 216, 0.14)");
    g.addColorStop(1, "rgba(0, 87, 216, 0)");
    ctx.fillStyle = g;
    ctx.fill();
  }

  /* 区域联动：京津冀及周边城市 AQI（德州按区域联防联控启动/解除） */
  function renderRegion(region) {
    const el = $("regionBlock");
    if (!el) return;
    if (!region || !region.available) { el.innerHTML = ""; return; }
    const bj = region.beijing || {};
    const trend = (region.trend || {}).direction || "flat";
    const summary = t("region.summary", {
      n: region.city_count,
      median: region.median_aqi,
      hot: region.hot_count,
      bj: bj.aqi == null ? "—" : bj.aqi,
      bjl: aqiLevel(bj.level) || "—",
      trend: t("region.trend." + trend),
    });
    const chips = (region.cities || []).map((c) =>
      `<span class="region-chip" title="${esc(aqiLevel(c.level) || "")}"><i style="background:${aqiColor(c.aqi)}"></i>${esc(c.name)}<b>${esc(c.aqi)}</b></span>`
    ).join("");
    el.innerHTML =
      `<div class="region-head"><span class="region-title" title="${esc(t("region.hint"))}">${esc(t("region.title"))}</span>` +
      `<span class="region-state" data-level="${esc(region.level)}">${esc(t("region.level." + region.level))}</span></div>` +
      `<div class="region-chips">${chips}</div>` +
      `<div class="region-note">${esc(summary)}</div>`;
  }

  /* 北京官方动态：北京预警公告 + 与德州本次响应的时间重叠 */
  function renderBeijing(data) {
    const el = $("bjStatus");
    const feedEl = $("bjFeed");
    if (!el || !feedEl) return;
    const bj = (data.air && data.air.beijing) || {};
    if (!bj.available) {
      el.innerHTML = `<div class="bj-empty">${esc(t("bj.unavailable"))}</div>`;
      feedEl.innerHTML = "";
      return;
    }
    const link = bj.link || {};
    const state = bj.state || "none";
    const start = String(bj.started_at || "").slice(0, 10);
    const end = String(bj.ended_at || "").slice(0, 10);
    const short = (d) => (d ? d.slice(5) : "—");
    const windowText = end
      ? t("bj.window", { start: short(start), end: short(end), days: bj.days ?? "—" })
      : (bj.elapsed_days != null ? t("bj.windowOpen", { start: short(start), days: bj.elapsed_days }) : "");
    const signal = bj.signal || "none";
    const note = signal !== "none" ? t("bj.signal." + signal, {
      start: short(start),
      dz: short(String((link.dezhou || {}).started_at || "").slice(0, 10)),
      end: short(end),
      days: bj.days ?? "—",
      elapsed: bj.elapsed_days ?? "—",
      lag: link.beijing_lifted_days ?? "—",
      level: bj.level || "",
    }) : (state !== "none" ? t("bj.signal.none") : "");

    // 北京↔德州历史关系：启动/终止滞后 + 由北京日期反推的预计解除
    const hist = bj.history || {};
    const signed = (v) => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v);
    const sl = hist.start_lag || null;
    const el2 = hist.end_lag || null;
    let relation = "";
    if (hist.available && sl && el2) {
      relation = t("bj.relation", {
        n: hist.pair_count ?? (hist.pairs || []).length,
        start: Math.abs(sl.median),
        end: el2.median,
        nEnd: el2.n,
      });
    } else if (state !== "none") {
      relation = t("bj.relationEmpty");
    }
    const est = bj.estimate || {};
    const estDate = String(est.predicted_end || "").slice(0, 10);
    const estText = estDate && est.sample_size
      ? t(est.overdue ? "bj.estimateOverdue" : "bj.estimate", {
          date: short(estDate), lag: est.median_end_lag_days, n: est.sample_size,
        })
      : "";

    const pairs = (hist.pairs || []).slice().reverse();
    const pairRows = pairs.map((p) =>
      `<li><span class="t-date">${esc(p.bj_start)} → ${esc(p.bj_end || "—")}</span>` +
      `<span class="bj-pair-dz">${esc(t("bj.pairDz", { start: p.dz_start, end: p.dz_end || "—" }))}</span>` +
      (p.end_lag != null
        ? `<span class="bj-pair-lag">${esc(t("bj.pairLag", { v: signed(p.end_lag) }))}</span>`
        : "") +
      `</li>`).join("");

    el.innerHTML =
      `<div class="bj-head" data-state="${esc(state)}">` +
      `<span class="bj-state">${esc(t("bj.state." + state))}</span>` +
      `<span class="bj-level">${esc(bj.level || "—")}</span>` +
      `<span class="bj-window">${esc(windowText)}</span>` +
      (estText ? `<span class="bj-adjust">${esc(estText)}</span>` : "") +
      `</div>` +
      (note ? `<div class="bj-note" data-signal="${esc(signal)}">${esc(note)}</div>` : "") +
      (relation ? `<div class="bj-relation">${esc(relation)}</div>` : "") +
      (pairRows
        ? `<details class="bj-pairs"><summary>${esc(t("bj.pairs", { n: pairs.length }))}</summary><ul>${pairRows}</ul></details>`
        : "") +
      `<div class="bj-link"><a href="${esc(bj.url || "")}" target="_blank" rel="noopener">${esc(t("bj.column"))}</a></div>`;

    const items = bj.items || [];
    feedEl.innerHTML = items.length
      ? items.map((it) => {
          const kind = it.kind === "terminate" ? "lift" : "start";
          return `<li class="${it.overlap ? "on" : ""}">` +
            `<span class="t-date">${esc(it.effective_date || it.published_date || "—")}</span>` +
            `<span class="bj-kind ${kind}">${esc(t("bj.kind." + kind))}</span>` +
            (it.overlap ? `<span class="bj-overlap">${esc(t("bj.overlapTag"))}</span>` : "") +
            `<a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.title)}</a></li>`;
        }).join("")
      : `<li class="bj-empty">${esc(t("bj.feedEmpty"))}</li>`;
  }

  function renderAir(data) {
    const air = (data.air && data.air.current) || {};
    const meteo = (data.air && data.air.weather) || {};
    const disp = (data.air && data.air.dispersion) || {};
    $("aqiSource").textContent = t("tag.waqi");
    $("aqiValue").textContent = air.aqi == null ? "—" : Math.round(air.aqi);
    $("aqiLevel").textContent = aqiLevel(air.level) || "—";
    $("aqiStation").textContent = air.station ? t("air.station", { name: air.station }) : "";

    const ps = [
      ["PM2.5", air.pm25, "μg/m³"],
      ["PM10", air.pm10, "μg/m³"],
      [t("air.dominant"), air.dominant || "—", ""],
    ];
    $("pollutants").innerHTML = ps.map(([k, v, u]) => `<div class="poll">
        <span>${esc(k)}</span><b>${v == null || v === "" ? "—" : (typeof v === "number" ? esc(num(v, 0)) : esc(v))}</b><span>${esc(u)}</span>
      </div>`).join("");

    const w = [
      [t("air.temp"), meteo.temperature != null ? meteo.temperature + "℃" : "—"],
      [t("air.humidity"), meteo.humidity != null ? meteo.humidity + "%" : "—"],
      [t("air.windDir"), meteo.wind_dir != null ? meteo.wind_dir + "°" : "—"],
      [t("air.rain"), meteo.precipitation != null ? meteo.precipitation + " mm" : "—"],
    ];
    $("weatherRow").innerHTML = w.map(([k, v]) => `<div class="item">${esc(k)} ${esc(v)}</div>`).join("");

    $("dispersion").innerHTML = disp.level
      ? esc(t("air.dispersion", { level: dispLabel(disp.level), note: t("dispNote." + disp.level) }))
      : esc(t("air.dispersionNone"));

    renderRegion(data.air && data.air.region);

    const alerts = ana(data).alerts || [];
    $("alerts").innerHTML = alerts.map((x) => `<div class="alert-item">${esc(x)}</div>`).join("");

    drawSpark(data);
  }

  /* 近期复警概率（未来 72h 预报 + 历史阈值） */
  function renderReAlert(data) {
    const el = $("reAlert");
    if (!el) return;
    const ra = data.re_alert || {};
    if (!ra.available) { el.hidden = true; return; }
    el.hidden = false;

    $("reAlertProb").textContent = ra.probability;
    const lvl = $("reAlertLevel");
    lvl.className = "realert-level " + (ra.level || "");
    lvl.textContent = t("realert.level." + (ra.level || "low"));

    const bar = $("reAlertBar");
    bar.className = ra.level || "";
    bar.style.width = Math.max(4, Math.min(100, ra.probability)) + "%";

    const label = {
      peak: t("realert.peak", { v: ra.peak_aqi ?? "—", line: ra.alert_line }),
      persist: t("realert.persist", { v: ra.hot_hours }),
      calm: t("realert.calm", { v: ra.calm_hours, share: ra.calm_share }),
      dry: t("realert.dry", { v: ra.rain_mm }),
    };
    $("reAlertDrivers").innerHTML = (ra.drivers || []).map((d) =>
      `<li><span>${esc(label[d.key] || d.key)}</span><b>+${esc(Math.round(d.points))}</b></li>`).join("");
  }

  function renderChart(data) {
    const el = $("chart");
    const series = (data.air && data.air.hourly) || [];
    if (refs.air) { refs.air.dispose(); refs.air = null; }
    if (!window.echarts || !series.length) { el.innerHTML = '<p class="hint">—</p>'; return; }
    const time = series.map((s) => String(s.t).slice(5).replace("T", " "));
    const pick = (k) => series.map((s) => (s[k] == null ? null : s[k]));
    const defs = [
      { key: "pm25", name: "PM2.5", color: "#1f4e79", width: 1.9, area: true, axis: 0 },
      { key: "pm10", name: "PM10", color: "#8a6d3b", width: 1.4, axis: 0 },
      { key: "o3", name: "O₃", color: "#5c6b73", width: 1.2, axis: 0 },
      { key: "no2", name: "NO₂", color: "#8c6b6b", width: 1.2, axis: 0 },
      { key: "so2", name: "SO₂", color: "#2f6b47", width: 1.2, axis: 0 },
      { key: "dust", name: isEn() ? "Dust" : "沙尘", color: "#a8abae", width: 1.1, dash: true, axis: 0 },
      { key: "co", name: "CO (mg/m³)", color: "#a8752a", width: 1.2, axis: 1 },
    ];
    const chart = echarts.init(el, null, { renderer: "canvas" });
    refs.air = chart;
    chart.setOption({
      textStyle: { fontFamily: 'Inter, "PingFang SC", "Microsoft YaHei", sans-serif' },
      grid: { left: 46, right: 52, top: 44, bottom: 32 },
      tooltip: {
        trigger: "axis", backgroundColor: "#fff", borderColor: "#e3e4e6",
        textStyle: { color: "#1c1f21", fontSize: 12 }, extraCssText: "box-shadow:none;border-radius:2px;",
      },
      legend: {
        type: "scroll", top: 0, right: 0, itemGap: 14, icon: "rect", itemWidth: 9, itemHeight: 2,
        textStyle: { color: "#6b7280", fontSize: 10.5 },
        data: defs.map((d) => d.name),
        selected: { "CO (mg/m³)": false },
      },
      xAxis: {
        type: "category", data: time, boundaryGap: false,
        axisLine: { lineStyle: { color: "#e3e4e6" } }, axisTick: { show: false },
        axisLabel: { color: "#9aa0a6", fontSize: 10, interval: Math.ceil(time.length / 7) },
      },
      yAxis: [
        {
          type: "value", name: "μg/m³", nameTextStyle: { color: "#9aa0a6", fontSize: 10 },
          splitLine: { lineStyle: { color: "#f2f2f0" } }, axisLabel: { color: "#9aa0a6", fontSize: 10 },
        },
        {
          type: "value", position: "right", splitLine: { show: false },
          axisLabel: { color: "#9aa0a6", fontSize: 10 },
        },
      ],
      series: defs.map((d) => ({
        name: d.name, type: "line", smooth: true, showSymbol: false,
        yAxisIndex: d.axis, connectNulls: true,
        data: pick(d.key).map((v) => (d.key === "co" && v != null ? +(v / 1000).toFixed(2) : v)),
        lineStyle: { width: d.width, color: d.color, type: d.dash ? "dashed" : "solid" },
        itemStyle: { color: d.color },
        areaStyle: d.area ? { color: "rgba(31, 78, 121, 0.06)" } : undefined,
      })),
    });
    window.addEventListener("resize", () => refs.air && refs.air.resize());
  }

  function renderHistory(data) {
    const pred = data.prediction || {};
    const statsEl = $("histStats");
    const chartEl = $("histChart");
    if (refs.hist) { refs.hist.dispose(); refs.hist = null; }
    if (!pred.available) {
      statsEl.innerHTML = `<div class="hist-stat"><span>${t("hist.samples")}</span><b>${t("hist.none")}</b></div>
        <div class="hist-stat"><span>${t("hist.none")}</span><b style="font-size:12.5px">${t("hist.noneNote")}</b></div>`;
      chartEl.innerHTML = "";
      return;
    }
    const applicable = pred.applicable !== false;
    const bjEst = pred.beijing_estimate || {};
    const cards = [
      [t("hist.samples"), pred.sample_size, false],
      [t("hist.median"), pred.median_days + " " + t("unit.day"), false],
      [t("hist.p75"), pred.p75_days + " " + t("unit.day"), false],
    ];
    if (applicable && pred.elapsed_days > 0) {
      cards.push([t("hist.elapsed"), pred.elapsed_days + " " + t("unit.day"), false]);
    }
    cards.push(
      [t("hist.predicted"), applicable ? pred.predicted_days + " " + t("unit.day") : "—", true],
      [t("hist.end"), applicable && pred.predicted_end ? fmtDay(pred.predicted_end) : "—", true],
    );
    if (applicable && bjEst.predicted_end && bjEst.sample_size) {
      cards.push([t("hist.bjEst"), fmtDay(bjEst.predicted_end), true]);
      cards.push([t("hist.bjLag"),
        `${bjEst.median_end_lag_days} ${t("unit.day")} · ${bjEst.sample_size} ${t("unit.samples")}`, false]);
    }
    statsEl.innerHTML = cards.map(([k, v, hl]) =>
      `<div class="hist-stat ${hl ? "hl" : ""}"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join("");

    const noteEl = $("histBjNote");
    if (noteEl) {
      const hist = (data.air && data.air.beijing && data.air.beijing.history) || {};
      if (applicable && hist.available && bjEst.predicted_end) {
        noteEl.hidden = false;
        noteEl.textContent = t("hist.bjNote", {
          n: hist.pair_count ?? (hist.pairs || []).length,
          nEnd: (hist.end_lag || {}).n ?? 0,
          end: (hist.end_lag || {}).median ?? "—",
          date: fmtDay(bjEst.predicted_end),
        });
      } else {
        noteEl.hidden = true;
      }
    }

    if (!window.echarts) { chartEl.innerHTML = ""; return; }
    const rows = (pred.recent || []).filter((e) => e.days != null);
    if (applicable) rows.push({ start: t("hist.thisTime"), days: pred.predicted_days, predicted: true });
    const labels = rows.map((e) => (e.predicted ? t("hist.thisTime") : String(e.start).slice(5)));
    const values = rows.map((e) => e.days);
    const colors = rows.map((e) => (e.predicted ? "#8a5a12" : e.incomplete ? "#cdd0d3" : "#1f4e79"));
    let bjDays = null;
    const startIso = (data.notice || {}).effective_time;
    if (applicable && bjEst.predicted_end && startIso) {
      const diff = (new Date(bjEst.predicted_end) - new Date(startIso)) / 86400000;
      if (isFinite(diff) && diff > 0) bjDays = Math.round(diff * 10) / 10;
    }

    const chart = echarts.init(chartEl, null, { renderer: "canvas" });
    refs.hist = chart;
    chart.setOption({
      textStyle: { fontFamily: '-apple-system, "PingFang SC", "Microsoft YaHei", sans-serif' },
      grid: { left: 34, right: 14, top: 16, bottom: 24 },
      tooltip: {
        trigger: "axis", backgroundColor: "#fff", borderColor: "#e3e4e6",
        textStyle: { color: "#1c1f21", fontSize: 12 }, extraCssText: "box-shadow:none;border-radius:2px;",
        formatter: (p) => {
          const e = rows[p[0].dataIndex];
          if (e.predicted) return `${t("hist.predicted")}: ${e.days} ${t("unit.day")} → ${fmtDay(pred.predicted_end)}`;
          return `${e.start} → ${e.end || "—"}<br/>${e.days} ${t("unit.day")}${e.incomplete ? " (partial)" : ""}`;
        },
      },
      xAxis: {
        type: "category", data: labels, axisLine: { lineStyle: { color: "#e3e4e6" } },
        axisTick: { show: false }, axisLabel: { color: "#9aa0a6", fontSize: 10 },
      },
      yAxis: {
        type: "value", name: t("unit.day"), nameTextStyle: { color: "#9aa0a6", fontSize: 10 },
        splitLine: { lineStyle: { color: "#f2f2f0" } }, axisLabel: { color: "#9aa0a6", fontSize: 10 },
      },
      series: [{
        type: "bar",
        data: values.map((v, i) => ({ value: v, itemStyle: { color: colors[i], opacity: 0.9 } })),
        barMaxWidth: 20,
        label: { show: true, position: "top", color: "#9aa0a6", fontSize: 10 },
        markLine: {
          silent: true, symbol: "none",
          lineStyle: { color: "#8a5a12", type: "dashed", width: 1 },
          label: { formatter: t("hist.medianLine", { n: pred.median_days }), color: "#6b7280", fontSize: 10, position: "insideStartTop" },
          data: [
            { yAxis: pred.median_days },
            ...(bjDays ? [{
              yAxis: bjDays,
              lineStyle: { color: "#1f7a5a", type: "dotted", width: 1 },
              label: {
                formatter: t("hist.bjLine", { n: bjDays }), color: "#1f7a5a",
                fontSize: 10, position: "insideEndTop",
              },
            }] : []),
          ],
        },
      }],
    });
    window.addEventListener("resize", () => refs.hist && refs.hist.resize());
  }

  function renderThreshold(data) {
    const th = data.threshold || {};
    const statusEl = $("thrStatus");
    const barEl = $("thrBar");
    const scaleEl = $("thrScale");
    const statsEl = $("thrStats");
    const legendEl = $("thrLegend");
    const sentenceEl = $("thrSentence");
    if (!th.available) {
      statusEl.className = "thr-status unknown";
      statusEl.textContent = t("thr.status.unknown");
      $("thrCurrent").textContent = "—";
      $("thrCurrentUnit").textContent = "";
      sentenceEl.textContent = "";
      barEl.innerHTML = "";
      scaleEl.innerHTML = "";
      legendEl.innerHTML = "";
      statsEl.innerHTML = `<div class="thr-row"><span>${esc(t("thr.none"))}</span></div>`;
      return;
    }
    const hc = th.hot_count || {};
    const cur = th.current || {};
    const st = th.stations || {};
    const max = hc.max || th.grid_points || 9;
    const curN = cur.hot_count;
    const thr = hc.threshold;
    const typ = hc.typical;
    const status = cur.status || "unknown";

    statusEl.className = "thr-status " + status;
    statusEl.textContent = t("thr.status." + status);
    $("thrCurrent").textContent = curN == null ? "—" : curN;
    $("thrCurrentUnit").textContent = ` / ${max}`;

    // 一句话说清楚：现在几个点、警戒线几个、差多少
    if (curN != null && thr != null) {
      const gap = Math.abs(thr - curN);
      const dist = curN >= thr ? t("thr.distOver", { gap }) : t("thr.distAway", { gap });
      sentenceEl.innerHTML = t("thr.sentence", { cur: curN, thr, theta: th.hot_theta, dist }) +
        (typ != null ? `<br/><span style="color:var(--muted)">${esc(t("thr.typicalNote", { typ }))}</span>` : "");
    } else {
      sentenceEl.textContent = t("thr.distNone");
    }

    // 9 个格子：已超标的点亮，达到警戒线的格子描边，当前值所在格子高亮
    let segHtml = "";
    for (let i = 0; i < max; i++) {
      const cls = ["seg"];
      if (curN != null && i < curN) cls.push("on");
      if (thr != null && i + 1 >= thr) cls.push("hot");
      if (curN != null && i === curN - 1) cls.push("now");
      if (thr != null && i + 1 === thr) cls.push("thr");
      segHtml += `<span class="${cls.join(" ")}" title="${i + 1}"></span>`;
    }
    barEl.innerHTML = segHtml;

    scaleEl.style.display = "grid";
    scaleEl.style.gridTemplateColumns = `repeat(${max}, 1fr)`;
    scaleEl.innerHTML = Array.from({ length: max }, (_, i) => {
      if (i === 0) return "<span>0</span>";
      if (thr != null && i + 1 === thr) return `<span class="lbl">▲ ${thr}</span>`;
      if (i === max - 1) return `<span style="text-align:right">${max}</span>`;
      return "<span></span>";
    }).join("");

    legendEl.innerHTML = [
      `<span class="safe"><i></i>${esc(t("thr.legendSafe", { a: thr != null ? thr - 1 : 0 }))}</span>`,
      `<span class="watch"><i></i>${esc(t("thr.legendWatch", { b: thr ?? "—", c: typ != null ? Math.max(thr ?? 0, Math.ceil(typ)) - 1 : "—" }))}</span>`,
      `<span class="typ"><i></i>${esc(t("thr.legendTyp", { d: typ != null ? Math.ceil(typ) : "—" }))}</span>`,
    ].join("");

    const pctText = (v) => (v == null ? "—" : `${Math.round(v * 100)}%`);
    const rows = [
      [t("thr.rule"), thr != null ? `≥ ${thr} / ${max}` : "—"],
      [t("thr.typical"), typ != null ? `${typ} / ${max}` : "—"],
      [t("thr.recall"), `${pctText(hc.recall)} / ${pctText(hc.precision)}`],
      [t("thr.samples"), `${th.samples?.positive_days ?? "—"} / ${th.samples?.history_days ?? "—"}`],
      [t("thr.city"), th.city_aqi?.threshold != null ? `${cur.city_aqi_3d ?? "—"} / ${th.city_aqi.threshold}` : "—"],
      [t("thr.cityState"), t("thr.status." + (cur.city_status || "unknown"))],
      [t("thr.forecast"), cur.forecast_peak != null ? String(Math.round(cur.forecast_peak)) : "—"],
      [t("thr.stations", { theta: th.hot_theta }), `${st.exceed_hot ?? "—"} / ${st.total ?? "—"}`],
      [t("thr.window"), `${th.window?.start || "—"} → ${th.window?.end || "—"}`],
    ];
    statsEl.innerHTML = rows.map(([k, v]) =>
      `<div class="thr-row"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join("");
  }

  function renderMap(data) {
    const el = $("map");
    if (!window.L) { el.innerHTML = ""; return; }
    if (refs.map) { refs.map.remove(); refs.map = null; }
    const map = L.map(el, { zoomControl: true, attributionControl: true }).setView([37.4355, 116.3594], 10);
    refs.map = map;

    // 免 Key 底图：优先国内可直连的 OSM 镜像，官方源作兜底；失败自动切换
    const providers = [
      {
        url: "https://tile.openstreetmap.de/{z}/{x}/{y}.png",
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        subdomains: "abc", maxZoom: 18, name: "OSM DE",
      },
      {
        url: "https://tile.openstreetmap.jp/{z}/{x}/{y}.png",
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        subdomains: "abc", maxZoom: 18, name: "OSM Japan",
      },
      {
        url: "https://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · HOT',
        subdomains: "ab", maxZoom: 18, name: "OSM France",
      },
      {
        url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        subdomains: "abc", maxZoom: 19, name: "OpenStreetMap",
      },
    ];
    let idx = 0, errors = 0, layer = null;
    const showFallback = () => {
      if (el.querySelector(".map-fallback")) return;
      const box = document.createElement("div");
      box.className = "map-fallback";
      box.innerHTML = `<span>${esc(t("map.failed"))}</span><button type="button">${esc(t("map.retry"))}</button>`;
      box.querySelector("button").addEventListener("click", () => {
        box.remove();
        idx = 0; errors = 0;
        useProvider(0);
      });
      el.appendChild(box);
    };
    const useProvider = (i) => {
      const p = providers[i];
      if (!p) return;
      if (layer) map.removeLayer(layer);
      layer = L.tileLayer(p.url, { attribution: p.attribution, subdomains: p.subdomains, maxZoom: p.maxZoom }).addTo(map);
      layer.on("tileerror", () => {
        errors += 1;
        if (errors > 2 && idx + 1 < providers.length) { idx += 1; errors = 0; useProvider(idx); }
        else if (errors > 6 && idx + 1 >= providers.length) showFallback();
      });
      $("mapHint").textContent = t("hint.map", { tiles: p.name });
    };
    useProvider(0);

    L.circleMarker([37.4355, 116.3594], {
      radius: 6, color: "#f79009", weight: 2, dashArray: "3 3", fillColor: "#f79009", fillOpacity: 0.12,
    }).addTo(map).bindPopup(isEn() ? "<b>Dezhou centre</b>" : "<b>德州市中心</b>");

    const supplierLayer = L.layerGroup().addTo(map);
    const pts = [[37.4355, 116.3594]];
    (data.suppliers || []).forEach((s) => {
      if (!s.lat || !s.lon) return;
      const color = { stop: "#c8321f", heavy: "#f79009", partial: "#eab308", none: "#98a2b3" }[s.impact] || "#98a2b3";
      const icon = L.divIcon({
        className: "",
        html: `<div class="map-pin-wrap" style="--pin:${color}">
                 <span class="map-pin-ring"></span><span class="map-pin"></span>
                 <em class="map-pin-label">${esc(s.name.replace(/^山东/, "").replace(/有限公司$/, ""))} · ${s.impact === "none" ? esc(impactLabel(s)) : esc(s.reduction_pct) + "%"}</em>
               </div>`,
        iconSize: [14, 14], iconAnchor: [7, 7],
      });
      L.marker([s.lat, s.lon], { icon }).addTo(supplierLayer).bindPopup(
        `<b>${esc(s.name)}</b><br/>${esc(s.district || "")} · ${esc(s.industry || "")}/${esc(s.industry_branch || "")}<br/>` +
        `${esc(impactLabel(s))} · ${esc(s.duration_days)} ${t("unit.day")}<br/>` +
        `<span style="color:#7b8794;font-size:11.5px">` +
        ((s.affected_lines || []).map((l) =>
          `${esc(l.process)}${l.total_lines ? ` (${l.stopped_lines || 0}/${l.total_lines})` : ""}`).join(" · ")
          || esc(s.line_text || "")) +
        `</span>`
      );
      pts.push([s.lat, s.lon]);
    });

    // 污染区（示意）：以监测站为圆心，按 AQI 放大半径；只表示量级，不是实测边界
    const zoneLayer = L.layerGroup().addTo(map);
    const stations = (data.air && data.air.stations) || [];
    stations.forEach((st) => {
      if (!st.lat || !st.lon || st.aqi == null) return;
      const c = aqiColor(st.aqi);
      const radius = Math.min(9000, Math.max(1200, (st.aqi / 100) * 2200));
      L.circle([st.lat, st.lon], {
        radius, color: c, weight: 1, opacity: 0.35,
        fillColor: c, fillOpacity: 0.18, interactive: false,
      }).addTo(zoneLayer);
    });

    const stationLayer = L.layerGroup().addTo(map);
    stations.forEach((st) => {
      if (!st.lat || !st.lon) return;
      const c = aqiColor(st.aqi);
      L.circleMarker([st.lat, st.lon], { radius: 5, color: "#fff", weight: 1.2, fillColor: c, fillOpacity: 0.85 })
        .addTo(stationLayer)
        .bindPopup(`<b>${esc(st.name)}</b><br/>AQI <b style="color:${c}">${esc(st.aqi)}</b> · ${esc(aqiLevel(st.level))}<br/>
          <span style="color:#7b8794;font-size:11px">${esc(st.full_name || "")}<br/>${esc(st.time || "")}</span>`);
    });
    // 区域联动：京津冀及周边城市（不参与 fitBounds，避免把德州视角缩得太远）
    const regionCities = (data.air && data.air.region && data.air.region.cities) || [];
    const regionLayer = L.layerGroup();
    regionCities.forEach((c) => {
      if (!c.lat || !c.lon || c.aqi == null) return;
      const col = aqiColor(c.aqi);
      L.circleMarker([c.lat, c.lon], {
        radius: 7, color: col, weight: 2, fillColor: col, fillOpacity: 0.35,
      }).addTo(regionLayer).bindPopup(
        `<b>${esc(c.name)}</b><br/>AQI <b style="color:${col}">${esc(c.aqi)}</b> · ${esc(aqiLevel(c.level))}` +
        (c.pm25_24h != null
          ? `<br/><span style="color:#7b8794;font-size:11px">${esc(t("region.forecast", { v: c.pm25_24h }))}</span>`
          : ""));
    });
    if (regionCities.length) regionLayer.addTo(map);

    const ctl = {};
    ctl[isEn() ? "Suppliers" : "供应商"] = supplierLayer;
    if (stations.length) ctl[isEn() ? "Stations (WAQI)" : "监测站 (WAQI)"] = stationLayer;
    if (stations.length) ctl[isEn() ? "Pollution zones (indicative)" : "污染区（示意）"] = zoneLayer;
    if (regionCities.length) ctl[isEn() ? "Region cities" : "区域城市"] = regionLayer;
    if (Object.keys(ctl).length > 1) {
      L.control.layers(null, ctl, { position: "topright", collapsed: true }).addTo(map);
    }

    const legend = document.querySelector(".legend");
    if (legend && stations.length) {
      const stops = [[isEn() ? "Good" : "优", "#12b76a"], [isEn() ? "Mod" : "良", "#eab308"],
                     [isEn() ? "Light" : "轻度", "#f79009"], [isEn() ? "Heavy" : "中度", "#ef4444"],
                     [isEn() ? "Severe" : "重度", "#a855f7"]];
      legend.insertAdjacentHTML("beforeend",
        `<span class="aqi-legend">${t("legend.stations")}：` +
        stops.map(([x, c]) => `<i class="dot-risk" style="background:${c}"></i>${x}`).join("") + "</span>" +
        `<span class="zone-legend"><i></i>${esc(t("legend.zones"))}</span>`);
    }

    // 容器在移动端可能刚布局完成，先 invalidateSize 再 fit，避免缩放异常
    const fit = () => {
      map.invalidateSize();
      map.fitBounds(pts, { padding: [50, 50], maxZoom: 11 });
    };
    fit();
    setTimeout(fit, 300);
  }

  function renderSuppliers(data) {
    const body = $("supplierBody");
    const list = data.suppliers || [];
    if (!list.length) {
      body.innerHTML = `<tr><td colspan="8" class="hint">${esc(t("supplier.empty"))}</td></tr>`;
      $("supplierNote").innerHTML = "";
      return;
    }
    body.innerHTML = list.map((s) => {
      const heat = s.reduction_pct >= 80 ? "hot" : s.reduction_pct >= 30 ? "mid" : "cool";
      const cost = s.impact === "none" ? "—" : s.daily_cost
        ? `${Number(s.daily_cost).toLocaleString()} ${isEn() ? "CNY/day" : "元/天"}`
        : "—";
      const lineText = isEn() && s.line_text_en ? s.line_text_en : s.line_text;
      const method = (() => {
        if (!isEn()) return s.reduction_method || "";
        const m = String(s.reduction_method || "").match(/(\d+)/);
        return m && String(s.reduction_method).indexOf("加权") >= 0
          ? `weighted by ${m[1]} lines`
          : "max factor";
      })();
      const linesHtml = (s.affected_lines || []).map((l) =>
        `${esc(l.process)}<small>${esc(wayLabel(l.way))}${l.total_lines ? ` · ${l.stopped_lines || 0}/${l.total_lines} ${isEn() ? "lines" : "条线"}` : ""}</small>`).join("")
        || `<span class="unknown">${esc(t("impact.none"))}</span>`;
      const mobile = (s.mobile_lines || []).length
        ? `<small>${esc(t("mobility", { way: wayLabel(s.mobile_lines[0].way) }))}</small>` : "";
      return `<tr>
        <td class="name">${esc(s.name)}<small>${esc(s.district || "")} · ${esc(s.industry || "")}/${esc(s.industry_branch || "")}</small></td>
        <td data-label="${esc(t("th.performance"))}">${esc(s.performance || "—")}</td>
        <td data-label="${esc(t("th.impact"))}"><span class="badge ${esc(s.impact)}">${esc(impactLabel(s))}</span><small>${esc(lineText || "")}</small></td>
        <td data-label="${esc(t("th.lines"))}">${linesHtml}${mobile}</td>
        <td data-label="${esc(t("th.reduction"))}">${s.impact === "none"
          ? "—"
          : `<span class="reduction ${heat}">${esc(s.reduction_pct)}%</span><small>${esc(method)}</small>`}</td>
        <td data-label="${esc(t("th.duration"))}">${s.impact === "none" ? "—" : esc(s.duration_days) + " " + `<small style="display:inline;color:#9aa0a6">${t("unit.day")}</small>`}</td>
        <td class="nowrap" data-label="${esc(t("th.window"))}">${s.impact === "none"
          ? esc(t("row.ended", { time: fmtTime(s.window_end) }))
          : esc(fmtDay(s.window_start)) + " → " + esc(fmtDay(s.window_end))}</td>
        <td class="nowrap" data-label="${esc(t("th.cost"))}">${esc(cost)}</td>
      </tr>`;
    }).join("");
    $("supplierNote").innerHTML = `<p class="hint">${esc(t("supplier.note"))}</p>`;
  }

  function evidenceFieldName(field) {
    if (!isEn()) return field;
    if (field.indexOf("工序与措施") === 0) {
      return "Process & measure · " + field.replace("工序与措施 · ", "");
    }
    return FIELD_EN[field] || field;
  }

  function renderEvidence(data) {
    const list = data.suppliers || [];
    const box = $("evidenceBody");
    if (!list.length) { box.innerHTML = ""; return; }
    box.innerHTML = list.map((s) => {
      const ev = s.evidence || [];
      const official = ev.filter((e) => e.tier === "official").length;
      const rows = ev.map((e) => `<tr>
          <td>${esc(evidenceFieldName(e.field))}</td>
          <td>${esc(isEn() && e.value_en ? e.value_en : e.value)}</td>
          <td><span class="tier ${esc(e.tier)}">${esc(t("tier." + e.tier))}</span></td>
          <td class="src">${esc(isEn() && e.source_en ? e.source_en : e.source)}${e.url ? ` · <a href="${esc(e.url)}" target="_blank" rel="noopener">link</a>` : ""}</td>
          <td><code>${esc(e.raw)}</code></td>
        </tr>`).join("");
      return `<div class="evidence-block">
        <h4 class="evidence-title">${esc(t("evidence.title", { name: s.name }))}
          <span>${esc(t("evidence.intro", { n: ev.length, o: official }))}</span></h4>
        <div class="table-wrap">
          <table class="evidence">
            <thead><tr>
              <th>${esc(t("th.field"))}</th><th>${esc(t("th.value"))}</th>
              <th>${esc(t("th.tier"))}</th><th>${esc(t("th.basis"))}</th><th>${esc(t("th.raw"))}</th>
            </tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>`;
    }).join("");
  }

  function renderCounter(data) {
    const items = ana(data).counter_hoarding || [];
    $("counterList").innerHTML = items.length
      ? items.map((x, i) => `<li data-i="${i + 1}">${esc(x)}</li>`).join("")
      : `<li data-i="!">${esc(t("counter.none"))}</li>`;
  }

  function renderTimeline(data) {
    const list = (data.history || []).slice(0, 10);
    const current = (data.notice && data.notice.id) || "";
    $("timeline").innerHTML = list.length
      ? list.map((h) => `<li class="${h.id === current ? "on" : ""}">
          <div class="t-date">${esc(h.publish_date || "")}</div>
          <a class="t-title" href="${esc(h.url)}" target="_blank" rel="noopener">${esc(h.title)}</a>
          <span class="t-tag">${esc(colorLabel(h.color) || h.kind_label || "")}</span>
        </li>`).join("")
      : `<li>${esc(t("timeline.empty"))}</li>`;
  }

  function renderSources(data) {
    const s = data.sources || {};
    const item = (label, value, url) => `<div class="src-item"><b>${esc(label)}</b>：` +
      (url ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(value)}</a>` : esc(value)) + "</div>";
    const parts = [];
    if (s.notice) parts.push(item(t("src.notice"), s.notice.title, s.notice.url));
    parts.push(item(t("src.list"), t("src.listv"), s.list_url));
    if (s.emission_list) {
      const snap = s.emission_list.snapshot || {};
      const val = t("src.emissionv", {
        file: s.emission_list.file, sheet: s.emission_list.sheet, dir: s.emission_list.dir,
      }) + (snap.generated_at ? ` · ${isEn() ? "built-in snapshot" : "内置快照"} ${fmtDay(snap.generated_at)}` : "");
      parts.push(item(t("src.emission"), val));
    }
    if (s.aqi) parts.push(item(t("src.aqi"), t("src.aqiv", {
      provider: s.aqi.provider, station: s.aqi.station || "—", time: s.aqi.time || "—",
    }), s.aqi.url));
    if (s.meteo) parts.push(item(t("src.meteo"), t("src.meteov", {
      provider: s.meteo.provider, vars: s.meteo.variables, time: fmtTime(s.meteo.generated_at),
    }), s.meteo.url));
    if (s.history) parts.push(item(t("src.history"), t("src.historyv", { n: s.history.samples ?? "—" }), s.history.list_url));
    if (s.beijing) parts.push(item(t("src.beijing"), t("src.beijingv", {
      state: t("bj.state." + (s.beijing.state || "none")), n: s.beijing.count ?? "—",
    }), s.beijing.url));
    if (s.map) parts.push(item(t("src.map"), t("src.mapv", { tiles: s.map.tiles, stations: s.map.stations })));
    $("sourcesBox").innerHTML = parts.join("");
    document.querySelector("footer .disclaimer").textContent = t("footer.disclaimer");
  }

  /* ================= boot ================= */
  function applyStaticText() {
    document.documentElement.lang = isEn() ? "en" : "zh-CN";
    document.title = t("site.title");
    document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    document.querySelectorAll(".lang-switch button").forEach((b) => {
      b.setAttribute("aria-pressed", String(b.dataset.lang === LANG));
    });
  }

  /* ---------------- 视图切换（桌面侧栏 / 手机底部标签） ---------------- */
  const VIEWS = ["overview", "trend", "impact", "basis"];
  const VIEW_LABEL = { overview: "toc.now", trend: "toc.trend", impact: "toc.impact", basis: "toc.basis" };

  function currentView() {
    const h = (location.hash || "").replace("#", "").toLowerCase();
    return VIEWS.indexOf(h) >= 0 ? h : "overview";
  }

  function activate(view, opts) {
    const scrollTop = !opts || opts.scroll !== false;
    document.querySelectorAll(".view").forEach((v) => {
      v.hidden = v.dataset.view !== view;
    });
    document.querySelectorAll("button[data-view]").forEach((b) => {
      const on = b.dataset.view === view;
      b.classList.toggle("active", on);
      b.setAttribute("aria-current", on ? "page" : "false");
    });
    const title = $("appbarTitle");
    if (title) title.textContent = t(VIEW_LABEL[view] || "toc.now");
    if (scrollTop) window.scrollTo({ top: 0, behavior: "auto" });

    // 重的组件按需初始化，避免在隐藏容器里以 0 尺寸绘制
    if (!DATA) return;
    if (view === "overview") {
      drawSpark(DATA);
    } else if (view === "trend") {
      if (!refs.air) renderChart(DATA); else refs.air.resize();
      if (!refs.hist) renderHistory(DATA); else refs.hist.resize();
    } else if (view === "impact") {
      if (!refs.map) renderMap(DATA); else refs.map.invalidateSize();
    }
  }

  function setupNav() {
    document.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-view]");
      if (!btn) return;
      const view = btn.dataset.view;
      if (currentView() === view) {
        activate(view);
      } else {
        location.hash = view;
      }
    });
    window.addEventListener("hashchange", () => activate(currentView()));
    window.addEventListener("resize", () => {
      if (refs.air) refs.air.resize();
      if (refs.hist) refs.hist.resize();
      if (refs.map) refs.map.invalidateSize();
      if (DATA) drawSpark(DATA);
    });
  }

  function render(data) {
    DATA = data;
    applyStaticText();
    if (!data) {
      $("kpis").innerHTML = `<div class="kpi"><div class="label">data/latest.js not found</div></div>`;
      return;
    }
    // 重建前清掉旧的实例，避免语言切换后重复叠加
    if (refs.map) { refs.map.remove(); refs.map = null; }
    if (refs.air) { refs.air.dispose(); refs.air = null; }
    if (refs.hist) { refs.hist.dispose(); refs.hist = null; }
    document.querySelector(".legend .aqi-legend")?.remove();

    renderHero(data);
    renderKpis(data);
    renderAnalysis(data);
    renderAir(data);
    renderBeijing(data);
    renderReAlert(data);
    renderSuppliers(data);
    renderEvidence(data);
    renderCounter(data);
    renderTimeline(data);
    renderSources(data);
    renderThreshold(data);
    setupNav();

    // 小屏默认收起证据链
    const evidence = document.getElementById("evidencePane");
    if (evidence) evidence.open = window.innerWidth > 720;

    // 只渲染当前标签页里的重组件
    activate(currentView(), { scroll: false });
  }

  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".lang-switch button");
    if (!btn) return;
    LANG = btn.dataset.lang;
    localStorage.setItem("sw-lang", LANG);
    render(DATA);
  });

  if (window.__DATA__) {
    render(window.__DATA__);
  } else {
    fetch("./data/latest.json?t=" + Date.now())
      .then((r) => r.json())
      .then(render)
      .catch(() => render(null));
  }
})();
