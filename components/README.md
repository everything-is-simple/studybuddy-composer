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
