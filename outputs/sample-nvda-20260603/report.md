# Earnings Review: NVDA 2027Q1

## Verdict

Neutral

Confidence: 0.68

## Summary

2027Q1はEPS 0.81と売上350億ドルがコンセンサスを上回り、当期実績は明確に良好でした。一方で、粗利率改善の一部は前年在庫引当の反動で説明され、営業費用も増加しています。FCFは120億ドルと強いものの、前期比・前年同期比や working capital、cash、debt、liquidity の欠落により持続性は限定的にしか確認できません。EPSとFCFがともに悪化しているわけではないが、将来の再現性に重要な未確認点が多く、総合判定は neutral が妥当です。

## Evidence Matrix

| # | Direction | Claim | Evidence value / quote | Interpretation | Source | Timing | Confidence |
|---:|---|---|---|---|---|---|---:|
| 1 | positive | EPSはコンセンサスを上回った | 0.81 USD/share (eps) | reported_period_actualsのEPSは0.81で、consensus_for_reported_periodの0.75を上回っている。四半期EPSは期待超えで、ヘッドラインはポジティブ。 | `financial_api:NVDA:2027Q1:eps` / eps | same_period_primary | 0.95 |
| 2 | positive | 売上はコンセンサスを上回った | 35,000,000,000 USD (revenue) | reported_period_actualsのrevenueは350億ドルで、consensus_for_reported_periodの330億ドルを上回っている。売上の上振れはEPS上振れの土台として整合的。 | `financial_api:NVDA:2027Q1:revenue` / revenue | same_period_primary | 0.90 |
| 3 | positive | 粗利率が前年同四半期比で大きく改善 | 74.9 % | presentationのGAAP P&Lで粗利率は74.9%、Non-GAAPで75.0%と示され、Q1 FY26の60.5%/60.8%から大幅に上昇している。presentationでは主因として、前年のH20 excess inventoryに関連する大きな在庫引当の反動が挙げられており、売上成長だけでなく利益率改善がEPSを支えた。 | `nvda-f1q27-quarterly-presentation:p9:section-1` / nvda-f1q27-quarterly-presentation:p9:section-1 | same_period_primary | 0.72 |
| 4 | positive | FCFと資本還元を同時に強化 | Q1 FY27 の Free Cash Flow は 48.6B、Capital Return は約20Bと示され、さらに新たな 80B の自己株取得枠と配当増額が公表されている。経営陣は強いキャッシュ創出を株主還元と戦略投資の両方に配分しており、FCFの強さを重視している。 | Q1 FY27 の Free Cash Flow は 48.6B、Capital Return は約20Bと示され、さらに新たな 80B の自己株取得枠と配当増額が公表されている。経営陣は強いキャッシュ創出を株主還元と戦略投資の両方に配分しており、FCFの強さを重視している。 | `nvda-f1q27-quarterly-presentation:p8:section-1` / nvda-f1q27-quarterly-presentation:p8:section-1 | same_period_primary | 0.64 |
| 5 | negative | 粗利改善は前年の在庫引当反動の影響を含む | 粗利率の前年差改善について、前年のH20 excess inventory に関連する 4.5B の在庫費用が主因だったと説明されており、利益率改善の一部は一時要因に依存している。したがって、現在の粗利率の強さをそのまま持続的な構造改善とみなすのは慎重であるべき。 | 粗利率の前年差改善について、前年のH20 excess inventory に関連する 4.5B の在庫費用が主因だったと説明されており、利益率改善の一部は一時要因に依存している。したがって、現在の粗利率の強さをそのまま持続的な構造改善とみなすのは慎重であるべき。 | `nvda-f1q27-quarterly-presentation:p5:section-1` / nvda-f1q27-quarterly-presentation:p5:section-1 | same_period_primary | 0.62 |
| 6 | negative | Opex増加は短期EPSの逆風 | Q1 FY26 と比べて Q1 FY27 の GAAP/Non-GAAP Opex が上昇しており、成長投資の実行がコスト負担を増やしていることを示す。短期では売上成長が強くても、費用増がEPS拡大を相殺する可能性がある。 | Q1 FY26 と比べて Q1 FY27 の GAAP/Non-GAAP Opex が上昇しており、成長投資の実行がコスト負担を増やしていることを示す。短期では売上成長が強くても、費用増がEPS拡大を相殺する可能性がある。 | `nvda-f1q27-quarterly-presentation:p6:section-1` / nvda-f1q27-quarterly-presentation:p6:section-1 | same_period_primary | 0.60 |
| 7 | risk | EPSの質を分解するための補助指標が不足 | 税率、希薄化株式数、GAAP/non-GAAP差分の定量的なEPSブリッジは提示されているが、対象四半期の継続的な寄与か一時要因かを独立に検証できる補助指標が限られる。特にセグメント別売上や製品ミックスがないため、売上品質とEPS持続性の評価は限定的。 | 税率、希薄化株式数、GAAP/non-GAAP差分の定量的なEPSブリッジは提示されているが、対象四半期の継続的な寄与か一時要因かを独立に検証できる補助指標が限られる。特にセグメント別売上や製品ミックスがないため、売上品質とEPS持続性の評価は限定的。 | `nvda-f1q27-quarterly-presentation:p13:section-1` / nvda-f1q27-quarterly-presentation:p13:section-1 | same_period_primary | 0.60 |

## Agent Analysis

- **EarningsQualityAnalyst** (positive, confidence 0.74): 対象四半期はEPS・売上ともにコンセンサス超えで、粗利率と営業利益の拡大がEPSの質を支えているため、総合的にはポジティブです。ただし、粗利率改善の一部は前年の大きな在庫引当反動という一時的・比較ベース要因で説明され、セグメント/税率/株式数の補助情報が不足しているため、EPS改善の全てを恒常的とみなすには慎重さが必要です。FCFは高水準の売上・利益率と整合的な方向感はあるものの、本タスクでは詳細評価をしません。
- **CashFlowRiskAnalyst** (mixed, confidence 0.58): 当期はCFO 150億ドル、FCF 120億ドル、CapEx 30億ドルでキャッシュ創出は強い。一方、比較期間がなくトレンドは未確認で、working capital・cash・debt・liquidity・maturityの欠落により将来FCF改善の持続性は限定的にしか判断できない。EPS面ではキャッシュ制約を示す材料は見当たらないが、資本配分と投資強度が増える場合のFCF変動リスクには留意が必要。
- **ManagementIntentAnalyst** (mixed, confidence 0.63): 経営陣は、AI需要と次世代製品の立ち上がりに合わせて供給・生産・流通と成長投資を進めつつ、強いFCFを株主還元にも振り向けている。短期は費用増と実行リスクでEPSがぶれやすいが、中期は需要取り込みと供給制約緩和が利益成長とFCF維持を支える余地がある。粗利率の強さには前年在庫引当の反動が含まれるため、構造的改善かどうかは追加確認が必要。
- **GuidanceAnalyst** (neutral, confidence 0.57): 2027Q1の実績はEPSと売上高でコンセンサス超え。ガイダンス分析では、Q2 FY27 Outlookとして売上高910億ドル、粗利率75.0%、Opex83億ドル程度、China Data Center compute revenueを織り込まない前提が確認できる。一方で guided_period と consensus_for_guided_period が未提供のため、ガイダンスの保守性・強気度、EPS/FCFへの定量的影響、修正リスクを強くは結論づけられない。資料の明確さは高いが、コンセンサス対比の欠落が主要な制約。

## Positive Evidence

- EPSはコンセンサスを上回った
- 売上はコンセンサスを上回った
- 粗利率が前年同四半期比で大きく改善
- FCFと資本還元を同時に強化

## Negative Evidence

- 粗利改善は前年の在庫引当反動の影響を含む
- Opex増加は短期EPSの逆風
- EPSの質を分解するための補助指標が不足

## EPS Outlook

短期EPSは良好だが、持続性は未確定

Reason: 当期EPSは 0.81 でコンセンサス 0.75 を上回り、売上と粗利率改善が支えました。ただし、粗利率改善の一部は前年在庫引当の反動で説明され、Opex も増加しています。さらに税率、希薄化株式数、セグメント別売上が不足しているため、来期以降のEPS改善を定量的に裏づける材料は限定的です。

## FCF Outlook

当期FCFは強いが、再現性は限定的

Reason: FCF は 120億ドル、営業CF は 150億ドル、CapEx は 30億ドルで、当期のキャッシュ創出力は良好です。一方で、前期比・前年同期比の比較、working capital、cash、debt、liquidity、maturity profile が不足しており、将来FCFの持続性は十分に確認できません。成長投資の継続も変動要因です。

## Bull Case

当四半期はEPS・売上ともにコンセンサスを上回り、粗利率と営業利益の拡大が利益の質を支えたうえ、CFO/FCFも強く、経営陣が成長投資と資本還元を両立させているため、総合的には good と評価できる材料が揃っています。ただし、粗利率改善の一部は前年差の反動要因が含まれ、FCFの持続性やガイダンスの定量評価には欠落情報があるため、強いが無条件ではないケースです。

## Bear Case

今回の決算はヘッドラインでは上振れだが、bad寄りではなくても少なくとも『無条件に良い』とは言い切れません。EPS・売上はコンセンサス超えでも、その一部は前年の在庫引当反動による粗利率改善が含まれ、営業費用も増加しているため、EPSの質と持続性には留保が必要です。加えて、FCFは強い一方で前期比・前年同期比の比較や working capital、cash、debt、liquidity の情報が不足しており、将来FCFの再現性は未確認です。ガイダンスもQ2 FY27の水準は示されているものの、guided_period と consensus_for_guided_period が欠けるため、強さを定量評価できません。

## Analyst Brief

対象四半期はEPS・売上ともにコンセンサス超えで、粗利率と営業利益の拡大がEPSの質を支えているため、総合的にはポジティブです。ただし、粗利率改善の一部は前年の大きな在庫引当反動という一時的・比較ベース要因で説明され、セグメント/税率/株式数の補助情報が不足しているため、EPS改善の全てを恒常的とみなすには慎重さが必要です。FCFは高水準の売上・利益率と整合的な方向感はあるものの、本タスクでは詳細評価をしません。 当期はCFO 150億ドル、FCF 120億ドル、CapEx 30億ドルでキャッシュ創出は強い。一方、比較期間がなくトレンドは未確認で、working capital・cash・debt・liquidity・maturityの欠落により将来FCF改善の持続性は限定的にしか判断できない。EPS面ではキャッシュ制約を示す材料は見当たらないが、資本配分と投資強度が増える場合のFCF変動リスクには留意が必要。 経営陣は、AI需要と次世代製品の立ち上がりに合わせて供給・生産・流通と成長投資を進めつつ、強いFCFを株主還元にも振り向けている。短期は費用増と実行リスクでEPSがぶれやすいが、中期は需要取り込みと供給制約緩和が利益成長とFCF維持を支える余地がある。粗利率の強さには前年在庫引当の反動が含まれるため、構造的改善かどうかは追加確認が必要。 2027Q1の実績はEPSと売上高でコンセンサス超え。ガイダンス分析では、Q2 FY27 Outlookとして売上高910億ドル、粗利率75.0%、Opex83億ドル程度、China Data Center compute revenueを織り込まない前提が確認できる。一方で guided_period と consensus_for_guided_period が未提供のため、ガイダンスの保守性・強気度、EPS/FCFへの定量的影響、修正リスクを強くは結論づけられない。資料の明確さは高いが、コンセンサス対比の欠落が主要な制約。

## Source Inventory

| source_id | type | locator | title | period_role | timing | used for | source/location |
|---|---|---|---|---|---|---|---|
| `financial_api:NVDA:2027Q1:eps` | financial_api | eps | Financial metrics input | reported_period_actuals | same_period_primary | EarningsQualityAnalyst: EPSはコンセンサスを上回った | Financial metrics input |
| `financial_api:NVDA:2027Q1:revenue` | financial_api | revenue | Financial metrics input | reported_period_actuals | same_period_primary | EarningsQualityAnalyst: 売上はコンセンサスを上回った | Financial metrics input |
| `nvda-f1q27-quarterly-presentation:p9:section-1` | earnings_presentation | nvda-f1q27-quarterly-presentation:p9:section-1 | NVDA F1Q27 Quarterly Presentation | target_period_document | same_period_primary | EarningsQualityAnalyst: 営業費用増加を吸収しつつ営業利益が大きく伸長; EarningsQualityAnalyst: 粗利率が前年同四半期比で大きく改善 | nvda-f1q27-quarterly-presentation:p9:section-1 |
| `nvda-f1q27-quarterly-presentation:p13:section-1` | earnings_presentation | nvda-f1q27-quarterly-presentation:p13:section-1 | NVDA F1Q27 Quarterly Presentation | target_period_document | same_period_primary | EarningsQualityAnalyst: EPSの質を分解するための補助指標が不足 | nvda-f1q27-quarterly-presentation:p13:section-1 |
| `nvda-f1q27-quarterly-presentation:p5:section-1` | earnings_presentation | nvda-f1q27-quarterly-presentation:p5:section-1 | NVDA F1Q27 Quarterly Presentation | target_period_document | same_period_primary | EarningsQualityAnalyst: 粗利率改善の一部は前年の異常費用反動で説明される; ManagementIntentAnalyst: 粗利改善は前年の在庫引当反動の影響を含む | nvda-f1q27-quarterly-presentation:p5:section-1 |
| `financial_api:NVDA:2027Q1:free_cash_flow` | financial_api | free_cash_flow | Financial metrics input | reported_period_actuals | same_period_primary | CashFlowRiskAnalyst: CFO/FCFの前期比較がなくトレンド判定ができない; CashFlowRiskAnalyst: 当期FCFは120億ドルで高水準 | Financial metrics input |
| `financial_api:NVDA:2027Q1:operating_cash_flow` | financial_api | operating_cash_flow | Financial metrics input | reported_period_actuals | same_period_primary | CashFlowRiskAnalyst: 営業CFは150億ドルでFCFを支える | Financial metrics input |
| `financial_api:NVDA:2027Q1:capex` | financial_api | capex | Financial metrics input | reported_period_actuals | same_period_primary | CashFlowRiskAnalyst: CapExは30億ドルで、当期FCFを大きく圧迫していない | Financial metrics input |
| `nvda-f1q27-quarterly-presentation:p8:section-1` | earnings_presentation | nvda-f1q27-quarterly-presentation:p8:section-1 | NVDA F1Q27 Quarterly Presentation | target_period_document | same_period_primary | CashFlowRiskAnalyst: プレゼンでは記録的FCFと投資継続が同時に示された; ManagementIntentAnalyst: FCFと資本還元を同時に強化 | nvda-f1q27-quarterly-presentation:p8:section-1 |
| `nvda-f1q27-quarterly-presentation:p2:section-1` | earnings_presentation | nvda-f1q27-quarterly-presentation:p2:section-1 | NVDA F1Q27 Quarterly Presentation | target_period_document | same_period_primary | CashFlowRiskAnalyst: working capital、cash、debt、maturity、liquidityの指標が欠落; ManagementIntentAnalyst: 供給・需要・在庫・外部依存のリスクを明記 | nvda-f1q27-quarterly-presentation:p2:section-1 |
| `nvda-f1q27-quarterly-presentation:p6:section-1` | earnings_presentation | nvda-f1q27-quarterly-presentation:p6:section-1 | NVDA F1Q27 Quarterly Presentation | target_period_document | same_period_primary | CashFlowRiskAnalyst: 投資・成長機会向け支出はFCF変動要因になりうる; ManagementIntentAnalyst: Opex増加は短期EPSの逆風; ManagementIntentAnalyst: 成長機会対応への投資を明示 | nvda-f1q27-quarterly-presentation:p6:section-1 |
| `nvda-f1q27-quarterly-presentation:p11:section-1` | earnings_presentation | nvda-f1q27-quarterly-presentation:p11:section-1 | NVDA F1Q27 Quarterly Presentation | target_period_document | same_period_primary | GuidanceAnalyst: Q2 FY27の売上高ガイダンスは910億ドル（±2%）と明示; GuidanceAnalyst: Q2 FY27の粗利率・営業費用前提が併記されている; GuidanceAnalyst: 中国向けData Center compute revenueを前提に含めないと明記; ManagementIntentAnalyst: 次四半期も高水準の売上・粗利・費用計画を提示 | nvda-f1q27-quarterly-presentation:p11:section-1 |
| `financial_api:NVDA:2027Q1:eps_consensus` | financial_api | eps_consensus | Financial metrics input | consensus_for_reported_period | same_period_primary | GuidanceAnalyst: guided_period と consensus_for_guided_period が未提供 | Financial metrics input |
| `financial_api:NVDA:2027Q1:revenue_consensus` | financial_api | revenue_consensus | Financial metrics input | consensus_for_reported_period | same_period_primary | GuidanceAnalyst: ガイダンスの定量評価を支える対象期間コンセンサスが欠ける | Financial metrics input |

## Metric Store

| metric | value | unit | fiscal_period | period_role | source | source_ref |
|---|---:|---|---|---|---|---|
| eps | 0.81 | USD/share | 2027Q1 | reported_period_actuals | Financial metrics input (financial_api) | `financial_api:NVDA:2027Q1:eps` |
| eps_consensus | 0.75 | USD/share | 2027Q1 | consensus_for_reported_period | Financial metrics input (financial_api) | `financial_api:NVDA:2027Q1:eps_consensus` |
| revenue | 3.5e+10 | USD | 2027Q1 | reported_period_actuals | Financial metrics input (financial_api) | `financial_api:NVDA:2027Q1:revenue` |
| revenue_consensus | 3.3e+10 | USD | 2027Q1 | consensus_for_reported_period | Financial metrics input (financial_api) | `financial_api:NVDA:2027Q1:revenue_consensus` |
| operating_cash_flow | 1.5e+10 | USD | 2027Q1 | reported_period_actuals | Financial metrics input (financial_api) | `financial_api:NVDA:2027Q1:operating_cash_flow` |
| free_cash_flow | 1.2e+10 | USD | 2027Q1 | reported_period_actuals | Financial metrics input (financial_api) | `financial_api:NVDA:2027Q1:free_cash_flow` |
| capex | 3e+09 | USD | 2027Q1 | reported_period_actuals | Financial metrics input (financial_api) | `financial_api:NVDA:2027Q1:capex` |

## Presentation Metric Hints

- Non-canonical PDF/table extraction candidates; `ambiguous` rows are not promoted or used as facts.

| metric | raw_text | raw_value | value | unit | fiscal_period | period_role | status | source | source_ref |
|---|---|---:|---:|---|---|---|---|---|---|
| revenue_guidance | Revenue $91.0 billion | 91.0 | 91 | USD billion |  |  | parsed | NVDA F1Q27 Quarterly Presentation (earnings_presentation) | `nvda-f1q27-quarterly-presentation:p11:section-1` |

## Missing Data Caveats

| Agent | Severity | Missing data / confidence limit |
|---|---|---|
| EarningsQualityAnalyst | non_blocking | セグメント別売上・ミックスが提供されていないため、売上品質の内訳評価ができない。 |
| EarningsQualityAnalyst | non_blocking | 税率、希薄化株式数の対象四半期の実績指標が不足しており、EPS上振れへの寄与分解ができない。 |
| EarningsQualityAnalyst | non_blocking | 前四半期比較および前年同四半期比較の計算済み指標がなく、margin trend を時系列で限定的にしか確認できない。 |
| EarningsQualityAnalyst | non_blocking | guided_period とそのコンセンサスがないため、将来EPSへの定量的なガイダンス評価はできない。 |
| EarningsQualityAnalyst | material_caveat | FCF/CapExは提示されているが、本ワークフローでは詳細なFCF分析を行わない制約があるため、P&Lからの限定的示唆に留める。 |
| CashFlowRiskAnalyst | material_caveat | 前期比・前年同期比のCFO/FCF/CapEx比較がなく、トレンドの方向性を検証できない |
| CashFlowRiskAnalyst | material_caveat | working capital change の指標がない |
| CashFlowRiskAnalyst | non_blocking | cash、debt、liquidity、maturity profile の指標がない |
| CashFlowRiskAnalyst | material_caveat | guided_period と関連するFCF見通しがない |
| CashFlowRiskAnalyst | non_blocking | balance sheet面の financing constraint を定量評価できない |
| ManagementIntentAnalyst | material_caveat | 管理陣がどの事業領域に対して採用、CapEx、R&D、在庫積み増しをどの程度優先したかの定量的内訳が不足している。 |
| ManagementIntentAnalyst | material_caveat | FCF改善の持続性を確認するための prior year / prior sequential の詳細な比較指標が限定的で、投資増加とのトレードオフを厳密に検証できない。 |
| ManagementIntentAnalyst | material_caveat | guidance の妥当性や consensus との差分は評価対象外のため、経営陣の意図と市場期待のズレは判断していない。 |
| GuidanceAnalyst | material_caveat | guided_period の会社ガイダンス値が routed_context で null のため、対象期間の guidance/consensus 差分を確認できません。 |
| GuidanceAnalyst | material_caveat | EPS と FCF の来期見通しに関する明示的なガイダンス数値が routed_context にありません。 |

## Sources

### EarningsQualityAnalyst
- `financial_api:NVDA:2027Q1:eps` (eps): Financial metrics input — Financial metrics input
- `financial_api:NVDA:2027Q1:revenue` (revenue): Financial metrics input — Financial metrics input
- `nvda-f1q27-quarterly-presentation:p9:section-1` (nvda-f1q27-quarterly-presentation:p9:section-1): NVDA F1Q27 Quarterly Presentation — nvda-f1q27-quarterly-presentation:p9:section-1
- `nvda-f1q27-quarterly-presentation:p13:section-1` (nvda-f1q27-quarterly-presentation:p13:section-1): NVDA F1Q27 Quarterly Presentation — nvda-f1q27-quarterly-presentation:p13:section-1
- `nvda-f1q27-quarterly-presentation:p5:section-1` (nvda-f1q27-quarterly-presentation:p5:section-1): NVDA F1Q27 Quarterly Presentation — nvda-f1q27-quarterly-presentation:p5:section-1
### CashFlowRiskAnalyst
- `financial_api:NVDA:2027Q1:free_cash_flow` (free_cash_flow): Financial metrics input — Financial metrics input
- `financial_api:NVDA:2027Q1:operating_cash_flow` (operating_cash_flow): Financial metrics input — Financial metrics input
- `financial_api:NVDA:2027Q1:capex` (capex): Financial metrics input — Financial metrics input
- `nvda-f1q27-quarterly-presentation:p8:section-1` (nvda-f1q27-quarterly-presentation:p8:section-1): NVDA F1Q27 Quarterly Presentation — nvda-f1q27-quarterly-presentation:p8:section-1
- `nvda-f1q27-quarterly-presentation:p2:section-1` (nvda-f1q27-quarterly-presentation:p2:section-1): NVDA F1Q27 Quarterly Presentation — nvda-f1q27-quarterly-presentation:p2:section-1
- `nvda-f1q27-quarterly-presentation:p6:section-1` (nvda-f1q27-quarterly-presentation:p6:section-1): NVDA F1Q27 Quarterly Presentation — nvda-f1q27-quarterly-presentation:p6:section-1
### ManagementIntentAnalyst
- `nvda-f1q27-quarterly-presentation:p6:section-1` (nvda-f1q27-quarterly-presentation:p6:section-1): NVDA F1Q27 Quarterly Presentation — nvda-f1q27-quarterly-presentation:p6:section-1
- `nvda-f1q27-quarterly-presentation:p8:section-1` (nvda-f1q27-quarterly-presentation:p8:section-1): NVDA F1Q27 Quarterly Presentation — nvda-f1q27-quarterly-presentation:p8:section-1
- `nvda-f1q27-quarterly-presentation:p11:section-1` (nvda-f1q27-quarterly-presentation:p11:section-1): NVDA F1Q27 Quarterly Presentation — nvda-f1q27-quarterly-presentation:p11:section-1
- `nvda-f1q27-quarterly-presentation:p2:section-1` (nvda-f1q27-quarterly-presentation:p2:section-1): NVDA F1Q27 Quarterly Presentation — nvda-f1q27-quarterly-presentation:p2:section-1
- `nvda-f1q27-quarterly-presentation:p5:section-1` (nvda-f1q27-quarterly-presentation:p5:section-1): NVDA F1Q27 Quarterly Presentation — nvda-f1q27-quarterly-presentation:p5:section-1
### GuidanceAnalyst
- `nvda-f1q27-quarterly-presentation:p11:section-1` (nvda-f1q27-quarterly-presentation:p11:section-1): NVDA F1Q27 Quarterly Presentation — nvda-f1q27-quarterly-presentation:p11:section-1
- `financial_api:NVDA:2027Q1:eps_consensus` (eps_consensus): Financial metrics input — Financial metrics input
- `financial_api:NVDA:2027Q1:revenue_consensus` (revenue_consensus): Financial metrics input — Financial metrics input

_This report is an earnings analysis artifact and is not investment advice._