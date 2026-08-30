# Component Cards

每个子目录或组件登记必须包含 `COMPONENT-CARD.md`，并记录：

- 来源与许可证；
- 固定版本；
- 独立测试命令；
- 真实输入与输出契约；
- 失败边界；
- Windows 依赖；
- 资源消耗；
- 隐私和日志限制；
- 进入 integration 的结果。

状态只允许：`researching`、`smoke_passed`、`integration_passed`、`rejected`。
`smoke_passed` 之前不得装配，`integration_passed` 之前不得进入主系统。


B0 intake 约束：候选必须同时存在于 `../manifests/b0-catalog.json` 和自己的 `COMPONENT-CARD.md`；`researching` 只能表示待审计，不代表可用。独立 smoke 结果必须是脱敏、可重跑的 artifact，且不得把真实外部服务、真实收件人、真实 webhook 或真实学习材料作为默认目标。
