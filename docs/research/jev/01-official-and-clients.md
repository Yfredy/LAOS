# 01 · Jev 官方与客户端（SDK / MCP / Agent Skill）

> 列名逐字照抄 12 列 schema（口径文件 §7）。校验：`check_jev_table.py`。
> 关键判据：官方/客户端封装 TypeSafe 云端 API，中国大陆未开放，
> **laos_fit 一律 unrelated**（违反本地优先，不得作运行时依赖）。

| 项目 | 类别 | 星数 | 语言 | 许可 | 运行时依赖 | 端侧可跑 | 原语 | 报告延迟 | laos 落点 | 验证状态 | 来源 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| browser-use/jev-ultrafast | 客户端 | 11101 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（官方云端 API） | 仅README | https://github.com/browser-use/jev-ultrafast |
| typesafe-ai/skills | 官方 | 1022 | 未知 | MIT | 云端API | no | 组合 | 未实测 | 不值得（官方云端 API） | 仅README | https://github.com/typesafe-ai/skills |
| tinystruct/tinystruct | 客户端 | 354 | Java | Apache-2.0 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/tinystruct/tinystruct |
| dabit3/jev-experiments | 客户端 | 328 | TypeScript | 未知 | 云端API | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/dabit3/jev-experiments |
| wy-coliney/jev-browser-use | 客户端 | 240 | JavaScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/wy-coliney/jev-browser-use |
| rokbenko/quackd | 客户端 | 218 | Python | Apache-2.0 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/rokbenko/quackd |
| kitze/skillbox | 客户端 | 213 | TypeScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/kitze/skillbox |
| typesafe-ai/system-one-adapter-python | 官方 | 192 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（官方云端 API） | 仅README | https://github.com/typesafe-ai/system-one-adapter-python |
| jkudish/jev-browser | 客户端 | 179 | TypeScript | MIT | 云端API | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/jkudish/jev-browser |
| NiazMorshed2007/jev-review | 客户端 | 178 | TypeScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/NiazMorshed2007/jev-review |
| typesafe-ai/typesafe-sdk-js | 官方 | 178 | TypeScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（官方云端 API） | 仅README | https://github.com/typesafe-ai/typesafe-sdk-js |
| jkudish/jev-mcp | 客户端 | 147 | TypeScript | MIT | 云端API | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/jkudish/jev-mcp |
| typesafe-ai/typesafe-sdk-python | 官方 | 145 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（官方云端 API） | 仅README | https://github.com/typesafe-ai/typesafe-sdk-python |
| itsmostafa/typesafe-mcp | 客户端 | 131 | Go | MIT | 云端API | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/itsmostafa/typesafe-mcp |
| dbreunig/building-with-jev-skill | 客户端 | 124 | 未知 | 未知 | 云端API | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/dbreunig/building-with-jev-skill |
| wuyoscar/jev-skill | 客户端 | 103 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/wuyoscar/jev-skill |
| qiz029/dscode | 客户端 | 100 | JavaScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/qiz029/dscode |
| pithings/advocaat | 客户端 | 85 | TypeScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/pithings/advocaat |
| obie/ruby_decision_model | 客户端 | 46 | Ruby | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/obie/ruby_decision_model |
| kbhuw/jev-sift | 客户端 | 45 | JavaScript | 未知 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/kbhuw/jev-sift |
| Ying-Kai-Liao/jev-browser | 客户端 | 44 | JavaScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/Ying-Kai-Liao/jev-browser |
| shantanugoel/ask-jev-skill | 客户端 | 35 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/shantanugoel/ask-jev-skill |
| tacticocc/Jevbridge | 客户端 | 30 | TypeScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/tacticocc/Jevbridge |
| burnigtm/jev-mcp | 客户端 | 26 | TypeScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/burnigtm/jev-mcp |
| wundercorp/loki | 客户端 | 26 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/wundercorp/loki |
| SAGAR-TAMANG/sarvam-jev | 客户端 | 23 | Python | 未知 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/SAGAR-TAMANG/sarvam-jev |
| jevinskie/jevxpctrace | 客户端 | 20 | Objective-C | BSD-2-Clause | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/jevinskie/jevxpctrace |
| AkashPriyadarshii/jev-seo | 客户端 | 16 | Rust | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/AkashPriyadarshii/jev-seo |
| CheshiAI/Cheshi | 客户端 | 16 | C | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/CheshiAI/Cheshi |
| win4r/jev-skill-suggester | 客户端 | 14 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/win4r/jev-skill-suggester |
| blakestone-x/jev-mcp | 客户端 | 14 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/blakestone-x/jev-mcp |
| Brainwires/jevwire | 客户端 | 13 | TypeScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/Brainwires/jevwire |
| utk2103/jev-studio | 客户端 | 11 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/utk2103/jev-studio |
| shitianfang/jev-use | 客户端 | 10 | JavaScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/shitianfang/jev-use |
| GodsBoy/jev-agent-skill-router | 客户端 | 9 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/GodsBoy/jev-agent-skill-router |
| NSStudent/JevSwiftSDK | 客户端 | 7 | Swift | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/NSStudent/JevSwiftSDK |
| win4r/jev-security-scan | 客户端 | 7 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/win4r/jev-security-scan |
| danvega/jev-spring-boot-starter | 客户端 | 7 | Java | 未知 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/danvega/jev-spring-boot-starter |
| inso1337/revl | 客户端 | 7 | Python | AGPL-3.0 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/inso1337/revl |
| captain-corgi/typesafe-sdk-go | 客户端 | 7 | Go | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/captain-corgi/typesafe-sdk-go |
| ticofab/scala-jev-sdk | 客户端 | 6 | Scala | Apache-2.0 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/ticofab/scala-jev-sdk |
| jiawei686/jev-ultrafast-mcp | 客户端 | 6 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/jiawei686/jev-ultrafast-mcp |
| arunav25/jev-mcp | 客户端 | 5 | JavaScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/arunav25/jev-mcp |
| safzanpirani/pi-jev-skill-picker | 客户端 | 5 | TypeScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/safzanpirani/pi-jev-skill-picker |
| saibimajdi/typesafeai-dotnet-sdk | 客户端 | 5 | C# | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/saibimajdi/typesafeai-dotnet-sdk |
| docxology/daf-jev | 客户端 | 4 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/docxology/daf-jev |
| rashedInt32/jev-mcp | 客户端 | 4 | TypeScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/rashedInt32/jev-mcp |
| himomohi/aside-jev | 客户端 | 4 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/himomohi/aside-jev |
| xingwudao/OpenJev | 客户端 | 4 | Python | 未知 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/xingwudao/OpenJev |
| NiazMorshed2007/jcr | 客户端 | 4 | JavaScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/NiazMorshed2007/jcr |
| shaharia-lab/jev-cli | 客户端 | 3 | Rust | Apache-2.0 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/shaharia-lab/jev-cli |
| Premo-Cloud/typesafe-sdk-java | 客户端 | 3 | Java | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/Premo-Cloud/typesafe-sdk-java |
| ChosenXu/newsletter-link-harvester | 客户端 | 3 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/ChosenXu/newsletter-link-harvester |
| nshkrdotcom/typesafe_sdk | 客户端 | 3 | Elixir | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/nshkrdotcom/typesafe_sdk |
| TimothyZhang7/open-decisions | 客户端 | 3 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/TimothyZhang7/open-decisions |
| tontoko/jev-browser | 客户端 | 2 | JavaScript | Apache-2.0 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/tontoko/jev-browser |
| ShivamPansuriya/jev-skill-gate | 客户端 | 2 | JavaScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/ShivamPansuriya/jev-skill-gate |
| AboveColin/jevclient | 客户端 | 2 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/AboveColin/jevclient |
| gudcks0305/jev-java | 客户端 | 2 | Java | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/gudcks0305/jev-java |
| mzainzulifqar/jev-php-sdk | 客户端 | 2 | PHP | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/mzainzulifqar/jev-php-sdk |
| simota/tenbin | 客户端 | 2 | TypeScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/simota/tenbin |
| omkarghugarkar007/actiongate-jev | 客户端 | 2 | TypeScript | Apache-2.0 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/omkarghugarkar007/actiongate-jev |
| drowzeys/keys-MiniMax-Code-CLI-Browser-Scroll-Context-Enhancement-Pack-with-Jev-Ultrafast-Integration | 客户端 | 2 | Python | 未知 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/drowzeys/keys-MiniMax-Code-CLI-Browser-Scroll-Context-Enhancement-Pack-with-Jev-Ultrafast-Integration |
| Barneyjm/decision-circuits | 客户端 | 1 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/Barneyjm/decision-circuits |
| kierandotai/jev-client | 客户端 | 1 | TypeScript | 未知 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/kierandotai/jev-client |
| fraserxu/node-decision-model | 客户端 | 1 | TypeScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/fraserxu/node-decision-model |
| khalilelghoul01/decision-lab | 客户端 | 1 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/khalilelghoul01/decision-lab |
| zurfyx/jev-browser-skill-demo | 客户端 | 1 | JavaScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/zurfyx/jev-browser-skill-demo |
| shkumbinhasani/typedecide | 客户端 | 1 | TypeScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/shkumbinhasani/typedecide |
| Mandrilsquad1441/jev-model-router | 客户端 | 1 | TypeScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/Mandrilsquad1441/jev-model-router |
| kisshan13/typesafe-ai-go | 客户端 | 1 | Go | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/kisshan13/typesafe-ai-go |
| LeddoEngano/jev-eyes | 客户端 | 1 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/LeddoEngano/jev-eyes |
| Wang-auspicious/codex-jev-compaction | 客户端 | 1 | JavaScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/Wang-auspicious/codex-jev-compaction |
| zhirschtritt/typesafe-go | 客户端 | 1 | Go | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/zhirschtritt/typesafe-go |
| lazniak/jevskill | 客户端 | 1 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/lazniak/jevskill |
| reiswaffel78/jev-agent-toolkit | 客户端 | 1 | JavaScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/reiswaffel78/jev-agent-toolkit |
| brnyxx/jev-ra | 客户端 | 1 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/brnyxx/jev-ra |
| unimtx/typesafe-sdk-go | 客户端 | 1 | Go | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/unimtx/typesafe-sdk-go |
| edwardyen724-g/jev-compactor | 客户端 | 1 | TypeScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/edwardyen724-g/jev-compactor |
| FrancoisChastel/jev-code | 客户端 | 1 | TypeScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/FrancoisChastel/jev-code |
| yibie/pi-jev-browser | 客户端 | 1 | TypeScript | Apache-2.0 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/yibie/pi-jev-browser |
| lukeramsden/system-one | 客户端 | 0 | TypeScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/lukeramsden/system-one |
| nshkrdotcom/system_one_sdk | 客户端 | 0 | Elixir | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/nshkrdotcom/system_one_sdk |
| SC0d3r/jev-systemone | 客户端 | 0 | TypeScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/SC0d3r/jev-systemone |
| codaaiteam/jev-mcp | 客户端 | 0 | JavaScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/codaaiteam/jev-mcp |
| Perferic/openjev-mcp | 客户端 | 0 | 未知 | 未知 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/Perferic/openjev-mcp |
| api-evangelist/typesafe-ai | 客户端 | 0 | 未知 | 未知 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/api-evangelist/typesafe-ai |
| ninthspace/hunch | 客户端 | 0 | PHP | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/ninthspace/hunch |
| tanishqnalloju/typesafe-rust-sdk | 客户端 | 0 | Rust | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/tanishqnalloju/typesafe-rust-sdk |
| Chris-Crimi/seacat-python | 客户端 | 0 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/Chris-Crimi/seacat-python |
| MokiMeow/jev-fabric | 客户端 | 0 | TypeScript | Apache-2.0 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/MokiMeow/jev-fabric |
| Chris-Crimi/seacat-js | 客户端 | 0 | JavaScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/Chris-Crimi/seacat-js |
| hraness/sys1 | 客户端 | 0 | TypeScript | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/hraness/sys1 |
| FelineStateMachine/typesafe-go | 客户端 | 0 | Go | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/FelineStateMachine/typesafe-go |
| jerepaira/local-jev | 客户端 | 0 | Python | 未知 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/jerepaira/local-jev |
| Barba-Tech-CO/jev-claude-skill | 客户端 | 0 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/Barba-Tech-CO/jev-claude-skill |
| aashirsohail104/lead-desk | 客户端 | 0 | Python | 未知 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/aashirsohail104/lead-desk |
| omauser119/JaxModels | 客户端 | 0 | Python | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/omauser119/JaxModels |
| lengoman/laya-go | 客户端 | 0 | Go | Apache-2.0 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/lengoman/laya-go |
| jevbook/jevbook-mcp | 客户端 | 0 | 未知 | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/jevbook/jevbook-mcp |
| milfordai/milford | 客户端 | 0 | TypeScript | Apache-2.0 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/milfordai/milford |
| essabu/toli-php | 客户端 | 0 | PHP | 未知 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/essabu/toli-php |
| essabu/toli-python | 客户端 | 0 | Python | 未知 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/essabu/toli-python |
| essabu/toli-ts | 客户端 | 0 | TypeScript | 未知 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/essabu/toli-ts |
| nathanmauro/black-box | 客户端 | 0 | Java | MIT | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/nathanmauro/black-box |
| shmindmaster/assay | 客户端 | 0 | JavaScript | Apache-2.0 | 未知 | no | 组合 | 未实测 | 不值得（云端 API 封装） | 仅README | https://github.com/shmindmaster/assay |
