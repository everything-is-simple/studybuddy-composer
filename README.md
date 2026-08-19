# StudyBuddy Composer

组件与参考系统试炼场，不是正式产品源码。

## 目录职责

- `references/`：借鉴系统的本地路径登记、版本、许可证和借鉴范围。
- `components/`：组件能力卡、独立 smoke test、输入输出契约和失败边界。
- `manifests/`：组件状态清单，只有真实测试通过才允许进入 integration。
- `results/`：可再生测试结果，不进入正式仓库。

## 装配门禁

1. 组件来源和许可证可确认。
2. 独立 smoke test 使用真实组件通过。
3. `COMPONENT-CARD.md` 写清版本、命令、输入、输出、限制和资源消耗。
4. 没有真实通过证据，不得写入 `H:\studybuddy-integration`。
5. Composer 代码不得被主系统 import；主系统必须重新实现 Adapter 或明确采用依赖。

允许登记和试炼的对象包括：KaoBuddy、ai-studybuddy、pi-studybuddy、PDF/DOCX/PPTX 解析、RapidOCR、whisper.cpp、SQLite、QQ SMTP、飞书 Webhook 和 OpenAI-compatible provider。

禁止保存：真实 API Key、Webhook、SMTP 授权码、完整学生资料、生产数据库、完整会话输出。
