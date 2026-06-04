# Earnings Review: ZS 2026Q3

## Verdict

Neutral

Confidence: 0.73

## Summary

当四半期の売上・EPSはコンセンサスを上回り、非GAAP利益率とFCFもプラスでヘッドラインは良好です。一方で、EPSの上振れ幅は大きくなく、GAAP営業損失が残り、FCFはCapEx前倒しと回収タイミング要因で持続性の裏取りが弱いです。さらに、Q4/FY26ガイダンスは存在するものの、guided_period の consensus がなく市場予想比の良否を定量判定できないため、総合判断は neutral が妥当です。

## Evidence Matrix

| # | Direction | Claim | Evidence value / quote | Interpretation | Source | Timing | Confidence |
|---:|---|---|---|---|---|---|---:|
| 1 | positive | EPSはコンセンサスを上回った | 0.84 USD/share (eps) | reported_period_actualsのEPSは0.84で、consensus_for_reported_periodの0.8を上回っています。ヘッドラインEPSは良好です。 | `financial_api:ZS:2026Q3:eps` / eps | same_period_primary | 0.94 |
| 2 | positive | 売上もコンセンサスを上回った | 700,000,000 USD (revenue) | reported_period_actualsのrevenueは700.0Mで、consensus_for_reported_periodの690.0Mを上回っています。売上面のヘッドラインは良好です。 | `financial_api:ZS:2026Q3:revenue` / revenue | same_period_primary | 0.94 |
| 3 | positive | FCFはプラスで、営業キャッシュも確保 | 80,000,000 USD (free_cash_flow) | reported_period_actualsではoperating_cash_flowが100.0M、free_cash_flowが80.0M、capexが20.0Mです。P&L面から見ても、利益だけでなく現金創出はプラスです。 | `financial_api:ZS:2026Q3:free_cash_flow` / free_cash_flow | same_period_primary | 0.90 |
| 4 | positive | Q4ガイダンスではFCFマージン約22.8%〜23.3%を見込む | 23.05 % (free_cash_flow_margin_guidance) | 会社はQ4 26のFCFマージンを約22.8%〜23.3%と示しており、短期的にはFCFの改善余地があることを示唆する。ガイダンスは将来FCFの方向感としては前向き。 | `zs-2026q3-shareholder-letter:p19:section-1` / zs-2026q3-shareholder-letter:p19:section-1 | same_period_primary | 0.67 |
| 5 | risk | Q4にCapExが前倒しされ、2026年のCapEx比率は上昇見通し | 会社はデータセンター設備やBranchアプライアンスの投資を前倒しし、Q4のCapExが高くなり、通期2026年のCapEx比率は従来想定のmid single-digitsからhigh single-digitsへ上がると説明した。さらに2027年は2026年比で最大200bpの上昇を見込むとしており、FCF改善の継続には逆風。 | 会社はデータセンター設備やBranchアプライアンスの投資を前倒しし、Q4のCapExが高くなり、通期2026年のCapEx比率は従来想定のmid single-digitsからhigh single-digitsへ上がると説明した。さらに2027年は2026年比で最大200bpの上昇を見込むとしており、FCF改善の継続には逆風。 | `zs-2026q3-shareholder-letter:p18:section-1` / zs-2026q3-shareholder-letter:p18:section-1 | same_period_primary | 0.80 |
| 6 | negative | GAAP営業損失が続いている | AppendixではGAAP loss from operationsがQ3 26で-29.640Mとなっており、会計ベースでは依然として赤字です。非GAAP利益率は強い一方、GAAPベースの利益質にはなお課題があります。 | AppendixではGAAP loss from operationsがQ3 26で-29.640Mとなっており、会計ベースでは依然として赤字です。非GAAP利益率は強い一方、GAAPベースの利益質にはなお課題があります。 | `zs-2026q3-shareholder-letter:p27:section-1` / zs-2026q3-shareholder-letter:p27:section-1 | same_period_primary | 0.78 |
| 7 | risk | 販売リーダー交代で移行期の不確実性がある | Q4/FY26見通しの説明で、期末に営業リーダー2名が退社し、1名は後任確定済み、もう1名は採用最終段階だが、ガイダンスは移行期を踏まえて慎重にしていると述べている。営業実行力や案件進行に一時的な摩擦が生じる可能性がある。 | Q4/FY26見通しの説明で、期末に営業リーダー2名が退社し、1名は後任確定済み、もう1名は採用最終段階だが、ガイダンスは移行期を踏まえて慎重にしていると述べている。営業実行力や案件進行に一時的な摩擦が生じる可能性がある。 | `zs-2026q3-shareholder-letter:p19:section-1` / zs-2026q3-shareholder-letter:p19:section-1 | same_period_primary | 0.63 |

## Agent Analysis

- **EarningsQualityAnalyst** (mixed, confidence 0.66): ヘッドラインではEPSと売上がコンセンサス超えで、非GAAP利益率も高水準維持、営業利益も前年同四半期比で拡大しています。一方、GAAP営業損失は残り、税率・株式報酬・一時項目・セグメントの分解が不足しているため、EPS上振れの持続性評価は中程度の確信に留めるべきです。FCFはプラスですが、FCFの持続性を裏付ける詳細なキャッシュドライバーは不足しています。
- **CashFlowRiskAnalyst** (neutral, confidence 0.58): CFO/FCFは当四半期ベースではプラスで、CapExも現時点では管理可能だが、将来FCFの改善はQ4に前倒しされるCapEx増加と回収タイミング要因で不確実性が残る。バランスシート面では現金と負債の水準は示される一方、満期・流動性詳細がなく、資金調達制約の強さは判定保留。EPSへの示唆は、キャッシュ創出は現時点で大きな制約を示さないが、CapEx増加が続く場合はFCFを通じた制約が強まりうる、という限定的な見方が妥当。
- **ManagementIntentAnalyst** (mixed, confidence 0.64): 経営陣は、Zero Trust/AI/データセキュリティを軸に、Z-Flex、GSI、クラウドマーケットプレイス、モジュール拡張でプラットフォーム浸透を深める意図が強い。Q3は成長と利益率が両立しており、営業利益率とFCFは一定の強さを示すが、Q4のcapex前倒しと営業体制の交代が短期FCF/EPSのノイズ要因。中期では、AI関連と顧客拡大がEPS/FCF改善余地を持つ一方、買収統合・供給コスト上昇・実行リスクが反対根拠。
- **GuidanceAnalyst** (neutral, confidence 0.58): 対象四半期の実績は売上・EPSともにコンセンサス超えで良好。一方、将来 guidance はQ4/FY26で提示されているが、guided_period の consensus がなく予想比評価は未確定。資料上は営業体制の移行とcapex上振れが主な下方リスクで、EPS/FCF は売上維持と投資増の吸収が達成条件。guidance の強気/保守性は現時点では unclear で、revision risk は『transitionとcapex増加次第』という定性的評価にとどまる。

## Positive Evidence

- EPSはコンセンサスを上回った
- 売上もコンセンサスを上回った
- FCFはプラスで、営業キャッシュも確保
- Q4ガイダンスではFCFマージン約22.8%〜23.3%を見込む

## Negative Evidence

- Q4にCapExが前倒しされ、2026年のCapEx比率は上昇見通し
- GAAP営業損失が続いている
- 販売リーダー交代で移行期の不確実性がある

## EPS Outlook

やや前向きだが確度は中程度

Reason: EPSは当四半期にコンセンサス超えで、非GAAP利益率と営業利益の拡大も支えています。ただし、上振れ幅は小幅で、GAAP営業損失が残り、税率・株式報酬・一時項目などの分解情報が不足しているため、次四半期以降の継続的改善を強く断定するには材料不足です。

## FCF Outlook

やや前向きだが不確実性が残る

Reason: 当四半期のFCFはプラスで、Q4ガイダンスでもFCFマージン改善が示されています。一方で、CapEx前倒し、回収タイミング要因、working capitalの定量不足があり、FCF改善の持続性はまだ十分に裏づけられていません。

## Bull Case

今回の決算は、売上とEPSがコンセンサスを上回り、非GAAP利益率も高水準を維持し、当四半期のFCFもプラスである点から、ヘッドラインとしてはgood と評価しやすい。加えて、経営陣はZero Trust/AI/データセキュリティを軸にプラットフォーム拡張を進める意図を示しており、中期のEPS・FCF改善余地を示唆している。一方で、GAAP営業損失の継続、FCFの質を分解する情報不足、Q4以降のCapEx上振れと営業体制移行リスクは残るため、強さは中程度にとどめる。

## Bear Case

今回の決算はヘッドラインでは売上・EPSともにコンセンサス超えで一見良好だが、GAAP営業損失が残り、EPSの上振れ幅は小さく、FCFも当四半期は黒字でも持続性の裏取りが弱い。さらに、Q4以降のCapEx前倒しと営業体制移行が示されており、短期の利益・キャッシュ創出は維持できても、次四半期以降の改善確度は限定的とみるのが妥当で、総合評価はneutral寄りだが下方リスクが残る。

## Analyst Brief

ヘッドラインではEPSと売上がコンセンサス超えで、非GAAP利益率も高水準維持、営業利益も前年同四半期比で拡大しています。一方、GAAP営業損失は残り、税率・株式報酬・一時項目・セグメントの分解が不足しているため、EPS上振れの持続性評価は中程度の確信に留めるべきです。FCFはプラスですが、FCFの持続性を裏付ける詳細なキャッシュドライバーは不足しています。 CFO/FCFは当四半期ベースではプラスで、CapExも現時点では管理可能だが、将来FCFの改善はQ4に前倒しされるCapEx増加と回収タイミング要因で不確実性が残る。バランスシート面では現金と負債の水準は示される一方、満期・流動性詳細がなく、資金調達制約の強さは判定保留。EPSへの示唆は、キャッシュ創出は現時点で大きな制約を示さないが、CapEx増加が続く場合はFCFを通じた制約が強まりうる、という限定的な見方が妥当。 経営陣は、Zero Trust/AI/データセキュリティを軸に、Z-Flex、GSI、クラウドマーケットプレイス、モジュール拡張でプラットフォーム浸透を深める意図が強い。Q3は成長と利益率が両立しており、営業利益率とFCFは一定の強さを示すが、Q4のcapex前倒しと営業体制の交代が短期FCF/EPSのノイズ要因。中期では、AI関連と顧客拡大がEPS/FCF改善余地を持つ一方、買収統合・供給コスト上昇・実行リスクが反対根拠。 対象四半期の実績は売上・EPSともにコンセンサス超えで良好。一方、将来 guidance はQ4/FY26で提示されているが、guided_period の consensus がなく予想比評価は未確定。資料上は営業体制の移行とcapex上振れが主な下方リスクで、EPS/FCF は売上維持と投資増の吸収が達成条件。guidance の強気/保守性は現時点では unclear で、revision risk は『transitionとcapex増加次第』という定性的評価にとどまる。

## Source Inventory

| source_id | type | locator | title | period_role | timing | used for | source/location |
|---|---|---|---|---|---|---|---|
| `financial_api:ZS:2026Q3:eps` | financial_api | eps | Financial metrics input | reported_period_actuals | same_period_primary | EarningsQualityAnalyst: EPSの上振れ幅は大きくはない; EarningsQualityAnalyst: EPSはコンセンサスを上回った; GuidanceAnalyst: Q3実績EPSはコンセンサス超え | Financial metrics input |
| `financial_api:ZS:2026Q3:revenue` | financial_api | revenue | Financial metrics input | reported_period_actuals | same_period_primary | EarningsQualityAnalyst: 売上もコンセンサスを上回った; GuidanceAnalyst: Q3実績は売上がコンセンサス超え | Financial metrics input |
| `zs-2026q3-shareholder-letter:p27:section-1` | earnings_presentation | zs-2026q3-shareholder-letter:p27:section-1 | ZS 2026 Q3 Shareholder Letter | target_period_document | same_period_primary | EarningsQualityAnalyst: GAAP営業損失が続いている; EarningsQualityAnalyst: 営業利益は前年同四半期比で増加; EarningsQualityAnalyst: 非GAAP粗利率と営業利益率は高水準を維持 | zs-2026q3-shareholder-letter:p27:section-1 |
| `financial_api:ZS:2026Q3:free_cash_flow` | financial_api | free_cash_flow | Financial metrics input | reported_period_actuals | same_period_primary | EarningsQualityAnalyst: FCFの質を分解する情報が限定的; EarningsQualityAnalyst: FCFはプラスで、営業キャッシュも確保 | Financial metrics input |
| `zs-2026q3-shareholder-letter:p25:section-1` | earnings_presentation | zs-2026q3-shareholder-letter:p25:section-1 | ZS 2026 Q3 Shareholder Letter | target_period_document | same_period_primary | EarningsQualityAnalyst: 売上以外の収益性ドライバーの詳細が不足 | zs-2026q3-shareholder-letter:p25:section-1 |
| `financial_api:ZS:2026Q3:operating_cash_flow` | financial_api | operating_cash_flow | Financial metrics input | reported_period_actuals | same_period_primary | CashFlowRiskAnalyst: Q3の営業キャッシュフローとFCFはプラスで、FCFの水準は良好 | Financial metrics input |
| `financial_api:ZS:2026Q3:capex` | financial_api | capex | Financial metrics input | reported_period_actuals | same_period_primary | CashFlowRiskAnalyst: CapExは2,000万ドルで、当四半期のFCFを大きく圧迫していない | Financial metrics input |
| `zs-2026q3-shareholder-letter:p18:section-1` | earnings_presentation | zs-2026q3-shareholder-letter:p18:section-1 | ZS 2026 Q3 Shareholder Letter | target_period_document | same_period_primary | CashFlowRiskAnalyst: FCFマージン低下の要因として回収タイミングが挙げられている; CashFlowRiskAnalyst: Q4にCapExが前倒しされ、2026年のCapEx比率は上昇見通し; CashFlowRiskAnalyst: 会社はQ3のFCFマージン16.0%と年初来29%を開示; CashFlowRiskAnalyst: 流動性・負債の定量評価に必要な詳細が不足; GuidanceAnalyst: ガイダンスには遷移リスクとcapex上振れ要因が明示; ManagementIntentAnalyst: FCFは当期も一定水準を維持し、資本効率はまだ機能; ManagementIntentAnalyst: FCFマージンは前年より低下している; ManagementIntentAnalyst: Q4にcapexが前倒しされ短期FCFを圧迫 | zs-2026q3-shareholder-letter:p18:section-1 |
| `zs-2026q3-shareholder-letter:p19:section-1` | earnings_presentation | zs-2026q3-shareholder-letter:p19:section-1 | ZS 2026 Q3 Shareholder Letter | target_period_document | same_period_primary | CashFlowRiskAnalyst: Q4ガイダンスではFCFマージン約22.8%〜23.3%を見込む; GuidanceAnalyst: Q4/FY26のガイダンス値が資料内に記載; GuidanceAnalyst: guidance の対象期間が明示されるが数値比較用の前提は不足; GuidanceAnalyst: guided_period の consensus がなく上振れ/下振れ判定ができない; ManagementIntentAnalyst: 販売リーダー交代で移行期の不確実性がある | zs-2026q3-shareholder-letter:p19:section-1 |
| `zs-2026q3-shareholder-letter:p32:section-1` | earnings_presentation | zs-2026q3-shareholder-letter:p32:section-1 | ZS 2026 Q3 Shareholder Letter | target_period_document | same_period_primary | ManagementIntentAnalyst: 成長の中核をZero Trust、AI Protect、Data Securityに置く | zs-2026q3-shareholder-letter:p32:section-1 |
| `zs-2026q3-shareholder-letter:p16:section-1` | earnings_presentation | zs-2026q3-shareholder-letter:p16:section-1 | ZS 2026 Q3 Shareholder Letter | target_period_document | same_period_primary | ManagementIntentAnalyst: Z-Flexとアカウント拡大で顧客浸透を深める意図 | zs-2026q3-shareholder-letter:p16:section-1 |
| `zs-2026q3-shareholder-letter:p14:section-1` | earnings_presentation | zs-2026q3-shareholder-letter:p14:section-1 | ZS 2026 Q3 Shareholder Letter | target_period_document | same_period_primary | ManagementIntentAnalyst: Q3は成長と収益性を両立 | zs-2026q3-shareholder-letter:p14:section-1 |
| `zs-2026q3-shareholder-letter:p6:section-1` | earnings_presentation | zs-2026q3-shareholder-letter:p6:section-1 | ZS 2026 Q3 Shareholder Letter | target_period_document | same_period_primary | ManagementIntentAnalyst: AI/新製品とパートナー網を成長レバーとして拡大 | zs-2026q3-shareholder-letter:p6:section-1 |
| `zs-2026q3-shareholder-letter:p35:section-1` | earnings_presentation | zs-2026q3-shareholder-letter:p35:section-1 | ZS 2026 Q3 Shareholder Letter | target_period_document | same_period_primary | ManagementIntentAnalyst: 成長の一部は買収と高投資テーマに依存 | zs-2026q3-shareholder-letter:p35:section-1 |

## Metric Store

| metric | value | unit | fiscal_period | period_role | source | source_ref |
|---|---:|---|---|---|---|---|
| eps | 0.84 | USD/share | 2026Q3 | reported_period_actuals | Financial metrics input (financial_api) | `financial_api:ZS:2026Q3:eps` |
| eps_consensus | 0.8 | USD/share | 2026Q3 | consensus_for_reported_period | Financial metrics input (financial_api) | `financial_api:ZS:2026Q3:eps_consensus` |
| revenue | 7e+08 | USD | 2026Q3 | reported_period_actuals | Financial metrics input (financial_api) | `financial_api:ZS:2026Q3:revenue` |
| revenue_consensus | 6.9e+08 | USD | 2026Q3 | consensus_for_reported_period | Financial metrics input (financial_api) | `financial_api:ZS:2026Q3:revenue_consensus` |
| operating_cash_flow | 1e+08 | USD | 2026Q3 | reported_period_actuals | Financial metrics input (financial_api) | `financial_api:ZS:2026Q3:operating_cash_flow` |
| free_cash_flow | 8e+07 | USD | 2026Q3 | reported_period_actuals | Financial metrics input (financial_api) | `financial_api:ZS:2026Q3:free_cash_flow` |
| capex | 2e+07 | USD | 2026Q3 | reported_period_actuals | Financial metrics input (financial_api) | `financial_api:ZS:2026Q3:capex` |

## Presentation Metric Hints

- Non-canonical PDF/table extraction candidates; `ambiguous` rows are not promoted or used as facts.

| metric | raw_text | raw_value | value | unit | fiscal_period | period_role | status | source | source_ref |
|---|---|---:|---:|---|---|---|---|---|---|
| revenue_guidance | revenue 2 | 2 | 2 |  |  |  | ambiguous | ZS 2026 Q3 Shareholder Letter (earnings_presentation) | `zs-2026q3-shareholder-letter:p14:section-1` |
| eps_guidance | EPS $1.00 | 1.00 | 1 | USD/share |  |  | ambiguous | ZS 2026 Q3 Shareholder Letter (earnings_presentation) | `zs-2026q3-shareholder-letter:p14:section-1` |
| revenue_guidance | revenue of approximately $137 million | 137 | 137 | USD million |  |  | parsed | ZS 2026 Q3 Shareholder Letter (earnings_presentation) | `zs-2026q3-shareholder-letter:p19:section-1` |

## Missing Data Caveats

| Agent | Severity | Missing data / confidence limit |
|---|---|---|
| EarningsQualityAnalyst | non_blocking | prior_sequential_period_actuals がなく、直前四半期との margin / operating leverage / revenue trend 比較ができません。 |
| EarningsQualityAnalyst | non_blocking | prior_year_period がなく、前年同四半期比較による収益性の継続性を確認できません。 |
| EarningsQualityAnalyst | non_blocking | segment_metrics が空で、segment mix が EPS/利益率に与えた影響を評価できません。 |
| EarningsQualityAnalyst | non_blocking | tax rate、share count、stock-based compensation、one-time item の canonical 指標がなく、EPS beat の質を十分に分解できません。 |
| EarningsQualityAnalyst | non_blocking | gross margin / operating margin の canonical metric は不足しており、開示資料ベースの定性的確認にとどまります。 |
| EarningsQualityAnalyst | material_caveat | revenue_consensus はあるが、同等に使える margin/expense の precomputed 指標が不足しているため、売上品質と収益性の因果は限定的にしか示せません。 |
| CashFlowRiskAnalyst | material_caveat | 前期比・前年同期比のCFO/FCFトレンドが入力にないため、trendの方向を厳密に確認できない。 |
| CashFlowRiskAnalyst | material_caveat | working capitalの定量指標がないため、FCF変動が一時要因か構造要因かを分解できない。 |
| CashFlowRiskAnalyst | non_blocking | 流動性の詳細、満期構成、借換え条件、財務制約の定量情報がないため、financing riskを十分に評価できない。 |
| CashFlowRiskAnalyst | material_caveat | guidanceのFCFはQ4のみで、通期ベースの詳細なFCFガイダンス数値はこの入力だけでは限定的。 |
| ManagementIntentAnalyst | material_caveat | guidance-vs-consensus の評価は要求範囲外のため行っていない。 |
| ManagementIntentAnalyst | material_caveat | 投資額、採用計画、R&D計画の定量値が不足しており、EPS/FCF への影響は定性的評価にとどまる。 |
| ManagementIntentAnalyst | non_blocking | 買収統合費用や更新率、解約率など、長期収益化を裏づける補助指標が不足している。 |
| GuidanceAnalyst | material_caveat | guided_period に対応する precomputed guidance delta がないため、conservative / balanced / aggressive の厳密判定はできません。 |
| GuidanceAnalyst | material_caveat | presentation_metric_hints は存在しますが、canonical fact としては guidance section の確認補助に限られ、追加の定量裏取りには使えません。 |

## Sources

### EarningsQualityAnalyst
- `financial_api:ZS:2026Q3:eps` (eps): Financial metrics input — Financial metrics input
- `financial_api:ZS:2026Q3:revenue` (revenue): Financial metrics input — Financial metrics input
- `zs-2026q3-shareholder-letter:p27:section-1` (zs-2026q3-shareholder-letter:p27:section-1): ZS 2026 Q3 Shareholder Letter — zs-2026q3-shareholder-letter:p27:section-1
- `financial_api:ZS:2026Q3:free_cash_flow` (free_cash_flow): Financial metrics input — Financial metrics input
- `zs-2026q3-shareholder-letter:p25:section-1` (zs-2026q3-shareholder-letter:p25:section-1): ZS 2026 Q3 Shareholder Letter — zs-2026q3-shareholder-letter:p25:section-1
### CashFlowRiskAnalyst
- `financial_api:ZS:2026Q3:operating_cash_flow` (operating_cash_flow): Financial metrics input — Financial metrics input
- `financial_api:ZS:2026Q3:capex` (capex): Financial metrics input — Financial metrics input
- `zs-2026q3-shareholder-letter:p18:section-1` (zs-2026q3-shareholder-letter:p18:section-1): ZS 2026 Q3 Shareholder Letter — zs-2026q3-shareholder-letter:p18:section-1
- `zs-2026q3-shareholder-letter:p19:section-1` (zs-2026q3-shareholder-letter:p19:section-1): ZS 2026 Q3 Shareholder Letter — zs-2026q3-shareholder-letter:p19:section-1
### ManagementIntentAnalyst
- `zs-2026q3-shareholder-letter:p32:section-1` (zs-2026q3-shareholder-letter:p32:section-1): ZS 2026 Q3 Shareholder Letter — zs-2026q3-shareholder-letter:p32:section-1
- `zs-2026q3-shareholder-letter:p16:section-1` (zs-2026q3-shareholder-letter:p16:section-1): ZS 2026 Q3 Shareholder Letter — zs-2026q3-shareholder-letter:p16:section-1
- `zs-2026q3-shareholder-letter:p14:section-1` (zs-2026q3-shareholder-letter:p14:section-1): ZS 2026 Q3 Shareholder Letter — zs-2026q3-shareholder-letter:p14:section-1
- `zs-2026q3-shareholder-letter:p18:section-1` (zs-2026q3-shareholder-letter:p18:section-1): ZS 2026 Q3 Shareholder Letter — zs-2026q3-shareholder-letter:p18:section-1
- `zs-2026q3-shareholder-letter:p6:section-1` (zs-2026q3-shareholder-letter:p6:section-1): ZS 2026 Q3 Shareholder Letter — zs-2026q3-shareholder-letter:p6:section-1
- `zs-2026q3-shareholder-letter:p19:section-1` (zs-2026q3-shareholder-letter:p19:section-1): ZS 2026 Q3 Shareholder Letter — zs-2026q3-shareholder-letter:p19:section-1
- `zs-2026q3-shareholder-letter:p35:section-1` (zs-2026q3-shareholder-letter:p35:section-1): ZS 2026 Q3 Shareholder Letter — zs-2026q3-shareholder-letter:p35:section-1
### GuidanceAnalyst
- `financial_api:ZS:2026Q3:revenue` (revenue): Financial metrics input — Financial metrics input
- `financial_api:ZS:2026Q3:eps` (eps): Financial metrics input — Financial metrics input
- `zs-2026q3-shareholder-letter:p19:section-1` (zs-2026q3-shareholder-letter:p19:section-1): ZS 2026 Q3 Shareholder Letter — zs-2026q3-shareholder-letter:p19:section-1
- `zs-2026q3-shareholder-letter:p18:section-1` (zs-2026q3-shareholder-letter:p18:section-1): ZS 2026 Q3 Shareholder Letter — zs-2026q3-shareholder-letter:p18:section-1

_This report is an earnings analysis artifact and is not investment advice._