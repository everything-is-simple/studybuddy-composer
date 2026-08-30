# StudyBuddy Composer

组件与参考系统试炼场，不是正式产品源码。

## 目录职责

- `references/`：借鉴系统的本地路径登记、版本、许可证和借鉴范围。
- `components/`：组件能力卡、独立 smoke test、输入输出契约和失败边界。
- `manifests/`：组件状态清单，只有真实测试通过才允许进入 integration。
- `results/`：可再生测试结果，不进入正式仓库。
- `manifests/b0-catalog.json`：B0 四类能力候选的机器可读 intake 清单；当前为 1 个 `smoke_passed`（ASR）和 8 个 `researching`，未有候选进入 Integration。
- `B0-COMPONENT-GOVERNANCE.md`：统一 component card、smoke、隐私、资源、网络和状态晋级规则。

## B0 当前状态

B0 governance scaffold 已建立，覆盖 ASR、OCR、report、delivery 四类候选及统一证据字段。C0 已选 `H:/WhisperCli`/whisper.cpp `large-v3-turbo` 为唯一 ASR runtime、PaddleOCR 为主 OCR、RapidOCR ONNX 为轻量回退；`DECISIONS/STUDYBUDDY_MEDIA_CAPABILITIES.md` 记录 edge-tts 与 PPTX 三层路径。当前选定的 whisper.cpp ASR 候选已通过独立 C1 smoke（合成静音 WAV、坏输入、边界输出、超时配置和清理证据）；OCR、报告和外发候选仍未通过 C1，且没有候选通过 Integration，因此没有新增正式系统可集成组件。C1 仅证明精确本机 runtime/模型和测试 fixture 范围，不构成准确率、Integration 或 Formal 结论。

机器可读清单：`manifests/b0-catalog.json`；治理说明：`B0-COMPONENT-GOVERNANCE.md`。

## 装配门禁

1. 组件来源和许可证可确认。
2. 独立 smoke test 使用真实组件通过。
3. `COMPONENT-CARD.md` 写清版本、命令、输入、输出、限制和资源消耗。
4. 没有真实通过证据，不得写入 `H:\studybuddy-integration`。
5. Composer 代码不得被主系统 import；主系统必须重新实现 Adapter 或明确采用依赖。

允许登记和试炼的对象包括：KaoBuddy、ai-studybuddy、pi-studybuddy、PDF/DOCX/PPTX 解析、RapidOCR、whisper.cpp、SQLite、QQ SMTP、飞书 Webhook 和 OpenAI-compatible provider。

禁止保存：真实 API Key、Webhook、SMTP 授权码、完整学生资料、生产数据库、完整会话输出。
