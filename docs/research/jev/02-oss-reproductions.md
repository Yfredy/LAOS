# 02 · Jev 开源复现（本次调研核心文档）

> **命门**：`复现` 与 `复现(单token打分)` 必须区分（口径 J9）。
> 前者真训非自回归决策头（需自训/权重）；后者只借现成 LM 首 token logits 打分。
> 不区分会得出「端侧跑 Jev 只要 15 ms」的错结论。

## 2.1 真复现（非自回归决策头，需自训/权重）

| 项目 | 类别 | 星数 | 语言 | 许可 | 运行时依赖 | 端侧可跑 | 原语 | 报告延迟 | laos 落点 | 验证状态 | 来源 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TheoLeeCJ/SemIf | 复现 | 2286 | Python | MIT | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/TheoLeeCJ/SemIf |
| TianyuCodings/NanoJev | 复现 | 1309 | Python | MIT | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/TianyuCodings/NanoJev |
| mizorewww/laya-mlx | 复现 | 1114 | Python | Apache-2.0 | 未知 | no | 组合 | 7–14 ms 未实测 | 漏斗③蒸馏（Apple Silicon 限定） | 仅README | https://github.com/mizorewww/laya-mlx |
| bespokelabsai/nimble | 复现 | 944 | Python | 未知 | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/bespokelabsai/nimble |
| jaredpalmer/kev | 复现 | 805 | Python | Apache-2.0 | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/jaredpalmer/kev |
| logan-markewich/jeff | 复现 | 156 | Python | MIT | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/logan-markewich/jeff |
| Heman10x-NGU/openJev-verdict-2.0 | 复现 | 153 | Python | NOASSERTION | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/Heman10x-NGU/openJev-verdict-2.0 |
| wfzyx/von | 复现 | 117 | Python | Apache-2.0 | 未知 | unknown(未实测) | 组合 | 15 ms 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/wfzyx/von |
| kshetrajna12/reflex | 复现 | 84 | Python | MIT | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/kshetrajna12/reflex |
| daseinlabs/open-jev | 复现 | 64 | Python | 未知 | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/daseinlabs/open-jev |
| Heman10x-NGU/Verdict-open-jev | 复现 | 33 | Python | NOASSERTION | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/Heman10x-NGU/Verdict-open-jev |
| zhihz/openjev | 复现 | 19 | Python | NOASSERTION | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/zhihz/openjev |
| Argos1111/jev_local | 复现 | 17 | Python | 未知 | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/Argos1111/jev_local |
| mithalouni/system-one-open | 复现 | 17 | Python | NOASSERTION | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/mithalouni/system-one-open |
| IamBusy/OpenJev-Vision | 复现 | 16 | Python | Apache-2.0 | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/IamBusy/OpenJev-Vision |
| genai-craft/openvons | 复现 | 11 | Python | NOASSERTION | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/genai-craft/openvons |
| abhixhek/jevcal | 复现 | 8 | Python | MIT | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/abhixhek/jevcal |
| receptron/laya | 复现 | 8 | TypeScript | MIT | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/receptron/laya |
| intikhab49/open-jev-typed-decision-engine | 复现 | 5 | Python | Apache-2.0 | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/intikhab49/open-jev-typed-decision-engine |
| alexj11324/open-jev-approvals | 复现 | 3 | Go | MIT | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/alexj11324/open-jev-approvals |
| jlt-commons/lev | 复现 | 3 | Clojure | Apache-2.0 | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/jlt-commons/lev |
| harrymunro/decision-first | 复现 | 2 | Python | MIT | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/harrymunro/decision-first |
| ddfeyes/jev-mode | 复现 | 2 | Python | MIT | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/ddfeyes/jev-mode |
| TypeSafeAI/clarity-judge | 复现 | 2 | TypeScript | 未知 | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/TypeSafeAI/clarity-judge |
| yzfly/edgejev | 复现 | 2 | Python | NOASSERTION | 未知 | yes | 组合 | 15.6 ms 未实测 | 漏斗③蒸馏 / 漏斗①触发（候选） | 仅README | https://github.com/yzfly/edgejev |
| apiplant/laya-rs | 复现 | 2 | Rust | 未知 | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/apiplant/laya-rs |
| jgridifier/jev-research-eval | 复现 | 2 | HTML | NOASSERTION | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/jgridifier/jev-research-eval |
| aovestdipaperino/laya-rust | 复现 | 1 | Rust | Apache-2.0 | rust | yes | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/aovestdipaperino/laya-rust |
| connectedGraph/claude-jev-warden | 复现 | 1 | HTML | MIT | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/connectedGraph/claude-jev-warden |
| mkeco/Cerebellum-2B | 复现 | 1 | Python | NOASSERTION | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/mkeco/Cerebellum-2B |
| DECRUX9812/openjev-lm | 复现 | 1 | Python | NOASSERTION | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/DECRUX9812/openjev-lm |
| logicrw/ask-jev | 复现 | 1 | Python | GPL-3.0 | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/logicrw/ask-jev |
| sw-ml-study/demo-decision-model | 复现 | 0 | Rust | MIT | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/sw-ml-study/demo-decision-model |
| UpHash-Network/mini-jev | 复现 | 0 | Python | MIT | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/UpHash-Network/mini-jev |
| syedabbasshaheer-art/jev-atlas | 复现 | 0 | HTML | MIT | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/syedabbasshaheer-art/jev-atlas |
| cyberumut/jev-bonsai-2-27B | 复现 | 0 | Python | NOASSERTION | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/cyberumut/jev-bonsai-2-27B |
| m-ahmed-elbeskeri/verdict | 复现 | 0 | Python | MIT | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/m-ahmed-elbeskeri/verdict |
| fatihsoysalcom/non-autoregressive-decision-model-simulation | 复现 | 0 | 未知 | MIT | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/fatihsoysalcom/non-autoregressive-decision-model-simulation |
| JonnyKreng/lidarr-decision-import | 复现 | 0 | Python | 未知 | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/JonnyKreng/lidarr-decision-import |
| allenporter/home-assistant-laya | 复现 | 0 | Python | Apache-2.0 | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/allenporter/home-assistant-laya |
| shantanugoel/laya-plays-doom | 复现 | 0 | Python | 未知 | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/shantanugoel/laya-plays-doom |
| ian-cowley/Glacier.Clavier | 复现 | 0 | C# | MIT | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/ian-cowley/Glacier.Clavier |

## 2.2 复现(单token打分)（借 LM 首 token logits，无需自训）

| 项目 | 类别 | 星数 | 语言 | 许可 | 运行时依赖 | 端侧可跑 | 原语 | 报告延迟 | laos 落点 | 验证状态 | 来源 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| featherless-ai/simple-jev | 复现(单token打分) | 371 | Python | 未知 | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏（范式参考） | 仅README | https://github.com/featherless-ai/simple-jev |
| Yinsongxu/LLM2Jev | 复现(单token打分) | 63 | Python | Apache-2.0 | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏（范式参考，非真复现） | 仅README | https://github.com/Yinsongxu/LLM2Jev |
| r-ms/mini-jev | 复现(单token打分) | 29 | Python | MIT | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏（借用基座 LM 首 token） | 仅README | https://github.com/r-ms/mini-jev |
| Micha0827/snapjudge | 复现(单token打分) | 5 | Python | MIT | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏（借用基座 LM 首 token） | 仅README | https://github.com/Micha0827/snapjudge |
| codesoda/openjev-rs | 复现(单token打分) | 0 | HTML | MIT | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏（借用基座 LM 首 token） | 仅README | https://github.com/codesoda/openjev-rs |
| Embodied-AI-System/Qwen3.5-OneForward | 复现(单token打分) | 0 | Python | Apache-2.0 | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏（借用基座 LM 首 token） | 仅README | https://github.com/Embodied-AI-System/Qwen3.5-OneForward |
| Wickypolineni/gemma-jev | 复现(单token打分) | 0 | Python | 未知 | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏（借用基座 LM 首 token） | 仅README | https://github.com/Wickypolineni/gemma-jev |
| gopalanj/jevons | 复现(单token打分) | 0 | Python | MIT | 未知 | unknown(未实测) | 组合 | 未实测 | 漏斗③蒸馏（借用基座 LM 首 token） | 仅README | https://github.com/gopalanj/jevons |

## 2.3 每条复现的「四问核查」

> 四问：①是否真非自回归 ②基座模型与参数量 ③是否需要自训练 ④许可。查不到写 未知。

- **TheoLeeCJ/SemIf** — ①非自回归：是（非自回归决策头）；②基座/参数量：开放模型；③需自训：是（需自训/提供权重）；④许可：MIT
- **TianyuCodings/NanoJev** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **mizorewww/laya-mlx** — ①非自回归：是（非自回归决策头）；②基座/参数量：Laya/MLX；③需自训：是（需自训/提供权重）；④许可：Apache-2.0
- **bespokelabsai/nimble** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：未知
- **jaredpalmer/kev** — ①非自回归：是（非自回归决策头）；②基座/参数量：Qwen2.5-0.5B；③需自训：是（需自训/提供权重）；④许可：Apache-2.0
- **logan-markewich/jeff** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **Heman10x-NGU/openJev-verdict-2.0** — ①非自回归：是（非自回归决策头）；②基座/参数量：ModernBERT 151M；③需自训：是（需自训/提供权重）；④许可：NOASSERTION
- **wfzyx/von** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：Apache-2.0
- **kshetrajna12/reflex** — ①非自回归：是（非自回归决策头）；②基座/参数量：Qwen3.5；③需自训：是（需自训/提供权重）；④许可：MIT
- **daseinlabs/open-jev** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：未知
- **Heman10x-NGU/Verdict-open-jev** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：NOASSERTION
- **zhihz/openjev** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：NOASSERTION
- **Argos1111/jev_local** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：未知
- **mithalouni/system-one-open** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：NOASSERTION
- **IamBusy/OpenJev-Vision** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：Apache-2.0
- **genai-craft/openvons** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：NOASSERTION
- **abhixhek/jevcal** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **receptron/laya** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **intikhab49/open-jev-typed-decision-engine** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：Apache-2.0
- **alexj11324/open-jev-approvals** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **jlt-commons/lev** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：Apache-2.0
- **harrymunro/decision-first** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **ddfeyes/jev-mode** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **TypeSafeAI/clarity-judge** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：未知
- **yzfly/edgejev** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：NOASSERTION
- **apiplant/laya-rs** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：未知
- **jgridifier/jev-research-eval** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：NOASSERTION
- **aovestdipaperino/laya-rust** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：Apache-2.0
- **connectedGraph/claude-jev-warden** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **mkeco/Cerebellum-2B** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：NOASSERTION
- **DECRUX9812/openjev-lm** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：NOASSERTION
- **logicrw/ask-jev** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：GPL-3.0
- **sw-ml-study/demo-decision-model** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **UpHash-Network/mini-jev** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **syedabbasshaheer-art/jev-atlas** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **cyberumut/jev-bonsai-2-27B** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：NOASSERTION
- **m-ahmed-elbeskeri/verdict** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **fatihsoysalcom/non-autoregressive-decision-model-simulation** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **JonnyKreng/lidarr-decision-import** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：未知
- **allenporter/home-assistant-laya** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：Apache-2.0
- **shantanugoel/laya-plays-doom** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：未知
- **ian-cowley/Glacier.Clavier** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **featherless-ai/simple-jev** — ①非自回归：否（借 LM 首 token logits）；②基座/参数量：未知；③需自训：否（依赖现成 LM）；④许可：未知
- **Yinsongxu/LLM2Jev** — ①非自回归：否（借 LM 首 token logits）；②基座/参数量：未知；③需自训：否（依赖现成 LM）；④许可：Apache-2.0
- **r-ms/mini-jev** — ①非自回归：否（借 LM 首 token logits）；②基座/参数量：未知；③需自训：否（依赖现成 LM）；④许可：MIT
- **Micha0827/snapjudge** — ①非自回归：否（借 LM 首 token logits）；②基座/参数量：未知；③需自训：否（依赖现成 LM）；④许可：MIT
- **codesoda/openjev-rs** — ①非自回归：否（借 LM 首 token logits）；②基座/参数量：未知；③需自训：否（依赖现成 LM）；④许可：MIT
- **Embodied-AI-System/Qwen3.5-OneForward** — ①非自回归：否（借 LM 首 token logits）；②基座/参数量：未知；③需自训：否（依赖现成 LM）；④许可：Apache-2.0
- **Wickypolineni/gemma-jev** — ①非自回归：否（借 LM 首 token logits）；②基座/参数量：未知；③需自训：否（依赖现成 LM）；④许可：未知
- **gopalanj/jevons** — ①非自回归：否（借 LM 首 token logits）；②基座/参数量：未知；③需自训：否（依赖现成 LM）；④许可：MIT
- **TheoLeeCJ/SemIf** — ①非自回归：是（非自回归决策头）；②基座/参数量：开放模型；③需自训：是（需自训/提供权重）；④许可：MIT
- **TianyuCodings/NanoJev** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **mizorewww/laya-mlx** — ①非自回归：是（非自回归决策头）；②基座/参数量：Laya/MLX；③需自训：是（需自训/提供权重）；④许可：Apache-2.0
- **bespokelabsai/nimble** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：未知
- **jaredpalmer/kev** — ①非自回归：是（非自回归决策头）；②基座/参数量：Qwen2.5-0.5B；③需自训：是（需自训/提供权重）；④许可：Apache-2.0
- **logan-markewich/jeff** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **Heman10x-NGU/openJev-verdict-2.0** — ①非自回归：是（非自回归决策头）；②基座/参数量：ModernBERT 151M；③需自训：是（需自训/提供权重）；④许可：NOASSERTION
- **wfzyx/von** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：Apache-2.0
- **kshetrajna12/reflex** — ①非自回归：是（非自回归决策头）；②基座/参数量：Qwen3.5；③需自训：是（需自训/提供权重）；④许可：MIT
- **daseinlabs/open-jev** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：未知
- **Heman10x-NGU/Verdict-open-jev** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：NOASSERTION
- **zhihz/openjev** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：NOASSERTION
- **Argos1111/jev_local** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：未知
- **mithalouni/system-one-open** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：NOASSERTION
- **IamBusy/OpenJev-Vision** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：Apache-2.0
- **genai-craft/openvons** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：NOASSERTION
- **abhixhek/jevcal** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **receptron/laya** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **intikhab49/open-jev-typed-decision-engine** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：Apache-2.0
- **alexj11324/open-jev-approvals** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **jlt-commons/lev** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：Apache-2.0
- **harrymunro/decision-first** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **ddfeyes/jev-mode** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **TypeSafeAI/clarity-judge** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：未知
- **yzfly/edgejev** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：NOASSERTION
- **apiplant/laya-rs** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：未知
- **jgridifier/jev-research-eval** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：NOASSERTION
- **aovestdipaperino/laya-rust** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：Apache-2.0
- **connectedGraph/claude-jev-warden** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **mkeco/Cerebellum-2B** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：NOASSERTION
- **DECRUX9812/openjev-lm** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：NOASSERTION
- **logicrw/ask-jev** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：GPL-3.0
- **sw-ml-study/demo-decision-model** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **UpHash-Network/mini-jev** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **syedabbasshaheer-art/jev-atlas** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **cyberumut/jev-bonsai-2-27B** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：NOASSERTION
- **m-ahmed-elbeskeri/verdict** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **fatihsoysalcom/non-autoregressive-decision-model-simulation** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **JonnyKreng/lidarr-decision-import** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：未知
- **allenporter/home-assistant-laya** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：Apache-2.0
- **shantanugoel/laya-plays-doom** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：未知
- **ian-cowley/Glacier.Clavier** — ①非自回归：是（非自回归决策头）；②基座/参数量：未知；③需自训：是（需自训/提供权重）；④许可：MIT
- **featherless-ai/simple-jev** — ①非自回归：否（借 LM 首 token logits）；②基座/参数量：未知；③需自训：否（依赖现成 LM）；④许可：未知
- **Yinsongxu/LLM2Jev** — ①非自回归：否（借 LM 首 token logits）；②基座/参数量：未知；③需自训：否（依赖现成 LM）；④许可：Apache-2.0
- **r-ms/mini-jev** — ①非自回归：否（借 LM 首 token logits）；②基座/参数量：未知；③需自训：否（依赖现成 LM）；④许可：MIT
- **Micha0827/snapjudge** — ①非自回归：否（借 LM 首 token logits）；②基座/参数量：未知；③需自训：否（依赖现成 LM）；④许可：MIT
- **codesoda/openjev-rs** — ①非自回归：否（借 LM 首 token logits）；②基座/参数量：未知；③需自训：否（依赖现成 LM）；④许可：MIT
- **Embodied-AI-System/Qwen3.5-OneForward** — ①非自回归：否（借 LM 首 token logits）；②基座/参数量：未知；③需自训：否（依赖现成 LM）；④许可：Apache-2.0
- **Wickypolineni/gemma-jev** — ①非自回归：否（借 LM 首 token logits）；②基座/参数量：未知；③需自训：否（依赖现成 LM）；④许可：未知
- **gopalanj/jevons** — ①非自回归：否（借 LM 首 token logits）；②基座/参数量：未知；③需自训：否（依赖现成 LM）；④许可：MIT
